# Entity Identity Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the entity identity and creation policy across `science-model`, `science-tool`, and curator-facing guidance so entity authoring, loading, health checks, and cross-project sync all enforce the same rules.

**Architecture:** Add a small typed identity layer to the core entity model, hydrate it from markdown and structured sources, then enforce it through `science-tool health` and sync-time registry checks. Keep internal `canonical_id` separate from external authority identifiers, avoid compatibility shims, and stage rollout so schema and loader work lands before health/sync enforcement and curator guidance.

**Tech Stack:** Python 3.13, Pydantic v2, Click, PyYAML, `uv`, `pytest`, `ruff`, `pyright`

---

## Non-Goals

- Do not bulk-backfill every legacy entity in this branch.
- Do not implement broad ontology resolver expansion or global synonym unification.
- Do not embed project scope into canonical ids.
- Do not add a compatibility alias layer beyond explicit `deprecated_ids` / `replaced_by`.
- Do not redesign the full attribute/observation model here; only add the dependency note and guardrails needed to keep curators from inventing workaround entities.

## Implementation Notes

- Follow `@superpowers:test-driven-development` for each code task.
- Keep commits small and frequent; each task below ends with its own commit.
- Prefer additive schema changes first, then loader hydration, then health/sync enforcement, then docs/skills.
- Keep existing projects loadable during rollout; surface policy violations through health and sync diagnostics before promoting any checks to hard-fail build paths.

### Task 1: Add Typed Identity Models To `science-model`

**Files:**
- Create: `science-model/src/science_model/identity.py`
- Modify: `science-model/src/science_model/entities.py`
- Modify: `science-model/src/science_model/__init__.py`
- Test: `science-model/tests/test_identity.py`
- Test: `science-model/tests/test_entities.py`

**Step 1: Write the failing tests**

Add a new test module that locks the shape and validation rules for external identifiers and entity lifecycle metadata.

```python
from datetime import date

import pytest
from pydantic import ValidationError

from science_model.entities import Entity, EntityType
from science_model.identity import ExternalId, EntityScope


def test_external_id_structured_round_trip() -> None:
    ext = ExternalId(
        source="HGNC",
        id="3527",
        curie="HGNC:3527",
        provenance="manual",
    )
    assert ext.curie == "HGNC:3527"


def test_entity_accepts_identity_fields() -> None:
    entity = Entity(
        id="gene:EZH2",
        canonical_id="gene:EZH2",
        kind="gene",
        type=None,
        title="EZH2",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/genes/EZH2.md",
        primary_external_id=ExternalId(source="HGNC", id="3527", curie="HGNC:3527", provenance="manual"),
        xrefs=[ExternalId(source="NCBIGene", id="2146", curie="NCBIGene:2146", provenance="manual")],
        scope=EntityScope.SHARED,
        deprecated_ids=["gene:ENX1"],
        taxon="NCBITaxon:9606",
    )
    assert entity.scope == EntityScope.SHARED
    assert entity.primary_external_id is not None


def test_entity_rejects_deprecated_id_equal_to_canonical_id() -> None:
    with pytest.raises(ValidationError, match="deprecated"):
        Entity(
            id="concept:chromatin",
            canonical_id="concept:chromatin",
            kind="concept",
            type=EntityType.CONCEPT,
            title="Chromatin",
            project="demo",
            ontology_terms=[],
            related=[],
            source_refs=[],
            content_preview="",
            file_path="doc/concepts/chromatin.md",
            deprecated_ids=["concept:chromatin"],
        )
```

Extend `science-model/tests/test_entities.py` with one regression asserting a versioned external id keeps the base CURIE canonical and the version in metadata.

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv run --frozen pytest tests/test_identity.py tests/test_entities.py -q
```

Expected: FAIL because `science_model.identity` and the new entity fields do not exist yet.

**Step 3: Write the minimal implementation**

Add a focused identity module and wire it into `Entity`.

```python
# science_model/identity.py
class EntityScope(StrEnum):
    PROJECT = "project"
    SHARED = "shared"


