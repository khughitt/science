from __future__ import annotations

from pathlib import Path

from science_tool.dag.retired_edges import build_retired_edges_report


def _write_manifest(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    (project / "science.yaml").write_text("profile: research\n", encoding="utf-8")


def test_retired_edges_report_counts_status_refs_and_claim_text(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "h1.dot").write_text("digraph h1 {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "h1.edges.yaml").write_text(
        """
dag: h1
source_dot: doc/figures/dags/h1.dot
edges:
  - id: 1
    source: a
    target: b
    edge_status: supported
    description: Curated description still needs migration.
    interpretation: Claim-bearing interpretation.
    data_support:
      - task: t001
        description: Completed task support.
    lit_support:
      - paper: Smith2020
        description: Literature support.
  - id: 2
    source: b
    target: c
    edge_status: eliminated
    eliminated_by:
      - task: t002
        description: Refutation support.
""".strip(),
        encoding="utf-8",
    )

    report = build_retired_edges_report(project)
    payload = report.to_json()

    assert payload["summary"] == {
        "files": 1,
        "edges": 2,
        "orphan_files": 0,
        "claim_text_edges": 1,
        "support_ref_edges": 2,
        "migration_worthy_edges": 2,
    }
    assert payload["files"][0]["dag"] == "h1"
    assert payload["files"][0]["edge_status_counts"] == {"eliminated": 1, "supported": 1}
    assert payload["files"][0]["edges"][0]["has_claim_text"] is True
    assert payload["files"][0]["edges"][0]["support_ref_count"] == 2


def test_retired_edges_report_honors_configured_dag_dir(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir(parents=True)
    (project / "science.yaml").write_text(
        "profile: research\ndag:\n  dag_dir: analysis/dags\n",
        encoding="utf-8",
    )
    dag_dir = project / "analysis/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "custom.dot").write_text("digraph custom {\n  a -> b;\n}\n", encoding="utf-8")
    (dag_dir / "custom.edges.yaml").write_text(
        """
dag: custom
edges:
  - id: 1
    source: a
    target: b
    edge_status: supported
    description: Custom DAG dir retired edge.
""".strip(),
        encoding="utf-8",
    )

    report = build_retired_edges_report(project)
    payload = report.to_json()

    assert payload["summary"]["files"] == 1
    assert payload["files"][0]["path"] == "analysis/dags/custom.edges.yaml"
    assert payload["files"][0]["dot_path"] == "analysis/dags/custom.dot"


def test_retired_edges_report_flags_orphan_yaml_without_dot(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    (dag_dir / "orphan.edges.yaml").write_text(
        """
dag: orphan
edges:
  - id: 1
    source: a
    target: b
    edge_status: tentative
    description: No DOT sibling exists.
""".strip(),
        encoding="utf-8",
    )

    report = build_retired_edges_report(project)
    payload = report.to_json()

    assert payload["summary"]["orphan_files"] == 1
    assert payload["files"][0]["orphan_dot"] is True
    assert payload["files"][0]["dot_path"] is None


def test_retired_edges_report_scopes_to_single_dag(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write_manifest(project)
    dag_dir = project / "doc/figures/dags"
    dag_dir.mkdir(parents=True)
    for slug in ("alpha", "beta"):
        (dag_dir / f"{slug}.dot").write_text(f"digraph {slug} {{\n  a -> b;\n}}\n", encoding="utf-8")
        (dag_dir / f"{slug}.edges.yaml").write_text(
            f"dag: {slug}\nedges:\n  - id: 1\n    source: a\n    target: b\n",
            encoding="utf-8",
        )

    report = build_retired_edges_report(project, dag="beta")

    assert [file["dag"] for file in report.to_json()["files"]] == ["beta"]
