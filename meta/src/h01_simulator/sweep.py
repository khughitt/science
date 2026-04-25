"""Run orchestration and sweep runner for the h01 simulator."""

from __future__ import annotations

import time
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import polars as pl

from .config import BiasModel, PolicyConfig, RunResult, SimConfig
from .metrics import brier, recall, signal_count_regret
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
        signal_count_regret=signal_count_regret(props.truth, props.bias_offsets, allocations, sim_config),
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


def _row_from_result(r: RunResult) -> dict[str, object]:
    sim_cfg = r.config
    pol_cfg = r.policy
    return {
        "policy": pol_cfg.kind,
        "revisit_prob": pol_cfg.revisit_prob,
        "warmup_actions": pol_cfg.warmup_actions,
        "ucb_c": pol_cfg.ucb_c,
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


@dataclass(frozen=True)
class BenchmarkReport:
    n_calibration_runs: int
    elapsed_seconds_calibration: float
    projected_full_grid_seconds: float
    projected_full_grid_runs: int


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
        indices = np.linspace(0, len(bucket) - 1, num=quota, dtype=int)
        chosen.extend(bucket[int(i)] for i in indices)
    return chosen


def benchmark_runtime(
    n_calibration_runs: int = 400,
    seeds_for_full_grid: int = 100,
) -> BenchmarkReport:
    """Time a stratified slice of default-grid runs and extrapolate to the full grid.

    400 calibration runs (the default) cuts projection standard deviation roughly 30%
    vs. the previous 200, keeping the gate from spuriously firing under timing noise. Calibration
    pairs are sampled stratified by (n_propositions, budget) — the axes that dominate
    per-run cost — so the timing slice covers cheap and expensive cells in proportion
    rather than concentrating in the grid prefix. Extrapolation is still linear.
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
