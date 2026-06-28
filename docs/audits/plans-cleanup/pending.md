# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `12`

## b-migration-paper-datasets

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-05-29-b-migration-paper-datasets-design.md`
  - `docs/plans/2026-05-29-b-migration-paper-datasets-plan.md`
- pending_actions:
  - `deferred`: review status incomplete; paper.datasets migration module and CLI are not implemented
    - `docs/plans/2026-05-29-b-migration-paper-datasets-design.md`
    - `docs/plans/2026-05-29-b-migration-paper-datasets-plan.md`
- remaining_gaps:
  - Implement paper_dataset_migration.py pure migration module.
  - Expose the migrate-paper-datasets CLI command.
  - Add migration tests and mark the design implemented.

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

## bio-dataset-influence-provenance

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md`
- pending_actions:
  - `deferred`: review status incomplete; B1 is implemented but B-migration and B2 remain active follow-up work
    - `docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md`
- remaining_gaps:
  - B-migration for paper.datasets transition
  - B2 candidate and committed independence signal derivation

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

## conventions-audit-p1-rollout

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-04-25-conventions-audit-p1-rollout.md`
- pending_actions:
  - `deferred`: review status incomplete; open downstream follow-ons and Bucket C design sessions remain tracked here
    - `docs/plans/2026-04-25-conventions-audit-p1-rollout.md`
- remaining_gaps:
  - Confirm which downstream migration follow-ons have since landed, then update or close the remaining checklist items.
  - Schedule or replace the Bucket C design-session tracking with current durable backlog entries before removing this tracker.

## downstream-conventions-migration

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-04-25-downstream-conventions-migration.md`
- pending_actions:
  - `deferred`: review status incomplete; tasks-archive, MAV update, and tracking/report tasks remain open
    - `docs/plans/2026-04-25-downstream-conventions-migration.md`
- remaining_gaps:
  - Verify downstream tasks-archive adoption, managed validate.sh update status, and migration tracking appendix status.
  - Resolve or retarget the Bucket C-dependent descriptor sidecar adoption note.

## topic-deprecation-and-mechanism

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md`
- pending_actions:
  - `deferred`: review status incomplete; topic deprecation remains partially implemented and needs reconciliation with unified references/theme follow-ons
    - `docs/plans/2026-04-22-topic-deprecation-and-mechanism-design.md`
- remaining_gaps:
  - Replace remaining topic-stub remediation guidance in health command docs and skills with semantic triage.
  - Reconcile topic registration and legacy migration-only handling with unified references, theme, and mechanism follow-ons.
  - Decide whether the stable topic-deprecation policy should move into durable docs before this design leaves active plans.

## unified-entity-references

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-04-21-unified-entity-references-design.md`
- pending_actions:
  - `deferred`: review status incomplete; reconcile partial implementation with mechanism/theme/topic follow-ons before cleanup
    - `docs/plans/2026-04-21-unified-entity-references-design.md`
- remaining_gaps:
  - Verify which of the five proposed changes fully landed: cross-kind slug fallback, ontology catalog resolvable instances, terms.yaml convention, tag: classification token, and topic deprecation.
  - Reconcile with mechanism/theme/topic follow-ons before moving or deleting.

