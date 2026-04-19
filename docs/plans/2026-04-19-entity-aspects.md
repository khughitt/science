# Entity-Level Aspects Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce an `aspects:` field on tasks, questions, interpretations, and hypotheses that inherits from `science.yaml` by default and acts as an explicit override when set, then consume that field in `/science:big-picture` so research synthesis can exclude software-oriented entities.

**Architecture:** A shared `science_model.aspects` module owns the vocabulary, validation, resolution, and filter predicate — no command reimplements aspect logic. `science_tool.aspects` holds the migration machinery and CLI subcommand. The existing `Task` pydantic model gains an `aspects` field alongside the legacy `type` field (kept for backward-compat through migration). The big-picture resolver adds a `resolved_aspects` output per question; bundle assembly and orphan accounting filter on that value.

**Tech Stack:** Python 3.11+, pydantic v2 (existing science-model pattern), click (existing CLI), pytest, PyYAML. No new runtime dependencies.

**Spec:** `docs/specs/2026-04-19-entity-aspects-design.md`

---

## File Structure

### New files

- `science-model/src/science_model/aspects.py` — canonical vocabulary + `resolve_entity_aspects`, `validate_entity_aspects`, `matches_aspect_filter`, `canonical_order`, `load_project_aspects`.
- `science-tool/src/science_tool/aspects/__init__.py` — module marker.
- `science-tool/src/science_tool/aspects/migrate.py` — `AspectsMigrationPlan`, `build_migration_plan`, `apply_migration_plan`.
- `science-tool/src/science_tool/aspects/cli.py` — registers `aspects` click group with `migrate` subcommand.
- `science-tool/tests/test_aspects_helpers.py` — unit tests for the `science_model.aspects` helpers.
- `science-tool/tests/test_aspects_migrate.py` — unit tests for `build_migration_plan` / `apply_migration_plan`.
- `science-tool/tests/test_aspects_cli.py` — integration tests for `science-tool aspects migrate`.
- `science-tool/tests/fixtures/aspects/legacy_project/` — synthetic project with legacy `type: research|dev` tasks for migration tests.
- `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q06-software-pipeline-concern.md` — new fixture question carrying `aspects: [software-development]`.

### Modified files

- `science-model/src/science_model/tasks.py` — add `aspects: list[str]` field to `Task`, `TaskCreate`, `TaskUpdate`.
- `science-tool/src/science_tool/tasks.py` — parse/render inline `- aspects:` field; relax `add_task` signature.
- `science-tool/src/science_tool/cli.py` — drop `--type` on `tasks add`/`tasks edit`/`tasks list`; add `--aspects`/`--aspect`; register `aspects_group`.
- `science-tool/src/science_tool/big_picture/resolver.py` — add `resolved_aspects` to `ResolverOutput`; load per-question aspects.
- `science-tool/src/science_tool/big_picture/cli.py` — unchanged logic; `resolve-questions` JSON automatically includes the new field via `asdict`.
- `science-tool/src/science_tool/big_picture/validator.py` — orphan-count check excludes software-only questions.
- `science-tool/tests/test_big_picture_resolver.py` — extended cases.
- `science-tool/tests/test_big_picture_validator.py` — extended cases.
- `science-tool/tests/fixtures/big_picture/minimal_project/science.yaml` — add `aspects: [...]`.
- `templates/hypothesis.md`, `templates/question.md`, `templates/interpretation.md` — add commented optional `aspects:` slot.
- `commands/big-picture.md` — Phase 1 bundle-assembly prose updated to filter by resolved aspects.
- `commands/tasks.md` — CLI references updated.
- `science-tool/src/science_tool/graph/health.py` — add `legacy_task_type_field` and `invalid_entity_aspects` checks.

### Unchanged

- `science-tool/src/science_tool/big_picture/frontmatter.py` — still used by the resolver. Not consolidated with `science_model.frontmatter` in this plan; that's a separate cleanup.
- The graph RDF layer — aspects are not propagated to triples in v1.

---

## Task 1: Scaffold `science_model.aspects` module with vocabulary constant

**Files:**
- Create: `science-model/src/science_model/aspects.py`
- Test: `science-tool/tests/test_aspects_helpers.py`

- [ ] **Step 1: Write the failing test**

Create `science-tool/tests/test_aspects_helpers.py`:

```python
from __future__ import annotations

from science_model.aspects import KNOWN_ASPECTS


def test_known_aspects_matches_science_yaml_schema() -> None:
    assert KNOWN_ASPECTS == frozenset(
        {
            "causal-modeling",
            "hypothesis-testing",
            "computational-analysis",
            "software-development",
        }
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: FAIL — `science_model.aspects` does not exist.

- [ ] **Step 3: Create the module**

Create `science-model/src/science_model/aspects.py`:

```python
"""Shared aspect vocabulary, resolution, validation, and filtering helpers.

Entity-level `aspects:` uses the same vocabulary as project-level `aspects:` in
science.yaml. This module is the single source of truth for that vocabulary
and for the resolution/filter rules; commands consume it rather than
reimplementing aspect logic.
"""
from __future__ import annotations

KNOWN_ASPECTS: frozenset[str] = frozenset(
    {
        "causal-modeling",
        "hypothesis-testing",
        "computational-analysis",
        "software-development",
    }
)

SOFTWARE_ASPECT: str = "software-development"
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd /mnt/ssd/Dropbox/science
git add science-model/src/science_model/aspects.py science-tool/tests/test_aspects_helpers.py
git commit -m "feat(aspects): scaffold science_model.aspects with vocabulary constant"
```

---

## Task 2: `resolve_entity_aspects` pure function

**Files:**
- Modify: `science-model/src/science_model/aspects.py`
- Modify: `science-tool/tests/test_aspects_helpers.py`

- [ ] **Step 1: Add failing tests**

Append to `test_aspects_helpers.py`:

```python
from science_model.aspects import resolve_entity_aspects


def test_resolve_returns_entity_aspects_when_explicit() -> None:
    resolved = resolve_entity_aspects(
        entity_aspects=["software-development"],
        project_aspects=["hypothesis-testing", "software-development"],
    )
    assert resolved == ["software-development"]


def test_resolve_inherits_project_when_entity_is_none() -> None:
    resolved = resolve_entity_aspects(
        entity_aspects=None,
        project_aspects=["hypothesis-testing", "computational-analysis"],
    )
    assert resolved == ["hypothesis-testing", "computational-analysis"]


