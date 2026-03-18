# Claim-Centric Dashboard Contract

This document defines the canonical data contract for dashboard-facing uncertainty summaries in `science`.
It is the summary-layer companion to [`claim-and-evidence-model.md`](./claim-and-evidence-model.md).

The purpose of this contract is simple:

- the graph store computes epistemic summaries
- CLI, notebooks, reports, and migration tools consume those summaries
- presentation layers do not invent their own uncertainty semantics

## Summary Units

The dashboard contract currently defines three summary units:

- `claim_summary`
- `neighborhood_summary`
- `evidence_mix_summary`

`claim_summary` is the primary unit already exposed in `graph dashboard-summary`.
`neighborhood_summary` is the next required unit for local uncertainty prioritization.
`evidence_mix_summary` is a reusable logical sub-summary that may be embedded in larger outputs rather than always emitted on its own.

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
- inquiry-level or question-level summaries
- notebook-specific rendering fields

Those may be added later, but the first contract should stay focused on stable claim and neighborhood summaries.

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
