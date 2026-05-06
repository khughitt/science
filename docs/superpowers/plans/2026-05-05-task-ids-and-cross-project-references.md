# Task IDs And Cross-Project References Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Science task IDs flat and strictly validated, add explicit local `parent:` task metadata, and standardize namespace-first cross-project entity references.

**Architecture:** Keep task-ID rules in `science_tool.tasks` as the single parser source of truth, and let storage/CLI surfaces consume that parser instead of rescanning loose regex matches. Extend `science_tool.addressing` with a small entity-reference classifier that separates local refs, bare task shorthand, namespace-first refs, legacy project shorthand, and artifact addresses. Validation remains explicit: task parsing rejects malformed task IDs early; frontmatter and task-queue validation use the classifier plus project IDs from `science.yaml`.

**Tech Stack:** Python 3.11+, Pydantic models in `science-model`, pytest, Click CLI, Bash managed artifact `validate.sh`, YAML via PyYAML.

---

## File Structure

- Modify `science-model/src/science_model/tasks.py`
  - Add `Task.parent: str = ""`, `TaskCreate.parent: str = ""`, and `TaskUpdate.parent: str | None = None`.
- Modify `science-model/tests/test_tasks.py`
  - Lock model defaults and explicit parent values.
- Modify `science/src/science_tool/tasks.py`
  - Replace loose task header parsing with one anchored strict regex.
  - Parse/render `parent:`.
  - Validate `parent:` is local task syntax only.
  - Make `next_task_id()` scan strict headers only.
- Modify `science/tests/test_tasks.py`
  - Add strict header, `t1000`, malformed header, parent round-trip, parent-locality, and `next_task_id()` regression tests.
- Modify `science/src/science_tool/graph/storage_adapters/task.py`
  - Expose `parent` on raw task records without emitting graph predicates.
- Modify `science/tests/test_storage_adapters/test_task.py`
  - Assert raw task records include `parent`.
- Modify `science/src/science_tool/addressing.py`
  - Keep artifact address helpers, and add entity-reference classification helpers.
- Modify `science/tests/test_addressing.py`
  - Update legacy two-part address expectations and add entity-reference classifier coverage.
- Modify `science/src/science_tool/refs.py`
  - Load project IDs from `science.yaml`.
  - Use address/reference classification for authored refs in frontmatter.
  - Report unknown namespaces and legacy two-part project shorthand.
- Modify `science/tests/test_refs.py`
  - Add project-aware reference validation tests.
- Modify `science/src/science_tool/project_artifacts/data/validate.sh`
  - Replace Section 15 task queue regex logic with strict task-header validation and task-reference scanning.
  - Extend Section 16 frontmatter cross-reference validation to understand namespace-first refs and legacy project shorthand.
- Modify `science/src/science_tool/project_artifacts/registry.yaml`
  - Bump `validate.sh` managed-artifact version and hash.
- Modify `science/tests/test_validate_script.py`
  - Add validator regression tests for invalid task IDs, stale task refs, parent locality, namespace refs, and legacy shorthand.
- Modify `commands/tasks.md`
  - Document flat IDs, local `parent:`, local refs, and namespace-first cross-project refs.
- Modify `docs/federation.md`
  - Tighten Addressing around canonical `<project-id>:<kind>:<slug>` entity refs and artifact addresses.
- Modify `meta/tasks/active.md`
  - Migrate `[t001b]` to `[t016]`, add `parent: task:t001`, add parent to `related:`, and update references from `t001b` to `t016`.

## Task 1: Strict Task Header Parser

**Files:**
- Modify: `science/src/science_tool/tasks.py`
- Modify: `science/tests/test_tasks.py`

- [ ] **Step 0: Audit existing task header widths before tightening**

Run:

```bash
rg -n "^## \[t[0-9]{1,2}\]" --glob "**/tasks/**/*.md" --glob "**/tasks/*.md" .
```

Expected: no output, or only fixtures that must be updated in the same task as the parser change. If this finds real project task IDs with one or two digits, migrate those task headers and references to zero-padded `tNNN` before committing the strict parser.

- [ ] **Step 1: Write failing strict-header tests**

Add these tests near the existing parser tests in `science/tests/test_tasks.py`:

```python
def test_parse_accepts_three_and_four_digit_task_ids(tmp_path: Path) -> None:
    f = _write(
        tmp_path / "active.md",
        """\
## [t016] Three digit
- type: dev
- priority: P2
- status: proposed
- created: 2026-05-05

Body.

## [t1000] Four digit
- type: dev
- priority: P2
- status: proposed
- created: 2026-05-05

Body.
""",
    )

    tasks = parse_tasks(f)

    assert [task.id for task in tasks] == ["t016", "t1000"]


def test_parse_rejects_suffix_task_id_without_partial_parse(tmp_path: Path) -> None:
    f = _write(
        tmp_path / "active.md",
        """\
## [t001b] H01 engine follow-ups
- type: dev
- priority: P1
- status: active
- created: 2026-04-24

Body.
""",
    )

    with pytest.raises(
        ValueError,
        match=r"Invalid task id 't001b' in .*active\.md: task ids must match tNNN",
    ):
        parse_tasks(f)


def test_next_task_id_ignores_invalid_suffix_header(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    _write(
        tasks_dir / "active.md",
        """\
## [t009] Valid task
- type: dev
- priority: P2
- status: proposed
- created: 2026-05-05

Body.

## [t010b] Invalid suffix task
- type: dev
- priority: P2
- status: proposed
- created: 2026-05-05

Body.
""",
    )

    assert next_task_id(tasks_dir) == "t010"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_tasks.py::test_parse_accepts_three_and_four_digit_task_ids science/tests/test_tasks.py::test_parse_rejects_suffix_task_id_without_partial_parse science/tests/test_tasks.py::test_next_task_id_ignores_invalid_suffix_header -q
```

Expected: the invalid suffix test fails because `_HEADER_RE` currently accepts `t001b`, and `next_task_id()` currently extracts `010` from `[t010b]`.

- [ ] **Step 3: Add strict task header helpers**

In `science/src/science_tool/tasks.py`, replace the current `_HEADER_RE` and `_TASK_ID_RE` declarations with:

```python
_TASK_ID_PATTERN = r"t[0-9]{3,}"
_HEADER_RE = re.compile(rf"^##\s+\[({_TASK_ID_PATTERN})\]\s+(.+)$")
_ANY_TASK_HEADER_RE = re.compile(r"^##\s+\[([^\]]+)\]\s+(.+)$")
_FIELD_RE = re.compile(r"^-\s+([\w-]+):\s*(.*)$")
_LIST_RE = re.compile(r"^\[(.+)\]$")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,3})\s+.+$")
_NOTES_HEADING_RE = re.compile(r"^###\s+Notes\s*$")
```

