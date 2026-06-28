from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _write_entity(root: Path, kind_dir: str, slug: str, frontmatter: str, body: str = "body") -> None:
    path = root / "entities" / kind_dir / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}\n", encoding="utf-8")


def _write_dataset(root: Path, slug: str, frontmatter: str, body: str = "body") -> None:
    _write_entity(root, "datasets", slug, frontmatter, body=body)


def _invoke(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "opportunities", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def _invoke_with_commons(tmp_path: Path, commons_root: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "opportunities", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(commons_root)},
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


def test_benchmark_sources_preserve_task_details_notes_and_limitations(tmp_path: Path) -> None:
    from science_tool.benchmark_catalog import benchmark_sources

    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq, perturbation]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  notes:
    - Useful perturbation benchmark.
  limitations:
    - No local datapackage staged.
  tasks:
    - id: compound-response
      prediction_target: post-treatment expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured expression
""",
    )

    sources, notice = benchmark_sources(tmp_path)

    assert notice is None
    assert len(sources) == 1
    source = sources[0]
    assert source["fallback_id"] == "dataset:sciplex3"
    assert source["scope"] == "local"
    frontmatter = cast("dict[str, Any]", source["frontmatter"])
    benchmark = cast("dict[str, Any]", frontmatter["benchmark"])
    assert benchmark["notes"] == ["Useful perturbation benchmark."]
    assert benchmark["limitations"] == ["No local datapackage staged."]
    assert benchmark["tasks"][0] == {
        "id": "compound-response",
        "prediction_target": "post-treatment expression",
        "held_out_unit": "compound",
        "metric": "rank-correlation",
        "baseline": "nearest-neighbor",
        "ground_truth": {
            "type": "measured-outcome",
            "description": "measured expression",
        },
    }


def test_load_opportunity_datasets_preserves_facets_only_and_task_rows(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import load_opportunity_datasets

    _write_dataset(
        tmp_path,
        "hca-spatial",
        """
id: dataset:hca-spatial
type: dataset
title: HCA Spatial
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  limitations:
    - Facets only.
""",
    )
    _write_dataset(
        tmp_path,
        "cptac",
        """
id: dataset:cptac
type: dataset
title: CPTAC Proteogenomics
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [proteomics, multimodal]
  signal_types: [multi-omic]
  benchmark_kinds: [mechanism-discrimination]
  tasks:
    - id: subtype-transfer
      prediction_target: subtype
      held_out_unit: cohort
      metric: auroc
      baseline: clinical-only
      ground_truth:
        type: measured-outcome
        description: curated subtype
""",
    )

    rows, notice = load_opportunity_datasets(tmp_path, include_commons=False)

    assert notice is None
    assert [row.id for row in rows] == ["dataset:cptac", "dataset:hca-spatial"]
    assert rows[0].tasks[0].canonical_task_id == "dataset:cptac#subtype-transfer"
    assert rows[1].tasks == []
    assert rows[1].limitations == ["Facets only."]


def test_baseline_score_is_component_sum_and_credits_perturbation_axes(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import baseline_score, load_opportunity_datasets

    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq, perturbation]
  signal_types: [perturbation, cross-context-generalization]
  benchmark_kinds: [perturbation-response]
  limitations:
    - No local datapackage staged.
  tasks:
    - id: compound-response
      prediction_target: post-treatment expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured expression
""",
    )

    dataset = load_opportunity_datasets(tmp_path, include_commons=False)[0][0]
    score = baseline_score(dataset)

    assert score.total == sum(score.components.values())
    assert score.components["task_completeness"] == 30
    assert score.components["signal_value"] > 0
    assert score.components["modality_value"] > 0
    assert score.components["limitations"] == 10
    assert "signal:perturbation" in score.notes
    assert "modality:perturbation" in score.notes


