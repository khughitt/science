# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `5`

## distill-import

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-03-04-distill-import-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until distill/import user guidance is migrated
    - `docs/plans/2026-03-04-distill-import-design.md`
- remaining_gaps:
  - No durable user-guide page or command-map entry documents when to use science distill or graph import.
  - The plan's examples and manifest contract should be migrated before deleting the plan.

## inquiry-workflow

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-03-06-inquiry-workflow-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until current inquiry architecture is checkpointed
    - `docs/plans/2026-03-06-inquiry-workflow-design.md`
- remaining_gaps:
  - Current architecture diverges from the March plan: docs use entities/inquiries-style authored profiles and compiled views; the old plan's doc/inquiries graph-canonical rendering model is stale.
  - No single durable architecture note records the current inquiry model, old interactive RDF path, authored profile compiler, and validation boundaries.

## phase3-completion

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-03-07-phase3-completion-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until phase-gate closure context is checkpointed
    - `docs/plans/2026-03-07-phase3-completion-design.md`
- remaining_gaps:
  - The current tree no longer contains the Phase 3 evidence README, validation JSON/log bundle, biomedical starter profile, or docs/plan.md closure note.
  - Without a migration checkpoint, deleting this plan would leave Phase 3 closure context mostly in git history plus the snapshot files.

## phase4b-causal-dag

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-03-07-phase4b-causal-dag-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until causal-inquiry rationale and stale references are migrated
    - `docs/plans/2026-03-07-phase4b-causal-dag-design.md`
- remaining_gaps:
  - Active docs still reference docs/specs/2026-03-07-phase4b-causal-dag-design.md in places, while the actual file is under docs/plans/.
  - Current CLI differs from the plan: inquiry init uses --profile causal, not --type causal; direct graph mutators such as set-estimand/add-node/add-edge are retired source-editing bridges.
  - No compact durable causal-inquiry rationale doc found outside the old plan and skill docs.

## phase4c-operationalization

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-03-07-phase4c-operationalization-design.md`
- pending_actions:
  - `deferred`: review status incomplete; command-doc and CLI mismatch needs triage
    - `docs/plans/2026-03-07-phase4c-operationalization-design.md`
- remaining_gaps:
  - CLI and command docs appear inconsistent: find-datasets instructs science datasets search, but current CLI exposes science dataset catalog/entity lifecycle commands.
  - The March plan's Frictionless dependency and datasets validate/check-coverage CLI shape were not found as originally designed.
  - The thread combines adapter search, dataset entity lifecycle, datapackage validation, and pipeline guidance, which now live in separate evolved systems.

