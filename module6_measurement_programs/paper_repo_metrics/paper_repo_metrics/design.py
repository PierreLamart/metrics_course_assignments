"""P7 design metrics from normalized JSON or a supported subset of UML2 XMI.

Association links come from the design model. Attribute types are deliberately
NOT treated as association edges. Scope-branch interpretation is explicit.
"""
from __future__ import annotations
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from .model import measure_model

DESIGN_KEYS = ["attribute_count", "method_count", "public_methods", "setters", "getters",
              "interfaces_implemented", "noc_children", "num_descendants", "num_ancestors_known", "dit",
              "cld", "inherited_operations_known", "inherited_attributes_known", "direct_interface_clients",
              "indirect_interface_clients", "num_ass_el_ssc", "num_ass_el_sb", "num_ass_el_nsb",
              "ec_attr_known", "ic_attr_known", "ec_par_known", "ic_par_known", "assoc", "nesting"]


def normalize(data: dict) -> tuple[list[dict], list[dict]]:
    classes, methods = [], []
    for raw in data["classes"]:
        cid = str(raw["id"])
        scope = list(raw.get("scope", []))
        name = raw.get("name", cid)
        c = {"id": cid, "qname": raw.get("qname", ".".join(scope + [name])),
             "name": name, "scope": scope, "module": ".".join(scope), "path": "<design-model>",
             "language": "uml", "kind": raw.get("kind", "class"), "imports": {},
             "bases": raw.get("parents", []), "interfaces": raw.get("interfaces", []),
             "parent_class": raw.get("nested_in"), "attributes": raw.get("attributes", []),
             "method_ids": [], "associations": None}
        for i, op in enumerate(raw.get("operations", [])):
            params = op.get("parameters", [])
            mid = f"{cid}::op::{i}"
            m = {"id": mid, "name": op["name"], "qname": c["qname"] + "." + op["name"],
                 "owner": cid, "path": "<design-model>", "language": "uml",
                 "module": c["module"], "imports": {}, "params": params, "visibility": op.get("visibility"),
                 "static": op.get("static", False), "constructor": op.get("constructor", False),
                 "calls": [], "type_refs": [], "has_body": False,
                 "arity_min": len(params), "arity_max": len(params)}
            methods.append(m); c["method_ids"].append(mid)
        classes.append(c)
    return classes, methods


def xmi_to_normalized(path: Path, *, scope_branch_policy: str | None = None) -> dict:
    raw = path.read_bytes()
    if len(raw) > 32 * 1024 * 1024:
        raise ValueError("XMI exceeds 32 MiB input limit")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("DTD/entity declarations are not accepted in XMI")
    root = ET.fromstring(raw)
    def local(tag): return tag.rsplit("}", 1)[-1]
    def attr(element, name):
        return next((v for k, v in element.attrib.items() if local(k) == name and "}" in k), None)
    def kind(element):
        return (attr(element, "type") or local(element.tag)).rsplit(":", 1)[-1]
    def type_ref(element):
        if element.get("type"):
            return element.get("type")
        for child in element:
            if local(child.tag) == "type":
                return attr(child, "idref") or child.get("href", "")
        return ""
    all_elements = list(root.iter())
    properties = {attr(e, "id"): type_ref(e) for e in all_elements if attr(e, "id") and type_ref(e)}
    classes, association_nodes = [], []
    warnings = []
    def walk(element, scope=(), nested_in=None):
        k = kind(element)
        if k == "Association":
            association_nodes.append(element)
            return
        if k in {"Package", "Model"}:
            name = element.get("name", "")
            if name and k == "Package": scope = (*scope, name)
        if k in {"Class", "Interface"}:
            cid = attr(element, "id")
            if not cid:
                raise ValueError("UML classifier is missing xmi:id")
            c = {"id": cid, "name": element.get("name", cid), "kind": k.lower(),
                 "scope": list(scope), "nested_in": nested_in,
                 "attributes": [], "operations": [], "parents": [], "interfaces": []}
            for child in element:
                tag = local(child.tag)
                if tag == "generalization":
                    c["parents"].append(child.get("general", ""))
                elif tag in {"interfaceRealization", "realization"}:
                    c["interfaces"].append(child.get("contract", child.get("supplier", "")))
                elif tag == "ownedAttribute":
                    c["attributes"].append({"name": child.get("name", attr(child, "id") or ""),
                                             "type": type_ref(child), "visibility": child.get("visibility"),
                                             "static": child.get("isStatic", "false") == "true"})
                elif tag == "ownedOperation":
                    params = [{"name": p.get("name", ""), "type": type_ref(p)} for p in child
                              if local(p.tag) == "ownedParameter" and p.get("direction", "in") != "return"]
                    c["operations"].append({"name": child.get("name", ""), "parameters": params,
                                             "visibility": child.get("visibility"),
                                             "static": child.get("isStatic", "false") == "true"})
            classes.append(c)
            for child in element:
                if kind(child) in {"Class", "Interface", "Association"}:
                    walk(child, (*scope, c["name"]), cid)
            return
        for child in element:
            walk(child, scope, nested_in)
    walk(root)
    if not classes:
        raise ValueError("No supported UML2 Class/Interface classifiers found; use normalized JSON for other XMI dialects")
    ids = {c["id"] for c in classes}
    pairs = set()
    for a in association_nodes:
        endpoints = [properties.get(x, "") for x in a.get("memberEnd", "").split()]
        endpoints += [type_ref(c) for c in a if local(c.tag) == "ownedEnd"]
        endpoints = list(dict.fromkeys(x for x in endpoints if x))
        if len(endpoints) != 2 or not set(endpoints) <= ids:
            warnings.append("Association omitted: not a binary association between supported classifiers")
            continue
        pairs.add(tuple(sorted(endpoints)))
    return {"classes": classes, "associations": [list(x) for x in sorted(pairs)],
            "scope_branch_policy": scope_branch_policy, "warnings": warnings,
            "xmi_support": "UML2 Class/Interface, owned members, generalizations, interfaceRealization, binary associations"}


def measure_design(data: dict) -> dict:
    classes, methods = normalize(data)
    linkage = measure_model(classes, methods, include_constructors=True,
                            associations=data.get("associations"),
                            scope_branch_policy=data.get("scope_branch_policy"))
    return {"class_count": len(classes), "classes": [
                {"id": c["id"], "name": c["name"], "metrics": {key: c["metrics"][key] for key in DESIGN_KEYS},
                 "linkage": c["linkage"]} for c in classes],
            "warnings": data.get("warnings", []), "scope_branch_policy": linkage["scope_branch_policy"],
            "root_depth": 0,
            "policy": "Explicit model relations only; return parameters excluded; inherited members deduplicated by signature/name"}


def load_design(path: Path, scope_branch_policy: str | None = None) -> dict:
    if path.suffix.lower() in {".xmi", ".uml", ".xml"}:
        data = xmi_to_normalized(path, scope_branch_policy=scope_branch_policy)
    else:
        data = json.loads(path.read_text(encoding="utf-8"))
        if scope_branch_policy:
            data["scope_branch_policy"] = scope_branch_policy
    return measure_design(data)
