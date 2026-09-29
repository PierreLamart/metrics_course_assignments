# Measurement policies, version 1

This document separates **paper formulas** from **engineering choices needed to extract their inputs**. Changing the latter changes comparability, even when the final formula stays unchanged. The code is not the original extractor used in any paper.

## Repository population and safety

The scanner uses Git's tracked path list by default, reads the working-tree contents without executing Python imports or repository build commands, and reports whether tracked contents are dirty. `--ref` reads blobs from a resolved commit without changing the worktree. Bare repositories and remote bare clones are supported. Git hooks and fsmonitor are disabled on scanner Git commands. Remote authentication still follows the user's Git/SSH configuration.

Recognized but unsupported languages, source symlinks, deleted tracked paths, excessive size, decoding errors and parse errors are visible in `files` and `coverage`. Unknown non-source file extensions are outside the candidate set. Submodules are not recursively analyzed. Default exclusion directory names and explicit patterns are recorded. This is not a security sandbox for hostile native tools, but it does not intentionally run the analyzed project.

Default limits are 2,000,000 bytes per file, 10,000 files analyzed, 100,000 cyclic path-search steps and a 120-second subprocess timeout. Java files are parsed in batches of up to 200 with a 768 MiB heap. A report can still be large; source text is not included, but declaration/call-site metadata is. No performance guarantee has been established for very large monorepos.

## Physical lines

A physical final line is counted even without a terminal newline; a terminal newline does not create an additional empty line. CRLF/CR is normalized to LF. Blank means whitespace-only. LOC counts nonblank lines containing noncomment tokens. Comment lines include inline comments; a mixed line contributes to both LOC and comment count. Blank lines inside block comments may count as both blank and comment lines. Therefore raw category counts are not assumed to form a partition.

Python docstrings are string literals and remain code, not lexer comments. `mixed_code_comment_lines` is an extraction diagnostic and is **not asserted to reproduce NASA's ambiguously described field**. `lines_without_comment_only` retains blanks and mixed lines; this is the explicit LN-CM interpretation. Comment/code ratio is unbounded above by 1 when comments outnumber code. CP is that ratio times 100.

## Halstead token policy: lexical-v1

For Python and Java, identifier/literal tokens are operands; keywords and operators are operators. Delimiters `()[]{};,:.` are excluded from operator counts. Literals remain distinct by their source spelling. Scope/symbol equivalence is not inferred. Python True/False/None and Java true/false/null are operand literals. Tokens inside comments are excluded. Each language/interpreter version is recorded; Python f-string token behavior may change with interpreter version.

Java Unicode escape preprocessing is deliberately not emulated by the custom lexical scanner. A detected `\\uXXXX` form makes the lexical metrics unavailable, while JDK AST metrics may still be available. Token vocabulary across files is the union of tokens, not the sum of vocabulary sizes. Combined volume and sum-of-file-volumes are separately reported. Smali has line/instruction counts, not an invented Halstead equivalence.

Only the source-supported primitives and `N*log2(n)` volume are calculated. Empty vocabulary has volume 0 by explicit implementation convention. Difficulty/effort/intelligence/estimated bugs/time are not populated from external textbook equations.

## AST declarations/statements and units

Python uses `ast`; Java uses `JavacTask.parse()` with annotation processing disabled. Java parsing does not perform full semantic/type checking. Smali uses structural declarations and instruction recognition. Named classes include enum/record declarations; interfaces are separate. Java anonymous classes are excluded with a warning. Python and Java lambda bodies are excluded from named-callable complexity/call-graph metrics; source token counts still include their text. Module-level execution and Java initializer blocks are not separate callable units. Their statements contribute to file statement counts, but their control flow is outside the named-callable CC population.

NOM is locally declared class methods; free/nested functions contribute to UNITS but not to class NOM. Explicit Java/Smali constructors are excluded from NOM/WMC by default, but remain available as callable records and in the call graph. `--include-constructors` changes NOM/WMC populations. Python `__init__` remains an ordinary Python method. Abstract/bodyless Java methods count as declarations but are excluded from mean CC/WMC/RCI populations, with their count reported.

