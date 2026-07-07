"""`science project serialize` — deterministic, git-faithful project bundle.

Source files (entities + results, no data/ payloads) + a manifest that
hash-inventories the excluded payloads. See
docs/user-guide/project-packaging.md.
"""

from __future__ import annotations

import gzip
import io
import json
import re
import subprocess
import tarfile
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from science_tool.data_audit import Quadrant, audit_project
from science_tool.data_root import resolve_data_root
from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.project_config import load_project_config, resolve_data_policy
from science_tool.project_package.core import FileResource, content_version, file_resource
from science_tool.project_package.manifest import data_version_chunks
from science_tool.project_package.payload import PayloadError, payload_inventory

SCHEMA_VERSION = "science-project-serialized.v1"
SOURCE_ROOTS = ("entities", "results")
TOP_LEVEL_SINGLES = ("science.yaml", "papers/references.bib", "knowledge/graph.trig")


class SerializeError(Exception):
    """Raised for any hard-fail precondition or guard failure."""


@dataclass(frozen=True)
class SerializeResult:
    out_path: Path
    file_count: int
    payload_count: int
    forced: bool


def _tracked_files(project_root: Path) -> list[str]:
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SerializeError(
            f"not a git worktree (git ls-files failed): {project_root}"
        ) from exc
    return [p for p in out.decode("utf-8").split("\0") if p]


def _selected_source(tracked: list[str]) -> list[str]:
    selected: set[str] = set()
    for rel in tracked:
        if rel in TOP_LEVEL_SINGLES or rel.split("/", 1)[0] in SOURCE_ROOTS:
            selected.add(rel)
    return sorted(selected)


def _payload_inventory(
    project_root: Path,
    data_dirs: tuple[Path, ...],
    tracked_set: set[str],
    data_root: Path | None = None,
) -> list[dict]:
    """Serialize's view of the shared walk: translate guard failures to
    SerializeError so the existing fail-loud contract is unchanged."""
    try:
        return payload_inventory(project_root, data_dirs, tracked_set, data_root=data_root)
    except PayloadError as exc:
        raise SerializeError(str(exc)) from exc


def _build_manifest(
    project_root: Path,
    files: list[FileResource],
    payloads: list[dict],
    *,
    audit_passed: bool,
    forced: bool,
    git_commit: str,
) -> dict:
    config = load_project_config(project_root)
    raw = yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
    base = str(raw.get("last_modified") or raw.get("version") or "0")

    file_records = sorted(
        ({"path": fr.path, "sha256": fr.sha256, "bytes": fr.bytes} for fr in files),
        key=lambda record: record["path"],
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "id": config.id,
            "label": str(raw.get("name") or config.id),
            "summary": raw.get("summary"),
        },
        "data_version": content_version(base, data_version_chunks(file_records, payloads)),
        "provenance": {"git_commit": git_commit, "tool": "science"},
        # `passed` = zero blocking payload-boundary violations (STRANDED_RECORD /
        # LEAKED_PAYLOAD / TRACKED_PAYLOAD); non-blocking FLAG findings are not counted.
        "boundary_audit": {"passed": audit_passed, "forced": forced},
        "files": file_records,
        "payloads": payloads,
    }


