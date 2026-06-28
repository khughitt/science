# Project Peers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace tree-shaped `parent:` / `children:` federation with a decentralized peer-graph (Layer 1 addressability + minimal Layer 2 read access). Implements `docs/plans/historical/2026-05-05-project-peers-design.md`.

**Architecture:** Additive-then-breaking sequencing. Phase A introduces the new `peers:` field, resolver, validator, CLI, migration command, and composite graph alongside the existing `parent:`/`children:`/federation code so the test suite stays green. Phase B runs the migration on this monorepo, updates remaining tests, switches `ProjectConfig` to reject the legacy fields, and deletes the dead federation modules.

**Tech Stack:** Python 3.11+, pydantic v2, click, rdflib, pytest 9.x. New modules in `science/src/science_tool/`. Tests in `science/tests/`.

---

**CLI executable note:** this repo's `science/pyproject.toml` exposes the console script as `science`, not `science-tool`. Implementation commands in this plan use `uv run science ...`; user-facing docs may still discuss the product as `science-tool` where that wording is intentional.

## Spec

`docs/plans/historical/2026-05-05-project-peers-design.md`. Refer to **Decisions 1–10** by number throughout this plan.

## File Structure

**New files (`science/src/science_tool/`):**

| File | Responsibility |
|---|---|
| `peers.py` | `ResolvedPeer`, `PeerNotFound`, `PeerUnresolved`, `PeerResolver` Protocol, `LocalPeerResolver`, `make_local_resolver`, `resolve_peer_path`, `load_peer_entity_index`. `PeerEntry` lives in `project_config.py` because it is part of the `science.yaml` schema. |
| `peers_validate.py` | `PeerIssueKind`, `PeerIssue`, `validate_peers()` (reads raw YAML; produces structured issue list). |
| `peers_migrate.py` | Pure migration logic: read raw YAML → emit migrated YAML. Idempotent, dry-run-aware. |
| `peers_cli.py` | Click subcommand group for `science-tool peers list / check / show / migrate`. |
| `graph/composite.py` | `assemble_composite_graph()` (renamed from `graph/federation.py:assemble_federated_graph`); reads peers, writes `composite.trig`, never reads another project's `composite.trig`. |

**New tests (`science/tests/`):**

- `test_peers.py`, `test_peers_validate.py`, `test_peers_migrate.py`, `test_peers_cli.py`, `test_graph_composite.py`.

**Modified files:**

| File | Change |
|---|---|
| `addressing.py` | Tighten `_ADDRESS_RE` to disallow `@` in artifact position. |
| `tasks_blockers.py` | Tighten `_TYPED_REF_RE` to disallow `@` in slug position. |
| `project_config.py` | Phase A: add `peers: list[PeerEntry]` field. Phase B: remove `parent:` / `children:` / `ChildEntry` / `resolve_child_path`; add `_reject_legacy_fields` model_validator. |
| `refs.py` | `_load_project_ids` rewritten to consult resolver. |
| `cli.py` | Phase A: register `peers` subcommand group. Phase B: refactor `graph_build` to drop the `META`/`parent` branch and call `assemble_composite_graph` whenever peers exist. |
| `project_artifacts/data/validate.sh` | Replace `children:` references in error messages and templates. |
| `project_artifacts/registry.yaml` | Bump to mark the breaking change. |

**Deleted files (Phase B):**

- `federation.py`, `federation_cli.py`, `federation_status.py`, `graph/federation.py` and the `science-tool federation` CLI registration.
- `tests/test_federation_cli.py`, `tests/test_federation_validation.py`, `tests/test_federation_integration.py`, `tests/test_federation_status_cli.py`, `tests/test_graph_federation.py`, `tests/test_graph_build_federated.py`, `tests/test_graph_build_parent_register.py`.

**Migrated data:** any `science.yaml` in this monorepo currently using top-level `parent:` or `children:` — covered by Task 14 (`peers migrate --all`). The implementation must run the inventory first; if the current repo has no live legacy project configs, Task 14 is a documented no-op rather than a failure.

**Documentation:** `docs/federation.md`, `commands/tasks.md`, plus any `commands/` / `skills/` content mentioning federation.

---

## Phase A — Additive (peers system lands; parent/children still accepted)

### Task 1: Tighten ref grammar to reserve `@`

**Files:**
- Modify: `science/src/science_tool/addressing.py:8`
- Modify: `science/src/science_tool/tasks_blockers.py:12` (also update `is_typed_ref` if needed)
- Test: `science/tests/test_addressing.py` (add new test)

- [ ] **Step 1: Add failing test for @ rejection in addressing**

Append to `science/tests/test_addressing.py`:

```python
def test_classify_entity_ref_rejects_at_in_artifact() -> None:
    """`@` in the artifact position must not classify as any entity ref shape.

    Rationale: Decision 1 of the project-peers design reserves `@<version>` as
    a future suffix; allowing it in slugs today would conflict with the future
    versioning grammar.
    """
    from science_tool.addressing import classify_entity_ref

    result = classify_entity_ref(
        "task:t001@v2",
        local_kinds={"task"},
        project_ids=frozenset(),
    )
    assert result.shape == "non-entity"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && uv run pytest tests/test_addressing.py::test_classify_entity_ref_rejects_at_in_artifact -v
```

Expected: FAIL — current `_ADDRESS_RE` accepts `@`, so the call produces `local-entity` shape.

- [ ] **Step 3: Tighten `_ADDRESS_RE` and `_TYPED_REF_RE`**

In `science/src/science_tool/addressing.py:8`, change:

```python
_ADDRESS_RE = re.compile(r"^(?P<project>[a-z][a-z0-9-]{1,63}):(?P<artifact>\S+)$")
```

to:

```python
_ADDRESS_RE = re.compile(r"^(?P<project>[a-z][a-z0-9-]{1,63}):(?P<artifact>[^@\s]+)$")
```

In `science/src/science_tool/tasks_blockers.py:12`, change:

```python
_TYPED_REF_RE = re.compile(r"^[a-z][a-z0-9-]*:\S+$")
```

to:

```python
_TYPED_REF_RE = re.compile(r"^[a-z][a-z0-9-]*:[^@\s]+$")
```

- [ ] **Step 4: Run test to verify it passes; run wider test set**

```bash
cd science && uv run pytest tests/test_addressing.py tests/test_tasks_blockers.py -v
```

Expected: PASS for the new test. All existing tests remain green (no fixtures use `@` in refs).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/addressing.py science/src/science_tool/tasks_blockers.py science/tests/test_addressing.py
git commit -m "$(cat <<'EOF'
refs: reserve @ in slug position for future versioning

Tightens _ADDRESS_RE and _TYPED_REF_RE to disallow @ in the artifact /
slug positions. Lays groundwork for the future <project-id>:<kind>:<slug>@<version>
ref grammar (deferred — see project-peers design Decision 1).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Introduce `PeerEntry` and `peers:` field on `ProjectConfig` (additive)

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Test: `science/tests/test_project_config.py`

This task is **purely additive**: `parent:` / `children:` continue to work. The new `peers:` field is optional. Schema rejection of `parent:` / `children:` lands in Task 16.

- [ ] **Step 1: Add failing test for `peers:` field**

Append to `science/tests/test_project_config.py`:

```python
def test_project_config_accepts_peers(tmp_path: Path) -> None:
    """`peers:` is a list of {id, path}; loaded as PeerEntry objects."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: mm30
    path: ~/d/cancer/mm30
  - id: lit-explore
    path: ../../r/lit-explore
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert len(cfg.peers) == 2
    assert cfg.peers[0].id == "mm30"
    assert cfg.peers[0].path == "~/d/cancer/mm30"
    assert cfg.peers[1].id == "lit-explore"
    assert cfg.peers[1].path == "../../r/lit-explore"


def test_project_config_peers_default_empty(tmp_path: Path) -> None:
    """A config without peers: gets an empty list."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert cfg.peers == []


def test_peer_entry_accepts_unknown_fields_for_forward_compat(tmp_path: Path) -> None:
    """Reserved fields (git, url, etc.) parse without raising; surfaced by validator."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: future-peer
    path: ./somewhere
    git: https://github.com/example/future-peer
""",
        encoding="utf-8",
    )
    cfg = load_project_config(project_root)
    assert cfg.peers[0].id == "future-peer"
```

Also add to the same file `from science_tool.project_config import PeerEntry  # noqa: F401` if not already imported via `*`.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_project_config.py::test_project_config_accepts_peers tests/test_project_config.py::test_project_config_peers_default_empty tests/test_peer_entry_accepts_unknown_fields_for_forward_compat -v
```

Expected: FAIL — `PeerEntry` doesn't exist; `peers` attribute missing.

- [ ] **Step 3: Add `PeerEntry` and `peers:` field**

In `science/src/science_tool/project_config.py`, after the existing `ChildEntry` class (around line 46) add:

```python
class PeerEntry(BaseModel):
    """Declares another project this one references.

    `id` must match the peer project's own self-declared `id:` (validated by
    `validate_peers()` at use time, not at parse time, so configs with
    transient inconsistencies still load).

    `path` is a local filesystem path. Three accepted shapes:
      - absolute (`/...`)
      - `~`-anchored (`~/d/...`)
      - relative to this project's root (`../mm30`)

    Reserved fields (`git`, `repo`, `url`, `doi`, `ref`, `version`) are
    accepted at parse time (extra="allow") but flagged by `validate_peers()`
    until their respective specs ship. See project-peers design Decision 2.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    path: str
```

Then in `ProjectConfig` (around line 57), add the `peers` field next to `children`:

```python
class ProjectConfig(BaseModel):
    """Typed view of science.yaml. Non-listed fields are preserved as-is."""

    model_config = ConfigDict(extra="allow")

    name: str
    id: str | None = None
    role: RoleField = ProjectRole.STANDALONE
    parent: str | None = None
    children: list[ChildEntry] = Field(default_factory=list)
    peers: list[PeerEntry] = Field(default_factory=list)  # NEW

    # ... existing validators stay
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_project_config.py -v
```

Expected: All pass, including the three new tests.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config.py
git commit -m "$(cat <<'EOF'
project-config: add PeerEntry and peers: field (additive)

Introduces peers: as an optional list of {id, path} entries on
ProjectConfig, alongside the existing parent: / children: federation
fields. Schema rejection of the legacy fields lands in a later task
once consumers have migrated.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: `resolve_peer_path()` helper (non-fatal path math)

**Files:**
- Create: `science/src/science_tool/peers.py`
- Test: `science/tests/test_peers.py`

Per Decision 3 + Decision 4: `resolve_peer_path` is the non-fatal helper. It returns a canonical or would-be canonical Path and never raises for missing files.

- [ ] **Step 1: Create the failing test file**

Create `science/tests/test_peers.py`:

```python
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
        # The path doesn't exist but we still get a normalized would-be path.
        assert isinstance(result, Path)
        assert "missing" in str(result)
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers.py::TestResolvePeerPath -v
```

Expected: FAIL — `science_tool.peers` doesn't exist.

- [ ] **Step 3: Create `peers.py` with `resolve_peer_path`**

Create `science/src/science_tool/peers.py`:

```python
"""Project peers: addressability (Layer 1) and minimal read access (Layer 2).

