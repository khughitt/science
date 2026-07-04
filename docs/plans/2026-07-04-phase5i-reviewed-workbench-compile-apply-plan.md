# Phase 5i Reviewed Workbench Compile/Apply Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science dag apply-workbench`, a body-preserving reviewed apply command that compiles a workbench into proposition/evidence-line entities and rewrites the workbench to canonical form.

**Architecture:** Extract one pure entity renderer in `entities.py`, then build a new `science_tool.dag.workbench_apply` planner around the existing strict `WorkbenchFile`, `compile_workbench`, and `serialize_canonical` semantics. The CLI is a thin wrapper that reports the planned/applied writes; `workbench --check` remains read-only.

**Tech Stack:** Python 3.13, Click, Pydantic v2, PyYAML, existing Science entity path policies and DAG workbench models.

---

## File Structure

- Modify `science/src/science_tool/entities.py`
  - Add public `render_entity_text(...)`.
  - Add public `parse_markdown_entity_file_preserving_body(...)`.
  - Refactor `write_entity_file(...)` to use `render_entity_text(...)`.
- Modify `science/src/science_tool/dag/workbench.py`
  - Add public `workbench_entity_body(entity)`.
  - Use that helper in the existing low-level workbench writer.
- Create `science/src/science_tool/dag/workbench_apply.py`
  - Own the Phase 5i preflight plan and apply command logic.
  - Do not import retired-edge migration code.
- Modify `science/src/science_tool/dag/cli.py`
  - Add flat `dag apply-workbench`.
- Modify `science/src/science_tool/dag/__init__.py`
  - Export the apply dataclasses/functions.
- Create `science/tests/test_workbench_apply.py`
  - Unit tests for body-safe planning and apply behavior.
- Modify `science/tests/dag/test_cli.py`
  - CLI tests for the new command.
- Modify `science/tests/test_cli_surface_contract.py`
  - Register the new command's `--project` alias.

---

## Task 1: Extract Shared Entity Rendering

**Files:**
- Modify: `science/src/science_tool/entities.py`
- Modify: `science/src/science_tool/dag/workbench.py`
- Test: `science/tests/test_workbench_apply.py`

- [ ] **Step 1: Create the initial apply test file with renderer tests**

Create `science/tests/test_workbench_apply.py`:

```python
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from science_model.propositions import PropositionEntity

from science_tool.dag.workbench import workbench_entity_body
from science_tool.entities import (
    parse_markdown_entity_file_preserving_body,
    render_entity_text,
    write_entity_file,
)


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: workbench-apply-test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    _, fm_text, _body = text.split("---\n", 2)
    loaded = yaml.safe_load(fm_text) or {}
    assert isinstance(loaded, dict)
    return loaded


def _proposition(entity_id: str = "proposition:a-affects-b") -> PropositionEntity:
    return PropositionEntity(
        id=entity_id,
        subject="a",
        predicate="affects",
        object="b",
        polarity="positive",
        claim_layer="causal_effect",
        identification_strength="observational",
    )


def test_render_entity_text_matches_write_entity_file_output(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    entity = _proposition()
    body = workbench_entity_body(entity)

    write_entity_file(entity, project_root=tmp_path, body=body, as_of=date(2026, 7, 4))

    path = tmp_path / "entities/propositions/a-affects-b.md"
    written = path.read_text(encoding="utf-8")
    rendered = render_entity_text(
        entity,
        body=body,
        created="2026-07-04",
        updated="2026-07-04",
    )
    assert written == rendered


def test_parse_markdown_entity_file_preserving_body_keeps_body_bytes(tmp_path: Path) -> None:
    path = tmp_path / "entity.md"
    path.write_text(
        "---\nid: proposition:x\ntype: proposition\n---\n\n# Title\n\nBody.\n",
        encoding="utf-8",
    )

    frontmatter, body = parse_markdown_entity_file_preserving_body(path)

    assert frontmatter["id"] == "proposition:x"
    assert body == "\n# Title\n\nBody.\n"
```

- [ ] **Step 2: Run the renderer tests and verify they fail**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/test_workbench_apply.py::test_render_entity_text_matches_write_entity_file_output tests/test_workbench_apply.py::test_parse_markdown_entity_file_preserving_body_keeps_body_bytes -q
```

Expected: FAIL because `render_entity_text`, `parse_markdown_entity_file_preserving_body`, and `workbench_entity_body` are not defined.

- [ ] **Step 3: Add `render_entity_text` and preserving parser**

In `science/src/science_tool/entities.py`, add `render_entity_text(...)` above `write_entity_file(...)`:

```python
def render_entity_text(
    entity: Any,  # any typed entity exposing .kind, .id, and Pydantic .model_dump()
    *,
    body: str,
    created: str,
    updated: str,
) -> str:
    """Render a typed entity Markdown file with caller-selected dates and body."""
    kind = entity.kind
    assert entity.id is not None
    frontmatter = entity.model_dump(mode="json", exclude_none=True, exclude_defaults=False)
    frontmatter["id"] = entity.id
    frontmatter["kind"] = kind
    frontmatter.setdefault("status", default_status(kind))
    for derived in ("canonical_id", "content_preview", "content", "file_path"):
        frontmatter.pop(derived, None)
    frontmatter["created"] = created
    frontmatter["updated"] = updated
    return _render_markdown(frontmatter, body)
