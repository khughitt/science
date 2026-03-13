# Knowledge Graph Layering And Canonical Model Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Introduce a canonical, profile-driven knowledge graph model across `science-model`, `science-tool`, `science-web`, and `seq-feats`, with `core` as the required base profile, composable curated domain profiles such as `bio`, a formal `project_specific` extension profile, canonical IDs shared across docs/tasks/RDF/UI, and `graph.trig` treated as a deterministic materialized artifact.

**Architecture:** `science-model` becomes the sole authority for profile schema, canonical IDs, entity kinds, relation kinds, and validation rules. `science-tool` parses structured upstream sources and materializes named graph layers (`core`, domain profiles, `project_specific`, `bridge`, `provenance`, `causal`, `datasets`) into RDF. `science-web` becomes profile-aware and renders tasks as first-class graph entities. `seq-feats` migrates onto `core + bio + project_specific` through explicit migration tooling rather than direct graph editing.

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

Extend `Entity` and graph payloads to carry canonical/profile metadata:

```python
class Entity(BaseModel):
    ...
    canonical_id: str
    profile: str = "core"
    aliases: list[str] = []


class GraphNode(BaseModel):
    ...
    canonical_id: str
    profile: str
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
    related: list[str] = []
    aliases: list[str] = []


class SourceRelation(BaseModel):
    source_id: str
    relation: str
    target_id: str
    profile: str
    layer: str
    source_path: str
```

Add a materializer in `science-tool/src/science_tool/graph/materialize.py` that:

1. Reads `science.yaml` profile selections
2. Scans canonical entity docs and tasks
3. Loads structured manual assertions from `knowledge/sources/`
4. Resolves aliases via `science-model`
5. Writes named graph layers deterministically to `knowledge/graph.trig`

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

### Task 5: Make `science-web` profile-aware and render tasks as graph entities

**Files:**
- Create: `../science-web/backend/profiles.py`
- Modify: `../science-web/backend/indexer.py`
- Modify: `../science-web/backend/graph.py`
- Modify: `../science-web/backend/store.py`
- Modify: `../science-web/frontend/src/types/index.ts`
- Modify: `../science-web/frontend/src/routes/projects.$slug.graph.tsx`
- Test: `../science-web/tests/test_graph.py`
- Test: `../science-web/tests/test_indexer.py`

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
```

**Step 2: Run tests to verify they fail**

Run: `cd ../science-web && UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph.py tests/test_indexer.py -q`
Expected: FAIL because `Task` typing/profile metadata are not handled yet.

**Step 3: Implement profile-aware graph loading**

In `../science-web/backend/profiles.py`, add helpers that import manifests from `science_model.profiles` and expose:

```python
def load_enabled_profiles(project_root: Path) -> list[str]: ...
def graph_type_map() -> dict[str, str]: ...
```

Update `../science-web/backend/graph.py` to build node types from `science-model` profile manifests instead of a hardcoded `_TYPE_MAP`. Extend `GraphNode` handling so nodes carry `canonical_id`, `profile`, and `graph_layer`. Treat tasks as first-class graph nodes.

Update the frontend types to expect:

```ts
export interface GraphNode {
  id: string
  canonical_id: string
  label: string
  type: string
  profile: string
  graph_layer: string
}
```

Remove the design assumption that tasks are not graph entities and update the graph route to render them with the same interaction model as other core nodes.

**Step 4: Verify**

Run:

```bash
cd ../science-web
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pytest tests/test_graph.py tests/test_indexer.py -q
UV_CACHE_DIR=/tmp/uv-cache uv run --frozen pyright
cd frontend && npm run build
```

Expected: backend tests, type-checking, and frontend build all pass.

**Step 5: Commit**

```bash
git -C ../science-web add backend/profiles.py backend/indexer.py backend/graph.py backend/store.py frontend/src/types/index.ts frontend/src/routes/projects.$slug.graph.tsx tests/test_graph.py tests/test_indexer.py
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
```

**Step 2: Run verification and capture evidence**

Expected:

1. `science-model` tests and checks pass
2. `science-tool` tests and checks pass
3. `science-web` backend checks and frontend build pass
4. `seq-feats` graph rebuild succeeds
5. `seq-feats` graph validate shows no unresolved canonical ID failures and no missing task node materialization

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

Verification summary:
- `science-model` package-scoped tests, `pyright`, and `ruff check` passed.
- `science-tool` graph-focused regression suite passed, including the cross-process determinism test.
- `science-tool` full-suite collection remains blocked by a pre-existing missing `httpx` dependency in dataset tests.
- `science-web` tests, typecheck, and frontend build passed in this implementation run.
- `seq-feats` repeated graph builds now produce identical bytes; graph audit and graph validation pass; `validate.sh --verbose` reports all frontmatter cross-references valid and passes with warnings only.
