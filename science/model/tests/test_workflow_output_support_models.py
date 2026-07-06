from __future__ import annotations

import pytest
from pydantic import ValidationError
from science_model.packages.schema import WorkflowOutput, WorkflowOutputSupport


def _output(**support_kw) -> dict:
    base = {
        "slug": "survival-os-combined",
        "title": "Survival OS combined meta-analysis scores",
        "resource_names": ["survival_os_combined_gene", "survival_os_combined_gene_set"],
    }
    if support_kw:
        base["support"] = support_kw
    return base


def test_support_absent_leaves_field_none() -> None:
    output = WorkflowOutput.model_validate(_output())
    assert output.support is None


def test_support_block_parses() -> None:
    output = WorkflowOutput.model_validate(_output(unit="dataset", min=3, expected=5))
    assert output.support is not None
    assert output.support.unit == "dataset"
    assert output.support.min == 3
    assert output.support.expected == 5


def test_support_expected_optional() -> None:
    output = WorkflowOutput.model_validate(_output(unit="cohort", min=2))
    assert output.support is not None
    assert output.support.expected is None


def test_support_roundtrips_json() -> None:
    output = WorkflowOutput.model_validate(_output(unit="dataset", min=3, expected=5))
    dumped = output.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["support"] == {"unit": "dataset", "min": 3, "expected": 5}


def test_support_roundtrips_json_without_expected() -> None:
    output = WorkflowOutput.model_validate(_output(unit="cohort", min=2))
    dumped = output.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["support"] == {"unit": "cohort", "min": 2}
    assert "expected" not in dumped["support"]


def test_support_min_required_when_block_present() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="dataset", expected=5))


def test_support_min_must_be_ge_one() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="dataset", min=0))


def test_support_expected_below_min_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="dataset", min=5, expected=3))


def test_support_unknown_unit_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="gene", min=3))


def test_support_stray_key_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutputSupport.model_validate({"unit": "dataset", "min": 3, "floor": 2})


def test_support_min_must_be_strict_int() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(_output(unit="dataset", min=3.0))


def test_support_requires_non_empty_resource_names() -> None:
    with pytest.raises(ValidationError):
        WorkflowOutput.model_validate(
            {"slug": "x", "title": "X", "resource_names": [], "support": {"unit": "dataset", "min": 3}}
        )