def test_opportunity_report_matches_shorthand_related_belief_and_controlled_facets(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0005-dynamic-homeostasis",
        """
id: hypothesis:0005-dynamic-homeostasis
type: hypothesis
title: Dynamic perturbation recovery
status: active
""",
        body="Proteomics should improve recovery predictions. Prose mentions noisy measured expression.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq, perturbation]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  related_beliefs:
    - h5 predicts response shifts.
  limitations:
    - No local datapackage staged.
  tasks:
    - id: compound-response
      prediction_target: post-treatment expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured expression
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)

    rows = payload["matched_opportunities"]
    assert len(rows) == 1
    assert rows[0]["entity_id"] == "hypothesis:0005-dynamic-homeostasis"
    assert rows[0]["benchmark_id"] == "dataset:sciplex3"
    assert rows[0]["task_id"] == "dataset:sciplex3#compound-response"
    assert "related-belief-id:h5" in rows[0]["match_reasons"]
    assert "facet-token:perturbation" in rows[0]["match_reasons"]
    assert not any("measured" in reason for reason in rows[0]["match_reasons"])


def test_opportunity_report_matches_prefixed_shorthand_related_belief(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-perturbation",
        """
id: hypothesis:0001-perturbation
type: hypothesis
title: Response shift model
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [dose-response]
  benchmark_kinds: [expression-response]
  related_beliefs:
    - hypothesis:h1 predicts response shifts.
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)

    rows = payload["matched_opportunities"]
    assert len(rows) == 1
    assert rows[0]["entity_id"] == "hypothesis:0001-perturbation"
    assert rows[0]["benchmark_id"] == "dataset:sciplex3"
    assert "related-belief-id:hypothesis:h1" in rows[0]["match_reasons"]


def test_stoplist_blocks_generic_token_only_match(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-model",
        """
id: hypothesis:0001-model
type: hypothesis
title: Model response analysis
status: active
""",
        body="Data and model evidence.",
    )
    _write_dataset(
        tmp_path,
        "generic",
        """
id: dataset:generic
type: dataset
title: Generic
benchmark:
  domains: [biology]
  modalities: [data]
  signal_types: [response]
  benchmark_kinds: [analysis]
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)

    assert payload["matched_opportunities"] == []
    assert payload["unmapped_project_entities"][0]["entity_id"] == "hypothesis:0001-model"
    assert payload["available_unmapped_benchmarks"][0]["benchmark_id"] == "dataset:generic"


