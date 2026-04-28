# Tags → Related Unification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the `tags` field from entities and tasks, unifying all entity-to-entity connections through the `related` field — so "tagging" is just adding edges to the knowledge graph.

**Architecture:** Remove `tags` from data models (Entity, SourceEntity, Task, Filters). During frontmatter parsing, merge any legacy `tags` entries into `related` as `topic:<tag>` references for backward compatibility. Update CLI commands, display code, and templates to use `related` exclusively. Project-level tags (`science.yaml`) are out of scope — they describe the project itself, not entity relationships.

**Tech Stack:** Python, Pydantic, Click, Rich, rdflib, pytest

---

## File Structure

| File | Change | Responsibility |
|------|--------|---------------|
| `science-model/src/science_model/entities.py` | Modify | Remove `tags` from Entity and EntityUpdate |
| `science-model/src/science_model/search.py` | Modify | Remove `tags` from Filters |
| `science-model/src/science_model/frontmatter.py` | Modify | Merge legacy `tags` → `related` during parse |
| `science-model/src/science_model/tasks.py` | Modify | Remove `tags` from Task, TaskCreate, TaskUpdate |
| `science-tool/src/science_tool/graph/sources.py` | Modify | Remove `tags` from SourceEntity |
| `science-tool/src/science_tool/tasks.py` | Modify | Remove tags from parser, renderer, CRUD, filter |
| `science-tool/src/science_tool/tasks_display.py` | Modify | Remove tags column, add related column |
| `science-tool/src/science_tool/cli.py` | Modify | Remove `--tag`/`--tags` options, widen question `--related` |
| `science-tool/src/science_tool/graph/store.py` | Modify | Widen `add_question()` to accept generic `--related` |
| `templates/*.md` | Modify | Remove `tags:` field from all entity templates |
| `commands/review-tasks.md` | Modify | Replace tag/group references with related |
| `science-model/tests/test_entities.py` | Modify | Remove `tags` from test fixtures |
| `science-model/tests/test_frontmatter.py` | Modify | Test legacy tags merge, remove tags assertions |
| `science-tool/tests/test_tasks.py` | Modify | Remove tags tests, update fixtures |
| `science-tool/tests/test_tasks_cli.py` | Modify | Remove --tag CLI tests |
| `science-tool/tests/test_graph_materialize.py` | Modify | Remove `tags:` from test fixtures |
| `science-tool/tests/test_graph_cli.py` | Modify | Update question CLI tests, remove tags from fixtures |

---

### Task 1: Remove `tags` from Entity and EntityUpdate models

**Files:**
- Modify: `science-model/src/science_model/entities.py:47-51` (EntityUpdate)
- Modify: `science-model/src/science_model/entities.py:54-88` (Entity)
- Modify: `science-model/src/science_model/search.py:10-17` (Filters)
- Test: `science-model/tests/test_entities.py`

- [ ] **Step 1: Write failing test — Entity without tags field**

In `science-model/tests/test_entities.py`, update all Entity constructors to remove the `tags` parameter. Verify the model no longer accepts `tags`.

```python
def test_entity_has_no_tags_field():
    """After unification, Entity should not have a tags field."""
    e = Entity(
        id="hypothesis:h01-foo",
        type=EntityType.HYPOTHESIS,
        title="Test hypothesis",
        status="proposed",
        project="my-project",
        ontology_terms=["GO:0006915"],
        created=date(2026, 3, 1),
        updated=date(2026, 3, 10),
        related=["question:q01"],
        source_refs=[],
        content_preview="A test hypothesis about...",
        file_path="specs/hypotheses/h01-foo.md",
    )
    assert not hasattr(e, "tags")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pytest tests/test_entities.py::test_entity_has_no_tags_field -v`
Expected: FAIL — `tags` is still a required field and the assertion fails.

- [ ] **Step 3: Remove `tags` from Entity, EntityUpdate, and Filters**

In `science-model/src/science_model/entities.py`, remove line 51 (`tags: list[str] | None = None`) from `EntityUpdate` and line 65 (`tags: list[str]`) from `Entity`.

