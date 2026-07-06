"""Contract tests for the meta: ref prefix.

A `meta:<anything>` ref is intentional metadata: preserved in source files,
ignored by audit (no error if no matching entity), and never materialized
as a KG edge.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import build_entity_graph

from science_tool.graph.sources import is_metadata_reference


class TestIsMetadataReference:
    def test_meta_prefix_recognized(self) -> None:
        assert is_metadata_reference("meta:phase3b") is True
        assert is_metadata_reference("meta:cycle1") is True
        assert is_metadata_reference("meta:") is True

    def test_spec_prefix_recognized(self) -> None:
        # spec: pointers reference design documents, not entities — annotation-only.
        assert is_metadata_reference("spec:2026-04-12-catalog-health-design") is True
        assert is_metadata_reference("spec:scope-boundaries") is True
        assert is_metadata_reference("spec:") is True

    def test_other_prefixes_not_metadata(self) -> None:
        assert is_metadata_reference("topic:genomics") is False
        assert is_metadata_reference("hypothesis:h01") is False
        assert is_metadata_reference("task:t001") is False
        # A prefix that merely starts with "spec" (no colon boundary) must not match.
        assert is_metadata_reference("specialization:x") is False

    def test_no_prefix_not_metadata(self) -> None:
        assert is_metadata_reference("genomics") is False
        assert is_metadata_reference("") is False

    def test_meta_in_middle_not_metadata(self) -> None:
        # The prefix check must be at the start
        assert is_metadata_reference("topic:meta:foo") is False


class TestMetaRefsInAudit:
    def test_audit_accepts_meta_ref_with_no_entity(self, tmp_path: Path) -> None:
        """A meta: ref should not produce an unresolved-reference audit failure."""
        from science_tool.graph.migrate import audit_project_sources
        from science_tool.graph.sources import load_project_sources

        # Minimal project: one hypothesis with a meta: ref in related
        (tmp_path / "science.yaml").write_text("name: test\n")
        spec_dir = tmp_path / "specs" / "hypotheses"
        spec_dir.mkdir(parents=True)
        (spec_dir / "h01.md").write_text(
            '---\nid: "hypothesis:h01-test"\nkind: "hypothesis"\n'
            'title: "Test"\nstatus: "proposed"\n'
            "related: [meta:phase3b, meta:cycle1]\n"
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        sources = load_project_sources(tmp_path)
        rows, has_failures = audit_project_sources(sources)

        assert has_failures is False, f"audit failed for meta: refs: {rows}"
        # No row should mention the meta refs as unresolved
        unresolved = [r for r in rows if r["status"] == "fail"]
        assert unresolved == []

    def test_load_project_sources_preserves_article_prefix_in_relations(
        self, tmp_path: Path
    ) -> None:
        """Structured relation YAML should not silently rewrite article refs."""
        from science_tool.graph.sources import load_project_sources

        (tmp_path / "science.yaml").write_text("name: test\n")
        paper_dir = tmp_path / "entities" / "papers"
        paper_dir.mkdir(parents=True)
        (paper_dir / "Smith2024.md").write_text(
            "\n".join(
                [
                    "---",
                    'id: "paper:Smith2024"',
                    'kind: "paper"',
                    'title: "Smith 2024"',
                    "aliases:",
                    "  - Smith2024",
                    "---",
                    "",
                    "Paper summary.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        sources_dir = tmp_path / "knowledge" / "sources" / "local"
        sources_dir.mkdir(parents=True)
        (sources_dir / "relations.yaml").write_text(
            "\n".join(
                [
                    "relations:",
                    "- subject: article:Smith2024",
                    "  predicate: skos:related",
                    "  object: article:Jones2023",
                    "  source_path: knowledge/sources/local/relations.yaml",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        sources = load_project_sources(tmp_path)
        entity = next(item for item in sources.entities if item.title == "Smith 2024")
        relation = sources.relations[0]

        assert entity.canonical_id == "paper:Smith2024"
        assert relation.subject == "article:Smith2024"
        assert relation.object == "article:Jones2023"


class TestMetaRefsInMaterialize:
    def test_meta_ref_produces_no_skos_related_triple(self, tmp_path: Path) -> None:
        """A meta: ref in related should not be materialized as a SKOS.related edge."""
        from rdflib import Dataset
        from rdflib.namespace import SKOS

        from science_tool.graph.materialize import materialize_graph

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec_dir = tmp_path / "specs" / "hypotheses"
        spec_dir.mkdir(parents=True)
        (spec_dir / "h01.md").write_text(
            '---\nid: "hypothesis:h01-test"\nkind: "hypothesis"\n'
            'title: "Test"\nstatus: "proposed"\n'
            "related: [meta:phase3b]\n"
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        trig_path = materialize_graph(tmp_path)
        dataset = Dataset()
        dataset.parse(source=str(trig_path), format="trig")

        # No SKOS.related edge should originate from h01 with a meta target
        for graph in dataset.graphs():
            for s, p, o in graph.triples((None, SKOS.related, None)):
                assert "meta" not in str(o), f"meta ref leaked into KG: {s} {p} {o}"


class TestMetaRefsInSourceRelations:
    def test_source_relation_rejects_meta_subject(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="meta:phase3b"):
            build_entity_graph(
                tmp_path,
                entities=[
                    {
                        "kind": "hypothesis",
                        "id": "h01",
                        "frontmatter": {"title": "H1", "status": "proposed", "source_refs": []},
                        "body": "H1.",
                    }
                ],
                relations=[
                    {
                        "subject": "meta:phase3b",
                        "predicate": "skos:related",
                        "object": "hypothesis:h01",
                        "graph_layer": "graph/knowledge",
                    }
                ],
            )

    def test_source_relation_rejects_meta_object(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="meta:phase3b"):
            build_entity_graph(
                tmp_path,
                entities=[
                    {
                        "kind": "hypothesis",
                        "id": "h01",
                        "frontmatter": {"title": "H1", "status": "proposed", "source_refs": []},
                        "body": "H1.",
                    }
                ],
                relations=[
                    {
                        "subject": "hypothesis:h01",
                        "predicate": "skos:related",
                        "object": "meta:phase3b",
                        "graph_layer": "graph/knowledge",
                    }
                ],
            )


class TestMetaRefsInQuestionSource:
    def test_question_source_skips_meta_in_related(self, tmp_path: Path) -> None:
        from rdflib import Dataset
        from rdflib.namespace import SKOS

        graph_path = build_entity_graph(
            tmp_path,
            entities=[
                {
                    "kind": "hypothesis",
                    "id": "h1",
                    "frontmatter": {"title": "H1", "status": "proposed", "source_refs": []},
                    "body": "H1.",
                },
                {
                    "kind": "question",
                    "id": "q1",
                    "frontmatter": {
                        "title": "Q",
                        "status": "open",
                        "related": ["hypothesis:h1", "meta:phase3b"],
                        "source_refs": [],
                    },
                    "body": "Q.",
                },
            ],
        )

        dataset = Dataset()
        dataset.parse(source=str(graph_path), format="trig")
        related_objs = [str(o) for graph in dataset.graphs() for o in graph.objects(None, SKOS.related)]
        assert any("hypothesis/h1" in r for r in related_objs)
        assert not any("meta" in r for r in related_objs)


class TestMetaRefsInBlockedByAndSourceRefs:
    def test_meta_ref_in_blocked_by_not_materialized(self, tmp_path: Path) -> None:
        """meta: refs in blocked_by must not produce sci:blockedBy edges."""
        from rdflib import Dataset

        from science_tool.graph.materialize import materialize_graph
        from science_tool.graph.store import SCI_NS

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec_dir = tmp_path / "specs" / "hypotheses"
        spec_dir.mkdir(parents=True)
        (spec_dir / "h01.md").write_text(
            '---\nid: "hypothesis:h01-test"\nkind: "hypothesis"\n'
            'title: "Test"\nstatus: "proposed"\nrelated: []\n'
            "blocked_by: [meta:phase3b]\n"
            'source_refs: []\ncreated: "2026-04-13"\n---\nBody.\n'
        )

        trig_path = materialize_graph(tmp_path)
        dataset = Dataset()
        dataset.parse(source=str(trig_path), format="trig")

        for graph in dataset.graphs():
            for s, p, o in graph.triples((None, SCI_NS.blockedBy, None)):
                assert "meta" not in str(o), f"meta blocked_by leaked into KG: {s} {p} {o}"

    def test_meta_ref_in_source_refs_not_materialized(self, tmp_path: Path) -> None:
        """meta: refs in source_refs must not produce prov:wasDerivedFrom edges."""
        from rdflib import Dataset
        from rdflib.namespace import PROV

        from science_tool.graph.materialize import materialize_graph

        (tmp_path / "science.yaml").write_text("name: test\n")
        spec_dir = tmp_path / "specs" / "hypotheses"
        spec_dir.mkdir(parents=True)
        (spec_dir / "h01.md").write_text(
            '---\nid: "hypothesis:h01-test"\nkind: "hypothesis"\n'
            'title: "Test"\nstatus: "proposed"\nrelated: []\n'
            "source_refs: [meta:phase3b]\n"
            'created: "2026-04-13"\n---\nBody.\n'
        )

        trig_path = materialize_graph(tmp_path)
        dataset = Dataset()
        dataset.parse(source=str(trig_path), format="trig")

        for graph in dataset.graphs():
            for s, p, o in graph.triples((None, PROV.wasDerivedFrom, None)):
                assert "meta" not in str(o), f"meta source_ref leaked into KG: {s} {p} {o}"


class TestMetaRefsInInquiryFlowEdge:
    """A meta: ref in an inquiry flow edge must never reach the KG.

    The retired ``add_inquiry_edge`` mutator rejected meta refs interactively.
    In the source-built pipeline an inquiry flow-edge endpoint is a required
    member ref, so an authored ``meta:`` endpoint fails the build early in the
    patch-membership deriver (``_resolve_required`` raises) rather than
    materializing a spurious edge — a strictly stronger invariant.
    """

    @staticmethod
    def _author_inquiry(tmp_path: Path, *, subject: str, object: str) -> None:
        (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")

        def _write(rel: str, frontmatter: list[str]) -> None:
            path = tmp_path / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(["---", *frontmatter, "---", "", "Body.", ""]), encoding="utf-8")

        _write(
            "entities/hypotheses/h1.md",
            ['id: "hypothesis:h1"', 'kind: "hypothesis"', 'title: "H1"', 'status: "proposed"',
             "ontology_terms: []", "source_refs: []", "related: []"],
        )
        _write(
            "entities/concepts/x.md",
            ['id: "concept:x"', 'kind: "concept"', 'title: "X"', 'status: "active"',
             "ontology_terms: []", "source_refs: []", "related: []"],
        )
        _write(
            "entities/patches/i1.md",
            ['id: "patch-definition:i1"', 'kind: "patch-definition"', 'title: "Inquiry one"',
             'status: "active"', "ontology_terms: []", "source_refs: []", "related: []",
             'focal: "hypothesis:h1"',
             "scope_set:", '  - scope: "local"',
             "neighborhood_policy:", '  name: "local-closure-v1"', '  version: "local-closure-v1"', "  max_depth: 2",
             "patch_type: inquiry",
             "inquiry:", "  profile: investigation", "  status: sketch",
             "  flow_edges:",
             f'    - subject: "{subject}"', "      predicate: feedsInto", f'      object: "{object}"'],
        )

    def test_meta_subject_fails_build(self, tmp_path: Path) -> None:
        from science_tool.graph.materialize import materialize_graph
        from science_tool.graph.patch_membership import PatchMembershipError

        self._author_inquiry(tmp_path, subject="meta:phase3b", object="concept:x")
        with pytest.raises(PatchMembershipError, match="meta:phase3b"):
            materialize_graph(tmp_path)

    def test_meta_object_fails_build(self, tmp_path: Path) -> None:
        from science_tool.graph.materialize import materialize_graph
        from science_tool.graph.patch_membership import PatchMembershipError

        self._author_inquiry(tmp_path, subject="concept:x", object="meta:phase3b")
        with pytest.raises(PatchMembershipError, match="meta:phase3b"):
            materialize_graph(tmp_path)
