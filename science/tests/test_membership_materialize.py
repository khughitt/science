from __future__ import annotations

from pathlib import Path

import pytest
from rdflib import Dataset, Literal
from rdflib.namespace import RDF

from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.materialize import _entity_uri, materialize_graph


def _write_entity(path: Path, frontmatter: list[str], body: str = "Body.") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *frontmatter, "---", "", body, ""]), encoding="utf-8")


def _hyp(path: Path, hid: str) -> None:
    _write_entity(
        path / "entities" / "hypotheses" / f"{hid}.md",
        [
            f'id: "hypothesis:{hid}"',
            'type: "hypothesis"',
            f'title: "{hid}"',
            'status: "proposed"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
        ],
    )


def _prop(path: Path, pid: str, discusses_yaml: str) -> None:
    _write_entity(
        path / "entities" / "propositions" / f"{pid}.md",
        [
            f'id: "proposition:{pid}"',
            'type: "proposition"',
            f'title: "{pid}"',
            'status: "active"',
            "ontology_terms: []",
            "source_refs: []",
            "related: []",
            f"discusses: {discusses_yaml}",
        ],
    )


def _knowledge(tmp_path: Path):
    """Build the graph and return its knowledge named-graph.

    materialize_graph returns the TriG Path (materialize.py:429); the knowledge
    triples live in the PROJECT_NS["graph/knowledge"] named graph (materialize.py:162).
    """
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")
    return ds.graph(PROJECT_NS["graph/knowledge"])


def test_plain_discusses_triple_always_emitted_for_object_form(tmp_path: Path):
    _hyp(tmp_path, "h1")
    _prop(tmp_path, "p1", '[{frame: "hypothesis:h1", role: "rival"}]')
    knowledge = _knowledge(tmp_path)
    prop, hyp = _entity_uri("proposition:p1"), _entity_uri("hypothesis:h1")
    # The plain triple is preserved verbatim (annotate, never replace).
    assert (prop, CITO_NS.discusses, hyp) in knowledge


def test_membership_node_carries_role(tmp_path: Path):
    _hyp(tmp_path, "h1")
    _prop(tmp_path, "p1", '[{frame: "hypothesis:h1", role: "rival"}]')
    knowledge = _knowledge(tmp_path)
    prop, hyp = _entity_uri("proposition:p1"), _entity_uri("hypothesis:h1")
    members = list(knowledge.subjects(SCI_NS.membershipProposition, prop))
    assert len(members) == 1
    m = members[0]
    assert (m, RDF.type, SCI_NS.BundleMembership) in knowledge
    assert (m, SCI_NS.membershipFrame, hyp) in knowledge
    assert (m, SCI_NS.membershipRole, Literal("rival")) in knowledge


def test_bare_string_emits_core_membership(tmp_path: Path):
    _hyp(tmp_path, "h1")
    _prop(tmp_path, "p1", '["hypothesis:h1"]')
    knowledge = _knowledge(tmp_path)
    prop = _entity_uri("proposition:p1")
    m = next(iter(knowledge.subjects(SCI_NS.membershipProposition, prop)))
    assert (m, SCI_NS.membershipRole, Literal("core")) in knowledge


def test_unresolved_frame_is_loud_fail(tmp_path: Path):
    # No hypothesis h99 exists; the frame must not be silently dropped.
    _prop(tmp_path, "p1", '[{frame: "hypothesis:h99", role: "rival"}]')
    with pytest.raises(Exception) as exc:  # ValueError surfaced through the compile
        _knowledge(tmp_path)
    assert "h99" in str(exc.value) or "resolve" in str(exc.value).lower()


def test_non_bundle_frame_is_loud_fail(tmp_path: Path):
    # discusses must point at a bundle (hypothesis/mechanism), never another proposition.
    _prop(tmp_path, "p1", '["proposition:p2"]')
    _prop(tmp_path, "p2", "[]")
    with pytest.raises(Exception) as exc:
        _knowledge(tmp_path)
    assert "bundle" in str(exc.value).lower()


def test_metadata_ref_in_discusses_is_skipped_not_membership(tmp_path: Path):
    # meta:/spec: are the global annotation escape hatch — skipped, never rejected,
    # and never producing a membership node.
    _prop(tmp_path, "p1", '["meta:see-also"]')
    knowledge = _knowledge(tmp_path)
    prop = _entity_uri("proposition:p1")
    assert list(knowledge.subjects(SCI_NS.membershipProposition, prop)) == []
