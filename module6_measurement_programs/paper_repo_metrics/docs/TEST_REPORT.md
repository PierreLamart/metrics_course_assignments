# Validation performed

## Automated suite

Command:

```bash
python -m unittest discover -s tests -v
```

**Result: 120 tests passed; no failures or skips in the tested environment.** The full captured run is in `test-run.txt`.

Tested environment:

- Linux container
- Python 3.13.5
- Git 2.47.3
- OpenJDK / javac 21.0.11
- The bundled Java bridge was compiled with `javac --release 17`, then executed on JDK 21. This checks Java 17 API compatibility, not execution on every supported JDK/Python/OS combination.

The tests cover paper-formula calculations, undefined/invalid inputs, P1's relative-complexity example, the literal P9 expressions, P10 formula behavior, comment/string distinctions, Java text blocks and UTF-16 offsets, supported and unsupported CFGs, Boolean/ternary/loop paths, bounded graph search, source declarations and static linkage, overloaded calls, all 24 model output fields, UML2 XMI versus JSON equivalence, source API registries, prediction/telemetry/test-fault metrics, Git blobs/working trees/untracked/ignored files, symlinks, file limits, malformed source, output validation and CSV escaping. A Git fsmonitor hook fixture is checked not to execute.

`python -m compileall -q paper_repo_metrics tests` also completed successfully. The ZIP was extracted into a fresh directory and all 120 tests passed again. A local offline pip installation into a separate target directory succeeded, including the catalog and Java bridge package data.

## End-to-end mixed-language example

The three supplied demonstration source files were committed into a temporary local Git repository and scanned together, with the supplied API registry, observation JSON and design model.

- Three candidate files: one Python, one Java and one Smali.
- Three files lexically and structurally measured.
- Twelve callable bodies.
- Eleven callable CFGs measured.
- One deliberately unsupported Java try/catch body correctly returned unavailable CC instead of a guessed number.
- The interface's bodyless declaration is reported separately and is not a callable body.
- All fixture invocation sites resolved under the declared syntactic policy; this is not a general runtime-call-graph completeness claim.

The produced JSON is `examples/example_report.json`. The standalone `evaluate`, `model`, `graph` and CSV export commands were also exercised.

## Self-analysis smoke test

An earlier snapshot of the toolkit and its fixtures/tests was copied into a temporary Git repository and analyzed at its committed `HEAD` through Git blob access. It contained 20 recognized source files, all of which were lexically and structurally parsed; 183 of 263 callable bodies had supported CFGs. Remaining CFGs were explicitly unavailable. The report retained unresolved calls instead of assigning arbitrary targets. This is a smoke test, not independent verification of every output value.

## Boundaries of validation

Local working trees, immutable revisions, and local bare clones were exercised. A live remote HTTPS/SSH clone was **not** verified against an external hosting service in this environment. The remote implementation delegates transport/authentication to Git. No claim is made about all hosting/authentication configurations.

The code was not benchmarked against large industrial repositories, against the original paper authors' proprietary tools, or across all advertised runtime versions and operating systems. Unit tests establish the selected reference conventions; they do not prove that incomplete source-paper descriptions equal the authors' original extraction implementations.
