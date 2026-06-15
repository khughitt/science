"""Entity consolidation — auto-derive `superseded` from supersedes chains (P1).

Read-only by default (report); `--apply` stamps `status: superseded` on the
superseded members of *linear* chains only. Non-linear (branched/cyclic) chains
are reported and skipped — their survivor is ambiguous and needs human review.

The canonical machine-readable supersession edge is a `relations:` entry with
`predicate: "sci:supersedes"` (the graph source of truth per the conclusion
templates) — NOT a top-level `supersedes:` field, and NOT `sci:amends` (which
revises, not replaces). This module reads those relation entries directly from
entity markdown under `entities/`. It is a CONSUMER surface, not the KG ingestion
path; it never mutates KG materialization behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entities import _STATUS_VALUES, edit_entity

_SUPERSEDED = "superseded"
_SUPERSEDES_PREDICATE = "sci:supersedes"


def iter_entity_frontmatter(project_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """All entity markdown frontmatter under entities/, as (path, frontmatter)."""
    entities_root = project_root / "entities"
    out: list[tuple[Path, dict[str, Any]]] = []
    if not entities_root.is_dir():
        return out
    for path in sorted(entities_root.rglob("*.md")):
        fm = read_frontmatter(path)
        if fm and "id" in fm:
            out.append((path, fm))
    return out


def _supersedes_targets(fm: dict[str, Any]) -> list[str]:
    """Targets this entity supersedes, from canonical `relations:` entries with
    `predicate: "sci:supersedes"`. Ignores `sci:amends` and any other predicate."""
    relations = fm.get("relations")
    if not isinstance(relations, list):
        return []
    targets: list[str] = []
    for rel in relations:
        if not isinstance(rel, dict):
            continue
        if rel.get("predicate") != _SUPERSEDES_PREDICATE:
            continue
        target = rel.get("target")
        if isinstance(target, str) and target:
            targets.append(target)
    return targets


def _kind_of(entity_id: str, fm: dict[str, Any]) -> str:
    """The entity's kind: `type`, else `kind`, else the id prefix before `:`."""
    return str(fm.get("type") or fm.get("kind") or entity_id.split(":", 1)[0])


def _supports_superseded(kind: str) -> bool:
    """Whether `kind` is a BUILT-IN markdown kind that declares the `superseded`
    status. P1 auto-apply is restricted to built-in policy-backed kinds: a
    project-local kind would pass a naive vocab check but then fail inside
    `edit_entity`, whose `find_entity` lookup iterates `_BUILTIN_MARKDOWN_POLICIES`
    only and whose `_validate_status` indexes `_STATUS_VALUES[kind]` (KeyError for
    a local kind). Checking `_STATUS_VALUES` membership directly covers both the
    status-less eligible kinds (`workflow-run`/`story`/`validation-report`, absent
    from the map) and all local kinds — every one is skipped, never crashed.
    Honoring project-local policies in `edit_entity` is deferred past P1."""
    return _SUPERSEDED in _STATUS_VALUES.get(kind, frozenset())


def _connected_components(nodes: set[str], edges: list[tuple[str, str]]) -> list[set[str]]:
    adj: dict[str, set[str]] = {n: set() for n in nodes}
    for src, dst in edges:
        adj[src].add(dst)
        adj[dst].add(src)
    seen: set[str] = set()
    components: list[set[str]] = []
    for start in sorted(nodes):
        if start in seen:
            continue
        stack = [start]
        comp: set[str] = set()
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            comp.add(node)
            stack.extend(adj[node] - seen)
        components.append(comp)
    return components


def _classify(comp: set[str], edges: list[tuple[str, str]]) -> tuple[bool, str | None, set[str]]:
    """Return (linear, survivor, members). For a linear simple path S supersedes T,
    survivor = the node nothing supersedes (in-degree 0); members = every node with
    in-degree >= 1. Non-linear when any node has in/out-degree > 1 or there is not
    exactly one survivor (cycle / branch)."""
    comp_edges = [(s, d) for s, d in edges if s in comp and d in comp]
    out_deg: dict[str, int] = {n: 0 for n in comp}
    in_deg: dict[str, int] = {n: 0 for n in comp}
    for src, dst in comp_edges:
        out_deg[src] += 1
        in_deg[dst] += 1
    survivors = [n for n in comp if in_deg[n] == 0]
    sinks = [n for n in comp if out_deg[n] == 0]
    linear = (
        all(out_deg[n] <= 1 for n in comp)
        and all(in_deg[n] <= 1 for n in comp)
        and len(survivors) == 1
        and len(sinks) == 1
    )
    survivor = survivors[0] if len(survivors) == 1 else None
    members = {n for n in comp if in_deg[n] >= 1}
    return linear, survivor, members


