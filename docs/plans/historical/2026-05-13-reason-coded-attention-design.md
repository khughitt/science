---
id: "plan:2026-05-13-reason-coded-attention-design"
type: "plan"
title: "Reason-coded attention design"
status: "draft"
created: "2026-05-13"
related:
  - "hypothesis:h03-reason-coded-revisiting-beats-posterior-only-revisiting"
---

# Reason-Coded Attention Design

**Status:** draft
**Date:** 2026-05-13
**Scope:** upstream Science framework

## Purpose

Science already supports the core pieces needed for continuous epistemic attention: propositions as uncertain entities, evidence edges, `bears_on` freshness, and weighted attention sampling with an epsilon floor.
This design extends that surface from freshness-weighted sampling to reason-coded attention.

The goal is not to replace belief updating with another score.
The goal is to keep three quantities separate:

| Weight | Meaning | First consumers |
| --- | --- | --- |
| Belief | how much current evidence supports a proposition | `big-picture`, proposition and hypothesis summaries |
| Attention | how often the project should revisit or sample an entity | `status`, `next-steps`, `wander`, `graph attention-sample` |
| Influence | how much the entity should shape current narrative or decisions | synthesis rollups, reports, manuscript framing |

A low-belief proposition can deserve high attention when it has high option value, missing orthogonal evidence, or unclear measurement.
A high-belief proposition can deserve low attention when it is stable and recently reviewed.
A high-attention proposition can have low influence when it is interesting but not yet load-bearing.

## Existing anchors

This design extends existing upstream commitments rather than adding a parallel model:

- `docs/proposition-and-evidence-model.md` defines propositions, observations, and evidence edges as the core reasoning model.
- `meta/core/decisions.md` D-003 states that operational beliefs are continuous in `(0, 1)`.
- `meta/specs/hypotheses/h01-stochastic-revisiting.md` motivates non-zero revisit probability for down-weighted propositions.
- `meta/specs/hypotheses/h02-rich-evidence-payloads-improve-graph-calibration.md` argues that evidence payloads need more structure than scalar support/dispute.
- `meta/specs/hypotheses/h03-reason-coded-revisiting-beats-posterior-only-revisiting.md` argues that the reason for uncertainty should shape revisiting.
- `docs/plans/historical/2026-05-03-epistemic-dependency-graph-design.md` defines `bears_on`, freshness, and the graph-level attention surface.
- `science_tool.graph.attention` currently computes attention from observable graph features: `bears_on`, freshness, review age, support/dispute counts, and epsilon.

This plan is one operationalization of H03, not evidence that H03 is settled.
The pilot comparison below should feed back into H03's status as `simulation_evidence` or `benchmark_evidence`, depending on whether it uses synthetic or project-real graph state.

## Design stance

Reason codes must come from observable graph state, structured evidence payloads, or reviewed annotations with provenance.
They should not be inferred silently by an LLM and then treated as equivalent to derived graph facts.

The first implementation should be deliberately small.
It should add a reason payload to attention candidates before changing any sampling policy.
Sampling can continue to use the current weight formula until the reason payload is inspectable and testable.

## V1 glossary and schema choices

**Observable inbound edge count** means the number of distinct upstream entity URIs that directly target the candidate with `sci:bearsOn`, `cito:supports`, or `cito:disputes`.
It is useful for attention bookkeeping but is not an evidence-base size.

**Evidence source count** means the number of distinct upstream entity URIs that directly target the candidate with evidence-bearing `cito:supports` or `cito:disputes` edges.
Phase 1 fragility uses this stricter count rather than `sci:bearsOn`, because `bears_on` is a dependency/relevance edge and does not by itself imply empirical support or dispute.
Evidence source count is still only a Phase 1 proxy for independent source count, not a claim that the sources are genuinely independent.
Richer independence groups belong to the evidence payload layer.

**Candidate scope** is proposition-only for Phase 1 reason derivation.
Non-proposition attention candidates should still emit `reasons: []` when the reason pass ran, but Phase 1 should not pretend that contestation, fragility, or counterevidence have identical semantics for hypotheses, observations, questions, or operational entities.
Later phases may add kind-specific rules.

**Reason strength** is categorical in v1: `low`, `moderate`, or `high`.
Numeric strengths are deferred until there is calibration evidence.

**Direction** is an enum:

| Direction | Meaning |
| --- | --- |
| `increase_attention` | reason should raise revisit priority |
| `decrease_attention` | reason should lower revisit priority while preserving the epsilon floor |
| `route_attention` | reason mainly changes the next action or review bucket, not the scalar priority |

**Next action** is a controlled vocabulary in v1:

- `seek_independent_evidence`
- `compare_contexts`
- `preserve_floor`
- `review_measurement_validity`
- `seek_target_context_evidence`
- `causal_audit`
- `search_orthogonal_modality`
- `exploratory_revisit`
- `scaffold_evidence_base`

