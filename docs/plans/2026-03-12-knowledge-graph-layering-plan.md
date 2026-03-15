# Knowledge Graph Layering And Canonical Model Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a canonical, profile-driven knowledge graph model across `science-model`, `science-tool`, `science-web`, and `seq-feats`, with `core` as the required base profile, composable curated domain profiles such as `bio`, a formal `project_specific` extension profile, canonical IDs shared across docs/tasks/RDF/UI, explicit per-entity and per-node `domain` metadata for downstream consumers, and `graph.trig` treated as a deterministic materialized artifact.

**Architecture:** `science-model` becomes the sole authority for profile schema, canonical IDs, entity kinds, relation kinds, validation rules, and the shared distinction between `profile`, `graph_layer`, and `domain`. `science-tool` parses structured upstream sources, assigns explicit `domain` values, and materializes named graph layers (`core`, domain profiles, `project_specific`, `bridge`, `provenance`, `causal`, `datasets`) into RDF. `science-web` becomes profile-aware, consumes upstream domain metadata directly, and renders tasks as first-class graph entities. `seq-feats` migrates onto `core + bio + project_specific` through explicit migration tooling rather than direct graph editing.

**Tech Stack:** Python 3.11+, Pydantic, rdflib, click, rich, pathlib, FastAPI, React/TypeScript, existing `science-model`, `science-tool`, and `science-web` packages. No new storage backend.

---

### Task 1: Document the target refactor footprint

**Files:**
- Create: `doc/kg-model/desired_file_structure.md`
- Create: `doc/kg-model/files_to_remove.md`
- Modify: `docs/plans/2026-03-12-knowledge-graph-layering-design.md`

**Step 1: Write the failing test-equivalent artifact expectations**

Create `doc/kg-model/desired_file_structure.md` with a tree like:

```markdown
# Desired File Structure

science-model/
  src/science_model/
    ids.py
    relations.py
    profiles/
      __init__.py
      schema.py
      core.py
      bio.py
      project_specific.py
science-tool/
  src/science_tool/graph/
    sources.py
    materialize.py
    migrate.py
science-web/
  backend/
    profiles.py
```

Create `doc/kg-model/files_to_remove.md` with placeholders such as:

```markdown
# Files To Remove

- Legacy short-ID graph migration shims after project migration is complete
- Hardcoded type maps in `../science-web/backend/graph.py` once profile-driven maps replace them
- Any direct `graph.trig` authoring assumptions in command docs after materialization workflow lands
```

**Step 2: Verify the docs do not exist yet**

Run: `test ! -f doc/kg-model/desired_file_structure.md && test ! -f doc/kg-model/files_to_remove.md`
Expected: exit code `0`

**Step 3: Add the refactor prep docs**

Use concise markdown with one section for package layout and one section for cleanup/deprecation items. Add a short note to [2026-03-12-knowledge-graph-layering-design.md](./2026-03-12-knowledge-graph-layering-design.md) pointing to these refactor-prep docs.

**Step 4: Verify**

Run: `sed -n '1,200p' doc/kg-model/desired_file_structure.md && sed -n '1,200p' doc/kg-model/files_to_remove.md`
Expected: both files exist and describe the target layout and cleanup list.

**Step 5: Commit**

```bash
git add doc/kg-model/desired_file_structure.md doc/kg-model/files_to_remove.md docs/plans/2026-03-12-knowledge-graph-layering-design.md
git commit -m "docs: add KG layering refactor prep docs"
```

### Task 2: Add profile schema and canonical ID utilities to `science-model`

**Files:**
- Create: `science-model/src/science_model/ids.py`
- Create: `science-model/src/science_model/relations.py`
- Create: `science-model/src/science_model/profiles/__init__.py`
- Create: `science-model/src/science_model/profiles/schema.py`
- Modify: `science-model/src/science_model/entities.py`
- Modify: `science-model/src/science_model/graph.py`
- Modify: `science-model/src/science_model/__init__.py`
- Test: `science-model/tests/test_ids.py`
- Test: `science-model/tests/test_relations.py`
- Test: `science-model/tests/test_profiles.py`

**Step 1: Write the failing tests**

Add tests like:

```python
from science_model.ids import CanonicalId, normalize_alias
from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind


def test_canonical_id_roundtrip() -> None:
    cid = CanonicalId.parse("hypothesis:h01-raw-feature-embedding-informativeness")
    assert cid.kind == "hypothesis"
    assert cid.slug == "h01-raw-feature-embedding-informativeness"
    assert str(cid) == "hypothesis:h01-raw-feature-embedding-informativeness"


def test_alias_normalization_handles_legacy_short_forms() -> None:
    aliases = {"H01": "hypothesis:h01-raw-feature-embedding-informativeness"}
    assert normalize_alias("H01", aliases) == "hypothesis:h01-raw-feature-embedding-informativeness"


def test_relation_kind_restricts_endpoints() -> None:
    relation = RelationKind(
        name="tests",
        predicate="sci:tests",
        source_kinds=["task", "experiment"],
        target_kinds=["hypothesis", "question"],
        layer="layer/core",
    )
    assert "hypothesis" in relation.target_kinds


def test_profile_manifest_requires_imports_for_extension_profiles() -> None:
    manifest = ProfileManifest(
        name="project_specific",
        imports=["core"],
        entity_kinds=[],
        relation_kinds=[],
        strictness="typed-extension",
    )
    assert manifest.imports == ["core"]
```