def test_resolve_preserves_order_of_explicit_entity_aspects() -> None:
    resolved = resolve_entity_aspects(
        entity_aspects=["computational-analysis", "hypothesis-testing"],
        project_aspects=["hypothesis-testing", "computational-analysis"],
    )
    assert resolved == ["computational-analysis", "hypothesis-testing"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: FAIL — `resolve_entity_aspects` not defined.

- [ ] **Step 3: Implement the function**

Append to `science-model/src/science_model/aspects.py`:

```python
def resolve_entity_aspects(
    entity_aspects: list[str] | None,
    project_aspects: list[str],
) -> list[str]:
    """Return the effective aspect list for an entity.

    - If ``entity_aspects`` is None (absent), inherit ``project_aspects``.
    - If ``entity_aspects`` is a non-empty list, return it unchanged.
    - Callers are responsible for having validated ``entity_aspects`` before
      resolution; this function does not re-validate.
    """
    if entity_aspects is None:
        return list(project_aspects)
    return list(entity_aspects)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/aspects.py science-tool/tests/test_aspects_helpers.py
git commit -m "feat(aspects): resolve_entity_aspects inheritance helper"
```

---

## Task 3: `matches_aspect_filter` predicate

**Files:**
- Modify: `science-model/src/science_model/aspects.py`
- Modify: `science-tool/tests/test_aspects_helpers.py`

- [ ] **Step 1: Add failing tests**

Append to `test_aspects_helpers.py`:

```python
from science_model.aspects import matches_aspect_filter


def test_matches_when_intersection_is_nonempty() -> None:
    assert matches_aspect_filter(
        resolved=["hypothesis-testing", "computational-analysis"],
        filter_set={"hypothesis-testing"},
    )


def test_does_not_match_when_disjoint() -> None:
    assert not matches_aspect_filter(
        resolved=["software-development"],
        filter_set={"hypothesis-testing", "computational-analysis"},
    )


def test_does_not_match_on_empty_resolved() -> None:
    assert not matches_aspect_filter(resolved=[], filter_set={"hypothesis-testing"})


def test_does_not_match_on_empty_filter_set() -> None:
    assert not matches_aspect_filter(
        resolved=["hypothesis-testing"], filter_set=set()
    )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: 4 failures.

- [ ] **Step 3: Implement the predicate**

Append to `science-model/src/science_model/aspects.py`:

```python
def matches_aspect_filter(resolved: list[str], filter_set: set[str]) -> bool:
    """Return True iff ``resolved`` intersects ``filter_set``.

    The sole aspect-filter rule used by downstream commands. Callers choose
    ``filter_set``; this helper does not invent the filter.
    """
    return bool(set(resolved) & filter_set)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: 8 total tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/aspects.py science-tool/tests/test_aspects_helpers.py
git commit -m "feat(aspects): matches_aspect_filter shared predicate"
```

---

## Task 4: `validate_entity_aspects` with canonical ordering

**Files:**
- Modify: `science-model/src/science_model/aspects.py`
- Modify: `science-tool/tests/test_aspects_helpers.py`

- [ ] **Step 1: Add failing tests**

Append to `test_aspects_helpers.py`:

```python
import pytest

from science_model.aspects import AspectValidationError, validate_entity_aspects


PROJECT = ["causal-modeling", "hypothesis-testing", "software-development"]


def test_validate_accepts_subset_of_project() -> None:
    assert validate_entity_aspects(["hypothesis-testing"], PROJECT) == [
        "hypothesis-testing"
    ]


def test_validate_returns_canonical_order() -> None:
    # Caller supplied in a non-project order; helper normalizes to project order.
    assert validate_entity_aspects(
        ["software-development", "causal-modeling"], PROJECT
    ) == ["causal-modeling", "software-development"]


def test_validate_rejects_empty_list() -> None:
    with pytest.raises(AspectValidationError, match="empty"):
        validate_entity_aspects([], PROJECT)


def test_validate_rejects_duplicates() -> None:
    with pytest.raises(AspectValidationError, match="duplicate"):
        validate_entity_aspects(["hypothesis-testing", "hypothesis-testing"], PROJECT)


def test_validate_rejects_aspect_not_in_project() -> None:
    with pytest.raises(AspectValidationError, match="not declared"):
        validate_entity_aspects(["computational-analysis"], PROJECT)


def test_validate_rejects_aspect_not_in_vocabulary() -> None:
    with pytest.raises(AspectValidationError, match="vocabulary"):
        validate_entity_aspects(["typo-aspect"], PROJECT + ["typo-aspect"])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: 6 failures (new tests) — `AspectValidationError` and `validate_entity_aspects` not defined.

- [ ] **Step 3: Implement validation + canonicalization**

Append to `science-model/src/science_model/aspects.py`:

```python
class AspectValidationError(ValueError):
    """Raised when entity aspects are invalid for a project."""


def validate_entity_aspects(
    entity_aspects: list[str],
    project_aspects: list[str],
) -> list[str]:
    """Validate explicit entity aspects and return them in canonical order.

    Invariants enforced:
    - Non-empty list.
    - No duplicates.
    - Every entry is a member of ``KNOWN_ASPECTS``.
    - Every entry is declared in ``project_aspects``.

    Returns the canonicalized list: same values, reordered to match
    ``project_aspects`` ordering for stable diffs.
    """
    if not entity_aspects:
        raise AspectValidationError(
            "Entity aspects list is empty; use absent field to inherit."
        )
    seen: set[str] = set()
    for aspect in entity_aspects:
        if aspect in seen:
            raise AspectValidationError(f"duplicate aspect: {aspect!r}")
        seen.add(aspect)
        if aspect not in KNOWN_ASPECTS:
            raise AspectValidationError(
                f"{aspect!r} is not in the aspect vocabulary "
                f"({sorted(KNOWN_ASPECTS)})."
            )
        if aspect not in project_aspects:
            raise AspectValidationError(
                f"{aspect!r} is not declared in project aspects "
                f"({project_aspects}); add it to science.yaml first."
            )
    return [a for a in project_aspects if a in seen]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: 14 total tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/aspects.py science-tool/tests/test_aspects_helpers.py
git commit -m "feat(aspects): validate_entity_aspects with canonical ordering"
```

---

## Task 5: `load_project_aspects` from `science.yaml`

**Files:**
- Modify: `science-model/src/science_model/aspects.py`
- Modify: `science-tool/tests/test_aspects_helpers.py`

- [ ] **Step 1: Add failing tests**

Append to `test_aspects_helpers.py`:

```python
from pathlib import Path

from science_model.aspects import load_project_aspects


def test_load_reads_aspects_field(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects:\n  - hypothesis-testing\n"
        "  - computational-analysis\n"
    )
    assert load_project_aspects(tmp_path) == [
        "hypothesis-testing",
        "computational-analysis",
    ]


def test_load_returns_empty_list_when_aspects_absent(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\n")
    assert load_project_aspects(tmp_path) == []


def test_load_raises_when_yaml_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_project_aspects(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: 3 failures — `load_project_aspects` not defined.

- [ ] **Step 3: Implement the loader**

Append to `science-model/src/science_model/aspects.py`:

```python
from pathlib import Path

import yaml


def load_project_aspects(project_root: Path) -> list[str]:
    """Return the ``aspects:`` list declared in the project's science.yaml.

    Returns an empty list if the field is absent or the list is empty.
    Raises ``FileNotFoundError`` if science.yaml is missing.
    """
    yaml_path = project_root / "science.yaml"
    if not yaml_path.is_file():
        raise FileNotFoundError(f"science.yaml not found at {yaml_path}")
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    aspects = data.get("aspects") or []
    if not isinstance(aspects, list):
        raise TypeError(
            f"science.yaml 'aspects' must be a list, got {type(aspects).__name__}"
        )
    return [str(a) for a in aspects]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_helpers.py -v
```

Expected: 17 total tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/aspects.py science-tool/tests/test_aspects_helpers.py
git commit -m "feat(aspects): load_project_aspects from science.yaml"
```

---

## Task 6: Add `aspects` field to `Task`/`TaskCreate`/`TaskUpdate`

**Files:**
- Modify: `science-model/src/science_model/tasks.py`
- Test: `science-tool/tests/test_tasks.py` (existing file)

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_tasks.py`:

```python
from science_model.tasks import Task, TaskCreate, TaskUpdate


def test_task_accepts_aspects_field() -> None:
    t = Task(id="t001", title="demo", aspects=["hypothesis-testing"])
    assert t.aspects == ["hypothesis-testing"]


def test_task_defaults_aspects_to_empty_list() -> None:
    t = Task(id="t001", title="demo")
    assert t.aspects == []


def test_task_create_and_update_carry_aspects() -> None:
    create = TaskCreate(title="demo", aspects=["software-development"])
    update = TaskUpdate(aspects=["hypothesis-testing"])
    assert create.aspects == ["software-development"]
    assert update.aspects == ["hypothesis-testing"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks.py::test_task_accepts_aspects_field -v
```

Expected: FAIL — `aspects` is not an accepted field.

- [ ] **Step 3: Add the field to all three models**

Edit `science-model/src/science_model/tasks.py`. Update `Task`:

```python
class Task(BaseModel):
    """A research task."""

    id: str
    project: str = ""
    title: str
    description: str = ""
    type: str = ""
    aspects: list[str] = Field(default_factory=list)
    priority: str = "P2"
    status: str = TaskStatus.PROPOSED
    blocked_by: list[str] = []
    related: list[str] = []
    group: str = ""
    artifacts: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    created: date = Field(default_factory=date.today)
    completed: date | None = None
```

Update `TaskCreate`:

```python
class TaskCreate(BaseModel):
    """Input for creating a new task."""

    title: str
    type: str = ""
    aspects: list[str] = Field(default_factory=list)
    priority: str = "P2"
    related: list[str] = []
    blocked_by: list[str] = []
    group: str = ""
    description: str = ""
```

Update `TaskUpdate`:

```python
class TaskUpdate(BaseModel):
    """Partial update for a task."""

    title: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    type: str | None = None
    aspects: list[str] | None = None
    related: list[str] | None = None
    blocked_by: list[str] | None = None
    group: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks.py -v
```

Expected: PASS (new tests + existing tests still pass).

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/tasks.py science-tool/tests/test_tasks.py
git commit -m "feat(aspects): add aspects field to Task/TaskCreate/TaskUpdate models"
```

---

## Task 7: Task parser reads inline `- aspects:` field

**Files:**
- Modify: `science-tool/src/science_tool/tasks.py`
- Test: `science-tool/tests/test_tasks.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_tasks.py`:

```python
def test_parse_task_reads_aspects_inline_field(tmp_path):
    from science_tool.tasks import parse_tasks

    active = tmp_path / "active.md"
    active.write_text(
        "## [t001] Example\n"
        "- priority: P1\n"
        "- status: active\n"
        "- aspects: [hypothesis-testing, computational-analysis]\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
    )
    tasks = parse_tasks(active)
    assert len(tasks) == 1
    assert tasks[0].aspects == ["hypothesis-testing", "computational-analysis"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks.py::test_parse_task_reads_aspects_inline_field -v
```

Expected: FAIL — parser doesn't populate `aspects`.

- [ ] **Step 3: Extend `_parse_task_block`**

Edit `science-tool/src/science_tool/tasks.py`. Locate `_parse_task_block` and extend the `Task(...)` constructor call (around line 64–76) to include the new field:

```python
    return Task(
        id=task_id,
        title=title,
        type=fields.get("type", ""),
        aspects=_parse_list_value(fields.get("aspects", "")),
        priority=fields.get("priority", ""),
        status=fields.get("status", ""),
        created=created,
        description=description,
        related=_parse_list_value(fields.get("related", "")),
        blocked_by=_parse_list_value(fields.get("blocked-by", "")),
        group=fields.get("group", ""),
        completed=completed,
    )
```

The existing `_parse_list_value` helper already handles `[a, b, c]`-bracketed lists, so nothing else needs changing.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks.py
git commit -m "feat(aspects): parse inline task aspects field"
```

---

## Task 8: Task renderer emits `- aspects:` line

**Files:**
- Modify: `science-tool/src/science_tool/tasks.py`
- Test: `science-tool/tests/test_tasks.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_tasks.py`:

```python
def test_render_task_emits_aspects_when_nonempty() -> None:
    from datetime import date

    from science_tool.tasks import Task, render_task

    t = Task(
        id="t001",
        title="Demo",
        priority="P1",
        status="proposed",
        aspects=["hypothesis-testing", "computational-analysis"],
        created=date(2026, 4, 19),
    )
    rendered = render_task(t)
    assert "- aspects: [hypothesis-testing, computational-analysis]" in rendered


def test_render_task_omits_aspects_when_empty() -> None:
    from datetime import date

    from science_tool.tasks import Task, render_task

    t = Task(
        id="t001",
        title="Demo",
        priority="P1",
        status="proposed",
        created=date(2026, 4, 19),
    )
    rendered = render_task(t)
    assert "aspects" not in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks.py -v
```

Expected: first new test FAILs (renderer doesn't emit aspects); second passes incidentally.

- [ ] **Step 3: Extend `render_task`**

Edit `science-tool/src/science_tool/tasks.py`. In `render_task`, add an `aspects` emission after the `status` line and before `related`:

```python
def render_task(task: Task) -> str:
    """Render a single task to markdown."""
    lines = [f"## [{task.id}] {task.title}"]
    if task.type:
        lines.append(f"- type: {task.type}")
    lines.append(f"- priority: {task.priority}")
    lines.append(f"- status: {task.status}")
    if task.aspects:
        items = ", ".join(task.aspects)
        lines.append(f"- aspects: [{items}]")
    if task.related:
        items = ", ".join(task.related)
        lines.append(f"- related: [{items}]")
    if task.blocked_by:
        items = ", ".join(task.blocked_by)
        lines.append(f"- blocked-by: [{items}]")
    if task.group:
        lines.append(f"- group: {task.group}")
    lines.append(f"- created: {task.created.isoformat()}")
    if task.completed is not None:
        lines.append(f"- completed: {task.completed.isoformat()}")
    lines.append("")
    lines.append(task.description)
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks.py
git commit -m "feat(aspects): render aspects field in task markdown"
```

---

## Task 9: `add_task()` accepts aspects; drop required `task_type`

**Files:**
- Modify: `science-tool/src/science_tool/tasks.py`
- Test: `science-tool/tests/test_tasks.py`

- [ ] **Step 1: Write the failing test**

Append to `test_tasks.py`:

```python
def test_add_task_with_aspects(tmp_path) -> None:
    from science_tool.tasks import add_task, parse_tasks

    (tmp_path / "active.md").write_text("")

    task = add_task(
        tasks_dir=tmp_path,
        title="Test task",
        priority="P1",
        aspects=["hypothesis-testing"],
    )
    assert task.aspects == ["hypothesis-testing"]
    assert task.type == ""

    reread = parse_tasks(tmp_path / "active.md")
    assert reread[0].aspects == ["hypothesis-testing"]


def test_add_task_without_aspects_writes_no_aspects_line(tmp_path) -> None:
    from science_tool.tasks import add_task

    (tmp_path / "active.md").write_text("")
    add_task(tasks_dir=tmp_path, title="Test", priority="P2")

    body = (tmp_path / "active.md").read_text()
    assert "aspects" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks.py -v
```

Expected: FAIL — `add_task` signature requires `task_type`.

- [ ] **Step 3: Relax `add_task` signature**

Edit `science-tool/src/science_tool/tasks.py`. Update `add_task`:

```python
def add_task(
    tasks_dir: Path,
    title: str,
    priority: str,
    task_type: str = "",
    aspects: list[str] | None = None,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    group: str = "",
    description: str = "",
) -> Task:
    """Create a task with status 'proposed', auto-assign ID, write to active.md."""
    task_id = next_task_id(tasks_dir)
    task = Task(
        id=task_id,
        title=title,
        type=task_type,
        aspects=aspects or [],
        priority=priority,
        status="proposed",
        created=date.today(),
        related=related or [],
        blocked_by=blocked_by or [],
        group=group,
        description=description,
    )
    tasks = _read_active(tasks_dir)
    tasks.append(task)
    _write_active(tasks_dir, tasks)
    return task
```

`task_type` is now optional and defaults to empty; callers that passed `task_type="research"` continue to work during transition, but new callers use `aspects=[...]`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks.py -v
```

Expected: PASS. No existing test should regress (they pass `task_type=` as a keyword, which still works).

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks.py
git commit -m "feat(aspects): add_task accepts aspects; task_type is optional"
```

---

## Task 10: `tasks add` CLI — drop `--type`, add `--aspects`

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_tasks_cli.py` (existing file)

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_tasks_cli.py`:

```python
def test_tasks_add_accepts_aspects_flag(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing]\n"
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "tasks",
            "add",
            "Demo task",
            "--priority",
            "P1",
            "--aspects",
            "hypothesis-testing",
        ],
    )
    assert result.exit_code == 0, result.output
    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "- aspects: [hypothesis-testing]" in body


