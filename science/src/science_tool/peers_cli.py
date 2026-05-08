"""CLI for `science-tool peers`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

import click
import yaml

from science_tool.peers import PeerNotFound, PeerUnresolved, make_local_resolver, resolve_peer_path
from science_tool.peers_validate import PeerIssue, PeerIssueKind, validate_peers
from science_tool.project_config import ProjectConfig, load_project_config


class PeerIssueRow(TypedDict):
    kind: str
    severity: str
    detail: str


class PeerCheckIssueRow(PeerIssueRow):
    peer_id: str


class PeerRow(TypedDict):
    id: str
    path: str
    resolved: str | None
    status: str
    issues: list[PeerIssueRow]


@click.group("peers")
def peers_group() -> None:
    """Manage and inspect project peers."""


@peers_group.command("list")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
)
@click.option("--format", "fmt", type=click.Choice(["table", "json"]), default="table", show_default=True)
def peers_list(project_root: Path, fmt: str) -> None:
    """List declared peers and their status."""
    cfg = load_project_config(project_root)
    rows = _peer_rows(project_root, cfg)

    if fmt == "json":
        click.echo(json.dumps({"project_id": cfg.id, "peers": rows}, indent=2))
        return

    if not rows:
        click.echo("no peers declared")
        return

    _emit_table(rows)


@peers_group.command("check")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text", show_default=True)
@click.option("--strict", is_flag=True, help="Treat warnings as errors.")
def peers_check(project_root: Path, fmt: str, strict: bool) -> None:
    """Validate declared peers."""
    issues = validate_peers(project_root)
    rows = [_check_issue_row(issue) for issue in issues]
    peer_count = _raw_peer_count(project_root)
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    error_count = sum(1 for issue in issues if issue.severity == "error")
    should_fail = error_count > 0 or (strict and warning_count > 0)

    if fmt == "json":
        click.echo(json.dumps(rows, indent=2))
    else:
        for issue in issues:
            click.echo(f"{issue.severity.upper()} [{issue.peer_id}] {issue.kind.value}: {issue.detail}")
        summary_label = "failed" if should_fail else "ok"
        click.echo(f"{summary_label}: {peer_count} peers, {warning_count} warning, {error_count} error")

    if should_fail:
        raise click.exceptions.Exit(1)


@peers_group.command("show")
@click.argument("peer_id")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
)
def peers_show(peer_id: str, project_root: Path) -> None:
    """Show details for a single peer."""
    project_root = Path.cwd() if str(project_root) == "." else project_root
    try:
        resolver = make_local_resolver(project_root)
        resolved = resolver.resolve(peer_id)
    except PeerNotFound as exc:
        raise click.ClickException(str(exc)) from exc
    except PeerUnresolved as exc:
        raise click.ClickException(str(exc)) from exc

    peer_cfg = load_project_config(resolved.path)
    click.echo(f"declared_id: {resolved.id}")
    click.echo(f"project_id:  {peer_cfg.id}")
    click.echo(f"name:        {peer_cfg.name}")
    click.echo(f"role:        {peer_cfg.role}")
    click.echo(f"path:        {resolved.path}")


@peers_group.command("migrate")
@click.option(
    "--project-root",
    default=".",
    show_default=True,
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
)
@click.option("--dry-run", is_flag=True, help="Report migrations without writing files.")
@click.option("--all", "migrate_all", is_flag=True, help="Also migrate legacy child projects.")
def peers_migrate(project_root: Path, dry_run: bool, migrate_all: bool) -> None:
    """Migrate legacy parent/children fields to peers."""
    from science_tool.peers_migrate import MigrationError, migrate_project

    try:
        targets = [project_root]
        if migrate_all:
            targets.extend(_legacy_child_project_roots(project_root))
            if not dry_run:
                for target in targets:
                    migrate_project(target, dry_run=True)

        for target in targets:
            summary = migrate_project(target, dry_run=dry_run)
            if summary.migrated:
                action = "would migrate" if dry_run else "migrated"
                click.echo(f"{action}: {target}")
            else:
                note = f" - {summary.note}" if summary.note else ""
                click.echo(f"skipped: {target}{note}")
    except MigrationError as exc:
        raise click.ClickException(str(exc)) from exc


def _peer_rows(project_root: Path, cfg: ProjectConfig) -> list[PeerRow]:
    issues_by_entry = _issues_by_entry(project_root, cfg)

    rows: list[PeerRow] = []
    for entry_index, entry in enumerate(cfg.peers):
        resolved = resolve_peer_path(project_root, entry)
        issue_rows = issues_by_entry[entry_index]
        rows.append(
            {
                "id": entry.id,
                "path": entry.path,
                "resolved": None if not resolved.exists() else str(resolved),
                "status": _status_for(issue_rows),
                "issues": issue_rows,
            }
        )
    return rows


def _raw_peer_count(project_root: Path) -> int:
    yaml_path = project_root / "science.yaml"
    if not yaml_path.is_file():
        return 0

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return 0

    peers = raw.get("peers")
    if not isinstance(peers, list):
        return 0
    return len(peers)


def _legacy_child_project_roots(project_root: Path) -> list[Path]:
    raw = _raw_project_yaml(project_root)
    if not isinstance(raw, dict):
        return []

    children = raw.get("children")
    if not isinstance(children, list):
        return []

    targets: list[Path] = []
    for index, child in enumerate(children):
        if not isinstance(child, dict):
            raise click.ClickException(f"children[{index}] must be a mapping with string path")
        child_path = child.get("path")
        if not isinstance(child_path, str):
            raise click.ClickException(f"children[{index}] must include string path")
        target = _resolve_migration_path(project_root, child_path)
        if not (target / "science.yaml").is_file():
            raise click.ClickException(
                f"children[{index}] path {child_path!r} resolved to {target}, but no science.yaml was found"
            )
        targets.append(target)
    return targets


def _raw_project_yaml(project_root: Path) -> Any:
    yaml_path = project_root / "science.yaml"
    try:
        return yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise click.ClickException(f"failed to read {yaml_path}: {exc}") from exc


def _resolve_migration_path(project_root: Path, raw_path: str) -> Path:
    if raw_path.startswith("~"):
        return Path(raw_path).expanduser().resolve(strict=False)

    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (project_root / path).resolve(strict=False)


def _issues_by_entry(project_root: Path, cfg: ProjectConfig) -> list[list[PeerIssueRow]]:
    issues_by_entry: list[list[PeerIssueRow]] = [[] for _ in cfg.peers]
    seen_by_entry: list[set[tuple[str, str, str]]] = [set() for _ in cfg.peers]

    for issue in validate_peers(project_root):
        issue_row = _issue_row(issue)
        issue_key = (issue_row["kind"], issue_row["severity"], issue_row["detail"])
        if issue.entry_index is None:
            for entry_index, entry in enumerate(cfg.peers):
                if entry.id == issue.peer_id and issue_key not in seen_by_entry[entry_index]:
                    issues_by_entry[entry_index].append(issue_row)
                    seen_by_entry[entry_index].add(issue_key)
            continue

        if 0 <= issue.entry_index < len(issues_by_entry):
            issues_by_entry[issue.entry_index].append(issue_row)

    return issues_by_entry


def _status_for(issues: list[PeerIssueRow]) -> str:
    for issue in issues:
        if issue["severity"] == "error":
            return issue["kind"].replace("_", "-")
    issue_kinds = [issue["kind"] for issue in issues]
    if PeerIssueKind.PATH_MISSING.value in issue_kinds:
        return "path-missing"
    if PeerIssueKind.NOT_A_PROJECT.value in issue_kinds:
        return "not-a-project"
    if issue_kinds:
        return issue_kinds[0].replace("_", "-")
    return "ok"


def _issue_row(issue: PeerIssue) -> PeerIssueRow:
    return {
        "kind": issue.kind.value,
        "severity": issue.severity,
        "detail": issue.detail,
    }


def _check_issue_row(issue: PeerIssue) -> PeerCheckIssueRow:
    return {
        "kind": issue.kind.value,
        "peer_id": issue.peer_id,
        "detail": issue.detail,
        "severity": issue.severity,
    }


def _emit_table(rows: list[PeerRow]) -> None:
    headers = ("PEER", "PATH", "STATUS")
    peer_width = max(len(headers[0]), *(len(row["id"]) for row in rows))
    path_width = max(len(headers[1]), *(len(row["path"]) for row in rows))
    click.echo(f"{headers[0]:<{peer_width}}  {headers[1]:<{path_width}}  {headers[2]}")
    for row in rows:
        click.echo(f"{row['id']:<{peer_width}}  {row['path']:<{path_width}}  {row['status']}")
