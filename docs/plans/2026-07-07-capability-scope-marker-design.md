# Capability-Scope Marker Design

## Status

Proposed. Tier-1 of a two-tier plan: this design ships a per-entity
`capability_scope` marker now; a second outcome/clinical measurement axis is the
declared end-state for one class of markers (Type I below) and is deferred.

## Context

The dataset capability-fit gate (`docs/plans/2026-07-03-dataset-capability-fit-gating-design.md`)
warns, in `science/src/science_tool/validate/checks/dataset_capabilities.py`, when an
entity reaches live targets/datasets but declares no capabilities:

- `dataset-capabilities.provided-missing` — a dataset reaches targets but has no
  `provided_capabilities`.
- `dataset-capabilities.required-missing` — a question/hypothesis reaches
  datasets but has no `required_capabilities`.

Both fire from the `missing` branch of `_capability_shape_issue`, which treats
`None`, absent, and `[]` identically. That is the defect: **an empty capability
field is overloaded**. It means two incompatible things at once —

1. *"not yet annotated"* — a molecular entity whose assay simply hasn't been
   filled in (a real TODO the warning should surface), and
2. *"non-molecular by nature"* — an entity for which no molecular assay is the
   measurement layer, so the field is *correctly* empty.

The validator cannot distinguish them, so it warns on both. There is no
field-level exemption anywhere in the framework today; the only existing
suppressor is demand-closed status.

### Empirical grounding

The marker vocabulary below is not invented — it is derived from a survey of the
three projects that use these fields (`provided_capabilities` /
`required_capabilities`):

- **MM30** (`~/d/cancer/cancer-types/multiple-myeloma`) — 32 non-molecular
  entities (15 datasets, 16 questions, 1 hypothesis) among ~130 that lack the
  field; the rest are molecular TODOs. Uses a molecular-only vocabulary
  (its "Decision A") plus a project-local `data-needs-audit` ledger.
- **post-acute-infection** (`~/d/health/processes/post-acute-infection`) —
  ~40 non-molecular entities. *Folds* non-molecular measurement into
  capabilities as first-class tokens on extra axes (`outcome`, `cohort_design`,
  `modality: clinical-ehr/epidemiology`); a clinical cohort declares
  `{cohort_design: meta-analysis, outcome: fatigue}` and omits `modality`.
  Deliberately has no ledger.
- **cbioportal** (`~/d/cancer/data-sources/cbioportal`) — ~20 non-molecular
  entities. Folds in *ad hoc* (`assay: clinical-covariates`,
  `pathway-driver-annotation`, `curated-marker-database`) with no governance, so
  it is inconsistent: some reference resources carry tokens while COSMIC/OncoKB/
  SomaMutDB carry a blank block — the exact TODO-vs-N/A ambiguity, untamed.

### The structural finding: two situations, not one

Every legitimately non-molecular entity across the three corpora falls into one
of two structurally different situations. This distinction — not the specific
labels — is the load-bearing result:

- **Type I — measures something, just not molecules.** Clinical labs, survival /
  response / MRD endpoints, symptoms / QoL, epidemiology, questionnaires,
  wearables. These have a *real non-molecular measurement axis*. PAIS and
  cbioportal already describe them with positive tokens.
- **Type II — measures nothing at all.** Reference/annotation catalogs, LD
  panels, gene-set collections, project-produced result tables, and pure
  method / census / vocabulary-curation questions, and model-system pointers.
  There is *no* axis on which they measure anything; a positive token would be a
  fabrication.

The two live philosophies (MM30's exclude-and-mark vs PAIS's fold-in) are each
half-right. Type I genuinely wants a measurement axis (fold-in is honest and more
expressive — it also fixes the gate's own known cross-modality over-credit for
outcome questions). Type II genuinely wants "not applicable" (a marker is honest;
a token is a lie). This design serves both by making the marker primary now and
recording, per entity, which situation it is — so Type I can migrate onto a real
axis later without rework.

## Goals

- Make "intentionally outside the molecular assay/modality gate" a **first-class,
  positively-declared, validator-visible** state.
- Suppress the false `*-missing` warning for scoped entities **without**
  suppressing genuine molecular-TODO warnings.
- **Never** grant molecular coverage credit to a scoped entity.
- Record **why** (Type I vs Type II) so the marker is legible and
  forward-compatible with a future outcome axis.
- Add an **audit lint** that can falsify a wrong marker.
- Stay framework-native: no dependency on any project-local ledger or file layout.

## Non-Goals

- Do **not** build the outcome/clinical measurement axis now. It is the declared
  end-state for Type I markers and is deferred until a real outcome-fit question
  demands it.
- Do **not** solve cross-axis / cross-dataset outcome-fit matching (a question
  that needs `expression AND drug-response` from two different datasets).
