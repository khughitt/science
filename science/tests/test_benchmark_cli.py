from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest
import yaml
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


def _invoke_opportunities(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "opportunities", *args],
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


def _invoke_hint_candidates(tmp_path: Path, *args: str):
    result = CliRunner().invoke(
        science_cli,
        ["benchmark", "hint-candidates", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )
    if result.exit_code == 0 and "--format" in args and args[args.index("--format") + 1] == "json":
        result.output_bytes = result.stdout_bytes
    return result


def _invoke_tests(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "tests", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def _invoke_test_triage(tmp_path: Path, *args: str):
    result = CliRunner().invoke(
        science_cli,
        ["benchmark", "test-triage", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )
    if result.exit_code == 0 and "--format" in args and args[args.index("--format") + 1] == "json":
        result.output_bytes = result.stdout_bytes
    return result


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
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: dataset
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
kind: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )
    _write_dataset(
        project_a,
        "sciplex",
        """
id: dataset:sciplex
kind: dataset
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
kind: hypothesis
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
kind: hypothesis
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
kind: hypothesis
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
kind: hypothesis
title: Organoid therapy benchmark gap
""",
        body="Organoid therapy clone validation should be tested.",
    )
    _write_dataset(
        tmp_path,
        "generic",
        """
id: dataset:generic
kind: dataset
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


def test_benchmark_gaps_cli_table_collapses_generic_fallback_candidates(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-generic",
        """
id: hypothesis:0004-generic
kind: hypothesis
title: Generic fallback benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    for slug in ("generic-a", "generic-b", "generic-c"):
        _write_dataset(
            tmp_path,
            slug,
            f"""
id: dataset:{slug}
kind: dataset
title: {slug}
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
        )

    result = _invoke_gaps(tmp_path)

    assert result.exit_code == 0
    assert "fallback-only" in result.output
    assert "generic fallback: 3 candidates" in result.output
    assert "Collapsed 3 generic fallback candidates" in result.output
    assert "dataset:generic-a [" not in result.output
    assert "+2 fallback" not in result.output


def test_benchmark_gaps_cli_json_keeps_raw_generic_fallback_candidates(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-generic",
        """
id: hypothesis:0004-generic
kind: hypothesis
title: Generic fallback benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    for slug in ("generic-a", "generic-b"):
        _write_dataset(
            tmp_path,
            slug,
            f"""
id: dataset:{slug}
kind: dataset
title: {slug}
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
        )

    result = _invoke_gaps(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    candidates = payload["benchmark_gaps"][0]["candidate_benchmarks"]
    assert len(candidates) == 2
    assert {candidate["benchmark_id"] for candidate in candidates} == {"dataset:generic-a", "dataset:generic-b"}
    assert payload["fallback_diagnostics"]["generic_fallback_candidate_rows"] == 2


def test_format_gap_candidates_renders_mixed_fallback_without_raising() -> None:
    from science_tool.cli import _format_gap_candidates_for_table

    row = {
        "candidate_mode": "fallback-only",
        "candidate_benchmarks": [
            {
                "benchmark_id": "dataset:specific-a",
                "candidate_score": 2.0,
                "context_fit": "adjacent-fit",
                "context_fit_warnings": [],
                "reason_notes": ["fallback:task-ready"],
            },
            {
                "benchmark_id": "dataset:generic-a",
                "candidate_score": 1.0,
                "context_fit": "generic-fallback",
                "context_fit_warnings": [],
                "reason_notes": ["fallback:baseline-quality"],
            },
        ],
    }

    rendered = _format_gap_candidates_for_table(row)

    assert "dataset:specific-a" in rendered
    assert "generic fallback: 1 candidates (top: dataset:generic-a)" in rendered


def test_format_gap_candidates_rejects_entity_specific_and_fallback_mix() -> None:
    from science_tool.cli import _format_gap_candidates_for_table

    row = {
        "candidate_mode": "entity-specific",
        "candidate_benchmarks": [
            {
                "benchmark_id": "dataset:specific-a",
                "candidate_score": 2.0,
                "context_fit": "direct-fit",
                "context_fit_warnings": [],
                "reason_notes": ["missing-facet:proteomics"],
            },
            {
                "benchmark_id": "dataset:generic-a",
                "candidate_score": 1.0,
                "context_fit": "generic-fallback",
                "context_fit_warnings": [],
                "reason_notes": ["fallback:baseline-quality"],
            },
        ],
    }

    with pytest.raises(ValueError, match="mixes entity-specific and fallback candidates"):
        _format_gap_candidates_for_table(row)


def test_benchmark_gaps_cli_filters_context_fit_json(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0600-direct",
        """
id: hypothesis:0600-direct
kind: hypothesis
title: Direct Sci-Plex gap
""",
        body="Sci-plex drug compound screen should be benchmarked.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0601-generic",
        """
id: hypothesis:0601-generic
kind: hypothesis
title: Generic fallback gap
""",
        body="No specific benchmark facet appears here.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    result = _invoke_gaps(tmp_path, "--context-fit", "direct-fit", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert [row["entity_id"] for row in payload["benchmark_gaps"]] == ["hypothesis:0600-direct"]
    candidates = payload["benchmark_gaps"][0]["candidate_benchmarks"]
    assert [candidate["context_fit"] for candidate in candidates] == ["direct-fit"]


def test_benchmark_gaps_cli_rejects_unknown_context_fit(tmp_path: Path) -> None:
    result = _invoke_gaps(tmp_path, "--context-fit", "near-fit")

    assert result.exit_code != 0
    assert "Invalid value for '--context-fit'" in result.output


def test_benchmark_gaps_cli_table_shows_candidate_context_fit(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0602-context-table",
        """
id: hypothesis:0602-context-table
kind: hypothesis
title: Context table gap
""",
        body="Sci-plex drug compound screen should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression response
      support:
        state: supported
""",
    )

    result = _invoke_gaps(tmp_path)

    assert result.exit_code == 0
    assert "dataset:sciplex3 [direct-fit]" in result.output


def test_benchmark_hint_candidates_cli_json_and_commons_notice(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0070-alpha",
        """
id: hypothesis:0070-alpha
kind: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    assert "notice: commons benchmarks unavailable" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["commons_notice"] is not None
    assert payload["review_file"] is None
    assert payload["summary"]["term_bucket_cap"] == 10
    assert payload["summary"]["truncation_notice"] == "evidence categories are capped at top 10 terms per bucket"
    assert {row["term"] for row in payload["hint_candidates"]} >= {"cytogenetic", "lesion", "mutation"}
    assert all(row["suggested_facets"] == [] for row in payload["hint_candidates"])
    assert all(row["suggested_action"] != "needs-new-facet-vocab" for row in payload["hint_candidates"])


def test_benchmark_hint_candidates_cli_table_shows_only_domain_candidates(tmp_path: Path) -> None:
    project_root = tmp_path / "cbioportal-project"
    project_root.mkdir()
    _write_entity(
        project_root,
        "hypotheses",
        "0071-alpha",
        """
id: hypothesis:0071-alpha
kind: hypothesis
title: Cytogenetic project model
""",
        body="Cytogenetic lesion evidence should be benchmarked against project catalog models.",
    )

    result = _invoke_hint_candidates(project_root)

    assert result.exit_code == 0
    assert "Benchmark Hint Candidates" in result.output
    assert "cytogenetic" in result.output
    assert "review-for-hint" in result.output
    assert "catalog" not in result.output
    assert "cbioportal" not in result.output


def test_benchmark_hint_candidates_cli_include_existing_json(tmp_path: Path) -> None:
    result = _invoke_hint_candidates(tmp_path, "--include-existing", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    existing = [row for row in payload["hint_candidates"] if row["category"] == "existing-hint"]
    assert existing
    by_term = {row["term"]: row for row in existing}
    assert by_term["drug"]["count"] is None
    assert by_term["drug"]["current_hint"] == "perturbation"
    assert by_term["drug"]["example_entities"] == []
    assert by_term["drug"]["reason_notes"] == ["already-mapped-term"]


def test_benchmark_hint_candidates_cli_output_requires_write_flag(tmp_path: Path) -> None:
    result = _invoke_hint_candidates(tmp_path, "--output", "docs/audits/benchmark-hint-candidates/custom.yaml")

    assert result.exit_code != 0
    assert "--output requires --write-review-file" in result.output


def test_benchmark_hint_candidates_cli_writes_default_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0072-alpha",
        """
id: hypothesis:0072-alpha
kind: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(tmp_path, "--write-review-file", "--format", "json")

    assert result.exit_code == 0
    review_path = tmp_path / "doc" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    assert review_path.is_file()
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    written = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    assert written["project"] == tmp_path.name
    assert written["generated_at"] == "2026-06-30"
    assert written["source_command"].startswith("science benchmark hint-candidates")
    assert written["summary"]["term_bucket_cap"] == 10
    assert written["candidates"][0]["decision"] == "pending"
    assert written["candidates"][0]["reviewer_notes"] == ""
    assert written["candidates"][0]["suggested_facets"] == []


def test_benchmark_hint_candidates_cli_default_review_file_always_uses_canonical_doc_dir(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    (tmp_path / "doc").mkdir()
    (tmp_path / "docs").mkdir()
    _write_entity(
        tmp_path,
        "hypotheses",
        "0074-alpha",
        """
id: hypothesis:0074-alpha
kind: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(tmp_path, "--write-review-file", "--format", "json")

    assert result.exit_code == 0, result.output
    review_path = tmp_path / "doc" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    wrong_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    assert review_path.exists()
    assert not wrong_path.exists()
    assert f"wrote benchmark hint candidate review file: {review_path}" in result.stderr


def test_benchmark_hint_candidates_cli_default_review_file_creates_doc_for_docs_only_project(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    (tmp_path / "docs").mkdir()
    _write_entity(
        tmp_path,
        "hypotheses",
        "0075-beta",
        """
id: hypothesis:0075-beta
kind: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(tmp_path, "--write-review-file", "--format", "json")

    assert result.exit_code == 0, result.output
    review_path = tmp_path / "doc" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    wrong_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / f"2026-06-30-{tmp_path.name}.yaml"
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    assert review_path.exists()
    assert not wrong_path.exists()
    assert f"wrote benchmark hint candidate review file: {review_path}" in result.stderr


def test_benchmark_hint_candidates_cli_writes_custom_project_relative_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0073-alpha",
        """
id: hypothesis:0073-alpha
kind: hypothesis
title: Cytogenetic benchmark gap
""",
        body="Cytogenetic lesion mutation evidence should be reviewed.",
    )

    result = _invoke_hint_candidates(
        tmp_path,
        "--write-review-file",
        "--output",
        "docs/audits/benchmark-hint-candidates/custom.yaml",
    )

    assert result.exit_code == 0
    review_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / "custom.yaml"
    assert review_path.is_file()
    assert f"wrote benchmark hint candidate review file: {review_path}" in result.stderr


def test_benchmark_hint_candidates_cli_refuses_existing_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    output_path = tmp_path / "docs" / "audits" / "benchmark-hint-candidates" / "custom.yaml"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("existing: true\n", encoding="utf-8")

    result = _invoke_hint_candidates(
        tmp_path,
        "--write-review-file",
        "--output",
        "docs/audits/benchmark-hint-candidates/custom.yaml",
    )

    assert result.exit_code != 0
    assert "review file already exists" in result.output
    assert output_path.read_text(encoding="utf-8") == "existing: true\n"


def test_benchmark_hint_candidates_cli_rejects_relative_output_outside_project_root(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))

    result = _invoke_hint_candidates(tmp_path, "--write-review-file", "--output", "../outside.yaml")

    assert result.exit_code != 0
    assert "--output must stay under project root" in result.output
    assert not (tmp_path.parent / "outside.yaml").exists()


def test_benchmark_hint_candidates_cli_rejects_absolute_output_outside_project_root(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_hint_candidates_today", lambda: date(2026, 6, 30))
    outside_path = tmp_path.parent / "outside-absolute.yaml"

    result = _invoke_hint_candidates(tmp_path, "--write-review-file", "--output", str(outside_path))

    assert result.exit_code != 0
    assert "--output must stay under project root" in result.output
    assert not outside_path.exists()


def test_benchmark_hint_candidates_cli_table_empty_state(tmp_path: Path) -> None:
    result = _invoke_hint_candidates(tmp_path)

    assert result.exit_code == 0
    assert "No benchmark hint candidates." in result.output


def test_benchmark_tests_cli_json_output(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-perturbation",
        """
id: hypothesis:0001-perturbation
kind: hypothesis
title: Perturbation response hypothesis
""",
        body="Sci-plex drug perturbation should shift response states.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    result = _invoke_tests(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["concrete_rows"] == 1
    row = payload["benchmark_tests"][0]
    assert row["test_plan_state"] == "concrete"
    assert row["priority_source"] == "opportunity-relative"
    assert row["context_fit"] == "direct-fit"
    assert "specific-context:sci-plex" in row["context_fit_reasons"]
    assert "task-support:supported" in row["context_fit_reasons"]
    assert row["context_fit_warnings"] == []
    assert payload["summary"]["context_fit_counts"]["direct-fit"] == 1


def test_benchmark_tests_cli_projects_task_support_fields(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0301-progression",
        """
id: hypothesis:0301-progression
kind: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked in multiple myeloma.",
    )
    _write_dataset(
        tmp_path,
        "mmrf-commpass",
        """
id: dataset:mmrf-commpass
kind: dataset
title: MMRF CoMMpass
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression-free survival endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-02'
        evidence:
          - recipe/reports/validation.json#task_support.progression-risk
        notes:
          - Open metadata lacks progression endpoint coverage.
""",
    )

    result = _invoke_tests(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    row = payload["benchmark_tests"][0]
    assert row["benchmark_id"] == "dataset:mmrf-commpass"
    assert row["task_id"] == "dataset:mmrf-commpass#progression-risk"
    assert row["readiness_label"] == "metadata-only"
    assert row["task_support_state"] == "blocked"
    assert row["task_support_reason"] == "open-metadata-missing-progression-endpoint"
    assert row["task_support_checked_at"] == "2026-07-02"
    assert row["task_support_evidence"] == ["recipe/reports/validation.json#task_support.progression-risk"]
    assert row["task_support_notes"] == ["Open metadata lacks progression endpoint coverage."]
    assert "task-support:blocked:open-metadata-missing-progression-endpoint" in row["reason_notes"]
    assert "task-support:blocked:open-metadata-missing-progression-endpoint" not in row["needs"]


def test_benchmark_tests_cli_rejects_invalid_task_support_state(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0302-progression",
        """
id: hypothesis:0302-progression
kind: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "bad-support",
        """
id: dataset:bad-support
kind: dataset
title: Bad Support
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blockd
        reason: open-metadata-missing-progression-endpoint
""",
    )

    result = _invoke_tests(tmp_path, "--format", "json")

    assert result.exit_code != 0
    assert "benchmark task support state" in result.output
    assert "blockd" in result.output


def test_benchmark_tests_cli_rejects_scalar_task_support_evidence(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0304-progression",
        """
id: hypothesis:0304-progression
kind: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "bad-support-evidence",
        """
id: dataset:bad-support-evidence
kind: dataset
title: Bad Support Evidence
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        evidence: recipe/reports/validation.json#x
""",
    )

    result = _invoke_tests(tmp_path, "--format", "json")

    assert result.exit_code != 0
    assert "benchmark task support evidence" in result.output
    assert "dataset:bad-support-evidence#progression-risk" in result.output


def test_benchmark_tests_cli_rejects_unknown_task_support_key(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0305-progression",
        """
id: hypothesis:0305-progression
kind: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "bad-support-field",
        """
id: dataset:bad-support-field
kind: dataset
title: Bad Support Field
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: supported
        reviewer: analyst
""",
    )

    result = _invoke_tests(tmp_path, "--format", "json")

    assert result.exit_code != 0
    assert "benchmark task support field" in result.output
    assert "reviewer" in result.output
    assert "dataset:bad-support-field#progression-risk" in result.output


def test_benchmark_opportunities_cli_rejects_invalid_task_support_cleanly(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0303-progression",
        """
id: hypothesis:0303-progression
kind: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "bad-support-opportunities",
        """
id: dataset:bad-support-opportunities
kind: dataset
title: Bad Support Opportunities
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      prediction_target: progression or relapse
      support:
        state: blockd
        reason: open-metadata-missing-progression-endpoint
""",
    )

    result = _invoke_opportunities(tmp_path, "--format", "json")

    assert result.exit_code != 0
    assert "benchmark task support state" in result.output
    assert "blockd" in result.output
    assert "Traceback" not in result.output


def test_benchmark_tests_cli_table_output(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial",
        """
id: hypothesis:0002-spatial
kind: hypothesis
title: Spatial hypothesis
""",
        body="Microenvironment region needs spatial validation.",
    )
    _write_dataset(
        tmp_path,
        "hca-spatial",
        """
id: dataset:hca-spatial
kind: dataset
title: HCA Spatial
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke_tests(tmp_path)

    assert result.exit_code == 0
    assert "Benchmark Tests" in result.output
    assert "hypothesis:0002-spatial" in result.output
    assert "draft-needed" in result.output
    assert "source" in result.output
    assert "readiness" in result.output
    assert "opportunity-relative" in result.output
    assert "metadata-only" in result.output
    assert "dataset:hca-spatial" in result.output
    assert "prediction-target" in result.output


def test_benchmark_tests_cli_filters_context_fit_or_values(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0506-context-cli",
        """
id: hypothesis:0506-context-cli
kind: hypothesis
title: Context CLI
""",
        body="Sci-plex perturbation and temporal benchmark evidence should be considered.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    result = _invoke_tests(
        tmp_path,
        "--context-fit",
        "direct-fit",
        "--context-fit",
        "method-fit",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["filters"]["context_fit"] == ["direct-fit", "method-fit"]
    assert {row["context_fit"] for row in payload["benchmark_tests"]} <= {"direct-fit", "method-fit"}


def test_benchmark_tests_cli_rejects_unknown_context_fit(tmp_path: Path) -> None:
    result = _invoke_tests(tmp_path, "--context-fit", "near-fit")

    assert result.exit_code != 0
    assert "Invalid value for '--context-fit'" in result.output


def test_benchmark_tests_cli_table_shows_context_fit(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0507-context-table",
        """
id: hypothesis:0507-context-table
kind: hypothesis
title: Context table
""",
        body="Sci-plex perturbation should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    result = _invoke_tests(tmp_path)

    assert result.exit_code == 0
    assert "fit" in result.output
    assert "direct-fit" in result.output


def test_benchmark_tests_cli_filters_and_empty_state(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0003-drug",
        """
id: hypothesis:0003-drug
kind: hypothesis
title: Drug hypothesis
""",
        body="Drug compound knockout screen should be tested.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )

    result = _invoke_tests(tmp_path, "--state", "concrete")

    assert result.exit_code == 0
    assert "No benchmark test plans." in result.output


def test_benchmark_tests_cli_source_and_readiness_filters(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-triage",
        """
id: hypothesis:0004-triage
kind: hypothesis
title: Triage hypothesis
""",
        body="Drug perturbation should shift response states. Microenvironment region needs benchmark support.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )
    _write_dataset(
        tmp_path,
        "hca-spatial",
        """
id: dataset:hca-spatial
kind: dataset
title: HCA Spatial
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    source_result = _invoke_tests(tmp_path, "--source", "opportunity-relative", "--format", "json")
    readiness_result = _invoke_tests(tmp_path, "--runnable-only", "--format", "json")

    source_payload = json.loads(source_result.output)
    readiness_payload = json.loads(readiness_result.output)
    assert source_result.exit_code == 0
    assert [row["benchmark_id"] for row in source_payload["benchmark_tests"]] == ["dataset:sciplex3"]
    assert {row["priority_source"] for row in source_payload["benchmark_tests"]} == {"opportunity-relative"}
    assert readiness_result.exit_code == 0
    assert [row["benchmark_id"] for row in readiness_payload["benchmark_tests"]] == ["dataset:sciplex3"]
    assert {row["readiness_label"] for row in readiness_payload["benchmark_tests"]} == {"runnable"}


def test_benchmark_tests_cli_exclude_fallback(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0005-spatial",
        """
id: hypothesis:0005-spatial
kind: hypothesis
title: Spatial fallback hypothesis
""",
        body="Microenvironment region needs benchmark support.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )

    result = _invoke_tests(tmp_path, "--exclude-fallback", "--format", "json")

    payload = json.loads(result.output)
    assert result.exit_code == 0
    assert payload["benchmark_tests"] == []
    assert payload["summary"]["test_plan_rows"] == 0


def test_benchmark_tests_cli_invalid_entity_and_facet_errors(tmp_path: Path) -> None:
    entity_result = _invoke_tests(tmp_path, "--entity", "hypothesis:missing")
    assert entity_result.exit_code != 0
    assert "Entity not found" in entity_result.output

    facet_result = _invoke_tests(tmp_path, "--facet", "not-a-facet")
    assert facet_result.exit_code != 0
    assert "unknown benchmark gap facet" in facet_result.output


def test_benchmark_tests_cli_rejects_conflicting_readiness_filters(tmp_path: Path) -> None:
    result = _invoke_tests(tmp_path, "--readiness", "metadata-only", "--runnable-only")

    assert result.exit_code != 0
    assert "--runnable-only conflicts with --readiness metadata-only" in result.output


def test_benchmark_tests_cli_commons_unavailable_degrades_to_local_rows(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-local",
        """
id: hypothesis:0004-local
kind: hypothesis
title: Local hypothesis
""",
        body="Drug response should be tested.",
    )
    _write_dataset(
        tmp_path,
        "local-benchmark",
        """
id: dataset:local-benchmark
kind: dataset
title: Local Benchmark
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )

    result = _invoke_tests(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    assert "notice: commons benchmarks unavailable" in result.stderr
    payload = json.loads(result.stdout)
    assert payload["commons_notice"] is not None
    assert payload["benchmark_tests"]


def test_benchmark_test_triage_cli_json_output(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0200-perturbation",
        """
id: hypothesis:0200-perturbation
kind: hypothesis
title: Perturbation response hypothesis
""",
        body="Drug perturbation should shift response states.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: compound-response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )

    result = _invoke_test_triage(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["review_file"] is None
    assert payload["summary"]["bucket_counts"]["run-now"] == 1
    assert payload["buckets"]["run-now"][0]["benchmark_id"] == "dataset:sciplex3"
    assert payload["buckets"]["run-now"][0]["dataset_class"] == "deposit"
    assert payload["buckets"]["run-now"][0]["review"] == {
        "decision": "",
        "owner": "",
        "next_action": "",
        "notes": "",
    }
    assert payload["filters"] == {}


def test_benchmark_test_triage_routes_blocked_task_support_to_blocked_bucket(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0303-progression",
        """
id: hypothesis:0303-progression
kind: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked with bulk RNA-seq time-series survival data.",
    )
    _write_dataset(
        tmp_path,
        "blocked-progress",
        """
id: dataset:blocked-progress
kind: dataset
title: Blocked Progression
dataset_class: deposit
local_path: data/blocked-progress
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-02'
""",
    )

    result = _invoke_test_triage(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    row = payload["buckets"]["blocked-or-reference"][0]
    assert row["benchmark_id"] == "dataset:blocked-progress"
    assert row["readiness_label"] == "runnable"
    assert row["task_support_state"] == "blocked"
    assert "task-support:blocked:open-metadata-missing-progression-endpoint" in row["reason_notes"]
    assert payload["summary"]["bucket_counts"]["run-now"] == 0


def test_benchmark_test_triage_candidate_support_does_not_enter_run_now(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0304-survival",
        """
id: hypothesis:0304-survival
kind: hypothesis
title: Survival benchmark hypothesis
""",
        body="Overall survival should be benchmarked with bulk RNA-seq time-series expression data.",
    )
    _write_dataset(
        tmp_path,
        "candidate-survival",
        """
id: dataset:candidate-survival
kind: dataset
title: Candidate Survival
dataset_class: deposit
local_path: data/candidate-survival
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: overall-survival
      task_type: survival prediction
      prediction_target: overall survival
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: overall survival endpoint
      support:
        state: candidate
        reason: open-metadata-survival-endpoint-present
        checked_at: '2026-07-02'
""",
    )

    result = _invoke_test_triage(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["bucket_counts"]["run-now"] == 0
    row = payload["buckets"]["metadata-needed"][0]
    assert row["benchmark_id"] == "dataset:candidate-survival"
    assert row["readiness_label"] == "runnable"
    assert row["test_plan_state"] == "concrete"
    assert row["task_support_state"] == "candidate"
    assert "task-support:candidate:open-metadata-survival-endpoint-present" in row["reason_notes"]


def test_benchmark_test_triage_cli_filters_context_fit(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0508-context-triage-cli",
        """
id: hypothesis:0508-context-triage-cli
kind: hypothesis
title: Context triage CLI
""",
        body="Sci-plex perturbation should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  source_datasets: [sci-plex]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
      support:
        state: supported
""",
    )

    result = _invoke_test_triage(tmp_path, "--context-fit", "direct-fit", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["filters"]["context_fit"] == ["direct-fit"]
    assert payload["summary"]["context_fit_counts"]["direct-fit"] == 1


def test_benchmark_test_triage_cli_rejects_unknown_context_fit(tmp_path: Path) -> None:
    result = _invoke_test_triage(tmp_path, "--context-fit", "near-fit")

    assert result.exit_code != 0
    assert "Invalid value for '--context-fit'" in result.output


def _write_blocked_fallback_triage_fixture(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0305-homeostatic-recovery",
        """
id: hypothesis:0305-homeostatic-recovery
kind: hypothesis
title: Homeostatic recovery hypothesis
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "blocked-fallback",
        """
id: dataset:blocked-fallback
kind: dataset
title: Blocked Fallback
dataset_class: deposit
local_path: data/blocked-fallback
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
""",
    )


def test_benchmark_test_triage_cli_suppresses_blocked_fallback_by_default(tmp_path: Path) -> None:
    _write_blocked_fallback_triage_fixture(tmp_path)

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["fallback_rows"] == 1
    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == 0
    assert payload["summary"]["suppressed_blocked_support_fallback_rows"] == 1
    assert payload["fallback_diagnostics"]["suppressed_blocked_support"] == {
        "rows": 1,
        "top_benchmarks": [{"benchmark_id": "dataset:blocked-fallback", "count": 1}],
    }
    assert "include_blocked_fallback" not in payload["filters"]


def test_benchmark_test_triage_cli_include_blocked_fallback_restores_json_rows(tmp_path: Path) -> None:
    _write_blocked_fallback_triage_fixture(tmp_path)

    result = _invoke_test_triage(
        tmp_path,
        "--source",
        "gap-fallback",
        "--include-blocked-fallback",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["bucket_counts"]["fallback-diagnostic"] == 1
    assert payload["summary"]["suppressed_blocked_support_fallback_rows"] == 0
    assert "suppressed_blocked_support" not in payload["fallback_diagnostics"]
    assert payload["filters"]["include_blocked_fallback"] is True
    assert payload["buckets"]["fallback-diagnostic"][0]["task_support_state"] == "blocked"


def test_benchmark_test_triage_cli_table_output_shows_suppression_diagnostic(tmp_path: Path) -> None:
    _write_blocked_fallback_triage_fixture(tmp_path)

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback")

    assert result.exit_code == 0
    assert "Suppressed 1 fallback rows for blocked task support" in result.output
    assert "dataset:blocked-fallback:1" in result.output
    assert "Benchmark Test Triage: fallback-diagnostic" not in result.output
    assert "No benchmark test triage rows." not in result.output


def test_benchmark_test_triage_cli_table_output_shows_fallback_rollups(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0306-generic",
        """
id: hypothesis:0306-generic
kind: hypothesis
title: Generic hypothesis
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "visible-fallback",
        """
id: dataset:visible-fallback
kind: dataset
title: Visible Fallback
dataset_class: deposit
local_path: data/visible-fallback
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
      support:
        state: supported
        checked_at: '2026-07-03'
""",
    )

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback")

    assert result.exit_code == 0
    assert "Benchmark Test Triage: fallback-diagnostic" not in result.output
    assert "Benchmark Test Triage: generic fallback summary" in result.output
    assert "1 generic fallback rows hidden from detailed table" in result.output
    assert "dataset:visible-fallback:1" in result.output
    assert "ready (protein-lineage-association)" not in result.output
    assert "hypothesis:0306-generic" not in result.output
    assert "runnable:1" not in result.output
    assert "deposit:1" not in result.output
    assert "none:1" not in result.output


def test_benchmark_test_triage_cli_table_output_shows_hidden_fallback_rollup_count(
    tmp_path: Path,
    monkeypatch,
) -> None:
    rollups = [
        {
            "benchmark_id": f"dataset:fallback-{index:02d}",
            "benchmark_title": f"Fallback {index:02d}",
            "display_group": "specific-fallback",
            "task_id": f"dataset:fallback-{index:02d}#ready",
            "task_type": "",
            "count": 1,
            "task_support_state": "supported",
            "task_support_reason": "",
            "readiness_label": "runnable",
            "dataset_class": "deposit",
            "test_plan_state": "concrete",
            "top_facets": [{"facet": "proteomics", "count": 1}],
            "example_entities": [f"hypothesis:{index:02d}"],
            "reason_notes": ["fallback:high-baseline"],
        }
        for index in range(12)
    ]

    def fake_benchmark_test_triage_report(*args, **kwargs):
        return {
            "summary": {
                "bucket_counts": {
                    "run-now": 0,
                    "stage-next": 0,
                    "metadata-needed": 0,
                    "blocked-or-reference": 0,
                    "fallback-diagnostic": 12,
                }
            },
            "buckets": {
                "run-now": [],
                "stage-next": [],
                "metadata-needed": [],
                "blocked-or-reference": [],
                "fallback-diagnostic": [],
            },
            "fallback_diagnostics": {"rollups": rollups},
            "commons_notice": "",
            "filters": {},
            "review_file": None,
        }

    monkeypatch.setattr(
        "science_tool.benchmark_opportunities.benchmark_test_triage_report",
        fake_benchmark_test_triage_report,
    )

    result = CliRunner().invoke(
        science_cli,
        ["benchmark", "test-triage"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )

    assert result.exit_code == 0
    assert "12 fallback rows grouped into 12 rollups (showing 10, 2 hidden)" in result.output
    assert "dataset:fallback-00" in result.output
    assert "dataset:fallback-09" in result.output
    assert "dataset:fallback-10" not in result.output


def test_benchmark_test_triage_cli_errors_when_fallback_rollups_missing(tmp_path: Path, monkeypatch) -> None:
    def fake_benchmark_test_triage_report(*args, **kwargs):
        return {
            "summary": {
                "bucket_counts": {
                    "run-now": 0,
                    "stage-next": 0,
                    "metadata-needed": 0,
                    "blocked-or-reference": 0,
                    "fallback-diagnostic": 1,
                }
            },
            "buckets": {
                "run-now": [],
                "stage-next": [],
                "metadata-needed": [],
                "blocked-or-reference": [],
                "fallback-diagnostic": [],
            },
            "fallback_diagnostics": {"rollups": [], "terminal_visible_rollup_count": 1},
            "commons_notice": "",
            "filters": {},
            "review_file": None,
        }

    monkeypatch.setattr(
        "science_tool.benchmark_opportunities.benchmark_test_triage_report",
        fake_benchmark_test_triage_report,
    )

    result = CliRunner().invoke(
        science_cli,
        ["benchmark", "test-triage"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )

    assert result.exit_code != 0
    assert "fallback diagnostics rollups missing for fallback rows" in result.output


def test_benchmark_test_triage_cli_errors_on_unknown_fallback_display_group(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def fake_benchmark_test_triage_report(*args, **kwargs):
        return {
            "summary": {
                "bucket_counts": {
                    "run-now": 0,
                    "stage-next": 0,
                    "metadata-needed": 0,
                    "blocked-or-reference": 0,
                    "fallback-diagnostic": 1,
                }
            },
            "buckets": {
                "run-now": [],
                "stage-next": [],
                "metadata-needed": [],
                "blocked-or-reference": [],
                "fallback-diagnostic": [],
            },
            "fallback_diagnostics": {
                "rollups": [
                    {
                        "benchmark_id": "dataset:fallback",
                        "benchmark_title": "Fallback",
                        "display_group": "generic-ish",
                        "task_id": "dataset:fallback#ready",
                        "task_type": "",
                        "count": 1,
                        "task_support_state": "supported",
                        "task_support_reason": "",
                        "readiness_label": "runnable",
                        "dataset_class": "deposit",
                        "test_plan_state": "concrete",
                        "top_facets": [],
                        "example_entities": ["hypothesis:one"],
                        "reason_notes": ["fallback:baseline-quality"],
                    }
                ],
                "terminal_visible_rollup_count": 1,
            },
            "commons_notice": "",
            "filters": {},
            "review_file": None,
        }

    monkeypatch.setattr(
        "science_tool.benchmark_opportunities.benchmark_test_triage_report",
        fake_benchmark_test_triage_report,
    )

    result = CliRunner().invoke(
        science_cli,
        ["benchmark", "test-triage"],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )

    assert result.exit_code != 0
    assert "unknown fallback display group: generic-ish" in result.output


def test_benchmark_test_triage_cli_table_hides_generic_but_keeps_json_rollups(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0307-generic",
        """
id: hypothesis:0307-generic
kind: hypothesis
title: Generic hypothesis
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "visible-fallback",
        """
id: dataset:visible-fallback
kind: dataset
title: Visible Fallback
dataset_class: deposit
local_path: data/visible-fallback
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
      support:
        state: supported
        checked_at: '2026-07-03'
""",
    )

    table_result = _invoke_test_triage(tmp_path, "--source", "gap-fallback")

    assert table_result.exit_code == 0
    assert "Benchmark Test Triage: fallback-diagnostic" not in table_result.output
    assert "Benchmark Test Triage: generic fallback summary" in table_result.output

    json_result = _invoke_test_triage(tmp_path, "--source", "gap-fallback", "--format", "json")

    assert json_result.exit_code == 0
    payload = json.loads(json_result.output)
    rollup = payload["fallback_diagnostics"]["rollups"][0]
    assert rollup["benchmark_id"] == "dataset:visible-fallback"
    assert rollup["display_group"] == "generic-baseline-fallback"
    assert payload["buckets"]["fallback-diagnostic"][0]["benchmark_id"] == "dataset:visible-fallback"


def test_benchmark_test_triage_cli_table_output_shows_buckets(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0201-spatial",
        """
id: hypothesis:0201-spatial
kind: hypothesis
title: Spatial hypothesis
""",
        body="Microenvironment region needs spatial validation.",
    )
    _write_dataset(
        tmp_path,
        "hca-spatial",
        """
id: dataset:hca-spatial
kind: dataset
title: HCA Spatial
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke_test_triage(tmp_path)

    assert result.exit_code == 0
    assert "Benchmark Test Triage" in result.output
    assert "metadata-needed" in result.output
    assert "hypothesis:0201-spatial" in result.output
    assert "dataset:hca-spatial" in result.output
    assert "prediction-target" in result.output


def test_benchmark_test_triage_cli_output_requires_write_flag(tmp_path: Path) -> None:
    result = _invoke_test_triage(tmp_path, "--output", "doc/audits/benchmark-test-triage/custom.yaml")

    assert result.exit_code != 0
    assert "--output requires --write-review-file" in result.output


def test_benchmark_test_triage_cli_runnable_only_conflicts_with_other_readiness(tmp_path: Path) -> None:
    result = _invoke_test_triage(tmp_path, "--runnable-only", "--readiness", "stage-needed")

    assert result.exit_code != 0
    assert "--runnable-only conflicts with --readiness stage-needed" in result.output


def test_benchmark_test_triage_cli_writes_default_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 1))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0202-perturbation",
        """
id: hypothesis:0202-perturbation
kind: hypothesis
title: Perturbation response hypothesis
""",
        body="Drug perturbation should shift response states.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
kind: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: compound-response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )

    result = _invoke_test_triage(tmp_path, "--write-review-file", "--format", "json")

    assert result.exit_code == 0
    review_path = tmp_path / "doc" / "audits" / "benchmark-test-triage" / f"2026-07-01-{tmp_path.name}.yaml"
    assert review_path.is_file()
    assert f"wrote benchmark test triage review file: {review_path}" in result.stderr
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    written = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    assert written["project"] == tmp_path.name
    assert written["generated_at"] == "2026-07-01"
    assert written["review_file"] == str(review_path)
    assert written["source_command"].startswith("science benchmark test-triage")
    assert written["summary"]["bucket_counts"]["run-now"] == 1
    assert written["buckets"]["run-now"][0]["review"]["decision"] == ""
    assert written["fallback_diagnostics"] == {
        "top_benchmarks": [],
        "top_facets": [],
        "readiness_counts": {
            "runnable": 0,
            "stage-needed": 0,
            "metadata-only": 0,
            "blocked": 0,
        },
        "dataset_class_counts": {
            "deposit": 0,
            "reference": 0,
            "pointer": 0,
        },
        "task_support_counts": {
            "supported": 0,
            "candidate": 0,
            "blocked": 0,
            "none": 0,
        },
        "top_benchmarks_by_readiness": {
            "runnable": [],
            "stage-needed": [],
            "metadata-only": [],
            "blocked": [],
        },
        "top_benchmarks_by_dataset_class": {
            "deposit": [],
            "reference": [],
            "pointer": [],
        },
        "display_group_counts": {
            "specific-fallback": 0,
            "blocked-support-fallback": 0,
            "generic-baseline-fallback": 0,
            "generic-task-ready-fallback": 0,
            "generic-available-fallback": 0,
        },
        "hidden_generic_fallback_rows": 0,
        "shown_fallback_rows": 0,
        "top_generic_fallback_benchmarks": [],
        "top_generic_fallback_reasons": [],
        "terminal_visible_rollup_count": 0,
        "terminal_hidden_rollup_count": 0,
        "rollups": [],
    }


def test_benchmark_test_triage_review_file_includes_visible_fallback_rollups(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 3))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0307-generic",
        """
id: hypothesis:0307-generic
kind: hypothesis
title: Generic fallback hypothesis
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "visible-review-fallback",
        """
id: dataset:visible-review-fallback
kind: dataset
title: Visible Review Fallback
dataset_class: deposit
local_path: data/visible-review-fallback
benchmark:
  domains: [biology]
  modalities: [proteomics]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      task_type: protein-lineage-association
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
      support:
        state: supported
        checked_at: '2026-07-03'
""",
    )

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback", "--write-review-file", "--format", "json")

    assert result.exit_code == 0
    review_path = tmp_path / "doc" / "audits" / "benchmark-test-triage" / f"2026-07-03-{tmp_path.name}.yaml"
    written = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    rollups = written["fallback_diagnostics"]["rollups"]
    assert len(rollups) == 1
    assert rollups[0]["benchmark_id"] == "dataset:visible-review-fallback"
    assert rollups[0]["display_group"] == "specific-fallback"
    assert rollups[0]["task_id"] == "dataset:visible-review-fallback#ready"
    assert rollups[0]["task_type"] == "protein-lineage-association"
    assert rollups[0]["count"] == 1
    assert rollups[0]["task_support_state"] == "supported"
    assert rollups[0]["example_entities"] == ["hypothesis:0307-generic"]
    assert written["fallback_diagnostics"]["hidden_generic_fallback_rows"] == 0
    assert written["fallback_diagnostics"]["terminal_hidden_rollup_count"] == 0


def test_benchmark_test_triage_review_file_includes_suppression_diagnostics(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 3))
    _write_entity(
        tmp_path,
        "hypotheses",
        "0308-generic",
        """
id: hypothesis:0308-generic
kind: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "blocked-fallback",
        """
id: dataset:blocked-fallback
kind: dataset
title: Blocked Fallback
dataset_class: deposit
local_path: data/blocked-fallback
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-03'
""",
    )

    result = _invoke_test_triage(tmp_path, "--source", "gap-fallback", "--write-review-file", "--format", "json")

    assert result.exit_code == 0
    review_path = tmp_path / "doc" / "audits" / "benchmark-test-triage" / f"2026-07-03-{tmp_path.name}.yaml"
    written = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    assert written["summary"]["fallback_rows"] == 1
    assert written["summary"]["bucket_counts"]["fallback-diagnostic"] == 0
    assert written["summary"]["suppressed_blocked_support_fallback_rows"] == 1
    assert written["buckets"]["fallback-diagnostic"] == []
    assert written["fallback_diagnostics"]["suppressed_blocked_support"] == {
        "rows": 1,
        "top_benchmarks": [{"benchmark_id": "dataset:blocked-fallback", "count": 1}],
    }
    assert written["fallback_diagnostics"]["rollups"] == []
    assert written["fallback_diagnostics"]["display_group_counts"] == {
        "specific-fallback": 0,
        "blocked-support-fallback": 0,
        "generic-baseline-fallback": 0,
        "generic-task-ready-fallback": 0,
        "generic-available-fallback": 0,
    }
    assert written["fallback_diagnostics"]["hidden_generic_fallback_rows"] == 0


def test_benchmark_test_triage_cli_writes_custom_project_relative_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 1))

    result = _invoke_test_triage(
        tmp_path,
        "--write-review-file",
        "--output",
        "docs/audits/benchmark-test-triage/custom.yaml",
        "--format",
        "json",
    )

    assert result.exit_code == 0
    review_path = tmp_path / "docs" / "audits" / "benchmark-test-triage" / "custom.yaml"
    assert review_path.is_file()
    assert f"wrote benchmark test triage review file: {review_path}" in result.stderr
    payload = json.loads(result.output)
    assert payload["review_file"] == str(review_path)
    written = yaml.safe_load(review_path.read_text(encoding="utf-8"))
    assert written["review_file"] == str(review_path)


def test_benchmark_test_triage_cli_refuses_existing_review_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 1))
    output_path = tmp_path / "doc" / "audits" / "benchmark-test-triage" / "custom.yaml"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("existing: true\n", encoding="utf-8")

    result = _invoke_test_triage(
        tmp_path,
        "--write-review-file",
        "--output",
        "doc/audits/benchmark-test-triage/custom.yaml",
    )

    assert result.exit_code != 0
    assert "review file already exists" in result.output
    assert output_path.read_text(encoding="utf-8") == "existing: true\n"


def test_benchmark_test_triage_cli_rejects_output_outside_project_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("science_tool.cli._benchmark_test_triage_today", lambda: date(2026, 7, 1))

    relative_result = _invoke_test_triage(tmp_path, "--write-review-file", "--output", "../outside.yaml")
    assert relative_result.exit_code != 0
    assert "--output must stay under project root" in relative_result.output
    assert not (tmp_path.parent / "outside.yaml").exists()

    outside_path = tmp_path.parent / "outside-absolute.yaml"
    absolute_result = _invoke_test_triage(tmp_path, "--write-review-file", "--output", str(outside_path))
    assert absolute_result.exit_code != 0
    assert "--output must stay under project root" in absolute_result.output
    assert not outside_path.exists()


def test_benchmark_test_triage_cli_json_and_commons_notice(tmp_path: Path) -> None:
    result = _invoke_test_triage(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["commons_notice"] is not None
    assert "notice: commons benchmarks unavailable" in result.stderr
