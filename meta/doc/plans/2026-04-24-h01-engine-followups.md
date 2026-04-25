# H01 Engine Follow-Ups — Implementation Plan (t001b)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the three engine issues flagged in `meta/doc/plans/2026-04-24-h01-engine-handoff.md` so `[t002]` can run a meaningful full-seed sweep: (1) parameterise the grid in dimensionless terms so no degenerate cells ship; (2) rename `regret` to `signal_count_regret` and document its known decorrelation from recall under shared bias so the interpretation writeup picks the right metric for each claim; (3) parallelise the sweep, switch benchmark calibration to stratified sampling, and re-anchor the runtime gate so it measures honest serial CPU cost.

**Architecture:** All changes are internal to the `h01_simulator` package in `meta/src/`. Grid axis `budgets` becomes `budget_multiples` (floats), scaled to `n_propositions` at grid-build time; cells with `budget <= warmup_actions * n_propositions` are filtered before they enter the sweep. `metrics.regret` is renamed `signal_count_regret` with a docstring caveat about its decorrelation from recall under shared bias; no new metric is introduced (recall already encodes the gap-to-perfect, so a "recall oracle regret" would be a redundant transform — see "Why no companion metric for recall" below). `run_sweep` gains a validated `workers` parameter backed by `ProcessPoolExecutor` and `benchmark_runtime` samples calibration points stratified by `(n_propositions, budget)` buckets — the axes that dominate per-run cost — rather than from a prefix. The 600 s benchmark gate is re-anchored to a serial-CPU-honest budget; wall-clock feasibility (via `--workers`) is `[t002]`'s concern.

**Tech Stack:** Python 3.11+, numpy, polars, click, pytest. No new runtime dependencies. `concurrent.futures.ProcessPoolExecutor` for parallelism.

**Context docs:**
- Handoff note: `meta/doc/plans/2026-04-24-h01-engine-handoff.md`
- Engine plan (completed): `meta/doc/plans/2026-04-24-h01-simulator.md`
- Spec: `meta/specs/h01-simulator.md`
- Hypothesis: `meta/specs/hypotheses/h01-stochastic-revisiting.md`

**Out of scope:** Running the sweep, populating notebook figures, writing the interpretation (all `[t002]`). Adding reference policies (UCB, optimistic-init, annealed revisit, info-gain) — deferred to `[t002]` plan authoring. Gaussian-effect-size variants and other alternative simulator designs from the handoff note — future work. A budget-aware recall oracle (a real, non-redundant companion metric for recall) — defer to `[t002]` if interpretation actually needs it.

**Why no companion metric for recall.** A first cut of this plan added `recall_oracle_regret = oracle_recall - policy_recall`. With perfect knowledge the oracle's recall is always 1.0 when at least one truth-positive exists, so the metric collapses to `1 - recall` — a renamed transform of the primary metric, not an independent corroborator. A genuinely informative recall oracle would have to be budget-aware (e.g. expected fraction of truth-positives whose posterior crosses threshold given optimal allocation under noise + prior). That is real work and arguably premature before the first sweep result. We keep `recall`, `brier`, and `signal_count_regret` (with its caveat) and revisit if `[t002]` interpretation actually needs more.

---

## File Structure

**Modify:**
- `meta/src/h01_simulator/metrics.py` — rename `regret` → `signal_count_regret`; add module + function docstring documenting the metric/oracle taxonomy and the shared-bias decorrelation.
- `meta/src/h01_simulator/config.py` — `RunResult.regret: float` becomes `RunResult.signal_count_regret: float`.
- `meta/src/h01_simulator/sweep.py` — `build_default_grid` uses `budget_multiples` + filters degenerate cells + records `budget_multiple` in output; `run_single` uses the renamed metric; `run_sweep` parallelises via `ProcessPoolExecutor` (validates `workers >= 1`) and writes the renamed regret column and `budget_multiple`; `benchmark_runtime` samples calibration stratified by `(n_propositions, budget)`; `RUNTIME_BUDGET_SECONDS` is re-anchored.
- `meta/src/h01_simulator/cli.py` — re-anchor `RUNTIME_BUDGET_SECONDS` (lives here today); add `--workers` option to `sweep` subcommand using `click.IntRange(min=1)`.
- `meta/src/h01_simulator/__init__.py` — if it currently re-exports `regret`, rename to `signal_count_regret`.
- `meta/tests/test_metrics.py` — rename existing `regret` tests to the new name.
- `meta/tests/test_config.py` — update `RunResult` construction.
- `meta/tests/test_sweep.py` — update parquet schema assertions; add tests for grid filtering, `budget_multiple` recording, stratified calibration sampling, parallel-sweep equivalence (including list columns), `workers` validation.
- `meta/tasks/active.md` — add `[t001b]` entry; update `[t002]`'s `blocked_by`.

**Create:** (none — all changes land in existing modules.)

---

### Task 1: Dimensionless grid with degenerate-cell filtering

