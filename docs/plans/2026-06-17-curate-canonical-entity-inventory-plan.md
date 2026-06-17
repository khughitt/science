# Curate Canonical-Entity Inventory (G2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate curate's inventory to discover entities from the canonical `entities/<kind>/` homes via the shared `iter_entity_markdown` iterator, instead of the retired `doc/**`+`specs/**` layout.

**Architecture:** Replace the legacy path-glob discovery (`_collect_markdown_paths`) and path-based classification (`_markdown_artifact_class`, `_DOC_KIND_BY_DIR`) in `curate/inventory.py` with `iter_entity_markdown(project_root / "entities")` plus a frontmatter-driven `artifact_class` (`type` → `kind` → colon-prefixed `id` prefix). All `CandidateSignals`, the `recent_days`/`recent_top_k` knobs, the task/knowledge-source/agents_md surfaces, the `_emergent-threads.md` orphan-absorption pass, and the JSON contract are preserved. Register `curate/inventory.py` in the entity-scanner guard.

**Tech Stack:** Python 3.13, Pydantic, pytest. Two-package repo: tool code in `science/src/science_tool/`, model in `science/model/src/science_model/`.

**Design doc:** `docs/plans/2026-06-17-curate-canonical-entity-inventory-design.md` (same worktree).

**How to run tests (from the worktree's `science/` dir):**
```bash
rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest <path> -q
```
The worktree has no `.venv`; the command above points at the main checkout's interpreter and prepends the worktree's `src`/`model/src` so the worktree code is what runs.

**Key facts the implementer needs:**
- `iter_entity_markdown(entities_root: Path, *, include_archived: bool = False) -> Iterator[Path]` lives in `science_tool/entity_scan.py`. It yields `*.md` under `entities_root` in **sorted** order, **skips any `_`-prefixed path segment** (so `entities/_archive/` is excluded by default), and yields nothing if the root is missing. It is stdlib-only (safe to import — no cycles).
- `parse_frontmatter(path)` (from `science_model.frontmatter`, already imported in `inventory.py`) returns `(frontmatter_dict, body)` or `None` when the file has no parseable frontmatter.
- The signal-eligibility sets are kind-name keyed and stay unchanged: `_RELATED_CLASSES = {"hypothesis", "interpretation", "paper", "question"}`, `_SOURCE_REF_CLASSES = {"interpretation", "paper"}`.
- `artifact_class` for an entity is its **kind string**, so these sets keep matching.

---

### Task 1: Migrate entity discovery + classification to canonical `entities/`

This is the core change: the test fixture moves from the legacy `doc/`+`specs/` tree to `entities/<kind>/`, which makes the existing tests fail against the current (legacy-scanning) implementation; then `inventory.py` is rewritten to scan `entities/`.

**Files:**
- Modify: `science/src/science_tool/curate/inventory.py`
- Test: `science/tests/test_curate_inventory.py`

- [ ] **Step 1: Rewrite the fixture and existing assertions to the canonical layout**

In `science/tests/test_curate_inventory.py`, replace the `curated_project` fixture's six entity-file `_write` calls and the matching `_set_mtime` calls so every entity lives under `entities/<kind-plural>/` instead of `doc/<kind>/` or `specs/hypotheses/`. Frontmatter is unchanged (id-only, no `type:`), which exercises the id-prefix derivation path across the whole fixture. Replace the fixture body's entity-write block (currently the `specs/hypotheses/h1.md` … `doc/discussions/d1.md` writes) with:

```python
    _write(
        project_root / "entities/hypotheses/h1.md",
        "---\nid: hypothesis:h1\ntitle: Hypothesis One\nrelated:\n  - question:q1\n---\nHypothesis body.\n",
    )
    _write(
        project_root / "entities/questions/q1.md",
        "---\nid: question:q1\ntitle: Question One\n---\nQuestion body.\n",
    )
    _write(
        project_root / "entities/papers/p1.md",
        "---\n"
        "id: paper:p1\n"
        "title: Paper One\n"
        "related:\n"
        "  - question:q1\n"
        "source_refs:\n"
        "  - cite:paper-one\n"
        "---\n"
        "Paper body.\n",
    )
    _write(
        project_root / "entities/interpretations/i1.md",
        "---\nid: interpretation:i1\ntitle: Interpretation One\nrelated:\n  - question:q1\n---\nInterpretation body.\n",
    )
    _write(
        project_root / "entities/topics/topic-a.md",
        "---\n"
        "id: topic:topic-a\n"
        "title: Topic A\n"
        "related:\n"
        "  - question:q1\n"
        "source_refs:\n"
        "  - cite:topic-a\n"
        "---\n"
        "Topic body.\n",
    )
    _write(
        project_root / "entities/discussions/d1.md",
        "---\n"
        "id: discussion:d1\n"
        "title: Discussion One\n"
        "related:\n"
        "  - question:q1\n"
        "source_refs:\n"
        "  - cite:discussion-one\n"
        "---\n"
        "Discussion body.\n",
    )
```

Then update the six entity `_set_mtime` calls (leave the `knowledge/...` and `tasks/...` mtimes unchanged):

```python
    _set_mtime(project_root / "entities/hypotheses/h1.md", today - timedelta(days=9))
    _set_mtime(project_root / "entities/questions/q1.md", today)
    _set_mtime(project_root / "entities/papers/p1.md", today - timedelta(days=2))
    _set_mtime(project_root / "entities/interpretations/i1.md", today - timedelta(days=45))
    _set_mtime(project_root / "entities/topics/topic-a.md", today - timedelta(days=4))
    _set_mtime(project_root / "entities/discussions/d1.md", today - timedelta(days=6))
```

Now update the assertions in `test_collect_inventory_tracks_counts_and_candidate_signals`. The `artifact_counts` dict is unchanged (same classes). The `artifacts` path list re-sorts because the `entities/...` prefixes sort differently from `doc/...`/`specs/...`:

```python
    assert [artifact.path for artifact in inventory.artifacts] == [
        "entities/discussions/d1.md",
        "entities/hypotheses/h1.md",
        "entities/interpretations/i1.md",
        "entities/papers/p1.md",
        "entities/questions/q1.md",
        "entities/topics/topic-a.md",
        "knowledge/sources/local/entities.yaml",
        "tasks/active.md#t001",
        "tasks/done/2026-04-01.md#t002",
    ]

    assert inventory.candidate_signals.missing_related == ["entities/questions/q1.md"]
    assert inventory.candidate_signals.missing_source_refs == ["entities/interpretations/i1.md"]
    assert inventory.candidate_signals.no_outbound_links == ["entities/questions/q1.md"]
    assert inventory.candidate_signals.recently_modified == [
        "entities/questions/q1.md",
        "tasks/active.md#t001",
        "entities/papers/p1.md",
        "entities/topics/topic-a.md",
        "entities/discussions/d1.md",
    ]
    assert inventory.candidate_signals.long_idle == [
        "entities/interpretations/i1.md",
        "knowledge/sources/local/entities.yaml",
        "tasks/done/2026-04-01.md#t002",
    ]

    assert [artifact.modified_days_ago for artifact in inventory.artifacts] == [6, 9, 45, 2, 0, 4, 60, 1, 90]
```

(The `modified_days_ago` list follows the new path sort order: discussions=6, hypotheses=9, interpretations=45, papers=2, questions=0, topics=4, knowledge=60, active#t001=1, done#t002=90.)

In `test_collect_inventory_defers_to_emergent_threads_orphans` and `test_collect_inventory_ignores_stale_emergent_threads`, the `_emergent-threads.md` file stays at `doc/reports/synthesis/_emergent-threads.md` (it is read directly, not via entity discovery — do **not** move it). Update only the `missing_source_refs` assertion in the stale test:

```python
    assert inventory.candidate_signals.missing_source_refs == ["entities/interpretations/i1.md"]
```

In `test_collect_inventory_recent_top_k_caps_recently_modified` and `test_collect_inventory_recent_days_tightens_window`, update the expected paths:

```python
    assert inventory.candidate_signals.recently_modified == [
        "entities/questions/q1.md",
        "tasks/active.md#t001",
    ]
```

In `test_collect_inventory_surfaces_frontmatter_less_files`, move both added files under `entities/` (the scan no longer looks at `doc/reports/`):

```python
    _write(
        curated_project / "entities/reports/2026-05-01-untracked-report.md",
        "# Untracked report\n\nSome body without frontmatter.\n",
    )
    _write(
        curated_project / "entities/reports/2026-05-01-with-fm.md",
        "---\nid: report:r1\ntitle: Tracked\n---\nBody.\n",
    )
    inventory = collect_inventory(curated_project, today=date(2026, 5, 1))
    assert inventory.candidate_signals.no_frontmatter_files == [
        "entities/reports/2026-05-01-untracked-report.md",
    ]
```

The agents_md tests (`test_collect_inventory_includes_agents_md_state`, `test_collect_inventory_surfaces_agents_md_drift`) need no changes.

- [ ] **Step 2: Run the migrated tests and confirm they FAIL**

Run (from the worktree's `science/` dir):
```bash
rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_curate_inventory.py -q
```
Expected: FAIL. The current implementation scans `doc/`+`specs/`, so it finds zero entities under the new `entities/` fixture — `artifact_counts` and the path/signal assertions will not match (e.g. `artifact_counts` lacks the entity classes).

- [ ] **Step 3: Rewrite `inventory.py` discovery + classification**

In `science/src/science_tool/curate/inventory.py`:

(a) Add the import near the other `science_tool` imports (after `from science_tool.curate.agents_md import ...`):
```python
from science_tool.entity_scan import iter_entity_markdown
```

(b) Delete the `_DOC_KIND_BY_DIR` constant (the dict at module scope) and the explanatory `# topic remains in inventory ...` comment block that follows it.

(c) Delete the `_collect_markdown_paths` and `_markdown_artifact_class` functions entirely.

(d) Add a canonical entity-path collector (place it where `_collect_markdown_paths` was):
```python
def _collect_entity_paths(project_root: Path) -> list[Path]:
    """Canonical entity markdown under entities/<kind>/, via the shared iterator.

    The iterator skips _archive/ and every _-prefixed segment, so relocated
    (archived) members and reserved dirs drop out; it returns nothing when
    entities/ is absent (a legacy-layout project reports zero entities — the
    intended posture, matching big-picture's v2->v3 read).
    """
    return list(iter_entity_markdown(project_root / "entities"))
```

(e) Add the frontmatter-driven classifier (place it next to `_collect_entity_paths`):
```python
def _entity_artifact_class(frontmatter: dict[str, object]) -> str | None:
    """Entity kind from frontmatter: `type`, then `kind`, then the `id` prefix
    before ':'. A bare/unprefixed `id` (no colon) yields no kind. Returns None
    when none applies — the record is then skipped (it can key no signal)."""
    for key in ("type", "kind"):
        value = frontmatter.get(key)
        if isinstance(value, str) and value:
            return value
    raw_id = frontmatter.get("id")
    if isinstance(raw_id, str) and ":" in raw_id:
        return raw_id.split(":", 1)[0]
    return None
```

(f) Replace `_record_markdown` with `_record_entity` (path-based class → frontmatter-based class):
```python
def _record_entity(project_root: Path, path: Path, today: date) -> InventoryArtifact | None:
    fm_body = parse_frontmatter(path)
    if fm_body is None:
        return None
    fm, _body = fm_body
    artifact_class = _entity_artifact_class(fm)
    if artifact_class is None:
        return None
    rel_path = path.relative_to(project_root)
    return InventoryArtifact(
        path=str(rel_path),
        artifact_class=artifact_class,
        id=str(fm["id"]) if fm.get("id") else None,
        title=str(fm["title"]) if fm.get("title") else None,
        related_count=_count_entries(fm.get("related")),
        source_refs_count=_count_entries(fm.get("source_refs")),
        modified_days_ago=_modified_days_ago(path, today),
    )
```

(g) Update the discovery loop in `collect_inventory`. Replace the existing markdown loop (the `for path in _collect_markdown_paths(project_root):` block) with:
```python
    for path in _collect_entity_paths(project_root):
        rel_path = path.relative_to(project_root)
        # Any *.md under entities/ without YAML frontmatter is entity-file drift
        # (fb-2026-05-01-002 generalized from doc roots to the canonical home).
        if not _has_frontmatter(path):
            candidate_signals.no_frontmatter_files.append(str(rel_path))
            continue
        record = _record_entity(project_root, path, today)
        if record is None:
            continue
        records.append(record)
        _accumulate_markdown_signals(record, candidate_signals)
```

Leave `_collect_task_paths`, `_record_tasks`, `_collect_knowledge_source_paths`, `_record_knowledge_source`, `_accumulate_markdown_signals`, `_count_entries`, `_load_emergent_threads_orphans`, `_has_frontmatter`, `_modified_days_ago`, and the rest of `collect_inventory` unchanged.

- [ ] **Step 4: Run the tests and confirm they PASS**

Run:
```bash
rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_curate_inventory.py -q
```
Expected: PASS (all tests in the file).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/curate/inventory.py science/tests/test_curate_inventory.py
git commit -m "feat(curate): scan canonical entities/ for inventory, not legacy doc/specs (G2)"
```

---

### Task 2: New-behavior coverage — derivation paths, visibility, drift, no spec class

Add dedicated tests that lock the behaviors a `type:`-only or path-based implementation would miss. These run against the Task 1 implementation; if any fail, fix `inventory.py` minimally to satisfy them (the reference implementation in Task 1 already does).

**Files:**
- Test: `science/tests/test_curate_inventory.py`

- [ ] **Step 1: Add the new tests**

Append to `science/tests/test_curate_inventory.py`:

```python
def test_artifact_class_prefers_type_over_dir_and_id(tmp_path: Path) -> None:
    # `type:` wins even when the dir name and id prefix disagree.
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "entities/questions/m1.md",
        "---\nid: question:m1\ntype: mechanism\ntitle: M\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    cls = {a.path: a.artifact_class for a in inventory.artifacts}
    assert cls["entities/questions/m1.md"] == "mechanism"


def test_artifact_class_falls_back_to_kind_then_id_prefix(tmp_path: Path) -> None:
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    # No `type:` -> use `kind:`.
    _write(
        tmp_path / "entities/findings/f1.md",
        "---\nid: finding:f1\nkind: finding\ntitle: F\n---\nBody.\n",
    )
    # No `type:`/`kind:` -> use the colon-prefixed id prefix.
    _write(
        tmp_path / "entities/observations/o1.md",
        "---\nid: observation:o1\ntitle: O\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    cls = {a.path: a.artifact_class for a in inventory.artifacts}
    assert cls["entities/findings/f1.md"] == "finding"
    assert cls["entities/observations/o1.md"] == "observation"


def test_record_with_frontmatter_but_no_classifiable_kind_is_skipped(tmp_path: Path) -> None:
    # Has frontmatter (so not no_frontmatter) but no type/kind and a bare id ->
    # unclassifiable -> skipped (keys no signal, not counted).
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "entities/misc/x1.md",
        "---\nid: bare-no-colon\ntitle: X\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    assert [a.path for a in inventory.artifacts] == []
    assert inventory.candidate_signals.no_frontmatter_files == []


def test_archived_member_is_absent_from_inventory(tmp_path: Path) -> None:
    # A relocated archived member under entities/_archive/ is skipped by the iterator.
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "entities/_archive/interpretations/old.md",
        "---\nid: interpretation:old\ntype: interpretation\nstatus: archived\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    assert [a.path for a in inventory.artifacts] == []


def test_superseded_status_entity_is_present(tmp_path: Path) -> None:
    # No status filter: a superseded-but-not-relocated entity stays visible so a
    # human can act on it in curate.
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "entities/interpretations/s1.md",
        "---\nid: interpretation:s1\ntype: interpretation\nstatus: superseded\n---\nBody.\n",
    )
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    assert [a.path for a in inventory.artifacts] == ["entities/interpretations/s1.md"]


def test_legacy_specs_and_doc_are_no_longer_scanned(tmp_path: Path) -> None:
    # The retired layout is ignored: a doc/ entity and a depth-2 specs/*.md "spec"
    # contribute nothing.
    _write(tmp_path / "science.yaml", "name: p\nprofile: research\n")
    _write(
        tmp_path / "doc/questions/q9.md",
        "---\nid: question:q9\ntype: question\n---\nBody.\n",
    )
    _write(tmp_path / "specs/overview.md", "---\nid: spec:overview\n---\nBody.\n")
    inventory = collect_inventory(tmp_path, today=date(2026, 4, 21))
    assert [a.path for a in inventory.artifacts] == []
    assert "spec" not in inventory.artifact_counts
```

- [ ] **Step 2: Run the new tests and confirm they PASS**

Run:
```bash
rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_curate_inventory.py -q
```
Expected: PASS (all, including the six new tests). If `test_record_with_frontmatter_but_no_classifiable_kind_is_skipped` or any other fails, the Task 1 implementation diverged from the design — fix `_entity_artifact_class`/`_record_entity` to match the design's derivation rule, then re-run.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_curate_inventory.py
git commit -m "test(curate): lock derivation paths, archive skip, superseded visibility, no-legacy (G2)"
```

---

### Task 3: Register the new scanner in the entity-scan guard

`curate/inventory.py` now scans `entities/` through the SSOT iterator, so it must be listed in the positive guard that asserts every entity scanner uses `iter_entity_markdown`. (The frozen `rglob` ALLOWLIST is **not** touched — inventory only *calls* the iterator; it holds no local `rglob("*.md")`.)

**Files:**
- Test: `science/tests/test_entity_scan_guard.py:52-61`

- [ ] **Step 1: Add `curate/inventory.py` to `ENTITY_SCANNERS`**

In `science/tests/test_entity_scan_guard.py`, add the entry to the `ENTITY_SCANNERS` set (keep it sorted-ish; the set is order-insensitive):
```python
ENTITY_SCANNERS: set[str] = {
    "consolidation.py",
    "curate/inventory.py",
    "graph/storage_adapters/markdown.py",
    "validate/checks/cross_references.py",
    "validate/checks/id_prefixes.py",
    "validate/checks/entity_conformance.py",
    "validate/checks/hypotheses.py",
    "big_picture/validator.py",
    "entities.py",
}
```

Also update the docstring/comment that says "The eight files that scan entities/" to "The nine files that scan entities/" (line ~48).

- [ ] **Step 2: Run the guard and confirm it PASSES**

Run:
```bash
rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest tests/test_entity_scan_guard.py -q
```
Expected: PASS. `test_entity_scanners_use_the_ssot` confirms `curate/inventory.py` contains `iter_entity_markdown`; `test_recursive_md_rglob_inventory_is_frozen` stays green (inventory adds no new `rglob`).

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_entity_scan_guard.py
git commit -m "test(guard): register curate/inventory.py as an entity scanner (G2)"
```

---

### Final verification (after all tasks)

- [ ] **Run the curate + guard + scan-affected suites:**

```bash
rtk env PYTHONPATH=src:model/src ~/d/science/science/.venv/bin/pytest \
  tests/test_curate_inventory.py tests/test_curate_cli.py \
  tests/test_entity_scan_guard.py tests/test_consolidation_candidates.py -q
```
Expected: all pass. `test_curate_cli.py` validates the `science curate inventory` JSON contract is intact; `test_consolidation_candidates.py` confirms the untouched detector still passes.

- [ ] **Sanity-check the CLI shape is unchanged** (optional, manual):
The `science curate inventory` JSON keys (`project_root`, `artifact_counts`, `artifacts`, `candidate_signals`, `agents_md`) and options (`--project-root`, `--format`, `--recently-modified-days`, `--recently-modified-top-k`) are untouched by this plan.

---

## Self-Review (run by plan author)

**Spec coverage** (against the design doc):
- §2 Decision 1 (canonical-only replace) → Task 1 Step 3 (b)/(c)/(d), Task 2 `test_legacy_specs_and_doc_are_no_longer_scanned`.
- §2 Decision 2 (drop `spec` class) → `_markdown_artifact_class` deleted (Task 1), `test_legacy_specs_and_doc_are_no_longer_scanned` asserts no `spec`.
- §3 derivation `type`→`kind`→colon-id, bare-id skip → `_entity_artifact_class` (Task 1), Task 2 derivation tests.
- §3 `no_frontmatter_files` over entities/ → Task 1 loop + migrated Test 6.
- §3 visibility (archive skip; no status filter) → Task 2 archived-absent / superseded-present.
- §3 preserved surfaces (tasks/knowledge/agents_md/emergent-threads/signals/knobs/JSON) → untouched in Task 1; final-verification suite covers CLI + detector.
- §3 scanner-guard registration → Task 3.

**Placeholder scan:** none — every code step shows complete code; every run step shows the exact command and expected result.

**Type consistency:** `_collect_entity_paths`, `_entity_artifact_class`, `_record_entity` names are used consistently across Task 1 steps; `ENTITY_SCANNERS` entry matches the guard's `SRC`-relative path convention (`curate/inventory.py`).