def test_broad_domain_facet_is_not_scored_as_opportunity_match(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-biology",
        """
id: hypothesis:0001-biology
type: hypothesis
title: Biology framing
status: active
""",
        body="This project asks whether biology is the right explanatory level.",
    )
    _write_dataset(
        tmp_path,
        "proteogenomics",
        """
id: dataset:proteogenomics
type: dataset
title: Proteogenomics benchmark
benchmark:
  domains: [biology]
  modalities: [proteomics, multimodal]
  signal_types: [multi-omic]
  benchmark_kinds: [cross-context-generalization]
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False, calibration_report=True)

    assert payload["matched_opportunities"] == []
    assert payload["unmapped_project_entities"][0]["entity_id"] == "hypothesis:0001-biology"
    assert payload["available_unmapped_benchmarks"][0]["benchmark_id"] == "dataset:proteogenomics"
    benchmark_tokens = payload["calibration"].get("benchmark_controlled_facet_tokens")
    assert benchmark_tokens is not None
    assert "biology" in benchmark_tokens["dataset:proteogenomics"]


def test_diversity_credit_requires_specific_match_signal(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-biology",
        """
id: hypothesis:0001-biology
type: hypothesis
title: Biology framing
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "spatial",
        """
id: dataset:spatial
type: dataset
title: Spatial benchmark
benchmark:
  domains: [biology]
  modalities: [spatial, single-cell-rna-seq]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)

    assert payload["matched_opportunities"] == []


def test_facets_only_rows_use_null_task_and_diversity_is_per_entity(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial",
        """
id: hypothesis:0002-spatial
type: hypothesis
title: Spatial proteomics transfer
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "atlas",
        """
id: dataset:atlas
type: dataset
title: Spatial atlas
benchmark:
  domains: [biology]
  modalities: [spatial, proteomics]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  limitations:
    - Facets only.
""",
    )
    _write_dataset(
        tmp_path,
        "multi-task",
        """
id: dataset:multi-task
type: dataset
title: Spatial proteomics tasks
benchmark:
  domains: [biology]
  modalities: [spatial, proteomics]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  tasks:
    - id: task-a
      prediction_target: subtype
    - id: task-b
      prediction_target: subtype
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)
    rows = payload["matched_opportunities"]

    atlas = next(row for row in rows if row["benchmark_id"] == "dataset:atlas")
    assert atlas["task_id"] is None
    assert atlas["score_components"]["relative"]["diversity_added"] > 0
    task_rows = [row for row in rows if row["benchmark_id"] == "dataset:multi-task"]
    assert [row["task_id"] for row in task_rows] == ["dataset:multi-task#task-a", "dataset:multi-task#task-b"]
    diversity_points = [row["score_components"]["relative"]["diversity_added"] for row in task_rows]
    assert diversity_points[0] == 0
    assert diversity_points[1] == 0


def test_multi_task_rows_share_relative_score_when_first_match(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial",
        """
id: hypothesis:0002-spatial
type: hypothesis
title: Spatial proteomics transfer
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "multi-task",
        """
id: dataset:multi-task
type: dataset
title: Spatial proteomics tasks
benchmark:
  domains: [biology]
  modalities: [spatial, proteomics]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  tasks:
    - id: task-a
      prediction_target: subtype
    - id: task-b
      prediction_target: subtype
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)

    rows = payload["matched_opportunities"]
    assert [row["task_id"] for row in rows] == ["dataset:multi-task#task-a", "dataset:multi-task#task-b"]
    assert rows[0]["relative_score"] == rows[1]["relative_score"]
    assert (
        rows[0]["score_components"]["relative"]["diversity_added"]
        == rows[1]["score_components"]["relative"]["diversity_added"]
    )


def test_related_belief_id_match_sorts_above_token_only_match(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0005-perturbation",
        """
id: hypothesis:0005-perturbation
type: hypothesis
title: Perturbation response
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "token-only",
        """
id: dataset:token-only
type: dataset
title: Token-only
benchmark:
  domains: [biology]
  modalities: [perturbation]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )
    _write_dataset(
        tmp_path,
        "id-linked",
        """
id: dataset:id-linked
type: dataset
title: ID linked
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  related_beliefs:
    - hypothesis:0005-perturbation has an explicit benchmark link.
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)

    rows = payload["matched_opportunities"]
    assert [row["benchmark_id"] for row in rows[:2]] == ["dataset:id-linked", "dataset:token-only"]
    assert rows[0]["score_components"]["relative"]["related_belief_id"] == 40
    assert rows[1]["score_components"]["relative"]["related_belief_id"] == 0


