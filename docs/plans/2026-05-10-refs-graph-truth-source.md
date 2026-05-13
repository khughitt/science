# refs: graph truth source + extensible scan roots — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `science refs check --include-body` capable of fully replacing project-local citation auditors (like natural-systems' `scripts/audit-citations.ts`) by adding two `refs` config knobs: a pluggable entity-index truth source (frontmatter `id:` sweep vs. built `knowledge/graph.trig`) and an extensible scan-root list (canonical defaults `doc/` + `specs/`, plus opt-in `tasks/`, `papers/`, `core/`, root `.md`, etc.).

**Architecture:** Add a typed `RefsConfig` to `ProjectConfig` mirroring the existing `ProseLintConfig` pattern. Add `_load_entity_index_from_graph()` parser in `refs.py` reusing the canonical `DEFAULT_GRAPH_PATH` constant from `science_tool.graph.store`. Thread the truth-source choice through `check_refs(root, *, include_body=…)` and the scan-roots list through `_collect_markdown_files()`. Falls back to frontmatter sweep with a warning if `knowledge_graph` source is configured but the trig file is missing.

**Tech Stack:** Python (Pydantic v2 for config, regex for trig parsing — matches the existing pattern; no rdflib dependency for the lightweight identifier sweep).

---

## File Structure

- Modify: `science/src/science_tool/project_config.py` — add `RefsConfig` model + `refs:` field on `ProjectConfig`
- Modify: `science/src/science_tool/refs.py` — add graph parser + plumbing
- Modify: `science/tests/test_refs.py` — add tests for new behaviors
- Modify: `docs/conventions/refs-check.md` (or create if missing) — document new knobs
- Create: `docs/audits/2026-05-10-refs-graph-truth-source-baselines.md` — capture NS + MM baselines

---

## Task 1: Add `RefsConfig` to `project_config.py`

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Modify: `science/tests/test_project_config.py` (or create — verify location first)

- [ ] **Step 1: Verify test file location**

```bash
ls science/tests/test_project_config.py 2>/dev/null && echo "exists" || find science/tests -name "*project_config*" 2>/dev/null
```

- [ ] **Step 2: Write failing test for RefsConfig parsing**

Add to the project config tests (create file if needed; mirror `ProseLintConfig` test patterns).

```python
def test_refs_config_defaults_when_absent(tmp_path):
    """ProjectConfig.refs is None when science.yaml omits the section."""
    from science_tool.project_config import load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n", encoding="utf-8"
    )
    config = load_project_config(tmp_path)
    assert config.refs is None


def test_refs_config_parses_graph_truth_source(tmp_path):
    """`refs.entity_index_source: knowledge_graph` parses to the enum value."""
    from science_tool.project_config import EntityIndexSource, load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n"
        "refs:\n"
        "  entity_index_source: knowledge_graph\n"
        "  scan_roots: [tasks, papers, core]\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.refs is not None
    assert config.refs.entity_index_source == EntityIndexSource.KNOWLEDGE_GRAPH
    assert config.refs.scan_roots == ["tasks", "papers", "core"]


def test_refs_config_default_source_is_frontmatter(tmp_path):
    """`refs:` block with only scan_roots defaults source to frontmatter."""
    from science_tool.project_config import EntityIndexSource, load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n"
        "refs:\n"
        "  scan_roots: [tasks]\n",
        encoding="utf-8",
    )
    config = load_project_config(tmp_path)
    assert config.refs is not None
    assert config.refs.entity_index_source == EntityIndexSource.FRONTMATTER
    assert config.refs.scan_roots == ["tasks"]


def test_refs_config_rejects_unknown_source(tmp_path):
    """`refs.entity_index_source` rejects unknown values via Pydantic validation."""
    from pydantic import ValidationError
    from science_tool.project_config import load_project_config

    (tmp_path / "science.yaml").write_text(
        "name: test-project\nprofile: research\n"
        "refs:\n"
        "  entity_index_source: rdfox\n",
        encoding="utf-8",
    )
    try:
        load_project_config(tmp_path)
    except ValidationError:
        return
    raise AssertionError("Expected ValidationError for unknown source")
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_project_config.py -v -k refs_config
```

Expected: FAIL with `ImportError` for `EntityIndexSource` or `AttributeError` for `config.refs`.

- [ ] **Step 4: Implement RefsConfig**

