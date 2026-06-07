# Phase 2a — Dataset Promotion + Members-Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote orphan datapackages to real `entities/datasets/<id>.md` owner files, and fix the geneset `members_resource` extraction gate so promotion (a markdown owner shadowing a geneset datapackage) never silently drops member extraction.

**Architecture:** Three surgical changes routed through the compiled model (design §C2). (1) The loader records, at datapackage **defer** time, the datapackage path it currently discards — exposed as `ProjectSources.dataset_datapackages`. (2) Both geneset member gates (`materialize.py`, `migrate.py`) locate a dataset's geneset resource frontmatter via that map instead of keying off the *winning* adapter tag — so geneset resource metadata stays in the datapackage (§B4) and a promoted markdown owner still extracts members. (3) A new `science data-package promote-orphans` command writes a real owner `.md` from each orphan datapackage's entity fields plus a `datapackage:` pointer, leaving the datapackage in place as the attachment; idempotent.

**Tech Stack:** Python 3.12/3.13, pydantic v2, click, PyYAML, pytest. Library at `~/d/science/science/` (`src/science_tool/`, `model/src/science_model/`, `tests/`). Tests run via `cd ~/d/science/science && uv run --frozen pytest`. Lint: `uv run --frozen ruff check .` and `uv run --frozen ruff format --check .` (120-char line limit).

---

## Background & invariants (read before starting)

This is **Phase 2a** of the substrate redesign (consolidated design: `~/d/science/docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md`, §B4 + §C). Design Phase 1 (the "compiler seam") is complete and merged. Phase 1.5 made a `datapackage.yaml` **defer** to any existing same-scope owner: in `science/src/science_tool/graph/sources.py` the adapter loop at lines 387–397 does

```python
owner_scope, deprecated = classify_owner_scope(adapter.name, project_name=project_name)
if isinstance(adapter, DatapackageAdapter) and entity.canonical_id in identity_table:
    # §B4: a datapackage is attached resource metadata, not a second owner. ...DEFERS...
    continue
```

So today: a **true orphan** datapackage (no entity-file owner) becomes the owner itself (`entity_source_adapters[id] == "datapackage"`, deprecated transitional row); a datapackage **with** an owner defers and emits nothing.

**The two problems Phase 2a fixes:**

1. **Promotion does not exist.** There is no tool to turn an orphan datapackage into a real `entities/datasets/<id>.md` owner. The `orphan-datapackage-owner` conformance check (`science/src/science_tool/validate/checks/orphan_datapackage_owner.py`) only *flags* them.

2. **Footgun (a) — silent geneset-member loss on promotion.** The geneset member gate keys off the *winning* adapter tag:

   - `science/src/science_tool/graph/materialize.py:671` and `science/src/science_tool/graph/migrate.py:231` both do
     `if sources.entity_source_adapters.get(entity.canonical_id) not in {"datapackage", "commons-merged"}: continue`.
   - A true orphan geneset datapackage is tagged `"datapackage"` → gate passes → members extract.
   - **After promotion**, the datapackage defers and the owner is a `.md` → tagged `"markdown"` → gate **skips** → members silently disappear from the graph.

**The fix's shape.** A datapackage's geneset resource metadata (`schema_profile`, `members_resource`, `resources`, …) *stays in the datapackage* (§B4: "datapackage is attached resource metadata"); the promoted `.md` is the identity owner and carries a `datapackage:` pointer. The loader already *sees* the datapackage path when it defers (the `ref` at `sources.py:387`) — it just discards it. We record it as `ProjectSources.dataset_datapackages[id] = ref.path`, and the gate reads the geneset frontmatter from that path. This is the minimum that keeps member extraction working regardless of which adapter won the owner column.

**Reference helper that resolves member CSVs** (`science/src/science_tool/commons/geneset_resources.py`):
- `geneset_resource_frontmatter(project_root, entity_path)` (line 23) — reads frontmatter at `entity_path`; returns it (with `_path` set to the source) iff geneset-shaped, else `None`. `is_geneset_frontmatter(fm)` (in `commons/geneset.py:47`) returns `(fm.get("kind") or fm.get("type")) == "dataset"` AND the `schema_profile` contains the geneset token.
- `read_member_rows(project_root, fm)` (line 86) — resolves `fm["_path"]` + `fm["members_resource"]` into the member CSV (datapackage `resources[].path`), falling back to the commons resolver.

**Existing owner-file template** (`science/src/science_tool/datasets_register.py:108`, `_entity_yaml_block`) shows the exact owner shape, **including the `datapackage:` pointer** (line 134: `f'datapackage: "{dp_path_rel}"\n'`) and `created`/`updated` (lines 143–144). The `datapackage:` pointer convention is also consumed by `cli.py:4902` (`fm.get("datapackage")`). Promotion produces the same shape but derives `origin`/`access`/`derivation` from the real datapackage instead of hard-coding `origin: derived`.

**Undated sentinel.** `migrate_layout` blocks `--apply` when any `created == "9999-99-99"` (the undated sentinel; `entity_layout_migration.py` undated gate). Promotion reuses this sentinel when a datapackage carries no `created`, so the same gate surfaces the gap rather than inventing provenance.

