import yaml

from science_model.profiles import CORE_PROFILE, LOCAL_PROFILE, load_shared_profile


def test_core_profile_contains_task_and_hypothesis() -> None:
    names = {kind.name for kind in CORE_PROFILE.entity_kinds}
    assert {"task", "hypothesis", "question", "proposition", "experiment", "observation"} <= names


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


def test_local_profile_is_typed_extension() -> None:
    assert LOCAL_PROFILE.strictness == "typed-extension"


def test_load_shared_profile_from_yaml(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    manifest = {
        "name": "shared",
        "imports": ["core"],
        "strictness": "curated",
        "entity_kinds": [
            {
                "name": "protein-complex",
                "canonical_prefix": "protein-complex",
                "layer": "layer/shared",
                "description": "Shared protein complex kind.",
            },
        ],
        "relation_kinds": [],
    }
    manifest_path = tmp_path / "manifest.yaml"
    manifest_path.write_text(yaml.dump(manifest), encoding="utf-8")
    profile = load_shared_profile(manifest_path)
    assert profile is not None
    assert profile.name == "shared"
    assert profile.strictness == "curated"
    assert len(profile.entity_kinds) == 1
    assert profile.entity_kinds[0].name == "protein-complex"


def test_core_profile_has_data_package_kind() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "data-package" in kind_names


def test_core_profile_has_produced_by_relation() -> None:
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "produced_by" in rel_names


def test_produced_by_connects_data_package_to_workflow_run() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "produced_by")
    assert "data-package" in rel.source_kinds
    assert "workflow-run" in rel.target_kinds


def test_core_profile_no_artifact_kind() -> None:
    """artifact entity kind is retired; must not appear in core profile."""
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert "artifact" not in kind_names


def test_core_profile_no_derived_from_relation() -> None:
    """derived_from relation is retired alongside artifact."""
    rel_names = {r.name for r in CORE_PROFILE.relation_kinds}
    assert "derived_from" not in rel_names


def test_core_profile_has_new_entity_kinds() -> None:
    kind_names = {k.name for k in CORE_PROFILE.entity_kinds}
    assert {"proposition", "observation", "finding", "interpretation", "story", "paper"} <= kind_names


def test_supports_uses_observation_and_proposition() -> None:
    supports = next(r for r in CORE_PROFILE.relation_kinds if r.name == "supports")
    assert set(supports.source_kinds) == {"observation", "proposition"}
    assert set(supports.target_kinds) == {"proposition", "hypothesis"}


def test_disputes_uses_observation_and_proposition() -> None:
    disputes = next(r for r in CORE_PROFILE.relation_kinds if r.name == "disputes")
    assert set(disputes.source_kinds) == {"observation", "proposition"}
    assert set(disputes.target_kinds) == {"proposition", "hypothesis"}


def test_addresses_relation() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "addresses")
    assert rel.source_kinds == ["question"]
    assert rel.target_kinds == ["proposition"]
    assert rel.predicate == "sci:addresses"


def test_grounded_by_relation() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "grounded_by")
    assert "finding" in rel.source_kinds
    assert "data-package" in rel.target_kinds
    assert "workflow-run" in rel.target_kinds
    assert rel.predicate == "sci:groundedBy"


def test_synthesizes_relation() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "synthesizes")
    assert rel.source_kinds == ["story"]
    assert rel.target_kinds == ["interpretation"]
    assert rel.predicate == "sci:synthesizes"


def test_organized_by_relation() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "organized_by")
    assert rel.source_kinds == ["story"]
    assert set(rel.target_kinds) == {"question", "hypothesis"}
    assert rel.predicate == "sci:organizedBy"


def test_comprises_relation() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "comprises")
    assert rel.source_kinds == ["paper"]
    assert rel.target_kinds == ["story"]
    assert rel.predicate == "sci:comprises"


def test_grounds_relation() -> None:
    rel = next(r for r in CORE_PROFILE.relation_kinds if r.name == "grounds")
    assert rel.source_kinds == ["workflow-run"]
    assert rel.target_kinds == ["observation"]
    assert rel.predicate == "sci:grounds"


def test_contains_broadened() -> None:
    contains = next(r for r in CORE_PROFILE.relation_kinds if r.name == "contains")
    assert "workflow" in contains.source_kinds
    assert "finding" in contains.source_kinds
    assert "interpretation" in contains.source_kinds
    assert "workflow-step" in contains.target_kinds
    assert "proposition" in contains.target_kinds
    assert "observation" in contains.target_kinds


def test_load_shared_profile_missing(tmp_path: object) -> None:
    from pathlib import Path

    assert isinstance(tmp_path, Path)
    profile = load_shared_profile(tmp_path / "missing.yaml")
    assert profile is None
