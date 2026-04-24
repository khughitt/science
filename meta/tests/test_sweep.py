from typing import Any

import numpy as np
import polars as pl
import pytest

from h01_simulator.config import PolicyConfig, SimConfig
from h01_simulator.sweep import build_default_grid, run_single, run_sweep


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
    # regret is non-negative within float tolerance
    assert r.regret >= -1e-9


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
        "n_props",
        "budget",
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
        "regret",
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
