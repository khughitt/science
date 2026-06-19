from __future__ import annotations

from pathlib import Path
from typing import Callable

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


# ---------------------------------------------------------------------------
# Relations-store (relations.yaml) routing tests
# ---------------------------------------------------------------------------


def _write_project_base(project: Path) -> Path:
    """Write a minimal project root with science.yaml and return the local sources dir."""
    project.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    local_sources = project / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True, exist_ok=True)
    return local_sources


def _write_subject_entity(project: Path, ref: str) -> None:
    """Write a minimal entity file for the given canonical ref (kind:slug form)."""
    kind, slug = ref.split(":", 1)
    if kind == "proposition":
        _write_entity(
            project / "entities" / "propositions" / f"{slug}.md",
            [
                f'id: "{ref}"',
                'type: "proposition"',
                f'title: "{slug}"',
                'status: "active"',
                "ontology_terms: []",
                "source_refs: []",
                "related: []",
                "discusses: []",
            ],
        )
    elif kind == "hypothesis":
        _hyp(project, slug)
    elif kind == "question":
        _write_entity(
            project / "entities" / "questions" / f"{slug}.md",
            [
                f'id: "{ref}"',
                'type: "question"',
                f'title: "{slug}"',
                'status: "open"',
                "ontology_terms: []",
                "source_refs: []",
                "related: []",
            ],
        )
    else:
        # Fallback: put non-file-backed kinds in entities.yaml via _write_source_entity
        raise ValueError(f"Unsupported kind for file-backed entity: {kind!r}")


def _write_source_entity(local_sources: Path, ref: str) -> None:
    """Append an entity entry to entities.yaml for source-backed kinds (e.g. paper)."""
    kind, slug = ref.split(":", 1)
    entities_yaml = local_sources / "entities.yaml"
    if not entities_yaml.exists():
        entities_yaml.write_text("entities:\n", encoding="utf-8")
    with entities_yaml.open("a", encoding="utf-8") as fh:
        fh.write(f"  - canonical_id: {ref}\n")
        fh.write(f"    kind: {kind}\n")
        fh.write(f"    title: {slug}\n")


# Kinds that live in entities.yaml rather than standalone entity files.
_SOURCE_YAML_KINDS = frozenset({"paper"})


@pytest.fixture
def make_project_with_relation(tmp_path: Path) -> Callable[..., object]:
    """Factory fixture: build a minimal project with one relations.yaml entry.

    Mirrors the fixture pattern from test_graph_materialize.py:884-913.
    Returns the parsed graph/knowledge named graph after materialize_graph runs.
    """

    def _factory(*, subject: str, predicate: str, object: str) -> object:
        project = tmp_path / "demo"
        local_sources = _write_project_base(project)

        # Write entity files for subject and object.
        for ref in (subject, object):
            kind = ref.split(":", 1)[0]
            if kind in _SOURCE_YAML_KINDS:
                _write_source_entity(local_sources, ref)
            else:
                _write_subject_entity(project, ref)

        # Write the single relation.
        (local_sources / "relations.yaml").write_text(
            "\n".join([
                "relations:",
                f"  - subject: {subject}",
                f"    predicate: {predicate}",
                f"    object: {object}",
                "",
            ]),
            encoding="utf-8",
        )

        trig_path = materialize_graph(project)
        ds = Dataset()
        ds.parse(str(trig_path), format="trig")
        return ds.graph(PROJECT_NS["graph/knowledge"])

    return _factory


def test_relations_store_prop_to_bundle_emits_core_node(make_project_with_relation):
    knowledge = make_project_with_relation(
        subject="proposition:0011-bar", predicate="cito:discusses", object="hypothesis:0001-foo",
    )
    from science_tool.graph.io import SCI_NS, membership_uri_for
    from rdflib import Literal
    node = membership_uri_for("proposition:0011-bar", "hypothesis:0001-foo")
    assert (node, SCI_NS.membershipRole, Literal("core")) in knowledge


def test_relations_store_paper_to_question_has_no_membership_node(make_project_with_relation):
    knowledge = make_project_with_relation(
        subject="paper:legatiuk2021", predicate="cito:discusses", object="question:q01-demo",
    )
    from science_tool.graph.io import SCI_NS
    # The plain structural link still materializes; no BundleMembership node exists.
    assert not list(knowledge.triples((None, SCI_NS.membershipFrame, None)))


def test_relations_store_paper_to_bundle_has_no_membership_node(make_project_with_relation):
    # Subject is NOT a proposition: object is a bundle but this is not a membership.
    knowledge = make_project_with_relation(
        subject="paper:legatiuk2021", predicate="cito:discusses", object="hypothesis:0001-foo",
    )
    from science_tool.graph.io import CITO_NS, SCI_NS, entity_uri_for_ref
    # The plain structural link still materializes...
    assert (entity_uri_for_ref("paper:legatiuk2021"), CITO_NS.discusses,
            entity_uri_for_ref("hypothesis:0001-foo")) in knowledge
    # ...but no membership node is minted for a non-proposition subject.
    assert not list(knowledge.triples((None, SCI_NS.membershipFrame, None)))
