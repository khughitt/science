"""Does every authored relation MATERIALIZE? — asked once, by the code that materializes.

☠️ THIS MODULE EXISTS BECAUSE A SECOND OPINION IS A SECOND BUG. Its rules are not written here.
Every per-edge verdict is `admit_authored_relation`'s — the *same call* `materialize` makes on the
*same* `SourceRelation` stream — and this module only decides what to do with the refusal: collect
it and report it, instead of raising on the first one and stopping.

The alternative was tried. A hand-written authority that "asked the same question" as the graph
builder was wrong six times in a row, and every time in the same direction: it asked a NARROWER
question. It read entity markdown while the builder read `relations.yaml` too. It scanned
`sci:supersedes` while the builder scanned `{amends, supersedes}` as one family. It walked the
edges it could WRITE while the builder walked the edges it could RESOLVE. It let an ARCHIVED
record author an edge that the builder refuses from any non-live subject. Each fix closed one gap
and left the frame — and the frame was the defect. A validator narrower than the builder reports a
clean corpus that has no graph, which is worse than no validator at all: it is a certificate that
something checked.

So the question is asked ONCE, in the builder's own words:

    for relation in sources.relations:
        try:    admit_authored_relation(relation, ...)
        except RelationRejection as rejected:   # <- the rule that fired, with its code
            ...

A rule the builder gains, this audit gains. A rule the builder loses, this audit loses. There is
no third place to forget one — the membership-role rule and the unsupported-`graph_layer` refusal
both arrived here without being written here, and neither was on the hand-written list.

☠️ WITH ONE OBLIGATION, WHICH IS THE PRICE OF DELEGATION: a refusal is only *collectable* if it is
typed. `_graph_uri` raised a bare `ValueError`, `admit_authored_relation` let it through, and this
loop catches `RelationRejection` — so that rule did not reach the report; it CRASHED it. The fix was
at the boundary, not here (materialize.py). The standing rule: every path out of admission that
means "this does not materialize" carries a `RelationRejection` with a code. An untyped refusal is
not a stricter check, it is a broken one.

TWO KINDS OF QUESTION LIVE HERE, and only two:

  - PER-EDGE — resolution and endpoint validity. Delegated, entirely. Not re-implemented, not
    "kept in sync", not summarized.
  - CORPUS-LEVEL — acyclicity of the `{sci:amends, sci:supersedes}` lineage, which is a property of
    the edge SET and cannot be asked of one edge. `materialize` asks it of the finished dataset
    (`_validate_no_amendment_cycles`) and raises on the first cycle it closes; a CHECK has to name
    every offender and name the same ones every run, so this asks it of the admitted edges, via
    strongly-connected components. The two agree by construction: `sci:supersedes` and `sci:amends`
    triples enter the graph from authored relations and from nowhere else. (`superseded_by:`
    frontmatter emits `sci:supersededBy` — the INVERSE predicate, which is not in the cycle scan's
    family and does not belong in it.)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.materialize import (
    AdmittedRelation,
    RelationRejection,
    admit_authored_relation,
)
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import _EXTERNAL_PREFIXES, ProjectSources, external_prefixes

_AMENDMENT_PREDICATES = ("supersedes", "amends")


@dataclass(frozen=True)
class RelationDefect:
    """One authored relation the corpus cannot materialize, and where it is written.

    `path` is the **project-relative** file that authored the edge, straight off
    `SourceRelation.source_path`. Not the subject's markdown: an edge in `relations.yaml` is a line
    in *that* file, and its subject may have no markdown in this project at all. A finding has to
    name a file someone can open.
    """

    code: str
    path: str
    subject: str
    predicate: str
    object: str
    message: str


@dataclass(frozen=True)
class RelationAudit:
    """Every authored relation, sorted into the ones that build and the ones that don't."""

    admitted: tuple[AdmittedRelation, ...]
    defects: tuple[RelationDefect, ...]

    def relations(self, name: str) -> list[AdmittedRelation]:
        """Every ADMITTED relation of one kind — resolved by the profile's relation NAME.

        Not by a string compare against `"sci:supersedes"`. A predicate is a CURIE *or* an absolute
        IRI (`_resolve_relation_term` accepts both), so the same edge has more than one authored
        spelling, and a CURIE compare drops the IRI spelling out of every consumer while the graph
        builder emits it normally. Admission already resolved the term; ask what it resolved TO.
        """
        return [
            a for a in self.admitted if a.relation_kind is not None and a.relation_kind.name == name
        ]