See docs/plans/historical/2026-05-05-project-peers-design.md.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.project_config import PeerEntry


def resolve_peer_path(project_root: Path, entry: PeerEntry) -> Path:
    """Return the canonical (or would-be canonical) Path for a peer entry.

    Non-fatal: never raises for missing files. Uses Path.resolve(strict=False),
    which follows symlinks where present and normalizes `..`. Callers that
    need an existing project should use PeerResolver.resolve() instead.

    Path-form dispatch (Decision 3):
        - leading `/` → absolute, used as-is
        - leading `~` → expanduser(), then resolve
        - otherwise   → resolved against project_root
    """
    raw = entry.path
    if raw.startswith("/"):
        candidate = Path(raw)
    elif raw.startswith("~"):
        candidate = Path(raw).expanduser()
    else:
        candidate = (project_root / raw)
    return candidate.resolve(strict=False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers.py -v
```

Expected: All five `TestResolvePeerPath` tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers.py science/tests/test_peers.py
git commit -m "$(cat <<'EOF'
peers: add resolve_peer_path() non-fatal path helper

Resolves PeerEntry.path against three accepted forms (absolute,
~-anchored, project-root-relative) using Path.resolve(strict=False).
Returns would-be paths for missing peers; the fatal resolver
(PeerResolver.resolve) lands in a follow-up task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: `PeerResolver` protocol + `LocalPeerResolver` + `make_local_resolver`

**Files:**
- Modify: `science/src/science_tool/peers.py`
- Modify: `science/tests/test_peers.py`

Per Decision 4: protocol-typed resolver interface, default local implementation, cycle protection.

- [ ] **Step 1: Add failing tests for resolver behavior**

Append to `science/tests/test_peers.py`:

```python
class TestLocalPeerResolver:
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

    def test_resolve_path_exists_but_no_science_yaml_raises(self, tmp_path: Path) -> None:
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
        _write_minimal_science_yaml(host, "host")
        r1 = make_local_resolver(host)
        r2 = make_local_resolver(host)
        assert r1 is not r2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers.py::TestLocalPeerResolver -v
```

Expected: FAIL — `PeerNotFound`, `PeerUnresolved`, `make_local_resolver` don't exist.

- [ ] **Step 3: Implement resolver in `peers.py`**

Append to `science/src/science_tool/peers.py`:

```python
from dataclasses import dataclass
from typing import Protocol


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

    Future implementations: workspace-registry-backed (deferred — Trajectory 2),
    git-clone-on-resolve (deferred — Trajectory 3). Consumers depend only on
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
        self._entries: dict[str, PeerEntry] = {entry.id: entry for entry in cfg.peers}

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers.py -v
```

Expected: All `TestLocalPeerResolver` tests pass; `TestResolvePeerPath` tests still pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers.py science/tests/test_peers.py
git commit -m "$(cat <<'EOF'
peers: add PeerResolver protocol and LocalPeerResolver

Introduces the fatal resolver tier: PeerResolver.resolve() raises
PeerNotFound / PeerUnresolved per Decision 4. LocalPeerResolver reads
peers: from a single science.yaml; future workspace-registry and
git-clone resolvers can drop in via the Protocol without consumer
changes.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Cycle protection in resolver

**Files:**
- Modify: `science/src/science_tool/peers.py`
- Modify: `science/tests/test_peers.py`

Cross-project resolution can be recursive (A's resolver calls into B's, which may call back into A's). Cycle protection prevents infinite loops.

- [ ] **Step 1: Add failing test for cycle protection**

Append to `science/tests/test_peers.py`:

```python
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

        # Simulate a recursive consumer: enter resolution for "peer", then
        # while inside, enter resolution for "host" via a peer-side resolver.
        with resolver.enter("peer"):
            assert "peer" in resolver.in_flight()
            with pytest.raises(RuntimeError, match="cycle"):
                with resolver.enter("peer"):
                    pass
        assert resolver.in_flight() == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && uv run pytest tests/test_peers.py::TestResolverCycleProtection -v
```

Expected: FAIL — `enter` and `in_flight` don't exist.

- [ ] **Step 3: Add cycle-tracking to `LocalPeerResolver`**

In `science/src/science_tool/peers.py`, modify `LocalPeerResolver` to add a context-manager helper. Add to the class body:

```python
    def __init__(self, project_root: Path) -> None:
        from science_tool.project_config import load_project_config  # noqa: PLC0415

        self._project_root = project_root
        cfg = load_project_config(project_root)
        self._entries: dict[str, PeerEntry] = {entry.id: entry for entry in cfg.peers}
        self._in_flight: set[str] = set()

    def in_flight(self) -> frozenset[str]:
        return frozenset(self._in_flight)

    @contextmanager
    def enter(self, peer_id: str) -> Iterator[None]:
        """Track in-flight peer resolution; raise on cycle.

        Use this around recursive peer-traversal blocks to prevent infinite
        loops when peer A peers B and B peers A.
        """
        if peer_id in self._in_flight:
            raise RuntimeError(
                f"resolver cycle detected on peer id {peer_id!r}: "
                f"already in-flight (currently resolving {sorted(self._in_flight)})"
            )
        self._in_flight.add(peer_id)
        try:
            yield
        finally:
            self._in_flight.discard(peer_id)
```

Also add to imports near the top of `peers.py`:

```python
from collections.abc import Iterator
from contextlib import contextmanager
```

And update the `PeerResolver` protocol to include the new methods:

```python
class PeerResolver(Protocol):
    def known_ids(self) -> frozenset[str]: ...
    def resolve(self, peer_id: str) -> ResolvedPeer: ...
    def in_flight(self) -> frozenset[str]: ...
    def enter(self, peer_id: str) -> "AbstractContextManager[None]": ...
```

Add the import:

```python
from contextlib import AbstractContextManager
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers.py science/tests/test_peers.py
git commit -m "$(cat <<'EOF'
peers: add cycle protection via enter()/in_flight() helpers

LocalPeerResolver tracks in-flight peer IDs and raises RuntimeError on
re-entry. Recursive consumers (e.g., the future cross-project
ReadinessResolver) wrap traversal in `with resolver.enter(peer_id):`
to enforce the invariant.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: `load_peer_entity_index` (minimal Layer 2 read access)

**Files:**
- Modify: `science/src/science_tool/peers.py`
- Modify: `science/tests/test_peers.py`

Per Decision 5: thin wrapper that routes through the resolver, then calls the existing local entity loader at the peer's path.

The existing loader is `load_local_entity_index(project_root: Path) -> dict[str, ProjectEntity]` at `science/src/science_tool/entities.py:465`. The wrapper just routes through the resolver.

- [ ] **Step 1: Add failing test**

Append to `science/tests/test_peers.py`:

```python
class TestLoadPeerEntityIndex:
    def test_load_peer_entity_index_returns_peer_entities(self, tmp_path: Path) -> None:
        from science_tool.peers import load_peer_entity_index, make_local_resolver

        host = tmp_path / "host"
        peer = tmp_path / "peer"
        peer.mkdir()
        (peer / "science.yaml").write_text(
            """
name: peer
id: peer
profile: research
research_question: "..."
""",
            encoding="utf-8",
        )
        # Place a minimal hypothesis entity in the peer so the index isn't empty.
        (peer / "specs" / "hypotheses").mkdir(parents=True)
        (peer / "specs" / "hypotheses" / "h01-test.md").write_text(
            """---
id: hypothesis:h01-test
title: Test
---

A hypothesis for testing.
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
        index = load_peer_entity_index(resolver, "peer")
        # load_local_entity_index returns dict[str, ProjectEntity] keyed by canonical id.
        assert "hypothesis:h01-test" in index

    def test_load_peer_entity_index_unknown_peer_raises(self, tmp_path: Path) -> None:
        from science_tool.peers import PeerNotFound, load_peer_entity_index, make_local_resolver

        host = tmp_path / "host"
        _write_minimal_science_yaml(host, "host")
        resolver = make_local_resolver(host)
        with pytest.raises(PeerNotFound):
            load_peer_entity_index(resolver, "ghost")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers.py::TestLoadPeerEntityIndex -v
```

Expected: FAIL — `load_peer_entity_index` doesn't exist.

- [ ] **Step 3: Implement the wrapper**

Append to `science/src/science_tool/peers.py`:

```python
def load_peer_entity_index(resolver: PeerResolver, peer_id: str):
    """Load a peer's entity index using the existing local-load machinery.

    Raises PeerNotFound or PeerUnresolved on resolver failure (propagated from
    `resolver.resolve()`). Raises FileNotFoundError if the peer's
    science.yaml or entity files are missing.

    Returns dict[str, ProjectEntity] (same shape as load_local_entity_index).
    """
    from science_tool.entities import load_local_entity_index  # noqa: PLC0415

    peer = resolver.resolve(peer_id)
    return load_local_entity_index(peer.path)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers.py science/tests/test_peers.py
git commit -m "$(cat <<'EOF'
peers: add load_peer_entity_index for minimal L2 read access

Routes a peer-id through the resolver (raises if missing) and calls
the existing load_local_entity_index at the peer's resolved path.
Caching, freshness, and materialized-graph delegation are deferred
(Trajectory item 5).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: `peers_validate.py` — validator with all `PeerIssueKind`s

**Files:**
- Create: `science/src/science_tool/peers_validate.py`
- Test: `science/tests/test_peers_validate.py`

Per Decision 7: reads raw YAML, surfaces structured issues. Reads raw because schema-level rejection of duplicates / self-peers would prevent issues from reaching the CLI.

- [ ] **Step 1: Create the test file**

Create `science/tests/test_peers_validate.py`:

```python
"""Tests for science_tool.peers_validate."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_minimal_science_yaml(root: Path, project_id: str) -> None:
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


def test_no_peers_returns_empty(tmp_path: Path) -> None:
    from science_tool.peers_validate import validate_peers

    root = tmp_path / "host"
    _write_minimal_science_yaml(root, "host")
    assert validate_peers(root) == []


def test_path_missing_warning(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
        encoding="utf-8",
    )
    issues = validate_peers(root)
    assert len(issues) == 1
    assert issues[0].kind is PeerIssueKind.PATH_MISSING
    assert issues[0].peer_id == "ghost"
    assert issues[0].severity == "warning"


def test_not_a_project_warning(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    junk = tmp_path / "junk"
    junk.mkdir()
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: junk
    path: {junk}
""",
        encoding="utf-8",
    )
    issues = validate_peers(root)
    assert len(issues) == 1
    assert issues[0].kind is PeerIssueKind.NOT_A_PROJECT
    assert issues[0].severity == "warning"


def test_id_mismatch_error(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    peer = tmp_path / "peer-dir"
    _write_minimal_science_yaml(peer, "actual-id")
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: declared-id
    path: {peer}
""",
        encoding="utf-8",
    )
    issues = validate_peers(root)
    assert any(i.kind is PeerIssueKind.ID_MISMATCH for i in issues)
    mismatch = next(i for i in issues if i.kind is PeerIssueKind.ID_MISMATCH)
    assert mismatch.severity == "error"
    assert "actual-id" in mismatch.detail
    assert "declared-id" in mismatch.detail


def test_duplicate_peer_id_error(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    a = tmp_path / "a"
    b = tmp_path / "b"
    _write_minimal_science_yaml(a, "dup")
    _write_minimal_science_yaml(b, "dup")
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: {a}
  - id: dup
    path: {b}
""",
        encoding="utf-8",
    )
    issues = validate_peers(root)
    assert any(i.kind is PeerIssueKind.DUPLICATE_PEER_ID for i in issues)
    dup = next(i for i in issues if i.kind is PeerIssueKind.DUPLICATE_PEER_ID)
    assert dup.severity == "error"


