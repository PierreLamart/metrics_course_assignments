# Implementation catalog

Each ID is an implementation output or variant, not necessarily a distinct metric family. Consult the required input and limitations; missing inputs are not replaced with zero.

| ID | Paper aliases | Papers | Input | Policy / limitation |
|---|---|---|---|---|
| loc | LOC, Lines of Code | P1, P2, P8, P9 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| total_lines | NL, LINES | P2, P8 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| blank_lines | BLOC, loBlank | P2, P8 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| comment_lines | NCL, loComment | P2, P8 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| lines_without_comment_only | LN-CM | P8 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| comment_to_code_ratio | RCTC, CCR | P2, P9 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| comment_percentage | CP | P9 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| statements | NOS, CountStmt | P2 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| declarative_statements | NDS, CountStmtDecl | P2 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| executable_statements | NExS, CountStmtExe, STMTS | P2, P8 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| unit_count | UNITS | P8 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| statements_per_unit | STMT/Unit | P8 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| file_count | NOF, #Files | P2, P9 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| class_count | NOC [P2 only], #Classes | P1, P2, P6, P9 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| method_count | NOM, CountDeclMethod, NumOps | P1, P2, P6, P7 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| default_methods | NDM, CountDeclMethodDefault | P2 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| private_methods | NPriM | P2 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| protected_methods | NProM | P2 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| public_methods | NPM, NumPubOps | P2, P7 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| instance_methods | NIM | P2 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| instance_variables | NIV | P2 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| methods_per_class | methods_per_class | P6 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| attribute_count | NumAttr | P7 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| getters | Getters | P7 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| setters | Setters | P7 | source AST/lexer | Aliases have measurement-policy differences; see MEASUREMENT_POLICIES.md. Python visibility is unavailable. |
| distinct_operators | n1, uniqOp | P8, P9 | source lexer | lexical-v1 convention is explicit; no claim of extractor identity. |
| distinct_operands | n2, uniqOpnd | P8, P9 | source lexer | lexical-v1 convention is explicit; no claim of extractor identity. |
| total_operators | N1, totalOp | P8, P9 | source lexer | lexical-v1 convention is explicit; no claim of extractor identity. |
| total_operands | N2, totalOpnd | P8, P9 | source lexer | lexical-v1 convention is explicit; no claim of extractor identity. |
| halstead_length | N | P8, P9 | source lexer | lexical-v1 convention is explicit; no claim of extractor identity. |
| halstead_vocabulary | n | P8, P9 | source lexer | lexical-v1 convention is explicit; no claim of extractor identity. |
| halstead_volume | HV, V | P8, P9 | source lexer | lexical-v1 convention is explicit; no claim of extractor identity. |
| dit | DIT | P1, P2, P6, P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| noc_children | NOC [CK], NOCh | P1, P2, P6, P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| immediate_bases | IFANIN | P2 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| num_descendants | NumDesc | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| num_ancestors_known | NumAnc | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| cld | CLD | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| interfaces_implemented | IFImpI | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| inherited_operations_known | OpsInh | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| inherited_attributes_known | AttInh | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| direct_interface_clients | NumDirClients | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| indirect_interface_clients | NumIndClients | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| nesting | Nesting | P7 | source/model inheritance graph | Known/in-scope relationships only. DIT is null when ancestor linkage is incomplete. |
| ec_attr_known | EC_Attr | P7 | source/model type references | Count resolved type occurrences, not unique target types; self-type and return parameters excluded by explicit convention. |
| ic_attr_known | IC_Attr | P7 | source/model type references | Count resolved type occurrences, not unique target types; self-type and return parameters excluded by explicit convention. |
| ec_par_known | EC_Par | P7 | source/model type references | Count resolved type occurrences, not unique target types; self-type and return parameters excluded by explicit convention. |
| ic_par_known | IC_Par | P7 | source/model type references | Count resolved type occurrences, not unique target types; self-type and return parameters excluded by explicit convention. |
| assoc | Assoc | P7 | explicit UML/normalized association model | No association inference from fields. Branch metrics require a supplied scope-branch policy. |
| num_ass_el_ssc | NumAssEl_ssc | P7 | explicit UML/normalized association model | No association inference from fields. Branch metrics require a supplied scope-branch policy. |
| num_ass_el_sb | NumAssEl_sb | P7 | explicit UML/normalized association model | No association inference from fields. Branch metrics require a supplied scope-branch policy. |
| num_ass_el_nsb | NumAssEl_nsb | P7 | explicit UML/normalized association model | No association inference from fields. Branch metrics require a supplied scope-branch policy. |
| cbo_known | CBO | P2, P6, P9 | source or explicit graph | Symmetric resolved type/call coupling; excludes inheritance-only links. |
| rfc_p2_methods_including_inherited_known | RFC [P2] | P2 | source or explicit graph | Local plus inherited method population, per P2 wording. |
| rfc_p9_boundary_fanin_plus_fanout_resolved | RFC [P9] | P9 | source or explicit graph | P9 sum formula; boundary union-of-methods interpretation is explicitly declared. |
| fanin_resolved | FANIN | P1 | source or explicit graph | Distinct resolved caller methods; not inheritance IFANIN. |
| fanout_resolved | FANOUT | P1 | source or explicit graph | Distinct resolved callee methods. |
| lcom_p9_literal | LCOM [P9 literal] | P9 | source or explicit graph | (sum(mu)-m)/(a*(1-m)); not the common normalized LCOM3 rewrite. |
| cc | CC, V(G) | P1, P8, P9 | source or explicit graph | E-N+2P; source CFG conventions and unsupported constructs are reported. |
| sum_cyclomatic | SumCyclomatic | P2 | source or explicit graph | Sum across callable bodies in the file; missing components keep full sum null. |
| wmc | WMC | P1, P2, P6, P9 | source or explicit graph | Sum local body complexities; constructor population is configurable. |
| rci | RCI | P1 | source or explicit graph | Method CC / class mean CC. |
| rcim | RCIM | P1 | source or explicit graph | mean(RCI)+k*pstdev(RCI). |
| ic_resolved | IC | P1 | source or explicit graph | CC+log10(fanin+1)+0.5*log10(fanout+1) on resolved call graph. |
| binary_decisions | CL | P8 | source or explicit graph | Count binary branch vertices in the chosen CFG. |
| relative_logical_complexity | cL | P8 | source or explicit graph | CL / executable statement count. |
| npath_node_simple | NPATH [explicit node-simple policy] | P8 | source or explicit graph | Bounded node-simple path enumeration or DAG DP; original NPATH loop rules are not specified in the PDF. |
| mi_p9_literal | MI [P9 literal] | P9 | source or explicit graph | 171-5.2 ln(HV)-.23 CC-16.2 ln(LOC)+50 sin(sqrt(246*COM)). |
| bytecode_instructions | bytecode instructions | P6 | Smali; handler counts also from Python/Java | Handlers, not protected regions, counted; bytecode no-action convention is explicit. No APK decompilation. |
| bytecode_per_method | bytecode_per_method | P6 | Smali; handler counts also from Python/Java | Handlers, not protected regions, counted; bytecode no-action convention is explicit. No APK decompilation. |
| catch_handlers | catch | P6 | Smali; handler counts also from Python/Java | Handlers, not protected regions, counted; bytecode no-action convention is explicit. No APK decompilation. |
| empty_catch_handlers | no_action | P6 | Smali; handler counts also from Python/Java | Handlers, not protected regions, counted; bytecode no-action convention is explicit. No APK decompilation. |
| network_op | network_op | P6 | qualified static invocation sites + user API rule registry | Exact original API mapping is not published. Empty/missing rules are not silently filled. |
| fileio_op | fileio_op | P6 | qualified static invocation sites + user API rule registry | Exact original API mapping is not published. Empty/missing rules are not silently filled. |
| sqlite_op | sqlite_op | P6 | qualified static invocation sites + user API rule registry | Exact original API mapping is not published. Empty/missing rules are not silently filled. |
| start_activity | start_activity | P6 | qualified static invocation sites + user API rule registry | Exact original API mapping is not published. Empty/missing rules are not silently filled. |
| start_service | start_service | P6 | qualified static invocation sites + user API rule registry | Exact original API mapping is not published. Empty/missing rules are not silently filled. |
| start_intent_for_result | start_intent_for_result | P6 | qualified static invocation sites + user API rule registry | Exact original API mapping is not published. Empty/missing rules are not silently filled. |
| start_activity_result | start_activity_result | P6 | qualified static invocation sites + user API rule registry | Exact original API mapping is not published. Empty/missing rules are not silently filled. |
| log | log | P6 | qualified static invocation sites + user API rule registry | Exact original API mapping is not published. Empty/missing rules are not silently filled. |
| accuracy | Accuracy | P3, P4, P7, P8 | explicit auxiliary observations | Confusion-matrix correctness. |
| precision | Precision | P3, P4, P5, P7, P8 | explicit auxiliary observations | TP/(TP+FP). |
| recall | Recall, Sensitivity, TPR | P3, P4, P5, P7, P8 | explicit auxiliary observations | TP/(TP+FN). |
| specificity | Specificity | P7 | explicit auxiliary observations | TN/(TN+FP), described in P7 AUC definition. |
| f1 | F1, F-measure | P3, P4, P7, P8 | explicit auxiliary observations | 2TP/(2TP+FP+FN); explicit zero policy. |
| mcc | MCC | P3 | explicit auxiliary observations | Matthews correlation coefficient. |
| cohens_kappa | Cohen's Kappa | P3, P4 | explicit auxiliary observations | Observed versus expected agreement. |
| auc | AUC, ROC AUC | P3, P7, P8 | explicit auxiliary observations | P3 strict > default; alternate tie credit must be explicit. |
| rmse | RMSE | P3 | explicit auxiliary observations | Root mean squared probability error. |
| percentage_agreement | Percent agreement | P4 | explicit auxiliary observations | 100*same labels/n. |
| map_50 | mAP@50 | P5 | explicit auxiliary observations | Average supplied AP by class at IoU .50. |
| map_50_95 | mAP@50-95 | P5 | explicit auxiliary observations | Average supplied AP over classes and ten IoU thresholds. |
| latency_ms_per_image | Latency | P5 | explicit auxiliary observations | Measured elapsed milliseconds / images; optional explicit benchmark API. |
| gpu_memory_mb | GPU memory usage | P5 | explicit auxiliary observations | Supplied device telemetry; report observed mean/max, not CPU RSS. |
| test_execution_time_ms | Test execution time | P10 | explicit auxiliary observations | Sum supplied test durations. |
| suite_percentage_to_cover_all_faults | % test suite to cover all faults | P10 | explicit auxiliary observations | Smallest fault-covering prefix / complete ordered suite. |
| software_health | Software Quality, Software Health | P10 | explicit auxiliary observations | Mean of externally supplied SR, SA, SE. |
| rocr | ROCR | P10 | explicit auxiliary observations | Weighted deficiency * BI / (100 * components). |
| highest_risk_file_count | Files with highest risk | P10 | explicit auxiliary observations | Count externally supplied risky-file IDs; no vendor risk rule invented. |
| ai_ratio | AI ratio | P4 | explicit auxiliary observations | Externally supplied AI/Human labels; Unknown excluded and counted separately. |
| citation_count | Citation count | P4 | explicit auxiliary observations | Count supplied canonical citing-work identifiers. |
| fomts | FOMTS | P8 | explicit auxiliary observations | Count externally supplied I/O format construct IDs; no Fortran frontend. |
| new1 | NEW_1 | P8 | explicit auxiliary observations | Only equation evaluation from supplied raw/adjusted complexities; no invented scope reconstruction. |