Then add this helper below `_parse_list_value`:

```python
def _parse_task_header(line: str, *, path: Path | None = None) -> tuple[str, str]:
    """Parse and validate a task header line."""
    match = _HEADER_RE.match(line)
    if match:
        return match.group(1), match.group(2).strip()

    loose = _ANY_TASK_HEADER_RE.match(line)
    if loose:
        task_id = loose.group(1)
        where = f" in {path}" if path is not None else ""
        msg = (
            f"Invalid task id '{task_id}'{where}: task ids must match tNNN. "
            "Use parent: task:t001 for fragments or subtasks."
        )
        raise ValueError(msg)

    where = f" in {path}" if path is not None else ""
    raise ValueError(f"Invalid task header{where}: {line}")
```

- [ ] **Step 4: Thread path-aware parsing through task blocks**

Change `_parse_task_block` to accept `path` and call the new helper:

```python
def _parse_task_block(lines: list[str], *, path: Path | None = None) -> Task:
    """Parse a single task block (header line + metadata + description)."""
    task_id, title = _parse_task_header(lines[0], path=path)
```

Change the final return in `parse_tasks()` to pass the file path:

```python
    return [_parse_task_block(block, path=path) for block in blocks]
```

Change the block splitter in `parse_tasks()` so invalid task headers start a block and then fail inside `_parse_task_block`:

```python
    for line in lines:
        if _ANY_TASK_HEADER_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
```

- [ ] **Step 5: Make `next_task_id()` strict without raising on invalid headers**

Replace the loose `_TASK_ID_RE`-based scanner in `next_task_id()` with:

```python
def _strict_task_ids_in_text(text: str) -> list[str]:
    ids: list[str] = []
    for line in text.splitlines():
        match = _HEADER_RE.match(line)
        if match:
            ids.append(match.group(1))
    return ids


def next_task_id(tasks_dir: Path) -> str:
    """Determine the next task ID by scanning active.md and done/ directory."""
    max_num = 0

    active = tasks_dir / "active.md"
    if active.is_file():
        for task_id in _strict_task_ids_in_text(active.read_text()):
            max_num = max(max_num, int(task_id[1:]))

    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        for f in done_dir.glob("*.md"):
            for task_id in _strict_task_ids_in_text(f.read_text()):
                max_num = max(max_num, int(task_id[1:]))

    return f"t{max_num + 1:03d}"
```

- [ ] **Step 6: Run tests to verify the strict parser passes**

Run:

```bash
uv run --frozen pytest science/tests/test_tasks.py::test_parse_accepts_three_and_four_digit_task_ids science/tests/test_tasks.py::test_parse_rejects_suffix_task_id_without_partial_parse science/tests/test_tasks.py::test_next_task_id_ignores_invalid_suffix_header -q
```

Expected: all three tests pass.

- [ ] **Step 7: Commit strict task header parser with the meta migration**

Before committing, complete Task 7's file edit for `meta/tasks/active.md` so the strict parser and the checked-in meta queue stay consistent in the same commit. Do not leave an intermediate commit where `parse_tasks(meta/tasks/active.md)` raises on `[t001b]`.

```bash
git add science/src/science_tool/tasks.py science/tests/test_tasks.py meta/tasks/active.md
git commit -m "fix: validate flat task ids strictly"
```

## Task 2: Parent Field In Task Model, Parser, Renderer, And Adapter

**Files:**
- Modify: `science-model/src/science_model/tasks.py`
- Modify: `science-model/tests/test_tasks.py`
- Modify: `science/src/science_tool/tasks.py`
- Modify: `science/tests/test_tasks.py`
- Modify: `science/src/science_tool/graph/storage_adapters/task.py`
- Modify: `science/tests/test_storage_adapters/test_task.py`

- [ ] **Step 1: Write failing model tests**

Add to `science-model/tests/test_tasks.py`:

```python
def test_task_parent_defaults_to_empty_string():
    t = Task(id="t016", title="Follow-up")
    assert t.parent == ""


def test_task_parent_can_be_set():
    t = Task(id="t016", title="Follow-up", parent="task:t001")
    assert t.parent == "task:t001"


def test_task_create_and_update_parent_fields():
    tc = TaskCreate(title="Follow-up", parent="task:t001")
    tu = TaskUpdate(parent="task:t002")
    assert tc.parent == "task:t001"
    assert tu.parent == "task:t002"
```

- [ ] **Step 2: Run model tests to verify they fail**

Run:

```bash
uv run --frozen pytest science-model/tests/test_tasks.py::test_task_parent_defaults_to_empty_string science-model/tests/test_tasks.py::test_task_parent_can_be_set science-model/tests/test_tasks.py::test_task_create_and_update_parent_fields -q
```

Expected: fails because `parent` is not defined.

- [ ] **Step 3: Add parent fields to task models**

In `science-model/src/science_model/tasks.py`, add `parent` immediately after `related` on `Task`, after `related` on `TaskCreate`, and after `related` on `TaskUpdate`:

```python
    parent: str = ""
```

```python
    parent: str = ""
```

```python
    parent: str | None = None
```

- [ ] **Step 4: Run model tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-model/tests/test_tasks.py::test_task_parent_defaults_to_empty_string science-model/tests/test_tasks.py::test_task_parent_can_be_set science-model/tests/test_tasks.py::test_task_create_and_update_parent_fields -q
```

Expected: all three tests pass.

- [ ] **Step 5: Write failing parser, renderer, and adapter tests**

Add to `science/tests/test_tasks.py`:

```python
def test_parse_and_render_parent_round_trips(tmp_path: Path) -> None:
    f = _write(
        tmp_path / "active.md",
        """\
## [t016] Follow-up
- type: dev
- priority: P1
- status: proposed
- parent: task:t001
- related: [hypothesis:h01, task:t001]
- created: 2026-05-05

Body.
""",
    )

    task = parse_tasks(f)[0]
    rendered = render_task(task)

    assert task.parent == "task:t001"
    assert "- parent: task:t001" in rendered
    assert parse_tasks(_write(tmp_path / "rendered.md", rendered))[0].parent == "task:t001"


def test_parent_must_be_local_task_ref(tmp_path: Path) -> None:
    f = _write(
        tmp_path / "active.md",
        """\
## [t016] Cross project parent
- type: dev
- priority: P1
- status: proposed
- parent: natural-systems:task:t001
- created: 2026-05-05

Body.
""",
    )

    with pytest.raises(ValueError, match="parent for task t016 must be local task ref like task:t001"):
        parse_tasks(f)


