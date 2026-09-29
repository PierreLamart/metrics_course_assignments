# Paper-derived repository metrics

A runnable Python command-line tool for measuring a local Git repository or an HTTPS/SSH Git URL. It produces strict JSON, with optional CSV tables for files, classes and methods.

**Automatic source analysis:** Python, Java and Smali. **Additional inputs:** UML/design models, compiler control-flow graphs, classifier predictions, measured runtime telemetry, test/fault records, supplied vendor risk scores, AI/Human labels and citation identifiers.

This is a reference implementation of the sufficiently specified formulas in the ten supplied papers, with explicitly documented extraction conventions. It is **not** a claim of numerical equivalence to Understand, Multimetric, SDMetrics, CAST Highlight, the NASA extractor, or the original AndroMetric tool. Read `coverage`, `policies`, linkage information and unavailable reasons in each report before comparing results.

## Requirements

- Python 3.10 or newer. Python source syntax must be supported by the interpreter used to run the tool.
- Git on `PATH` for repository scanning.
- **JDK 17 or newer**, with both `java` and `javac` on `PATH`, for Java AST analysis only. The bundled parser bridge uses the JDK's syntax-tree API; the metric calculations are in Python.
- No third-party Python runtime packages. No API key is required.

The target repository is parsed, not imported, compiled, built or tested. The tool compiles only its own small Java parser bridge in a temporary directory, then calls the parser on target sources. Remote repositories are cloned bare. Source symlinks and submodules are not followed.

## Quick start: no installation needed

Unzip the project, change into its top-level directory, then run:

```bash
python repo_metrics.py scan /absolute/path/to/repository --output metrics.json
```

Export the three entity tables as well:

```bash
python repo_metrics.py scan /absolute/path/to/repository \
  --output metrics.json \
  --csv-dir metrics_csv
```

On Windows, `py -3` can replace `python`. Paths with spaces must be quoted.

### Analyze a Git URL

```bash
python repo_metrics.py scan https://github.com/OWNER/REPOSITORY.git \
  --output metrics.json
```

Git uses your existing HTTPS/SSH authentication configuration. The tool does not collect credentials. The default remote clone is shallow. A branch/tag can be selected with `--ref`; a full 40- or 64-character commit ID is fetched explicitly, subject to server availability.

### Reproducible revision analysis without changing your checkout

```bash
python repo_metrics.py scan /path/to/repository \
  --ref HEAD \
  --output metrics-at-head.json
```

Without `--ref`, tracked files are read from the current working tree, including local modifications. Add `--include-untracked` to include untracked, non-ignored files. It cannot be combined with `--ref`.

### Exclusions and thresholds

```bash
python repo_metrics.py scan /path/to/repository \
  --exclude 'tests/*' \
  --exclude 'generated/*' \
  --k 2.0 \
  --output metrics.json
```

By default, dependency/build/cache directories such as `vendor`, `node_modules`, `.venv`, `build`, `dist` and `target` are excluded. `--no-default-excludes` disables those defaults. No project-specific generated-code detector is silently applied.

### Optional install

```bash
python -m pip install --no-build-isolation .
paper-repo-metrics scan /path/to/repository --output metrics.json
```

The direct `python repo_metrics.py ...` invocation does not require setuptools or installation.

## What is implemented

| Family | Implemented measurements | Required input |
|---|---|---|
| Physical size/documentation | Code/total/blank/comment lines, comment-only and mixed-line diagnostics, comment/code ratio and CP | Source lexer |
| Declarations/statements | Classes, interfaces, methods, public/private/protected/default methods, instance methods/variables, attributes, getters/setters, units, statements and declaration/executable subsets | Python or Java AST; applicable Smali declarations |
| Halstead primitives | Distinct/total operators and operands, program length, vocabulary, volume | Versioned Python/Java token policy |
| Control flow | CC, binary decisions, relative logical complexity, explicit node-simple acyclic path count | Supported source CFG or supplied compiler graph |
| Composite complexity | SumCyclomatic, WMC, RCI, RCIM, IC | Method complexities; resolved call graph for IC |
| Inheritance/design | DIT, immediate bases/children, ancestors/descendants, class-to-leaf depth, implemented interfaces, inherited members, interface clients, nesting | Source declarations or explicit model |
| Coupling/cohesion | Known type/call coupling, two separately named RFC definitions, attribute/parameter coupling counts, literal P9 LCOM | Resolved source/model relations; field-access sets for LCOM |
| UML associations | Assoc and same-scope/same-branch/outside-branch association counts | Explicit UML2 XMI or normalized model JSON |
| Maintainability | Literal P9 Maintainability Index | HV, CC, LOC and comment percentage |
| Android | Bytecode instructions and instructions/method; catch/empty-handler counts; registry-based sensitive API, intent-launch and handler-log counts | Smali; explicit API signature registry |
| Prediction evaluation | Accuracy, precision, recall, specificity, F1, MCC, Cohen's kappa, AUC, probability RMSE, percentage agreement | Labels/predictions/probabilities |
| Object detection | mAP@50 and mAP@50:95 averaging | Per-class AP at specified IoU thresholds, already evaluated externally |
| Runtime/testing | Latency/image, GPU telemetry sample summaries, test duration and shortest fault-covering suite prefix | Observations, not source-code estimates |
| Research/risk | AI ratio, citation count, software health, ROCR, supplied highest-risk file count | Explicit classifications/IDs/vendor scores |
| Other supplied primitives | NEW_1 arithmetic, raw hybrid complexity, I/O format count, smell-instance count | Explicit component values/IDs |

