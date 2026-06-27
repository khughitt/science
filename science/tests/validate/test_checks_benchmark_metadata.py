from __future__ import annotations

from pathlib import Path

from science_tool.validate.result import Severity


def _load_checks_with_benchmark_metadata_fresh() -> None:
    import sys

    import science_tool.validate.checks as checks

    checks.clear_checks_for_tests()
    sys.modules.pop("science_tool.validate.checks.benchmark_metadata", None)
    checks._load_canonical_checks()


def _ds(**kw) -> dict:
    base = {
        "type": "dataset",
        "id": "dataset:x",
        "_path": "entities/datasets/x.md",
        "dataset_class": "deposit",
    }
    base.update(kw)
    return base


def _rules(datasets: list[dict]) -> list[tuple[Severity, str]]:
    from science_tool.validate.checks.benchmark_metadata import evaluate_benchmark_metadata

    return [(r.severity, r.rule) for r in evaluate_benchmark_metadata(datasets)]


def _results(datasets: list[dict]):
    from science_tool.validate.checks.benchmark_metadata import evaluate_benchmark_metadata

    return list(evaluate_benchmark_metadata(datasets))


def test_dataset_without_benchmark_is_ignored() -> None:
    assert _rules([_ds()]) == []


def test_duplicate_task_ids_are_error() -> None:
    rules = _rules(
        [
            _ds(
                benchmark={
                    "tasks": [
                        {"task_id": "rank-genes", "task_type": "ranking", "prediction_target": "gene"},
                        {"task_id": "rank-genes", "task_type": "ranking", "prediction_target": "gene"},
                    ]
                }
            )
        ]
    )

    assert (Severity.ERROR, "benchmark.task-id-duplicate") in rules


def test_invalid_task_id_is_error_and_mentions_lowercase_kebab_case() -> None:
    results = _results([_ds(benchmark={"tasks": [{"task_id": "Rank__Genes"}]})])

    assert any(
        result.severity is Severity.ERROR
        and result.rule == "benchmark.task-id-invalid"
        and "lowercase kebab-case" in result.message
        for result in results
    )


def test_task_missing_core_evaluation_fields_warns() -> None:
    assert (Severity.WARN, "benchmark.task-sparse") in _rules(
        [_ds(benchmark={"tasks": [{"task_id": "rank-genes", "task_type": "ranking"}]})]
    )


def test_facets_only_block_without_limitations_warns() -> None:
    assert (Severity.WARN, "benchmark.facets-lack-task-or-limitation") in _rules(
        [_ds(benchmark={"benchmark_kinds": ["static-association"]})]
    )


def test_perturbation_response_without_intervention_or_contexts_warns() -> None:
    assert (Severity.WARN, "benchmark.perturbation-context-missing") in _rules(
        [
            _ds(
                benchmark={
                    "benchmark_kinds": ["perturbation-response"],
                    "tasks": [
                        {
                            "task_id": "predict-response",
                            "task_type": "prediction",
                            "prediction_target": "response",
                        }
                    ],
                }
            )
        ]
    )


def test_time_series_without_timepoints_warns() -> None:
    assert (Severity.WARN, "benchmark.timepoints-missing") in _rules(
        [
            _ds(
                benchmark={
                    "benchmark_kinds": ["time-series"],
                    "tasks": [
                        {
                            "task_id": "predict-trajectory",
                            "task_type": "prediction",
                            "prediction_target": "trajectory",
                        }
                    ],
                }
            )
        ]
    )


def test_pointer_dataset_with_benchmark_emits_info() -> None:
    assert (Severity.INFO, "benchmark.pointer-block") in _rules(
        [
            _ds(
                dataset_class="pointer",
                benchmark={"tasks": [{"task_id": "rank-genes", "task_type": "ranking", "prediction_target": "gene"}]},
            )
        ]
    )


def test_module_is_registered() -> None:
    from science_tool.validate.checks import CANONICAL_CHECKS

    _load_checks_with_benchmark_metadata_fresh()
    assert any(entry.fn.__module__.endswith("benchmark_metadata") for entry in CANONICAL_CHECKS)


def test_runner_surfaces_benchmark_warning_through_full_profile(tmp_path: Path) -> None:
    from science_tool.validate.runner import run

    _load_checks_with_benchmark_metadata_fresh()
    (tmp_path / "science.yaml").write_text(
        "name: demo\n"
        "created: '2026-01-01'\n"
        "last_modified: '2026-01-01'\n"
        "status: active\n"
        "summary: demo\n"
        "profile: research\n"
        "layout_version: 1\n"
        "knowledge_profiles: {local: local}\n",
        encoding="utf-8",
    )
    ds_dir = tmp_path / "entities" / "datasets"
    ds_dir.mkdir(parents=True)
    (ds_dir / "x.md").write_text(
        "---\n"
        "id: dataset:x\n"
        "type: dataset\n"
        "title: X\n"
        "status: active\n"
        "origin: external\n"
        "dataset_class: deposit\n"
        "license: MIT\n"
        "ontology_terms: []\n"
        "benchmark:\n"
        "  benchmark_kinds: [static-association]\n"
        "---\n\n"
        "# X\n",
        encoding="utf-8",
    )

    result = run(tmp_path, strict=False, verbose=False, profile="full", enable_python_sidecar=False)

    assert any(r.rule == "benchmark.facets-lack-task-or-limitation" for r in result.results)
