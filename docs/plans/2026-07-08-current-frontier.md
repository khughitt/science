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
- `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`:
  Bio-identity P4.1-P4.4 are implemented. The P4.2 gene-crosswalk track landed
  in Science (`e697c403`) and `science-commons` (`0752782`).

## Recommended next choices

Each choice below names the goal it best serves, so the trade-off lives with
the option rather than in a separate table.

1. **Bio-identity P5 follow-through.** *Choose this to turn the landed reference
   artifacts into end-to-end consumer proof.* Continue from
   `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`: review the MM30 P5
   migration report, decide exact UCSC hg19/hg38 registry-row scope, and register
   a real t665 runtime output when available. Higher impact, but touches a real
   consumer project and may require MM30 runtime artifacts.
2. **Cross-paper evidence readiness surfaces.** *Choose this to improve review
   visibility with lower schema churn.* Pick up
   `docs/plans/2026-06-30-cross-paper-evidence-readiness-surfaces-plan.md` when
   the immediate priority is review/reporting ergonomics rather than identity
   infrastructure.

## Scope

This is a curated shortlist of the open frontier, not the full plan set. Most
other recent plans under `docs/plans/` have already landed on `main` — for
example the `benchmark-*` fallback series, the `phase4e`/`phase4f`
reconciliation threads, and the Bio-identity P4 artifact tracks. Any open plans
not listed above are lower priority than these two.