@dataclass(frozen=True)
class SupersededChain:
    """A linear supersedes chain: `survivor` is the in-degree-0 node; `superseded`
    is its sorted tail (every node with in-degree >= 1)."""

    survivor: str
    superseded: tuple[str, ...]


@dataclass(frozen=True)
class NonLinearComponent:
    """A branched/cyclic component — reported, never acted on."""

    nodes: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SupersedesGraph:
    """Topology of the supersedes graph plus per-id status/kind, derived from one
    pass over the entity frontmatter. Carries NO apply-time filtering — that lives
    in `mark_superseded`."""

    linear: tuple[SupersededChain, ...]
    non_linear: tuple[NonLinearComponent, ...]
    status_by_id: dict[str, str | None]
    kind_by_id: dict[str, str]


def build_supersedes_graph(entries: list[tuple[Path, dict[str, Any]]]) -> SupersedesGraph:
    """Classify supersedes chains from already-iterated `entries`. Edges come from
    canonical `relations:` entries with `predicate: "sci:supersedes"`; edges to
    unknown ids are ignored. Components are split into linear chains (survivor +
    sorted superseded tail) and non-linear components (branched/cyclic)."""
    status_by_id: dict[str, str | None] = {}
    kind_by_id: dict[str, str] = {}
    known: set[str] = set()
    for _path, fm in entries:
        eid = str(fm["id"])
        known.add(eid)
        status_by_id[eid] = fm.get("status")
        kind_by_id[eid] = _kind_of(eid, fm)

    edges: list[tuple[str, str]] = []
    for _path, fm in entries:
        src = str(fm["id"])
        for dst in _supersedes_targets(fm):
            if dst in known:  # ignore edges to unknown ids
                edges.append((src, dst))

    nodes = {n for edge in edges for n in edge}
    linear: list[SupersededChain] = []
    non_linear: list[NonLinearComponent] = []
    for comp in _connected_components(nodes, edges):
        if len(comp) < 2:
            continue
        is_linear, survivor, members = _classify(comp, edges)
        if not is_linear or survivor is None:
            non_linear.append(
                NonLinearComponent(nodes=tuple(sorted(comp)), reason="branched or cyclic supersedes chain")
            )
            continue
        linear.append(SupersededChain(survivor=survivor, superseded=tuple(sorted(members))))
    return SupersedesGraph(
        linear=tuple(linear),
        non_linear=tuple(non_linear),
        status_by_id=status_by_id,
        kind_by_id=kind_by_id,
    )


def mark_superseded(project_root: Path, *, apply: bool) -> dict[str, Any]:
    """Scan supersedes chains under ``project_root`` and report (or apply) the
    `superseded` status auto-derivation.

    Returns a dict with keys:
    - ``chains``: linear chains as ``{"survivor", "members" (sorted), "linear": True}``.
    - ``non_linear``: branched/cyclic components as ``{"nodes" (sorted), "reason"}``.
    - ``to_mark``: member ids a linear chain would stamp ``superseded`` (excludes
      already-superseded members and members whose kind can't carry the status).
    - ``applied``: member ids actually stamped (empty unless ``apply=True``).
    - ``skipped_kinds``: ``{"id", "kind"}`` for members whose kind does not declare
      the ``superseded`` status (see ``_supports_superseded``).
    """
    project_root = project_root.resolve()
    graph = build_supersedes_graph(iter_entity_frontmatter(project_root))

    chains: list[dict[str, Any]] = []
    to_mark: list[str] = []
    skipped_kinds: list[dict[str, str]] = []
    for chain in graph.linear:
        chains.append({"survivor": chain.survivor, "members": list(chain.superseded), "linear": True})
        for member in chain.superseded:
            if graph.status_by_id.get(member) == _SUPERSEDED:
                continue  # already superseded
            kind = graph.kind_by_id.get(member, member.split(":", 1)[0])
            if not _supports_superseded(kind):
                skipped_kinds.append({"id": member, "kind": kind})
                continue  # not a built-in 'superseded'-capable kind; can't stamp it
            to_mark.append(member)

    non_linear = [{"nodes": list(comp.nodes), "reason": comp.reason} for comp in graph.non_linear]

    report: dict[str, Any] = {
        "chains": chains,
        "non_linear": non_linear,
        "to_mark": to_mark,
        "applied": [],
        "skipped_kinds": skipped_kinds,
    }
    if apply:
        for member in to_mark:
            edit_entity(project_root, member, status=_SUPERSEDED)
            report["applied"].append(member)
    return report