Add to `science/src/science_tool/project_config.py`:

```python
class EntityIndexSource(StrEnum):
    """Truth source for `science refs check --include-body` entity-ref validation."""

    FRONTMATTER = "frontmatter"
    KNOWLEDGE_GRAPH = "knowledge_graph"


class RefsConfig(BaseModel):
    """Configuration for `science refs check`."""

    model_config = ConfigDict(extra="forbid")

    entity_index_source: EntityIndexSource = EntityIndexSource.FRONTMATTER
    scan_roots: list[str] = Field(default_factory=list)
```

Then add the field to `ProjectConfig`:

```python
class ProjectConfig(BaseModel):
    # ... existing fields ...
    prose_lint: ProseLintConfig | None = None
    refs: RefsConfig | None = None  # NEW
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_project_config.py -v -k refs_config
```

Expected: PASS (4/4).

- [ ] **Step 6: Run the full project_config test file to ensure no regression**

```bash
cd science && uv run pytest tests/test_project_config.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config.py
git commit -m "feat(project_config): add RefsConfig with entity_index_source + scan_roots"
```

---

## Task 2: Add `_load_entity_index_from_graph()` parser in `refs.py`

**Files:**
- Modify: `science/src/science_tool/refs.py`
- Modify: `science/tests/test_refs.py`

- [ ] **Step 1: Write failing test for graph parser**

Add to `science/tests/test_refs.py` near existing `_load_entity_index` tests:

```python
def test_load_entity_index_from_graph_parses_schema_identifiers(tmp_path):
    """`_load_entity_index_from_graph` extracts <kind>:<slug> from schema:identifier triples."""
    from science_tool.refs import _load_entity_index_from_graph

    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()
    (knowledge_dir / "graph.trig").write_text(
        "@prefix schema: <https://schema.org/> .\n"
        "<http://example.org/project/graph/knowledge> {\n"
        '    <http://example.org/project/task/t100>\n'
        '        schema:identifier "task:t100" .\n'
        '    <http://example.org/project/question/q42-foo>\n'
        '        schema:identifier "question:q42-foo" .\n'
        '    <http://example.org/project/concept/info>\n'
        '        schema:identifier "concept:info" .\n'  # not in _LOCAL_ENTITY_KINDS, must be skipped
        '}\n',
        encoding="utf-8",
    )
    index = _load_entity_index_from_graph(tmp_path)
    assert "task:t100" in index
    assert "question:q42-foo" in index
    assert "concept:info" not in index  # filtered: kind not in _LOCAL_ENTITY_KINDS


def test_load_entity_index_from_graph_returns_empty_when_missing(tmp_path):
    """Missing graph.trig returns empty set without raising."""
    from science_tool.refs import _load_entity_index_from_graph

    index = _load_entity_index_from_graph(tmp_path)
    assert index == set()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_refs.py -v -k entity_index_from_graph
```

Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement the parser**

Add to `science/src/science_tool/refs.py` near `_load_entity_index()`:

```python
_GRAPH_IDENTIFIER_RE = re.compile(r'schema:identifier\s+"([^"]+)"')


def _load_entity_index_from_graph(root: Path) -> set[str]:
    """Load entity-ref index from the project's built `knowledge/graph.trig` file.

    Parses `schema:identifier "<kind>:<slug>"` triples and keeps only those
    whose kind is in `_LOCAL_ENTITY_KINDS`. Returns an empty set if the trig
    file is missing — caller is responsible for falling back to the
    frontmatter sweep (with a warning) when this is the configured source.
    """
    from science_tool.graph.store import DEFAULT_GRAPH_PATH

    trig_path = root / DEFAULT_GRAPH_PATH
    if not trig_path.is_file():
        return set()
    text = trig_path.read_text(encoding="utf-8")
    index: set[str] = set()
    for match in _GRAPH_IDENTIFIER_RE.finditer(text):
        ref = match.group(1)
        if ":" not in ref:
            continue
        kind, _, slug = ref.partition(":")
        if kind in _LOCAL_ENTITY_KINDS and slug:
            index.add(ref)
    return index
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_refs.py -v -k entity_index_from_graph
```

Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "feat(refs): add _load_entity_index_from_graph trig parser"
```

---

## Task 3: Wire entity-index source choice through `check_refs()`

**Files:**
- Modify: `science/src/science_tool/refs.py`
- Modify: `science/tests/test_refs.py`

- [ ] **Step 1: Write failing test for graph source selection**

Add to `science/tests/test_refs.py`:

```python
class TestEntityIndexSourceSelection:
    """`check_refs` honors `refs.entity_index_source` from science.yaml."""

    def test_graph_source_uses_trig_file(self, tmp_path):
        """When configured to `knowledge_graph`, refs in graph.trig are accepted
        even when missing from frontmatter `id:` index."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n"
            "refs:\n  entity_index_source: knowledge_graph\n",
            encoding="utf-8",
        )
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "graph.trig").write_text(
            '<x> schema:identifier "task:t999" .\n', encoding="utf-8"
        )
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()
        # File with body ref to task:t999 — exists in graph but no frontmatter file.
        (doc_dir / "note.md").write_text(
            "---\nid: discussion:2026-05-10-note\n---\n\nReferences task:t999 in body.\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert body_issues == [], f"Expected no body-entity-ref issues; got {body_issues}"

    def test_frontmatter_source_default_ignores_graph(self, tmp_path):
        """Default `frontmatter` source ignores graph.trig — same ref reports broken."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n", encoding="utf-8"
        )
        knowledge_dir = tmp_path / "knowledge"
        knowledge_dir.mkdir()
        (knowledge_dir / "graph.trig").write_text(
            '<x> schema:identifier "task:t999" .\n', encoding="utf-8"
        )
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()
        (doc_dir / "note.md").write_text(
            "---\nid: discussion:2026-05-10-note\n---\n\nReferences task:t999 in body.\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert any(i.ref_value == "task:t999" for i in body_issues)

    def test_graph_source_falls_back_when_trig_missing(self, tmp_path, capsys):
        """Configured `knowledge_graph` with missing trig falls back to frontmatter
        with a stderr warning."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n"
            "refs:\n  entity_index_source: knowledge_graph\n",
            encoding="utf-8",
        )
        # No knowledge/graph.trig file exists.
        doc_dir = tmp_path / "doc"
        doc_dir.mkdir()
        (doc_dir / "note.md").write_text(
            "---\nid: discussion:2026-05-10-note\n---\n\nReferences task:t999 in body.\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        # Should report task:t999 as broken (frontmatter fallback, no file with that id).
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert any(i.ref_value == "task:t999" for i in body_issues)
        captured = capsys.readouterr()
        assert "knowledge/graph.trig" in captured.err
        assert "frontmatter" in captured.err.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_refs.py -v -k EntityIndexSourceSelection
```

Expected: FAIL.

- [ ] **Step 3: Modify `check_refs()` to read project config**

In `science/src/science_tool/refs.py`, modify `check_refs(root, *, include_body=False)`:

```python
def check_refs(root: Path, *, include_body: bool = False) -> list[RefIssue]:
    """Run all reference checks and return issues found."""
    issues: list[RefIssue] = []

    # Load project config to determine entity-index source.
    refs_config = _load_refs_config(root)

    files = _collect_markdown_files(root)
    hyp_ids = _load_hypothesis_ids(root)
    bib_keys = _load_bib_keys(root)
    entity_index = _resolve_entity_index(root, refs_config) if include_body else set()
    # ... rest unchanged ...
```

Add helper functions near `_load_entity_index()`:

```python
def _load_refs_config(root: Path):
    """Load project's RefsConfig, returning None on any error (defensive)."""
    try:
        from science_tool.project_config import load_project_config

        return load_project_config(root).refs
    except Exception:  # noqa: BLE001 — defensive; missing/malformed config tolerated.
        return None


def _resolve_entity_index(root: Path, refs_config) -> set[str]:
    """Choose entity-index loader based on configured truth source.

    Falls back to frontmatter with a stderr warning when `knowledge_graph`
    is configured but the trig file is missing.
    """
    import sys

    from science_tool.project_config import EntityIndexSource

    source = (
        refs_config.entity_index_source
        if refs_config is not None
        else EntityIndexSource.FRONTMATTER
    )
    if source == EntityIndexSource.KNOWLEDGE_GRAPH:
        index = _load_entity_index_from_graph(root)
        if index:
            return index
        print(
            "[refs] knowledge/graph.trig not found or empty; "
            "falling back to frontmatter `id:` sweep. Run `science graph build` first.",
            file=sys.stderr,
        )
    return _load_entity_index(root)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_refs.py -v -k EntityIndexSourceSelection
```

Expected: PASS (3/3).

- [ ] **Step 5: Run full refs test file to verify no regression**

```bash
cd science && uv run pytest tests/test_refs.py -v
```

Expected: all existing refs tests still pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "feat(refs): wire entity_index_source config through check_refs"
```

---

## Task 4: Extend `_collect_markdown_files()` to honor `scan_roots`

**Files:**
- Modify: `science/src/science_tool/refs.py`
- Modify: `science/tests/test_refs.py`

- [ ] **Step 1: Write failing test for scan_roots extension**

Add to `science/tests/test_refs.py`:

```python
class TestRefsScanRoots:
    """`refs.scan_roots` config extends the default scan beyond doc/specs."""

    def test_extra_dir_scanned_when_configured(self, tmp_path):
        """A `tasks/` ref shows up only when `scan_roots: [tasks]` is configured."""
        from science_tool.refs import check_refs

        # Set up a project with a body-ref in tasks/active.md.
        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n"
            "refs:\n  scan_roots: [tasks]\n",
            encoding="utf-8",
        )
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "active.md").write_text(
            "# Active\n\nReferences task:t999 (does not exist).\n",
            encoding="utf-8",
        )
        # Frontmatter id index has nothing matching.
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert any(i.ref_value == "task:t999" for i in body_issues), (
            f"Expected task:t999 issue from tasks/active.md; got {body_issues}"
        )

    def test_root_markdown_scanned_when_dot_in_scan_roots(self, tmp_path):
        """`scan_roots: ['.']` includes root-level .md files."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n"
            "refs:\n  scan_roots: ['.']\n",
            encoding="utf-8",
        )
        (tmp_path / "README.md").write_text(
            "# Project\n\nSee task:t999 (broken).\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert any(
            i.file == "README.md" and i.ref_value == "task:t999"
            for i in body_issues
        ), f"Expected README.md/task:t999 issue; got {body_issues}"

    def test_extra_dir_not_scanned_by_default(self, tmp_path):
        """Without `scan_roots`, tasks/ refs are NOT detected — confirming default."""
        from science_tool.refs import check_refs

        (tmp_path / "science.yaml").write_text(
            "name: test-project\nprofile: research\n", encoding="utf-8"
        )
        tasks_dir = tmp_path / "tasks"
        tasks_dir.mkdir()
        (tasks_dir / "active.md").write_text(
            "# Active\n\nReferences task:t999.\n",
            encoding="utf-8",
        )
        issues = check_refs(tmp_path, include_body=True)
        body_issues = [i for i in issues if i.ref_type == "body-entity-ref"]
        assert not any(i.ref_value == "task:t999" for i in body_issues)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_refs.py -v -k RefsScanRoots
```

Expected: FAIL.

- [ ] **Step 3: Modify `_collect_markdown_files` and `check_refs`**

In `science/src/science_tool/refs.py`, change `_collect_markdown_files` signature:

```python
def _collect_markdown_files(
    root: Path, *, extra_roots: list[str] | None = None
) -> list[Path]:
    """Collect all markdown files to scan.

    Defaults to `paths.doc_dir` + `paths.specs_dir`. `extra_roots` (from
    `RefsConfig.scan_roots`) appends additional dirs; the special value `"."`
    means root-level `.md` files only (non-recursive).
    """
    try:
        from science_tool.paths import resolve_paths

        pp = resolve_paths(root)
        scan_dirs = [pp.doc_dir, pp.specs_dir]
    except Exception:
        scan_dirs = [root / d for d in _SCAN_DIRS]

    files: list[Path] = []
    for d in scan_dirs:
        if d.is_dir():
            for p in d.rglob("*.md"):
                if not any(part in _SKIP_DIRS for part in p.parts):
                    files.append(p)
    for scan_file in _SCAN_FILES:
        f = root / scan_file
        if f.is_file():
            files.append(f)

    # Honor extra scan roots from refs.scan_roots config.
    for extra in extra_roots or []:
        if extra == ".":
            # Root-level .md files only (non-recursive).
            for p in root.glob("*.md"):
                if p.is_file():
                    files.append(p)
        else:
            d = root / extra
            if d.is_dir():
                for p in d.rglob("*.md"):
                    if not any(part in _SKIP_DIRS for part in p.parts):
                        files.append(p)

    # Deduplicate (a file may already be counted via _SCAN_FILES).
    return sorted(set(files))
```

Then update `check_refs` to thread the value through:

```python
def check_refs(root: Path, *, include_body: bool = False) -> list[RefIssue]:
    issues: list[RefIssue] = []
    refs_config = _load_refs_config(root)
    extra_roots = refs_config.scan_roots if refs_config is not None else None
    files = _collect_markdown_files(root, extra_roots=extra_roots)
    # ... rest unchanged ...
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_refs.py -v -k RefsScanRoots
```

Expected: PASS (3/3).

- [ ] **Step 5: Run the full refs test file**

```bash
cd science && uv run pytest tests/test_refs.py -v
```

Expected: no regressions.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "feat(refs): extend _collect_markdown_files with scan_roots config"
```

---

## Task 5: Run full test suite to catch any cross-file regressions

**Files:** none (verification only)

- [ ] **Step 1: Run the full science test suite**

```bash
cd science && uv run pytest -x -q
```

Expected: all green (was 2167 passed, 2 skipped before this branch).

If any test fails, fix the underlying issue before continuing.

---

## Task 6: Document the new knobs in `docs/conventions/`

**Files:**
- Modify or create: `docs/conventions/refs-check.md`

- [ ] **Step 1: Check whether refs-check doc exists**

```bash
ls docs/conventions/refs-check.md docs/conventions/refs.md 2>/dev/null
```

If neither exists, create `docs/conventions/refs-check.md`.

- [ ] **Step 2: Write or extend the doc**

If creating from scratch, use this skeleton — otherwise append a "Configuration" section.

````markdown
# `science refs check` — conventions

Validates references across the project: hypothesis IDs, citations, markdown
links, DOIs, PMIDs, typed entity refs in frontmatter, and (with `--include-body`)
typed entity refs in body prose.

## Default behavior

Scans `doc/` and `specs/` plus `RESEARCH_PLAN.md`. Body-prose entity-ref scan
(opt-in via `--include-body`) validates against the frontmatter `id:` sweep.

## Configuration

Configure via `science.yaml`:

```yaml
refs:
  # Truth source for body-prose entity-ref validation.
  # `frontmatter` (default): walk all markdown frontmatter for `id:` fields.
  # `knowledge_graph`: parse `knowledge/graph.trig` (built by `science graph build`).
  # The graph source is more accurate for projects that rely on built
  # entity indexes; falls back to frontmatter (with a stderr warning) when
  # the trig file is missing.
  entity_index_source: knowledge_graph

  # Extra dirs to scan beyond the defaults (doc/, specs/).
  # The special value "." means root-level .md files only (non-recursive).
  scan_roots:
    - tasks
    - papers
    - core
    - "."
```

## When to use `knowledge_graph` source

- Project uses `science graph build` and treats the trig as the canonical
  entity index.
- Frontmatter `id:` sweep produces too many false positives (e.g. some
  entities are declared without a markdown file with matching frontmatter).

## Related

- `science refs check --include-body` — opt-in body-prose entity-ref scan.
- `science prose lint` — separate lint group for citation gaps and short-form
  ID references in prose.
````

- [ ] **Step 3: Commit**

```bash
git add docs/conventions/refs-check.md
git commit -m "docs(refs-check): document entity_index_source + scan_roots knobs"
```

---

## Task 7: Capture baselines on natural-systems and multiple-myeloma

**Files:**
- Create: `docs/audits/2026-05-10-refs-graph-truth-source-baselines.md`

This task is research/measurement, not new code. Run the new feature against both projects with each truth-source choice and compare against the existing `audit-citations.ts` output for natural-systems.

- [ ] **Step 1: Build the science wheel from the worktree branch**

```bash
cd science
uv pip install -e . --quiet
which science
```

Verify the worktree's science is on PATH (or use the venv binary path explicitly in the next steps).

- [ ] **Step 2: Run baseline scan in natural-systems with `frontmatter` source**

```bash
SCIENCE=~/d/science/science/.venv/bin/science  # or wherever uv installed
cd ~/d/natural-systems
"$SCIENCE" refs check --include-body 2>&1 | grep -E "broken|Found" | head -3 > /tmp/ns-frontmatter.txt
cat /tmp/ns-frontmatter.txt
```

Record the broken count.

- [ ] **Step 3: Add `refs.entity_index_source: knowledge_graph` to NS science.yaml temporarily and re-run**

```bash
cd ~/d/natural-systems
# Backup
cp science.yaml science.yaml.bak
# Append config (verify not already present first)
cat >> science.yaml <<'EOF'
refs:
  entity_index_source: knowledge_graph
  scan_roots:
    - tasks
    - papers
    - core
    - "."
EOF
"$SCIENCE" refs check --include-body 2>&1 | grep -E "broken|Found" | head -3 > /tmp/ns-graph.txt
cat /tmp/ns-graph.txt
# Restore
mv science.yaml.bak science.yaml
```

Record the broken count. **Target:** within ~10% of `audit-citations.ts`'s 208 unresolved (allowing for the wider kind coverage).

- [ ] **Step 4: Compare against audit-citations.ts output**

```bash
cd ~/d/natural-systems
npm run audit:citations 2>&1 | grep -E "unresolved" | head -1 > /tmp/ns-audit-citations.txt
cat /tmp/ns-audit-citations.txt
```

Record the count.

- [ ] **Step 5: Run baselines in multiple-myeloma**

```bash
SCIENCE=~/d/science/science/.venv/bin/science
cd ~/d/cancer/cancer-types/multiple-myeloma
"$SCIENCE" refs check --include-body 2>&1 | grep -E "broken|Found" | head -3 > /tmp/mm-frontmatter.txt
cat /tmp/mm-frontmatter.txt
# Same config swap as Step 3
cp science.yaml science.yaml.bak
cat >> science.yaml <<'EOF'
refs:
  entity_index_source: knowledge_graph
EOF
"$SCIENCE" refs check --include-body 2>&1 | grep -E "broken|Found" | head -3 > /tmp/mm-graph.txt
cat /tmp/mm-graph.txt
mv science.yaml.bak science.yaml
```

- [ ] **Step 6: Write the audit doc**

Create `docs/audits/2026-05-10-refs-graph-truth-source-baselines.md`:

```markdown
# refs graph truth source — baselines

Date: 2026-05-10

Captured before retiring natural-systems' `scripts/audit-citations.ts` (t469).
Compares the new `refs.entity_index_source: knowledge_graph` knob against the
default `frontmatter` source and against the project-local script.

## natural-systems

| Source | Body-entity-ref count |
|---|---:|
| `science refs check --include-body` (frontmatter, no scan_roots) | <fill in from /tmp/ns-frontmatter.txt> |
| `science refs check --include-body` (graph + scan_roots: tasks, papers, core, .) | <fill in from /tmp/ns-graph.txt> |
| `npm run audit:citations` (graph.trig truth source, 10 kinds) | <fill in from /tmp/ns-audit-citations.txt> |

**Divergence analysis:** <one paragraph — note kinds covered (27 vs 10),
scan-root differences, and any other deltas observed>

## multiple-myeloma

| Source | Body-entity-ref count |
|---|---:|
| `science refs check --include-body` (frontmatter, no scan_roots) | <fill in> |
| `science refs check --include-body` (graph) | <fill in> |

## Conclusion

<one paragraph: ready to retire audit-citations.ts? Y/N + caveats>
```

- [ ] **Step 7: Commit**

```bash
git add docs/audits/2026-05-10-refs-graph-truth-source-baselines.md
git commit -m "docs(audits): capture refs graph-truth-source baselines vs audit-citations.ts"
```

---

## Self-Review Checklist (before subagent dispatch)

- All Pydantic models use `ConfigDict(extra="forbid")` for new schemas.
- The `_load_refs_config()` helper is defensive (returns None on any error)
  to avoid breaking projects without `science.yaml`.
- `_resolve_entity_index()` only writes to stderr when graph source is
  configured but trig is missing — silent for normal frontmatter use.
- `_collect_markdown_files()` deduplicates after appending extra roots
  (prevents double-counting `RESEARCH_PLAN.md` if `.` is in scan_roots).
- All new tests are isolated via `tmp_path` and don't depend on real projects.
- Task 7 is research/measurement (not new code) — its commit is a doc commit only.
- Default behavior is preserved: projects with no `refs:` block in
  science.yaml see no change.
