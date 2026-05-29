from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


_MANIFEST = "name: demo\nknowledge_profiles:\n  local: local\n"


def _rules(results):
    return [(r.severity, r.rule) for r in results]


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _fm(**extra):
    return {
        "id": "paper:Adams2025",
        "type": "paper",
        "_path": "doc/papers/Adams2025.md",
        **extra,
    }


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")


def _write_dataset_usage_paper(root: Path, ref: str = "dataset:gtex-v8") -> None:
    (root / "doc" / "papers").mkdir(parents=True)
    (root / "doc" / "papers" / "Adams2025.md").write_text(
        f"---\nid: paper:Adams2025\ntype: paper\ntitle: Adams\ndataset_usage:\n"
        f"  - ref: {ref}\n    role: analyzed\n---\n",
        encoding="utf-8",
    )


def _write_initialized_commons(root: Path) -> Path:
    commons = root / "commons"
    for dirname in (".git", "datasets", "papers", "topics", "themes"):
        (commons / dirname).mkdir(parents=True)
    return commons


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


def test_check_dataset_influence_resolves_local_dataset_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path)
    dp_dir = tmp_path / "data" / "gtex"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:gtex-v8\ntype: dataset\ntitle: GTEx\n"
        "origin: external\ntier: use-now\ndatapackage: datapackage.yaml\naccess: {level: public, verified: true}\n",
        encoding="utf-8",
    )

    assert list(check_dataset_influence(_ctx(tmp_path))) == []


def test_check_dataset_influence_unbuilt_commons_ref_infos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path)

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.INFO, "dataset-influence.ref-unresolved-unavailable")]


def test_check_dataset_influence_empty_commons_dir_ref_infos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    commons = tmp_path / "empty-commons"
    commons.mkdir()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path)

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.INFO, "dataset-influence.ref-unresolved-unavailable")]


def test_check_dataset_influence_built_commons_missing_ref_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_write_initialized_commons(tmp_path)))
    _write_project(tmp_path)
    _write_dataset_usage_paper(tmp_path)

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.WARN, "dataset-influence.ref-unresolved")]


def test_dataset_influence_registration_after_genesets() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.dataset_influence as dataset_influence
    import science_tool.validate.checks.genesets as genesets

    importlib.reload(genesets)
    importlib.reload(dataset_influence)

    ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]
    genesets_index = next(index for index, entry in enumerate(ordered) if entry[0] == "gene-set collections")
    influence_index = next(index for index, entry in enumerate(ordered) if entry[0] == "dataset influence")
    assert influence_index == genesets_index + 1


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
