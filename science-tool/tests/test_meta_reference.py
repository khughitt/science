"""Contract tests for the meta: ref prefix.

A `meta:<anything>` ref is intentional metadata: preserved in source files,
ignored by audit (no error if no matching entity), and never materialized
as a KG edge.
"""

from __future__ import annotations

from pathlib import Path

import click
import pytest

from science_tool.graph.sources import is_metadata_reference


class TestIsMetadataReference:
    def test_meta_prefix_recognized(self) -> None:
        assert is_metadata_reference("meta:phase3b") is True
        assert is_metadata_reference("meta:cycle1") is True
        assert is_metadata_reference("meta:") is True

    def test_other_prefixes_not_metadata(self) -> None:
        assert is_metadata_reference("topic:genomics") is False
        assert is_metadata_reference("hypothesis:h01") is False
        assert is_metadata_reference("task:t001") is False

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
            '---\nid: "hypothesis:h01-test"\ntype: "hypothesis"\n'
            'title: "Test"\nstatus: "proposed"\n'
            "related: [meta:phase3b, meta:cycle1]\n"
            "source_refs: []\ncreated: \"2026-04-13\"\n---\nBody.\n"
        )

        sources = load_project_sources(tmp_path)
        rows, has_failures = audit_project_sources(sources)

        assert has_failures is False, f"audit failed for meta: refs: {rows}"
        # No row should mention the meta refs as unresolved
        unresolved = [r for r in rows if r["status"] == "fail"]
        assert unresolved == []


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
            '---\nid: "hypothesis:h01-test"\ntype: "hypothesis"\n'
            'title: "Test"\nstatus: "proposed"\n'
            "related: [meta:phase3b]\n"
            "source_refs: []\ncreated: \"2026-04-13\"\n---\nBody.\n"
        )

        trig_path = materialize_graph(tmp_path)
        dataset = Dataset()
        dataset.parse(source=str(trig_path), format="trig")

        # No SKOS.related edge should originate from h01 with a meta target
        for graph in dataset.graphs():
            for s, p, o in graph.triples((None, SKOS.related, None)):
                assert "meta" not in str(o), f"meta ref leaked into KG: {s} {p} {o}"


class TestMetaRefsInAddEdge:
    def test_add_edge_rejects_meta_subject(self, tmp_path: Path) -> None:
        from science_tool.graph.store import add_edge, init_graph_file

        graph_path = tmp_path / "graph.trig"
        init_graph_file(graph_path)

        with pytest.raises(click.ClickException) as exc:
            add_edge(
                graph_path=graph_path,
                subject="meta:phase3b",
                predicate="skos:related",
                obj="hypothesis/h01",
                graph_layer="graph/knowledge",
            )
        assert "meta" in str(exc.value).lower()

    def test_add_edge_rejects_meta_object(self, tmp_path: Path) -> None:
        from science_tool.graph.store import add_edge, init_graph_file

        graph_path = tmp_path / "graph.trig"
        init_graph_file(graph_path)

        with pytest.raises(click.ClickException) as exc:
            add_edge(
                graph_path=graph_path,
                subject="hypothesis/h01",
                predicate="skos:related",
                obj="meta:phase3b",
                graph_layer="graph/knowledge",
            )
        assert "meta" in str(exc.value).lower()


class TestMetaRefsInAddQuestion:
    def test_add_question_skips_meta_in_related(self, tmp_path: Path) -> None:
        from rdflib import Dataset
        from rdflib.namespace import SKOS

        from science_tool.graph.store import (
            PROJECT_NS,
            add_hypothesis,
            add_question,
            init_graph_file,
        )

        graph_path = tmp_path / "graph.trig"
        init_graph_file(graph_path)
        # Add a hypothesis so the non-meta ref resolves
        add_hypothesis(
            graph_path=graph_path,
            hypothesis_id="H1",
            text="Test",
            source="paper:doi_10_1111_a",
        )

        add_question(
            graph_path=graph_path,
            question_id="Q1",
            text="Q",
            source="paper:doi_10_2222_b",
            related=["hypothesis/h1", "meta:phase3b"],
        )

        dataset = Dataset()
        dataset.parse(source=str(graph_path), format="trig")
        knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
        q_uri = PROJECT_NS["question/q1"]
        related_objs = [str(o) for o in knowledge.objects(q_uri, SKOS.related)]
        assert any("hypothesis/h1" in r for r in related_objs)
        assert not any("meta" in r for r in related_objs)
