"""Materialization of entity.origins/added_by as minimal PROV-O.

Covers `_add_entity` (via `_add_relations`, where entity_uri/resolver/provenance
are in scope) emitting sci:hasOrigin nodes, prov:wasAttributedTo/wasDerivedFrom
edges, and the sci:addedBy stamp.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, Literal, Namespace, URIRef
from rdflib.namespace import PROV, RDF, XSD

from science_tool.graph.materialize import materialize_graph
from test_graph_materialize import _write_demo_project, _write_minimal_entity

PROJECT_NS = Namespace("http://example.org/project/")
SCI_NS = Namespace("http://example.org/science/vocab/")


def _materialize_provenance(project: Path) -> object:
    trig_path = materialize_graph(project)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    return dataset.graph(PROJECT_NS["graph/provenance"])


def test_user_origin_agent_attribution(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "hypotheses" / "origin-user.md",
        "hypothesis:origin-user",
        "hypothesis",
        "Origin user",
        extra_frontmatter=[
            "origins:",
            "  - {type: user, date: '2026-05-10'}",
            "added_by: user",
        ],
    )

    provenance = _materialize_provenance(project)

    entity_uri = PROJECT_NS["hypothesis/origin-user"]
    agent_uri = SCI_NS["agent/user"]

    origin_nodes = list(provenance.objects(entity_uri, SCI_NS.hasOrigin))
    assert len(origin_nodes) == 1
    origin_node = origin_nodes[0]

    assert (origin_node, RDF.type, SCI_NS.Origin) in provenance
    assert (origin_node, SCI_NS.originKind, Literal("user")) in provenance
    assert (origin_node, PROV.wasAttributedTo, agent_uri) in provenance
    assert (agent_uri, RDF.type, PROV.Agent) in provenance
    assert (entity_uri, SCI_NS.addedBy, Literal("user")) in provenance


def test_cite_origin_bib_node(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "hypotheses" / "origin-cite.md",
        "hypothesis:origin-cite",
        "hypothesis",
        "Origin cite",
        extra_frontmatter=[
            "origins:",
            "  - {type: literature, ref: 'cite:Smith2019'}",
        ],
    )

    provenance = _materialize_provenance(project)

    entity_uri = PROJECT_NS["hypothesis/origin-cite"]
    bib_uri = SCI_NS["cite/Smith2019"]

    origin_nodes = list(provenance.objects(entity_uri, SCI_NS.hasOrigin))
    assert len(origin_nodes) == 1
    origin_node = origin_nodes[0]

    assert (origin_node, PROV.wasDerivedFrom, bib_uri) in provenance
    assert (bib_uri, RDF.type, PROV.Entity) in provenance


def test_independent_and_date_emitted(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "hypotheses" / "origin-dated.md",
        "hypothesis:origin-dated",
        "hypothesis",
        "Origin dated",
        extra_frontmatter=[
            "origins:",
            "  - {type: user, date: '2019-03-01', independent: true}",
        ],
    )

    provenance = _materialize_provenance(project)

    entity_uri = PROJECT_NS["hypothesis/origin-dated"]
    origin_node = next(iter(provenance.objects(entity_uri, SCI_NS.hasOrigin)))

    assert (origin_node, PROV.generatedAtTime, Literal("2019-03-01", datatype=XSD.date)) in provenance
    assert (origin_node, SCI_NS.independentOrigination, Literal(True)) in provenance


def test_paper_origin_resolves_to_paper_entity(tmp_path: Path) -> None:
    project = tmp_path / "demo"
    _write_demo_project(project)
    _write_minimal_entity(
        project / "entities" / "papers" / "smith2019.md",
        "paper:smith2019",
        "paper",
        "Smith 2019",
    )
    _write_minimal_entity(
        project / "entities" / "hypotheses" / "origin-paper.md",
        "hypothesis:origin-paper",
        "hypothesis",
        "Origin paper",
        extra_frontmatter=[
            "origins:",
            "  - {type: literature, ref: 'paper:smith2019'}",
        ],
    )

    provenance = _materialize_provenance(project)

    entity_uri = PROJECT_NS["hypothesis/origin-paper"]
    paper_uri = PROJECT_NS["paper/smith2019"]
    origin_node = next(iter(provenance.objects(entity_uri, SCI_NS.hasOrigin)))

    assert (origin_node, PROV.wasDerivedFrom, paper_uri) in provenance
