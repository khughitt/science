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
        "kind": "dataset",
        "_path": "entities/datasets/rna.md",
        "provided_capabilities": [{"assay": "gene-expression", "modality": "bulk-rna"}],
    }
    base.update(kw)
    return base


def _question(**kw) -> dict:
    base = {
        "id": "question:q1",
        "kind": "question",
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
        "kind": "hypothesis",
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


def test_provided_missing_suppressed_when_all_reached_targets_demand_closed() -> None:
    dataset = _dataset()
    dataset.pop("provided_capabilities")
    answered = _question(status="answered")

    rules = _rules([dataset, answered])

    assert (Severity.WARN, "dataset-capabilities.provided-missing") not in rules


def test_provided_missing_kept_when_any_reached_target_is_live() -> None:
    dataset = _dataset(related=["question:q1", "question:q2"])
    dataset.pop("provided_capabilities")
    answered = _question(id="question:q1", _path="entities/questions/q1.md", status="answered", datasets=[])
    active = _question(id="question:q2", _path="entities/questions/q2.md", status="active", datasets=[])

    rules = _rules([dataset, answered, active])

    assert (Severity.WARN, "dataset-capabilities.provided-missing") in rules


def test_supported_hypothesis_keeps_provided_missing_warn() -> None:
    # A `supported` hypothesis can still be strengthened, so it stays LIVE — a
    # candidate reaching only it must keep warning (conservative suppression).
    dataset = _dataset(related=["hypothesis:h1"])
    dataset.pop("provided_capabilities")
    hypothesis = {
        "id": "hypothesis:h1",
        "kind": "hypothesis",
        "_path": "entities/hypotheses/h1.md",
        "status": "supported",
        "required_capabilities": [{"assay": "gene-expression"}],
    }

    rules = _rules([dataset, hypothesis])

    assert (Severity.WARN, "dataset-capabilities.provided-missing") in rules


def test_required_missing_suppressed_when_target_demand_closed() -> None:
    question = _question(status="answered")
    question.pop("required_capabilities")

    rules = _rules([_dataset(), question])

    assert (Severity.WARN, "dataset-capabilities.required-missing") not in rules


def test_required_missing_kept_when_target_live() -> None:
    question = _question(status="active")
    question.pop("required_capabilities")

    rules = _rules([_dataset(), question])

    assert (Severity.WARN, "dataset-capabilities.required-missing") in rules


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
        'kind: "dataset"\n'
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
        'kind: "question"\n'
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