**Scope guard — explicitly OUT of Phase 2a (deferred to 2b):**
- Do **not** flip the orphan rule from "synthesize + warn" to hard error. The `orphan-datapackage-owner` check stays WARN (ERROR at `layout_version >= 3`) unchanged.
- Do **not** add the "forbid a second declaration" conformance guard.
- Do **not** add datapackage `resources → PROV-triple` attachment beyond what already compiles.
- Do **not** touch `commons_sources.py:220` (the *third* `geneset_resource_frontmatter` caller — a commons-loading path, different context).
- Do **not** slim resource fields out of the datapackage, and do **not** delete datapackages.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/graph/sources.py` | Compile authoring inputs into `ProjectSources` | Add `dataset_datapackages` field + accumulator; record datapackage path at defer time |
| `science/src/science_tool/commons/geneset_resources.py` | Geneset resource/member resolution helpers | Add `dataset_geneset_frontmatter(...)` — adapter-tag-agnostic source resolution |
| `science/src/science_tool/graph/materialize.py` | Materialize project graph | Route the geneset gate through the new helper |
| `science/src/science_tool/graph/migrate.py` | Audit project references | Route the geneset audit gate through the new helper (audit/materialize symmetry) |
| `science/src/science_tool/datapackage_promote.py` | **NEW** — orphan→owner promotion | Plan + write `entities/datasets/<id>.md` from orphan datapackages |
| `science/src/science_tool/cli.py` | CLI | **NEW** `data-package promote-orphans` subcommand |
| `science/tests/test_load_project_sources_unified.py` | Loader tests | `dataset_datapackages` population tests |
| `science/tests/test_commons_geneset.py` | Geneset resource helper tests | `dataset_geneset_frontmatter` unit tests |
| `science/tests/test_dataset_usage_materialize.py` | Geneset materialization + materialization-audit tests | Promoted-geneset regression guard (footgun a) + provenance assertion |
| `science/tests/test_datapackage_promote.py` | **NEW** — promotion tests | Plan/apply/idempotency/e2e |

---

### Task 1: Record the datapackage path at defer time (`dataset_datapackages` map)

**Files:**
- Modify: `science/src/science_tool/graph/sources.py` (ProjectSources model ~`:141-160`; accumulator ~`:273`; defer branch `:387-397`; constructor ~`:551`)
- Test: `science/tests/test_load_project_sources_unified.py`

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_load_project_sources_unified.py`. Reuse the project-scaffolding idiom already in that file (look at `test_datapackage_defers_to_markdown_owner` / `test_datapackage_defers_to_aggregate_stub_owner` for the exact `_write` / manifest helpers used there, and mirror them — do not invent a new scaffolding style).

```python
def test_dataset_datapackages_records_deferred_datapackage_path(tmp_path):
    # A real markdown dataset owner + a same-id datapackage.yaml. The datapackage
    # defers (§B4); its path must be recorded on ProjectSources.dataset_datapackages
    # so the geneset member gate can find it after the markdown owner wins.
    _scaffold_project(tmp_path)  # use this file's existing project scaffolder
    _write(tmp_path / "entities/datasets/x.md",
        '---\n'
        'id: "dataset:x"\n'
        'type: "dataset"\n'
        'title: "X md"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n'
        'created: "2026-01-01"\n'
        'updated: "2026-01-01"\n'
        '---\n')
    _write(tmp_path / "data/x/datapackage.yaml",
        'profiles: ["science-pkg-entity-1.0"]\n'
        'id: "dataset:x"\n'
        'type: "dataset"\n'
        'title: "X dp"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n')

    sources = load_project_sources(tmp_path, include_commons=False,
                                   strict_core_schema=False, strict_identity=False)

    assert sources.dataset_datapackages == {"dataset:x": "data/x/datapackage.yaml"}
    # The markdown owner won; the datapackage emitted no owner declaration.
    assert sources.entity_source_adapters["dataset:x"] == "markdown"


def test_dataset_datapackages_excludes_true_orphan(tmp_path):
    # A datapackage with no entity-file owner IS the owner (a true orphan). It is
    # not "deferred", so it must NOT appear in dataset_datapackages.
    _scaffold_project(tmp_path)
    _write(tmp_path / "data/y/datapackage.yaml",
        'profiles: ["science-pkg-entity-1.0"]\n'
        'id: "dataset:y"\n'
        'type: "dataset"\n'
        'title: "Y dp"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n')

    sources = load_project_sources(tmp_path, include_commons=False,
                                   strict_core_schema=False, strict_identity=False)

    assert "dataset:y" not in sources.dataset_datapackages
    assert sources.entity_source_adapters["dataset:y"] == "datapackage"
```

> NOTE TO IMPLEMENTER: `_scaffold_project` / `_write` are placeholders for *this test file's existing* scaffolding helpers. Open the file first, find how `test_datapackage_defers_to_markdown_owner` builds its project (manifest, `knowledge_profiles`, profile dirs), and use the identical mechanism. If that test inlines the scaffolding, inline it here too.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_load_project_sources_unified.py -k dataset_datapackages -v`
Expected: FAIL — `AttributeError: 'ProjectSources' object has no attribute 'dataset_datapackages'`.

- [ ] **Step 3: Add the `dataset_datapackages` field to `ProjectSources`**

In `science/src/science_tool/graph/sources.py`, in the `ProjectSources` model (after `entity_source_adapters` at line 150):

