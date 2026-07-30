# Default Test Performance Design

## Goal

Reduce wall-clock time for the default `science/` and `science/model/` pytest
suites without weakening assertions or changing the explicitly excluded
`snapshot`, `real_projects`, `git_source`, and `packaging` groups.

## Baseline

- `science/model`: 1,902 passed in 5.74 seconds.
- An initial unpinned `science` run reported 12,103 passed, 7 skipped, and 42
  deselected in 752.15 seconds. Comparisons must disable pytest's randomized
  ordering with `-p no:randomly`.
- Eight health budget cases take 16.16–17.05 seconds each, roughly 134 seconds
  together.
- `test_validate_is_bounded_and_complete` takes 20.42 seconds.
- The real-repository text scan takes 16–20 seconds depending on checkout and
  filesystem state.
- Repeated ontology catalog parsing is the only clustered model cost, totaling
  roughly 0.7 seconds.

The repository guide's “~2–3 min” full-suite estimate predates substantial
test growth and conflicts with current measurements. Re-measure after the
first optimization tranche, then update the guide and its shipped template if
the estimate remains stale.

## Root Causes

Removing the shared fixture's 3,000 data-audit files changed health timings by
approximately zero seconds. Fixture shrinking and corpus right-sizing are
therefore not part of this work; the large corpora are useful stress coverage
for output ceilings.

A profile of one health run over 400 tasks and 300 questions observed eight
`load_project_sources()` calls. The 400 task files were parsed 3,200 times and
PyYAML dominated the run. Static tracing confirms that health performs an
initial lenient source load, canonical validation creates several cache entries
that differ only by strictness flags, and the authored-relations check bypasses
`ValidateContext.project_sources()` entirely.

`strict_identity` is a raise-or-report projection over the arbitration errors
already retained by `ProjectSources`. `strict_core_schema` can likewise enforce
its exception contract from the lenient load's skipped-entity ledger.
`include_commons`, however, changes the contribution set before arbitration;
local-only sources cannot be recovered by filtering an already-arbitrated
commons-inclusive result. The correct target is consequently two canonical
loads per validation run—one with commons and one without—not one lossy load
or a cache entry per strictness combination.

Three corpus walkers—`text_scan.iter_scannable_files()`,
`entities._iter_reference_scan_files()`, and
`migrate_specs.discover_specs()`—filter excluded directories only after
`Path.rglob()` has descended into them. The toolkit repository therefore walks
large `.git`, virtual-environment, cache, and worktree trees even though their
files can never be returned.

The ontology tests repeatedly parse the same immutable package YAML while
testing independent catalog properties. `OntologyCatalog` itself is mutable,
so shared test data must be copied before it is handed to a test.

Pytest records tens of thousands of deprecations emitted inside rdflib's
Dataset/TriG implementation. There is no non-deprecated toolkit call site to
substitute. Exact-message warning filters are the only local lever and will be
kept only if a focused measurement shows material savings.

## Design

1. Add a small regression test that counts task parsing during a real health
   run and proves the current repeated-load behavior before changing it.
2. Make `ValidateContext` cache a canonical lenient `ProjectSources` bundle per
   `include_commons` value. Enforce strict core-schema and identity behavior as
   cheap projections over that bundle's diagnostic ledgers.
3. Allow health's already-loaded commons-inclusive bundle to seed canonical
   validation, and route the authored-relations check through
   `ValidateContext.project_sources()`. Preserve standalone collector
   fallbacks; normal health checks already receive `HealthContext.sources`.
4. Extract one shared standard-library project walker for the three
   prune-after-descent consumers. It must prune excluded directory names before
   descent, exclude files whose names match the skip set, use
   `followlinks=False`, preserve symlink-file behavior, fail on walk errors, and
   return deterministic paths. Text scanning must check suffixes before
   resolving or statting candidate paths.
5. Reuse parsed ontology YAML within `test_ontologies.py`, returning deep model
   copies so tests never share mutable catalog state. Keep direct registry and
   loader tests.
6. Measure exact-message rdflib warning filters on a warning-heavy module and
   retain them only if the timing improves materially.
7. Re-profile the full default suite after this tranche. The measured hotspots
   above explain only part of the initial wall clock; use the new duration
   report to choose any second tranche rather than guessing from the remaining
   total.

No new dependency, parallel test runner, persistent production cache, or
cross-suite concurrency will be introduced. Budget fixture sizes and their
assertions remain unchanged.

## Verification

For each change, run the affected test module with randomized ordering disabled
and compare repeated before/after duration reports. The real-checkout walker
benchmark is inherently sensitive to Dropbox and checkout state, so measure it
back-to-back more than once rather than comparing isolated runs.

Then run the two default suites sequentially:

```bash
cd science/model && uv run --frozen pytest -p no:randomly --durations=40
cd science && uv run --frozen pytest -p no:randomly --durations=60
```

Run Ruff and pyright after the scoped tests. The final report will include
before/after wall-clock times, source-load and task-parse counts, and any
measured candidate intentionally left unchanged.
