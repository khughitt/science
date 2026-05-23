# Evidence-Line Entity Kind (Phase 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable, first-class `evidence-line` entity kind that is the **subject** of `cito:supports` / `cito:disputes` toward a proposition (or hypothesis), carrying per-line evidence metadata (`stance`, `strength`, `independence` + `independence_group`, `evidence_role`, `dispute_scope`, observability fields, optional `measurement_model`, source ref). This is the *only* canonical shape for counted evidence and the hard prerequisite for all aggregation work. **Phase 0 ships representation + structural QA only — no aggregation, no `belief_state`/`belief_weight` changes, no edge-status/posteriors.**

**Architecture:** An `evidence-line` is an epistemic `ProjectEntity` subclass. Its `stance` + `target` materialize into a `cito:supports`/`cito:disputes` edge (`evidence-line → proposition`) via the existing authored-relation path; its `source` materializes as `prov:wasDerivedFrom`; its metadata materializes onto the line node. Background material that is not ready to count stays as `source_refs`/`related`/`bears_on`/`unassessed` — there is no second evidence path. Counting (Phase 1) will read these line entities; Phase 0 only makes them exist, validate, and round-trip.

**Tech Stack:** Python 3.12, pydantic v2, rdflib, jsonschema, pytest, `uv`. Two packages: `science-model` (`science/model/`, tests `science/model/tests/`, run `cd science/model && uv run pytest …`) and `science_tool` (`science/`, tests `science/tests/`, run `cd science && uv run pytest …`).

**Spec:** `docs/plans/2026-05-22-evidence-aggregation-and-belief-design.md` (rev 2026-05-22c) — see §Prerequisite and §QA checks #1/#2/#2b/#9.

**Branch:** Continue on `evidence-line-belief-design` (already carries the committed design doc). All commits local; do **not** push.

**Scope guard (do NOT do in Phase 0):** independence-aware aggregation, the belief ladder, `belief_weight`/`influence_weight`, `sci:edgeStatus`/`sci:Posterior`, leave-one-out sensitivity, calibration backtest. Those are Phase 1+. Leave the existing count-based `_belief_state` (store.py:3613) untouched — note that authored evidence-line cito edges will begin to count there as ordinary support/dispute subjects, which is acceptable and an improvement; do not "fix" it this phase.

---

### Task 1: Resolve the `EvidenceLineMetadata` name collision

The class `reasoning.EvidenceLineMetadata` (reasoning.py:90-101) is misnamed — it is the shared proposition reasoning-metadata model (claim_layer/identification_strength/…); there is no `PropositionMetadata`. Free the name before adding a real evidence-line.

**Files:**
- Modify: `science/model/src/science_model/reasoning.py:90`
- Modify: any importers (grep first)
- Test: `science/model/tests/test_reasoning.py`

- [ ] **Step 1: Measure blast radius** — `rg -n "EvidenceLineMetadata" science/`. If usages are confined to model + a couple of call sites, proceed; if it is load-bearing across many modules, instead leave it and add a `PropositionMetadata = EvidenceLineMetadata` is **not** acceptable (dual name) — rename it.
- [ ] **Step 2: Failing test** — in `test_reasoning.py`, assert `from science_model.reasoning import PropositionMetadata` imports and that `EvidenceLineMetadata` no longer exists. Run → FAIL.
- [ ] **Step 3: Rename** `EvidenceLineMetadata` → `PropositionMetadata` (class + docstring "Authored reasoning metadata for a proposition.") and update all importers. Re-export both packages' `__init__` if it was exported.
- [ ] **Step 4:** `cd science/model && uv run pytest` and `cd science && uv run pytest` green.
- [ ] **Step 5:** Commit `refactor(model): rename EvidenceLineMetadata -> PropositionMetadata`.

---

### Task 2: New enums for evidence-line fields

**Files:**
- Modify: `science/model/src/science_model/reasoning.py` (add enums near the others, reasoning.py:10-63)
- Test: `science/model/tests/test_reasoning.py`

- [ ] **Step 1: Failing test** — assert the four enums and their members import and round-trip from their string values.
- [ ] **Step 2: Add enums** (mirror the existing `StrEnum` style; reuse vocabularies that already exist in the CLI evidence path, store.py:809/cli.py:1856):

