"""Tests for patch-driven cito:discusses bundle membership (Task 0.2).

``WorkbenchFile.focal_hypothesis`` stamps every minted proposition's
``discusses`` list during ``compile_workbench``; ``_add_relations`` then emits
``cito:discusses`` to the KNOWLEDGE graph so ``bundle_members`` can find
compiled edge-propositions.
"""

from __future__ import annotations

from pathlib import Path

from rdflib import URIRef

from science_tool.dag.workbench import WorkbenchFile, WorkbenchRow, compile_workbench
from science_tool.graph.io import CITO_NS
from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import PROJECT_NS


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: compile-test\nknowledge_profiles:\n  local: local\n", encoding="utf-8"
    )


def _write(path: Path, rel: str, body: str) -> None:
    p = path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _minimal_hypothesis_file(root: Path, hyp_id: str) -> None:
    """Write a minimal hypothesis entity file for ``hyp_id`` (e.g. ``hypothesis:0001-…``)."""
    slug = hyp_id.split(":", 1)[1]
    _write(
        root,
        f"entities/hypotheses/{slug}.md",
        f"""---
id: {hyp_id}
kind: hypothesis
title: "Test hypothesis"
project: compile-test
ontology_terms: []
related: []
source_refs: []
created: 2026-01-01
updated: 2026-01-01
---
""",
    )


# ---------------------------------------------------------------------------
# Step 1 — compile propagates focal_hypothesis → proposition.discusses
# ---------------------------------------------------------------------------


def test_focal_hypothesis_populates_discusses(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        patch="h1-prognosis",
        focal_hypothesis="hypothesis:0001-epigenetic-commitment",
        rows=[
            WorkbenchRow(
                subject="gene:phf19",
                predicate="associates_with",
                object="outcome:os",
                patch="h1-prognosis",
                polarity="positive",
            )
        ],
    )
    result = compile_workbench(wb, project_root=tmp_path)
    assert result.propositions[0].discusses == ["hypothesis:0001-epigenetic-commitment"]


def test_no_focal_hypothesis_leaves_discusses_empty(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    wb = WorkbenchFile(
        patch="h1-prognosis",
        rows=[
            WorkbenchRow(
                subject="gene:phf19",
                predicate="associates_with",
                object="outcome:os",
                patch="h1-prognosis",
                polarity="positive",
            )
        ],
    )
    result = compile_workbench(wb, project_root=tmp_path)
    assert result.propositions[0].discusses == []


# ---------------------------------------------------------------------------
# Step 6 — end-to-end: materialize emits cito:discusses to KNOWLEDGE graph
# ---------------------------------------------------------------------------


def test_bundle_members_finds_compiled_edge_proposition(tmp_path: Path) -> None:
    """compile_workbench + materialize_graph → cito:discusses triple in knowledge graph.

    Uses the materialize_graph → Dataset.parse path (same as
    test_evidence_line_materialize.py) rather than hand-building triples, so we
    exercise the real _add_relations path.
    """
    from rdflib import Dataset

    _seed_project(tmp_path)

    # Write the focal hypothesis entity so the resolver can find it.
    _minimal_hypothesis_file(tmp_path, "hypothesis:0001-epigenetic-commitment")

    # Compile the workbench — this writes the proposition entity file.
    wb = WorkbenchFile(
        patch="h1-prognosis",
        focal_hypothesis="hypothesis:0001-epigenetic-commitment",
        rows=[
            WorkbenchRow(
                subject="gene:phf19",
                predicate="associates_with",
                object="outcome:os",
                patch="h1-prognosis",
                polarity="positive",
            )
        ],
    )
    result = compile_workbench(wb, project_root=tmp_path)
    prop = result.propositions[0]

    # Materialize the full graph from the written entity files.
    trig_path = materialize_graph(tmp_path, strict=False)
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    # Build the expected URIs using the same _entity_uri convention.
    prop_slug = prop.id.split(":", 1)[1]
    hyp_slug = "0001-epigenetic-commitment"
    prop_uri = URIRef(PROJECT_NS[f"proposition/{prop_slug}"])
    hyp_uri = URIRef(PROJECT_NS[f"hypothesis/{hyp_slug}"])

    assert (prop_uri, CITO_NS.discusses, hyp_uri) in knowledge, (
        f"Expected cito:discusses triple ({prop_uri!s}, cito:discusses, {hyp_uri!s}) "
        f"in knowledge graph after materialize"
    )
