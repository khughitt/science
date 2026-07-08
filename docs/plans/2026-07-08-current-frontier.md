# Current Frontier

Date: 2026-07-08

This note records the practical next-work frontier after recent plan execution.
It is not a new design and does not supersede the linked plans.

## Recently landed

- `docs/plans/2026-07-07-project-data-root-config-implementation-plan.md`:
  project data-root configuration is implemented on `main`.
- `docs/plans/2026-07-07-explore-ideas-gap-closure-plan.md`:
  `science explore-ideas gaps` is implemented on `main`.
- `docs/plans/2026-07-07-review-pipeline-data-availability-plan.md`:
  the review-pipeline data-availability tightening is implemented on `main`.
- `docs/plans/2026-07-07-capability-scope-marker-implementation-plan.md`:
  the framework-side `capability_scope` marker work is implemented on `main`;
  the downstream MM30 marker rollout also landed in MM30 (`2c5be544`, merged by
  `c1c99e75`).

## Recommended next choices

Each choice below names the goal it best serves, so the trade-off lives with
the option rather than in a separate table.

1. **Bio-identity P4 gene crosswalk.** *Choose this to unlock more
   dataset-resolution work.* Continue the adoption-layer path through
   `docs/plans/2026-07-03-bio-identity-p4-gene-crosswalk-implementation-plan.md`,
   one of four P4 tracks (assembly-registry, cytoband, liftover, gene-crosswalk)
   under `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`. Higher
   impact, but touches Science and `science-commons`.
2. **Cross-paper evidence readiness surfaces.** *Choose this to improve review
   visibility with lower schema churn.* Pick up
   `docs/plans/2026-06-30-cross-paper-evidence-readiness-surfaces-plan.md` when
   the immediate priority is review/reporting ergonomics rather than identity
   infrastructure.

## Scope

This is a curated shortlist of the open frontier, not the full plan set. Most
other recent plans under `docs/plans/` have already landed on `main` — for
example the `benchmark-*` fallback series and the `phase4e`/`phase4f`
reconciliation threads. Any open plans not listed above are lower priority than
these three.
