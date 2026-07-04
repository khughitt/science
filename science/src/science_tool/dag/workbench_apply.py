"""Read-plan/write-apply support for canonicalizing DAG workbench files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from pathlib import Path
import tempfile
from typing import Literal

import yaml
from pydantic import ValidationError
from science_model.entities import EvidenceLineEntity
from science_model.propositions import PropositionEntity

from science_tool.dag.workbench import (
    CompileResult,
    WorkbenchFile,
    compile_workbench,
    serialize_canonical,
    workbench_entity_body,
)
from science_tool.entities import (
    EntityCommandError,
    parse_markdown_entity_file_preserving_body,
    render_entity_text,
    resolve_path_policy,
)

ApplyStatus = Literal["applied", "no-op"]
WorkbenchEntity = PropositionEntity | EvidenceLineEntity
_PROPOSITION_ROW_FIELDS: tuple[str, ...] = (
    "subject",
    "predicate",
    "object",
    "polarity",
    "legacy_relation_label",
    "legacy_patch",
    "legacy_edge_id",
    "discusses",
    "claim_layer",
    "identification_strength",
)


class WorkbenchApplyError(ValueError):
    """Raised when a workbench apply plan cannot be safely built or applied."""


@dataclass(frozen=True)
class PlannedWorkbenchEdit:
    path: Path
    reason: str
    final_text: str
    changed: bool
    before_sha256: str | None
    after_sha256: str


@dataclass(frozen=True)
class WorkbenchApplyPlan:
    project_root: Path
    input_path: Path
    input_sha256: str
    canonical_workbench_text: str
    row_count: int
    proposition_count: int
    evidence_line_count: int
    edits: tuple[PlannedWorkbenchEdit, ...]

    @property
    def changed_edits(self) -> tuple[PlannedWorkbenchEdit, ...]:
        return tuple(edit for edit in self.edits if edit.changed)

    @property
    def status(self) -> ApplyStatus:
        return "applied" if self.changed_edits else "no-op"


@dataclass(frozen=True)
class WorkbenchApplyResult:
    project_root: Path
    input_path: Path
    status: ApplyStatus
    row_count: int
    proposition_count: int
    evidence_line_count: int
    changed_paths: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        """Return JSON-ready output; evidence_lines means evidence stubs lifted in this run."""
        return {
            "project_root": str(self.project_root),
            "input": _project_relative_or_absolute(self.project_root, self.input_path),
            "status": self.status,
            "rows": self.row_count,
            "propositions": self.proposition_count,
            "evidence_lines": self.evidence_line_count,
            "changed_path_count": len(self.changed_paths),
            "changed_paths": list(self.changed_paths),
        }


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _project_relative_or_absolute(project_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(project_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _resolve_input_path(project_root: Path, input_path: Path) -> Path:
    root = project_root.resolve()
    candidate = input_path if input_path.is_absolute() else project_root / input_path
    if not candidate.is_file():
        raise WorkbenchApplyError(f"workbench input does not exist: {candidate}")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise WorkbenchApplyError(f"workbench input escapes project root: {candidate}") from exc
    if resolved.name.endswith(".edges.yaml"):
        raise WorkbenchApplyError("workbench apply does not accept .edges.yaml input")
    if resolved.suffix == ".dot":
        raise WorkbenchApplyError("workbench apply does not accept .dot input")
    return resolved


def _target_path(project_root: Path, entity: WorkbenchEntity) -> Path:
    if entity.id is None:
        raise WorkbenchApplyError("compiled workbench entity is missing an id")
    try:
        policy = resolve_path_policy(entity.kind, project_root=project_root)
    except EntityCommandError as exc:
        raise WorkbenchApplyError(str(exc)) from exc
    local_part = entity.id.split(":", 1)[1]
    return project_root / policy.root / f"{local_part}.md"


def _read_existing_target(path: Path, entity: WorkbenchEntity) -> tuple[dict[str, object], str, str]:
    expected_id = entity.id
    expected_kind = entity.kind
    try:
        frontmatter, body = parse_markdown_entity_file_preserving_body(path)
        current_text = path.read_text(encoding="utf-8")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise WorkbenchApplyError(f"malformed existing entity target {path}: {exc}") from exc
    existing_kind = frontmatter.get("kind") or frontmatter.get("type")
    if frontmatter.get("id") != expected_id or existing_kind != expected_kind:
        raise WorkbenchApplyError(
            f"malformed existing entity target {path}: expected {expected_kind} {expected_id}"
        )
    if frontmatter.get("created") is None or frontmatter.get("updated") is None:
        raise WorkbenchApplyError(f"malformed existing entity target {path}: missing created/updated")
    return frontmatter, body, current_text


def _new_entity_body(entity: WorkbenchEntity) -> str:
    body = workbench_entity_body(entity)
    return body if body.endswith("\n\n") else body + "\n"


def _entity_edit(project_root: Path, entity: WorkbenchEntity, *, as_of: date) -> PlannedWorkbenchEdit:
    path = _target_path(project_root, entity)
    today = as_of.isoformat()
    if not path.exists():
        body = _new_entity_body(entity)
        final_text = render_entity_text(entity, body=body, created=today, updated=today)
        return PlannedWorkbenchEdit(
            path=path,
            reason="entity",
            final_text=final_text,
            changed=True,
            before_sha256=None,
            after_sha256=_sha256_text(final_text),
        )

    frontmatter, body, current_text = _read_existing_target(path, entity)
    created = str(frontmatter["created"])
    existing_updated = str(frontmatter["updated"])
    unchanged_timestamp_text = render_entity_text(
        entity,
        body=body,
        created=created,
        updated=existing_updated,
    )
    if unchanged_timestamp_text == current_text:
        final_text = current_text
    else:
        final_text = render_entity_text(entity, body=body, created=created, updated=today)
    return PlannedWorkbenchEdit(
        path=path,
        reason="entity",
        final_text=final_text,
        changed=final_text != current_text,
        before_sha256=_sha256_text(current_text),
        after_sha256=_sha256_text(final_text),
    )


def _workbench_edit(input_path: Path, current_text: str, canonical_text: str) -> PlannedWorkbenchEdit:
    return PlannedWorkbenchEdit(
        path=input_path,
        reason="canonical workbench",
        final_text=canonical_text,
        changed=canonical_text != current_text,
        before_sha256=_sha256_text(current_text),
        after_sha256=_sha256_text(canonical_text),
    )


def _check_duplicate_workbench_rows(workbench: WorkbenchFile) -> None:
    signatures: dict[str, tuple[object, ...]] = {}
    for row in workbench.rows:
        if row.id is None:
            continue
        dumped = row.model_dump(mode="json")
        signature = tuple(dumped.get(field) for field in _PROPOSITION_ROW_FIELDS)
        existing = signatures.get(row.id)
        if existing is None:
            signatures[row.id] = signature
            continue
        if existing != signature:
            raise WorkbenchApplyError(f"conflicting planned writes for proposition target {row.id}")


def _compile_in_scratch(project_root: Path, input_text: str, *, as_of: date) -> tuple[CompileResult, str]:
    try:
        raw = yaml.safe_load(input_text) or {}
        workbench = WorkbenchFile.model_validate(raw)
    except (ValidationError, ValueError, yaml.YAMLError) as exc:
        raise WorkbenchApplyError(f"invalid workbench input: {exc}") from exc
    _check_duplicate_workbench_rows(workbench)

    with tempfile.TemporaryDirectory(prefix="science-workbench-apply-") as scratch_name:
        scratch_root = Path(scratch_name)
        config_path = project_root / "science.yaml"
        if config_path.is_file():
            (scratch_root / "science.yaml").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            result = compile_workbench(workbench, project_root=scratch_root, as_of=as_of)
        except (EntityCommandError, ValidationError, ValueError) as exc:
            raise WorkbenchApplyError(f"could not compile workbench: {exc}") from exc
        return result, serialize_canonical(result)


def _check_duplicate_edits(edits: list[PlannedWorkbenchEdit]) -> tuple[PlannedWorkbenchEdit, ...]:
    by_path: dict[Path, PlannedWorkbenchEdit] = {}
    ordered: list[PlannedWorkbenchEdit] = []
    for edit in edits:
        resolved = edit.path.resolve()
        existing = by_path.get(resolved)
        if existing is None:
            by_path[resolved] = edit
            ordered.append(edit)
            continue
        if existing.final_text != edit.final_text:
            raise WorkbenchApplyError(f"conflicting planned writes for {edit.path}")
    return tuple(ordered)


def build_workbench_apply_plan(
    project_root: Path,
    *,
    input_path: Path,
    as_of: date | None = None,
) -> WorkbenchApplyPlan:
    root = project_root.resolve()
    resolved_input = _resolve_input_path(root, input_path)
    today = as_of or date.today()
    input_text = resolved_input.read_text(encoding="utf-8")
    input_sha256 = _sha256_text(input_text)
    compile_result, canonical_text = _compile_in_scratch(root, input_text, as_of=today)

    edits: list[PlannedWorkbenchEdit] = []
    for entity in compile_result.propositions:
        edits.append(_entity_edit(root, entity, as_of=today))
    for entity in compile_result.evidence_lines:
        edits.append(_entity_edit(root, entity, as_of=today))
    edits.append(_workbench_edit(resolved_input, input_text, canonical_text))

    return WorkbenchApplyPlan(
        project_root=root,
        input_path=resolved_input,
        input_sha256=input_sha256,
        canonical_workbench_text=canonical_text,
        row_count=len(compile_result.workbench.rows),
        proposition_count=len(compile_result.propositions),
        evidence_line_count=len(compile_result.evidence_lines),
        edits=_check_duplicate_edits(edits),
    )


def _assert_input_unchanged(plan: WorkbenchApplyPlan) -> None:
    current_text = plan.input_path.read_text(encoding="utf-8")
    if _sha256_text(current_text) != plan.input_sha256:
        raise WorkbenchApplyError(f"workbench input changed since it was parsed: {plan.input_path}")


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            fh.write(text)
            tmp_path = Path(fh.name)
        tmp_path.replace(path)
    finally:
        if tmp_path is not None and tmp_path.exists():
            tmp_path.unlink()


def apply_workbench_plan(plan: WorkbenchApplyPlan) -> WorkbenchApplyResult:
    _assert_input_unchanged(plan)
    changed_entity_edits = [edit for edit in plan.changed_edits if edit.path != plan.input_path]
    changed_workbench_edits = [edit for edit in plan.changed_edits if edit.path == plan.input_path]
    written_paths: list[Path] = []
    try:
        for edit in changed_entity_edits:
            _atomic_write_text(edit.path, edit.final_text)
            written_paths.append(edit.path)
        _assert_input_unchanged(plan)
        for edit in changed_workbench_edits:
            _atomic_write_text(edit.path, edit.final_text)
            written_paths.append(edit.path)
    except OSError as exc:
        detail = ", ".join(_project_relative_or_absolute(plan.project_root, path) for path in written_paths)
        suffix = f" after writing: {detail}" if detail else ""
        raise WorkbenchApplyError(f"failed to apply workbench plan{suffix}: {exc}") from exc

    changed_paths = tuple(_project_relative_or_absolute(plan.project_root, path) for path in written_paths)
    return WorkbenchApplyResult(
        project_root=plan.project_root,
        input_path=plan.input_path,
        status=plan.status,
        row_count=plan.row_count,
        proposition_count=plan.proposition_count,
        evidence_line_count=plan.evidence_line_count,
        changed_paths=changed_paths,
    )


def apply_workbench(
    project_root: Path,
    *,
    input_path: Path,
    as_of: date | None = None,
) -> WorkbenchApplyResult:
    return apply_workbench_plan(build_workbench_apply_plan(project_root, input_path=input_path, as_of=as_of))