- Do **not** change the molecular `{assay, modality}` vocabulary, the matching
  engine, or MM30's Decision A.
- Do **not** auto-infer the marker from absence, other frontmatter, or file
  contents. Inference cannot separate "non-molecular" from "unannotated" — that
  is the definitional reason the marker must be a human declaration. Absence is
  not evidence of intent.

## Data model: the `capability_scope` field

A new optional frontmatter key, valid on `dataset`, `question`, and `hypothesis`
entities:

```yaml
capability_scope: clinical-outcome
```

**Meaning (single, precise):** *this entity is outside the molecular
assay/modality gate.* It is a positive declaration that the empty
`provided_capabilities` / `required_capabilities` is intentional and complete,
not a pending annotation.

**Value is a controlled enum**, owned by a small framework registry module
(`science_tool.datasets.capability_scope` — see Resolved decisions), drawn from
the derived vocabulary:

| Type | Value | Definition | Example members |
|---|---|---|---|
| II | `reference-substrate` | External curated catalog, annotation track, LD panel, gene-set collection, or corpus/panel metadata registry — enables molecular analysis, measures nothing itself. | COSMIC, OncoKB, PanglaoDB, MSigDB collections, GENIE panel-callable registry, MM30 probe-collapse policy artifact |
| II | `derived-product` | A project-produced **result artifact with no independent measurement capability**. *Narrow:* NOT "anything downstream of assays" — a cleaned per-study mutation table is still a molecular substrate and must be annotated, not scoped. | cbioportal gene-cancer-study-ratio summary table |
| II | `methodological` | Question answered by an algorithm / statistic / pipeline-design / census / vocabulary-curation decision over **already-derived** artifacts; consumes no assay matrix. | MM30 meta-method questions (q0001/q0003/q0176/…), cbioportal aggregator/saturation questions |
| II | `model-system` | In-vivo / functional model or analogy pointer with no catalogued assay. | MM30 chek2-mouse, vk-myc-mouse |
| I | `clinical-outcome` | Clinical labs, survival, treatment response / MRD endpoints, symptom / QoL, frailty, drug-dosing. | MM30 chabrun clinical cohorts, MRD trials, q0018 (symptom/QoL); cbioportal TCGA clinical; PAIS EHR cohorts |
| I | `epidemiological` | Population incidence / prevalence / burden / exposure. | PAIS dengue/Q-fever/Lyme cohorts, burden questions |
| I | `behavioral-instrument` | Questionnaire / self-report / neurocognitive-task / wearable / EMA. | PAIS PEM self-report, wearable-EMA protocol |

**Type II values are terminal** not-applicable states — an entity marked
`reference-substrate` will never acquire molecular capability. **Type I values are
transitional** — they suppress molecular-warning noise now, but they are *not*
the final representation of endpoint/clinical coverage; they are a forward pointer
to the deferred outcome axis (see End-State).

A project uses only the subset it has: MM30 needs `clinical-outcome`,
`methodological`, `model-system`, `reference-substrate`; PAIS additionally needs
`epidemiological`, `behavioral-instrument`, `derived-product`.

**Mutual exclusion.** `capability_scope` is mutually exclusive with **any
non-empty** capability field (`provided_capabilities` / `required_capabilities`)
on the same entity. Tier 1 has no governed non-molecular axis, so there is no
capability an entity could legitimately declare *alongside* a scope. A project may
either keep fold-in tokens or use the marker on a given entity — never both.
Declaring both is a contradiction the validator flags (`scope-conflict`, see
Validator changes). Rationale goes in the entity body or an inline `#` comment;
the field itself stays a scalar enum.

## Validator changes

All in `science/src/science_tool/validate/checks/dataset_capabilities.py`.

1. **Suppression.** In the `missing` branch (both dataset and Q/H paths), if the
   entity carries a valid `capability_scope` value, emit no warning. Absent /
   `None` / `[]` with **no** `capability_scope` continues to warn exactly as
   today — the molecular-TODO signal is preserved intact.
2. **Unknown-value check.** A `capability_scope` outside the enum → WARN
   (`dataset-capabilities.scope-unknown`). Fail closed: an unknown value does not
   suppress.
3. **Contradiction check.** `capability_scope` set **and any non-empty**
   capability field (`provided_capabilities` / `required_capabilities`) on the
   same entity → WARN (`dataset-capabilities.scope-conflict`).
4. **Audit lint (falsifiability).** A scoped **dataset** that reaches a live
   target whose `required_capabilities` is a non-empty molecular set → WARN
   (`dataset-capabilities.scope-contradicted`): the dataset is declared
   non-molecular yet sits on the provider side of a live molecular requirement,
   which usually means either the scope or the reach is wrong. Note this must be a
   pure graph/frontmatter contradiction — keying the lint on a `capability_fit`
   *match* would make it inert, because a valid scoped dataset has empty caps and
   `capability_fit` fail-closes empties, so it can never match. File-level checks
   ("ships molecular data files") and assay-matrix-consumption checks are
   project-local, documented as a project responsibility, not implemented in the
   framework lint.