class ExternalId(BaseModel):
    source: str
    id: str
    curie: str
    version: str | None = None
    provenance: str


# science_model/entities.py
class Entity(BaseModel):
    ...
    primary_external_id: ExternalId | None = None
    xrefs: list[ExternalId] = Field(default_factory=list)
    scope: EntityScope = EntityScope.PROJECT
    provisional: bool = False
    review_after: date | None = None
    deprecated_ids: list[str] = Field(default_factory=list)
    replaced_by: str | None = None
    taxon: str | None = None
```

Add a validator that rejects:

- `deprecated_ids` containing the entity’s own canonical id
- duplicate `xrefs`
- `replaced_by` equal to the entity’s own id

Do not add merge/split orchestration logic here; only the typed data contract.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv run --frozen pytest tests/test_identity.py tests/test_entities.py -q
uv run --frozen ruff check src/science_model/identity.py src/science_model/entities.py tests/test_identity.py tests/test_entities.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-model/src/science_model/identity.py \
        science-model/src/science_model/entities.py \
        science-model/src/science_model/__init__.py \
        science-model/tests/test_identity.py \
        science-model/tests/test_entities.py
git commit -m "feat: add entity identity schema"
```

### Task 2: Parse Identity Metadata From Markdown Frontmatter

**Files:**
- Modify: `science-model/src/science_model/frontmatter.py`
- Test: `science-model/tests/test_frontmatter.py`
- Test: `science-model/tests/test_frontmatter_dataset.py`

**Step 1: Write the failing tests**

Extend frontmatter parsing tests to cover structured external ids, scope, lifecycle fields, and taxon.

```python
def test_parse_entity_file_reads_identity_fields(tmp_path: Path) -> None:
    md = tmp_path / "doc" / "genes" / "EZH2.md"
    md.parent.mkdir(parents=True)
    md.write_text(
        "---\n"
        'id: "gene:EZH2"\n'
        'kind: "gene"\n'
        'title: "EZH2"\n'
        "primary_external_id:\n"
        '  source: "HGNC"\n'
        '  id: "3527"\n'
        '  curie: "HGNC:3527"\n'
        '  provenance: "manual"\n'
        "xrefs:\n"
        '  - source: "NCBIGene"\n'
        '    id: "2146"\n'
        '    curie: "NCBIGene:2146"\n'
        '    provenance: "manual"\n'
        'scope: "shared"\n'
        'deprecated_ids: ["gene:ENX1"]\n'
        'taxon: "NCBITaxon:9606"\n'
        "---\n"
        "Body.\n",
        encoding="utf-8",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity is not None
    assert entity.primary_external_id is not None
    assert entity.scope.value == "shared"
    assert entity.taxon == "NCBITaxon:9606"
```

Add a second test that a versioned accession in frontmatter normalizes to an unversioned canonical external id while preserving the original version in the parsed model.

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv run --frozen pytest tests/test_frontmatter.py tests/test_frontmatter_dataset.py -q
```

Expected: FAIL because `parse_entity_file()` does not yet hydrate the new fields.

**Step 3: Write the minimal implementation**

Add small coercion helpers in `frontmatter.py` and pass the new fields through to `Entity`.

```python
def _coerce_external_id(raw: dict | None) -> ExternalId | None:
    ...


def _coerce_external_ids(raw: list[dict] | None) -> list[ExternalId]:
    ...


