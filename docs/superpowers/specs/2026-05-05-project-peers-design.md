# Project Peers Design

## Status

Approved design. Replaces the tree-shaped `parent:` / `children:` federation with a decentralized peer-graph. Layer 1 (addressability) and minimal Layer 2 (read access) only; richer L2, remote peers, workspace registries, and Layer 3 (services) are deferred.

## Problem

Science projects increasingly need to reference each other's entities, tasks, datasets, and tools. Three concrete drivers:

- **Cross-project blockers:** a task in `cancer/mechanisms/evolution` is gated on a dataset that lives in a sibling project (`cancer/mm30`).
- **Knowledge / tooling reuse:** pipelines built in one project (e.g. `r/lit-explore`) should be consumable from any other project that wants to ask questions of the literature.
- **Composite views:** a "global" knowledge graph that unions multiple projects' graphs into one queryable surface.

The existing federation model (`children:` / `parent:` in `science.yaml`) is intrinsically tree-shaped. It supports meta → child aggregation but not sibling-to-sibling references, peer-to-peer tooling reuse, or arbitrary graph topologies. Upstream's `<project-id>:<kind>:<slug>` ref grammar (`docs/superpowers/specs/2026-05-05-task-ids-and-cross-project-references-design.md`) defines the syntax, but no project mechanism currently lets a project know which other-project IDs it's allowed to reference, or where those projects live on disk.

## Goals

- Define a single, decentralized addressability primitive: each project declares its **peers** (other projects it references, by canonical ID + path).
- Replace the tree-shaped `parent:` / `children:` federation with a peer-graph. Migrate existing meta-project structure cleanly.
- Define minimal read-access semantics: given a peer, read its entity index from disk.
- Reserve design space for: workspace registries, remote (cloneable / network) peers, versioned references, multi-user identity scoping, composite graphs.

## Non-Goals

- Service / capability exchange (Layer 3): tool invocation, query APIs, lit-explore-style cross-project queries. Separate spec.
- Workspace registries (deferred — design behind a swappable resolver interface so a future spec can add this without breaking changes).
- Remote peers via git URLs / HTTP / DOI (deferred; schema reserves field names).
- Versioned references (deferred; ref grammar reserves `@<version>` suffix).
- Caching, freshness, staleness detection for peer reads (deferred).
- Auto-unblock or any push-based notification across peers (deferred).
- Multi-user identity scoping (deferred).

## Layered Architecture

This spec defines **Layer 1 (addressability)** and a thin **Layer 2 (read access)**:

- **L1 — Addressability.** Project A can name project B by ID and resolve B's location on disk. Substrate for everything else.
- **L2 — Read access (minimal).** Given a resolved peer, read its entity index using the same machinery that already reads the local project's entities. No caching, no freshness contract — trust on-disk state. Richer L2 (caching, materialized graph delegation, staleness reporting) is a separate concern.
- **L3 — Service / capability exchange.** Out of scope. Future spec.

The L1/L2 boundary is enforced by the resolver returning a `Path`. L1 produces it; L2 consumes it. Future remote-peer support (git clone, etc.) extends L1 (returns a local cache path after fetch) without changing L2.

## Decisions

### 1. Identity Rules

**Project IDs.** Every project's identity is its `id:` field in `science.yaml` (already validated by upstream). The `id:` is authoritative; peer entries reference it exactly. Defaults to project directory name when unset.

**Reserved characters in project IDs:** the existing `_ADDRESS_RE` constrains the project segment to `[a-z][a-z0-9-]{1,63}`, which already disallows `:` and `@`. We additionally **tighten the artifact/slug position** in this spec: today `_ADDRESS_RE` uses `(?P<artifact>\S+)` which would accept `@` in the slug, contradicting the version-suffix reservation. Implementation updates `_ADDRESS_RE` to `(?P<artifact>[^@\s]+)` (and applies the same change to `tasks_blockers._TYPED_REF_RE`) so `@` is genuinely reserved across the whole ref. No callers use `@` today, so this is a safe tightening.

**Uniqueness scope.** Within a single project's `peers:` list, IDs must be unique and not equal to the project's own `id` (enforced by `validate_peers()`). Transitive collisions across the peer closure (e.g. peer `A` and peer `B` both claim id `mm30`) are NOT checked in this spec — closure walks need a workspace-registry-style API and are deferred (Trajectory item 2). Cross-user / global uniqueness is a multi-user concern, also deferred.

**Forward-compat for multi-user.** Project IDs in this spec are bare strings (`mm30`, `lit-explore`). Future multi-user scoping is expected to take the shape `@<user>/<project>` or similar, which nests cleanly outside today's grammar (the leading `@` is currently invalid as a project-ID start character).

### 2. Peer Entry Schema

New optional field in `science.yaml`:

```yaml
peers:
  - id: mm30
    path: ~/d/cancer/mm30
  - id: lit-explore
    path: ~/d/r/lit-explore
  - id: cbio-data
    path: ../data-sources/cbioportal
```

**`PeerEntry` shape:**

