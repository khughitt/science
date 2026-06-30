# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `26`

## bundle-belief-rollup

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-11-bundle-belief-rollup-design.md`
  - `docs/plans/2026-06-11-bundle-belief-rollup-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until bundle belief semantics, composition_rule, membership-role gating, and snapshot fields are documented
    - `docs/plans/2026-06-11-bundle-belief-rollup-design.md`
    - `docs/plans/2026-06-11-bundle-belief-rollup-plan.md`
- remaining_gaps:
  - Low-level durable contract is not fully migrated: model/graph code still cites docs/plans/2026-06-11-bundle-belief-rollup-design.md.
  - Original member-enumeration semantics are partially superseded by membership_role/core_members gating, so the active plan is no longer reliable as current truth.
  - No docs/proposition-and-evidence-model.md exists despite the plan claiming the canonical proposition model should be updated.

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

## data-driven-discovery-improvements

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-06-10-data-driven-discovery-improvements.md`
- pending_actions:
  - `deferred`: review status incomplete; retain umbrella until open evidence-tier, robustness, reproducibility, provenance, and bias-memory items are split or re-homed
    - `docs/plans/2026-06-10-data-driven-discovery-improvements.md`
- remaining_gaps:
  - A1 evidence-tier ladder and A2 cross-modality corroboration remain unimplemented despite substrate now existing.
  - B4 adaptive pre-registration, C1/C2 robustness/model-comparison, D1/D2 reproducibility seed/rerun gates, E1/E2 provenance/faithfulness, and F1/F2 memory/bias additions are not closed by this thread.
  - The umbrella mixes shipped, stale-gated, and speculative items in one file and should be split or re-homed before archival.

## dataset-evidence-flow

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-08-dataset-evidence-flow-design.md`
  - `docs/plans/2026-06-08-dataset-evidence-flow-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until evidence-line dataset_usage, belief_eligible staging, overlap curation, and B2 independence behavior are documented
    - `docs/plans/2026-06-08-dataset-evidence-flow-design.md`
    - `docs/plans/2026-06-08-dataset-evidence-flow-plan.md`
- remaining_gaps:
  - MM30 task-to-dataset resolution table and population of staged evidence-lines are out of this repo and not verified here.
  - Root plans still contain stale/transition wording, especially doc/datasets versus current entities/datasets/data dataset homes after adapter layout work.
  - Durable user docs mention paper dataset_usage but do not fully document evidence-line dataset_usage, belief_eligible staging, overlap curation, and B2 commitment versus candidate behavior.

## dataset-sub-cohort-lineage

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-13-dataset-sub-cohort-lineage-design.md`
  - `docs/plans/2026-06-13-dataset-sub-cohort-lineage-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until sub-cohort lineage and B2 ancestor-vs-sibling semantics are documented
    - `docs/plans/2026-06-13-dataset-sub-cohort-lineage-design.md`
    - `docs/plans/2026-06-13-dataset-sub-cohort-lineage-plan.md`
- remaining_gaps:
  - Migrate sub-cohort semantics and B2 ancestor-vs-sibling behavior into durable docs before deleting the active plan pair.

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

## epistemic-data-model

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-08-epistemic-data-model-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until post-implementation epistemic model contract is checkpointed in durable docs
    - `docs/plans/2026-06-08-epistemic-data-model-design.md`
- remaining_gaps:
  - The umbrella's implementation facts are spread across code/tests and partial user docs; no durable single checkpoint captures the post-implementation epistemic model contract.
  - MM30 corpus migration remains separate from the framework implementation.
  - The still-active epistemic-drift-detection design is not superseded; operationalized_by/claims_scope M2/M3 checks remain outside this umbrella's implemented surface.

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

## epistemic-edges

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-08-epistemic-edges-design.md`
  - `docs/plans/2026-06-08-epistemic-edges-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until relational proposition, workbench compile/check, staged evidence, and derived_edge_status behavior are documented
    - `docs/plans/2026-06-08-epistemic-edges-design.md`
    - `docs/plans/2026-06-08-epistemic-edges-plan.md`
- remaining_gaps:
  - MM30 legacy edges.yaml corpus migration is not present in this repo review and remains a downstream migration task.
  - Durable docs do not fully explain relational proposition fields, workbench compile/check, staged empirical evidence, or derived_edge_status; much of the contract lives in plans/tests.
  - The plan header still says held until v3/planning only, which is stale now that v3 and framework implementation have landed.

## infer-schema-scaffold

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-14-infer-schema-scaffold-design.md`
  - `docs/plans/2026-06-14-infer-schema-scaffold-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until infer-schema command contract and safety rules are documented
    - `docs/plans/2026-06-14-infer-schema-scaffold-design.md`
    - `docs/plans/2026-06-14-infer-schema-scaffold-plan.md`
- remaining_gaps:
  - Migrate the command contract and safety rules into durable docs before deleting the plan pair.

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

## patch-contract-keystone

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-14-patch-contract-keystone-design.md`
  - `docs/plans/2026-06-14-patch-contract-keystone-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until patch membership contract, predicates, and CLI diagnostics are documented
    - `docs/plans/2026-06-14-patch-contract-keystone-design.md`
    - `docs/plans/2026-06-14-patch-contract-keystone-plan.md`
- remaining_gaps:
  - Original design deferrals remain: PatchSnapshot, remote/commons scopes, maturity L0-L4, and latent/ontology glue.
  - Durable docs mention patch-definition and inquiry profiles but do not capture the full patch membership contract, predicates, or CLI diagnostics.

## patchwork-kernel-architecture

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-06-14-patchwork-kernel-architecture-design.md`
- pending_actions:
  - `deferred`: review status incomplete; retain umbrella until shipped invariants and aspirational patchwork backlog are separated
    - `docs/plans/2026-06-14-patchwork-kernel-architecture-design.md`