```

Still in `entities.py`, replace the frontmatter assembly in `write_entity_file(...)`:

```python
    text = render_entity_text(
        entity,
        body=body,
        created=existing_created if existing_created is not None else today.isoformat(),
        updated=today.isoformat(),
    )
```

Keep the existing `dest.parent.mkdir(...)` and `_atomic_replace_text(...)` lines after this replacement.

Add a public preserving parser near `parse_markdown_entity_file(...)`:

```python
def parse_markdown_entity_file_preserving_body(path: Path) -> tuple[dict[str, Any], str]:
    """Public markdown frontmatter/body parser that preserves body bytes exactly."""
    return _parse_markdown_file_preserving_body(path)
```

- [ ] **Step 4: Add `workbench_entity_body`**

In `science/src/science_tool/dag/workbench.py`, add this helper immediately above `_write_entity_file(...)`:

```python
def workbench_entity_body(entity: PropositionEntity | EvidenceLineEntity) -> str:
    """Default body used for new entities compiled from a workbench."""
    assert entity.id is not None
    local_part = entity.id.split(":", 1)[1]
    return f"# {entity.title or local_part}\n\n## Summary\n\n\n## Notes\n"
```

Then update `_write_entity_file(...)` to use the helper:

```python
    write_entity_file(entity, project_root=project_root, body=workbench_entity_body(entity), as_of=as_of)
```

- [ ] **Step 5: Run renderer tests and existing writer conformance**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/test_workbench_apply.py::test_render_entity_text_matches_write_entity_file_output tests/test_workbench_apply.py::test_parse_markdown_entity_file_preserving_body_keeps_body_bytes tests/test_workbench_compile_conformance.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
rtk git add src/science_tool/entities.py src/science_tool/dag/workbench.py tests/test_workbench_apply.py
rtk git commit -m "Extract shared entity renderer"
```

---

## Task 2: Build Body-Safe Workbench Apply Planner

**Files:**
- Create: `science/src/science_tool/dag/workbench_apply.py`
- Modify: `science/tests/test_workbench_apply.py`

- [ ] **Step 1: Add failing planner tests**

Append to `science/tests/test_workbench_apply.py`:

```python
from science_tool.dag.workbench_apply import (
    WorkbenchApplyError,
    apply_workbench,
    apply_workbench_plan,
    build_workbench_apply_plan,
)


def _write_workbench(
    path: Path,
    *,
    claim_layer: str = "causal_effect",
    inline_evidence: bool = True,
) -> None:
    evidence = (
        """
    evidence:
      - stance: supports
        source: paper:Smith2026
        evidence_type: literature
"""
        if inline_evidence
        else """
    evidence:
      - evidence-line:a-affects-b-ev0
"""
    )
    path.write_text(
        f"""rows:
  - id: proposition:a-affects-b
    subject: a
    predicate: affects
    object: b
    patch: h1
    polarity: positive
    claim_layer: {claim_layer}
    identification_strength: observational
{evidence}""",
        encoding="utf-8",
    )


def test_build_workbench_apply_plan_is_read_only_and_plans_canonical_workbench(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    plan = build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    assert plan.status == "applied"
    assert plan.row_count == 1
    assert plan.proposition_count == 1
    assert plan.evidence_line_count == 1
    assert (tmp_path / "entities").exists() is False
    assert any(edit.path == workbench_path for edit in plan.edits)
    assert "evidence-line:a-affects-b-ev0" in plan.canonical_workbench_text


def test_apply_workbench_writes_entities_and_canonicalizes_workbench(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    assert result.status == "applied"
    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    ev_path = tmp_path / "entities/evidence-lines/a-affects-b-ev0.md"
    assert prop_path.is_file()
    assert ev_path.is_file()
    assert "evidence-line:a-affects-b-ev0" in workbench_path.read_text(encoding="utf-8")
    assert _frontmatter(prop_path)["updated"] == "2026-07-04"


def test_apply_workbench_rerun_is_noop_without_timestamp_churn(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    first_frontmatter = _frontmatter(prop_path)

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 10))

    assert result.status == "no-op"
    assert _frontmatter(prop_path) == first_frontmatter


def test_apply_workbench_preserves_authored_proposition_body_on_semantic_update(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)
    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    prop_path.write_text(
        prop_path.read_text(encoding="utf-8").replace("## Summary\n\n", "## Summary\n\nReviewed prose.\n"),
        encoding="utf-8",
    )
    _write_workbench(workbench_path, claim_layer="structural_claim", inline_evidence=False)

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 10))

    assert result.status == "applied"
    assert "Reviewed prose." in prop_path.read_text(encoding="utf-8")
    fm = _frontmatter(prop_path)
    assert fm["claim_layer"] == "structural_claim"
    assert fm["created"] == "2026-07-04"
    assert fm["updated"] == "2026-07-10"


def test_apply_workbench_preserves_authored_evidence_line_body_on_semantic_update(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)
    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    ev_path = tmp_path / "entities/evidence-lines/a-affects-b-ev0.md"
    ev_path.write_text(
        ev_path.read_text(encoding="utf-8").replace("## Notes\n\n", "## Notes\n\nCurated evidence note.\n"),
        encoding="utf-8",
    )
    _write_workbench(workbench_path)
    text = workbench_path.read_text(encoding="utf-8").replace("paper:Smith2026", "paper:Jones2026")
    workbench_path.write_text(text, encoding="utf-8")

    result = apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 11))

    assert result.status == "applied"
    assert "Curated evidence note." in ev_path.read_text(encoding="utf-8")
    fm = _frontmatter(ev_path)
    assert fm["source"] == "paper:Jones2026"
    assert fm["created"] == "2026-07-04"
    assert fm["updated"] == "2026-07-11"


def test_apply_workbench_rejects_malformed_existing_target_before_write(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)
    prop_path = tmp_path / "entities/propositions/a-affects-b.md"
    prop_path.parent.mkdir(parents=True)
    prop_path.write_text("---\n: : bad yaml\n---\nBody\n", encoding="utf-8")

    try:
        apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    except WorkbenchApplyError as exc:
        assert "malformed existing entity target" in str(exc)
    else:
        raise AssertionError("expected WorkbenchApplyError")
    assert "evidence-line:a-affects-b-ev0" not in workbench_path.read_text(encoding="utf-8")


def test_apply_workbench_rejects_input_hash_drift(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    _write_workbench(workbench_path)

    plan = build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    workbench_path.write_text(workbench_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    try:
        apply_workbench_plan(plan)
    except WorkbenchApplyError as exc:
        assert "changed since it was parsed" in str(exc)
    else:
        raise AssertionError("expected WorkbenchApplyError")


def test_build_workbench_apply_plan_rejects_duplicate_target_with_different_final_text(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    workbench_path = tmp_path / "doc/figures/dags/h1.workbench.yaml"
    workbench_path.parent.mkdir(parents=True)
    workbench_path.write_text(
        """rows:
  - id: proposition:shared
    subject: a
    predicate: affects
    object: b
    patch: h1
    claim_layer: causal_effect
  - id: proposition:shared
    subject: a
    predicate: affects
    object: c
    patch: h1
    claim_layer: structural_claim
""",
        encoding="utf-8",
    )

    try:
        build_workbench_apply_plan(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))
    except WorkbenchApplyError as exc:
        assert "conflicting planned writes" in str(exc)
    else:
        raise AssertionError("expected WorkbenchApplyError")
```