```python
class EvidenceStance(StrEnum):
    SUPPORTS = "supports"
    DISPUTES = "disputes"

class EvidenceStrength(StrEnum):       # same vocab as `graph add evidence --strength`
    STRONG = "strong"
    MODERATE = "moderate"
    WEAK = "weak"

class IndependenceTag(StrEnum):        # same vocab as `--independence`
    INDEPENDENT = "independent"
    SHARED_SOURCE = "shared-source"
    CIRCULAR = "circular"

class DisputeScope(StrEnum):
    WHOLE_CLAIM = "whole_claim"
    GENERALIZATION = "generalization"
    MECHANISM = "mechanism"
    BOUNDARY = "boundary"
```

- [ ] **Step 3:** Tests green; commit `feat(model): add evidence-line stance/strength/independence/scope enums`.

---

### Task 3: `EvidenceLineEntity` model + `EntityType.EVIDENCE_LINE`

**Files:**
- Modify: `science/model/src/science_model/entities.py` (`EntityType` enum at 59-97; new subclass near `ProjectEntity` at 339)
- Test: `science/model/tests/test_reasoning.py` or new `science/model/tests/test_evidence_line_entity.py`

- [ ] **Step 1: Failing test** — construct an `EvidenceLineEntity(kind="evidence-line", type=EntityType.EVIDENCE_LINE, …, stance="disputes", target="proposition:p", source="paper:X", strength="strong", independence="independent", independence_group="g", evidence_role="model_criticism", dispute_scope="generalization")`; assert it validates and `core_entity_type_for_kind("evidence-line") == EntityType.EVIDENCE_LINE`.
- [ ] **Step 2: Add `EVIDENCE_LINE = "evidence-line"`** to `EntityType` (else `_validate_kind_type_consistency` at entities.py:291 rejects the kind).
- [ ] **Step 3: Add `EvidenceLineEntity(ProjectEntity)`** with typed fields. `evidence_role` is inherited from `ProjectEntity` (entities.py:362); add the line-specific fields:

```python
class EvidenceLineEntity(ProjectEntity):
    stance: EvidenceStance
    target: str                              # ref to proposition/hypothesis it bears on
    source: str | None = None                # paper:/dataset:/data-package: ref
    strength: EvidenceStrength | None = None
    independence: IndependenceTag | None = None
    dispute_scope: DisputeScope | None = None
    shared_dataset: str | None = None
    shared_lab: str | None = None
    shared_platform: str | None = None
    shared_cohort: str | None = None
    # inherited: evidence_role, independence_group, measurement_model
```

`stance` and `target` are required (an evidence line must declare what it bears on and which way). Keep `entity_class` epistemic.
- [ ] **Step 4:** Tests green; commit `feat(model): add EvidenceLineEntity + EntityType.EVIDENCE_LINE`.

---