def test_tasks_add_without_type_or_aspects(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing]\n"
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main, ["tasks", "add", "Demo", "--priority", "P2"]
    )
    assert result.exit_code == 0, result.output
    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "aspects" not in body
    assert "- type:" not in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks_cli.py -v
```

Expected: FAIL — `--type` is still required.

- [ ] **Step 3: Update the CLI**

Edit `science-tool/src/science_tool/cli.py`. Find `tasks_add` (around line 1983) and rewrite:

```python
@tasks.command("add")
@click.argument("title")
@click.option("--priority", required=True, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--aspects", "aspects", multiple=True)
@click.option("--related", multiple=True)
@click.option("--blocked-by", multiple=True)
@click.option("--group", default="")
@click.option("--description", default="")
def tasks_add(
    title: str,
    priority: str,
    aspects: tuple[str, ...],
    related: tuple[str, ...],
    blocked_by: tuple[str, ...],
    group: str,
    description: str,
) -> None:
    """Add a new task."""
    from science_model.aspects import (
        AspectValidationError,
        load_project_aspects,
        validate_entity_aspects,
    )
    from science_tool.tasks import add_task

    validated_aspects: list[str] = []
    if aspects:
        project_aspects = load_project_aspects(Path.cwd())
        try:
            validated_aspects = validate_entity_aspects(list(aspects), project_aspects)
        except AspectValidationError as exc:
            raise click.ClickException(str(exc)) from exc

    task = add_task(
        tasks_dir=DEFAULT_TASKS_DIR,
        title=title,
        priority=priority,
        aspects=validated_aspects or None,
        related=list(related) or None,
        blocked_by=list(blocked_by) or None,
        group=group,
        description=description,
    )
    click.echo(f"Created [{task.id}] {task.title}")
```

Note: the `--type` flag is removed entirely. Callers that previously passed `--type=research` now pass `--aspects=<aspect-name>` or omit (to inherit from project). The `add_task` helper no longer requires a type.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/tests/test_tasks_cli.py
git commit -m "feat(aspects): tasks add — drop --type, add --aspects"
```

---

## Task 11: `tasks edit` CLI — drop `--type`, add `--aspects`

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_tasks_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `test_tasks_cli.py`:

```python
def test_tasks_edit_updates_aspects(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Demo\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- created: 2026-04-19\n"
        "\n"
        "Body.\n"
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "tasks",
            "edit",
            "t001",
            "--aspects",
            "software-development",
        ],
    )
    assert result.exit_code == 0, result.output
    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "- aspects: [software-development]" in body
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks_cli.py::test_tasks_edit_updates_aspects -v
```

Expected: FAIL — `--aspects` not accepted.

- [ ] **Step 3: Update `tasks_edit`**

Edit `science-tool/src/science_tool/cli.py`. Find `tasks_edit` and:
- Remove the `@click.option("--type", "task_type", ...)` decorator.
- Add `@click.option("--aspects", "aspects", multiple=True)` in its place.
- Update the function signature: remove `task_type: str | None = None`, add `aspects: tuple[str, ...]`.
- Inside the function body, replace any `task_type=task_type` handling with aspect validation + update, similar to `tasks_add`.

The existing `tasks_edit` calls into `science_tool.tasks.edit_task`. Update that helper too:

In `science-tool/src/science_tool/tasks.py`, find `edit_task` (around line 291) and replace its `task_type` parameter with `aspects`:

```python
def edit_task(
    tasks_dir: Path,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    aspects: list[str] | None = None,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    group: str | None = None,
) -> Task:
    tasks = _read_active(tasks_dir)
    task = _find_task(tasks, task_id)
    if title is not None:
        task.title = title
    if description is not None:
        task.description = description
    if priority is not None:
        task.priority = priority
    if status is not None:
        task.status = status
    if aspects is not None:
        task.aspects = aspects
    if related is not None:
        task.related = related
    if blocked_by is not None:
        task.blocked_by = blocked_by
    if group is not None:
        task.group = group
    _write_active(tasks_dir, tasks)
    return task
```

Update the CLI wrapper accordingly:

```python
@tasks.command("edit")
@click.argument("task_id")
@click.option("--title", default=None)
@click.option("--description", default=None)
@click.option("--priority", default=None, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--status", default=None)
@click.option("--aspects", "aspects", multiple=True)
@click.option("--related", multiple=True)
@click.option("--blocked-by", multiple=True)
@click.option("--group", default=None)
def tasks_edit(
    task_id: str,
    title: str | None,
    description: str | None,
    priority: str | None,
    status: str | None,
    aspects: tuple[str, ...],
    related: tuple[str, ...],
    blocked_by: tuple[str, ...],
    group: str | None,
) -> None:
    """Edit an existing task's fields."""
    from science_model.aspects import (
        AspectValidationError,
        load_project_aspects,
        validate_entity_aspects,
    )
    from science_tool.tasks import edit_task

    validated_aspects: list[str] | None = None
    if aspects:
        project_aspects = load_project_aspects(Path.cwd())
        try:
            validated_aspects = validate_entity_aspects(list(aspects), project_aspects)
        except AspectValidationError as exc:
            raise click.ClickException(str(exc)) from exc

    task = edit_task(
        tasks_dir=DEFAULT_TASKS_DIR,
        task_id=task_id,
        title=title,
        description=description,
        priority=priority,
        status=status,
        aspects=validated_aspects,
        related=list(related) if related else None,
        blocked_by=list(blocked_by) if blocked_by else None,
        group=group,
    )
    click.echo(f"Edited [{task.id}] {task.title}")
```

Find any remaining callers that pass `task_type=` into `edit_task` and update them to pass `aspects=` instead. Run `grep -rn "edit_task(.*task_type" science-tool/` to check.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks_cli.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks_cli.py
git commit -m "feat(aspects): tasks edit — drop --type, add --aspects"
```

---

## Task 12: `tasks list` CLI — drop `--type`, add `--aspect` filter

**Files:**
- Modify: `science-tool/src/science_tool/cli.py`
- Modify: `science-tool/src/science_tool/tasks.py`
- Test: `science-tool/tests/test_tasks_cli.py`

- [ ] **Step 1: Write the failing test**

Append to `test_tasks_cli.py`:

```python
def test_tasks_list_filter_by_aspect(tmp_path, monkeypatch):
    from click.testing import CliRunner

    from science_tool.cli import main

    (tmp_path / "tasks").mkdir()
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Research task\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- aspects: [hypothesis-testing]\n"
        "- created: 2026-04-19\n"
        "\n"
        "Body.\n"
        "\n"
        "## [t002] Software task\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- aspects: [software-development]\n"
        "- created: 2026-04-19\n"
        "\n"
        "Body.\n"
    )
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(main, ["tasks", "list", "--aspect", "hypothesis-testing"])
    assert result.exit_code == 0, result.output
    assert "t001" in result.output
    assert "t002" not in result.output
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks_cli.py::test_tasks_list_filter_by_aspect -v
```

Expected: FAIL — `--aspect` not recognized.

- [ ] **Step 3: Update the CLI and filter logic**

In `science-tool/src/science_tool/cli.py`, find `tasks_list` and:
- Remove the `--type` option.
- Add `@click.option("--aspect", "aspects", multiple=True)`.
- In the function body, pass `aspects` through to `list_tasks`.

In `science-tool/src/science_tool/tasks.py`, update `list_tasks` to accept and apply an aspect filter. Look at its existing signature (around line 334) and add:

```python
def list_tasks(
    tasks_dir: Path,
    project_root: Path | None = None,
    status: str | None = None,
    priority: str | None = None,
    related: str | None = None,
    group: str | None = None,
    aspects: list[str] | None = None,
) -> list[Task]:
    # ... existing logic ...
    # After existing filters, add:
    if aspects:
        from science_model.aspects import (
            load_project_aspects,
            matches_aspect_filter,
            resolve_entity_aspects,
        )

        project_aspects = load_project_aspects(project_root or tasks_dir.parent)
        filter_set = set(aspects)
        tasks = [
            t
            for t in tasks
            if matches_aspect_filter(
                resolve_entity_aspects(t.aspects or None, project_aspects),
                filter_set,
            )
        ]
    return tasks
