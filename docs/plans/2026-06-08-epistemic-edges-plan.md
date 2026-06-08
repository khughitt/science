# Epistemic Edges (Framework) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended)
> or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`)
> syntax for tracking.

> **⛔ HELD until `layout_version: 3` is confirmed in place.** Per the umbrella
> ([`2026-06-08-epistemic-data-model-design.md`](./2026-06-08-epistemic-data-model-design.md) §7) and
> the design ([`2026-06-08-epistemic-edges-design.md`](./2026-06-08-epistemic-edges-design.md)),
> implementation does **not** start until the v2→v3 substrate migration has landed and been confirmed.
> Phase 0 is the gate. Tasks tagged **[v3-API]** have a contract that must be *finalized against the
> confirmed v3 substrate API* (entity layout, TriG compilation, edge-as-node identity) — do not pin
> their exact code before Phase 0 resolves the edge-as-node identity question (design risk 4).

**Goal:** Build the framework machinery that lets a truth-apt causal-DAG edge *be* a relational
`proposition` (one belief, derived `edge_status`), with a normalized-projection authoring workbench —
**without** the MM30 corpus migration (deferred to a separate `~/d/r/mm30` plan).

**Architecture:** Three layers. (1) **Schema** — new reference-class node kinds `construct`/`outcome`,
relational-proposition fields (`predicate`/`polarity`/`legacy_relation_label`) bound to canonical
`claim_layer`/`identification_strength`/t034 axes, evidence-line quantitative-result + staging marker.
(2) **Derivation** — `derived_edge_status` as a pure ordered projection over derived belief; posterior
payload → scalar-belief input; staged ungrounded empirical evidence excluded from the compiled graph.
(3) **Authoring** — `<patch>.workbench.yaml` as an editable normalized projection kept honest by an
idempotent `compile`→regenerate cycle and a fixpoint CI gate.

**Tech Stack:** Python; `science_model` (pydantic schemas + StrEnums) and `science_tool` (Click CLI,
`@Check` validators, RDF/TriG materialization via `rdflib`); `uv run pytest`; `ruff`.

**Repos:** All tasks here are in **`~/d/science`** (the `science/` package). The MM30 data migration is
out of scope (separate plan, gated on this + the `dataset-evidence-flow` facet).

---

## File structure

| File | Responsibility | Phase |
|---|---|---|
| `science/model/src/science_model/entities.py` | `EntityClass` membership for new kinds; `EvidenceLineEntity` quantitative-result + staging fields | 1, 1c |
| `science/model/src/science_model/reasoning.py` | `Predicate`, `Polarity` enums; reuse `ClaimLayer`/`IdentificationStrength` | 1b |
| `science/model/src/science_model/propositions.py` *(new)* | `PropositionEntity` subclass with relational fields + cross-field validators | 1b |
| `science/src/science_tool/graph/entity_registry.py` | register `construct`/`outcome` (reference class) | 1a |
| `science/src/science_tool/entities.py` | path policies + status sets for new kinds | 1a |
| `science/src/science_tool/validate/checks/propositions.py` *(new)* | polarity↔predicate, canonical-enum binding checks | 2 |
| `science/src/science_tool/validate/checks/evidence_lines.py` | staging-exclusion check (extend) | 2c |
| `science/src/science_tool/graph/derived_status.py` *(new)* | `derived_edge_status` ordered projection + reason | 4a |
| `science/src/science_tool/graph/materialize.py` | posterior→scalar input; staged-evidence exclusion | 3 |
| `science/src/science_tool/graph/belief_scalar.py` | accept quantitative result as scalar input | 3a |
| `science/src/science_tool/dag/workbench.py` *(new)* | `<patch>.workbench.yaml` schema + compile/normalize | 5 |
| `science/src/science_tool/dag/cli.py` | `dag workbench` / `dag compile` commands; legacy `edge_status` render adapter | 4b, 5 |
| `science/tests/...` | per-task tests | all |

---

## Phase 0 — v3 gate (no code; blocks everything below)

### Task 0: Confirm v3 + resolve edge-as-node identity

**Files:** none (investigation; record findings in this plan's Task 0 checklist + a note in the design's §11 risk 4).

- [ ] **Step 1: Confirm `layout_version: 3`.** Verify `science.yaml` reports `layout_version >= 3`
  and `science validate` passes the manifest + directory-structure checks
  (`validate/checks/manifest.py:30`, `validate/checks/directory_structure.py`).
  Expected: no `layout_version must be >= 3` error.
- [ ] **Step 2: Resolve edge-as-node identity (design risk 4).** Inspect the confirmed v3 compilation
  path (`graph/materialize.py`, the store/compilation modules) and determine whether a relational
  proposition's **own IRI** can serve as its reified edge-node IRI, or whether the substrate forces a
  content-addressed edge-node (like `freshness.py`'s `bears-on-edge/<sha256>`).
  - If proposition-IRI works directly → record "no shim"; Tasks 9/12 use the proposition IRI as the
    edge-node IRI.
  - If the substrate forces a content-addressed edge-node → record the **`realized_as` shim** contract
    (proposition IRI `sci:realizedAsEdge` content-addressed-edge-IRI; belief still keys on the
    proposition IRI) and thread it through Tasks 9/12.
- [ ] **Step 3: Record the resolution** as a short note appended to the design §11 risk 4, and unblock
  the [v3-API] tasks.

**Acceptance:** layout_version 3 confirmed; the edge-as-node identity decision is written down; every
[v3-API] task below has a concrete identity contract to build against.

---

## Phase 1 — Schema

### Task 1a: Register `construct` and `outcome` (reference-class node kinds)

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py` (`_CORE_KIND_CLASSES` ~48–92; `with_core_types()` ~137–168)
- Modify: `science/src/science_tool/entities.py` (`_BUILTIN_MARKDOWN_POLICIES` ~25–65; `_DEFAULT_STATUS`/`_STATUS_VALUES` ~200–262)
- Test: `science/tests/test_entity_registry_construct_outcome.py` *(new)*