In `science-model/src/science_model/search.py`, remove line 17 (`tags: list[str] | None = None`) from `Filters`.

```python
# entities.py — EntityUpdate (lines 47-52)
class EntityUpdate(BaseModel):
    """Partial update for entity metadata (written back to frontmatter)."""

    status: str | None = None
    related: list[str] | None = None


# entities.py — Entity (lines 54-88): remove line 65 entirely
# The field `tags: list[str]` is deleted. No replacement needed.


# search.py — Filters (lines 10-17)
class Filters(BaseModel):
    """Query filters for entity listing."""

    project: str | None = None
    entity_type: str | None = None
    status: str | None = None
    domain: str | None = None
    related: str | None = None
```

- [ ] **Step 4: Fix all test fixtures that pass `tags=` to Entity**

Update every Entity constructor in `test_entities.py` to remove the `tags` parameter. There are instances at approximately lines 12, 35, 72, 122, 141. Remove `tags=["genomics"]`, `tags=[]`, `tags=["feature-eval"]`, etc.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pytest tests/test_entities.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add science-model/src/science_model/entities.py science-model/src/science_model/search.py science-model/tests/test_entities.py
git commit -m "refactor: remove tags field from Entity, EntityUpdate, and Filters"
```

---

### Task 2: Merge legacy `tags` into `related` during frontmatter parsing

**Files:**
- Modify: `science-model/src/science_model/frontmatter.py:92-135`
- Test: `science-model/tests/test_frontmatter.py`

- [ ] **Step 1: Write failing test — tags in frontmatter merge into related**

```python
def test_legacy_tags_merged_into_related(tmp_path: Path) -> None:
    """Frontmatter with tags: [genomics, ml] should merge them into related as topic: refs."""
    md = tmp_path / "h01.md"
    md.write_text(
        '---\nid: "hypothesis:h01-test"\ntype: hypothesis\ntitle: "Test"\n'
        'status: proposed\ntags: [genomics, ml]\nrelated: ["question:q01"]\n'
        "source_refs: []\ncreated: 2026-03-01\nupdated: 2026-03-10\n---\nBody.\n"
    )
    entity = parse_entity_file(md, "test-project")
    assert entity is not None
    assert "topic:genomics" in entity.related
    assert "topic:ml" in entity.related
    assert "question:q01" in entity.related


def test_legacy_tags_no_duplicates(tmp_path: Path) -> None:
    """If a tag already appears in related, don't duplicate it."""
    md = tmp_path / "h01.md"
    md.write_text(
        '---\nid: "hypothesis:h01-test"\ntype: hypothesis\ntitle: "Test"\n'
        'status: proposed\ntags: [genomics]\nrelated: ["topic:genomics"]\n'
        "source_refs: []\ncreated: 2026-03-01\n---\nBody.\n"
    )
    entity = parse_entity_file(md, "test-project")
    assert entity is not None
    assert entity.related.count("topic:genomics") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pytest tests/test_frontmatter.py::test_legacy_tags_merged_into_related tests/test_frontmatter.py::test_legacy_tags_no_duplicates -v`
Expected: FAIL — Entity no longer has `tags` field (from Task 1), and the merge logic doesn't exist yet.

- [ ] **Step 3: Implement legacy tags merge in `parse_entity_file`**

In `science-model/src/science_model/frontmatter.py`, modify `parse_entity_file` (lines 92-135). Remove `tags=fm.get("tags") or []` from the Entity constructor. Add merge logic before the return statement:

```python
def parse_entity_file(path: Path, project_slug: str) -> Entity | None:
    """Parse a markdown file into an Entity. Returns None on parse failure."""
    result = parse_frontmatter(path)
    if result is None:
        return None

    fm, body = result
    if not fm.get("type"):
        entity_id = fm.get("id", "")
        inferred = _infer_type_from_id(entity_id) if entity_id else None
        if inferred:
            fm["type"] = inferred
        else:
            return None

    rel_path = str(path)
    for parent in path.parents:
        if (parent / "science.yaml").exists():
            rel_path = str(path.relative_to(parent))
            break

    # Merge legacy tags into related as topic: references
    related = fm.get("related") or []
    legacy_tags = fm.get("tags") or []
    for tag in legacy_tags:
        tag_ref = f"topic:{tag}" if ":" not in str(tag) else str(tag)
        if tag_ref not in related:
            related.append(tag_ref)

    return Entity(
        id=fm.get("id", f"{fm['type']}:{path.stem}"),
        type=_resolve_type(fm["type"]),
        title=fm.get("title", path.stem),
        status=fm.get("status"),
        project=project_slug,
        domain=None,
        ontology_terms=fm.get("ontology_terms") or [],
        created=_coerce_date(fm.get("created")),
        updated=_coerce_date(fm.get("updated")),
        related=related,
        source_refs=fm.get("source_refs") or [],
        content_preview=body[:200] if body else "",
        content=body or "",
        file_path=rel_path,
        maturity=fm.get("maturity"),
        confidence=_coerce_confidence(fm.get("confidence")),
        datasets=fm.get("datasets"),
        sync_source=_parse_sync_source(fm.get("sync_source")),
    )
