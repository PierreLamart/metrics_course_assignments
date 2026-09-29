"""Command-line interface; JSON output is strict (no NaN or infinity)."""
from __future__ import annotations
import argparse
import csv
import json
import os
from pathlib import Path
import sys
import tempfile
from .analyzer import analyze_repository, catalog
from .design import load_design
from .evaluation import evaluate
from .graphs import CFG, graph_metrics
from .repository import RepositoryError


def load_json(path: Path | None):
    if path is None:
        return None
    if path.stat().st_size > 32 * 1024 * 1024:
        raise ValueError(f"JSON input exceeds 32 MiB: {path}")
    def invalid_constant(value):
        raise ValueError(f"Nonfinite JSON number {value} is not permitted")
    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid_constant)


def write_json(data: dict, path: Path | None) -> None:
    encoded = json.dumps(data, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
    if path is None:
        print(encoded, end="")
        return
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents leaving a truncated report on failure.
    fd, temporary = tempfile.mkstemp(prefix=".metrics-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            file.write(encoded)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def write_csvs(report: dict, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for section in ("files", "classes", "methods"):
        rows = []
        for item in report.get(section, []):
            row = {k: item.get(k) for k in ("id", "path", "name", "language", "start_line", "end_line", "status") if k in item}
            row.update(item.get("metrics", {}))
            rows.append(row)
        columns = sorted({key for row in rows for key in row})
        with (directory / f"{section}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                clean = {}
                for key, value in row.items():
                    if isinstance(value, (list, dict)): value = json.dumps(value, ensure_ascii=True)
                    # Escape spreadsheet-formula injection in repository names.
                    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")): value = "'" + value
                    clean[key] = value
                writer.writerow(clean)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Paper-derived Git repository metrics with explicit coverage and policies")
    subs = p.add_subparsers(dest="command", required=True)
    scan = subs.add_parser("scan", help="Measure a local Git working tree or an HTTPS/SSH repository")
    scan.add_argument("repository")
    scan.add_argument("--ref", help="Commit/tag/branch; read immutable blobs without modifying your checkout")
    scan.add_argument("--include-untracked", action="store_true")
    scan.add_argument("--exclude", action="append", default=[], help="Repeatable relative-path glob or directory name")
    scan.add_argument("--no-default-excludes", action="store_true")
    scan.add_argument("--include-constructors", action="store_true", help="Include explicit Java/Smali constructors in NOM/WMC")
    scan.add_argument("--k", type=float, default=2.0, help="RCIM population-standard-deviation multiplier")
    scan.add_argument("--max-file-bytes", type=int, default=2000000)
    scan.add_argument("--max-files", type=int, default=10000)
    scan.add_argument("--max-path-steps", type=int, default=100000)
    scan.add_argument("--timeout", type=int, default=120, help="Git/JDK subprocess timeout in seconds")
    scan.add_argument("--include-cfg", action="store_true", help="Include constructed graphs in method records")
    scan.add_argument("--cfg-input", type=Path, help="JSON mapping method IDs to compiler CFGs")
    scan.add_argument("--api-rules", type=Path, help="JSON map of Android/API metric names to signature globs")
    scan.add_argument("--aux", type=Path, help="Predictions, telemetry, vendor scores, etc. in explicit auxiliary JSON")
    scan.add_argument("--design-model", type=Path, help="Normalized UML JSON or supported UML2 XMI")
    scan.add_argument("--scope-branch-policy", choices=["prefix_comparable"])
    scan.add_argument("--csv-dir", type=Path)
    scan.add_argument("--output", "-o", type=Path)
    scan.add_argument("--fail-on-incomplete", action="store_true", help="Write report, then return exit code 2 on missing structural/CFG coverage")
    for name, helptext in (("evaluate", "Measure predictions, telemetry and supplied scores"),
                           ("model", "Measure a UML/normalized design model"),
                           ("graph", "Measure a supplied control-flow graph")):
        sp = subs.add_parser(name, help=helptext)
        sp.add_argument("input", type=Path)
        sp.add_argument("--output", "-o", type=Path)
        if name == "model": sp.add_argument("--scope-branch-policy", choices=["prefix_comparable"])
        if name == "graph": sp.add_argument("--max-path-steps", type=int, default=100000)
    cp = subs.add_parser("catalog", help="Show metric aliases, provenance, and unsupported definitions")
    cp.add_argument("--output", "-o", type=Path)
    return p


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.command == "scan":
            report = analyze_repository(args.repository, ref=args.ref, include_untracked=args.include_untracked,
                exclude=args.exclude, use_default_excludes=not args.no_default_excludes,
                include_constructors=args.include_constructors, k=args.k, max_file_bytes=args.max_file_bytes,
                max_files=args.max_files, max_path_steps=args.max_path_steps, timeout=args.timeout,
                keep_cfg=args.include_cfg, api_rules=load_json(args.api_rules), auxiliary=load_json(args.aux),
                cfg_overrides=load_json(args.cfg_input), design_model=args.design_model,
                scope_branch_policy=args.scope_branch_policy)
            write_json(report, args.output)
            if args.csv_dir: write_csvs(report, args.csv_dir)
            coverage = report["coverage"]
            if args.output:
                print(f"Wrote {args.output}; {coverage['structurally_measured_files']}/{coverage['selected_source_files']} selected source files parsed; "
                      f"{coverage['callables_with_cc']}/{coverage['callables_with_bodies']} callable CFGs measured.", file=sys.stderr)
            incomplete = not coverage["full_structural_coverage_of_selected_files"] or coverage["callables_with_cc"] < coverage["callables_with_bodies"]
            return 2 if args.fail_on_incomplete and incomplete else 0
        if args.command == "catalog": report = catalog()
        elif args.command == "evaluate": report = evaluate(load_json(args.input))
        elif args.command == "model": report = load_design(args.input, args.scope_branch_policy)
        else: report = graph_metrics(CFG.from_dict(load_json(args.input)), args.max_path_steps)
        write_json(report, args.output)
        return 0
    except (RepositoryError, ValueError, KeyError, TypeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