### Task 4: Profile registration — kind, relation subjects, bears_on target, dir map

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py` (EntityKind ~43; `supports`/`disputes` RelationKinds 163-178; `bears_on` target_kinds 333-362)
- Modify: `science/model/src/science_model/frontmatter.py:191-214` (`_DIR_TO_KIND`)
- Test: `science/model/tests/test_profile_manifests.py`, `science/model/tests/test_relations.py`

- [ ] **Step 1: Failing tests** —
  - `test_profile_manifests.py`: `evidence-line` kind present with `canonical_prefix="evidence-line"`, `layer="layer/core"`, `entity_class="epistemic"`.
  - `test_relations.py`: `relation_allows_kinds(supports, "evidence-line", "proposition")` and `(disputes, "evidence-line", "hypothesis")` are True; and `relation_allows_kinds(bears_on, "<any>", "evidence-line")` is True.
- [ ] **Step 2: Add the EntityKind** in core.py:

```python
EntityKind(
    name="evidence-line",
    canonical_prefix="evidence-line",
    layer="layer/core",
    description="A single, independence-tagged line of evidence that supports or disputes a proposition.",
    entity_class="epistemic",
),
```

- [ ] **Step 3: Extend `supports`/`disputes` `source_kinds`** (core.py:163-178) to include `"evidence-line"`: `source_kinds=["observation", "proposition", "evidence-line"]`. Leave `target_kinds` as `["proposition", "hypothesis"]`.
- [ ] **Step 4: Add `"evidence-line"`** to the `bears_on` `target_kinds` list (core.py:336-353) so freshness/closure can reach a line.
- [ ] **Step 5: Add `"evidence-lines": "evidence-line"`** to `_DIR_TO_KIND` (frontmatter.py).
- [ ] **Step 6:** Tests green; commit `feat(model): register evidence-line kind + cito subject + bears_on target`.

---

### Task 5: Frontmatter parsing of evidence-line metadata

**Resolve the open question** the research flagged: `parse_entity_file` (frontmatter.py:286-360) may not currently parse reasoning metadata into the entity at all — propositions appear to round-trip `claim_layer` downstream, so confirm which path does it. The test will settle it; wire whatever is missing.

**Files:**
- Modify: `science/model/src/science_model/frontmatter.py` (`entity_kwargs` build 312-352; typed-subclass dispatch 353-360, mirror the `mechanism` branch)
- Test: `science/model/tests/test_frontmatter.py`

- [ ] **Step 1: Failing test** — write a temp `evidence-line` markdown with full frontmatter; `parse_entity_file` it; assert the result is an `EvidenceLineEntity` with `stance`, `target`, `source`, `strength`, `independence`, `independence_group`, `evidence_role`, `dispute_scope`, and one observability field all populated (not defaults).
- [ ] **Step 2: Parse + dispatch** — add the evidence-line keys to `entity_kwargs` and a typed-subclass branch (`if kind == EntityType.EVIDENCE_LINE.value: build EvidenceLineEntity(...)`) alongside the `mechanism` case at frontmatter.py:353. While here, if `claim_layer`/`evidence_role`/etc. are genuinely not parsed for any kind, add them (propositions need this too — but keep the change minimal and covered by the test).
- [ ] **Step 3:** Tests green; commit `feat(model): parse evidence-line frontmatter into EvidenceLineEntity`.

---

### Task 6: Template + MIGRATED_KINDS

**Files:**
- Create: `science/model/src/science_model/templates/evidence-line.md`
- Modify: `science/model/src/science_model/templates.py:14` (`MIGRATED_KINDS`)
- Test: `science/model/tests/` (mirror an existing template test)

- [ ] **Step 1: Failing test** — `science entity sections evidence-line` (or the underlying `_read_template`) returns the declared sections; `science entity create evidence-line "…"` renders without error.
- [ ] **Step 2: Add `"evidence-line"`** to `MIGRATED_KINDS`.
- [ ] **Step 3: Author `templates/evidence-line.md`** mirroring `proposition.md`: frontmatter with `stance`/`target`/`source`/`strength`/`independence`/`independence_group`/`evidence_role`/`dispute_scope` defaults, and sections `## What this line shows` (required), `## Why it is independent` (required), `## Caveats / scope` (required), `## Measurement Model` (optional). Every declared section must have a matching `## <name>` heading (templates.py:186).
- [ ] **Step 4:** Tests green; commit `feat(model): evidence-line template`.

---

### Task 7: Materializer — cito edge + source edge + line-specific metadata

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (`_add_relations` 247-391 for the stance→cito edge; a small `_add_evidence_line_metadata` for fields not covered by `_add_reasoning_metadata` at 771-803)
- Test: create `science/tests/test_evidence_line_materialize.py` (template: `test_chain_materialize.py`)

- [ ] **Step 1: Failing test** — using the `test_chain_materialize.py` idiom (write `science.yaml` + `doc/propositions/p.md` + `doc/evidence-lines/e.md`, call `materialize_graph(tmp_path)`, re-parse `.trig` with `rdflib.Dataset`), assert:
  - `(evidence-line:e, cito:disputes, proposition:p)` exists (driven by `stance: disputes` + `target: proposition:p`),
  - `(evidence-line:e, prov:wasDerivedFrom, paper:X)` exists (from `source:`),
  - line node carries `sci:evidenceStrength "strong"`, `sci:evidenceIndependence "independent"`, `sci:independenceGroup`, `sci:evidenceRole "model_criticism"`, `sci:disputeScope "generalization"`, and a `sci:shared*` triple.
