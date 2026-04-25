from typing import Any

import numpy as np
import polars as pl
import pytest

from h01_simulator.config import PolicyConfig, SimConfig
from h01_simulator.sweep import benchmark_runtime, build_default_grid, run_single, run_sweep


def _sim(**overrides: Any) -> SimConfig:
    base: dict[str, Any] = dict(n_propositions=10, budget=50, p_pos=0.8, p_neg=0.2, prior_true=0.5, seed=0)
    base.update(overrides)
    return SimConfig(**base)


def test_run_single_returns_result_record_with_expected_shapes():
    r = run_single(_sim(), PolicyConfig(kind="thompson"))
    assert r.allocations.sum() == 50
    assert r.allocations.shape == (10,)
    assert r.final_posteriors.shape == (10, 2)
    assert r.ground_truth.shape == (10,)
    assert r.bias_offsets.shape == (10,)
    assert 0.0 <= r.brier <= 1.0
    # signal_count_regret is non-negative within float tolerance
    assert r.signal_count_regret >= -1e-9


def test_run_single_deterministic_given_seed():
    a = run_single(_sim(seed=42), PolicyConfig(kind="thompson"))
    b = run_single(_sim(seed=42), PolicyConfig(kind="thompson"))
    assert np.array_equal(a.allocations, b.allocations)
    assert np.array_equal(a.final_posteriors, b.final_posteriors)
    assert np.array_equal(a.ground_truth, b.ground_truth)
    assert a.recall == b.recall or (np.isnan(a.recall) and np.isnan(b.recall))
    assert a.brier == b.brier


@pytest.mark.parametrize("kind", ["hard_gate", "constant_revisit", "thompson"])
def test_run_single_dispatches_every_policy_kind(kind):
    r = run_single(
        _sim(),
        PolicyConfig(kind=kind, warmup_actions=1, revisit_prob=0.1),
    )
    assert r.allocations.sum() == 50


def test_run_single_respects_configured_prior():
    sim = _sim(prior_alpha=5.0, prior_beta=5.0, budget=0)
    r = run_single(sim, PolicyConfig(kind="thompson"))
    # With budget=0 no observations happen; posteriors stay at the prior.
    assert np.allclose(r.final_posteriors[:, 0], 5.0)
    assert np.allclose(r.final_posteriors[:, 1], 5.0)


def test_run_single_integrates_with_shared_bias():
    sim = _sim(bias_model="shared", bias_fraction=0.3, bias_sigma=0.3, seed=1)
    r = run_single(sim, PolicyConfig(kind="thompson"))
    # Smoke: run terminates, shapes are correct, at least some bias offsets non-zero.
    assert r.allocations.sum() == 50
    assert r.bias_offsets.shape == (10,)
    assert np.count_nonzero(r.bias_offsets) >= 1


def test_build_default_grid_is_nonempty():
    grid = list(build_default_grid(seeds=3, quick=True))
    assert len(grid) > 0
    for sim_cfg, pol_cfg in grid:
        assert isinstance(sim_cfg, SimConfig)
        assert isinstance(pol_cfg, PolicyConfig)


def test_build_default_grid_covers_all_bias_modes():
    grid = list(build_default_grid(seeds=1, quick=True))
    seen = {s.bias_model for s, _ in grid}
    assert {"none", "independent", "shared"} <= seen


def test_run_sweep_writes_parquet_with_list_columns(tmp_path):
    grid = list(build_default_grid(seeds=2, quick=True))
    out_path = tmp_path / "sweep.parquet"
    df = run_sweep(grid, out_path)
    assert out_path.exists()
    assert df.height == len(grid)
    expected_scalars = {
        "policy",
        "revisit_prob",
        "warmup_actions",
        "ucb_c",
        "gate_threshold",
        "n_props",
        "budget",
        "budget_multiple",
        "p_pos",
        "p_neg",
        "prior_true",
        "prior_alpha",
        "prior_beta",
        "bias_model",
        "bias_fraction",
        "bias_sigma",
        "seed",
        "recall",
        "brier",
        "signal_count_regret",
    }
    expected_lists = {"allocations", "final_alpha", "final_beta", "ground_truth"}
    assert expected_scalars.issubset(set(df.columns))
    assert expected_lists.issubset(set(df.columns))
    # list columns round-trip
    loaded = pl.read_parquet(out_path)
    first = loaded.row(0, named=True)
    assert isinstance(first["allocations"], list)
    assert isinstance(first["final_alpha"], list)
    assert len(first["allocations"]) == first["n_props"]
    assert len(first["final_alpha"]) == first["n_props"]


def test_run_sweep_output_round_trip(tmp_path):
    grid = list(build_default_grid(seeds=2, quick=True))
    out_path = tmp_path / "sweep.parquet"
    run_sweep(grid, out_path)
    loaded = pl.read_parquet(out_path)
    assert loaded.height > 0


def test_benchmark_runtime_returns_extrapolation():
    report = benchmark_runtime(n_calibration_runs=20, seeds_for_full_grid=5)
    assert report.n_calibration_runs == 20
    assert report.elapsed_seconds_calibration > 0.0
    assert report.projected_full_grid_seconds > 0.0
    assert report.projected_full_grid_seconds >= report.elapsed_seconds_calibration


