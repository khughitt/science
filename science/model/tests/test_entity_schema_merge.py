from __future__ import annotations

from science_model.entity_schema import read_canonical_body_sections, read_effective_frontmatter_fields
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


def test_read_canonical_body_sections_returns_paper_2_0_sections() -> None:
    profile = parse_profile("science-entity-base/1.0+paper/2.0")
    sections = read_canonical_body_sections(profile)
    assert "Key Findings" in sections
    assert "Methods Summary" in sections
    assert "Limitations" in sections


def test_read_canonical_body_sections_returns_empty_when_annotation_absent() -> None:
    # base schema has no x-canonical-body-sections
    profile = parse_profile("science-entity-base/1.0")
    assert read_canonical_body_sections(profile) == []


def test_read_effective_frontmatter_fields_intersects_composed_schema_constraints() -> None:
    profile = parse_profile("science-entity-base/1.0+theme/2.0")
    fields = {field.key: field for field in read_effective_frontmatter_fields(profile)}

    assert fields["kind"].required is True
    assert fields["kind"].type == "string"
    assert fields["kind"].constraints == {"const": "theme"}

    assert fields["theme_kind"].required is True
    assert fields["theme_kind"].type == "string"
    assert fields["theme_kind"].constraints == {
        "enum": [
            "methodological",
            "biological",
            "translational",
            "evidence-quality",
            "organizational",
            "conceptual",
            "empirical",
            "domain",
        ]
    }
