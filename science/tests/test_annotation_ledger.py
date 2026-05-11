# science/tests/test_annotation_ledger.py
"""Unit tests for science_tool.annotation.ledger."""
from datetime import datetime, timezone

import pytest

from science_tool.annotation import AuditLedger, Sidecar
from science_tool.annotation.ledger import (
    find_or_create_ledger,
    ledger_append_hash,
    ledger_contains_hash,
)


def _now() -> datetime:
    return datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc)


def test_find_or_create_returns_existing_ledger_unchanged() -> None:
    led = AuditLedger(
        id="ledger-gap-d-v1",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:abc",),
        modified=_now(),
    )
    sc = Sidecar(ledgers=(led,))
    new_sc, found = find_or_create_ledger(sc, "llm-audit:gap-d-v1", now=_now())
    assert found is led
    assert new_sc is sc  # no mutation needed


def test_find_or_create_creates_when_missing() -> None:
    sc = Sidecar()
    new_sc, led = find_or_create_ledger(sc, "llm-audit:gap-d-v1", now=_now())
    assert led.source == "llm-audit:gap-d-v1"
    assert led.audited_hashes == ()
    assert led.id.startswith("ledger-")
    assert "gap-d-v1" in led.id
    assert len(new_sc.ledgers) == 1
    assert new_sc.ledgers[0] is led


def test_ledger_contains_hash() -> None:
    led = AuditLedger(
        id="ledger-x",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:abc", "sha256:def"),
        modified=_now(),
    )
    assert ledger_contains_hash(led, "sha256:abc")
    assert ledger_contains_hash(led, "sha256:def")
    assert not ledger_contains_hash(led, "sha256:missing")


def test_ledger_append_hash_returns_new_ledger() -> None:
    led = AuditLedger(
        id="ledger-x",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:abc",),
        modified=datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
    )
    later = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    new_led = ledger_append_hash(led, "sha256:def", now=later)
    assert new_led.audited_hashes == ("sha256:abc", "sha256:def")
    assert new_led.modified == later
    # Original unchanged.
    assert led.audited_hashes == ("sha256:abc",)


def test_ledger_append_hash_dedupes() -> None:
    led = AuditLedger(
        id="ledger-x",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:abc",),
        modified=datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
    )
    later = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    new_led = ledger_append_hash(led, "sha256:abc", now=later)
    # Already present → no append, no modified bump.
    assert new_led is led
