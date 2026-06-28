# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `30`

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

## dataset-adapter-expansion

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-04-17-dataset-adapter-expansion-design.md`
- pending_actions:
  - `deferred`: review status incomplete; adapter list is partially implemented and explicitly demand-gated
    - `docs/plans/2026-04-17-dataset-adapter-expansion-design.md`
- remaining_gaps:
  - Decide whether the remaining adapter backlog should be refiled as current tasks or retired as demand-gated ideas.
  - If retained, summarize adapter source priorities in durable dataset discovery docs instead of leaving an active plan as the only list.

## dataset-entity-lifecycle

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md`
  - `docs/plans/2026-04-19-dataset-entity-lifecycle.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until dataset lifecycle contract is migrated to durable docs
    - `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md`
    - `docs/plans/2026-04-19-dataset-entity-lifecycle.md`
- remaining_gaps:
  - Migrate the useful dataset lifecycle contract into durable user-guide/reference docs before removing the active plan.
  - Normalize stale docs/specs references while this remains a pending architectural source.

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

## general-graph-api-visualization

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-04-12-general-graph-api-visualization-design.md`
  - `docs/plans/2026-04-12-general-graph-api-visualization.md`
- pending_actions:
  - `deferred`: review status incomplete; science-side graph export exists but cross-repo dashboard adoption was not verified
    - `docs/plans/2026-04-12-general-graph-api-visualization-design.md`
    - `docs/plans/2026-04-12-general-graph-api-visualization.md`
- remaining_gaps:
  - Verify whether the dashboard route consumed this contract or whether only the science-side export landed.
  - Decide whether a small durable graph-export contract doc is needed before deleting the implementation plan.

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

## knowledge-gaps

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-04-19-knowledge-gaps-design.md`
  - `docs/plans/2026-04-19-knowledge-gaps.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until legacy topic-gap semantics move to durable big-picture docs
    - `docs/plans/2026-04-19-knowledge-gaps-design.md`
    - `docs/plans/2026-04-19-knowledge-gaps.md`
- remaining_gaps:
  - Migrate the stable user-facing contract for legacy topic-coverage gaps and aspect integration into big-picture user or command docs before deleting.

## manuscript-paper-rename

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-04-19-manuscript-paper-rename-design.md`
  - `docs/plans/2026-04-19-manuscript-paper-rename.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; transition-window removal guidance and canonical bibkey rules still need durable docs
    - `docs/plans/2026-04-19-manuscript-paper-rename-design.md`
    - `docs/plans/2026-04-19-manuscript-paper-rename.md`
- remaining_gaps:
  - Migrate transition-window removal criteria and the canonical bibkey rule into durable user or convention docs before deleting.

## multi-backend-entity-resolver

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-04-20-multi-backend-entity-resolver-design.md`
  - `docs/plans/2026-04-20-multi-backend-entity-resolver.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until model/adapter contract is durable outside active plans
    - `docs/plans/2026-04-20-multi-backend-entity-resolver-design.md`
    - `docs/plans/2026-04-20-multi-backend-entity-resolver.md`
- remaining_gaps:
  - Migrate the stable model/adapter contract into durable documentation before deleting the design from active plans.

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

## open-ended-kinds-and-catalog-registration

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-04-21-open-ended-kinds-and-catalog-registration-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until open-ended kind semantics and catalog registration are durable docs
    - `docs/plans/2026-04-21-open-ended-kinds-and-catalog-registration-design.md`
- remaining_gaps:
  - The open-ended kind contract and catalog registration semantics are not yet summarized in durable user/convention docs.
  - Later topic-deprecation and unified-reference docs still depend on this design for rationale.

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

## project-big-picture

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-04-18-project-big-picture-design.md`
  - `docs/plans/2026-04-18-project-big-picture.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until full big-picture semantics move to durable docs
    - `docs/plans/2026-04-18-project-big-picture-design.md`
    - `docs/plans/2026-04-18-project-big-picture.md`
- remaining_gaps:
  - Create or migrate a durable big-picture user-guide/contract note, or update the command to stop depending on an implementation plan for semantics.
  - Fix stale docs/specs references while the thread remains pending.

## project-model

- status: `unclear`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-04-05-project-model-design.md`
  - `docs/plans/2026-04-05-project-model.md`
- pending_actions:
  - `deferred`: review status unclear; reconcile with companion paper-model and later entity/epistemic model docs before cleanup
    - `docs/plans/2026-04-05-project-model-design.md`
    - `docs/plans/2026-04-05-project-model.md`
- remaining_gaps:
  - Reconcile project-model and paper-model together before moving or deleting either thread.
  - Confirm which parts of the broad entity taxonomy are now durable user-guide contract versus superseded by later epistemic-data-model and dataset lifecycle work.

## source-entity-cli

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-04-28-source-entity-cli-design.md`
  - `docs/plans/2026-04-28-source-entity-cli-implementation.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; source-authored entity CLI shipped but needs compact durable user/process docs before deletion
    - `docs/plans/2026-04-28-source-entity-cli-design.md`
    - `docs/plans/2026-04-28-source-entity-cli-implementation.md`
- remaining_gaps:
  - Migrate the stable source-authored entity CLI contract, path policy, and graph-vs-source write boundary into durable user or process docs before deleting the plan thread.
  - Reconcile later entity-consolidation changes with this older MVP design so docs describe the current expanded entity set rather than only the original question/hypothesis/discussion/interpretation MVP.

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

## verdict-tokens-and-atomic-decomposition

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-04-19-verdict-tokens-and-atomic-decomposition-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; verdict token and claim-decomposition contract still needs durable user/convention docs
    - `docs/plans/2026-04-19-verdict-tokens-and-atomic-decomposition-design.md`
- remaining_gaps:
  - The verdict subsystem still lacks a compact durable user-guide or convention page; code and templates cite the old spec-level concepts directly.