def test_self_peer_error(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: host
    path: {root}
""",
        encoding="utf-8",
    )
    issues = validate_peers(root)
    assert any(i.kind is PeerIssueKind.SELF_PEER for i in issues)


def test_reserved_field_error(tmp_path: Path) -> None:
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    peer = tmp_path / "peer"
    _write_minimal_science_yaml(peer, "peer")
    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
    git: https://github.com/example/peer
""",
        encoding="utf-8",
    )
    issues = validate_peers(root)
    assert any(
        i.kind is PeerIssueKind.RESERVED_FIELD and "git" in i.detail for i in issues
    )


def test_local_graph_missing_warning(tmp_path: Path) -> None:
    """Peer has composite.trig but no graph.trig: surfaced as warning per Decision 6."""
    from science_tool.peers_validate import PeerIssueKind, validate_peers

    peer = tmp_path / "peer"
    _write_minimal_science_yaml(peer, "peer")
    (peer / "knowledge").mkdir()
    (peer / "knowledge" / "composite.trig").write_text("# minimal\n", encoding="utf-8")
    # Note: NO graph.trig.

    root = tmp_path / "host"
    root.mkdir()
    (root / "science.yaml").write_text(
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
    issues = validate_peers(root)
    assert any(i.kind is PeerIssueKind.LOCAL_GRAPH_MISSING for i in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers_validate.py -v
```

Expected: FAIL — `science_tool.peers_validate` doesn't exist.

- [ ] **Step 3: Implement `peers_validate.py`**

Create `science/src/science_tool/peers_validate.py`:

```python
"""Peer-graph validation. See project-peers design Decision 7."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal

import yaml

from science_tool.peers import resolve_peer_path
from science_tool.project_config import PeerEntry

_KNOWN_PEER_FIELDS = frozenset({"id", "path"})
_RESERVED_PEER_FIELDS = frozenset({"git", "repo", "url", "doi", "ref", "version"})


class PeerIssueKind(StrEnum):
    PATH_MISSING        = "path_missing"
    NOT_A_PROJECT       = "not_a_project"
    ID_MISMATCH         = "id_mismatch"
    DUPLICATE_PEER_ID   = "duplicate_peer_id"
    SELF_PEER           = "self_peer"
    RESERVED_FIELD      = "reserved_field"
    LOCAL_GRAPH_MISSING = "local_graph_missing"


@dataclass
class PeerIssue:
    kind: PeerIssueKind
    peer_id: str
    detail: str
    severity: Literal["error", "warning"]


_SEVERITIES: dict[PeerIssueKind, Literal["error", "warning"]] = {
    PeerIssueKind.PATH_MISSING: "warning",
    PeerIssueKind.NOT_A_PROJECT: "warning",
    PeerIssueKind.ID_MISMATCH: "error",
    PeerIssueKind.DUPLICATE_PEER_ID: "error",
    PeerIssueKind.SELF_PEER: "error",
    PeerIssueKind.RESERVED_FIELD: "error",
    PeerIssueKind.LOCAL_GRAPH_MISSING: "warning",
}


def _issue(kind: PeerIssueKind, peer_id: str, detail: str) -> PeerIssue:
    return PeerIssue(kind=kind, peer_id=peer_id, detail=detail, severity=_SEVERITIES[kind])


def validate_peers(project_root: Path) -> list[PeerIssue]:
    """Return all peer-graph issues for the project at `project_root`.

    Reads science.yaml as raw YAML so duplicate-id / self-peer issues
    surface as structured PeerIssues (rather than schema-level errors).
    """
    issues: list[PeerIssue] = []
    yaml_path = project_root / "science.yaml"
    if not yaml_path.is_file():
        return issues
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    own_id = raw.get("id") or project_root.resolve().name
    raw_peers = raw.get("peers") or []
    if not isinstance(raw_peers, list):
        return issues

    seen_ids: set[str] = set()
    for raw_entry in raw_peers:
        if not isinstance(raw_entry, dict):
            continue
        peer_id = raw_entry.get("id") or "<unknown>"

        # DUPLICATE_PEER_ID
        if peer_id in seen_ids:
            issues.append(
                _issue(
                    PeerIssueKind.DUPLICATE_PEER_ID,
                    peer_id,
                    f"peer id {peer_id!r} appears more than once in peers:",
                )
            )
        seen_ids.add(peer_id)

        # SELF_PEER
        if peer_id == own_id:
            issues.append(
                _issue(
                    PeerIssueKind.SELF_PEER,
                    peer_id,
                    f"project {own_id!r} lists itself as a peer",
                )
            )

        # RESERVED_FIELD
        for field in raw_entry.keys() - _KNOWN_PEER_FIELDS:
            kind_detail = (
                f"reserved peer field {field!r} not yet supported"
                if field in _RESERVED_PEER_FIELDS
                else f"unknown peer field {field!r}"
            )
            issues.append(_issue(PeerIssueKind.RESERVED_FIELD, peer_id, kind_detail))

        path_str = raw_entry.get("path")
        if not isinstance(path_str, str):
            continue

        entry = PeerEntry(id=peer_id, path=path_str)
        resolved = resolve_peer_path(project_root, entry)

        # PATH_MISSING
        if not resolved.exists():
            issues.append(
                _issue(
                    PeerIssueKind.PATH_MISSING,
                    peer_id,
                    f"declared path {path_str!r} resolves to {resolved}, which does not exist",
                )
            )
            continue

        peer_yaml = resolved / "science.yaml"
        if not peer_yaml.is_file():
            issues.append(
                _issue(
                    PeerIssueKind.NOT_A_PROJECT,
                    peer_id,
                    f"path {resolved} exists but contains no science.yaml",
                )
            )
            continue

        # ID_MISMATCH
        try:
            peer_raw = yaml.safe_load(peer_yaml.read_text(encoding="utf-8")) or {}
            peer_self_id = peer_raw.get("id") or resolved.name
        except Exception:  # noqa: BLE001
            peer_self_id = None
        if peer_self_id is not None and peer_self_id != peer_id:
            issues.append(
                _issue(
                    PeerIssueKind.ID_MISMATCH,
                    peer_id,
                    f"declared id {peer_id!r}, peer's science.yaml says {peer_self_id!r}",
                )
            )

        # LOCAL_GRAPH_MISSING (Decision 6)
        knowledge_dir = resolved / "knowledge"
        if (knowledge_dir / "composite.trig").is_file() and not (knowledge_dir / "graph.trig").is_file():
            issues.append(
                _issue(
                    PeerIssueKind.LOCAL_GRAPH_MISSING,
                    peer_id,
                    f"peer has composite.trig but no graph.trig at {knowledge_dir}",
                )
            )

    return issues
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers_validate.py -v
```

Expected: All eight tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers_validate.py science/tests/test_peers_validate.py
git commit -m "$(cat <<'EOF'
peers: validate_peers() with all seven PeerIssueKinds

Reads science.yaml as raw YAML so duplicate-id / self-peer / reserved-
field issues surface as structured PeerIssues instead of pydantic
errors. Covers Decision 7 of the project-peers design.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: Refactor `refs._load_project_ids` to consult resolver

**Files:**
- Modify: `science/src/science_tool/refs.py:152-160`
- Test: `science/tests/test_refs.py` (or wherever `_load_project_ids` is exercised)

Before this task: `_load_project_ids` returns `cfg.id + child.id for child in cfg.children`. After: returns `cfg.id + resolver.known_ids()`. During the additive phase both `children:` and `peers:` may be populated; we union them so the test suite stays green.

- [ ] **Step 1: Add failing test for peers-driven project IDs**

Append to `science/tests/test_refs.py` (or create if needed):

```python
def test_load_project_ids_includes_peers(tmp_path: Path) -> None:
    """`_load_project_ids` should pick up peers via the resolver."""
    from science_tool.refs import _load_project_ids

    peer = tmp_path / "peer"
    peer.mkdir()
    (peer / "science.yaml").write_text(
        """
name: peer
id: peer
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )
    host = tmp_path / "host"
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
    ids = _load_project_ids(host)
    assert "host" in ids
    assert "peer" in ids
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd science && uv run pytest tests/test_refs.py::test_load_project_ids_includes_peers -v
```

Expected: FAIL — current `_load_project_ids` reads `cfg.children`, not `cfg.peers`.

- [ ] **Step 3: Update `_load_project_ids`**

In `science/src/science_tool/refs.py`, locate the existing function (around line 152) and replace:

```python
def _load_project_ids(root: Path) -> set[str]:
    try:
        cfg = load_project_config(root)
    except Exception:
        return set()
    ids = {child.id for child in cfg.children}
    if cfg.id:
        ids.add(cfg.id)
    return ids
```

with:

```python
def _load_project_ids(root: Path) -> set[str]:
    try:
        cfg = load_project_config(root)
    except Exception:
        return set()
    # Phase A: union legacy children (for back-compat during migration window)
    # with new peers via the resolver. Phase B drops the children union when
    # the field is removed from ProjectConfig.
    ids: set[str] = {child.id for child in cfg.children}
    try:
        from science_tool.peers import make_local_resolver  # noqa: PLC0415
        ids.update(make_local_resolver(root).known_ids())
    except Exception:  # noqa: BLE001
        pass
    if cfg.id:
        ids.add(cfg.id)
    return ids
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_refs.py tests/test_validate_script.py -v
```

Expected: New test passes; existing `validate.sh` ref-resolution tests stay green (since they declare projects via `children:` which still works).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/refs.py science/tests/test_refs.py
git commit -m "$(cat <<'EOF'
refs: _load_project_ids consults the peer resolver

Phase A: union legacy children-derived IDs with peer-derived IDs from
make_local_resolver(). Both fields work simultaneously during the
migration window. The children union is dropped in Phase B when
parent: / children: are removed from ProjectConfig.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 9: `peers_cli.py` — `peers list` command

**Files:**
- Create: `science/src/science_tool/peers_cli.py`
- Modify: `science/src/science_tool/cli.py` (register subgroup)
- Test: `science/tests/test_peers_cli.py`

Per Decision 8: tabular + JSON output, status column derived from `validate_peers`.

- [ ] **Step 1: Add failing test for `peers list`**

Create `science/tests/test_peers_cli.py`:

```python
"""Tests for science-tool peers CLI."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def _write_yaml(path: Path, body: str) -> None:
    (path / "science.yaml").write_text(body, encoding="utf-8")


def test_peers_list_table(tmp_path: Path) -> None:
    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(
        peer,
        """
name: peer
id: peer
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host)])
    assert result.exit_code == 0, result.output
    assert "peer" in result.output
    assert "ok" in result.output


