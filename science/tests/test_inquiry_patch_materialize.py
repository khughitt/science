from __future__ import annotations

from pathlib import Path

from rdflib import Dataset, URIRef
from rdflib.namespace import RDF

from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.graph.materialize import materialize_graph


def _write_entity(path: Path, frontmatter: list[str], body: str = "Body.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *frontmatter, "---", "", body, ""]), encoding="utf-8")


def test_graph_build_emits_inquiry_view_and_membership(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write_entity(
        tmp_path / "entities" / "hypotheses" / "h1.md",
        ['id: "hypothesis:h1"', 'kind: "hypothesis"', 'title: "H1"', 'status: "proposed"',
         "ontology_terms: []", "source_refs: []", "related: []"],
    )
    _write_entity(
        tmp_path / "entities" / "concepts" / "x.md",
        ['id: "concept:x"', 'kind: "concept"', 'title: "X"', 'status: "active"',
         "ontology_terms: []", "source_refs: []", "related: []"],
    )
    _write_entity(
        tmp_path / "entities" / "patches" / "i1.md",
        ['id: "patch-definition:i1"', 'kind: "patch-definition"', 'title: "Inquiry one"',
         'status: "active"', "ontology_terms: []", "source_refs: []", "related: []",
         'focal: "hypothesis:h1"',
         "scope_set:", '  - scope: "local"',
         "neighborhood_policy:", '  name: "local-closure-v1"', '  version: "local-closure-v1"', "  max_depth: 2",
         "patch_type: inquiry",
         "inquiry:", "  profile: investigation", "  status: sketch",
         "  boundary_roles:", "    - ref: \"concept:x\"", "      role: BoundaryIn"],
    )

    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")

    inquiry_uri = URIRef(PROJECT_NS["inquiry/i1"])
    assert (inquiry_uri, RDF.type, SCI_NS.Inquiry) in ds.graph(inquiry_uri)
    assert (URIRef(PROJECT_NS["concept/x"]), SCI_NS.boundaryRole, SCI_NS.BoundaryIn) in ds.graph(inquiry_uri)

    patch_uri = URIRef(PROJECT_NS["patch-definition/i1"])
    patch_graph = ds.graph(patch_uri)
    assert (patch_uri, RDF.type, SCI_NS.EpistemicPatch) in patch_graph
    members = {str(o) for o in patch_graph.objects(patch_uri, SCI_NS.hasMember)}
    assert str(URIRef(PROJECT_NS["concept/x"])) in members
