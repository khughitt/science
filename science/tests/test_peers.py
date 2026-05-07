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


class TestLocalPeerResolver:
    def test_duplicate_non_self_peer_ids_raise_peer_unresolved(
        self, tmp_path: Path
    ) -> None:
        from science_tool.peers import PeerUnresolved, make_local_resolver

        host = tmp_path / "host"
        peer_a = tmp_path / "peer-a"
        peer_b = tmp_path / "peer-b"
        _write_minimal_science_yaml(peer_a, "peer-a")
        _write_minimal_science_yaml(peer_b, "peer-b")
        host.mkdir()
        (host / "science.yaml").write_text(
            f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer_a}
  - id: peer
    path: {peer_b}
""",
            encoding="utf-8",
        )

        with pytest.raises(PeerUnresolved, match="peer"):
            make_local_resolver(host)

    def test_known_ids_excludes_self_peer_entry(self, tmp_path: Path) -> None:
        from science_tool.peers import make_local_resolver

        host = tmp_path / "host"
        peer = tmp_path / "peer"
        _write_minimal_science_yaml(peer, "peer")
        host.mkdir()
        (host / "science.yaml").write_text(
            f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: host
    path: .
  - id: peer
    path: {peer}
""",
            encoding="utf-8",
        )

        resolver = make_local_resolver(host)
        assert resolver.known_ids() == frozenset({"peer"})

    def test_resolve_self_peer_entry_raises_peer_not_found(
        self, tmp_path: Path
    ) -> None:
        from science_tool.peers import PeerNotFound, make_local_resolver

        host = tmp_path / "host"
        host.mkdir()
        (host / "science.yaml").write_text(
            """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: host
    path: .
""",
            encoding="utf-8",
        )

        resolver = make_local_resolver(host)
        with pytest.raises(PeerNotFound, match="host"):
            resolver.resolve("host")

    def test_known_ids_excludes_host_and_includes_peers(self, tmp_path: Path) -> None:
        from science_tool.peers import make_local_resolver

        host = tmp_path / "host"
        peer_a = tmp_path / "peer-a"
        peer_b = tmp_path / "peer-b"
        _write_minimal_science_yaml(peer_a, "peer-a")
        _write_minimal_science_yaml(peer_b, "peer-b")
        host.mkdir()
        (host / "science.yaml").write_text(
            f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer-a
    path: {peer_a}
  - id: peer-b
    path: {peer_b}
""",
            encoding="utf-8",
        )

        resolver = make_local_resolver(host)
        assert resolver.known_ids() == frozenset({"peer-a", "peer-b"})

    def test_resolve_returns_resolved_peer(self, tmp_path: Path) -> None:
        from science_tool.peers import make_local_resolver

        host = tmp_path / "host"
        peer = tmp_path / "peer"
        _write_minimal_science_yaml(peer, "peer")
        host.mkdir()
        (host / "science.yaml").write_text(
            f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
            encoding="utf-8",
        )

        resolver = make_local_resolver(host)
        resolved = resolver.resolve("peer")
        assert resolved.id == "peer"
        assert resolved.path == peer.resolve()
        assert resolved.entry.id == "peer"
        assert resolved.entry.path == str(peer)

    def test_resolve_unknown_raises_peer_not_found(self, tmp_path: Path) -> None:
        from science_tool.peers import PeerNotFound, make_local_resolver

        host = tmp_path / "host"
        _write_minimal_science_yaml(host, "host")
        resolver = make_local_resolver(host)
        with pytest.raises(PeerNotFound, match="ghost"):
            resolver.resolve("ghost")

    def test_resolve_missing_path_raises_peer_unresolved(self, tmp_path: Path) -> None:
        from science_tool.peers import PeerUnresolved, make_local_resolver

        host = tmp_path / "host"
        host.mkdir()
        (host / "science.yaml").write_text(
            """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../does-not-exist
""",
            encoding="utf-8",
        )
        resolver = make_local_resolver(host)
        with pytest.raises(PeerUnresolved, match="ghost"):
            resolver.resolve("ghost")

    def test_resolve_path_exists_but_no_science_yaml_raises(
        self, tmp_path: Path
    ) -> None:
        from science_tool.peers import PeerUnresolved, make_local_resolver

        host = tmp_path / "host"
        not_a_project = tmp_path / "junk"
        not_a_project.mkdir()
        host.mkdir()
        (host / "science.yaml").write_text(
            f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: junk
    path: {not_a_project}
""",
            encoding="utf-8",
        )
        resolver = make_local_resolver(host)
        with pytest.raises(PeerUnresolved, match="science.yaml"):
            resolver.resolve("junk")

    def test_resolver_is_per_invocation_not_module_cached(self, tmp_path: Path) -> None:
        """Two calls to make_local_resolver return distinct resolver objects."""
        from science_tool.peers import make_local_resolver

        host = tmp_path / "host"
        peer = tmp_path / "peer"
        _write_minimal_science_yaml(peer, "peer")
        _write_minimal_science_yaml(host, "host")
        r1 = make_local_resolver(host)
        (host / "science.yaml").write_text(
            f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
            encoding="utf-8",
        )
        r2 = make_local_resolver(host)
        assert r1 is not r2
        assert r1.known_ids() == frozenset()
        assert r2.known_ids() == frozenset({"peer"})


class TestResolverCycleProtection:
    def test_recursive_resolution_with_cycle_does_not_infinite_loop(
        self, tmp_path: Path
    ) -> None:
        """A resolver tracks in-flight peer IDs in a visited set.

        We exercise the protection by simulating a consumer that calls back
        into the resolver while resolving a peer.
        """
        from science_tool.peers import make_local_resolver

        host = tmp_path / "host"
        peer = tmp_path / "peer"
        peer.mkdir()
        (peer / "science.yaml").write_text(
            f"""
name: peer
id: peer
profile: research
research_question: "..."
peers:
  - id: host
    path: {host}
""",
            encoding="utf-8",
        )
        host.mkdir()
        (host / "science.yaml").write_text(
            f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
            encoding="utf-8",
        )

        resolver = make_local_resolver(host)

        with resolver.enter("peer"):
            assert "peer" in resolver.in_flight()
            with pytest.raises(RuntimeError, match="cycle"):
                with resolver.enter("peer"):
                    pass
        assert resolver.in_flight() == frozenset()
