# Namespace Registry IDs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix false entity deduplication by namespacing canonical IDs in the registry with project names, so `task:t001` in project A and `task:t001` in project B are tracked as distinct entities.

**Architecture:** The registry stores globally-unique IDs in the form `project::local_id` (e.g., `seq-feats::task:t001`). The alignment phase uses these namespaced IDs as the primary key. Cross-project deduplication happens only via the tiered matching logic (aliases, ontology terms, fuzzy title) — never by bare canonical ID collision. A cleanup task removes the stale registry and propagated files from the first (buggy) sync run.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, pytest.

---

## File Structure

### Modified files

```
science-tool/src/science_tool/registry/sync.py           # Namespace IDs in align_registry, run_sync
science-tool/src/science_tool/registry/propagation.py     # Use namespaced IDs in propagation lookups
science-tool/tests/test_registry_sync.py                  # Fix tests + add collision test
science-tool/tests/test_registry_propagation.py           # Fix tests for namespaced IDs
```

---

## Task 1: Namespace IDs in `align_registry`

**Files:**
- Modify: `science-tool/src/science_tool/registry/sync.py:49-81`
- Test: `science-tool/tests/test_registry_sync.py`

The core change: when building the registry entity map, use `project::canonical_id` as the key instead of bare `canonical_id`. The `RegistryEntity.canonical_id` field stores the namespaced form.

- [ ] **Step 1: Write test for ID collision prevention**

Add to `science-tool/tests/test_registry_sync.py`:

```python
def test_align_does_not_merge_same_id_different_projects():
    """task:t001 in proj-a and task:t001 in proj-b are different entities."""
    existing = RegistryIndex()
    project_sources = {
        "proj-a": [_source_entity("task:t001", "task", "Run analysis on dataset X")],
        "proj-b": [_source_entity("task:t001", "task", "Set up CI pipeline")],
    }
    result = align_registry(existing, project_sources)
    # Should have TWO separate entities, not one merged entity
    t001_entries = [e for e in result.entities if "task:t001" in e.canonical_id]
    assert len(t001_entries) == 2
    # Each should have exactly one source project
    for entry in t001_entries:
        assert len(entry.source_projects) == 1
    project_names = {entry.source_projects[0].project for entry in t001_entries}
    assert project_names == {"proj-a", "proj-b"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_sync.py::test_align_does_not_merge_same_id_different_projects -v`
Expected: FAIL — currently merges into 1 entity with 2 source projects

- [ ] **Step 3: Implement namespaced IDs in `align_registry`**

In `science-tool/src/science_tool/registry/sync.py`, change `align_registry`:

```python
def align_registry(
    existing: RegistryIndex,
    project_sources: dict[str, list[SourceEntity]],
) -> RegistryIndex:
    """Phase 2: Align entities across projects into the registry.

    project_sources maps project_name -> list of SourceEntity.
    Registry entities use namespaced IDs: "project::local_id".
    """
    entity_map: dict[str, RegistryEntity] = {e.canonical_id: e for e in existing.entities}

    for project_name, entities in project_sources.items():
        today = date.today()
        for src in entities:
            registry_id = f"{project_name}::{src.canonical_id}"
            if registry_id in entity_map:
                entry = entity_map[registry_id]
                _merge_aliases(entry, src.aliases)
                _merge_ontology_terms(entry, src.ontology_terms)
                _ensure_project_listed(entry, project_name, today)
            else:
                entity_map[registry_id] = RegistryEntity(
                    canonical_id=registry_id,
                    kind=src.kind,
                    title=src.title,
                    profile=src.profile,
                    aliases=list(src.aliases),
                    ontology_terms=list(src.ontology_terms),
                    source_projects=[
                        RegistryEntitySource(project=project_name, first_seen=today),
                    ],
                )

    entities = sorted(entity_map.values(), key=lambda e: e.canonical_id)
    return RegistryIndex(entities=entities, relations=existing.relations)
```

