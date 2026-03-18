# Claim-Centric Uncertainty Design

> Canonical reference: [`docs/claim-and-evidence-model.md`](../claim-and-evidence-model.md) defines the reasoning model terminology and belief-update rules used by this design.
> Dashboard contract: [`docs/claim-centric-dashboard-contract.md`](../claim-centric-dashboard-contract.md) defines the stable claim and neighborhood summary shapes that should drive uncertainty views.
> Long-term roadmap: [`2026-03-18-claim-centric-reasoning-roadmap.md`](./2026-03-18-claim-centric-reasoning-roadmap.md) extends this design into a phased reasoning architecture for summaries, prioritization, and multi-scale views.

## Summary

Science should adopt a skeptical, claim-centric reasoning model.
Scientific relations should not be represented as settled edges by default.
Instead, the primary unit of belief should be a `claim`, especially a `relation_claim` for graph-native assertions such as `X affects Y`.
Evidence should update claim `belief_state` rather than directly validating or deleting graph edges.

This design keeps the model opt-in and layered:

- users can still start with questions, hypotheses, and inquiry sketches
- richer formalization becomes available as they add claims, evidence, studies, and results
- uncertainty is derived from evidential structure rather than authored as a simple scalar truth label

## Goals

- Make all scientific assertions uncertain by default.
- Make `claim` and `relation_claim` the first-class units of uncertainty.
- Aggregate support and dispute from multiple evidence lines.
- Distinguish evidence types by epistemic weight, especially empirical vs simulation evidence.
- Support future structured study/result metadata without forcing it on every project.
- Use uncertainty to prioritize work, especially through neighborhood-level fragility analysis.
- Align code, commands, templates, README language, and skills to the same reasoning model.

## Non-Goals

- Do not build a fully calibrated Bayesian engine in the first iteration.
- Do not introduce full formal logic or premise/inference-rule systems in v1.
- Do not remove `question`, `hypothesis`, or `inquiry`; instead reinterpret them in a layered model.
- Do not require every project to author full experiment metadata before using the graph.

## Design Decisions

### 1. Claims Are The Primary Unit Of Uncertainty

The system should compute belief where scientific assertions live: in `claim` and especially `relation_claim`.
Questions, hypotheses, and inquiries remain user-facing structures, but they should summarize claim `belief_state` rather than replace it.

### 2. Hypotheses Stay Layered And Less Committal

`hypothesis` should remain a higher-level conjecture or bundle of related claims.
It should not become a separate competing epistemic core, and this design does not require treating it as a subtype of `claim`.

### 3. Evidence Targets Claims, With Study And Result As Structure

Evidence should attach to claims, not directly to uncertain scientific edges.
`study` and `result` provide structured provenance and outcome records that can ground evidence without forcing every project into a heavy schema on day one.

### 4. Uncertainty Is Derived From Evidential Structure

Confidence, uncertainty, contestation, and fragility should be derived from support and dispute patterns rather than authored as primary truth labels.
Neighborhood uncertainty remains secondary and should be used for prioritization, not as the main belief score.

## Mismatch Resolutions

### 1. Hypothesis-Centric Evidence Querying

Current mismatch:
- `query_evidence(...)` in `science_tool.graph.store` is centered on hypotheses and direct evidence-to-hypothesis links.

Resolution:
- make evidence querying claim-centric
- support hypothesis summaries as aggregations over subordinate claims
- treat direct evidence-to-hypothesis links as transitional compatibility behavior only

### 2. Scalar Entity-Centric Uncertainty

Current mismatch:
- `query_gaps(...)` and `query_uncertainty(...)` inspect confidence as a direct property on entities or claims
- there is no evidential aggregation or neighborhood diffusion

Resolution:
- compute claim uncertainty from support/dispute structure
- compute entity-level and neighborhood-level uncertainty secondarily
- preserve structural fragility signals like low connectivity, but separate them from epistemic uncertainty