`python repo_metrics.py catalog` prints the machine-readable catalog, aliases, paper IDs, input requirements and exclusions. `docs/METRIC_COVERAGE.md` is the readable equivalent. Catalog entries include implementation variants and derived output fields; their number is **not** a claim about the number of unique metrics across the papers.

## Important source corrections and limits

**P9 Table 2 is preserved literally.** Its supplied PDF prints:

```text
LCOM = (sum(mu) - m) / (a * (1 - m))
MI   = 171 - 5.2*ln(HV) - 0.23*CC - 16.2*ln(LOC)
       + 50*sin(sqrt(246*COM))
```

The earlier conversational summary instead used `(mean(mu)-m)/(1-m)` and `2.46`. Those substitutions are not used here. Outputs are named `lcom_p9_literal` and `mi_p9_literal`, are not clipped, and can differ substantially from familiar textbook/tool variants. This preserves the printed paper, **not** necessarily the authors' actual tool implementation or intended equation.

P10's printed ROCR formula is implemented without modifying it to reproduce inconsistent example table values. For its Navigation row, the stated inputs and five components give `2.511876`, not Table 3's `2.31`.

**Not implemented from source because the papers do not specify enough:** KNOT1/KNOT2 algorithms; SCOPE/adjusted-region reconstruction; NASA `ev(g)`, `iv(g)`, ambiguous `L`, `B` and related undocumented Halstead fields; PPIV/APD; AndroMetric's unnamed columns; RSEMM scoring thresholds and final maturity rules; proprietary vendor base scores; and candidate metrics only named in P9. In particular, `B` is not silently reinterpreted as observed bug count. NEW_1's arithmetic is available, but its undefined scope extraction is not invented.

**Source-language coverage is not universal.** C, C++, C#, JavaScript, TypeScript and other recognized source extensions are reported as `unsupported_language`, not counted as successfully analyzed. APKs are not decompiled automatically. Supply already decompiled Smali when applicable.

**CFG coverage is explicit.** Python `try`, `with`, comprehensions, pattern matching and suspension/resumption, and Java `try`, pattern switches, switch expressions and unsupported constructs yield `cc: null` with a reason. Ordinary straight-line code, conditionals, short-circuit conditions, loops, early returns and supported Java switches have constructed graphs. Named callables are the measurement population; lambda/anonymous bodies and module/static-initializer execution are not separate units. See the full policy document for details.

**Static relationships are not runtime truth.** Unresolved calls and external/ambiguous classes are retained in the report. A `_known`/`_resolved` suffix identifies the measured graph, not a complete runtime graph. Reflection, monkey-patching, receiver flow analysis and virtual dispatch expansion are not implemented.

## Run the included source fixture

The demonstration source directory is intentionally not shipped with a `.git` directory. To scan it, initialize a temporary test repository:

```bash
git -C examples/demo_repo init
git -C examples/demo_repo add .
git -C examples/demo_repo -c user.name="Metrics Demo" -c user.email="demo@example.invalid" commit -m "Demo fixture"
python repo_metrics.py scan examples/demo_repo --output demo-metrics.json
```

The included `examples/example_report.json` was produced from these source files with the example API, observation and design inputs. Commit IDs and runtime versions will differ when you repeat it.

## Additional input examples

Evaluate the included synthetic observations:

```bash
python repo_metrics.py evaluate examples/auxiliary.json --output evaluation.json
```

Measure the explicit design model (all 24 P7 output fields):

