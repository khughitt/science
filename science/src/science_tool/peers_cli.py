"""CLI for `science-tool peers`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

import click

from science_tool.peers import resolve_peer_path
from science_tool.peers_validate import PeerIssue, PeerIssueKind, validate_peers
from science_tool.project_config import ProjectConfig, load_project_config


class PeerIssueRow(TypedDict):
    kind: str
    severity: str
    detail: str


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


def _emit_table(rows: list[PeerRow]) -> None:
    headers = ("PEER", "PATH", "STATUS")
    peer_width = max(len(headers[0]), *(len(row["id"]) for row in rows))
    path_width = max(len(headers[1]), *(len(row["path"]) for row in rows))
    click.echo(f"{headers[0]:<{peer_width}}  {headers[1]:<{path_width}}  {headers[2]}")
    for row in rows:
        click.echo(f"{row['id']:<{peer_width}}  {row['path']:<{path_width}}  {row['status']}")