```python
    entity_source_adapters: dict[str, str] = Field(default_factory=dict)
    # §B4: id -> rel path of a datapackage.yaml that DEFERRED to an existing owner.
    # The owner won the owner column, but member-resource resolution still needs the
    # datapackage path (the geneset member CSV lives there, not in the owner file).
    dataset_datapackages: dict[str, str] = Field(default_factory=dict)
```

- [ ] **Step 4: Declare the accumulator and record at defer time**

In `load_project_sources`, next to the other accumulators (~line 273, alongside `entity_source_adapters: dict[str, str] = {}`):

```python
    entity_source_adapters: dict[str, str] = {}
    dataset_datapackages: dict[str, str] = {}
```

Then in the defer branch (currently lines 387–397), record the path **before** `continue`:

```python
                if isinstance(adapter, DatapackageAdapter) and entity.canonical_id in identity_table:
                    # §B4: a datapackage is attached resource metadata, not a second
                    # owner. Its id already has an owner recorded this load ... so it
                    # DEFERS: emit no competing owner declaration and no duplicate entity.
                    # Record its path so the geneset member gate can still locate the
                    # datapackage's resources after the owner (markdown) wins the column.
                    dataset_datapackages[entity.canonical_id] = ref.path
                    continue
```

(Keep the rest of the existing comment block; only add the `dataset_datapackages[...] = ref.path` line and a sentence about why.)

- [ ] **Step 5: Pass the accumulator into the `ProjectSources(...)` constructor**

At the `ProjectSources(...)` construction (~line 551, where `entity_source_adapters=entity_source_adapters,` is passed):

```python
        entity_source_adapters=entity_source_adapters,
        dataset_datapackages=dataset_datapackages,
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_load_project_sources_unified.py -k dataset_datapackages -v`
Expected: PASS (both).

- [ ] **Step 7: Run the full loader suite + lint (no regression)**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_load_project_sources_unified.py -q && uv run --frozen ruff check src/science_tool/graph/sources.py`
Expected: all pass, no lint errors.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/graph/sources.py science/tests/test_load_project_sources_unified.py
git commit -m "feat(substrate): record deferred datapackage paths on ProjectSources (§B4 2a)"
```

---

### Task 2: Adapter-tag-agnostic geneset member gate

**Files:**
- Modify: `science/src/science_tool/commons/geneset_resources.py` (add helper after `geneset_resource_frontmatter`, ~`:33`)
- Modify: `science/src/science_tool/graph/materialize.py` (import `:25`; gate `:666-690`)
- Modify: `science/src/science_tool/graph/migrate.py` (import `:17`; gate `:228-256`)
- Test: `science/tests/test_commons_geneset.py` (unit), `science/tests/test_dataset_usage_materialize.py` (integration/regression)

- [ ] **Step 1: Write the failing unit tests for the helper**

Add to `science/tests/test_commons_geneset.py`:

```python
from science_tool.commons.geneset_resources import dataset_geneset_frontmatter


def _write_geneset_datapackage(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        'profiles: ["science-pkg-entity-1.0"]\n'
        'id: "dataset:gs"\n'
        'type: "dataset"\n'
        'title: "GS"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: true\n'
        'schema_profile: "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0"\n'
        'member_key_column: "set_key"\n'
        'members_resource: "sets"\n'
        'resources:\n'
        '  - name: "sets"\n'
        '    path: "sets.csv"\n',
        encoding="utf-8",
    )


def test_dataset_geneset_frontmatter_orphan_reads_entity_path(tmp_path):
    # entity IS the datapackage (orphan): adapter tag "datapackage" -> read entity_path.
    dp = tmp_path / "data/gs/datapackage.yaml"
    _write_geneset_datapackage(dp)
    fm = dataset_geneset_frontmatter(
        tmp_path, "data/gs/datapackage.yaml",
        entity_adapter="datapackage", datapackage_rel=None,
    )
    assert fm is not None
    assert fm["members_resource"] == "sets"
    assert fm["_path"] == "data/gs/datapackage.yaml"


def test_dataset_geneset_frontmatter_promoted_reads_datapackage_rel(tmp_path):
    # Promoted: a markdown owner won (adapter "markdown"), datapackage deferred.
    # The geneset shape lives in the datapackage, located via datapackage_rel.
    _write_geneset_datapackage(tmp_path / "data/gs/datapackage.yaml")
    fm = dataset_geneset_frontmatter(
        tmp_path, "entities/datasets/gs.md",
        entity_adapter="markdown", datapackage_rel="data/gs/datapackage.yaml",
    )
    assert fm is not None
    assert fm["members_resource"] == "sets"
    assert fm["_path"] == "data/gs/datapackage.yaml"


def test_dataset_geneset_frontmatter_no_datapackage_returns_none(tmp_path):
    # A plain markdown dataset with no attached datapackage -> None (skip).
    fm = dataset_geneset_frontmatter(
        tmp_path, "entities/datasets/plain.md",
        entity_adapter="markdown", datapackage_rel=None,
    )
    assert fm is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_geneset.py -k dataset_geneset_frontmatter -v`
Expected: FAIL — `ImportError: cannot import name 'dataset_geneset_frontmatter'`.

- [ ] **Step 3: Implement the helper**