def test_add_task_omits_parent_by_default(tmp_path: Path) -> None:
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()

    task = add_task(tmp_path, tasks_dir, "Temporary smoke task", "P3", task_type="dev")
    rendered = (tasks_dir / "active.md").read_text(encoding="utf-8")

    assert task.id == "t001"
    assert "- parent:" not in rendered
```

Add to `science/tests/test_storage_adapters/test_task.py`:

```python
def test_load_raw_includes_parent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tasks").mkdir()
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t016] Follow-up\n"
        "- type: research\n"
        "- priority: P1\n"
        "- status: active\n"
        "- parent: task:t001\n"
        "- created: 2026-05-05\n\n"
        "Body prose.\n",
        encoding="utf-8",
    )
    adapter = TaskAdapter()
    refs = adapter.discover(tmp_path)
    monkeypatch.chdir(tmp_path)

    raw = adapter.load_raw(refs[0])

    assert raw["parent"] == "task:t001"
```

- [ ] **Step 6: Run parser and adapter tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_tasks.py::test_parse_and_render_parent_round_trips science/tests/test_tasks.py::test_parent_must_be_local_task_ref science/tests/test_tasks.py::test_add_task_omits_parent_by_default science/tests/test_storage_adapters/test_task.py::test_load_raw_includes_parent -q
```

Expected: parent is missing from parsed/rendered tasks and raw adapter output.

- [ ] **Step 7: Parse and render parent**

In `science/src/science_tool/tasks.py`, add a local parent validator near `_parse_task_header`:

```python
_LOCAL_PARENT_RE = re.compile(r"^task:t[0-9]{3,}$")


def _parse_parent(raw: str, *, task_id: str) -> str:
    parent = raw.strip()
    if not parent:
        return ""
    if _LOCAL_PARENT_RE.match(parent):
        return parent
    raise ValueError(f"parent for task {task_id} must be local task ref like task:t001")
```

In `_parse_task_block()`, pass the parsed parent to `Task`:

```python
        parent=_parse_parent(fields.get("parent", ""), task_id=task_id),
```

In `render_task()`, emit parent after status and before relationship lists:

```python
    if task.parent:
        lines.append(f"- parent: {task.parent}")
```

- [ ] **Step 8: Expose parent in raw task records**

In `science/src/science_tool/graph/storage_adapters/task.py`, add this key near `"related": task.related`:

```python
            "parent": task.parent,
```

- [ ] **Step 9: Run parent tests to verify they pass**

Run:

```bash
uv run --frozen pytest science-model/tests/test_tasks.py science/tests/test_tasks.py::test_parse_and_render_parent_round_trips science/tests/test_tasks.py::test_parent_must_be_local_task_ref science/tests/test_tasks.py::test_add_task_omits_parent_by_default science/tests/test_storage_adapters/test_task.py::test_load_raw_includes_parent -q
```

Expected: all selected tests pass.

- [ ] **Step 10: Commit parent support**

```bash
git add science-model/src/science_model/tasks.py science-model/tests/test_tasks.py science/src/science_tool/tasks.py science/tests/test_tasks.py science/src/science_tool/graph/storage_adapters/task.py science/tests/test_storage_adapters/test_task.py
git commit -m "feat: add local parent field to tasks"
```

## Task 3: Namespace-First Entity Reference Parser

**Files:**
- Modify: `science/src/science_tool/addressing.py`
- Modify: `science/tests/test_addressing.py`

- [ ] **Step 1: Write failing addressing tests**

Replace the existing `science/tests/test_addressing.py` contents with:

```python
import pytest

from science_tool.addressing import (
    Address,
    RefShape,
    classify_entity_ref,
    is_address,
    parse_address,
    render_uri,
)


LOCAL_KINDS = {"task", "hypothesis", "question", "meta", "topic"}
PROJECT_IDS = {"cbioportal", "multiple-myeloma", "natural-systems"}


def test_parse_artifact_address_keeps_two_part_shape() -> None:
    address = parse_address("cbioportal:topics/clonal-hematopoiesis-contamination")
    assert address == Address(project_id="cbioportal", artifact_id="topics/clonal-hematopoiesis-contamination")


def test_parse_legacy_two_part_entity_address_still_round_trips_as_artifact_address() -> None:
    address = parse_address("cbioportal:q014")
    assert address == Address(project_id="cbioportal", artifact_id="q014")


def test_render_uri_for_artifact_address() -> None:
    address = Address(project_id="multiple-myeloma", artifact_id="h003")
    assert render_uri(address) == "<cancer://multiple-myeloma/h003>"


def test_is_address_positive_for_artifacts() -> None:
    assert is_address("cbioportal:topics/clonal-hematopoiesis-contamination") is True


def test_is_address_negative() -> None:
    assert is_address("not an address") is False
    assert is_address("just-a-word") is False
    assert is_address("a:") is False
    assert is_address(":x") is False


def test_parse_invalid_address_raises() -> None:
    with pytest.raises(ValueError):
        parse_address("not an address")


def test_classifies_bare_task_shorthand_as_local_task() -> None:
    ref = classify_entity_ref("t123", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(raw="t123", shape="bare-task", kind="task", slug="t123")


def test_classifies_local_entity_ref() -> None:
    ref = classify_entity_ref("task:t123", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(raw="task:t123", shape="local-entity", kind="task", slug="t123")


def test_classifies_namespace_first_entity_ref() -> None:
    ref = classify_entity_ref("natural-systems:task:t335", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(
        raw="natural-systems:task:t335",
        shape="cross-project-entity",
        project_id="natural-systems",
        kind="task",
        slug="t335",
    )


def test_two_part_local_kind_wins_even_when_project_id_exists() -> None:
    ref = classify_entity_ref("meta:next-steps-2026-05-05", local_kinds=LOCAL_KINDS, project_ids={"meta"})
    assert ref == RefShape(
        raw="meta:next-steps-2026-05-05",
        shape="local-entity",
        kind="meta",
        slug="next-steps-2026-05-05",
    )


def test_classifies_legacy_two_part_cross_project_ref() -> None:
    ref = classify_entity_ref("cbioportal:q014", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(
        raw="cbioportal:q014",
        shape="legacy-cross-project",
        project_id="cbioportal",
        slug="q014",
    )


def test_classifies_unknown_three_part_namespace() -> None:
    ref = classify_entity_ref("unknown-project:task:t001", local_kinds=LOCAL_KINDS, project_ids=PROJECT_IDS)
    assert ref == RefShape(
        raw="unknown-project:task:t001",
        shape="unknown-namespace",
        project_id="unknown-project",
        kind="task",
        slug="t001",
    )
```

