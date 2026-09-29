"""Read Git working trees or immutable Git blobs without checking out code.

Remote clones are bare. Submodules, symlinks, repository build scripts and
hooks are not executed. Commands use argument arrays, never shell=True.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory
from typing import Iterator
import fnmatch
import os
import re
import shutil
import subprocess

SUPPORTED = {".py": "python", ".pyi": "python", ".java": "java", ".smali": "smali"}
SOURCE_EXTENSIONS = set(SUPPORTED) | {".c", ".h", ".cpp", ".cc", ".hpp", ".cxx", ".cs",
    ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".rb", ".php", ".kt", ".kts",
    ".swift", ".scala", ".f", ".f90", ".f95", ".m", ".lua", ".sh", ".r"}
DEFAULT_EXCLUDES = [".git", "node_modules", ".venv", "venv", "__pycache__", "vendor",
                    "build", "dist", "target", ".mypy_cache", ".pytest_cache"]


class RepositoryError(RuntimeError):
    pass


def run(args: list[str], *, cwd: Path | None = None, timeout: int = 120,
        check: bool = True, input: bytes | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(key, None)
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        p = subprocess.run(args, cwd=cwd, env=env, input=input, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        raise RepositoryError(str(e)) from e
    if check and p.returncode:
        raise RepositoryError(f"{args[0]} failed ({p.returncode}): {p.stderr.decode('utf-8', 'replace').strip()}")
    return p


def git(root: Path, *args: str, timeout: int = 120, check: bool = True) -> bytes:
    return run(["git", "-c", "core.hooksPath=" + os.devnull,
                "-c", "protocol.ext.allow=never", "-c", "core.fsmonitor=false", "-C", str(root), *args],
               timeout=timeout, check=check).stdout


def safe_relative(path: str) -> PurePosixPath:
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or not p.parts or "\x00" in path:
        raise RepositoryError(f"Unsafe repository path {path!r}")
    return p


def excluded(path: str, patterns: list[str]) -> bool:
    p = PurePosixPath(path)
    return any(pattern in p.parts if not any(c in pattern for c in "/*?[") else
               fnmatch.fnmatchcase(path, pattern) or p.match(pattern)
               for pattern in patterns)


@dataclass
class Source:
    path: str
    language: str | None
    data: bytes | None = None
    reason: str | None = None


@dataclass
class Repository:
    root: Path
    revision: str | None
    include_untracked: bool = False
    timeout: int = 120

    def metadata(self) -> dict:
        commit = git(self.root, "rev-parse", "--verify", "HEAD", check=False).decode().strip() or None
        if self.revision:
            commit = self.revision
        return {"commit": commit, "measurement_source": "git_blobs" if self.revision else "working_tree",
                "working_tree_dirty": None if self.revision else bool(git(self.root, "status", "--porcelain", "--untracked-files=no")),
                "include_untracked": self.include_untracked,
                "git_version": run(["git", "--version"]).stdout.decode().strip()}

    def sources(self, patterns: list[str], max_bytes: int) -> Iterator[Source]:
        if self.revision:
            raw = git(self.root, "ls-tree", "-r", "-z", "--full-tree", self.revision)
            entries = []
            for record in raw.split(b"\0"):
                if not record:
                    continue
                meta, name = record.split(b"\t", 1)
                mode, kind, oid = meta.decode("ascii").split()
                path = os.fsdecode(name)
                entries.append((path, mode, kind, oid))
        else:
            args = ["ls-files", "-z", "--cached"]
            if self.include_untracked:
                args.extend(["--others", "--exclude-standard"])
            names = sorted(set(os.fsdecode(x) for x in git(self.root, *args).split(b"\0") if x))
            entries = [(name, "", "", "") for name in names]
        for path, mode, kind, oid in sorted(entries):
            p = safe_relative(path)
            suffix = p.suffix.lower()
            if suffix not in SOURCE_EXTENSIONS:
                continue
            lang = SUPPORTED.get(suffix)
            if excluded(path, patterns):
                yield Source(path, lang, reason="excluded_by_pattern")
                continue
            if lang is None:
                yield Source(path, None, reason="unsupported_language")
                continue
            if self.revision:
                if mode not in {"100644", "100755"} or kind != "blob":
                    yield Source(path, lang, reason="symlink_or_submodule")
                    continue
                size = int(git(self.root, "cat-file", "-s", oid))
                if size > max_bytes:
                    yield Source(path, lang, reason="file_size_limit")
                    continue
                data = git(self.root, "cat-file", "blob", oid)
            else:
                fp = self.root.joinpath(*p.parts)
                if any(x.is_symlink() for x in [fp, *fp.parents] if x != self.root):
                    yield Source(path, lang, reason="symlink")
                    continue
                try:
                    if not fp.is_file():
                        yield Source(path, lang, reason="deleted_or_not_a_file")
                        continue
                    fp.resolve().relative_to(self.root.resolve())
                    if fp.stat().st_size > max_bytes:
                        yield Source(path, lang, reason="file_size_limit")
                        continue
                    with fp.open("rb") as handle:
                        data = handle.read(max_bytes + 1)
                    if len(data) > max_bytes:
                        yield Source(path, lang, reason="file_size_limit")
                        continue
                except (OSError, ValueError) as e:
                    yield Source(path, lang, reason=f"read_error: {e}")
                    continue
            if b"\0" in data:
                yield Source(path, lang, reason="binary_or_non_utf8_source")
            else:
                yield Source(path, lang, data=data)


@contextmanager
def open_repository(location: str, *, ref: str | None = None,
                    include_untracked: bool = False, timeout: int = 120) -> Iterator[Repository]:
    if not shutil.which("git"):
        raise RepositoryError("Git must be installed and available on PATH")
    if ref and (ref.startswith("-") or "\x00" in ref):
        raise RepositoryError("Invalid ref")
    if ref and include_untracked:
        raise RepositoryError("--include-untracked cannot be combined with --ref")
    local = Path(location).expanduser()
    if local.exists():
        if not local.is_dir():
            raise RepositoryError("Repository path is not a directory")
        local = local.resolve()
        is_bare = git(local, "rev-parse", "--is-bare-repository").decode().strip() == "true"
        root = local if is_bare else Path(git(local, "rev-parse", "--show-toplevel").decode().strip())
        revision = None
        if ref or is_bare:
            revision = git(root, "rev-parse", "--verify", "--end-of-options", (ref or "HEAD") + "^{commit}").decode().strip()
        yield Repository(root, revision, include_untracked, timeout)
        return
    if not (location.startswith(("https://", "ssh://")) or re.match(r"^[\w.-]+@[\w.-]+:", location)):
        raise RepositoryError("Expected a local Git directory, HTTPS URL, or SSH Git URL")
    with TemporaryDirectory(prefix="paper-metrics-clone-") as tmp:
        root = Path(tmp) / "repository.git"
        args = ["git", "-c", "core.hooksPath=" + os.devnull, "-c", "protocol.ext.allow=never",
                "clone", "--bare", "--quiet", "--depth", "1"]
        sha = bool(ref and re.fullmatch(r"[a-fA-F0-9]{40}|[a-fA-F0-9]{64}", ref))
        if ref and not sha:
            args.extend(["--branch", ref])
        args.extend(["--", location, str(root)])
        run(args, timeout=timeout)
        revision_ref = "HEAD"
        if sha:
            git(root, "fetch", "--depth", "1", "origin", ref, timeout=timeout)
            revision_ref = "FETCH_HEAD"
        revision = git(root, "rev-parse", "--verify", revision_ref + "^{commit}").decode().strip()
        yield Repository(root, revision, False, timeout)