- remaining_gaps:
  - Large parts of the overview remain target-state rather than implementation reality.
  - Separate shipped invariants from aspirational subsystem backlog before cleanup.

## qa-check-library

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-13-qa-check-library-design.md`
  - `docs/plans/2026-06-13-qa-check-library-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until QA aspect/program semantics replace stale modality-pack docs
    - `docs/plans/2026-06-13-qa-check-library-design.md`
    - `docs/plans/2026-06-13-qa-check-library-plan.md`
- remaining_gaps:
  - docs/conventions/pipeline-qa-checkpoints.md still has stale pre-refactor wording about modality packs/packs:[scrna] and links back to this plan for details.
  - Migrate locked QA-library semantics before deleting the plan files.

## substrate-3b-entities-retirement-apply

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-08-substrate-3b-entities-retirement-apply-design.md`
  - `docs/plans/2026-06-08-substrate-3b-entities-retirement-apply-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until aggregate retirement workflow, v3 gate, crash recovery, and Phase 4 expanded scope are checkpointed
    - `docs/plans/2026-06-08-substrate-3b-entities-retirement-apply-design.md`
    - `docs/plans/2026-06-08-substrate-3b-entities-retirement-apply-implementation-plan.md`
- remaining_gaps:
  - Durable docs do not yet document the triage-aggregate retirement workflow, flags, v3 gate, crash-recovery marker, or current Phase 4 expanded scope.
  - The design's terms.yaml-untouched firewall is stale after later Phase 4a work.

## substrate-3c-decision-log-promotion

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-08-substrate-3c-decision-log-promotion-design.md`
  - `docs/plans/2026-06-08-substrate-3c-decision-log-promotion-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until decision owner promotion and generated decision-view behavior are documented
    - `docs/plans/2026-06-08-substrate-3c-decision-log-promotion-design.md`
    - `docs/plans/2026-06-08-substrate-3c-decision-log-promotion-implementation-plan.md`
- remaining_gaps:
  - No durable user or migration doc explains decision owner shape, --promote-decisions, generate-decisions, generated-view semantics, or the opaque-body parser contract.
  - The original constraint that decision stays out of the graph core registry is superseded by later kind-descriptor work; current core profile registers decision directly.

## substrate-4a-terms-coined-promotion

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-08-substrate-4a-terms-coined-promotion-design.md`
  - `docs/plans/2026-06-08-substrate-4a-terms-coined-promotion-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until terms.yaml promotion and aggregate retirement phase rationale are checkpointed
    - `docs/plans/2026-06-08-substrate-4a-terms-coined-promotion-design.md`
    - `docs/plans/2026-06-08-substrate-4a-terms-coined-promotion-implementation-plan.md`
