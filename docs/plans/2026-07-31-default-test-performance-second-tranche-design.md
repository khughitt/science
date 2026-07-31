# Default Test Performance: Second Tranche

## Goal

Reduce the default `science/` pytest wall-clock time without changing production
behavior, weakening assertions, adding dependencies, or excluding more tests from
the default run.

## Baseline

Fresh deterministic profiling (`-p no:randomly`) found two dominant clusters:

- `tests/test_agent_assets.py`: 151 tests in 106.77 seconds. One complete agent
  distribution generation takes 1.54 seconds; read-only tests repeatedly generate
  the same 53 skills and 40 OpenCode adapters.
- The three budget-regression modules: 73 tests in 180.58 seconds. Repeated health
  collection over the same stress corpus costs 7.6–8.8 seconds per invocation,
  while repeated task-list collection costs 3.1–4.2 seconds per invocation.

Control measurements rule out broad pytest overhead: 1,061 other large-module
tests finish in 14.73 seconds, the 2,141-test model suite finishes in 6.65 seconds,
and enabling `pytest-randomly` does not materially change the representative
sample.

## Design

### 1. Reuse deterministic agent distributions

Make the `generated` and `skills_root` fixtures in `test_agent_assets.py`
module-scoped and build them under `tmp_path_factory`. Replace direct `_generate`
calls in read-only assertion tests with the shared fixture. Tests that exercise
generation failures, pruning, symlink handling, or committed-output equivalence
keep private output trees because mutation is the behavior under test.

The shared tree is immutable by convention: consumers may read paths and bytes but
must not write, remove, or replace anything beneath it.

### 2. Reuse expensive command results for presentation checks

Keep one real stress-corpus execution for each expensive command path. Cache that
result at the narrow test boundary, then use it for the table, JSON, output-file,
projection, and failure-path assertions that exercise presentation rather than
collection.

For health, reuse a completed `HealthExecution` by monkeypatching the existing
`execute_health_report` boundary in presentation-only cases; this is the same
boundary already used by focused health CLI tests. For task listing, preload the
parsed task collection once and patch the existing read boundary in
presentation-only cases. At least one unpatched CLI case per command continues to
prove the real collector-to-renderer integration over the full stress corpus.

No production cache is introduced. Tests of distinct collection options continue
to execute the real collector when the option changes the result.

### 3. Reuse immutable budget corpora

Split each large fixture into a module-scoped corpus created with
`tmp_path_factory` and a function-scoped wrapper that applies transient environment
or working-directory changes with `monkeypatch`. Write command output files to each
test's own `tmp_path`, not into the shared corpus, so test order cannot alter later
collection.

Mutation tests and fixtures whose command changes source records remain
function-scoped. Shared corpora contain only source inputs and are never cleaned or
rewritten by individual tests.

## Regression Guards

- The complete affected modules must pass with randomized ordering disabled and
  enabled.
- Mutation/error-path generation tests retain private trees and continue to prove
  atomicity and user-content preservation.
- Real-corpus command tests continue to prove bounded stdout and complete file
  output; presentation-only cases use the same complete result rather than smaller
  fixtures.
- Repeated timing runs compare the same scoped commands used for the baseline.

## Non-goals

- No `pytest-xdist`, new marker, or default-suite exclusion.
- No production memoization or generator rewrite.
- No reduction in stress-corpus sizes or asserted output counts.

## Verification

Run sequentially from `science/`:

```bash
uv run --frozen pytest -p no:randomly --durations=30 tests/test_agent_assets.py
uv run --frozen pytest -p no:randomly --durations=40 \
  tests/test_budget_regression.py \
  tests/test_budget_regression_reports.py \
  tests/test_budget_regression_rows.py
uv run --frozen pytest tests/test_agent_assets.py \
  tests/test_budget_regression.py \
  tests/test_budget_regression_reports.py \
  tests/test_budget_regression_rows.py
uv run --frozen ruff check
uv run --frozen pyright
uv run --frozen pytest -p no:randomly --durations=60
```

Then run `cd science/model && uv run --frozen pytest -p no:randomly` sequentially.