- `id: str` — required. Must match the peer project's own self-declared `id:`. Same character rules as `ProjectConfig.id`.
- `path: str` — required for now. Local filesystem path to the peer's project root (the directory containing `science.yaml`). Three accepted shapes (Decision 3).
- `model_config = ConfigDict(extra="allow")` — unknown fields are accepted at parse time so the config still loads, but caught at validation time as `RESERVED_FIELD` issues with a clear "field not yet supported" error (see Decision 7). Reserved field names: `git`, `repo`, `url`, `doi`, `ref`, `version`. Other extras (typos) are also caught as `RESERVED_FIELD` by the validator.

**`ProjectConfig` deltas:**

- New: `peers: list[PeerEntry] = Field(default_factory=list)`.
- Removed: `parent: str | None`. (Migrated to peer entries; see Decision 9.)
- Removed: `children: list[ChildEntry]`. (Migrated to peer entries; see Decision 9.)
- `ChildEntry` and `resolve_child_path` are deleted along with the field.
- The `_children_only_on_meta` and `_children_unique_ids` validators are deleted.
- New `_reject_legacy_fields` `model_validator(mode="before")` rejects raw input that contains `parent:` or `children:` keys with a clear error: `"science.yaml uses removed 'parent:' / 'children:' fields. Run `science-tool peers migrate` to migrate to 'peers:'."` This is necessary because `ProjectConfig` has `extra="allow"` (preserves unknown fields for forward-compat); without an explicit pre-validator, removed fields would be silently retained as extras.

**Schema-level validation on `peers`:**

The schema enforces only basic well-formedness (so `ProjectConfig` rejects malformed input):

- `peers` is a list (or absent).
- Each entry has string `id` and string `path`.
- Each `path` must currently parse syntactically (Decision 3); we do NOT require it to resolve at load time (peers can be temporarily missing without making the whole config invalid).

**Semantic checks (handled by `validate_peers()`, not the schema):**

- Each `id` is unique within the list.
- An `id` does not equal the project's own `id`.
- Reserved fields (`git`, `url`, etc.) are not yet supported.
- Path resolves on disk, points at a real project, peer's self-declared id matches the declared id.

**Why semantic checks live in the validator, not the schema:** the validator surfaces structured `PeerIssue` lists to the CLI (see Decision 7 / Decision 8). If schema rejects duplicates or self-peers at parse time, the CLI never gets a chance to render them as structured issues — the user just sees a pydantic stack trace. Putting these checks in `validate_peers()` lets `peers check` always produce its normal output, while consumers who care about hard-rejection (e.g., the resolver) explicitly run validation before trusting the config.

### 3. Path Resolution

The `path` field accepts three shapes, dispatched by leading character:

| Form | Example | Resolution |
|---|---|---|
| Absolute | `/home/keith/d/r/lit-explore` | Used as-is. |
| `~`-anchored | `~/d/r/lit-explore` | `Path.expanduser()` then resolve. |
| Relative | `../mm30`, `../../r/lit-explore` | Resolved against the project root (the directory containing the `science.yaml` declaring this peer). |

**Two-tier API for missing-path handling.** The contract is split deliberately so different consumers can choose their own fatality:

- **`resolve_peer_path(project_root: Path, entry: PeerEntry) -> Path`** — *non-fatal*. Pure path math. Always returns a canonical (or would-be canonical) `Path`, never raises for missing files. Used by tools that want to display would-be paths regardless of disk state (e.g. `peers list` showing the resolved path next to a `path-missing` status).
  1. Apply the dispatch above to produce a candidate path.
  2. Call `Path.resolve(strict=False)` (follows symlinks where present, collapses `..`, normalizes; tolerates non-existence).
  3. Return the canonical resolved path.

- **`PeerResolver.resolve(peer_id: str) -> ResolvedPeer`** — *fatal*. Used by consumers (e.g. cross-project blockers, `load_peer_entity_index`) that need an actually-usable peer. Raises `PeerNotFound` if the ID isn't declared, `PeerUnresolved` if it's declared but the resolved path doesn't exist or isn't a project (no `science.yaml`).

This split lets `peers list` use the non-fatal helper to show every declared peer, while `tasks block --by mm30:task:t015` uses the fatal resolver to refuse the operation when `mm30` is unreachable.

**Authored form is preserved.** What's written in `science.yaml` stays in `science.yaml`. Resolution is a runtime concern, not a serialization concern. This matters for diffs, code review, and human-edited configs.

