"""Metrics over a normalized declaration/type/call graph.

Automatic source linkage is conservative: only unambiguous declarations in
this snapshot are connected. External and ambiguous symbols are retained as
unresolved, not guessed by matching a method name anywhere in the repository.
"""
from __future__ import annotations
from collections import Counter, defaultdict, deque
import re
from .formulas import interaction_complexity, lcom_p9_literal, relative_complexity

PRIMITIVES = {"", "void", "boolean", "byte", "char", "short", "int", "long", "float", "double",
              "bool", "str", "bytes", "list", "dict", "tuple", "set", "frozenset", "None", "Any",
              "typing.Any", "object", "var", "NoneType", "V", "Z", "B", "C", "S", "I", "J", "F", "D"}


def root_type(raw: str) -> str:
    raw = raw.strip().strip("'\"")
    raw = re.sub(r"@[\w.]+(?:\([^)]*\))?\s*", "", raw)
    raw = re.sub(r"\b(?:final|volatile|transient)\s+", "", raw)
    return re.split(r"[<\[]", raw, maxsplit=1)[0].strip().removesuffix("...")


def measure_model(classes: list[dict], methods: list[dict], *, k: float = 2.0,
                  include_constructors: bool = False,
                  associations: list[list[str]] | None = None,
                  scope_branch_policy: str | None = None) -> dict:
    C = {c["id"]: c for c in classes}
    M = {m["id"]: m for m in methods}
    if len(C) != len(classes) or len(M) != len(methods):
        raise ValueError("Duplicate class or method IDs in semantic model")
    by_qname = defaultdict(list)
    by_suffix = defaultdict(set)
    for c in classes:
        by_qname[c["qname"]].append(c["id"])
        parts = c["qname"].split(".")
        for start in range(1, len(parts) - 1):
            by_suffix[".".join(parts[start:])].add(c["id"])
    def resolve(raw: str, context: dict) -> str | None:
        if raw in C:
            return raw
        name = root_type(raw)
        if name in PRIMITIVES:
            return None
        module = context.get("module", "")
        imports = context.get("imports", {})
        first, _, rest = name.partition(".")
        imported = imports.get(first)
        candidates = []
        if imported:
            candidates.append(imported + ("." + rest if rest else ""))
        else:
            candidates.append(name)
            if module:
                candidates.append(module + "." + name)
            owner = context.get("owner") or context.get("parent_class")
            if owner in C:
                candidates.append(C[owner]["qname"] + "." + name)
            if context.get("qname"):
                candidates.append(context["qname"] + "." + name)
            candidates.extend(x + "." + name for x in context.get("wildcard_imports", []))
        hits = {cid for q in candidates for cid in by_qname.get(q, [])}
        # 'src/pkg/A.py' is represented as src.pkg.A. A qualified import of
        # pkg.A may match that source root; an unqualified global name may not.
        if not hits and imported:
            fq = candidates[0]
            hits = by_suffix.get(fq, set())
        return next(iter(hits)) if len(hits) == 1 else None

    parents, children, unresolved_bases = defaultdict(set), defaultdict(set), defaultdict(list)
    impl, implementers = defaultdict(set), defaultdict(set)
    for c in classes:
        cid = c["id"]
        for raw in c.get("bases", []):
            target = resolve(raw, c)
            if target:
                parents[cid].add(target)
                children[target].add(cid)
            elif root_type(raw) not in {"object", "java.lang.Object", "Object"}:
                unresolved_bases[cid].append(raw)
        for raw in c.get("interfaces", []):
            target = resolve(raw, c)
            if target:
                impl[cid].add(target)
                implementers[target].add(cid)
    # Topological sorting makes cycles explicit instead of recursing forever.
    degrees = {cid: len(parents[cid]) for cid in C}
    q = deque(sorted(cid for cid, d in degrees.items() if d == 0))
    order = []
    while q:
        cid = q.popleft()
        order.append(cid)
        for child in sorted(children[cid]):
            degrees[child] -= 1
            if degrees[child] == 0:
                q.append(child)
    invalid_hierarchy = set(C) - set(order)
    ancestors, descendants, depth, leaf_depth, complete = {}, {}, {}, {}, {}
    for cid in order:
        ancestors[cid] = set().union(*(ancestors[p] | {p} for p in parents[cid])) if parents[cid] else set()
        depth[cid] = max((depth[p] + 1 for p in parents[cid]), default=0)
        complete[cid] = not unresolved_bases[cid] and all(complete[p] for p in parents[cid])
    for cid in reversed(order):
        descendants[cid] = set().union(*(descendants[x] | {x} for x in children[cid] if x in descendants)) if children[cid] else set()
        leaf_depth[cid] = max((leaf_depth[x] + 1 for x in children[cid] if x in leaf_depth), default=0)

    owned = defaultdict(list)
    for m in methods:
        if m.get("owner"):
            if m["owner"] not in C:
                raise ValueError(f"Unknown method owner {m['owner']!r}")
            owned[m["owner"]].append(m)
    chosen = {cid: [m for m in owned[cid] if include_constructors or not m.get("constructor", False)] for cid in C}
    method_qnames = defaultdict(list)
    nested_functions = defaultdict(list)
    raw_signatures = {}
    for m in methods:
        method_qnames[m["qname"]].append(m)
        if m.get("lexical_parent"):
            nested_functions[(m["lexical_parent"], m["name"])].append(m)
        if m.get("raw_signature"):
            raw_signatures[m["raw_signature"]] = m["id"]

    def ancestry_bfs(cid: str):
        queue, seen = deque(sorted(parents[cid])), set()
        while queue:
            x = queue.popleft()
            if x not in seen:
                seen.add(x)
                yield x
                queue.extend(sorted(parents[x]))

    def methods_named(cid: str, name: str, arity: int | None) -> list[dict]:
        for source in [cid, *list(ancestry_bfs(cid))]:
            candidates = [m for m in owned[source] if m["name"] == name and
                          (arity is None or m.get("arity_min", len(m.get("params", []))) <= arity)
                          and (arity is None or m.get("arity_max") is None or arity <= m["arity_max"])]
            if candidates:
                return candidates
        return []

    def receiver_class(recv: str, m: dict) -> str | None:
        owner = m.get("owner")
        if recv in {"this", m.get("receiver_name")} and owner:
            return owner
        if recv in {"super", "super()"} and owner:
            return next(iter(parents[owner])) if len(parents[owner]) == 1 else None
        if recv in m.get("local_types", {}):
            return resolve(m["local_types"][recv], m)
        field_name = recv.split(".")[-1]
        if owner and (recv == field_name or recv.startswith(("this.", "self.", "cls."))):
            attrs = [a for x in [owner, *list(ancestry_bfs(owner))]
                     for a in C[x].get("attributes", []) if a["name"] == field_name]
            if attrs:
                return resolve(attrs[0].get("type", ""), C[owner])
        return resolve(recv, m)

    edges, unresolved_calls = set(), []
    incoming, outgoing = defaultdict(set), defaultdict(set)
    invocation_sites = []
    for m in methods:
        for call in m.get("calls", []):
            recv, name, arity = call.get("receiver", ""), call["name"], call.get("arity")
            target, api_target = None, call.get("raw_target")
            if api_target:
                target = raw_signatures.get(api_target, "external-signature:" + api_target)
            else:
                cid = receiver_class(recv, m) if recv else None
                candidates = []
                if call.get("kind") == "constructor":
                    cid = resolve(recv, m)
                    if cid:
                        candidates = methods_named(cid, "<init>", arity)
                elif recv:
                    if cid:
                        candidates = methods_named(cid, name, arity)
                else:
                    # Local nested functions have priority over module functions.
                    nested = nested_functions.get((m["id"], name), [])
                    if nested:
                        candidates = nested
                    elif m.get("owner") and m["language"] != "python":
                        candidates = methods_named(m["owner"], name, arity)
                    if not candidates:
                        fq = m.get("imports", {}).get(name, m.get("module", "") + "." + name)
                        candidates = method_qnames.get(fq, [])
                    if not candidates:
                        constructor_class = resolve(name, m)
                        if constructor_class:
                            cid = constructor_class
                            candidates = methods_named(cid, "__init__" if m["language"] == "python" else "<init>", arity)
                candidates = [n for n in candidates if (arity is None or n.get("arity_min", 0) <= arity)
                              and (arity is None or n.get("arity_max") is None or arity <= n["arity_max"])]
                if len(candidates) == 1 and arity is not None:
                    target = candidates[0]["id"]
                if cid:
                    api_target = C[cid]["qname"] + "." + name
                elif recv:
                    first, _, rest = recv.partition(".")
                    base = m.get("imports", {}).get(first)
                    if base:
                        api_target = base + ("." + rest if rest else "") + "." + name
            if target is not None:
                edges.add((m["id"], target))
                outgoing[m["id"]].add(target)
                incoming[target].add(m["id"])
            else:
                unresolved_calls.append({"caller": m["id"], **call})
            invocation_sites.append({"caller": m["id"], "path": m["path"], **call,
                                     "resolved_target": target, "api_target": api_target})

    coupled = defaultdict(set)
    type_unknown = defaultdict(set)
    ic_attr, ec_attr, ic_par, ec_par = Counter(), Counter(), Counter(), Counter()
    def connect(a: str, b: str | None) -> None:
        if b and a != b:
            coupled[a].add(b)
            coupled[b].add(a)
    for c in classes:
        cid = c["id"]
        for attr in c.get("attributes", []):
            raw = attr.get("type", "")
            target = resolve(raw, c)
            if target and target != cid:
                ic_attr[cid] += 1; ec_attr[target] += 1
                connect(cid, target)
            elif root_type(raw) not in PRIMITIVES and target is None:
                type_unknown[cid].add(raw)
        for m in owned[cid]:
            for p in m.get("params", []):
                raw = p.get("type", "")
                target = resolve(raw, m)
                if target and target != cid:
                    ic_par[cid] += 1; ec_par[target] += 1
                    connect(cid, target)
                elif root_type(raw) not in PRIMITIVES and target is None:
                    type_unknown[cid].add(raw)
            for raw in m.get("type_refs", []):
                target = resolve(raw, m)
                connect(cid, target)
    for a, b in edges:
        ca, cb = M[a].get("owner"), M.get(b, {}).get("owner")
        if ca:
            connect(ca, cb)

    assoc = defaultdict(set)
    if associations is not None:
        for edge in associations:
            if len(edge) != 2 or edge[0] not in C or edge[1] not in C:
                raise ValueError("Associations must be pairs of known class IDs")
            a, b = edge
            if a != b:
                assoc[a].add(b); assoc[b].add(a)
    if scope_branch_policy not in {None, "prefix_comparable"}:
        raise ValueError("scope_branch_policy must be null or 'prefix_comparable'")

    def inherited_members(cid: str) -> tuple[int, int]:
        def signature(m: dict):
            if m.get("language") == "python":
                return (m["name"],)
            return (m["name"], tuple(root_type(p.get("type", "")) for p in m.get("params", [])))
        method_seen = {signature(m) for m in chosen[cid]}
        attr_seen = {a["name"] for a in C[cid].get("attributes", [])}
        ni, ai = 0, 0
        for ancestor in ancestry_bfs(cid):
            def visible(x: dict) -> bool:
                v = x.get("visibility")
                return v != "private" and (v != "default" or C[cid].get("scope") == C[ancestor].get("scope"))
            for m in owned[ancestor]:
                sig = signature(m)
                if not m.get("constructor") and visible(m) and sig not in method_seen:
                    ni += 1; method_seen.add(sig)
            for attr in C[ancestor].get("attributes", []):
                if visible(attr) and attr["name"] not in attr_seen:
                    ai += 1; attr_seen.add(attr["name"])
        return ni, ai

    unresolved_by_caller = Counter(x["caller"] for x in unresolved_calls)
    for m in methods:
        mm = m.setdefault("metrics", {})
        mm.update({"fanin_resolved": len(incoming[m["id"]]), "fanout_resolved": len(outgoing[m["id"]]),
                   "unresolved_call_sites": unresolved_by_caller[m["id"]]})
        cc = mm.get("cc")
        mm["ic_resolved"] = interaction_complexity(cc, mm["fanin_resolved"], mm["fanout_resolved"]) if cc is not None else None
        mm["ic_resolved_exceeds_10"] = mm["ic_resolved"] > 10 if mm["ic_resolved"] is not None else None
        mm["rci"] = None
    for c in classes:
        cid, ms = c["id"], chosen[c["id"]]
        attrs = c.get("attributes", [])
        public_known = all(m.get("visibility") is not None for m in ms)
        ni, ai = inherited_members(cid) if cid not in invalid_hierarchy else (None, None)
        measured = [m for m in ms if m.get("has_body", False)]
        ccs = [m.get("metrics", {}).get("cc") for m in measured]
        fully_measured = all(x is not None for x in ccs)
        indices = relative_complexity(ccs, k) if fully_measured else relative_complexity([], k)
        if fully_measured:
            for m, index, flag in zip(measured, indices["rci"], indices["rci_exceeds_rcim"]):
                m["metrics"]["rci"] = index
                m["metrics"]["rci_exceeds_rcim"] = flag
        ids = {m["id"] for m in ms}
        class_in = set().union(*(incoming[mid] for mid in ids)) - ids if ids else set()
        class_out = set().union(*(outgoing[mid] for mid in ids)) - ids if ids else set()
        metrics = {
            "method_count": len(ms), "attribute_count": len(attrs),
            "instance_methods": sum(not m.get("static", False) for m in ms),
            "instance_variables": sum(not a.get("static", False) for a in attrs),
            "public_methods": sum(m.get("visibility") == "public" for m in ms) if public_known else None,
            "private_methods": sum(m.get("visibility") == "private" for m in ms) if public_known else None,
            "protected_methods": sum(m.get("visibility") == "protected" for m in ms) if public_known else None,
            "default_methods": sum(m.get("visibility") == "default" for m in ms) if public_known else None,
            "getters": sum(m["name"].startswith(("get", "is", "has")) for m in ms),
            "setters": sum(m["name"].startswith("set") for m in ms),
            "immediate_bases": len(c.get("bases", [])),
            "noc_children": len(children[cid]), "dit_known": depth.get(cid),
            "dit": depth.get(cid) if complete.get(cid) else None,
            "num_ancestors_known": len(ancestors[cid]) if cid in ancestors else None,
            "num_descendants": len(descendants[cid]) if cid in descendants else None,
            "cld": leaf_depth.get(cid), "interfaces_implemented": len(c.get("interfaces", [])),
            "inherited_operations_known": ni, "inherited_attributes_known": ai,
            "direct_interface_clients": len(implementers[cid]) if c.get("kind") == "interface" else None,
            "indirect_interface_clients": len(set().union(*(implementers[x] for x in descendants.get(cid, set())))) if c.get("kind") == "interface" else None,
            "cbo_known": len(coupled[cid]),
            "ic_attr_known": ic_attr[cid], "ec_attr_known": ec_attr[cid],
            "ic_par_known": ic_par[cid], "ec_par_known": ec_par[cid],
            "rfc_p2_methods_including_inherited_known": len(ms) + ni if ni is not None else None,
            "rfc_p9_boundary_fanin_plus_fanout_resolved": len(class_in) + len(class_out),
            "wmc": sum(ccs) if fully_measured else None,
            "wmc_measured_lower_bound": sum(x for x in ccs if x is not None),
            "methods_with_cc": sum(x is not None for x in ccs),
            "bodyless_methods_excluded_from_complexity": len(ms) - len(measured),
            "rcim": indices["rcim"], "mean_cc": indices["cc_mean"],
            "lcom_p9_literal": lcom_p9_literal([m["field_accesses"] for m in ms], [a["name"] for a in attrs]) if all("field_accesses" in m for m in ms) else None,
            "assoc": len(assoc[cid]) if associations is not None else None,
            "num_ass_el_ssc": None, "num_ass_el_sb": None, "num_ass_el_nsb": None,
        }
        nesting, seen, parent = 0, {cid}, c.get("parent_class")
        while parent:
            if parent not in C or parent in seen:
                nesting = None; break
            seen.add(parent); nesting += 1; parent = C[parent].get("parent_class")
        metrics["nesting"] = nesting
        if associations is not None:
            scope = tuple(c.get("scope", []))
            metrics["num_ass_el_ssc"] = sum(tuple(C[x].get("scope", [])) == scope for x in assoc[cid])
            if scope_branch_policy == "prefix_comparable":
                def same_branch(x: str) -> bool:
                    other = tuple(C[x].get("scope", []))
                    return scope[:len(other)] == other or other[:len(scope)] == scope
                metrics["num_ass_el_sb"] = sum(same_branch(x) for x in assoc[cid])
                metrics["num_ass_el_nsb"] = len(assoc[cid]) - metrics["num_ass_el_sb"]
        c["metrics"] = {**c.get("metrics", {}), **metrics}
        c["linkage"] = {"unresolved_bases": unresolved_bases[cid],
                        "unresolved_declared_types": sorted(type_unknown[cid]),
                        "hierarchy_complete_within_declared_scope": complete.get(cid, False),
                        "hierarchy_cycle_or_dependency_on_cycle": cid in invalid_hierarchy}
    return {"resolved_edges": [list(x) for x in sorted(edges)],
            "unresolved_calls": unresolved_calls, "invocation_sites": invocation_sites,
            "scope": "Named declarations in analyzed snapshot; syntactic resolution, not runtime dispatch",
            "resolution_complete": not unresolved_calls,
            "scope_branch_policy": scope_branch_policy}
