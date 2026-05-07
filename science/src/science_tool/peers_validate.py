"""Peer-graph validation. See project-peers design Decision 7."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Any

import yaml

from science_tool.peers import resolve_peer_path
from science_tool.project_config import PeerEntry

_KNOWN_PEER_FIELDS = frozenset({"id", "path"})
_RESERVED_PEER_FIELDS = frozenset({"git", "repo", "url", "doi", "ref", "version"})


class PeerIssueKind(StrEnum):
    PATH_MISSING = "path_missing"
    NOT_A_PROJECT = "not_a_project"
    ID_MISMATCH = "id_mismatch"
    DUPLICATE_PEER_ID = "duplicate_peer_id"
    SELF_PEER = "self_peer"
    RESERVED_FIELD = "reserved_field"
    LOCAL_GRAPH_MISSING = "local_graph_missing"


@dataclass
class PeerIssue:
    kind: PeerIssueKind
    peer_id: str
    detail: str
    severity: Literal["error", "warning"]
    entry_index: int | None = None


_SEVERITIES: dict[PeerIssueKind, Literal["error", "warning"]] = {
    PeerIssueKind.PATH_MISSING: "warning",
    PeerIssueKind.NOT_A_PROJECT: "warning",
    PeerIssueKind.ID_MISMATCH: "error",
    PeerIssueKind.DUPLICATE_PEER_ID: "error",
    PeerIssueKind.SELF_PEER: "error",
    PeerIssueKind.RESERVED_FIELD: "error",
    PeerIssueKind.LOCAL_GRAPH_MISSING: "warning",
}


def _issue(
    kind: PeerIssueKind,
    peer_id: str,
    detail: str,
    entry_index: int | None = None,
) -> PeerIssue:
    return PeerIssue(
        kind=kind,
        peer_id=peer_id,
        detail=detail,
        severity=_SEVERITIES[kind],
        entry_index=entry_index,
    )


def validate_peers(project_root: Path) -> list[PeerIssue]:
    """Return all peer-graph issues for the project at `project_root`.

    Reads science.yaml as raw YAML so duplicate-id, self-peer, and reserved-field
    issues surface as structured PeerIssues rather than schema-level errors.
    """
    yaml_path = project_root / "science.yaml"
    if not yaml_path.is_file():
        return []

    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        return []

    raw_peers = raw.get("peers")
    if not isinstance(raw_peers, list):
        return []

    own_id = raw.get("id") or project_root.resolve().name
    issues: list[PeerIssue] = []
    seen_ids: set[str] = set()

    for entry_index, raw_entry in enumerate(raw_peers):
        if not isinstance(raw_entry, dict):
            continue

        peer_id = _peer_id(raw_entry)
        if peer_id in seen_ids:
            issues.append(
                _issue(
                    PeerIssueKind.DUPLICATE_PEER_ID,
                    peer_id,
                    f"peer id {peer_id!r} appears more than once in peers:",
                )
            )
        seen_ids.add(peer_id)

        if peer_id == own_id:
            issues.append(
                _issue(
                    PeerIssueKind.SELF_PEER,
                    peer_id,
                    f"project {own_id!r} lists itself as a peer",
                    entry_index=entry_index,
                )
            )

        for field in sorted(raw_entry.keys() - _KNOWN_PEER_FIELDS, key=str):
            issues.append(_reserved_field_issue(peer_id, field, entry_index))

        path = raw_entry.get("path")
        if not isinstance(path, str):
            continue

        _validate_peer_path(project_root, PeerEntry(id=peer_id, path=path), issues, entry_index)

    return issues


def _peer_id(raw_entry: dict[Any, Any]) -> str:
    raw_id = raw_entry.get("id")
    if isinstance(raw_id, str) and raw_id:
        return raw_id
    return "<unknown>"


def _reserved_field_issue(peer_id: str, field: Any, entry_index: int) -> PeerIssue:
    if field in _RESERVED_PEER_FIELDS:
        detail = f"reserved peer field {field!r} is not yet supported"
    else:
        detail = f"unknown peer field {field!r} is not supported"
    return _issue(PeerIssueKind.RESERVED_FIELD, peer_id, detail, entry_index=entry_index)


def _validate_peer_path(
    project_root: Path,
    entry: PeerEntry,
    issues: list[PeerIssue],
    entry_index: int,
) -> None:
    resolved = resolve_peer_path(project_root, entry)
    if not resolved.exists():
        issues.append(
            _issue(
                PeerIssueKind.PATH_MISSING,
                entry.id,
                f"declared path {entry.path!r} resolves to {resolved}, which does not exist",
                entry_index=entry_index,
            )
        )
        return

    peer_yaml = resolved / "science.yaml"
    if not peer_yaml.is_file():
        issues.append(
            _issue(
                PeerIssueKind.NOT_A_PROJECT,
                entry.id,
                f"path {resolved} exists but contains no science.yaml",
                entry_index=entry_index,
            )
        )
        return

    _validate_peer_id(entry, peer_yaml, resolved, issues, entry_index)
    _validate_local_graph(entry.id, resolved, issues, entry_index)


def _validate_peer_id(
    entry: PeerEntry,
    peer_yaml: Path,
    resolved: Path,
    issues: list[PeerIssue],
    entry_index: int,
) -> None:
    try:
        peer_raw = yaml.safe_load(peer_yaml.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return

    if not isinstance(peer_raw, dict):
        return

    peer_self_id = peer_raw.get("id") or resolved.name
    if peer_self_id != entry.id:
        issues.append(
            _issue(
                PeerIssueKind.ID_MISMATCH,
                entry.id,
                f"declared id {entry.id!r}, peer's science.yaml says {peer_self_id!r}",
                entry_index=entry_index,
            )
        )


def _validate_local_graph(
    peer_id: str,
    resolved: Path,
    issues: list[PeerIssue],
    entry_index: int,
) -> None:
    knowledge_dir = resolved / "knowledge"
    if (knowledge_dir / "composite.trig").is_file() and not (knowledge_dir / "graph.trig").is_file():
        issues.append(
            _issue(
                PeerIssueKind.LOCAL_GRAPH_MISSING,
                peer_id,
                f"peer has composite.trig but no graph.trig at {knowledge_dir}",
                entry_index=entry_index,
            )
        )
