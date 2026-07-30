"""Entity consolidation — derive `superseded` (and its lineage) from supersedes chains.

Read-only by default (report); `--apply` stamps `status: superseded` **and the derived inverse
`superseded_by`** on the superseded members of *linear* chains only.

A BRANCH and a CYCLE ARE NOT THE SAME OUTCOME, and grouping them cost this module six review rounds.
A **branch** is a legal graph with an ambiguous survivor: it materializes, it is reported, and apply
skips it pending human review. A **cycle** is not a graph at all — `materialize` refuses it — so it
is a `relation.cycle` ERROR from the relation audit, and it BLOCKS apply for the whole corpus rather
than being quietly stepped around. Every other invalid relation blocks the same way, supersession or
not: a corpus that does not materialize is not one this tool derives anything from.

The canonical machine-readable supersession edge is a relation with `predicate: "sci:supersedes"`,
authored on the **successor**, pointing newer → older. It is **not** top-level `supersedes:`
(silently dropped), and not `sci:amends` (which revises, not replaces).

**THIS MODULE DOES NOT DECIDE WHAT AN EDGE IS.** `science_tool.graph.relation_audit` does, by
delegating to `materialize`'s own `admit_authored_relation` — so the edges here are, by
construction, the edges the graph builder admits. Six review rounds found six defects in a
hand-written admission ladder that lived in this file, and every one of them was the same defect:
it asked a NARROWER question than `materialize` asks. The ladder is gone. What remains is the only
question this module is actually the authority on:

    the edge is REAL — can we STAMP the thing it points at?

That is the WRITER's question, and `archived` / `mutable` are the WRITER's populations. Legality,
resolvability, acyclicity and endpoint validity are the BUILDER's, asked once, in the builder's
words. When the audit refuses an edge, apply refuses too: a corpus that does not materialize is not
one this tool derives anything from.

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

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Mapping

from pydantic import BaseModel, ConfigDict

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.entities import _commit_write, _PreparedWrite
from science_tool.entity_scan import iter_entity_markdown
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.relation_audit import RelationAudit, RelationDefect, audit_relations
from science_tool.kind_descriptors import DECLARED_SUPERSEDABLE

if TYPE_CHECKING:
    from science_tool.graph.sources import ProjectSources

_SUPERSEDED = "superseded"
_SUPERSEDES = "supersedes"


class SupersessionError(RuntimeError):
    """An authored supersession the corpus cannot honour.

    Either a relation the graph builder REFUSES (the audit's verdict, whatever rule fired: an
    endpoint that resolves nowhere or to a record that is not live, a kind pair the relation model
    forbids, an entity superseding itself, a cycle in the amendment/supersession lineage), or an
    authored inverse with no edge behind it. Apply is ALL-OR-NONE over these: the derivation is
    corpus-wide, and if part of the corpus is not a graph, the derivation is not trustworthy
    anywhere.
    """

    def __init__(self, blocking: list[str]) -> None:
        super().__init__("refusing to apply: " + "; ".join(blocking))
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


def _kind_or_prefix(entity_id: str, declared: object) -> str:
    """The declared kind, else the id prefix. Ids are `<kind>:<slug>`."""
    return str(declared or entity_id.split(":", 1)[0])


def _kind_of(entity_id: str, fm: dict[str, Any]) -> str:
    return _kind_or_prefix(entity_id, fm.get("kind"))


# ---------------------------------------------------------------------------------------------
# resolution — resolvable, ours, and legal are THREE questions
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class IdResolution:
    """How an authored reference becomes a canonical id, and WHO OWNS that id.

    It carries the CONFIGURED RESOLVER, not a token dump: per-entity `aliases`/`same_as` live in
    neither the live scan nor the manual-alias map — they are registered inside `build_alias_map`,
    which the resolver owns. Ask the resolver; do not reconstruct what it knows.

    THE WRITER'S TWO POPULATIONS, AND NOTHING ELSE. `mutable` is the LIVE MARKDOWN scan — not
    `sources.entities`, which also carries commons-overlay and non-markdown entities that
    `iter_entity_frontmatter` never saw and the graph's live maps have no key for. `archived` is the
    active archive.

    There is deliberately NO kind map here any more. A kind map in this file existed to answer
    "is this edge LEGAL?", which is not this module's question and never was — it is
    `materialize`'s, and it is now asked there, once. (The docstring that used to live here asserted
    that materialize "reads the resolved entity's kind, live or not, and never asks who can write
    the file". That is true of the OBJECT endpoint and FALSE of the SUBJECT, which must be a live
    loaded entity. Generalizing it to both endpoints is how an ARCHIVED record came to author a
    supersession that `--apply` then stamped into a live one.)
    """

    resolver: ReferenceResolver  # the SAME object, with the SAME args, that `materialize` builds
    mutable: frozenset[str]  # canonical ids of LIVE MARKDOWN entities -- the only stampable set
    archived: frozenset[str]  # canonical ids of ACTIVE archived rows

    def canonical(self, raw: str) -> str | None:
        res = self.resolver.resolve(raw)
        return res.canonical_id if res.status == "resolved" and res.canonical_id else None


@dataclass(frozen=True)
class SupersessionInputs:
    """Everything the builder reads, loaded ONCE — and the VERDICT it reads the edges *through*.

    `audit` is `materialize`'s admission over the whole `sources.relations` stream: which authored
    relations build, and which do not, decided by the graph builder itself. The builder below never
    re-decides an admission — it consumes one.

    `entries` stays separate and stays *markdown*: it is the WRITER's population — the records
    `mark_superseded` can stamp, and the only place an authored `superseded_by` can live.
    """

    entries: tuple[tuple[Path, dict[str, Any]], ...]
    resolution: IdResolution
    audit: RelationAudit


def load_supersession_inputs(
    project_root: Path,
    *,
    sources: ProjectSources | None = None,
) -> SupersessionInputs:
    """Load the entries, the resolver, and the relation audit — from ONE `load_project_sources` pass.

    One pass because the resolver and the audit have to agree: an edge admitted against one snapshot
    of the corpus and resolved against another is an edge nobody validated.
    """
    from science_tool.graph.sources import load_project_sources

    entries = iter_entity_frontmatter(project_root)
    if sources is None:
        sources = load_project_sources(project_root)
    return SupersessionInputs(
        entries=tuple(entries),
        resolution=_id_resolution(project_root, entries, sources),
        audit=audit_relations(project_root, sources),
    )


def _id_resolution(
    project_root: Path, entries: list[tuple[Path, dict[str, Any]]], sources: ProjectSources
) -> IdResolution:
    """Built with the SAME CALL the materializer makes — not a reimplementation of it.

    Same three arguments, same answers, which is the only way "an edge that materializes must not be
    reported unstampable" is a guarantee rather than a coincidence. (`sources.manual_aliases` already
    has the archive's `resolvable_ids()` folded in, so archived aliases resolve too.)
    """
    from science_tool.archive import load_archive_index
    from science_tool.graph.identity_table import build_identity_table

    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
        identity_table=build_identity_table(sources),
    )

    def canon_or_self(raw: str) -> str:
        res = resolver.resolve(raw)
        return res.canonical_id if res.status == "resolved" and res.canonical_id else raw

    # MUTABLE = the MARKDOWN SCAN, canonicalized. NOT `sources.entities`: that list also carries
    # commons-overlay and non-markdown entities the live scan never yielded, so the graph's
    # `kind_by_id`/`path_by_id` have no key for them -- classify one as stampable and the next line
    # KeyErrors.
    return IdResolution(
        resolver=resolver,
        mutable=frozenset(canon_or_self(str(fm["id"])) for _path, fm in entries),
        archived=frozenset(load_archive_index(project_root).active_by_id),
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
    """A BRANCHED component — a valid corpus with an ambiguous survivor. Reported, never acted on.

    Branched, and no longer "branched **or cyclic**". Those are not one outcome and never were: a
    branch materializes into a perfectly good graph and is merely ambiguous about which node
    survives, while a cycle is a corpus `materialize` REFUSES to build at all
    (`_validate_no_amendment_cycles`). Filing them together gave the cycle a branch's disposition —
    reported, skipped, and *not blocking* — so `--apply` returned clean over a corpus that has no
    graph. A cycle is a relation-VALIDITY failure, so it is not this module's to classify: it comes
    back from the audit as a `code == "cycle"` defect, rides `SupersedesGraph.invalid` out to
    `report["invalid_relations"]` with every other refusal, and it BLOCKS apply.
    """

    nodes: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SupersedesGraph:
    """The topology, the inversion, and the writer's disposition of every admitted edge.

    `invalid` is the AUDIT's verdict, passed through untouched — every authored relation the graph
    builder refuses, whatever the rule. This module does not classify those and must not: it once
    did, in four hand-maintained buckets, and the buckets were narrower than the builder every
    single time. There is one bucket now, it is not ours, and it BLOCKS.

    `kind_by_id` and `path_by_id` are LIVE-ONLY: the writer's map of what it can stamp. `edges` is
    the ADMITTED and STAMPABLE set — the edges that both build and land in a file we own — and it is
    exposed precisely so the unbacked-inverse rule can ask "is there an edge behind this?" without
    re-deciding what an edge is.
    """

    linear: tuple[SupersededChain, ...]
    non_linear: tuple[NonLinearComponent, ...]
    status_by_id: Mapping[str, str | None]
    kind_by_id: Mapping[str, str]  # LIVE entities -- the population `mark_superseded` stamps
    path_by_id: Mapping[str, Path]  # LIVE entities -- `Result` reports a FILE, not an id
    edges: frozenset[tuple[str, str]]  # ADMITTED and STAMPABLE (superseder, superseded), canonical
    superseder_by_id: Mapping[str, str]  # superseded id -> its IMMEDIATE superseder (linear only)
    superseded_by_id: Mapping[str, str]  # superseded id -> the AUTHORED inverse, CANONICALIZED
    invalid: tuple[RelationDefect, ...]  # every relation MATERIALIZE REFUSES -- not our verdict
    archived_targets: tuple[dict[str, str], ...]  # edge resolves INTO the archive -- historical
    unmanaged_targets: tuple[dict[str, str], ...]  # edge resolves, but to nothing WE can stamp
    unbacked_inverses: tuple[dict[str, str], ...]  # authored inverse with NO admitted edge behind it
    supported_kinds: frozenset[str]  # the frozen auto-apply policy (I4) -- travels WITH the graph


def _classify_from_projections(
    material: SupersessionDecisionMaterial, *, path_by_id: Mapping[str, Path]
) -> SupersedesGraph:
    """The single supersession classifier. A pure function of the material projections plus a
    live-only path map.

    Both `build_supersedes_graph` (live, FS-backed) and `build_supersedes_graph_from_material`
    (frozen material, no filesystem) call this. `path_by_id` is the ONLY thing that differs between
    the two callers -- it is live-only and not decision-bearing (`Result` needs a FILE, but nothing
    that decides WHAT to stamp reads a path) -- so the two entry points are structurally guaranteed
    to classify identically wherever it matters.

    The audit has already decided WHICH EDGES ARE REAL — resolvable, legal, non-self-referential,
    acyclic — by asking `materialize`'s own admission, and `_project_inputs` froze that verdict into
    `material.admitted_supersedes` / `material.defects`. This function asks the one question left:
    OF THE REAL EDGES, WHICH TARGETS CAN WE STAMP? Archived (frozen: report, don't block), unmanaged
    (not our markdown: report, don't block), or ours (stamp it).
    """
    mutable = frozenset(material.mutable_population)
    archived = frozenset(material.archived_population)
    status_by_id: dict[str, str | None] = {e.eid: e.status for e in material.entries}
    kind_by_id: dict[str, str] = {e.eid: e.kind for e in material.entries}

    # THE EDGE IS ALREADY REAL. `material.admitted_supersedes` is exactly the relations `materialize`
    # ADMITTED: the subject is a live loaded entity, the object resolves to a live entity or an
    # active archived row, the kind pair is allowed, it is not a self-edge, and the lineage it sits
    # in is acyclic. Not one of those questions is re-asked here, because every time this module
    # asked one of them itself it asked a narrower version and let a corpus through that has no
    # graph. What is left below is the single question this module owns: CAN WE STAMP THE TARGET?
    #
    # A SET, NOT A LIST -- because an RDF graph is a set of triples, and `materialize` collapses the
    # identical triple authored twice into the one edge it is. Counting degrees off a list turns a
    # duplicate spelling (the canonical id once and an alias of it once) into a second in-edge AND a
    # second out-edge, so an ordinary one-edge chain classifies as branched and is silently skipped.
    edges: set[tuple[str, str]] = set()
    archived_targets: list[dict[str, str]] = []
    unmanaged_targets: list[dict[str, str]] = []

    for ep in material.admitted_supersedes:
        src, dst, path_of_edge = ep.src, ep.dst, ep.source_path
        if dst is None:
            continue  # an EXTERNAL term: a real edge, but not a node of this project, so unstampable

        if dst in archived:
            # A VALID historical supersession into a frozen record -- the ordinary end of a lineage
            # (supersede, then archive). Not an error, and not a mutation. Report it, keep it out of
            # the topology, and do NOT block.
            archived_targets.append(
                {
                    "id": dst,
                    "superseder": src,
                    "path": path_of_edge,
                    "reason": "target is archived (frozen); no live record to stamp",
                }
            )
            continue
        if dst not in mutable:
            # ADMITTED, but not ours: a commons-overlay entity, a non-markdown source. `materialize`
            # builds this edge happily; we simply have no markdown file here to write.
            unmanaged_targets.append(
                {
                    "id": dst,
                    "superseder": src,
                    "path": path_of_edge,
                    "reason": (
                        "target resolves but is not a live markdown entity of this project; "
                        "nothing here to stamp"
                    ),
                }
            )
            continue
        edges.add((src, dst))

    # Nodes the audit says lie on a lineage cycle. A component touching one is not a chain and not a
    # branch -- it is a corpus with no graph, already reported edge-by-edge in `invalid`. Skipping it
    # below is the second lock, behind `--apply`'s refusal: a cycle closed by an `amends` edge can
    # leave the `supersedes` edges perfectly linear, so this component would otherwise be advertised
    # as a STAMPABLE chain. Nothing inside a cycle is stampable.
    cyclic_nodes = frozenset(
        node for d in material.defects if d.code == "cycle" for node in (d.subject, d.object)
    )

    # --- UNCHANGED from the pre-refactor build_supersedes_graph body -------------------------------
    # SORTED, so the topology and every id it yields are deterministic -- a set's iteration order is
    # not. Everything below reads THIS list; nothing re-derives an admission.
    admitted = sorted(edges)
    nodes = {n for edge in admitted for n in edge}
    linear: list[SupersededChain] = []
    non_linear: list[NonLinearComponent] = []
    for comp in _connected_components(nodes, admitted):
        if len(comp) < 2:
            continue
        if comp & cyclic_nodes:
            # ALREADY DIAGNOSED, by the audit, and diagnosed better -- see `cyclic_nodes` above for
            # why nothing in a cyclic component is stampable.
            continue
        is_linear, survivor, members = _classify(comp, admitted)
        if not is_linear or survivor is None:
            non_linear.append(
                NonLinearComponent(nodes=tuple(sorted(comp)), reason="branched supersedes chain")
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
        chain_members = {chain.survivor, *chain.superseded}
        for src, dst in admitted:
            if src in chain_members and dst in chain_members:
                superseder_by_id[dst] = src  # a linear chain is a path: exactly one in-edge
    # --- end UNCHANGED block ------------------------------------------------------------------------

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
    for e in material.entries:
        if e.superseded_by_raw is None:
            continue
        superseder = e.superseded_by_canonical
        if superseder is None:
            continue  # a DANGLING inverse -- `check_resolution` owns that one, not this check
        if (superseder, e.eid) not in edges:
            # SAME SHAPE as the other outcomes -- {id, superseder, reason}. `SupersessionError`
            # formats a blocking list uniformly, so a bespoke key name would KeyError inside the
            # raise: the failure path would fail.
            unbacked_inverses.append(
                {
                    "id": e.eid,
                    "superseder": superseder,
                    "reason": (
                        "authored superseded_by has no canonical sci:supersedes edge behind it"
                    ),
                }
            )
        superseded_by_id[e.eid] = superseder  # canonicalized, so reconciliation compares like-for-like

    invalid = tuple(
        RelationDefect(code=d.code, path=d.path, subject=d.subject, predicate=d.predicate,
                       object=d.object, message=d.message)
        for d in material.defects
    )
    return SupersedesGraph(
        linear=tuple(linear),
        non_linear=tuple(non_linear),
        status_by_id=MappingProxyType(status_by_id),
        kind_by_id=MappingProxyType(kind_by_id),
        path_by_id=MappingProxyType(dict(path_by_id)),
        edges=frozenset(edges),
        superseder_by_id=MappingProxyType(superseder_by_id),
        superseded_by_id=MappingProxyType(superseded_by_id),
        invalid=invalid,
        archived_targets=tuple(archived_targets),
        unmanaged_targets=tuple(unmanaged_targets),
        unbacked_inverses=tuple(unbacked_inverses),
        supported_kinds=frozenset(material.supported_kinds),  # I4: policy travels on the graph
    )


def build_supersedes_graph(inputs: SupersessionInputs) -> SupersedesGraph:
    """Classify the supersession lineage from the loaded `inputs`.

    A thin wrapper now: project the inputs through `_project_inputs` (the SAME projection Gate A
    freezes into a `SupersessionDecisionMaterial`), keep the live-only path map, and run the shared
    classifier `_classify_from_projections`. This is what makes the live path and the
    material-derived path (`build_supersedes_graph_from_material`) produce the SAME graph on every
    decision-bearing field: they are the same function, called with the same material, differing
    only in `path_by_id`.

    A pure function of its inputs: it never touches the filesystem itself (the loader does), which
    is what lets a test construct the commons/non-markdown populations — and the audit's verdict —
    as the data they are.
    """
    material = _project_inputs(inputs)
    resolution = inputs.resolution
    path_by_id: dict[str, Path] = {}
    for path, fm in inputs.entries:
        eid = resolution.canonical(str(fm["id"])) or str(fm["id"])
        path_by_id[eid] = path
    return _classify_from_projections(material, path_by_id=path_by_id)


def build_supersedes_graph_from_material(
    material: SupersessionDecisionMaterial,
) -> SupersedesGraph:
    """Gate-B derivation: rebuild the disposition from the frozen material, no filesystem read.

    `path_by_id` is empty on purpose -- paths are not decision-bearing (see `_classify_from_projections`)
    -- so a caller that needs a path (there is none here: the material carries no filesystem) never
    gets one silently wrong.
    """
    return _classify_from_projections(material, path_by_id={})


# ---------------------------------------------------------------------------------------------
# decision material — the classifier's INPUT projections, frozen for a Gate A drift digest
# ---------------------------------------------------------------------------------------------

_MATERIAL_VERSION = 1


class EntryProjection(BaseModel):
    """One entity's decision-relevant frontmatter: identity, status, kind, and the authored
    `superseded_by` inverse, both as-written and canonicalized."""

    model_config = ConfigDict(extra="forbid")

    eid: str
    status: str | None
    kind: str
    superseded_by_raw: str | None
    superseded_by_canonical: str | None


class EdgeProjection(BaseModel):
    """One ADMITTED `sci:supersedes` relation. Duplicates are NOT collapsed: the admitted stream
    is a list here, on purpose — collapsing it to a set is the exact degree-miscount bug
    `build_supersedes_graph` warns about for its own `edges` set."""

    model_config = ConfigDict(extra="forbid")

    src: str
    dst: str | None
    source_path: str


class DefectProjection(BaseModel):
    """One relation the audit refused — the full `RelationDefect` record, not a summary."""

    model_config = ConfigDict(extra="forbid")

    code: str
    path: str
    subject: str
    predicate: str
    object: str
    message: str


class SupersessionDecisionMaterial(BaseModel):
    """Everything `build_supersedes_graph` reads off `SupersessionInputs`, frozen BEFORE any
    graph exists. A digest over this reproduces the whole derivation — `superseded_by_id`,
    `unbacked_inverses`, `archived_targets`, `unmanaged_targets` all fall out of these same
    fields — not just the handful a graph-OUTPUT serialization would happen to keep.

    Every list is sorted for a deterministic digest, EXCEPT that sorting `admitted_supersedes`
    and `defects` never collapses a duplicate: sort is a total order over the projected tuples,
    not a dedup.
    """

    model_config = ConfigDict(extra="forbid")

    material_version: int
    entries: list[EntryProjection]
    admitted_supersedes: list[EdgeProjection]
    defects: list[DefectProjection]
    mutable_population: list[str]
    archived_population: list[str]
    supported_kinds: list[str]  # the frozen auto-apply policy the classifier reads (I4)


def _project_inputs(inputs: SupersessionInputs) -> SupersessionDecisionMaterial:
    """Serialize exactly what `build_supersedes_graph` reads off `SupersessionInputs`, resolving
    the two things the classifier needs the resolver for (each entry's canonical id and each
    authored `superseded_by`'s canonical) so the classifier can run without a resolver. Sorted for
    a deterministic digest; admitted relations and defects keep duplicates."""
    resolution = inputs.resolution
    entries: list[EntryProjection] = []
    for _path, fm in inputs.entries:
        eid = resolution.canonical(str(fm["id"])) or str(fm["id"])
        raw_inverse = fm.get("superseded_by")
        raw = raw_inverse if isinstance(raw_inverse, str) and raw_inverse else None
        entries.append(
            EntryProjection(
                eid=eid,
                status=fm.get("status"),
                kind=_kind_of(eid, fm),
                superseded_by_raw=raw,
                superseded_by_canonical=(resolution.canonical(raw) if raw else None),
            )
        )
    edges = [
        EdgeProjection(
            src=admitted_relation.subject.canonical_id,
            dst=admitted_relation.object_canonical_id,
            source_path=admitted_relation.relation.source_path,
        )
        for admitted_relation in inputs.audit.relations(_SUPERSEDES)
    ]
    defects = [
        DefectProjection(
            code=d.code, path=d.path, subject=d.subject, predicate=d.predicate,
            object=d.object, message=d.message,
        )
        for d in inputs.audit.defects
    ]
    return SupersessionDecisionMaterial(
        material_version=_MATERIAL_VERSION,
        entries=sorted(entries, key=lambda e: e.eid),
        admitted_supersedes=sorted(edges, key=lambda e: (e.src, e.dst or "", e.source_path)),
        defects=sorted(
            defects, key=lambda d: (d.code, d.subject, d.predicate, d.object, d.path, d.message)
        ),
        mutable_population=sorted(resolution.mutable),
        archived_population=sorted(resolution.archived),
        # The auto-apply supported-kind policy IS a decision input (design §5.2): serialize it so
        # the digest covers it. It is the DECLARATION (S2) -- not a re-derivation from the status
        # vocabulary, which was how lineage capability came to be answered by two surfaces.
        supported_kinds=sorted(k for k, v in DECLARED_SUPERSEDABLE.items() if v),
    )


def build_decision_material(project_root: Path) -> SupersessionDecisionMaterial:
    """The classifier's frozen INPUT — never the graph's output. Never calls
    `build_supersedes_graph`: that would invert input and output, and defeat the whole point of a
    digest that has to reproduce the derivation independently of it."""
    return _project_inputs(load_supersession_inputs(project_root))


def decision_digest(material: SupersessionDecisionMaterial) -> str:
    """A stable digest over the full decision material — Gate A's apply-time drift check."""
    return hashlib.sha256(material.model_dump_json().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------------------------
# the derived writer, and the operation
# ---------------------------------------------------------------------------------------------


def _prepare_supersession(
    project_root: Path, graph: SupersedesGraph, member: str, *, preview_date: str
) -> _PreparedWrite:
    """Prepare `status: superseded` + its derived inverse for one member. Writes NOTHING.

    ☠️ `superseded_by` is NEVER a parameter. It is READ from `graph.superseder_by_id`, which is
    populated from the admitted canonical edges and nothing else — so there is no argument a caller
    could corrupt, and a groundless inverse is *unexpressible* rather than merely unreached. A field
    nobody can author is not the same as a field nobody can pass; this is the latter, closed.

    `preview_date` is threaded through to `_prepare_write_with_date` as the `updated` default, so a
    saved plan's preview and its later apply stamp the same date.
    """
    from science_tool.entities import _prepare_write_with_date

    return _prepare_write_with_date(
        project_root,
        member,
        {"status": _SUPERSEDED, "superseded_by": graph.superseder_by_id[member]},
        updated_default=preview_date,
    )


def _disposition_report(graph: SupersedesGraph, *, ids: frozenset[str] | None) -> dict[str, Any]:
    """The dry-run report, as a PURE function of a `SupersedesGraph`. Lifted out of `mark_superseded`
    so `mark_superseded` (FS-loaded graph) and the future `plan_supersede` preview (material-derived
    graph) both call it — the disposition needs the graph and nothing else, so preview never needs a
    second filesystem load. Raises `SupersessionError` when an allowlisted id is not a derivable
    member, exactly as `mark_superseded` did before the extraction.

    Reads `graph.supported_kinds` -- the AUTHENTICATED policy carried on the graph (I4): a preview
    built from a saved material must derive the same disposition even if the live project's policy
    has since moved.
    """
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
            if kind not in graph.supported_kinds:
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

    if ids is not None:
        derivable = set(to_mark) | set(to_repair)
        unresolved = sorted(ids - derivable)
        if unresolved:
            raise SupersessionError(
                [f"allowlisted id is not derivable as a supersession member: {entity_id}" for entity_id in unresolved]
            )
        to_mark = [member for member in to_mark if member in ids]
        to_repair = [member for member in to_repair if member in ids]

    return {
        "chains": chains,
        "non_linear": [{"nodes": list(c.nodes), "reason": c.reason} for c in graph.non_linear],
        "to_mark": to_mark,
        "applied": [],
        "skipped_kinds": skipped_kinds,
        "to_repair": to_repair,
        "repaired": [],
        # The outcomes come OFF THE GRAPH. They are not recomputed here: the audit and the builder
        # decided, and a second classification could disagree with the first.
        #
        # SORTED, so the four secondary lists are CANONICAL rather than audit/scan order -- an
        # OBSERVABLE 0.5.0 behavior change (Task 18 release notes). Blocking semantics are UNCHANGED:
        # `invalid_relations` and `unbacked_inverses` still refuse apply; `archived_targets` and
        # `unmanaged_targets` still do not block. Only the order is now deterministic.
        "invalid_relations": sorted(
            (
                {
                    "code": d.code,
                    "path": d.path,
                    "subject": d.subject,
                    "predicate": d.predicate,
                    "object": d.object,
                    "message": d.message,
                }
                for d in graph.invalid
            ),
            key=lambda d: (d["code"], d["path"], d["subject"], d["predicate"], d["object"], d["message"]),
        ),
        "archived_targets": sorted(
            (dict(a) for a in graph.archived_targets),
            key=lambda a: (a["id"], a["superseder"], a["path"]),
        ),
        "unmanaged_targets": sorted(
            (dict(u) for u in graph.unmanaged_targets),
            key=lambda u: (u["id"], u["superseder"], u["path"]),
        ),
        "unbacked_inverses": sorted(
            (dict(u) for u in graph.unbacked_inverses),
            key=lambda u: (u["id"], u["superseder"]),
        ),
    }


def mark_superseded(
    project_root: Path, *, ids: frozenset[str] | None = None, apply: bool
) -> dict[str, Any]:
    """Scan supersedes chains under ``project_root`` and report (or apply) the `superseded`
    auto-derivation, status **and** lineage.

    When `ids` is provided it is AUTHORITATIVE: only enumerated members are
    written (or appear in the dry-run report), and an id that is neither
    markable nor repairable is an error in both dry-run and apply. It narrows
    BOTH write sets -- `to_mark` and `to_repair` -- because both are committed
    by the prepare loop below; a filter on `to_mark` alone would still repair
    out-of-cohort records.

    Chain derivation and graph validation remain corpus-wide: the allowlist
    narrows what is WRITTEN and REPORTED, never what is CHECKED.

    Returns a dict with keys:
    - ``chains``: linear chains as ``{"survivor", "members" (sorted), "linear": True}``.
    - ``non_linear``: BRANCHED components as ``{"nodes" (sorted), "reason"}``. No longer "branched
      *or cyclic*" — a cycle is a relation-validity failure and has its own key, which BLOCKS.
    - ``to_mark``: member ids a linear chain would stamp ``superseded`` (excludes already-superseded
      members and members whose kind is absent from the graph's frozen ``supported_kinds``).
    - ``applied``: member ids actually stamped (empty unless ``apply=True``). **Unchanged meaning.**
    - ``skipped_kinds``: ``{"id", "kind"}`` for members whose kind is absent from the graph's frozen
      ``supported_kinds`` policy. After S2 no authored input reaches this: every admissible
      supersedes target is supersedable. It remains reachable from STALE or hand-built decision
      material whose policy disagrees with its admitted edges -- which is what the I4 digest exists
      to detect.
    - ``to_repair`` / ``repaired``: members whose status was ALREADY ``superseded`` but whose derived
      inverse was missing or stale. A separate key on purpose — widening ``applied`` would silently
      change what an existing, JSON-serialized key means for every consumer already reading it, and
      a field whose meaning changes under a consumer is worse than one that disappears.
    - ``invalid_relations``: every authored relation `materialize` REFUSES, as
      ``{"code", "path", "subject", "predicate", "object", "message"}`` — the audit's verdict,
      verbatim. Replaces the old ``self_referential`` / ``mismatched_kinds`` / ``cycles`` /
      ``unresolved_targets`` keys, which were four hand-maintained buckets that between them never
      managed to cover what the graph builder actually refuses. Refuses **and blocks**.
    - ``unbacked_inverses``: an authored ``superseded_by`` with no edge behind it. Refuse **and
      block**.
    - ``archived_targets`` / ``unmanaged_targets``: refuse to stamp, but **do not block**.
    """
    project_root = project_root.resolve()
    graph = build_supersedes_graph(load_supersession_inputs(project_root))
    report = _disposition_report(graph, ids=ids)
    if not apply:
        return report

    to_mark = report["to_mark"]
    to_repair = report["to_repair"]

    # ALL-OR-NONE, PHASE 1: the authored graph must BE a graph, and the corpus must not contradict
    # it. `archived_targets`/`unmanaged_targets` are NOT here -- both are edges the graph resolves
    # fine and that we simply have no local markdown file to stamp. `unbacked_inverses` IS: a record
    # claiming a superseder the graph does not contain means the corpus disagrees with itself about
    # what supersedes what. There is no edge to reconcile TOWARD, so the honest moves are refuse and
    # report -- never a silent "fix".
    #
    # `graph.invalid` is EVERY relation the audit refused, not only the supersession ones -- because
    # a corpus with any unbuildable relation HAS NO GRAPH, and stamping a derived lineage into it
    # writes a record whose graph never builds. This derivation is corpus-wide or it is nothing.
    blocking = [
        *(f"{d.path}: {d.message}" for d in graph.invalid),
        *(f"{u['superseder']} -> {u['id']} ({u['reason']})" for u in graph.unbacked_inverses),
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
    from datetime import date

    _preview_date = date.today().isoformat()
    prepared = [
        _prepare_supersession(project_root, graph, m, preview_date=_preview_date)
        for m in (*to_mark, *to_repair)
    ]
    for write in prepared:  # validation is BEHIND us; this loop only commits
        _commit_write(write)

    report["applied"] = list(to_mark)
    report["repaired"] = list(to_repair)
    return report
