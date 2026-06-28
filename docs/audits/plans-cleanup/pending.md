# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `6`

## bio-data-architecture-umbrella

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`
- pending_actions:
  - `deferred`: review status incomplete; umbrella still tracks open dbSNP smoke, RG3+ workflows, C4c transcript/protein projection, and D2 work
    - `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`
- remaining_gaps:
  - full dbSNP artifact build/operator smoke
  - RG3+ workflows
  - C4c transcript/protein projection
  - D2 promoted gene-set members

## bio-geneset-type

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-05-26-bio-geneset-type-design.md`
- pending_actions:
  - `deferred`: review status incomplete; D1 collection type is implemented but D2 promoted-member mechanics remain open
    - `docs/plans/2026-05-26-bio-geneset-type-design.md`
- remaining_gaps:
  - D2 promoted bio.geneset.member implementation
  - bio.geneset virtual payload resolution

## bio-identity-and-reference-genome

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md`
- pending_actions:
  - `deferred`: review status incomplete; Pillar C still tracks full dbSNP artifact smoke and C4c transcript/protein projection
    - `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md`
- remaining_gaps:
  - full dbSNP artifact build/operator smoke
  - C4c transcript/protein projection

## bio-reference-graph-design

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-05-31-bio-reference-graph-design.md`
- pending_actions:
  - `deferred`: review status incomplete; RG3 broader graph-member workflows and RG5 non-molecular identity resolvers remain open
    - `docs/plans/2026-05-31-bio-reference-graph-design.md`
- remaining_gaps:
  - RG3 broader graph-member promotion workflows and unpromoted-member B materialization hooks
  - RG5 non-molecular identity resolvers over reference graphs

## c4-variant-identity

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-05-28-c4-variant-identity-design.md`
- pending_actions:
  - `deferred`: review status incomplete; C4 still tracks full dbSNP artifact smoke and transcript/protein projection work
    - `docs/plans/2026-05-28-c4-variant-identity-design.md`
- remaining_gaps:
  - full dbSNP artifact build/operator smoke
  - C4c transcript/protein projection

## c4c-rsid-variant-label

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-05-31-c4c-rsid-variant-label-plan.md`
- pending_actions:
  - `deferred`: review status incomplete; full dbSNP artifact build, lockfile/hash refresh, and real-artifact resolver smoke remain operator-pending
    - `docs/plans/2026-05-31-c4c-rsid-variant-label-plan.md`
- remaining_gaps:
  - full dbSNP archive fetch/build
  - full-source lockfile pinning
  - datapackage hash refresh
  - resolver smoke against the real commons artifact
  - later transcript/protein HGVS projection

