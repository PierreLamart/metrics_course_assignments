"""Metrics requiring predictions, telemetry, labels, or vendor measurements.

None of these inputs can be inferred reliably from a Git source snapshot.
This module consumes explicit data and never fabricates missing observations.
"""
from __future__ import annotations
from bisect import bisect_left, bisect_right
from collections import Counter
from math import sqrt
from statistics import fmean
from typing import Callable, Sequence
from time import perf_counter_ns
from .formulas import (ai_ratio, finite, new1, nonnegative_int, ratio,
                       raw_hybrid_complexity, rocr, software_health)


def agreement(a: Sequence, b: Sequence) -> dict:
    if len(a) != len(b):
        raise ValueError("Rater arrays must have equal lengths")
    n = len(a)
    if not n:
        return {"percentage_agreement": None, "cohens_kappa": None, "n": 0}
    ca, cb = Counter(a), Counter(b)
    observed = sum(x == y for x, y in zip(a, b)) / n
    expected = sum(ca[x] * cb[x] for x in ca.keys() | cb.keys()) / (n * n)
    return {"percentage_agreement": 100 * observed,
            "cohens_kappa": ratio(observed - expected, 1 - expected), "n": n}


def binary_counts(true: Sequence, predicted: Sequence, positive=1) -> tuple[int, int, int, int]:
    if len(true) != len(predicted):
        raise ValueError("Truth and prediction arrays have different lengths")
    tp = tn = fp = fn = 0
    for a, b in zip(true, predicted):
        if a == positive:
            if b == positive: tp += 1
            else: fn += 1
        elif b == positive: fp += 1
        else: tn += 1
    return tp, tn, fp, fn


def confusion_metrics(tp: int, tn: int, fp: int, fn: int) -> dict:
    for name, value in (("tp", tp), ("tn", tn), ("fp", fp), ("fn", fn)):
        nonnegative_int(value, name)
    den = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    return {"tp": tp, "tn": tn, "fp": fp, "fn": fn,
            "accuracy": ratio(tp + tn, tp + tn + fp + fn),
            "precision": ratio(tp, tp + fp), "recall": ratio(tp, tp + fn),
            "specificity": ratio(tn, tn + fp),
            # Algebraic confusion-matrix form. Undefined only if denominator 0.
            "f1": ratio(2 * tp, 2 * tp + fp + fn),
            "mcc": (tp * tn - fp * fn) / sqrt(den) if den else None}


def auc(true: Sequence, scores: Sequence[float], positive=1, *, tie_credit: float = 0.0) -> float | None:
    """P3 Eq.18 default: strict greater-than, ties get zero credit.

    tie_credit=0.5 is an explicit alternative convention, not substituted
    silently for the paper's expression. O(n log n), not a quadratic matrix.
    """
    if len(true) != len(scores):
        raise ValueError("Truth and score arrays have different lengths")
    tie_credit = finite(tie_credit, "tie_credit", 0, 1)
    values = [finite(x, "score") for x in scores]
    neg = sorted(s for y, s in zip(true, values) if y != positive)
    pos = [s for y, s in zip(true, values) if y == positive]
    if not neg or not pos:
        return None
    total = 0.0
    for s in pos:
        below, through = bisect_left(neg, s), bisect_right(neg, s)
        total += below + tie_credit * (through - below)
    return total / (len(pos) * len(neg))