```

The existing CLI wrapper should pass `project_root=Path.cwd()` and `aspects=list(aspects) or None` when calling `list_tasks`.

Update `tasks_list` CLI:

```python
@tasks.command("list")
@click.option("--status", default=None)
@click.option("--priority", default=None, type=click.Choice(["P0", "P1", "P2", "P3"]))
@click.option("--related", default=None)
@click.option("--group", default=None)
@click.option("--aspect", "aspects", multiple=True)
def tasks_list(
    status: str | None,
    priority: str | None,
    related: str | None,
    group: str | None,
    aspects: tuple[str, ...],
) -> None:
    """List active tasks, optionally filtered."""
    from science_tool.tasks import list_tasks
    from science_tool.tasks_display import render_tasks_table, sort_tasks

    matched = list_tasks(
        tasks_dir=DEFAULT_TASKS_DIR,
        project_root=Path.cwd(),
        status=status,
        priority=priority,
        related=related,
        group=group,
        aspects=list(aspects) or None,
    )
    render_tasks_table(sort_tasks(matched))
```

If the existing `list_tasks` wrapper has a different signature (e.g., accepts `task_type`), remove that parameter. Search for existing callers in `cli.py` and update them to match the new signature.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_tasks_cli.py tests/test_tasks.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/cli.py science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks_cli.py
git commit -m "feat(aspects): tasks list — drop --type, add --aspect filter"
```

---

## Task 13: Aspects migration — `build_migration_plan` (pure function)

**Files:**
- Create: `science-tool/src/science_tool/aspects/__init__.py`
- Create: `science-tool/src/science_tool/aspects/migrate.py`
- Create: `science-tool/tests/test_aspects_migrate.py`

- [ ] **Step 1: Write the failing tests**

