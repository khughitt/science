# Plans Cleanup Pending Triage

- Source index: `docs/audits/plans-cleanup/thread-index.json`
- Pending thread count: `35`

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
