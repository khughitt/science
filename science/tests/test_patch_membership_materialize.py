from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.io import PROJECT_NS, SCI_NS, entity_uri_for_ref
from science_tool.graph.materialize import _entity_uri, materialize_graph


def _write_entity(path: Path, frontmatter: list[str], body: str = "Body.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *frontmatter, "---", "", body, ""]), encoding="utf-8")


def test_materialize_entity_uri_uses_shared_project_minter() -> None:
    assert _entity_uri("hypothesis:H1") == entity_uri_for_ref("hypothesis:H1")


def test_graph_build_emits_patch_membership_context(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write_entity(
        tmp_path / "entities" / "hypotheses" / "h1.md",
        [
            'id: "hypothesis:h1"',
            'type: "hypothesis"',
            'title: "H1"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )
    _write_entity(
        tmp_path / "entities" / "propositions" / "p1.md",
        [
            'id: "proposition:p1"',
            'type: "proposition"',
            'title: "P1"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'discusses: ["hypothesis:h1"]',
        ],
    )
    _write_entity(
        tmp_path / "entities" / "patches" / "local-demo.md",
        [
            'id: "patch-definition:local-demo"',
            'type: "patch-definition"',
            'title: "Local demo patch"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'focal: "hypothesis:h1"',
            "scope_set:",
            '  - scope: "local"',
            "neighborhood_policy:",
            '  name: "local-closure-v1"',
            '  version: "local-closure-v1"',
            "  max_depth: 2",
        ],
    )

    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")
    patch_uri = URIRef(PROJECT_NS["patch-definition/local-demo"])
    proposition_uri = URIRef(PROJECT_NS["proposition/p1"])
    patch_graph = ds.graph(patch_uri)

    assert (patch_uri, RDF.type, SCI_NS.EpistemicPatch) in patch_graph
    assert (patch_uri, SCI_NS.hasMember, proposition_uri) in patch_graph
    assert (proposition_uri, SCI_NS.inPatch, patch_uri) in patch_graph
    assert list(patch_graph.subjects(RDF.type, SCI_NS.PatchMembership))


def test_graph_build_excludes_provenance_source_nodes(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write_entity(
        tmp_path / "entities" / "hypotheses" / "h1.md",
        [
            'id: "hypothesis:h1"',
            'type: "hypothesis"',
            'title: "H1"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )
    _write_entity(
        tmp_path / "entities" / "propositions" / "p1.md",
        [
            'id: "proposition:p1"',
            'type: "proposition"',
            'title: "P1"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'discusses: ["hypothesis:h1"]',
        ],
    )
    _write_entity(
        tmp_path / "entities" / "patches" / "local-demo.md",
        [
            'id: "patch-definition:local-demo"',
            'type: "patch-definition"',
            'title: "Local demo patch"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            'focal: "hypothesis:h1"',
            "scope_set:",
            '  - scope: "local"',
            "neighborhood_policy:",
            '  name: "local-closure-v1"',
            '  version: "local-closure-v1"',
            "  max_depth: 2",
        ],
    )

    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")
    patch_uri = URIRef(PROJECT_NS["patch-definition/local-demo"])
    patch_graph = ds.graph(patch_uri)

    kinds = [
        str(obj)
        for node in patch_graph.subjects(RDF.type, SCI_NS.PatchMembership)
        for obj in patch_graph.objects(node, SCI_NS.memberKind)
    ]
    assert kinds  # at least one membership exists
    assert "unknown" not in kinds
    members = {
        str(obj)
        for node in patch_graph.subjects(RDF.type, SCI_NS.PatchMembership)
        for obj in patch_graph.objects(node, SCI_NS.member)
    }
    assert not any("/source/" in m for m in members)
