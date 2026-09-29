# Source papers and implementation provenance

The ten uploaded PDFs are the basis for the metric definitions. External implementation references describe parser/Git interfaces only; they do not supply missing metrics or replace paper equations. The PDFs themselves are not included in this distribution.

| ID | Paper | Relevant location |
|---|---|---|
| P1 | Y. Kataieva and M. Nemec, *Determining software quality using code analysis metrics*, 2025, DOI 10.1109/IT64745.2025.10930266 | Pages 2-3: traditional metrics, RCI, RCIM and IC; Eqs. 1-6 |
| P2 | M. M. Rahman et al., *Software Metric Based Impact Analysis of Code Smells - A Large Scale Empirical Study*, Software: Practice and Experience, 2025, DOI 10.1002/spe.3405 | PDF page 8, Table 3: 25 internal metrics; later sections describe smell frequencies/analysis |
| P3 | A. T. Siahmarzkooh, *Code Smell Detection Using a Hybrid LSTM-CNN Deep Learning Approach with Optimized Software Metrics*, 2026, DOI 10.1007/s40009-026-02183-x | Pages 3-4, Eqs. 12-19: classifier evaluation; actual source input feature names not enumerated |
| P4 | K. E. Bennin et al., *RSEMM: A dashboard for evaluating research software maturity*, SoftwareX, 2025, DOI 10.1016/j.softx.2025.102437 | Sections 2.3-2.5: AI ratio and assessment modules; Section 4: agreement/classifier validation |
| P5 | J. Harefa et al., *Optimizing Oil Palm Detection: A Deep Dive into Algorithm Performance and Software Metrics*, 2026, DOI 10.1109/IEHNS68708.2026.11606837 | Section 3.5, pages 3-4: six evaluation/resource measures |
| P6 | S. Siedler and K. Elish, *AndroMetric: Bridging Multi-Dimensional Software Metrics and Mobile Application Security*, 2026, DOI 10.1145/3793302.3793329 | Section 3.1 and Table 1: representative static columns; 31 claimed but not fully enumerated |
| P7 | B. Battulga et al., *Metric-based defect prediction from class diagram*, Array, 2025, DOI 10.1016/j.array.2025.100438 | PDF page 4, Table 2: 24 design metrics; Section 3.3: model evaluation |
| P8 | S. Saini et al., *Effective Software Metrics Prediction for Bug Detection Using Machine Learning*, International Journal of Artificial Intelligence and Machine Learning, 6(4s), 2026 | PDF pages 4-5: conventional counts, control flow and NEW_1; page 7 Table 3: dataset fields; Section 5.2: evaluation |
| P9 | N. Khezemi et al., *A comparison of code quality metrics and best practices in non-IoT and IoT systems*, Internet of Things, 2025, DOI 10.1016/j.iot.2025.101803 | PDF page 7, Table 2: implemented metric expressions; page 6 Table 1 contains additional candidate names |
| P10 | V. Malik, *Implementing Risk-Based Testing by Computational Intelligence of Software Quality Metrics*, 2025, DOI 10.1007/978-981-96-3102-5_23 | Sections 3-4: vendor score inputs, health/ROCR equations and test outcomes |

## Corrections to the earlier conversational extraction

The implementation is based on the papers, not on treating the earlier answer as authoritative. The following distinctions matter:

1. P9's LCOM equation prints the factor `1/a` outside the fraction `(sum(mu)-m)/(1-m)`. The implementation preserves this expression and does not silently replace it with the frequently used normalized variant.
2. P9 prints `246.COM` inside the MI square root, not `2.46*COM`. It is preserved as printed and clearly labeled. It may be a paper error; no claim is made that the original Multimetric implementation uses that expression.
3. P8's `B` label is ambiguous and no formula is provided. The tool does not turn it into an observed defect count or a textbook Halstead bug estimator.
4. The brief KNOT1/KNOT2 and SCOPE descriptions are not sufficient to guarantee an implementable original algorithm. They remain explicitly unavailable. NEW_1 arithmetic operates only on supplied primitives.
5. AndroMetric's total of 31 does not expose all 31 column names in its representative table. The missing names and undocumented registry are not reconstructed as invented features.
6. P2 and P9 describe different RFCs. They are implementation variants under one conceptual family, not silently reconciled into an unrelated standard RFC formula.
7. P10's formula and example ROCR table do not agree for the Navigation row. The implementation follows the equation, not an unreported correction fitted to the table.
8. Named dimensions (for example RSEMM community activity) are not reproducible numeric scores until their thresholds, windows and weights are supplied. No substitute heuristics are called those paper scores.

## Implementation API references

The code uses the public Python `ast` and `tokenize` interfaces, Git's `ls-files`, `ls-tree`, `cat-file` and revision commands, the JDK public `JavacTask.parse()` / `com.sun.source.tree` APIs, and Smali/Dalvik opcode structure. Current official interface documentation was consulted during construction. These dependencies do not make the extraction conventions identical to the original papers' tools.

All additional measurement choices are recorded in `MEASUREMENT_POLICIES.md` and the report's policy block. The catalog's `papers` arrays identify the relevant source for a conceptual metric; they are not claims that every alias/aggregation convention appears verbatim in every listed paper.