**Step 2: Run tests to verify they fail**

Run: `cd science-model && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_ids.py tests/test_relations.py tests/test_profiles.py -q`
Expected: FAIL with missing module or symbol errors.

**Step 3: Implement the profile schema and ID helpers**

Add an ID model in `science-model/src/science_model/ids.py`:

```python
from __future__ import annotations

from pydantic import BaseModel, Field


class CanonicalId(BaseModel):
    kind: str
    slug: str

    @classmethod
    def parse(cls, raw: str) -> "CanonicalId":
        kind, slug = raw.split(":", 1)
        return cls(kind=kind, slug=slug)

    def __str__(self) -> str:
        return f"{self.kind}:{self.slug}"


def normalize_alias(raw: str, aliases: dict[str, str]) -> str:
    return aliases.get(raw, aliases.get(raw.lower(), raw.lower()))
```

Add profile schema models in `science-model/src/science_model/profiles/schema.py`:

```python
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class EntityKind(BaseModel):
    name: str
    canonical_prefix: str
    layer: str
    description: str


class RelationKind(BaseModel):
    name: str
    predicate: str
    source_kinds: list[str]
    target_kinds: list[str]
    layer: str
    description: str = ""


class ProfileManifest(BaseModel):
    name: str
    imports: list[str]
    entity_kinds: list[EntityKind]
    relation_kinds: list[RelationKind]
    strictness: Literal["core", "curated", "typed-extension"]
```

Extend `Entity` and graph payloads to carry canonical/profile/domain metadata:

```python
class Entity(BaseModel):
    ...
    canonical_id: str
    profile: str = "core"
    domain: str | None = None
    aliases: list[str] = []


class GraphNode(BaseModel):
    ...
    canonical_id: str
    profile: str
    domain: str | None = None
    aliases: list[str] = []
```

**Step 4: Verify**

Run:

```bash
cd science-model
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_ids.py tests/test_relations.py tests/test_profiles.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .
```

Expected: all three commands pass.

**Step 5: Commit**

```bash
git add science-model/src/science_model/ids.py science-model/src/science_model/relations.py science-model/src/science_model/profiles/__init__.py science-model/src/science_model/profiles/schema.py science-model/src/science_model/entities.py science-model/src/science_model/graph.py science-model/src/science_model/__init__.py science-model/tests/test_ids.py science-model/tests/test_relations.py science-model/tests/test_profiles.py
git commit -m "feat(science-model): add profile schema and canonical ids"
```

### Task 3: Define `core`, `bio`, and `project_specific` profile manifests in `science-model`

**Files:**
- Create: `science-model/src/science_model/profiles/core.py`
- Create: `science-model/src/science_model/profiles/bio.py`
- Create: `science-model/src/science_model/profiles/project_specific.py`
- Modify: `science-model/src/science_model/profiles/__init__.py`
- Test: `science-model/tests/test_profile_manifests.py`

**Step 1: Write the failing tests**

```python
from science_model.profiles import BIO_PROFILE, CORE_PROFILE, PROJECT_SPECIFIC_PROFILE


def test_core_profile_contains_task_and_hypothesis() -> None:
    names = {kind.name for kind in CORE_PROFILE.entity_kinds}
    assert {"task", "hypothesis", "question", "claim"} <= names


def test_bio_profile_imports_core() -> None:
    assert BIO_PROFILE.imports == ["core"]


def test_project_specific_profile_is_typed_extension() -> None:
    assert PROJECT_SPECIFIC_PROFILE.strictness == "typed-extension"
```

**Step 2: Run tests to verify they fail**

Run: `cd science-model && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_profile_manifests.py -q`
Expected: FAIL because the manifest modules do not exist yet.

**Step 3: Implement the manifests**

Use explicit declarations rather than loading ad hoc YAML for the first version:

```python
# science-model/src/science_model/profiles/core.py
from science_model.profiles.schema import EntityKind, ProfileManifest, RelationKind

CORE_PROFILE = ProfileManifest(
    name="core",
    imports=[],
    strictness="core",
    entity_kinds=[
        EntityKind(name="hypothesis", canonical_prefix="hypothesis", layer="layer/core", description="Testable project hypothesis"),
        EntityKind(name="question", canonical_prefix="question", layer="layer/core", description="Project question"),
        EntityKind(name="task", canonical_prefix="task", layer="layer/core", description="Operational project task"),
    ],
    relation_kinds=[
        RelationKind(name="tests", predicate="sci:tests", source_kinds=["task", "experiment"], target_kinds=["hypothesis", "question"], layer="layer/core"),
        RelationKind(name="blocked_by", predicate="sci:blockedBy", source_kinds=["task"], target_kinds=["task"], layer="layer/core"),
    ],
)
```

