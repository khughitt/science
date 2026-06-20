"""End-to-end smoke test for the evidence-line entity (Phase 0 exit criterion).

Covers:
1. ``science entity create evidence-line`` writes a valid template.
2. ``science graph build`` materialises cito:supports/disputes edge,
   prov:wasDerivedFrom source edge, and line-metadata predicates.
3. All four structural QA checks pass on a clean project.
4. Corrupting independence: shared-source without independence_group fires
   the expected ERROR (independence.ungrouped-collapse).
"""

from __future__ import annotations

from pathlib import Path

import yaml
from click.testing import CliRunner
from rdflib import Dataset, URIRef
from rdflib.namespace import PROV

from science_tool.cli import main
from science_tool.graph.io import CITO_NS, PROJECT_NS
from science_tool.graph.store import SCI_NS
from science_tool.validate import Severity, ValidateContext
from science_tool.validate.checks.evidence_lines import (
    check_evidence_lines_unstanced,
    check_evidence_strength_implausible,
    check_independence_suspect_circular,
    check_independence_ungrouped_collapse,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(root: Path, rel: str, body: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    return p


def _seed_project(root: Path) -> None:
    _write(root, "science.yaml", "name: e2e-test\nknowledge_profiles:\n  local: local\n")


def _load_dataset(project: Path) -> Dataset:
    """Run graph build via CLI and parse the output .trig."""
    runner = CliRunner()
    result = runner.invoke(main, ["graph", "build", "--project-root", str(project)])
    assert result.exit_code == 0, f"graph build failed:\n{result.output}"
    trig_path = project / "knowledge" / "graph.trig"
    assert trig_path.is_file(), "graph.trig not written"
    dataset = Dataset()
    dataset.parse(source=str(trig_path), format="trig")
    return dataset


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_proposition(root: Path, id_suffix: str = "p1") -> str:
    """Write a minimal proposition and return its id string."""
    entity_id = f"proposition:{id_suffix}"
    _write(
        root,
        f"entities/propositions/{id_suffix}.md",
        "\n".join([
            "---",
            f"id: {entity_id!r}",
            "kind: proposition",
            "title: 'Test Proposition'",
            "project: e2e-test",
            "ontology_terms: []",
            "related: []",
            "source_refs: []",
            "created: 2026-05-01",
            "updated: 2026-05-01",
            "---",
            "",
        ]),
    )
    return entity_id


def _write_paper(root: Path, id_suffix: str = "x") -> str:
    """Write a minimal paper and return its id string."""
    entity_id = f"paper:{id_suffix}"
    _write(
        root,
        f"entities/papers/{id_suffix}.md",
        "\n".join([
            "---",
            f"id: {entity_id!r}",
            "kind: paper",
            "title: 'Test Paper'",
            "project: e2e-test",
            "ontology_terms: []",
            "related: []",
            "source_refs: []",
            "created: 2026-05-01",
            "updated: 2026-05-01",
            "---",
            "",
        ]),
    )
    return entity_id


def _write_evidence_line(root: Path, *, id_suffix: str = "e1", **extra: object) -> Path:
    """Write an evidence-line with a valid full payload."""
    fields: dict[str, object] = {
        "id": f"evidence-line:{id_suffix}",
        "kind": "evidence-line",
        "title": "Evidence line e2e",
        "project": "e2e-test",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "created": "2026-05-01",
        "updated": "2026-05-01",
        "stance": "supports",
        "target": "proposition:p1",
        "source": "paper:x",
        "strength": "moderate",
        "independence": "independent",
        "independence_group": "grp-a",
        "evidence_role": "direct_test",
        "shared_dataset": "ds:gse100",
    }
    fields.update(extra)
    path = root / f"entities/evidence-lines/{id_suffix}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\n" + yaml.safe_dump(fields, sort_keys=False) + "---\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Part A: entity create evidence-line
# ---------------------------------------------------------------------------

def test_entity_create_evidence_line_writes_template(tmp_path: Path) -> None:
    """``science entity create evidence-line`` should write a valid template file."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path):
        root = Path.cwd()
        _seed_project(root)
        # Provide an explicit id because no sibling exists yet for auto-numbering.
        result = runner.invoke(
            main,
            ["entity", "create", "evidence-line", "My first evidence line",
             "--id", "evidence-line:0001-first"],
        )
        assert result.exit_code == 0, f"entity create failed:\n{result.output}"
        assert "evidence-line:0001-first" in result.output

        dest = root / "entities" / "evidence-lines" / "0001-first.md"
        assert dest.is_file(), f"Expected file at {dest}"
        text = dest.read_text(encoding="utf-8")
        # Template should seed stance, target, independence.
        assert "stance:" in text
        assert "target:" in text
        assert "independence:" in text
        # Template should seed direct_test evidence_role.
        assert "direct_test" in text


# ---------------------------------------------------------------------------
# Part A: graph build — cito edge, provenance, line metadata
# ---------------------------------------------------------------------------

def test_graph_build_evidence_line_supports_cito_edge(tmp_path: Path) -> None:
    """stance: supports → cito:supports edge in knowledge graph after graph build."""
    _seed_project(tmp_path)
    _write_proposition(tmp_path)
    _write_paper(tmp_path)
    _write_evidence_line(tmp_path, stance="supports")

    dataset = _load_dataset(tmp_path)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e1"])
    target_uri = URIRef(PROJECT_NS["proposition/p1"])

    assert (line_uri, CITO_NS.supports, target_uri) in knowledge, (
        "Expected cito:supports in knowledge graph"
    )
    assert (line_uri, CITO_NS.disputes, target_uri) not in knowledge


def test_graph_build_evidence_line_disputes_cito_edge(tmp_path: Path) -> None:
    """stance: disputes → cito:disputes edge in knowledge graph after graph build."""
    _seed_project(tmp_path)
    _write_proposition(tmp_path)
    _write_paper(tmp_path)
    _write_evidence_line(tmp_path, stance="disputes", dispute_scope="generalization")

    dataset = _load_dataset(tmp_path)
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e1"])
    target_uri = URIRef(PROJECT_NS["proposition/p1"])

    assert (line_uri, CITO_NS.disputes, target_uri) in knowledge, (
        "Expected cito:disputes in knowledge graph"
    )
    assert (line_uri, CITO_NS.supports, target_uri) not in knowledge


def test_graph_build_evidence_line_prov_derived_from(tmp_path: Path) -> None:
    """source: paper:x → prov:wasDerivedFrom paper:x in provenance graph."""
    _seed_project(tmp_path)
    _write_proposition(tmp_path)
    _write_paper(tmp_path)
    _write_evidence_line(tmp_path)

    dataset = _load_dataset(tmp_path)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    line_uri = URIRef(PROJECT_NS["evidence-line/e1"])
    paper_uri = URIRef(PROJECT_NS["paper/x"])

    assert (line_uri, PROV.wasDerivedFrom, paper_uri) in provenance, (
        "Expected prov:wasDerivedFrom edge from evidence-line:e1 to paper:x"
    )


def test_graph_build_evidence_line_metadata_predicates(tmp_path: Path) -> None:
    """Line metadata (strength, independence, evidence_role, shared_dataset) are emitted."""
    _seed_project(tmp_path)
    _write_proposition(tmp_path)
    _write_paper(tmp_path)
    _write_evidence_line(
        tmp_path,
        strength="moderate",
        independence="independent",
        independence_group="grp-a",
        evidence_role="direct_test",
        shared_dataset="ds:gse100",
    )

    dataset = _load_dataset(tmp_path)
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    line_uri = URIRef(PROJECT_NS["evidence-line/e1"])

    strengths = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.evidenceStrength, None))}
    assert "moderate" in strengths, f"sci:evidenceStrength missing, got {strengths}"

    indeps = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.evidenceIndependence, None))}
    assert "independent" in indeps, f"sci:evidenceIndependence missing, got {indeps}"

    roles = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.evidenceRole, None))}
    assert "direct_test" in roles, f"sci:evidenceRole missing, got {roles}"

    datasets = {str(o) for _, _, o in provenance.triples((line_uri, SCI_NS.sharedDataset, None))}
    assert "ds:gse100" in datasets, f"sci:sharedDataset missing, got {datasets}"


# ---------------------------------------------------------------------------
# Part A: QA checks — clean project + corruption
# ---------------------------------------------------------------------------

def test_qa_checks_all_pass_on_clean_project(tmp_path: Path) -> None:
    """All four evidence-line QA checks emit no results for a well-formed project."""
    _seed_project(tmp_path)
    _write_proposition(tmp_path)
    _write_paper(tmp_path)
    _write_evidence_line(tmp_path)

    ctx = _ctx(tmp_path)
    assert list(check_evidence_lines_unstanced(ctx)) == [], "evidence.unstanced fired unexpectedly"
    assert list(check_independence_ungrouped_collapse(ctx)) == [], "independence.ungrouped-collapse fired unexpectedly"
    assert list(check_independence_suspect_circular(ctx)) == [], "independence.suspect-circular fired unexpectedly"
    assert list(check_evidence_strength_implausible(ctx)) == [], "evidence.strength-implausible fired unexpectedly"


def test_qa_check_fires_on_shared_source_without_group(tmp_path: Path) -> None:
    """Corrupted evidence-line (shared-source, no group) triggers independence.ungrouped-collapse ERROR."""
    _seed_project(tmp_path)
    _write_proposition(tmp_path)
    _write_paper(tmp_path)
    # independence: shared-source but no independence_group → ERROR
    _write_evidence_line(tmp_path, independence="shared-source", independence_group=None)

    ctx = _ctx(tmp_path)
    results = list(check_independence_ungrouped_collapse(ctx))
    assert len(results) == 1, f"Expected 1 result, got {len(results)}: {results}"
    assert results[0].severity == Severity.ERROR
    assert results[0].rule == "independence.ungrouped-collapse"
