# Default Test Performance: Second Tranche

## Goal

Reduce the default `science/` pytest wall-clock time without changing production
behavior, weakening assertions, adding dependencies, or excluding more tests from
the default run.

## Baseline

Fresh deterministic profiling (`-p no:randomly`) found two dominant clusters:

- `tests/test_agent_assets.py`: 151 tests in 106.77 seconds. One complete agent
  distribution generation takes 1.05–1.09 seconds at steady state; 51 fixture
  consumers plus 28 direct `_generate(tmp_path)` calls account for about 84
  seconds of the module.
- The three budget-regression modules: 73 tests in 180.58 seconds. Repeated health
  collection over the same stress corpus costs 7.6–8.8 seconds per invocation,
  while repeated task-list collection costs 3.1–4.2 seconds per invocation.
- Building the shared `test_budget_regression.py` corpus takes 0.59 seconds. The
  32 cases that use it therefore spend about 19 seconds on construction, only
  about 11% of the three-module budget cluster.

Control measurements rule out broad pytest overhead: 1,061 other large-module
tests finish in 14.73 seconds, the 2,141-test model suite finishes in 6.65 seconds,
and enabling `pytest-randomly` does not materially change the representative
sample.

## Design

### 1. Reuse expensive command results for presentation checks

Cache the first real collector call for each distinct set of collection inputs,
then reuse that complete result for the remaining table, JSON, output-file,
projection, and failure-path invocations. In `test_budget_regression.py` the
cache survives across tests that share the module corpus; in the reports module
it lives only for the current inline corpus. The first call through every cache
key invokes the real collector over the full corpus; no synthetic small report
may stand in for it.

The cache wrappers live in the test modules and patch these existing read or
collection boundaries:

- health: `science_tool.graph.health.execute_health_report`;
- task listing: `science_tool.tasks._read_active`, returning a fresh list around
  the cached tasks for each caller;
- prose lint: `science_tool.prose_lint_cli.scan_root`;
- curate inventory: `science_tool.curate.cli.collect_inventory`;
- consolidation candidates:
  `science_tool.consolidation_candidates.detect_consolidation_candidates`
  (imported inside the CLI callback, so patch the defining module);
- validate: `science_tool.validate.cli.run`.

The four tests in `test_budget_regression_reports.py` build corpora inline, so
fixture sharing cannot help them. Their shared `_assert_report_projection`
helper currently invokes the same command four times: JSON file, JSON stdout,
table stdout, and table file. Each test will install a cache wrapper around its
named boundary before calling the helper. The helper therefore continues to
exercise all four complete CLI paths while only the first path performs the
real corpus scan.

`tasks list` currently reads the 400-task active store twice per invocation:
`list_tasks(...)` reads it for results, then `parse_tasks_for_cli(...)` reads it
again for legacy-blocker warnings. Both paths funnel through `_read_active`, so
patching that boundary preserves Python-side filtering for `--status`,
`--priority`, `--related`, and the other list options. The duplicate production
read remains recorded as a separate optimization opportunity; this tranche does
not change production behavior.

Health reuse follows the same constraint: the cached `HealthExecution` must be
produced by the first real `science health` run over the module's unchanged
400-task, 300-question, 3,000-data-file corpus. Existing focused tests that inject
hand-built reports prove CLI mechanics but are not substitutes for this budget
ceiling guard.

No production cache is introduced. Tests whose options change collection inputs
rather than only filtering or presentation keep independent cache keys or execute
the real collector.

### 2. Reuse deterministic agent distributions

Make the `generated` and `skills_root` fixtures in `test_agent_assets.py`
module-scoped and build them under `tmp_path_factory`. Replace direct `_generate`
calls in read-only assertion tests with the shared fixture. Tests that exercise
generation failures, pruning, symlink handling, or committed-output equivalence
keep private output trees because mutation is the behavior under test.

The current consumers were AST-scanned for writes beneath the shared tree. None
mutates it. The one apparent hit creates a symlink from its private `tmp_path`
into the shared tree and only reads through that link. Mutation tests continue to
use private generations.

### 3. Reuse only the shared `project` budget corpus

Narrow corpus reuse to the `project` fixture in `test_budget_regression.py`; do
not generalize it to the 14 small overflow fixtures or to
`test_budget_regression_reports.py`, whose corpora are inline and whose time is
dominated by four command invocations per test.

Build the 3,701-file source corpus once with a module-scoped fixture created via
`tmp_path_factory`. Keep a function-scoped `project` wrapper that applies the
working-directory change with `monkeypatch`. Every `--output` target moves to the
test's own function-scoped `tmp_path` so generated reports cannot become inputs to
later scans.

The current commands are not literally read-only: each CLI invocation appends a
telemetry event under `SCIENCE_CONFIG_DIR`. Three interleaved health, task,
inventory, and data-audit rounds over one corpus nevertheless produced identical
totals on every round (1,024 findings, 701 entities, and 3,703 violations). In the
revised fixture, the existing autouse config isolation places telemetry under the
function-scoped temp root, outside the shared source corpus. Together with
per-test output paths, this makes shared-source reuse a verified property of these
commands rather than a convention imposed on test authors.

This priority is expected to save only about 19 seconds. It ships after command
result reuse and agent-distribution reuse, and is retained only if randomized-order
verification remains clean.

## Regression Guards

- The complete affected modules must pass with randomized ordering disabled and
  enabled.
- Mutation/error-path generation tests retain private trees and continue to prove
  atomicity and user-content preservation.
- Real-corpus command tests continue to prove bounded stdout and complete file
  output; presentation-only cases use the same complete result rather than smaller
  fixtures.
- Repeated timing runs compare the same scoped commands used for the baseline.

## Success Targets

On this Dropbox-backed checkout, using three sequential deterministic runs and
comparing their median:

- `test_agent_assets.py`: at most 35 seconds, down from 106.77 seconds;
- the three budget-regression modules: at most 90 seconds, down from 180.58
  seconds;
- the full default `science/` suite: at most 8 minutes, down from the documented
  approximately 10 minutes.

The test counts must remain 151 for agent assets and 73 for the budget cluster.
Randomized-order runs must produce the same counts and no failures.

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
