# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `79`

## adapter-entity-layout-and-overlay-root

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-21-adapter-entity-layout-and-overlay-root-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until layout-v3 migration deviations and plan citations are checkpointed
    - `docs/plans/2026-06-21-adapter-entity-layout-and-overlay-root-design.md`
- remaining_gaps:
  - Live code/test comments still cite docs/plans/2026-06-21-adapter-entity-layout-and-overlay-root-design.md.
  - The plan includes migration-deviation notes useful as a compact historical checkpoint, but current user-facing layout knowledge is already durable.

## authored-confidence

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-16-authored-confidence-design.md`
  - `docs/plans/2026-06-16-authored-confidence-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until authored-confidence gate and ceiling semantics are documented
    - `docs/plans/2026-06-16-authored-confidence-design.md`
    - `docs/plans/2026-06-16-authored-confidence-plan.md`
- remaining_gaps:
  - Durable user docs only list expert_judgment as an evidence type; they do not explain confidence as a gate, authored-only ceiling, authored_capped, or excluded_authored_confidence.
  - Implementation comments still reference Spec 5/Slice B plan docs as rationale.

## bears-on-multihop-reach

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-22-bears-on-multihop-reach.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until dataset-prioritization reach rationale is checkpointed and later plan citations are repointed
    - `docs/plans/2026-06-22-bears-on-multihop-reach.md`
- remaining_gaps:
  - The behavior is implemented and tested, but the explanatory contract is still mostly in plan files and the code docstring rather than a stable non-plan dataset-prioritize reference.
  - docs/plans/2026-06-24-dataset-reach-authoring-surfaces-design.md still cites plan:2026-06-22-bears-on-multihop-reach, so deleting this plan without a checkpoint or citation repoint would remove context.
  - The parent catalog-datasets thread is already pending a migration checkpoint for dataset prioritization rationale; this small plan should be folded into that checkpoint rather than kept as active work.

## belief-policy-keystone

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-16-belief-policy-keystone-design.md`
  - `docs/plans/2026-06-16-belief-policy-keystone-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until belief policy identity/versioning contract is documented
    - `docs/plans/2026-06-16-belief-policy-keystone-design.md`
    - `docs/plans/2026-06-16-belief-policy-keystone-plan.md`
- remaining_gaps:
  - Durable docs mention belief states and snapshots but not policy identity, versioning, comparability, or how future policy changes affect reproducibility.
  - Plan rationale remains the clearest explanation of the BeliefPolicy boundary versus belief_scalar CONFIG_VERSION.

## belief-profile

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-23-belief-profile-design.md`
  - `docs/plans/2026-06-23-belief-profile-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until belief profile CLI contract is documented outside active plans
    - `docs/plans/2026-06-23-belief-profile-design.md`
    - `docs/plans/2026-06-23-belief-profile-implementation-plan.md`
- remaining_gaps:
  - No durable non-plan documentation was found for the CLI contract, output fields, labels, filters, scalar behavior, or non-goals.
  - The plan files currently carry useful user-facing contract details, so deleting them without a checkpoint would lose the only discovered narrative documentation.

## benchmark-catalog-v1

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-27-benchmark-catalog-v1-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until benchmark metadata/list schema, validation, commons behavior, and CLI contract are documented outside active plans
    - `docs/plans/2026-06-27-benchmark-catalog-v1-implementation-plan.md`
- remaining_gaps:
  - No consolidated durable user-guide/reference page was found for benchmark metadata schema, science benchmark list JSON shape, validation rules, and commons benchmark behavior.
  - Later benchmark opportunities, gaps, and tests plans extend this foundation, so deletion should wait until the durable benchmark checkpoint covers the shared contract.

## benchmark-fallback-diagnostics

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-benchmark-fallback-diagnostics-design.md`
  - `docs/plans/2026-06-28-benchmark-fallback-diagnostics-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until fallback reason diagnostics, concentration warnings, and summary fields are documented outside active plans
    - `docs/plans/2026-06-28-benchmark-fallback-diagnostics-design.md`
    - `docs/plans/2026-06-28-benchmark-fallback-diagnostics-implementation-plan.md`
- remaining_gaps:
  - No durable benchmark report reference doc was found for fallback reason semantics, concentration warnings, JSON fields, or table rendering.
  - The plan remains useful until the benchmark report checkpoint captures fallback diagnostics alongside gaps, calibration, and tests.

