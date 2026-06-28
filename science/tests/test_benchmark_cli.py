from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _write_dataset(root: Path, slug: str, frontmatter: str) -> None:
    path = root / "entities" / "datasets" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\nbody\n", encoding="utf-8")


def _write_entity(root: Path, folder: str, slug: str, frontmatter: str, *, body: str) -> None:
    path = root / "entities" / folder / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}\n", encoding="utf-8")


def _invoke(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "list", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def _invoke_with_commons(tmp_path: Path, commons_root: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "list", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(commons_root)},
    )


def _invoke_gap_calibration(*args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "gap-calibration", *args],
        catch_exceptions=False,
        env={"SCIENCE_COMMONS_ROOT": "/tmp/science-no-commons"},
    )


def _invoke_gaps(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "gaps", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def _write_corrupt_commons_registry(root: Path, frontmatter_json: str = "{not-json") -> None:
    root.mkdir()
    conn = sqlite3.connect(root / "registry.sqlite")
    try:
        conn.executescript(
            """
            CREATE TABLE entities (
                canonical_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                slug TEXT NOT NULL,
                title TEXT,
                schema_profile TEXT NOT NULL,
                body_path TEXT NOT NULL,
                datapackage_path TEXT,
                mtime_ns INTEGER NOT NULL,
                frontmatter_json TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO entities "
            "(canonical_id, type, slug, title, schema_profile, body_path, datapackage_path, mtime_ns, frontmatter_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "dataset:corrupt",
                "dataset",
                "corrupt",
                "Corrupt",
                "dataset/v1",
                "datasets/corrupt/entity.md",
                None,
                0,
                frontmatter_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_benchmark_list_filters_domain_and_kind_json(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
benchmark:
  domains: [biology]
  modalities: [single-cell]
  signal_types: [transcriptomics]
  benchmark_kinds: [perturbation-response]
  source_datasets: [dataset:sciplex3-raw]
  related_beliefs:
    - hypothesis:h1 predicts response shifts.
  tasks:
    - id: predict-response
      task_type: prediction
      prediction_target: response
""",
    )
    _write_dataset(
        tmp_path,
        "imagenet",
        """
id: dataset:imagenet
type: dataset
title: ImageNet
benchmark:
  domains: [vision]
  benchmark_kinds: [classification]
  tasks:
    - id: classify-image
""",
    )

    result = _invoke(
        tmp_path,
        "--domain",
        "biology",
        "--kind",
        "perturbation-response",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [row["id"] for row in payload["rows"]] == ["dataset:sciplex3"]
    assert payload["summary"]["benchmark_kinds"]["perturbation-response"] == 1
    assert payload["summary"]["tasks"]["with_tasks"] == 1


def test_belief_ref_text_is_case_insensitive_exact_token_match(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "h1",
        """
id: dataset:h1
type: dataset
title: H1
benchmark:
  related_beliefs:
    - Supports Hypothesis:H1 under treatment.
  benchmark_kinds: [static-association]
""",
    )
    _write_dataset(
        tmp_path,
        "h10",
        """
id: dataset:h10
type: dataset
title: H10
benchmark:
  related_beliefs:
    - Supports hypothesis:h10 under treatment.
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke(tmp_path, "--belief-ref-text", "hypothesis:h1", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [row["id"] for row in payload["rows"]] == ["dataset:h1"]


def test_coverage_summary_json_omits_rows_and_counts_facets_only_reference(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "hca-spatial",
        """
id: dataset:hca-spatial
type: dataset
title: HCA spatial reference
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [transcriptomics]
  benchmark_kinds: [static-association]
  limitations:
    - Facets only; no task authored yet.
""",
    )

    result = _invoke(tmp_path, "--coverage-summary", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "rows" not in payload
    assert payload["summary"]["dataset_class"]["reference"] == 1
    assert payload["summary"]["modalities"]["spatial"] == 1
    assert payload["summary"]["tasks"]["facets_only"] == 1


def test_benchmark_list_counts_only_tasks_with_string_id(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "legacy-task-id",
        """
id: dataset:legacy-task-id
type: dataset
title: Legacy task id
benchmark:
  domains: [biology]
  benchmark_kinds: [perturbation-response]
  tasks:
    - task_id: old-id
      task_type: response-prediction
""",
    )

    result = _invoke(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["rows"][0]["task_count"] == 0
    assert payload["rows"][0]["task_ids"] == []
    assert payload["summary"]["tasks"]["facets_only"] == 1
    assert payload["summary"]["tasks"]["with_tasks"] == 0


def test_coverage_summary_json_omits_rows_when_no_rows_match(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "--domain", "no-such-domain", "--coverage-summary", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert "summary" in payload
    assert "commons_notice" in payload
    assert "rows" not in payload
    task_counts = payload["summary"].get("tasks")
    assert isinstance(task_counts, dict)
    assert not task_counts or all(count == 0 for count in task_counts.values())
    assert "No matching benchmark dataset entities." not in result.output


def test_benchmark_list_commons_missing_registry_json_degrades_to_local_rows(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "local",
        """
id: dataset:local
type: dataset
title: Local
benchmark:
  domains: [biology]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [row["id"] for row in payload["rows"]] == ["dataset:local"]
    assert payload["commons_notice"]
    assert "notice: commons benchmarks unavailable" in result.stderr


def test_benchmark_list_commons_corrupt_registry_json_degrades_to_local_rows(tmp_path: Path) -> None:
    commons_root = tmp_path / "commons"
    _write_corrupt_commons_registry(commons_root)
    _write_dataset(
        tmp_path,
        "local",
        """
id: dataset:local
type: dataset
title: Local
benchmark:
  domains: [biology]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke_with_commons(tmp_path, commons_root, "--commons", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [row["id"] for row in payload["rows"]] == ["dataset:local"]
    assert payload["commons_notice"]
    assert "notice: commons benchmarks unavailable" in result.stderr


def test_benchmark_list_commons_non_object_registry_json_degrades_to_local_rows(tmp_path: Path) -> None:
    commons_root = tmp_path / "commons"
    _write_corrupt_commons_registry(commons_root, '"bad"')
    _write_dataset(
        tmp_path,
        "local",
        """
id: dataset:local
type: dataset
title: Local
benchmark:
  domains: [biology]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke_with_commons(tmp_path, commons_root, "--commons", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert [row["id"] for row in payload["rows"]] == ["dataset:local"]
    assert payload["commons_notice"]
    assert "notice: commons benchmarks unavailable" in result.stderr


def test_coverage_summary_table_renders_when_no_rows_match(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "--domain", "biology", "--coverage-summary")

    assert result.exit_code == 0
    assert "facet" in result.output
    assert "No matching benchmark dataset entities." not in result.output


def test_benchmark_gap_calibration_json_summarizes_projects(tmp_path: Path) -> None:
    project_a = tmp_path / "project-a"
    project_b = tmp_path / "project-b"
    project_a.mkdir()
    project_b.mkdir()
    _write_entity(
        project_a,
        "hypotheses",
        "0001-drug",
        """
id: hypothesis:0001-drug
type: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )
    _write_dataset(
        project_a,
        "sciplex",
        """
id: dataset:sciplex
type: dataset
title: Sci-Plex
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )
    _write_entity(
        project_b,
        "hypotheses",
        "0002-temporal",
        """
id: hypothesis:0002-temporal
type: hypothesis
title: Temporal benchmark gap
""",
        body="Temporal dynamic measurements should be tested.",
    )

    result = _invoke_gap_calibration(
        "--project",
        f"a={project_a}",
        "--project",
        f"b={project_b}",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [row["label"] for row in payload["projects"]] == ["a", "b"]
    assert payload["aggregate"]["project_count"] == 2
    assert payload["aggregate"]["entity_specific_candidate_rows"] == 1


def test_benchmark_gap_calibration_rejects_duplicate_project_labels(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()

    result = _invoke_gap_calibration("--project", f"demo={project}", "--project", f"demo={project}")

    assert result.exit_code != 0
    assert "duplicate --project label: demo" in result.output


def test_benchmark_gap_calibration_table_renders_sections(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    _write_entity(
        project,
        "hypotheses",
        "0001-drug",
        """
id: hypothesis:0001-drug
type: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )

    result = _invoke_gap_calibration("--project", f"demo={project}")

    assert result.exit_code == 0
    assert "Benchmark Gap Calibration" in result.output
    assert "Aggregate Benchmark Gap Calibration" in result.output
    assert "top_fallback_reasons" in result.output
    assert "top_fallback_selection_reasons" in result.output
    assert "top_fallback_benchmark_shares" in result.output
    assert "fallback_concentration_warning" in result.output
    assert "demo" in result.output


def test_benchmark_gaps_cli_evidence_report_json(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-organoid",
        """
id: hypothesis:0001-organoid
type: hypothesis
title: Organoid therapy benchmark gap
""",
        body="Organoid therapy clone validation should be tested.",
    )

    result = _invoke_gaps(tmp_path, "--evidence-report", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["evidence_report"]["enabled"] is True
    assert "entities" in payload["evidence_report"]
    assert "hypothesis:0001-organoid" in payload["evidence_report"]["entities"]


def test_benchmark_gaps_cli_evidence_report_table(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-organoid",
        """
id: hypothesis:0002-organoid
type: hypothesis
title: Organoid therapy benchmark gap
""",
        body="Organoid therapy clone validation should be tested.",
    )
    _write_dataset(
        tmp_path,
        "generic",
        """
id: dataset:generic
type: dataset
title: Generic benchmark
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [clinical-outcome]
  benchmark_kinds: [static-association]
  tasks:
    - id: outcome
      prediction_target: outcome
      held_out_unit: patient
      metric: auroc
      baseline: clinical-only
      ground_truth:
        type: measured-outcome
        description: outcome
""",
    )

    result = _invoke_gaps(tmp_path, "--evidence-report")

    assert result.exit_code == 0
    assert "Gap Evidence" in result.output
    assert "fallback-only" in result.output