In `science/src/science_tool/commons/geneset_resources.py`, add immediately after `geneset_resource_frontmatter` (after line 33):

```python
def dataset_geneset_frontmatter(
    project_root: Path,
    entity_path: str | Path,
    *,
    entity_adapter: str | None,
    datapackage_rel: str | None,
) -> dict[str, Any] | None:
    """Geneset resource frontmatter for a dataset entity, independent of which
    adapter won the owner column (design §B4).

    A datapackage's geneset resource metadata stays in the datapackage; a promoted
    markdown owner does not duplicate it. So member extraction reads the geneset
    shape from the datapackage:

    - the entity IS the datapackage (orphan) or a commons-merged dataset → read from
      the entity's own source path (preserves prior behavior);
    - a real owner with a deferred datapackage attachment → read from the recorded
      datapackage path (``datapackage_rel``);
    - no datapackage attachment → ``None`` (not a geneset dataset).
    """
    if entity_adapter in {"datapackage", "commons-merged"}:
        source: str | Path = entity_path
    elif datapackage_rel is not None:
        source = datapackage_rel
    else:
        return None
    return geneset_resource_frontmatter(project_root, source)
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_commons_geneset.py -k dataset_geneset_frontmatter -v`
Expected: PASS (all three).

- [ ] **Step 5: Route the materialize gate through the helper**

In `science/src/science_tool/graph/materialize.py`:

Update the import at line 25:
```python
from science_tool.commons.geneset_resources import dataset_geneset_frontmatter, read_member_rows
```
(Drop `geneset_resource_frontmatter` from this import — confirm it is not used elsewhere in the file with `grep -n geneset_resource_frontmatter science/src/science_tool/graph/materialize.py`; it should appear only in the gate you are replacing.)

Replace the gate in `_geneset_usage_records` (lines 669–673). **Before:**
```python
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        if sources.entity_source_adapters.get(entity.canonical_id) not in {"datapackage", "commons-merged"}:
            continue
        fm = geneset_resource_frontmatter(project_root, entity.file_path)
        if fm is None:
            continue
```
**After:**
```python
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        fm = dataset_geneset_frontmatter(
            project_root,
            entity.file_path,
            entity_adapter=sources.entity_source_adapters.get(entity.canonical_id),
            datapackage_rel=sources.dataset_datapackages.get(entity.canonical_id),
        )
        if fm is None:
            continue
```

Then **also** fix the usage-record provenance further down in the same function. The
`usage_records_for_geneset_rows(...)` call (currently line 685–690) passes
`source_path=entity.file_path`. After promotion that is the markdown owner, but the
members resource lives in the datapackage. `geneset_resource_frontmatter` recorded
the actual source as `fm["_path"]`, so cite that. **Before:**
```python
        yield from usage_records_for_geneset_rows(
            collection_id=entity.canonical_id,
            source_path=entity.file_path,
            rows=rows,
            resolve_dataset_ref=lambda raw_ref: _resolve_dataset_usage_ref(raw_ref, resolver),
        )
```
**After:**
```python
        yield from usage_records_for_geneset_rows(
            collection_id=entity.canonical_id,
            # Cite the resource's real source (the datapackage), not whichever owner
            # won the column — fm["_path"] is the datapackage for a promoted owner and
            # is identical to entity.file_path for an orphan datapackage (no change).
            source_path=str(fm["_path"]),
            rows=rows,
            resolve_dataset_ref=lambda raw_ref: _resolve_dataset_usage_ref(raw_ref, resolver),
        )
```

> NOTE: for the orphan-datapackage and most commons-merged cases `fm["_path"]` equals
> the previous `entity.file_path`, so existing provenance is unchanged. The one case
> it shifts is a commons-merged dataset whose `file_path` is an `entity.md` (there
> `fm["_path"]` becomes the sibling `datapackage.yaml` — the more correct source). If
> an existing test asserts the old `entity.md` provenance, update it to the
> datapackage path; the new value is correct. Do NOT change the `migrate.py` audit
> gate's provenance — it reports the owning dataset entity, which is correct there.

- [ ] **Step 6: Route the migrate audit gate through the helper (audit/materialize symmetry)**

In `science/src/science_tool/graph/migrate.py`:

Update the import at line 17:
```python
from science_tool.commons.geneset_resources import dataset_geneset_frontmatter, read_member_rows
```
(Same check: `grep -n geneset_resource_frontmatter science/src/science_tool/graph/migrate.py` — only the gate.)

Replace the gate in `_audit_geneset_row_dataset_usage` (lines 228–234). **Before:**
```python
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        if sources.entity_source_adapters.get(entity.canonical_id) not in {"datapackage", "commons-merged"}:
            continue
        fm = geneset_resource_frontmatter(project_root, entity.file_path)
        if fm is None:
            continue
```
**After:**
```python
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        fm = dataset_geneset_frontmatter(
            project_root,
            entity.file_path,
            entity_adapter=sources.entity_source_adapters.get(entity.canonical_id),
            datapackage_rel=sources.dataset_datapackages.get(entity.canonical_id),
        )
        if fm is None:
            continue
```

- [ ] **Step 7: Write the materialize regression guard (footgun a)**