```

- [ ] **Step 4: Update existing frontmatter tests**

In `test_frontmatter.py`, update:
- `test_parse_entity_file` (line ~28): change `assert fm["tags"] == ["genomics", "ml"]` to verify tags are not in the parsed entity but are merged into related.
- Remove any assertions on `entity.tags` and replace with assertions on `entity.related`.
- Update the test fixture YAML to reflect the expected behavior.

```python
def test_parse_entity_file(tmp_path: Path) -> None:
    md = tmp_path / "h01-test.md"
    md.write_text(SAMPLE_MD)
    entity = parse_entity_file(md, "test-project")
    assert entity is not None
    assert entity.id == "hypothesis:h01-test"
    assert entity.type == EntityType.HYPOTHESIS
    # Legacy tags merged into related
    assert "topic:genomics" in entity.related
    assert "topic:ml" in entity.related
    assert "question:q01" in entity.related
```

- [ ] **Step 5: Run all frontmatter tests**

Run: `cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pytest tests/test_frontmatter.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add science-model/src/science_model/frontmatter.py science-model/tests/test_frontmatter.py
git commit -m "feat: merge legacy frontmatter tags into related as topic: references"
```

---

### Task 3: Remove `tags` from Task data models

**Files:**
- Modify: `science-model/src/science_model/tasks.py:22-66`
- Test: `science-tool/tests/test_tasks.py`

- [ ] **Step 1: Write failing test — Task without tags**

```python
def test_task_has_no_tags_field():
    """After unification, Task should not have a tags field."""
    t = Task(
        id="t001",
        title="Test",
        type="dev",
        priority="P1",
        status="proposed",
        created=date(2026, 4, 1),
    )
    assert not hasattr(t, "tags")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_tasks.py::test_task_has_no_tags_field -v`
Expected: FAIL — Task still has `tags`.

- [ ] **Step 3: Remove `tags` from Task, TaskCreate, TaskUpdate**

In `science-model/src/science_model/tasks.py`:
- Remove line 34: `tags: list[str] = []` from `Task`
- Remove line 50: `tags: list[str] = []` from `TaskCreate`
- Remove line 65: `tags: list[str] | None = None` from `TaskUpdate`

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_tasks.py::test_task_has_no_tags_field -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science-model/src/science_model/tasks.py
git commit -m "refactor: remove tags field from Task, TaskCreate, TaskUpdate"
```

---