- [ ] **Step 2: Run addressing tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_addressing.py -q
```

Expected: fails because `RefShape` and `classify_entity_ref()` do not exist, and old tests still treated `cbioportal:q014` as canonical.

- [ ] **Step 3: Add entity-reference classifier**

In `science/src/science_tool/addressing.py`, keep the artifact `Address` API and add:

```python
_BARE_TASK_RE = re.compile(r"^t[0-9]{3,}$")


@dataclass(frozen=True)
class RefShape:
    raw: str
    shape: str
    project_id: str = ""
    kind: str = ""
    slug: str = ""


def classify_entity_ref(
    raw: str,
    *,
    local_kinds: set[str] | frozenset[str],
    project_ids: set[str] | frozenset[str],
) -> RefShape:
    value = raw.strip()
    if _BARE_TASK_RE.match(value):
        return RefShape(raw=value, shape="bare-task", kind="task", slug=value)

    parts = value.split(":")
    if len(parts) == 2:
        first, slug = parts
        if first in local_kinds:
            return RefShape(raw=value, shape="local-entity", kind=first, slug=slug)
        if first in project_ids:
            return RefShape(raw=value, shape="legacy-cross-project", project_id=first, slug=slug)
        return RefShape(raw=value, shape="unresolved-local-kind", kind=first, slug=slug)

    if len(parts) == 3:
        project_id, kind, slug = parts
        if project_id in project_ids:
            return RefShape(
                raw=value,
                shape="cross-project-entity",
                project_id=project_id,
                kind=kind,
                slug=slug,
            )
        return RefShape(
            raw=value,
            shape="unknown-namespace",
            project_id=project_id,
            kind=kind,
            slug=slug,
        )

    return RefShape(raw=value, shape="non-entity")
