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


def _write_corrupt_commons_registry(root: Path) -> None:
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
                "{not-json",
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


def test_coverage_summary_table_renders_when_no_rows_match(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "--domain", "biology", "--coverage-summary")

    assert result.exit_code == 0
    assert "facet" in result.output
    assert "No matching benchmark dataset entities." not in result.output