`bio.py` should import `core` and declare curated entity/relation bundles that map to useful bio semantics. `project_specific.py` should import `core` and define the rules for typed project-local extensions, not project-specific content itself.

**Step 4: Verify**

Run:

```bash
cd science-model
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_profile_manifests.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest
```

Expected: pass.

**Step 5: Commit**

```bash
git add science-model/src/science_model/profiles/core.py science-model/src/science_model/profiles/bio.py science-model/src/science_model/profiles/project_specific.py science-model/src/science_model/profiles/__init__.py science-model/tests/test_profile_manifests.py
git commit -m "feat(science-model): add core and curated KG profiles"
```

### Task 4: Implement structured graph sources and deterministic materialization in `science-tool`

**Files:**
- Create: `science-tool/src/science_tool/graph/sources.py`
- Create: `science-tool/src/science_tool/graph/materialize.py`
- Create: `science-tool/src/science_tool/graph/migrate.py`
- Modify: `science-tool/src/science_tool/graph/store.py`
- Modify: `science-tool/src/science_tool/graph/__init__.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_graph_materialize.py`
- Test: `science-tool/tests/test_graph_cli.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from rdflib import Dataset, Namespace

from science_tool.graph.materialize import materialize_graph


def test_materialize_graph_includes_task_nodes(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    (project / "tasks").mkdir(parents=True)
    (project / "tasks" / "active.md").write_text(
        "## [t001] Validate H01\\n- priority: P1\\n- status: active\\n- related: [hypothesis:h01-demo]\\n- created: 2026-03-12\\n\\nDo it.\\n",
        encoding="utf-8",
    )
    (project / "science.yaml").write_text("name: demo\\nknowledge_profiles:\\n  curated: [bio]\\n  local: project_specific\\n", encoding="utf-8")
    (project / "specs" / "hypotheses").mkdir(parents=True)
    (project / "specs" / "hypotheses" / "h01-demo.md").write_text(
        "---\\nid: hypothesis:h01-demo\\ntype: hypothesis\\ntitle: Demo\\nrelated: []\\nsource_refs: []\\ncreated: '2026-03-12'\\nupdated: '2026-03-12'\\n---\\n",
        encoding="utf-8",
    )

    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(trig_path, format="trig")
    project_ns = Namespace("http://example.org/project/")
    assert any(str(s).endswith("/task/t001-validate-h01") for s, _, _ in dataset.triples((None, None, None)))


def test_materialize_graph_writes_bridge_layer_for_profile_mappings(tmp_path: Path) -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph_materialize.py -q`
Expected: FAIL because the materializer module does not exist.

**Step 3: Implement the source loaders and materializer**

Add source models in `science-tool/src/science_tool/graph/sources.py`:

```python
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class SourceEntity(BaseModel):
    canonical_id: str
    kind: str
    title: str
    profile: str
    source_path: str
    domain: str | None = None
    related: list[str] = []
    blocked_by: list[str] = []
    source_refs: list[str] = []
    ontology_terms: list[str] = []
    aliases: list[str] = []


class SourceRelation(BaseModel):
    subject: str
    predicate: str
    object: str
    graph_layer: str
    source_path: str
```

Add a materializer in `science-tool/src/science_tool/graph/materialize.py` that:

1. Reads `science.yaml` profile selections
2. Scans canonical entity docs and tasks
3. Loads structured manual assertions from `knowledge/sources/`
4. Resolves aliases via `science-model`
5. Accepts structured relation endpoints that point at canonical project IDs, external CURIEs, URLs, or bare controlled vocabulary tokens
6. Writes named graph layers deterministically to `knowledge/graph.trig`

Use a narrow API:

```python
def materialize_graph(project_root: Path) -> Path:
    ...
```

Modify CLI to add materialization-oriented commands:

```python
@graph.command("build")
def graph_build() -> None: ...


@graph.command("audit")
def graph_audit() -> None: ...
```

Retain existing query commands, but stop treating direct graph mutation as the primary workflow. If keeping `graph add ...`, rewrite those commands to update structured upstream source files under `knowledge/sources/` rather than writing raw TriG triples directly.

**Step 4: Verify**

Run:

```bash
cd science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph_materialize.py tests/test_graph_cli.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
```