### Task 4: Remove `tags` from SourceEntity

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py:59-76`
- Modify: `science-tool/src/science_tool/graph/sources.py:242-260`
- Test: `science-tool/tests/test_graph_materialize.py`

- [ ] **Step 1: Write failing test — SourceEntity without tags**

```python
def test_source_entity_has_no_tags_field():
    """After unification, SourceEntity should not have a tags field."""
    from science_tool.graph.sources import SourceEntity

    se = SourceEntity(
        canonical_id="hypothesis:h01-demo",
        kind="hypothesis",
        title="Demo",
        profile="core",
        source_path="doc/hypotheses/h01-demo.md",
    )
    assert not hasattr(se, "tags")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_graph_materialize.py::test_source_entity_has_no_tags_field -v`
Expected: FAIL

- [ ] **Step 3: Remove `tags` from SourceEntity and markdown loading**

In `science-tool/src/science_tool/graph/sources.py`:
- Remove line 76: `tags: list[str] = Field(default_factory=list)` from `SourceEntity`
- Remove line 259: `tags=[str(t) for t in (entity.tags or [])],` from the markdown entity collection

- [ ] **Step 4: Update test fixtures**

In `science-tool/tests/test_graph_materialize.py`, remove all `"tags: [demo]"` lines from test fixture markdown strings (approximately lines 64, 87, 112). These frontmatter files will still parse correctly — the legacy tags merge from Task 2 handles them.

- [ ] **Step 5: Run materialize tests**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_graph_materialize.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/graph/sources.py science-tool/tests/test_graph_materialize.py
git commit -m "refactor: remove tags field from SourceEntity"
```

---

### Task 5: Remove tags from task parser, renderer, and CRUD

**Files:**
- Modify: `science-tool/src/science_tool/tasks.py:33-34,74,119-121,184,199,304,319-320,349,372-373`
- Test: `science-tool/tests/test_tasks.py`

- [ ] **Step 1: Write failing test — task roundtrip without tags**

```python
def test_render_and_parse_task_without_tags(tmp_path: Path) -> None:
    """Tasks should render and parse without any tags field."""
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    t = add_task(tasks_dir, "Test task", "dev", "P1", related=["topic:umap"])
    assert "- tags:" not in render_task(t)
    tasks = parse_tasks(tasks_dir / "active.md")
    assert tasks[0].related == ["topic:umap"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_tasks.py::test_render_and_parse_task_without_tags -v`
Expected: FAIL — `add_task` still expects `tags` parameter.

- [ ] **Step 3: Remove tags from task parser, renderer, and CRUD functions**

In `science-tool/src/science_tool/tasks.py`:

**Parser** (`_parse_task_block`, line 64-77): Remove line 74 (`tags=_parse_list_value(fields.get("tags", "")),`). Add legacy tags→related merge:
```python
    related = _parse_list_value(fields.get("related", ""))
    # Merge legacy tags into related as topic: references
    for tag in _parse_list_value(fields.get("tags", "")):
        tag_ref = f"topic:{tag}" if ":" not in tag else tag
        if tag_ref not in related:
            related.append(tag_ref)

    return Task(
        id=task_id,
        title=title,
        type=fields.get("type", ""),
        priority=fields.get("priority", ""),
        status=fields.get("status", ""),
        created=created,
        description=description,
        related=related,
        blocked_by=_parse_list_value(fields.get("blocked-by", "")),
        group=fields.get("group", ""),
        completed=completed,
    )
```

**Renderer** (`render_task`, lines 106-129): Remove lines 119-121 (the `if task.tags:` block).

**`add_task`** (lines 177-206): Remove `tags` parameter (line 184) and `tags=tags or []` (line 199).

**`edit_task`** (lines 297-325): Remove `tags` parameter (line 304) and the `if tags is not None:` block (lines 319-320).

**`list_tasks`** (lines 343-377): Remove `tag` parameter (line 349) and the `if tag is not None:` filter (lines 372-373).

- [ ] **Step 4: Update the `TestTagsAndGroups` test class**

In `science-tool/tests/test_tasks.py`, update the `TestTagsAndGroups` class:
- Remove or rewrite `test_parse_tags_and_group`: test that legacy `- tags: [lens-system, umap]` in markdown is merged into `related` as `["topic:lens-system", "topic:umap"]`.
- Remove `test_add_with_tags_and_group`: tags parameter no longer exists.
- Remove `test_edit_tags`: tags parameter no longer exists.
- Remove `test_list_by_tag`: tag filter no longer exists.
- Keep `test_empty_tags_not_rendered`: update to verify no `- tags:` line in output.
- Update `TAGGED_TASK` fixture: keep the `- tags:` line to test legacy merge, but assert on `related` output.

