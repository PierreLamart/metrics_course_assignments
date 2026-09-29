"""Control-flow graph construction and formula-level graph measurements.

The source frontends emit a small structured intermediate representation.
Unsupported control constructs are rejected: the caller reports null, rather
than returning a plausible but wrong complexity. Supplied compiler CFGs can
be measured independently of this source-front-end subset.
"""
from __future__ import annotations
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field


class UnsupportedControlFlow(ValueError):
    pass


@dataclass
class CFG:
    nodes: dict[str, str] = field(default_factory=dict)
    edges: list[tuple[str, str, str]] = field(default_factory=list)
    entry: str = ""
    exits: set[str] = field(default_factory=set)

    def node(self, kind: str) -> str:
        key = str(len(self.nodes))
        self.nodes[key] = kind
        return key

    def edge(self, source: str, target: str, label: str = "next") -> None:
        # Distinct true/false edges to the same node must remain distinct.
        edge = (source, target, label)
        if edge not in self.edges:
            self.edges.append(edge)

    def reachable(self) -> set[str]:
        adj = defaultdict(list)
        for a, b, _ in self.edges:
            adj[a].append(b)
        seen, todo = set(), [self.entry]
        while todo:
            v = todo.pop()
            if v not in seen:
                seen.add(v)
                todo.extend(adj[v])
        return seen

    def pruned(self) -> "CFG":
        reach = self.reachable()
        return CFG({v: k for v, k in self.nodes.items() if v in reach},
                   [e for e in self.edges if e[0] in reach and e[1] in reach],
                   self.entry, self.exits & reach)

    def to_dict(self) -> dict:
        return {"nodes": self.nodes, "edges": [list(e) for e in self.edges],
                "entry": self.entry, "exits": sorted(self.exits)}

    @classmethod
    def from_dict(cls, data: dict) -> "CFG":
        nodes = data["nodes"]
        if isinstance(nodes, list):
            if len(nodes) != len(set(map(str, nodes))):
                raise ValueError("Duplicate CFG node IDs")
            nodes = {str(n): "supplied" for n in nodes}
        elif isinstance(nodes, dict):
            nodes = {str(n): str(k) for n, k in nodes.items()}
        else:
            raise ValueError("CFG nodes must be a list or object")
        edges = []
        for i, e in enumerate(data.get("edges", [])):
            if len(e) not in (2, 3):
                raise ValueError("Each CFG edge needs two endpoints and an optional label")
            a, b = str(e[0]), str(e[1])
            if a not in nodes or b not in nodes:
                raise ValueError("CFG edge refers to an unknown node")
            edges.append((a, b, str(e[2]) if len(e) == 3 else f"edge_{i}"))
        entry = str(data["entry"])
        exits = set(map(str, data.get("exits", [])))
        if entry not in nodes or not exits <= set(nodes):
            raise ValueError("Invalid CFG entry or exits")
        return cls(nodes, edges, entry, exits)


def component_count(graph: CFG) -> int:
    adj = defaultdict(set)
    for a, b, _ in graph.edges:
        adj[a].add(b)
        adj[b].add(a)
    unseen, count = set(graph.nodes), 0
    while unseen:
        todo = [unseen.pop()]
        count += 1
        while todo:
            for v in adj[todo.pop()] & unseen:
                unseen.remove(v)
                todo.append(v)
    return count


def acyclic_path_count(graph: CFG, max_steps: int = 100000) -> dict:
    """Count node-simple entry-to-exit paths; no node is revisited in a path.

    This makes P8's phrase 'acyclic execution paths' explicit. It is NOT a
    claim of bit-for-bit equivalence to a particular Nejmeh/NPATH tool.
    A loop path returning to its header is excluded. Use compiler-supplied
    unrolled/acyclic graphs to choose another convention. Acyclic graphs use
    linear-time DP; cyclic graphs use bounded DFS. No silent saturation.
    """
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    g = graph.pruned()
    adj = defaultdict(list)
    incoming = Counter({n: 0 for n in g.nodes})
    for a, b, _ in g.edges:
        adj[a].append(b)
        incoming[b] += 1
    q = deque(v for v, d in incoming.items() if d == 0)
    order = []
    while q:
        v = q.popleft()
        order.append(v)
        for nxt in adj[v]:
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                q.append(nxt)
    if len(order) == len(g.nodes):
        values = {}
        for v in reversed(order):
            values[v] = 1 if v in g.exits else sum(values[nxt] for nxt in adj[v])
            if values[v].bit_length() > 12000:
                return {"value": None, "exact": False, "algorithm": "dag_dp",
                        "reason": "path_count_output_size_limit_12000_bits"}
        return {"value": values.get(g.entry, 0), "exact": True, "algorithm": "dag_dp"}
    count, steps = 0, 0
    visited = {g.entry}
    stack = [(g.entry, iter(adj[g.entry]))]
    if g.entry in g.exits:
        return {"value": 1, "exact": True, "algorithm": "node_simple_dfs"}
    while stack:
        v, it = stack[-1]
        nxt = next(it, None)
        if nxt is None:
            stack.pop()
            visited.remove(v)
            continue
        steps += 1
        if steps > max_steps:
            return {"value": None, "exact": False, "algorithm": "node_simple_dfs",
                    "reason": "path_search_step_limit", "paths_found_lower_bound": count}
        if nxt in visited:
            continue
        if nxt in g.exits:
            count += 1
        else:
            visited.add(nxt)
            stack.append((nxt, iter(adj[nxt])))
    return {"value": count, "exact": True, "algorithm": "node_simple_dfs"}