**Equality semantics.** Two peer paths are "the same project" iff their `Path.resolve()` outputs match. This becomes load-bearing for the eventual composite-graph union (don't double-count the same project reached via two different paths).

**Missing peer behavior at the classification layer.**

- At config-load time: a missing path is **not** an error. The peer entry is preserved.
- For `classify_entity_ref`: a peer ID with a missing on-disk path is still a *known* project ID — refs to it classify as `cross-project-entity`, not `unknown-namespace`. The validator reports the missing path as a `PATH_MISSING` warning. Resolution failures (via the fatal `PeerResolver.resolve()`) surface at use, not classification.

### 4. Resolver Interface

The resolver is the indirection layer that lets future workspace registries and remote-peer support drop in without consumer changes.

**New module: `science_tool/peers.py`**

```python
class PeerNotFound(Exception):
    """Peer ID is not declared in this project's peers list."""

class PeerUnresolved(Exception):
    """Peer is declared but its path does not exist on disk."""


@dataclass(frozen=True)
class ResolvedPeer:
    id: str
    path: Path           # canonical (resolved) path to the peer's project root
    entry: PeerEntry     # original authored entry (path field unmodified)


class PeerResolver(Protocol):
    """Strategy for resolving peer IDs to filesystem locations."""

    def known_ids(self) -> frozenset[str]:
        """All peer IDs visible to this resolver (excludes the host project's own id)."""

    def resolve(self, peer_id: str) -> ResolvedPeer:
        """Return the resolved peer or raise PeerNotFound / PeerUnresolved."""


def make_local_resolver(project_root: Path) -> PeerResolver:
    """Default resolver: reads peers: from project_root/science.yaml."""
```

**Why a `Protocol`, not a concrete class:** the workspace-registry spec (deferred) will provide an alternate resolver that consults a registry file; remote-peer support will provide one that materializes git URLs to a cache dir. Consumers depend only on the protocol, so adding either is purely additive.

**Cycle protection.** Cross-project resolution can be recursive (project A's resolver, while computing readiness, calls into project B's resolver, which may reference back). Each `PeerResolver` instance maintains a `_visiting: set[str]` and uses try/finally to track in-flight peer IDs. Same shape as the existing `ReadinessResolver` cycle protection in the typed-blockers work.

**Caching.** Per-invocation only (resolver instance lifetime). Consumers create a fresh resolver per CLI invocation; cross-invocation caching is deferred along with the broader L2 freshness story.

**Integration with `classify_entity_ref`.** The existing `_load_project_ids(root)` (in `refs.py`) is rewritten to consult the resolver instead of `cfg.children`:

```python
def _load_project_ids(root: Path) -> set[str]:
    cfg = load_project_config(root)
    resolver = make_local_resolver(root)
    ids = set(resolver.known_ids())
    if cfg.id:
        ids.add(cfg.id)
    return ids
```

This keeps `classify_entity_ref`'s public API unchanged. Every existing call site continues to work.

### 5. Reading Peer Entities (Minimal L2)

Defined narrowly: just enough that downstream consumers (cross-project blockers, refs validation, future composite-graph union) can read another project's entity surface.

**New helper in `science_tool/peers.py`:**

```python
def load_peer_entity_index(resolver: PeerResolver, peer_id: str) -> EntityIndex:
    """Load the peer's project entity index using the existing local-load machinery.

    Raises PeerNotFound or PeerUnresolved on resolver failure.
    Raises FileNotFoundError if the peer's science.yaml or entity files are missing.
    """
    peer = resolver.resolve(peer_id)
    return load_local_entity_index(peer.path)  # existing function, just different root
```

**What this does NOT include (deferred to a future L2 spec):**

- Caching across calls or across CLI invocations.
- Staleness detection (the peer's source files may have changed since you last looked).
- Materialized-graph-aware reads (read from `peer/knowledge/graph.trig` instead of source files).
- Partial loads (load only specific entity kinds for performance).
- Concurrent-read safety.

**Symmetry with local loads.** A peer entity index has identical shape to the host project's own entity index — same machinery, same models, just rooted at a different `Path`. This means downstream consumers (e.g. the eventual cross-project `ReadinessResolver`) treat local and peer entities uniformly: pass them an `EntityIndex` and they don't care where it came from.

**Cross-project `ReadinessResolver` (illustrative, will be specified in the blockers spec):** when a typed blocker like `mm30:dataset:scwgs-2026` is encountered, the resolver does:

```python
peer = peer_resolver.resolve("mm30")
peer_entity_index = load_peer_entity_index(peer_resolver, "mm30")
peer_readiness_resolver = ReadinessResolver(peer_entity_index)  # rooted at peer
return peer_entity_index["dataset:scwgs-2026"].readiness(peer_readiness_resolver)
```

The peer's readiness is computed *in the peer's context* (so the peer's own intra-project blockers, derived datasets, etc. are evaluated correctly).

**Trust model.** The host project trusts the peer's on-disk source files. No signing, no integrity checks, no version pinning. Same trust model as the existing local-project read.

### 6. Local Graph vs. Composite Graph

The current federation graph (`graph/federation.py`) writes its output to `<root>/knowledge/graph.trig` after reading meta's own `graph.trig` as the meta-local source — i.e., it conflates local and composite content in one file. This works in a tree-shape because only meta composes; children stay local. In a peer-graph, A and B can both compose, and if either reads the other's output as input, composite content recursively pollutes future builds.

**Rule:** composite assembly never consumes another project's composite graph. Composite reads only locals.

**File-path split (this spec ships the rename):**

| File | Owner / writer | Consumed as input by |
|---|---|---|
| `<root>/knowledge/graph.trig` | `materialize_graph(root)` — local-only | Local consumers; **composite assembly of any peer** |
| `<root>/knowledge/composite.trig` | `assemble_composite_graph(root)` — local + peers' locals | End consumers (queries, audits); **never** read as input by another composite build |

Concretely:

- `materialize_graph(root)` writes only the project's own contribution to `graph.trig`. It no longer also writes a composite for meta-role projects (the conflation goes away).
- `assemble_composite_graph(root)` (renamed from `assemble_federated_graph`) reads `root/knowledge/graph.trig` for the host's contribution, reads `peer.path/knowledge/graph.trig` for each peer's contribution, and writes the union to `root/knowledge/composite.trig`.
- A composite build that encounters a peer with a `composite.trig` but no `graph.trig` reports the peer as `LOCAL_GRAPH_MISSING` (treated as a warning) and skips it, rather than reading the composite. This is the file-path split's enforcement mechanism.

**Migration impact:** any external consumer that today reads `meta/knowledge/graph.trig` expecting composite content will need to switch to `meta/knowledge/composite.trig` after this spec lands. The implementation plan inventories these consumers; in this monorepo the count appears small (graph audits, big-picture, ontology suggestions). Consumers reading per-project `graph.trig` for local-only content (the common case) need no change.

**Cycle / order-independence:** because composite reads only locals, the composite output for project A is a pure function of `{A.local, B.local, C.local, ...}` for A's peers. Peer build order doesn't affect A's output, and bidirectional peering (A↔B) doesn't recurse — A reads B.local, B reads A.local, neither reads the other's composite.

**`compose: true` opt-in deferred.** This spec keeps current "union all peers" behavior. A future spec may add per-peer compose controls (e.g., a peer marked `compose: false` is reachable for refs but not unioned into the composite graph). Trajectory item 6.

### 7. Validation

A new validator module checks peer health independently of any specific consumer. Run automatically as part of `science-tool validate`; can be run standalone via `science-tool peers check`.

**New module: `science_tool/peers_validate.py`**

```python
class PeerIssueKind(StrEnum):
    PATH_MISSING         = "path_missing"          # declared path does not exist
    NOT_A_PROJECT        = "not_a_project"         # path exists but no science.yaml inside
    ID_MISMATCH          = "id_mismatch"           # peer's self-declared id differs from declared
    DUPLICATE_PEER_ID    = "duplicate_peer_id"     # same id appears twice in peers:
    SELF_PEER            = "self_peer"             # a project lists itself as a peer
    RESERVED_FIELD       = "reserved_field"        # used `git:` / `url:` / `doi:` (not yet supported)
    LOCAL_GRAPH_MISSING  = "local_graph_missing"   # peer has composite.trig but no graph.trig (Decision 6)


@dataclass
class PeerIssue:
    kind: PeerIssueKind
    peer_id: str
    detail: str
    severity: Literal["error", "warning"]


def validate_peers(project_root: Path) -> list[PeerIssue]:
    """Return all peer-graph issues for the given project. Reads science.yaml as raw YAML
    so duplicate/self-peer issues surface as structured PeerIssues instead of pydantic errors."""
```

**Severity rules:**

| Kind | Severity | Reasoning |
|---|---|---|
| `DUPLICATE_PEER_ID` | error | Resolver semantics break (which path wins for a duplicate id?). |
| `SELF_PEER` | error | A project peering itself is meaningless and signals a config bug. |
| `ID_MISMATCH` | error | Breaks the global-graph uniqueness story; refs would address the wrong project. |
| `PATH_MISSING` | warning | Peer is declared but unavailable; consumers fall back to "unresolved" at use. |
| `NOT_A_PROJECT` | warning | Path exists but isn't a project; treated like missing for resolution purposes. |
| `RESERVED_FIELD` | error | The user used a future field; fail loudly until it's actually supported. |
| `LOCAL_GRAPH_MISSING` | warning | Peer has only `composite.trig`; composite assembly skips it (Decision 6). |

**Validator reads raw YAML, not `ProjectConfig`.** This is deliberate: `DUPLICATE_PEER_ID` and `SELF_PEER` would otherwise have to live as schema-level errors (because a config with two peers having the same `id` is malformed enough that downstream consumers shouldn't trust it), but schema rejection makes them invisible to the structured-issue pipeline. By validating raw YAML, the validator can surface them as `PeerIssue`s with proper severity + detail strings — which is what the CLI promises. Consumers that want hard rejection (e.g., the resolver) explicitly run `validate_peers()` first and refuse to operate if any errors are present.

**Closure / transitive checks: out of scope this spec.** Transitive ID collisions (e.g., peer `A` and peer `B` both claim id `mm30`) are NOT checked here. Adding a closure walk requires a new resolver API and a new issue kind (`TRANSITIVE_ID_COLLISION`), neither of which this spec ships. Trajectory item — fold into the workspace registry spec where closure walks are natural.

**Not in scope.** The validator does NOT run the peer's own validators recursively. Each project owns its own validation.

### 8. CLI Surface

Three new commands under `science-tool peers`. All read-only; mutations go through editing `science.yaml` directly (peers are usually a small, deliberate list — no need for `peers add` / `peers remove` ergonomics in v1).

**`science-tool peers list`** — show all peers and their status.

```
$ science-tool peers list
PEER         PATH                                 STATUS
mm30         ~/d/cancer/mm30                      ok
lit-explore  ~/d/r/lit-explore                    ok
cbio-data    ../data-sources/cbioportal           ok
old-project  ~/d/archive/old-project              path-missing
```

`--format=json` produces:

```json
{
  "project_id": "evolution",
  "peers": [
    {"id": "mm30", "path": "~/d/cancer/mm30", "resolved": "/home/keith/d/cancer/mm30", "status": "ok"},
    {"id": "old-project", "path": "~/d/archive/old-project", "resolved": null, "status": "path-missing"}
  ]
}
```

**`science-tool peers check`** — run `validate_peers()` and print issues.

```
$ science-tool peers check
ERROR    [evolution] peers[mm30] id mismatch: declared 'mm30', peer's science.yaml says 'multiple-myeloma-30'
WARNING  [evolution] peers[old-project] path-missing: ~/d/archive/old-project does not exist
ok: 2 peers, 1 warning, 1 error
```

Exits 0 on warnings only, non-zero on errors. `--format=json` produces structured output. `--strict` treats warnings as errors.

**`science-tool peers show <peer-id>`** — single-peer detail; renders the resolved peer's `id`, `name`, `role` (project category), `path`, and a count of its entities by kind.

```
$ science-tool peers show mm30
id:       mm30
name:     multiple-myeloma-30
role:     cancer-type
path:     /home/keith/d/cancer/mm30
entities: 12 hypotheses, 8 questions, 3 datasets, 24 tasks
```

**Existing CLI integration:**

- `science-tool validate` — runs `validate_peers()` and surfaces issues at its existing severity levels.
- `science-tool federation status` — DELETED; superseded by `peers list`.
- `science-tool federation validate` — DELETED; superseded by `peers check`.

**No new tasks/blockers commands in this spec.** Cross-project blocker validation lives in the follow-up blockers spec; the only thing that lights up here is that `tasks block --by mm30:task:t015` will start being accepted (because `classify_entity_ref` recognizes `mm30` as a known project ID once it's a peer).

### 9. Migration

The current peer-graph in this monorepo is small enough to migrate by hand, but we ship a migration command for repeatability and so external projects (e.g. `~/d/r/lit-explore` once it joins) can run it locally.

**Current state to migrate (all in this monorepo):**

```yaml
# meta/science.yaml — current
role: meta
children:
  - id: cbioportal
    path: ../cancer/data-sources/cbioportal
    role: data-source
  - id: multiple-myeloma
    path: ../cancer/multiple-myeloma
    role: cancer-type
  - id: evolution
    path: ../cancer/mechanisms/evolution
    role: mechanism
  - id: pre-cancer
    path: ../cancer/conditions/pre-cancer
    role: condition

# cancer/multiple-myeloma/science.yaml — current
role: cancer-type
parent: ../../meta
```

**Target state:**

```yaml
# meta/science.yaml — after migration
role: meta            # role stays — it's project category, not a relationship
peers:
  - id: cbioportal
    path: ../cancer/data-sources/cbioportal
  - id: multiple-myeloma
    path: ../cancer/multiple-myeloma
  - id: evolution
    path: ../cancer/mechanisms/evolution
  - id: pre-cancer
    path: ../cancer/conditions/pre-cancer

# cancer/multiple-myeloma/science.yaml — after migration
role: cancer-type
peers:
  - id: meta
    path: ../../meta    # or any other peers this project wants
```

**What changes vs. current `children:`:**

- `role:` field on each entry is dropped. The peer's own self-declared `role:` is the source of truth (and `peers show` displays it).
- The meta→child semantic (one-way structural relationship) becomes a peer-graph (each project independently declares who it peers with). A child no longer auto-points back to meta — it must list meta in its own `peers:` if it wants to reference meta entities.

**`ProjectRole` stays.** The enum (`META`, `CANCER_TYPE`, `MECHANISM`, etc.) is project category, independent of relationship topology. Keep it.

**Migration command: `science-tool peers migrate`**

Reads the host project's `science.yaml` as **raw YAML** (not through `ProjectConfig`, which after migration rejects the legacy fields), applies the following rewrites in place, and re-saves:

1. `parent: <path>` → reads the peer project's `id` from `<path>/science.yaml`, adds a peer entry `{id, path}`. Removes `parent:`.
2. `children: [...]` → for each child, adds a peer entry `{id: child.id, path: child.path}` (dropping per-child `role:`). Child IDs come from the legacy manifest — no peer read required. Removes `children:`.
3. If `peers:` already exists, merges (errors on conflicting `id` with different `path`).

**Failure modes for parent migration (rule 1):**

- If `<path>` does not exist or has no `science.yaml`: migration **fails with a clear error**. Message: `"cannot migrate parent: <path> — no science.yaml found at resolved path <resolved>. Fix the path, or remove the parent: line manually before migrating."` Rationale: we need the peer's `id` to write the peer entry; guessing it from path basename would silently corrupt the migration.
- If the peer's `science.yaml` itself fails to load (malformed): same outcome — fail with the underlying parse error attached.
- No `--id-override` flag in v1. The "fix the path first" workaround keeps migration deterministic; if a flag turns out to be needed later, it's purely additive.

**Failure mode for child migration (rule 2):** missing child paths do NOT block migration — the legacy manifest already records the child's `id` directly, so we have everything we need to write the peer entry. The migrated project carries the peer; `validate_peers()` will report `PATH_MISSING` afterward.

Idempotent: running on an already-migrated project is a no-op. `--dry-run` previews. `--all` (run from a meta-project root) reads the legacy `children:` from the meta's raw YAML, walks each child path, and runs the migration on each — convenient for the meta-project's one-shot migration. `--all` is the only path that survives the schema change for a one-shot, since after migration the legacy fields are no longer accessible via `ProjectConfig`.

**Code consumers to update:**

- `science_tool/federation.py` → DELETED.
- `science_tool/federation_cli.py` → DELETED.
- `science_tool/federation_status.py` → DELETED.
- `science_tool/graph/federation.py` → KEPT, renamed to `science_tool/graph/composite.py`. Behavior preserved (union peers' `knowledge/graph.trig` files into the host's named-graph dataset), but: (a) reads from the peer graph instead of `cfg.children`, (b) the `role: meta` restriction is dropped (any project can build a composite graph from its peers). Future spec may add policy controls (which peers to compose, ergonomics, etc.); this spec keeps current "union all of them" behavior.
- `science_tool/refs.py:_load_project_ids` → rewritten to consult resolver.
- `science_tool/cli.py:graph_build` (around lines 720-766) — the meta-aware branch (`if _cfg.role == ProjectRole.META: ... assemble_federated_graph(...)`) — rewritten to call `assemble_composite_graph` whenever the project has peers, regardless of role. The `_cfg.parent` references and the `ensure_registered(parent=...)` calls are dropped along with the field.
- Templates (`templates/science.yaml`-style scaffolds): updated to use `peers:` instead of `parent:` / `children:`.

**Documentation to update (must land with the code):**

- `docs/federation.md` — currently describes the tree-shaped federation. Rewrite (or supersede with a `docs/peers.md`) so the canonical addressing convention reflects the peer-graph model. Cross-link to this spec.
- `docs/superpowers/specs/2026-05-05-task-ids-and-cross-project-references-design.md` — Decision 5 says "the parser can use an explicit project-ID set from federation config to decide whether the first segment is a namespace" (line ~135) and the unresolved-namespace error message tells users to add to `children:` (line ~255). Both need updating to refer to `peers:` instead.
- `docs/superpowers/plans/2026-05-05-task-ids-and-cross-project-references.md` — same treatment if it carries the same wording in task descriptions.
- `meta/AGENTS.md` and any project-level `AGENTS.md` / `CLAUDE.md` that documents the federation/parent/children model.
- Any `commands/` or `skills/` markdown that documents `science-tool federation ...` commands (deleted) or recommends adding entries to `children:`.

The implementation plan must include a grep pass (`grep -rln "children:\|parent:\|federation" docs/ commands/ skills/`) to inventory consumers and a TODO per file with the required edit.

**Validation impact.** `validate_federation` is deleted along with `federation.py`. Its checks (child-path-missing, id-mismatch, missing-parent-back-ref) are subsumed by `validate_peers`, with the asymmetric/back-ref check dropped (peers are not symmetric by design).

**Manual review step.** After migration, the user reviews:

- Did any project lose a relationship that mattered? (e.g., meta listed `multiple-myeloma` as a child, but `multiple-myeloma` didn't have `parent:` set — now `multiple-myeloma` won't peer back to meta unless the user adds it.)
- For each project, decide which peers it actually wants. The migration is conservative (preserves existing structural edges); pruning happens in review.

### 10. Forward Compatibility

Design affordances that let future specs ship cleanly — not behavior shipping in this spec.

**Versioned references** (deferred):

- Ref grammar reserves `@<version>` suffix: `mm30:dataset:scwgs-2026@v3`, `mm30:dataset:scwgs-2026@2026-04-01`.
- After this spec lands the regex tightening (Decision 1), `_ADDRESS_RE` disallows `@` in both the project-ID and slug positions. The future versioning spec extends parsing with an optional `(?:@\S+)?` suffix capture at the end of the artifact segment — purely additive over today's grammar.
- Resolution semantics for versions are explicitly out of scope: filesystem doesn't natively store entity history. Likely candidates: git revisions, content-addressed snapshots, explicit version field in entity frontmatter. Decision deferred.

**Workspace registry** (deferred):

- Future `~/.config/science/workspace.yaml` lists all known projects with canonical paths.
- Drops in as an alternative `PeerResolver` implementation; consumers are protocol-typed so this is purely additive.
- Peer entries gain ability to omit `path:` (registry-only lookup): `peers: [{id: mm30}]`. Spec-time check: `path` becomes optional once the registry resolver is the default.

**Remote peers via cloneable repos** (deferred):

- Schema gains `git: <url>`, `repo: <url>`, optional `ref: <branch|tag|sha>` fields on `PeerEntry`. Validator's `RESERVED_FIELD` rule is updated to accept them.
- Resolver gets a `GitCloneResolver` strategy that materializes to a cache dir (likely `~/.cache/science/peers/<project-id>/`), then returns the cache path.
- L2 read access works unchanged (still reading on-disk source files, just at a cache path).

**Service-style remote peers (HTTP / DOI / registries)** (deferred, separate spec):

- Out of scope for `peers:`. Will be modeled as a separate `services:` (or similar) section in `science.yaml` — different protocol, different staleness, different auth.
- Layer 3 concern. Probably needs its own design pass concurrent with the cross-project tooling work (e.g. lit-explore as a service).

**Composite / global knowledge graph** (this spec preserves current behavior + groundwork; future spec evolves):

- `science_tool/graph/composite.py` (renamed from `graph/federation.py`) becomes the place where multi-project graph assembly lives.
- **In this spec:** behavior preserved from the current federation graph — union all peers' `knowledge/graph.trig` files into the host's named-graph dataset. Just sourced from `peers:` instead of `children:`, with the `role: meta` restriction dropped.
- Peer graph supplies the project-ID → path mapping. Each project's `knowledge/graph.trig` loads as a named graph with URI `<scheme>://<project-id>`.
- `Path.resolve()`-based equality ensures the same project reached via different paths doesn't double-materialize.
- **Future spec evolves policy:** which peers does a project union? All (current default)? Only those explicitly opted-in via a `compose: true` flag? A user-supplied subset? Probably "all peers" by default, with overrides — but that's a design decision for the composite-graph spec, not this one.
- Multi-user identity scoping (`@<user>/<project>`) integrates here naturally: the URI scheme grows from `<scheme>://<project-id>` to `<scheme>://<user>/<project-id>` with no change to the peers data shape.

**Multi-user** (deferred):

- Project IDs nest into `@<user>/<project>` — leading `@` is currently invalid as a project-ID start, so this is purely additive.
- Cross-user peer paths likely route through the cloneable-repos affordance plus auth/identity that's a separate concern entirely.

## Trajectory

Tracked as task group `project-peers` so we revisit deliberately. Each is a separate spec when its time comes.

| # | Item | Why deferred |
|---|---|---|
| 1 | **Cross-project blockers spec** | Original motivation; lands first after this. Consumes the resolver protocol and `load_peer_entity_index`. Adds a cross-project `ReadinessResolver` and the `tasks block --by mm30:task:t015` use case. |
| 2 | **Workspace registry** | Single source of truth for project-ID → path. Drops in as an alternate `PeerResolver`. Triggered when a user has many projects (or pain from path edits propagating). |
| 3 | **Remote peers (cloneable repos)** | `git:` / `ref:` fields on `PeerEntry`, `GitCloneResolver` strategy, cache-dir materialization. Triggered when first cross-machine collaboration use case appears. |
| 4 | **Versioned entity references** | `<project-id>:<kind>:<slug>@<version>` ref grammar + resolution semantics. Triggered when reproducibility / pinning becomes load-bearing. |
| 5 | **L2 caching & freshness** | Cross-invocation caching, staleness detection, materialized-graph delegation, partial loads. Triggered when peer reads become hot enough to matter. |
| 6 | **Composite / global knowledge graph** | Multi-project graph union built on the peer graph. Replaces the meta-only federated graph that this spec deletes. Likely small spec — most of the substrate is here. |
| 7 | **Service / capability exchange (Layer 3)** | `services:` section, tool/skill discovery, query APIs (the lit-explore "ask the literature" use case). Different protocol entirely. |
| 8 | **Multi-user identity scoping** | `@<user>/<project>` IDs, cross-user auth, registry collisions. Probably waits on (3) and a real cross-user use case. |
| 9 | **Auto-unblock / change notification** | Inverse of cross-project blockers: when peer state changes, propagate to consumers. Likely needs (5) for staleness signal first. |
| 10 | **Symmetry tooling** | Optional `peers check --symmetric` flag that warns when A peers B but B doesn't peer A. Useful for tightly-coupled clusters; not enforced. |

## Open Questions

1. **`peers migrate` and external projects.** The migration command runs in a single project root. For the meta+children migration, it works one project at a time. A `--all` mode that walks the existing `children:` and migrates each is a nice-to-have for the one-shot meta migration. Decision: include `--all` (simple to implement; one-shot use).
2. **Empty migration.** Running `peers migrate` on a project with no `parent:` or `children:`: print "No legacy fields found; nothing to migrate." and exit 0.
3. **Empty peer list rendering.** `peers list` for a project with no `peers:`: empty table + "no peers declared." JSON: `{"project_id": "...", "peers": []}`. No error.
4. **Templates / scaffolds.** The project-init templates in `science_tool/project_artifacts/` need updating to use `peers:` instead of `parent:` / `children:`. Mechanical but easy to miss; flag explicitly in the implementation plan.

## Risks

1. **Hidden consumers of `cfg.children` / `cfg.parent`.** The grep pass found ~10 sites, but indirect consumers (e.g. graph audits, big-picture aggregators in research-agent code, prereg validators) may exist. Mitigation: implementation plan starts with a comprehensive inventory pass; tests cover deletion of the old fields by ensuring `ProjectConfig.model_validate({"children": [...]})` fails cleanly.
2. **Backward-incompatible config change.** Any project's `science.yaml` with `parent:` or `children:` will fail to load after this lands. Mitigation: migration command, clear error message ("This project still uses `parent:` / `children:`; run `science-tool peers migrate`."), and the migration is mechanical.
3. **Federation graph (`graph/federation.py`) has its own behavior assumptions.** It currently restricts to `role: meta` and unions only `children`. The rename to `composite.py` + behavior update (any project, peers instead of children) is non-trivial — tests need to cover the new shape, including non-meta projects building composite graphs.
4. **Symmetry assumptions in existing code.** Some current code may assume "if I'm meta, I know about all my children" or "if I'm a child, my parent knows about me." After migration, neither holds. Mitigation: same inventory pass + targeted tests.
5. **`Path.resolve()` on missing paths.** Behavior differs across Python versions and OS — strict=False is the right call, but symlink resolution semantics on missing paths can be subtle. Mitigation: explicit tests covering missing paths, broken symlinks, paths with `..` traversal.

## Testing Strategy

**`peers.py` (resolver + read access):**

- `make_local_resolver` returns expected IDs from a project with peers.
- `resolve()` raises `PeerNotFound` for unknown IDs, `PeerUnresolved` for missing paths.
- Cycle detection: A peers B, B peers A, querying through both does not infinite-loop.
- `load_peer_entity_index` returns the same shape as `load_local_entity_index` for the peer's root.
- Path forms (absolute, `~`-anchored, relative) all resolve correctly. Symlinked paths resolve to canonical form.

**`peers_validate.py`:**

- One test per `PeerIssueKind`: malformed config produces the expected issue.
- ID-mismatch detection: peer's self-declared `id` differs from declared.
- Severity tagging matches the table in Decision 7.

**`project_config.py`:**

- `ProjectConfig.model_validate({"children": [...]})` fails with a clear error from `_reject_legacy_fields` (regression test against accidental re-introduction).
- `ProjectConfig.model_validate({"parent": ...})` fails with the same error.
- New `peers:` field accepts well-formed entries at the schema level.
- `peers:` entries with reserved/unknown fields (`git`, `url`, etc.) parse successfully but surface as `RESERVED_FIELD` issues from `validate_peers()`.
- Duplicate peer IDs and self-peers parse successfully at the schema level (validator catches them, not the schema).

**`addressing.py` integration (no change to `addressing.py` itself):**

- `classify_entity_ref` with project IDs sourced from a resolver-backed `_load_project_ids` correctly classifies cross-project refs to peers.
- A peer with a missing path is still in the known-IDs set (refs classify as `cross-project-entity`, not `unknown-namespace`).

**`peers migrate`:**

- Migrates `parent:` to a peer entry; reads peer's `id` from peer's `science.yaml`.
- Migrates `parent:` with missing/unreadable parent path: fails with the documented error message; project is not modified.
- Migrates `children:` to peer entries; drops per-child `role:`.
- `children:` with missing child path: succeeds (uses `id` from manifest); resulting config carries `PATH_MISSING` warning.
- Idempotent: running twice on a migrated project is a no-op.
- `--dry-run` produces preview without writing.
- Conflict detection: existing `peers:` entry with a path that conflicts with the parent/child being migrated is an error.

**Composite graph (`graph/composite.py`):**

- `materialize_graph(root)` writes only local content to `knowledge/graph.trig` (no longer composes for meta-role projects).
- `assemble_composite_graph(root)` reads the host's `graph.trig` plus each peer's `graph.trig` and writes the union to `knowledge/composite.trig`.
- Composite assembly never reads a peer's `composite.trig`, even if `graph.trig` is missing — surfaces `LOCAL_GRAPH_MISSING` instead.
- Bidirectional peering (A↔B): both projects' composite outputs are deterministic and order-independent.

**Regex tightening (`addressing._ADDRESS_RE`, `tasks_blockers._TYPED_REF_RE`):**

- Refs containing `@` in the artifact/slug position fail classification (`non-entity` or equivalent), and existing fixtures + snapshots remain green.

**CLI:**

- `peers list`: tabular and JSON output match expected shape; missing-path peers are displayed with status.
- `peers check`: exit code matches issue severity; `--strict` flips warnings to errors.
- `peers show <id>` for a missing peer raises a clear error.

**Integration:**

- After migration, `tasks block --by mm30:task:t015` succeeds (because `mm30` is now a peer ID).
- `science-tool validate` runs `validate_peers()` and surfaces issues.
- The deleted `federation` CLI subcommand returns "command not found" or equivalent.

**Snapshot tests.** The kitchen-sink fixture (`science/tests/fixtures/spec_y_kitchen_sink/`) gets a `peers:` section in its `science.yaml`. Existing snapshot updates expected.

## Acceptance Criteria

- `ProjectConfig` schema rejects `parent:` and `children:` fields (via the `_reject_legacy_fields` pre-validator) with a clear "use `peers:`; run `science-tool peers migrate`" error.
- `peers:` field accepts well-formed entries at the schema level; `validate_peers()` catches semantic issues (duplicate IDs, self-peer, ID mismatch, path missing, reserved fields, local-graph missing) with the issue kinds listed in Decision 7.
- `science-tool peers list / check / show` commands work as specified.
- `science-tool peers migrate` migrates the existing meta+children layout in this monorepo cleanly; running it twice is a no-op; missing parent paths fail with a clear error.
- All existing consumers of `cfg.children` / `cfg.parent` are updated; deleted modules (`federation.py`, `federation_cli.py`, `federation_status.py`) leave no dangling imports.
- `classify_entity_ref` resolves peer IDs through the resolver; `tasks block --by <peer-id>:task:t...` is accepted at the parser level.
- Composite graph (renamed from federation graph) builds from peers without restriction to meta-role projects, writes to `knowledge/composite.trig`, and reads only peers' local `knowledge/graph.trig` (Decision 6).
- `_ADDRESS_RE` and `_TYPED_REF_RE` are tightened to disallow `@` in the artifact/slug position (Decision 1); existing tests pass with the tighter regex.
- Documentation updates land with the code: `docs/federation.md` rewritten/replaced, the upstream task-IDs spec's references to `children:` updated to `peers:`, and any `commands/` / `skills/` mentions of `science-tool federation ...` updated.
- All new modules have direct unit test coverage; integration tests cover the migration end-to-end.