entity_kwargs = {
    ...,
    "primary_external_id": _coerce_external_id(fm.get("primary_external_id")),
    "xrefs": _coerce_external_ids(fm.get("xrefs")),
    "scope": fm.get("scope") or "project",
    "provisional": bool(fm.get("provisional", False)),
    "review_after": _coerce_date(fm.get("review_after")),
    "deprecated_ids": list(fm.get("deprecated_ids") or []),
    "replaced_by": fm.get("replaced_by"),
    "taxon": fm.get("taxon"),
}
```

Normalize versioned external identifiers here so every loader path sees the same canonical form.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv run --frozen pytest tests/test_frontmatter.py tests/test_frontmatter_dataset.py -q
uv run --frozen ruff check src/science_model/frontmatter.py tests/test_frontmatter.py tests/test_frontmatter_dataset.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-model/src/science_model/frontmatter.py \
        science-model/tests/test_frontmatter.py \
        science-model/tests/test_frontmatter_dataset.py
git commit -m "feat: parse entity identity frontmatter"
```

### Task 3: Hydrate Identity Fields In Unified Project Loading

**Files:**
- Modify: `science-tool/src/science_tool/graph/sources.py`
- Test: `science-tool/tests/test_load_project_sources_unified.py`
- Test: `science-tool/tests/test_load_project_sources_regression.py`

**Step 1: Write the failing tests**

Add one markdown-backed and one aggregate-backed regression that prove `load_project_sources()` preserves the new identity fields.

```python
def test_load_project_sources_preserves_identity_fields(tmp_path: Path) -> None:
    ...
    sources = load_project_sources(tmp_path)
    entity = next(e for e in sources.entities if e.canonical_id == "gene:EZH2")
    assert entity.primary_external_id is not None
    assert entity.primary_external_id.curie == "HGNC:3527"
    assert entity.scope.value == "shared"
    assert entity.taxon == "NCBITaxon:9606"
```

Add a regression that structured source rows with `deprecated_ids` and `replaced_by` survive normalization unchanged.

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_load_project_sources_unified.py tests/test_load_project_sources_regression.py -q
```

Expected: FAIL because `_enrich_raw()` and unified loading do not yet project the identity metadata consistently.

**Step 3: Write the minimal implementation**

Update `_enrich_raw()` defaults and any legacy record projection blocks that need to preserve identity metadata.

```python
raw.setdefault("aliases", [])
raw.setdefault("deprecated_ids", [])
raw.setdefault("xrefs", [])
raw.setdefault("scope", "project")
raw.setdefault("provisional", False)

if "primary_external_id" in raw:
    raw["primary_external_id"] = raw["primary_external_id"]
```

Do not add alias derivation from `deprecated_ids`; keep deprecation explicit.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_load_project_sources_unified.py tests/test_load_project_sources_regression.py -q
uv run --frozen ruff check src/science_tool/graph/sources.py tests/test_load_project_sources_unified.py tests/test_load_project_sources_regression.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/sources.py \
        science-tool/tests/test_load_project_sources_unified.py \
        science-tool/tests/test_load_project_sources_regression.py
git commit -m "feat: preserve entity identity metadata during source loading"
```

### Task 4: Add Single-Project Identity Lints To `science-tool health`

**Files:**
- Modify: `science-tool/src/science_tool/graph/health.py`
- Modify: `science-tool/src/science_tool/cli.py`
- Test: `science-tool/tests/test_health.py`

**Step 1: Write the failing tests**

Add health tests for the core policy checks:

```python
def test_health_flags_primary_external_id_collision(tmp_path: Path) -> None:
    ...
    report = build_health_report(tmp_path)
    assert any(row["check"] == "primary_external_id_collision" for row in report["identity_policy"])


def test_health_flags_missing_required_external_id(tmp_path: Path) -> None:
    ...
    assert any(row["check"] == "missing_primary_external_id" for row in report["identity_policy"])


def test_health_flags_missing_taxon_for_gene(tmp_path: Path) -> None:
    ...


def test_health_flags_deprecated_id_inbound_ref(tmp_path: Path) -> None:
    ...


def test_health_flags_relation_endpoint_disambiguation(tmp_path: Path) -> None:
    ...
```