Candidates should always emit `reasons`.
Use `reasons: []` when the reason pass ran and no reason qualified.
Omitting the field means legacy output or a code path that did not attempt reason extraction.

**Provenance** is a controlled string in v1:

- `derived:<rule_id>(<comma-separated source fields>)` for graph-derived reasons;
- `payload:<field_name>` for reasons copied from structured evidence payloads;
- `reviewed:<annotation_id>` for reviewed annotations.

For example, contestation derived from support and dispute counts should use `derived:contestation_counts(support_count,dispute_count)`, not a free-text provenance sentence.

**Shared payload fields** are standardized before downstream projects depend on them.
Phase 2 should define `evidence_type`, `stance`, `measurement_model`, and `independence_group` for evidence payloads.
Phase 3 should define `claim_layer`, `identification_strength`, and `influence_role` for causal or narrative claims.
Projects may use explicit prose labels before these fields exist, but they should not treat those labels as machine-visible schema.

## Reason components

| Component | Phase | Preferred provenance | Initial action |
| --- | --- | --- | --- |
| `unscaffolded` | Phase 1 | zero evidence-bearing source edges | create or attach first support/dispute evidence |
| `fragility` | Phase 1 | low non-zero evidence source count; later: independence groups, platform, cohort, pipeline | revisit or seek independent evidence |
| `contestation` | Phase 1 | support and dispute evidence both present | compare contexts and moderators |
| `strong_counterevidence` | Phase 1 | disputing evidence dominates support | lower revisit, preserve epsilon |
| `novelty_option_value` | Phase 2 | reviewed annotation with rationale and source | low-rate exploratory revisit |
| `proxy_risk` | Phase 2 | proposition has `measurement_model` with known failure modes | review measurement validity |
| `transport_risk` | Phase 2 | source and target populations differ materially | seek target-context evidence |
| `identification_gap` | Phase 3 | causal claim layer with observational or missing identification strength | causal audit |
| `missing_modality` | Phase 4 | boundary map or evidence payload marks a missing view | search for orthogonal modality |

`novelty_option_value` is intentionally not auto-derived in v1.
It is a reviewed annotation because option value depends on project goals and is too easy to fake from novelty alone.
Reviewed `novelty_option_value` reasons must include a `review_by` or expiration date so they do not accumulate indefinitely.

## Phase 1 derivation rules

Phase 1 reason extraction uses only fields already available to the attention surface or directly countable from the materialized graph.

| Reason | Emit when | Strength rule | Direction | Next action |
| --- | --- | --- | --- | --- |
| `unscaffolded` | `evidence_source_count == 0` | always `high` | `route_attention` | `scaffold_evidence_base` |
| `fragility` | `evidence_source_count >= 1` and `evidence_source_count <= 2` | `high` if `== 1`, `moderate` if `== 2` | `increase_attention` | `seek_independent_evidence` |
| `contestation` | `support_count >= 1` and `dispute_count >= 1` | `high` if `min(support, dispute) >= 2`; `moderate` if counts are balanced at a ratio strictly less than 3:1; otherwise `low` | `increase_attention` | `compare_contexts` |
| `strong_counterevidence` | `dispute_count >= 1` and `support_count == 0`, or `dispute_count >= 2 * max(support_count, 1)` with `dispute_count >= 2` | `high` if `support_count == 0` and `dispute_count >= 3`, or dispute/support ratio `>= 3`; otherwise `moderate` | `decrease_attention` | `preserve_floor` |

These thresholds are policy defaults, not calibrated truth.
They should be easy to change after the first pilot.
`contestation` and `strong_counterevidence` can both fire on the same proposition when evidence is mixed but skewed toward dispute.
In Phase 1, `direction` is advisory metadata only; no consumer should aggregate directions into a scalar priority.
The first reason-aware review-routing phase must define conflict handling before using direction to route candidates.
`unscaffolded` prevents zero-evidence proposition stubs from masquerading as ordinary fragility.
Phase 1.5 should route these to an evidence-scaffolding queue and should not let them flood top-ranked exploratory sampling solely because they have no evidence edges.

## Output contract

Add a reason-aware attention candidate shape without removing existing fields:

```json
{
  "id": "proposition:p01",
  "kind": "proposition",
  "label": "Readable label",
  "attention_weight": "12.5000",
  "belief_weight": null,
  "influence_weight": null,
  "reasons": [
    {
      "code": "fragility",
      "direction": "increase_attention",
      "strength": "moderate",
      "provenance": "derived:fragility_source_count(evidence_source_count)",
      "next_action": "seek_independent_evidence"
    }
  ]
}
```

`belief_weight` and `influence_weight` may be absent in the first pass.
The output contract reserves the names so downstream commands do not overload attention weight as belief.
Consumers must not derive belief from `attention_weight`, `direction`, or `strong_counterevidence`.
Counterevidence is evidence payload for belief-updating logic; its attention direction only says how this sampler should route future review.