def test_peers_list_json(tmp_path: Path) -> None:
    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(
        peer,
        """
name: peer
id: peer
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["peers", "list", "--project-root", str(host), "--format=json"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["project_id"] == "host"
    assert len(payload["peers"]) == 1
    assert payload["peers"][0]["id"] == "peer"
    assert payload["peers"][0]["status"] == "ok"


def test_peers_list_path_missing(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "path-missing" in result.output


def test_peers_list_no_peers(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "list", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "no peers declared" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers_cli.py::test_peers_list_table -v
```

Expected: FAIL — `peers` subcommand isn't registered.

- [ ] **Step 3: Create `peers_cli.py`**

Create `science/src/science_tool/peers_cli.py`:

```python
"""CLI for `science-tool peers`."""

from __future__ import annotations

import json
from pathlib import Path

import click

from science_tool.peers import resolve_peer_path
from science_tool.peers_validate import PeerIssueKind, validate_peers
from science_tool.project_config import load_project_config


@click.group("peers")
def peers_group() -> None:
    """Manage and inspect project peers."""


@peers_group.command("list")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["table", "json"]),
    default="table",
)
def peers_list(project_root: Path, fmt: str) -> None:
    """List declared peers and their status."""
    project_root = Path.cwd() if str(project_root) == "." else project_root
    cfg = load_project_config(project_root)
    issues_by_id: dict[str, list[str]] = {}
    for issue in validate_peers(project_root):
        issues_by_id.setdefault(issue.peer_id, []).append(issue.kind.value)

    rows: list[dict[str, str | None]] = []
    for entry in cfg.peers:
        resolved = resolve_peer_path(project_root, entry)
        peer_issues = issues_by_id.get(entry.id, [])
        if PeerIssueKind.PATH_MISSING.value in peer_issues:
            status = "path-missing"
            resolved_str: str | None = None
        elif PeerIssueKind.NOT_A_PROJECT.value in peer_issues:
            status = "not-a-project"
            resolved_str = str(resolved)
        elif peer_issues:
            status = peer_issues[0].replace("_", "-")
            resolved_str = str(resolved)
        else:
            status = "ok"
            resolved_str = str(resolved)
        rows.append({"id": entry.id, "path": entry.path, "resolved": resolved_str, "status": status})

    if fmt == "json":
        click.echo(json.dumps({"project_id": cfg.id, "peers": rows}, indent=2))
        return

    if not rows:
        click.echo("no peers declared")
        return

    headers = ("PEER", "PATH", "STATUS")
    width_id = max(len(headers[0]), max(len(r["id"] or "") for r in rows))
    width_path = max(len(headers[1]), max(len(r["path"] or "") for r in rows))
    click.echo(f"{headers[0]:<{width_id}}  {headers[1]:<{width_path}}  {headers[2]}")
    for row in rows:
        click.echo(
            f"{row['id']:<{width_id}}  {row['path']:<{width_path}}  {row['status']}"
        )
```

- [ ] **Step 4: Register the group in `cli.py`**

In `science/src/science_tool/cli.py`, find the `main` group definition (search for `@click.group()` followed by `def main`). Add an import near the top:

```python
from science_tool.peers_cli import peers_group
```

And after `main` is defined, register the subgroup:

```python
main.add_command(peers_group)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers_cli.py::test_peers_list_table tests/test_peers_cli.py::test_peers_list_json tests/test_peers_cli.py::test_peers_list_path_missing tests/test_peers_cli.py::test_peers_list_no_peers -v
```

Expected: All four tests pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/peers_cli.py science/src/science_tool/cli.py science/tests/test_peers_cli.py
git commit -m "$(cat <<'EOF'
peers-cli: implement \`science-tool peers list\`

Tabular and JSON output, with status derived from validate_peers().
Empty peers: list renders 'no peers declared'.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 10: `peers check` command

**Files:**
- Modify: `science/src/science_tool/peers_cli.py`
- Modify: `science/tests/test_peers_cli.py`

- [ ] **Step 1: Add failing tests**

Append to `science/tests/test_peers_cli.py`:

```python
def test_peers_check_clean(tmp_path: Path) -> None:
    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(peer, "name: peer\nid: peer\nprofile: research\nresearch_question: \"...\"\n")
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "ok" in result.output.lower()


def test_peers_check_warning_does_not_fail(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "path_missing" in result.output or "path-missing" in result.output


def test_peers_check_error_exits_nonzero(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir(exist_ok=True)
    _write_yaml(a, "name: a\nid: dup\nprofile: research\nresearch_question: \"...\"\n")
    b.mkdir(exist_ok=True)
    _write_yaml(b, "name: b\nid: dup\nprofile: research\nresearch_question: \"...\"\n")
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: dup
    path: {a}
  - id: dup
    path: {b}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "check", "--project-root", str(host)])
    assert result.exit_code != 0


def test_peers_check_strict_treats_warnings_as_errors(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: ghost
    path: ../missing
""",
    )
    runner = CliRunner()
    result = runner.invoke(
        main, ["peers", "check", "--project-root", str(host), "--strict"]
    )
    assert result.exit_code != 0
```

The duplicate-id fixture intentionally creates each directory before `_write_yaml(...)`; keep that ordering when editing the test.

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers_cli.py::test_peers_check_clean -v
```

Expected: FAIL — `peers check` not implemented.

- [ ] **Step 3: Implement `peers check`**

Add `import sys` near the top of `science/src/science_tool/peers_cli.py`, then append:

```python
@peers_group.command("check")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
)
@click.option("--strict", is_flag=True, help="Treat warnings as errors.")
def peers_check(project_root: Path, fmt: str, strict: bool) -> None:
    """Validate the peer graph; exit non-zero on errors (or warnings with --strict)."""
    project_root = Path.cwd() if str(project_root) == "." else project_root
    issues = validate_peers(project_root)

    if fmt == "json":
        payload = [
            {
                "kind": i.kind.value,
                "peer_id": i.peer_id,
                "detail": i.detail,
                "severity": i.severity,
            }
            for i in issues
        ]
        click.echo(json.dumps(payload, indent=2))
    else:
        for issue in issues:
            click.echo(f"{issue.severity.upper():<8} [{issue.peer_id}] {issue.kind.value}: {issue.detail}")
        n_err = sum(1 for i in issues if i.severity == "error")
        n_warn = sum(1 for i in issues if i.severity == "warning")
        cfg = load_project_config(project_root)
        click.echo(f"ok: {len(cfg.peers)} peers, {n_warn} warning, {n_err} error")

    n_err = sum(1 for i in issues if i.severity == "error")
    n_warn = sum(1 for i in issues if i.severity == "warning")
    if n_err > 0 or (strict and n_warn > 0):
        sys.exit(1)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers_cli.py -v
```

Expected: All `peers list` and `peers check` tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers_cli.py science/tests/test_peers_cli.py
git commit -m "$(cat <<'EOF'
peers-cli: implement \`science-tool peers check\`

Surfaces all PeerIssues from validate_peers(); exits non-zero on
errors, or on warnings with --strict. Supports text and JSON output.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 11: `peers show` command

**Files:**
- Modify: `science/src/science_tool/peers_cli.py`
- Modify: `science/tests/test_peers_cli.py`

- [ ] **Step 1: Add failing test**

Append to `science/tests/test_peers_cli.py`:

```python
def test_peers_show(tmp_path: Path) -> None:
    peer = tmp_path / "mm30-dir"
    peer.mkdir()
    _write_yaml(
        peer,
        """
name: multiple-myeloma-30
id: mm30
role: cancer-type
profile: research
research_question: "..."
""",
    )
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: mm30
    path: {peer}
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "show", "mm30", "--project-root", str(host)])
    assert result.exit_code == 0
    assert "mm30" in result.output
    assert "multiple-myeloma-30" in result.output
    assert "cancer-type" in result.output


def test_peers_show_unknown_fails(tmp_path: Path) -> None:
    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        """
name: host
id: host
profile: research
research_question: "..."
""",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["peers", "show", "ghost", "--project-root", str(host)])
    assert result.exit_code != 0
    assert "ghost" in result.output.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers_cli.py::test_peers_show -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `peers show`**

Append to `science/src/science_tool/peers_cli.py`:

```python
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
    from science_tool.peers import PeerNotFound, PeerUnresolved, make_local_resolver  # noqa: PLC0415

    project_root = Path.cwd() if str(project_root) == "." else project_root
    resolver = make_local_resolver(project_root)
    try:
        resolved = resolver.resolve(peer_id)
    except PeerNotFound as exc:
        raise click.ClickException(str(exc)) from exc
    except PeerUnresolved as exc:
        raise click.ClickException(str(exc)) from exc

    peer_cfg = load_project_config(resolved.path)
    click.echo(f"id:       {resolved.id}")
    click.echo(f"name:     {peer_cfg.name}")
    click.echo(f"role:     {peer_cfg.role}")
    click.echo(f"path:     {resolved.path}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers_cli.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers_cli.py science/tests/test_peers_cli.py
git commit -m "$(cat <<'EOF'
peers-cli: implement \`science-tool peers show\`

Renders a single peer's id/name/role/path. Unknown or unresolved
peers raise a clear ClickException.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 12: `peers_migrate.py` — pure migration logic

**Files:**
- Create: `science/src/science_tool/peers_migrate.py`
- Test: `science/tests/test_peers_migrate.py`

Pure-function module: takes a path, reads raw YAML, returns a tuple `(migrated_yaml: str, summary: MigrationSummary)`. No CLI here — that lands in Task 13.

- [ ] **Step 1: Create the test file**

Create `science/tests/test_peers_migrate.py`:

```python
"""Tests for science_tool.peers_migrate."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_yaml(path: Path, body: str) -> None:
    (path / "science.yaml").write_text(body, encoding="utf-8")


def test_migrate_parent_to_peer(tmp_path: Path) -> None:
    from science_tool.peers_migrate import migrate_project

    parent = tmp_path / "meta"
    parent.mkdir()
    _write_yaml(parent, "name: meta\nid: meta\nprofile: research\nresearch_question: \"...\"\n")
    child = tmp_path / "child"
    child.mkdir()
    _write_yaml(
        child,
        f"""
name: child
id: child
profile: research
research_question: "..."
parent: {parent}
""",
    )

    summary = migrate_project(child, dry_run=False)

    assert summary.migrated is True
    text = (child / "science.yaml").read_text(encoding="utf-8")
    assert "parent:" not in text
    assert "peers:" in text
    assert "meta" in text


def test_migrate_children_to_peers(tmp_path: Path) -> None:
    from science_tool.peers_migrate import migrate_project

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _write_yaml(a, "name: a\nid: a\nprofile: research\nresearch_question: \"...\"\n")
    _write_yaml(b, "name: b\nid: b\nprofile: research\nresearch_question: \"...\"\n")
    meta = tmp_path / "meta"
    meta.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
  - id: b
    path: {b}
""",
    )

    summary = migrate_project(meta, dry_run=False)

    assert summary.migrated is True
    text = (meta / "science.yaml").read_text(encoding="utf-8")
    assert "children:" not in text
    assert "peers:" in text
    assert "id: a" in text
    assert "id: b" in text
    assert "role: data-source" not in text  # per-peer role dropped


