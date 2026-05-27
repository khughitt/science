# Pillar A1 — `source_class` / `derived_kind` / `dataset_usage` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record a dataset's epistemic class (`source_class`) and derived-subtype (`derived_kind`) on the core dataset model, plus the co-owned forward-provenance object (`dataset_usage`), so later phases can down-weight curated artifacts and derive independence — without yet touching the belief math (that is A2).

**Architecture:** Three new core fields land at four layers that already co-enforce the dataset invariants: the JSON mixin schema (`mixin-dataset-1.0.json`, the `EntityValidator` path), the Pydantic `Entity`/`DatasetEntity` models, the `frontmatter.py` parser, and a new tolerant `science validate` check (order 29) that re-enforces the rules on raw frontmatter. A small refactor first promotes the shared dataset-frontmatter discovery helper (currently private in the C `identity_context` check) into `validate/_helpers.py` so the new check reuses it instead of copying it a third time.

**Tech Stack:** Python 3.13, Pydantic v2, JSON Schema (draft 2020-12), `jsonschema` via `EntityValidator`, pytest, `uv` workspace.

---

## Scope & deviations (read before starting)

This plan implements **A1 only** (design `docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` §8). A2 (the curation down-weight in `belief.py`/`belief_scalar.py`, the `identification_strength: structural` tendency, and the `CONFIG_VERSION` bump) is a **separate plan**.

Three scope decisions, confirmed with the user, deviate slightly from a literal reading of the design and are called out so the reviewer sees they are intentional:

1. **`dataset_usage` ships its full schema here, not just the `{upstream, training}` slice.** A's design (A-D3, §4 resolved decision #1) and B's design (B-D1/B-D2) agree the object is *core and co-owned*. To honour B-D3's "one model, not two," A1 defines the complete `dataset_usage` shape — all six roles (`analyzed | set_definition_source | validation_source | cited | upstream | training`) and `overlap` (`full | partial | unknown`) — so Pillar B1 does **not** have to migrate a partial field. A1 only *validates/uses* the `{upstream, training}` projection (the A-D3 external-derived independence contract); B1 adds the materialization, `paper.datasets` migration, and the auto-independence semantics for the other roles.

2. **`source_class` is optional in the schema, surfaced by a WARN.** Making it `required` would break every existing dataset entity (and the committed commons reference collections). Instead the JSON schema constrains it to an enum *when present*, and the new validate check emits a WARN (`taxonomy.source-class-undeclared`) for any dataset that omits it — exactly mirroring how C's `identity.assembly-undeclared` nudges coordinate-bearing datasets. A2's modifier only fires on `source_class: reference`, so an absent class is the safe "no down-weight" default.

3. **The "`reference`-as-evidence without the modifier flagged" check (design A1 §8) is deferred to A2.** That check is only well-defined once the curation *modifier* exists (A2) and requires evidence-line→dataset resolution that A2's materialization introduces. A1 ships the dataset-recording checks (class presence, `derived_kind` consistency, external-derived provenance). The cross-entity "reference-as-evidence" check belongs with the modifier it refers to.

Authoritative schema: the `EntityValidator` resolves profile `science-entity-base/1.0+dataset/1.0` to `mixin-dataset-1.0.json` (`entity_schema/loader.py` `_filename_for`). `science-pkg-entity-1.0.json` is **not** run through `jsonschema` (the `DatapackageAdapter` only checks required-field presence, `graph/storage_adapters/datapackage.py:66`) and neither schema sets `additionalProperties:false`, so A1 targets `mixin-dataset-1.0.json` only.

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `science/src/science_tool/validate/_helpers.py` | shared validate-check helpers | **Add** `raw_frontmatter` + `dataset_frontmatters` (moved from `identity_context` and **broadened** to discover both markdown + datapackage datasets, `kind`-or-`type` filter) |
| `science/src/science_tool/validate/checks/identity_context.py` | C assembly/gene/protein checks | **Modify**: import the two helpers instead of defining them (gains markdown-dataset coverage) |
| `science/model/src/science_model/schemas/mixin-dataset-1.0.json` | dataset entity JSON schema | **Add** `source_class`, `derived_kind`, `dataset_usage` props + `$defs/dataset_usage` + two `if/then` clauses |
| `science/model/src/science_model/packages/schema.py` | dataset block models | **Add** `DatasetUsage` block model |
| `science/model/src/science_model/entities.py` | `Entity` / `DatasetEntity` | **Add** three fields to `Entity`; **add** a kind-gated `_validate_dataset_taxonomy` validator on `Entity` (covers both load paths) |
| `science/model/src/science_model/frontmatter.py` | frontmatter → `Entity` (the `plan_gate` path) | wire three fields into `entity_kwargs` (raw `dataset_usage` → Pydantic validates) |
| `science/src/science_tool/graph/storage_adapters/datapackage.py` | datapackage-backed dataset loading (the **graph** path) | **Add** the three fields to `_ENTITY_FIELDS` whitelist |
| `science/src/science_tool/validate/checks/dataset_taxonomy.py` | the new check | **Create**: pure `evaluate_dataset_taxonomy` + `@Check(order=29)` wrapper |
| `science/src/science_tool/validate/checks/__init__.py` | check registry | **Modify**: register `dataset_taxonomy` |
| `science/model/tests/test_entity_schema_mixin_dataset.py` | JSON schema tests | **Add** source_class/derived_kind/dataset_usage cases |
| `science/model/tests/test_dataset_models.py` | model tests | **Add** `DatasetUsage` + invariant cases |
| `science/model/tests/test_frontmatter*.py` (or new) | parse round-trip | **Add** coercion test |
| `science/tests/validate/test_checks_dataset_taxonomy.py` | check tests | **Create** |

**Test command (all tasks):** run from `~/d/science/science`:
```bash
cd ~/d/science/science && uv run pytest <path> -q
```
Model tests live under `model/tests/`; tool/validate tests under `tests/`.