- [ ] **Step 1: Write the failing test.**
```python
# tests/test_entity_registry_construct_outcome.py
from science_model.entities import EntityClass
from science_tool.graph.entity_registry import EntityRegistry

def test_construct_and_outcome_are_reference_kinds():
    r = EntityRegistry.with_core_types()
    for kind in ("construct", "outcome"):
        spec = r.spec_for(kind)            # use the registry's existing lookup accessor
        assert spec is not None, f"{kind} not registered"
        assert spec.entity_class == EntityClass.REFERENCE
```
(If the accessor is not named `spec_for`, match the registry's actual lookup method found in
`entity_registry.py`.)
- [ ] **Step 2: Run it; expect FAIL** (`construct not registered`). `cd ~/d/science/science && uv run pytest tests/test_entity_registry_construct_outcome.py -q`
- [ ] **Step 3: Register the kinds.** Add `"construct": EntityClass.REFERENCE` and
  `"outcome": EntityClass.REFERENCE` to `_CORE_KIND_CLASSES`; add `"construct"`, `"outcome"` to the
  `with_core_types()` ProjectEntity registration loop; add path policies
  `"construct": EntityPathPolicy(Path("entities/constructs"), "slug")` and
  `"outcome": EntityPathPolicy(Path("entities/outcomes"), "slug")` to `_BUILTIN_MARKDOWN_POLICIES`; add
  `_DEFAULT_STATUS`/`_STATUS_VALUES` entries (`{"active", "retired"}` — reference kinds carry no belief
  status).
- [ ] **Step 4: Run it; expect PASS.**
- [ ] **Step 5: Commit.** `git commit -m "feat(entities): register construct/outcome reference kinds (epistemic-edges)"`

**Acceptance:** `construct`/`outcome` resolve as REFERENCE-class kinds with `slug` storage under
`entities/constructs|outcomes/`; they carry no belief/freshness (design §3).

### Task 1b: Relational-proposition fields + `Predicate`/`Polarity` enums

**Files:**
- Modify: `science/model/src/science_model/reasoning.py` (add `Predicate`, `Polarity`; `ClaimLayer`/`IdentificationStrength` already here)
- Create: `science/model/src/science_model/propositions.py` (`PropositionEntity(ProjectEntity)`)
- Modify: `science/src/science_tool/graph/entity_registry.py` (register `proposition` → `PropositionEntity` instead of generic `ProjectEntity`)
- Test: `science/tests/test_proposition_relational_fields.py` *(new)*

