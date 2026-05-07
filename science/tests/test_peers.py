"""Tests for science_tool.peers (resolver + read access)."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_minimal_science_yaml(root: Path, project_id: str) -> None:
    """Write a minimum-viable science.yaml at `root`."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text(
        f"""
name: {project_id}
id: {project_id}
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )


class TestResolvePeerPath:
    def test_absolute_path(self, tmp_path: Path) -> None:
        from science_tool.peers import resolve_peer_path
        from science_tool.project_config import PeerEntry

        target = tmp_path / "absolute" / "peer"
        target.mkdir(parents=True)
        entry = PeerEntry(id="x", path=str(target))
        result = resolve_peer_path(tmp_path / "host", entry)
        assert result == target.resolve()

    def test_tilde_anchored_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from science_tool.peers import resolve_peer_path
        from science_tool.project_config import PeerEntry

        monkeypatch.setenv("HOME", str(tmp_path))
        target = tmp_path / "d" / "r" / "lit-explore"
        target.mkdir(parents=True)
        entry = PeerEntry(id="lit", path="~/d/r/lit-explore")
        result = resolve_peer_path(tmp_path / "host", entry)
        assert result == target.resolve()

    def test_relative_path(self, tmp_path: Path) -> None:
        from science_tool.peers import resolve_peer_path
        from science_tool.project_config import PeerEntry

        host = tmp_path / "cluster" / "host"
        peer = tmp_path / "cluster" / "mm30"
        host.mkdir(parents=True)
        peer.mkdir(parents=True)
        entry = PeerEntry(id="mm30", path="../mm30")
        result = resolve_peer_path(host, entry)
        assert result == peer.resolve()

    def test_missing_path_returns_would_be_canonical(self, tmp_path: Path) -> None:
        """Decision 3: missing paths are NOT errors; we return the would-be path."""
        from science_tool.peers import resolve_peer_path
        from science_tool.project_config import PeerEntry

        host = tmp_path / "host"
        host.mkdir()
        entry = PeerEntry(id="ghost", path="../missing")
        result = resolve_peer_path(host, entry)
        assert isinstance(result, Path)
        assert result == (host / "../missing").resolve(strict=False)
        assert not result.exists()

    def test_symlinks_resolve_to_canonical(self, tmp_path: Path) -> None:
        from science_tool.peers import resolve_peer_path
        from science_tool.project_config import PeerEntry

        real = tmp_path / "real"
        real.mkdir()
        link = tmp_path / "link"
        link.symlink_to(real)
        entry = PeerEntry(id="x", path=str(link))
        result = resolve_peer_path(tmp_path / "host", entry)
        assert result == real.resolve()