Expected: all pass.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/sources.py science-tool/src/science_tool/graph/materialize.py science-tool/src/science_tool/graph/migrate.py science-tool/src/science_tool/graph/store.py science-tool/src/science_tool/graph/__init__.py science-tool/src/science_tool/cli.py science-tool/tests/test_graph_materialize.py science-tool/tests/test_graph_cli.py
git commit -m "feat(science-tool): materialize profile-driven knowledge graphs"
```

### Task 5: Make `science-web` profile-aware, domain-aware, and task-inclusive

**Files:**
- Create: `../science-web/backend/profiles.py`
- Modify: `../science-web/backend/indexer.py`
- Modify: `../science-web/backend/graph.py`
- Modify: `../science-web/backend/store.py`
- Modify: `../science-web/tests/test_store.py`
- Modify: `../science-web/frontend/src/types/index.ts`
- Modify: `../science-web/frontend/src/routes/projects.$slug.graph.tsx`
- Test: `../science-web/tests/test_graph.py`
- Test: `../science-web/tests/test_indexer.py`
- Test: `../science-web/tests/test_store.py`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from backend.graph import load_graph


def test_load_graph_exposes_task_nodes(tmp_path: Path) -> None:
    trig = tmp_path / "graph.trig"
    trig.write_text(
        \"\"\"@prefix sci: <http://example.org/science/vocab/> .
        @prefix : <http://example.org/project/> .
        @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

        <http://example.org/project/layer/core> {
          :task/t001-demo rdf:type sci:Task ;
            skos:prefLabel "Demo task" .
        }
        \"\"\",
        encoding="utf-8",
    )
    data = load_graph(trig, lod=1.0)
    assert any(node.type == "Task" for node in data.nodes)


def test_scan_project_preserves_task_related_links() -> None:
    ...


def test_load_graph_exposes_explicit_node_domain_metadata(tmp_path: Path) -> None:
    ...


def test_store_get_project_populates_top_domains_from_graph() -> None:
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd ../science-web && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph.py tests/test_indexer.py tests/test_store.py -q`
Expected: FAIL because `Task` typing/profile metadata and explicit domain metadata are not handled yet.

**Step 3: Implement profile-aware and domain-aware graph loading**

In `../science-web/backend/profiles.py`, add helpers that import manifests from `science_model.profiles` and expose:

```python
def load_enabled_profiles(project_root: Path) -> list[str]: ...
def graph_type_map() -> dict[str, str]: ...
```

Update `../science-web/backend/graph.py` to build node types from `science-model` profile manifests instead of a hardcoded `_TYPE_MAP`. Extend `GraphNode` handling so nodes carry `canonical_id`, `profile`, `domain`, and `graph_layer`. Treat tasks as first-class graph nodes.

Add explicit tests and implementation for the shared contract that:

1. `profile` identifies the governing schema bundle
2. `graph_layer` identifies the named graph storing the statement
3. `domain` is the stable UI-facing topical grouping used for graph coloring and summaries

Do not make `science-web` infer `domain` from profile names or graph layers.

Update the frontend types to expect:

```ts
export interface GraphNode {
  id: string
  canonical_id: string
  label: string
  type: string
  profile: string
  domain: string | null
  graph_layer: string
}
```

Remove the design assumption that tasks are not graph entities and update the graph route to render them with the same interaction model as other core nodes. Preserve existing graph metadata that the web app already uses, including `status`, `importance`, and domain color lookup data.

**Step 4: Verify**

Run:

```bash
cd ../science-web
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph.py tests/test_indexer.py tests/test_store.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
cd frontend && npm run build
```

Expected: backend tests, type-checking, and frontend build all pass. Graph payloads expose explicit `domain` metadata and project summaries expose non-empty `top_domains` when upstream data provides them.

**Step 5: Commit**

```bash
git -C ../science-web add backend/profiles.py backend/indexer.py backend/graph.py backend/store.py frontend/src/types/index.ts frontend/src/routes/projects.$slug.graph.tsx tests/test_graph.py tests/test_indexer.py tests/test_store.py
git -C ../science-web commit -m "feat: make science-web profile-aware and task-inclusive"
```

### Task 6: Add migration and audit tooling, then migrate `seq-feats` onto `core + bio + project_specific`

**Files:**
- Create: `science-tool/tests/test_graph_migrate.py`
- Modify: `science-tool/src/science_tool/graph/migrate.py`
- Modify: `../seq-feats/science.yaml`
- Create: `../seq-feats/knowledge/sources/project_specific/entities.yaml`
- Create: `../seq-feats/knowledge/sources/project_specific/relations.yaml`
- Create: `../seq-feats/knowledge/sources/project_specific/mappings.yaml`
- Create: `../seq-feats/knowledge/reports/kg-migration-audit.json`
- Modify: `../seq-feats/tasks/active.md`
- Modify: `../seq-feats/tasks/done/2026-03.md`

**Step 1: Write the failing tests**

```python
from pathlib import Path

from science_tool.graph.migrate import audit_project_graph, migrate_project_ids


def test_audit_project_graph_reports_unresolved_related_refs(tmp_path: Path) -> None:
    root = tmp_path / "project"
    ...
    report = audit_project_graph(root)
    assert report["unresolved_related_count"] > 0


def test_migrate_project_ids_rewrites_short_refs() -> None:
    mapping = {"H01": "hypothesis:h01-demo"}
    assert migrate_project_ids("related: [H01]\\n", mapping) == "related: [hypothesis:h01-demo]\\n"
```

**Step 2: Run tests to verify they fail**

Run: `cd science-tool && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph_migrate.py -q`
Expected: FAIL because the migration helpers do not exist or are incomplete.

**Step 3: Implement migration tooling and apply it to `seq-feats`**

In `science-tool/src/science_tool/graph/migrate.py`, add:

```python
def audit_project_graph(project_root: Path) -> dict[str, object]: ...
def migrate_project_ids(text: str, alias_map: dict[str, str]) -> str: ...
def write_project_specific_sources(project_root: Path, report: dict[str, object]) -> None: ...
```

Update `../seq-feats/science.yaml` to opt into profile composition:

```yaml
knowledge_profiles:
  curated: [bio]
  local: project_specific
```

Use the migration tooling to:

1. Rewrite `related:` links in task files to canonical IDs
2. Generate structured `project_specific` entity/relation/mapping files for unresolved project-local semantics
3. Write an audit report capturing any remaining unresolved IDs or promoted aliases

Do not hand-edit `../seq-feats/knowledge/graph.trig`; regenerate it from the materializer after the migration inputs are in place.

**Step 4: Verify**

Run:

```bash
cd science-tool
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph_migrate.py -q
cd ../seq-feats
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph audit --format json
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph build
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph validate --format json
```

Expected: migration tests pass; audit output shows no unresolved canonical IDs that block graph build; graph build and validate pass.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/migrate.py science-tool/tests/test_graph_migrate.py
git commit -m "feat(science-tool): add KG migration and audit tooling"
git -C ../seq-feats add science.yaml tasks/active.md tasks/done/2026-03.md knowledge/sources/project_specific/entities.yaml knowledge/sources/project_specific/relations.yaml knowledge/sources/project_specific/mappings.yaml knowledge/reports/kg-migration-audit.json knowledge/graph.trig
git -C ../seq-feats commit -m "kg: migrate seq-feats to canonical layered model"
```

### Task 6B: Define canonical model-layer source contracts and migrate `natural-systems-guide` off app-internal KG inputs

Reminder:
Do not resume the `natural-systems-guide` graph cutover work piecemeal before this task lands. Finish the typed source-contract implementation first, then return to `natural-systems-guide` to run the importer, rebuild the graph, and retire the remaining legacy model-layer builders.

**Files:**
- Modify: `docs/plans/2026-03-12-knowledge-graph-layering-design.md`
- Create: `science-model/src/science_model/source_contracts.py`
- Test: `science-model/tests/test_source_contracts.py`
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Modify: `science-tool/src/science_tool/graph/materialize.py`
- Modify: `science-tool/src/science_tool/graph/migrate.py`
- Create: `../natural-systems-guide/knowledge/sources/project_specific/models.yaml`
- Create: `../natural-systems-guide/knowledge/sources/project_specific/parameters.yaml`
- Create: `../natural-systems-guide/knowledge/sources/project_specific/bindings.yaml`
- Create or Modify: `../natural-systems-guide/scripts/export_kg_model_sources.py`
- Modify: `../natural-systems-guide/science.yaml`
- Modify: `../natural-systems-guide/validate.sh`

**Step 1: Write the failing test-equivalent contract expectations**

Capture these required outcomes:

```text
- `science-tool graph build` must not permanently parse project-specific TypeScript or generated JSON files
- model-layer knowledge must flow through typed canonical source files under `knowledge/sources/<local-profile>/`
- canonical model-layer contracts must cover model entities, parameter entities, authored model/parameter relations, and model-parameter bindings
- importer scripts may read app internals, but only to write canonical source files
```

**Step 2: Add typed source-contract models**

Define explicit source-contract schemas, preferably in `science-model`, for:

1. `ModelSource`
2. `ParameterSource`
3. `BindingSource`
4. Shared helper records for authored relations and provenance references

Use concrete fields that match the design contract, for example:

```python
class ModelSource(BaseModel):
    canonical_id: str
    title: str
    profile: str
    source_path: str
    domain: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    relations: list[AuthoredTargetedRelation] = Field(default_factory=list)


class ParameterSource(BaseModel):
    canonical_id: str
    title: str
    symbol: str
    profile: str
    source_path: str
    units: str | None = None
    quantity_group: str | None = None
    domain: str | None = None
    aliases: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    relations: list[AuthoredTargetedRelation] = Field(default_factory=list)


class BindingSource(BaseModel):
    model: str
    parameter: str
    source_path: str
    symbol: str | None = None
    role: str | None = None
    units_override: str | None = None
    confidence: float | None = None
    match_tier: str | None = None