### 3. Direct Edge Assertion

Current mismatch:
- `graph add edge` creates asserted facts even for uncertain scientific relations

Resolution:
- reserve direct edge authoring for structural or organizational facts
- introduce claim-backed authoring for uncertain scientific assertions
- permit sketch edges only when clearly marked as tentative or inquiry-local

### 4. Heuristic Claim-to-Edge Matching in Causal Export

Current mismatch:
- causal exporters infer support by matching claim text to edge endpoint names

Resolution:
- attach explicit `relation_claim` references to inquiry and causal edges
- export evidence strength, dispute, and gaps from attached claim bundles
- keep ungrounded edges exportable but explicitly flagged

### 5. Flat Confidence Dashboard

Current mismatch:
- the visualization layer scans `sci:confidence` literals directly and treats them as the main quality signal

Resolution:
- redesign around evidential state:
  - weakly supported claims
  - contested claims
  - single-source claims
  - claims lacking empirical evidence
  - high-uncertainty neighborhoods

## Command, Template, and Skill Implications

### High-Impact Command Changes

- `commands/add-hypothesis.md`
  - keep hypotheses, but frame them as uncertain claim bundles
- `commands/sketch-model.md`
  - replace “assert edge + justification claim” with “record candidate relation-claim”
- `commands/specify-model.md`
  - make this the main bridge from sketch edges to typed relation-claims with evidence bundles
- `commands/interpret-results.md`
  - update support/dispute and uncertainty, rather than flipping hypothesis status directly
- `commands/compare-hypotheses.md`
  - compare claim support structure and unresolved uncertainty, not only “which hypothesis wins”
- `commands/status.md`
  - orient the user around uncertain claims and evidence state, not settled edges

### Template Changes

- `templates/hypothesis.md`
  - add fields for subclaims, current uncertainty, supporting evidence, disputing evidence, and belief shifts
- `templates/comparison.md`
  - focus on claim-by-claim support, disputes, and discriminating evidence
- `templates/experiment.md`
  - prepare for richer study/result metadata
- `templates/interpretation.md`
  - explicitly capture belief updates and residual uncertainty

### Global Language Changes

- `README.md`
- `skills/research/SKILL.md`
- `skills/writing/SKILL.md`
- `references/role-prompts/discussant.md`

These files must be updated so the project consistently teaches:

- claims are uncertain
- evidence updates belief
- support and dispute matter more than discrete hypothesis verdicts
- direct graph edges are not equivalent to established truth

## Ontology Alignment

The model should learn from existing systems rather than inventing every term from scratch:

- SEPIO for assertions, evidence lines, provenance, and confidence concepts
- PROV-O for derivation and activity provenance
- ISA for investigation / study / assay structure
- EFO for domain vocabulary around conditions and factors
- STATO for statistical methods and result descriptors

These should inform the semantic design without forcing full ontology adoption in v1.

## Canonical Reference Document

`docs/claim-and-evidence-model.md` is the canonical home for:

- reasoning-model definitions
- evidence taxonomy and stance language
- authored versus derived fields
- epistemic vocabulary
- worked examples

This design doc should defer to that reference instead of duplicating canonical terminology or schema detail.

## Rollout Strategy

### Phase 1

- introduce first-class claim / relation-claim / evidence / study / result semantics
- keep compatibility with existing question / hypothesis / inquiry structures

### Phase 2

- add claim-centric querying and uncertainty aggregation
- adapt dashboards and status views

### Phase 3

- align commands, templates, and skills
- update user guidance to teach skeptical defaults

### Phase 4

- add richer empirical and simulation evidence structure
- add neighborhood uncertainty and prioritization workflows

## Design Decision

The system should be built around `claim` and `relation_claim`, not around settled edges or discrete hypothesis verdicts.
Questions and hypotheses remain valuable, but uncertainty should be computed where the scientific assertions live: in the claims that evidence supports or disputes.