Add to `science/tests/test_dataset_usage_materialize.py` (this is where the geneset
materialization **and** materialization-audit tests live — there is no
`test_graph_materialize.py` for genesets). Study the existing geneset-materialization
test in that file first (search for `members_resource` / `geneset` / a
datapackage-backed dataset) and mirror its graph-assertion idiom (which triple/edge
it checks for a geneset member, and how it asserts the usage-record `source_path`).
The new test asserts that the **same** geneset member edges appear — with provenance
pointing at the **datapackage** — when the dataset owner is a **markdown** file
shadowing the datapackage (the post-promotion steady state).

```python
def test_geneset_members_extracted_when_markdown_owner_shadows_datapackage(tmp_path):
    # Footgun (a) regression guard: after promotion a markdown owner wins the owner
    # column (adapter "markdown"), the geneset datapackage defers. Member extraction
    # must still happen via dataset_datapackages, not be skipped on the adapter tag,
    # and the usage provenance must cite the datapackage (where the members live).
    _scaffold_geneset_project(tmp_path)  # mirror the existing geneset materialize test

    # Real markdown owner at entities/datasets/<id>.md (identity only + datapackage ptr)
    _write(tmp_path / "entities/datasets/gs.md",
        '---\n'
        'id: "dataset:gs"\n'
        'type: "dataset"\n'
        'title: "GS"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: true\n'
        'datapackage: "data/gs/datapackage.yaml"\n'
        'created: "2026-01-01"\n'
        'updated: "2026-01-01"\n'
        '---\n')
    # Geneset resource metadata stays in the datapackage; members CSV next to it.
    _write_geneset_datapackage_with_members(tmp_path / "data/gs")

    graph = _materialize(tmp_path)  # use this file's existing materialize entrypoint

    # (1) Member usage edge(s) present — copy the exact triple/URI check from the
    #     existing orphan-geneset materialize test.
    assert _has_geneset_member_edges(graph, "dataset:gs")
    # (2) Provenance cites the datapackage, not the markdown owner (Medium finding).
    #     Use the same provenance-inspection the existing test uses; the source must
    #     resolve to data/gs/datapackage.yaml, NOT entities/datasets/gs.md.
    assert _geneset_usage_source(graph, "dataset:gs").endswith("data/gs/datapackage.yaml")
```

> NOTE TO IMPLEMENTER: `_scaffold_geneset_project`, `_write_geneset_datapackage_with_members`, `_materialize`, `_has_geneset_member_edges`, `_geneset_usage_source` are placeholders for the equivalents already in `test_dataset_usage_materialize.py`. There is already a passing test that materializes a geneset from an **orphan/datapackage-tagged** dataset; clone its fixtures and its member-edge/provenance assertions exactly, changing only the owner to a markdown file + datapackage as above. If the existing test inspects usage-record provenance differently (e.g. a `prov:` triple or a record field), use that mechanism for assertion (2).

- [ ] **Step 8: Run to verify the guard passes and nothing regressed**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_dataset_usage_materialize.py tests/test_commons_geneset.py -q`
(`test_dataset_usage_materialize.py` covers both `_geneset_usage_records` materialization and the `_audit_geneset_row_dataset_usage` audit path. Confirm with `grep -rln "_audit_geneset_row_dataset_usage\|_geneset_usage_records" tests/`; if a separate module also exercises a gate, add it.)
Expected: PASS, including any pre-existing orphan-geneset test (unchanged behavior, unchanged provenance) and the new guard.

- [ ] **Step 9: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/commons/geneset_resources.py src/science_tool/graph/materialize.py src/science_tool/graph/migrate.py`
Expected: clean.

- [ ] **Step 10: Commit**

```bash
git add science/src/science_tool/commons/geneset_resources.py \
        science/src/science_tool/graph/materialize.py \
        science/src/science_tool/graph/migrate.py \
        science/tests/test_commons_geneset.py \
        science/tests/test_dataset_usage_materialize.py
git commit -m "fix(substrate): geneset member gate follows datapackage attachment, not adapter tag (§B4 2a)"
```

---

### Task 3: `science data-package promote-orphans` — orphan → real owner

**Files:**
- Create: `science/src/science_tool/datapackage_promote.py`
- Modify: `science/src/science_tool/cli.py` (add subcommand to the existing `data_package_group`; mirror `data_package_migrate_cmd` ~`:4945`)
- Test: `science/tests/test_datapackage_promote.py` (NEW)

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_datapackage_promote.py`:

```python
from pathlib import Path

import yaml

from science_model.frontmatter import parse_frontmatter
from science_tool.datapackage_promote import plan_orphan_promotions, promote_orphan_datapackages
from science_tool.graph.sources import load_project_sources


def _scaffold(tmp_path):
    # Mirror the minimal project manifest other loader tests use (knowledge_profiles
    # + layout_version). Reuse the helper from tests/test_load_project_sources_unified.py
    # if importable; otherwise inline the same manifest shape.
    ...  # IMPLEMENTER: copy the minimal manifest scaffolding used by the loader tests


def _write_orphan_external_datapackage(tmp_path, slug="z"):
    p = tmp_path / f"data/{slug}/datapackage.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        'profiles: ["science-pkg-entity-1.0"]\n'
        f'id: "dataset:{slug}"\n'
        'type: "dataset"\n'
        f'title: "Z {slug}"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n'
        'created: "2026-02-02"\n'
        'updated: "2026-02-02"\n',
        encoding="utf-8",
    )
    return p


