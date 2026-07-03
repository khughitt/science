from __future__ import annotations

from pathlib import Path

from science_tool.validate.result import Severity


def _load_checks_with_dataset_capabilities_fresh() -> None:
    import sys

    import science_tool.validate.checks as checks

    checks.clear_checks_for_tests()
    sys.modules.pop("science_tool.validate.checks.dataset_capabilities", None)
    checks._load_canonical_checks()


def _results(entities: list[dict]):
    from science_tool.validate.checks.dataset_capabilities import evaluate_dataset_capabilities

    return list(evaluate_dataset_capabilities(entities))


def _rules(entities: list[dict]) -> list[tuple[Severity, str]]:
    return [(result.severity, result.rule) for result in _results(entities)]


def _dataset(**kw) -> dict:
    base = {
        "id": "dataset:rna",
        "type": "dataset",
        "_path": "entities/datasets/rna.md",
        "provided_capabilities": [{"assay": "gene-expression", "modality": "bulk-rna"}],
    }
    base.update(kw)
    return base


def _question(**kw) -> dict:
    base = {
        "id": "question:q1",
        "type": "question",
        "_path": "entities/questions/q1.md",
        "datasets": ["dataset:rna"],
        "required_capabilities": [{"assay": "gene-expression", "modality": "bulk-rna"}],
    }
    base.update(kw)
    return base


def test_valid_capability_metadata_is_clean() -> None:
    assert _rules([_dataset(), _question()]) == []


def test_target_with_dataset_reference_missing_required_capabilities_warns() -> None:
    question = _question()
    question.pop("required_capabilities")

    rules = _rules([_dataset(), question])

    assert (Severity.WARN, "dataset-capabilities.required-missing") in rules


def test_dataset_reaching_target_missing_provided_capabilities_warns() -> None:
    dataset = _dataset()
    dataset.pop("provided_capabilities")

    rules = _rules([dataset, _question()])

    assert (Severity.WARN, "dataset-capabilities.provided-missing") in rules


def test_dataset_related_to_target_counts_as_capability_relevant() -> None:
    dataset = _dataset(related=["hypothesis:h1"])
    dataset.pop("provided_capabilities")
    hypothesis = {
        "id": "hypothesis:h1",
        "type": "hypothesis",
        "_path": "entities/hypotheses/h1.md",
        "required_capabilities": [{"assay": "gene-expression"}],
    }

    rules = _rules([dataset, hypothesis])

    assert (Severity.WARN, "dataset-capabilities.provided-missing") in rules


def test_capability_fields_warn_on_malformed_shape() -> None:
    rules = _rules(
        [
            _dataset(provided_capabilities={"assay": "gene-expression"}),
            _question(required_capabilities=[{"assay": "gene-expression", "modality": 7}]),
        ]
    )

    assert (Severity.WARN, "dataset-capabilities.provided-malformed") in rules
    assert (Severity.WARN, "dataset-capabilities.required-malformed") in rules


def test_unreached_dataset_without_provided_capabilities_does_not_warn() -> None:
    dataset = _dataset()
    dataset.pop("provided_capabilities")

    assert _rules([dataset]) == []


def test_module_is_registered() -> None:
    from science_tool.validate.checks import CANONICAL_CHECKS

    _load_checks_with_dataset_capabilities_fresh()

    assert any(entry.fn.__module__.endswith("dataset_capabilities") for entry in CANONICAL_CHECKS)


def test_capability_warning_surfaces_through_runner(tmp_path: Path) -> None:
    from science_tool.validate.runner import run

    _load_checks_with_dataset_capabilities_fresh()
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    ds_dir = tmp_path / "entities" / "datasets"
    q_dir = tmp_path / "entities" / "questions"
    ds_dir.mkdir(parents=True)
    q_dir.mkdir(parents=True)
    (ds_dir / "rna.md").write_text(
        "---\n"
        'id: "dataset:rna"\n'
        'type: "dataset"\n'
        'title: "RNA"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'license: "MIT"\n'
        'dataset_class: "deposit"\n'
        "ontology_terms: []\n"
        "---\n\n# RNA\n",
        encoding="utf-8",
    )
    (q_dir / "q1.md").write_text(
        "---\n"
        'id: "question:q1"\n'
        'type: "question"\n'
        'title: "Q1"\n'
        'status: "open"\n'
        'datasets: ["dataset:rna"]\n'
        "ontology_terms: []\n"
        "---\n\n# Q1\n",
        encoding="utf-8",
    )

    result = run(tmp_path, strict=False, verbose=False, enable_python_sidecar=False)

    assert any(r.rule == "dataset-capabilities.provided-missing" for r in result.results)
    assert any(r.rule == "dataset-capabilities.required-missing" for r in result.results)