def test_benchmark_opportunities_json_and_calibration_shape(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-perturbation",
        """
id: hypothesis:0001-perturbation
type: hypothesis
title: Perturbation response
status: active
""",
        body="Perturbation response uses an x condition.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  notes:
    - Measured expression prose is displayed for calibration only.
    - The q marker is too small for matching.
""",
    )

    result = _invoke(tmp_path, "--format", "json", "--calibration-report")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["matched_opportunities"][0]["entity_id"] == "hypothesis:0001-perturbation"
    assert payload["calibration"]["enabled"] is True
    assert "stop_tokens" in payload["calibration"]
    entity_tokens = payload["calibration"]["entity_tokens"]["hypothesis:0001-perturbation"]
    assert "hypothesis:0001-perturbation" in entity_tokens
    assert "perturbation" in entity_tokens
    benchmark_tokens = payload["calibration"]["benchmark_controlled_facet_tokens"]["dataset:sciplex3"]
    assert "dataset:sciplex3" in benchmark_tokens
    assert "perturbation" in benchmark_tokens
    dropped = payload["calibration"]["dropped_tokens"]
    assert "response" in dropped["stop"]["hypothesis:0001-perturbation"]
    assert "x" in dropped["short"]["hypothesis:0001-perturbation"]
    assert "q" in dropped["short"]["dataset:sciplex3"]
    evidence = payload["calibration"]["matched_token_evidence"]
    assert evidence
    matched = next(
        item
        for item in evidence
        if item["entity_id"] == "hypothesis:0001-perturbation" and item["benchmark_id"] == "dataset:sciplex3"
    )
    assert "perturbation" in matched["facet_overlap"]
    assert matched["score_components"] == payload["matched_opportunities"][0]["score_components"]
    unmatched = payload["calibration"]["unmatched_tokens"]
    assert "entities" in unmatched
    assert "benchmarks" in unmatched
    assert "hypothesis:0001-perturbation" in unmatched["entities"]
    assert "dataset:sciplex3" in unmatched["benchmarks"]
    excluded = payload["calibration"]["excluded_benchmark_prose_tokens"]["dataset:sciplex3"]
    assert "measured" in excluded
    assert not any("measured" in reason for reason in payload["matched_opportunities"][0]["match_reasons"])


def test_benchmark_opportunities_table_uses_candidate_language(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-spatial",
        """
id: hypothesis:0001-spatial
type: hypothesis
title: Spatial transfer
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "atlas",
        """
id: dataset:atlas
type: dataset
title: Atlas
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke(tmp_path)

    assert result.exit_code == 0
    assert "Candidate Opportunities" in result.output
    assert "recommended" not in result.output.lower()
    assert "best" not in result.output.lower()


def test_benchmark_opportunities_invalid_entity_is_click_error(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "--entity", "hypothesis:missing")

    assert result.exit_code == 1
    assert "Entity not found: hypothesis:missing" in result.output


def test_benchmark_opportunities_commons_unavailable_degrades_to_local_rows(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-static",
        """
id: hypothesis:0001-static
type: hypothesis
title: Static spatial association
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "local",
        """
id: dataset:local
type: dataset
title: Local
benchmark:
  domains: [biology]
  modalities: [spatial]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["matched_opportunities"][0]["benchmark_id"] == "dataset:local"
    assert payload["matched_opportunities"][0]["entity_id"] == "hypothesis:0001-static"
    assert payload["commons_notice"]
    assert "notice: commons benchmarks unavailable" in result.stderr


def test_benchmark_opportunities_commons_corrupt_registry_degrades_to_local_rows(tmp_path: Path) -> None:
    commons_root = tmp_path / "commons"
    _write_corrupt_commons_registry(commons_root, '"bad"')
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-static",
        """
id: hypothesis:0001-static
type: hypothesis
title: Static spatial association
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "local",
        """
id: dataset:local
type: dataset
title: Local
benchmark:
  domains: [biology]
  modalities: [spatial]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke_with_commons(tmp_path, commons_root, "--commons", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["matched_opportunities"][0]["benchmark_id"] == "dataset:local"
    assert payload["matched_opportunities"][0]["entity_id"] == "hypothesis:0001-static"
    assert payload["commons_notice"]
    assert "frontmatter_json must decode to an object" in payload["commons_notice"]
    assert "notice: commons benchmarks unavailable" in result.stderr
    assert "frontmatter_json must decode to an object" in result.stderr


def test_gaps_report_projects_uncovered_entities_and_candidate_benchmarks(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-unmapped",
        """
id: hypothesis:0001-unmapped
type: hypothesis
title: Homeostatic recovery has no benchmark yet
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "atlas",
        """
id: dataset:atlas
type: dataset
title: Atlas Benchmark
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  tasks:
    - id: transfer
      prediction_target: region label
      held_out_unit: tissue
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: curated region
""",
    )

    payload = gaps_report(tmp_path)

    assert payload["summary"] == {
        "entities_total": 1,
        "entities_with_gaps": 1,
        "uncovered_entities": 1,
        "weakly_covered_entities": 0,
        "missing_facet_entities": 0,
    }
    row = payload["benchmark_gaps"][0]
    assert row["entity_id"] == "hypothesis:0001-unmapped"
    assert row["gap_level"] == "uncovered"
    assert row["missing_modalities"] == []
    assert row["missing_signal_types"] == []
    assert row["current_matches"] == []
    assert row["candidate_benchmarks"][0]["benchmark_id"] == "dataset:atlas"
    assert row["candidate_benchmarks"][0]["matched_missing_facets"] == []