def test_migrate_idempotent(tmp_path: Path) -> None:
    from science_tool.peers_migrate import migrate_project

    parent = tmp_path / "meta"
    parent.mkdir()
    _write_yaml(parent, "name: meta\nid: meta\nprofile: research\nresearch_question: \"...\"\n")
    project = tmp_path / "child"
    project.mkdir()
    _write_yaml(
        project,
        f"""
name: child
id: child
profile: research
research_question: "..."
parent: {parent}
""",
    )

    migrate_project(project, dry_run=False)
    text_after_first = (project / "science.yaml").read_text(encoding="utf-8")
    summary = migrate_project(project, dry_run=False)
    assert summary.migrated is False
    assert summary.note and "nothing to migrate" in summary.note.lower()
    text_after_second = (project / "science.yaml").read_text(encoding="utf-8")
    assert text_after_first == text_after_second


def test_migrate_dry_run_does_not_write(tmp_path: Path) -> None:
    from science_tool.peers_migrate import migrate_project

    parent = tmp_path / "meta"
    parent.mkdir()
    _write_yaml(parent, "name: meta\nid: meta\nprofile: research\nresearch_question: \"...\"\n")
    project = tmp_path / "child"
    project.mkdir()
    original_yaml = f"""
name: child
id: child
profile: research
research_question: "..."
parent: {parent}
"""
    _write_yaml(project, original_yaml)

    summary = migrate_project(project, dry_run=True)
    assert summary.migrated is True
    assert (project / "science.yaml").read_text(encoding="utf-8") == original_yaml


def test_migrate_missing_parent_path_fails(tmp_path: Path) -> None:
    from science_tool.peers_migrate import MigrationError, migrate_project

    project = tmp_path / "child"
    project.mkdir()
    _write_yaml(
        project,
        """
name: child
id: child
profile: research
research_question: "..."
parent: ../does-not-exist
""",
    )
    with pytest.raises(MigrationError, match="no science.yaml"):
        migrate_project(project, dry_run=False)


def test_migrate_no_legacy_fields_returns_unchanged(tmp_path: Path) -> None:
    from science_tool.peers_migrate import migrate_project

    project = tmp_path / "host"
    project.mkdir()
    _write_yaml(
        project,
        """
name: host
id: host
profile: research
research_question: "..."
""",
    )
    summary = migrate_project(project, dry_run=False)
    assert summary.migrated is False
    assert summary.note and "nothing to migrate" in summary.note.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers_migrate.py -v
```

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `peers_migrate.py`**

Create `science/src/science_tool/peers_migrate.py`:

```python
"""Migrate parent: / children: science.yaml fields to peers:.

See project-peers design Decision 9.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class MigrationError(Exception):
    """Migration cannot proceed (e.g., parent path unreadable)."""


@dataclass
class MigrationSummary:
    migrated: bool
    note: str | None = None


def migrate_project(project_root: Path, *, dry_run: bool) -> MigrationSummary:
    """Migrate `parent:` and `children:` to `peers:` in project_root/science.yaml.

    Idempotent: if no legacy fields are present, returns migrated=False with a
    "nothing to migrate" note. Raises MigrationError if a `parent:` path
    cannot be read (we need the peer's id from its science.yaml).
    """
    yaml_path = project_root / "science.yaml"
    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    has_parent = "parent" in raw and raw["parent"] is not None
    has_children = bool(raw.get("children"))

    if not has_parent and not has_children:
        return MigrationSummary(migrated=False, note="No legacy fields found; nothing to migrate.")

    peers: list[dict[str, str]] = list(raw.get("peers") or [])
    seen_ids = {entry["id"] for entry in peers if isinstance(entry, dict) and "id" in entry}

    # parent: → peer
    if has_parent:
        parent_path_str = raw["parent"]
        parent_path = (project_root / parent_path_str).expanduser() if not str(parent_path_str).startswith(("/", "~")) else Path(parent_path_str).expanduser()
        parent_path = parent_path.resolve(strict=False)
        parent_yaml = parent_path / "science.yaml"
        if not parent_yaml.is_file():
            raise MigrationError(
                f"cannot migrate parent: {parent_path_str!r} — "
                f"no science.yaml found at resolved path {parent_path}. "
                "Fix the path, or remove the parent: line manually before migrating."
            )
        try:
            parent_raw = yaml.safe_load(parent_yaml.read_text(encoding="utf-8")) or {}
        except Exception as exc:  # noqa: BLE001
            raise MigrationError(
                f"cannot migrate parent: {parent_path_str!r} — "
                f"failed to parse {parent_yaml}: {exc}"
            ) from exc
        parent_id = parent_raw.get("id") or parent_path.name
        if parent_id in seen_ids:
            existing = next(p for p in peers if p.get("id") == parent_id)
            if existing.get("path") != parent_path_str:
                raise MigrationError(
                    f"peer id {parent_id!r} already declared with different path "
                    f"{existing.get('path')!r}; refusing to overwrite"
                )
        else:
            peers.append({"id": parent_id, "path": parent_path_str})
            seen_ids.add(parent_id)
        del raw["parent"]

    # children: → peers
    if has_children:
        for child in raw["children"]:
            if not isinstance(child, dict) or "id" not in child or "path" not in child:
                continue
            child_id = child["id"]
            child_path = child["path"]
            if child_id in seen_ids:
                existing = next(p for p in peers if p.get("id") == child_id)
                if existing.get("path") != child_path:
                    raise MigrationError(
                        f"peer id {child_id!r} already declared with different path "
                        f"{existing.get('path')!r}; refusing to overwrite"
                    )
            else:
                peers.append({"id": child_id, "path": child_path})
                seen_ids.add(child_id)
        del raw["children"]

    raw["peers"] = peers

    if dry_run:
        return MigrationSummary(migrated=True, note="dry-run: no files written")

    yaml_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return MigrationSummary(migrated=True)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers_migrate.py -v
```

Expected: All six tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers_migrate.py science/tests/test_peers_migrate.py
git commit -m "$(cat <<'EOF'
peers-migrate: pure migration logic for parent: / children: → peers:

Reads raw YAML, rewrites in place (or returns dry-run summary). Fails
on unreadable parent paths since the peer's id is needed; succeeds on
missing children paths since the legacy manifest carries the id.
Idempotent.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 13: `peers migrate` CLI command (single project + `--all`)

**Files:**
- Modify: `science/src/science_tool/peers_cli.py`
- Modify: `science/tests/test_peers_cli.py`

- [ ] **Step 1: Add failing tests**

Append to `science/tests/test_peers_cli.py`:

```python
def test_peers_migrate_single(tmp_path: Path) -> None:
    parent = tmp_path / "meta"
    parent.mkdir()
    _write_yaml(parent, "name: meta\nid: meta\nprofile: research\nresearch_question: \"...\"\n")
    project = tmp_path / "child"
    project.mkdir()
    _write_yaml(
        project,
        f"""
name: child
id: child
profile: research
research_question: "..."
parent: {parent}
""",
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["peers", "migrate", "--project-root", str(project)]
    )
    assert result.exit_code == 0, result.output
    text = (project / "science.yaml").read_text(encoding="utf-8")
    assert "parent:" not in text
    assert "peers:" in text


def test_peers_migrate_dry_run(tmp_path: Path) -> None:
    parent = tmp_path / "meta"
    parent.mkdir()
    _write_yaml(parent, "name: meta\nid: meta\nprofile: research\nresearch_question: \"...\"\n")
    project = tmp_path / "child"
    project.mkdir()
    original_text = f"""
name: child
id: child
profile: research
research_question: "..."
parent: {parent}
"""
    _write_yaml(project, original_text)

    runner = CliRunner()
    result = runner.invoke(
        main, ["peers", "migrate", "--project-root", str(project), "--dry-run"]
    )
    assert result.exit_code == 0
    assert (project / "science.yaml").read_text(encoding="utf-8") == original_text


def test_peers_migrate_all_walks_children(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _write_yaml(a, "name: a\nid: a\nprofile: research\nresearch_question: \"...\"\n")
    _write_yaml(b, "name: b\nid: b\nprofile: research\nresearch_question: \"...\"\n")
    meta = tmp_path / "meta"
    meta.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
  - id: b
    path: {b}
""",
    )

    runner = CliRunner()
    result = runner.invoke(
        main, ["peers", "migrate", "--project-root", str(meta), "--all"]
    )
    assert result.exit_code == 0, result.output

    # meta now has peers, no children
    meta_text = (meta / "science.yaml").read_text(encoding="utf-8")
    assert "children:" not in meta_text
    assert "peers:" in meta_text
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_peers_cli.py::test_peers_migrate_single -v
```

Expected: FAIL.

- [ ] **Step 3: Implement `peers migrate`**

Append to `science/src/science_tool/peers_cli.py`:

```python
@peers_group.command("migrate")
@click.option(
    "--project-root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
)
@click.option("--dry-run", is_flag=True, help="Print what would change without writing.")
@click.option(
    "--all",
    "migrate_all",
    is_flag=True,
    help="Walk legacy children: and migrate each child too (one-shot).",
)
def peers_migrate_cli(project_root: Path, dry_run: bool, migrate_all: bool) -> None:
    """Migrate parent: / children: in science.yaml to peers:."""
    from science_tool.peers_migrate import MigrationError, migrate_project  # noqa: PLC0415
    import yaml as _yaml  # noqa: PLC0415

    project_root = Path.cwd() if str(project_root) == "." else project_root
    targets: list[Path] = [project_root]
    if migrate_all:
        # Walk the legacy children: in the host's raw YAML BEFORE migrating it.
        raw = _yaml.safe_load((project_root / "science.yaml").read_text(encoding="utf-8")) or {}
        for child in raw.get("children") or []:
            if not isinstance(child, dict) or "path" not in child:
                continue
            cp = child["path"]
            child_path = (
                Path(cp).expanduser()
                if str(cp).startswith(("/", "~"))
                else (project_root / cp)
            ).resolve(strict=False)
            if (child_path / "science.yaml").is_file():
                targets.append(child_path)

    for target in targets:
        try:
            summary = migrate_project(target, dry_run=dry_run)
        except MigrationError as exc:
            raise click.ClickException(str(exc)) from exc
        if summary.migrated:
            verb = "would migrate" if dry_run else "migrated"
            click.echo(f"{verb}: {target}")
        else:
            click.echo(f"skipped: {target} — {summary.note}")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_peers_cli.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/peers_cli.py science/tests/test_peers_cli.py