Create `science-tool/tests/test_aspects_migrate.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.aspects.migrate import (
    AspectsMigrationConflict,
    build_migration_plan,
)

FIXTURE = Path(__file__).parent / "fixtures" / "aspects" / "legacy_project"


def test_plan_maps_type_dev_to_software_development(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Pipeline cleanup\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )

    plan = build_migration_plan(tmp_path)
    assert len(plan.task_rewrites) == 1
    rewrite = plan.task_rewrites[0]
    assert rewrite.task_id == "t001"
    assert rewrite.new_aspects == ["software-development"]


def test_plan_maps_type_research_to_non_software_project_aspects(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t002] PHF19 analysis\n"
        "- type: research\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- created: 2026-04-02\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, computational-analysis, software-development]\n"
    )

    plan = build_migration_plan(tmp_path)
    rewrite = plan.task_rewrites[0]
    assert rewrite.new_aspects == ["hypothesis-testing", "computational-analysis"]


def test_plan_skips_tasks_already_migrated(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t003] Already done\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- aspects: [hypothesis-testing]\n"
        "- created: 2026-04-03\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing]\n"
    )

    plan = build_migration_plan(tmp_path)
    assert plan.task_rewrites == []
    assert plan.conflicts == []


def test_plan_reports_conflict_for_tasks_with_both_type_and_aspects(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t004] Both fields\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- aspects: [hypothesis-testing]\n"
        "- created: 2026-04-04\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )

    plan = build_migration_plan(tmp_path)
    assert plan.task_rewrites == []
    assert len(plan.conflicts) == 1
    assert plan.conflicts[0].task_id == "t004"


def test_plan_raises_when_project_has_no_aspects(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t005] Any\n- type: research\n- priority: P2\n- status: proposed\n"
        "- created: 2026-04-05\n\nBody.\n"
    )
    (tmp_path / "science.yaml").write_text("name: demo\nprofile: research\n")

    with pytest.raises(AspectsMigrationConflict, match="science.yaml"):
        build_migration_plan(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_migrate.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create the migration module**

Create `science-tool/src/science_tool/aspects/__init__.py`:

```python
"""Aspect migration: one-shot rewrite of legacy task `type: research|dev`."""
from __future__ import annotations
```

Create `science-tool/src/science_tool/aspects/migrate.py`:

```python
"""Build and apply the one-shot aspect migration for legacy task entries."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from science_model.aspects import SOFTWARE_ASPECT, load_project_aspects
from science_tool.tasks import parse_tasks


@dataclass(frozen=True)
class TaskRewrite:
    task_id: str
    source_path: Path
    new_aspects: list[str]


@dataclass(frozen=True)
class TaskConflict:
    task_id: str
    source_path: Path
    reason: str


@dataclass(frozen=True)
class AspectsMigrationPlan:
    task_rewrites: list[TaskRewrite] = field(default_factory=list)
    conflicts: list[TaskConflict] = field(default_factory=list)


class AspectsMigrationConflict(RuntimeError):
    """Raised when migration cannot safely proceed without user action."""


def build_migration_plan(project_root: Path) -> AspectsMigrationPlan:
    """Scan project task files and produce a migration plan.

    Rules:
    - `type: dev` → `aspects: [software-development]`.
    - `type: research` → `aspects: <project.aspects \\ {software-development}>`.
      Falls back to full project.aspects if the set difference is empty.
    - Task already carrying `aspects:` and no `type:`: skipped.
    - Task carrying both `type:` and `aspects:`: reported as a conflict, no rewrite.
    - Project with no `aspects:` in science.yaml: raises
      ``AspectsMigrationConflict`` because there is no target vocabulary.
    """
    project_aspects = load_project_aspects(project_root)
    if not project_aspects:
        raise AspectsMigrationConflict(
            "Project science.yaml has no 'aspects:' declaration; "
            "migration has no target vocabulary."
        )
    non_software = [a for a in project_aspects if a != SOFTWARE_ASPECT]

    rewrites: list[TaskRewrite] = []
    conflicts: list[TaskConflict] = []

    tasks_dir = project_root / "tasks"
    task_files = [tasks_dir / "active.md"]
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        task_files.extend(sorted(done_dir.glob("*.md")))

    for path in task_files:
        if not path.is_file():
            continue
        for task in parse_tasks(path):
            legacy_type = (task.type or "").strip()
            has_aspects = bool(task.aspects)

            if not legacy_type:
                continue
            if has_aspects:
                conflicts.append(
                    TaskConflict(
                        task_id=task.id,
                        source_path=path,
                        reason=(
                            f"task carries both 'type: {legacy_type}' and "
                            f"'aspects: {task.aspects}'; manual cleanup required."
                        ),
                    )
                )
                continue

            if legacy_type == "dev":
                target = [SOFTWARE_ASPECT]
            elif legacy_type == "research":
                target = non_software or list(project_aspects)
            else:
                conflicts.append(
                    TaskConflict(
                        task_id=task.id,
                        source_path=path,
                        reason=f"unknown legacy task type: {legacy_type!r}",
                    )
                )
                continue

            rewrites.append(
                TaskRewrite(task_id=task.id, source_path=path, new_aspects=target)
            )

    return AspectsMigrationPlan(task_rewrites=rewrites, conflicts=conflicts)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_migrate.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/aspects/ science-tool/tests/test_aspects_migrate.py
git commit -m "feat(aspects): build_migration_plan for legacy task type field"
```

---

## Task 14: Aspects migration — `apply_migration_plan`

**Files:**
- Modify: `science-tool/src/science_tool/aspects/migrate.py`
- Modify: `science-tool/tests/test_aspects_migrate.py`

- [ ] **Step 1: Add failing tests**

Append to `test_aspects_migrate.py`:

```python
from science_tool.aspects.migrate import apply_migration_plan


def test_apply_rewrites_task_file_in_place(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    original = (
        "## [t001] Cleanup\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "tasks" / "active.md").write_text(original)
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )

    plan = build_migration_plan(tmp_path)
    apply_migration_plan(plan)

    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "- type: dev" not in body
    assert "- aspects: [software-development]" in body


def test_apply_is_idempotent(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Cleanup\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )

    apply_migration_plan(build_migration_plan(tmp_path))
    # Second run: no more rewrites because no more `type:` lines.
    plan2 = build_migration_plan(tmp_path)
    assert plan2.task_rewrites == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_migrate.py -v
```

Expected: FAIL — `apply_migration_plan` not defined.

- [ ] **Step 3: Implement `apply_migration_plan`**

Append to `science-tool/src/science_tool/aspects/migrate.py`:

```python
def apply_migration_plan(plan: AspectsMigrationPlan) -> None:
    """Apply the rewrites in ``plan`` in place.

    For each `TaskRewrite`: parse the source file, find the task by ID,
    remove its `- type:` line, insert `- aspects: [...]` (canonical order),
    preserve all other formatting.
    """
    from collections import defaultdict

    from science_tool.tasks import parse_tasks, render_tasks

    rewrites_by_path: dict[Path, dict[str, list[str]]] = defaultdict(dict)
    for rewrite in plan.task_rewrites:
        rewrites_by_path[rewrite.source_path][rewrite.task_id] = rewrite.new_aspects

    for path, per_task in rewrites_by_path.items():
        tasks = parse_tasks(path)
        for task in tasks:
            if task.id in per_task:
                task.aspects = per_task[task.id]
                task.type = ""  # drop legacy field
        path.write_text(render_tasks(tasks))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_migrate.py -v
```

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/aspects/migrate.py science-tool/tests/test_aspects_migrate.py
git commit -m "feat(aspects): apply_migration_plan in-place rewrite"
```

---

## Task 15: `science-tool aspects migrate` CLI

**Files:**
- Create: `science-tool/src/science_tool/aspects/cli.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Create: `science-tool/tests/test_aspects_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `science-tool/tests/test_aspects_cli.py`:

```python
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _seed_legacy_project(tmp_path: Path) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Pipeline\n"
        "- type: dev\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
    )
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\n"
        "aspects: [hypothesis-testing, software-development]\n"
    )


def test_migrate_group_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["aspects", "--help"])
    assert result.exit_code == 0
    assert "migrate" in result.output


def test_migrate_dry_run_prints_plan_without_writing(tmp_path: Path) -> None:
    _seed_legacy_project(tmp_path)
    original = (tmp_path / "tasks" / "active.md").read_text()
    runner = CliRunner()
    result = runner.invoke(
        main, ["aspects", "migrate", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    assert "t001" in result.output
    assert (tmp_path / "tasks" / "active.md").read_text() == original


def test_migrate_apply_rewrites_file(tmp_path: Path) -> None:
    _seed_legacy_project(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main, ["aspects", "migrate", "--project-root", str(tmp_path), "--apply"]
    )
    assert result.exit_code == 0, result.output
    body = (tmp_path / "tasks" / "active.md").read_text()
    assert "- type: dev" not in body
    assert "- aspects: [software-development]" in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_cli.py -v
```

Expected: FAIL — `aspects` group not registered.

- [ ] **Step 3: Implement the CLI**

Create `science-tool/src/science_tool/aspects/cli.py`:

```python
from __future__ import annotations

from pathlib import Path

import click

from science_tool.aspects.migrate import (
    AspectsMigrationConflict,
    apply_migration_plan,
    build_migration_plan,
)


@click.group("aspects")
def aspects_group() -> None:
    """Manage entity aspects — migration and validation helpers."""


@aspects_group.command("migrate")
@click.option(
    "--project-root",
    type=click.Path(file_okay=False, exists=True, path_type=Path),
    default=Path.cwd(),
    show_default=True,
    help="Path to the project root (containing tasks/, science.yaml).",
)
@click.option(
    "--apply",
    "apply_flag",
    is_flag=True,
    default=False,
    help="Write changes in place. Without this flag, prints the plan and exits.",
)
def migrate_cmd(project_root: Path, apply_flag: bool) -> None:
    """Migrate legacy task `type: research|dev` fields into `aspects:`."""
    try:
        plan = build_migration_plan(project_root)
    except AspectsMigrationConflict as exc:
        raise click.ClickException(str(exc)) from exc

    if not plan.task_rewrites and not plan.conflicts:
        click.echo("No legacy task entries found. Project is migrated.")
        return

    for rewrite in plan.task_rewrites:
        click.echo(
            f"[{rewrite.task_id}] in {rewrite.source_path.name}: "
            f"-> aspects: {rewrite.new_aspects}"
        )
    for conflict in plan.conflicts:
        click.echo(
            f"[{conflict.task_id}] in {conflict.source_path.name}: "
            f"CONFLICT — {conflict.reason}",
            err=True,
        )

    if not apply_flag:
        click.echo("")
        click.echo(f"Dry run. Re-run with --apply to write {len(plan.task_rewrites)} change(s).")
        return

    apply_migration_plan(plan)
    click.echo("")
    click.echo(f"Applied {len(plan.task_rewrites)} rewrite(s).")
    if plan.conflicts:
        click.echo(f"Skipped {len(plan.conflicts)} conflict(s); resolve manually.")
```

Register in `science-tool/src/science_tool/cli.py`. Near the other module imports (top of the file with `big_picture_group`), add:

```python
from science_tool.aspects.cli import aspects_group
```

Near the other `main.add_command(...)` calls (same location as `main.add_command(big_picture_group)`), add:

```python
main.add_command(aspects_group)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_aspects_cli.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/aspects/cli.py science-tool/src/science_tool/cli.py science-tool/tests/test_aspects_cli.py
git commit -m "feat(aspects): science-tool aspects migrate CLI"
```

---

## Task 16: Resolver — load entity aspects per question + emit `resolved_aspects`

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/resolver.py`
- Modify: `science-tool/tests/test_big_picture_resolver.py`

- [ ] **Step 1: Extend the fixture project with an explicitly-software-tagged question**

Add `science-tool/tests/fixtures/big_picture/minimal_project/science.yaml` with aspects:

```yaml
name: "big-picture-minimal"
profile: "research"
aspects:
  - hypothesis-testing
  - software-development
```

Create `science-tool/tests/fixtures/big_picture/minimal_project/doc/questions/q06-software-pipeline-concern.md`:

```markdown
---
id: "question:q06-software-pipeline-concern"
type: "question"
aspects: ["software-development"]
---
Software-scoped question: exists but does not belong in research synthesis.
```

- [ ] **Step 2: Write the failing tests**

Append to `science-tool/tests/test_big_picture_resolver.py`:

```python
def test_resolved_aspects_inherits_from_project() -> None:
    result = resolve_questions(FIXTURE)
    q01 = result["question:q01-direct-to-h1"]
    # q01 declares no aspects; fixture project aspects are
    # [hypothesis-testing, software-development].
    assert q01.resolved_aspects == ["hypothesis-testing", "software-development"]


def test_resolved_aspects_overrides_with_explicit_entity_aspects() -> None:
    result = resolve_questions(FIXTURE)
    q06 = result["question:q06-software-pipeline-concern"]
    assert q06.resolved_aspects == ["software-development"]


def test_resolver_raises_on_invalid_explicit_aspects(tmp_path: Path) -> None:
    (tmp_path / "specs" / "hypotheses").mkdir(parents=True)
    (tmp_path / "doc" / "questions").mkdir(parents=True)
    (tmp_path / "science.yaml").write_text(
        "name: broken\nprofile: research\naspects: [hypothesis-testing]\n"
    )
    (tmp_path / "doc" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\naspects: [\"not-a-real-aspect\"]\n---\nBroken.\n'
    )
    with pytest.raises(Exception):  # AspectValidationError or ClickException-like
        resolve_questions(tmp_path)
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py -v
```

Expected: new tests FAIL — `resolved_aspects` not on `ResolverOutput`.

- [ ] **Step 4: Update the resolver**

Edit `science-tool/src/science_tool/big_picture/resolver.py`:

Add the new field to `ResolverOutput`:

```python
@dataclass(frozen=True)
class ResolverOutput:
    hypotheses: list[HypothesisMatch] = field(default_factory=list)
    primary_hypothesis: str | None = None
    resolved_aspects: list[str] = field(default_factory=list)
```

Update imports at the top:

```python
from science_model.aspects import (
    AspectValidationError,
    load_project_aspects,
    resolve_entity_aspects,
    validate_entity_aspects,
)
```

Extend `resolve_questions` to load project aspects once and compute `resolved_aspects` per question:

```python
def resolve_questions(project_root: Path) -> dict[str, ResolverOutput]:
    """Resolve all questions in ``project_root`` to hypothesis associations."""
    questions = _load_entities(project_root / "doc" / "questions")
    hypotheses = _load_entities(project_root / "specs" / "hypotheses")

    try:
        project_aspects = load_project_aspects(project_root)
    except FileNotFoundError:
        project_aspects = []

    results: dict[str, dict[str, HypothesisMatch]] = {qid: {} for qid in questions}

    # (existing direct/inverse/transitive logic unchanged) ...

    out: dict[str, ResolverOutput] = {}
    for qid, matches in results.items():
        qfm = questions[qid]
        raw_aspects = qfm.get("aspects")
        if raw_aspects is None:
            resolved = resolve_entity_aspects(None, project_aspects)
        else:
            if not isinstance(raw_aspects, list):
                raise AspectValidationError(
                    f"{qid}: 'aspects' must be a list, got {type(raw_aspects).__name__}"
                )
            validated = validate_entity_aspects([str(a) for a in raw_aspects], project_aspects)
            resolved = resolve_entity_aspects(validated, project_aspects)

        finalized = _finalize(matches)
        out[qid] = ResolverOutput(
            hypotheses=finalized.hypotheses,
            primary_hypothesis=finalized.primary_hypothesis,
            resolved_aspects=resolved,
        )
    return out
```

Replace the old `return {qid: _finalize(matches) for qid, matches in results.items()}` with the loop above.

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_resolver.py -v
```

Expected: all PASS (existing tests + new tests). The existing direct/inverse/transitive tests still pass because the resolver's association logic is unchanged.

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/big_picture/resolver.py science-tool/tests/test_big_picture_resolver.py science-tool/tests/fixtures/big_picture/minimal_project/
git commit -m "feat(aspects): resolver emits resolved_aspects per question"
```

---

## Task 17: Validator — exclude software-only questions from orphan count

**Files:**
- Modify: `science-tool/src/science_tool/big_picture/validator.py`
- Modify: `science-tool/tests/test_big_picture_validator.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_big_picture_validator.py`:

```python
def test_orphan_count_excludes_software_only_questions() -> None:
    # Using the extended minimal_project fixture which now has q06 tagged
    # aspects: [software-development]. That question has no hypothesis
    # match, but should NOT count as a research orphan.
    from science_tool.big_picture.resolver import resolve_questions

    resolved = resolve_questions(FIXTURE)
    q06 = resolved.get("question:q06-software-pipeline-concern")
    assert q06 is not None
    assert q06.primary_hypothesis is None
    # The count of "research orphans" excludes software-only.
    from science_tool.big_picture.validator import count_research_orphans

    count = count_research_orphans(resolved, project_root=FIXTURE)
    # FIXTURE's research orphans: q05-orphan (declared no aspects -> inherits
    # research). q06 should not count here.
    assert count == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_validator.py -v
```

Expected: FAIL — `count_research_orphans` not defined.

- [ ] **Step 3: Implement `count_research_orphans`**

Edit `science-tool/src/science_tool/big_picture/validator.py`. Add:

```python
def count_research_orphans(
    resolved: dict[str, "ResolverOutput"],  # noqa: F821
    project_root: Path,
) -> int:
    """Return the number of research orphans.

    A question counts as a research orphan iff it has no hypothesis match
    AND at least one of its resolved aspects is not ``software-development``.
    Pure-software questions without hypothesis matches are out of scope
    for research synthesis and therefore do not count.
    """
    from science_model.aspects import SOFTWARE_ASPECT, matches_aspect_filter, load_project_aspects

    project_aspects = load_project_aspects(project_root)
    research_filter = {a for a in project_aspects if a != SOFTWARE_ASPECT}
    count = 0
    for output in resolved.values():
        if output.primary_hypothesis is not None:
            continue
        if matches_aspect_filter(output.resolved_aspects, research_filter):
            count += 1
    return count
```

Update `validate_rollup_file` to use the new helper:

```python
def validate_rollup_file(path: Path, project_root: Path) -> list[ValidationIssue]:
    """Return structural issues with a generated rollup (synthesis.md)."""
    issues: list[ValidationIssue] = []
    fm = read_frontmatter(path) or {}

    claimed = fm.get("orphan_question_count")
    if claimed is not None:
        resolved = resolve_questions(project_root)
        actual = count_research_orphans(resolved, project_root)
        if int(claimed) != actual:
            issues.append(
                ValidationIssue(
                    kind="orphan_count_mismatch",
                    message=f"Rollup claims {claimed} orphans but resolver expected {actual}.",
                    path=path,
                )
            )

    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_big_picture_validator.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/big_picture/validator.py science-tool/tests/test_big_picture_validator.py
git commit -m "feat(aspects): orphan count excludes software-only questions"
```

---

## Task 18: `commands/big-picture.md` — Phase 1 bundle assembly filter

**Files:**
- Modify: `commands/big-picture.md`

- [ ] **Step 1: Update the bundle-assembly prose**

Edit `commands/big-picture.md`. Find the "Phase 1: Precompute" → "For each hypothesis, assemble a bundle" section. At the top of that bullet list (before `hypothesis_path`), add a new preamble paragraph:

```markdown
**Aspect filtering**. Before assembling bundles, load project aspects via `load_project_aspects` (or parse `science.yaml` directly). Compute `research_filter = project.aspects \ {software-development}`. Throughout bundle assembly, any entity whose resolved aspects (entity `aspects:` if set, else project `aspects:`) does NOT intersect `research_filter` is excluded from the bundle. This means software-oriented questions (e.g., ones explicitly tagged `aspects: [software-development]`) are dropped before hypothesis matching runs. If `research_filter` is empty, refuse to proceed and point the user at `science-tool big-picture` — research synthesis is undefined on a software-only project.
```

And update the `interpretations` and `tasks` bullets to note the filter:

```markdown
- `tasks`: glob `tasks/*.md` and `tasks/done/*.md`; parse frontmatter; include entries whose `related:` mentions this hypothesis or any of its resolved questions **AND** whose resolved aspects intersect `research_filter`. If `tasks/active.md` is a single aggregated file (common pattern, e.g., mm30), scan its body for per-task headings and `related:` metadata instead of expecting one file per task.
- `interpretations`: glob `doc/interpretations/*.md`; parse frontmatter; include entries that either (a) directly reference this hypothesis in `related:`, or (b) reference a question whose **primary** hypothesis (per resolver output) is this hypothesis. Do NOT include interpretations that only reach this hypothesis via transitive-only questions. Apply the same `research_filter` aspect check.
```

Find the "Orphan-question counting" section (Phase 3) and update:

```markdown
Orphan-question counting:

- Compute via `count_research_orphans(resolved, project_root)` from `science_tool.big_picture.validator`. The count excludes questions whose resolved aspects are only `[software-development]`; these are out of scope for research synthesis.
```

- [ ] **Step 2: Commit**

```bash
git add commands/big-picture.md
git commit -m "docs(big-picture): filter bundle assembly by resolved aspects"
```

---

## Task 19: Templates — add optional `aspects:` slot

**Files:**
- Modify: `templates/hypothesis.md`
- Modify: `templates/question.md`
- Modify: `templates/interpretation.md`

- [ ] **Step 1: Update `templates/hypothesis.md`**

Edit `templates/hypothesis.md`. Replace the frontmatter block at the top:

```yaml
---
id: "hypothesis:h{{nn}}-{{slug}}"
type: "hypothesis"
title: "{{Short Title}}"
status: "proposed"
# aspects: ["hypothesis-testing"]  # optional override; omitted entities inherit project aspects
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---
```

- [ ] **Step 2: Update `templates/question.md`**

Edit `templates/question.md`. Replace the frontmatter:

```yaml
---
id: "question:<nn>-<slug>"
type: "question"
title: "<Question>"
status: "active"
# aspects: ["hypothesis-testing"]  # optional override; omitted entities inherit project aspects
ontology_terms: []
datasets: []
source_refs: []
related: []
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---
```

- [ ] **Step 3: Update `templates/interpretation.md`**

Edit `templates/interpretation.md`. Replace the frontmatter:

```yaml
---
id: "interpretation:{{slug}}"
type: "interpretation"
title: "{{Short Title}}"
status: "active"
# aspects: ["hypothesis-testing"]  # optional override; omitted entities inherit project aspects
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
input: "{{path to results, notebook, or prose description}}"
workflow_run: "<workflow-run-slug>"  # optional: links to the run that produced the interpreted results
prior_interpretations: []  # optional: interpretation IDs this document extends or supersedes
---
```

- [ ] **Step 4: Verify**

```bash
grep -n "aspects" /mnt/ssd/Dropbox/science/templates/hypothesis.md /mnt/ssd/Dropbox/science/templates/question.md /mnt/ssd/Dropbox/science/templates/interpretation.md
```

Expected: three lines, one per file, each showing `# aspects: ["hypothesis-testing"]`.

- [ ] **Step 5: Commit**

```bash
git add templates/hypothesis.md templates/question.md templates/interpretation.md
git commit -m "feat(aspects): optional aspects slot on entity templates"
```

---

## Task 20: Health — flag legacy `type:` and invalid `aspects:`

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/tests/test_health.py`

- [ ] **Step 1: Write the failing test**

Append to `science-tool/tests/test_health.py`:

```python
def test_health_flags_legacy_task_type_field(tmp_path: Path) -> None:
    from science_tool.graph.health import collect_legacy_task_type

    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Legacy\n"
        "- type: research\n"
        "- priority: P2\n"
        "- status: proposed\n"
        "- created: 2026-04-01\n"
        "\n"
        "Body.\n"
    )
    findings = collect_legacy_task_type(tmp_path)
    assert len(findings) == 1
    assert findings[0]["task_id"] == "t001"
    assert findings[0]["legacy_type"] == "research"


def test_health_flags_invalid_entity_aspects(tmp_path: Path) -> None:
    from science_tool.graph.health import collect_invalid_entity_aspects

    (tmp_path / "doc" / "questions").mkdir(parents=True)
    (tmp_path / "science.yaml").write_text(
        "name: demo\nprofile: research\naspects: [hypothesis-testing]\n"
    )
    (tmp_path / "doc" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\naspects: [\"not-declared\"]\n---\nBroken.\n'
    )
    findings = collect_invalid_entity_aspects(tmp_path)
    assert len(findings) == 1
    assert "not-declared" in findings[0]["message"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_health.py -v
```

Expected: FAIL — functions don't exist.

- [ ] **Step 3: Add the health helpers**

Append to `science-tool/src/science_tool/graph/health.py`:

```python
class LegacyTaskTypeFinding(TypedDict):
    task_id: str
    legacy_type: str
    source_file: str


def collect_legacy_task_type(project_root: Path) -> list[LegacyTaskTypeFinding]:
    """Return a list of tasks still carrying the legacy `type:` field."""
    from science_tool.tasks import parse_tasks

    findings: list[LegacyTaskTypeFinding] = []
    tasks_dir = project_root / "tasks"
    candidates = [tasks_dir / "active.md"]
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        candidates.extend(sorted(done_dir.glob("*.md")))
    for path in candidates:
        if not path.is_file():
            continue
        for task in parse_tasks(path):
            if task.type:
                findings.append(
                    LegacyTaskTypeFinding(
                        task_id=task.id,
                        legacy_type=task.type,
                        source_file=str(path.relative_to(project_root)),
                    )
                )
    return findings


class InvalidEntityAspectsFinding(TypedDict):
    entity_id: str
    source_file: str
    message: str


def collect_invalid_entity_aspects(project_root: Path) -> list[InvalidEntityAspectsFinding]:
    """Return a list of entity files carrying invalid explicit `aspects:` values."""
    from science_model.aspects import (
        AspectValidationError,
        load_project_aspects,
        validate_entity_aspects,
    )
    from science_model.frontmatter import parse_frontmatter

    try:
        project_aspects = load_project_aspects(project_root)
    except FileNotFoundError:
        return []

    findings: list[InvalidEntityAspectsFinding] = []
    for relative in ("specs/hypotheses", "doc/questions", "doc/interpretations"):
        directory = project_root / relative
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.md"):
            result = parse_frontmatter(path)
            if result is None:
                continue
            fm, _ = result
            if "aspects" not in fm:
                continue
            raw = fm.get("aspects")
            if not isinstance(raw, list):
                findings.append(
                    InvalidEntityAspectsFinding(
                        entity_id=str(fm.get("id", path.stem)),
                        source_file=str(path.relative_to(project_root)),
                        message="aspects must be a list",
                    )
                )
                continue
            try:
                validate_entity_aspects([str(a) for a in raw], project_aspects)
            except AspectValidationError as exc:
                findings.append(
                    InvalidEntityAspectsFinding(
                        entity_id=str(fm.get("id", path.stem)),
                        source_file=str(path.relative_to(project_root)),
                        message=str(exc),
                    )
                )
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/health.py science-tool/tests/test_health.py
git commit -m "feat(aspects): health check for legacy type and invalid aspects"
```

---

## Task 21: Full test sweep

**Files:** none (verification only)

- [ ] **Step 1: Run the full science-tool test suite**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run pytest --tb=no 2>&1 | tail -5
```

Expected: all tests pass. If any pre-existing big-picture test regressed due to the resolver output-schema change or the fixture science.yaml aspect addition, fix inline.

- [ ] **Step 2: Ruff + pyright**

```bash
cd /mnt/ssd/Dropbox/science/science-tool && uv run --frozen ruff check src/science_tool/aspects/ src/science_tool/big_picture/ src/science_tool/tasks.py src/science_tool/cli.py tests/test_aspects_*.py tests/test_big_picture_*.py tests/test_tasks*.py 2>&1 | tail -3
cd /mnt/ssd/Dropbox/science/science-tool && uv run --frozen pyright src/science_tool/aspects/ src/science_tool/big_picture/resolver.py src/science_tool/big_picture/validator.py 2>&1 | tail -3
```

Expected: ruff clean on new files; pyright clean on new files (pre-existing errors in unrelated files are OK).

- [ ] **Step 3: No commit — verification only**

---

## Task 22: Smoke test on mm30 — run migration + `/science:big-picture`

**Files:** none in `science`; execution occurs in `/mnt/ssd/Dropbox/r/mm30/`

- [ ] **Step 1: Capture pre-state**

```bash
cd /mnt/ssd/Dropbox/r/mm30
git status
git rev-parse HEAD
```

Record the SHA.

- [ ] **Step 2: Check current `science.yaml` aspects**

```bash
grep -A4 "^aspects:" science.yaml
```

If `aspects:` is absent or empty, add appropriate aspects (research projects typically get `hypothesis-testing`, `computational-analysis`, `software-development`).

- [ ] **Step 3: Run migration dry-run**

```bash
cd /mnt/ssd/Dropbox/r/mm30
uv run science-tool aspects migrate --project-root . 2>&1 | head -50
```

Expected: lists each legacy `type:` task with its proposed `aspects:` mapping. Confirm the mapping is sensible — `type: dev` tasks map to `[software-development]`, `type: research` tasks map to the project's non-software aspects.

- [ ] **Step 4: Apply migration**

```bash
uv run science-tool aspects migrate --project-root . --apply
```

Expected: task files rewritten. `git diff tasks/` should show `- type:` lines removed and `- aspects:` lines added. Commit the migration inside mm30 (optional; user's call).

- [ ] **Step 5: Re-run `/science:big-picture`**

In a Claude Code session at `/mnt/ssd/Dropbox/r/mm30`, invoke `/science:big-picture`. Confirm:

- The generated bundles no longer include software-oriented tasks.
- `_emergent-threads.md`'s orphan count has dropped by the number of previously-orphaned software questions.
- Per-hypothesis files still cite the same research interpretations as before.

- [ ] **Step 6: Run validator**

```bash
uv run science-tool big-picture validate --project-root .
```

Expected: exit 0. Any `orphan_count_mismatch` surfaces from aspect-aware counting interacting with whatever the rollup wrote; re-run big-picture if so.

---

## Task 23: Smoke test on natural-systems — same flow

**Files:** none in `science`; execution occurs in `/home/keith/d/natural-systems/`

Same structure as Task 22.

- [ ] **Step 1: Pre-state + science.yaml aspects check**

```bash
cd /home/keith/d/natural-systems
git status
git rev-parse HEAD
grep -A4 "^aspects:" science.yaml
```

Natural-systems is `profile: software` but has a research arm. Its `aspects:` should include at least one non-software aspect (likely `hypothesis-testing` or `computational-analysis`) for research synthesis to work. If not, add them before proceeding.

- [ ] **Step 2: Migrate task files**

```bash
uv run science-tool aspects migrate --project-root .
uv run science-tool aspects migrate --project-root . --apply
```

- [ ] **Step 3: Classify a few software-oriented questions manually**

The audit flagged `question:q14-data-quality-lens-design` as software-oriented. Open its file and add explicit `aspects: ["software-development"]` to its frontmatter. Do the same for any other obviously-software questions the user identifies.

- [ ] **Step 4: Re-run `/science:big-picture` + validator**

```bash
# In a fresh Claude Code session at /home/keith/d/natural-systems/:
/science:big-picture
# After it finishes:
uv run science-tool big-picture validate --project-root .
```

Expected: orphan count drops; `q14-data-quality-lens-design` no longer appears in `_emergent-threads.md`.

- [ ] **Step 5: Record observations**

If issues surface (the synthesizer cites IDs that don't exist, the validator flags unexpected mismatches), note them for a follow-up session. Known acceptable: the first run post-aspects may surface old orphan counts in the rollup if the previous run's `_emergent-threads.md` is still on disk and Phase 3 misreads it — regenerate and re-validate.

---

## Self-Review Checklist

After plan lands, before declaring complete:

**Spec coverage:**

- Motivation / Goal / Scope → captured in plan header.
- Design Principles (1-4) → reflected throughout: Task 1 (shared vocabulary), Task 2 (single resolution rule), Task 4 (strict validation), Task 16-17 (filtering separate from association).
- Data Model (field + semantics) → Tasks 1–6.
- Validation behavior → Task 4 (hard errors at validate), Task 16 (hard errors at resolve time), Task 20 (health surface).
- Filter Semantics → Tasks 3 (predicate), 17 (orphan counting), 18 (bundle assembly).
- Migration → Tasks 13–15 (plan/apply/CLI), Tasks 22–23 (exercised on real projects).
- Template Updates → Task 19.
- CLI Updates → Tasks 10–12 (tasks), Task 15 (aspects), Task 16 (resolver schema).
- `/science:big-picture` Updates → Tasks 16–18.
- Testing → Tasks 1–17 cover unit tests; Task 21 runs the full sweep; Tasks 22–23 cover real-project integration.
- Relationship to existing specs / Resolved decisions / Follow-on work → documentary; no plan tasks required.

**Placeholder scan:** none of the "TBD" / "implement later" / bare "handle edge cases" patterns appear in this plan. Every step shows concrete code or exact commands.

**Type consistency:**

- `KNOWN_ASPECTS`, `SOFTWARE_ASPECT`, `AspectValidationError`, `resolve_entity_aspects`, `validate_entity_aspects`, `matches_aspect_filter`, `load_project_aspects` — defined in Task 1-5 and referenced consistently in Tasks 10, 11, 12, 16, 17, 20.
- `AspectsMigrationPlan`, `TaskRewrite`, `TaskConflict`, `AspectsMigrationConflict`, `build_migration_plan`, `apply_migration_plan` — defined in Task 13-14 and consumed by Task 15 (CLI).
- `aspects_group` / `migrate_cmd` — introduced in Task 15, wired into main CLI in Task 15.
- `ResolverOutput.resolved_aspects` — introduced in Task 16, consumed by Task 17 (validator orphan count).
- `count_research_orphans` — introduced in Task 17, referenced by Task 18 (command prose).
- `collect_legacy_task_type`, `collect_invalid_entity_aspects` — introduced in Task 20.

All names consistent across tasks.