- [ ] **Step 2: Run planner tests and verify they fail**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/test_workbench_apply.py -q
```

Expected: FAIL because `science_tool.dag.workbench_apply` does not exist.

- [ ] **Step 3: Create `workbench_apply.py` with dataclasses and helpers**

Create `science/src/science_tool/dag/workbench_apply.py`:

```python
"""Reviewed workbench apply surface for DAG workbench files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
from pathlib import Path
import tempfile
from typing import Literal

import yaml
from pydantic import ValidationError

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


class WorkbenchApplyError(ValueError):
    """Raised when a reviewed workbench cannot be safely applied."""


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
    project_root: str
    input_path: str
    status: ApplyStatus
    row_count: int
    proposition_count: int
    evidence_line_count: int
    changed_paths: tuple[str, ...]

    def to_json(self) -> dict[str, object]:
        """Return command JSON. evidence_lines means evidence stubs lifted in this run."""
        return {
            "project_root": self.project_root,
            "input": self.input_path,
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
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()


def _resolve_input_path(project_root: Path, input_path: Path) -> Path:
    candidate = input_path if input_path.is_absolute() else project_root / input_path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise WorkbenchApplyError(f"input path escapes project root: {input_path}") from exc
    if not resolved.exists():
        raise WorkbenchApplyError(f"workbench input does not exist: {input_path}")
    if resolved.name.endswith(".edges.yaml"):
        raise WorkbenchApplyError(f"refusing to apply retired edges YAML as a workbench: {input_path}")
    if resolved.suffix == ".dot":
        raise WorkbenchApplyError(f"refusing to apply DOT topology as a workbench: {input_path}")
    return resolved


def _target_path(project_root: Path, entity: object) -> Path:
    kind = getattr(entity, "kind")
    entity_id = getattr(entity, "id")
    if not isinstance(entity_id, str) or ":" not in entity_id:
        raise WorkbenchApplyError(f"compiled entity has invalid id: {entity_id!r}")
    local_part = entity_id.split(":", 1)[1]
    policy = resolve_path_policy(kind, project_root=project_root)
    return (project_root / policy.root / f"{local_part}.md").resolve()


def _read_existing_target(path: Path, entity: object) -> tuple[str, str, str]:
    try:
        frontmatter, body = parse_markdown_entity_file_preserving_body(path)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise WorkbenchApplyError(f"malformed existing entity target {path}: {exc}") from exc
    expected_id = getattr(entity, "id")
    expected_kind = getattr(entity, "kind")
    actual_id = frontmatter.get("id")
    actual_kind = frontmatter.get("kind") or frontmatter.get("type")
    if actual_id != expected_id or actual_kind != expected_kind:
        raise WorkbenchApplyError(
            f"existing entity target {path} is {actual_kind}:{actual_id}, "
            f"expected {expected_kind}:{expected_id}"
        )
    created = frontmatter.get("created")
    updated = frontmatter.get("updated")
    if not isinstance(created, str) or not isinstance(updated, str):
        raise WorkbenchApplyError(f"existing entity target {path} is missing created/updated")
    return body, created, updated
```

- [ ] **Step 4: Add planning functions**

Append to `workbench_apply.py`:

```python
def _entity_edit(project_root: Path, entity: object, *, as_of: date) -> PlannedWorkbenchEdit:
    path = _target_path(project_root, entity)
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise WorkbenchApplyError(f"entity target escapes project root: {path}") from exc

    current_text: str | None = None
    if path.exists():
        current_text = path.read_text(encoding="utf-8")
        body, created, existing_updated = _read_existing_target(path, entity)
        unchanged_text = render_entity_text(entity, body=body, created=created, updated=existing_updated)
        if unchanged_text == current_text:
            final_text = current_text
        else:
            final_text = render_entity_text(entity, body=body, created=created, updated=as_of.isoformat())
    else:
        body = workbench_entity_body(entity)  # type: ignore[arg-type]
        final_text = render_entity_text(
            entity,
            body=body,
            created=as_of.isoformat(),
            updated=as_of.isoformat(),
        )

    before_sha = _sha256_text(current_text) if current_text is not None else None
    after_sha = _sha256_text(final_text)
    return PlannedWorkbenchEdit(
        path=path,
        reason="entity",
        final_text=final_text,
        changed=current_text != final_text,
        before_sha256=before_sha,
        after_sha256=after_sha,
    )


def _workbench_edit(input_path: Path, current_text: str, canonical_text: str) -> PlannedWorkbenchEdit:
    return PlannedWorkbenchEdit(
        path=input_path,
        reason="canonical-workbench",
        final_text=canonical_text,
        changed=current_text != canonical_text,
        before_sha256=_sha256_text(current_text),
        after_sha256=_sha256_text(canonical_text),
    )


def _compile_in_scratch(text: str, *, as_of: date) -> CompileResult:
    with tempfile.TemporaryDirectory() as scratch_str:
        scratch = Path(scratch_str)
        (scratch / "science.yaml").write_text(
            "name: workbench-apply-scratch\nknowledge_profiles:\n  local: local\n",
            encoding="utf-8",
        )
        try:
            workbench = WorkbenchFile.model_validate(yaml.safe_load(text) or {})
            return compile_workbench(workbench, project_root=scratch, as_of=as_of)
        except (EntityCommandError, TypeError, ValueError, ValidationError, yaml.YAMLError) as exc:
            raise WorkbenchApplyError(f"failed to compile workbench: {exc}") from exc


def _check_duplicate_edits(edits: list[PlannedWorkbenchEdit]) -> None:
    final_by_path: dict[Path, str] = {}
    for edit in edits:
        existing = final_by_path.setdefault(edit.path, edit.final_text)
        if existing != edit.final_text:
            raise WorkbenchApplyError(f"conflicting planned writes for {edit.path}")


def build_workbench_apply_plan(
    project_root: Path,
    *,
    input_path: Path,
    as_of: date | None = None,
) -> WorkbenchApplyPlan:
    project_root = project_root.resolve()
    stamp = as_of or date.today()
    resolved_input = _resolve_input_path(project_root, input_path)
    input_text = resolved_input.read_text(encoding="utf-8")
    input_sha = _sha256_text(input_text)
    compiled = _compile_in_scratch(input_text, as_of=stamp)
    canonical_text = serialize_canonical(compiled)

    edits: list[PlannedWorkbenchEdit] = []
    for entity in (*compiled.propositions, *compiled.evidence_lines):
        edits.append(_entity_edit(project_root, entity, as_of=stamp))
    edits.append(_workbench_edit(resolved_input, input_text, canonical_text))
    _check_duplicate_edits(edits)

    return WorkbenchApplyPlan(
        project_root=project_root,
        input_path=resolved_input,
        input_sha256=input_sha,
        canonical_workbench_text=canonical_text,
        row_count=len(compiled.workbench.rows),
        proposition_count=len(compiled.propositions),
        evidence_line_count=len(compiled.evidence_lines),
        edits=tuple(edits),
    )
```

- [ ] **Step 5: Add apply functions**

Append to `workbench_apply.py`:

```python
def _assert_input_unchanged(plan: WorkbenchApplyPlan) -> None:
    current = plan.input_path.read_text(encoding="utf-8")
    if _sha256_text(current) != plan.input_sha256:
        raise WorkbenchApplyError(f"workbench input changed since it was parsed: {plan.input_path}")


def apply_workbench_plan(plan: WorkbenchApplyPlan) -> WorkbenchApplyResult:
    _assert_input_unchanged(plan)
    written: list[Path] = []
    try:
        entity_edits = [edit for edit in plan.edits if edit.reason == "entity" and edit.changed]
        workbench_edits = [edit for edit in plan.edits if edit.reason == "canonical-workbench" and edit.changed]
        for edit in entity_edits:
            edit.path.parent.mkdir(parents=True, exist_ok=True)
            edit.path.write_text(edit.final_text, encoding="utf-8")
            written.append(edit.path)
        if workbench_edits:
            _assert_input_unchanged(plan)
            edit = workbench_edits[0]
            edit.path.write_text(edit.final_text, encoding="utf-8")
            written.append(edit.path)
    except OSError as exc:
        paths = ", ".join(_project_relative_or_absolute(plan.project_root, path) for path in written)
        raise WorkbenchApplyError(f"failed while applying workbench after writing [{paths}]: {exc}") from exc

    changed_paths = tuple(_project_relative_or_absolute(plan.project_root, edit.path) for edit in plan.changed_edits)
    return WorkbenchApplyResult(
        project_root=plan.project_root.as_posix(),
        input_path=_project_relative_or_absolute(plan.project_root, plan.input_path),
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
```

- [ ] **Step 6: Run planner tests**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/test_workbench_apply.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
rtk git add src/science_tool/dag/workbench_apply.py tests/test_workbench_apply.py
rtk git commit -m "Add reviewed workbench apply planner"
```

---

## Task 3: Wire CLI And Public Exports

**Files:**
- Modify: `science/src/science_tool/dag/cli.py`
- Modify: `science/src/science_tool/dag/__init__.py`
- Modify: `science/tests/test_cli_surface_contract.py`
- Modify: `science/tests/dag/test_cli.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `science/tests/dag/test_cli.py`:

```python
def _write_apply_workbench(project: Path, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        """rows:
  - id: proposition:a-affects-b
    subject: a
    predicate: affects
    object: b
    patch: h1
    polarity: positive
    claim_layer: causal_effect
    identification_strength: observational
    evidence:
      - stance: supports
        source: paper:Smith2026
        evidence_type: literature
