"""Entity consolidation — derive `superseded` (and its lineage) from supersedes chains.

Read-only by default (report); `--apply` stamps `status: superseded` **and the derived inverse
`superseded_by`** on the superseded members of *linear* chains only. Non-linear (branched/cyclic)
components are reported and skipped — their survivor is ambiguous and needs human review.

The canonical machine-readable supersession edge is a `relations:` entry with
`predicate: "sci:supersedes"`, authored on the **successor**, pointing newer → older. It is **not**
top-level `supersedes:` (silently dropped), and not `sci:amends` (which revises, not replaces).

**The inverse is a PROJECTION, not a second authored spelling.** JSON Schema sees one record in
isolation, so it can never read an edge authored in *another* file — which is why the closed record
carries `superseded_by`, written here from the admitted canonical edge. Author the edge; the inverse
is written for you. `_prepare_supersession` therefore takes the **graph**, not a lineage string:
there is no argument a caller could corrupt, so a groundless inverse is *unexpressible*, not merely
unreached.

**And a derived field is reconciled every pass, or it is not derived.** A record whose status is
already `superseded` but whose inverse is missing or stale is *repaired*, not skipped.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.schema import RelationKind
from science_model.relations import relation_allows_kinds

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entities import _commit_write, _prepare_write, _PreparedWrite, _STATUS_VALUES
from science_tool.entity_scan import iter_entity_markdown
from science_tool.graph.reference_resolution import ReferenceResolver

_SUPERSEDED = "superseded"
_SUPERSEDES_PREDICATE = "sci:supersedes"


def _supersedes_kind() -> RelationKind:
    """The relation kind, resolved from the profile — the SAME object `materialize` validates against."""
    return next(r for r in CORE_PROFILE.relation_kinds if r.name == "supersedes")


class SupersessionError(RuntimeError):
    """An authored supersession the corpus cannot honour.

    Either an edge that is not admissible as an edge (it runs from an entity to itself, the relation
    model forbids the kind pair, or the target resolves nowhere), or an authored inverse with no edge
    behind it. Apply is
    ALL-OR-NONE over these: the derivation is corpus-wide, and if part of the corpus is not a graph,
    the derivation is not trustworthy anywhere.
    """

    def __init__(self, blocking: list[dict[str, str]]) -> None:
        super().__init__(
            "refusing to apply: "
            + "; ".join(f"{b['superseder']} -> {b['id']} ({b['reason']})" for b in blocking)
        )
        self.blocking = blocking


def iter_entity_frontmatter(project_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """All entity markdown frontmatter under entities/, as (path, frontmatter)."""
    entities_root = project_root / "entities"
    out: list[tuple[Path, dict[str, Any]]] = []
    for path in iter_entity_markdown(entities_root):
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


def _kind_or_prefix(entity_id: str, declared: object) -> str:
    """The declared kind, else the id prefix. Ids are `<kind>:<slug>`."""
    return str(declared or entity_id.split(":", 1)[0])


def _kind_of(entity_id: str, fm: dict[str, Any]) -> str:
    return _kind_or_prefix(entity_id, fm.get("kind"))


def _supports_superseded(kind: str) -> bool:
    """Whether `kind` is a BUILT-IN markdown kind that declares the `superseded` status.

    Auto-apply is restricted to built-in policy-backed kinds: a project-local kind would pass a naive
    vocab check but then fail inside the write boundary, whose `find_entity` lookup iterates the
    built-in policies only and whose `_validate_status` indexes `_STATUS_VALUES[kind]` (KeyError for
    a local kind). Checking `_STATUS_VALUES` membership directly covers both the status-less eligible
    kinds (`workflow-run`/`story`/`validation-report`, absent from the map) and all local kinds —
    every one is skipped, never crashed.
    """
    return _SUPERSEDED in _STATUS_VALUES.get(kind, frozenset())


# ---------------------------------------------------------------------------------------------
# resolution — resolvable, ours, and legal are THREE questions
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class IdResolution:
    """How an authored reference becomes a canonical id, and WHO OWNS that id.

    It carries the CONFIGURED RESOLVER, not a token dump: per-entity `aliases`/`same_as` live in
    neither the live scan nor the manual-alias map — they are registered inside `build_alias_map`,
    which the resolver owns. Ask the resolver; do not reconstruct what it knows.

    Resolvability and ownership are ORTHOGONAL. `mutable` is the LIVE MARKDOWN scan — not
    `sources.entities`, which also carries commons-overlay and non-markdown entities that
    `iter_entity_frontmatter` never saw and the graph's live maps have no key for.

    And LEGALITY is orthogonal to BOTH. `kind_of` spans EVERY population the resolver can reach —
    live, archived, and everything else — because that is the population `materialize` validates a
    relation endpoint against: it reads the resolved entity's kind, live or not, and never asks who
    can write the file. A kind map that stopped at the live scan could not ask the legality question
    about the very targets we decline to stamp, so those edges would skip the check entirely.
    """

    resolver: ReferenceResolver  # the SAME object, with the SAME args, that `materialize` builds
    mutable: frozenset[str]  # canonical ids of LIVE MARKDOWN entities -- the only stampable set
    archived: frozenset[str]  # canonical ids of ACTIVE archived rows
    kind_by_id: Mapping[str, str]  # kind of EVERY id ANY population backs

    def canonical(self, raw: str) -> str | None:
        res = self.resolver.resolve(raw)
        return res.canonical_id if res.status == "resolved" and res.canonical_id else None

    def kind_of(self, canonical_id: str) -> str | None:
        """The kind of a RESOLVED id, or None if NOTHING backs it.

        `None` is a real answer, not a lookup miss: `build_alias_map` registers manual aliases
        UNCONDITIONALLY, so an alias resolves to its canonical id whether or not any record backs
        that id. Such a target is dangling with extra steps — we cannot ask whether the edge is
        legal, and an unanswerable guard must not report "benign".

        `""` IS A DIFFERENT ANSWER FROM `None`: a record backs the id but declares no kind (an
        archive row predating the field). Materialize resolves that to `""` too, and `""` satisfies
        no `allowed_kind_pairs` entry — so the edge is MISMATCHED, not dangling. Distinguishing the
        two is what keeps this authority's refusals identical to materialize's.
        """
        return self.kind_by_id.get(canonical_id)


def _id_resolution(project_root: Path, entries: list[tuple[Path, dict[str, Any]]]) -> IdResolution:
    """Built with the SAME CALL the materializer makes — not a reimplementation of it.

    Same three arguments, same answers, which is the only way "an edge that materializes must not be
    reported unresolved" is a guarantee rather than a coincidence. (`sources.manual_aliases` already
    has the archive's `resolvable_ids()` folded in, so archived aliases resolve too.)
    """
    from science_tool.archive import load_archive_index
    from science_tool.graph.identity_table import build_identity_table
    from science_tool.graph.sources import load_project_sources

    sources = load_project_sources(project_root)
    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        identity_table=build_identity_table(sources),
    )

    def canon_or_self(raw: str) -> str:
        res = resolver.resolve(raw)
        return res.canonical_id if res.status == "resolved" and res.canonical_id else raw

    # THE KIND MAP SPANS EVERY POPULATION THE RESOLVER CAN REACH, because the LEGALITY question is
    # about the resolved ENTITY, not about whether we can write to it. Three sources, live last so
    # it wins -- it is the only one that reflects what is on disk right now.
    #
    # The ARCHIVE's `ArchiveRow.kind` is NULLABLE, and `or ""` MIRRORS MATERIALIZE EXACTLY. Do NOT
    # fall back to the id prefix: `supersedes` declares `allowed_kind_pairs`, an authoritative
    # allow-list, so `""` matches no pair and materialize RAISES on the edge. A prefix fallback here
    # would ADMIT and STAMP an edge the graph then refuses to build -- a write that succeeds and
    # leaves the corpus unmaterializable, which is worse than either authority refusing alone.
    archive = load_archive_index(project_root)
    kind_by_id: dict[str, str] = {}
    for entity in sources.entities:
        kind_by_id[entity.canonical_id] = entity.kind
    for cid, row in archive.active_by_id.items():
        kind_by_id[cid] = row.kind or ""
    for _path, fm in entries:
        eid = canon_or_self(str(fm["id"]))
        kind_by_id[eid] = _kind_or_prefix(eid, fm.get("kind"))

    # MUTABLE = the MARKDOWN SCAN, canonicalized. NOT `sources.entities`: that list also carries
    # commons-overlay and non-markdown entities the live scan never yielded, so the graph's
    # `kind_by_id`/`path_by_id` have no key for them -- classify one as stampable and the next line
    # KeyErrors.
    return IdResolution(
        resolver=resolver,
        mutable=frozenset(canon_or_self(str(fm["id"])) for _path, fm in entries),
        archived=frozenset(archive.active_by_id),
        kind_by_id=kind_by_id,
    )


# ---------------------------------------------------------------------------------------------
# topology
# ---------------------------------------------------------------------------------------------


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
    """The topology, the inversion, and every edge-admission outcome — from one pass.

    The builder is the SOLE authority on which edges are real. Nothing downstream recomputes an
    admission decision; `edges` is exposed precisely so the unbacked-inverse rule and the `validate`
    check can ask "is there an edge behind this?" without ever re-deciding what an edge is.

    `kind_by_id` and `path_by_id` are LIVE-ONLY, deliberately: they are the writer's map of what it
    can stamp. The legality question needs kinds for targets we will never stamp (archived rows,
    commons entities), and that is a different map on `IdResolution`, spanning a different
    population. Merging them would put a node in the topology that has no file here to write.
    """

    linear: tuple[SupersededChain, ...]
    non_linear: tuple[NonLinearComponent, ...]
    status_by_id: Mapping[str, str | None]
    kind_by_id: Mapping[str, str]  # LIVE entities -- the population `mark_superseded` stamps
    path_by_id: Mapping[str, Path]  # LIVE entities -- `Result` reports a FILE, not an id
    edges: frozenset[tuple[str, str]]  # every ADMITTED (superseder, superseded) edge, canonical
    superseder_by_id: Mapping[str, str]  # superseded id -> its IMMEDIATE superseder (linear only)
    superseded_by_id: Mapping[str, str]  # superseded id -> the AUTHORED inverse, CANONICALIZED
    self_referential: tuple[dict[str, str], ...]  # edge from an entity to ITSELF -- not an edge
    mismatched: tuple[dict[str, str], ...]  # edge the RELATION MODEL forbids
    archived_targets: tuple[dict[str, str], ...]  # edge resolves INTO the archive -- historical
    unmanaged_targets: tuple[dict[str, str], ...]  # edge resolves, but to nothing WE can stamp
    unresolved_targets: tuple[dict[str, str], ...]  # edge resolves NOWHERE -- dangling
    unbacked_inverses: tuple[dict[str, str], ...]  # authored inverse with NO admitted edge behind it


def build_supersedes_graph(
    entries: list[tuple[Path, dict[str, Any]]], resolution: IdResolution
) -> SupersedesGraph:
    """Classify supersedes chains from already-iterated `entries`.

    RESOLVE -> is it BACKED? -> is it an EDGE AT ALL? -> is the pair LEGAL? -> only THEN, who OWNS it?

    A pure function of its inputs: it resolves through `resolution` and never touches the
    filesystem, which is what lets a test construct the commons/non-markdown populations as the data
    they actually are.
    """
    status_by_id: dict[str, str | None] = {}
    kind_by_id: dict[str, str] = {}
    path_by_id: dict[str, Path] = {}
    for path, fm in entries:
        eid = resolution.canonical(str(fm["id"])) or str(fm["id"])
        status_by_id[eid] = fm.get("status")
        kind_by_id[eid] = _kind_of(eid, fm)
        path_by_id[eid] = path

    # A SET, NOT A LIST -- because an RDF graph is a set of triples, and `materialize` collapses the
    # identical triple authored twice into the one edge it is. Accumulating admissions in a list and
    # counting degrees off it turns a duplicate spelling (the same target twice, or the canonical id
    # once and an alias of it once) into a second in-edge AND a second out-edge, so an ordinary
    # one-edge chain classifies as "branched or cyclic" and is silently skipped: the corpus is valid,
    # the tool refuses to act on it, and the defect it reports does not exist. Deduplication happens
    # HERE, on the CANONICAL pair, because a duplicate is invisible in the authored text.
    edges: set[tuple[str, str]] = set()
    self_referential: list[dict[str, str]] = []
    mismatched: list[dict[str, str]] = []
    archived_targets: list[dict[str, str]] = []
    unmanaged_targets: list[dict[str, str]] = []
    unresolved_targets: list[dict[str, str]] = []
    relation = _supersedes_kind()

    for _path, fm in entries:
        src = resolution.canonical(str(fm["id"])) or str(fm["id"])
        for raw in _supersedes_targets(fm):
            dst = resolution.canonical(raw)  # ASK THE RESOLVER, exactly as `materialize` does
            if dst is None:
                # DANGLING. The reference denotes nothing. The old `if dst not in known: continue`
                # filter DELETED this case, which is the only reason "a derived inverse cannot
                # dangle" was ever true -- an invariant held by removing its counterexamples.
                unresolved_targets.append(
                    {
                        "id": raw,
                        "superseder": src,
                        "reason": "sci:supersedes target resolves to nothing",
                    }
                )
                continue

            # BACKED? A manual alias resolves whether or not any RECORD backs the id. No record
            # means no kind; no kind means the legality question below is UNANSWERABLE -- and an
            # unanswerable guard must not return "benign". Dangling with extra steps. It BLOCKS.
            dst_kind = resolution.kind_of(dst)
            if dst_kind is None:
                unresolved_targets.append(
                    {
                        "id": dst,
                        "superseder": src,
                        "reason": (
                            "sci:supersedes target resolves through an alias to an id that no "
                            "live, archived, or source record backs"
                        ),
                    }
                )
                continue

            # AN EDGE AT ALL? -- on the CANONICAL pair, and BEFORE the kind pair, exactly where
            # `materialize` asks it (`subject.canonical_id == object.canonical_id`, checked for any
            # predicate the moment the object resolves to an entity, before `relation_allows_kinds`).
            #
            # THE KIND-PAIR CHECK CANNOT CATCH THIS, because a self-edge's kind pair is `K -> K` --
            # legal for every kind that supersedes its own kind, which is every kind in the roster.
            # So the self-edge is admitted as real, and then `len(comp) < 2` DROPS its one-node
            # component before classification: no mismatch, no non-linear component, no blocker, and
            # `--apply` walks a corpus that does not build a graph. An entity does not supersede
            # itself; `(x, x)` is not an edge, whatever `x` is.
            if src == dst:
                self_referential.append(
                    {
                        "id": dst,
                        "superseder": src,
                        "reason": "the entity supersedes itself: the target resolves to its subject",
                    }
                )
                continue

            # LEGAL? -- BEFORE ownership, and before `_connected_components`.
            #
            # `materialize` raises on a forbidden pair for ANY resolved target, live or not: it
            # reads the resolved entity's kind and never asks who can write the file. Ask ownership
            # first and this check never runs on an archived or commons target -- an illegal edge
            # would be filed as benign, unstampable debt and apply would proceed.
            #
            # And it must be here rather than in the apply loop for the same reason one layer up: an
            # illegal edge is still an EDGE. It joins the component and counts toward in-degree, so
            # a guard inside the `linear` loop never runs on it -- the component is classified
            # NON-LINEAR, `mismatched` comes back empty, and the LEGAL supersession sharing that
            # component is silently suppressed as "branched or cyclic" when nothing branched.
            # A guard downstream of the corruption it detects is not a guard.
            src_kind = resolution.kind_of(src) or _kind_of(src, fm)
            if not relation_allows_kinds(relation, src_kind, dst_kind):
                mismatched.append(
                    {
                        "id": dst,
                        "superseder": src,
                        "reason": (
                            f"{src_kind} -> {dst_kind or '(no kind)'} is not an allowed "
                            f"sci:supersedes pair"
                        ),
                    }
                )
                continue

            # The edge is REAL. Now, and only now, the question the WRITER cares about: can we stamp
            # the thing it points at?
            if dst in resolution.archived:
                # A VALID historical supersession into a frozen record -- the ordinary end of a
                # lineage (supersede, then archive). Not an error, and not a mutation. Report it,
                # keep it out of the topology, and do NOT block.
                archived_targets.append(
                    {
                        "id": dst,
                        "superseder": src,
                        "reason": "target is archived (frozen); no live record to stamp",
                    }
                )
                continue
            if dst not in resolution.mutable:
                # RESOLVED and LEGAL, but not ours: a commons-overlay entity, a non-markdown source.
                # `materialize` builds this edge happily; we simply have no markdown file here.
                unmanaged_targets.append(
                    {
                        "id": dst,
                        "superseder": src,
                        "reason": (
                            "target resolves but is not a live markdown entity of this project; "
                            "nothing here to stamp"
                        ),
                    }
                )
                continue
            edges.add((src, dst))

    # SORTED, so the topology and every id it yields are deterministic -- a set's iteration order is
    # not. Everything below reads THIS list; nothing re-derives an admission.
    admitted = sorted(edges)
    nodes = {n for edge in admitted for n in edge}
    linear: list[SupersededChain] = []
    non_linear: list[NonLinearComponent] = []
    for comp in _connected_components(nodes, admitted):
        if len(comp) < 2:
            continue
        is_linear, survivor, members = _classify(comp, admitted)
        if not is_linear or survivor is None:
            non_linear.append(
                NonLinearComponent(
                    nodes=tuple(sorted(comp)), reason="branched or cyclic supersedes chain"
                )
            )
            continue
        linear.append(SupersededChain(survivor=survivor, superseded=tuple(sorted(members))))

    # THE IMMEDIATE SUPERSEDER, NOT THE CHAIN'S SURVIVOR. In A -> B -> C, `A` survives but the edge
    # that closed `C` was authored by `B`. `superseded_by` is the mechanical INVERSION of the
    # authored edge; stamping the survivor onto every member would collapse the chain -- lossy, and
    # an interpretation rather than an inversion. Linear chains only: a non-linear component has an
    # ambiguous survivor and must not acquire a lineage claim here.
    superseder_by_id: dict[str, str] = {}
    for chain in linear:
        members = {chain.survivor, *chain.superseded}
        for src, dst in admitted:
            if src in members and dst in members:
                superseder_by_id[dst] = src  # a linear chain is a path: exactly one in-edge

    # THE FOURTH OUTCOME, derived from the ADMITTED edges and nothing else.
    #
    # An inverse that RESOLVES and is still groundless: schema passes (non-empty string),
    # `check_resolution` passes (the id resolves -- it only ever caught DANGLING refs), and
    # reconciliation never looks (the record is in no chain, because there is no edge). Four nets,
    # zero coverage -- for the exact failure `supersedes:` was deleted to prevent: a lineage that is
    # true and grounded in nothing.
    #
    # Compared against `edges` (ALL admitted edges), NOT `superseder_by_id` (linear only): a member
    # of a BRANCHED component has a real in-edge and IS backed, even though it is never stamped.
    superseded_by_id: dict[str, str] = {}
    unbacked_inverses: list[dict[str, str]] = []
    for _path, fm in entries:
        raw_inverse = fm.get("superseded_by")
        if not isinstance(raw_inverse, str) or not raw_inverse:
            continue
        eid = resolution.canonical(str(fm["id"])) or str(fm["id"])
        superseder = resolution.canonical(raw_inverse)
        if superseder is None:
            continue  # a DANGLING inverse -- `check_resolution` owns that one, not this check
        if (superseder, eid) not in edges:
            # SAME SHAPE as the other outcomes -- {id, superseder, reason}. `SupersessionError`
            # formats a blocking list uniformly, so a bespoke key name would KeyError inside the
            # raise: the failure path would fail.
            unbacked_inverses.append(
                {
                    "id": eid,
                    "superseder": superseder,
                    "reason": (
                        "authored superseded_by has no canonical sci:supersedes edge behind it"
                    ),
                }
            )
        superseded_by_id[eid] = superseder  # canonicalized, so reconciliation compares like-for-like

    return SupersedesGraph(
        linear=tuple(linear),
        non_linear=tuple(non_linear),
        status_by_id=MappingProxyType(status_by_id),
        kind_by_id=MappingProxyType(kind_by_id),
        path_by_id=MappingProxyType(path_by_id),
        edges=frozenset(edges),
        superseder_by_id=MappingProxyType(superseder_by_id),
        superseded_by_id=MappingProxyType(superseded_by_id),
        self_referential=tuple(self_referential),
        mismatched=tuple(mismatched),
        archived_targets=tuple(archived_targets),
        unmanaged_targets=tuple(unmanaged_targets),
        unresolved_targets=tuple(unresolved_targets),
        unbacked_inverses=tuple(unbacked_inverses),
    )


# ---------------------------------------------------------------------------------------------
# the derived writer, and the operation
# ---------------------------------------------------------------------------------------------


def _prepare_supersession(
    project_root: Path, graph: SupersedesGraph, member: str
) -> _PreparedWrite:
    """Prepare `status: superseded` + its derived inverse for one member. Writes NOTHING.

    ☠️ `superseded_by` is NEVER a parameter. It is READ from `graph.superseder_by_id`, which is
    populated from the admitted canonical edges and nothing else — so there is no argument a caller
    could corrupt, and a groundless inverse is *unexpressible* rather than merely unreached. A field
    nobody can author is not the same as a field nobody can pass; this is the latter, closed.
    """
    return _prepare_write(
        project_root,
        member,
        {"status": _SUPERSEDED, "superseded_by": graph.superseder_by_id[member]},
    )


def mark_superseded(project_root: Path, *, apply: bool) -> dict[str, Any]:
    """Scan supersedes chains under ``project_root`` and report (or apply) the `superseded`
    auto-derivation, status **and** lineage.

    Returns a dict with keys:
    - ``chains``: linear chains as ``{"survivor", "members" (sorted), "linear": True}``.
    - ``non_linear``: branched/cyclic components as ``{"nodes" (sorted), "reason"}``.
    - ``to_mark``: member ids a linear chain would stamp ``superseded`` (excludes already-superseded
      members and members whose kind can't carry the status). **Unchanged meaning.**
    - ``applied``: member ids actually stamped (empty unless ``apply=True``). **Unchanged meaning.**
    - ``skipped_kinds``: ``{"id", "kind"}`` for members whose kind does not declare ``superseded``.
    - ``to_repair`` / ``repaired``: members whose status was ALREADY ``superseded`` but whose derived
      inverse was missing or stale. A separate key on purpose — widening ``applied`` would silently
      change what an existing, JSON-serialized key means for every consumer already reading it, and
      a field whose meaning changes under a consumer is worse than one that disappears.
    - ``self_referential`` / ``mismatched_kinds`` / ``unresolved_targets`` / ``unbacked_inverses``:
      refuse **and block**.
    - ``archived_targets`` / ``unmanaged_targets``: refuse to stamp, but **do not block**.
    """
    project_root = project_root.resolve()
    entries = iter_entity_frontmatter(project_root)
    graph = build_supersedes_graph(entries, _id_resolution(project_root, entries))

    chains: list[dict[str, Any]] = []
    to_mark: list[str] = []
    to_repair: list[str] = []
    skipped_kinds: list[dict[str, str]] = []
    for chain in graph.linear:
        chains.append(
            {"survivor": chain.survivor, "members": list(chain.superseded), "linear": True}
        )
        for member in chain.superseded:
            kind = graph.kind_by_id.get(member, member.split(":", 1)[0])
            if not _supports_superseded(kind):
                skipped_kinds.append({"id": member, "kind": kind})
                continue
            # THE PROJECTION IS RECONCILED, NOT MERELY INITIALIZED. A bare `status == superseded`
            # short-circuit conflates "the status is already right" with "the projection is already
            # right", so a missing or stale inverse stays broken forever and no re-run repairs it.
            if graph.status_by_id.get(member) != _SUPERSEDED:
                to_mark.append(member)  # status not yet stamped
            elif graph.superseded_by_id.get(member) != graph.superseder_by_id[member]:
                to_repair.append(member)  # status fine, inverse MISSING or STALE
            # else: fully reconciled -- touch nothing, not one byte.

    report: dict[str, Any] = {
        "chains": chains,
        "non_linear": [{"nodes": list(c.nodes), "reason": c.reason} for c in graph.non_linear],
        "to_mark": to_mark,
        "applied": [],
        "skipped_kinds": skipped_kinds,
        "to_repair": to_repair,
        "repaired": [],
        # The admission outcomes come OFF THE GRAPH. They are not recomputed here: the builder
        # decided, and a second classification could disagree with the first.
        "self_referential": [dict(s) for s in graph.self_referential],
        "mismatched_kinds": [dict(m) for m in graph.mismatched],
        "unresolved_targets": [dict(u) for u in graph.unresolved_targets],
        "archived_targets": [dict(a) for a in graph.archived_targets],
        "unmanaged_targets": [dict(u) for u in graph.unmanaged_targets],
        "unbacked_inverses": [dict(u) for u in graph.unbacked_inverses],
    }
    if not apply:
        return report

    # ALL-OR-NONE, PHASE 1: the authored graph must BE a graph, and the corpus must not contradict
    # it. `archived_targets`/`unmanaged_targets` are NOT here -- both are edges the graph resolves
    # fine and that we simply have no local markdown file to stamp. `unbacked_inverses` IS: a record
    # claiming a superseder the graph does not contain means the corpus disagrees with itself about
    # what supersedes what. There is no edge to reconcile TOWARD, so the honest moves are refuse and
    # report -- never a silent "fix".
    blocking = [
        *graph.self_referential,
        *graph.mismatched,
        *graph.unresolved_targets,
        *graph.unbacked_inverses,
    ]
    if blocking:
        raise SupersessionError(blocking)

    # ALL-OR-NONE, PHASE 2: PREPARE EVERY WRITE BEFORE COMMITTING ANY OF THEM. A member can fail the
    # write boundary for reasons this function never looked at -- an unrelated invalid field already
    # on the record. With a sequential write-and-validate loop, member 1 lands on disk and member 2
    # raises, leaving a corpus that is neither the old state nor the new one.
    #
    # What this does NOT promise: atomicity against a process kill partway through the commit loop.
    # Individual writes are atomic; the loop is not. What makes that survivable is the reconciliation
    # above -- a re-run recomputes the graph, sees the members whose projection is missing or stale,
    # and finishes the job.
    prepared = [_prepare_supersession(project_root, graph, m) for m in (*to_mark, *to_repair)]
    for write in prepared:  # validation is BEHIND us; this loop only commits
        _commit_write(write)

    report["applied"] = list(to_mark)
    report["repaired"] = list(to_repair)
    return report