def classification(data: dict) -> dict:
    true = data["y_true"]
    scores = data.get("probabilities")
    pred = data.get("y_pred")
    positive = data.get("positive_label", 1)
    if scores is not None:
        scores = [finite(x, "probability", 0, 1) for x in scores]
        if len(scores) != len(true):
            raise ValueError("Probability count differs from label count")
    if pred is None:
        if scores is None or set(true) - {0, 1}:
            raise ValueError("y_pred is required except for binary 0/1 probability input")
        if positive != 1:
            raise ValueError("Automatic probability thresholding requires positive_label=1")
        threshold = finite(data.get("threshold", 0.5), "threshold", 0, 1)
        pred = [int(s >= threshold) for s in scores]
    if len(pred) != len(true):
        raise ValueError("Truth and prediction arrays have different lengths")
    labels = sorted(set(true) | set(pred), key=str)
    result = {"n": len(true), "accuracy": ratio(sum(x == y for x, y in zip(true, pred)), len(true)),
              "cohens_kappa": agreement(true, pred)["cohens_kappa"],
              "per_class": [{"label": label, **confusion_metrics(*binary_counts(true, pred, label))}
                            for label in labels]}
    if len(labels) <= 2:
        if labels and positive not in labels and set(labels) - {0, 1}:
            raise ValueError("Specify positive_label for nonnumeric binary labels")
        result["binary"] = confusion_metrics(*binary_counts(true, pred, positive))
        if scores is not None:
            credit = data.get("auc_tie_credit", 0.0)
            result["binary"].update({"auc": auc(true, scores, positive, tie_credit=credit),
                "auc_tie_credit": credit,
                "rmse": sqrt(fmean((int(y == positive) - p) ** 2 for y, p in zip(true, scores))) if true else None})
    elif scores is not None:
        raise ValueError("Scalar probabilities are only accepted for binary classification")
    return result


def mean_average_precision(ap_by_iou: dict[str, dict[str, float]]) -> dict:
    """P5 averaging operations; AP itself must be supplied by a detector evaluator.

    The paper does not specify AP interpolation, matching, or confidence rules.
    This function intentionally does not choose them on the user's behalf.
    """
    values = {round(float(k), 2): {name: finite(v, "AP", 0, 1) for name, v in row.items()}
              for k, row in ap_by_iou.items()}
    if len(values) != len(ap_by_iou):
        raise ValueError("Duplicate IoU keys after normalization")
    def at(t: float):
        row = values.get(t, {})
        return fmean(row.values()) if row else None
    thresholds = [round(0.50 + 0.05 * i, 2) for i in range(10)]
    class_sets = [set(values.get(t, {})) for t in thresholds]
    complete = bool(class_sets[0]) and all(x == class_sets[0] for x in class_sets)
    return {"map_50": at(0.5),
            "map_50_95": fmean(at(t) for t in thresholds) if complete else None,
            "ap_thresholds_complete_and_same_classes": complete,
            "missing_iou_thresholds": [t for t in thresholds if not values.get(t)],
            "input_requirement": "AP values from a separately configured detection evaluator"}


def runtime_metrics(records: list[dict]) -> dict:
    total_images, elapsed, memory = 0, 0.0, []
    for row in records:
        count = nonnegative_int(row["images"], "images")
        if count == 0:
            raise ValueError("A timed inference record must contain at least one image")
        total_images += count
        elapsed += finite(row["elapsed_ms"], "elapsed_ms", 0)
        if "gpu_memory_mb" in row:
            memory.append(finite(row["gpu_memory_mb"], "gpu_memory_mb", 0))
    return {"latency_ms_per_image": ratio(elapsed, total_images), "images": total_images,
            "gpu_memory_mb_samples": len(memory),
            "gpu_memory_mb_mean": fmean(memory) if memory else None,
            "gpu_memory_mb_max_observed": max(memory) if memory else None,
            "gpu_memory_note": "Observed telemetry samples; not automatically a device-wide peak"}


def benchmark_inference(function: Callable[[], object], *, iterations: int = 20,
                        warmup: int = 5, images_per_call: int = 1,
                        synchronize: Callable[[], None] | None = None,
                        gpu_memory_mb: Callable[[], float] | None = None) -> dict:
    """Opt-in API: run a caller-provided function; scan never invokes this.

    For asynchronous accelerators provide a synchronization callback. GPU
    memory is measured only when an appropriate device-specific reader is
    explicitly supplied; process RSS is never substituted for GPU memory.
    """
    for name, value in (("iterations", iterations), ("warmup", warmup), ("images_per_call", images_per_call)):
        nonnegative_int(value, name)
    if not iterations or not images_per_call:
        raise ValueError("iterations and images_per_call must be positive")
    for _ in range(warmup):
        function()
    records = []
    for _ in range(iterations):
        if synchronize: synchronize()
        start = perf_counter_ns()
        result = function()  # keep result alive until memory is sampled
        if synchronize: synchronize()
        elapsed = (perf_counter_ns() - start) / 1_000_000
        row = {"images": images_per_call, "elapsed_ms": elapsed}
        if gpu_memory_mb: row["gpu_memory_mb"] = gpu_memory_mb()
        records.append(row)
        del result
    return {"records": records, "metrics": runtime_metrics(records)}


