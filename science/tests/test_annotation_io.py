# science/tests/test_annotation_io.py
"""Unit tests for science_tool.annotation.io (parse half — Task 4)."""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from science_tool.annotation import (
    Annotation,
    AuditLedger,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.io import read_sidecar

FIXTURE = Path(__file__).parent / "_fixtures/annotation/citation-audit-pilot.anno.trig"


def test_read_sidecar_returns_sidecar() -> None:
    sc = read_sidecar(FIXTURE)
    assert isinstance(sc, Sidecar)


def test_read_sidecar_finds_two_annotations() -> None:
    sc = read_sidecar(FIXTURE)
    assert len(sc.annotations) == 2


def test_read_sidecar_finds_one_ledger() -> None:
    sc = read_sidecar(FIXTURE)
    assert len(sc.ledgers) == 1


def test_read_sidecar_finds_one_shared_target() -> None:
    sc = read_sidecar(FIXTURE)
    assert len(sc.shared_targets) == 1
    target = sc.shared_targets[0]
    assert target.id == "t-7f3a"
    assert target.source == "citation-audit-pilot.md"
    assert target.selector.exact == "category theory is the right framework"


def test_audit_annotation_parses() -> None:
    sc = read_sidecar(FIXTURE)
    by_id = {a.id: a for a in sc.annotations}
    a = by_id["a-7f3a"]
    assert a.annotation_type == "consensus-claim-unsupported"
    assert a.source == "llm-audit:gap-d-v1"
    assert a.status is Status.ACK
    assert a.motivation is Motivation.CLASSIFYING
    assert a.content_hash == "sha256:1f9dab"
    assert a.creator == "claude-opus-4-7"          # original producer preserved
    assert a.modified_by == "keith.hughitt@gmail.com"   # mutating actor
    assert a.created == datetime(2026, 5, 10, 14, 23, tzinfo=timezone.utc)
    assert a.modified == datetime(2026, 5, 10, 15, 1, tzinfo=timezone.utc)
    assert a.description == "Standard textbook framing; no source needed."
    assert a.target.id == "t-7f3a"  # references shared target by ID
    assert a.target.source == "citation-audit-pilot.md"  # bare relative path, not file URI


def test_audit_annotation_has_prior_state() -> None:
    sc = read_sidecar(FIXTURE)
    a = next(a for a in sc.annotations if a.id == "a-7f3a")
    assert len(a.prior_states) == 1
    prior = a.prior_states[0]
    assert prior.status is Status.OPEN
    assert prior.creator == "claude-opus-4-7"
    assert prior.created == datetime(2026, 5, 10, 14, 23, tzinfo=timezone.utc)


def test_comment_annotation_parses() -> None:
    sc = read_sidecar(FIXTURE)
    a = next(a for a in sc.annotations if a.id == "a-7f3b")
    assert a.annotation_type == "comment"
    assert a.source == "human:keith.hughitt@gmail.com"
    assert a.status is Status.OPEN
    assert a.motivation is Motivation.COMMENTING
    assert a.content_hash is None  # comment source omits hash
    body = a.bodies[0]
    assert isinstance(body, TextualBody)
    assert "Spivak" in body.value


def test_ledger_parses() -> None:
    sc = read_sidecar(FIXTURE)
    led = sc.ledgers[0]
    assert led.id == "ledger-gap-d-v1"
    assert led.source == "llm-audit:gap-d-v1"
    assert led.audited_hashes == ("sha256:1f9dab", "sha256:abc1", "sha256:def2")


def test_read_sidecar_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        read_sidecar(Path("/nonexistent/path.anno.trig"))


def test_empty_sidecar_returns_empty() -> None:
    # An empty TriG file (no annotations or ledgers) is valid.
    sc = read_sidecar(FIXTURE.parent / "empty.anno.trig")
    assert sc.annotations == ()
    assert sc.ledgers == ()
    assert sc.shared_targets == ()


def test_malformed_sidecar_missing_required_field_raises() -> None:
    # An annotation missing sci:annotationType MUST raise, not silently
    # produce annotation_type="None" or "".
    with pytest.raises(ValueError, match="missing required"):
        read_sidecar(FIXTURE.parent / "malformed-missing-type.anno.trig")