```

- [ ] **Step 4: Run addressing tests to verify they pass**

Run:

```bash
uv run --frozen pytest science/tests/test_addressing.py -q
```

Expected: all addressing tests pass.

- [ ] **Step 5: Commit reference classifier**

```bash
git add science/src/science_tool/addressing.py science/tests/test_addressing.py
git commit -m "feat: classify namespace-first entity refs"
```

## Task 4: Project-Aware Reference Validation

**Files:**
- Modify: `science/src/science_tool/refs.py`
- Modify: `science/tests/test_refs.py`

- [ ] **Step 1: Write failing reference validation tests**

Add to `science/tests/test_refs.py`:

```python
def test_namespace_first_cross_project_task_ref_is_accepted_when_child_declared() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "science.yaml").write_text(
            "name: meta\n"
            "id: meta\n"
            "role: meta\n"
            "children:\n"
            "  - id: natural-systems\n"
            f"    path: {root / 'natural-systems'}\n"
            "    role: data-source\n",
            encoding="utf-8",
        )
        (root / "doc" / "questions" / "x.md").write_text(
            "---\n"
            "id: question:x\n"
            "type: question\n"
            "related: [natural-systems:task:t335]\n"
            "---\n\n"
            "# X\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        assert [issue for issue in issues if issue.ref_value == "natural-systems:task:t335"] == []
        assert [issue for issue in issues if issue.ref_type == "task" and issue.ref_value == "t335"] == []


def test_unknown_namespace_is_reported() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "science.yaml").write_text("name: demo\nid: demo\n", encoding="utf-8")
        (root / "doc" / "questions" / "x.md").write_text(
            "---\n"
            "id: question:x\n"
            "type: question\n"
            "related: [natural-systems:task:t335]\n"
            "---\n\n"
            "# X\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        namespace_issues = [issue for issue in issues if issue.ref_type == "namespace"]
        assert len(namespace_issues) == 1
        assert namespace_issues[0].message == (
            "Unknown project namespace 'natural-systems' in ref 'natural-systems:task:t335'. "
            "Add it to science.yaml children: or use a local ref."
        )


def test_legacy_two_part_cross_project_ref_reports_suggestion() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem() as td:
        root = Path(td)
        _scaffold(root)
        (root / "science.yaml").write_text(
            "name: meta\n"
            "id: meta\n"
            "role: meta\n"
            "children:\n"
            "  - id: cbioportal\n"
            f"    path: {root / 'cbioportal'}\n"
            "    role: data-source\n",
            encoding="utf-8",
        )
        (root / "doc" / "questions" / "x.md").write_text(
            "---\n"
            "id: question:x\n"
            "type: question\n"
            "related: [cbioportal:q014]\n"
            "---\n\n"
            "# X\n",
            encoding="utf-8",
        )

        issues = check_refs(root)

        legacy = [issue for issue in issues if issue.ref_type == "legacy-cross-project"]
        assert len(legacy) == 1
        assert legacy[0].message == (
            "Legacy cross-project ref 'cbioportal:q014' is missing an entity kind. "
            "Use 'cbioportal:question:q014' or another explicit <project-id>:<kind>:<slug> ref."
        )
```

- [ ] **Step 2: Run reference tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_refs.py::test_namespace_first_cross_project_task_ref_is_accepted_when_child_declared science/tests/test_refs.py::test_unknown_namespace_is_reported science/tests/test_refs.py::test_legacy_two_part_cross_project_ref_reports_suggestion -q
```

Expected: fails because `check_refs()` does not inspect frontmatter entity refs with federation metadata.

- [ ] **Step 3: Load project IDs and frontmatter refs**

In `science/src/science_tool/refs.py`, import the new classifier and project config:

```python
from science_tool.addressing import classify_entity_ref
from science_tool.project_config import load_project_config
```

Add helpers near `_load_task_ids()`:

```python
_LOCAL_ENTITY_KINDS = frozenset(
    {
        "assumption",
        "concept",
        "data-package",
        "dataset",
        "discussion",
        "experiment",
        "finding",
        "hypothesis",
        "inquiry",
        "interpretation",
        "mechanism",
        "method",
        "model",
        "observation",
        "paper",
        "pre-registration",
        "proposition",
        "question",
        "report",
        "source",
        "story",
        "task",
        "theme",
        "topic",
        "validation-report",
        "workflow",
        "workflow-run",
        "meta",
    }
)


def _load_project_ids(root: Path) -> set[str]:
    try:
        cfg = load_project_config(root)
    except Exception:
        return set()
    ids = {child.id for child in cfg.children}
    if cfg.id:
        ids.add(cfg.id)
    return ids


def _extract_frontmatter_refs(path: Path) -> list[str]:
    parsed = parse_frontmatter(path)
    if parsed is None:
        return []
    fm, _body = parsed
    refs: list[str] = []
    for key in ("related", "blocked_by", "blocked-by", "source_refs"):
        value = fm.get(key)
        if isinstance(value, str):
            refs.append(value)
        elif isinstance(value, list):
            refs.extend(item for item in value if isinstance(item, str))
    return refs


def _frontmatter_line_numbers(path: Path) -> set[int]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return set()
    if not lines or lines[0].strip() != "---":
        return set()
    for index, line in enumerate(lines[1:], start=2):
        if line.strip() == "---":
            return set(range(1, index + 1))
    return set()
```

- [ ] **Step 4: Validate namespace-aware frontmatter refs**

In `check_refs()`, after `task_ids = _load_task_ids(root)`, add:

```python
    project_ids = _load_project_ids(root)
```

Inside the per-file loop, after reading `rel_path`, add:

```python
        frontmatter_lines = _frontmatter_line_numbers(file_path)
        for raw_ref in _extract_frontmatter_refs(file_path):
            parsed_ref = classify_entity_ref(
                raw_ref,
                local_kinds=_LOCAL_ENTITY_KINDS,
                project_ids=frozenset(project_ids),
            )
            if parsed_ref.shape == "cross-project-entity":
                continue
            if parsed_ref.shape == "unknown-namespace":
                issues.append(
                    RefIssue(
                        file=rel_path,
                        line=1,
                        ref_type="namespace",
                        ref_value=raw_ref,
                        message=(
                            f"Unknown project namespace '{parsed_ref.project_id}' in ref '{raw_ref}'. "
                            "Add it to science.yaml children: or use a local ref."
                        ),
                    )
                )
            elif parsed_ref.shape == "legacy-cross-project":
                issues.append(
                    RefIssue(
                        file=rel_path,
                        line=1,
                        ref_type="legacy-cross-project",
                        ref_value=raw_ref,
                        message=(
                            f"Legacy cross-project ref '{raw_ref}' is missing an entity kind. "
                            f"Use '{parsed_ref.project_id}:question:{parsed_ref.slug}' or another explicit "
                            "<project-id>:<kind>:<slug> ref."
                        ),
                    )
                )
```

Then, inside the existing `for line_num, line in enumerate(lines, start=1):` scanner, add this guard before task-ID, hypothesis, citation, link, and marker checks:

```python
            if line_num in frontmatter_lines:
                continue
```

- [ ] **Step 5: Run reference tests to verify they pass**

Run:

```bash
uv run --frozen pytest science/tests/test_refs.py::test_namespace_first_cross_project_task_ref_is_accepted_when_child_declared science/tests/test_refs.py::test_unknown_namespace_is_reported science/tests/test_refs.py::test_legacy_two_part_cross_project_ref_reports_suggestion -q
```

Expected: all three tests pass.

- [ ] **Step 6: Commit reference validation**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "feat: validate namespace-first refs"
```

## Task 5: Managed Validator Task And Frontmatter Checks

**Files:**
- Modify: `science/src/science_tool/project_artifacts/data/validate.sh`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml`
- Modify: `science/tests/test_validate_script.py`
- Modify: `science/tests/test_initial_validate_sh.py`

- [ ] **Step 1: Write failing validate.sh tests**

Add to `science/tests/test_validate_script.py`:

```python
def test_validate_rejects_invalid_task_id_suffix(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    _write_science_tool_stub(tmp_path / "bin")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001b] Follow-up\n"
        "- aspects: [software-development]\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- created: 2026-05-05\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 1, combined
    assert (
        "Invalid task id 't001b' in tasks/active.md: task ids must match tNNN. "
        "Use parent: task:t001 for fragments or subtasks."
    ) in combined


def test_validate_rejects_cross_project_parent(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    _write_science_tool_stub(tmp_path / "bin")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t016] Follow-up\n"
        "- aspects: [software-development]\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- parent: natural-systems:task:t001\n"
        "- created: 2026-05-05\n\n"
        "Body.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 1, combined
    assert "task t016 parent must be local task ref like task:t001" in combined


def test_validate_catches_stale_task_ref_after_migration(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    _write_science_tool_stub(tmp_path / "bin")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "tasks" / "active.md").write_text(
        "## [t001] Parent task\n"
        "- aspects: [software-development]\n"
        "- priority: P1\n"
        "- status: done\n"
        "- created: 2026-05-04\n\n"
        "Parent body.\n\n"
        "## [t016] Follow-up\n"
        "- aspects: [software-development]\n"
        "- priority: P1\n"
        "- status: proposed\n"
        "- parent: task:t001\n"
        "- related: [task:t001, task:t001b]\n"
        "- created: 2026-05-05\n\n"
        "The body can use words like task, to, and the without task-ref false positives.\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 1, combined
    assert "stale or invalid task ref 't001b' in tasks/active.md" in combined
    assert "stale or invalid task ref 'task'" not in combined
    assert "stale or invalid task ref 'to'" not in combined
    assert "stale task ref 't001'" not in combined


def test_validate_accepts_namespace_first_ref_for_declared_child(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    _write_science_tool_stub(tmp_path / "bin")
    (tmp_path / "science.yaml").write_text(
        'name: "demo"\n'
        'created: "2026-03-18"\n'
        'last_modified: "2026-03-18"\n'
        'summary: "demo"\n'
        'status: "active"\n'
        "profile: software\n"
        "layout_version: 2\n"
        "knowledge_profiles:\n"
        "  local: local\n"
        "children:\n"
        "  - id: natural-systems\n"
        f"    path: {tmp_path / 'natural-systems'}\n"
        "    role: data-source\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "doc" / "questions" / "x.md").write_text(
        "---\n"
        'id: "question:x"\n'
        'type: "question"\n'
        'related: ["natural-systems:task:t335"]\n'
        "---\n\n"
        "# X\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert "natural-systems:task:t335" not in combined


def test_validate_reports_unknown_namespace_with_raw_ref(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    _write_science_tool_stub(tmp_path / "bin")
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "doc" / "questions" / "x.md").write_text(
        "---\n"
        'id: "question:x"\n'
        'type: "question"\n'
        'related: ["natural-systems:task:t335"]\n'
        "---\n\n"
        "# X\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 1, combined
    assert (
        "Unknown project namespace 'natural-systems' in ref 'natural-systems:task:t335'. "
        "Add it to science.yaml children: or use a local ref."
    ) in combined


def test_validate_reports_legacy_two_part_cross_project_ref(tmp_path: Path) -> None:
    _write_common_files(tmp_path, "software")
    _write_python3_stub(tmp_path / "bin")
    _write_science_tool_stub(tmp_path / "bin")
    (tmp_path / "science.yaml").write_text(
        'name: "demo"\n'
        'created: "2026-03-18"\n'
        'last_modified: "2026-03-18"\n'
        'summary: "demo"\n'
        'status: "active"\n'
        "profile: software\n"
        "layout_version: 2\n"
        "knowledge_profiles:\n"
        "  local: local\n"
        "children:\n"
        "  - id: cbioportal\n"
        f"    path: {tmp_path / 'cbioportal'}\n"
        "    role: data-source\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Demo\n", encoding="utf-8")
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "tests").mkdir(parents=True)
    (tmp_path / "doc" / "questions" / "x.md").write_text(
        "---\n"
        'id: "question:x"\n'
        'type: "question"\n'
        'related: ["cbioportal:q014"]\n'
        "---\n\n"
        "# X\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(_validate_script_path())],
        cwd=tmp_path,
        env=_validate_env(extra_path=tmp_path / "bin"),
        capture_output=True,
        text=True,
        check=False,
    )

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined
    assert (
        "Legacy cross-project ref 'cbioportal:q014' is missing an entity kind. "
        "Use 'cbioportal:question:q014' or another explicit <project-id>:<kind>:<slug> ref."
    ) in combined
```

- [ ] **Step 2: Run validate tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_validate_script.py::test_validate_rejects_invalid_task_id_suffix science/tests/test_validate_script.py::test_validate_rejects_cross_project_parent science/tests/test_validate_script.py::test_validate_catches_stale_task_ref_after_migration science/tests/test_validate_script.py::test_validate_accepts_namespace_first_ref_for_declared_child science/tests/test_validate_script.py::test_validate_reports_unknown_namespace_with_raw_ref science/tests/test_validate_script.py::test_validate_reports_legacy_two_part_cross_project_ref -q
```

Expected: fails because Section 15 still partially parses invalid task headers and Section 16 treats namespace-first refs as broken local refs.

- [ ] **Step 3: Replace validate.sh Section 15 task queue logic**

In `science/src/science_tool/project_artifacts/data/validate.sh`, replace the body under `if [ ! -f "$TASKS_DIR/active.md" ]; then ... else ... fi` in Section 15 with a Python-backed check:

```bash
    task_check_result=$(XREF_TASKS="$TASKS_DIR" python3 <<'PYEOF'
import os
import re
from pathlib import Path

tasks_dir = Path(os.environ["XREF_TASKS"])
header_any = re.compile(r"^##\s+\[([^\]]+)\]\s+(.+)$")
header_valid = re.compile(r"^##\s+\[(t[0-9]{3,})\]\s+(.+)$")
task_ref = re.compile(r"\bt\d+[A-Za-z.]*\b")
local_parent = re.compile(r"^task:t[0-9]{3,}$")
required = ("aspects", "priority", "status", "created")
ref_fields = {"related", "blocked-by", "blocked_by", "parent"}


def display_path(path):
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return path.as_posix()


def split_list_value(raw):
    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        return [item.strip() for item in value[1:-1].split(",") if item.strip()]
    return [value] if value else []

paths = [tasks_dir / "active.md"]
done_dir = tasks_dir / "done"
if done_dir.is_dir():
    paths.extend(sorted(done_dir.glob("*.md")))

declared = set()
blocks = []
for path in paths:
    if not path.is_file():
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    current = None
    for line_no, line in enumerate(lines, start=1):
        any_match = header_any.match(line)
        if any_match:
            task_id = any_match.group(1)
            valid_match = header_valid.match(line)
            if valid_match is None:
                print(
                    f"ERROR:Invalid task id '{task_id}' in {display_path(path)}: task ids must match tNNN. "
                    "Use parent: task:t001 for fragments or subtasks."
                )
                current = None
                continue
            current = {"path": display_path(path), "line": line_no, "id": task_id, "lines": []}
            blocks.append(current)
            declared.add(task_id)
            continue
        if current is not None:
            current["lines"].append(line)

seen = {}
for task_id in sorted(declared):
    count = sum(1 for block in blocks if block["id"] == task_id)
    if count > 1:
        seen[task_id] = count
for task_id in sorted(seen):
    print(f"ERROR:duplicate task IDs in active.md: {task_id}")

for block in blocks:
    fields = {}
    for line in block["lines"]:
        match = re.match(r"^-\s+([\w-]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    for field in required:
        if field not in fields:
            print(f"ERROR:task {block['id']} missing required field: {field}")
    parent = fields.get("parent", "")
    if parent and not local_parent.match(parent):
        print(f"ERROR:task {block['id']} parent must be local task ref like task:t001")
    refs_to_check = []
    for field_name in ref_fields:
        for value in split_list_value(fields.get(field_name, "")):
            refs_to_check.append(value)
    for raw_ref in refs_to_check:
        if raw_ref.count(":") == 2:
            continue
        for match in task_ref.finditer(raw_ref):
            raw = match.group(0)
            if raw in declared:
                continue
            if re.fullmatch(r"t[0-9]{3,}", raw):
                print(f"ERROR:stale task ref '{raw}' in {block['path']}")
            elif raw.startswith("t"):
                print(f"ERROR:stale or invalid task ref '{raw}' in {block['path']}")

if blocks:
    print(f"OK:{len(blocks)}")
else:
    print("EMPTY:0")
PYEOF
2>/dev/null || echo "SKIP")

    if [ "$task_check_result" = "SKIP" ]; then
        warn "Task queue check skipped (python3 error)"
    else
        task_count=0
        while IFS=: read -r status detail; do
            case "$status" in
                ERROR)
                    error "$detail"
                    ;;
                OK)
                    task_count="$detail"
                    ;;
                EMPTY)
                    task_count=0
                    ;;
            esac
        done <<< "$task_check_result"
        if [ "$task_count" = "0" ]; then
            info "  no tasks in active.md"
        else
            info "  ${task_count} task(s) validated"
        fi
    fi