```python
class TestTagsAndGroups:
    def test_legacy_tags_merged_into_related(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "active.md", TAGGED_TASK)
        tasks = parse_tasks(f)
        assert len(tasks) == 1
        t = tasks[0]
        assert "topic:lens-system" in t.related
        assert "topic:umap" in t.related
        assert t.group == "visualization"

    def test_roundtrip_without_tags(self, tmp_path: Path) -> None:
        f = _write(tmp_path / "active.md", TAGGED_TASK)
        tasks1 = parse_tasks(f)
        rendered = render_tasks(tasks1)
        assert "- tags:" not in rendered
        # Related should contain the merged topic refs
        f2 = _write(tmp_path / "roundtrip.md", rendered)
        tasks2 = parse_tasks(f2)
        assert "topic:lens-system" in tasks2[0].related
        assert tasks1[0].group == tasks2[0].group

    def test_empty_tags_not_rendered(self) -> None:
        t = Task(
            id="t001",
            title="Plain task",
            type="dev",
            priority="P2",
            status="proposed",
            created=date(2026, 4, 1),
            description="Desc.",
        )
        rendered = render_task(t)
        assert "- tags:" not in rendered
        assert "- group:" not in rendered

    def test_list_by_related(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        add_task(tasks_dir, "T1", "dev", "P1", related=["topic:alpha", "topic:beta"])
        add_task(tasks_dir, "T2", "dev", "P2", related=["topic:beta", "topic:gamma"])
        add_task(tasks_dir, "T3", "dev", "P1", related=["topic:alpha"])
        result = list_tasks(tasks_dir, related="topic:alpha")
        assert len(result) == 2
        assert {t.id for t in result} == {"t001", "t003"}

    def test_edit_group(self, tmp_path: Path) -> None:
        tasks_dir = _make_tasks_dir(tmp_path)
        t = edit_task(tasks_dir, "t001", group="new-group")
        assert t.group == "new-group"

    def test_list_by_group(self, tmp_path: Path) -> None:
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        add_task(tasks_dir, "T1", "dev", "P1", group="lens")
        add_task(tasks_dir, "T2", "dev", "P2", group="lens")
        add_task(tasks_dir, "T3", "dev", "P1", group="other")
        result = list_tasks(tasks_dir, group="lens")
        assert len(result) == 2
```

- [ ] **Step 5: Run task tests**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_tasks.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add science-tool/src/science_tool/tasks.py science-tool/tests/test_tasks.py
git commit -m "refactor: remove tags from task parser, renderer, and CRUD — merge legacy tags into related"
```

---

### Task 6: Remove tags from task display and CLI

**Files:**
- Modify: `science-tool/src/science_tool/tasks_display.py:86-114`
- Modify: `science-tool/src/science_tool/cli.py:1605,1614,1628,1710,1718,1732,1749,1758,1787,1798`
- Test: `science-tool/tests/test_tasks_cli.py`

- [ ] **Step 1: Update task display — replace tags column with related column**

In `science-tool/src/science_tool/tasks_display.py`, replace the tags conditional column with a related column:

```python
def render_tasks_table(tasks: list[Task]) -> None:
    """Render a colored Rich table of tasks to stdout."""
    has_groups = any(t.group for t in tasks)
    has_related = any(t.related for t in tasks)

    table = Table(title="Tasks", show_lines=False)
    table.add_column("ID", style="bold")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Pri")
    table.add_column("Status")
    if has_groups:
        table.add_column("Group")
    if has_related:
        table.add_column("Related")
    table.add_column("Created")

    for t in tasks:
        id_text = Text(t.id, style="bold")
        title_text = Text(t.title)
        type_text = Text(t.type, style=_TYPE_STYLE.get(t.type, ""))
        pri_text = Text(t.priority, style=_PRIORITY_STYLE.get(t.priority, ""))
        status_text = Text(t.status, style=_STATUS_STYLE.get(t.status, ""))
        created_text = Text(t.created.isoformat(), style=_age_style(t.created))

        row: list[Text] = [id_text, title_text, type_text, pri_text, status_text]
        if has_groups:
            row.append(Text(t.group, style="cyan"))
        if has_related:
            row.append(Text(", ".join(t.related), style="dim"))
        row.append(created_text)

        table.add_row(*row)

    console = Console()
    console.print(table)
