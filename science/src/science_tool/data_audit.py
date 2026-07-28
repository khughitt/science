# science/src/science_tool/data_audit.py
"""Detection pass for `science data audit`.

Cross-checks each project file's (class × location × git-tracked) into violation
quadrants and renders the stable `--json` contract. Read-only — the fixer lives in
data_audit_fix.py. See docs/conventions/data-boundary.md.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict
from science_model.audit import (
    FindingRule,
    FindingSection,
    PathSubject,
    ProjectSubject,
)
from science_model.frontmatter import project_config_path

from science_tool.boundary.gitio import BoundaryGitError, visible_paths
from science_tool.data_root import resolve_data_root
from science_tool.data_policy import (
    DEFAULT_DATA_POLICY,
    DataPolicy,
    FileClass,
    classify,
)
from science_tool.data_worktree import DEFAULT_DATA_DIRS
from science_tool.findings.producers import FindingProducer, FindingProducerResult
from science_tool.instruments import InstrumentResult
from science_tool.project_config import load_project_config


class Quadrant(StrEnum):
    STRANDED_RECORD = "stranded_record"
    LEAKED_PAYLOAD = "leaked_payload"
    TRACKED_PAYLOAD = "tracked_payload"
    FLAG = "flag"


@dataclass(frozen=True)
class Violation:
    quadrant: Quadrant
    path: str  # repo-relative posix
    file_class: FileClass
    proposed_target: str | None


@dataclass(frozen=True)
class AuditNote:
    severity: Literal["info", "warning"]
    code: str
    message: str


@dataclass(frozen=True)
class DataAuditSnapshot:
    violations: tuple[Violation, ...]
    notes: tuple[AuditNote, ...]


class DataViolationQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quadrant: str
    file_class: str


class DataAuditNoteQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


SECTION = FindingSection(id="data-audit", title="Data audit", section_order=300)
DATA_RULES = {
    quadrant: FindingRule(
        id=f"data.violation.{quadrant.value.replace('_', '-')}",
        severities=frozenset({"warn"}),
        subject_types=frozenset({"path"}),
        qualifier_schema=DataViolationQualifiers,
        remediation="producer",
        remediator="data-audit",
        title=f"Data {quadrant.value.replace('_', ' ')}",
        section=SECTION.id,
        display_order=index,
    )
    for index, quadrant in enumerate(Quadrant, start=1)
}
DATA_AUDIT_NOTE_RULE = FindingRule(
    id="data.audit-note",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"project"}),
    qualifier_schema=DataAuditNoteQualifiers,
    identity_qualifiers=("code",),
    title="Data audit note",
    section=SECTION.id,
    display_order=5,
)
DATA_AUDIT_PRODUCER = FindingProducer(
    producer_id="data-audit",
    namespace="data_audit",
    source_module="data_audit.py",
    rules=(*DATA_RULES.values(), DATA_AUDIT_NOTE_RULE),
    sections=(SECTION,),
    remediators=frozenset({"data-audit"}),
)


def collect_data_audit(
    project_root: Path,
    policy: DataPolicy = DEFAULT_DATA_POLICY,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> DataAuditSnapshot:
    return DataAuditSnapshot(
        violations=tuple(audit_project(project_root, policy, data_dirs)),
        notes=tuple(audit_project_notes(project_root)),
    )


def _violation_message(violation: Violation) -> str:
    return (
        f"{violation.file_class.value} file is in the "
        f"{violation.quadrant.value.replace('_', ' ')} quadrant."
    )


def data_audit_result(snapshot: DataAuditSnapshot) -> FindingProducerResult:
    findings = [
        DATA_RULES[violation.quadrant].build(
            subject=PathSubject(path=violation.path),
            severity="warn",
            qualifiers={
                "quadrant": violation.quadrant.value,
                "file_class": violation.file_class.value,
            },
            message=_violation_message(violation),
        )
        for violation in snapshot.violations
    ]
    findings.extend(
        DATA_AUDIT_NOTE_RULE.build(
            subject=ProjectSubject(),
            severity="warn",
            qualifiers={"code": note.code},
            message=note.message,
        )
        for note in snapshot.notes
        if note.severity == "warning"
    )
    return FindingProducerResult(instrument=InstrumentResult.from_rows(findings))


def run_data_audit(
    project_root: Path,
    policy: DataPolicy = DEFAULT_DATA_POLICY,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> FindingProducerResult:
    return data_audit_result(collect_data_audit(project_root, policy, data_dirs))


def git_tracked_set(project_root: Path) -> set[str]:
    """Posix paths of all git-tracked files. Empty set if not a git repo."""
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), "ls-files", "-z"],
            capture_output=True, check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    return {p for p in out.decode("utf-8").split("\0") if p}


_NOT_A_GIT_REPOSITORY = "fatal: not a git repository (or any of the parent directories): .git"


def _discover_git_root(project_root: Path) -> Path | None:
    """Return the containing worktree root, or None for a genuine non-repository.

    The C locale makes the one documented non-repository diagnostic stable. Any
    other probe failure -- including a corrupt `.git` marker -- is operational
    and must reach the caller rather than silently expanding audit scope.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(project_root), "rev-parse", "--is-inside-work-tree", "--show-toplevel"],
            capture_output=True,
            check=False,
            env={**os.environ, "LC_ALL": "C", "LANG": "C"},
        )
    except OSError as exc:
        raise BoundaryGitError(f"git discovery failed: {exc}") from exc

    stderr = proc.stderr.decode("utf-8", "replace").strip()
    if proc.returncode == 128 and stderr == _NOT_A_GIT_REPOSITORY:
        if any(os.path.lexists(parent / ".git") for parent in (project_root, *project_root.parents)):
            raise BoundaryGitError(
                "git discovery reported no repository despite a .git marker; refusing all-path fallback"
            )
        return None
    if proc.returncode != 0:
        raise BoundaryGitError(f"git discovery failed ({proc.returncode}): {stderr}")

    fields = proc.stdout.decode("utf-8", "replace").splitlines()
    if len(fields) != 2 or fields[0] != "true":
        raise BoundaryGitError("git discovery returned malformed worktree metadata")
    root = Path(fields[1])
    if not root.is_absolute():
        raise BoundaryGitError(f"git discovery returned a non-absolute worktree root: {root!s}")
    return root.resolve()


