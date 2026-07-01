# Final Root Plans Checkpoint

This checkpoint retires the last two active root `docs/plans/` files from the
cleanup pass. They remain in `docs/plans/historical/`, while the residual work
is summarized here so future agents do not treat root planning docs as the active
source of truth.

After this checkpoint, `docs/plans/` should contain no active root planning
documents. New framework plans should be deliberate, current implementation
plans, not indefinite parking for operator tasks or broad residual design
backlog.

## C4c rsID Variant Labels

Historical plan:

- `docs/plans/historical/2026-05-31-c4c-rsid-variant-label-plan.md`

Current state:

- C4c-1 rsID input is implemented in `~/d/science`.
- `science_tool.commons.rsid` resolves pinned rsID labels from a SQLite mapping.
- `science_tool.commons.variant.vrs_id_from_rsid(...)` converts resolved rsID
  alleles to the existing assembly-anchored VRS identity path.
- Variant identity validation accepts `locator.format: rsid`, resolves the
  configured registry resource once per dataset validation pass, and reports
  row-layer defects.
- Focused tests cover resolver behavior, VRS delegation, rsID locator
  validation, row minting, ambiguity, malformed rows, and unavailable registries.

Residual backlog:

- Run the full dbSNP b157 Snakemake workflow in `~/d/science-commons`.
- Inspect retained row count, SQLite byte size, build time, and skipped bucket
  counts before treating the artifact as production-ready.
- Commit the full-source `recipe/lockfile.yaml`.
- Refresh `datapackage.yaml` with non-zero hashes, byte counts, and final
  resource metadata.
- Smoke `resolve_rsid(...)` against the real commons artifact.
- Treat transcript/protein HGVS projection as a separate future C4c increment,
  not as unfinished C4c-1 framework work.

## Epistemic Drift Detection

Historical plan:

- `docs/plans/historical/2026-06-04-epistemic-drift-detection-design.md`

Current state:

- M1 is implemented and documented: `science graph attention-rank` ranks
  open-question debt over `skos:related` and shared-theme connectivity rather
  than relying on `bears_on`.
- CLI `science entity review` requires a note artifact, avoiding bare timestamp
  review bumps.
- Current user-facing behavior is documented in
  `docs/user-guide/health-and-validation.md`.
- The framework-level implementation checkpoint is
  `docs/audits/plans-cleanup/2026-06-08-epistemic-model-checkpoint.md`.

Residual backlog:

- M2: add an opt-in operationalization coverage contract for scoped empirical
  claims, likely around `operationalized_by` / `claims_scope` plus manifest
  adapters. Structured contradictions should fail validation; free-prose
  coverage extraction should remain warning-only.
- M3: define review semantics beyond M1, including per-kind rubric/backstop
  behavior for settled-looking epistemic entities, review semantics for
  `decision` reference entities, and whether a typed scoping predicate should
  enter freshness propagation.