- [ ] **Step 1: Define the enums** in `reasoning.py`:
```python
class Predicate(StrEnum):                       # v1 seed set — strictly binary; sign-free
    affects = "affects"
    regulates = "regulates"
    associates_with = "associates_with"
    binds = "binds"
    is_proxy_for = "is_proxy_for"
    induces_state = "induces_state"
    transitions_to = "transitions_to"
    subtype_of = "subtype_of"
    part_of = "part_of"

class Polarity(StrEnum):
    positive = "positive"
    negative = "negative"
    unsigned = "unsigned"
    not_applicable = "not_applicable"

SIGN_MEANINGFUL_PREDICATES = frozenset({Predicate.affects, Predicate.regulates, Predicate.associates_with})
```
(Do **not** add `mediates_effect_of` — deferred, design §2.1.)
- [ ] **Step 2: Write the failing test** for the proposition schema + the sign-aptitude model invariant:
```python
# tests/test_proposition_relational_fields.py
import pytest
from pydantic import ValidationError
from science_model.propositions import PropositionEntity

def test_relational_proposition_accepts_factored_axes():
    p = PropositionEntity(id="proposition:p1", subject="gene:PHF19", predicate="affects",
                          object="construct:proliferation", polarity="positive",
                          claim_layer="causal_effect", identification_strength="observational",
                          legacy_relation_label="dosage → transcription")
    assert p.predicate == "affects" and p.polarity == "positive"

def test_signless_predicate_requires_not_applicable_polarity():
    with pytest.raises(ValidationError):
        PropositionEntity(id="proposition:p2", subject="gene:A", predicate="binds",
                          object="gene:B", polarity="positive", claim_layer="empirical_regularity")
```
- [ ] **Step 3: Run it; expect FAIL** (no `science_model.propositions`).
- [ ] **Step 4: Implement `PropositionEntity`** with fields `subject: str | None`, `object: str | None`,
  `predicate: Predicate | None`, `polarity: Polarity | None`, `legacy_relation_label: str | None`,
  reusing existing `claim_layer: ClaimLayer | None` / `identification_strength: IdentificationStrength | None`,
  and a `model_validator` enforcing: a `predicate` requires `subject`+`object`; sign-meaningful
  predicate → polarity ∈ {positive, negative, unsigned}; sign-less predicate → polarity =
  `not_applicable`. Register `proposition → PropositionEntity` in `entity_registry.py`.
- [ ] **Step 5: Run it; expect PASS.**
- [ ] **Step 6: Commit.** `git commit -m "feat(model): relational PropositionEntity (predicate/polarity factored axes)"`

**Acceptance:** propositions carry the factored, sign-free relation model (design §2); `predicate` and
`polarity` cannot disagree; `mediates_effect_of` is absent (v1 binary-only).

### Task 1c: Evidence-line quantitative-result + staging marker

**Files:**
- Modify: `science/model/src/science_model/entities.py` (`EvidenceLineEntity` ~725–750)
- Test: `science/tests/test_evidence_line_quant_result.py` *(new)*

- [ ] **Step 1: Write the failing test:**
```python
# tests/test_evidence_line_quant_result.py
from science_model.entities import EvidenceLineEntity

def test_quantitative_result_and_staging_fields():
    e = EvidenceLineEntity(stance="supports", target="proposition:p1", evidence_type="empirical_data_evidence",
                           quantitative_result={"beta": 0.41, "hdi": [0.2, 0.6], "prob_sign": 0.98},
                           compiled=False)            # staged: excluded from compiled graph
    assert e.quantitative_result["prob_sign"] == 0.98
    assert e.compiled is False
```
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Add fields** to `EvidenceLineEntity`: `quantitative_result: dict | None = None` (a
  small typed sub-model `QuantitativeResult(beta, hdi, prob_sign, fit_task, model)` is preferred over a
  bare dict — define it alongside), and `compiled: bool = True` (default compiled; staged
  empirical-without-`dataset_usage` lines set `compiled=False`).
- [ ] **Step 4: Run it; expect PASS.**
- [ ] **Step 5: Commit.** `git commit -m "feat(model): evidence-line quantitative_result + compiled/staging marker"`