def location(rel_path: Path, data_dirs: tuple[Path, ...]) -> str:
    for d in data_dirs:
        if rel_path == d or d in rel_path.parents:
            return "DATA"
    top = rel_path.parts[0] if rel_path.parts else ""
    if top == "results":
        return "RESULTS"
    if top == "entities":
        return "ENTITIES"
    return "TRACKED_OTHER"


def _data_subpath(rel_path: Path, data_dirs: tuple[Path, ...]) -> Path | None:
    """The path *relative to* the matching data dir, e.g. data/processed/exp/a → exp/a."""
    for d in data_dirs:
        if d in rel_path.parents:
            return rel_path.relative_to(d)
    return None


def _workflow_slug_from_siblings(project_root: Path, rel_path: Path) -> str | None:
    """Inspect a sibling datapackage for an explicit `workflow:` field only.

    Resolution step 1. The `name` field (`<workflow-slug>-<run>-<out>`) is NOT parsed:
    workflow slugs themselves contain hyphens, so the segment boundaries are ambiguous
    from the string alone. Without an explicit `workflow:` field we fall back to the
    first path segment (step 2 in the caller).
    """
    sib_dir = (project_root / rel_path).parent
    for name in ("datapackage.yaml", "datapackage.json"):
        dp_path = sib_dir / name
        if not dp_path.is_file():
            continue
        try:
            dp = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(dp, dict):
            wf = dp.get("workflow")
            if isinstance(wf, str) and wf:
                return wf.removeprefix("workflow:")
    return None


def propose_results_target(
    project_root: Path, rel_path: Path, data_dirs: tuple[Path, ...]
) -> str | None:
    """results/<nearest-exp-or-workflow>/<substructure-beneath-segment>."""
    sub = _data_subpath(rel_path, data_dirs)
    if sub is None or not sub.parts:
        return None
    slug = _workflow_slug_from_siblings(project_root, rel_path)
    if slug is None:
        if len(sub.parts) > 1:
            slug = sub.parts[0]
        else:
            # No experiment segment and no workflow: sibling → no unambiguous
            # results/<exp>/ target. Conservative: propose nothing (fixer FLAGs).
            return None
    beneath = Path(*sub.parts[1:]) if len(sub.parts) > 1 else Path(sub.name)
    return (Path("results") / slug / beneath).as_posix()