git commit -m "$(cat <<'EOF'
peers-cli: implement \`science-tool peers migrate\` (with --all and --dry-run)

CLI wrapper over peers_migrate.migrate_project. --all walks the legacy
children: list and migrates each child too — necessary for one-shot
meta-project migrations since children: is removed from ProjectConfig
in a follow-up task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 14: Run migration on this monorepo

**Files:**
- Modify: any live `science.yaml` files reported by the pre-check (often none in the current monorepo; historical fixtures are handled by tests)
- Test: existing test suite (no new tests; this is a data migration)

**Pre-check command (run BEFORE migrating):**

```bash
grep -rln "^parent:\|^children:" --include="science.yaml" .
```

Note the file list. If it is empty, record that no live monorepo configs need migration and skip Steps 1-2 and Step 6. Do not create an empty commit.

- [ ] **Step 1: Dry-run the migration**

```bash
cd meta && uv run science peers migrate --all --dry-run
```

Expected: prints "would migrate: <path>" for each affected science.yaml.

- [ ] **Step 2: Apply the migration**

```bash
cd meta && uv run science peers migrate --all
```

Expected: prints "migrated: <path>" for each.

- [ ] **Step 3: Verify the legacy fields are gone**

```bash
grep -l "^parent:\|^children:" $(grep -rl "" --include="science.yaml" .) 2>/dev/null
```

Expected: no output for live project configs (no remaining top-level `parent:` or `children:` keys). Historical test fixtures may still contain legacy YAML until Task 17.

- [ ] **Step 4: Run validate to confirm clean state**

```bash
cd meta && uv run science peers check
```

Expected: 0 errors. Some `path-missing` warnings are acceptable for projects whose paths are outside the monorepo.

- [ ] **Step 5: Run the full test suite**

```bash
cd science && uv run pytest -q
```

Expected: all green (everything still passes because Phase A code accepts both forms).

- [ ] **Step 6: Commit the migrated YAML files**

```bash
git add -- '**/science.yaml'
git commit -m "$(cat <<'EOF'
chore: migrate parent: / children: to peers: in this monorepo

Runs \`science-tool peers migrate --all\` on meta and its children.
Schema-level rejection of the legacy fields lands in a follow-up task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 15: Add `graph/composite.py` (additive — alongside `graph/federation.py`)

**Files:**
- Create: `science/src/science_tool/graph/composite.py`
- Test: `science/tests/test_graph_composite.py`

This task adds the new module without removing federation.py. The CLI integration (Task 16) uses composite.py going forward; federation.py is deleted in Task 19.

- [ ] **Step 1: Create the test file**

Create `science/tests/test_graph_composite.py` (model after `tests/test_graph_federation.py`):

```python
"""Tests for science_tool.graph.composite."""

from __future__ import annotations

from pathlib import Path

import rdflib
from rdflib import Dataset, URIRef


def _write_yaml(path: Path, body: str) -> None:
    (path / "science.yaml").write_text(body, encoding="utf-8")


def _write_local_trig(root: Path, project_id: str) -> None:
    knowledge = root / "knowledge"
    knowledge.mkdir(exist_ok=True)
    dataset = Dataset()
    ex = rdflib.Namespace("https://example.org/")
    g = dataset.graph(URIRef("https://example.org/local"))
    g.add((URIRef(f"{ex}{project_id}"), rdflib.RDF.type, ex.Project))
    dataset.serialize(destination=knowledge / "graph.trig", format="trig")


def test_composite_unions_peers_local_graphs(tmp_path: Path) -> None:
    from science_tool.graph.composite import assemble_composite_graph

    peer_a = tmp_path / "peer-a"
    peer_a.mkdir()
    _write_yaml(peer_a, "name: a\nid: a\nprofile: research\nresearch_question: \"...\"\n")
    _write_local_trig(peer_a, "a")

    peer_b = tmp_path / "peer-b"
    peer_b.mkdir()
    _write_yaml(peer_b, "name: b\nid: b\nprofile: research\nresearch_question: \"...\"\n")
    _write_local_trig(peer_b, "b")

    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: a
    path: {peer_a}
  - id: b
    path: {peer_b}
""",
    )
    _write_local_trig(host, "host")

    out = assemble_composite_graph(host)
    assert out == host / "knowledge" / "composite.trig"
    assert out.is_file()

    ds = Dataset()
    ds.parse(out, format="trig")
    triples = {(s, p, o) for s, p, o in ds.triples((None, None, None))}
    assert any("host" in str(s) for s, _, _ in triples)
    assert any(str(s).endswith("/a") for s, _, _ in triples)
    assert any(str(s).endswith("/b") for s, _, _ in triples)


def test_composite_skips_peer_with_no_local_graph(tmp_path: Path) -> None:
    """Peer with composite.trig but no graph.trig is skipped (Decision 6)."""
    from science_tool.graph.composite import assemble_composite_graph

    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(peer, "name: peer\nid: peer\nprofile: research\nresearch_question: \"...\"\n")
    (peer / "knowledge").mkdir()
    (peer / "knowledge" / "composite.trig").write_text(
        "@prefix : <https://example.org/> . :x :y :z .", encoding="utf-8"
    )
    # No graph.trig.

    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
    )
    _write_local_trig(host, "host")

    out = assemble_composite_graph(host)
    ds = Dataset()
    ds.parse(out, format="trig")
    # Peer's composite.trig content must NOT be unioned in.
    assert not any(":x" in str(s) for s, _, _ in ds.triples((None, None, None)))


def test_composite_no_peers_writes_only_local(tmp_path: Path) -> None:
    from science_tool.graph.composite import assemble_composite_graph

    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(host, "name: host\nid: host\nprofile: research\nresearch_question: \"...\"\n")
    _write_local_trig(host, "host")

    out = assemble_composite_graph(host)
    assert out.is_file()
    ds = Dataset()
    ds.parse(out, format="trig")
    assert any("host" in str(s) for s, _, _ in ds.triples((None, None, None)))


def test_composite_bidirectional_peering_does_not_recurse(tmp_path: Path) -> None:
    """A peers B, B peers A: both composite outputs must be deterministic and finite."""
    from science_tool.graph.composite import assemble_composite_graph

    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    _write_yaml(
        a,
        f"""
name: a
id: a
profile: research
research_question: "..."
peers:
  - id: b
    path: {b}
""",
    )
    _write_yaml(
        b,
        f"""
name: b
id: b
profile: research
research_question: "..."
peers:
  - id: a
    path: {a}
""",
    )
    _write_local_trig(a, "a")
    _write_local_trig(b, "b")

    out_a = assemble_composite_graph(a)
    out_b = assemble_composite_graph(b)
    # Both succeed without infinite recursion.
    assert out_a.is_file()
    assert out_b.is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_graph_composite.py -v
```

Expected: FAIL — `science_tool.graph.composite` doesn't exist.

- [ ] **Step 3: Create `graph/composite.py`**

Model after `science/src/science_tool/graph/federation.py`. Create `science/src/science_tool/graph/composite.py`:

```python
"""Composite graph assembly: union the host's local graph with each peer's local graph.

Per project-peers design Decision 6:
- Composite reads ONLY locals (each peer's `knowledge/graph.trig`).
- Composite NEVER reads another project's `composite.trig`.
- Output is at `<root>/knowledge/composite.trig` (separate from local `graph.trig`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from rdflib import Dataset, Literal, URIRef
from rdflib.graph import Graph
from rdflib.namespace import PROV, RDF, XSD

from science_tool.graph.io import save_canonical_graph_dataset
from science_tool.peers import make_local_resolver
from science_tool.project_config import load_project_config

_URI_SCHEME = "cancer"


def _project_uri(project_id: str) -> URIRef:
    return URIRef(f"{_URI_SCHEME}://{project_id}")


def assemble_composite_graph(project_root: Path) -> Path:
    """Assemble project_root/knowledge/composite.trig from host + peers' locals."""
    cfg = load_project_config(project_root)
    out_dir = project_root / "knowledge"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "composite.trig"

    dataset = Dataset()
    host_uri = _project_uri(cfg.id or project_root.name)
    host_graph = dataset.graph(host_uri)
    _include_local_graph(project_root, host_graph)

    resolver = make_local_resolver(project_root)
    for peer_id in sorted(resolver.known_ids()):
        try:
            peer = resolver.resolve(peer_id)
        except Exception:  # noqa: BLE001
            continue
        peer_uri = _project_uri(peer_id)
        included = _include_peer_local(dataset, peer.path, peer_uri)
        if included:
            peer_graph_path = peer.path / "knowledge" / "graph.trig"
            source_uri = URIRef(peer_graph_path.resolve().as_uri())
            host_graph.add((peer_uri, PROV.wasDerivedFrom, source_uri))
            host_graph.add((source_uri, RDF.type, PROV.Entity))
            host_graph.add(
                (peer_uri, PROV.generatedAtTime, _source_graph_timestamp(peer_graph_path))
            )

    save_canonical_graph_dataset(dataset, out_path)
    return out_path


def _include_local_graph(project_root: Path, dest: Graph) -> None:
    src_path = project_root / "knowledge" / "graph.trig"
    if not src_path.is_file():
        return
    src = Dataset()
    src.parse(src_path, format="trig")
    for graph in src.graphs():
        for triple in graph:
            dest.add(triple)


def _include_peer_local(dataset: Dataset, peer_root: Path, peer_uri: URIRef) -> bool:
    """Read ONLY peer/knowledge/graph.trig (the local). Never composite.trig."""
    src_path = peer_root / "knowledge" / "graph.trig"
    if not src_path.is_file():
        return False
    target = dataset.graph(peer_uri)
    src = Dataset()
    src.parse(src_path, format="trig")
    for graph in src.graphs():
        for triple in graph:
            target.add(triple)
    return True


def _source_graph_timestamp(graph_path: Path) -> Literal:
    seconds, nanoseconds = divmod(graph_path.stat().st_mtime_ns, 1_000_000_000)
    timestamp = datetime.fromtimestamp(seconds, tz=timezone.utc).replace(
        microsecond=nanoseconds // 1000
    )
    return Literal(timestamp.isoformat().replace("+00:00", "Z"), datatype=XSD.dateTime)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd science && uv run pytest tests/test_graph_composite.py -v
```

Expected: All four tests pass.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/composite.py science/tests/test_graph_composite.py
git commit -m "$(cat <<'EOF'
graph/composite: assemble_composite_graph reads peers' locals only

Writes <root>/knowledge/composite.trig; never reads another project's
composite.trig (per project-peers design Decision 6). Bidirectional
peering is order-independent and recursion-free.

federation.py is kept until consumers migrate; deleted in a follow-up
task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 16: Refactor `cli.py:graph_build` to use composite + drop META branch

**Files:**
- Modify: `science/src/science_tool/cli.py:720-766` (the `graph_build` command body)
- Test: existing tests in `tests/test_graph_build*.py` plus a new test

After this task: `graph_build` always writes `knowledge/graph.trig` as local-only, and additionally writes `knowledge/composite.trig` whenever the project has peers. The `if _cfg.role == ProjectRole.META` branch is removed.

- [ ] **Step 1: Add a failing test for the composite output**

Append to `science/tests/test_graph_composite.py`:

```python
def test_graph_build_writes_composite_when_peers_present(tmp_path: Path) -> None:
    """`science-tool graph build` writes composite.trig if peers: is non-empty."""
    from click.testing import CliRunner
    from science_tool.cli import main

    peer = tmp_path / "peer"
    peer.mkdir()
    _write_yaml(peer, "name: peer\nid: peer\nprofile: research\nresearch_question: \"...\"\n")
    _write_local_trig(peer, "peer")

    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(
        host,
        f"""
name: host
id: host
profile: research
research_question: "..."
peers:
  - id: peer
    path: {peer}
""",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])
    assert result.exit_code == 0, result.output
    assert (host / "knowledge" / "graph.trig").is_file()
    assert (host / "knowledge" / "composite.trig").is_file()


def test_graph_build_no_peers_no_composite(tmp_path: Path) -> None:
    from click.testing import CliRunner
    from science_tool.cli import main

    host = tmp_path / "host"
    host.mkdir()
    _write_yaml(host, "name: host\nid: host\nprofile: research\nresearch_question: \"...\"\n")

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(host)])
    assert result.exit_code == 0
    assert (host / "knowledge" / "graph.trig").is_file()
    assert not (host / "knowledge" / "composite.trig").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_graph_composite.py::test_graph_build_writes_composite_when_peers_present -v