## Sequencing

### Phase 1 - reason payload only

Entry point: `science/src/science_tool/graph/attention.py`.

Definition of done:

- attention candidates include a `reasons` list;
- Phase 1 reason codes are derived only for proposition candidates and only from currently observable graph fields;
- candidates with no qualifying reasons emit `reasons: []`;
- reason payloads use the v1 `direction`, `strength`, and `next_action` enums above;
- existing `attention_weight` behavior remains unchanged;
- tests cover at least `unscaffolded`, `fragility`, `contestation`, and `strong_counterevidence`;
- `graph attention-sample --format json` emits reasons.

### Phase 1.5 - opt-in reason-aware review-routing toggle

Entry point: `science/src/science_tool/graph/attention.py`.

Definition of done:

- a non-default CLI option can route a bounded reason-coded review slice before weighted sampling fills the remaining slots;
- the default `attention_weight` and default sampler remain unchanged;
- direction conflicts are handled explicitly before routing.

Initial conflict policy: if `strong_counterevidence` co-occurs with `contestation`, the candidate is routed to a counterevidence-review bucket and is not promoted by `contestation` alone.
The epsilon floor still applies, and the output should preserve both reasons so a reviewer can see why the route happened.
Other conflicting directions should be reported as unresolved rather than silently averaged.
If `unscaffolded` fires, route the candidate to evidence scaffolding rather than ordinary uncertainty-driven promotion.
The first implementation should promote ordinary uncertainty-review reasons such as `contestation` and `fragility`, cap that promoted slice, and fill the remaining output slots with the existing weighted sampler so no-reason and epsilon-floor candidates remain reachable.

### Phase 2 - reviewed annotations

Entry point: proposition or annotation frontmatter schema.

Definition of done:

- reviewed annotations can add `novelty_option_value` reasons;
- structured evidence payloads can emit `proxy_risk` and `transport_risk` reasons when the relevant fields are present;
- each reviewed reason records author/source/date/rationale;
- reviewed `novelty_option_value` reasons without a future `review_by` or expiration date fail validation or are excluded from reason-coded sampling;
- evidence payload fields standardize at least `evidence_type`, `stance`, `measurement_model`, and `independence_group`;
- derived and reviewed reasons are distinguishable in CLI output.

### Phase 3 - separate influence from belief and attention

Entry points: `big-picture`, synthesis rollup generation, and status/next-steps summaries.

Definition of done:

- synthesis can down-weight high-attention exploratory signals without removing them;
- stable high-belief claims do not dominate attention queues merely because they are important;
- claim payload fields standardize at least `claim_layer`, `identification_strength`, and `influence_role`;
- reports can state when a claim has high influence but unresolved uncertainty.

### Phase 4 - modality and boundary integration

Entry point: a project-level boundary/lens map surface.

Definition of done:

- missing modality reasons can be generated from declared project boundaries;
- attention can recommend "seek orthogonal modality" instead of only "review more evidence";
- at least one pilot project, initially MM30, demonstrates the workflow.

## Evaluation protocol

The first pilot should compare current attention against reason-coded attention on one project.
MM30 is a good stress test because it has heterogeneous modalities, many hypotheses, and known risks of overclaiming causal mechanisms from observational expression data.

Minimal comparison:

1. Generate `N=20` entities from the current `graph attention-sample`.
2. Generate `N=20` entities from reason-coded attention after Phase 1.5 or Phase 2.
3. Blind-label each entity for actionability before revealing the source sampler.
4. Use a simple rubric: clear next action, evidence relevance, uncertainty reason clarity, and expected decision impact.
5. Report paired or bootstrap uncertainty rather than a binary win/loss.

Phase 1 alone can evaluate reason-label clarity but cannot evaluate reason-coded sampling quality, because it does not change candidate ranking or sampling.
If the bootstrap interval for the overall rubric difference straddles zero, the pilot should pre-commit to a second cycle rather than treating the first cycle as directional evidence.

For the first MM30 pilot, store the comparison artifact in the upstream meta-project as `meta/doc/interpretations/YYYY-MM-DD-reason-coded-attention-mm30-pilot.md`, with links to a mirrored MM30-local note under `doc/interpretations/` and the sampled entity list.
The upstream meta-project owns the benchmark interpretation because it is evidence about the Science framework.
Any conclusion from this pilot is conditioned on the MM30 graph state and should be treated as stress-test evidence, not a project-independent benchmark.

This is not a final benchmark.
It is a guard against concluding that reason-coded attention is better merely because it sounds more principled.

## Open questions

- Which reason codes should remain derived-only, reviewed-only, or both?
- How should `belief_weight` be computed without pretending to have a calibrated Bayesian engine?
- Should `influence_weight` be authored, derived from synthesis role, or reviewed during report generation?
- Beyond expiration dates, how should projects prevent option value from becoming a backdoor for arbitrary pet hypotheses?