**Acceptance:** evidence-lines can carry a fitted posterior result (design §8 step 5) and a staging
marker (design §8 step 4) without affecting their stance/target contract.

---

## Phase 2 — Validation

### Task 2a: polarity↔predicate sign-aptitude check

**Files:**
- Create: `science/src/science_tool/validate/checks/propositions.py`
- Test: `science/tests/validate/test_check_propositions.py` *(new)*

- [ ] **Step 1: Write the failing test** asserting a `Result(severity=ERROR, rule="proposition.polarity.aptitude")`
  is yielded for a `binds` proposition with `polarity: positive`, and none for a valid `affects`+`positive`.
  Follow the fixture style in `tests/validate/conftest.py` + `validate/checks/evidence_lines.py`.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** `@Check(section="propositions", order=10) def check_polarity_predicate_aptitude(ctx)`
  iterating proposition frontmatter (mirror `_ev_lines(ctx)` → a `_propositions(ctx)` helper), yielding
  the ERROR when polarity violates `SIGN_MEANINGFUL_PREDICATES` membership (model invariant restated as
  a corpus-level check so authored entity files are caught even if constructed outside the model).
- [ ] **Step 4: Run it; expect PASS.**
- [ ] **Step 5: Commit.**

**Acceptance:** corpus-level enforcement of the design §2.2 sign rule.

### Task 2b: canonical enum binding (anti-drift)

**Files:** `validate/checks/propositions.py` (extend); test in same test module.

- [ ] **Step 1: Write the failing test** asserting ERROR `proposition.claim_layer.canonical` for a
  proposition with `claim_layer: mechanistic_claim` (a non-canonical name) and `proposition.identification.canonical`
  for `identification_strength: none`; and that the legacy DAG `none` is *mapped to unspecified*, not
  accepted as a value.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** a check that `claim_layer` ∈ canonical `ClaimLayer` and
  `identification_strength` ∈ canonical `IdentificationStrength` (design §2.3); treat absent/`none` as
  unspecified (not an error, but not a new enum value).
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** no parallel `claim_layer`/`identification_strength` vocabulary can enter the corpus.

### Task 2c: staging-exclusion check for empirical evidence-lines

**Files:** `science/src/science_tool/validate/checks/evidence_lines.py` (extend); `science/tests/validate/test_check_evidence_staging.py` *(new)*

- [ ] **Step 1: Write the failing test:** an empirical evidence-line with `compiled: true` and no
  `dataset_usage` yields ERROR `evidence.empirical.requires_dataset_usage`; the same line with
  `compiled: false` (staged) yields **no** error.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** `@Check(section="evidence lines", order=30) def check_compiled_empirical_has_dataset_usage(ctx)`:
  for `evidence_type == "empirical_data_evidence"` and `compiled is True`, require non-empty
  `dataset_usage`; staged (`compiled=False`) lines are exempt (design §8 step 4, §11 risk 6).
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** the mandatory-`dataset_usage` invariant holds for any **compiled** empirical
evidence-line; staged ones are legal but excluded.

---

## Phase 3 — Belief & materialization wiring

### Task 3a: posterior quantitative result → scalar-belief input

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_evidence_line_metadata` ~570 `scalar_predicates`)
- Modify: `science/src/science_tool/graph/belief_scalar.py` (accept the result as a scalar input)
- Test: `science/tests/test_belief_scalar_quant_result.py` *(new)*

- [ ] **Step 1: Write the failing test** that an evidence-line carrying `quantitative_result`
  contributes its `beta`/`prob_sign` to the scalar `(massed_support, massed_dispute)` pair for the
  target proposition (assert the scalar shifts vs. the same line without a result).
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement.** Emit the quantitative result onto the evidence-line in `materialize.py`
  (extend `scalar_predicates` with `SCI_NS.quantBeta`/`quantProbSign`/`quantHdiLow`/`quantHdiHigh`),
  and read them in `belief_scalar.py` as a scalar input (a fitted effect with a sign probability maps
  to a log-odds contribution). Keep the ordinal magnitude path unchanged.
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** fitted posteriors feed continuous scalar belief (design §8 step 5); no posterior
payload is dropped.

### Task 3b: exclude staged evidence-lines from the compiled graph **[v3-API]**

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_evidence_line_relations` ~536; the evidence-line iteration in `materialize_graph`)
- Test: `science/tests/test_materialize_staging_exclusion.py` *(new)*