```

**Step 3: Extend `science-tool` to read those contracts**

Update `science-tool` so that:

1. `sources.py` loads `models.yaml`, `parameters.yaml`, and `bindings.yaml` in addition to `entities.yaml`, `relations.yaml`, and `mappings.yaml`
2. `migrate.py` audits canonical IDs across those typed source files
3. `materialize.py` emits:
   - `sci:Model` nodes
   - `sci:CanonicalParameter` nodes
   - authored model-to-model and parameter-to-parameter relations
   - provenance-layer binding records for model-parameter bindings

Do not add a permanent `science-tool` dependency on `natural-systems-guide` TypeScript files.

**Step 4: Add a project-local importer for `natural-systems-guide`**

Create or update a project-local importer script that reads the current app-internal sources:

1. `src/chapters/generated/guide-data.json`
2. `src/natural/registry/parameterRegistry.ts`
3. `src/natural/registry/modelParameterBindings.ts`
4. supporting reports such as `doc/reports/parameter-matches.json` when needed

The importer must write canonical source files:

1. `knowledge/sources/project_specific/models.yaml`
2. `knowledge/sources/project_specific/parameters.yaml`
3. `knowledge/sources/project_specific/bindings.yaml`

This importer is a migration bridge, not a permanent `science-tool graph build` input.

**Step 5: Verify with `natural-systems-guide`**

Run:

```bash
cd ../natural-systems-guide
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/export_kg_model_sources.py
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph audit --project-root . --format json
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph build --project-root .
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph validate --format json --path knowledge/graph.trig
./validate.sh --verbose
```

Expected:

1. The importer writes canonical model-layer source files without manual TriG editing
2. `graph audit` returns no unresolved canonical IDs
3. `graph build` succeeds without reading app-internal TS/JSON files directly
4. The rebuilt graph preserves model-layer coverage closely enough to replace the old `knowledge/scripts/build-model-layer.ts` pipeline

**Step 6: Commit**

```bash
git add docs/plans/2026-03-12-knowledge-graph-layering-design.md science-model/src/science_model/source_contracts.py science-model/tests/test_source_contracts.py science-tool/src/science_tool/graph/sources.py science-tool/src/science_tool/graph/materialize.py science-tool/src/science_tool/graph/migrate.py
git commit -m "feat: add canonical model-layer source contracts"
git -C ../natural-systems-guide add knowledge/sources/project_specific/models.yaml knowledge/sources/project_specific/parameters.yaml knowledge/sources/project_specific/bindings.yaml scripts/export_kg_model_sources.py science.yaml validate.sh knowledge/graph.trig
git -C ../natural-systems-guide commit -m "kg: migrate model layer to canonical sources"
```

### Task 6C: Finish `science-web` model-layer consumption, summaries, and graph UX

This is a follow-up to the earlier `science-web` profile-awareness task, not a replacement for it.
The earlier work established basic task-node support and manifest-driven type mapping.
This task finishes the consumer side now that typed model-layer source contracts and real migrated projects exist.

**Files:**
- Modify: `science-model/src/science_model/graph.py`
- Modify: `science-model/src/science_model/projects.py`
- Modify: `../science-web/backend/graph.py`
- Modify: `../science-web/backend/indexer.py`
- Modify: `../science-web/backend/store.py`
- Modify: `../science-web/backend/routes/projects.py`
- Modify: `../science-web/tests/test_graph.py`
- Modify: `../science-web/tests/test_indexer.py`
- Modify: `../science-web/tests/test_store.py`
- Modify: `../science-web/tests/test_api_projects.py`
- Modify: `../science-web/frontend/src/types/index.ts`
- Modify: `../science-web/frontend/src/components/GraphExplorer/GraphExplorer.tsx`
- Modify: `../science-web/frontend/src/components/GraphExplorer/GraphExplorer3D.tsx`
- Modify: `../science-web/frontend/src/components/GraphExplorer/nodeShapes.ts`
- Modify: `../science-web/frontend/src/routes/ProjectGraph.tsx`
- Modify: `../science-web/frontend/src/routes/ProjectDashboard.tsx`

**Step 1: Write the failing tests around real graph-consumer gaps**

Capture these expectations:

```text
- `load_graph()` exposes `Model`, `CanonicalParameter`, and `ParameterBinding` nodes from a canonical TriG fixture
- node payloads preserve explicit `domain`, `profile`, `graph_layer`, aliases, and source refs when present
- binding nodes preserve provenance-facing metadata such as `confidence`, `match_tier`, `symbol`, and `role`
- `get_project()` computes non-empty `top_domains` from graph content when domain-tagged nodes exist
- the dashboard/API remain valid for small task/question-only projects with no model-layer nodes
```

Use two fixture styles:

1. a minimal synthetic TriG fixture in `science-web/tests/test_graph.py`
2. one richer verification fixture derived from the migrated `natural-systems-guide` shape so the tests cover `Model` + `CanonicalParameter` + `ParameterBinding`

**Step 2: Tighten the shared graph payload contract**

Update the shared `science-model` graph payloads so the API contract is explicit about the data `science-web` actually needs.

The target shape should include at least:

```python
class GraphNode(BaseModel):
    id: str
    canonical_id: str
    label: str
    type: str
    profile: str
    domain: str | None = None
    graph_layer: str
    aliases: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    status: str | None = None
    confidence: float | None = None
    symbol: str | None = None
    role: str | None = None
    match_tier: str | None = None