def test_execution(data: dict) -> dict:
    tests = data["tests"]
    identifiers = [row["id"] for row in tests]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("Duplicate test IDs")
    observed = set().union(*(set(t.get("faults", [])) for t in tests))
    known = set(data.get("fault_universe", observed))
    if not observed <= known:
        raise ValueError("A test reports a fault outside fault_universe")
    durations = [finite(t["duration_ms"], "duration_ms", 0) for t in tests]
    seen, first_cover, cover_time = set(), None, None
    elapsed = 0.0
    for i, (t, duration) in enumerate(zip(tests, durations), 1):
        elapsed += duration
        seen.update(t.get("faults", []))
        if known and first_cover is None and known <= seen:
            first_cover, cover_time = i, elapsed
    return {"test_execution_time_ms": sum(durations), "test_count": len(tests),
            "suite_percentage_to_cover_all_faults": 100 * first_cover / len(tests) if first_cover else None,
            "tests_to_cover_all_faults": first_cover, "time_to_cover_all_faults_ms": cover_time,
            "fault_count": len(known), "uncovered_faults": sorted(known - seen, key=str),
            "fault_universe_source": "supplied" if "fault_universe" in data else "union_observed_in_full_suite"}


def evaluate(data: dict) -> dict:
    allowed = {"classification", "agreement", "detection_ap", "runtime", "test_execution", "risk",
               "ai_labels", "citation_ids", "hybrid", "io_format_ids", "smell_instances"}
    unknown = set(data) - allowed
    if unknown:
        raise ValueError(f"Unknown auxiliary sections: {sorted(unknown)}")
    out = {}
    if "classification" in data: out["classification"] = classification(data["classification"])
    if "agreement" in data: out["agreement"] = agreement(data["agreement"]["rater_a"], data["agreement"]["rater_b"])
    if "detection_ap" in data: out["detection"] = mean_average_precision(data["detection_ap"])
    if "runtime" in data: out["runtime"] = runtime_metrics(data["runtime"])
    if "test_execution" in data: out["test_execution"] = test_execution(data["test_execution"])
    if "risk" in data:
        rows = data["risk"]["components"]
        n = data["risk"].get("component_count", len(rows))
        out["risk"] = []
        for row in rows:
            record = {"id": row["id"], "software_health": software_health(row["sr"], row["sa"], row["se"]),
                      "rocr": rocr(row["sr"], row["sa"], row["se"], row["business_impact"], n)}
            if "highest_risk_file_ids" in row:
                record["highest_risk_file_count"] = len(set(row["highest_risk_file_ids"]))
            out["risk"].append(record)
    if "ai_labels" in data: out["ai"] = ai_ratio(data["ai_labels"])
    if "citation_ids" in data:
        out["citations"] = {"citation_count": len(set(data["citation_ids"])),
                            "note": "Deduplicate cross-provider work IDs before input"}
    if "io_format_ids" in data: out["io_formats"] = {"fomts": len(set(data["io_format_ids"]))}
    if "smell_instances" in data:
        instances = {(x["smell"], x["entity"]) for x in data["smell_instances"]}
        out["smells"] = {"count": len(instances), "by_type": dict(Counter(s for s, _ in instances))}
    if "hybrid" in data:
        h = data["hybrid"]
        raw = h.get("raw_complexities")
        if raw is None:
            raw = [raw_hybrid_complexity(x["N"], x["n"], h["L"], log_base=h["log_base"]) for x in h["nodes"]]
        adjusted = h["adjusted_complexities"]
        out["hybrid"] = {"raw_complexities": raw, "scope_sum_of_supplied_adjusted_complexities": sum(
            finite(x, "adjusted complexity", 0) for x in adjusted), "new1": new1(raw, adjusted),
            "note": "Scope membership/adjusted values are supplied, not inferred from source"}
    return out