**Two dataset load paths (both must carry the fields):**
- **`parse_entity_file`** (`frontmatter.py`) — used by `plan_gate.py`. Covered by Task 5.
- **Graph loader** (`graph/sources.py` `load_project_sources`) — uses storage adapters + `schema.model_validate(raw)`, **not** `parse_entity_file`. `MarkdownAdapter.load_raw` returns the full frontmatter (so markdown datasets surface the fields once `Entity` declares them — Task 4 — and Pydantic coerces `dataset_usage` dicts to `DatasetUsage`). `DatapackageAdapter.load_raw` projects onto a whitelist and must be extended (Task 6).

Shell commands are written plain; apply this repo's `rtk` convention per your runtime's own RTK instruction (hook-rewritten on some, manually-prefixed on others).

---

## Task 1: Promote + broaden the shared dataset-frontmatter discovery helper

The C `identity_context` check defines `_raw_frontmatter` and `_dataset_frontmatters` (tolerant discovery that does **not** strict-validate through the graph loader). The new A1 check needs the same discovery, so move both into `validate/_helpers.py` (the shared-helpers module) and rewire `identity_context` to import them — instead of copying a third time.

**One deliberate behaviour change:** the current `_dataset_frontmatters` only loops `DatapackageAdapter().discover` (`data/`, `results/`), so it sees **only datapackage-backed datasets** and misses hand-authored markdown datasets in `doc/datasets/` — exactly where most `source_class: observational|reference` datasets live. "Every project dataset entity" must include both backends, so the moved helper also scans markdown datasets (`MarkdownAdapter` scoped to `doc/datasets` for cost), filters on `kind`-or-`type` `== "dataset"`, and de-dupes by id. This *expands* the C identity checks to markdown datasets too — a latent gap, and strictly additional coverage: those checks already skip datasets that are not coordinate-bearing / declare no tier, so a well-formed markdown dataset yields no new diagnostics. The C test suite is the guard (Step 3); a failure there means a test encoded the datapackage-only assumption and is a coverage decision to surface.

**Files:**
- Modify: `science/src/science_tool/validate/_helpers.py`
- Modify: `science/src/science_tool/validate/checks/identity_context.py:54-64,166-184` (remove local defs, import instead)
- Test: existing `science/tests/validate/` C check tests (regression) + a unit test for the broadened discovery

- [ ] **Step 1: Add the two helpers to `_helpers.py`**

Append to `science/src/science_tool/validate/_helpers.py` (it already imports `Path`, `yaml`, and `ValidateContext` under `TYPE_CHECKING`):

```python
from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
from science_tool.graph.storage_adapters.markdown import MarkdownAdapter


def raw_frontmatter(path: Path) -> dict[str, Any]:
    """Raw frontmatter for either an entity.md (fenced YAML) or a datapackage.yaml.

    Reads directly (uncached) and tolerates malformed input by returning {} —
    callers re-enforce schema-critical fields themselves, because raw frontmatter
    bypasses the closed graph Entity.
    """
    text = path.read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text) or {}
    elif text.startswith("---"):
        end = text.find("\n---", 3)
        data = yaml.safe_load(text[3:end]) if end != -1 else {}
    else:
        data = {}
    return data if isinstance(data, dict) else {}


def dataset_frontmatters(ctx: ValidateContext) -> list[dict[str, Any]]:
    """Raw frontmatter for every project dataset entity, BOTH backends, by tolerant
    file discovery that does NOT strict-validate through the graph loader (which
    RAISES on a malformed core-kind entity and would crash the run):

    - datapackage-backed datasets (`DatapackageAdapter`: data/, results/)
    - markdown datasets (`MarkdownAdapter` scoped to doc/datasets/)

    `kind` is the canonical field; `type` is the authored alias — accept either.
    Each dict carries `_path` (project-relative). De-duped by entity id (first wins).
    """
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    adapters = (DatapackageAdapter(), MarkdownAdapter(scan_roots=["doc/datasets"]))
    for adapter in adapters:
        for ref in adapter.discover(ctx.project_root):
            abs_path = ctx.project_root / ref.path
            if not abs_path.is_file():
                continue
            fm = raw_frontmatter(abs_path)
            if (fm.get("kind") or fm.get("type")) != "dataset":
                continue
            ident = fm.get("id")
            if isinstance(ident, str) and ident:
                if ident in seen_ids:
                    continue
                seen_ids.add(ident)
            fm["_path"] = ref.path
            out.append(fm)
    return out
```

Notes: `ValidateContext` stays `TYPE_CHECKING`-only (used as an annotation). `DatapackageAdapter` and `MarkdownAdapter` are runtime imports. Scoping `MarkdownAdapter` to `doc/datasets` (the canonical dataset location) bounds the cost — it does not read the whole `doc/` tree.

- [ ] **Step 2: Rewire `identity_context.py` to import them**

In `science/src/science_tool/validate/checks/identity_context.py`, delete the local `_raw_frontmatter` (lines ~54-64) and `_dataset_frontmatters` (lines ~166-184) definitions. Add the import near the other validate imports:

```python
from science_tool.validate._helpers import dataset_frontmatters, raw_frontmatter
```

Then replace every internal call: `_dataset_frontmatters(ctx)` → `dataset_frontmatters(ctx)` (4 call sites: `check_identity_context_assembly`, `check_cross_dataset_assembly`, `_run_tier_check`, and the `local_by_id` build) and `_raw_frontmatter(...)` → `raw_frontmatter(...)` (in `_load_registry_meta`). The `DatapackageAdapter` import in `identity_context.py` is now unused — remove it if no other reference remains (grep first).

- [ ] **Step 3: Add a discovery unit test + run the C regression suite**

Add to `science/tests/validate/` (e.g. a new `test_helpers_dataset_discovery.py`) a test that both backends are discovered:

```python
from pathlib import Path

import yaml

from science_tool.validate._helpers import dataset_frontmatters


class _Ctx:
    def __init__(self, root: Path) -> None:
        self.project_root = root


def test_dataset_frontmatters_covers_markdown_and_datapackage(tmp_path: Path) -> None:
    (tmp_path / "doc" / "datasets").mkdir(parents=True)
    (tmp_path / "doc" / "datasets" / "gtex.md").write_text(
        "---\nid: dataset:gtex\ntype: dataset\ntitle: GTEx\n---\nBody.\n", encoding="utf-8"
    )
    (tmp_path / "data" / "refcoll").mkdir(parents=True)
    (tmp_path / "data" / "refcoll" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "refcoll",
                "id": "dataset:refcoll",
                "type": "dataset",
                "title": "Ref coll",
            }
        ),
        encoding="utf-8",
    )
    ids = {fm["id"] for fm in dataset_frontmatters(_Ctx(tmp_path))}  # type: ignore[arg-type]
    assert ids == {"dataset:gtex", "dataset:refcoll"}
```