```

- [ ] **Step 4: Extend Section 16 frontmatter xref Python**

Inside the Section 16 Python block, add `XREF_SCIENCE_YAML="science.yaml"` to the shell environment:

```bash
xref_result=$(XREF_SPECS="$SPECS_DIR" XREF_DOC="$DOC_DIR" XREF_TASKS="$TASKS_DIR" XREF_ENTITIES="$LOCAL_PROFILE_DIR/entities.yaml" XREF_SCIENCE_YAML="science.yaml" python3 << 'PYEOF'
```

Inside the Python block, add:

```python
LOCAL_KINDS = {
    "assumption", "concept", "data-package", "dataset", "discussion", "experiment",
    "finding", "hypothesis", "inquiry", "interpretation", "mechanism", "method",
    "model", "observation", "paper", "pre-registration", "proposition", "question",
    "report", "source", "story", "task", "theme", "topic", "validation-report",
    "workflow", "workflow-run", "meta",
}


def load_project_ids(path):
    if yaml is None or not os.path.isfile(path):
        return set()
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return set()
    ids = set()
    project_id = data.get("id")
    if isinstance(project_id, str) and project_id:
        ids.add(project_id)
    children = data.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict) and isinstance(child.get("id"), str):
                ids.add(child["id"])
    return ids


