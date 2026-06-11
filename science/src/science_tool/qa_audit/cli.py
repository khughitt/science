from __future__ import annotations

import json
from pathlib import Path

import click

from science_tool.qa_audit.audit import audit_workflows, render_markdown


@click.command("qa-audit")
@click.option("--runs-dir", type=click.Path(path_type=Path), default=Path("doc/workflow-runs"),
              show_default=True, help="Directory of authored workflow-run entities.")
@click.option("--repo-root", type=click.Path(path_type=Path), default=Path("."), show_default=True,
              help="Repo root used to resolve each run's manifest_path.")
@click.option("--out", "out_path", type=click.Path(path_type=Path), default=None,
              help="Optional file to write the markdown report to.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Emit JSON rows instead of a table.")
def qa_audit_command(runs_dir: Path, repo_root: Path, out_path: Path | None, as_json: bool) -> None:
    """Advisory process-quality audit: flag single-run / QA-ignoring workflows.

    Always exits 0 — this never gates a build or `science validate`.
    """
    if not runs_dir.exists():
        raise click.ClickException(f"runs dir not found: {runs_dir}")
    rows = audit_workflows(runs_dir=runs_dir, repo_root=repo_root)
    if as_json:
        click.echo(json.dumps(rows, indent=2, sort_keys=True))
        return
    md = render_markdown(rows)
    click.echo(md, nl=False)
    if out_path is not None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(md, encoding="utf-8")
