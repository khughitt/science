from science_model.profiles.core import CORE_PROFILE
from science_model.relations import build_relation_registry, relation_allows_kinds


def test_produced_by_allows_dataset_and_data_package_to_code_file() -> None:
    registry = build_relation_registry(CORE_PROFILE.relation_kinds)
    produced_by = registry["produced_by"]
    assert relation_allows_kinds(produced_by, "dataset", "code-file")
    assert relation_allows_kinds(produced_by, "data-package", "code-file")
    # The pre-existing run-producer pairing must still be permitted.
    assert relation_allows_kinds(produced_by, "data-package", "workflow-run")