## benchmark-fallback-selection

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-benchmark-fallback-selection-design.md`
  - `docs/plans/2026-06-28-benchmark-fallback-selection-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until fallback selection policy, selected reason notes, and quality-tier rotation are documented outside active plans
    - `docs/plans/2026-06-28-benchmark-fallback-selection-design.md`
    - `docs/plans/2026-06-28-benchmark-fallback-selection-implementation-plan.md`
- remaining_gaps:
  - No durable benchmark reference doc was found for fallback selection policy, selected:* diagnostics, quality-tier rotation, or aggregate summary fields.

## benchmark-gap-calibration-batch

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-benchmark-gap-calibration-batch-design.md`
  - `docs/plans/2026-06-28-benchmark-gap-calibration-batch-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until benchmark gap-calibration CLI, aggregate JSON shape, project-label semantics, and commons behavior are documented outside active plans
    - `docs/plans/2026-06-28-benchmark-gap-calibration-batch-design.md`
    - `docs/plans/2026-06-28-benchmark-gap-calibration-batch-implementation-plan.md`
- remaining_gaps:
  - No durable docs were found for benchmark gap-calibration CLI syntax, JSON aggregate shape, table sections, project-label semantics, or commons degradation behavior.

## benchmark-gap-calibration-summary

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-benchmark-gap-calibration-summary-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until benchmark gaps calibration-summary fields and table/JSON contract are documented outside active plans
    - `docs/plans/2026-06-28-benchmark-gap-calibration-summary-implementation-plan.md`
- remaining_gaps:
  - No durable benchmark reference doc was found for calibration-summary fields, definitions, or table/JSON contract.

## benchmark-gap-calibration-v2

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-benchmark-gap-calibration-v2-design.md`
  - `docs/plans/2026-06-28-benchmark-gap-calibration-v2-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until v2 benchmark gap candidate semantics, scoring caveats, evidence fields, and calibration interpretation are documented outside active plans
    - `docs/plans/2026-06-28-benchmark-gap-calibration-v2-design.md`
    - `docs/plans/2026-06-28-benchmark-gap-calibration-v2-implementation-plan.md`
- remaining_gaps:
  - No durable benchmark reference doc was found for the v2 candidate semantics, scoring caveats, evidence fields, or calibration interpretation.

## benchmark-gap-evidence-extraction

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-benchmark-gap-evidence-extraction-design.md`
  - `docs/plans/2026-06-28-benchmark-gap-evidence-extraction-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until benchmark gap evidence-report fields and fallback-only explanations are documented outside active plans
    - `docs/plans/2026-06-28-benchmark-gap-evidence-extraction-design.md`
    - `docs/plans/2026-06-28-benchmark-gap-evidence-extraction-implementation-plan.md`
- remaining_gaps:
  - No durable benchmark reference doc was found for evidence-report fields, interpretation of fallback-only explanations, or how the evidence report relates to calibration output.

## benchmark-gaps

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-benchmark-gaps-design.md`
  - `docs/plans/2026-06-28-benchmark-gaps-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until current benchmark gaps command usage, filters, JSON contract, candidate semantics, fallback semantics, calibration, and evidence reports are documented outside active plans
    - `docs/plans/2026-06-28-benchmark-gaps-design.md`
    - `docs/plans/2026-06-28-benchmark-gaps-implementation-plan.md`
- remaining_gaps:
  - No durable benchmark reference doc was found for benchmark gaps command usage, JSON contract, filters, candidate semantics, fallback semantics, calibration, or evidence reports.
  - The original v1 candidate semantics in this plan are partly stale after calibration v2; durable docs should capture the live v2 contract before deleting.