```

Expected: FAIL — `graph_build` still uses the META/federation path; doesn't write `composite.trig`.

- [ ] **Step 3: Refactor `graph_build` in `cli.py`**

In `science/src/science_tool/cli.py:720-766`, replace the body of `graph_build` with:

```python
def graph_build(project_root: Path) -> None:
    """Materialize graph.trig (local) and composite.trig (peers union) if applicable."""
    from science_tool.graph.composite import assemble_composite_graph
    from science_tool.project_config import load_project_config
    from science_tool.registry.config import ensure_registered

    _project_root = Path.cwd() if str(project_root) == "." else project_root
    _science_yaml = _project_root / "science.yaml"
    _cfg = None
    if _science_yaml.is_file():
        _cfg = load_project_config(_project_root)
        ensure_registered(
            _project_root,
            _cfg.name,
            project_id=_cfg.id,
            role=str(_cfg.role),
            parent=None,  # parent: removed; registry-side compat handled by registry
        )

    try:
        local_path = materialize_graph(_project_root)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"Materialized local graph at {local_path}")

    if _cfg is not None and _cfg.peers:
        composite_path = assemble_composite_graph(_project_root)
        click.echo(f"Materialized composite graph at {composite_path}")

    # Non-blocking ontology suggestions
    from science_tool.graph.sources import load_project_sources
    from science_tool.graph.suggest import suggest_ontologies

    try:
        sources = load_project_sources(project_root)
        suggestions = suggest_ontologies(
            entities=sources.entities,
            declared_ontologies=[c.ontology for c in sources.ontology_catalogs],
        )
        for s in suggestions:
            click.echo(
                f"  Ontology suggestion: {s.entity_count} entities match '{s.ontology_name}' "
                f"— consider adding `ontologies: [{s.ontology_name}]` to science.yaml"
            )
    except Exception:  # noqa: BLE001
        pass  # Suggestions are non-blocking
```

Also delete the `from science_tool.graph.federation import assemble_federated_graph` import at the top of the function (line 722 in the current file). The `from science_tool.project_config import ProjectRole` import is also unused after this refactor — delete it from `graph_build` (it may still be used elsewhere in `cli.py`; only remove from the function-local imports).

- [ ] **Step 4: Run tests**

```bash
cd science && uv run pytest tests/test_graph_composite.py tests/test_graph_federation.py -v
```

Expected: new composite tests pass. Existing federation tests may fail — that's OK; they're deleted in Task 19.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/cli.py science/tests/test_graph_composite.py
git commit -m "$(cat <<'EOF'
cli: graph build writes local + composite (drops META branch)

Replaces the role==META / parent-aware branch with a uniform two-step
build: materialize_graph for the local artifact (always), and
assemble_composite_graph for the peers union (when peers exist).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase B — Breaking switchover (remove legacy fields, delete dead code)

### Task 17: Update test fixtures from `children:` / `parent:` to `peers:`

**Files:**
- Modify: `science/tests/test_project_config.py`
- Modify: `science/tests/test_validate_script.py`
- Modify: `science/tests/test_graph_federation.py` (will be deleted in Task 19, but updating now keeps the suite green throughout)
- Modify: `science/tests/test_graph_build_federated.py` (also slated for deletion; leave as-is unless it blocks intermediate verification)
- Modify: `science/tests/test_federation_*.py` (also slated for deletion; leave as-is — they'll be deleted in Task 19)

The goal: tests that we're KEEPING should not depend on `children:` or `parent:`. Tests slated for deletion can stay until Task 19.

- [ ] **Step 1: Identify tests to keep that touch legacy fields**

```bash
grep -ln "children:\|^parent:" science/tests/test_project_config.py science/tests/test_validate_script.py
```

Expected output: both files.

- [ ] **Step 2: Update `test_project_config.py`**

In `science/tests/test_project_config.py`:

- Locate `assert cfg.parent is None` and `assert cfg.children == []` assertions in `test_loads_minimal_existing_yaml`. Replace with `assert cfg.peers == []` (and remove the parent/children asserts).
- Locate any test using `children:` in fixture YAML. Either rewrite to use `peers:` form, or move the test to `test_peers_migrate.py` (if it's actually about migration).
- Locate any test using `parent:` in fixture YAML. Rewrite to `peers:`.
- Delete or replace tests whose only purpose was legacy schema behavior (`children` only on meta, duplicate child IDs). Duplicate peer IDs and self-peers now belong to `test_peers_validate.py`; legacy-field rejection is added in Task 18.

Concretely, search and replace fixture blocks like:

```yaml
children:
  - id: a
    path: ...
```

to:

```yaml
peers:
  - id: a
    path: ...
```

- [ ] **Step 3: Update `test_validate_script.py` fixtures only**

In `science/tests/test_validate_script.py`, locate fixture YAML at lines 1276 and 1357 that uses `children:` and rewrite to `peers:`. Do **not** change the error-message expectation at line 1339 (`"Add it to science.yaml children:..."`) — that assertion matches the current validate.sh output and must stay green until Task 20 updates the script.

- [ ] **Step 4: Run the suite**

```bash
cd science && uv run pytest tests/test_project_config.py tests/test_validate_script.py -v
```

Expected: all green. Fixtures use peers: form; the children-mention error-message test still passes because it asserts the current (pre-Task-20) validate.sh output.

- [ ] **Step 5: Commit**

```bash
git add science/tests/test_project_config.py science/tests/test_validate_script.py
git commit -m "$(cat <<'EOF'
tests: migrate kept fixtures from children:/parent: to peers:

Updates tests that survive the federation deletion to use peers:
fixtures. Federation-specific tests are deleted in a follow-up task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 18: Reject `parent:` and `children:` in `ProjectConfig`

**Files:**
- Modify: `science/src/science_tool/project_config.py`
- Modify: `science/tests/test_project_config.py`

- [ ] **Step 1: Add failing tests for rejection**

Append to `science/tests/test_project_config.py`:

```python
def test_project_config_rejects_legacy_parent(tmp_path: Path) -> None:
    """parent: is removed; loading a config with it must fail clearly."""
    project_root = tmp_path / "host"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: host
id: host
profile: research
research_question: "..."
parent: ../meta
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="peers migrate"):
        load_project_config(project_root)


def test_project_config_rejects_legacy_children(tmp_path: Path) -> None:
    """children: is removed; loading a config with it must fail clearly."""
    project_root = tmp_path / "meta"
    project_root.mkdir()
    (project_root / "science.yaml").write_text(
        """
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: ../a
""",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="peers migrate"):
        load_project_config(project_root)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd science && uv run pytest tests/test_project_config.py::test_project_config_rejects_legacy_parent tests/test_project_config.py::test_project_config_rejects_legacy_children -v
```

Expected: FAIL — both fields still load silently.

- [ ] **Step 3: Update `ProjectConfig`**

In `science/src/science_tool/project_config.py`:

1. Delete `ChildEntry` class.
2. Delete `resolve_child_path` function.
3. Delete the `parent: str | None` and `children: list[ChildEntry]` fields from `ProjectConfig`.
4. Delete the `_children_only_on_meta` and `_children_unique_ids` validators.
5. Add `_reject_legacy_fields` BEFORE-mode validator:

```python
    @model_validator(mode="before")
    @classmethod
    def _reject_legacy_fields(cls, raw: Any) -> Any:
        if isinstance(raw, dict):
            illegal = [k for k in ("parent", "children") if k in raw]
            if illegal:
                raise ValueError(
                    f"science.yaml uses removed field(s) {illegal!r}. "
                    "Run `science-tool peers migrate` to migrate to `peers:`."
                )
        return raw
```

(Also add `from typing import Any` to imports if not already present.)

- [ ] **Step 4: Run tests**

```bash
cd science && uv run pytest tests/test_project_config.py -v
```

Expected: all `test_project_config.py` tests pass.

- [ ] **Step 5: Run wider suite to find consumers that break**

```bash
cd science && uv run pytest -q
```

Expected: federation-related tests fail (those modules still call `cfg.children`). Note the failures.

- [ ] **Step 6: Update `refs._load_project_ids` to drop the children fallback**

In `science/src/science_tool/refs.py`, the function still references `cfg.children` for back-compat. Remove that:

```python
def _load_project_ids(root: Path) -> set[str]:
    try:
        cfg = load_project_config(root)
    except Exception:
        return set()
    ids: set[str] = set()
    try:
        from science_tool.peers import make_local_resolver  # noqa: PLC0415
        ids.update(make_local_resolver(root).known_ids())
    except Exception:  # noqa: BLE001
        pass
    if cfg.id:
        ids.add(cfg.id)
    return ids
```

- [ ] **Step 7: Run the suite again, isolating non-federation tests**

```bash
cd science && uv run pytest --ignore=tests/test_federation_cli.py --ignore=tests/test_federation_validation.py --ignore=tests/test_federation_integration.py --ignore=tests/test_federation_status_cli.py --ignore=tests/test_graph_federation.py --ignore=tests/test_graph_build_federated.py --ignore=tests/test_graph_build_parent_register.py -q
```

Expected: all green.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/project_config.py science/src/science_tool/refs.py science/tests/test_project_config.py
git commit -m "$(cat <<'EOF'
project-config: reject parent: / children: with migration message

Removes ChildEntry, resolve_child_path, and the parent/children fields
from ProjectConfig. Adds _reject_legacy_fields before-validator with a
clear "run \`science-tool peers migrate\`" message. refs._load_project_ids
drops its children fallback.

Federation modules and their tests still depend on the deleted fields;
they are deleted in the next task.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 19: Delete federation modules and their tests

**Files (delete entirely):**

- `science/src/science_tool/federation.py`
- `science/src/science_tool/federation_cli.py`
- `science/src/science_tool/federation_status.py`
- `science/src/science_tool/graph/federation.py`
- `science/tests/test_federation_cli.py`
- `science/tests/test_federation_validation.py`
- `science/tests/test_federation_integration.py`
- `science/tests/test_federation_status_cli.py`
- `science/tests/test_graph_federation.py`
- `science/tests/test_graph_build_federated.py`
- `science/tests/test_graph_build_parent_register.py`

**Files (modify to remove federation references):**

- `science/src/science_tool/cli.py` — remove the `federation` subcommand registration and any imports of the deleted modules.

- [ ] **Step 1: Find all federation imports/references**

```bash
grep -rn "from science_tool.federation\|federation_cli\|federation_status\|graph.federation\|assemble_federated_graph\|validate_federation\|render_federation_status" science/src/ 2>/dev/null
```

Expected: handful of references in `cli.py` and possibly `__init__.py`.

- [ ] **Step 2: Delete the source files**

```bash
rm science/src/science_tool/federation.py
rm science/src/science_tool/federation_cli.py
rm science/src/science_tool/federation_status.py
rm science/src/science_tool/graph/federation.py
```

- [ ] **Step 3: Delete the test files**