- remaining_gaps:
  - No durable migration checkpoint records 4a completion and terms.yaml retirement behavior.
  - docs/user-guide/entities.md documents terms.yaml as a lightweight semantic surface but not the promotion executor, --promote-coined retirement path, or historical phase rationale.
  - Live downstream/MM30 migration evidence was not verified in this repo review.

## substrate-4b-bibliography-external-reference

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-08-substrate-4b-bibliography-external-reference-design.md`
  - `docs/plans/2026-06-08-substrate-4b-bibliography-external-reference-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until bibliography external-reference authority and retirement semantics are documented
    - `docs/plans/2026-06-08-substrate-4b-bibliography-external-reference-design.md`
    - `docs/plans/2026-06-08-substrate-4b-bibliography-external-reference-implementation-plan.md`
- remaining_gaps:
  - No durable migration checkpoint records the bibliography external-reference authority and retirement semantics as completed.
  - docs/user-guide/entities.md mentions bib/curie-ref adapters and cite/paper references but does not fully document that bib rows are external-reference nodes rather than owners, or how --retire-external-refs retires aggregate stubs.
  - Bib-vs-commons precedence is plausible from identity_table-before-commons loading, but no dedicated precedence test was identified.

## substrate-4c-ambiguous-adjudication

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-09-substrate-4c-ambiguous-adjudication-design.md`
  - `docs/plans/2026-06-09-substrate-4c-ambiguous-adjudication-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until CURIE external refs, triage buckets, migration semantics, and v3 aggregate-retirement gate are documented
    - `docs/plans/2026-06-09-substrate-4c-ambiguous-adjudication-design.md`
    - `docs/plans/2026-06-09-substrate-4c-ambiguous-adjudication-implementation-plan.md`
- remaining_gaps:
  - No code gap found for the 4c scope.
  - Durable docs do not yet capture external_refs.yaml schema, CURIE migration semantics, aggregate triage bucket meanings, method/topic slug promotion consequences, question-deferred handling, or the layout_version >= 3 aggregate-retirement gate.
  - The implementation plan is stale as operational guidance because later adapter-policy work moved AggregateRowMeta and deferral behavior behind adapter hooks.

## substrate-dataset-reconciliation-2c

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-07-substrate-dataset-reconciliation-2c-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until DCAT distribution materialization and transitional collision WARN semantics are documented
    - `docs/plans/2026-06-07-substrate-dataset-reconciliation-2c-implementation-plan.md`
- remaining_gaps:
  - Durable docs mention dataset-vs-runtime datapackage authority but do not explicitly document graph/datasets DCAT distribution materialization or the transitional identity-collision WARN gate.

## substrate-identity-table

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-06-substrate-identity-table-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until strict_identity, non-strict diagnostics, and 2c collision grading semantics are checkpointed in durable docs
    - `docs/plans/2026-06-06-substrate-identity-table-implementation-plan.md`
- remaining_gaps:
  - No non-plan migration checkpoint/ADR records why strict_identity exists, why diagnostics are non-strict, or the later 2c warn-vs-fail grading change.

## substrate-migrator-compiled-model

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-07-substrate-migrator-compiled-model-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until dry-run report, transitional collisions, non-strict compiled-model gate, and malformed-core triage are checkpointed
    - `docs/plans/2026-06-07-substrate-migrator-compiled-model-implementation-plan.md`
- remaining_gaps:
  - No durable migration checkpoint documents the current dry-run report contract, transitional_owner_collisions, non-strict compiled-model gate, and malformed-core triage outside plan/test code.

## substrate-scope-aware-loading

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-07-substrate-scope-aware-loading-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until scoped reference syntax, bare-ref ambiguity, and materialize/audit behavior are durable docs
    - `docs/plans/2026-06-07-substrate-scope-aware-loading-implementation-plan.md`
- remaining_gaps:
  - Durable user docs mention owner scopes generally but do not explain bare-ref ambiguity, scoped reference syntax, or the materialize/audit behavior users see.

## typed-dataset-schema

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-13-typed-dataset-schema-design.md`
  - `docs/plans/2026-06-13-typed-dataset-schema-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until dataset schema profile vocabulary and validate behavior are documented
    - `docs/plans/2026-06-13-typed-dataset-schema-design.md`
    - `docs/plans/2026-06-13-typed-dataset-schema-plan.md`
- remaining_gaps:
  - Add durable documentation for the profile vocabulary, qa: extension boundary, emitted schema, and datasets validate behavior.
