# Input formats and extension points

All examples are included under `examples/`. JSON inputs must not contain NaN or infinity. External observations must belong to the repository/version being analyzed; the scanner does not validate that association for you. Example observations are synthetic.

## 1. Compiler control-flow graph

`graph` accepts this schema. Edges may have a third string label; parallel differently labeled branches are preserved.

```json
{
  "nodes": {"entry":"entry", "decision":"if", "yes":"statement", "exit":"exit"},
  "entry":"entry",
  "exits":["exit"],
  "edges":[["entry","decision"], ["decision","yes","true"],
           ["decision","exit","false"], ["yes","exit"]]
}
```

Nodes can instead be a list of IDs. Every edge endpoint, entry and exit must exist. Provide the CFG convention you intend to measure: synthetic exits, exception edges, reachability and path unrolling affect results. Source frontends ordinarily construct one entry and one synthetic exit.

For source-method overrides:

```json
{
  "python:module.function@1": {
    "nodes":["entry","exit"], "entry":"entry", "exits":["exit"],
    "edges":[["entry","exit"]]
  }
}
```

The key must be an **actual method ID from a previous scan of the same source snapshot**. Use `scan --cfg-input overrides.json`; unknown IDs are rejected. This supplies complexity inputs, not a replacement call graph.

## 2. Normalized design model

Use `model` for standalone output or `scan --design-model` to attach it to a repository report. `examples/design_model.json` contains a complete runnable example.

```json
{
  "scope_branch_policy":"prefix_comparable",
  "classes":[
    {
      "id":"A", "name":"A", "kind":"class", "scope":["package"],
      "parents":[], "interfaces":[],
      "attributes":[{"name":"other", "type":"B", "visibility":"private", "static":false}],
      "operations":[{"name":"getOther", "visibility":"public", "static":false,
                     "parameters":[]}]
    },
    {"id":"B", "name":"B", "kind":"class", "scope":["package"]}
  ],
  "associations":[["A","B"]]
}
```

`id` is mandatory and unique. `kind` can be `class` or `interface`. `parents` and `interfaces` refer to classifier IDs or resolvable names. `nested_in` optionally points to the containing class ID. Member visibility is `public`, `private`, `protected` or `default`; missing visibility remains unknown. Operations accept `constructor`; parameters contain `name` and `type`. Attribute/static defaults are explicit implementation conventions; supply them to avoid ambiguity.

No bodies or method-field-access sets are inferred from a class diagram. The standalone model report returns the 24 design fields, not invented CC/LCOM values. `associations: []` means the model has zero associations; **omitting `associations` means unavailable**. Omit `scope_branch_policy` to leave the two branch-specific association measurements unavailable.

`.xmi`, `.uml` and `.xml` files use the included limited UML2 adapter. Unsupported vendor encodings should be converted into normalized JSON. DTD/entity declarations are rejected. The supplied example XMI and JSON are tested for equivalent metrics.

## 3. API signature registry

`scan --api-rules api_rules.json` takes a mapping from metric IDs to case-sensitive glob patterns over `call_graph.invocation_sites[].api_target`.

```json
{
  "network_op":["Ljava/net/*;->*"],
  "fileio_op":["Ljava/io/*;->*"],
  "sqlite_op":["Landroid/database/sqlite/*;->*"],
  "start_activity":["Landroid/*;->startActivity(*)*"],
  "log":["Landroid/util/Log;->*"]
}
```

These are **example patterns, not the paper's registry**. Enumerating precise APIs/overloads is better than relying on broad package globs. Choose rules appropriate to the target signatures and metric definition. Smali targets use `Lpackage/Class;->method(descriptor)returnType`; Java/Python qualified targets, when resolved, use dotted names.

Supported keys: `network_op`, `fileio_op`, `sqlite_op`, `start_activity`, `start_service`, `start_intent_for_result`, `start_activity_result`, `log`. Each call site contributes at most once to each configured metric, regardless of how many patterns match; the same site can match different categories. `log` additionally requires a catch-handler site. Missing keys return null, while an explicitly configured empty list produces zero matches. Counts are static invocation sites, not runtime invocation frequency.

## 4. Auxiliary observation document

`evaluate observations.json` works without Git. `scan --aux observations.json` appends the same evaluation to a repository report. All top-level sections are optional; unknown names are rejected.

### Classification

```json
{"classification": {
  "y_true":[0,0,1,1], "y_pred":[0,1,1,1],
  "probabilities":[0.1,0.6,0.8,0.9], "positive_label":1,
  "auc_tie_credit":0.0
}}
```

