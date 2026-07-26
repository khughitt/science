from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import click

from science_tool.graph.attention import (
    compute_attention_candidates,
    weighted_sample_without_replacement,
)
from science_tool.graph.trig import load_trig_dataset_preserving_literals
from science_tool.output import emit
from science_tool.wander.context import assemble_bundle
from science_tool.wander.skeleton import build_json_payload, render_markdown_skeleton
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
    "--output",
    "output_path",
    type=click.Path(path_type=Path),
    default=None,
    help=(
        "Output file. For --format markdown, the walk skeleton path (defaults to "
        "doc/meta/walks/walk-<id>.md; --out is a kept alias). For --format json, write the "
        "complete, unbudgeted bundle report to PATH instead of stdout."
    ),
)
@click.option(
    "--today",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    default=None,
    help="Override the date used for the walk and stub-smell.",
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
    output_path: Path | None,
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
        dataset = load_trig_dataset_preserving_literals(graph_path)
        candidates = compute_attention_candidates(dataset, kinds=set(kinds) if kinds else None, epsilon=epsilon)
        if candidates.status == "unwired":
            # A walk over a graph that was never assessed for attention is not a walk that
            # found nothing — it is a walk that never happened. Refuse rather than emit an
            # empty skeleton the reader would take for a completed pass.
            raise click.ClickException(f"wander did not run ({candidates.code}): {candidates.reason}")
        sample = weighted_sample_without_replacement(candidates.rows, limit=n, seed=seed)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    bundles = [assemble_bundle(c, dataset, repo_root=repo_root) for c in sample]
    bundles_with_signals = [(b, compute_stub_signals(b, today=walk_date)) for b in bundles]

    if output_format == "json":
        from science_tool.budget.control import bounded_control_notice
        from science_tool.budget.invocation import build_complete_via, hint_for
        from science_tool.budget.projection import project_single_list_report
        from science_tool.budget.registry import lookup
        from science_tool.budget.sink import BoundedSink

        complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("wander", output_format))
        sink = BoundedSink(
            lookup("wander"), output_path=output_path, command_path="wander", complete_via=complete_via
        )
        control_notice = (
            bounded_control_notice(f"wrote the complete walk bundle report to {output_path}")
            if output_path is not None
            else None
        )
        full = build_json_payload(
            walk_id=walk_id, walk_date=walk_date, seed=seed, n=n, bundles_with_signals=bundles_with_signals
        )
        displayed = full if output_path is not None else project_single_list_report(full, "bundles", 40)
        if output_path is None and displayed.get("bundles_omitted", 0):
            displayed = {
                **displayed,
                "truncation": {
                    "omitted": displayed["bundles_omitted"],
                    "total": len(full["bundles"]),
                    "complete_via": complete_via,
                },
            }

        emit(
            output_format=output_format,
            payload=displayed,
            render_text=lambda: None,
            sort_keys=True,
            default=str,
            sink=sink,
        )
        sink.flush()
        if control_notice is not None:
            click.echo(control_notice)
        return

    text = render_markdown_skeleton(
        walk_id=walk_id,
        walk_date=walk_date,
        seed=seed,
        n=n,
        bundles_with_signals=bundles_with_signals,
    )
    target = output_path or Path("doc/meta/walks") / f"walk-{walk_id}.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    click.echo(str(target))