def test_plan_lists_orphan_datapackage(tmp_path):
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    plans = plan_orphan_promotions(tmp_path)
    ids = {p.canonical_id for p in plans}
    assert "dataset:z" in ids
    plan = next(p for p in plans if p.canonical_id == "dataset:z")
    assert plan.datapackage_rel == "data/z/datapackage.yaml"
    assert plan.owner_rel == "entities/datasets/z.md"


def test_dry_run_writes_nothing(tmp_path):
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    report = promote_orphan_datapackages(tmp_path, apply=False)
    assert [p.canonical_id for p in report["promotions"]] == ["dataset:z"]
    assert not (tmp_path / "entities/datasets/z.md").exists()


def test_apply_writes_owner_with_pointer_and_no_resource_fields(tmp_path):
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    promote_orphan_datapackages(tmp_path, apply=True)
    owner = tmp_path / "entities/datasets/z.md"
    assert owner.exists()
    fm, _ = parse_frontmatter(owner)
    assert fm["id"] == "dataset:z"
    assert fm["type"] == "dataset"
    assert fm["origin"] == "external"
    assert fm["access"]["level"] == "public"
    assert fm["datapackage"] == "data/z/datapackage.yaml"
    assert fm["created"] == "2026-02-02"
    # Resource-only fields never leak into the identity owner.
    assert "resources" not in fm
    assert "members_resource" not in fm
    assert "profiles" not in fm


def test_after_apply_datapackage_defers_and_orphan_check_clean(tmp_path):
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    promote_orphan_datapackages(tmp_path, apply=True)
    sources = load_project_sources(tmp_path, include_commons=False,
                                   strict_core_schema=False, strict_identity=False)
    # The new markdown owner won; the datapackage now defers.
    assert sources.entity_source_adapters["dataset:z"] == "markdown"
    assert sources.dataset_datapackages["dataset:z"] == "data/z/datapackage.yaml"
    # No datapackage owner declaration remains -> nothing for plan to promote.
    assert plan_orphan_promotions(tmp_path) == []


def test_apply_is_idempotent(tmp_path):
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    promote_orphan_datapackages(tmp_path, apply=True)
    first = (tmp_path / "entities/datasets/z.md").read_text(encoding="utf-8")
    # Second run finds no orphan (it now defers) and does not rewrite the owner.
    report2 = promote_orphan_datapackages(tmp_path, apply=True)
    assert report2["promotions"] == []
    assert (tmp_path / "entities/datasets/z.md").read_text(encoding="utf-8") == first


def test_undated_datapackage_promotes_with_sentinel(tmp_path):
    _scaffold(tmp_path)
    p = tmp_path / "data/u/datapackage.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        'profiles: ["science-pkg-entity-1.0"]\n'
        'id: "dataset:u"\n'
        'type: "dataset"\n'
        'title: "U"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n',
        encoding="utf-8",
    )
    promote_orphan_datapackages(tmp_path, apply=True)
    fm, _ = parse_frontmatter(tmp_path / "entities/datasets/u.md")
    assert fm["created"] == "9999-99-99"  # undated sentinel -> migrate_layout undated gate


def test_path_traversal_id_is_rejected_not_written(tmp_path):
    # High finding: the dataset-id schema only requires a `dataset:` prefix, so a
    # traversal id must be rejected before it can write outside entities/datasets/.
    _scaffold(tmp_path)
    p = tmp_path / "data/evil/datapackage.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        'profiles: ["science-pkg-entity-1.0"]\n'
        'id: "dataset:../../escape"\n'
        'type: "dataset"\n'
        'title: "Evil"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n',
        encoding="utf-8",
    )
    report = promote_orphan_datapackages(tmp_path, apply=True)
    # Not promoted; surfaced under rejected; nothing written anywhere outside the tree.
    assert report["promotions"] == []
    assert ("dataset:../../escape", "data/evil/datapackage.yaml") in report["rejected"]
    assert not (tmp_path.parent / "escape.md").exists()
    assert not (tmp_path / "entities/datasets/escape.md").exists()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_datapackage_promote.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.datapackage_promote'`.

- [ ] **Step 3: Implement the promotion module**

Create `science/src/science_tool/datapackage_promote.py`:

```python
"""`science data-package promote-orphans` — promote orphan datapackages to real
`entities/datasets/<id>.md` owner files (design §B4, Phase 2).

An orphan datapackage is a `datapackage.yaml` (profile `science-pkg-entity-1.0`)
with no entity-file owner. After Phase 1.5, such a datapackage is the (deprecated,
transitional) owner of its id. Promotion lifts the datapackage's identity/project
metadata into a real markdown owner and adds a `datapackage:` pointer back to the
datapackage, which stays in place as the attachment holding resource metadata. On
the next load the datapackage DEFERS to the new owner.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from science_tool.graph.sources import load_project_sources

# Datapackage fields that are *resource* metadata — they stay in the datapackage
# and are never copied into the identity owner file (§B4). `profiles` is the
# datapackage profile marker, not an entity field.
_RESOURCE_ONLY_FIELDS = frozenset(
    {
        "profiles",
        "schema_profile",
        "resources",
        "members_resource",
        "member_key_column",
        "n_sets",
        "set_size_summary",
        "identifier_space",
        "datapackage",  # never let a datapackage self-pointer through; we set it
    }
)

# Reuse migrate_layout's undated sentinel so the existing `--apply` undated gate
# surfaces a datapackage that carries no `created` rather than inventing a date.
_UNDATED_SENTINEL = "9999-99-99"

# Path-safety: a promoted owner is written at entities/datasets/<slug>.md. The
# dataset-id schema only requires a `dataset:` prefix (no path-safe slug
# constraint), so an id like `dataset:../../x` would otherwise escape the tree.
# Guard the slug before it ever touches the filesystem.
_SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def _is_safe_slug(slug: str) -> bool:
    # The character class already excludes path separators; `..` is the only
    # traversal token the class would otherwise admit (it permits `.`).
    return bool(_SAFE_SLUG.match(slug)) and ".." not in slug


@dataclass(frozen=True)
class OrphanPromotion:
    canonical_id: str
    datapackage_rel: str
    owner_rel: str  # entities/datasets/<slug>.md


def _scan_orphans(project_root: Path) -> tuple[list[OrphanPromotion], list[tuple[str, str]]]:
    """Return (promotable orphans, rejected). Rejected = (canonical_id, datapackage_rel)
    pairs whose slug is not path-safe — reported, never written."""
    sources = load_project_sources(
        project_root,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    plans: list[OrphanPromotion] = []
    rejected: list[tuple[str, str]] = []
    for decl in sources.identity_declarations:
        # adapter == "datapackage" means it did NOT defer -> a true orphan owner.
        if decl.adapter != "datapackage" or decl.source_ref is None:
            continue
        slug = decl.canonical_id.split(":", 1)[-1]
        if not _is_safe_slug(slug):
            rejected.append((decl.canonical_id, decl.source_ref.path))
            continue
        plans.append(
            OrphanPromotion(
                canonical_id=decl.canonical_id,
                datapackage_rel=decl.source_ref.path,
                owner_rel=f"entities/datasets/{slug}.md",
            )
        )
    return plans, rejected


def plan_orphan_promotions(project_root: Path) -> list[OrphanPromotion]:
    """Every path-safe orphan datapackage owner in the compiled model, as a plan."""
    return _scan_orphans(project_root)[0]


def _owner_frontmatter(dp: dict, *, datapackage_rel: str) -> dict:
    fm = {k: v for k, v in dp.items() if k not in _RESOURCE_ONLY_FIELDS}
    # Datapackages declare `type`; some carry `kind`. Normalize to `type`.
    fm["type"] = fm.get("type") or fm.pop("kind", None) or "dataset"
    fm.pop("kind", None)
    fm["datapackage"] = datapackage_rel
    created = str(dp.get("created") or _UNDATED_SENTINEL)
    fm["created"] = created
    fm["updated"] = str(dp.get("updated") or created)
    return fm


def _render_owner(fm: dict, *, datapackage_rel: str) -> str:
    return (
        "---\n"
        + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)
        + "---\n\n"
        + f"Promoted from orphan datapackage `{datapackage_rel}` (design §B4).\n"
    )


def promote_orphan_datapackages(project_root: Path, *, apply: bool) -> dict:
    """Plan (and optionally write) owner files for every path-safe orphan datapackage.
    Unsafe-slug orphans are returned under ``rejected`` and never written."""
    plans, rejected = _scan_orphans(project_root)
    for plan in plans:
        dp = yaml.safe_load((project_root / plan.datapackage_rel).read_text(encoding="utf-8")) or {}
        fm = _owner_frontmatter(dp, datapackage_rel=plan.datapackage_rel)
        body = _render_owner(fm, datapackage_rel=plan.datapackage_rel)
        owner_path = project_root / plan.owner_rel
        if apply:
            owner_path.parent.mkdir(parents=True, exist_ok=True)
            if not (owner_path.exists() and owner_path.read_text(encoding="utf-8") == body):
                owner_path.write_text(body, encoding="utf-8")
    return {"promotions": plans, "rejected": rejected, "applied": apply}
```

- [ ] **Step 4: Run the module tests to verify they pass**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_datapackage_promote.py -v`
Expected: PASS (all). If `_scaffold` was left as `...`, fill it with the same minimal-manifest scaffolding the loader tests use before running.

- [ ] **Step 5: Wire the CLI subcommand**

In `science/src/science_tool/cli.py`, add a new command to the existing `data_package_group` (the group that defines `data_package_migrate_cmd` ~line 4945 and `data_package_list_cmd`). Mirror their option shape exactly:

```python
@data_package_group.command(name="promote-orphans")
@click.option("--apply", "apply_changes", is_flag=True, default=False,
              help="Write owner files (default: dry-run).")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
)
def data_package_promote_orphans_cmd(apply_changes: bool, project_root: Path | None) -> None:
    """Promote orphan datapackages to real entities/datasets/<id>.md owners (§B4)."""
    from science_tool.datapackage_promote import promote_orphan_datapackages

    proj = project_root or _project_root_from_env()
    report = promote_orphan_datapackages(proj, apply=apply_changes)
    for canonical_id, dp_rel in report["rejected"]:
        click.echo(f"skipped {canonical_id}: unsafe slug, not path-safe (from {dp_rel})", err=True)
    if not report["promotions"]:
        if not report["rejected"]:
            click.echo("no orphan datapackages to promote")
        return
    prefix = "wrote" if apply_changes else "[dry-run] would write"
    for plan in report["promotions"]:
        click.echo(f"{prefix} {plan.owner_rel}  (from {plan.datapackage_rel})")