Then run the full check suite:
```bash
cd ~/d/science/science && uv run pytest tests/validate/ model/tests/test_bio_extension_identity_context.py -q
```
Expected: PASS. The C identity checks now also see `doc/datasets/` markdown datasets; a well-formed project yields no new diagnostics. If a pre-existing C test fails, inspect whether it asserted datapackage-only scope (a coverage decision to raise), not a logic break.

- [ ] **Step 4: Commit**

```bash
git add science/src/science_tool/validate/_helpers.py science/src/science_tool/validate/checks/identity_context.py science/tests/validate/test_helpers_dataset_discovery.py
git commit -m "refactor(validate): promote + broaden dataset discovery to both backends (A1 prep)"
```

---

## Task 2: JSON schema — `source_class`, `derived_kind`, `dataset_usage`

Add the three fields and the conditional-requirement clauses to `mixin-dataset-1.0.json`. The schema is the authoritative `EntityValidator` surface.

**Files:**
- Modify: `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
- Test: `science/model/tests/test_entity_schema_mixin_dataset.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_entity_schema_mixin_dataset.py`:

```python
def test_dataset_observational_source_class_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "observational",
    }
    EntityValidator().validate(entity)


def test_dataset_reference_source_class_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "reference",
    }
    EntityValidator().validate(entity)


def test_dataset_source_class_invalid_enum_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "curated",  # not in enum
    }
    with pytest.raises(EntityValidationError, match="source_class"):
        EntityValidator().validate(entity)


def test_dataset_derived_class_requires_derived_kind(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "derived",  # derived_kind missing
    }
    with pytest.raises(EntityValidationError, match="derived_kind"):
        EntityValidator().validate(entity)


def test_dataset_derived_class_with_kind_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "derived",
        "derived_kind": "model_output",
    }
    EntityValidator().validate(entity)


def test_dataset_derived_kind_without_derived_class_rejected(base_entity: dict) -> None:
    # derived_kind is only meaningful when source_class == derived.
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "observational",
        "derived_kind": "aggregate",
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_usage_entry_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "source_class": "derived",
        "derived_kind": "model_output",
        "dataset_usage": [
            {"ref": "dataset:training-corpus", "role": "training", "overlap": "full"}
        ],
    }
    EntityValidator().validate(entity)


def test_dataset_usage_bad_role_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "dataset_usage": [{"ref": "dataset:x", "role": "consulted"}],  # bad role
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)


def test_dataset_usage_ref_must_be_dataset_prefixed(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "dataset_usage": [{"ref": "paper:smith2024", "role": "analyzed"}],
    }
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(entity)
```

- [ ] **Step 2: Run to verify they fail**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/test_entity_schema_mixin_dataset.py -q
```
Expected: the new tests FAIL (the schema does not yet constrain the fields; absent `additionalProperties:false` means unknown values currently pass, so the `*_rejected` tests fail).

- [ ] **Step 3: Edit `mixin-dataset-1.0.json`**

Add three entries to `properties` (after `"consumed_by"`):

```json
    "consumed_by": {"type": "array", "items": {"type": "string"}},
    "source_class": {"enum": ["observational", "derived", "reference"]},
    "derived_kind": {"enum": ["aggregate", "transform", "model_output"]},
    "dataset_usage": {"$ref": "#/$defs/dataset_usage"}
```

Add two clauses to the existing top-level `allOf` array (alongside the origin clauses):

```json
    {
      "if": {"properties": {"source_class": {"const": "derived"}}, "required": ["source_class"]},
      "then": {"required": ["derived_kind"]}
    },
    {
      "if": {"required": ["derived_kind"]},
      "then": {"properties": {"source_class": {"const": "derived"}}, "required": ["source_class"]}
    }
```

Add one entry to `$defs` (alongside `access` and `derivation`):

```json
    "dataset_usage": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["ref", "role"],
        "properties": {
          "ref": {"type": "string", "pattern": "^dataset:"},
          "role": {"enum": ["analyzed", "set_definition_source", "validation_source", "cited", "upstream", "training"]},
          "overlap": {"enum": ["full", "partial", "unknown"]}
        }
      }
    }
```

- [ ] **Step 4: Run to verify PASS**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/test_entity_schema_mixin_dataset.py -q
```
Expected: PASS (all, including the pre-existing cases).

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-dataset-1.0.json science/model/tests/test_entity_schema_mixin_dataset.py
git commit -m "feat(bio): source_class/derived_kind/dataset_usage on dataset mixin schema (A1)"
```

---

## Task 3: `DatasetUsage` Pydantic block model

Add the block model that mirrors the `$defs/dataset_usage` item shape, with field validators matching the `DerivationBlock`/`MemberOfDerivationBlock` style already in this module.

**Files:**
- Modify: `science/model/src/science_model/packages/schema.py` (after `MemberOfDerivationBlock`, ~line 176)
- Test: `science/model/tests/test_dataset_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_dataset_models.py` (extend the existing import on line 8 to add `DatasetUsage`):

```python
from science_model.packages.schema import AccessBlock, AccessException, DatasetUsage, DerivationBlock


class TestDatasetUsage:
    def test_minimal_defaults_overlap_unknown(self) -> None:
        u = DatasetUsage(ref="dataset:gtex-v8", role="analyzed")
        assert u.ref == "dataset:gtex-v8"
        assert u.role == "analyzed"
        assert u.overlap == "unknown"

    def test_training_role_full_overlap(self) -> None:
        u = DatasetUsage(ref="dataset:corpus", role="training", overlap="full")
        assert u.role == "training"
        assert u.overlap == "full"

    def test_ref_must_be_dataset_prefixed(self) -> None:
        with pytest.raises(ValueError, match="dataset:"):
            DatasetUsage(ref="paper:smith2024", role="cited")

    def test_invalid_role_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetUsage(ref="dataset:x", role="consulted")  # type: ignore[arg-type]

    def test_invalid_overlap_rejected(self) -> None:
        with pytest.raises(ValueError):
            DatasetUsage(ref="dataset:x", role="analyzed", overlap="some")  # type: ignore[arg-type]
```