## Not automatically measured

**KNOT1, KNOT2**

No formal knot algorithm/ordering is defined in the supplied paper.

**Adjusted Complexity, SCOPE graph reconstruction, NEW_1 graph extraction**

Scope membership and global/local parameter definitions are insufficient. Raw E_j and NEW_1 arithmetic are implemented for supplied inputs.

**ev(g), iv(g), Halstead L, Halstead D, Halstead I, Halstead E, Halstead B, Halstead T, branchCount, potential volume, estimated program length**

Named or ambiguously labeled dataset fields; formulas/extractor specification are absent. B is NOT automatically treated as observed bug count.

**PPIV, APD, AndroMetric unnamed columns**

Only names/representative columns are supplied; exact definitions/schema are not reconstructed.

**FAIRness sub-principle scores, RSEMM best-practice score, community activity score, CI integration score, documentation coverage score, development history score, issue management score, licensing score, unit testing score, overall maturity band, citation velocity, h-index-style measure**

Scoring rules/thresholds/measurement windows are incomplete. No substitute Git heuristics are presented as these scores.

**SR, SA, SE, Business Impact**

Vendor/business inputs must be supplied. Health and ROCR arithmetic are implemented.

**AP from raw bounding boxes**

P5 does not specify matching/interpolation/confidence rules. Supply per-class AP at each IoU threshold.

**ERV, UIS, Average Unit Size, NAC, NTI, INC, C3, NRCI**

Candidate names in P9, without sufficient operational definitions in its implementation table.

**Original-tool LCOM for P1/P2/P6, Exact NASA locCodeAndComment**

Variants/extractor conventions unspecified; do not substitute a different metric silently.

