"""mutate_status: author transitions require source==OPEN; auto→SUPERSEDED is free."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from science_tool.annotation.lifecycle import mutate_status
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)


def _ann(status: Status) -> Annotation:
    base = Annotation(
        id="a-abc",
        target=SpecificResource(
            source="x.md",
            selector=TextQuoteSelector(exact="x", prefix="", suffix=""),
        ),
        bodies=(TextualBody(value="msg"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="bare-author-year",
        source="lint:bare-author-year-v2026-05-11",
        status=Status.OPEN,
        creator="test",
        created=datetime(2026, 5, 11, tzinfo=timezone.utc),
        content_hash="sha256:dead",
        match_text="m",
    )
    if status is Status.OPEN:
        return base
    return replace(
        base,
        status=status,
        modified=datetime(2026, 5, 11, 1, tzinfo=timezone.utc),
        modified_by="test",
    )


_NOW = datetime(2026, 5, 11, 12, tzinfo=timezone.utc)


# ---- OPEN → terminal: allowed ---------------------------------------

@pytest.mark.parametrize("target", [Status.ACK, Status.FIXED, Status.DISMISSED])
def test_open_to_terminal_allowed(target: Status) -> None:
    a = _ann(Status.OPEN)
    out = mutate_status(a, target, actor="alice", now=_NOW)
    assert out.status is target


# ---- SUPERSEDED → terminal: refused (the new guard) -----------------

@pytest.mark.parametrize("target", [Status.ACK, Status.FIXED, Status.DISMISSED])
def test_superseded_to_terminal_refused(target: Status) -> None:
    a = _ann(Status.SUPERSEDED)
    with pytest.raises(ValueError, match="only 'open'"):
        mutate_status(a, target, actor="alice", now=_NOW)


# ---- Existing terminal-state refusals: still raise ------------------

@pytest.mark.parametrize("source", [Status.ACK, Status.FIXED, Status.DISMISSED])
@pytest.mark.parametrize("target", [Status.ACK, Status.FIXED, Status.DISMISSED])
def test_terminal_to_terminal_refused(source: Status, target: Status) -> None:
    a = _ann(source)
    with pytest.raises(ValueError, match="terminal status"):
        mutate_status(a, target, actor="alice", now=_NOW)


# ---- * → SUPERSEDED: always allowed --------------------------------

@pytest.mark.parametrize(
    "source",
    [Status.OPEN, Status.ACK, Status.FIXED, Status.DISMISSED, Status.SUPERSEDED],
)
def test_any_to_superseded_allowed(source: Status) -> None:
    a = _ann(source)
    out = mutate_status(a, Status.SUPERSEDED, actor="auto", now=_NOW)
    assert out.status is Status.SUPERSEDED


# ---- Transition to OPEN always refused ------------------------------

def test_transition_to_open_refused() -> None:
    a = _ann(Status.ACK)
    with pytest.raises(ValueError, match="status flows forward only"):
        mutate_status(a, Status.OPEN, actor="alice", now=_NOW)