```bash
rm science/tests/test_federation_cli.py
rm science/tests/test_federation_validation.py
rm science/tests/test_federation_integration.py
rm science/tests/test_federation_status_cli.py
rm science/tests/test_graph_federation.py
rm science/tests/test_graph_build_federated.py
rm science/tests/test_graph_build_parent_register.py
```

- [ ] **Step 4: Remove federation registrations from `cli.py`**

In `science/src/science_tool/cli.py`:

- Remove the import at line 93: `from science_tool.federation_cli import federation_group`.
- Remove the registration at line 203: `main.add_command(federation_group)`.
- Confirm no remaining references to `assemble_federated_graph`, `validate_federation`, `render_federation_status`.

Re-run the grep:

```bash
grep -rn "federation" science/src/science_tool/ 2>/dev/null
```

Expected: no remaining references to deleted symbols. (Mentions of "composite" or "peers" are fine.)

- [ ] **Step 5: Run the full suite**

```bash
cd science && uv run pytest -q
```

Expected: all green (or no new failures relative to known issues).

- [ ] **Step 6: Commit**

```bash
git add -A science/src/science_tool/ science/tests/
git commit -m "$(cat <<'EOF'
chore: delete federation modules and tests

Removes federation.py, federation_cli.py, federation_status.py,
graph/federation.py, and their test files. Removes federation
subcommand registration from cli.py. Replaced by peers + composite.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 20: Update `validate.sh` template + project_artifacts

**Files:**
- Modify: `science/src/science_tool/project_artifacts/data/validate.sh`
- Modify: `science/src/science_tool/project_artifacts/registry.yaml` (bump version)
- Modify: `science/tests/test_validate_script.py` (re-check expectations)

The validate.sh template still derives known project namespaces from `children:` and its error message still says "use children:". Update both the logic and the message.

- [ ] **Step 1: Update validate.sh project namespace loading**

In `science/src/science_tool/project_artifacts/data/validate.sh`, replace the Python helper's `load_project_ids()` logic that reads `children = data.get("children")` with `peers = data.get("peers")`:

```python
def load_project_ids(path):
    if yaml is None or not os.path.isfile(path):
        return set()
    try:
        with open(path, encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception:
        return set()
    ids = set()
    project_id = data.get("id")
    if isinstance(project_id, str) and project_id:
        ids.add(project_id)
    peers = data.get("peers")
    if isinstance(peers, list):
        for peer in peers:
            if isinstance(peer, dict) and isinstance(peer.get("id"), str):
                ids.add(peer["id"])
    return ids
```

- [ ] **Step 2: Update validate.sh error messages**

In `science/src/science_tool/project_artifacts/data/validate.sh`, find the line:

```bash
warn "Legacy cross-project ref '${raw}' is missing an entity kind. Use '${project_id}:question:${slug}' or another explicit <project-id>:<kind>:<slug> ref."
```

and any nearby reference to `children:`. Update messages that mention `children:` to mention `peers:` instead. For example:

```bash
warn "Unknown project namespace '${ns}' in ref '${raw}'. Add it to science.yaml peers: or use a local ref."
```

- [ ] **Step 3: Bump artifact version**

In `science/src/science_tool/project_artifacts/registry.yaml`, find the version entry referencing `2026.05.05.1` (or the latest) and add a new entry like:

```yaml
'2026.05.05.2': 'Replace children:/parent: with peers: across templates and validators.'
```

Also update the `summary:` field on the artifact's main entry to reflect the change.

- [ ] **Step 4: Update or delete project-init scaffold templates**

```bash
grep -rn "children:\|^parent:" science/src/science_tool/project_artifacts/ 2>/dev/null
```

Replace any scaffold template's `children:` / `parent:` fixtures with `peers:` form.

- [ ] **Step 5: Update `test_validate_script.py` namespace fixtures and assertion**

Update the fixture YAML that previously declared known project IDs via `children:` so it declares them via `peers:` instead. Then update the error-message assertion.

The assertion at line 1339 of `science/tests/test_validate_script.py` reads:

```python
"Add it to science.yaml children: or use a local ref."
```

Update it to:

```python
"Add it to science.yaml peers: or use a local ref."
```

(matching the new validate.sh wording from Step 2).

- [ ] **Step 6: Run validate-script tests**

```bash
cd science && uv run pytest tests/test_validate_script.py -v
```

Expected: all green — the validate.sh template now emits the peers: wording and the test asserts the same.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/project_artifacts/ science/tests/test_validate_script.py
git commit -m "$(cat <<'EOF'
artifacts: replace children:/parent: with peers: across templates

Updates validate.sh error messages and project-init scaffolds to use
peers: instead of children:. Bumps artifact registry version.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Phase C — Documentation

### Task 21: Update `docs/federation.md` and the upstream task-IDs spec

**Files:**
- Modify: `docs/federation.md` (replace content with peers-aware addressing convention OR rewrite as `docs/peers.md`)
- Modify: `docs/federation.md` (update children: references)
- Modify: `commands/tasks.md` (update if it carries the same wording)

- [ ] **Step 1: Inventory remaining doc references**

```bash
grep -rln "children:\|^parent:\|federation\b" docs/ commands/ skills/ 2>/dev/null | grep -v "2026-05-05-project-peers\|audits/\|migration/"
```

Expected output: `docs/federation.md`, the upstream task-IDs spec/plan, possibly some `commands/` or `skills/` files.

- [ ] **Step 2: Rewrite `docs/federation.md`**

Replace its content with a peer-graph-oriented addressing convention. Open the file, read existing content, and rewrite as a peers reference document. Cross-link to `docs/plans/historical/2026-05-05-project-peers-design.md` for the full design. The body should:

- Define the canonical entity ref shape: `[<project-id>:]<kind>:<slug>` (local or namespaced).
- Note that `peers:` in `science.yaml` declares which other projects' IDs are recognized as namespaces.
- Reference Decision 1 of the project-peers design for character rules.
- NOT mention `children:` / `parent:` except as historical context (one paragraph at most).

(Optionally rename to `docs/peers.md` and leave `docs/federation.md` as a one-line redirect: `See [docs/peers.md](peers.md).` Either choice; the user can pick during execution.)

- [ ] **Step 3: Update the upstream task-IDs spec references**

In `docs/federation.md`:

- Around line 135 (Decision 5): change "the parser can use an explicit project-ID set from federation config to decide whether the first segment is a namespace" to refer to `peers:` instead of "federation config".
- Around line 255 (error-message section): change "Add it to science.yaml children: or use a local ref." to "Add it to science.yaml peers: or use a local ref."

- [ ] **Step 4: Update the upstream task-IDs plan if needed**

```bash
grep -n "children:\|federation" commands/tasks.md
```

Update similarly to the spec.

- [ ] **Step 5: Inventory and update commands/skills**

```bash
grep -rln "children:\|federation\b" commands/ skills/ 2>/dev/null
```

For each file in the output, open it, read for context, and update references from `children:` / `parent:` / federation to `peers:`. If the file documents a command that no longer exists (e.g., `science-tool federation status`), replace with the corresponding peers command (`science-tool peers list`).

- [ ] **Step 6: Verify the inventory is clean**

```bash
grep -rln "children:" docs/ commands/ skills/ 2>/dev/null | grep -v "2026-05-05-project-peers\|audits/\|migration/" || echo "clean"
```

Expected: `clean` (or only references in audit/migration documents which are historical records, not live docs).

- [ ] **Step 7: Commit**

```bash
git add docs/ commands/ skills/
git commit -m "$(cat <<'EOF'
docs: replace federation/children references with peers throughout

Rewrites docs/federation.md as the peers reference document. Updates
the upstream task-IDs spec and plan to refer to peers: instead of
children:. Inventories and updates commands/skills mentions.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 22: Add follow-up task group `project-peers` for trajectory items

**Files:**
- Modify: `meta/tasks/active.md` (via `science tasks add`)

Per the Trajectory section and the user's request: track the deferred items as tasks under group `project-peers`.

- [ ] **Step 1: Inventory existing related tasks to avoid duplicates**

```bash
grep -n "Cross-project freshness\|Cross-project typed blockers\|project-peers\|workspace registry\|remote peers\|versioned entity" meta/tasks/active.md
```

Expected: existing cross-project freshness / typed-blockers tasks may already exist. If a trajectory item is already represented, update that task's `group:` / `aspects:` / description manually instead of adding a duplicate task.

- [ ] **Step 2: Add missing trajectory tasks**

```bash
cd meta && uv run science tasks add "Cross-project blockers spec" --priority=P1 --group=project-peers --related=topic:cross-project --aspects=software-development --aspects=federation
cd meta && uv run science tasks add "Workspace registry design" --priority=P2 --group=project-peers --aspects=software-development
cd meta && uv run science tasks add "Remote peers via cloneable repos" --priority=P3 --group=project-peers --aspects=software-development
cd meta && uv run science tasks add "Versioned entity references" --priority=P3 --group=project-peers --aspects=software-development
cd meta && uv run science tasks add "L2 caching & freshness" --priority=P3 --group=project-peers --aspects=software-development
cd meta && uv run science tasks add "Composite graph policy controls (compose: opt-in)" --priority=P2 --group=project-peers --aspects=software-development
cd meta && uv run science tasks add "Service / capability exchange (Layer 3)" --priority=P2 --group=project-peers --aspects=software-development
cd meta && uv run science tasks add "Multi-user identity scoping" --priority=P3 --group=project-peers --aspects=software-development
cd meta && uv run science tasks add "Auto-unblock / change notification" --priority=P3 --group=project-peers --aspects=software-development
cd meta && uv run science tasks add "Symmetry tooling (peers check --symmetric)" --priority=P3 --group=project-peers --aspects=software-development
```

- [ ] **Step 3: Verify**

```bash
cd meta && uv run science tasks list --group=project-peers
```

Expected: every trajectory item is represented exactly once, either by an existing updated task or by a newly added task.

- [ ] **Step 4: Commit**

```bash
git add meta/tasks/
git commit -m "$(cat <<'EOF'
tasks: register project-peers trajectory items as deferred tasks

Tracks the ten deferred items from project-peers design Decision 13
(Trajectory) under task group 'project-peers' so they can be picked
up deliberately.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Verification

After all 22 tasks:

```bash
# 1. Full test suite green
cd science && uv run pytest -q

# 2. No legacy references in live code
grep -rn "ChildEntry\|cfg\.children\|cfg\.parent\|assemble_federated_graph" science/src/ 2>/dev/null && echo "FAIL" || echo "clean"

# 3. No legacy references in live docs
grep -rln "children:\|^parent:" docs/ commands/ skills/ 2>/dev/null | grep -v "audits/\|migration/\|2026-05-05-project-peers\|2026-05-05-task-ids" && echo "FAIL" || echo "clean"

# 4. Migration is idempotent
cd meta && uv run science peers migrate --all
# Expected: "skipped: <path> — No legacy fields found; nothing to migrate." for each.

# 5. Peers commands work end-to-end
cd meta && uv run science peers list
cd meta && uv run science peers check
cd meta && uv run science peers show <some-peer-id>

# 6. Composite graph builds for meta
cd meta && uv run science graph build
# Expected: writes both knowledge/graph.trig and knowledge/composite.trig.
```

All checks must pass before declaring the implementation complete.