`y_true` is required. `y_pred` may be omitted for 0/1 binary labels with probabilities; the threshold is then `threshold` (default 0.5). Probability means confidence in the designated positive class and must lie in [0,1]. For nonnumeric binary labels, specify `positive_label`. AUC defaults to P3's strict comparison; explicitly request 0.5 to give tied positive-negative pairs half credit. Multiclass data uses label arrays and reports per-class one-versus-rest metrics; scalar probabilities are not a multiclass probability matrix.

Direct count inputs are also supported through the Python API:

```python
from paper_repo_metrics.evaluation import confusion_metrics
result = confusion_metrics(tp=20, tn=60, fp=5, fn=15)
```

### Inter-rater agreement

```json
{"agreement":{"rater_a":["Low","High"],"rater_b":["Low","Low"]}}
```

Equal-length categorical label arrays produce percentage agreement and Cohen's kappa.

### Detection AP

```json
{"detection_ap":{"0.50":{"classA":0.8,"classB":0.9}}}
```

Supply all ten IoU keys from `0.50` through `0.95`, in steps of `0.05`, with the same class population to obtain mAP50:95. Raw AP must already have been computed using your explicitly selected matching/interpolation/evaluator conventions. The included example supplies ten thresholds. Missing values do not become zeros.

### Runtime observations

```json
{"runtime":[
  {"images":1,"elapsed_ms":16.0,"gpu_memory_mb":42.0},
  {"images":4,"elapsed_ms":40.0,"gpu_memory_mb":60.0}
]}
```

GPU memory is optional. Choose and document decimal MB versus binary MiB when collecting it; the tool preserves the supplied unit label. Reported latency is 56/5 = 11.2 ms/image in this example. GPU summaries are statistics of supplied observations, not an inferred device-wide peak.

### Ordered tests and faults

```json
{"test_execution":{
  "fault_universe":["F1","F2"],
  "tests":[
    {"id":"T1","duration_ms":10,"faults":["F1"]},
    {"id":"T2","duration_ms":20,"faults":["F2"]},
    {"id":"T3","duration_ms":15,"faults":[]}
  ]
}}
```

Array order is execution order; IDs must be unique. Omit `fault_universe` only when defining completeness relative to all faults observed in the supplied full suite. This example covers faults after 2/3 of tests, in 30 ms; the complete suite duration is 45 ms. It does not claim undiscovered real faults are covered.

### Vendor risk/quality inputs

```json
{"risk":{
  "component_count":5,
  "components":[{
    "id":"navigation", "sr":73.7, "sa":66.1, "se":77.9,
    "business_impact":47.9, "highest_risk_file_ids":["a.py","b.py"]
  }]
}}
```

The tool evaluates health and ROCR from these numbers. It does not reproduce CAST's underlying score calculation. The total component count must be explicit when rows are only a subset; otherwise it defaults to the number of rows. Risky files are deduplicated by supplied identifier, not classified by a new invented risk rule.

### Research-software observations

```json
{
  "ai_labels":["AI","Human","Unknown"],
  "citation_ids":["canonical-work-1","canonical-work-2"],
  "io_format_ids":["format-1","format-2"],
  "smell_instances":[{"smell":"LongMethod","entity":"A.f"}]
}
```

There is no automatic AI detector, bibliographic lookup, Fortran parser or undocumented smell detector behind these counts. Supply the classifications/identifiers from your chosen evidence-producing system. Citation identifiers must be canonicalized before combining providers. Smells are deduplicated by `(smell, entity)`.

### NEW_1 and raw node complexity

```json
{"hybrid":{"raw_complexities":[2,3],"adjusted_complexities":[4,6]}}
```

Alternatively, supply `nodes` with `N` and `n`, a global `L` and mandatory `log_base`, plus adjusted complexities:

```json
{"hybrid":{
  "nodes":[{"N":6,"n":4}], "L":2, "log_base":2,
  "adjusted_complexities":[12]
}}
```

This evaluates the stated arithmetic, including raw complexity 6 and NEW_1 50 for this example. Determining adjusted regions from source is not implemented because the paper does not specify an unambiguous algorithm.

## 5. Deliberate measurement of a running model

```python
from paper_repo_metrics.evaluation import benchmark_inference

# Define this only for a model you deliberately intend to execute.
def infer_batch():
    return model(batch)

result = benchmark_inference(
    infer_batch,
    warmup=5,
    iterations=20,
    images_per_call=len(batch),
    synchronize=accelerator_synchronize,     # omit for synchronous CPU work
    gpu_memory_mb=read_gpu_memory_in_mb,     # omit when no GPU reader exists
)
```

The last example intentionally uses application-specific callbacks, not a hard dependency on PyTorch/TensorFlow. The default repository scan does not execute it or any repository test command.
