from __future__ import annotations

from science_model.entity_schema.merge import MergePolicy, read_merge_policy
from science_model.entity_schema.profile import parse_profile


def test_default_merge_mode_is_replace_for_base_title() -> None:
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+paper/1.0"))
    assert policy["title"] == MergePolicy.REPLACE


def test_tags_field_is_append() -> None:
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+paper/1.0"))
    assert policy["tags"] == MergePolicy.APPEND


def test_canonical_only_dataset_fields_are_forbidden() -> None:
    # Required-from-canonical fields (derivation, access, datapackage,
    # accessions) carry merge: forbidden so overlays cannot override them.
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+dataset/1.0"))
    assert policy["derivation"] == MergePolicy.FORBIDDEN
    assert policy["datapackage"] == MergePolicy.FORBIDDEN


def test_overlay_specific_fields_are_project_only() -> None:
    # Project-only annotations live on the overlay schema, not mixins. The
    # reader treats overlay-permitted fields as project_only when invoked
    # via the overlay variant, EXCEPT those carrying an explicit
    # science:merge annotation (e.g. tags / ontology_terms = append).
    from science_model.entity_schema.merge import read_overlay_merge_policy
    policy = read_overlay_merge_policy()
    assert policy["hypothesis_links"] == MergePolicy.PROJECT_ONLY
    assert policy["relevance"] == MergePolicy.PROJECT_ONLY
    assert policy["tags"] == MergePolicy.APPEND
    assert policy["ontology_terms"] == MergePolicy.APPEND