## benchmark-grounded-model-assessment

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-06-26-benchmark-grounded-model-assessment-design.md`
- pending_actions:
  - `deferred`: review status incomplete; v1 and read-only projections are implemented, but graph edges, formal belief-test authoring, benchmark outcomes, and cross-project outcome analysis remain roadmap items
    - `docs/plans/2026-06-26-benchmark-grounded-model-assessment-design.md`
- remaining_gaps:
  - No formal authored plan_kind: belief-test schema or durable template was found; current science benchmark tests is a read-only projection.
  - No structured benchmark result/outcome model was found that can update propositions or evidence.
  - No graph-aware benchmark-to-belief typed edges were found; v1 related_beliefs remains free text and opportunity/gap matching is report logic, not graph semantics.
  - No cross-project success analysis tying benchmark outcomes to project practices was found; gap calibration summarizes report quality and candidate/fallback behavior rather than benchmark outcome success.
  - No consolidated durable reference page under docs/ describes the current benchmark catalog/opportunities/gaps/tests contract independent of active plans.

## benchmark-opportunities

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-27-benchmark-opportunities-design.md`
  - `docs/plans/2026-06-27-benchmark-opportunities-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until benchmark opportunity scoring, JSON contract, calibration output, and non-graph semantics are documented outside active plans
    - `docs/plans/2026-06-27-benchmark-opportunities-design.md`
    - `docs/plans/2026-06-27-benchmark-opportunities-implementation-plan.md`
- remaining_gaps:
  - No durable reference page under docs/ was found for benchmark opportunities JSON, scoring caveats, calibration output, row ordering, commons behavior, and non-graph semantics.
  - The plan pair remains the most complete explanation of the opportunity report semantics until a durable benchmark guide/checkpoint exists.

## benchmark-tests-v0

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-benchmark-tests-v0-design.md`
  - `docs/plans/2026-06-28-benchmark-tests-v0-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until benchmark tests JSON contract, row semantics, priority_source values, readiness labels, filters, and non-goals are documented outside active plans
    - `docs/plans/2026-06-28-benchmark-tests-v0-design.md`
    - `docs/plans/2026-06-28-benchmark-tests-v0-implementation-plan.md`
- remaining_gaps:
  - No durable benchmark reference doc was found for benchmark tests JSON contract, row semantics, priority_source values, readiness labels, filters, or non-goals around automatic belief-test creation.

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

## catalog-datasets

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-21-catalog-datasets-design.md`
  - `docs/plans/2026-06-21-catalog-datasets-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until dataset prioritization workflow rationale is checkpointed and live citations are repointed
    - `docs/plans/2026-06-21-catalog-datasets-design.md`
    - `docs/plans/2026-06-21-catalog-datasets-plan.md`
- remaining_gaps:
  - commands/catalog-datasets.md and science/src/science_tool/dataset_prioritize.py still cite the plan as the design anchor.
  - The original design is partially stale: later plans added verify-access, Q/H datasets: reach, reference/pointer classes, coverage reasons, and commons-promotion guidance.

## contextual-structural-roles

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-19-contextual-structural-roles-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until membership-role semantics and causal-role boundary are documented
    - `docs/plans/2026-06-19-contextual-structural-roles-design.md`
- remaining_gaps:
  - Durable docs do not yet explain the semantic boundary: membership role is frame-relative bundle plumbing, not a proposition role or causal structural role.
  - docs/user-guide/epistemic-model.md only gives high-level weakest-link bundle belief and does not describe rival/background exclusion or the BundleMembership node.

## data-audit

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-data-audit-design.md`
  - `docs/plans/2026-06-28-data-audit-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until the data boundary, data_policy configuration, science data audit workflow, and deferred follow-ons are documented outside active plans
    - `docs/plans/2026-06-28-data-audit-design.md`
    - `docs/plans/2026-06-28-data-audit-plan.md`
- remaining_gaps:
  - No durable non-plan convention page was found for the data boundary, data_policy configuration, or science data audit command.
  - The design explicitly defers size-guard hooks, validate-time ignored-provenance warnings, health checks, .gitignore/scaffold deltas, and downstream sweeps.

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

## dataset-catalog-cli

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-21-dataset-catalog-cli-design.md`
  - `docs/plans/2026-06-21-dataset-catalog-cli-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until dataset catalog CLI rationale is checkpointed and live citations are repointed
    - `docs/plans/2026-06-21-dataset-catalog-cli-design.md`
    - `docs/plans/2026-06-21-dataset-catalog-cli-plan.md`
- remaining_gaps:
  - science/src/science_tool/datasets_catalog.py and science/src/science_tool/validate/checks/dataset_acquisition.py still cite the plan.
  - Some original details are stale after layout v3 and triage-pack changes: doc/datasets became entities/datasets, dataset_class exists, and verify-access owns coupled access edits.

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

## dataset-qa-seam

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-16-dataset-qa-seam-design.md`
  - `docs/plans/2026-06-16-dataset-qa-seam-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until dataset QA graph stamping and belief cap semantics are documented
    - `docs/plans/2026-06-16-dataset-qa-seam-design.md`
    - `docs/plans/2026-06-16-dataset-qa-seam-plan.md`
- remaining_gaps:
  - Durable docs do not describe DatasetEntity.qa_report, report-hash audit semantics, qaFailedDataset stamping, or qa_dataset_capped belief behavior.
  - No user-facing doc explains that the seam consumes persisted science datasets qa reports and does not rerun QA during graph build.

## dataset-reach-authoring-surfaces

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-24-dataset-reach-authoring-surfaces-design.md`
  - `docs/plans/2026-06-24-dataset-reach-authoring-surfaces-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until dataset-prioritization reach surfaces are checkpointed and later plan citations are repointed
    - `docs/plans/2026-06-24-dataset-reach-authoring-surfaces-design.md`
    - `docs/plans/2026-06-24-dataset-reach-authoring-surfaces-implementation-plan.md`
- remaining_gaps:
  - The implementation and tests are complete, but the full reach contract and rationale are still split across active plans, command docs, and code comments rather than one stable non-plan dataset-prioritization reference.
  - commands/catalog-datasets.md still cites docs/plans/2026-06-21-catalog-datasets-design.md as its design anchor, and the catalog-datasets cleanup record already calls for a dataset-prioritization migration checkpoint.
  - docs/plans/2026-06-26-dataset-catalog-triage-pack-design.md still cites plan:2026-06-24-dataset-reach-authoring-surfaces-design, so deleting this thread without a checkpoint or citation repoint would remove referenced context.

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

## datasets-qa-reachability

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-16-datasets-qa-reachability-design.md`
  - `docs/plans/2026-06-16-datasets-qa-reachability-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until science datasets qa command and report contract are documented
    - `docs/plans/2026-06-16-datasets-qa-reachability-design.md`
    - `docs/plans/2026-06-16-datasets-qa-reachability-plan.md`
- remaining_gaps:
  - No durable user-guide page documents science datasets qa usage, exit codes, report layout, or the relationship between transient QA runs and persisted qa_report.json consumed by graph build.
  - docs/conventions/pipeline-qa-checkpoints.md documents workflow QA reports, not this datapackage command contract.

## discusses-membership-surfaces

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-19-discusses-membership-surfaces-design.md`
  - `docs/plans/2026-06-19-discusses-membership-surfaces-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until discusses membership surfaces and validation contract are documented
    - `docs/plans/2026-06-19-discusses-membership-surfaces-design.md`
    - `docs/plans/2026-06-19-discusses-membership-surfaces-implementation-plan.md`
- remaining_gaps:
  - Durable docs/templates mention frontmatter object-form discusses, but do not document relations.yaml role, --bridge-role, the proposition-to-bundle subtype rule, or the non-membership cito:discusses cases.
  - Validation messages still cite design section numbers, so the plan is acting as accidental rationale.

## entity-consolidation-and-archive

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-15-entity-consolidation-and-archive-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until as-built archive/consolidation workflow and invariants are documented
    - `docs/plans/2026-06-15-entity-consolidation-and-archive-design.md`
- remaining_gaps:
  - Durable user docs mention entity list flags and registry basics but do not fully document archive/consolidation workflows, invariants, or as-built deviations now captured only in the plan.
  - Migrate the as-built contract before removing from active plans.

## entity-consolidation-p1-visibility

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-15-entity-consolidation-p1-visibility-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until mark-superseded and default-hidden semantics are documented
    - `docs/plans/2026-06-15-entity-consolidation-p1-visibility-plan.md`
- remaining_gaps:
  - mark-superseded and default-hidden semantics are not clearly documented in durable user/process docs beyond CLI surface references.

## entity-consolidation-p2-candidate-detector

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-15-entity-consolidation-p2-candidate-detector-design.md`
  - `docs/plans/2026-06-15-entity-consolidation-p2-candidate-detector-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until consolidation-candidate command and tuning semantics are documented
    - `docs/plans/2026-06-15-entity-consolidation-p2-candidate-detector-design.md`
    - `docs/plans/2026-06-15-entity-consolidation-p2-candidate-detector-plan.md`
- remaining_gaps:
  - The detector command and tuning semantics are not documented in durable user/process docs.
  - The design includes real-corpus tuning results that should be preserved outside active plans if future tuning matters.

## entity-consolidation-p3-archive

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-15-entity-consolidation-p3-archive-design.md`
  - `docs/plans/2026-06-15-entity-consolidation-p3-archive-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until archive index, freeze, reconciliation, and graph-resolution contract are documented
    - `docs/plans/2026-06-15-entity-consolidation-p3-archive-design.md`
    - `docs/plans/2026-06-15-entity-consolidation-p3-archive-plan.md`
- remaining_gaps:
  - Durable docs do not fully explain entities/_archive, archive-index.jsonl, archive freeze/reconciliation, or index-only graph resolution.
  - P3 code now includes P4 additive fields consolidated_into and digest_insight in ArchiveRow; preserve phase boundary when moving files.

## entity-consolidation-p4-consolidate-apply

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-16-entity-consolidation-p4-consolidate-apply-design.md`
  - `docs/plans/2026-06-16-entity-consolidation-p4-consolidate-apply-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until consolidate scaffold/apply operational contract is documented
    - `docs/plans/2026-06-16-entity-consolidation-p4-consolidate-apply-design.md`
    - `docs/plans/2026-06-16-entity-consolidation-p4-consolidate-apply-plan.md`
- remaining_gaps:
  - No durable user/migration doc found for the mutating workflow: scaffold, fill digest, apply, rollback/partial-failure recovery, unarchive limitations, and archive-index fields.
  - P5 docs mention cluster-digests consumption, not the P4 authoring/operator contract.

## entity-consolidation-p5-tier4-substitution

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-16-entity-consolidation-p5-tier4-substitution-design.md`
  - `docs/plans/2026-06-16-entity-consolidation-p5-tier4-substitution-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until cluster-digests JSON and bridge semantics are documented
    - `docs/plans/2026-06-16-entity-consolidation-p5-tier4-substitution-design.md`
    - `docs/plans/2026-06-16-entity-consolidation-p5-tier4-substitution-plan.md`
- remaining_gaps:
  - Durable docs mention the support surface and bridge behavior, but not the JSON contract, --deep index-only semantics, member_to_digest alias/same_as behavior, or scaffolded-but-unapplied archived=false semantics.

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

## feedback-data-evidence-tracking-boundary

- status: `superseded_delete`
- recommended_action: `delete`
- actions: `deferred`
- files:
  - `docs/plans/2026-06-28-feedback-data-evidence-tracking-boundary.md`
- pending_actions:
  - `deferred`: review status superseded_delete, but deletion depends on first creating the data-audit/data-boundary durable checkpoint and cleaning stale pointers
    - `docs/plans/2026-06-28-feedback-data-evidence-tracking-boundary.md`
- remaining_gaps:
  - Delete after the data-audit migration checkpoint exists so the origin, resolved boundary decision, and deferred follow-ons are not lost.
  - docs/plans/2026-06-28-downstream-feedback-fixes.md still points fb-004 at this feedback note, so that stale pointer may need cleanup when deleting.

## feedback-from-recent

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-27-feedback-from-recent-design.md`
  - `docs/plans/2026-06-27-feedback-from-recent-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until feedback add --from-recent and broader telemetry lifecycle docs are captured outside active plans
    - `docs/plans/2026-06-27-feedback-from-recent-design.md`
    - `docs/plans/2026-06-27-feedback-from-recent-implementation-plan.md`
- remaining_gaps:
  - No durable non-plan user/operator doc was found for science feedback add --from-recent.
  - The CLI help documents newest eligible selection but not the full indexed selection contract.
  - The broader telemetry lifecycle docs are still missing for storage, redaction, opt-out, reporting, export, prune, validation summaries, feedback triage telemetry, and feedback-from-recent.

## feedback-telemetry-adaptation

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-26-feedback-telemetry-adaptation-design.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until telemetry/adaptation contract and deferred skill-note scope are documented outside active plans
    - `docs/plans/2026-06-26-feedback-telemetry-adaptation-design.md`
- remaining_gaps:
  - No durable non-plan user/operator doc was found for telemetry storage, redaction, opt-out, report/export/prune, validation-summary events, feedback triage telemetry, or feedback add --from-recent.
  - No science telemetry note helper was found; the broad design treated skill note events as optional/high-value workflow instrumentation, and later telemetry-v1.5 explicitly deferred skill note events.

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

## kind-descriptor-model-registry

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-14-kind-descriptor-model-registry-design.md`
  - `docs/plans/2026-06-15-kind-descriptor-model-registry-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until CORE_PROFILE source-of-truth decision and CORE_KINDS removal are documented
    - `docs/plans/2026-06-14-kind-descriptor-model-registry-design.md`
    - `docs/plans/2026-06-15-kind-descriptor-model-registry-plan.md`
- remaining_gaps:
  - The architectural decision that CORE_PROFILE is the source of truth and CORE_KINDS was removed is still mostly in plans/test names, not in durable docs.
  - Later adapter work changed the exact strategy typing boundary, so the design is not an exact as-built spec.

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

## membership-roles

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-19-membership-roles-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until final membership-role vocabulary, syntax, and roll-up contract are documented
    - `docs/plans/2026-06-19-membership-roles-implementation-plan.md`
- remaining_gaps:
  - The original plan is stale as an implementation guide because BundleMembership emission moved into graph/io.py and relations.yaml/bridge support was added later.
  - Durable user docs lack the complete current contract for role vocabulary, default core behavior, frontmatter syntax, roll-up gating, and surface parity.

## methodology-feedback

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-28-methodology-feedback-design.md`
  - `docs/plans/2026-06-28-methodology-feedback-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until feedback concern taxonomy, methodology lens filtering, triage semantics, and report grouping are documented outside active plans
    - `docs/plans/2026-06-28-methodology-feedback-design.md`
    - `docs/plans/2026-06-28-methodology-feedback-plan.md`
- remaining_gaps:
  - No durable user-guide/process doc was found for the feedback concern taxonomy, methodology lens filtering, report grouping, or triage semantics outside command/skill docs and tests.
  - No command-doc test was found specifically asserting commands/post-mortem.md or the interpret-results handoff text.

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

## project-serialize

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-29-project-serialize-design.md`
  - `docs/plans/2026-06-29-project-serialize-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until project serialize schema, payload inventory, force semantics, privacy stance, and data-audit interaction are documented outside active plans
    - `docs/plans/2026-06-29-project-serialize-design.md`
    - `docs/plans/2026-06-29-project-serialize-plan.md`
- remaining_gaps:
  - No durable user/workflow doc was found for science project serialize, the science-project-serialized schema, payload inventory, force semantics, privacy stance, or data-audit interaction.

## project-verify

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-29-project-verify-design.md`
  - `docs/plans/2026-06-29-project-verify-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until project verify self-check, against-checkout comparison, extraction, JSON verdicts, exit codes, and git_tracked mismatch behavior are documented outside active plans
    - `docs/plans/2026-06-29-project-verify-design.md`
    - `docs/plans/2026-06-29-project-verify-plan.md`
- remaining_gaps:
  - No durable user/workflow doc was found for science project verify, self-check versus --against behavior, extraction, JSON verdict shape, warnings, or exit codes.
  - Implementation differs from the design: verify treats payload git_tracked mismatches as differ, while the design said git_tracked was informational. The shipped behavior is tested and should be checkpointed explicitly.

## proposition-cross-paper-evidence-phase4d

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-30-proposition-cross-paper-evidence-phase4d-design.md`
  - `docs/plans/2026-06-30-proposition-cross-paper-evidence-phase4d-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until derived cross-paper literature evidence scanning, materialize behavior, diagnostic command, fault semantics, belief effect, and non-goals are documented outside active plans
    - `docs/plans/2026-06-30-proposition-cross-paper-evidence-phase4d-design.md`
    - `docs/plans/2026-06-30-proposition-cross-paper-evidence-phase4d-plan.md`
- remaining_gaps:
  - No durable user or developer doc was found for the derived literature evidence scanner, materialize-time behavior, diagnostic command, fault semantics, belief effect, or non-goals.
  - docs/conventions/annotation-tokens.md still mentions cross-paper evidence as future work, so durable docs should replace that stale forward-looking note.

## prose-epistemics-p1-source-adapter

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-17-prose-epistemics-p1-source-adapter-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until TextSourceAdapter contract and P1/P2 boundary are documented
    - `docs/plans/2026-06-17-prose-epistemics-p1-source-adapter-plan.md`
- remaining_gaps:
  - No durable non-plan doc found that explains the TextSourceAdapter contract, P1/P2 boundary, and why regenerable is declared but not implemented in P1.

## prose-epistemics-p2-internal-prose

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`
  - `docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until P2 prose decomposition artifact, storage, stale, locator, and operator contracts are documented
    - `docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`
    - `docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-plan.md`
- remaining_gaps:
  - Durable docs only briefly mention prose-derived reports in docs/user-guide/graph-and-derived-state.md and list prose-source in docs/user-guide/entities.md; they do not document the P2 artifact schema, storage paths, fingerprint identity, stale semantics, locator resolver contract, or operator commands.
  - Later pilot-improvements work adds pre-ingest validation and batch promotion, so the original P2 plan is not the full as-built operator contract.

## prose-epistemics-p3-domain-grounding

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-design.md`
  - `docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until grounding kernel and prose grounding artifact contracts are documented
    - `docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-design.md`
    - `docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-plan.md`
- remaining_gaps:
  - No durable non-plan doc explains the grounding kernel contract, default supported floor, status semantics, P2 fingerprint join invariant, grounding artifact schema, or timestamp-churn policy.
  - Natural-systems application docs consume the framework but are still plans, not durable science framework docs.

## prose-epistemics-p4-health-coverage

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-18-prose-epistemics-p4-health-coverage-design.md`
  - `docs/plans/2026-06-18-prose-epistemics-p4-health-coverage-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until prose health manifest, artifact, coverage, findings, and health reader contracts are documented
    - `docs/plans/2026-06-18-prose-epistemics-p4-health-coverage-design.md`
    - `docs/plans/2026-06-18-prose-epistemics-p4-health-coverage-plan.md`
- remaining_gaps:
  - Durable docs do not describe data/prose-health/manifest.json, data/prose-health/prose-health.json, source-state precedence, coverage ratios, finding codes, or the science health prose_epistemics behavior beyond a short derived-state mention.
  - The plan remains the clearest source for downstream consumer contract details, so deletion would lose useful operational knowledge.

## prose-epistemics-pilot-improvements

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-19-prose-epistemics-pilot-improvements-design.md`
  - `docs/plans/2026-06-19-prose-epistemics-pilot-improvements-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until prose-epistemics framework hardening contract is documented
    - `docs/plans/2026-06-19-prose-epistemics-pilot-improvements-design.md`
    - `docs/plans/2026-06-19-prose-epistemics-pilot-improvements-plan.md`
- remaining_gaps:
  - Durable non-plan docs still only briefly mention prose-derived reports and prose-source; they do not describe the raw validation CLI, batch promotion plan schema, project-relative path policy, revision_manifest_excludes, or operational annotation-ref behavior.
  - Existing cleanup records for P2/P3/P4 already mark migration checkpoints as needed; this improvement plan expands the same as-built prose-epistemics contract that should be documented together.
  - The offline-agent pilot validates one source only; larger natural-systems decomposition quality remains future campaign work.

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

## qa-schema-compiler

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-14-qa-schema-compiler-design.md`
  - `docs/plans/2026-06-14-qa-schema-compiler-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until schema-to-QA compiler contract is documented
    - `docs/plans/2026-06-14-qa-schema-compiler-design.md`
    - `docs/plans/2026-06-14-qa-schema-compiler-plan.md`
- remaining_gaps:
  - No durable non-plan doc fully records the schema-to-check mapping, compile errors, merge semantics, YAML timestamp rule, or tabular program contract.
  - docs/conventions/pipeline-qa-checkpoints.md documents the older config-driven QA convention and science_qa generally, but not the schema compiler as the current contract.

## remove-v3-migration-code

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-06-20-remove-v3-migration-code-design.md`
  - `docs/plans/2026-06-20-remove-v3-migration-code-implementation-plan.md`
