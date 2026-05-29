from __future__ import annotations

from science_tool.validate.result import Severity


def _rules(results):
    return [(r.severity, r.rule) for r in results]


def _fm(**extra):
    return {
        "id": "paper:Adams2025",
        "type": "paper",
        "_path": "doc/papers/Adams2025.md",
        **extra,
    }


def test_malformed_dataset_usage_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage={"ref": "dataset:gtex-v8", "role": "analyzed"})],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.dataset-usage-malformed")]


def test_paper_datasets_invalid_entry_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets=["paper:Other"])],
            dataset_ref_status={},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_paper_datasets_empty_mapping_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets={})],
            dataset_ref_status={},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_paper_datasets_empty_string_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets="")],
            dataset_ref_status={},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_legacy_paper_datasets_warns_when_not_equivalent() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets=["dataset:gtex-v8"])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.WARN, "dataset-influence.paper-datasets-legacy")]


def test_paper_datasets_conflict_warns_and_explicit_wins() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    datasets=["dataset:gtex-v8"],
                    dataset_usage=[{"ref": "dataset:gtex-v8", "role": "cited"}],
                )
            ],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.WARN, "dataset-influence.paper-datasets-conflict")]


def test_paper_datasets_analyzed_full_is_refinement_not_conflict() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    datasets=["dataset:gtex-v8"],
                    dataset_usage=[{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}],
                )
            ],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert results == []


def test_dataset_self_reference_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "dataset:self",
                    "type": "dataset",
                    "_path": "data/self/datapackage.yaml",
                    "dataset_usage": [{"ref": "dataset:self", "role": "analyzed"}],
                }
            ],
            dataset_ref_status={"dataset:self": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.self-reference")]


def test_dataset_derivation_inputs_self_reference_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "dataset:self",
                    "type": "dataset",
                    "_path": "data/self/datapackage.yaml",
                    "derivation": {"inputs": ["dataset:self"]},
                }
            ],
            dataset_ref_status={"dataset:self": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.self-reference")]


def test_unresolved_refs_use_pinned_severities() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    dataset_usage=[
                        {"ref": "dataset:unknown-a", "role": "analyzed"},
                        {"ref": "dataset:unknown-b", "role": "training"},
                    ]
                )
            ],
            dataset_ref_status={
                "dataset:unknown-a": "unavailable",
                "dataset:unknown-b": "missing",
            },
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [
        (Severity.INFO, "dataset-influence.ref-unresolved-unavailable"),
        (Severity.WARN, "dataset-influence.ref-unresolved"),
    ]


def test_row_usage_refs_unresolved_uses_pinned_severities() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [],
            dataset_ref_status={
                "dataset:row-a": "unavailable",
                "dataset:row-b": "missing",
            },
            row_usage_refs=[
                ("dataset:row-a", "geneset:one", "doc/gene-sets.tsv"),
                ("dataset:row-b", "geneset:two", "doc/gene-sets.tsv"),
            ],
        )
    )

    assert _rules(results) == [
        (Severity.INFO, "dataset-influence.ref-unresolved-unavailable"),
        (Severity.WARN, "dataset-influence.ref-unresolved"),
    ]
