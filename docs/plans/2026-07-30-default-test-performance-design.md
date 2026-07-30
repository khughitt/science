# Default Test Performance Design

## Goal

Reduce wall-clock time for the default `science/` and `science/model/` pytest
suites without weakening assertions or changing the explicitly excluded
`snapshot`, `real_projects`, `git_source`, and `packaging` groups.

## Baseline

- `science/model`: 1,902 passed in 5.74 seconds.
- `science`: 12,103 passed, 7 skipped, and 42 deselected in 752.15 seconds.
- Repeated `health` budget tests account for roughly 165 seconds.
- The real-repository text scan takes 16.60 seconds.
- Repeated ontology catalog parsing is the only clustered model cost, totaling
  roughly 0.7 seconds.

## Root Causes

The shared budget-test fixture creates 3,000 data-audit files for every
consumer. Health tests do not need those files but repeatedly discover and
scan them. Other budget fixtures use substantially more entities than needed
to exceed their output ceilings.

`iter_scannable_files()` filters excluded directories only after
`Path.rglob()` has descended into them. The toolkit repository therefore walks
large `.git`, virtual-environment, cache, and worktree trees even though their
files can never be returned.

The ontology tests repeatedly parse the same immutable package YAML while
testing independent catalog properties.

Pytest also records tens of thousands of identical rdflib deprecation
warnings. These will be filtered only if a focused measurement shows that
doing so materially improves the suite.

## Design

1. Remove the 3,000-file data corpus from the shared budget fixture and seed it
   only in tests whose contract requires an over-budget or complete data-audit
   result.
2. Reduce oversized synthetic corpora to the smallest comfortably
   over-budget size, with the existing completeness and projection assertions
   proving that the boundary is still exercised.
3. Implement `iter_scannable_files()` with a standard-library directory walk
   that prunes known excluded directory names before descent while preserving
   suffix, size, explicit-path, graph-artifact, and deterministic-order rules.
4. Reuse each parsed ontology catalog within the ontology test module while
   retaining direct loader tests.
5. Add narrowly matched rdflib warning filters only when before/after timing
   demonstrates a worthwhile reduction.

No new dependency, parallel test runner, persistent production cache, or
cross-suite concurrency will be introduced.

## Verification

For each change, run the affected test module with pytest duration reporting
and compare it to its measured baseline. Then run the two default suites
sequentially:

```bash
cd science/model && uv run --frozen pytest --durations=40
cd science && uv run --frozen pytest --durations=60
```

Run Ruff on changed Python files. The final report will include before/after
wall-clock times and identify any measured candidate intentionally left
unchanged.
