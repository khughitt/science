"""Pure migration from legacy parent/children fields to peers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class MigrationError(Exception):
    """Project peer migration cannot be completed."""


@dataclass
class MigrationSummary:
    migrated: bool
    note: str | None = None


def migrate_project(project_root: Path, *, dry_run: bool) -> MigrationSummary:
    yaml_path = project_root / "science.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise MigrationError(f"{yaml_path} must contain a YAML mapping")

    has_parent = "parent" in raw
    has_children = "children" in raw
    if not has_parent and not has_children:
        return MigrationSummary(False, "No legacy fields found; nothing to migrate.")

    peers = _peers(raw)
    if has_parent:
        parent_path = raw["parent"]
        if parent_path is None:
            del raw["parent"]
        elif not isinstance(parent_path, str):
            raise MigrationError("parent must be a path string")
        else:
            parent_id = _read_parent_id(project_root, parent_path)
            _append_peer(peers, peer_id=parent_id, path=parent_path)
            del raw["parent"]

    if has_children:
        children = raw["children"]
        if children is None:
            del raw["children"]
        elif not isinstance(children, list):
            raise MigrationError("children must be a list")
        else:
            for child_id, child_path in _child_peers(children):
                _append_peer(peers, peer_id=child_id, path=child_path)
            del raw["children"]

    if dry_run:
        return MigrationSummary(True, "dry-run: no files written")

    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return MigrationSummary(True)


def _peers(raw: dict[Any, Any]) -> list[Any]:
    existing = raw.get("peers")
    if existing is None:
        peers: list[Any] = []
        raw["peers"] = peers
        return peers
    if not isinstance(existing, list):
        raise MigrationError("peers must be a list")
    _validate_existing_peer_conflicts(existing)
    return existing


def _validate_existing_peer_conflicts(peers: list[Any]) -> None:
    paths_by_id: dict[str, Any] = {}
    for peer in peers:
        if not isinstance(peer, dict):
            continue
        peer_id = peer.get("id")
        if not isinstance(peer_id, str):
            continue
        path = peer.get("path")
        if peer_id in paths_by_id and paths_by_id[peer_id] != path:
            raise MigrationError(
                f"duplicate peer id {peer_id!r} has conflicting paths: {paths_by_id[peer_id]!r} and {path!r}"
            )
        paths_by_id[peer_id] = path


def _child_peers(children: list[Any]) -> list[tuple[str, str]]:
    peers: list[tuple[str, str]] = []
    for index, child in enumerate(children):
        if not isinstance(child, dict):
            raise MigrationError(f"children[{index}] must be a mapping with string id and path")
        child_id = child.get("id")
        child_path = child.get("path")
        if not isinstance(child_id, str) or not isinstance(child_path, str):
            raise MigrationError(f"children[{index}] must include string id and string path")
        peers.append((child_id, child_path))
    return peers


def _append_peer(peers: list[Any], *, peer_id: str, path: str) -> None:
    for peer in peers:
        if not isinstance(peer, dict):
            continue
        if peer.get("id") == peer_id:
            if peer.get("path") == path:
                return
            raise MigrationError(
                f"peer id {peer_id!r} already exists with path {peer.get('path')!r}; "
                f"cannot migrate different path {path!r}"
            )
    peers.append({"id": peer_id, "path": path})


def _read_parent_id(project_root: Path, parent_path: str) -> str:
    resolved = _resolve_project_path(project_root, parent_path)
    parent_yaml = resolved / "science.yaml"
    if not parent_yaml.is_file():
        raise MigrationError(
            f"cannot migrate parent: {parent_path!r}: no science.yaml found at resolved path {resolved}"
        )

    try:
        loaded = yaml.safe_load(parent_yaml.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise MigrationError(
            f"cannot migrate parent: {parent_path!r}: failed to parse parent YAML at resolved path {parent_yaml}"
        ) from exc
    if not isinstance(loaded, dict):
        raise MigrationError(
            f"cannot migrate parent: {parent_path!r}: parent YAML at resolved path {parent_yaml} must be a mapping"
        )
    parent_id = loaded.get("id")
    if isinstance(parent_id, str) and parent_id:
        return parent_id
    return resolved.name


def _resolve_project_path(project_root: Path, raw_path: str) -> Path:
    if raw_path.startswith("~"):
        return Path(raw_path).expanduser().resolve(strict=False)
    path = Path(raw_path)
    if path.is_absolute():
        return path.resolve(strict=False)
    return (project_root / path).resolve(strict=False)