- [ ] **Step 1: Write the failing test:** a staged evidence-line (`compiled=False`) emits **no**
  `cito:supports`/`disputes` triple and is **invisible** to `belief.collect_evidence_units` for its
  target; a `compiled=True` line emits normally.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** the exclusion: skip `compiled=False` evidence-lines when emitting cito
  relations / building the dataset for belief. *(v3-API: confirm the exact materialization entry that
  iterates evidence-lines under the confirmed v3 compilation contract.)*
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** belief never aggregates ungrounded empirical evidence (design §8 step 4, §9).

---

## Phase 4 — Projection & rendering

### Task 4a: `derived_edge_status` ordered projection

**Files:**
- Create: `science/src/science_tool/graph/derived_status.py`
- Test: `science/tests/test_derived_edge_status.py` *(new)*

- [ ] **Step 1: Write the failing tests** covering the ordered projection (design §6):
```python
# eliminated > unknown > structural > supported > tentative ; contested is a SEPARATE flag
from science_tool.graph.derived_status import derived_edge_status

def test_eliminated_wins():
    s = derived_edge_status(belief_magnitude="well_supported", refuted=True, claim_layer="causal_effect",
                            has_grounding_evidence=True)
    assert s.status == "eliminated"

def test_ungrounded_structural_is_unknown_not_structural():
    s = derived_edge_status(belief_magnitude="speculative", refuted=False, claim_layer="structural_claim",
                            has_grounding_evidence=False)
    assert s.status == "unknown"            # design L2 fix: unknown ordered before structural

def test_grounded_structural_is_structural():
    s = derived_edge_status(belief_magnitude="supported", refuted=False, claim_layer="structural_claim",
                            has_grounding_evidence=True)
    assert s.status == "structural"

def test_supported_and_tentative_bands():
    assert derived_edge_status(belief_magnitude="supported", refuted=False, claim_layer="causal_effect",
                               has_grounding_evidence=True).status == "supported"
    assert derived_edge_status(belief_magnitude="fragile", refuted=False, claim_layer="causal_effect",
                               has_grounding_evidence=True).status == "tentative"
```
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** a pure function returning a small dataclass
  `DerivedEdgeStatus(status: str, reason: str)` with the ordered logic (first match wins):
  `eliminated` (refuted) → `unknown` (not has_grounding_evidence) → `structural`
  (`claim_layer == structural_claim`) → `supported` (magnitude ∈ {supported, well_supported}) →
  `tentative`. `reason` records which rule fired. `contested` is **not** an input to the ordinal — it
  stays a separate overlay (computed by the belief engine).
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** the lossy summary is a pure, documented, ordered projection over canonical derived
fields; ungrounded structural claims surface as `unknown` (design §6 + review fix L2).

### Task 4b: legacy `edge_status` render adapter

**Files:**
- Modify: `science/src/science_tool/dag/render.py` and/or `science/src/science_tool/dag/cli.py` (the render path)
- Test: `science/tests/test_dag_render_status_adapter.py` *(new)*

- [ ] **Step 1: Write the failing test:** the renderer, given a proposition with derived belief,
  styles the edge from the **orthogonal channels** (polarity→hue, identification→line-style,
  belief→intensity, contested→overlay) and exposes a bare `edge_status` string **only** through the
  legacy adapter boundary (assert the adapter maps `derived_edge_status` → the 5-value enum, and that
  axis-specific styling is applied independent of that enum).
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** the adapter: at the render boundary call `derived_edge_status(...)` and
  expose `.status` as `edge_status` for legacy `science dag` consumers; drive styling from the
  channels, not the enum. No authored `edge_status` is read.
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** new rendering reads orthogonal channels; legacy `edge_status` exists only at the
boundary (design §6 normative rules).

---

## Phase 5 — Workbench authoring layer

### Task 5a: `<patch>.workbench.yaml` schema (allowed/forbidden fields)

**Files:**
- Create: `science/src/science_tool/dag/workbench.py` (pydantic `WorkbenchFile`, `WorkbenchRow`)
- Test: `science/tests/test_workbench_schema.py` *(new)*