def _iter_project_files(project_root: Path, data_dirs: tuple[Path, ...]):
    """Yield (abs_path, rel_path) for project files.

    The real tree is walked without following symlinks; symlinked dirs whose realpath
    escapes project_root are pruned (avoids scanning arbitrary external trees / loops).
    A *DEFAULT_DATA_DIRS* entry that is itself a symlink (the data_worktree hydration
    case) is a known, bounded payload dir, so it gets a supplementary follow-links scan
    — its records must still be *reported* (the fixer FLAGs rather than moves them)."""
    seen: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(project_root):
        dirnames[:] = [
            d for d in dirnames
            if d != ".git" and not _escapes_root(project_root, Path(dirpath) / d)
        ]
        for fn in filenames:
            abs_path = Path(dirpath) / fn
            if abs_path.is_symlink():
                continue
            rel = abs_path.relative_to(project_root)
            seen.add(rel.as_posix())
            yield abs_path, rel
    # Supplementary: symlinked known data dirs (not descended above).
    for d in data_dirs:
        entry = project_root / d
        if not (entry.is_symlink() and entry.is_dir()):
            continue
        for dirpath, _dirnames, filenames in os.walk(entry, followlinks=True):
            for fn in filenames:
                abs_path = Path(dirpath) / fn
                rel = abs_path.relative_to(project_root)
                if rel.as_posix() in seen:
                    continue
                seen.add(rel.as_posix())
                yield abs_path, rel


def audit_project(
    project_root: Path,
    policy: DataPolicy = DEFAULT_DATA_POLICY,
    data_dirs: tuple[Path, ...] = DEFAULT_DATA_DIRS,
) -> list[Violation]:
    """Advisory discovery pass. Blocks nothing; enforcement is the boundary checks.

    SCOPE: skip a path that is ignored AND outside every declared boundary root.
    Ignored tooling noise (.venv, node_modules) is not the audit's business, but
    a stranded record inside an ignored payload root is exactly what it exists to
    find -- so blanket-pruning ignored paths would be wrong.
    """
    git_root = _discover_git_root(project_root)
    tracked = git_tracked_set(project_root) if git_root is not None else set()
    # Deliberately NOT wrapped: treating an invalid declaration as absent would
    # drop every declared root out of scope and hide the stranded records inside
    # them -- failing open exactly where the config is broken.
    config_path = project_config_path(project_root)
    boundary = load_project_config(project_root).boundary if config_path.exists() else None
    declared = tuple(r.path for r in boundary.roots) if boundary else ()
    # `data audit` also supports bare project directories, which have no Git
    # ignore semantics; in that case every walked path remains in scope.
    visible = visible_paths(project_root) if git_root is not None else None
    hydrated_data_dirs = tuple(d for d in data_dirs if (project_root / d).is_symlink())

    violations: list[Violation] = []
    for abs_path, rel in _iter_project_files(project_root, data_dirs):
        posix = rel.as_posix()
        in_declared_root = any(posix == d or posix.startswith(d + "/") for d in declared)
        # Git exposes the untracked symlink but not its descendants. Those
        # descendants are not ignored, and the walk explicitly promises to
        # report their records.
        in_hydrated_data_dir = any(rel == d or d in rel.parents for d in hydrated_data_dirs)
        if (
            visible is not None
            and posix not in visible
            and not in_declared_root
            and not in_hydrated_data_dir
        ):
            continue
        try:
            size = abs_path.stat().st_size
        except OSError:
            continue
        cls = classify(rel, size, policy)
        loc = location(rel, data_dirs)
        is_tracked = posix in tracked
        v = _violation_for(project_root, rel, cls, loc, is_tracked, data_dirs)
        if v is not None:
            violations.append(v)
    violations.sort(key=lambda v: v.path)
    return violations