**Files:**
- Modify: `meta/src/h01_simulator/sweep.py` — `build_default_grid`, `run_sweep` output schema.
- Modify: `meta/tests/test_sweep.py` — grid-shape assertions, new filter tests.

- [ ] **Step 1: Write the failing test for budget_multiples scaling**

Append to `meta/tests/test_sweep.py`:

```python
def test_build_default_grid_scales_budget_with_n_propositions():
    """Every yielded sim's budget is one of the configured multiples * N."""
    from h01_simulator.sweep import DEFAULT_BUDGET_MULTIPLES, DEFAULT_N_PROPS

    grid = list(build_default_grid(seeds=1, quick=False))
    for sim, _policy in grid:
        expected = {int(k * sim.n_propositions) for k in DEFAULT_BUDGET_MULTIPLES}
        assert sim.budget in expected, (
            f"budget {sim.budget} not in {expected} for n={sim.n_propositions}"
        )
    # Every (N, multiple) combination should appear at least once when non-degenerate.
    seen_pairs = {(sim.n_propositions, sim.budget) for sim, _ in grid}
    for n in DEFAULT_N_PROPS:
        for k in DEFAULT_BUDGET_MULTIPLES:
            b = int(k * n)
            warmup_total = n  # all default policies use warmup_actions=1
            if b > warmup_total:
                assert (n, b) in seen_pairs, f"missing ({n}, {b})"
```

- [ ] **Step 2: Run to confirm it fails**

```
uv run --frozen pytest meta/tests/test_sweep.py::test_build_default_grid_scales_budget_with_n_propositions -v
```
Expected: FAIL — `DEFAULT_BUDGET_MULTIPLES` does not exist yet.

- [ ] **Step 3: Write the failing test for degenerate-cell filtering**

Append to `meta/tests/test_sweep.py`:

```python
def test_build_default_grid_filters_degenerate_cells():
    """No cell should have budget <= warmup_total (budget consumed entirely by warmup)."""
    grid = list(build_default_grid(seeds=1, quick=False))
    for sim, policy in grid:
        warmup_total = policy.warmup_actions * sim.n_propositions
        assert sim.budget > warmup_total, (
            f"degenerate cell: budget={sim.budget}, warmup_total={warmup_total}"
        )
```

- [ ] **Step 4: Run to confirm it fails**

```
uv run --frozen pytest meta/tests/test_sweep.py::test_build_default_grid_filters_degenerate_cells -v
```
Expected: FAIL — current grid yields `n=100, budget=100, warmup=1` cells where `budget == warmup_total`.

- [ ] **Step 5: Write the failing test for budget_multiple recording**

Append to `meta/tests/test_sweep.py`:

```python
def test_run_sweep_records_budget_multiple(tmp_path):
    grid = list(build_default_grid(seeds=1, quick=True))
    df = run_sweep(grid, tmp_path / "sweep.parquet")
    assert "budget_multiple" in df.columns
    for row in df.iter_rows(named=True):
        assert row["budget_multiple"] == pytest.approx(row["budget"] / row["n_props"])
```

- [ ] **Step 6: Run to confirm it fails**

```
uv run --frozen pytest meta/tests/test_sweep.py::test_run_sweep_records_budget_multiple -v
```
Expected: FAIL — `budget_multiple` column does not exist.

- [ ] **Step 7: Implement dimensionless grid**

Replace `build_default_grid` in `meta/src/h01_simulator/sweep.py` with:

```python
DEFAULT_BUDGET_MULTIPLES: tuple[float, ...] = (2.0, 8.0, 32.0)
DEFAULT_N_PROPS: tuple[int, ...] = (20, 100)


def build_default_grid(seeds: int = 100, quick: bool = False) -> Iterator[tuple[SimConfig, PolicyConfig]]:
    """Yield (SimConfig, PolicyConfig) pairs covering the H01 sweep grid.

    Budget is expressed as a multiple of ``n_propositions`` (dimensionless) so
    information-per-proposition is comparable across N. Cells with
    ``budget <= warmup_actions * n_propositions`` are filtered, since they
    leave no post-warmup actions and collapse every policy to the same
    allocation.

    ``quick=True`` shrinks every axis to 1-2 values for smoke-testing.
    """
    if quick:
        noise_pairs = [(0.9, 0.1), (0.6, 0.4)]
        budget_multiples: tuple[float, ...] = (2.0,)
        n_props_values: tuple[int, ...] = (20,)
        prior_true_values = [0.5]
    else:
        noise_pairs = [
            (0.9, 0.1),
            (0.8, 0.2),
            (0.7, 0.3),
            (0.6, 0.4),
            (0.55, 0.45),
        ]
        budget_multiples = DEFAULT_BUDGET_MULTIPLES
        n_props_values = DEFAULT_N_PROPS
        prior_true_values = [0.3, 0.5]

    bias_settings: list[tuple[BiasModel, float, float]] = [
        ("none", 0.0, 0.0),
        ("independent", 0.3, 0.3),
        ("shared", 0.3, 0.3),
    ]

    policies = [
        PolicyConfig(kind="hard_gate", warmup_actions=1, gate_threshold=0.5),
        PolicyConfig(
            kind="constant_revisit",
            warmup_actions=1,
            gate_threshold=0.5,
            revisit_prob=0.1,
        ),
        PolicyConfig(
            kind="constant_revisit",
            warmup_actions=1,
            gate_threshold=0.5,
            revisit_prob=0.3,
        ),
        PolicyConfig(kind="thompson", warmup_actions=1),
    ]

    for p_pos, p_neg in noise_pairs:
        for k in budget_multiples:
            for n in n_props_values:
                budget = int(k * n)
                for prior_true in prior_true_values:
                    for bias_model, bias_fraction, bias_sigma in bias_settings:
                        for seed in range(seeds):
                            sim = SimConfig(
                                n_propositions=n,
                                budget=budget,
                                p_pos=p_pos,
                                p_neg=p_neg,
                                prior_true=prior_true,
                                bias_model=bias_model,
                                bias_fraction=bias_fraction,
                                bias_sigma=bias_sigma,
                                seed=seed,
                            )
                            for policy in policies:
                                warmup_total = policy.warmup_actions * n
                                if budget <= warmup_total:
                                    continue
                                yield sim, policy
```