- [ ] **Step 1: Write the failing test:** a row with allowed fields (id?, subject, predicate, object,
  patch, claim_layer, identification_strength, epistemic_role, evidence stubs) validates; a row with a
  **forbidden** field (`edge_status`, `belief`, `posterior` *as status*, embedded post-compile support
  arrays) raises `ValidationError`.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** `WorkbenchRow`/`WorkbenchFile` with the allowed set and an explicit reject
  of forbidden keys (design §5 allowed/forbidden). Evidence stubs are an *input-only* nested shape; a
  quantitative result is permitted **inside an evidence stub** (it lifts to the evidence-line), not as
  a row-level status field.
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** the workbench schema structurally forbids belief/status fields (design §5).

### Task 5b: `compile` — upsert entities, mint IDs, lift stubs **[v3-API]**

**Files:**
- Modify: `science/src/science_tool/dag/workbench.py` (`compile_workbench(path) -> CompileResult`)
- Test: `science/tests/test_workbench_compile.py` *(new)*

- [ ] **Step 1: Write the failing tests:** (i) an id-less row gets a **minted** proposition ID written
  back and a `PropositionEntity` created in `entities/propositions/`; (ii) an inline evidence stub
  becomes an `EvidenceLineEntity` and the row at rest holds an evidence-line **reference**, not
  substance; (iii) empirical evidence stub without `dataset_usage` produces a **staged**
  (`compiled=False`) evidence-line.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** `compile_workbench`: parse → for each row upsert a `PropositionEntity`
  (mint ID for id-less rows — entity layer owns identity, design §5 step 2; the proposition IRI is the
  edge-node IRI per Task 0) → lift evidence stubs to `EvidenceLineEntity` (staging empirical-without-
  dataset_usage) → return the canonical model. *(v3-API: writing entities + edge-as-node uses the v3
  layout/identity contract from Task 0.)*
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** compile is the only writer of proposition/evidence-line entities from the workbench;
identity is entity-layer-owned; stubs normalize to references (design §5).

### Task 5c: regenerate canonical workbench + idempotence

**Files:** `science/src/science_tool/dag/workbench.py` (`serialize_canonical(patch) -> str`); test `science/tests/test_workbench_idempotent.py` *(new)*

- [ ] **Step 1: Write the failing test:** `compile` then `serialize_canonical` produces a file equal to
  re-running the same cycle (idempotent fixed point); id-less rows now carry IDs; stubs now appear as
  refs.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** canonical serialization from the patch's entities (deterministic ordering;
  references not substance; no layout/cosmetic fields — those live in the sibling file, Task 5e).
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** `serialize_canonical(apply(workbench, entities))` is a fixed point (design §5).

### Task 5d: CI fixpoint gate on a non-mutating scratch graph

**Files:**
- Modify: `science/src/science_tool/dag/cli.py` (`dag workbench --check`) and/or a `validate/checks/` hook
- Test: `science/tests/test_workbench_ci_gate.py` *(new)*

- [ ] **Step 1: Write the failing test:** a committed workbench that equals its canonical form passes;
  one with an **uncompiled** id-less row (no minted ID written back) **fails** with a diff; the check
  performs **no writes** to real entity files (assert the entities dir is unchanged after the check).
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** `dag workbench --check`: parse committed workbench → apply valid edits to an
  **in-memory scratch copy** of the patch entities → `serialize_canonical` → diff against committed →
  nonzero exit on diff. Never writes real entities (design §5 step 4 + review: model the real compile
  on a scratch graph).
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** committed drift fails CI; the check is side-effect-free; the equality is "committed ==
fixed point of normalize" (design §5).

### Task 5e: sibling layout/view file separation

**Files:** `science/src/science_tool/dag/workbench.py` + a `<patch>.layout.yaml` reader; test `science/tests/test_workbench_layout_sibling.py` *(new)*

- [ ] **Step 1: Write the failing test:** layout/cosmetic data (node positions) round-trips via
  `<patch>.layout.yaml` and is **rejected** if placed in the workbench; the workbench↔entity equality
  (Task 5c) is unaffected by layout edits.
