from science_model.profiles import BIO_PROFILE, CORE_PROFILE, PROJECT_SPECIFIC_PROFILE


def test_core_profile_contains_task_and_hypothesis() -> None:
    names = {kind.name for kind in CORE_PROFILE.entity_kinds}
    assert {"task", "hypothesis", "question", "claim", "experiment", "evidence"} <= names


def test_core_profile_contains_workflow_kinds() -> None:
    names = {kind.name for kind in CORE_PROFILE.entity_kinds}
    assert {"method", "workflow", "workflow-run", "workflow-step"} <= names


def test_core_profile_no_pipeline_step() -> None:
    """Guard rail: pipeline-step should never appear in core profile."""
    names = {kind.name for kind in CORE_PROFILE.entity_kinds}
    assert "pipeline-step" not in names


def test_core_profile_workflow_relations() -> None:
    relation_names = {relation.name for relation in CORE_PROFILE.relation_kinds}
    assert {"realizes", "contains", "executes", "supersedes"} <= relation_names


def test_tests_relation_accepts_workflow_run() -> None:
    tests_rel = next(relation for relation in CORE_PROFILE.relation_kinds if relation.name == "tests")
    assert "workflow-run" in tests_rel.source_kinds


def test_executes_relation_targets_workflow() -> None:
    executes = next(relation for relation in CORE_PROFILE.relation_kinds if relation.name == "executes")
    assert executes.source_kinds == ["workflow-run"]
    assert executes.target_kinds == ["workflow"]
    assert executes.predicate == "sci:executes"


def test_feeds_into_relation() -> None:
    feeds = next(relation for relation in CORE_PROFILE.relation_kinds if relation.name == "feeds_into")
    assert feeds.source_kinds == ["workflow-step"]
    assert feeds.target_kinds == ["workflow-step"]
    assert feeds.predicate == "sci:feedsInto"


def test_bio_profile_imports_core() -> None:
    assert BIO_PROFILE.imports == ["core"]


def test_project_specific_profile_is_typed_extension() -> None:
    assert PROJECT_SPECIFIC_PROFILE.strictness == "typed-extension"


def test_bio_profile_encodes_targets_protein() -> None:
    encodes = next(relation for relation in BIO_PROFILE.relation_kinds if relation.name == "encodes")
    assert encodes.target_kinds == ["protein"]
