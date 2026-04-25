"""Run orchestration and sweep runner for the h01 simulator."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import polars as pl

from .config import BiasModel, PolicyConfig, RunResult, SimConfig
from .metrics import brier, recall, regret
from .model import SignalModel, generate_propositions
from .policies import POLICIES

DEFAULT_BUDGET_MULTIPLES: tuple[float, ...] = (2.0, 8.0, 32.0)
DEFAULT_N_PROPS: tuple[int, ...] = (20, 100)


def run_single(sim_config: SimConfig, policy_config: PolicyConfig) -> RunResult:
    """Execute one simulation run."""
    rng = np.random.default_rng(sim_config.seed)
    props = generate_propositions(sim_config, rng)
    model = SignalModel(props, sim_config, rng)
    policy_fn = POLICIES[policy_config.kind](policy_config)

    allocations = np.zeros(sim_config.n_propositions, dtype=int)
    for action_idx in range(sim_config.budget):
        i = policy_fn(model, action_idx, rng)
        signal = model.sample_signal(i)
        model.observe(i, signal)
        allocations[i] += 1

    post_mean = model.posterior_mean()
    return RunResult(
        config=sim_config,
        policy=policy_config,
        recall=recall(props.truth, post_mean),
        brier=brier(props.truth, post_mean),
        regret=regret(props.truth, props.bias_offsets, allocations, sim_config),
        allocations=allocations,
        final_posteriors=np.stack([model.alpha, model.beta], axis=1),
        ground_truth=props.truth,
        bias_offsets=props.bias_offsets,
    )


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


def run_sweep(grid: Iterable[tuple[SimConfig, PolicyConfig]], out_path: Path) -> pl.DataFrame:
    """Run every (sim, policy) pair and write a tidy parquet with list columns."""
    rows: list[dict] = []
    for sim_cfg, pol_cfg in grid:
        r = run_single(sim_cfg, pol_cfg)
        rows.append(
            {
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
                "regret": r.regret,
                "allocations": r.allocations.tolist(),
                "final_alpha": r.final_posteriors[:, 0].tolist(),
                "final_beta": r.final_posteriors[:, 1].tolist(),
                "ground_truth": r.ground_truth.astype(int).tolist(),
            }
        )
    df = pl.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out_path)
    return df


@dataclass(frozen=True)
class BenchmarkReport:
    n_calibration_runs: int
    elapsed_seconds_calibration: float
    projected_full_grid_seconds: float
    projected_full_grid_runs: int


def benchmark_runtime(
    n_calibration_runs: int = 200,
    seeds_for_full_grid: int = 100,
) -> BenchmarkReport:
    """Time a slice of default-grid runs and extrapolate to the full grid.

    Uses the first ``n_calibration_runs`` runs produced by
    ``build_default_grid(seeds=1, quick=False)`` (always-same slice for
    reproducibility) and extrapolates linearly to the full-seed grid size.
    """
    calibration = []
    for sim_cfg, pol_cfg in build_default_grid(seeds=1, quick=False):
        calibration.append((sim_cfg, pol_cfg))
        if len(calibration) >= n_calibration_runs:
            break

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