- [ ] **Step 4: Run collision test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_sync.py::test_align_does_not_merge_same_id_different_projects -v`
Expected: PASS

- [ ] **Step 5: Write test for genuine cross-project match via shared semantics**

True deduplication should still work when entities share aliases or ontology terms:

```python
def test_align_genuine_match_via_ontology_terms():
    """Same gene in two projects, different local IDs, matched by ontology term."""
    existing = RegistryIndex()
    project_sources = {
        "proj-a": [_source_entity("gene:tp53", "gene", "TP53", ["p53"], ["NCBIGene:7157"])],
        "proj-b": [_source_entity("gene:tumor-protein-53", "gene", "Tumor Protein 53", [], ["NCBIGene:7157"])],
    }
    result = align_registry(existing, project_sources)
    # These are different local IDs, so they get separate registry entries
    # Cross-project matching happens at a separate layer (matching.py)
    entries_with_ncbi = [e for e in result.entities if "NCBIGene:7157" in e.ontology_terms]
    assert len(entries_with_ncbi) == 2  # separate entries, matching happens elsewhere
```

- [ ] **Step 6: Fix existing `test_align_deduplicates_across_projects` test**

The old test assumed same canonical ID across projects would merge. Update it to use namespaced IDs:

```python
def test_align_deduplicates_within_project():
    """Same entity loaded twice from same project is deduplicated."""
    existing = RegistryIndex()
    project_sources = {
        "proj-a": [
            _source_entity("gene:tp53", "gene", "TP53", ["p53"], ["NCBIGene:7157"]),
            _source_entity("gene:tp53", "gene", "TP53", ["TP53"], ["NCBIGene:7157"]),
        ],
    }
    result = align_registry(existing, project_sources)
    tp53_entries = [e for e in result.entities if "gene:tp53" in e.canonical_id]
    assert len(tp53_entries) == 1
    # Aliases from both loads are merged
    aliases = set(tp53_entries[0].aliases)
    assert "p53" in aliases
    assert "TP53" in aliases
