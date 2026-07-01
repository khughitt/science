# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `2`

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

## epistemic-drift-detection

- status: `incomplete`
- recommended_action: `keep active`
- actions: `deferred`
- files:
  - `docs/plans/2026-06-04-epistemic-drift-detection-design.md`
- pending_actions:
  - `deferred`: review status incomplete; M1 is implemented but M2/M3 operationalization coverage and decision-review scope remain active triage
    - `docs/plans/2026-06-04-epistemic-drift-detection-design.md`
- remaining_gaps:
  - M2 static operationalization and coverage validation are not present.
  - No operationalized_by schema/check or manifest adapter was found.
  - Decision-review path and broader M3 rubric/backstop remain design-level.
