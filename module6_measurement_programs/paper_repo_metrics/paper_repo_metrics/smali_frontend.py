"""Static counts over text Smali already present in a Git repository.

No APK decompilation is performed. Instruction count means opcode statements,
not encoded bytes/code units. Labels, annotations and data payloads are excluded.
"""
from __future__ import annotations
from collections import defaultdict
import re
from .graphs import CFG
from .lexical import smali_lexemes

TYPE = re.compile(r"\[*(?:L[^;]+;|[VZBCSIJFD])")
METHOD = re.compile(r"([^\s(]+)\(([^)]*)\)(\S+)$")
CALL = re.compile(r"(L[^;]+;)->([^\s(]+)\(([^)]*)\)(\S+)")
FIELD = re.compile(r"(L[^;]+;)->([^:\s]+):(\S+)")


def typename(value: str) -> str:
    value = value.lstrip("[")
    return value[1:-1].replace("/", ".") if value.startswith("L") and value.endswith(";") else value


def visibility(flags: list[str]) -> str:
    return next((x for x in ("public", "private", "protected") if x in flags), "default")


def normal_cfg(instructions: list[dict], labels: dict, payloads: dict) -> CFG:
    g = CFG({str(i): x["opcode"] for i, x in enumerate(instructions)}, [], "entry", {"exit"})
    g.nodes.update({"entry": "entry", "exit": "exit"})
    g.edge("entry", "0" if instructions else "exit")
    def target(label: str) -> str:
        if label not in labels:
            raise ValueError(f"Unresolved Smali label {label}")
        n = labels[label]
        return str(n) if n < len(instructions) else "exit"
    for i, ins in enumerate(instructions):
        node, op = str(i), ins["opcode"]
        nxt = str(i + 1) if i + 1 < len(instructions) else "exit"
        operands = ins["text"].split()
        if op.startswith("return") or op == "throw":
            g.edge(node, "exit")
        elif op.startswith("goto"):
            g.edge(node, target(operands[-1]))
        elif op.startswith("if-"):
            g.edge(node, target(operands[-1]), "true")
            g.edge(node, nxt, "false")
        elif op in {"packed-switch", "sparse-switch"}:
            payload = operands[-1]
            if payload not in payloads:
                raise ValueError(f"Missing Smali switch payload {payload}")
            for j, label in enumerate(payloads[payload]):
                g.edge(node, target(label), f"case_{j}")
            g.edge(node, nxt, "default")
        else:
            g.edge(node, nxt)
    return g