- pending_actions:
  - `deferred`: review status incomplete; later work intentionally restored migration surfaces, so this needs triage rather than deletion
    - `docs/plans/2026-06-20-remove-v3-migration-code-design.md`
    - `docs/plans/2026-06-20-remove-v3-migration-code-implementation-plan.md`
- remaining_gaps:
  - Plan still says to remove surfaces that are currently live and tested: entities migrate/entity_layout_migration and graph migrate-paper-datasets/paper_dataset_migration.
  - Manifest guard still references the restored command at science/src/science_tool/validate/checks/manifest.py.
  - Triage needed to decide whether this plan should be split into completed cleanup notes plus explicit supersession by later migration plans.

## science-citations-and-references

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-23-science-citations-and-references-design.md`
  - `docs/plans/2026-06-23-science-citations-and-references-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until science.references and Labnote citation contract are checkpointed in durable docs
    - `docs/plans/2026-06-23-science-citations-and-references-design.md`
    - `docs/plans/2026-06-23-science-citations-and-references-plan.md`
- remaining_gaps:
  - No durable science-side user/convention doc was found for the science.references contract, references/index.json package resource, citation grammar v1, fail-closed export behavior, or consumer expectations.
  - The plan files carry locked design decisions such as exporting all bibliography records, app export owning references/index.json, and normal exports rejecting unresolved citations.
  - The old plan text is now too broad as active implementation guidance because the functionality spans science and Labnote and later Labnote export specs have absorbed part of the contract.