def _violation_for(project_root, rel, cls, loc, is_tracked, data_dirs) -> Violation | None:
    if cls is FileClass.RECORD and loc == "DATA":
        return Violation(
            Quadrant.STRANDED_RECORD, rel.as_posix(), cls,
            propose_results_target(project_root, rel, data_dirs),
        )
    if cls is FileClass.PAYLOAD and is_tracked and loc != "DATA":
        return Violation(
            Quadrant.LEAKED_PAYLOAD, rel.as_posix(), cls, "data/processed/" + rel.name,
        )
    if cls is FileClass.PAYLOAD and is_tracked and loc == "DATA":
        # Tracked payload sitting in ignored data/ territory. Remediation is
        # `git rm --cached` (untrack-in-place); never an auto-move, so no target.
        return Violation(Quadrant.TRACKED_PAYLOAD, rel.as_posix(), cls, None)
    if cls is FileClass.FLAG:
        return Violation(Quadrant.FLAG, rel.as_posix(), cls, None)
    return None


def _escapes_root(project_root: Path, candidate: Path) -> bool:
    """True if candidate is a symlink whose realpath is outside project_root."""
    if not candidate.is_symlink():
        return False
    try:
        real = candidate.resolve()
        root = project_root.resolve()
        return root != real and root not in real.parents
    except OSError:
        return True


def audit_project_notes(project_root: Path) -> list[AuditNote]:
    project_root = project_root.resolve()
    data_root = resolve_data_root(project_root).resolve(strict=False)
    notes: list[AuditNote] = []
    if not _is_relative_to(data_root, project_root):
        notes.append(
            AuditNote(
                "info",
                "external-data-root",
                f"external data root: {data_root} (not walked by repo-boundary audit)",
            )
        )
    tracked_under_root = _tracked_paths_under_data_root(project_root, data_root)
    if tracked_under_root:
        shown = ", ".join(tracked_under_root[:5])
        suffix = "" if len(tracked_under_root) <= 5 else f", +{len(tracked_under_root) - 5} more"
        notes.append(
            AuditNote(
                "warning",
                "tracked-data-root",
                f"git-tracked file(s) under data root: {shown}{suffix}",
            )
        )
    return notes


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _tracked_paths_under_data_root(project_root: Path, data_root: Path) -> list[str]:
    if not _is_relative_to(data_root, project_root):
        return []
    data_rel = data_root.relative_to(project_root)
    return sorted(
        rel
        for rel in git_tracked_set(project_root)
        if Path(rel) == data_rel or data_rel in Path(rel).parents
    )


_DATAPACKAGE_NAMES = ("datapackage.yaml", "datapackage.json")


def _planned_action(v: Violation) -> str:
    """The action the fixer *would* take, for read-only report parity with --fix."""
    if v.quadrant is Quadrant.STRANDED_RECORD:
        if v.proposed_target is None:
            return "flag"  # fixer cannot propose a target → FLAG
        if Path(v.path).name in _DATAPACKAGE_NAMES:
            return "move+rewrite-resources"
        return "move"
    return "flag"  # leaked_payload, flag → never auto-acted


def render_json(
    violations: list[Violation],
    outcomes: "list | None" = None,
    notes: list[AuditNote] | None = None,
) -> str:
    """Stable contract. In read-only mode (outcomes is None) performed is always False
    and `action` reports the *planned* action, matching what --fix would attempt."""
    by_path = {o.violation.path: o for o in (outcomes or [])}
    rows = []
    for v in violations:
        o = by_path.get(v.path)
        row = {
            "quadrant": v.quadrant.value,
            "path": v.path,
            "class": v.file_class.value,
            "action": (o.action if o else _planned_action(v)),
            "target": v.proposed_target,
            "performed": bool(o.performed) if o else False,
        }
        if o is not None and o.basepath is not None:
            row["basepath"] = o.basepath
        if o is not None and o.rewritten_resources is not None:
            row["rewritten_resources"] = o.rewritten_resources
        rows.append(row)
    payload = {"version": 1, "violations": rows}
    if notes:
        payload["notes"] = [
            {"severity": note.severity, "code": note.code, "message": note.message}
            for note in notes
        ]
    return json.dumps(payload, indent=2) + "\n"