## Matching engine and coverage surfacing

**No change to `science/src/science_tool/datasets/capabilities.py`.** `capability_fit`
already fail-closes an empty provided/required set to `compatible=False`
(`missing-provided-capabilities` / `missing-required-capabilities`). A scoped
entity has an empty molecular set, so it can never satisfy a molecular
requirement — the "never grants molecular credit" goal holds *for free*. The
marker is deliberately a validator- and coverage-surfacing concept only.

**Coverage surfacing** (`science/src/science_tool/dataset_prioritize.py`): a scoped target
or dataset should report a distinct `out-of-molecular-scope` coverage state
(carrying the `capability_scope` value as its reason) rather than one of the
capability-gap reasons (`missing-required-capabilities`, etc.). This keeps
`science dataset prioritize --coverage` from listing intentional scopes as gaps,
mirroring the validator's suppression.

## The q0003 vs q0148 discriminator

The fuzziest boundary in the corpus — and the one the spec must state explicitly
so `methodological` is not over-applied:

- **Scopeable (`methodological`):** operates *only* on already-derived rankings /
  results / scores / outputs. Example: MM30 q0003 re-partitions the existing meta
  signal into proliferation vs other axes — no assay matrix is read.
- **NOT scopeable (molecular TODO):** *consumes an assay matrix*, even if the work
  is internal, `not_external`, or fully in-silico. Example: MM30 q0148 projects a
  signature onto the MM30 bulk expression matrix, so it requires
  `gene-expression` and must be annotated, not scoped.

Corollary: a project-local ledger's `not_external` class is **not** the same as
non-molecular. q0003 and q0148 are both `not_external`; only q0003 is
non-molecular. Any project mapping a ledger to markers must apply the
matrix-consumption discriminator, not the ledger class.

## Relationship to project-local policy

The framework provides the marker, the enum, the validator branches, the audit
lint, and the coverage state. Whether a project *also* folds non-molecular
measurement into `provided_capabilities` (as PAIS does) is project vocabulary
policy and is not forbidden. MM30 keeps Decision A: its Type-I entities receive a
`capability_scope` marker rather than clinical tokens. MM30's `data-needs-audit`
ledger remains the richer human adjudication record; the marker is the
machine-readable signal, and a project may cross-check the two.

## End-state: the deferred outcome axis (Tier 2)

The honest long-term model gives Type-I entities a real, independently-matched
outcome/clinical axis (separate capability *sets* keyed on `outcome` /
`cohort_design`, matched by the existing key-agnostic `_satisfies`, never merged
into the molecular set — consistent with Decision A's actual intent). This is
already the de-facto model in two of the three surveyed projects and it fixes the
gate's cross-modality over-credit for outcome questions. It is deferred because
its hard part — cross-axis requirements satisfied across *multiple* datasets —
needs matching semantics the current OR-of-sets engine does not have, and no live
question demands it yet.

Forward-compatibility is designed in: Type-II marker values are permanent; Type-I
marker values (`clinical-outcome`, `epidemiological`, `behavioral-instrument`)
name exactly the entities that migrate onto the outcome axis when it ships. The
scope value is the migration key, so nothing written under this design is thrown
away.

## Rollout

1. **Framework:** add the field + enum registry module
   (`science_tool.datasets.capability_scope`), the four validator behaviors, the
   coverage state, user-guide docs, and tests.
2. **MM30:** annotate the 32 surveyed non-molecular entities — clearing the 8
   currently-firing warnings (7 chabrun/chek2-adjacent datasets + q0018) honestly,
   and pre-empting the rest.
3. **cbioportal / PAIS:** opt-in adoption for their Type-II entities (the
   reference/method blanks); their Type-I fold-in tokens can remain until the
   outcome axis lands.

## Resolved decisions

- **Audit-lint reach split — accepted.** The framework lint asserts only
  graph/frontmatter contradictions (a scoped dataset reaching a live molecular
  target, per Validator change 4). Checking shipped files and assay-matrix
  consumption is project-local code, not a framework responsibility.
- **Enum governance — framework-owned registry module.** The allowed values, the
  scope type/class, and their definitions live in one small framework module
  (`science_tool.datasets.capability_scope`), consumed by the validator and
  coverage surfacing — not hardcoded validator-locally, and not a
  project-extensible YAML at this tier. A project requests a new value by changing
  that module plus its docs and tests.
- **Hypotheses in scope.** The field is validated on hypotheses as well as
  questions and datasets. The validator already treats questions and hypotheses
  together; excluding hypotheses would add a needless special case for the one
  known non-molecular MM30 hypothesis.