- [ ] **Step 2: Run it; expect FAIL. Step 3: Implement** the sibling file + the workbench rejection of
  layout keys. **Step 4: PASS. Step 5: Commit.**

**Acceptance:** cosmetic state is non-epistemic, lives in a sibling file, and does not perturb the
round-trip (design §5).

### Task 5f: retire `edges.yaml` as epistemic source-of-truth **[v3-API]**

**Files:**
- Modify: `science/src/science_tool/dag/cli.py` (`render`/`number` ingestion ~93), `science/src/science_tool/dag/schema.py` (`EdgesYamlFile`)
- Test: `science/tests/test_edges_yaml_retired.py` *(new)*

- [ ] **Step 1: Write the failing test:** the DAG renderer sources edges from compiled relational
  propositions (via Task 4b), not from authored `edge_status` in `edges.yaml`; an `edges.yaml` is
  accepted only through the documented **legacy read adapter** (and emits a deprecation result),
  never as a status source-of-truth.
- [ ] **Step 2: Run it; expect FAIL.**
- [ ] **Step 3: Implement** the cutover: render/number read compiled propositions + `derived_edge_status`;
  `EdgesYamlFile` becomes a legacy-import adapter only. *(v3-API: reads the compiled graph under the v3
  contract.)*
- [ ] **Step 4: Run it; expect PASS. Step 5: Commit.**

**Acceptance:** `edges.yaml` is retired as an epistemic store; the DAG is a view over propositions
(design §1.1 invariant 9, §6).

---

## Phase 6 — Integration

### Task 6: end-to-end workbench round-trip on a fixture patch **[v3-API]**

**Files:** `science/tests/test_epistemic_edges_e2e.py` *(new)*; a small fixture patch under `tests/fixtures/`.

- [ ] **Step 1: Write the failing test:** author a tiny `<patch>.workbench.yaml` (2 relational
  propositions — one `affects/positive` with a literature evidence stub, one `is_proxy_for`
  structural_claim with a staged empirical stub) → `compile` → materialize → assert: belief derives on
  the proposition IRIs; the literature line is compiled and the staged empirical line is excluded;
  `derived_edge_status` projects as expected; `dag workbench --check` passes; renderer styles from
  channels.
- [ ] **Step 2: Run it; expect FAIL → implement any glue → PASS.**
- [ ] **Step 3: Run the full suite** `cd ~/d/science/science && uv run pytest tests/ -m "not snapshot and not real_projects" -q` and `uv run ruff check .`; expect green.
- [ ] **Step 4: Commit.**

**Acceptance:** the whole framework loop works on a fixture without any MM30 data; this is the seam the
deferred MM30 migration plan plugs into.

---

## Out of scope (separate plan)

- **MM30 corpus migration** (`~/d/r/mm30`): mapping the 356 edges / 214 nodes into propositions +
  evidence-lines, the 260-string `relation` decomposition, node resolution, `eliminated_by`, loud-fail
  gates. Gated on this plan **and** the `dataset-evidence-flow` facet (for `dataset_usage`).
- **`dataset-evidence-flow` facet** (`dataset_usage` authoring, `task→dataset` resolution, independence
  surfacing): its own design+plan; it populates the dataset bindings this plan leaves staged.

---

## Self-review notes (coverage vs design)

- §1 invariants → Tasks 1b (proposition IS the unit, factored axes), 0+5b (IRI=edge-node), 3a/3b/4
  (belief derived, edge_status derived), 5f (edges.yaml retired). ✓
- §2 relation model → 1b (enums + sign rule), 2a/2b (validation). ✓
- §3 node identity → 1a (construct/outcome reference kinds). *(Node-resolution gates are migration-side
  → deferred MM30 plan; flagged here.)* ✓ (framework portion)
- §5 workbench → 5a–5e. ✓
- §6 projection/rendering → 4a/4b. ✓
- §7 lifecycle / §8 elimination → freshness reused (no new field); `eliminated`→disputing handled at
  derivation (4a `refuted`) + migration (deferred). ✓
- §8 migration gates → deferred MM30 plan (explicitly out of scope). ✓
- [v3-API] tasks: 0 (gate), 3b, 5b, 5f, 6 — all carry the "finalize against confirmed v3 API" note.
