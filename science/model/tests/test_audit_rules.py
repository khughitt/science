import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from science_model.audit.rules import (
    FindingRule,
    FindingSection,
    RuleDeclarationError,
)
from science_model.audit.subjects import (
    EntitySubject,
    IdentifierSubject,
    ProjectSubject,
)


class FieldQualifier(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str


def _rule(**overrides) -> FindingRule:
    base = dict(
        id="dataset.cached-field-drift",
        severities={"warn"},
        subject_types={"entity"},
        identifier_namespaces=set(),
        qualifier_schema=FieldQualifier,
        identity_qualifiers=("field",),
        remediation="producer",
        remediator="fix_it",
        title="Cached dataset field drifted from source",
        section="datasets",
        display_order=340,
        default_visibility="visible",
    )
    return FindingRule(**{**base, **overrides})


def test_build_produces_a_finding_carrying_the_rule_id():
    finding = _rule().build(
        subject=EntitySubject(ref="dataset:gtex-v8"),
        severity="warn",
        qualifiers={"field": "year"},
        message="drifted",
    )
    assert finding.rule_id == "dataset.cached-field-drift"


def test_build_refuses_a_severity_outside_the_declared_set():
    with pytest.raises(RuleDeclarationError):
        _rule().build(
            subject=EntitySubject(ref="dataset:x"),
            severity="error",
            qualifiers={"field": "year"},
            message="m",
        )


def test_build_refuses_a_subject_type_outside_the_declared_set():
    with pytest.raises(RuleDeclarationError):
        _rule().build(
            subject=ProjectSubject(), severity="warn", qualifiers={"field": "y"}, message="m"
        )


def test_build_validates_qualifiers_against_the_declared_schema():
    with pytest.raises(RuleDeclarationError):
        _rule().build(
            subject=EntitySubject(ref="dataset:x"),
            severity="warn",
            qualifiers={"feild": "typo"},
            message="m",
        )


def test_identity_qualifiers_must_exist_in_the_schema():
    with pytest.raises(ValidationError, match="is not a field"):
        _rule(identity_qualifiers=("nonexistent",))


def test_identity_qualifier_types_are_constrained_at_declaration():
    class FloatQualifier(BaseModel):
        model_config = ConfigDict(extra="forbid")
        ratio: float

    with pytest.raises(ValidationError, match="only str, bool, int"):
        _rule(qualifier_schema=FloatQualifier, identity_qualifiers=("ratio",))


def test_qualifier_schema_must_forbid_unknown_fields():
    class IgnoredQualifier(BaseModel):
        field: str

    with pytest.raises(ValidationError, match="extra='forbid'"):
        _rule(qualifier_schema=IgnoredQualifier)


def test_bare_base_model_is_not_a_qualifier_schema():
    with pytest.raises(ValidationError, match="extra='forbid'"):
        _rule(
            qualifier_schema=BaseModel,
            identity_qualifiers=(),
            remediation="none",
            remediator=None,
        )


def test_rule_declaring_producer_remediation_needs_a_handler_name():
    with pytest.raises(ValidationError, match="requires a remediator name"):
        _rule(remediation="producer", remediator=None)


def test_there_is_no_opt_out_flag_for_the_remediator_check():
    # A field that disables the check would be a bypass of the check.
    assert "requires_remediator" not in FindingRule.model_fields


def test_a_remediator_without_producer_remediation_is_refused():
    with pytest.raises(ValidationError, match="declares remediation='none'"):
        _rule(remediation="none", remediator="fix_it")


def test_unordered_identity_qualifier_collections_are_refused():
    class SetQualifier(BaseModel):
        model_config = ConfigDict(extra="forbid")
        tags: frozenset[str]

    # frozenset is unordered; §3 encodes arrays in declaration order.
    with pytest.raises(ValidationError, match="only str, bool, int"):
        _rule(qualifier_schema=SetQualifier, identity_qualifiers=("tags",))


def test_ordered_identity_qualifier_collections_are_permitted():
    class ListQualifier(BaseModel):
        model_config = ConfigDict(extra="forbid")
        tags: list[str]

    _rule(qualifier_schema=ListQualifier, identity_qualifiers=("tags",))


def test_section_order_is_declared_not_derived_from_the_name():
    section = FindingSection(id="datasets", title="Datasets", section_order=300)
    assert section.section_order == 300


def test_a_qualifier_of_the_wrong_type_is_refused_not_quietly_coerced():
    """Lax validation would not CHECK the value, it would REPLACE it -- elsewhere.

    Pydantic accepts `{"count": "1"}` for an `int` field and reports `count=1`, but
    the validated model is discarded: the mapping that gets stored and fingerprinted
    still holds the string. `1` and `"1"` would then be two identities for one
    finding, both passing validation. `strict=True` is what makes it sound to
    validate one object and keep another.
    """
    class Counted(BaseModel):
        model_config = ConfigDict(extra="forbid")
        count: int

    assert Counted.model_validate({"count": "1"}).count == 1  # lax would accept it

    rule = _rule(
        qualifier_schema=Counted, identity_qualifiers=("count",),
        remediation="none", remediator=None,
    )
    with pytest.raises(RuleDeclarationError, match="qualifiers invalid"):
        rule.validate_qualifiers({"count": "1"})
    with pytest.raises(RuleDeclarationError, match="qualifiers invalid"):
        rule.build(
            subject=EntitySubject(ref="dataset:a"), severity="warn",
            qualifiers={"count": "1"}, message="m",
        )
    assert rule.build(
        subject=EntitySubject(ref="dataset:a"), severity="warn",
        qualifiers={"count": 1}, message="m",
    ).qualifiers["count"] == 1


def test_strict_validation_leaves_every_identity_bearing_type_untouched():
    """The premise of validating one object and storing another.

    If strict mode altered any permitted identity value, keeping the input would be
    keeping something the schema did not endorse. It does not: for str, bool, int, and
    lists of those, the validated value IS the input value. The `float` widening
    strict mode does keep cannot reach identity -- `_identity_type_permitted` refuses
    `float` outright, so no identity depends on float formatting.
    """
    class Mixed(BaseModel):
        model_config = ConfigDict(extra="forbid")
        name: str
        flag: bool
        count: int
        tags: list[str]

    values = {"name": "gtex", "flag": True, "count": 3, "tags": ["a", "b"]}
    validated = Mixed.model_validate(values, strict=True)
    assert validated.model_dump() == values

    rule = _rule(
        qualifier_schema=Mixed,
        identity_qualifiers=("name", "flag", "count", "tags"),
        remediation="none", remediator=None,
    )
    assert rule.identity_subset(values) == values


def test_an_identity_qualifier_must_be_stated_even_when_the_schema_defaults_it():
    # The trap: schema validation is NOT protection here. `{}` validates against a
    # field with a default and reports `field=""`, but the fingerprint would receive
    # `{}` -- a different digest from `{"field": ""}`, so identity would depend on
    # whether the producer happened to spell out a value the schema supplies anyway.
    class Defaulted(BaseModel):
        model_config = ConfigDict(extra="forbid")
        field: str = ""

    assert Defaulted.model_validate({}).field == ""     # the schema is happy

    rule = _rule(qualifier_schema=Defaulted, remediation="none", remediator=None)
    with pytest.raises(RuleDeclarationError, match="declared but absent"):
        rule.identity_subset({})
    with pytest.raises(RuleDeclarationError, match="declared but absent"):
        rule.build(
            subject=EntitySubject(ref="dataset:a"), severity="warn",
            qualifiers={}, message="m",
        )
    # Stated explicitly, it is accepted -- and it is the empty string, not nothing.
    assert rule.identity_subset({"field": ""}) == {"field": ""}


def test_omitting_and_defaulting_an_identity_qualifier_are_different_identities():
    from science_model.audit.fingerprint import finding_fingerprint

    subject = EntitySubject(ref="dataset:a")
    omitted = finding_fingerprint(
        rule_id="dataset.cached-field-drift", subject=subject, identity_qualifiers={}
    )
    explicit = finding_fingerprint(
        rule_id="dataset.cached-field-drift",
        subject=subject,
        identity_qualifiers={"field": ""},
    )
    assert omitted != explicit, (
        "if these were equal, silently dropping an absent identity qualifier would be "
        "harmless -- they are not, which is why identity_subset refuses instead"
    )


def test_identity_subset_returns_declared_qualifiers_in_declaration_order():
    rule = _rule(identity_qualifiers=("field",))
    assert rule.identity_subset({"field": "year", "extra": "ignored"}) == {
        "field": "year"
    }


def test_build_stores_identity_qualifiers_in_the_fingerprinted_nfc_form():
    class UnicodeQualifier(BaseModel):
        model_config = ConfigDict(extra="forbid")
        label: str
        note: str

    rule = _rule(
        qualifier_schema=UnicodeQualifier,
        identity_qualifiers=("label",),
        remediation="none",
        remediator=None,
    )
    finding = rule.build(
        subject=EntitySubject(ref="dataset:a"),
        severity="warn",
        qualifiers={"label": "cafe\u0301", "note": "re\u0301sume\u0301"},
        message="m",
    )

    assert finding.qualifiers["label"] == "café"
    assert finding.qualifiers["note"] == "re\u0301sume\u0301"
    assert rule.identity_subset(finding.qualifiers) == {"label": "café"}


def test_subject_type_declarations_use_the_closed_four_value_vocabulary():
    with pytest.raises(ValidationError, match="subject_types"):
        _rule(subject_types={"enttiy"})


def test_identifier_subject_rules_require_a_namespace_vocabulary():
    with pytest.raises(ValidationError, match="identifier_namespaces"):
        _rule(subject_types={"identifier"}, identifier_namespaces=set())


def test_non_identifier_rules_may_not_declare_identifier_namespaces():
    with pytest.raises(ValidationError, match="identifier_namespaces"):
        _rule(subject_types={"entity"}, identifier_namespaces={"reference"})


def test_identifier_namespace_declarations_use_the_subject_vocabulary():
    with pytest.raises(ValidationError, match="kebab-case"):
        _rule(
            subject_types={"identifier"},
            identifier_namespaces={"not_a_namespace"},
        )


def test_identifier_namespace_membership_is_unconditional():
    rule = _rule(
        subject_types={"identifier"},
        identifier_namespaces={"reference"},
    )
    with pytest.raises(RuleDeclarationError, match="namespace"):
        rule.build(
            subject=IdentifierSubject(namespace="managed-artifact", value="validate.sh"),
            severity="warn",
            qualifiers={"field": "year"},
            message="m",
        )