def test_gaps_report_projects_existing_coverage_gaps_as_missing_facet(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial-proteomics",
        """
id: hypothesis:0002-spatial-proteomics
type: hypothesis
title: Spatial proteomics transfer
""",
        body="Spatial proteomics transfer should generalize.",
    )
    _write_dataset(
        tmp_path,
        "spatial",
        """
id: dataset:spatial
type: dataset
title: Spatial Atlas
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  related_beliefs:
    - hypothesis:0002-spatial-proteomics
  tasks:
    - id: transfer
      prediction_target: region label
      held_out_unit: tissue
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: curated region
""",
    )
    _write_dataset(
        tmp_path,
        "unrelated",
        """
id: dataset:unrelated
type: dataset
title: Unrelated Benchmark
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: response
      prediction_target: response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured response
""",
    )

    payload = gaps_report(tmp_path)

    row = payload["benchmark_gaps"][0]
    assert row["gap_level"] == "missing-facet"
    assert row["missing_modalities"] == ["proteomics"]
    assert row["missing_signal_types"] == []
    assert row["current_matches"][0]["relative_score"] >= 15
    assert row["suggested_search_facets"] == ["proteomics"]
    assert row["candidate_benchmarks"][0]["benchmark_id"] == "dataset:unrelated"
    assert row["candidate_benchmarks"][0]["matched_missing_facets"] == []


def test_gaps_report_prioritizes_weak_matches_over_missing_facets(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial-proteomics",
        """
id: hypothesis:0002-spatial-proteomics
type: hypothesis
title: Spatial proteomics transfer
""",
        body="Spatial proteomics transfer should generalize.",
    )
    _write_dataset(
        tmp_path,
        "spatial",
        """
id: dataset:spatial
type: dataset
title: Spatial Atlas
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  tasks:
    - id: transfer
      prediction_target: region label
      held_out_unit: tissue
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: curated region
""",
    )

    payload = gaps_report(tmp_path)

    row = payload["benchmark_gaps"][0]
    assert row["gap_level"] == "weak"
    assert row["missing_modalities"] == ["proteomics"]
    assert row["current_matches"][0]["relative_score"] < 15


def test_gaps_report_rejects_blank_or_unknown_facet(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    for facet in ("", "   ", "unknown-facet"):
        with pytest.raises(ValueError, match="facet"):
            gaps_report(tmp_path, facet=facet)


def test_gaps_report_filters_by_high_value_facet(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-temporal",
        """
id: hypothesis:0004-temporal
type: hypothesis
title: Time-series missing gap
""",
        body="Time-series dynamics remain untested.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0005-proteomics",
        """
id: hypothesis:0005-proteomics
type: hypothesis
title: Proteomics missing gap
""",
        body="Proteomics transfer remains untested.",
    )

    payload = gaps_report(tmp_path, facet="time-series")

    assert [row["entity_id"] for row in payload["benchmark_gaps"]] == ["hypothesis:0004-temporal"]
    assert payload["summary"]["entities_total"] == 2
    assert payload["summary"]["entities_with_gaps"] == 1


def test_candidate_rows_sort_by_matched_facets_score_then_id() -> None:
    from science_tool.benchmark_opportunities import _candidate_rows

    rows = _candidate_rows(
        [
            {
                "benchmark_id": "dataset:z-unmatched-high-score",
                "benchmark_title": "Unmatched High Score",
                "baseline_score": 99,
                "unmapped_facets": ["spatial"],
            },
            {
                "benchmark_id": "dataset:beta",
                "benchmark_title": "Beta",
                "baseline_score": 20,
                "unmapped_facets": ["proteomics"],
            },
            {
                "benchmark_id": "dataset:alpha",
                "benchmark_title": "Alpha",
                "baseline_score": 20,
                "unmapped_facets": ["proteomics"],
            },
            {
                "benchmark_id": "dataset:score",
                "benchmark_title": "Score",
                "baseline_score": 30,
                "unmapped_facets": ["proteomics"],
            },
            {
                "benchmark_id": "dataset:two-match",
                "benchmark_title": "Two Match",
                "baseline_score": 1,
                "unmapped_facets": ["perturbation", "proteomics"],
            },
        ],
        {"perturbation", "proteomics"},
    )

    assert [row["benchmark_id"] for row in rows] == [
        "dataset:two-match",
        "dataset:score",
        "dataset:alpha",
        "dataset:beta",
        "dataset:z-unmatched-high-score",
    ]
    assert rows[0]["matched_missing_facets"] == ["perturbation", "proteomics"]
