from __future__ import annotations

import pytest

from science_tool.graph.skill_loads import (
    SkillLoadRecord,
    SkillLoadValidationError,
    build_skill_load_records,
    canonicalize_skill_id,
    load_skill_aliases,
    skill_load_node_uri,
    validate_skill_aliases,
    validate_skill_aliases_yaml,
)


def test_identity_excludes_reason() -> None:
    a = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="one")
    b = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="two")
    assert skill_load_node_uri(a) == skill_load_node_uri(b)
    assert a.source == "authored"
    assert "reason" not in a.identity_payload()
    assert a.payload()["reason"] == "one"


def test_identity_distinguishes_plan_and_skill() -> None:
    base = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="r")
    other_skill = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="mutational-signatures-qa", reason="r")
    other_plan = SkillLoadRecord(plan_id="plan:0002-y", canonical_skill_id="driver-selection", reason="r")
    assert skill_load_node_uri(base) != skill_load_node_uri(other_skill)
    assert skill_load_node_uri(base) != skill_load_node_uri(other_plan)


def test_node_uri_is_under_project_skill_load_namespace() -> None:
    rec = SkillLoadRecord(plan_id="plan:0001-x", canonical_skill_id="driver-selection", reason="r")
    assert "skill-load/" in str(skill_load_node_uri(rec))


def test_source_must_be_authored() -> None:
    with pytest.raises(ValueError, match="source must be 'authored'"):
        SkillLoadRecord(
            plan_id="plan:0001-x",
            canonical_skill_id="driver-selection",
            reason="r",
            source="imported",  # type: ignore[arg-type]
        )


def test_packaged_alias_table_loads() -> None:
    # The shipped table must parse and validate (it may be empty).
    assert isinstance(load_skill_aliases(), dict)


def test_validate_aliases_accepts_valid_map() -> None:
    assert validate_skill_aliases({"old-skill-name": "driver-selection"}) == {
        "old-skill-name": "driver-selection"
    }


def test_validate_aliases_rejects_chain() -> None:
    # A target that is itself a key is a chain (a -> b -> c); prohibited.
    with pytest.raises(SkillLoadValidationError, match="chain"):
        validate_skill_aliases({"a": "b", "b": "c"})


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "Bad-Case",
        "has_underscore",
        "a/b",
        "sci:skill/x",
        "-leading",
        "driver-selection\n",
    ],
)
def test_validate_aliases_rejects_non_grammar(bad: str) -> None:
    with pytest.raises(SkillLoadValidationError):
        validate_skill_aliases({bad: "driver-selection"})
    with pytest.raises(SkillLoadValidationError):
        validate_skill_aliases({"old-name": bad})


def test_validate_aliases_rejects_duplicate_keys() -> None:
    with pytest.raises(SkillLoadValidationError, match="duplicate"):
        validate_skill_aliases_yaml(
            "old-name: driver-selection\nold-name: mutational-signatures-qa\n"
        )


@pytest.mark.parametrize("text", ["", "null\n", "[]\n", "false\n", "0\n"])
def test_validate_aliases_yaml_rejects_falsey_non_mapping(text: str) -> None:
    # An empty document, null, an empty list, false, or 0 must fail — never coerce to an empty map.
    with pytest.raises(SkillLoadValidationError, match="mapping"):
        validate_skill_aliases_yaml(text)


def test_canonicalize_resolves_alias() -> None:
    assert canonicalize_skill_id("old-name", {"old-name": "driver-selection"}) == "driver-selection"


def test_canonicalize_passes_through_unknown() -> None:
    assert canonicalize_skill_id("driver-selection", {}) == "driver-selection"


@pytest.mark.parametrize(
    "bad", ["", "  ", "a/b", "sci:skill/x", "Bad", "driver-selection\n"]
)
def test_canonicalize_rejects_malformed_post_alias_id(bad: str) -> None:
    # A raw id absent from the table is treated as canonical -> must still be grammar-checked.
    with pytest.raises(SkillLoadValidationError):
        canonicalize_skill_id(bad, {})


def test_build_records_well_formed() -> None:
    records = build_skill_load_records(
        "plan:0001-x",
        [{"id": "driver-selection", "reason": "selection modeling"}],
        aliases={},
    )
    assert [(r.plan_id, r.canonical_skill_id, r.reason) for r in records] == [
        ("plan:0001-x", "driver-selection", "selection modeling")
    ]


def test_build_records_canonicalizes_via_alias() -> None:
    records = build_skill_load_records(
        "plan:0001-x",
        [{"id": "old-name", "reason": "r"}],
        aliases={"old-name": "driver-selection"},
    )
    assert records[0].canonical_skill_id == "driver-selection"


@pytest.mark.parametrize(
    "value",
    [
        "not-a-list",
        ["not-a-mapping"],
        [{"reason": "missing id"}],
        [{"id": "driver-selection"}],
        [{"id": 5, "reason": "non-string id"}],
        [{"id": "driver-selection", "reason": 5}],
        [{"id": "driver-selection", "reason": ""}],
        [{"id": "driver-selection", "reason": "   "}],
    ],
)
def test_build_records_rejects_malformed_shape(value: object) -> None:
    with pytest.raises(SkillLoadValidationError):
        build_skill_load_records("plan:0001-x", value, aliases={})


def test_build_records_rejects_literal_duplicate() -> None:
    with pytest.raises(SkillLoadValidationError, match="duplicate canonical"):
        build_skill_load_records(
            "plan:0001-x",
            [
                {"id": "driver-selection", "reason": "a"},
                {"id": "driver-selection", "reason": "b"},
            ],
            aliases={},
        )


def test_build_records_rejects_converging_aliases() -> None:
    # Two distinct raw ids that resolve to one canonical id collide.
    with pytest.raises(SkillLoadValidationError, match="duplicate canonical"):
        build_skill_load_records(
            "plan:0001-x",
            [
                {"id": "old-name", "reason": "a"},
                {"id": "driver-selection", "reason": "b"},
            ],
            aliases={"old-name": "driver-selection"},
        )