## source-compiler-adapter-policy-keystone

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-15-source-compiler-adapter-policy-keystone-design.md`
  - `docs/plans/2026-06-15-source-compiler-adapter-policy-keystone-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until the source compiler adapter-policy rationale is checkpointed
    - `docs/plans/2026-06-15-source-compiler-adapter-policy-keystone-design.md`
    - `docs/plans/2026-06-15-source-compiler-adapter-policy-keystone-plan.md`
- remaining_gaps:
  - No non-plan durable checkpoint records why adapter policy hooks exist, why owner scope remains centralized, or which adapter quirks are intentionally preserved.

## source-compiler-phase-split

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-15-source-compiler-phase-split-design.md`
  - `docs/plans/2026-06-15-source-compiler-phase-split-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until compiler phase boundaries and audit/materialize contract are checkpointed
    - `docs/plans/2026-06-15-source-compiler-phase-split-design.md`
    - `docs/plans/2026-06-15-source-compiler-phase-split-plan.md`
- remaining_gaps:
  - No durable non-plan compiler checkpoint records the phase boundary contract, materialize-only preflight rule, audit hard-gate, and pure build path.

## source-compiler-snapshot-freshness

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-15-source-compiler-snapshot-freshness-design.md`
  - `docs/plans/2026-06-15-source-compiler-snapshot-freshness-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until SourceSnapshot and SourceChange semantics are checkpointed
    - `docs/plans/2026-06-15-source-compiler-snapshot-freshness-design.md`
    - `docs/plans/2026-06-15-source-compiler-snapshot-freshness-plan.md`
