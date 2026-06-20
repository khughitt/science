---
type: question
title: How should Science detect and prevent epistemic drift between an entity's claims
  and its operationalization?
status: active
created: '2026-06-04'
updated: '2026-06-04'
id: question:0015-claim-operationalization-drift
ontology_terms: []
datasets: []
source_refs: []
related:
- question:0014-adaptive-project-topology
- question:0005-authoring-cost-audit
---

# How should Science detect and prevent epistemic drift between an entity's claims and its operationalization?

## Summary

A real failure in the `multiple-myeloma` project exposed a category of drift the framework
does not currently catch. Hypothesis H2 ("cytogenetic subtypes are distinct disease
entities") was rated `supported` / high-confidence and treated as a top organizing model,
but its prose claimed far more than its implementation supported: the pipeline operationalizes
**7** cytogenetic events (`constants.py::EVENTS`) and is analytically load-bearing on only
**2** (gain(1q), hyperdiploidy). Meanwhile a paper note and a project decision (D5) asserted
the pipeline "covers" del(1p) and t(14;20) when the code never operationalized them — a claim
that directly contradicted an authoritative code manifest. Linked questions that flagged the
missing high-risk subtypes existed but were only weakly bound and never reshaped the
hypothesis.

This question asks: which forms of **claim-vs-operationalization drift** can the framework
detect and prevent — mechanically where possible, agentically where not — across **all
load-bearing (epistemic) entity types**, not just hypotheses?

## Why It Matters

- The current freshness engine is *event-driven* (an upstream entity changed) and
  *horizon-driven* (time since `last_reviewed`). Neither fires on an entity that was
  **over-scoped from the start and then sat still**. "Looks settled" is precisely the blind
  spot, and confidence ratings make it worse by signalling the opposite.
- Structural orphan detection (`no_outbound_links`, unresolved refs, `graph validate`
  orphaned nodes) did not and could not catch this: the gap-flagging questions were *linked*,
  not orphaned. The miss was *semantic under-attention*, not disconnection.
- Prose-vs-code drift (a decision/doc asserting coverage the code contradicts) is a recurring,
  high-cost failure that no validate check currently inspects. `graph diff` checks
  prose↔graph sync, not prose↔implementation.
- Risk if unanswered: confident, well-cited entities silently overstate scope; downstream
  synthesis inherits the overstatement; and the project's own caveat-bearing questions pile up
  unread against the very entities they should be re-scoping.

## Three Failure Modes (from the H2 exemplar)

- **A — Scope/operationalization drift.** An entity's stated scope exceeds what is actually
  measured/operationalized. Static-detectable *if* the entity declares what operationalizes it;
  otherwise needs agentic review for leaky language and altitude.
- **B — Prose-vs-implementation drift.** Prose asserts a fact about what code/pipeline does
  (e.g. "covers del(1p)") that an authoritative manifest contradicts. Mechanically checkable
  against a declared manifest source.
- **C — Weakly-bound / under-attended questions.** Questions that pertain to an entity
  accumulate without ever being folded into its claims. Computable as per-entity "open-question
  debt" — but over the **`related:` + theme/tag** connectivity layer, **not** `bears_on`:
  `bears_on` is derived only from typed predicates (`graph/freshness.py:70`), so the
  related-only/unlinked questions that drive this failure are invisible to it. A debt metric over
  `bears_on` would inherit the same blind spot. Debt statuses are the canonical question
  vocabulary `active` / `partially-answered` / `deferred` (`entities.py:97`), excluding
  `answered` / `retired`.

## Current Evidence

- The model already supports `review_state.last_reviewed` and
  `review_state.review_horizon_days`, a full freshness engine (`fresh`/`stale`/`needs-review`)
  with `bears_on` upstream propagation (and `bears_on` derives **only** from typed edges, not
  `related:` — `graph/freshness.py:70`), and attention weighting (3× needs-review, 2× stale). A
  `science entity review` command already *populates* `review_state.last_reviewed`
  (`entity_review.py:39`, `cli.py:494`). So the substrate and a populator both exist; what is
  missing is (i) that the existing command permits a **bare timestamp bump** with no artifact —
  the real gap is artifact-guarded review, i.e. hardening that command, not building population;
  (ii) a skill that performs the actual scrutiny; and (iii) checks for failure modes A and B.
- `EntityClass` already separates EPISTEMIC / OPERATIONAL / REFERENCE, so any review machinery
  can be entity-type-agnostic with type-specific rubrics rather than hypothesis-only.
- Adjacent commands (`bias-audit`, `discuss`, `curate`, `dag-audit`, `next-steps`) cover parts
  of the space but none diffs claimed scope against operationalized scope, nor prose against a
  code manifest.

## Thoughts

- Best current interpretation: split the problem by detectability, mirroring q05's stance on
  source dependence.
  - Mechanically detectable: prose-vs-manifest coverage (B); scope-vs-declared-operationalization
    (A, when an `operationalized_by:` link is declared); open-question debt (C).
  - Requires agentic judgment: leaky language, altitude mismatch, hidden assumptions,
    falsifiability erosion — the residue after static checks.
- Highest-leverage single mechanism is likely an **operationalization-coverage check**: let
  scoped empirical entities optionally declare `operationalized_by:` (a manifest/variable/event
  set), and fail validation when prose scope or coverage claims exceed it. This is cheap,
  deterministic, and would have caught both the H2 over-scope and the D5/paper coverage error.
- The agentic layer is a generalized `review` skill (entity-type-agnostic, rubric per kind)
  that consumes the attention ranking and writes guarded `review_state` — guarded meaning a
  review must emit a concrete artifact (finding, diff, task, or explicit reasoned "no change"),
  never a bare timestamp bump, to avoid review-theater.
- Prioritization should not rest on time horizons alone (busywork). The sharpest trigger is the
  conjunction *settled-looking + heavily-caveated + overdue*: `status: supported` + high
  confidence + old `last_reviewed` + high open-question debt.

## Connections to Project

- Related questions: `question:0014-adaptive-project-topology` (topology adaptation to
  evidence/uncertainty/decay — this question is the drift-detection half of that), and
  `question:0005-authoring-cost-audit` (the `operationalized_by:` contract and agentic review both
  add authoring cost that must be justified).
- Design artifact: `docs/plans/2026-06-04-epistemic-drift-detection-design.md` (proposes the
  three mechanisms and a staged rollout).
- Required analyses: enumerate drift patterns; score each on mechanical detectability;
  prototype the coverage check + open-question-debt term on a real project (multiple-myeloma H2
  is a ready regression fixture).
- Priority: medium-high — the failure it targets corrupts synthesis silently and is recurring.

## Related

- Sibling project exemplar: `multiple-myeloma:hypothesis:h2-cytogenetic-distinct-entities`
  (the regression fixture), with the doc fixes in that project's `core/decisions.md` D5 and
  `doc/papers/Lu2025.md`.
