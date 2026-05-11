# science/tests/test_annotation_model.py
"""Unit tests for science_tool.annotation.model."""
from datetime import datetime, timezone

import pytest

from science_tool.annotation.model import (
    Annotation,
    AuditLedger,
    Motivation,
    Sidecar,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def test_status_values() -> None:
    assert {s.value for s in Status} == {
        "open", "ack", "fixed", "dismissed", "superseded"
    }


def test_motivation_values() -> None:
    assert {m.value for m in Motivation} == {
        "commenting", "tagging", "classifying", "linking",
        "questioning", "identifying", "highlighting",
    }


def test_text_quote_selector_is_frozen() -> None:
    sel = TextQuoteSelector(exact="x", prefix="a ", suffix=" b")
    with pytest.raises(AttributeError):
        sel.exact = "y"  # type: ignore[misc]


def test_specific_resource_holds_source_and_selector() -> None:
    sel = TextQuoteSelector(exact="x", prefix="a ", suffix=" b")
    sr = SpecificResource(source="foo.md", selector=sel)
    assert sr.source == "foo.md"
    assert sr.selector is sel


def test_annotation_minimal_construction() -> None:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    body = TextualBody(value="comment")
    ann = Annotation(
        id="a-1",
        target=target,
        bodies=(body,),
        motivation=Motivation.COMMENTING,
        annotation_type="comment",
        source="human:test",
        status=Status.OPEN,
        creator="test",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
    )
    assert ann.id == "a-1"
    assert ann.bodies == (body,)
    assert ann.content_hash is None  # optional for human source


def test_annotation_audit_source_requires_content_hash() -> None:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    body = TextualBody(value="finding")
    with pytest.raises(ValueError, match="content_hash required"):
        Annotation(
            id="a-2",
            target=target,
            bodies=(body,),
            motivation=Motivation.CLASSIFYING,
            annotation_type="consensus-claim-unsupported",
            source="llm-audit:gap-d-v1",
            status=Status.OPEN,
            creator="claude-opus-4-7",
            created=datetime(2026, 5, 11, tzinfo=timezone.utc),
            content_hash=None,
        )


def test_annotation_modified_required_when_status_changed() -> None:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    body = TextualBody(value="finding")
    with pytest.raises(ValueError, match="modified required"):
        Annotation(
            id="a-3",
            target=target,
            bodies=(body,),
            motivation=Motivation.CLASSIFYING,
            annotation_type="consensus-claim-unsupported",
            source="llm-audit:gap-d-v1",
            status=Status.ACK,           # not the initial state
            creator="claude-opus-4-7",
            created=datetime(2026, 5, 11, tzinfo=timezone.utc),
            content_hash="sha256:abc",
            modified=None,                # but no modified timestamp
            modified_by="alice",
        )


def test_annotation_modified_by_required_when_modified_set() -> None:
    sel = TextQuoteSelector(exact="x", prefix="", suffix="")
    target = SpecificResource(source="foo.md", selector=sel)
    body = TextualBody(value="finding")
    with pytest.raises(ValueError, match="modified_by required"):
        Annotation(
            id="a-4",
            target=target,
            bodies=(body,),
            motivation=Motivation.CLASSIFYING,
            annotation_type="consensus-claim-unsupported",
            source="llm-audit:gap-d-v1",
            status=Status.ACK,
            creator="claude-opus-4-7",
            created=datetime(2026, 5, 11, tzinfo=timezone.utc),
            content_hash="sha256:abc",
            modified=datetime(2026, 5, 11, 11, tzinfo=timezone.utc),
            modified_by=None,            # missing
        )


def test_audit_ledger_holds_source_and_hashes() -> None:
    led = AuditLedger(
        id="ledger-gap-d-v1",
        source="llm-audit:gap-d-v1",
        audited_hashes=("sha256:1f9d", "sha256:abc1"),
        modified=datetime(2026, 5, 11, tzinfo=timezone.utc),
    )
    assert led.source == "llm-audit:gap-d-v1"
    assert led.audited_hashes == ("sha256:1f9d", "sha256:abc1")


def test_sidecar_is_an_aggregate() -> None:
    sc = Sidecar(annotations=(), ledgers=(), shared_targets=())
    assert sc.annotations == ()
    assert sc.ledgers == ()
    assert sc.shared_targets == ()