- remaining_gaps:
  - No non-plan durable checkpoint captures SourceSnapshot semantics, current-only SourceChange policy, unchanged rebuild churn guard, and deferred remote/aggregate snapshot fill-outs.

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

## telemetry-core

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-27-telemetry-core-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until telemetry event schema, local storage, redaction, opt-out, report/export/prune, and retention behavior are documented outside active plans
    - `docs/plans/2026-06-27-telemetry-core-implementation-plan.md`
- remaining_gaps:
  - No durable user/developer doc was found for telemetry event schema, environment variables, local storage, retention/export behavior, or privacy/redaction guarantees.
  - The plan still carries the clearest explanation of the telemetry core contract until durable telemetry docs exist.

## telemetry-v1.5

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-27-telemetry-v1.5-design.md`
  - `docs/plans/2026-06-27-telemetry-v1.5-implementation-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until validation summaries, feedback triage telemetry, privacy boundaries, and exit-code regression rationale are documented outside active plans
    - `docs/plans/2026-06-27-telemetry-v1.5-design.md`
    - `docs/plans/2026-06-27-telemetry-v1.5-implementation-plan.md`
- remaining_gaps:
  - No durable doc was found for validation_summary schema, aggregate-only privacy boundary, feedback triage --with-telemetry matching/window semantics, or the Click exit-code regression rationale.
  - feedback add --from-recent is implemented in current code even though this v1.5 plan explicitly deferred it; durable telemetry docs should reconcile the shipped v1.5 plus feedback-from-recent surface.

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

## typed-evidence-vocabularies

- status: `implemented_needs_durable_docs`
- recommended_action: `create migration checkpoint`
- actions: `migration_checkpoint_created`
- files:
  - `docs/plans/2026-06-16-typed-evidence-vocabularies-design.md`
  - `docs/plans/2026-06-16-typed-evidence-vocabularies-plan.md`
- pending_actions:
  - `migration_checkpoint_created`: review status implemented_needs_durable_docs; retain source until typed evidence vocabulary and rank reconciliation contract is documented
    - `docs/plans/2026-06-16-typed-evidence-vocabularies-design.md`
    - `docs/plans/2026-06-16-typed-evidence-vocabularies-plan.md`
- remaining_gaps:
  - The plan's intended durable taxonomy target docs/proposition-and-evidence-model.md does not exist in this worktree.
  - docs/user-guide/evidence-lines.md captures authored evidence types and negative_result, but not the developer-facing SSOT contract: model enum ownership, suffix canonicalization policy, graph-reader degrade-to-rank-0 behavior, and rank reconciliation invariants.
  - Implementation differs slightly from the design wording by keying rank tables on canonical string values from EvidenceType rather than enum members directly; tests/reconciliation preserve behavior, but a checkpoint should state this accepted implementation shape.