""",
        encoding="utf-8",
    )
    (project / "science.yaml").write_text(
        "name: dag-cli-apply-test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def test_cli_dag_apply_workbench_writes_entities_and_canonicalizes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workbench = project / "doc/figures/dags/h1.workbench.yaml"
    _write_apply_workbench(project, workbench)

    result = CliRunner().invoke(
        main,
        [
            "dag",
            "apply-workbench",
            "--project",
            str(project),
            "--input",
            "doc/figures/dags/h1.workbench.yaml",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "applied"
    assert payload["rows"] == 1
    assert payload["propositions"] == 1
    assert payload["evidence_lines"] == 1
    assert (project / "entities/propositions/a-affects-b.md").is_file()
    assert (project / "entities/evidence-lines/a-affects-b-ev0.md").is_file()
    assert "evidence-line:a-affects-b-ev0" in workbench.read_text(encoding="utf-8")

    check = CliRunner().invoke(main, ["dag", "workbench", "--check", str(workbench)])
    assert check.exit_code == 0, check.output


def test_cli_dag_apply_workbench_json_reports_noop(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    workbench = project / "doc/figures/dags/h1.workbench.yaml"
    _write_apply_workbench(project, workbench)

    first = CliRunner().invoke(
        main,
        ["dag", "apply-workbench", "--project", str(project), "--input", str(workbench), "--format", "json"],
    )
    assert first.exit_code == 0, first.output
    second = CliRunner().invoke(
        main,
        ["dag", "apply-workbench", "--project", str(project), "--input", str(workbench), "--format", "json"],
    )
    assert second.exit_code == 0, second.output
    payload = json.loads(second.output)
    assert payload["status"] == "no-op"
    assert payload["changed_path_count"] == 0


def test_cli_dag_apply_workbench_refuses_retired_edges_input(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    path = project / "doc/figures/dags/h1.edges.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("dag: h1\nedges: []\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["dag", "apply-workbench", "--project", str(project), "--input", str(path)])

    assert result.exit_code != 0
    assert "retired edges YAML" in result.output


def test_cli_dag_apply_workbench_refuses_dot_input(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    path = project / "doc/figures/dags/h1.dot"
    path.parent.mkdir(parents=True)
    path.write_text("digraph h1 { a -> b; }\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["dag", "apply-workbench", "--project", str(project), "--input", str(path)])

    assert result.exit_code != 0
    assert "DOT topology" in result.output


def test_cli_dag_apply_workbench_invalid_workbench_is_click_error(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")
    path = project / "doc/figures/dags/h1.workbench.yaml"
    path.parent.mkdir(parents=True)
    path.write_text("rows:\n  - subject: a\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["dag", "apply-workbench", "--project", str(project), "--input", str(path)])

    assert result.exit_code != 0
    assert "Error:" in result.output
    assert "failed to compile workbench" in result.output
    assert result.exception is not None
    assert result.exception.__class__.__name__ != "ValidationError"
```

In `science/tests/test_cli_surface_contract.py`, add `"dag apply-workbench"` to `_PROJECT_OPTION_ALLOWLIST` and `_PROJECT_ROOT_ALIAS_COMMANDS` in the same style as `dag scaffold-retired-edge-workbench`:

```python
    "dag apply-workbench": (
        "DAG reviewed workbench apply surface; retains --project-root alongside --project",
        "project root",
    ),
```

```python
    "dag apply-workbench",
```

- [ ] **Step 2: Run CLI tests and verify they fail**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/dag/test_cli.py::test_cli_dag_apply_workbench_writes_entities_and_canonicalizes tests/dag/test_cli.py::test_cli_dag_apply_workbench_json_reports_noop tests/dag/test_cli.py::test_cli_dag_apply_workbench_refuses_retired_edges_input tests/dag/test_cli.py::test_cli_dag_apply_workbench_refuses_dot_input tests/dag/test_cli.py::test_cli_dag_apply_workbench_invalid_workbench_is_click_error tests/test_cli_surface_contract.py -q
```

Expected: FAIL because `dag apply-workbench` does not exist.

- [ ] **Step 3: Add exports**

In `science/src/science_tool/dag/__init__.py`, import:

```python
from science_tool.dag.workbench_apply import (
    PlannedWorkbenchEdit,
    WorkbenchApplyError,
    WorkbenchApplyPlan,
    WorkbenchApplyResult,
    apply_workbench,
    apply_workbench_plan,
    build_workbench_apply_plan,
)
```

Add these names to `__all__`:

```python
    "PlannedWorkbenchEdit",
    "WorkbenchApplyError",
    "WorkbenchApplyPlan",
    "WorkbenchApplyResult",
    "apply_workbench",
    "apply_workbench_plan",
    "build_workbench_apply_plan",
```

- [ ] **Step 4: Add the CLI command**

In `science/src/science_tool/dag/cli.py`, add the command before the existing `workbench` command section:

```python
@dag_group.command("apply-workbench")
@click.option(
    "--input",
    "input_path",
    required=True,
    type=click.Path(dir_okay=False, path_type=Path),
    help="Reviewed workbench YAML path to compile/apply. Relative paths resolve against the project root.",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    "--project",
    "project_path",
    default=None,
    type=click.Path(file_okay=False, path_type=Path),
    help="Project root (default: current working directory).",
)
def apply_workbench_cmd(input_path: Path, output_format: str, project_path: Path | None) -> None:
    """Compile a reviewed DAG workbench into entities and canonical YAML."""
    from science_tool.dag.workbench_apply import WorkbenchApplyError, apply_workbench

    project = (project_path or Path.cwd()).resolve()
    try:
        result = apply_workbench(project, input_path=input_path)
    except WorkbenchApplyError as exc:
        raise click.ClickException(str(exc)) from exc

    if output_format == "json":
        click.echo(json.dumps(result.to_json(), indent=2, sort_keys=True))
        return

    action = "Applied" if result.status == "applied" else "No-op"
    click.echo(f"{action} workbench: {result.input_path}")
    click.echo(
        f"  rows={result.row_count}, propositions={result.proposition_count}, "
        f"evidence_lines={result.evidence_line_count}, changed_paths={len(result.changed_paths)}"
    )
    for path in result.changed_paths:
        click.echo(f"  {path}")
```

- [ ] **Step 5: Run CLI tests**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/dag/test_cli.py::test_cli_dag_apply_workbench_writes_entities_and_canonicalizes tests/dag/test_cli.py::test_cli_dag_apply_workbench_json_reports_noop tests/dag/test_cli.py::test_cli_dag_apply_workbench_refuses_retired_edges_input tests/dag/test_cli.py::test_cli_dag_apply_workbench_refuses_dot_input tests/dag/test_cli.py::test_cli_dag_apply_workbench_invalid_workbench_is_click_error tests/test_cli_surface_contract.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
rtk git add src/science_tool/dag/__init__.py src/science_tool/dag/cli.py tests/dag/test_cli.py tests/test_cli_surface_contract.py
rtk git commit -m "Add reviewed workbench apply CLI"
```

---

## Task 4: Validate DAG Wiring With Compiled Workbench Rows

**Files:**
- Modify: `science/tests/test_workbench_apply.py`

- [ ] **Step 1: Add failing DAG validation integration test**

Append to `science/tests/test_workbench_apply.py`:

```python
from science_tool.dag.paths import load_dag_paths
from science_tool.dag.validate import validate_project


def test_apply_workbench_satisfies_dag_validate_subject_object_edge(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    dag_dir = tmp_path / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (tmp_path / "tasks").mkdir()
    workbench_path = dag_dir / "h1.workbench.yaml"
    _write_workbench(workbench_path, inline_evidence=False)

    before = validate_project(load_dag_paths(tmp_path))
    assert any(f.rule == "proposition_edge_missing" for f in before.findings)

    apply_workbench(tmp_path, input_path=workbench_path, as_of=date(2026, 7, 4))

    after = validate_project(load_dag_paths(tmp_path))
    assert not any(f.rule == "proposition_edge_missing" for f in after.findings)
```

- [ ] **Step 2: Run the validation integration test**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/test_workbench_apply.py::test_apply_workbench_satisfies_dag_validate_subject_object_edge -q
```

Expected: PASS if Tasks 2-3 are implemented correctly. If it fails, inspect whether `load_relational_propositions(...)` loaded the written proposition and whether the DOT node names match the workbench row's `subject`/`object`.

This fixture intentionally does not add `focal_hypothesis` or row-level `discusses`.
At the time of this plan, `validate_project(...)` clears `proposition_edge_missing`
by counting all loaded relational propositions keyed by `(subject, object)`; it
does not require patch membership for this rule.

- [ ] **Step 3: Run all workbench apply tests**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/test_workbench_apply.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Task 4**

```bash
rtk git add tests/test_workbench_apply.py
rtk git commit -m "Verify applied workbench backs DAG validation"
```

---

## Task 5: Full Focused Verification

**Files:**
- No source edits expected.

- [ ] **Step 1: Run focused pytest suite**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/test_workbench_apply.py tests/test_workbench_compile.py tests/test_workbench_compile_conformance.py tests/test_workbench_ci_gate.py tests/dag/test_cli.py tests/test_cli_surface_contract.py -q
```

Expected: PASS.

- [ ] **Step 2: Run focused ruff**

Run from `science/`:

```bash
rtk uv run --frozen ruff check src/science_tool/entities.py src/science_tool/dag/workbench.py src/science_tool/dag/workbench_apply.py src/science_tool/dag/cli.py src/science_tool/dag/__init__.py tests/test_workbench_apply.py tests/dag/test_cli.py tests/test_cli_surface_contract.py
```

Expected: PASS.

- [ ] **Step 3: Run pyright on the touched package**

Run from `science/`:

```bash
rtk uv run --frozen pyright src/science_tool/dag/workbench_apply.py src/science_tool/dag/workbench.py src/science_tool/entities.py
```

Expected: PASS. If pyright cannot accept file arguments in this project, run `rtk uv run --frozen pyright` and inspect only new errors caused by this branch.

- [ ] **Step 4: Commit any verification-only fixes**

If Steps 1-3 required edits, commit them:

```bash
rtk git add src/science_tool/entities.py src/science_tool/dag/workbench.py src/science_tool/dag/workbench_apply.py src/science_tool/dag/cli.py src/science_tool/dag/__init__.py tests/test_workbench_apply.py tests/dag/test_cli.py tests/test_cli_surface_contract.py
rtk git commit -m "Polish workbench apply verification"
```

If no edits were needed, do not create an empty commit.

---

## Task 6: Protein-Landscape Acceptance Smoke

**Files:**
- No science source edits expected.
- Use a disposable copy of `~/d/protein-landscape` unless the user explicitly chooses to apply directly to that project.

- [ ] **Step 1: Create a disposable protein-landscape copy**

Run from any directory:

```bash
tmpdir="$(mktemp -d)"
rtk cp -R ~/d/protein-landscape "$tmpdir/protein-landscape"
```

Expected: a disposable project exists at `$tmpdir/protein-landscape`.

- [ ] **Step 2: Scaffold the six-row workbench in the disposable copy**

Run from `science/`:

```bash
rtk uv run --frozen science dag scaffold-retired-edge-workbench \
  --project "$tmpdir/protein-landscape" \
  --dag h01-multi-manifold-protein-universe \
  --focal-hypothesis hypothesis:h01-multi-manifold-protein-universe \
  --output doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml \
  --format json
```

Expected JSON facts:

```json
{
  "status": "written",
  "rows": 6,
  "evidence_stubs": 10,
  "predicate_review_required": 6
}
```

- [ ] **Step 3: Apply the reviewed workbench in the disposable copy**

For this smoke, the scaffolded predicate defaults are accepted as a mechanical fixture. Run from `science/`:

```bash
rtk uv run --frozen science dag apply-workbench \
  --project "$tmpdir/protein-landscape" \
  --input doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml \
  --format json
```

Expected JSON facts:

```json
{
  "status": "applied",
  "rows": 6,
  "propositions": 6,
  "evidence_lines": 10
}
```

- [ ] **Step 4: Verify canonical workbench fixpoint**

Run from `science/`:

```bash
rtk uv run --frozen science dag workbench --check "$tmpdir/protein-landscape/doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml"
```

Expected: exit 0 with `workbench --check: OK (canonical)`.

- [ ] **Step 5: Verify DAG validation wiring**

Run from `science/`:

```bash
rtk uv run --frozen science dag validate \
  --project "$tmpdir/protein-landscape" \
  --dag h01-multi-manifold-protein-universe \
  --format json
```

Expected: output contains no `proposition_edge_missing` findings for these pairs:

- `snapshots -> pc1`
- `lenses -> orthogonality`
- `pc1 -> residualization`
- `residualization -> coherence`
- `orthogonality -> interaction`
- `interaction -> robust`

- [ ] **Step 6: Verify rerun no-op**

Run from `science/`:

```bash
rtk uv run --frozen science dag apply-workbench \
  --project "$tmpdir/protein-landscape" \
  --input doc/figures/dags/h01-multi-manifold-protein-universe.workbench.yaml \
  --format json
```

Expected JSON facts:

```json
{
  "status": "no-op",
  "changed_path_count": 0
}
```

- [ ] **Step 7: Commit smoke-discovered fixes only**

If the smoke reveals a science bug, fix it and commit:

```bash
rtk git add src/science_tool tests
rtk git commit -m "Fix workbench apply dogfood issue"
```

If no science edits were needed, do not commit anything for this task.

---

## Task 7: Final Branch Verification

**Files:**
- No source edits expected.

- [ ] **Step 1: Run the final focused verification suite**

Run from `science/`:

```bash
rtk uv run --frozen pytest tests/test_workbench_apply.py tests/test_workbench_compile.py tests/test_workbench_compile_conformance.py tests/test_workbench_ci_gate.py tests/dag/test_cli.py tests/test_cli_surface_contract.py -q
```

Expected: PASS.

- [ ] **Step 2: Run final ruff**

Run from `science/`:

```bash
rtk uv run --frozen ruff check src/science_tool/entities.py src/science_tool/dag/workbench.py src/science_tool/dag/workbench_apply.py src/science_tool/dag/cli.py src/science_tool/dag/__init__.py tests/test_workbench_apply.py tests/dag/test_cli.py tests/test_cli_surface_contract.py
```

Expected: PASS.

- [ ] **Step 3: Check git status**

Run from the worktree root:

```bash
rtk git status --short --branch
```

Expected: clean worktree on the Phase 5i implementation branch.

- [ ] **Step 4: Summarize the branch**

Run from the worktree root:

```bash
rtk git log --oneline --max-count=8
```

Expected: recent commits include the design, this plan, and the implementation commits from Tasks 1-6.