def test_build_default_grid_scales_budget_with_n_propositions():
    """Every yielded sim's budget is one of the configured multiples * N."""
    from h01_simulator.sweep import DEFAULT_BUDGET_MULTIPLES, DEFAULT_N_PROPS

    grid = list(build_default_grid(seeds=1, quick=False))
    # Make the warmup_actions assumption explicit so this test can't silently
    # mis-cover if the default policy list grows.
    for _sim, policy in grid:
        assert policy.warmup_actions == 1, (
            f"test assumes all default policies use warmup_actions=1; got {policy.warmup_actions}"
        )
    for sim, _policy in grid:
        expected = {int(k * sim.n_propositions) for k in DEFAULT_BUDGET_MULTIPLES}
        assert sim.budget in expected, f"budget {sim.budget} not in {expected} for n={sim.n_propositions}"
    # Every (N, multiple) combination should appear at least once when non-degenerate.
    seen_pairs = {(sim.n_propositions, sim.budget) for sim, _ in grid}
    for n in DEFAULT_N_PROPS:
        for k in DEFAULT_BUDGET_MULTIPLES:
            b = int(k * n)
            warmup_total = n  # all default policies use warmup_actions=1
            if b > warmup_total:
                assert (n, b) in seen_pairs, f"missing ({n}, {b})"


def test_build_default_grid_filters_degenerate_cells():
    """No cell should have budget <= warmup_total (budget consumed entirely by warmup)."""
    grid = list(build_default_grid(seeds=1, quick=False))
    for sim, policy in grid:
        warmup_total = policy.warmup_actions * sim.n_propositions
        assert sim.budget > warmup_total, f"degenerate cell: budget={sim.budget}, warmup_total={warmup_total}"


def test_build_default_grid_filter_actually_runs(monkeypatch):
    """Directly exercise the degenerate-cell filter by injecting a multiple
    that triggers it. With warmup_actions=1 at N=20, any multiple <= 1.0
    yields budget <= warmup_total and must be filtered out."""
    monkeypatch.setattr(
        "h01_simulator.sweep.DEFAULT_BUDGET_MULTIPLES",
        (0.5, 2.0),  # 0.5 triggers filter at every default N; 2.0 does not
    )
    grid = list(build_default_grid(seeds=1, quick=False))
    # No yielded cell should have budget <= warmup_total — the filter must skip them.
    for sim, policy in grid:
        warmup_total = policy.warmup_actions * sim.n_propositions
        assert sim.budget > warmup_total
    # And concretely: no cell with budget = int(0.5 * N) should appear.
    triggering_budgets = {int(0.5 * n) for n in (20, 100)}
    seen_budgets = {sim.budget for sim, _ in grid}
    assert triggering_budgets.isdisjoint(seen_budgets), (
        f"filter failed: degenerate budgets {triggering_budgets & seen_budgets} were yielded"
    )


def test_run_sweep_records_budget_multiple(tmp_path):
    grid = list(build_default_grid(seeds=1, quick=True))
    df = run_sweep(grid, tmp_path / "sweep.parquet")
    assert "budget_multiple" in df.columns
    for row in df.iter_rows(named=True):
        assert row["budget_multiple"] == pytest.approx(row["budget"] / row["n_props"])


def test_run_sweep_parallel_matches_serial(tmp_path):
    """workers>1 must produce identical rows including list columns (order-insensitive)."""
    grid_serial = list(build_default_grid(seeds=2, quick=True))
    grid_parallel = list(build_default_grid(seeds=2, quick=True))
    df_serial = run_sweep(grid_serial, tmp_path / "serial.parquet", workers=1)
    df_parallel = run_sweep(grid_parallel, tmp_path / "parallel.parquet", workers=2)

    key_cols = ["policy", "revisit_prob", "n_props", "budget", "p_pos", "p_neg", "prior_true", "bias_model", "seed"]
    a = df_serial.sort(key_cols)
    b = df_parallel.sort(key_cols)

    list_cols = ["allocations", "final_alpha", "final_beta", "ground_truth"]
    assert a.drop(list_cols).equals(b.drop(list_cols))

    for col in list_cols:
        assert a[col].to_list() == b[col].to_list(), f"list column {col} differs"


def test_run_sweep_rejects_invalid_workers(tmp_path):
    grid = list(build_default_grid(seeds=1, quick=True))
    with pytest.raises(ValueError, match="workers"):
        run_sweep(grid, tmp_path / "x.parquet", workers=0)
    with pytest.raises(ValueError, match="workers"):
        run_sweep(grid, tmp_path / "x.parquet", workers=-1)


def test_select_calibration_slice_stratifies_by_n_props_and_budget():
    """Calibration slice must (a) cover every (n_props, budget) bucket and
    (b) keep per-bucket counts within +/-1 of the base quota."""
    from collections import Counter

    from h01_simulator.sweep import _select_calibration_slice

    full = list(build_default_grid(seeds=1, quick=False))
    bucket_keys = {(sim.n_propositions, sim.budget) for sim, _ in full}

    n_calibration_runs = 200
    calibration = _select_calibration_slice(full, n_calibration_runs=n_calibration_runs)

    seen = {(sim.n_propositions, sim.budget) for sim, _ in calibration}
    assert seen == bucket_keys

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