def _write_archive(
    out_path: Path,
    project_root: Path,
    project_id: str,
    files: list[FileResource],
    manifest: dict,
) -> None:
    members: list[tuple[str, bytes]] = [(
        f"{project_id}/manifest.json",
        (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    )]
    for fr in files:
        members.append((f"{project_id}/{fr.path}", (project_root / fr.path).read_bytes()))
    members.sort(key=lambda m: m[0])

    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for arcname, data in members:
                info = tarfile.TarInfo(arcname)
                info.size = len(data)
                info.mtime = 0
                info.mode = 0o644
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                info.type = tarfile.REGTYPE
                tar.addfile(info, io.BytesIO(data))
    out_path.write_bytes(raw.getvalue())


_SAFE_ID_RE = re.compile(r"\A[A-Za-z0-9._-]+\Z")
_BOUNDARY_QUADRANTS = {
    Quadrant.STRANDED_RECORD,
    Quadrant.LEAKED_PAYLOAD,
    Quadrant.TRACKED_PAYLOAD,
}


def _out_inside_root(project_root: Path, out_archive: Path) -> bool:
    root = project_root.resolve()
    out_abs = out_archive.parent.resolve() / out_archive.name
    return root == out_abs or root in out_abs.parents


def _head_commit(project_root: Path) -> str:
    """HEAD sha; hard-fail if the repo has no commit (reproducibility anchor)."""
    try:
        return subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise SerializeError(
            "repository has no HEAD commit; nothing committed to serialize from"
        ) from exc


def _assert_regular_source(project_root: Path, source_rels: list[str]) -> None:
    for rel in source_rels:
        p = project_root / rel
        if p.is_symlink():
            raise SerializeError(f"selected source is a symlink (not git-faithful): {rel}")
        if not p.is_file():
            raise SerializeError(f"selected source is not a regular file: {rel}")


def _assert_clean_source(project_root: Path) -> None:
    """Every selected source path must match HEAD, so git_commit truly reproduces it."""
    pathspecs = [*SOURCE_ROOTS, *TOP_LEVEL_SINGLES]
    result = subprocess.run(
        ["git", "-C", str(project_root), "diff", "--name-only", "HEAD", "--", *pathspecs],
        capture_output=True, text=True, check=True,
    )
    dirty = [p for p in result.stdout.splitlines() if p]
    if dirty:
        raise SerializeError(
            f"refusing to serialize: {len(dirty)} selected source file(s) differ from HEAD "
            f"(e.g. {dirty[0]}). Commit or stash before serializing."
        )


def _assert_safe_project_id(project_id: str) -> None:
    if project_id in ("", ".", "..") or "/" in project_id or "\\" in project_id \
            or not _SAFE_ID_RE.match(project_id):
        raise SerializeError(f"unsafe project id for archive path: {project_id!r}")


def _config_error(exc: Exception) -> SerializeError:
    return SerializeError(f"invalid or unreadable science.yaml: {exc}")


def serialize_project(
    project_root: Path,
    out_archive: Path,
    *,
    force: bool = False,
) -> SerializeResult:
    project_root = project_root.expanduser().resolve()
    out_archive = out_archive.expanduser()

    if _out_inside_root(project_root, out_archive):
        raise SerializeError(f"--out must not be inside the project root: {out_archive}")
    if not (project_root / "science.yaml").exists():
        raise SerializeError(f"missing science.yaml: {project_root / 'science.yaml'}")

    tracked = _tracked_files(project_root)  # raises if not a git worktree
    if "science.yaml" not in tracked:
        raise SerializeError("science.yaml is not git-tracked; cannot build a portable bundle")
    commit = _head_commit(project_root)  # raises if no HEAD commit

    source_rels = _selected_source(tracked)
    _assert_regular_source(project_root, source_rels)
    _assert_clean_source(project_root)

    try:
        policy = resolve_data_policy(load_project_config(project_root))
    except (OSError, ValueError, yaml.YAMLError, ValidationError) as exc:
        raise _config_error(exc) from exc

    all_violations = audit_project(project_root, policy)
    violations = [v for v in all_violations if v.quadrant in _BOUNDARY_QUADRANTS]
    if violations and not force:
        quadrants = sorted({v.quadrant.value for v in violations})
        raise SerializeError(
            f"refusing to serialize: {len(violations)} data-audit boundary violation(s) "
            f"[{', '.join(quadrants)}]. Run `science data audit` to inspect, or pass --force."
        )
    forced = bool(violations) and force

    try:
        files = [file_resource(project_root, rel) for rel in source_rels]
        payloads = _payload_inventory(
            project_root,
            DEFAULT_DATA_DIRS,
            set(tracked),
            data_root=resolve_data_root(project_root),
        )
    except OSError as exc:
        raise SerializeError(f"filesystem error reading project source: {exc}") from exc

    try:
        manifest = _build_manifest(
            project_root, files, payloads,
            audit_passed=not violations, forced=forced, git_commit=commit,
        )
    except (OSError, ValueError, yaml.YAMLError, ValidationError) as exc:
        raise _config_error(exc) from exc

    _assert_safe_project_id(manifest["project"]["id"])

    try:
        out_archive.parent.mkdir(parents=True, exist_ok=True)
        _write_archive(out_archive, project_root, manifest["project"]["id"], files, manifest)
    except OSError as exc:
        raise SerializeError(f"filesystem error writing archive: {exc}") from exc
    return SerializeResult(out_archive, len(files), len(payloads), forced)