- [ ] **Step 2: Run to verify ImportError/failure**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/test_dataset_models.py::TestDatasetUsage -q
```
Expected: FAIL (`ImportError: cannot import name 'DatasetUsage'`).

- [ ] **Step 3: Add the model**

In `science/model/src/science_model/packages/schema.py`, after `MemberOfDerivationBlock` (the file already imports `Literal`, `BaseModel`, `Field`, `field_validator`):

```python
class DatasetUsage(BaseModel):
    """Forward-provenance: a consumer's declared use of one dataset (Pillar A/B).

    Co-owned by Pillar A (which uses the `{upstream, training}` projection for the
    external-derived independence contract, A-D3) and Pillar B (which adds the
    materialization, role semantics, and auto-independence). A1 defines the full
    shape so B1 does not migrate a partial field.
    """

    ref: str
    role: Literal[
        "analyzed", "set_definition_source", "validation_source", "cited", "upstream", "training"
    ]
    overlap: Literal["full", "partial", "unknown"] = "unknown"

    @field_validator("ref")
    @classmethod
    def _ref_id(cls, v: str) -> str:
        if not v.startswith("dataset:"):
            raise ValueError("dataset_usage.ref must be a dataset:<slug> entity reference")
        return v
```

- [ ] **Step 4: Run to verify PASS**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/test_dataset_models.py::TestDatasetUsage -q
```
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/packages/schema.py science/model/tests/test_dataset_models.py
git commit -m "feat(model): DatasetUsage block model (A1)"
```

---

## Task 4: `Entity` fields + dataset-taxonomy invariant (kind-gated)

Add the three fields to the `Entity` model and enforce the `source_class` enum + `derived_kind` ⟺ `source_class == derived` rule with an **`Entity`-level** `@model_validator` **gated on `kind == "dataset"`**.

Why `Entity`, not `DatasetEntity`: `parse_entity_file` returns a **plain `Entity`** for datasets (`frontmatter.py:401` — there is no `dataset` branch), so a validator that lives only on `DatasetEntity` would not fire on the `plan_gate` parse path. `DatasetEntity` inherits `Entity`'s validators, so a single kind-gated `Entity` validator covers **both** the parse path (plain `Entity`) and the graph path (`model_validate` → `DatasetEntity`). It is independent of `origin`, so it also sidesteps `DatasetEntity._enforce_dataset_invariants`'s `origin is None` early return. The existing origin invariants (#7/#8) on `DatasetEntity` are **untouched**.

**Files:**
- Modify: `science/model/src/science_model/entities.py:278-288` (Entity fields) + add one `@model_validator` on `Entity` (near `_validate_review_state_kind`, ~line 247). `DatasetEntity` is **not** modified.
- Test: `science/model/tests/test_dataset_models.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_dataset_models.py`:

```python
def test_entity_carries_source_class_and_dataset_usage() -> None:
    e = Entity(
        **_entity_kwargs(),
        origin="external",
        access=_ext_access(),
        source_class="observational",
        dataset_usage=[DatasetUsage(ref="dataset:up", role="analyzed")],
    )
    assert e.source_class == "observational"
    assert e.dataset_usage[0].role == "analyzed"


# --- enforced on the plain-Entity (parse_entity_file / plan_gate) path ---


def test_entity_dataset_kind_invalid_source_class_rejects() -> None:
    with pytest.raises(ValueError, match="source_class"):
        Entity(**_entity_kwargs(), origin="external", access=_ext_access(), source_class="curated")


def test_entity_dataset_kind_derived_requires_derived_kind() -> None:
    with pytest.raises(ValueError, match="derived_kind"):
        Entity(**_entity_kwargs(), origin="external", access=_ext_access(), source_class="derived")


def test_entity_dataset_kind_misplaced_derived_kind_rejects() -> None:
    with pytest.raises(ValueError, match="derived_kind"):
        Entity(
            **_entity_kwargs(),
            origin="external",
            access=_ext_access(),
            source_class="observational",
            derived_kind="aggregate",
        )


def test_non_dataset_kind_does_not_validate_source_class() -> None:
    # Gate: the taxonomy rule applies only to kind == "dataset".
    e = Entity(
        id="hypothesis:h1",
        kind="hypothesis",
        type=EntityType.HYPOTHESIS,
        title="H1",
        project="p",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/hypotheses/h1.md",
        source_class="curated",  # not validated for non-datasets
    )
    assert e.source_class == "curated"


# --- also enforced on the graph path (DatasetEntity inherits the Entity validator) ---


def test_dataset_entity_derived_class_with_kind_ok() -> None:
    ds = DatasetEntity(
        **_entity_kwargs(),
        origin="external",
        access=_ext_access(),
        source_class="derived",
        derived_kind="model_output",
    )
    assert ds.derived_kind == "model_output"


def test_dataset_entity_invalid_source_class_rejects() -> None:
    with pytest.raises(ValueError, match="source_class"):
        DatasetEntity(
            **_entity_kwargs(), origin="external", access=_ext_access(), source_class="curated"
        )


def test_dataset_entity_invalid_source_class_rejected_without_origin() -> None:
    # The taxonomy validator is independent of origin (not behind the origin=None
    # early return in _enforce_dataset_invariants).
    with pytest.raises(ValueError, match="source_class"):
        DatasetEntity(**_entity_kwargs(), source_class="curated")
```

Note: `EntityType` is already imported in this test module; `HYPOTHESIS` exists on it.

- [ ] **Step 2: Run to verify failure**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/test_dataset_models.py -q -k "source_class or derived_kind or dataset_usage"
```
Expected: FAIL (`Entity` has no `source_class`/`derived_kind`/`dataset_usage`).

- [ ] **Step 3: Add the `Entity` fields**

In `science/model/src/science_model/entities.py`, extend the dataset block (after `siblings`, ~line 288). Ensure `DatasetUsage` is imported at the top of the file alongside the other `packages.schema` imports (`AccessBlock`, `DerivationBlock`, `MemberOfDerivationBlock`):

