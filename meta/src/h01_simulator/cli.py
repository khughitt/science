"""CLI entry point for running the h01-simulator sweep."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import click

from .sweep import benchmark_runtime, build_default_grid, run_sweep

# Serial CPU budget, re-anchored after [t002] grid expansion (UCB + optimistic-init
# + expanded r-axis). Measured projection across 5 runs at n_calibration_runs=400:
# average 2967s, max 3115s (range 2871-3115s). Budget includes ~65s safety margin.
# Wall-clock feasibility via --workers remains [t002]'s sweep-time concern.
RUNTIME_BUDGET_SECONDS = 3180


@click.group()
def main() -> None:
    """H01 simulator CLI."""


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


@main.command()
@click.option("--seeds", type=int, default=100, help="Seed count for the projection target.")
@click.option(
    "--budget-seconds",
    type=float,
    default=float(RUNTIME_BUDGET_SECONDS),
    help="Fail if projected full-grid runtime exceeds this many seconds.",
)
def benchmark(seeds: int, budget_seconds: float) -> None:
    """Benchmark a slice of runs and project full-grid runtime."""
    report = benchmark_runtime(seeds_for_full_grid=seeds)
    click.echo(f"Calibration: {report.n_calibration_runs} runs in {report.elapsed_seconds_calibration:.2f}s")
    click.echo(
        f"Projected full grid ({report.projected_full_grid_runs} runs): {report.projected_full_grid_seconds:.1f}s"
    )
    if report.projected_full_grid_seconds > budget_seconds:
        raise click.ClickException(
            f"Projected runtime {report.projected_full_grid_seconds:.1f}s exceeds "
            f"budget {budget_seconds:.1f}s. Tighten the default grid, reduce seeds, "
            f"or add parallelism in a follow-up task before running the full sweep."
        )


if __name__ == "__main__":
    main()