```

- [ ] **Step 6: Write a CLI smoke test**

Add to `science/tests/test_datapackage_promote.py` (reuse the `CliRunner` idiom from the existing CLI tests — search `tests/` for `data-package migrate` invocations and copy the runner setup):

```python
def test_cli_promote_orphans_dry_run_then_apply(tmp_path):
    from click.testing import CliRunner
    from science_tool.cli import cli  # the root click group

    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    runner = CliRunner()

    dry = runner.invoke(cli, ["data-package", "promote-orphans", "--project-root", str(tmp_path)])
    assert dry.exit_code == 0
    assert "[dry-run] would write entities/datasets/z.md" in dry.output
    assert not (tmp_path / "entities/datasets/z.md").exists()

    applied = runner.invoke(
        cli, ["data-package", "promote-orphans", "--apply", "--project-root", str(tmp_path)]
    )
    assert applied.exit_code == 0
    assert "wrote entities/datasets/z.md" in applied.output
    assert (tmp_path / "entities/datasets/z.md").exists()
```

> NOTE TO IMPLEMENTER: confirm the root group import path (`from science_tool.cli import cli` vs another name) by reading the top of `cli.py` / an existing CLI test. Use whatever those tests import.

- [ ] **Step 7: Run the full promotion module + CLI test**

Run: `cd ~/d/science/science && uv run --frozen pytest tests/test_datapackage_promote.py -v`
Expected: PASS (all).

- [ ] **Step 8: Lint**

Run: `cd ~/d/science/science && uv run --frozen ruff check src/science_tool/datapackage_promote.py src/science_tool/cli.py && uv run --frozen ruff format --check src/science_tool/datapackage_promote.py`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add science/src/science_tool/datapackage_promote.py \
        science/src/science_tool/cli.py \
        science/tests/test_datapackage_promote.py
git commit -m "feat(substrate): science data-package promote-orphans (orphan datapackage -> real owner, §B4 2a)"
```

---

### Final verification (after all tasks)

- [ ] **Full suite + lint**

Run:
```bash
cd ~/d/science/science && uv run --frozen pytest -q && uv run --frozen ruff check . && uv run --frozen ruff format --check .
```
Expected: full suite green (baseline was 4670 passed at `bb61a865`; this plan adds tests, removes none), lint clean.

- [ ] **End-to-end smoke (promotion preserves geneset members)**

This is the cross-task capstone proving footgun (a) is closed by the *combination* of Task 2 + Task 3. If the materialize regression guard (Task 2, Step 7) already drives a markdown-owner-shadowing-datapackage through the real materialize path, this is covered. If not, add one e2e test in `test_datapackage_promote.py`: scaffold an **orphan geneset datapackage with a members CSV**, assert the materialized graph has the member edges (provenance = the datapackage), run `promote_orphan_datapackages(apply=True)`, re-materialize, and assert the **same** member edges + datapackage provenance still hold (now via the markdown owner). Reuse the geneset-edge assertion helper from `test_dataset_usage_materialize.py`.

---

## Self-review checklist (completed during authoring)

- **Spec coverage:** §B4 Phase-2a scope = (promotion ✔ Task 3) + (members-gate footgun a ✔ Tasks 1–2). Flip-to-error, forbid-second-declaration, resource→PROV are explicitly deferred to 2b and called out in the Scope guard.
- **Path-safety (High finding):** promotion derives a filesystem path from a dataset id whose schema only requires a `dataset:` prefix; `_is_safe_slug` guards traversal (`dataset:../../x`), rejections are reported (`report["rejected"]`, CLI stderr) and never written — covered by `test_path_traversal_id_is_rejected_not_written`.
- **Provenance (Medium finding):** the materialize gate cites `fm["_path"]` (the datapackage) for geneset usage records, so a promoted owner does not misattribute members to `entities/datasets/<id>.md`; asserted in the Task 2 regression guard.
- **Test targeting (Low finding):** geneset materialization + audit coverage lives in `test_dataset_usage_materialize.py` (there is no `test_graph_audit.py`); Task 2 points there.
- **Type consistency:** `dataset_datapackages: dict[str, str]` used identically in the model (Task 1), the materialize/migrate gates (Task 2), and the loader assertions (Task 3). `OrphanPromotion` fields (`canonical_id`, `datapackage_rel`, `owner_rel`) used consistently across module, CLI, and tests. Helper signature `dataset_geneset_frontmatter(project_root, entity_path, *, entity_adapter, datapackage_rel)` matches both call sites.
- **Placeholder scan:** the only `...` / placeholder markers are explicit "reuse this test file's existing scaffolding" notes for `_scaffold*` / `_write*` / `_materialize` / `_has_geneset_member_edges` helpers — flagged with NOTE TO IMPLEMENTER and a concrete instruction to clone the sibling test's fixtures, because inventing parallel fixtures would diverge from the suite's conventions.
- **Ordering:** Task 1 (map) precedes Task 2 (gate consumes the map) precedes Task 3 (promotion relies on the gate for lossless geneset promotion). Each task ends green and committed.
