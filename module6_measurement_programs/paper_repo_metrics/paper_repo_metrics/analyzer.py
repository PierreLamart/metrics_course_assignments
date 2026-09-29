"""Coordinate source parsing, graph measurements, and repository reporting."""
from __future__ import annotations
import fnmatch
import hashlib
import io
import sys
import tokenize
from collections import Counter, defaultdict
from pathlib import Path
from statistics import fmean
from typing import Any
from . import __version__
from .design import load_design
from .evaluation import evaluate
from .formulas import halstead, maintainability_p9_literal, ratio
from .graphs import Builder, CFG, UnsupportedControlFlow, graph_metrics
from .java_frontend import analyze_java_batch
from .lexical import measure_lexical
from .model import measure_model
from .python_frontend import analyze_python
from .repository import DEFAULT_EXCLUDES, open_repository
from .smali_frontend import analyze_smali

API_METRICS = ["network_op", "fileio_op", "sqlite_op", "start_activity", "start_service",
               "start_intent_for_result", "start_activity_result", "log"]


def catalog() -> dict:
    import json
    return json.loads(Path(__file__).with_name("catalog.json").read_text(encoding="utf-8"))


def classify_apis(sites: list[dict], rules: dict | None) -> dict:
    counts = {name: None for name in API_METRICS}
    if rules is None:
        return {"counts": counts, "reason": "api_signature_rules_not_supplied",
                "call_sites_with_qualified_targets": sum(bool(s.get("api_target")) for s in sites)}
    unknown = set(rules) - set(API_METRICS)
    if unknown:
        raise ValueError(f"Unknown API rule metric names: {sorted(unknown)}")
    for name, patterns in rules.items():
        if not isinstance(patterns, list) or any(not isinstance(p, str) for p in patterns):
            raise ValueError("Each API metric rule must be a list of glob patterns")
        counts[name] = sum(bool(s.get("api_target")) and
                           (name != "log" or s.get("in_handler") is True) and
                           any(fnmatch.fnmatchcase(s["api_target"], p) for p in patterns) for s in sites)
    return {"counts": counts, "rules": rules, "scope": "Matched static invocation sites, not dynamic execution counts",
            "call_sites_with_qualified_targets": sum(bool(s.get("api_target")) for s in sites),
            "call_sites_without_qualified_targets": sum(not s.get("api_target") for s in sites),
            "note": "Registry is user-supplied; the AndroMetric PDF does not publish its exact API mapping"}


def strip_internal(entity: dict, keep_cfg: bool) -> dict:
    excluded = {"ir", "supplied_cfg", "start", "end", "local_types", "type_refs", "imports", "wildcard_imports"}
    if not keep_cfg:
        excluded.add("cfg")
    return {key: value for key, value in entity.items() if key not in excluded and not key.startswith("_")}


