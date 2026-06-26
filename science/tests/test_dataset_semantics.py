from __future__ import annotations

from science_tool.datasets.semantics import dataset_class_for, runtime_state_for


def test_missing_dataset_class_defaults_to_deposit() -> None:
    assert dataset_class_for({"type": "dataset", "id": "dataset:x"}) == "deposit"


def test_source_class_reference_does_not_imply_runtime_reference() -> None:
    fm = {
        "type": "dataset",
        "id": "dataset:grch38",
        "source_class": "reference",
        "datapackage": "data/grch38/datapackage.yaml",
    }

    assert dataset_class_for(fm) == "deposit"
    assert runtime_state_for(fm) == "runnable"


def test_reference_and_pointer_classes_are_non_runtime_states() -> None:
    assert runtime_state_for({"dataset_class": "reference", "access": {"verified": True}}) == "reference-only"
    assert runtime_state_for({"dataset_class": "pointer", "access": {"verified": True}}) == "pointer-only"


def test_deposit_with_runtime_artifact_is_runnable_before_access_state() -> None:
    fm = {
        "dataset_class": "deposit",
        "local_path": "data/raw.tsv",
        "access": {
            "level": "controlled",
            "verified": False,
            "exception": {"mode": "scope-reduced"},
        },
    }

    assert runtime_state_for(fm) == "runnable"


def test_verified_deposit_without_runtime_artifact_is_unstaged() -> None:
    fm = {"dataset_class": "deposit", "access": {"level": "public", "verified": True}}

    assert runtime_state_for(fm) == "unstaged-deposit"


def test_unverified_or_exception_deposit_is_blocked_access() -> None:
    assert runtime_state_for({"dataset_class": "deposit", "access": {"level": "public", "verified": False}}) == (
        "blocked-access"
    )
    assert runtime_state_for(
        {
            "dataset_class": "deposit",
            "access": {
                "level": "public",
                "verified": False,
                "exception": {"mode": "expanded-to-acquire"},
            },
        }
    ) == "blocked-access"