Cover JSON and table output so the new section is visible to both humans and agents.

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_health.py -q
```

Expected: FAIL because `HealthReport` has no identity-policy section and the lints do not exist.

**Step 3: Write the minimal implementation**

Add an `identity_policy` section to the health report and implement focused collectors:

```python
class IdentityPolicyFinding(TypedDict):
    check: str
    canonical_id: str
    message: str
    source_path: str


def collect_identity_policy_findings(project_root: Path) -> list[IdentityPolicyFinding]:
    ...
```

Implement these first-pass checks:

- duplicate `primary_external_id.curie` within one project
- missing `primary_external_id` for required kinds when the entity is not provisional
- missing `taxon` for organism-bound bio entities
- inbound refs to `deprecated_ids`
- invalid local-id syntax for `concept` / `method` / `mechanism`
- structured relation endpoints that are bare symbols or otherwise lack typed ids

Expose a concise CLI section in `science_tool.cli.health_command()` and JSON output.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_health.py -q
uv run --frozen ruff check src/science_tool/graph/health.py src/science_tool/cli.py tests/test_health.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/graph/health.py \
        science-tool/src/science_tool/cli.py \
        science-tool/tests/test_health.py
git commit -m "feat: add entity identity health lints"
```

### Task 5: Add Cross-Project Identity Checks To Registry Sync

**Files:**
- Modify: `science-tool/src/science_tool/registry/index.py`
- Modify: `science-tool/src/science_tool/registry/sync.py`
- Test: `science-tool/tests/test_registry_index.py`
- Test: `science-tool/tests/test_registry_sync.py`
- Test: `science-tool/tests/test_sync_cli.py`

**Step 1: Write the failing tests**

Add registry tests for the new identity metadata and sync-time collision behavior.

```python
def test_registry_entity_round_trips_identity_metadata() -> None:
    entity = RegistryEntity(
        canonical_id="gene:EZH2",
        kind="gene",
        title="EZH2",
        profile="biology",
        scope="shared",
        primary_external_id={"source": "HGNC", "id": "3527", "curie": "HGNC:3527", "provenance": "manual"},
    )
    assert entity.primary_external_id is not None


def test_align_registry_warns_on_shared_id_collision() -> None:
    ...
    report = run_sync(...)
    assert any("canonical_id collision" in warning for warning in report.drift_warnings)
```

Add one test that a project-scoped collision remains namespaced and warned, rather than silently merged.

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_registry_index.py tests/test_registry_sync.py tests/test_sync_cli.py -q
```

Expected: FAIL because registry entities do not yet carry the new identity metadata and sync does not emit policy warnings.

**Step 3: Write the minimal implementation**

Extend `RegistryEntity` with the new fields and add collision/drift checks in `align_registry()` / `run_sync()`.

```python
class RegistryEntity(BaseModel):
    canonical_id: str
    kind: str
    title: str
    profile: str
    scope: str = "project"
    primary_external_id: ExternalId | None = None
    deprecated_ids: list[str] = Field(default_factory=list)
    taxon: str | None = None
```

Keep the current namespaced registry storage shape for v1, but compute warnings for:

- same bare `canonical_id` with incompatible shared metadata across projects
- same `primary_external_id` claimed by multiple different canonical ids
- project-scoped canonical-id collisions that need namespacing review

Thread these warnings through `SyncReport.drift_warnings` and the CLI.

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_registry_index.py tests/test_registry_sync.py tests/test_sync_cli.py -q
uv run --frozen ruff check src/science_tool/registry/index.py src/science_tool/registry/sync.py tests/test_registry_index.py tests/test_registry_sync.py tests/test_sync_cli.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add science-tool/src/science_tool/registry/index.py \
        science-tool/src/science_tool/registry/sync.py \
        science-tool/tests/test_registry_index.py \
        science-tool/tests/test_registry_sync.py \
        science-tool/tests/test_sync_cli.py
git commit -m "feat: enforce entity identity rules during sync"
```

