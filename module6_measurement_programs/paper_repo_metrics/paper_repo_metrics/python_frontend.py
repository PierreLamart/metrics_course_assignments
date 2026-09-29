"""Python AST -> named classes, named callables, and structured CFG IR.

No import or execution of the measured program occurs. Python visibility is
not equated with Java visibility. Runtime monkey-patching/dynamic dispatch
and dependencies outside this snapshot are explicitly not resolved.
"""
from __future__ import annotations
import ast
from pathlib import PurePosixPath
from typing import Iterator

DEFS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)


def own_walk(node: ast.AST) -> Iterator[ast.AST]:
    """Visit a body, but not nested declaration bodies."""
    todo = list(reversed(getattr(node, "body", [])))
    while todo:
        n = todo.pop()
        yield n
        if not isinstance(n, DEFS):
            todo.extend(reversed(list(ast.iter_child_nodes(n))))


def name_of(node: ast.AST | None) -> str:
    return ast.unparse(node) if node is not None else ""


def expr_ir(node: ast.AST | None) -> dict:
    if node is None:
        return {"kind": "ordinary"}
    if isinstance(node, ast.Lambda):
        return {"kind": "ordinary"}  # deferred body is excluded
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return {"kind": "unsupported", "reason": "Python comprehension/generator CFG"}
    if isinstance(node, (ast.Yield, ast.YieldFrom, ast.Await)):
        return {"kind": "unsupported", "reason": "Python suspension/resumption CFG"}
    if isinstance(node, ast.BoolOp):
        return {"kind": "and" if isinstance(node.op, ast.And) else "or",
                "children": [expr_ir(v) for v in node.values]}
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return {"kind": "not", "children": [expr_ir(node.operand)]}
    if isinstance(node, ast.IfExp):
        return {"kind": "ternary", "test": expr_ir(node.test),
                "then": expr_ir(node.body), "else": expr_ir(node.orelse)}
    if isinstance(node, ast.Compare) and len(node.ops) > 1:
        # Chained comparisons short-circuit. Comparands are represented once
        # in the first ordinary node; these are syntactic paths, not values.
        return {"kind": "and", "children": [
            {"kind": "ordinary", "children": ([expr_ir(node.left)] if i == 0 else []) + [expr_ir(x)]}
            for i, x in enumerate(node.comparators)]}
    return {"kind": "ordinary", "children": [expr_ir(c) for c in ast.iter_child_nodes(node)
                                             if isinstance(c, ast.expr)]}


def stmt_ir(node: ast.stmt) -> dict:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Pass)):
        return {"kind": "noop"}
    if isinstance(node, ast.If):
        return {"kind": "if", "test": expr_ir(node.test),
                "then": [stmt_ir(s) for s in node.body], "else": [stmt_ir(s) for s in node.orelse]}
    if isinstance(node, (ast.While, ast.For)):
        return {"kind": "loop", "test": expr_ir(node.test) if isinstance(node, ast.While) else {"kind": "ordinary"},
                "iter": expr_ir(node.iter) if isinstance(node, ast.For) else None,
                "body": [stmt_ir(s) for s in node.body], "else": [stmt_ir(s) for s in node.orelse]}
    if isinstance(node, ast.Break):
        return {"kind": "break"}
    if isinstance(node, ast.Continue):
        return {"kind": "continue"}
    if isinstance(node, ast.Return):
        return {"kind": "return", "expr": expr_ir(node.value)}
    if isinstance(node, ast.Raise):
        return {"kind": "throw", "expr": expr_ir(node.exc)}
    if isinstance(node, ast.Assert):
        return {"kind": "assert", "test": expr_ir(node.test)}
    if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try), ast.Match,
                         ast.With, ast.AsyncWith, ast.AsyncFor)):
        return {"kind": "unsupported", "reason": f"Python {type(node).__name__} CFG"}
    return {"kind": "basic", "expr": {"kind": "ordinary", "children": [
        expr_ir(n) for n in ast.iter_child_nodes(node) if isinstance(n, ast.expr)]}}


