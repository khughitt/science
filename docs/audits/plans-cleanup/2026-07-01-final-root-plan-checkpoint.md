# Final Root Plans Checkpoint

This checkpoint retires the last two active root `docs/plans/` files from the
cleanup pass. They remain in `docs/plans/historical/`, while the residual work
is summarized here so future agents do not treat root planning docs as the active
source of truth.

After this checkpoint, the cleanup-era root planning backlog should contain no
untriaged active documents. In the merged `main` history, newer 2026-06-30 and
2026-07-01 framework plans may still live under `docs/plans/`; those should be
treated as current implementation plans and tracked by the regenerated cleanup
index, not as residual backlog from this curation pass.

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

- Completed 2026-07-13: the full dbSNP b157 Snakemake workflow now publishes
  `rsid-shards.yaml` plus durable shard SQLite files instead of a monolithic
  `rsid_mappings.sqlite`. This supersedes the original single-SQLite production
  criterion after repeated multi-day/OOM final merge attempts.
- Completed 2026-07-13: retained/skipped counts and shard byte totals were
  captured in `build-summary.yaml`; the accepted full-source retained allele
  count is `2,892,721,560` across `128` shard SQLite files.
- Completed 2026-07-13: `recipe/lockfile.yaml` is committed in
  `~/d/science-commons`.
- Completed 2026-07-13: `datapackage.yaml` now records non-zero hashes, byte
  counts, and final metadata for the `rsid_shards` manifest and build summary.
- Completed 2026-07-13: `resolve_rsid(...)` was smoked against the real commons
  sharded artifact through the manifest-aware resolver.
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
