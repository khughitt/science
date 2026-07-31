"""The actor-facing evidence broker command."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NoReturn

import click

from science_tool.autonomy.baseline import BaselineError, read_baseline
from science_tool.autonomy.control_plane import ControlPlaneError, run_dir, run_slug
from science_tool.evidence_broker.policy import EvidenceOp, EvidenceRequest
from science_tool.evidence_broker.session import Session, SessionError
from science_tool.output import OUTPUT_FORMATS, emit


@click.group("evidence")
def evidence_group() -> None:
    """Serve bounded evidence from an autonomous run."""


def _fail(message: str, *, output_format: str) -> NoReturn:
    emit(
        output_format=output_format,
        payload={"error": message},
        render_text=lambda: click.echo(message),
    )
    sys.exit(2)


@evidence_group.command("serve")
@click.option("--session", "handle", required=True, help="Run id or run slug.")
@click.option("--op", type=click.Choice([op.value for op in EvidenceOp]), required=True)
@click.option("--target", required=True)
@click.option("--pathspec", default=None)
@click.option(
    "--project-root", type=click.Path(path_type=Path), default=Path("."), show_default=True
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(OUTPUT_FORMATS),
    default="table",
    show_default=True,
)
def serve_command(
    handle: str,
    op: str,
    target: str,
    pathspec: str | None,
    project_root: Path,
    output_format: str,
) -> None:
    """Serve one request without writing its bytes to stdout."""
    try:
        directory = run_dir(project_root, handle)
    except (ControlPlaneError, BaselineError) as exc:
        _fail(f"could not address run id {handle!r}: {exc}", output_format=output_format)

    try:
        baseline = read_baseline(directory / "baseline.json", project_root=project_root)
    except BaselineError as exc:
        _fail(f"could not read the baseline for {handle!r}: {exc}", output_format=output_format)

    try:
        mismatch = run_slug(baseline.run_id) != run_slug(handle)
    except ControlPlaneError as exc:
        _fail(f"the baseline at {directory} does not name a valid run: {exc}", output_format=output_format)
    if mismatch:
        _fail(f"the baseline at {directory} does not name run {handle!r}", output_format=output_format)

    if baseline.evidence is None:
        _fail(
            f"run {handle!r} was not opened with a broker spec; there is no surface to serve",
            output_format=output_format,
        )

    try:
        receipt = Session(project_root, baseline.evidence).request(
            EvidenceRequest(op=EvidenceOp(op), target=target, pathspec=pathspec)
        )
    except SessionError as exc:
        _fail(f"could not serve evidence for {handle!r}: {exc}", output_format=output_format)

    payload = {
        "outcome": receipt.outcome.value,
        "sha256": receipt.sha256,
        "path": None if receipt.path is None else str(receipt.path),
        "notice": receipt.notice,
    }
    emit(
        output_format=output_format,
        payload=payload,
        render_text=lambda: click.echo(receipt.notice or receipt.path or receipt.outcome.value),
    )