Python declarations are class/function definitions, imports, global/nonlocal declarations and annotation-only assignments. Other AST statements are executable under this convention. Java class/method/variable declarations are declaration statements; blocks and formal/catch/lambda parameters are not statements. Other statement nodes are executable. Java's enhanced-for variable is a variable declaration. File counts traverse the complete syntax tree once; method counts exclude nested declaration bodies. These are not guaranteed identical to Understand's language-specific statement taxonomy.

Java/Smali visibility comes from modifiers, with implicit interface visibility handled. Default access is package/default access, **not** the Java interface `default` modifier. Python public/private/protected/default metrics are unavailable, not inferred from naming conventions. Class/static and instance members are distinguished by actual syntax/decorators; Python instance attributes are those observed on the method receiver. Dynamic attributes and descriptors are not reconstructed. Python classmethods are not counted as instance methods.

Getter/setter classification follows P7's literal prefixes, not semantic behavior. For example, a name beginning `is` satisfies the getter predicate even when that is not its intended meaning.

## Control-flow graph (CFG)

Supported constructs include straight-line statements, ordinary conditionals, short-circuit Boolean operators, conditional expressions, supported loops, unlabelled break/continue, explicit returns and throws, and ordinary Java constant-label switches. Short-circuit evaluation is expanded in the graph. Syntactically unreachable vertices after unconditional transfers are pruned. Constant-condition feasibility is not solved. A single synthetic exit joins represented exits. Implicit exceptions, invoked method bodies, virtual dispatch, optimizer transformations and interpreter/compiler hidden control flow are not added.

Unsupported constructs do not receive a guessed CC: Python try/with/match/comprehensions/async iteration/await/yield, Java try/catch/finally control flow, switch expressions, pattern/guarded switches, labelled transfers and `for(;;)` without an explicit test. Exception handler counts can still be available when CC is unavailable. Smali methods containing exception handlers also require explicit CFG input for exception-flow CC.

CC is always `E-N+2P` for the graph actually measured. CL is the number of vertices with two outgoing edges. cL divides CL by the executable-statement count. This is a declared binary-branch interpretation.

### Acyclic path convention

`npath_node_simple` counts entry-to-exit paths that never revisit a vertex. It is not claimed equivalent to the original Nejmeh NPATH algorithm: the paper does not specify all loop, Boolean and early-exit recurrence rules. In an ordinary loop CFG, a body path returning to its header is excluded. A DAG uses dynamic programming; a cyclic graph uses bounded depth-first search. Exceeding the search budget yields null and a lower-bound diagnostic, not a saturated result. DAG counts exceeding 12,000 bits also yield null to bound JSON output. A compiler-supplied graph can implement a different, explicitly chosen unrolling policy.

`graph` computes CC over all supplied components. Its path count is entry-reachable only. Supplied CFGs must have valid node/edge IDs; callers are responsible for providing a graph suitable for the desired metric. `_cfg_origin`/`cfg_origin` identifies source-derived versus supplied graphs.

## Call graph and coupling

Callers/callees are distinct graph vertices, not invocation-site counts. The source resolver uses lexical/module context, imports, declared types, direct constructor assignments and argument counts. Unknown receivers, dynamic calls and ambiguous overloads remain unresolved. Java type inference and Python flow analysis are not comprehensive. Java overloads with the same arity are not guessed from literal argument types. The graph represents syntactic targets, not runtime dispatch to every override.

Smali's explicit method signatures can resolve a unique symbolic target outside the repository; those targets are labeled `external-signature:`. Their source bodies are not required to count that reference. Consequently source-language graphs may have different external-resolution coverage.

`fanin_resolved`, `fanout_resolved` and `ic_resolved` are calculated on this graph only. `resolution_complete` means listed invocation sites resolved under this mechanism; it is not a claim about reflection, callbacks or all runtime behavior. IC uses base-10 logs from P1's worked example.

CBO uses a symmetric union of resolved declared-type uses and resolved class-owned calls. Inheritance-only edges are excluded unless also connected by a measured use/call. External/ambiguous types are not invented. Attribute/parameter coupling counts count resolved occurrences, not unique target types; self-type references and return types are excluded under the declared convention. A generic container's outer declared type is used, not all generic arguments.

The two incompatible RFC descriptions are separate implementation variants: P2 is the local plus visible inherited method count; P9 is the sum of distinct caller and callee methods across the class boundary. Internal calls are excluded from the latter boundary sets. This boundary interpretation is an extraction choice because P9 does not formalize it.

