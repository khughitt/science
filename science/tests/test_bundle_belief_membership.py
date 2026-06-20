from __future__ import annotations

from pathlib import Path

from rdflib import RDF, Dataset, Graph, Literal, URIRef
from science_model.reasoning import MembershipRole

from science_tool.graph.bundle_belief import bundle_members, core_members, membership_role
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS
from science_tool.graph.materialize import _entity_uri, materialize_graph


def _membership(g, prop, frame, role):
    m = PROJECT_NS[f"membership/{str(prop)}__{str(frame)}".replace(":", "_").replace("/", "_")]
    g.add((m, RDF.type, SCI_NS.BundleMembership))
    g.add((m, SCI_NS.membershipProposition, prop))
    g.add((m, SCI_NS.membershipFrame, frame))
    g.add((m, SCI_NS.membershipRole, Literal(role)))


def _bundle_graph():
    g = Graph()
    hyp = URIRef("urn:h1")
    core, rival, bg = URIRef("urn:p_core"), URIRef("urn:p_rival"), URIRef("urn:p_bg")
    g.add((hyp, RDF.type, SCI_NS.Hypothesis))
    for p in (core, rival, bg):
        g.add((p, RDF.type, SCI_NS.Proposition))
        g.add((p, CITO_NS.discusses, hyp))
    _membership(g, core, hyp, "core")
    _membership(g, rival, hyp, "rival")
    _membership(g, bg, hyp, "background")
    return g, hyp, core, rival, bg


def test_membership_role_reads_node():
    g, hyp, core, rival, bg = _bundle_graph()
    assert membership_role(g, core, hyp) == MembershipRole.CORE
    assert membership_role(g, rival, hyp) == MembershipRole.RIVAL
    assert membership_role(g, bg, hyp) == MembershipRole.BACKGROUND


def test_membership_role_defaults_core_when_absent():
    g = Graph()
    p, hyp = URIRef("urn:p"), URIRef("urn:h")
    assert membership_role(g, p, hyp) == MembershipRole.CORE


def test_core_members_excludes_rival_and_background():
    g, hyp, core, rival, bg = _bundle_graph()
    assert core_members(g, hyp) == [core]


def test_has_proposition_is_authoritatively_core():
    # A proposition that is BOTH a mechanism step (hasProposition) AND discussed as a
    # rival of the same frame must stay core — forward membership wins (spec §3.3).
    g = Graph()
    mech, step = URIRef("urn:m1"), URIRef("urn:p_step")
    g.add((mech, RDF.type, SCI_NS.Mechanism))
    g.add((step, RDF.type, SCI_NS.Proposition))
    g.add((mech, SCI_NS.hasProposition, step))
    g.add((step, CITO_NS.discusses, mech))
    _membership(g, step, mech, "rival")  # contradictory authoring; forward wins
    assert membership_role(g, step, mech) == MembershipRole.RIVAL
    assert core_members(g, mech) == [step]


def _write(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["---", *lines, "---", "", "Body.", ""]), encoding="utf-8")


def _mini_project(tmp_path: Path, p2_discusses: str) -> Path:
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    _write(
        tmp_path / "entities" / "hypotheses" / "h1.md",
        ['id: "hypothesis:h1"', 'type: "hypothesis"', 'title: "H1"', 'status: "proposed"',
         "ontology_terms: []", "source_refs: []", "related: []"],
    )
    for pid, disc in (("p1", '["hypothesis:h1"]'), ("p2", p2_discusses)):
        _write(
            tmp_path / "entities" / "propositions" / f"{pid}.md",
            [f'id: "proposition:{pid}"', 'type: "proposition"', f'title: "{pid}"',
             'status: "active"', "ontology_terms: []", "source_refs: []", "related: []",
             f"discusses: {disc}"],
        )
    return tmp_path


def _knowledge(tmp_path: Path):
    """materialize_graph returns the TriG Path; parse it and return the knowledge graph."""
    trig_path = materialize_graph(tmp_path, strict=False)
    ds = Dataset()
    ds.parse(str(trig_path), format="trig")
    return ds.graph(PROJECT_NS["graph/knowledge"])


def test_coverage_is_role_blind_but_conjunction_is_not(tmp_path: Path):
    k = _knowledge(_mini_project(tmp_path, '[{frame: "hypothesis:h1", role: "rival"}]'))
    hyp = _entity_uri("hypothesis:h1")
    p1, p2 = _entity_uri("proposition:p1"), _entity_uri("proposition:p2")
    # Coverage / linked claims (role-blind): both propositions still discuss h1.
    assert set(bundle_members(k, hyp)) == {p1, p2}
    # Conjunction membership (role-aware): the rival is excluded.
    assert core_members(k, hyp) == [p1]


def test_all_core_corpus_conjunction_membership_unchanged(tmp_path: Path):
    k = _knowledge(_mini_project(tmp_path, '["hypothesis:h1"]'))
    hyp = _entity_uri("hypothesis:h1")
    assert set(core_members(k, hyp)) == set(bundle_members(k, hyp))