- [ ] **Step 8: Add `budget_multiple` to the parquet row in `run_sweep`**

In `meta/src/h01_simulator/sweep.py`, in `run_sweep`'s `rows.append({...})`, add immediately after `"budget": sim_cfg.budget,`:

```python
                "budget_multiple": sim_cfg.budget / sim_cfg.n_propositions,
```

- [ ] **Step 9: Update the parquet-column assertion test**

In `meta/tests/test_sweep.py`, the test around line 100-105 asserts the parquet schema. Locate the `expected_columns` tuple/list and add `"budget_multiple"` immediately after `"budget"`.

- [ ] **Step 10: Run the new tests + full sweep suite**

```
uv run --frozen pytest meta/tests/test_sweep.py -v
```
Expected: all pass.

- [ ] **Step 11: Run full quality gates**

```
uv run --frozen ruff check meta/src meta/tests
uv run --frozen ruff format --check meta/src meta/tests
uv run --frozen pyright
uv run --frozen pytest
```
Expected: all pass.

- [ ] **Step 12: Commit**

```
git add meta/src/h01_simulator/sweep.py meta/tests/test_sweep.py
git commit -m "feat(meta/h01-sim): parameterise grid in budget-multiples, filter degenerate cells

Budgets now scale with n_propositions via DEFAULT_BUDGET_MULTIPLES =
(2.0, 8.0, 32.0). Cells where budget <= warmup_actions * N are filtered
at grid-build time so no configuration collapses every policy to identical
allocations. Parquet gains budget_multiple column for axis-aware analysis.

Addresses issue 1 in meta/doc/plans/2026-04-24-h01-engine-handoff.md."
```

---

### Task 2: Rename `regret` → `signal_count_regret` and document the metric/oracle caveat

This task does not introduce a new metric. The handoff note's issue 2 is that the existing `regret` decorrelates from recall under shared bias at high noise — that is fixed by renaming the metric honestly and documenting the regime where it should not be read as recall corroboration. No companion metric is added; see "Why no companion metric for recall" in the plan header.

**Files:**
- Modify: `meta/src/h01_simulator/metrics.py` — rename, expand docstring.
- Modify: `meta/src/h01_simulator/config.py` — rename `RunResult.regret` field.
- Modify: `meta/src/h01_simulator/sweep.py` — update import and `run_single`/`run_sweep` references.
- Modify: `meta/src/h01_simulator/__init__.py` — if it re-exports `regret`, rename.
- Modify: `meta/tests/test_metrics.py` — rename tests + import.
- Modify: `meta/tests/test_config.py` — update `RunResult` construction.
- Modify: `meta/tests/test_sweep.py` — update column and field assertions.

- [ ] **Step 1: Rename `regret` → `signal_count_regret` in `metrics.py`**

Replace `meta/src/h01_simulator/metrics.py` with:

```python
"""End-of-run metrics for the h01 simulator.

Metric / oracle taxonomy
------------------------
Each metric implies a particular "best achievable" baseline (an oracle).
A policy that mimics one oracle may score badly on a metric defined against
a different oracle. Pick the metric matched to the claim under test and
read others as diagnostics, not corroboration.

- ``recall`` — fraction of truth-positives with ``posterior_mean >= threshold``.
  Already a gap-to-perfect (oracle recall is 1.0 when positives exist), so
  no separate "recall regret" is reported. A budget-aware recall oracle
  would be a meaningful companion metric but is deferred until interpretation
  needs it.
- ``brier`` — mean squared error of posterior mean against ground truth.
  Oracle is perfect calibration (mean = truth); reported directly, not as
  a regret.
- ``signal_count_regret`` — ``oracle - policy`` expected signal count, where
  the oracle allocates the whole budget to the proposition with the highest
  effective signal probability. WARNING: under ``bias_model="shared"`` at
  high noise, bias offsets can push a truth=0 proposition's effective
  probability above every truth=1, so this oracle targets a false
  proposition. A policy that mimics the oracle then scores
  ``signal_count_regret = 0`` and ``recall = 0`` — i.e. the metric
  decorrelates from recall in exactly the regime H01's disconfirmation route
  occupies. Treat as a diagnostic, NOT as recall corroboration in ``shared``
  rows.
"""

from __future__ import annotations

import math

import numpy as np

from .config import SimConfig


def recall(truth: np.ndarray, posterior_mean: np.ndarray, threshold: float = 0.5) -> float:
    """Fraction of truth=1 propositions with posterior_mean >= threshold.

    NaN when there are no ground-truth positives.
    """
    positives = truth == 1
    n_pos = int(positives.sum())
    if n_pos == 0:
        return math.nan
    predicted = posterior_mean >= threshold
    return float((positives & predicted).sum() / n_pos)


def brier(truth: np.ndarray, posterior_mean: np.ndarray) -> float:
    """Mean squared error of posterior mean vs binary ground truth."""
    return float(np.mean((posterior_mean - truth.astype(float)) ** 2))


def signal_count_regret(
    truth: np.ndarray,
    bias_offsets: np.ndarray,
    allocations: np.ndarray,
    config: SimConfig,
) -> float:
    """Oracle-minus-policy expected signal count over the run.

    Effective per-proposition signal probability is
    ``clip((p_pos if truth=1 else p_neg) + bias_offsets, 0, 1)``.
    Oracle allocates the whole budget to the highest-probability proposition.

    KNOWN LIMITATION: under ``bias_model="shared"`` at high noise, the oracle
    may target a truth=0 proposition whose bias-inflated effective probability
    exceeds every truth=1 proposition. In that regime this metric and recall
    decorrelate — see module docstring. Read as a diagnostic, not as recall
    corroboration in ``shared`` rows.
    """
    base = np.where(truth == 1, config.p_pos, config.p_neg)
    effective = np.clip(base + bias_offsets, 0.0, 1.0)
    total_budget = float(allocations.sum())
    oracle = float(effective.max()) * total_budget
    policy = float((effective * allocations).sum())
    return oracle - policy
```

- [ ] **Step 2: Update `RunResult` field name**

In `meta/src/h01_simulator/config.py`, replace the `RunResult` dataclass with:

```python
@dataclass
class RunResult:
    """Result of one simulator run."""

    config: SimConfig
    policy: PolicyConfig
    recall: float
    brier: float
    signal_count_regret: float
    allocations: np.ndarray
    final_posteriors: np.ndarray
    ground_truth: np.ndarray
    bias_offsets: np.ndarray
```

- [ ] **Step 3: Update `run_single` import and `RunResult` construction**

In `meta/src/h01_simulator/sweep.py`:
- Replace `from .metrics import brier, recall, regret` with `from .metrics import brier, recall, signal_count_regret`.
- In `run_single`, replace the `RunResult(...)` construction with:

```python
    return RunResult(
        config=sim_config,
        policy=policy_config,
        recall=recall(props.truth, post_mean),
        brier=brier(props.truth, post_mean),
        signal_count_regret=signal_count_regret(props.truth, props.bias_offsets, allocations, sim_config),
        allocations=allocations,
        final_posteriors=np.stack([model.alpha, model.beta], axis=1),
        ground_truth=props.truth,
        bias_offsets=props.bias_offsets,
    )
```

- [ ] **Step 4: Update `run_sweep`'s parquet row**

In `meta/src/h01_simulator/sweep.py`, in `run_sweep`, replace the line:

```python
                "regret": r.regret,
```

with:

```python
                "signal_count_regret": r.signal_count_regret,
```

- [ ] **Step 5: Update `__init__.py` re-exports**

Open `meta/src/h01_simulator/__init__.py`. If it currently re-exports `regret`, rename to `signal_count_regret`. If `__all__` is empty, leave it as is — metrics are imported through the submodule.

- [ ] **Step 6: Update `test_metrics.py`**

In `meta/tests/test_metrics.py`:
- Change `from h01_simulator.metrics import brier, recall, regret` to `from h01_simulator.metrics import brier, recall, signal_count_regret`.
- Rename function `test_regret_oracle_allocation_is_zero` → `test_signal_count_regret_oracle_allocation_is_zero` and replace `regret(` with `signal_count_regret(`.
- Rename `test_regret_positive_when_budget_on_false_props` → `test_signal_count_regret_positive_when_budget_on_false_props`, update call.
- Rename `test_regret_uses_per_proposition_offsets` → `test_signal_count_regret_uses_per_proposition_offsets`, update call.
- Rename `test_regret_clips_effective_probability_to_unit_interval` → `test_signal_count_regret_clips_effective_probability_to_unit_interval`, update call.

- [ ] **Step 7: Update `test_config.py` `RunResult` construction**

In `meta/tests/test_config.py` around line 96, replace `regret=1.0,` with:

```python
        signal_count_regret=1.0,
```

- [ ] **Step 8: Update `test_sweep.py` field and column assertions**

In `meta/tests/test_sweep.py`:
- Around line 25-26, replace `assert r.regret >= -1e-9` with `assert r.signal_count_regret >= -1e-9`.
- Around line 103, replace `"regret",` in the expected-columns tuple/list with `"signal_count_regret",`.

- [ ] **Step 9: Run full metrics + sweep + config tests**

```
uv run --frozen pytest meta/tests/test_metrics.py meta/tests/test_sweep.py meta/tests/test_config.py -v
```
Expected: all pass.

- [ ] **Step 10: Run full quality gates**

```
uv run --frozen ruff check meta/src meta/tests
uv run --frozen ruff format --check meta/src meta/tests
uv run --frozen pyright
uv run --frozen pytest
```
Expected: all pass.

- [ ] **Step 11: Commit**

```
git add meta/src/h01_simulator/metrics.py meta/src/h01_simulator/config.py \
        meta/src/h01_simulator/sweep.py meta/src/h01_simulator/__init__.py \
        meta/tests/test_metrics.py meta/tests/test_sweep.py meta/tests/test_config.py
git commit -m "refactor(meta/h01-sim): rename regret to signal_count_regret + document caveat

Renames regret -> signal_count_regret. Adds module-level metric/oracle
taxonomy and a function-level KNOWN LIMITATION block flagging that
signal_count_regret decorrelates from recall under bias_model=shared at
high noise, exactly where H01's disconfirmation route lives. Reading this
as recall corroboration in those rows would be misleading.

No companion metric for recall is added: a 1 - recall transform carries
no new information, and a budget-aware recall oracle is real work to be
deferred until [t002] interpretation needs it.

Addresses issue 2 in meta/doc/plans/2026-04-24-h01-engine-handoff.md."
```

---

### Task 3: Parallel sweep, stratified calibration, re-anchored runtime gate

**Files:**
- Modify: `meta/src/h01_simulator/sweep.py` — add validated `workers` param to `run_sweep`; stratified `_select_calibration_slice`; uniform sampling in `benchmark_runtime`.
- Modify: `meta/src/h01_simulator/cli.py` — `--workers` option for `sweep` (`click.IntRange(min=1)`); re-anchor `RUNTIME_BUDGET_SECONDS`.
- Modify: `meta/tests/test_sweep.py` — parallel-equivalence test (incl. list columns), stratified-calibration test, validation tests.

- [ ] **Step 1: Write the failing test for parallel equivalence (compares all columns)**

Append to `meta/tests/test_sweep.py`:

```python
def test_run_sweep_parallel_matches_serial(tmp_path):
    """workers>1 must produce identical rows including list columns (order-insensitive)."""
    grid_serial = list(build_default_grid(seeds=2, quick=True))
    grid_parallel = list(build_default_grid(seeds=2, quick=True))
    df_serial = run_sweep(grid_serial, tmp_path / "serial.parquet", workers=1)
    df_parallel = run_sweep(grid_parallel, tmp_path / "parallel.parquet", workers=2)

    key_cols = ["policy", "revisit_prob", "n_props", "budget", "p_pos", "p_neg",
                "prior_true", "bias_model", "seed"]
    a = df_serial.sort(key_cols)
    b = df_parallel.sort(key_cols)

    # Scalar columns: direct frame equality after dropping list columns.
    list_cols = ["allocations", "final_alpha", "final_beta", "ground_truth"]
    assert a.drop(list_cols).equals(b.drop(list_cols))

    # List columns: row-by-row equality (polars list equality is well-defined for fixed seeds).
    for col in list_cols:
        assert a[col].to_list() == b[col].to_list(), f"list column {col} differs"


def test_run_sweep_rejects_invalid_workers(tmp_path):
    grid = list(build_default_grid(seeds=1, quick=True))
    with pytest.raises(ValueError, match="workers"):
        run_sweep(grid, tmp_path / "x.parquet", workers=0)
    with pytest.raises(ValueError, match="workers"):
        run_sweep(grid, tmp_path / "x.parquet", workers=-1)
```

- [ ] **Step 2: Run to confirm failure**

```
uv run --frozen pytest meta/tests/test_sweep.py::test_run_sweep_parallel_matches_serial meta/tests/test_sweep.py::test_run_sweep_rejects_invalid_workers -v
```
Expected: FAIL — `run_sweep` does not accept `workers`.

- [ ] **Step 3: Write the failing test for stratified calibration sampling**

Append to `meta/tests/test_sweep.py`:

```python
def test_select_calibration_slice_stratifies_by_n_props_and_budget():
    """Calibration slice must (a) cover every (n_props, budget) bucket and
    (b) keep per-bucket counts within +/-1 of the base quota."""
    from collections import Counter

    from h01_simulator.sweep import _select_calibration_slice

    full = list(build_default_grid(seeds=1, quick=False))
    bucket_keys = {(sim.n_propositions, sim.budget) for sim, _ in full}

    n_calibration_runs = 200
    calibration = _select_calibration_slice(full, n_calibration_runs=n_calibration_runs)

    # (a) coverage
    seen = {(sim.n_propositions, sim.budget) for sim, _ in calibration}
    assert seen == bucket_keys

    # (b) roughly-equal counts: each bucket has either base_quota or base_quota + 1
    counts = Counter((sim.n_propositions, sim.budget) for sim, _ in calibration)
    n_buckets = len(bucket_keys)
    base_quota = n_calibration_runs // n_buckets
    for key in bucket_keys:
        assert counts[key] in (base_quota, base_quota + 1), (
            f"bucket {key} got {counts[key]}, expected {base_quota} or {base_quota + 1}"
        )


def test_select_calibration_slice_rejects_non_positive_n():
    from h01_simulator.sweep import _select_calibration_slice

    pairs = list(build_default_grid(seeds=1, quick=True))
    with pytest.raises(ValueError, match="n_calibration_runs"):
        _select_calibration_slice(pairs, n_calibration_runs=0)
    with pytest.raises(ValueError, match="n_calibration_runs"):
        _select_calibration_slice(pairs, n_calibration_runs=-5)
```

- [ ] **Step 4: Run to confirm failure**

```
uv run --frozen pytest meta/tests/test_sweep.py::test_select_calibration_slice_stratifies_by_n_props_and_budget meta/tests/test_sweep.py::test_select_calibration_slice_rejects_non_positive_n -v
```
Expected: FAIL — `_select_calibration_slice` does not exist.

- [ ] **Step 5: Implement parallel sweep + stratified calibration**

In `meta/src/h01_simulator/sweep.py`:

Add to imports:

```python
from concurrent.futures import ProcessPoolExecutor
```

Add helpers and replace `run_sweep`:

```python
def _row_from_result(r: RunResult) -> dict[str, object]:
    sim_cfg = r.config
    pol_cfg = r.policy
    return {
        "policy": pol_cfg.kind,
        "revisit_prob": pol_cfg.revisit_prob,
        "warmup_actions": pol_cfg.warmup_actions,
        "gate_threshold": pol_cfg.gate_threshold,
        "n_props": sim_cfg.n_propositions,
        "budget": sim_cfg.budget,
        "budget_multiple": sim_cfg.budget / sim_cfg.n_propositions,
        "p_pos": sim_cfg.p_pos,
        "p_neg": sim_cfg.p_neg,
        "prior_true": sim_cfg.prior_true,
        "prior_alpha": sim_cfg.prior_alpha,
        "prior_beta": sim_cfg.prior_beta,
        "bias_model": sim_cfg.bias_model,
        "bias_fraction": sim_cfg.bias_fraction,
        "bias_sigma": sim_cfg.bias_sigma,
        "seed": sim_cfg.seed,
        "recall": r.recall,
        "brier": r.brier,
        "signal_count_regret": r.signal_count_regret,
        "allocations": r.allocations.tolist(),
        "final_alpha": r.final_posteriors[:, 0].tolist(),
        "final_beta": r.final_posteriors[:, 1].tolist(),
        "ground_truth": r.ground_truth.astype(int).tolist(),
    }


def _run_one(pair: tuple[SimConfig, PolicyConfig]) -> RunResult:
    sim_cfg, pol_cfg = pair
    return run_single(sim_cfg, pol_cfg)


def run_sweep(
    grid: Iterable[tuple[SimConfig, PolicyConfig]],
    out_path: Path,
    workers: int = 1,
) -> pl.DataFrame:
    """Run every (sim, policy) pair and write a tidy parquet with list columns.

    ``workers=1`` runs serially in the caller's process. ``workers>1`` uses a
    ``ProcessPoolExecutor``. Runs are pure functions of their inputs (seeds
    are encoded in ``SimConfig``), so parallel and serial outputs are
    order-insensitive equivalent (including list columns).

    Raises ``ValueError`` for ``workers < 1`` — silent fallback to serial would
    hide a misconfigured CLI invocation.
    """
    if workers < 1:
        raise ValueError(f"workers must be >= 1, got {workers}")
    pairs = list(grid)
    if workers == 1:
        results = [_run_one(p) for p in pairs]
    else:
        with ProcessPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(_run_one, pairs))
    rows = [_row_from_result(r) for r in results]
    df = pl.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path)
    return df
```

Note: remove the old inline row-building loop in `run_sweep` (now lives in `_row_from_result`).

Replace `benchmark_runtime` and add `_select_calibration_slice`:

```python
def _select_calibration_slice(
    pairs: list[tuple[SimConfig, PolicyConfig]],
    n_calibration_runs: int,
) -> list[tuple[SimConfig, PolicyConfig]]:
    """Pick ``n_calibration_runs`` pairs stratified by (n_propositions, budget).

    Per-run cost is dominated by ``n_propositions * budget``; stratifying on
    that pair guarantees the calibration slice spans cheap and expensive
    cells in proportion. Within each bucket, pairs are taken at evenly-
    spaced indices so policy/bias variation is also represented.

    Raises ``ValueError`` for non-positive ``n_calibration_runs``.
    """
    if n_calibration_runs <= 0:
        raise ValueError(f"n_calibration_runs must be positive, got {n_calibration_runs}")
    if n_calibration_runs >= len(pairs):
        return list(pairs)

    buckets: dict[tuple[int, int], list[tuple[SimConfig, PolicyConfig]]] = {}
    for sim, pol in pairs:
        buckets.setdefault((sim.n_propositions, sim.budget), []).append((sim, pol))

    bucket_keys = sorted(buckets.keys())
    n_buckets = len(bucket_keys)
    base_quota = n_calibration_runs // n_buckets
    remainder = n_calibration_runs - base_quota * n_buckets

    chosen: list[tuple[SimConfig, PolicyConfig]] = []
    for i, key in enumerate(bucket_keys):
        bucket = buckets[key]
        quota = base_quota + (1 if i < remainder else 0)
        if quota >= len(bucket):
            chosen.extend(bucket)
            continue
        idx = np.linspace(0, len(bucket) - 1, num=quota, dtype=int)
        seen: set[int] = set()
        for j in idx:
            jj = int(j)
            if jj in seen:
                continue
            seen.add(jj)
            chosen.append(bucket[jj])
    return chosen


def benchmark_runtime(
    n_calibration_runs: int = 200,
    seeds_for_full_grid: int = 100,
) -> BenchmarkReport:
    """Time a slice of default-grid runs and extrapolate to the full grid.

    Calibration pairs are sampled stratified by (n_propositions, budget) —
    the axes that dominate per-run cost — so the timing slice covers cheap
    and expensive cells in proportion rather than concentrating in the grid
    prefix. Extrapolation is still linear; this change makes the per-run
    estimate representative.
    """
    all_pairs = list(build_default_grid(seeds=1, quick=False))
    calibration = _select_calibration_slice(all_pairs, n_calibration_runs)

    start = time.perf_counter()
    for sim_cfg, pol_cfg in calibration:
        run_single(sim_cfg, pol_cfg)
    elapsed = time.perf_counter() - start

    full_grid_runs = sum(1 for _ in build_default_grid(seeds=seeds_for_full_grid, quick=False))
    projected = elapsed * (full_grid_runs / max(len(calibration), 1))

    return BenchmarkReport(
        n_calibration_runs=len(calibration),
        elapsed_seconds_calibration=elapsed,
        projected_full_grid_seconds=projected,
        projected_full_grid_runs=full_grid_runs,
    )
```

- [ ] **Step 6: Add validated `--workers` to the sweep CLI**

In `meta/src/h01_simulator/cli.py`, replace the `sweep` command with:

```python
@main.command()
@click.option(
    "--out",
    type=click.Path(path_type=Path),
    default=None,
    help="Output parquet path. Defaults to results/h01-simulator/sweep-YYYY-MM-DD.parquet.",
)
@click.option("--seeds", type=int, default=100, help="Seeds per configuration cell.")
@click.option(
    "--quick",
    is_flag=True,
    help="Run a small smoke grid instead of the full sweep.",
)
@click.option(
    "--workers",
    type=click.IntRange(min=1),
    default=1,
    help="Number of worker processes (1 = serial). Must be >= 1.",
)
def sweep(out: Path | None, seeds: int, quick: bool, workers: int) -> None:
    """Run the H01 simulator sweep and write tidy results to parquet."""
    if out is None:
        out = Path("results/h01-simulator") / f"sweep-{date.today().isoformat()}.parquet"
    grid = list(build_default_grid(seeds=seeds, quick=quick))
    click.echo(f"Running {len(grid)} configurations on {workers} worker(s)...")
    df = run_sweep(grid, out, workers=workers)
    click.echo(f"Wrote {df.height} rows to {out}")
```

- [ ] **Step 7: Run all sweep tests (new + existing)**

```
uv run --frozen pytest meta/tests/test_sweep.py -v
```
Expected: all pass, including parallel-equivalence (with list columns), stratified calibration, and validation tests.

- [ ] **Step 8: Re-time the benchmark and re-anchor `RUNTIME_BUDGET_SECONDS`**

The benchmark gate measures honest **serial CPU time**. After Task 1's grid changes (heavier average cell from `(2.0, 8.0, 32.0)` budget multiples), the projected serial runtime will differ from the previously-reported 988 s. The right gate budget is one that says "this is the engine's serial CPU cost; meeting wall-clock targets via `--workers` is `[t002]`'s problem."

Run:

```
uv run --frozen h01-sim benchmark --seeds 100
```

Note the projected serial seconds. Then in `meta/src/h01_simulator/cli.py`, replace:

```python
RUNTIME_BUDGET_SECONDS = 10 * 60  # single-digit minutes per specs/h01-simulator.md
```

