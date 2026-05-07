"""Project peers: non-fatal path resolution.

See docs/superpowers/specs/2026-05-05-project-peers-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from science_tool.project_config import PeerEntry


def resolve_peer_path(project_root: Path, entry: PeerEntry) -> Path:
    """Return the canonical (or would-be canonical) Path for a peer entry.

    Non-fatal: never raises for missing files. Uses Path.resolve(strict=False),
    which follows symlinks where present and normalizes `..`.

    Path-form dispatch (Decision 3):
        - leading `~` -> expanduser(), then resolve
        - absolute    -> used as-is
        - otherwise   -> resolved against project_root
    """
    raw = entry.path
    if raw.startswith("~"):
        candidate = Path(raw).expanduser()
    else:
        raw_path = Path(raw)
        if raw_path.is_absolute():
            candidate = raw_path
        else:
            candidate = project_root / raw_path
    return candidate.resolve(strict=False)


class PeerNotFound(Exception):
    """Peer ID is not declared in this project's peers list."""


class PeerUnresolved(Exception):
    """Peer is declared but its path does not point at a valid project."""


@dataclass(frozen=True)
class ResolvedPeer:
    id: str
    path: Path
    entry: PeerEntry


class PeerResolver(Protocol):
    """Strategy for resolving peer IDs to filesystem locations.

    Future implementations: workspace-registry-backed (deferred - Trajectory 2),
    git-clone-on-resolve (deferred - Trajectory 3). Consumers depend only on
    this protocol so adding either is purely additive.
    """

    def known_ids(self) -> frozenset[str]:
        """All peer IDs visible to this resolver. Excludes the host project's own id."""
        ...

    def resolve(self, peer_id: str) -> ResolvedPeer:
        """Return the resolved peer or raise PeerNotFound / PeerUnresolved."""
        ...


class LocalPeerResolver:
    """Default resolver: reads `peers:` from a single project's science.yaml."""

    def __init__(self, project_root: Path) -> None:
        from science_tool.project_config import load_project_config  # noqa: PLC0415

        self._project_root = project_root
        cfg = load_project_config(project_root)
        self._entries: dict[str, PeerEntry] = {}
        for entry in cfg.peers:
            if entry.id == cfg.id:
                continue
            if entry.id in self._entries:
                raise PeerUnresolved(
                    f"duplicate peer id {entry.id!r} declared in "
                    f"{self._project_root}/science.yaml"
                )
            self._entries[entry.id] = entry

    def known_ids(self) -> frozenset[str]:
        return frozenset(self._entries.keys())

    def resolve(self, peer_id: str) -> ResolvedPeer:
        entry = self._entries.get(peer_id)
        if entry is None:
            raise PeerNotFound(
                f"peer id {peer_id!r} is not declared in {self._project_root}/science.yaml"
            )
        path = resolve_peer_path(self._project_root, entry)
        if not path.exists():
            raise PeerUnresolved(
                f"peer {peer_id!r} declared with path {entry.path!r}, "
                f"but resolved path {path} does not exist"
            )
        if not (path / "science.yaml").is_file():
            raise PeerUnresolved(
                f"peer {peer_id!r} resolves to {path}, "
                "but no science.yaml found there"
            )
        return ResolvedPeer(id=peer_id, path=path, entry=entry)


def make_local_resolver(project_root: Path) -> PeerResolver:
    """Return a fresh LocalPeerResolver for `project_root`."""
    return LocalPeerResolver(project_root)
