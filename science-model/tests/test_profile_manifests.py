from science_model.profiles import BIO_PROFILE, CORE_PROFILE, PROJECT_SPECIFIC_PROFILE


def test_core_profile_contains_task_and_hypothesis() -> None:
    names = {kind.name for kind in CORE_PROFILE.entity_kinds}
    assert {"task", "hypothesis", "question", "claim"} <= names


def test_bio_profile_imports_core() -> None:
    assert BIO_PROFILE.imports == ["core"]


def test_project_specific_profile_is_typed_extension() -> None:
    assert PROJECT_SPECIFIC_PROFILE.strictness == "typed-extension"
