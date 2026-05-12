from __future__ import annotations

from science_tool.dag.inventory import load_dag_inventory_records


def test_dag_edges_require_stable_declared_ids(tmp_path) -> None:
    project = tmp_path / "project"
    dag_path = project / "doc" / "figures" / "dags" / "h4-attractor-convergence.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - id: e001
    source: landscape
    target: attractor
    relation: converges_to
    interpretation: Landscape topology supports attractor convergence.
""".strip(),
        encoding="utf-8",
    )

    records = load_dag_inventory_records(project)

    assert [address.address for address in records.graph_addresses] == ["dag-edge:h4-attractor-convergence:e001"]
    assert records.finding_candidates[0].targets == ["dag-edge:h4-attractor-convergence:e001"]


def test_dag_edges_without_ids_emit_warning_instead_of_position_address(tmp_path) -> None:
    project = tmp_path / "project"
    dag_path = project / "doc" / "figures" / "dags" / "h4.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - source: a
    target: b
    relation: supports
""".strip(),
        encoding="utf-8",
    )

    records = load_dag_inventory_records(project)

    assert records.graph_addresses == []
    assert records.finding_candidates == []
    assert records.warnings[0].code == "missing-dag-edge-id"
    assert records.warnings[0].severity == "warning"


def test_dag_edges_with_whitespace_ids_emit_warning(tmp_path) -> None:
    project = tmp_path / "project"
    dag_path = project / "doc" / "figures" / "dags" / "h4.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - id: "   "
    source: a
    target: b
    relation: supports
""".strip(),
        encoding="utf-8",
    )

    records = load_dag_inventory_records(project)

    assert records.graph_addresses == []
    assert records.finding_candidates == []
    assert records.warnings[0].code == "missing-dag-edge-id"


def test_dag_finding_candidate_uses_first_non_blank_claim_text(tmp_path) -> None:
    project = tmp_path / "project"
    dag_path = project / "doc" / "figures" / "dags" / "h4.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - id: e001
    source: a
    target: b
    relation: supports
    interpretation: "   "
    finding: Finding text survives blank interpretation.
  - id: e002
    source: b
    target: c
    relation: supports
    interpretation:
      text: not a string
    claim: Claim text survives non-string interpretation.
""".strip(),
        encoding="utf-8",
    )

    records = load_dag_inventory_records(project)

    assert [candidate.title for candidate in records.finding_candidates] == [
        "Finding text survives blank interpretation.",
        "Claim text survives non-string interpretation.",
    ]
