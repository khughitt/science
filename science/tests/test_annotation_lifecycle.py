# science/tests/test_annotation_lifecycle.py
"""Unit tests for science_tool.annotation.lifecycle."""
from datetime import datetime, timezone

import pytest

from science_tool.annotation import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.lifecycle import mutate_status


def _open_audit_annotation() -> Annotation:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    return Annotation(
        id="a-1",
        target=target,
        bodies=(TextualBody(value="finding"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="consensus-claim-unsupported",
        source="llm-audit:gap-d-v1",
        status=Status.OPEN,
        creator="claude-opus-4-7",
        created=datetime(2026, 5, 11, 10, 0, tzinfo=timezone.utc),
        content_hash="sha256:abc",
    )


def test_ack_mutates_status_and_records_modified() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    out = mutate_status(ann, Status.ACK, actor="alice@example.com", now=later)
    assert out.status is Status.ACK
    assert out.modified == later
    assert out.modified_by == "alice@example.com"   # actor recorded as modifier
    # Other fields preserved — creator stays the original producer.
    assert out.id == ann.id
    assert out.created == ann.created
    assert out.creator == ann.creator               # NOT overwritten by actor
    assert out.content_hash == ann.content_hash


def test_ack_records_prior_state() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 11, 0, tzinfo=timezone.utc)
    out = mutate_status(ann, Status.ACK, actor="alice@example.com", now=later)
    assert len(out.prior_states) == 1
    prior = out.prior_states[0]
    assert prior.status is Status.OPEN
    assert prior.creator == ann.creator
    assert prior.created == ann.created


def test_dismiss_with_reason_sets_description() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    out = mutate_status(
        ann, Status.DISMISSED, actor="alice", now=later, reason="false positive"
    )
    assert out.status is Status.DISMISSED
    assert out.description == "false positive"


def test_fix_does_not_require_reason() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    out = mutate_status(ann, Status.FIXED, actor="alice", now=later)
    assert out.status is Status.FIXED
    assert out.description is None


def test_cannot_mutate_to_open() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="cannot transition to 'open'"):
        mutate_status(ann, Status.OPEN, actor="alice", now=later)


def test_cannot_mutate_already_terminal() -> None:
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    out = mutate_status(ann, Status.ACK, actor="alice", now=later)
    even_later = datetime(2026, 5, 11, 13, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="already in terminal status"):
        mutate_status(out, Status.DISMISSED, actor="bob", now=even_later)


def test_supersede_is_allowed_from_any_state() -> None:
    # Selector loss can fire even after ack/fixed/dismissed.
    ann = _open_audit_annotation()
    later = datetime(2026, 5, 11, 12, 0, tzinfo=timezone.utc)
    acked = mutate_status(ann, Status.ACK, actor="alice", now=later)
    even_later = datetime(2026, 5, 11, 13, 0, tzinfo=timezone.utc)
    superseded = mutate_status(acked, Status.SUPERSEDED, actor="tool:verify", now=even_later)
    assert superseded.status is Status.SUPERSEDED
    # Two prior states now.
    assert len(superseded.prior_states) == 2
