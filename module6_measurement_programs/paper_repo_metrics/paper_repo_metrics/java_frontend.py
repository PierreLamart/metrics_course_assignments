"""Batch Java parsing with the JDK's public syntax-tree API.

The bridge is compiled into a private temporary directory. Measured source
files are parsed only; no project build, annotation processing, or execution.
"""
from __future__ import annotations
import base64
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from .repository import run


def utf16_to_python_offsets(text: str) -> list[int]:
    offsets = [0]
    for i, char in enumerate(text):
        if ord(char) > 0xFFFF:
            offsets.append(i)  # no valid AST boundary lies inside this pair
        offsets.append(i + 1)
    return offsets


def analyze_java_batch(sources: dict[str, str], timeout: int = 120) -> tuple[dict[str, dict], str]:
    if not sources:
        return {}, "not_needed"
    if not shutil.which("javac") or not shutil.which("java"):
        raise RuntimeError("Java AST metrics require JDK 17+ (java and javac on PATH)")
    helper = Path(__file__).with_name("JavaAstBridge.java")
    version_proc = run(["java", "-version"])
    version = (version_proc.stderr or version_proc.stdout).decode("utf-8", "replace").splitlines()[0]
    with TemporaryDirectory(prefix="paper-metrics-java-") as tmp:
        root = Path(tmp)
        compiled = root / "compiled"
        compiled.mkdir()
        run(["javac", "--release", "17", "-encoding", "UTF-8", "-d", str(compiled), str(helper)], timeout=timeout)
        manifest_lines = []
        # Numbered directories prevent path traversal and duplicate basenames.
        for i, (relative, text) in enumerate(sources.items()):
            directory = root / "source" / str(i)
            directory.mkdir(parents=True)
            absolute = directory / "Input.java"
            absolute.write_text(text, encoding="utf-8")
            encoded = [base64.b64encode(x.encode("utf-8")).decode("ascii") for x in (relative, str(absolute))]
            manifest_lines.append("\t".join(encoded))
        manifest = root / "manifest.tsv"
        manifest.write_text("\n".join(manifest_lines), encoding="utf-8")
        result = run(["java", "-Xmx768m", "-Dfile.encoding=UTF-8", "-cp", str(compiled),
                      "JavaAstBridge", str(manifest)], timeout=timeout)
        parsed = {}
        for line in result.stdout.decode("utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            path = item["path"]
            if path not in sources:
                raise RuntimeError(f"Unexpected Java bridge path {path!r}")
            offsets = utf16_to_python_offsets(sources[path])
            for entity in item["classes"] + item["methods"]:
                for key in ("start", "end"):
                    value = entity[key]
                    if not 0 <= value < len(offsets):
                        raise RuntimeError("Invalid Java AST source position")
                    entity[key] = offsets[value]
            parsed[path] = item
        for path in sources.keys() - parsed.keys():
            parsed[path] = {"path": path, "parse_ok": False, "classes": [], "methods": [],
                            "errors": [{"message": "Java parser produced no compilation unit"}]}
        return parsed, version
