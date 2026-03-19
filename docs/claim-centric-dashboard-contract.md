# Claim-Centric Dashboard Contract

This document defines the canonical data contract for dashboard-facing uncertainty summaries in `science`.
It is the summary-layer companion to [`claim-and-evidence-model.md`](./claim-and-evidence-model.md).

The purpose of this contract is simple:

- the graph store computes epistemic summaries
- CLI, notebooks, reports, and migration tools consume those summaries
- presentation layers do not invent their own uncertainty semantics

## Summary Units

The dashboard contract currently defines six summary units:

- `claim_summary`
- `neighborhood_summary`
- `evidence_mix_summary`
- `question_summary`
- `inquiry_summary`
- `project_summary`

`claim_summary` is the primary unit already exposed in `graph dashboard-summary`.
`neighborhood_summary` is the next required unit for local uncertainty prioritization.
`evidence_mix_summary` is a reusable logical sub-summary that may be embedded in larger outputs rather than always emitted on its own.
`question_summary`, `inquiry_summary`, and `project_summary` are the higher-level rollup units that sit above the claim and neighborhood layers.

## Required Dashboard Panels

Any claim-centric dashboard should be able to surface:

- weakly supported claims
- contested claims
- single-source claims
- claims lacking empirical data evidence
- high-uncertainty neighborhoods

The presentation layer may choose the exact visual layout, but the underlying panels should be driven by contract-defined summaries rather than notebook-local heuristics.

## Contract Rules

- The store is the source of truth for belief-state and risk computation.
- Summary outputs must be stable enough for CLI and notebook reuse.
- Fields may be added over time, but existing field meanings should not drift silently.
- Structural fragility must remain distinct from evidential fragility.
- Evidence types must remain distinguishable; empirical, simulation, literature, and benchmark evidence must not be flattened into one bucket.

## `claim_summary`

`claim_summary` is the canonical summary for a single claim-like epistemic object.
It may summarize a `claim`, `relation_claim`, or, in transitional cases, a `hypothesis` that still serves as an aggregate target.

Required fields:

| Field | Meaning |
|---|---|
| `claim` | Canonical URI or identifier for the summarized claim object. |
| `label` | Human-readable label for display. |
| `text` | Primary claim text or fallback descriptive text. |
| `belief_state` | Derived top-level state such as `speculative`, `fragile`, `supported`, `well_supported`, or `contested`. |
| `support_count` | Count of distinct supporting evidence items after deduplication. |
| `dispute_count` | Count of distinct disputing evidence items after deduplication. |
| `source_count` | Count of distinct provenance sources contributing to support or dispute. |
| `evidence_types` | Explicitly observed evidence types contributing to the claim summary. |
| `has_empirical_data` | Whether the claim currently has empirical data support in its evidence mix. |
| `signals` | Derived risk or interpretation flags such as `contested`, `single_source`, or `no_empirical_data`. |
| `risk_score` | Derived numeric prioritization score for the claim itself. |

Current interpretation rules:

- `belief_state` is claim-local.
- `risk_score` is claim-local.
- `signals` should be explainable from support/dispute structure and evidence composition.
- `has_empirical_data` should currently become `true` when the observed evidence mix includes `empirical_data_evidence` or `benchmark_evidence`.

## `evidence_mix_summary`

`evidence_mix_summary` describes the evidential composition behind a claim or neighborhood.
It may be emitted separately or embedded inside larger summaries.

Required fields:

| Field | Meaning |
|---|---|
| `evidence_types` | Distinct evidence types observed in the underlying support/dispute set. |
| `has_empirical_data` | Whether empirical data evidence is present. |
| `support_count` | Supporting evidence-item count represented in the mix. |
| `dispute_count` | Disputing evidence-item count represented in the mix. |
| `source_count` | Distinct provenance-source count represented in the mix. |

This unit exists so that higher-level summaries can reuse the same semantics without restating them ad hoc.

## `question_summary`

`question_summary` is the canonical rollup for a research question.
It should summarize the claims that directly address the question and the local neighborhoods that make that question more or less urgent.

Required fields:

| Field | Meaning |
|---|---|
| `question` | Canonical URI or identifier for the summarized question. |
| `label` | Human-readable label for display. |
| `text` | Primary question text or fallback descriptive text. |
| `claim_count` | Count of claims directly addressing the question. |
| `neighborhood_count` | Count of claim neighborhoods contributing to the rollup. |
| `avg_risk_score` | Average claim-local risk across the addressed claims and neighborhoods. |
| `contested_claim_count` | Count of addressed claims whose support/dispute mix is contested. |
| `single_source_claim_count` | Count of addressed claims supported by only one source. |
| `no_empirical_claim_count` | Count of addressed claims lacking empirical data evidence. |
| `priority_score` | Derived question-level prioritization score. |

Required interpretation rules:

- `question_summary` rolls up claims that directly address the question.
- neighborhood metrics derive from already-computed claim neighborhoods rather than a separate question-local graph walk.
- `priority_score` is a question-level prioritization metric, not a claim-level belief state.
- question summaries should remain explainable in terms of the underlying claim summaries and neighborhood summaries.

First-pass profile constraints:

- `question_summary` is primarily a `research`-profile output.
- software-profile projects may eventually expose a lighter question layer, but they should not be forced into research-style question rollups in this first pass.

## `inquiry_summary`

`inquiry_summary` is the canonical rollup for an inquiry.
It should summarize the claims explicitly attached to inquiry edges plus claims directly targeted by the inquiry.

Required fields:

| Field | Meaning |
|---|---|
| `inquiry` | Canonical URI or identifier for the summarized inquiry. |
| `label` | Human-readable label for display. |
| `text` | Primary inquiry text or fallback descriptive text. |
| `inquiry_type` | Inquiry category such as general or causal. |
| `status` | Inquiry lifecycle status. |
| `claim_count` | Count of claims contributing to the inquiry rollup. |
| `backed_claim_count` | Count of claims concretely referenced by inquiry structure. |
| `avg_risk_score` | Average claim-local risk across the inquiry-linked claims. |
| `contested_claim_count` | Count of inquiry-linked claims whose support/dispute mix is contested. |
| `single_source_claim_count` | Count of inquiry-linked claims supported by only one source. |
| `no_empirical_claim_count` | Count of inquiry-linked claims lacking empirical data evidence. |
| `priority_score` | Derived inquiry-level prioritization score. |

Required interpretation rules:

- `inquiry_summary` rolls up claims explicitly attached to inquiry edges plus claims directly targeted by the inquiry.
- `backed_claim_count` counts claims concretely referenced by inquiry structure, not inferred topic overlap.
- inquiries with no explicit claim backing should remain visible as weakly grounded rather than being silently omitted.
- `priority_score` is an inquiry-level prioritization metric, not a claim-level belief state.

First-pass profile constraints:

- `inquiry_summary` is primarily a `research`-profile output.
- software-profile projects may use inquiry-style structures later, but the first-pass contract should not assume they exist.

## `project_summary`

`project_summary` is the canonical rollup for a research project.
It should summarize the highest-level reasoning state of the project from its questions, inquiries, claims, and neighborhoods.

Required fields:

| Field | Meaning |
|---|---|
| `project` | Canonical project URI or identifier. |
| `profile` | Project profile, currently expected to be `research` for this first-pass contract. |
| `question_count` | Count of summarized questions. |
| `inquiry_count` | Count of summarized inquiries. |
| `claim_count` | Count of summarized claims. |
| `high_risk_neighborhood_count` | Count of neighborhoods whose risk crosses the high-risk threshold. |
| `avg_risk_score` | Average risk across the project-level rollup. |
| `contested_claim_count` | Count of contested claims in the project rollup. |
| `single_source_claim_count` | Count of single-source claims in the project rollup. |
| `no_empirical_claim_count` | Count of claims lacking empirical data evidence. |
| `priority_score` | Derived project-level prioritization score. |

Required interpretation rules:

- `project_summary` is a rollup over question, inquiry, claim, and neighborhood summaries.
- `priority_score` is a project-level prioritization metric, not a claim-level belief state.
- project summaries should stay explainable in terms of the lower-level summary units.

First-pass profile constraints:

- this first pass is only defined for `research` projects.
- if `profile != research`, the command should fail clearly or emit a minimal unsupported message; do not invent a fake research rollup.
- software-profile projects may get a lighter overlay later, but that is out of scope for this contract revision.

## `neighborhood_summary`

`neighborhood_summary` is the canonical local-prioritization unit.
It summarizes a claim-centered local region of the graph and should help users find fragile or contested clusters rather than only isolated weak claims.

The first-pass neighborhood model should be claim-centered:

- each neighborhood is centered on a claim-like object
- nearby claims are discovered through graph-native claim links
- question, inquiry, and entity locality views should later derive from claim neighborhoods rather than replace them

Required fields:

| Field | Meaning |
|---|---|
| `center_claim` | Canonical URI or identifier for the neighborhood center. |
| `label` | Human-readable label for the center claim. |
| `text` | Primary center-claim text or fallback descriptive text. |
| `neighbor_claim_count` | Number of other summarized claim objects in the local neighborhood. |
| `avg_risk_score` | Average claim-local risk across the neighborhood, including the center. |
| `contested_count` | Count of claims in the neighborhood whose `belief_state` is `contested` or whose signals include `contested`. |
| `single_source_count` | Count of claims in the neighborhood marked `single_source`. |
| `no_empirical_count` | Count of claims in the neighborhood lacking empirical data support. |
| `structural_fragility` | Separate structural indicator such as `isolated`, `sparse`, or `connected`. |
| `neighborhood_risk` | Derived numeric prioritization score for the neighborhood as a local cluster. |

Required interpretation rules:

- `neighborhood_risk` is not the same thing as claim-local `risk_score`.
- structural isolation or sparsity must remain visible as a separate dimension.
- evidentially contested local clusters should outrank isolated but well-supported regions.

## First-Pass Contract Boundaries

The first contract version does not require:

- full probabilistic updates
- mathematically calibrated Bayesian posteriors
- notebook-specific rendering fields

The `question_summary`, `inquiry_summary`, and `project_summary` sections above are the first-pass higher-level summary contract.
Additional higher-level summary types may be added later, but this contract should stay focused on stable claim, neighborhood, and first-pass rollup summaries.

## What The Dashboard Must Not Do

The dashboard must not:

- treat raw `sci:confidence` as the primary signal of uncertainty
- infer claim state through notebook-local string scanning
- collapse empirical, simulation, literature, and benchmark evidence into one undifferentiated bucket
- conflate structural sparsity with evidential dispute or evidential weakness

## Versioning Guidance

This contract should evolve conservatively.

- Adding fields is acceptable when older fields retain their meaning.
- Renaming or redefining fields should require an explicit contract update.
- When CLI output changes materially, this document should change first or in the same commit.

## Relationship To The Roadmap

This document is the Phase 2 contract artifact described in [`2026-03-18-claim-centric-reasoning-roadmap.md`](./plans/2026-03-18-claim-centric-reasoning-roadmap.md).
It should remain the canonical dashboard-summary contract even as later phases add:

- richer evidence-item modeling
- neighborhood diffusion refinements
- inquiry and project summaries
- action-oriented next-step outputs