```python
    parent_dataset: str = ""
    siblings: list[str] = Field(default_factory=list)
    # Pillar A — epistemic class (orthogonal to origin) + co-owned forward provenance
    source_class: str | None = None       # "observational" | "derived" | "reference"
    derived_kind: str | None = None        # "aggregate" | "transform" | "model_output"
    dataset_usage: list[DatasetUsage] = Field(default_factory=list)
```

(Typed as `str | None` to match the existing `origin: str | None` style; the enum + conditional are enforced by the kind-gated `Entity` validator below and by the JSON schema. `dataset_usage` is typed `list[DatasetUsage]`, so Pydantic itself validates each entry's shape on both load paths.)

- [ ] **Step 4: Add the kind-gated `Entity` validator**

In `science/model/src/science_model/entities.py`, add a new `@model_validator(mode="after")` on `Entity` (place it near the existing `_validate_review_state_kind` validator, ~line 247):

```python
    @model_validator(mode="after")
    def _validate_dataset_taxonomy(self) -> "Entity":
        # Pillar A (A-D1/A-D4): on dataset entities, source_class is a small epistemic
        # class and derived_kind is required exactly when source_class == "derived".
        # Lives on Entity (gated to kind) — not DatasetEntity — so it also covers the
        # parse_entity_file path, which returns a plain Entity for datasets.
        if self.kind != "dataset":
            return self
        if self.source_class is not None and self.source_class not in (
            "observational",
            "derived",
            "reference",
        ):
            raise ValueError(
                f"{self.id}: source_class must be observational|derived|reference, "
                f"got {self.source_class!r}"
            )
        if self.source_class == "derived":
            if self.derived_kind not in ("aggregate", "transform", "model_output"):
                raise ValueError(
                    f"{self.id}: source_class=derived requires derived_kind "
                    f"(aggregate|transform|model_output), got {self.derived_kind!r}"
                )
        elif self.derived_kind is not None:
            raise ValueError(
                f"{self.id}: derived_kind is only allowed when source_class=derived "
                f"(got source_class={self.source_class!r})"
            )
        return self
```

- [ ] **Step 5: Run to verify PASS**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/test_dataset_models.py -q
```
Expected: PASS (new + all pre-existing).

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_dataset_models.py
git commit -m "feat(model): source_class/derived_kind/dataset_usage fields + kind-gated taxonomy validator (A1)"
```

---

## Task 5: frontmatter parsing

Wire the three fields through `parse_entity_file` so authored frontmatter round-trips into the model. **No custom `dataset_usage` coercer** — the raw value is passed straight through and Pydantic's `list[DatasetUsage]` field (Task 4) validates it. This is fail-early (a malformed entry raises a `ValidationError` rather than being silently dropped) and keeps the parse path and the graph `model_validate` path validating `dataset_usage` identically. `source_class`/`derived_kind` pass through as plain scalars; the kind-gated `Entity` validator (Task 4) enforces them on this path too, since `parse_entity_file` returns a plain `Entity` for datasets.

**Files:**
- Modify: `science/model/src/science_model/frontmatter.py` (extend `entity_kwargs` ~line 370)
- Test: `science/model/tests/test_dataset_models.py` (parse round-trip + fail-early) — `test_dataset_models.py` for locality (already imports `parse_entity_file`? add the import if absent).

- [ ] **Step 1: Write the failing tests**

Append to `science/model/tests/test_dataset_models.py` (ensure `from pathlib import Path`, `from science_model.frontmatter import parse_entity_file`, and `from pydantic import ValidationError` are imported at the top):

```python
def _write_dataset_md(tmp_path: Path, *extra_lines: str) -> Path:
    md = tmp_path / "ds.md"
    md.write_text(
        "---\n"
        "id: dataset:ds\n"
        "type: dataset\n"
        "title: A dataset\n"
        "origin: external\n"
        "tier: evaluate-next\n"
        "datapackage: data/ds/datapackage.yaml\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n" + "".join(line + "\n" for line in extra_lines) + "---\nBody.\n",
        encoding="utf-8",
    )
    return md


def test_parse_dataset_source_class_and_usage(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path,
        "source_class: derived",
        "derived_kind: model_output",
        "dataset_usage:",
        "  - ref: dataset:clinvar-training",
        "    role: training",
        "    overlap: full",
    )
    e = parse_entity_file(md, project_slug="testproj")
    assert e is not None
    assert e.source_class == "derived"
    assert e.derived_kind == "model_output"
    assert len(e.dataset_usage) == 1
    assert e.dataset_usage[0].ref == "dataset:clinvar-training"
    assert e.dataset_usage[0].role == "training"
    assert e.dataset_usage[0].overlap == "full"


def test_parse_dataset_invalid_source_class_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(tmp_path, "source_class: curated")
    with pytest.raises(ValidationError, match="source_class"):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_derived_without_kind_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(tmp_path, "source_class: derived")
    with pytest.raises(ValidationError, match="derived_kind"):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_misplaced_derived_kind_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(tmp_path, "source_class: observational", "derived_kind: aggregate")
    with pytest.raises(ValidationError, match="derived_kind"):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_malformed_usage_raises(tmp_path: Path) -> None:
    # A mapping authored without the leading list `-` must NOT be silently dropped.
    md = _write_dataset_md(tmp_path, "dataset_usage:", "  ref: dataset:x", "  role: training")
    with pytest.raises(ValidationError):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_empty_mapping_usage_raises(tmp_path: Path) -> None:
    # Present-but-non-list `dataset_usage: {}` is a defect, not "no usage" — fail early
    # (parity with the validate check), not silently coerced to [].
    md = _write_dataset_md(tmp_path, "dataset_usage: {}")
    with pytest.raises(ValidationError):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_usage_bad_role_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path, "dataset_usage:", "  - ref: dataset:x", "    role: consulted"
    )
    with pytest.raises(ValidationError):
        parse_entity_file(md, project_slug="testproj")
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/test_dataset_models.py -q -k parse_dataset
```
Expected: FAIL — `test_parse_dataset_source_class_and_usage` fails (`dataset_usage == []`); the `*_raises` tests fail (the parser currently drops the fields, so nothing raises).

- [ ] **Step 3: Wire the fields into `entity_kwargs`**

In `parse_entity_file`, add to the `entity_kwargs` dict (after `"siblings": ...`, ~line 370). Pass `dataset_usage` raw so Pydantic validates `list[DatasetUsage]` (no silent coercer):

```python
        "siblings": list(fm.get("siblings") or []),
        "source_class": fm.get("source_class"),
        "derived_kind": fm.get("derived_kind"),
        "dataset_usage": [] if fm.get("dataset_usage") is None else fm.get("dataset_usage"),
```

Absent or null `dataset_usage` → `[]` (no usage). Any *present* non-`None` value — a list (validated entry-by-entry), or a non-list including `{}` / `""` — flows to Pydantic's `list[DatasetUsage]`, which raises. This matches the Task 7 check's stance (None-tolerant, present-non-list-strict) and avoids `or []` silently swallowing `{}`/`""`. No `_coerce_dataset_usage` helper is added.

- [ ] **Step 5: Run to verify PASS**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/test_dataset_models.py -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/frontmatter.py science/model/tests/test_dataset_models.py
git commit -m "feat(model): parse source_class/derived_kind/dataset_usage frontmatter (A1)"
```

---

## Task 6: `DatapackageAdapter` — surface A1 fields on datapackage-backed datasets

The graph loader (`graph/sources.py` `load_project_sources`) builds entities via storage adapters + `schema.model_validate(raw)`, **not** via `parse_entity_file`. `DatapackageAdapter.load_raw` projects the datapackage onto a whitelist, `_ENTITY_FIELDS` (`datapackage.py:15-38`, applied at `:87` as `raw = {k: dp[k] for k in _ENTITY_FIELDS if k in dp}`), dropping every other key. Promoted `member_of` datasets — including C's identity reference collections, the umbrella's **first** `source_class: reference` datasets — live as `datapackage.yaml`, so without this fix the three A1 fields never reach `DatasetEntity` on the main storage path and A2 cannot read them. (`MarkdownAdapter.load_raw` returns the full frontmatter, so markdown-backed datasets need no adapter change — Task 4's `Entity` fields suffice and Pydantic coerces.)

**Files:**
- Modify: `science/src/science_tool/graph/storage_adapters/datapackage.py:15-38` (`_ENTITY_FIELDS`)
- Test: `science/tests/test_storage_adapters/test_datapackage.py`

- [ ] **Step 1: Write the failing test**

Append to `science/tests/test_storage_adapters/test_datapackage.py`:

```python
def test_load_raw_surfaces_a1_taxonomy_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # A promoted reference-collection member (datapackage-backed) declaring A1 fields.
    (tmp_path / "data" / "refcoll").mkdir(parents=True)
    (tmp_path / "data" / "refcoll" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "refcoll",
                "id": "dataset:refcoll",
                "type": "dataset",
                "title": "Ref coll",
                "origin": "external",
                "access": {"level": "public", "verified": True},
                "source_class": "reference",
                "dataset_usage": [
                    {"ref": "dataset:src", "role": "set_definition_source", "overlap": "full"}
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    [ref] = DatapackageAdapter().discover(tmp_path)
    raw = DatapackageAdapter().load_raw(ref)
    assert raw["source_class"] == "reference"
    assert raw["dataset_usage"][0]["role"] == "set_definition_source"


def test_load_raw_surfaces_derived_kind(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "data" / "am").mkdir(parents=True)
    (tmp_path / "data" / "am" / "datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "name": "am",
                "id": "dataset:am",
                "type": "dataset",
                "title": "AlphaMissense",
                "origin": "external",
                "access": {"level": "public", "verified": True},
                "source_class": "derived",
                "derived_kind": "model_output",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    [ref] = DatapackageAdapter().discover(tmp_path)
    raw = DatapackageAdapter().load_raw(ref)
    assert raw["source_class"] == "derived"
    assert raw["derived_kind"] == "model_output"
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
cd ~/d/science/science && uv run pytest tests/test_storage_adapters/test_datapackage.py -q -k "a1_taxonomy or derived_kind"
```
Expected: FAIL (`KeyError`/`assert` — `_ENTITY_FIELDS` drops the keys, so `raw` lacks them).

- [ ] **Step 3: Extend `_ENTITY_FIELDS`**

In `science/src/science_tool/graph/storage_adapters/datapackage.py`, add three entries to the `_ENTITY_FIELDS` tuple (e.g. after `"siblings",`):

```python
    "siblings",
    "source_class",
    "derived_kind",
    "dataset_usage",
    "ontology_terms",
```

- [ ] **Step 4: Run to verify PASS**

Run:
```bash
cd ~/d/science/science && uv run pytest tests/test_storage_adapters/test_datapackage.py -q
```
Expected: PASS (new + pre-existing).

Coverage note: the adapter test proves the fields survive the whitelist into `raw`; Task 4's model tests prove `DatasetEntity` accepts those exact fields (and Pydantic coerces `dataset_usage` dicts → `DatasetUsage`). Together they cover the datapackage graph-load path end-to-end without standing up a full project fixture.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/storage_adapters/datapackage.py science/tests/test_storage_adapters/test_datapackage.py
git commit -m "fix(graph): surface source_class/derived_kind/dataset_usage on datapackage-backed datasets (A1)"
```

---

## Task 7: `science validate` check (order 29)

A tolerant check that reads raw dataset frontmatter (bypassing the strict graph loader, like the C checks) and re-enforces the A1 rules with friendly messages, plus the A-D3 external-derived provenance nudge. Pure evaluator + thin `@Check` wrapper, mirroring `evaluate_tier_identity`.

**Files:**
- Create: `science/src/science_tool/validate/checks/dataset_taxonomy.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py` (register the module)
- Test: `science/tests/validate/test_checks_dataset_taxonomy.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/validate/test_checks_dataset_taxonomy.py`:

```python
from __future__ import annotations

from science_tool.validate.checks.dataset_taxonomy import evaluate_dataset_taxonomy
from science_tool.validate.result import Severity


def _rules(datasets: list[dict]) -> list[tuple[Severity, str]]:
    return [(r.severity, r.rule) for r in evaluate_dataset_taxonomy(datasets)]


def _ds(**kw) -> dict:
    base = {"type": "dataset", "id": "dataset:x", "_path": "doc/datasets/x.md"}
    base.update(kw)
    return base


def test_undeclared_source_class_warns() -> None:
    rules = _rules([_ds(origin="external")])
    assert (Severity.WARN, "taxonomy.source-class-undeclared") in rules


def test_observational_clean_passes_silently() -> None:
    rules = _rules([_ds(origin="external", source_class="observational")])
    assert rules == []


def test_invalid_source_class_errors() -> None:
    rules = _rules([_ds(origin="external", source_class="curated")])
    assert (Severity.ERROR, "taxonomy.source-class-invalid") in rules


def test_derived_without_kind_errors() -> None:
    rules = _rules([_ds(origin="external", source_class="derived")])
    assert (Severity.ERROR, "taxonomy.derived-kind-missing") in rules


def test_derived_with_bad_kind_errors() -> None:
    rules = _rules([_ds(origin="external", source_class="derived", derived_kind="guess")])
    assert (Severity.ERROR, "taxonomy.derived-kind-invalid") in rules


def test_derived_kind_misplaced_errors() -> None:
    rules = _rules([_ds(origin="external", source_class="observational", derived_kind="aggregate")])
    assert (Severity.ERROR, "taxonomy.derived-kind-misplaced") in rules


def test_external_derived_without_upstream_provenance_warns() -> None:
    rules = _rules([_ds(origin="external", source_class="derived", derived_kind="model_output")])
    assert (Severity.WARN, "taxonomy.external-derived-no-provenance") in rules


def test_external_derived_with_training_usage_no_provenance_warn() -> None:
    ds = _ds(
        origin="external",
        source_class="derived",
        derived_kind="model_output",
        dataset_usage=[{"ref": "dataset:corpus", "role": "training", "overlap": "full"}],
    )
    rules = [r for sev, r in _rules([ds])]
    assert "taxonomy.external-derived-no-provenance" not in rules


def test_malformed_dataset_usage_errors() -> None:
    ds = _ds(origin="external", source_class="observational", dataset_usage=[{"role": "analyzed"}])
    rules = _rules([ds])
    assert (Severity.ERROR, "taxonomy.dataset-usage-malformed") in rules


def test_dataset_usage_bad_role_errors() -> None:
    ds = _ds(
        origin="external",
        source_class="observational",
        dataset_usage=[{"ref": "dataset:x", "role": "consulted"}],
    )
    rules = _rules([ds])
    assert (Severity.ERROR, "taxonomy.dataset-usage-malformed") in rules


def test_non_list_dataset_usage_errors() -> None:
    # A single mapping authored without the leading list `-` is a defect, not "empty".
    ds = _ds(
        origin="external",
        source_class="observational",
        dataset_usage={"ref": "dataset:x", "role": "training"},
    )
    assert (Severity.ERROR, "taxonomy.dataset-usage-malformed") in _rules([ds])


def test_non_dataset_ignored() -> None:
    assert _rules([{"type": "paper", "id": "paper:p", "_path": "x"}]) == []


def test_kind_dataset_without_type_is_checked() -> None:
    # `kind` is the canonical field; a dataset declaring only kind must be evaluated.
    rules = _rules([{"kind": "dataset", "id": "dataset:k", "_path": "doc/datasets/k.md"}])
    assert (Severity.WARN, "taxonomy.source-class-undeclared") in rules
```

- [ ] **Step 2: Run to verify failure**

Run:
```bash
cd ~/d/science/science && uv run pytest tests/validate/test_checks_dataset_taxonomy.py -q
```
Expected: FAIL (`ModuleNotFoundError: ...dataset_taxonomy`).

- [ ] **Step 3: Create the check module**

Create `science/src/science_tool/validate/checks/dataset_taxonomy.py`:

```python
"""Dataset taxonomy checks (Pillar A1): source_class / derived_kind / dataset_usage.

Reads RAW frontmatter (the closed graph Entity does not surface these on a tolerant
discovery pass, and a malformed core-kind entity would otherwise crash the strict
loader), so the schema-critical rules are re-enforced here with friendly messages.
The curation down-weight itself, and the reference-as-evidence cross-entity check,
land in A2. See docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_SOURCE_CLASSES = ("observational", "derived", "reference")
_DERIVED_KINDS = ("aggregate", "transform", "model_output")
_USAGE_ROLES = (
    "analyzed",
    "set_definition_source",
    "validation_source",
    "cited",
    "upstream",
    "training",
)
_USAGE_OVERLAPS = ("full", "partial", "unknown")
_DEPENDENCE_PROVENANCE_ROLES = ("upstream", "training")


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _usage_defect(entry: Any) -> str | None:
    """Defect message for one dataset_usage entry, or None if well-formed."""
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    if entry.get("role") not in _USAGE_ROLES:
        return f"role must be one of {list(_USAGE_ROLES)}"
    overlap = entry.get("overlap")
    if overlap is not None and overlap not in _USAGE_OVERLAPS:
        return f"overlap must be one of {list(_USAGE_OVERLAPS)}"
    return None


def evaluate_dataset_taxonomy(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Pure core: `datasets` are raw frontmatter dicts (each with `_path`)."""
    for fm in datasets:
        # `kind` is canonical; `type` is the authored alias — accept either.
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        source_class = fm.get("source_class")
        derived_kind = fm.get("derived_kind")

        # --- source_class ---
        if source_class is None:
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: dataset declares no source_class "
                f"(observational|derived|reference); epistemic weighting cannot apply",
                "taxonomy.source-class-undeclared",
            )
        elif source_class not in _SOURCE_CLASSES:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: source_class {source_class!r} invalid "
                f"(expected one of {list(_SOURCE_CLASSES)})",
                "taxonomy.source-class-invalid",
            )

        # --- derived_kind consistency ---
        if source_class == "derived":
            if not derived_kind:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: source_class=derived requires derived_kind "
                    f"({list(_DERIVED_KINDS)})",
                    "taxonomy.derived-kind-missing",
                )
            elif derived_kind not in _DERIVED_KINDS:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: derived_kind {derived_kind!r} invalid "
                    f"(expected one of {list(_DERIVED_KINDS)})",
                    "taxonomy.derived-kind-invalid",
                )
        elif derived_kind is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: derived_kind is only allowed when source_class=derived "
                f"(source_class={source_class!r})",
                "taxonomy.derived-kind-misplaced",
            )

        # --- dataset_usage well-formedness ---
        # A present-but-non-list dataset_usage (e.g. a single mapping authored
        # without the leading `-`) is a real defect, not "no usage": ERROR rather
        # than silently treating it as empty.
        usage = fm.get("dataset_usage")
        entries: list[Any] = []
        if isinstance(usage, list):
            entries = usage
        elif usage is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: dataset_usage must be a list of usage entries, "
                f"got {type(usage).__name__}",
                "taxonomy.dataset-usage-malformed",
            )
        for entry in entries:
            defect = _usage_defect(entry)
            if defect is not None:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: malformed dataset_usage entry — {defect}",
                    "taxonomy.dataset-usage-malformed",
                )

        # --- A-D3: external-produced derived artifact must record its inputs ---
        # derivation.inputs is gated to origin=derived, so an origin=external model
        # output / meta-analysis can only record inputs via dataset_usage
        # (role upstream|training). Without it, independence is not derivable.
        if fm.get("origin") == "external" and source_class == "derived":
            has_provenance = any(
                isinstance(e, dict) and e.get("role") in _DEPENDENCE_PROVENANCE_ROLES
                for e in entries
            )
            if not has_provenance:
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: external derived artifact has no dataset_usage with "
                    f"role upstream|training; independence cannot be derived (A-D3)",
                    "taxonomy.external-derived-no-provenance",
                )


@Check(section="dataset taxonomy", order=29)
def check_dataset_taxonomy(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_taxonomy(dataset_frontmatters(ctx))
```

- [ ] **Step 4: Register the check**

In `science/src/science_tool/validate/checks/__init__.py`, add `"dataset_taxonomy"` to the `_load_canonical_checks` module tuple, after `"identity_context"`:

```python
        "reference_collections",
        "identity_context",
        "dataset_taxonomy",
        "prose_lints",
```

- [ ] **Step 5: Run to verify PASS**

Run:
```bash
cd ~/d/science/science && uv run pytest tests/validate/test_checks_dataset_taxonomy.py -q
```
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/dataset_taxonomy.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_dataset_taxonomy.py
git commit -m "feat(validate): dataset taxonomy check — source_class/derived_kind/dataset_usage (order 29, A1)"
```

---

## Task 8: Full regression + docs

Run the whole affected test surface, then record A1 as merged in the design + umbrella docs (mirroring the C2/C3 "identity migration note" commits).

**Files:**
- Modify: `docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` (§9 status)
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` (§6 table A row + §8)

- [ ] **Step 1: Full regression**

Run:
```bash
cd ~/d/science/science && uv run pytest model/tests/ tests/validate/ tests/test_storage_adapters/test_datapackage.py -q
```
Expected: PASS. Investigate any failure before proceeding (do not edit tests to pass).

- [ ] **Step 2: Update the Pillar A design status (§9)**

In `docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` change the §8 A1 row status and §9 to note A1 is implemented: the `source_class`/`derived_kind`/`dataset_usage` recording layer + validate check (order 29) merged; the `dataset_usage` full schema shipped in A1 per the co-ownership decision; A2 (belief-math composition) pending. Update the top-of-file `Status:` line accordingly.

- [ ] **Step 3: Update the umbrella (§6 table + §8)**

In `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`, update the §6 phasing table Phase-2 (A) row to "impl: A1 merged (recording layer); A2 (belief-math) pending", and add an A1 line to §8 "Remaining — other pillars" / status.

- [ ] **Step 4: Commit**

```bash
git add docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
git commit -m "docs(bio): mark A1 (dataset taxonomy recording layer) merged"
```

---

## Self-review checklist (run before handing to executor)

- **Spec coverage:** A-D1 `source_class` enum → Tasks 2/4/7. A-D3 external-derived `dataset_usage` `{upstream,training}` contract → schema (Task 2), model (Task 3), check WARN (Task 7). `derived_kind` required-when-derived → Tasks 2/4/7. `dataset_usage` full schema (co-ownership decision) → Tasks 2/3. **Both load paths carry the fields** → `parse_entity_file` (Task 5) + graph loader: `MarkdownAdapter` already passes full frontmatter (Task 4 `Entity` fields suffice), `DatapackageAdapter` whitelist extended (Task 6). A-D2 (causal axis stays on `identification_strength`) and A-D4/A-D5 (curation modifier, reference-as-evidence) → **A2, out of scope here** (documented in Scope & deviations).
- **Type consistency:** `DatasetUsage(ref, role, overlap)` identical across schema `$defs`, Pydantic model (Task 3), coercion (Task 5), and check (Task 7). Roles list identical in all four. `source_class`/`derived_kind` enums identical in schema, `DatasetEntity` invariant, and check.
- **Invariant home:** the `source_class`/`derived_kind` rule is a kind-gated `Entity` validator (Task 4), so it fires on **both** the `parse_entity_file` plain-`Entity` path (`plan_gate`) and the graph `DatasetEntity` path (inheritance) — and is independent of `origin`. `DatasetEntity`'s #7/#8 origin invariants are untouched.
- **dataset_usage validation, both paths:** Pydantic's `list[DatasetUsage]` validates entries on parse (raw passthrough, `None`→`[]` only — Task 5) and on graph load (Task 4 field); the `science validate` check additionally reports a present-but-non-list `dataset_usage` tolerantly (Task 7). Parse and check agree: `None`/absent is empty, any present non-list (incl. `{}`/`""`) fails.
- **Validate-check coverage spans both backends:** the broadened `dataset_frontmatters` (Task 1) discovers markdown (`doc/datasets/`) **and** datapackage datasets with a `kind`-or-`type` filter, so `taxonomy.source-class-undeclared` and the malformed diagnostics reach hand-authored markdown datasets, not just promoted ones. The evaluator filter matches (`kind`-or-`type`, Task 7).
- **No placeholders:** every step carries real code/commands and expected output.
- **Down-weight / belief config:** untouched by A1 (correct — that is A2).
```