```

If the dashboard needs project-level profile information, add it to the shared project/detail models here rather than inventing ad hoc backend-only payloads.

**Step 3: Finish backend graph loading and summaries**

Update `science-web` backend code so that:

1. `backend/graph.py` parses explicit node metadata from the materialized graph instead of only labels and types
2. model-layer provenance nodes such as `sci:ParameterBinding` are exposed as selectable graph nodes
3. `backend/store.py` computes `GraphSummary.top_domains` from graph nodes rather than returning an empty list
4. `backend/indexer.py` and `backend/routes/projects.py` expose any project-level profile/domain summary fields added to the shared models

Important constraints:

1. do not infer `domain` from profile names
2. do not special-case `natural-systems-guide` file layouts in `science-web`
3. do not parse YAML source files directly in `science-web`; consume the shared API payloads and materialized graph only

**Step 4: Upgrade the frontend graph explorer and dashboard**

Update the frontend so the graph explorer is useful for both `seq-feats` and `natural-systems-guide`.

Required outcomes:

1. node shapes or markers clearly distinguish `Task`, `Model`, `CanonicalParameter`, and `ParameterBinding`
2. the node inspector shows `canonical_id`, `profile`, `domain`, and `graph_layer` separately
3. binding nodes surface provenance metadata such as `confidence`, `match_tier`, `symbol`, `role`, and `source_refs`
4. the project dashboard displays non-empty `top_domains` when available
5. the graph UI remains readable for task/question-only projects without forcing model-layer affordances

Do not add frontend logic that reverse-engineers semantic categories from raw RDF predicate strings when the backend can provide explicit fields.

**Step 5: Verify against both small and rich projects**

Run:

```bash
cd ../science-web
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph.py tests/test_indexer.py tests/test_store.py tests/test_api_projects.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
cd frontend && npm run build

cd ../../science
UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science-web python - <<'PY'
from pathlib import Path
from backend.graph import load_graph

seq_feats = Path("../seq-feats/knowledge/graph.trig")
natural = Path("../mindful/natural-systems-guide/knowledge/graph.trig")

for path in [seq_feats, natural]:
    data = load_graph(path, lod=1.0)
    print(path, len(data.nodes), len(data.edges), sorted({node.type for node in data.nodes})[:12])
PY
```

Expected:

1. backend tests, typing checks, and frontend build all pass
2. `seq-feats` still loads as a task/question/paper graph without regressions
3. `natural-systems-guide` exposes `Model`, `CanonicalParameter`, and `ParameterBinding` nodes with explicit metadata
4. project summaries include non-empty `top_domains` when upstream nodes carry domains

**Step 6: Commit**

```bash
git add science-model/src/science_model/graph.py science-model/src/science_model/projects.py
git commit -m "feat(science-model): extend graph payloads for science-web"
git -C ../science-web add backend/graph.py backend/indexer.py backend/store.py backend/routes/projects.py tests/test_graph.py tests/test_indexer.py tests/test_store.py tests/test_api_projects.py frontend/src/types/index.ts frontend/src/components/GraphExplorer/GraphExplorer.tsx frontend/src/components/GraphExplorer/GraphExplorer3D.tsx frontend/src/components/GraphExplorer/nodeShapes.ts frontend/src/routes/ProjectGraph.tsx frontend/src/routes/ProjectDashboard.tsx
git -C ../science-web commit -m "feat: surface model-layer graph metadata in dashboard and explorer"
```

### Task 7: Replace direct graph authoring assumptions in command docs and validation flows

**Files:**
- Modify: `commands/create-graph.md`
- Modify: `commands/update-graph.md`
- Modify: `docs/biomedical-starter-profile.md`
- Modify: `README.md`
- Modify: `validate.sh`

**Step 1: Write the failing test-equivalent checklist**

Capture these required replacements:

```text
- "do NOT edit graph.trig directly" stays true
- graph creation docs now describe materializing from structured upstream sources
- profile selection and project-local extension files are documented
- validation checks canonical ID resolution and unresolved `related:` links
```

**Step 2: Verify the old assumptions exist**

Run:

```bash
rg -n "graph add|edit graph.trig directly|Tasks are not graph entities|open questions" commands/create-graph.md commands/update-graph.md docs/biomedical-starter-profile.md README.md validate.sh
```

Expected: matches show the old direct-authoring and pre-profile assumptions.

**Step 3: Update docs and validation**

Adjust the docs so that:

1. `create-graph` describes building upstream sources and then materializing
2. `update-graph` describes re-materializing from changed canonical inputs
3. `biomedical-starter-profile` becomes the first `bio` profile guide rather than a standalone ad hoc reference
4. `README.md` explains profile composition and generated graphs
5. `validate.sh` checks canonical ID resolution, unresolved references, and presence of profile config

**Step 4: Verify**

Run:

```bash
bash validate.sh --verbose
rg -n "knowledge_profiles|project_specific|materialize|canonical id" README.md commands/create-graph.md commands/update-graph.md docs/biomedical-starter-profile.md
```

Expected: validation passes; docs include the new profile/materialization language.

**Step 5: Commit**

```bash
git add commands/create-graph.md commands/update-graph.md docs/biomedical-starter-profile.md README.md validate.sh
git commit -m "docs: update KG commands for layered materialization workflow"
```

### Task 8: Run end-to-end cross-repo verification

**Files:**
- Modify: `docs/plans/2026-03-12-knowledge-graph-layering-plan.md`
- Create: `docs/exemplar-evidence/kg-layering-verification.md`

**Step 1: Collect verification commands**

Use these commands:

```bash
cd science-model && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .
cd ../science-tool && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen ruff check .
cd ../science-web && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright && cd frontend && npm run build
cd ../../seq-feats && UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph build && UV_CACHE_DIR=/tmp/uv-cache uv run --project ../science/science-tool science-tool graph validate --format json
cd ../mindful/natural-systems-guide && UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph audit --project-root . --format json && UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph build --project-root . && UV_CACHE_DIR=/tmp/uv-cache uv run --project ../../science/science-tool science-tool graph validate --format json --path knowledge/graph.trig
```

**Step 2: Run verification and capture evidence**

Expected:

1. `science-model` tests and checks pass
2. `science-tool` tests and checks pass
3. `science-web` backend checks and frontend build pass
4. `seq-feats` graph rebuild succeeds
5. `seq-feats` graph validate shows no unresolved canonical ID failures and no missing task node materialization
6. `natural-systems-guide` graph audit/build/validate succeed against canonical source files without the old model/community layer builders on the critical path

**Step 3: Write the evidence summary**

Create `docs/exemplar-evidence/kg-layering-verification.md` with:

```markdown
# KG Layering Verification

