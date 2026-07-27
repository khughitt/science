"""Fingerprint v1 — frozen (design §3).

The digest is an API. It is persisted in case filenames and in consumers'
`science.yaml` acceptance entries, so its observable bytes cannot change without a
new domain prefix. A future v2 normalization produces DISJOINT identities by
construction rather than silently colliding with v1.

Identity inputs, and only these: rule id, subject, and the rule-declared identity
qualifier subset. Excluded: date, model, lens, run id, producer, prose, message,
severity, evidence, line numbers, and list positions.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from science_model.audit.subjects import FindingSubject

FINDING_DOMAIN = "science.finding.v1"
FINGERPRINT_VERSION = 1

MAX_SLUG_LENGTH = 60

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")


class FingerprintError(ValueError):
    """A value cannot participate in an identity."""


def normalize_identity_value(value: Any) -> Any:
    """Permit str / bool / int and arrays of those. Nothing else.

    Floats are refused so no identity depends on float formatting; nulls are refused
    because §3 omits absent fields rather than encoding them; nested objects are
    refused so no identity depends on a nested key order.

    Public because `AuditFindingRecord` compares an occurrence's qualifiers against
    the record's identity in exactly this form. Two implementations of "the normalized
    value" would be two answers to what a finding IS. The golden vectors pin the digest
    independently, so this naming cannot move it.
    """
    if isinstance(value, bool):  # before int — bool is a subclass of int
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, (list, tuple)):
        return [normalize_identity_value(item) for item in value]
    raise FingerprintError(
        f"identity qualifier value of type {type(value).__name__} is not permitted; "
        "use str, bool, int, or an array of those (design §3)"
    )


def _prune(value: object) -> object:
    """Drop ``None`` members at EVERY level, never encode them as null (§3)."""
    if isinstance(value, Mapping):
        return {key: _prune(item) for key, item in value.items() if item is not None}
    if isinstance(value, (list, tuple)):
        return [_prune(item) for item in value]
    return value


def canonical_json(value: object) -> bytes:
    """UTF-8 JSON, keys sorted by code point, no insignificant whitespace.

    Pruning is RECURSIVE. A shallow prune would encode a nested absent field as null
    while `model_dump(exclude_none=True)` omitted it, so the same logical value would
    have two encodings depending on which path produced it.
    """
    return json.dumps(
        _prune(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def finding_fingerprint(
    *,
    rule_id: str,
    subject: FindingSubject,
    identity_qualifiers: Mapping[str, object],
) -> str:
    """The v1 digest: 64 lowercase hex characters."""
    payload = {
        "rule_id": unicodedata.normalize("NFC", rule_id),
        "subject": subject.model_dump(mode="json", exclude_none=True),
        "qualifiers": {
            key: normalize_identity_value(value)
            for key, value in sorted(identity_qualifiers.items())
        },
    }
    digest = hashlib.sha256(
        f"{FINDING_DOMAIN}\n".encode("utf-8") + canonical_json(payload)
    )
    return digest.hexdigest()


def rule_slug(rule_id: str) -> str:
    """Frozen transformation used in case filenames (design §3).

    Lowercase; `.`/`_`/any character outside [a-z0-9-] becomes `-`; runs of `-`
    collapse; leading and trailing `-` are stripped; truncated to 60 characters.
    """
    collapsed = _SLUG_STRIP_RE.sub("-", rule_id.lower()).strip("-")
    return collapsed[:MAX_SLUG_LENGTH].rstrip("-")
