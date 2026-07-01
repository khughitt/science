# Remaining Roadmap Checkpoint

This checkpoint retires three active `docs/plans/` roadmap documents after the
current user-facing contracts were migrated to durable docs. The original files
remain under `docs/plans/historical/` because they are useful design history, but
they are no longer active implementation plans.

Moved roadmaps:

- `docs/plans/historical/2026-06-10-data-driven-discovery-improvements.md`
- `docs/plans/historical/2026-06-14-patchwork-kernel-architecture-design.md`
- `docs/plans/historical/2026-06-26-benchmark-grounded-model-assessment-design.md`

## Guide Coherence Pass

The cleanup pass left the user guide with a coherent teaching spine:

- `docs/user-guide/science-model.md` introduces authored sources, derived graph
  views, epistemic neighborhoods, provenance, and federation.
- `docs/user-guide/entities.md`, `docs/user-guide/evidence-lines.md`, and
  `docs/user-guide/epistemic-model.md` carry the durable source/evidence/belief
  contracts.
- `docs/user-guide/graph-and-derived-state.md`, `docs/user-guide/benchmarking.md`,
  `docs/user-guide/health-and-validation.md`, and `docs/user-guide/feedback-and-telemetry.md`
  describe read models, diagnostics, and operator workflows.

The main curation rule from this pass is that current behavior belongs in the
user guide, while target-state roadmap material belongs in audit checkpoints or
new focused plans when it becomes actionable. This avoids turning the guide into
a backlog dump and keeps old roadmap prose from being cited as present behavior.

## Patchwork Kernel

Current behavior is now documented in `docs/user-guide/science-model.md`,
`docs/user-guide/epistemic-model.md`, `docs/user-guide/graph-and-derived-state.md`,
and `docs/audits/plans-cleanup/2026-06-08-epistemic-model-checkpoint.md`.

Implemented or documented invariants:

- Source files are the durable authority; graphs, dashboards, snapshots, and
  workbenches are derived views.
- The built-in core profile is the descriptor source for core entity-kind facts.
- Propositions carry belief, evidence lines ground belief, and edge status is a
  derived projection.
- `patch-definition` records express authored patch intent; graph build derives
  `sci:PatchMembership` records and convenience membership edges.
- `patch_type: inquiry` is the current source-first bridge from inquiry workflows
  to patch-backed graph views.
- Local Markdown source snapshots and source-change events exist for graph
  freshness.

Deferred backlog:

- Full scope/federation model for remote sources, peers, commons, sync leases,
  and federated belief builds.
- Full agent/trust/field-level provenance model.
- Source snapshots for aggregate rows, datapackages, DOI, Zenodo, API responses,
  and dataset manifests.
- Patch snapshots, remote/commons patch scopes, patch maturity levels,
  ontology/latent glue, and lead/candidate workflows.
- Full inquiry subsumption; `sci:Inquiry` still exists as a compiled
  compatibility view.
- Complete migration away from remaining direct graph mutation or parallel-store
  paths.

## Data-Driven Discovery

The umbrella was a roadmap/catalog, not an implementation plan. Theme B shipped
through the QA toolkit, QA breadth/depth reporting, and no-iteration workflow
audit surfaces. The relevant durable docs are
`docs/conventions/pipeline-qa-checkpoints.md`,
`docs/process/pipeline-audit-and-refactor.md`,
`docs/user-guide/evidence-lines.md`, and
`docs/user-guide/epistemic-model.md`.

Surviving backlog:

- Evidence-tier policy design: distinguish paper hints, single analyzed
  datasets, multiple datasets, and multi-modal corroboration as explicit belief
  policy inputs.
- Cross-modality reward design: reward orthogonal corroboration only after
  dataset, sample, label, and ground-truth dependence are accounted for.
- Adaptive pre-registration: keep pre-registration useful for exploratory work
  without turning it into a rigid confirmatory gate.
- Robustness and model comparison: seeded perturbation/noise checks, rerun/diff
  verification, and Bayesian model comparison support.
- Step-level decision telemetry: capture rationale and expected output before a
  tool runs.
- Artifact-over-narrative review: weight code, numbers, plots, and verified
  artifacts above tidy prose rationale.
- Bias-audit additions: no external grounding, hard-question opt-out, gene-set
  credulity, and tail-hiding aggregate metrics.

## Benchmark-Grounded Assessment

The current benchmark contract is durable in
`docs/user-guide/benchmarking.md`. It is descriptive and read-only: Science can
catalog benchmark-capable datasets, report coverage, find opportunities and
gaps, calibrate gap reports across projects, and project draft test rows.

Implemented or documented:

- Dataset `benchmark:` metadata, sparse task records, free-text v1 facets, and
  `dataset:<slug>#<task-id>` rendering.
- Benchmark metadata validation rules.
- `science benchmark list`, `opportunities`, `gaps`, `gap-calibration`, and
  read-only `tests` projections.
- The `/science:catalog-benchmarks` boundary: descriptive cataloging, not graph
  benchmark edges or outcome updates.

Deferred backlog:

- Formal authored `plan_kind: belief-test` schema and template.
- Graph-aware benchmark-to-belief/proposition edges; `related_beliefs` remains
  free text.
- Structured benchmark result/outcome records.
- Outcome-to-evidence/proposition update workflow.
- Cross-project success analysis over actual benchmark outcomes. Current gap
  calibration evaluates report quality and candidate behavior, not project
  success.
