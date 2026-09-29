"""Pure functions for formulas actually given in the uploaded papers.

P1: Kataieva & Nemec. P2: Rahman et al. P3: LSTM-CNN. P4: RSEMM.
P5: Oil palm detection. P7: UML defect prediction. P8: NASA study.
P9: IoT comparison. P10: risk-based testing.

None means mathematically undefined, unavailable, or not measured -- never zero.
LCOM and MI preserve P9's *printed* expressions, not textbook replacements.
"""
from __future__ import annotations

from collections import Counter
from math import isfinite, log, log2, log10, sin, sqrt
from statistics import fmean, pstdev
from typing import Iterable, Mapping, Sequence

Number = int | float


def finite(value: Number, name: str, minimum: float | None = None,
           maximum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number, not {type(value).__name__}")
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{name} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")
    return value


def nonnegative_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")
    return value


def ratio(numerator: Number, denominator: Number) -> float | None:
    return numerator / denominator if denominator else None


def halstead(operators: Mapping[str, int], operands: Mapping[str, int]) -> dict:
    """P9 Table 2 and P8 token primitives. No unprovided D/I/E/B/T formula."""
    for counts in (operators, operands):
        for token, count in counts.items():
            nonnegative_int(count, f"count for {token!r}")
    n1 = sum(v > 0 for v in operators.values())
    n2 = sum(v > 0 for v in operands.values())
    N1, N2 = sum(operators.values()), sum(operands.values())
    vocabulary, length = n1 + n2, N1 + N2
    return {
        "distinct_operators": n1, "distinct_operands": n2,
        "total_operators": N1, "total_operands": N2,
        "halstead_length": length, "halstead_vocabulary": vocabulary,
        # Empty input has no information volume; this is an explicit extension.
        "halstead_volume": length * log2(vocabulary) if vocabulary else 0.0,
    }


def relative_complexity(complexities: Sequence[Number], k: float = 2.0) -> dict:
    """P1 Eqs. 2-5; population, not sample, standard deviation."""
    k = finite(k, "k", 0)
    values = [finite(c, "complexity", 0) for c in complexities]
    if not values or not sum(values):
        return {"cc_mean": None, "rci": [None] * len(values),
                "rci_mean": None, "rci_stddev": None, "rcim": None,
                "rci_exceeds_rcim": [None] * len(values)}
    avg = fmean(values)
    indices = [c / avg for c in values]
    mu, sigma = fmean(indices), pstdev(indices)
    threshold = mu + k * sigma
    return {"cc_mean": avg, "rci": indices, "rci_mean": mu,
            "rci_stddev": sigma, "rcim": threshold,
            "rci_exceeds_rcim": [x > threshold for x in indices]}


def interaction_complexity(cc: Number, fanin: int, fanout: int) -> float:
    """P1 Eq. 6; base 10 is established by the paper's numeric example."""
    cc = finite(cc, "cc", 0)
    nonnegative_int(fanin, "fanin")
    nonnegative_int(fanout, "fanout")
    return cc + log10(fanin + 1) + 0.5 * log10(fanout + 1)


def lcom_p9_literal(method_field_accesses: Sequence[Iterable[str]],
                    fields: Iterable[str]) -> float | None:
    """P9 Table 2: (1/a) * ((sum_j mu(A_j) - m) / (1-m)).

    This is the literal equation in the supplied PDF. It differs from the
    frequently used (mean(mu)-m)/(1-m). Do not clamp negative results.
    Only the field and method population supplied by the caller is considered.
    """
    field_set = set(fields)
    a, m = len(field_set), len(method_field_accesses)
    if a == 0 or m <= 1:
        return None
    total_uses = sum(len(set(accesses) & field_set)
                     for accesses in method_field_accesses)
    return (total_uses - m) / (a * (1 - m))


def maintainability_p9_literal(volume: Number, cc: Number, loc: int,
                                comment_percent: Number) -> float | None:
    """P9 Table 2 prints sqrt(246 * COM); COM is a percentage in percentage points, not a 0-1 fraction.

    The earlier prose answer substituted 2.46; this implementation does not.
    No 0-100 normalization or clipping is introduced by this function.
    """
    volume = finite(volume, "halstead_volume", 0)
    cc = finite(cc, "cc", 0)
    nonnegative_int(loc, "loc")
    com = finite(comment_percent, "comment_percent", 0)
    if volume == 0 or loc == 0:
        return None
    return 171 - 5.2 * log(volume) - 0.23 * cc - 16.2 * log(loc) + 50 * sin(sqrt(246 * com))


def software_health(sr: Number, sa: Number, se: Number) -> float:
    """P10: inputs are externally supplied vendor scores, not inferred here."""
    return fmean([finite(sr, "resiliency", 0, 100),
                  finite(sa, "agility", 0, 100),
                  finite(se, "elegance", 0, 100)])


def rocr(sr: Number, sa: Number, se: Number, business_impact: Number,
         component_count: int) -> float:
    """P10: weighted deficiency * BI / (100 * number of components)."""
    sr, sa, se = [finite(v, n, 0, 100) for v, n in
                  ((sr, "resiliency"), (sa, "agility"), (se, "elegance"))]
    bi = finite(business_impact, "business_impact", 0, 100)
    nonnegative_int(component_count, "component_count")
    if component_count == 0:
        raise ValueError("component_count must be positive")
    deficiency = (7 * (100 - sr) + 2 * (100 - se) + (100 - sa)) / 10
    return deficiency * bi / (100 * component_count)


def ai_ratio(labels: Sequence[str]) -> dict:
    """P4. Labels must be supplied; this code does not guess code authorship."""
    counts = Counter(labels)
    bad = set(counts) - {"AI", "Human", "Unknown"}
    if bad:
        raise ValueError(f"Unknown AI label values: {sorted(bad)}")
    return {"ai_ratio": ratio(counts["AI"], counts["AI"] + counts["Human"]),
            "ai_files": counts["AI"], "human_files": counts["Human"],
            "unclassified_files": counts["Unknown"]}


def raw_hybrid_complexity(N: Number, n: Number, L: Number, *, log_base: Number) -> float:
    """P8 Eq. 2, with mandatory missing policy supplied explicitly by caller."""
    N, n, L = finite(N, "N", 0), finite(n, "n", 0), finite(L, "L", 0)
    base = finite(log_base, "log_base", 0)
    if n <= 0 or L <= 0 or base <= 0 or base == 1:
        raise ValueError("n and L must be positive; log_base must be positive and != 1")
    return N * log(n, base) / L


def new1(raw_complexities: Sequence[Number], adjusted_complexities: Sequence[Number]) -> float | None:
    """P8 Eq. 3; scope/adjusted-complexity values must be supplied, not guessed."""
    raw = [finite(x, "raw complexity", 0) for x in raw_complexities]
    adjusted = [finite(x, "adjusted complexity", 0) for x in adjusted_complexities]
    return 100 * (1 - sum(raw) / sum(adjusted)) if sum(adjusted) else None