with a budget chosen as **ceil(measured_projection / 60) * 60 + 60**, capped at 1800 s (30 minutes serial). For example, if the projection is 1180 s, set the budget to `1240`. If the projection exceeds 1800 s, do **not** keep raising the budget — instead tighten the grid (drop a budget multiple or trim noise pairs) and re-time. The point of the gate is to keep the engine honest.

Replace the constant with:

```python
RUNTIME_BUDGET_SECONDS = <chosen_value>  # serial CPU; --workers reduces wall-clock for [t002]
```

Adjust the comment to record the rationale: e.g. `# 1240s serial; covers Task-1 grid shape + ~5% margin`.

Also update the help text on `benchmark`'s `--budget-seconds` if needed; it already references the constant, so updating the constant suffices.

- [ ] **Step 9: Re-run the benchmark to confirm gate passes**

```
uv run --frozen h01-sim benchmark --seeds 100
```
Expected: no `ClickException`, projection prints under the new budget. If it fails, do not raise the budget further — go back to Step 8 and tighten the grid instead.

- [ ] **Step 10: Run full quality gates**

```
uv run --frozen ruff check meta/src meta/tests
uv run --frozen ruff format --check meta/src meta/tests
uv run --frozen pyright
uv run --frozen pytest
bash meta/validate.sh --verbose
```
Expected: all pass.

- [ ] **Step 11: Commit**

```
git add meta/src/h01_simulator/sweep.py meta/src/h01_simulator/cli.py meta/tests/test_sweep.py
git commit -m "feat(meta/h01-sim): parallel sweep, stratified calibration, re-anchored gate

run_sweep accepts workers>=1 and dispatches via ProcessPoolExecutor;
sweep CLI exposes --workers (click.IntRange(min=1), no silent fallback).
benchmark_runtime samples calibration stratified by (n_propositions,
budget) so the projection is representative of heavy cells, not the grid
prefix. RUNTIME_BUDGET_SECONDS re-anchored to honest serial CPU cost
after the Task-1 grid shape; wall-clock feasibility via --workers is
[t002]'s problem.

Output is order-insensitive identical between serial and parallel for a
given grid + seed set, including list columns (allocations, final_alpha,
final_beta, ground_truth).

Addresses issue 3 in meta/doc/plans/2026-04-24-h01-engine-handoff.md."
```

---

### Task 4: Close `[t001b]` in the task backlog

**Files:**
- Modify: `meta/tasks/active.md`.

- [ ] **Step 1: Add `[t001b]` with status `done`**

Insert between `[t001]` and `[t002]` in `meta/tasks/active.md`:

```markdown
## [t001b] H01 engine follow-ups (grid, metrics, parallelism)
- type: implementation
- priority: P1
- status: done
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t001]
- created: 2026-04-24

Resolve the three engine issues flagged in `meta/doc/plans/2026-04-24-h01-engine-handoff.md`: (1) parameterise the default grid in dimensionless budget-multiples with degenerate-cell filtering; (2) rename `regret` to `signal_count_regret` and document its decorrelation from recall under shared bias at high noise (no companion metric added; a budget-aware recall oracle is deferred until interpretation needs it); (3) parallelise `run_sweep` via `ProcessPoolExecutor` with validated `workers >= 1`, sample `benchmark_runtime` calibration stratified by `(n_propositions, budget)`, and re-anchor `RUNTIME_BUDGET_SECONDS` to honest serial CPU. Plan: `meta/doc/plans/2026-04-24-h01-engine-followups.md`. Unblocks [t002].
```

Also update `[t002]`'s `blocked_by` from `[t001]` to `[t001b]`.

- [ ] **Step 2: Commit**

```
git add meta/tasks/active.md
git commit -m "docs(meta): close [t001b] H01 engine follow-ups; unblock [t002]"
```

---

## Self-Review Checklist

- [x] Every issue from the handoff note has an owning task (1, 2, 3).
- [x] No placeholder steps — every code-step includes the full code.
- [x] Type / name consistency: `signal_count_regret` used uniformly across `metrics.py`, `RunResult`, `sweep.py` row-builder, parquet column, and tests. `DEFAULT_BUDGET_MULTIPLES` / `DEFAULT_N_PROPS` referenced consistently.
- [x] Each task ends with full quality gates (ruff, pyright, pytest) before committing.
- [x] `[t001b]` task entry added + `[t002]` unblocked.
- [x] Out-of-scope items (reference policies, Gaussian variant, alternative framings, budget-aware recall oracle) explicitly excluded in the Goal / Out of Scope section, with rationale.
- [x] All file references and commit-message references use `meta/...` paths so agents resolve them from any cwd.
- [x] No silent fallbacks: `workers < 1` raises in `run_sweep`; `n_calibration_runs <= 0` raises in `_select_calibration_slice`; CLI uses `click.IntRange(min=1)`.
- [x] Parallel-equivalence test compares list columns too, not only scalar columns.
- [x] Calibration sampling is explicitly stratified (deterministic per-bucket quotas), not implicit `np.linspace` over linearised order.
- [x] Runtime gate semantics are unambiguous: serial CPU only, no `--workers` interaction with the gate.