```

- [ ] **Step 2: Update task CLI — remove `--tags` and `--tag` options**

In `science-tool/src/science_tool/cli.py`:

**`tasks add`** (around line 1605): Remove `@click.option("--tags", multiple=True)`, remove `tags` from function signature and from `add_task()` call.

**`tasks edit`** (around line 1710): Remove `@click.option("--tags", multiple=True)`, remove `tags` from function signature and from `edit_task()` call.

**`tasks list`** (around line 1749): Remove `@click.option("--tag", ...)`, remove `tag` from function signature and from `list_tasks()` call. In the JSON output columns and rows, replace `("tags", "Tags")` with `("related", "Related")` and `"tags": ", ".join(t.tags)` with `"related": ", ".join(t.related)`.

- [ ] **Step 3: Update task CLI tests**

In `science-tool/tests/test_tasks_cli.py`, remove or update any tests that use `--tags` or `--tag` CLI options. Update tests to use `--related` instead where appropriate.

- [ ] **Step 4: Run CLI tests**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_tasks_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add science-tool/src/science_tool/tasks_display.py science-tool/src/science_tool/cli.py science-tool/tests/test_tasks_cli.py
git commit -m "refactor: remove tags from task display and CLI, show related column instead"
```

---

### Task 7: Widen `graph add question` to accept generic `--related`

**Files:**
- Modify: `science-tool/src/science_tool/cli.py:854-886`
- Modify: `science-tool/src/science_tool/graph/store.py:627-656`
- Test: `science-tool/tests/test_graph_cli.py`

- [ ] **Step 1: Write failing test — add question with generic `--related`**

```python
def test_graph_add_question_with_generic_related() -> None:
    """graph add question --related should accept any entity reference, not just hypotheses."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["graph", "init"]).exit_code == 0
        # Add a topic entity first
        assert runner.invoke(
            main, ["graph", "add", "hypothesis", "H1", "--text", "Test", "--source", "paper:doi_10_1111_a"]
        ).exit_code == 0

        add = runner.invoke(
            main,
            [
                "graph", "add", "question", "Q10",
                "--text", "How does X relate to Y?",
                "--source", "paper:doi_10_2222_b",
                "--related", "hypothesis/h1",
            ],
        )
        assert add.exit_code == 0

        dataset = Dataset()
        dataset.parse(source="knowledge/graph.trig", format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        q_uri = PROJECT_NS["question/q10"]
        related = [str(o) for o in knowledge.objects(q_uri, SKOS.related)]
        assert any("hypothesis/h1" in r for r in related)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_graph_cli.py::test_graph_add_question_with_generic_related -v`
Expected: FAIL — `--related` option doesn't exist yet.

- [ ] **Step 3: Update `add_question` in store.py**

In `science-tool/src/science_tool/graph/store.py`, modify `add_question` (lines 627-656) to accept a generic `related` parameter instead of `related_hypotheses`:

```python
def add_question(
    graph_path: Path,
    question_id: str,
    text: str,
    source: str,
    maturity: str = "open",
    status: str | None = None,
    related: list[str] | None = None,
) -> URIRef:
    """Add an open question with provenance to the graph."""
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    provenance = dataset.graph(_graph_uri("graph/provenance"))

    question_uri = URIRef(PROJECT_NS[f"question/{question_id.lower()}"])
    knowledge.add((question_uri, RDF.type, SCI_NS.Question))
    knowledge.add((question_uri, SCHEMA_NS.identifier, Literal(question_id)))
    knowledge.add((question_uri, SCHEMA_NS.text, Literal(text)))
    knowledge.add((question_uri, SCI_NS.maturity, Literal(maturity)))

    if status:
        knowledge.add((question_uri, SCI_NS.projectStatus, Literal(status)))

    provenance.add((question_uri, PROV.wasDerivedFrom, _resolve_term(source)))

    if related:
        for ref in related:
            knowledge.add((question_uri, SKOS.related, _resolve_term(ref)))

    _save_dataset(dataset, graph_path)
    return question_uri
```

