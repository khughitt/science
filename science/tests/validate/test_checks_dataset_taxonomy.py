from __future__ import annotations

from science_tool.validate.checks.dataset_taxonomy import evaluate_dataset_taxonomy
from science_tool.validate.result import Severity


def _rules(datasets: list[dict]) -> list[tuple[Severity, str]]:
    return [(r.severity, r.rule) for r in evaluate_dataset_taxonomy(datasets)]


def _ds(**kw) -> dict:
    base = {"type": "dataset", "id": "dataset:x", "_path": "doc/datasets/x.md"}
    base.update(kw)
    return base


def test_undeclared_source_class_warns() -> None:
    rules = _rules([_ds(origin="external")])
    assert (Severity.WARN, "taxonomy.source-class-undeclared") in rules


def test_observational_clean_passes_silently() -> None:
    rules = _rules([_ds(origin="external", source_class="observational")])
    assert rules == []


def test_invalid_source_class_errors() -> None:
    rules = _rules([_ds(origin="external", source_class="curated")])
    assert (Severity.ERROR, "taxonomy.source-class-invalid") in rules


def test_derived_without_kind_errors() -> None:
    rules = _rules([_ds(origin="external", source_class="derived")])
    assert (Severity.ERROR, "taxonomy.derived-kind-missing") in rules


def test_derived_with_bad_kind_errors() -> None:
    rules = _rules([_ds(origin="external", source_class="derived", derived_kind="guess")])
    assert (Severity.ERROR, "taxonomy.derived-kind-invalid") in rules


def test_derived_kind_misplaced_errors() -> None:
    rules = _rules([_ds(origin="external", source_class="observational", derived_kind="aggregate")])
    assert (Severity.ERROR, "taxonomy.derived-kind-misplaced") in rules


def test_external_derived_without_upstream_provenance_warns() -> None:
    rules = _rules([_ds(origin="external", source_class="derived", derived_kind="model_output")])
    assert (Severity.WARN, "taxonomy.external-derived-no-provenance") in rules


def test_external_derived_with_training_usage_no_provenance_warn() -> None:
    ds = _ds(
        origin="external",
        source_class="derived",
        derived_kind="model_output",
        dataset_usage=[{"ref": "dataset:corpus", "role": "training", "overlap": "full"}],
    )
    rules = [r for sev, r in _rules([ds])]
    assert "taxonomy.external-derived-no-provenance" not in rules


def test_malformed_dataset_usage_errors() -> None:
    ds = _ds(origin="external", source_class="observational", dataset_usage=[{"role": "analyzed"}])
    rules = _rules([ds])
    assert (Severity.ERROR, "taxonomy.dataset-usage-malformed") in rules


def test_dataset_usage_bad_role_errors() -> None:
    ds = _ds(
        origin="external",
        source_class="observational",
        dataset_usage=[{"ref": "dataset:x", "role": "consulted"}],
    )
    rules = _rules([ds])
    assert (Severity.ERROR, "taxonomy.dataset-usage-malformed") in rules


def test_non_list_dataset_usage_errors() -> None:
    # A single mapping authored without the leading list `-` is a defect, not "empty".
    ds = _ds(
        origin="external",
        source_class="observational",
        dataset_usage={"ref": "dataset:x", "role": "training"},
    )
    assert (Severity.ERROR, "taxonomy.dataset-usage-malformed") in _rules([ds])


def test_non_dataset_ignored() -> None:
    assert _rules([{"type": "paper", "id": "paper:p", "_path": "x"}]) == []


def test_kind_dataset_without_type_is_checked() -> None:
    # `kind` is the canonical field; a dataset declaring only kind must be evaluated.
    rules = _rules([{"kind": "dataset", "id": "dataset:k", "_path": "doc/datasets/k.md"}])
    assert (Severity.WARN, "taxonomy.source-class-undeclared") in rules