def analyze_repository(location: str, *, ref: str | None = None, include_untracked: bool = False,
                       exclude: list[str] | None = None, use_default_excludes: bool = True,
                       include_constructors: bool = False, k: float = 2.0, max_file_bytes: int = 2_000_000,
                       max_files: int = 10000, max_path_steps: int = 100000,
                       timeout: int = 120, keep_cfg: bool = False,
                       api_rules: dict | None = None, auxiliary: dict | None = None,
                       cfg_overrides: dict[str, dict] | None = None,
                       design_model: Path | None = None,
                       scope_branch_policy: str | None = None) -> dict:
    if max_file_bytes <= 0 or max_files <= 0 or max_path_steps <= 0 or timeout <= 0:
        raise ValueError("Resource limits must be positive")
    patterns = (list(DEFAULT_EXCLUDES) if use_default_excludes else []) + (exclude or [])
    records, source_text, parse_results = [], {}, {}
    operators, operands = Counter(), Counter()
    global_warnings = []
    with open_repository(location, ref=ref, include_untracked=include_untracked, timeout=timeout) as repo:
        metadata = repo.metadata()
        files_seen = 0
        for source in repo.sources(patterns, max_file_bytes):
            record: dict[str, Any] = {"path": source.path, "language": source.language}
            records.append(record)
            if source.reason:
                record.update({"status": "skipped", "reason": source.reason})
                continue
            files_seen += 1
            if files_seen > max_files:
                record.update({"status": "skipped", "reason": "file_count_limit"})
                continue
            assert source.data is not None
            record["sha256"] = hashlib.sha256(source.data).hexdigest()
            record["bytes"] = len(source.data)
            try:
                encoding = tokenize.detect_encoding(io.BytesIO(source.data).readline)[0] if source.language == "python" else "utf-8-sig"
                text = source.data.decode(encoding).replace("\r\n", "\n").replace("\r", "\n")
            except (UnicodeError, SyntaxError) as error:
                record.update({"status": "skipped", "reason": "decode_error", "detail": str(error)})
                continue
            source_text[source.path] = text
            record["encoding"] = encoding
            record["status"] = "measured"
            try:
                metrics, ops, opnds = measure_lexical(text, source.language)
                record["metrics"] = metrics
                record["lexical_status"] = "measured"
                operators.update(ops); operands.update(opnds)
            except (ValueError, tokenize.TokenError, IndentationError, SyntaxError) as error:
                record.update({"lexical_status": "unavailable", "lexical_error": str(error), "metrics": {}})
            if source.language != "java":
                try:
                    frontend = analyze_python if source.language == "python" else analyze_smali
                    parse_results[source.path] = frontend(source.path, text)
                except (ValueError, SyntaxError, RecursionError) as error:
                    parse_results[source.path] = {"parse_ok": False, "errors": [{"message": str(error)}],
                                                  "classes": [], "methods": []}
        java_sources = {r["path"]: source_text[r["path"]] for r in records
                        if r["language"] == "java" and r["path"] in source_text}
        java_version = "not_needed"
        if java_sources:
            try:
                # Batches bound javac memory without changing class ID generation.
                items = list(java_sources.items())
                for start in range(0, len(items), 200):
                    parsed, java_version = analyze_java_batch(dict(items[start:start + 200]), timeout=timeout)
                    parse_results.update(parsed)
            except (RuntimeError, ValueError) as error:
                global_warnings.append(str(error))
                for path in java_sources.keys() - parse_results.keys():
                    parse_results[path] = {"parse_ok": False, "errors": [{"message": str(error)}],
                                          "classes": [], "methods": []}

    classes, methods = [], []
    record_by_path = {r["path"]: r for r in records}
    for path, parsed in parse_results.items():
        record = record_by_path[path]
        if not parsed.get("parse_ok", False):
            record["structural_status"] = "unavailable"
            record["parse_errors"] = parsed.get("errors", [])
            continue
        record["structural_status"] = "measured"
        record["warnings"] = parsed.get("warnings", [])
        record["metrics"].update(parsed.get("metrics", {}))
        classes.extend(parsed["classes"]); methods.extend(parsed["methods"])
    overrides = cfg_overrides or {}
    unknown = set(overrides) - {m["id"] for m in methods}
    if unknown:
        raise ValueError("CFG overrides reference unknown method IDs: " + ", ".join(sorted(unknown)))
    for entity in classes + methods:
        try:
            region = source_text[entity["path"]][entity["start"]:entity["end"]]
            entity["metrics"] = measure_lexical(region, entity["language"])[0]
        except (ValueError, tokenize.TokenError, IndentationError, SyntaxError) as error:
            entity["metrics"] = {}
            entity["lexical_error"] = str(error)
    for m in methods:
        metrics = m["metrics"]
        for name in ("statements", "declarative_statements", "executable_statements",
                     "bytecode_instructions", "catch_handlers", "empty_catch_handlers"):
            if name in m:
                metrics[name] = m.pop(name)
        if m["id"] in overrides:
            graph = CFG.from_dict(overrides[m["id"]])
            metrics.update(graph_metrics(graph, max_path_steps))
            m["cfg"] = graph.to_dict(); m["cfg_origin"] = "user_supplied"
        elif not m.get("has_body"):
            metrics["cc"] = None; m["cfg_unavailable_reason"] = "declaration_without_body"
        elif m.get("cfg_unavailable_reason"):
            metrics["cc"] = None
        else:
            try:
                graph = CFG.from_dict(m["supplied_cfg"]) if "supplied_cfg" in m else Builder().build(m["ir"])
                metrics.update(graph_metrics(graph, max_path_steps))
                m["cfg"] = graph.to_dict(); m["cfg_origin"] = "frontend_normal_flow"
            except (UnsupportedControlFlow, ValueError, RecursionError) as error:
                metrics["cc"] = None; m["cfg_unavailable_reason"] = str(error)
        metrics.setdefault("binary_decisions", None)
        metrics.setdefault("npath_node_simple", None)
        metrics["relative_logical_complexity"] = ratio(metrics["binary_decisions"], metrics.get("executable_statements", 0)) if metrics["binary_decisions"] is not None else None
        cc = metrics.get("cc")
        metrics["cc_risk_band_p1"] = None if cc is None else (
            "low" if cc <= 10 else "moderate" if cc <= 20 else "high" if cc <= 50 else "very_high")

    linkage = measure_model(classes, methods, k=k, include_constructors=include_constructors)
    classes_by_file, methods_by_file = defaultdict(list), defaultdict(list)
    for c in classes:
        classes_by_file[c["path"]].append(c)
    for m in methods:
        methods_by_file[m["path"]].append(m)
    for record in records:
        if record.get("structural_status") != "measured":
            continue
        path, metrics = record["path"], record["metrics"]
        cs, ms_all = classes_by_file[path], methods_by_file[path]
        ms = [m for m in ms_all if include_constructors or not m.get("constructor")]
        concretes = [m for m in ms if m.get("has_body")]
        values = [m["metrics"].get("cc") for m in concretes]
        metrics.update({"class_count": sum(c["kind"] == "class" for c in cs),
                        "interface_count": sum(c["kind"] == "interface" for c in cs),
                        "unit_count": len(ms), "method_count": sum(bool(m.get("owner")) for m in ms),
                        "sum_cyclomatic": sum(values) if all(v is not None for v in values) else None,
                        "sum_cyclomatic_measured_lower_bound": sum(v for v in values if v is not None),
                        "statements_per_unit": ratio(metrics.get("executable_statements", 0), len(ms)) if "executable_statements" in metrics else None})
        for key in ("catch_handlers", "empty_catch_handlers"):
            vals = [m["metrics"].get(key) for m in ms_all]
            metrics[key] = sum(vals) if all(v is not None for v in vals) else None
        if record["language"] == "smali":
            metrics["bytecode_per_method"] = ratio(metrics["bytecode_instructions"], len(ms_all))
            metrics["bytecode_method_population_includes_constructors"] = True
        volume, com, cc = metrics.get("halstead_volume"), metrics.get("comment_percentage"), metrics.get("sum_cyclomatic")
        metrics["mi_p9_literal"] = maintainability_p9_literal(volume, cc, metrics["loc"], com) if None not in (volume, com, cc) else None
    for c in classes:
        metrics = c["metrics"]
        volume, com, cc = metrics.get("halstead_volume"), metrics.get("comment_percentage"), metrics.get("wmc")
        metrics["mi_p9_literal"] = maintainability_p9_literal(volume, cc, metrics["loc"], com) if None not in (volume, com, cc) else None

    lexical_files = [r for r in records if r.get("lexical_status") == "measured"]
    structural_files = [r for r in records if r.get("structural_status") == "measured"]
    selected_records = [r for r in records if r.get("reason") != "excluded_by_pattern"]
    project = {"scope": "successfully_measured_subset; inspect coverage before comparing repositories",
               "file_count": len(lexical_files), "structurally_measured_file_count": len(structural_files)}
    for key in ("total_lines", "blank_lines", "loc", "comment_lines", "comment_only_lines", "mixed_code_comment_lines", "lines_without_comment_only"):
        project[key] = sum(r["metrics"].get(key, 0) for r in lexical_files)
    project["comment_to_code_ratio"] = ratio(project["comment_lines"], project["loc"])
    project["comment_percentage_ratio_of_totals"] = 100 * project["comment_lines"] / project["loc"] if project["loc"] else None
    percentages = [r["metrics"]["comment_percentage"] for r in lexical_files]
    project["p9_sum_file_comment_percentages"] = sum(percentages) if all(v is not None for v in percentages) else None
    project["halstead_combined_token_stream"] = halstead(operators, operands)
    project["halstead_combined_token_stream_languages"] = ["python", "java"]
    project["sum_file_halstead_volumes"] = sum(r["metrics"].get("halstead_volume", 0) for r in lexical_files)
    for key in ("class_count", "interface_count", "method_count", "unit_count", "statements",
                "declarative_statements", "executable_statements", "bytecode_instructions"):
        applicable = [r["metrics"][key] for r in structural_files if key in r["metrics"]]
        project[key] = sum(applicable) if applicable else None
    class_method_count = sum(c["metrics"]["method_count"] for c in classes if c["kind"] == "class")
    project["methods_per_class"] = ratio(class_method_count, project["class_count"] or 0)
    project["statements_per_unit"] = ratio(project["executable_statements"], project["unit_count"] or 0) if project["executable_statements"] is not None else None
    cc_values = [r["metrics"].get("sum_cyclomatic") for r in structural_files]
    project["sum_cyclomatic"] = sum(cc_values) if all(v is not None for v in cc_values) else None
    project["sum_cyclomatic_measured_lower_bound"] = sum(r["metrics"].get("sum_cyclomatic_measured_lower_bound", 0) for r in structural_files)
    smali_methods = [m for m in methods if m["language"] == "smali"]
    project["bytecode_per_method"] = ratio(project["bytecode_instructions"] or 0, len(smali_methods))
    project["class_metric_summaries"] = {}
    for key in sorted({key for c in classes for key in c["metrics"]}):
        values = [c["metrics"].get(key) for c in classes]
        nums = [v for v in values if isinstance(v, (float, int)) and not isinstance(v, bool)]
        if nums:
            project["class_metric_summaries"][key] = {"measured": len(nums), "unavailable": len(values) - len(nums),
                                                      "sum": sum(nums), "mean": fmean(nums), "max": max(nums)}
    result = {
        "schema_version": "1.0", "tool_version": __version__, "repository": metadata,
        "measurement_policies": {"python_version": sys.version.split()[0], "java_version": java_version,
            "source_languages": ["python", "java", "smali"], "exclude_patterns": patterns,
            "include_explicit_constructors_in_source_method_metrics": include_constructors,
            "k_rcim": k, "hierarchy_root_depth": 0, "implicit_root_object_excluded": True,
            "line_policy": "physical nonblank code-bearing lines; comments and mixed lines counted separately; Python docstrings are literals",
            "halstead_policy": "lexical-v1; see docs/MEASUREMENT_POLICIES.md",
            "cc_policy": "E-N+2P on reachable normal-flow CFG; short-circuit conditions expanded; unsupported flow -> null",
            "npath_policy": "node-simple entry-exit paths; NOT asserted identical to original Nejmeh implementation",
            "lcom_policy": "P9 Table 2 literal: (sum(mu)-m)/(a*(1-m))",
            "mi_policy": "P9 Table 2 literal: sqrt(246*COM); natural logarithms; no clipping",
            "default_visibility_policy": "Java/Smali package/default access, NOT Java interface default keyword; unavailable for Python",
            "association_policy": "No source-level association inference; supply UML/normalized design model",
            "coupling_policy": "Symmetric union of resolved declared-type uses and calls; inheritance-only edges excluded",
            "callgraph_policy": "Conservative syntactic static targets; *_resolved counts exclude ambiguous calls; no runtime dispatch claim",
            "class_count_policy": "Named classes including enums/records; interfaces counted separately",
            "max_path_steps": max_path_steps, "max_file_bytes": max_file_bytes},
        "coverage": {"source_candidate_files": len(records), "selected_source_files": len(selected_records),
            "excluded_files": len(records) - len(selected_records), "lexically_measured_files": len(lexical_files),
            "structurally_measured_files": len(structural_files),
            "full_structural_coverage_of_selected_files": len(structural_files) == len(selected_records),
            "callables_with_bodies": sum(m.get("has_body", False) for m in methods),
            "callables_with_cc": sum(m["metrics"].get("cc") is not None for m in methods),
            "unresolved_call_sites": len(linkage["unresolved_calls"]),
            "skipped_reason_counts": dict(Counter(r["reason"] for r in records if "reason" in r))},
        "project": project, "files": records,
        "classes": [strip_internal(c, keep_cfg) for c in classes],
        "methods": [strip_internal(m, keep_cfg) for m in methods],
        "call_graph": linkage, "api_usage": classify_apis(linkage["invocation_sites"], api_rules),
        "warnings": global_warnings,
        "unavailable_or_external_input_metrics": catalog()["not_automatically_measured"],
    }
    if auxiliary is not None:
        result["auxiliary_metrics"] = evaluate(auxiliary)
    if design_model is not None:
        result["design_model_metrics"] = load_design(design_model, scope_branch_policy)
    return result