- [ ] **Step 2: Emit the cito edge** — in `_add_relations`, add an evidence-line block (mirror the `structural-chain` special-case at materialize.py:260-276): map `stance` → `cito:supports`/`cito:disputes`, `target` → object; reuse `_resolve_relation_term("cito:…")` (already works, materialize.py:829). Route `source` through the existing `source_refs`/`prov:wasDerivedFrom` machinery (materialize.py:355-370).
- [ ] **Step 3: Emit line-specific metadata** — `_add_reasoning_metadata` (771-803) already emits `evidence_role`, `independence_group`, `measurement_model`. Add a sibling emitter for the line-only predicates, reusing the CLI path's predicate names for consistency: `sci:evidenceStrength`, `sci:evidenceIndependence` (already used at store.py:809), plus new `sci:disputeScope`, `sci:sharedDataset`, `sci:sharedLab`, `sci:sharedPlatform`, `sci:sharedCohort`. Call it from `_add_entity` (236) for evidence-line entities.
- [ ] **Step 4:** `cd science && uv run pytest tests/test_evidence_line_materialize.py -v` green; full suite green.
- [ ] **Step 5:** Commit `feat(graph): materialize evidence-line cito edge + metadata`.

---

### Task 8: Structural QA checks (design §QA #1, #2, #2b, #9)

**Files:**
- Create: `science/src/science_tool/validate/checks/evidence_lines.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py:42` (`_load_canonical_checks` tuple)
- Test: create `science/tests/test_evidence_line_checks.py` (templates: `test_chain_audit_references.py`; graph-traversal model `checks/graph.py`)

Use `@Check(section="evidence lines", order=N)`; `Result(severity, path, line, message, rule, task)` with `rule` set to the ids below. Parse the materialized `knowledge/graph.trig` (`Dataset().parse(..., format="trig")`) for graph-level checks. **No aggregation — purely structural/authoring hygiene.**

- [ ] **Step 1: Failing tests** — one fixture project per rule.
- [ ] **Step 2: Implement checks:**
  - `evidence.unstanced` (WARN) — an `evidence-line` entity missing `stance` or `target` (it must declare what it bears on and which way); and, separately, a source ref'd into a proposition with **no** evidence-line carrying a stance — surfaced as "uncounted source," not silently treated as support.
  - `independence.ungrouped-collapse` (ERROR) — `independence ∈ {shared-source, circular}` with no `independence_group` ("collapse to what?" is undefined).
  - `independence.suspect-circular` (WARN) — two evidence-lines on the same target both tagged `independent` that share an `independence_group` or any observability key (`shared_dataset`/`shared_lab`/`shared_platform`/`shared_cohort`).
  - `evidence.strength-implausible` (WARN) — `strength == strong` with `evidence_role == background_constraint` (strong should require a direct test, not background framing).
- [ ] **Step 3: Register** the module in `_load_canonical_checks()`.
- [ ] **Step 4:** Tests green; full `science validate` runs clean on a fixture with valid lines and flags the bad ones. Commit `feat(validate): evidence-line structural QA checks`.

---

### Task 9: End-to-end smoke + docs

**Files:**
- Test: `science/tests/test_evidence_line_e2e.py`
- Modify: any kind listing / `science entity list` enumerations that hardcode kinds (grep `"proposition"` in CLI help/list)

- [ ] **Step 1:** E2E test — `science entity create evidence-line`, fill frontmatter, `science graph build`, assert the cito edge + metadata appear and all four QA checks pass; corrupt one field and assert the matching check fires.
- [ ] **Step 2:** Update CLI help/enumerations and any `science health` kind inventories that list known kinds.
- [ ] **Step 3:** Commit `test(graph): evidence-line end-to-end`.

---

## Exit criteria (Phase 0 done)

- `evidence-line` is a registered epistemic kind; `science entity create evidence-line` works.
- An authored evidence-line round-trips frontmatter → `EvidenceLineEntity` → durable `cito:{supports,disputes}` edge + line metadata in `graph.trig`, surviving `graph build`.
- The four structural QA checks (`evidence.unstanced`, `independence.ungrouped-collapse`, `independence.suspect-circular`, `evidence.strength-implausible`) ship and pass/flag correctly.
- Both test suites green. No aggregation, belief, or edge-status code touched.

## Follow-on (NOT this plan)

- **Phase 1**: re-author the cancer-evolution h012↔Simeonov2021 dispute as an `evidence-line` (independent, strong, `evidence_role: model_criticism`, `dispute_scope: generalization`); implement independence-aware aggregation → `belief_state`; add QA #3/#4/#5/#6.
- **Authoring shortcut**: a nested evidence block on the proposition (or a compact `evidence-lines.yaml`) that materializes into identical `evidence-line` entities — ergonomics over the one graph shape.