## Inheritance and UML

Inheritance uses a directed declared parent graph. Roots have DIT 0, and implicit platform Object roots are excluded. DIT is null if a referenced ancestor is unresolved; `dit_known` exposes the analyzed subgraph depth. NOC means immediate children, not class count. Ancestor/descendant closures use sets; class-to-leaf depth is the longest descendant distance within the snapshot. Cycles/dependencies on cycles are flagged rather than recursed forever. Unresolved interfaces do not acquire invented clients.

Superclass inheritance and implemented-interface relations are distinct. Inherited members are deduplicated by signature/name, omit locally overridden/hidden members and exclude private/nonvisible package members. This is a reference graph policy, not a complete compiler implementation of every language's inheritance rules.

The normalized design input supplies actual associations. Attributes do not automatically imply UML associations. The XMI adapter handles standard UML2 classifiers, owned attributes/operations, generalizations, interface realizations and binary associations; unsupported association endpoints are warned. Return parameters are excluded. Namespace/vendor extensions not recognized by the adapter should be converted to normalized JSON.

`num_ass_el_ssc` compares scope paths exactly. The optional `prefix_comparable` branch policy regards equal scopes or parent/child scope prefixes as the same branch. Sibling scopes are different branches. Branch fields remain null without that explicit policy.

## Composite formulas and aggregation

RCI uses all selected local callable bodies only if all have CC. RCIM uses population standard deviation, never sample standard deviation. No-method/zero-mean populations yield null. WMC is the sum of local body CC; file SumCyclomatic includes the chosen file callable population, including nested functions once as separate units. A missing CC makes the full sum null; measured lower-bound sums remain available.

P9's literal LCOM is `(sum(mu)-m)/(a*(1-m))`. The earlier conversational summary moved `1/a` inside the numerator; that was not a literal transcription. Negative results are not clamped. No fields or fewer than two methods yields null. The source frontend measures field accesses; pure UML diagrams do not provide them, so no LCOM is invented from design metadata.

P9's literal MI uses `sqrt(246*COM)` with COM in percentage points. Zero HV or LOC yields null because the logarithm is undefined. No conventional rescaling to 0-100 is applied. This implementation deliberately does not assert the printed expression equals the original tool's expression.

Ratios of totals and sums of ratios are different. The project report exposes both recomputed comment/code percentage and P9's sum-of-file-percentages. Class summaries include sum, mean, minimum, maximum and missing counts as reporting summaries, not newly claimed source metrics. Do not interpret sums of percentages as a global percentage or sums of DIT as a project inheritance depth.

## Auxiliary observations

Predictions, ratings, device telemetry, test results and external scores require separate data. A Git snapshot does not contain them by implication. Unknown AI labels are counted separately and excluded from the AI ratio denominator; no AI authorship detector is fabricated. Citation IDs must already be canonicalized across providers.

Zero metric denominators yield null. F1 uses the algebraic confusion-matrix expression, giving zero for unsuccessful positive predictions where its denominator is positive. AUC uses P3's strict `positive_score > negative_score` by default (ties receive zero); 0.5 tie credit is an explicit optional convention. Classifier probability RMSE requires probabilities in [0,1]. Scalar multiclass probabilities are rejected. Multiclass precision/recall/F1 are one-versus-rest per class; overall accuracy and kappa are also reported.

P5 only defines mAP aggregation, not complete AP matching/interpolation. Per-class AP at each IoU is supplied by an external evaluator. Missing thresholds or inconsistent class populations make mAP50:95 null. Latency is total measured elapsed milliseconds divided by total images, not an unweighted mean of batches. Device-memory mean and maximum are labeled observed samples, not inferred hardware peak usage.

Ordered test duration is the sum of supplied durations. The shortest prefix covering the supplied fault universe is reported; without an explicit universe, the union of observed full-suite faults is used and labeled. No known faults yields an undefined coverage percentage. Missing known faults produce null percentage and a list of uncovered IDs.

P10 health and ROCR use supplied scores in [0,100]. The component count is explicit (or the number of supplied rows), must be positive, and remains in the denominator. Raw SR/SA/SE/BI are not extracted from source. P8 NEW_1 uses supplied adjusted complexities; the undefined region-construction rule is not reconstructed. I/O-format and smell counts operate on supplied entity identifiers, not undocumented detectors.