def audit_relations(project_root: Path, sources: ProjectSources) -> RelationAudit:
    """Admit every authored relation through `materialize`'s own admission; collect the refusals.

    The context — resolver, entity index, external prefixes, active archive — is built with the
    SAME calls `_emit_phase` makes, from the SAME `ProjectSources`. An edge admitted against one
    snapshot of the corpus and resolved against another is an edge nobody validated.
    """
    from science_tool.archive import load_archive_index

    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
        identity_table=build_identity_table(sources),
    )
    entity_index = {entity.canonical_id: entity for entity in sources.entities}
    ext_prefixes = _EXTERNAL_PREFIXES | external_prefixes(sources.ontology_catalogs)
    archive_active = load_archive_index(project_root).active_by_id

    admitted: list[AdmittedRelation] = []
    defects: list[RelationDefect] = []
    for relation in sources.relations:
        try:
            admitted.append(
                admit_authored_relation(
                    relation,
                    entity_index=entity_index,
                    resolver=resolver,
                    ext_prefixes=ext_prefixes,
                    archive_active=archive_active,
                )
            )
        except RelationRejection as rejected:
            defects.append(
                RelationDefect(
                    code=rejected.code,
                    path=relation.source_path,
                    subject=relation.subject,
                    predicate=relation.predicate,
                    object=relation.object,
                    message=str(rejected),
                )
            )

    defects.extend(_lineage_cycles(admitted))
    return RelationAudit(admitted=tuple(admitted), defects=tuple(defects))


def _lineage_cycles(admitted: list[AdmittedRelation]) -> list[RelationDefect]:
    """Every admitted edge lying on a cycle in the amendment/supersession lineage.

    OVER THE FAMILY, NOT OVER `supersedes` ALONE: `_validate_no_amendment_cycles` walks
    `{sci:amends, sci:supersedes}` as ONE relation. `a supersedes b` + `b amends a` is two legal
    pairs, no self-reference, every per-edge rule green — and no graph. A supersedes-only scan sees
    a clean linear chain there and offers to stamp it.

    ONE DEFECT PER AUTHORED EDGE, not one per cycle: a cycle is a property of the edge set, every
    edge in it is implicated, and any one of them is a place to break it.
    """
    authored: dict[tuple[str, str], set[tuple[str, str]]] = {}  # pair -> {(path, predicate)}
    for a in admitted:
        if a.relation_kind is None or a.relation_kind.name not in _AMENDMENT_PREDICATES:
            continue
        obj = a.object_canonical_id
        if obj is None:
            continue  # an external term is not a node in the lineage
        authored.setdefault((a.subject.canonical_id, obj), set()).add(
            (a.relation.source_path, a.relation.predicate)
        )

    found: list[RelationDefect] = []
    for component in _cyclic_components(sorted(authored)):
        members = ", ".join(sorted(component))
        for src, dst in sorted(p for p in authored if p[0] in component and p[1] in component):
            for path, predicate in sorted(authored[(src, dst)]):
                found.append(
                    RelationDefect(
                        code="cycle",
                        path=path,
                        subject=src,
                        predicate=predicate,
                        object=dst,
                        message=(
                            f"cycle in amendment/supersession relations: {src} {predicate} {dst} "
                            f"lies on a cycle through: {members}"
                        ),
                    )
                )
    return found


def _cyclic_components(edges: list[tuple[str, str]]) -> list[frozenset[str]]:
    """Every cycle in the lineage, as a node set — the strongly connected components of size >= 2.

    SCCs, not "the first cycle a DFS happens to close". `materialize` raises on the first one and
    stops, which is right for a hard failure; a CHECK has to name every offender, and name the same
    ones on every run. An SCC of size >= 2 says exactly "these nodes can all reach one another", so
    an edge lies on a cycle iff both its endpoints share one — no ordering, no arbitrary entry node.

    (Size >= 2 because a self-loop is a one-node SCC. A self-edge never reaches here: admission
    rejects it as `self-referential`, and an entity that supersedes itself is a different defect
    from two entities that supersede each other.)
    """
    adjacency: dict[str, list[str]] = {}
    for src, dst in edges:
        adjacency.setdefault(src, []).append(dst)
        adjacency.setdefault(dst, [])

    index: dict[str, int] = {}
    low: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    counter = 0
    found: list[frozenset[str]] = []

    def strongconnect(node: str) -> None:
        nonlocal counter
        index[node] = low[node] = counter
        counter += 1
        stack.append(node)
        on_stack.add(node)
        for target in sorted(adjacency[node]):
            if target not in index:
                strongconnect(target)
                low[node] = min(low[node], low[target])
            elif target in on_stack:
                low[node] = min(low[node], index[target])
        if low[node] == index[node]:
            component: set[str] = set()
            while True:
                popped = stack.pop()
                on_stack.discard(popped)
                component.add(popped)
                if popped == node:
                    break
            if len(component) > 1:
                found.append(frozenset(component))

    for node in sorted(adjacency):
        if node not in index:
            strongconnect(node)
    return sorted(found, key=sorted)