def classify_ref(ref, project_ids):
    parts = ref.split(":")
    if re.fullmatch(r"t[0-9]{3,}", ref):
        return "local"
    if len(parts) == 2:
        first, _slug = parts
        if first in LOCAL_KINDS:
            return "local"
        if first in project_ids:
            return "legacy"
        return "local"
    if len(parts) == 3:
        project_id, _kind, _slug = parts
        if project_id in project_ids:
            return "cross"
        return "unknown-namespace"
    return "local"
```

After `all_ids.update(load_structured_ids(...))`, add:

```python
project_ids = load_project_ids(os.environ["XREF_SCIENCE_YAML"])
```

Replace the broken-ref loop with:

```python
def emit(*parts):
    print("\t".join(str(part) for part in parts))


broken = 0
for path, refs in refs_by_file.items():
    for ref in refs:
        shape = classify_ref(ref, project_ids)
        if shape == "cross":
            continue
        if shape == "unknown-namespace":
            project_id = ref.split(":", 1)[0]
            emit("UNKNOWN_NAMESPACE", os.path.basename(path), project_id, "", ref)
            broken += 1
            continue
        if shape == "legacy":
            project_id, slug = ref.split(":", 1)
            emit("LEGACY_PROJECT_REF", os.path.basename(path), project_id, slug, ref)
            continue
        if ref not in all_ids:
            emit("BROKEN", os.path.basename(path), ref)
            broken += 1
if broken == 0:
    print('OK')
```

Update the shell reader to handle the new statuses:

```bash
        if [ "$status" = "BROKEN" ]; then
            ref="$project_id"
            warn "Broken reference in $filename: related ID '$ref' not found"
        elif [ "$status" = "UNKNOWN_NAMESPACE" ]; then
            error "Unknown project namespace '${project_id}' in ref '${raw}'. Add it to science.yaml children: or use a local ref."
        elif [ "$status" = "LEGACY_PROJECT_REF" ]; then
            warn "Legacy cross-project ref '${raw}' is missing an entity kind. Use '${project_id}:question:${slug}' or another explicit <project-id>:<kind>:<slug> ref."
        fi
```

Use shell variable names that match the final `read` command:

```bash
    while IFS=$'\t' read -r status filename project_id slug raw; do
```

- [ ] **Step 5: Recompute managed-artifact hash and update registry**

Run:

```bash
uv run --frozen pytest science/tests/test_initial_validate_sh.py::test_current_hash_matches_body -q
```

Expected: fails with the new computed body hash in the assertion output.

Copy that expected hash into `science/src/science_tool/project_artifacts/registry.yaml`, set `version: '2026.05.05.1'`, move the previous current hash into `previous_hashes`, and add:

```yaml
      - from: '2026.05.03.3'
        to: '2026.05.05.1'
        kind: byte_replace
        summary: 'Strict task IDs, local task parent validation, and namespace-first cross-project reference checks.'
        steps: []
```

Add to `changelog`:

```yaml
      '2026.05.05.1': 'Strict task IDs, local task parent validation, and namespace-first cross-project reference checks.'
```

- [ ] **Step 6: Run validate tests to verify they pass**

Run:

```bash
uv run --frozen pytest science/tests/test_validate_script.py::test_validate_rejects_invalid_task_id_suffix science/tests/test_validate_script.py::test_validate_rejects_cross_project_parent science/tests/test_validate_script.py::test_validate_catches_stale_task_ref_after_migration science/tests/test_validate_script.py::test_validate_accepts_namespace_first_ref_for_declared_child science/tests/test_validate_script.py::test_validate_reports_unknown_namespace_with_raw_ref science/tests/test_validate_script.py::test_validate_reports_legacy_two_part_cross_project_ref science/tests/test_initial_validate_sh.py::test_current_hash_matches_body -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit managed validator changes**

```bash
git add science/src/science_tool/project_artifacts/data/validate.sh science/src/science_tool/project_artifacts/registry.yaml science/tests/test_validate_script.py science/tests/test_initial_validate_sh.py
git commit -m "feat: validate flat task ids and namespaced refs"
```

## Task 6: Documentation Updates

**Files:**
- Modify: `commands/tasks.md`
- Modify: `docs/federation.md`
- Modify: `science/tests/test_command_docs.py`

- [ ] **Step 1: Write failing documentation tests**

Add to `science/tests/test_command_docs.py`:

```python
def test_tasks_command_documents_flat_ids_parent_and_namespace_refs() -> None:
    text = _read("commands/tasks.md")

    expected_strings = (
        "Task IDs are flat local identifiers in the form `tNNN`",
        "`parent: task:t001`",
        "`natural-systems:task:t335`",
        "Bare `t123` always means a local task",
    )
    for expected in expected_strings:
        assert expected in text


def test_federation_docs_document_canonical_entity_refs_and_artifact_addresses() -> None:
    text = _read("docs/federation.md")

    expected_strings = (
        "<project-id>:<kind>:<slug>",
        "`cbioportal:question:q014`",
        "`multiple-myeloma:hypothesis:h003`",
        "`cbioportal:topics/clonal-hematopoiesis-contamination` is an artifact address",
        "Two-part entity shorthand such as",
        "`cbioportal:q014`",
        "is legacy and non-canonical",
    )
    for expected in expected_strings:
        assert expected in text
```

- [ ] **Step 2: Run documentation tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_command_docs.py::test_tasks_command_documents_flat_ids_parent_and_namespace_refs science/tests/test_command_docs.py::test_federation_docs_document_canonical_entity_refs_and_artifact_addresses -q
```

Expected: fails because current docs still describe the old addressing convention and do not document `parent:`.

- [ ] **Step 3: Update tasks command docs**

In `commands/tasks.md`, add this section after `## Setup`:

```markdown
## Task IDs And References

Task IDs are flat local identifiers in the form `tNNN`: `t001`, `t016`, `t335`, `t1000`. Do not encode hierarchy, revisions, or follow-up fragments in the ID. Use `parent: task:t001` for a local structural parent, and include the parent in `related` when it should remain visible in graph/search surfaces.

Bare `t123` always means a local task. `task:t123` is the canonical local task reference. Cross-project task and entity refs use namespace-first form: `natural-systems:task:t335`, `multiple-myeloma:hypothesis:h01`, `cbioportal:question:q006-ch-priority-gene-completeness`.
```

In the `"add <description>"` action, update the related entity bullet to:

```markdown
- **Related entities:** (optional) typed refs for hypotheses, themes, methods, questions, tasks, etc. Local refs use `<kind>:<slug>` such as `hypothesis:h01` or `task:t016`; cross-project refs use `<project-id>:<kind>:<slug>` such as `natural-systems:task:t335`.
```

