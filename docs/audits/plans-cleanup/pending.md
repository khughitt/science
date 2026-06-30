# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `6`

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

## entity-organization-and-naming-implementation-plan3

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-03-entity-organization-and-naming-implementation-plan3.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until v2-to-v3 migration cutover facts and guide intent are checkpointed in durable docs
    - `docs/plans/2026-06-03-entity-organization-and-naming-implementation-plan3.md`
- remaining_gaps:
  - Planned docs/entity-layout-migration-guide.md is not present in durable docs.
  - The migration command still exists while later remove-v3-migration plans propose deleting it.
  - No durable checkpoint summarizing pilot/cutover outcome was found outside plans.

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
  - M1 is implemented, but M2 static operationalization/coverage validation is not present.
  - No operationalized_by schema/check or manifest adapter was found.
  - Decision-review path and broader M3 rubric/backstop remain design-level.
  - Durable user-guide coverage for attention-rank/review workflow is thin.

## local-kind-layout-migration

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-05-local-kind-layout-migration-design.md`
  - `docs/plans/2026-06-05-local-kind-layout-migration-implementation.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until local entity_kinds migration, status override, and skip-warn behavior are checkpointed in durable docs
    - `docs/plans/2026-06-05-local-kind-layout-migration-design.md`
    - `docs/plans/2026-06-05-local-kind-layout-migration-implementation.md`
- remaining_gaps:
  - Durable docs do not clearly document local profile entity_kinds layout/status overrides, migration behavior, or the fact source entity CLI creation remains built-in-only.
  - docs/user-guide/entities.md still says the CLI creates only built-in Markdown path-policy kinds.

## m1-epistemic-drift-detection

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-04-m1-epistemic-drift-detection-implementation.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until open-question-debt, attention-rank, and artifact-required review behavior are durable user-guide content
    - `docs/plans/2026-06-04-m1-epistemic-drift-detection-implementation.md`
- remaining_gaps:
  - M1 behavior is implemented and tested, but durable user-facing docs outside the command/skill source do not explain open_question_debt, graph attention-rank, or the artifact-required review contract.

## migration-robustness

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-06-migration-robustness-design.md`
  - `docs/plans/2026-06-06-migration-robustness-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until current migration report contract and blocking/warning model are checkpointed in durable docs
    - `docs/plans/2026-06-06-migration-robustness-design.md`
    - `docs/plans/2026-06-06-migration-robustness-plan.md`
- remaining_gaps:
  - No durable migration guide/checkpoint was found that records the current dry-run report contract, structural-vs-prose blocking model, and skip+warn manifest behavior outside these plans and tests.
