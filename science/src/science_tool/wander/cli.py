from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import click
from rdflib import Dataset

from science_tool.graph.attention import (
    compute_attention_candidates,
    weighted_sample_without_replacement,
)
from science_tool.wander.context import assemble_bundle
from science_tool.wander.sampling import WanderSamplerError
from science_tool.wander.skeleton import render_json, render_markdown_skeleton
from science_tool.wander.stub_smell import compute_stub_signals

WANDER_FORMATS: tuple[str, ...] = ("markdown", "json")


@click.command("wander")
@click.option("--n", "n", type=int, default=3, show_default=True, help="Number of entities to sample.")
@click.option("--seed", type=int, default=None, help="Reproducibility seed.")
@click.option("--kind", "kinds", multiple=True, help="Restrict candidates to one or more entity kinds.")
@click.option("--epsilon", type=float, default=0.05, show_default=True, help="Positive weight floor.")
@click.option(
    "--graph-path",
    type=click.Path(path_type=Path),
    default=Path("knowledge/graph.trig"),
    show_default=True,
    help="Path to the materialized knowledge graph (.trig).",
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(WANDER_FORMATS),
    default="markdown",
    show_default=True,
    help="Output format. `markdown` writes a walk skeleton to --out; `json` prints bundles to stdout.",
)
@click.option(
    "--out",
    "out_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Output file (markdown). Defaults to doc/meta/walks/walk-<id>.md.",
)
@click.option(
    "--today",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Override the date used for sampling and stub-smell.",
)
@click.option(
    "--repo-root",
    type=click.Path(path_type=Path),
    default=Path("."),
    show_default=True,
    help="Repo root for git-based created-date fallback.",
)
def wander_command(
    n: int,
    seed: int | None,
    kinds: tuple[str, ...],
    epsilon: float,
    graph_path: Path,
    output_format: str,
    out_path: Path | None,
    today: datetime | None,
    repo_root: Path,
) -> None:
    """Draw a serendipitous sample of epistemic entities and write a walk skeleton."""
    if not graph_path.exists():
        raise click.ClickException(f"Graph file not found at {graph_path}. Run `science graph build` first.")
    if n < 0:
        raise click.ClickException("--n must be >= 0")

    walk_date: date = today.date() if today is not None else date.today()
    walk_id = walk_date.strftime("%Y-%m-%d") + "-" + datetime.now().strftime("%H%M")

    try:
        dataset = Dataset()
        dataset.parse(source=str(graph_path), format="trig")
        candidates = compute_attention_candidates(
            dataset, today=walk_date, kinds=set(kinds) if kinds else None, epsilon=epsilon
        )
        sample = weighted_sample_without_replacement(candidates, limit=n, seed=seed)
    except (WanderSamplerError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    bundles = [assemble_bundle(c, dataset, repo_root=repo_root) for c in sample]
    bundles_with_signals = [(b, compute_stub_signals(b, today=walk_date)) for b in bundles]

    if output_format == "json":
        click.echo(
            render_json(walk_id=walk_id, walk_date=walk_date, seed=seed, n=n, bundles_with_signals=bundles_with_signals)
        )
        return

    text = render_markdown_skeleton(
        walk_id=walk_id,
        walk_date=walk_date,
        seed=seed,
        n=n,
        bundles_with_signals=bundles_with_signals,
    )
    target = out_path or Path("doc/meta/walks") / f"walk-{walk_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    click.echo(str(target))
