from __future__ import annotations

from science_model.entity_schema import (
    admitted_field_names,
    read_canonical_body_sections,
    read_effective_frontmatter_fields,
)
from science_model.entity_schema.merge import MergePolicy, read_merge_policy
from science_model.entity_schema.profile import parse_profile


def test_default_merge_mode_is_replace_for_base_title() -> None:
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+paper/1.0"))
    assert policy["title"] == MergePolicy.REPLACE


def test_tags_field_is_append() -> None:
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+paper/1.0"))
    assert policy["tags"] == MergePolicy.APPEND


def test_a_mixin_that_removes_a_field_reads_as_forbidden() -> None:
    # `mixin-hypothesis-1.0` writes `"phase": false` -- a false subschema, meaning the property
    # may not appear at all. The reader assumed every property spec was an object and raised
    # AttributeError on it, so ANY caller reading a hypothesis profile's policy crashed. Nothing
    # read one until identity arbitration did, which is why a schema shipped for months could
    # not be asked its own merge policy.
    policy = read_merge_policy(parse_profile("science-entity-base/2.0+hypothesis/1.0"))
    assert policy["phase"] == MergePolicy.FORBIDDEN
    assert policy["disposition"] == MergePolicy.FORBIDDEN
    # A field the mixin does NOT remove still reads normally.
    assert policy["title"] == MergePolicy.REPLACE


def test_paper_kind_is_project_only() -> None:
    # paper_kind is project bookkeeping (research-papers / review-books set it),
    # meaningless commons-side (fb-2026-07-11-001). Like status/created/updated it
    # is modeled on the paper mixin but classified project_only so promote never
    # writes it to the canonical.
    policy = read_merge_policy(parse_profile("science-entity-base/2.0+paper/2.0"))
    assert policy["paper_kind"] == MergePolicy.PROJECT_ONLY


def test_canonical_only_dataset_fields_are_forbidden() -> None:
    # Required-from-canonical fields (derivation, access, datapackage,
    # accessions) carry merge: forbidden so overlays cannot override them.
    policy = read_merge_policy(parse_profile("science-entity-base/1.0+dataset/1.0"))
    assert policy["derivation"] == MergePolicy.FORBIDDEN
    assert policy["datapackage"] == MergePolicy.FORBIDDEN


def test_overlay_tier_is_override() -> None:
    # tier is canonical-with-override (fb-2026-07-18-005, D1): a consuming project may
    # record its own tier assessment on the overlay, shadowing the canonical value for
    # its own graph. tier + tier_rationale carry the new `override` policy.
    from science_model.entity_schema.merge import read_overlay_merge_policy

    policy = read_overlay_merge_policy()
    assert policy["tier"] == MergePolicy.OVERRIDE
    assert policy["tier_rationale"] == MergePolicy.OVERRIDE


def test_overlay_permits_project_only_paper_kind() -> None:
    # A consuming project may carry its own paper_kind on the overlay (fb-2026-07-11-001);
    # the overlay schema no longer forbids it, and it stays project_only (never promoted).
    from science_model.entity_schema.merge import read_overlay_merge_policy

    policy = read_overlay_merge_policy()
    assert policy["paper_kind"] == MergePolicy.PROJECT_ONLY


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
    assert "Methods" in sections
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


def test_admitted_field_names_excludes_what_a_later_component_forbids() -> None:
    # Composition is ORDERED: base 2.0 declares `tags`, the hypothesis mixin sets it to
    # `false`, and the composed profile therefore does not admit it. Deriving this from the
    # mixin ALONE is how `description` hid for four drafts -- it is declared by the BASE,
    # forbidden by nothing, and was on no model.
    admitted = admitted_field_names(parse_profile("science-entity-base/2.0+hypothesis/1.0"))

    assert "tags" not in admitted  # base declares it; the mixin forbids it
    assert "phase" not in admitted  # mixin-only, forbidden
    assert "description" in admitted  # base declares it; nothing forbids it
    assert "verdict" in admitted  # the mixin declares it


def test_effective_frontmatter_fields_omit_a_base_field_the_mixin_forbids() -> None:
    # `read_merge_policy` reads a `false` subschema as FORBIDDEN. This reader skipped it as
    # "not a dict", so a base field the mixin removed stayed in the output and
    # `science entity fields hypothesis` advertised six commons fields the kind rejects.
    keys = {
        field.key
        for field in read_effective_frontmatter_fields(
            parse_profile("science-entity-base/2.0+hypothesis/1.0")
        )
    }

    assert keys.isdisjoint({"contributors", "licenses", "schema_profile", "sources", "tags", "version"})
    assert "phase" not in keys
    assert "description" in keys  # the fix must not over-remove