- [ ] **Step 4: Update federation addressing docs**

Replace the current `## Addressing` section in `docs/federation.md` with:

````markdown
## Addressing

Canonical cross-project entity references use namespace-first form:

```text
<project-id>:<kind>:<slug>
```

Examples:

- `cbioportal:question:q014`
- `multiple-myeloma:hypothesis:h003`
- `evolution:task:t012`
- `cbioportal:topic:clonal-hematopoiesis-contamination`

The first segment is a federation project ID from the meta project's `children:` manifest or the current project's own `id`. The remaining segments are the target project's normal local entity reference.

Local refs stay local by default:

- `task:t123`
- `hypothesis:h01`
- `question:q006`

Bare task shorthand such as `t123` always means a local task. It never names another project.

Artifact addresses remain two-part or path-style addresses when the target is a file-like artifact rather than a canonical entity. For example, `cbioportal:topics/clonal-hematopoiesis-contamination` is an artifact address, while the canonical topic entity ref is `cbioportal:topic:clonal-hematopoiesis-contamination`.

Two-part entity shorthand such as `cbioportal:q014`, `multiple-myeloma:h003`, or `evolution:t012` is legacy and non-canonical. Migrate those references to explicit entity form, such as `cbioportal:question:q014`, `multiple-myeloma:hypothesis:h003`, or `evolution:task:t012`.

Graph URI form for artifact addresses remains:

```text
<cancer://project-id/artifact-id>
```
````

- [ ] **Step 5: Run documentation tests to verify they pass**

Run:

```bash
uv run --frozen pytest science/tests/test_command_docs.py::test_tasks_command_documents_flat_ids_parent_and_namespace_refs science/tests/test_command_docs.py::test_federation_docs_document_canonical_entity_refs_and_artifact_addresses -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit documentation changes**

```bash
git add commands/tasks.md docs/federation.md science/tests/test_command_docs.py
git commit -m "docs: define flat task ids and namespace refs"
```

## Task 7: Meta Task Queue Migration

**Files:**
- Modify: `meta/tasks/active.md`

Execute this migration before Task 1 Step 7. The strict parser and the meta queue migration should land in the same commit so the repository never contains strict task parsing while `meta/tasks/active.md` still has `[t001b]`.

- [ ] **Step 1: Inspect current highest task ID**

Run:

```bash
rg -n "^## \\[t[0-9A-Za-z.]+\\]" meta/tasks/active.md
```

Expected: current queue includes `[t001b]` and highest flat numeric ID is `[t015]`, so the migration target is `[t016]`.

- [ ] **Step 2: Migrate t001b to t016**

In `meta/tasks/active.md`, change this header:

```markdown
## [t001b] H01 engine follow-ups (grid, metrics, parallelism)
```

to:

```markdown
## [t016] H01 engine follow-ups (grid, metrics, parallelism)
```

In that same task block, replace:

```markdown
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t001]
```

with:

```markdown
- parent: task:t001
- related: [hypothesis:h01-stochastic-revisiting, task:t001]
- blocked_by: [t001]
```

Then replace the later task `[t002]` blocker metadata:

```markdown
- blocked_by: [t001b]
```

with:

```markdown
- blocked_by: [t016]
```

- [ ] **Step 3: Confirm no stale suffix references remain**

Run:

```bash
rg -n "t001b|\\[t001b\\]" meta
```

Expected: no output.

- [ ] **Step 4: Include migration in the strict-parser commit**

```bash
git add meta/tasks/active.md
```

Expected: `meta/tasks/active.md` is staged together with Task 1's parser and parser-test changes before `git commit -m "fix: validate flat task ids strictly"`.

## Task 8: Full Verification

**Files:**
- Verify: `science-model/src/science_model/tasks.py`
- Verify: `science/src/science_tool/tasks.py`
- Verify: `science/src/science_tool/addressing.py`
- Verify: `science/src/science_tool/refs.py`
- Verify: `science/src/science_tool/project_artifacts/data/validate.sh`
- Verify: `commands/tasks.md`
- Verify: `docs/federation.md`
- Verify: `meta/tasks/active.md`

- [ ] **Step 1: Run focused test suite**

Run:

```bash
uv run --frozen pytest science-model/tests/test_tasks.py science/tests/test_tasks.py science/tests/test_storage_adapters/test_task.py science/tests/test_addressing.py science/tests/test_refs.py science/tests/test_validate_script.py science/tests/test_initial_validate_sh.py science/tests/test_command_docs.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run ruff**

Run:

```bash
uv run --frozen ruff check science-model/src science-model/tests science/src science/tests
```

Expected: `All checks passed!`

- [ ] **Step 3: Run pyright**

Run:

```bash
uv run --frozen pyright science-model/src science/src
```

Expected: no type errors.

- [ ] **Step 4: Validate meta project**

Run from the repo root:

```bash
cd meta && bash validate.sh --verbose
```

Expected: validation exits 0. It must not report duplicate `t001`, invalid `t001b`, stale `t001b`, or a cross-project `parent:`.

- [ ] **Step 5: Verify task creation still emits no parent by default**

Run:

```bash
uv run --frozen pytest science/tests/test_tasks.py::test_add_task_omits_parent_by_default -q
```

Expected: the pytest tmp project creates `tasks/active.md`, emits a flat task ID, and writes no `parent:` line. Do not verify this by running `science tasks add` in the user's repo root.

- [ ] **Step 6: Commit verification fixes**

If verification required edits, commit them:

```bash
git add science-model science commands docs meta/tasks/active.md
git commit -m "test: verify task ids and cross-project refs"
```

If no edits were required, do not create an empty commit.

## Self-Review

- Spec coverage: Task 1 covers flat strict IDs, malformed suffix rejection, and `next_task_id()` partial-parse prevention. Task 2 covers explicit `parent:` parse/render/model/storage support and local-only parent validation. Tasks 3-5 cover local refs, bare local task shorthand, namespace-first cross-project refs, unknown namespaces, legacy two-part project shorthand, and validate.sh behavior. Task 6 covers `commands/tasks.md` and `docs/federation.md`. Task 7 covers the `meta/tasks/active.md` migration from `t001b` to `t016`. Task 8 covers acceptance criteria and quality gates.
- Placeholder scan: The plan contains no intentionally deferred implementation step. Every code-changing step names the file, the code to add or replace, the command to run, and the expected result.
- Type consistency: The plan consistently uses `Task.parent`, `TaskCreate.parent`, `TaskUpdate.parent`, `RefShape`, `classify_entity_ref()`, `project_id`, `kind`, and `slug` across tests and implementation.
