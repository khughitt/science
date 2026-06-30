# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `8`

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

## downstream-feedback-fixes-2026-06-28

- status: `incomplete`
- recommended_action: `keep for triage`
- actions: `deferred`
- files:
  - `docs/plans/2026-06-28-downstream-feedback-fixes.md`
- pending_actions:
  - `deferred`: review status incomplete; six downstream feedback fixes are implemented or documented, but fb-2026-06-28-014 remains deferred and should be kept for triage
    - `docs/plans/2026-06-28-downstream-feedback-fixes.md`
- remaining_gaps:
  - fb-2026-06-28-014 remains deferred; the plan records that catalog gap-scan no-candidate flooding likely needs upstream question formulation and brainstorming rather than an output filter.

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