- [ ] **Step 4: Update CLI command**

In `science-tool/src/science_tool/cli.py`, update `graph_add_question` (lines 854-886):

Replace `--related-hypothesis` with `--related`:

```python
@graph_add.command("question")
@click.argument("question_id")
@click.option("--text", required=True)
@click.option("--source", required=True)
@click.option(
    "--maturity", default="open", show_default=True, type=click.Choice(("open", "partially-resolved", "resolved"))
)
@click.option("--status", default=None, type=click.Choice(PROJECT_STATUSES), help="Project status")
@click.option("--related", "related_refs", multiple=True, help="Related entity reference (repeatable)")
@click.option(
    "--path", "graph_path", default=str(DEFAULT_GRAPH_PATH), show_default=True, type=click.Path(path_type=Path)
)
def graph_add_question(
    question_id: str,
    text: str,
    source: str,
    maturity: str,
    status: str | None,
    related_refs: tuple[str, ...],
    graph_path: Path,
) -> None:
    """Add an open question with provenance."""

    question_uri = add_question(
        graph_path=graph_path,
        question_id=question_id,
        text=text,
        source=source,
        maturity=maturity,
        status=status,
        related=list(related_refs) if related_refs else None,
    )
    click.echo(f"Added question: {question_uri}")
```

- [ ] **Step 5: Update existing tests that use `--related-hypothesis`**

In `science-tool/tests/test_graph_cli.py`, find all tests using `--related-hypothesis` and update them to use `--related`. The key test is `test_graph_add_question_with_maturity_and_related_hypothesis` (around line 3319). Update the CLI invocation from `"--related-hypothesis"` to `"--related"` and update the `add_question()` call from `related_hypotheses=` to `related=`.

- [ ] **Step 6: Run question CLI tests**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen pytest science-tool/tests/test_graph_cli.py -k "question" -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_cli.py
git commit -m "feat: widen graph add question to accept generic --related refs (replaces --related-hypothesis)"
```

---

### Task 8: Remove `tags:` from test fixtures and graph CLI tests

**Files:**
- Modify: `science-tool/tests/test_graph_cli.py`
- Modify: `science-model/tests/test_projects.py`

- [ ] **Step 1: Update graph CLI test fixtures**

In `science-tool/tests/test_graph_cli.py`, find all test fixture markdown strings that include `"tags: [demo]"` or similar and remove those lines. The legacy merge logic from Task 2 will handle any remaining `tags` in real frontmatter, but test fixtures for graph materialization should use `related` directly.

- [ ] **Step 2: Update project test fixtures**

In `science-model/tests/test_projects.py`, the `Project` model still has `tags` (project-level, out of scope for removal). Keep these as-is — project tags describe the project, not entity relationships.

- [ ] **Step 3: Run full test suite for both packages**

Run: `cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pytest -v`
Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run --frozen pytest -v`
Expected: PASS for both

- [ ] **Step 4: Commit**

```bash
git add science-tool/tests/ science-model/tests/
git commit -m "test: update fixtures to remove tags field from entity test data"
```

---

### Task 9: Update entity templates

**Files:**
- Modify: `templates/question.md`
- Modify: `templates/hypothesis.md`
- Modify: `templates/pre-registration.md`
- Modify: all other `templates/*.md` that have `tags: []`

- [ ] **Step 1: Remove `tags:` line from all entity templates**

For every template in `templates/`, remove the `tags: [...]` line from the YAML frontmatter. For templates that had non-empty tags, convert them to `related` entries:

**`templates/question.md`**: Remove `tags: []` (line 6).

**`templates/hypothesis.md`**: Remove `tags: []` (line 6).

**`templates/pre-registration.md`**: Change `tags: [pre-registration]` to use `related` instead. Since `pre-registration` is a structural marker rather than a topic entity, the cleanest approach is to either drop it (the template is already self-identifying via its filename/structure) or convert it to `related: ["topic:pre-registration"]`.

Apply the same removal to all other templates: `dataset.md`, `discussion.md`, `experiment.md`, `inquiry.md`, `interpretation.md`, `method.md`, `workflow.md`, `workflow-run.md`, `workflow-step.md`, `paper-summary.md`, `finding.md`, `story.md`, `paper.md`, `comparison.md`, `bias-audit.md`, `background-topic.md`.

