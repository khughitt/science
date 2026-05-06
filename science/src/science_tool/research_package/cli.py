"""Click commands for the research-package command group."""

from __future__ import annotations

import json
from pathlib import Path

import click

from science_model.packages.validation import check_freshness, validate_package

from .build_package import build_research_package
from .init_package import init_research_package


@click.group("research-package")
def research_package_group() -> None:
    """Research package management."""


@research_package_group.command("init")
@click.option("--name", required=True, help="Package name (slug)")
@click.option("--title", required=True, help="Human-readable title")
@click.option(
    "--workflow",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Workflow directory to read config from",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Output package directory",
)
def init_cmd(name: str, title: str, workflow: Path | None, output: Path) -> None:
    """Scaffold a new research package directory."""
    pkg_dir = init_research_package(name, title, output, workflow_dir=workflow)
    click.echo(f"Scaffolded research package at {pkg_dir}")


@research_package_group.command("validate")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--check-freshness", "check_freshness_flag", is_flag=True, help="Also check input freshness")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=None,
    help="Project root for freshness check",
)
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def validate_cmd(path: Path, check_freshness_flag: bool, project_root: Path | None, as_json: bool) -> None:
    """Validate research package(s)."""
    packages: list[Path] = []
    if (path / "datapackage.json").is_file():
        packages.append(path)
    else:
        for dp in sorted(path.rglob("datapackage.json")):
            try:
                raw = json.loads(dp.read_text(encoding="utf-8"))
                if raw.get("profile") == "science-research-package":
                    packages.append(dp.parent)
            except (json.JSONDecodeError, OSError):
                continue

    if not packages:
        click.echo("No research packages found.")
        raise SystemExit(0)

    results = []
    has_errors = False

    for pkg_dir in packages:
        result = validate_package(pkg_dir)
        if check_freshness_flag:
            root = project_root or Path.cwd()
            freshness = check_freshness(pkg_dir, root)
            result.warnings.extend(freshness.warnings)
        results.append(result)
        if not result.ok:
            has_errors = True

    if as_json:
        click.echo(json.dumps([r.to_dict() for r in results], indent=2))
    else:
        for result in results:
            pkg_name = Path(result.package_dir).name
            if result.ok and not result.warnings:
                click.echo(f"  \u2713 {result.package_dir}")
            elif result.ok:
                for w in result.warnings:
                    click.echo(f"  \u26a0 {pkg_name}: {w}")
            else:
                for e in result.errors:
                    click.echo(f"  \u2717 {pkg_name}: {e}")

    raise SystemExit(1 if has_errors else 0)


@research_package_group.command("build")
@click.option(
    "--results",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Results directory from workflow run",
)
@click.option(
    "--config",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Workflow config.yaml path",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(path_type=Path),
    help="Output package directory",
)
def build_cmd(results: Path, config: Path, output: Path) -> None:
    """Assemble a research package from workflow results."""
    errors = build_research_package(results, config, output)
    if errors:
        for e in errors:
            click.echo(f"  \u2717 {e}", err=True)
        raise SystemExit(1)
    click.echo(f"Built research package at {output}")