### Task 6: Publish Curator Cookbook And Update Skill Guidance

**Files:**
- Create: `docs/process/entity-creation-cookbook.md`
- Modify: `codex-skills/science-health/SKILL.md`
- Modify: `codex-skills/science-create-graph/SKILL.md`
- Modify: `codex-skills/science-update-graph/SKILL.md`
- Modify: `codex-skills/science-sync/SKILL.md`
- Test: `science-tool/tests/test_command_docs.py`
- Test: `science-tool/tests/test_codex_skills.py`

**Step 1: Write the failing tests**

Add doc/skill tests that look for the new guidance anchors:

```python
def test_science_health_mentions_identity_policy_triage() -> None:
    ...


def test_create_graph_points_to_cookbook_for_new_entities() -> None:
    ...
```

The cookbook should include both positive and negative examples:

- gene
- protein
- family
- complex
- disease
- drug/chemical
- cell type
- phenotype
- pathway/process
- histone mark
- mechanism
- prose-only note
- “what not to create” examples such as `concept:high-proliferation-rate`

**Step 2: Run the tests to verify they fail**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_command_docs.py tests/test_codex_skills.py -q
```

Expected: FAIL because the cookbook and updated skill language do not exist yet.

**Step 3: Write the minimal implementation**

Add the cookbook and update skills to reference it directly.

Required guidance changes:

- `science-health`
  - stop recommending topic stubs or generic entity stubs
  - triage against semantic kind, external-id requirement, and prose-only fallback
- `science-create-graph`
  - tell curators to check shared kinds and the cookbook before creating local `concept:*`
- `science-update-graph`
  - mention fix-on-touch for legacy entities discovered during updates
- `science-sync`
  - explain scope and cross-project collision warnings

**Step 4: Run the tests to verify they pass**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen pytest tests/test_command_docs.py tests/test_codex_skills.py -q
```

Expected: PASS.

**Step 5: Commit**

```bash
git add docs/process/entity-creation-cookbook.md \
        codex-skills/science-health/SKILL.md \
        codex-skills/science-create-graph/SKILL.md \
        codex-skills/science-update-graph/SKILL.md \
        codex-skills/science-sync/SKILL.md \
        science-tool/tests/test_command_docs.py \
        science-tool/tests/test_codex_skills.py
git commit -m "docs: publish entity creation cookbook and skill guidance"
```

### Task 7: Full Verification And Close-Out

**Files:**
- Modify: `docs/plans/2026-04-23-entity-identity-policy-implementation.md`

**Step 1: Run focused verification after each task**

Use the task-local commands above immediately after each implementation slice.

**Step 2: Run full repo verification at the end**

Run:

```bash
cd /mnt/ssd/Dropbox/science/science-model
uv run --frozen ruff check .
uv run --frozen pyright
uv run --frozen pytest

cd /mnt/ssd/Dropbox/science/science-tool
uv run --frozen ruff check .
uv run --frozen pyright
uv run --frozen pytest
```

Expected: PASS in both packages.

**Step 3: Update the plan with any execution notes**

Record any scope reductions, unexpected collisions, or deferred checks directly in this plan file before merge.

**Step 4: Commit**

```bash
git add docs/plans/2026-04-23-entity-identity-policy-implementation.md
git commit -m "docs: record entity identity implementation verification"
```

## Recommended Execution Order

1. Task 1
2. Task 2
3. Task 3
4. Task 4
5. Task 5
6. Task 6
7. Task 7

## Expected Outcomes

- `Entity` instances can carry typed external identity, scope, lifecycle, and taxon metadata.
- Markdown and structured loaders preserve those fields consistently.
- `science-tool health` reports identity-policy violations directly.
- Cross-project sync warns on shared-id and primary-external-id collisions.
- Curators get a concrete cookbook and skill guidance aligned with the same policy.