For templates with non-empty tags (`comparison.md` → `[comparison]`, `bias-audit.md` → `[bias-audit]`): these are structural self-identification tags. Remove them — the entity type and template structure already convey this information.

- [ ] **Step 2: Verify templates parse correctly**

Spot-check by parsing a template with frontmatter parser:

```bash
cd /mnt/ssd/Dropbox/science && python -c "
from science_model.frontmatter import parse_frontmatter
from pathlib import Path
for p in Path('templates').glob('*.md'):
    result = parse_frontmatter(p)
    if result:
        fm, _ = result
        assert 'tags' not in fm, f'{p}: still has tags'
        print(f'{p.name}: OK')
"
```

- [ ] **Step 3: Commit**

```bash
git add templates/
git commit -m "refactor: remove tags field from all entity templates"
```

---

### Task 10: Update `review-tasks` command

**Files:**
- Modify: `commands/review-tasks.md`

- [ ] **Step 1: Update the command to use `related` instead of tags**

In `commands/review-tasks.md`:

**Step 6 (lines 63-69)**: Update "Thematic grouping" to reference `related` and `group` instead of `tags`:

```markdown
### 6. Thematic grouping

If tasks lack `group` labels, suggest groupings based on shared themes. Common patterns:
- Tasks sharing the same `related` entities (especially topic references)
- Tasks that form a dependency chain
- Tasks addressing the same system component or research question

If open questions lack related entity links, suggest topic connections based on shared themes
with related hypotheses, tasks, or topics.
```

**Step 8 (lines 96-113)**: Remove the `--tags` reference from the apply commands:

```markdown
# Group assignments
uv run science-tool tasks edit <id> --group=<group>

# Add related entity links
uv run science-tool tasks edit <id> --related=topic:foo --related=topic:bar
```

- [ ] **Step 2: Commit**

```bash
git add commands/review-tasks.md
git commit -m "docs: update review-tasks command to use related instead of tags"
```

---

### Task 11: Run full test suite and type-check

**Files:** None (verification only)

- [ ] **Step 1: Run science-model tests**

Run: `cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pytest -v`
Expected: PASS

- [ ] **Step 2: Run science-tool tests**

Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run --frozen pytest -v`
Expected: PASS

- [ ] **Step 3: Run type checks**

Run: `cd /mnt/ssd/Dropbox/science/science-model && uv run --frozen pyright`
Run: `cd /mnt/ssd/Dropbox/science/science-tool && uv run --frozen pyright`
Expected: No new errors

- [ ] **Step 4: Run linting**

Run: `cd /mnt/ssd/Dropbox/science && uv run --frozen ruff check .`
Expected: No new errors

---

## Notes

### Out of scope
- **`Project.tags`** (in `science.yaml`): Project-level descriptors that categorize the project itself. These don't participate in entity-to-entity relationships and should remain as-is. A future change could convert these to `related` references to topic entities if desired.
- **Frontmatter migration script**: The backward-compat merge logic in `parse_entity_file` and `_parse_task_block` handles legacy `tags:` fields at parse time. A one-time migration to physically rewrite frontmatter files (removing `tags:` and adding to `related:`) is valuable but optional — the system works correctly without it. This can be done as a follow-up.
- **Question priority field**: Adding a `priority` field to questions (paralleling tasks) was discussed but is a separate concern from the tags→related unification.

### Migration strategy
The backward-compat merge approach means:
1. Existing files with `tags: [foo, bar]` continue to work — tags are merged into `related` as `topic:foo`, `topic:bar` at parse time.
2. Newly created entities use `related` exclusively — no `tags` field in templates or CLI.
3. A future optional migration script can rewrite all frontmatter files to physically remove `tags:` and move values into `related:`. This is cosmetic — the system is correct either way.
4. Topic entities referenced by migrated tags (e.g., `topic:genomics`) may not exist as files yet. The materialization audit will flag these as unresolved references. Create the corresponding topic entity files or add manual alias mappings as needed.