```

- [ ] **Step 7: Update integration tests `test_full_sync_two_projects` and `test_sync_idempotent`**

These tests set up two projects sharing `gene:tp53` by bare ID. After namespacing, matching relies on aliases/ontology terms, so the test projects need these:

```python
def test_full_sync_two_projects(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")

    # Both projects have gene:tp53 with shared ontology term — genuine match
    _write_entity_md(proj_a, "tp53.md", "gene:tp53", "concept", "TP53",
                     ontology_terms=["NCBIGene:7157"], aliases=["p53"])
    _write_entity_md(proj_a, "q1.md", "question:q1", "question", "TP53 question",
                     related=["gene:tp53"])
    _write_entity_md(proj_b, "tp53.md", "gene:tp53", "concept", "TP53",
                     ontology_terms=["NCBIGene:7157"], aliases=["p53"])

    report = run_sync(
        project_paths=[proj_a, proj_b],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
    )

    assert isinstance(report, SyncReport)
    assert report.entities_total > 0
    sync_files = list((proj_b / "doc" / "sync").glob("*.md"))
    assert len(sync_files) >= 1


def test_sync_idempotent(tmp_path: Path) -> None:
    proj_a = tmp_path / "proj-a"
    proj_b = tmp_path / "proj-b"
    _write_project(proj_a, "proj-a")
    _write_project(proj_b, "proj-b")
    _write_entity_md(proj_a, "tp53.md", "gene:tp53", "concept", "TP53",
                     ontology_terms=["NCBIGene:7157"], aliases=["p53"])
    _write_entity_md(proj_b, "tp53.md", "gene:tp53", "concept", "TP53",
                     ontology_terms=["NCBIGene:7157"], aliases=["p53"])
    _write_entity_md(proj_a, "q1.md", "question:q1", "question", "Q1", related=["gene:tp53"])

    kwargs: dict[str, object] = dict(
        project_paths=[proj_a, proj_b],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
    )
    run_sync(**kwargs)  # type: ignore[arg-type]
    run_sync(**kwargs)  # type: ignore[arg-type]
    sync_files = list((proj_b / "doc" / "sync").glob("*.md"))
    assert len(sync_files) <= 1
```

- [ ] **Step 8: Add test for re-sync with existing namespaced registry**

```python
def test_resync_with_existing_namespaced_registry(tmp_path: Path) -> None:
    """Second sync run with pre-existing namespaced registry doesn't create duplicates."""
    proj_a = tmp_path / "proj-a"
    _write_project(proj_a, "proj-a")
    _write_entity_md(proj_a, "q1.md", "question:q1", "question", "Question 1")

    kwargs: dict[str, object] = dict(
        project_paths=[proj_a],
        state_path=tmp_path / "sync_state.yaml",
        registry_dir=tmp_path / "registry",
    )
    report1 = run_sync(**kwargs)  # type: ignore[arg-type]
    report2 = run_sync(**kwargs)  # type: ignore[arg-type]
    # Entity count should be identical — no duplicates from re-indexing
    assert report1.entities_total == report2.entities_total
    assert report2.entities_new == 0
```

- [ ] **Step 9: Run all sync tests**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_sync.py -v`
Expected: All PASS

- [ ] **Step 10: Commit**

```bash
git add science-tool/src/science_tool/registry/sync.py \
       science-tool/tests/test_registry_sync.py
git commit -m "fix(registry): namespace entity IDs to prevent false cross-project dedup"
```

---

## Task 2: Update propagation for namespaced IDs

**Files:**
- Modify: `science-tool/src/science_tool/registry/propagation.py:27-69`
- Modify: `science-tool/src/science_tool/registry/sync.py:144-149` (shared entity detection)
- Modify: `science-tool/src/science_tool/registry/checks.py` (document behavior change)
- Test: `science-tool/tests/test_registry_propagation.py`
- Test: `science-tool/tests/test_registry_sync.py` (integration)

Propagation now needs to account for the fact that registry IDs are namespaced but entity `related` fields use local IDs. The shared entity detection and propagation lookups need updating.

**Key design decisions:**
- `_find_cross_project_matches` returns 4-tuples `(local_id_a, local_id_b, project_a, project_b)` to capture both sides of the match
- Matching runs in both directions (A→B and B→A) to avoid asymmetry
- `compute_propagations` checks both local IDs against `entity.related`
- Entities with identical local IDs but no aliases/ontology terms will NOT match cross-project — this is intentional; cross-project matching requires semantic evidence
- Proactive checks (`checks.py`) continue to work via alias/ontology matching; Tier 1 exact is effectively disabled for cross-project lookups since registry IDs are namespaced

- [ ] **Step 1: Update shared entity detection in `run_sync`**

In `sync.py`, replace the shared entity detection in `run_sync`:

```python
from science_tool.registry.matching import MatchTier, find_matches

# Phase 3: Propagate — find genuinely shared entities via matching
shared_pairs = _find_cross_project_matches(new_index, project_entity_map)
actions = compute_propagations(
    shared_pairs=shared_pairs,
    project_sources=project_entity_map,
)
```

Add a helper function that checks **both directions** and returns 4-tuples:

```python
def _find_cross_project_matches(
    index: RegistryIndex,
    project_sources: dict[str, list[SourceEntity]],
) -> list[tuple[str, str, str, str]]:
    """Find entity pairs that match across projects.

    Returns list of (local_id_a, local_id_b, project_a, project_b) tuples.
    Only tiers 1-3 (exact, alias, ontology) count as genuine matches.
    Checks both directions to avoid asymmetric matching.

    Note: O(P^2 * E_a * E_b) — acceptable for single-user with a handful of projects.
    """
    seen: set[tuple[str, str, str, str]] = set()
    project_names = list(project_sources.keys())

    for i, proj_a in enumerate(project_names):
        for proj_b in project_names[i + 1:]:
            entities_b_registry = [
                e for e in index.entities
                if e.source_projects and e.source_projects[0].project == proj_b
            ]
            entities_a_registry = [
                e for e in index.entities
                if e.source_projects and e.source_projects[0].project == proj_a
            ]

            # Direction A → B: check proj_a sources against proj_b registry entries
            for src_a in project_sources[proj_a]:
                results = find_matches(
                    src_a.canonical_id,
                    aliases=src_a.aliases,
                    ontology_terms=src_a.ontology_terms,
                    registry_entities=entities_b_registry,
                    candidate_kind=src_a.kind,
                    candidate_title=src_a.title,
                )
                for result in results:
                    if result.tier <= MatchTier.ONTOLOGY:
                        # Extract local ID from namespaced registry ID
                        local_id_b = result.entity.canonical_id.split("::", 1)[-1]
                        key = (src_a.canonical_id, local_id_b, proj_a, proj_b)
                        seen.add(key)

            # Direction B → A: check proj_b sources against proj_a registry entries
            for src_b in project_sources[proj_b]:
                results = find_matches(
                    src_b.canonical_id,
                    aliases=src_b.aliases,
                    ontology_terms=src_b.ontology_terms,
                    registry_entities=entities_a_registry,
                    candidate_kind=src_b.kind,
                    candidate_title=src_b.title,
                )
                for result in results:
                    if result.tier <= MatchTier.ONTOLOGY:
                        local_id_a = result.entity.canonical_id.split("::", 1)[-1]
                        key = (local_id_a, src_b.canonical_id, proj_a, proj_b)
                        seen.add(key)

    return list(seen)
```

- [ ] **Step 2: Update `compute_propagations` signature**

In `propagation.py`, change `compute_propagations` to work with 4-tuple match pairs and check **both** local IDs against `entity.related`:

```python
def compute_propagations(
    *,
    shared_pairs: list[tuple[str, str, str, str]],  # (local_id_a, local_id_b, project_a, project_b)
    project_sources: dict[str, list[SourceEntity]],
) -> list[PropagationAction]:
    """Compute which entities should be propagated across projects.

    shared_pairs: list of (local_id_a, local_id_b, project_a, project_b) indicating
    that the two local IDs represent the same real-world entity across projects.
    """
    project_ids: dict[str, set[str]] = {
        name: {e.canonical_id for e in entities} for name, entities in project_sources.items()
    }

    # Build lookup: for each project, which local IDs are involved in cross-project sharing
    # and which other projects share them
    SharedInfo = tuple[set[str], set[str]]  # (local_ids_in_this_project, partner_projects)
    project_shared: dict[str, dict[str, set[str]]] = {}  # project -> local_id -> set of partner projects

    for local_id_a, local_id_b, proj_a, proj_b in shared_pairs:
        project_shared.setdefault(proj_a, {}).setdefault(local_id_a, set()).add(proj_b)
        project_shared.setdefault(proj_b, {}).setdefault(local_id_b, set()).add(proj_a)

    # Collect all shared local IDs per project pair for related-field checking
    all_shared_local_ids: set[str] = set()
    for local_id_a, local_id_b, _, _ in shared_pairs:
        all_shared_local_ids.add(local_id_a)
        all_shared_local_ids.add(local_id_b)

    actions: list[PropagationAction] = []

    for source_project, entities in project_sources.items():
        shared_in_project = project_shared.get(source_project, {})
        if not shared_in_project:
            continue

        for entity in entities:
            if not _is_propagatable(entity):
                continue

            # Check if this entity references any shared local ID
            referenced_shared = all_shared_local_ids & set(entity.related)
            if not referenced_shared:
                continue

            # Find which target projects to propagate to
            target_projects: set[str] = set()
            for ref_id in referenced_shared:
                if ref_id in shared_in_project:
                    target_projects.update(shared_in_project[ref_id])

            for target_project in target_projects:
                if entity.canonical_id in project_ids.get(target_project, set()):
                    continue
                actions.append(
                    PropagationAction(
                        source_project=source_project,
                        target_project=target_project,
                        entity=entity,
                        shared_via=next(iter(referenced_shared)),
                    )
                )

    return actions
```

- [ ] **Step 3: Update propagation tests**

In `test_registry_propagation.py`, update all tests to use `shared_pairs` 4-tuples:

```python
def test_propagation_finds_cross_project_content():
    shared_pairs = [("gene:tp53", "gene:tp53", "proj-a", "proj-b")]
    project_sources = {
        "proj-a": [_source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])],
        "proj-b": [],
    }
    actions = compute_propagations(shared_pairs=shared_pairs, project_sources=project_sources)
    assert len(actions) == 1
    assert actions[0].source_project == "proj-a"
    assert actions[0].target_project == "proj-b"


def test_propagation_with_different_local_ids():
    """Entities matched via ontology with different local IDs should propagate."""
    shared_pairs = [("gene:tp53", "gene:tumor-protein-53", "proj-a", "proj-b")]
    project_sources = {
        "proj-a": [_source_entity("question:q1", "question", "Q about TP53", ["gene:tp53"])],
        "proj-b": [_source_entity("question:q2", "question", "Q about TP53 in proj-b", ["gene:tumor-protein-53"])],
    }
    actions = compute_propagations(shared_pairs=shared_pairs, project_sources=project_sources)
    # q1 should propagate to proj-b (references gene:tp53 which matches gene:tumor-protein-53)
    # q2 should propagate to proj-a (references gene:tumor-protein-53 which matches gene:tp53)
    assert len(actions) == 2
```

Update all remaining propagation tests (`test_propagation_skips_already_present`, `test_propagation_skips_sync_sourced_entities`, `test_propagation_tag_gated_task`, `test_propagation_excludes_non_propagatable_types`) to use `shared_pairs=[(id, id, "proj-a", "proj-b")]` format.

- [ ] **Step 4: Add `::` validation to `align_registry`**

At the top of `align_registry`, validate project names don't contain `::`:

```python
for project_name in project_sources:
    if "::" in project_name:
        raise ValueError(f"Project name must not contain '::': {project_name!r}")
```

- [ ] **Step 5: Document `checks.py` behavior**

Add a docstring note to `check_registry` in `checks.py`:

```python
    """Check if an entity matches anything in the registry.

    Read-only, advisory. After registry namespacing, Tier 1 (exact canonical ID)
    matching is effectively disabled for cross-project lookups since registry entities
    use namespaced IDs (project::local_id). Matching still works via Tier 2 (aliases)
    and Tier 3 (ontology terms).
    """
```

- [ ] **Step 6: Run all tests**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add science-tool/src/science_tool/registry/sync.py \
       science-tool/src/science_tool/registry/propagation.py \
       science-tool/src/science_tool/registry/checks.py \
       science-tool/tests/test_registry_propagation.py
git commit -m "fix(registry): update propagation for namespaced IDs with bidirectional matching"
```

---

## Task 3: Update entity hash computation

**Files:**
- Modify: `science-tool/src/science_tool/registry/sync.py:172`

- [ ] **Step 1: Update hash to use namespaced IDs**

In `run_sync`, the entity hash should use namespaced IDs for consistency:

```python
for sources in all_sources:
    ids = [f"{sources.project_name}::{e.canonical_id}" for e in sources.entities]
    state.projects[sources.project_name] = ProjectSyncState(
        last_synced=now,
        entity_count=len(ids),
        entity_hash=compute_entity_hash(ids),
    )
```

- [ ] **Step 2: Run tests**

Run: `cd science-tool && uv run --frozen pytest tests/test_registry_sync.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add science-tool/src/science_tool/registry/sync.py
git commit -m "fix(registry): use namespaced IDs in entity hash computation"
```

---

## Task 4: Clean up stale registry and propagated files

**IMPORTANT:** This task MUST run before the next `/sync` invocation. Old un-namespaced registry entries would create duplicates alongside new namespaced entries.

**Files:** No code changes — operational cleanup.

- [ ] **Step 1: Remove stale registry**

```bash
rm -rf ~/.config/science/registry/
rm -f ~/.config/science/sync_state.yaml
```

- [ ] **Step 2: Remove incorrectly propagated files**

```bash
rm -rf ~/d/seq-feats/doc/sync/
rm -rf ~/d/3d-attention-bias/doc/sync/
```

- [ ] **Step 3: Verify cleanup**

```bash
ls ~/.config/science/registry/ 2>/dev/null && echo "registry still exists" || echo "registry cleaned"
ls ~/d/seq-feats/doc/sync/ 2>/dev/null && echo "sync dir exists" || echo "cleaned"
ls ~/d/3d-attention-bias/doc/sync/ 2>/dev/null && echo "sync dir exists" || echo "cleaned"
```

- [ ] **Step 4: Commit cleanup in affected projects**

In each project that had propagated files, commit the removal:

```bash
cd ~/d/seq-feats && git add -A && git commit -m "chore: remove incorrectly propagated sync entities"
cd ~/d/3d-attention-bias && git add -A && git commit -m "chore: remove incorrectly propagated sync entities"
```

---

## Task 5: Final verification

- [ ] **Step 1: Run full science-tool test suite**

Run: `cd science-tool && uv run --frozen pytest -v`
Expected: All PASS

- [ ] **Step 2: Run ruff**

Run: `cd science-tool && uv run --frozen ruff check . && uv run --frozen ruff format --check .`
Expected: Clean

- [ ] **Step 3: Commit any remaining cleanup**

```bash
git add -A && git commit -m "chore: final cleanup for namespaced registry IDs"
```