def statement_counts(nodes: list[ast.AST]) -> dict:
    statements = [n for n in nodes if isinstance(n, ast.stmt)]
    decl_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import,
                  ast.ImportFrom, ast.Global, ast.Nonlocal)
    decl = sum(isinstance(n, decl_types) or (isinstance(n, ast.AnnAssign) and n.value is None)
               for n in statements)
    return {"statements": len(statements), "declarative_statements": decl,
            "executable_statements": len(statements) - decl}


def analyze_python(path: str, text: str) -> dict:
    tree = ast.parse(text, filename=path, type_comments=True)
    parts = list(PurePosixPath(path).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    module = ".".join(parts) or "__root__"
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))

    def offset(lineno: int, byte_col: int) -> int:
        line = lines[lineno - 1] if lineno <= len(lines) else ""
        return offsets[lineno - 1] + len(line.encode("utf-8")[:byte_col].decode("utf-8"))

    def span(n: ast.AST) -> dict:
        return {"start_line": n.lineno, "end_line": n.end_lineno,
                "start": offset(n.lineno, n.col_offset),
                "end": offset(n.end_lineno, n.end_col_offset)}

    imports = {}
    for n in tree.body:
        if isinstance(n, ast.Import):
            for alias in n.names:
                imports[alias.asname or alias.name.split(".")[0]] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(n, ast.ImportFrom):
            base = n.module or ""
            if n.level:
                # For __init__, the module itself is the containing package.
                package = module if PurePosixPath(path).stem == "__init__" else module.rpartition(".")[0]
                parent = package.split(".")
                keep = len(parent) - (n.level - 1)
                base = ".".join(parent[:max(0, keep)] + ([base] if base else []))
            for alias in n.names:
                if alias.name != "*":
                    imports[alias.asname or alias.name] = f"{base}.{alias.name}".strip(".")
    classes, methods = [], []

    def visit_body(body: list[ast.stmt], scope: str = "", owner: dict | None = None,
                   enclosing_callable: str | None = None) -> None:
        for n in body:
            if isinstance(n, ast.ClassDef):
                qual = f"{scope}.{n.name}".strip(".")
                cid = f"python:{module}.{qual}@{n.lineno}"
                c = {"id": cid, "name": n.name, "qname": f"{module}.{qual}",
                     "path": path, "language": "python", "module": module,
                     "kind": "class", "imports": imports, "scope": module.split("."),
                     "parent_class": owner["id"] if owner else None,
                     "bases": [name_of(b) for b in n.bases], "interfaces": [],
                     "attributes": [], "method_ids": [], "type_refs": [],
                     "associations": None, "visibility": None, **span(n)}
                # Class-level assignments are class variables, not instance fields.
                attrs = {}
                for item in n.body:
                    if isinstance(item, (ast.Assign, ast.AnnAssign)):
                        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                        for target in targets:
                            if isinstance(target, ast.Name):
                                attrs[target.id] = {"name": target.id, "static": True,
                                                    "type": name_of(item.annotation) if isinstance(item, ast.AnnAssign) else "",
                                                    "visibility": None}
                c["attributes"] = list(attrs.values())
                classes.append(c)
                visit_body(n.body, qual, c, None)
                # Instance attributes observed in direct methods only.
                for m in methods:
                    if m["owner"] == cid:
                        for attr in m.pop("_instance_attrs", []):
                            old = next((a for a in c["attributes"] if a["name"] == attr["name"] and not a["static"]), None)
                            if old is None:
                                c["attributes"].append(attr)
                continue
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qual = f"{scope}.{n.name}".strip(".")
                mid = f"python:{module}.{qual}@{n.lineno}"
                decorators = {name_of(d).split(".")[-1] for d in n.decorator_list}
                static = owner is not None and "staticmethod" in decorators
                classmethod = owner is not None and "classmethod" in decorators
                positional = list(n.args.posonlyargs) + list(n.args.args)
                receiver = positional[0].arg if positional and owner is not None and not static else None
                explicit = positional[1:] if receiver else positional
                params = [{"name": a.arg, "type": name_of(a.annotation)}
                          for a in explicit + list(n.args.kwonlyargs)]
                if n.args.vararg:
                    params.append({"name": n.args.vararg.arg, "type": name_of(n.args.vararg.annotation), "variadic": True})
                if n.args.kwarg:
                    params.append({"name": n.args.kwarg.arg, "type": name_of(n.args.kwarg.annotation), "variadic": True})
                nodes = list(own_walk(n))
                local_types = {a.arg: name_of(a.annotation) for a in positional + list(n.args.kwonlyargs)}
                field_accesses, instance_attrs, calls = set(), {}, []
                handler_nodes = set()
                handlers = [x for x in nodes if isinstance(x, ast.ExceptHandler)]
                for handler in handlers:
                    handler_nodes.update(id(x) for x in own_walk(handler))
                for item in nodes:
                    if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                        local_types[item.target.id] = name_of(item.annotation)
                    if isinstance(item, (ast.Assign, ast.AnnAssign)):
                        targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                        value = item.value
                        inferred = name_of(value.func) if isinstance(value, ast.Call) and isinstance(value.func, (ast.Name, ast.Attribute)) else ""
                        annotation = name_of(item.annotation) if isinstance(item, ast.AnnAssign) else inferred
                        for target in targets:
                            if isinstance(target, ast.Name) and annotation:
                                local_types[target.id] = annotation
                            if receiver and isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == receiver and not classmethod:
                                instance_attrs[target.attr] = {"name": target.attr, "static": False,
                                                              "type": annotation, "visibility": None}
                    if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name):
                        if item.value.id in {receiver, owner["name"] if owner else None}:
                            field_accesses.add(item.attr)
                    if isinstance(item, ast.Call):
                        fn = item.func
                        if isinstance(fn, ast.Name):
                            name, recv = fn.id, ""
                        elif isinstance(fn, ast.Attribute):
                            name, recv = fn.attr, name_of(fn.value)
                        else:
                            name, recv = name_of(fn), "<dynamic>"
                        arity = len(item.args) + len(item.keywords)
                        if any(isinstance(a, ast.Starred) for a in item.args) or any(k.arg is None for k in item.keywords):
                            arity = None
                        calls.append({"name": name, "receiver": recv, "arity": arity,
                                      "line": item.lineno, "in_handler": id(item) in handler_nodes,
                                      "kind": "call"})
                counts = statement_counts(nodes)
                def empty_handler(h: ast.ExceptHandler) -> bool:
                    return all(isinstance(s, ast.Pass) or
                               (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
                               for s in h.body)
                minimum = len(explicit) - min(len(explicit), len(n.args.defaults))
                m = {"id": mid, "name": n.name, "qname": f"{module}.{qual}",
                     "owner": owner["id"] if owner else None, "path": path,
                     "language": "python", "module": module, "imports": imports,
                     "lexical_parent": enclosing_callable, "visibility": None,
                     "static": static or classmethod, "constructor": False,
                     "receiver_name": receiver, "params": params,
                     "arity_min": max(0, minimum), "arity_max": None if n.args.vararg or n.args.kwarg else len(params),
                     "calls": calls, "local_types": local_types,
                     "field_accesses": sorted(field_accesses), "type_refs": list(local_types.values()),
                     "has_body": True, "abstract": "abstractmethod" in decorators,
                     "ir": [stmt_ir(s) for s in n.body], "catch_handlers": len(handlers),
                     "empty_catch_handlers": sum(empty_handler(h) for h in handlers),
                     "_instance_attrs": list(instance_attrs.values()), **counts, **span(n)}
                methods.append(m)
                if owner is not None:
                    owner["method_ids"].append(mid)
                # Nested functions are independent callables, never class methods.
                visit_body(n.body, qual + ".<locals>", None, mid)
                continue
            # Find declarations inside if/loop/try suites without recursing into
            # expression nodes or losing the enclosing lexical owner.
            for field_name in ("body", "orelse", "finalbody"):
                child_body = getattr(n, field_name, None)
                if isinstance(child_body, list):
                    visit_body(child_body, scope, owner, enclosing_callable)
            for handler in getattr(n, "handlers", []):
                visit_body(handler.body, scope, owner, enclosing_callable)
            for case in getattr(n, "cases", []):
                visit_body(case.body, scope, owner, enclosing_callable)

    visit_body(tree.body)
    for m in methods:
        m.pop("_instance_attrs", None)
    all_nodes = list(ast.walk(tree))
    return {"path": path, "language": "python", "module": module,
            "classes": classes, "methods": methods, "warnings": [],
            "metrics": statement_counts(all_nodes), "parse_ok": True}