```bash
python repo_metrics.py model examples/design_model.json --output design.json

python repo_metrics.py model examples/design_model.xmi \
  --scope-branch-policy prefix_comparable \
  --output design-from-xmi.json
```

The XMI adapter handles a documented UML2 subset, not every vendor dialect. Normalized JSON is the stable interchange format. Source attribute types are **not** automatically treated as UML associations.

Combine source metrics, API counts and observations:

```bash
python repo_metrics.py scan /path/to/repository \
  --api-rules examples/api_rules.json \
  --aux examples/auxiliary.json \
  --design-model examples/design_model.json \
  --output combined.json
```

The example observations and API registry are **synthetic demonstrations**, not measurements of your repository and not the original paper's registry. Replace them with your data.

Measure a supplied graph:

```bash
python repo_metrics.py graph examples/cfg.json --output graph-metrics.json
```

To override individual source CFGs, first scan to obtain method IDs, then supply a JSON object mapping those IDs to graphs via `--cfg-input`. This allows language-specific compiler graphs to replace frontend limitations.

## Output structure

```text
repository                  Commit, working-tree/blob mode, dirty flag
implementation              Runtime and parser version information
policies                    Constructor, token, graph and aggregation conventions
coverage                    Parsed/measured/skipped files and callable CFG coverage
project                     Aggregates with explicit measured-subset scope
files[]                     Path, content hash, counts, parse status and warnings
classes[]                   Members, class metrics and linkage completeness
methods[]                   Method metrics, resolved call counts, unavailable reasons
call_graph                  Resolved edges, unresolved calls and invocation sites
api_usage                   Registry-based counts and qualified-target coverage
auxiliary_metrics           Only when observations were supplied
design_model_metrics       Only when a design model was supplied
```

Undefined or unavailable results are JSON `null`, never NaN. Full sums remain null when a required component is unavailable; explicitly named measured lower bounds are provided separately. Class summary statistics include measured/missing counts. CSV empty cells correspond to null/missing values; inspect JSON for the reasons.

`--include-cfg` adds graph nodes/edges. This can considerably enlarge reports.

For CI, `--fail-on-incomplete` writes the report and returns exit code 2 when selected source files cannot be structurally parsed or callable bodies lack CC. It does not turn unresolved static calls into a runtime-completeness guarantee. Ordinary argument/data failures return exit code 1.

## Python API

```python
from paper_repo_metrics.analyzer import analyze_repository
from paper_repo_metrics.cli import write_json
from pathlib import Path

report = analyze_repository('/path/to/repository', ref='HEAD', k=2.0)
write_json(report, Path('metrics.json'))

for method in report['methods']:
    print(method['id'], method['metrics'].get('cc'),
          method['metrics'].get('ic_resolved'))
```

For deliberate runtime measurement, `evaluation.benchmark_inference()` accepts a callable and optional accelerator synchronization/memory callbacks. The repository scanner **never invokes this function automatically**. GPU memory is never substituted with CPU process memory.

## Tests

```bash
python -m unittest discover -s tests -v
```

The included tests exercise formulas, lexical edge cases, graphs, supplied models, both AST frontends, Smali, auxiliary observations, Git working-tree and revision access, errors and output handling. Java tests skip only when a JDK is absent. See `docs/TEST_REPORT.md` for the environment actually tested.

## Project layout

```text
repo_metrics.py                 Direct CLI entry point
paper_repo_metrics/
  formulas.py                   Paper equations and numerical validation
  lexical.py                    Physical lines and versioned Halstead lexer
  python_frontend.py            Python AST extraction
  JavaAstBridge.java            JDK AST-to-JSON bridge (no project build)
  java_frontend.py               Temporary compilation/parser orchestration
  smali_frontend.py              Smali declarations, instructions and CFG
  graphs.py                     CFG construction, CC and path enumeration
  model.py                      Inheritance, coupling, cohesion and call graph
  design.py                     Normalized model/UML2 XMI adapter
  repository.py                 Git file/blob reader and bare-clone handling
  evaluation.py                 Metrics requiring explicit observations
  analyzer.py                   Scan coordinator, coverage and aggregation
  cli.py                        Input validation, JSON/CSV and subcommands
  catalog.json                  Metric aliases, provenance and exclusions
examples/                       Small fixtures and explicit input schemas
tests/                         Executable unittest suite
docs/                          Policies, sources, input formats and test report
```

See `docs/SOURCES.md` for paper identifiers and `docs/MEASUREMENT_POLICIES.md` for all non-paper extraction choices. The original implementation is provided under the MIT license; source papers are not redistributed.