def graph_metrics(graph: CFG, max_steps: int = 100000) -> dict:
    P = component_count(graph)
    outgoing = Counter(a for a, _, _ in graph.edges)
    paths = acyclic_path_count(graph, max_steps)
    return {"cc": len(graph.edges) - len(graph.nodes) + 2 * P,
            "cfg_edges": len(graph.edges), "cfg_nodes": len(graph.nodes),
            "cfg_components": P,
            "binary_decisions": sum(n == 2 for n in outgoing.values()),
            "npath_node_simple": paths["value"], "npath_details": paths}


class Builder:
    def __init__(self) -> None:
        self.g = CFG()
        self.exit = self.g.node("exit")
        self.g.exits = {self.exit}

    def expression(self, e: dict | None, nxt: str) -> str:
        if not e:
            return nxt
        k = e.get("kind", "ordinary")
        if k == "unsupported":
            raise UnsupportedControlFlow(e.get("reason", "unsupported expression"))
        if k == "ternary":
            yes = self.expression(e["then"], nxt)
            no = self.expression(e["else"], nxt)
            return self.condition(e["test"], yes, no)
        if k == "not":
            return self.expression(e["children"][0], nxt)
        if k in {"and", "or"}:
            children = e.get("children", [])
            if not children:
                return nxt
            target = self.expression(children[-1], nxt)
            for child in reversed(children[:-1]):
                target = self.condition(child, target, nxt) if k == "and" else self.condition(child, nxt, target)
            return target
        for child in reversed(e.get("children", [])):
            nxt = self.expression(child, nxt)
        return nxt

    def condition(self, e: dict | None, yes: str, no: str) -> str:
        e = e or {"kind": "ordinary"}
        k = e.get("kind", "ordinary")
        children = e.get("children", [])
        if k == "unsupported":
            raise UnsupportedControlFlow(e.get("reason", "unsupported condition"))
        if k == "not":
            return self.condition(children[0], no, yes)
        if k == "and":
            target = yes
            for child in reversed(children):
                target = self.condition(child, target, no)
            return target
        if k == "or":
            target = no
            for child in reversed(children):
                target = self.condition(child, yes, target)
            return target
        if k == "ternary":
            a = self.condition(e["then"], yes, no)
            b = self.condition(e["else"], yes, no)
            return self.condition(e["test"], a, b)
        node = self.g.node("binary_decision")
        self.g.edge(node, yes, "true")
        self.g.edge(node, no, "false")
        return self.expression({"kind": "ordinary", "children": children}, node)

    def sequence(self, body: list[dict], nxt: str, brk: str | None = None,
                 cont: str | None = None) -> str:
        for item in reversed(body):
            nxt = self.statement(item, nxt, brk, cont)
        return nxt

    def statement(self, s: dict, nxt: str, brk: str | None, cont: str | None) -> str:
        k = s["kind"]
        if k == "unsupported":
            raise UnsupportedControlFlow(s.get("reason", k))
        if k == "noop":
            return nxt
        if k == "seq":
            return self.sequence(s["body"], nxt, brk, cont)
        if k == "if":
            yes = self.sequence(s.get("then", []), nxt, brk, cont)
            no = self.sequence(s.get("else", []), nxt, brk, cont)
            return self.condition(s["test"], yes, no)
        if k in {"loop", "do_loop"}:
            after = self.sequence(s.get("else", []), nxt, brk, cont)
            head = self.g.node("loop_header")
            update = self.sequence(s.get("update", []), head, nxt, head)
            body = self.sequence(s.get("body", []), update, nxt, update)
            test = self.condition(s.get("test"), body, after)
            self.g.edge(head, test)
            entry = body if k == "do_loop" else head
            entry = self.expression(s.get("iter"), entry)
            return self.sequence(s.get("init", []), entry, brk, cont)
        if k == "switch":
            dispatch = self.g.node("switch")
            fallthrough = nxt
            case_entries = []
            for case in reversed(s.get("cases", [])):
                target = fallthrough if case.get("fallthrough", False) else nxt
                entry = self.sequence(case.get("body", []), target, nxt, cont)
                case_entries.append((case, entry))
                fallthrough = entry
            default_found = False
            for i, (case, entry) in enumerate(reversed(case_entries)):
                if case.get("default", False):
                    default_found = True
                    self.g.edge(dispatch, entry, f"default_{i}")
                for j in range(case.get("labels", 0)):
                    self.g.edge(dispatch, entry, f"case_{i}_{j}")
            if not default_found:
                self.g.edge(dispatch, nxt, "no_match")
            return self.expression(s.get("expr"), dispatch)
        if k == "assert":
            fail = self.g.node("assert_failure")
            self.g.edge(fail, self.exit)
            return self.condition(s.get("test"), nxt, fail)
        if k in {"break", "continue"}:
            target = brk if k == "break" else cont
            if target is None or s.get("label"):
                raise UnsupportedControlFlow("unresolved or labelled loop jump")
            node = self.g.node(k)
            self.g.edge(node, target)
            return node
        if k in {"basic", "return", "throw"}:
            node = self.g.node(k)
            self.g.edge(node, self.exit if k in {"return", "throw"} else nxt)
            return self.expression(s.get("expr"), node)
        raise UnsupportedControlFlow(f"unrecognized IR statement {k!r}")

    def build(self, body: list[dict]) -> CFG:
        body_entry = self.sequence(body, self.exit)
        entry = self.g.node("entry")
        self.g.edge(entry, body_entry)
        self.g.entry = entry
        return self.g.pruned()