- Date:
- Repos verified:
- Commands run:
- Key outcomes:
  - canonical IDs resolved across docs/tasks/RDF
  - tasks materialized as graph nodes
  - profile-aware graph layers available in API/UI
```

Append a short completion note to this plan with actual outcomes and any residual risks.

**Step 4: Verify**

Run: `sed -n '1,200p' docs/exemplar-evidence/kg-layering-verification.md`
Expected: file contains concrete commands and outcomes.

**Step 5: Commit**

```bash
git add docs/plans/2026-03-12-knowledge-graph-layering-plan.md docs/exemplar-evidence/kg-layering-verification.md
git commit -m "docs: record KG layering verification"
```

### Completion Note

Executed on 2026-03-13.

Completed:
- Tasks 1 through 8 were implemented across `science-model`, `science-tool`, `science-web`, and `seq-feats`.
- `science-tool` now materializes `graph.trig` deterministically across separate processes.
- `seq-feats` migrated to `core + bio + project_specific` upstream sources with canonical task/question/hypothesis coverage and generated graph rebuilds.
- Command docs and validation flows were updated to treat `knowledge/graph.trig` as a generated artifact rather than a hand-edited source.

Follow-up gap discovered after the original implementation scope:
- `natural-systems-guide` exposed a second migration class where rich model-layer semantics still lived in project app internals rather than canonical KG source files.
- That gap is now captured explicitly as Task `6B`, which defines typed canonical source contracts for models, parameters, and bindings, and uses a project-local importer rather than teaching `science-tool` to permanently parse project-specific TS/JSON inputs.

Verification summary:
- `science-model` package-scoped tests, `pyright`, and `ruff check` passed.
- `science-tool` graph-focused regression suite passed, including the cross-process determinism test.
- `science-tool` full-suite collection remains blocked by a pre-existing missing `httpx` dependency in dataset tests.
- `science-web` tests, typecheck, and frontend build passed in this implementation run.
- `seq-feats` repeated graph builds now produce identical bytes; graph audit and graph validation pass; `validate.sh --verbose` reports all frontmatter cross-references valid and passes with warnings only.

Addendum (2026-03-14):
- Task `6C` follow-up implementation in `science-web` is now verified end-to-end:
  - backend tests and API tests pass with model/provenance fixtures
  - `science-web` `pyright` and frontend build pass
  - live graph loading confirms `natural-systems-guide` now surfaces `Model`, `CanonicalParameter`, and `ParameterBinding` node payloads with explicit metadata
- Task `7` docs/validation alignment was completed by removing the remaining stale README wording that still implied incremental graph mutation instead of canonical-source re-materialization.
- Current environment caveats in this verification run:
  - `uv run --frozen ruff check .` is currently unavailable in both `science-model` and `science-tool` because `ruff` is not installed in the runtime image.
  - `science-tool` full-suite `pytest` and `pyright` still report pre-existing dependency/type issues (including unresolved `httpx` imports in dataset modules).

Addendum (2026-03-14, verification refresh):
- Re-ran the Task 8 cross-repo verification commands after the migration typing fixes.
- `science-model` remained green for `pytest` and `pyright`; `ruff` remains unavailable in the runtime image.
- `science-web` remained green for backend tests, `pyright`, and frontend build.
- `seq-feats` and `natural-systems-guide` both passed `graph audit` (empty rows), `graph build`, and `graph validate`.
- `seq-feats` `validate.sh --verbose` still passes with warnings only; current graph hash in this run is `733830f7990ecc81c0db8defcca6a2bffe98e797df5d1f45982a7b55cc9982f0`.
- `science-tool` still has pre-existing full-suite blockers (`httpx`/`pykeen`/`pgmpy`/`marimo` family deps and existing `graph/store.py` typing issues), but the earlier 6B migration-report typing regressions are cleared.
