import pytest

from science_model.audit.fingerprint import (
    FingerprintError,
    canonical_json,
    finding_fingerprint,
    rule_slug,
)
from science_model.audit.subjects import (
    EntitySubject,
    IdentifierSubject,
    PathSubject,
    ProjectSubject,
)


# Golden vectors. These bytes are an API: they are persisted in case filenames and in
# consumers' science.yaml. Changing normalization MUST break this test.
#
# Each entry pins BOTH the canonical byte string AND the digest. The digests were
# produced by coreutils `sha256sum`, NOT by this implementation — see Step 4 for the
# exact command. An implementation checked against its own output is its own oracle
# and can only ever confirm that it is self-consistent.
GOLDEN = (
    (
        "entity",
        "dataset.cached-field-drift",
        EntitySubject(ref="dataset:gtex-v8"),
        {"field": "year"},
        '{"qualifiers":{"field":"year"},"rule_id":"dataset.cached-field-drift",'
        '"subject":{"ref":"dataset:gtex-v8","type":"entity"}}',
        "4c88cbe7b7951a0f68c084ab403a662440ab8432958501e2dc873a9a0469cf9f",
    ),
    (
        "path-with-pointer",
        "tags.lingering",
        PathSubject(path="doc/x.md", pointer="frontmatter.tags"),
        {},
        '{"qualifiers":{},"rule_id":"tags.lingering","subject":{"path":"doc/x.md",'
        '"pointer":"frontmatter.tags","type":"path"}}',
        "e21c72e84b7f48fdca1ae72fafb38d92b1611d7f20e87223d0e3bfc03f1abc3f",
    ),
    (
        "project-two-qualifiers",
        "layered-claim.coverage-incomplete",
        ProjectSubject(),
        {"coverage": "proposition_claim_layer", "threshold": 1},
        '{"qualifiers":{"coverage":"proposition_claim_layer","threshold":1},'
        '"rule_id":"layered-claim.coverage-incomplete","subject":{"type":"project"}}',
        "c0e10a4a0c9647f84c922addd40c7356ef6e78a2639b417d063d7d6926f9bd17",
    ),
    (
        "identifier-unicode-nfc",
        "refs.unresolved",
        IdentifierSubject(namespace="REFERENCE", value="cafe\u0301"),
        {"key": "résumé"},
        '{"qualifiers":{"key":"résumé"},"rule_id":"refs.unresolved",'
        '"subject":{"namespace":"reference","type":"identifier","value":"café"}}',
        # Independent oracle:
        # printf '%s' $'science.finding.v1\n<expected-bytes>' | sha256sum
        "b472390a7dd4b213e44a693b368276c7138bf0748dc92c11530447edf34b56ac",
    ),
)


def test_canonical_json_sorts_keys_and_omits_whitespace():
    assert canonical_json({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def test_canonical_json_omits_absent_fields_rather_than_nulling_them():
    assert canonical_json({"a": 1, "b": None}) == b'{"a":1}'


def test_canonical_json_preserves_array_order():
    assert canonical_json({"a": ["z", "y"]}) == b'{"a":["z","y"]}'


def test_fingerprint_is_64_lowercase_hex():
    digest = finding_fingerprint(
        rule_id="refs.unresolved",
        subject=IdentifierSubject(namespace="reference", value="dataset:missing"),
        identity_qualifiers={},
    )
    assert len(digest) == 64
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_fingerprint_is_stable_across_qualifier_insertion_order():
    a = finding_fingerprint(
        rule_id="r", subject=ProjectSubject(), identity_qualifiers={"x": 1, "y": 2}
    )
    b = finding_fingerprint(
        rule_id="r", subject=ProjectSubject(), identity_qualifiers={"y": 2, "x": 1}
    )
    assert a == b


def test_fingerprint_differs_by_subject_variant_for_the_same_string():
    path = finding_fingerprint(
        rule_id="r", subject=PathSubject(path="a.md"), identity_qualifiers={}
    )
    ident = finding_fingerprint(
        rule_id="r",
        subject=IdentifierSubject(namespace="reference", value="a.md"),
        identity_qualifiers={},
    )
    assert path != ident


def test_fingerprint_rejects_float_null_and_nested_qualifiers():
    for bad in ({"x": 1.5}, {"x": None}, {"x": {"nested": 1}}):
        with pytest.raises(FingerprintError):
            finding_fingerprint(
                rule_id="r", subject=ProjectSubject(), identity_qualifiers=bad
            )


def test_fingerprint_accepts_str_bool_int_and_arrays_of_those():
    finding_fingerprint(
        rule_id="r",
        subject=ProjectSubject(),
        identity_qualifiers={"s": "a", "b": True, "i": 3, "l": ["a", "b"]},
    )


def test_fingerprint_normalizes_identity_strings_recursively():
    composed = finding_fingerprint(
        rule_id="refs.unresolved",
        subject=IdentifierSubject(namespace="reference", value="café"),
        identity_qualifiers={"labels": ["résumé"]},
    )
    decomposed = finding_fingerprint(
        rule_id="refs.unresolved",
        subject=IdentifierSubject(namespace="reference", value="cafe\u0301"),
        identity_qualifiers={"labels": ["re\u0301sume\u0301"]},
    )
    assert decomposed == composed


def test_unencodable_identity_qualifier_uses_fingerprint_error():
    with pytest.raises(FingerprintError, match="UTF-8"):
        finding_fingerprint(
            rule_id="refs.unresolved",
            subject=ProjectSubject(),
            identity_qualifiers={"key": "\ud800"},
        )


def test_rule_slug_is_frozen():
    assert rule_slug("dataset.cached-field-drift") == "dataset-cached-field-drift"
    assert rule_slug("prose_lints.hit") == "prose-lints-hit"
    assert rule_slug("a..__b") == "a-b"
    assert rule_slug("-x-") == "x"
    assert len(rule_slug("a" * 100)) == 60


@pytest.mark.parametrize(
    ("name", "rule_id", "subject", "quals", "expected_bytes", "expected_digest"), GOLDEN
)
def test_canonical_bytes_are_frozen(
    name, rule_id, subject, quals, expected_bytes, expected_digest
):
    """Pin the ENCODING independently of the hash, so a break says which one moved."""
    payload = {
        "rule_id": rule_id,
        "subject": subject.model_dump(mode="json", exclude_none=True),
        "qualifiers": quals,
    }
    assert canonical_json(payload).decode("utf-8") == expected_bytes, (
        f"golden vector {name!r}: canonical encoding changed. Fingerprint v1 is frozen "
        "(design §3); a deliberate change requires a v2 domain prefix, not an edit."
    )


@pytest.mark.parametrize(
    ("name", "rule_id", "subject", "quals", "expected_bytes", "expected_digest"), GOLDEN
)
def test_golden_digests_match_an_independent_oracle(
    name, rule_id, subject, quals, expected_bytes, expected_digest
):
    """The expected digests came from coreutils `sha256sum`, not from this code."""
    actual = finding_fingerprint(
        rule_id=rule_id, subject=subject, identity_qualifiers=quals
    )
    assert actual == expected_digest, (
        f"golden vector {name!r}: digest changed. Fingerprint v1 is frozen (design §3)."
    )
