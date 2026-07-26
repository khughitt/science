from __future__ import annotations

from typing import Any

from science_model.entity_schema import (
    admitted_field_names,
    read_canonical_body_sections,
    read_effective_frontmatter_fields,
)
from science_model.entity_schema.merge import MergePolicy, read_merge_policy
from science_model.entity_schema.profile import (
    ProfileComponent,
    ProfileString,
    _MIXIN_VERSION_BY_GENERATION,
    default_profile_for_kind,
    parse_profile,
)


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
    # Composition is `allOf`: base 2.0 declares `tags`, the hypothesis mixin sets it to
    # `false`, and the composed profile therefore does not admit it -- regardless of which
    # component's `false` comes first or last. Deriving this from the mixin ALONE is how
    # `description` hid for four drafts -- it is declared by the BASE, forbidden by nothing,
    # and was on no model.
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


class _FakeLoader:
    """A minimal stand-in for `SchemaLoader` over hand-written schemas, keyed by component."""

    def __init__(self, schemas: dict[tuple[str, str], dict[str, Any]]) -> None:
        self._schemas = schemas

    def load(self, component: ProfileComponent) -> dict[str, Any]:
        return self._schemas[(component.name, component.version)]


def _three_component_forbid_then_redeclare_profile() -> tuple[ProfileString, _FakeLoader]:
    # base declares `widget`; mixin forbids it with a `false` subschema; an EXTENSION -- which
    # comes after the mixin in composition order -- re-declares it. Under `allOf` this must still
    # be forbidden: a `false` anywhere in the allOf rejects the property regardless of position.
    # An order-sensitive reader that discards-then-re-adds (or pops-then-re-adds) per component
    # would instead see the extension's re-declaration as the last word and admit `widget` --
    # exactly the defect this branch exists to close, one component later.
    base = ProfileComponent("fake-base", "1.0")
    mixin = ProfileComponent("fake-mixin", "1.0")
    extension = ProfileComponent("fake-ext", "1.0")
    profile = ProfileString(base=base, mixin=mixin, extensions=(extension,))
    loader = _FakeLoader(
        {
            (base.name, base.version): {"properties": {"widget": {"type": "string"}}},
            (mixin.name, mixin.version): {"properties": {"widget": False}},
            (extension.name, extension.version): {"properties": {"widget": {"type": "string"}}},
        }
    )
    return profile, loader


def test_admitted_field_names_is_order_insensitive_to_a_later_redeclaration() -> None:
    profile, loader = _three_component_forbid_then_redeclare_profile()
    admitted = admitted_field_names(profile, loader=loader)
    assert "widget" not in admitted, (
        "a component AFTER the one that forbids `widget` re-declared it, and the reader admitted "
        "it anyway -- allOf forbids regardless of position"
    )


def test_read_effective_frontmatter_fields_is_order_insensitive_to_a_later_redeclaration() -> None:
    profile, loader = _three_component_forbid_then_redeclare_profile()
    keys = {field.key for field in read_effective_frontmatter_fields(profile, loader=loader)}
    assert "widget" not in keys, (
        "a component AFTER the one that forbids `widget` re-declared it, and the reader admitted "
        "it anyway -- allOf forbids regardless of position"
    )


def test_the_two_readers_agree_on_every_live_profile() -> None:
    # Two readers of one fact -- "what does this composed profile admit" -- that could disagree is
    # exactly the defect class this branch exists to close. They agree on all 10 live profiles
    # today; this pins that down instead of leaving it merely observed.
    #
    # Scope note: a `true` property subschema is a DELIBERATE, KNOWN divergence and is NOT covered
    # here. `admitted_field_names` admits it (any non-`False` spec adds the name);
    # `read_effective_frontmatter_fields` drops it (`isinstance(spec, dict)` is False for `True`).
    # No shipped schema uses a bare `true` subschema, so no live profile exercises this, and this
    # test does not manufacture one -- that is a separate concern from "do the two readers agree
    # on what actually ships."
    for generation, kinds in _MIXIN_VERSION_BY_GENERATION.items():
        for kind in kinds:
            profile = default_profile_for_kind(kind, generation=generation)
            admitted = admitted_field_names(profile)
            effective = {field.key for field in read_effective_frontmatter_fields(profile)}
            assert admitted == effective, (
                f"generation {generation} kind {kind!r}: admitted_field_names has "
                f"{sorted(admitted - effective)} that read_effective_frontmatter_fields lacks, "
                f"and read_effective_frontmatter_fields has {sorted(effective - admitted)} that "
                f"admitted_field_names lacks"
            )