def analyze_smali(path: str, text: str) -> dict:
    raw_lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in raw_lines:
        offsets.append(offsets[-1] + len(line))
    clean = {x.start_line: x.text.strip() for x in smali_lexemes(text) if x.kind != "comment"}
    header = next((value for value in clean.values() if value.startswith(".class ")), None)
    if not header:
        raise ValueError("Smali file has no .class directive")
    descriptor = header.split()[-1]
    qname = typename(descriptor)
    cid = f"smali:{qname}@{path}"
    cls = {"id": cid, "qname": qname, "name": qname.rsplit(".", 1)[-1], "path": path,
           "language": "smali", "module": qname.rpartition(".")[0], "imports": {},
           "kind": "interface" if "interface" in header.split() else "class",
           "scope": qname.split(".")[:-1], "parent_class": None,
           "bases": [], "interfaces": [], "attributes": [], "method_ids": [],
           "associations": None, "start": 0, "end": len(text), "start_line": 1,
           "end_line": len(raw_lines)}
    methods, warnings, current = [], [], None
    annotation_depth, payload_kind, payload_name, last_label = 0, None, None, None
    for lineno in range(1, len(raw_lines) + 1):
        line = clean.get(lineno, "")
        if not line:
            continue
        if line.startswith((".annotation", ".subannotation")):
            annotation_depth += 1
            continue
        if line.startswith((".end annotation", ".end subannotation")):
            annotation_depth -= 1
            continue
        if annotation_depth:
            continue
        if line.startswith(".method "):
            if current:
                raise ValueError("Nested .method directive")
            match = METHOD.search(line)
            if not match:
                raise ValueError(f"Invalid Smali method at line {lineno}")
            name, parameter_string, ret = match.groups()
            params_raw = TYPE.findall(parameter_string)
            if "".join(params_raw) != parameter_string:
                raise ValueError("Invalid Smali parameter descriptor")
            flags = line.split()[1:-1]
            signature = descriptor + "->" + name + "(" + parameter_string + ")" + ret
            mid = "smali:" + signature + "@" + path
            current = {"id": mid, "qname": qname + "." + name, "name": name, "raw_signature": signature,
                       "owner": cid, "path": path, "language": "smali", "module": cls["module"],
                       "imports": {}, "visibility": visibility(flags), "static": "static" in flags,
                       "constructor": name in {"<init>", "<clinit>"}, "params": [
                           {"name": f"p{i}", "type": typename(t)} for i, t in enumerate(params_raw)],
                       "arity_min": len(params_raw), "arity_max": len(params_raw),
                       "has_body": not any(x in flags for x in ("abstract", "native")),
                       "abstract": "abstract" in flags, "calls": [], "local_types": {},
                       "field_accesses": [], "type_refs": [], "start": offsets[lineno - 1],
                       "start_line": lineno, "_instructions": [], "_labels": {}, "_payloads": {}, "_handlers": []}
            last_label = None
            continue
        if current and line.startswith(".end method"):
            current["end_line"], current["end"] = lineno, offsets[lineno]
            instructions = current.pop("_instructions")
            labels, payloads, handlers = current.pop("_labels"), current.pop("_payloads"), current.pop("_handlers")
            current["bytecode_instructions"] = len(instructions)
            current["catch_handlers"] = len(handlers)
            current["empty_catch_handlers"] = 0
            try:
                graph = normal_cfg(instructions, labels, payloads)
                normal = graph.reachable()
                adj = defaultdict(list)
                for a, b, _ in graph.edges:
                    adj[a].append(b)
                handler_regions = set()
                for label in handlers:
                    if label not in labels:
                        raise ValueError("Unresolved exception handler label")
                    stack, region = [str(labels[label])], set()
                    while stack:
                        node = stack.pop()
                        if node not in region and node not in normal and node != "exit":
                            region.add(node); stack.extend(adj[node])
                    handler_regions |= region
                    # Strict bytecode convention: only exception capture, nop,
                    # and a jump back to ordinary control flow are action-free.
                    if region and all(graph.nodes[n] in {"move-exception", "nop"} or
                                      graph.nodes[n].startswith("goto") for n in region):
                        current["empty_catch_handlers"] += 1
                for call in current["calls"]:
                    call["in_handler"] = str(call.pop("instruction_index")) in handler_regions
                if handlers:
                    current["cfg_unavailable_reason"] = "Smali exception edges require a compiler CFG/exception policy"
                else:
                    current["supplied_cfg"] = graph.pruned().to_dict()
            except ValueError as error:
                current["cfg_unavailable_reason"] = str(error)
                current["empty_catch_handlers"] = None
                for call in current["calls"]:
                    call.pop("instruction_index", None); call["in_handler"] = None
            current["field_accesses"] = sorted(set(current["field_accesses"]))
            methods.append(current); cls["method_ids"].append(current["id"])
            current = None
            continue
        if current is None:
            if line.startswith(".super "):
                cls["bases"].append(typename(line.split()[-1]))
            elif line.startswith(".implements "):
                cls["interfaces"].append(typename(line.split()[-1]))
            elif line.startswith(".field "):
                declaration = line.split("=", 1)[0].strip().split()
                name, t = declaration[-1].split(":", 1)
                cls["attributes"].append({"name": name, "type": typename(t),
                                          "visibility": visibility(declaration), "static": "static" in declaration})
            continue
        if payload_kind:
            if line.startswith(".end " + payload_kind):
                payload_kind, payload_name = None, None
            elif payload_kind in {"packed-switch", "sparse-switch"}:
                label = line.split()[-1]
                if label.startswith(":"):
                    current["_payloads"][payload_name].append(label)
            continue
        if line.startswith((".packed-switch", ".sparse-switch", ".array-data")):
            payload_kind = line.split()[0][1:]
            payload_name = last_label
            current["_payloads"][payload_name] = []
            continue
        if line.startswith(":"):
            last_label = line.split()[0]
            current["_labels"][last_label] = len(current["_instructions"])
            continue
        if line.startswith((".catch ", ".catchall ")):
            current["_handlers"].append(line.split()[-1])
            continue
        if line.startswith("."):
            continue
        opcode = line.split()[0]
        if not re.fullmatch(r"[a-z][a-z0-9_/-]*", opcode):
            raise ValueError(f"Unrecognized Smali instruction at line {lineno}")
        index = len(current["_instructions"])
        current["_instructions"].append({"opcode": opcode, "text": line, "line": lineno})
        if opcode.startswith("invoke-"):
            match = CALL.search(line)
            if match:
                recv, name, parameters, ret = match.groups()
                current["calls"].append({"name": name, "receiver": typename(recv), "arity": len(TYPE.findall(parameters)),
                                         "line": lineno, "raw_target": match.group(0), "instruction_index": index,
                                         "kind": "constructor" if name == "<init>" else "call"})
            else:
                current["calls"].append({"name": opcode, "receiver": "<dynamic>", "arity": None,
                                         "line": lineno, "instruction_index": index, "kind": "call"})
        if opcode.startswith(("iget", "iput", "sget", "sput")):
            match = FIELD.search(line)
            if match and match.group(1) == descriptor:
                current["field_accesses"].append(match.group(2))
        current["type_refs"].extend(typename(t) for t in re.findall(r"L[^\s;,]+;", line))
    if current:
        raise ValueError("Unterminated .method")
    return {"path": path, "language": "smali", "module": cls["module"], "classes": [cls],
            "methods": methods, "warnings": warnings, "parse_ok": True,
            "metrics": {"bytecode_instructions": sum(m["bytecode_instructions"] for m in methods)}}
