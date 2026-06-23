# Belief Profile CLI Design

**Date:** 2026-06-23
**Status:** Design approved in brainstorming; implementation not started.
**Feedback:** `fb-2026-05-31-009`

## Context

`fb-2026-05-31-009` originally asked for a unified first-class
epistemic/uncertainty attribute across graph entities: a provenance tier plus
derived confidence, uncertainty, contestation, and fragility. Recent Science
epistemic work resolves part of that ask, but also changes the right shape of
the remaining work:

- `meta/entities/hypotheses/0007-working-model.md` makes provenance and
  uncertainty central to the h00 working model.
- `docs/plans/2026-06-08-epistemic-data-model-design.md` consolidates the
  model around propositions, evidence-lines, derived belief, scalar bands,
  EntityClass, and provenance-as-axes.
- `docs/plans/2026-06-08-epistemic-edges-design.md` makes truth-apt graph edges
  relational propositions with derived belief and derived edge-status
  projections.
- `docs/plans/2026-06-17-prose-epistemics-umbrella-design.md` routes prose
  claims through the same proposition/evidence/belief machinery.

The remaining gap is no longer "add one authored provenance tier to every
entity." The remaining gap is a queryable derived profile over the existing
source-of-truth fields: evidence-line type/strength/role/independence, dataset
usage and dataset source class, PROV/source refs, review/freshness state,
bundle rollups, `aggregate_belief`, and existing belief scalar bands when
enabled.

## Decision

Add a read-only CLI surface:

```bash
science belief profile --format json
```

The command emits a stable per-entity epistemic profile. It does not persist new
metadata and does not introduce a new belief engine. The profile is a derived
reading of the current graph.

Initial supported entity kinds:

- `proposition`
- `hypothesis`
- `mechanism`

Default row set:

- Include supported belief-bearing entities that have at least one meaningful
  epistemic input: evidence units, bundle members, authored confidence,
  freshness state, caps, or another signal that makes the row informative.
- Exclude completely empty/speculative rows by default.
- `--all` includes all supported belief-bearing entities, including rows whose
  profile is mostly empty or speculative.

Initial filters:

```bash
science belief profile --label contested
science belief profile --kind proposition
```

`--label` may be repeated. Repeated labels use AND semantics so callers can ask
for intersections such as `--label fragile --label single_source`.

## Row Contract

JSON output should preserve one row per entity:

```json
{
  "entity": "proposition:example",
  "kind": "proposition",
  "label": "Short label or text",
  "belief_state": "fragile",
  "contested": false,
  "epistemic_labels": ["fragile", "single_source", "authored_only"],
  "evidence": {
    "support_count": 1,
    "dispute_count": 0,
    "source_count": 1,
    "evidence_types": ["expert_judgment"],
    "has_empirical_data": false
  },
  "caps": {
    "authored_capped": true,
    "qa_dataset_capped": false,
    "refutation_capped": false
  },
  "freshness_state": "fresh",
  "belief_scalar": null
}
```

When the existing belief scalar feature is enabled, `belief_scalar` includes the
current scalar outputs: massed support/dispute bands, net band when exposed by
the existing engine, robustness, and diagnostic dispute count. When disabled,
`belief_scalar` is `null`; the profile command must not invent a new scalar or
fallback score.

Field semantics:

- `belief_state` is the existing derived ordinal result.
- `contested` is the existing derived contestation flag.
- `epistemic_labels` are categorical readings derived from existing fields.
- `evidence` summarizes the evidence units after the existing collection path.
- `caps` mirrors existing belief caps and ceilings.
- `freshness_state` reads existing materialized freshness state when present.
- `belief_scalar` is a projection of existing scalar output only.

## Initial Label Set

The v1 labels are categorical and directly derivable:

- `speculative`
- `fragile`
- `supported`
- `well_supported`
- `contested`
- `single_source`
- `no_empirical_data`
- `authored_only`
- `literature_only`
- `empirical_data_backed`
- `authored_capped`
- `qa_dataset_capped`
- `refutation_capped`
- `stale`
- `needs_review`

Labels are readings of the graph, not authored truth. The command should avoid
labels that require normalized source-agent provenance that does not yet exist.

Deferred labels:

- `ai_drafted`
- `human_ratified`
- `editorial_only`

These are valid user needs, but they should wait until author/source agent and
review provenance are normalized enough to derive them without guessing.

## Data Flow

1. Load the materialized graph.
2. Enumerate supported belief-bearing entities.
3. For each entity, use the existing bundle-aware belief path.
4. Collect the same evidence units used by the belief engine.
5. Derive categorical labels from belief result, evidence summary, caps, and
   freshness state.
6. Attach scalar bands only when the existing scalar feature is enabled.
7. Apply `--kind`, `--label`, and default-vs-`--all` filtering.
8. Emit table or JSON via the existing query-row output machinery.

No persistent RDF predicates are introduced in v1. No source files are edited by
the command.

## Alternatives Considered

### Materialize RDF predicates first

This would make the profile more graph-native, but it would harden labels before
the contract is proven. It also risks creating another derived-state migration
surface. Rejected for v1.

### Extend `science graph uncertainty`

This would minimize command count, but `graph uncertainty` is a ranked risk
report. The new profile is a reusable per-entity contract, not only a
prioritization view. Rejected for v1.

### Use `science graph audit`

`graph audit` currently means source-reference/materialization audit. Overloading
it with epistemic profile filters would blur graph hygiene with belief reading.
Rejected.

## Non-Goals

- No new authored `EpistemicMetadata` block.
- No single universal `provenance_tier` enum.
- No numeric `confidence_scalar`, `uncertainty_scalar`, or `fragility_score`
  beyond already-enabled belief scalar bands.
- No new belief aggregation path.
- No health or validation gates in v1.
- No RDF materialization in v1.

## Success Criteria

- Researchers can list belief-bearing entities by categorical epistemic profile
  without manually traversing evidence lines.
- The output makes authored-only, literature-only, no-empirical, contested,
  fragile, capped, and stale/needs-review states queryable.
- The command agrees with existing belief and scalar machinery.
- The contract is stable enough to later consider RDF materialization,
  dashboard consumption, or health summaries.

