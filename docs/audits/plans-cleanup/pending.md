# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `8`

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

## multi-project-sync

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-03-23-multi-project-sync-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until sync registry/federation architecture is checkpointed
    - `docs/plans/2026-03-23-multi-project-sync-design.md`
- remaining_gaps:
  - No compact durable architecture note was found that explains the registry/config/state file contract and how it relates to newer peers/federation and commons/shared-store concepts.
  - The March design's cross-project profile vocabulary evolved from cross-project to shared/peers/commons surfaces, so deleting now would leave design rationale scattered across command docs and code.

## ontology-consumption

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-03-24-ontology-consumption-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until ontology catalog contract and stale docs/specs reference are migrated
    - `docs/plans/2026-03-24-ontology-consumption-design.md`
- remaining_gaps:
  - Active durable process docs still point at a nonexistent docs/specs path for this design example.
  - The implementation grew beyond biolink into multiple catalogs and a broader domain-adding process; a short durable migration note should explain the current ontology/catalog contract before deleting the original design.

## paper-model

- status: `unclear`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-04-05-paper-model-design.md`
  - `docs/plans/2026-04-05-paper-model.md`
- pending_actions:
  - `deferred`: review status unclear; reconcile with active companion project-model thread before cleanup
    - `docs/plans/2026-04-05-paper-model-design.md`
    - `docs/plans/2026-04-05-paper-model.md`
- remaining_gaps:
  - Reconcile this thread together with docs/plans/2026-04-05-project-model-design.md before deciding whether to delete, move both to historical, or migrate a durable paper/manuscript model note.
  - Confirm whether the originally planned graph store operations and CLI commands still exist or were replaced by entity source files and interpret-results workflow.

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

