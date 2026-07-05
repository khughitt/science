from __future__ import annotations

from science_tool.datasets.semantics import (
    dataset_class_for,
    reproducibility_class_for,
    repro_meets_bar,
    runtime_state_for,
)


def test_missing_dataset_class_defaults_to_deposit() -> None:
    assert dataset_class_for({"kind": "dataset", "id": "dataset:x"}) == "deposit"


def test_source_class_reference_does_not_imply_runtime_reference() -> None:
    fm = {
        "kind": "dataset",
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
    assert (
        runtime_state_for(
            {
                "dataset_class": "deposit",
                "access": {
                    "level": "public",
                    "verified": False,
                    "exception": {"mode": "expanded-to-acquire"},
                },
            }
        )
        == "blocked-access"
    )


def _fm(obtain, execution, extract):
    return {
        "access": {
            "reproducibility": {
                "obtainability": obtain,
                "execution": execution,
                "extractability": extract,
            }
        }
    }


def test_public_download_is_third_party_reproducible():
    cls, _ = reproducibility_class_for(_fm("public", "local", "full-dataset"))
    assert cls == "third-party-reproducible"


def test_self_service_dua_download_is_credentialed():
    cls, _ = reproducibility_class_for(_fm("self-service-dua", "local", "analysis-dataset"))
    assert cls == "credentialed-reproducible"


def test_n3c_shape_is_trust_based_output():
    cls, gap = reproducibility_class_for(_fm("approved-project", "trusted-environment", "aggregate-reviewed"))
    assert cls == "trust-based-output"
    assert "aggregate-reviewed" in gap


def test_custodian_run_is_insider_only_before_trust_based():
    # custodian-run + aggregate outputs must NOT be credited as trust-based
    cls, _ = reproducibility_class_for(_fm("named-collaboration", "custodian-run", "aggregate-reviewed"))
    assert cls == "insider-only"


def test_insider_only_wins_the_genuine_race_with_trust_based():
    # named-collaboration satisfies the insider-only rule; trusted-environment + aggregate-reviewed
    # simultaneously satisfies the trust-based-output rule. insider-only must win because it is
    # checked first. (This is the real ordering guard; the custodian-run case above never races.)
    cls, _ = reproducibility_class_for(_fm("named-collaboration", "trusted-environment", "aggregate-reviewed"))
    assert cls == "insider-only"


def test_any_unknown_control_yields_unknown():
    cls, _ = reproducibility_class_for(_fm("public", "unknown", "full-dataset"))
    assert cls == "unknown"


def test_absent_reproducibility_block_is_unknown():
    assert reproducibility_class_for({"access": {"level": "public", "verified": True}})[0] == "unknown"
    assert reproducibility_class_for({})[0] == "unknown"


def test_repro_meets_bar_ordering():
    assert repro_meets_bar("third-party-reproducible", "trust-based-output") is True
    assert repro_meets_bar("insider-only", "trust-based-output") is False
