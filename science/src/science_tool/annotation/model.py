# science/src/science_tool/annotation/model.py
"""Frozen domain model for the phase-3 annotation system.

See docs/plans/2026-05-10-annotation-system-spec.md §Data model.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Optional


class Status(StrEnum):
    OPEN = "open"
    ACK = "ack"
    FIXED = "fixed"
    DISMISSED = "dismissed"
    SUPERSEDED = "superseded"


class Motivation(StrEnum):
    COMMENTING = "commenting"
    TAGGING = "tagging"
    CLASSIFYING = "classifying"
    LINKING = "linking"
    QUESTIONING = "questioning"
    IDENTIFYING = "identifying"
    HIGHLIGHTING = "highlighting"


# Source kinds whose annotations require a content_hash for re-audit caching.
HASH_REQUIRED_SOURCE_PREFIXES: tuple[str, ...] = (
    "llm-audit:",
    "lint:",
    "marker-scanner:",
    "pubtator3:",
    "llm-annot:",
)


@dataclass(frozen=True)
class TextQuoteSelector:
    exact: str
    prefix: str
    suffix: str


@dataclass(frozen=True)
class SpecificResource:
    """Named or shared annotation target. id is None for inline blank-node form."""

    source: str
    selector: TextQuoteSelector
    id: Optional[str] = None  # only set for shared (named-node) targets


@dataclass(frozen=True)
class TextualBody:
    value: str
    format: str = "text/plain"


@dataclass(frozen=True)
class IriBody:
    iri: str


Body = TextualBody | IriBody


@dataclass(frozen=True)
class PriorState:
    """Snapshot of an annotation's pre-mutation state, written into prov:wasRevisionOf."""

    status: Status
    creator: str
    created: datetime


@dataclass(frozen=True)
class Annotation:
    id: str
    target: SpecificResource
    bodies: tuple[Body, ...]
    motivation: Motivation
    annotation_type: str
    source: str
    status: Status
    creator: str                          # original producing agent (preserved across mutations)
    created: datetime
    content_hash: Optional[str] = None
    modified: Optional[datetime] = None
    modified_by: Optional[str] = None     # actor of most recent status mutation
    description: Optional[str] = None
    lifted_from: Optional[str] = None
    match_text: Optional[str] = None      # per-finding identity (P3.2 dedupe key)
    prior_states: tuple[PriorState, ...] = ()

    def __post_init__(self) -> None:
        if any(self.source.startswith(p) for p in HASH_REQUIRED_SOURCE_PREFIXES):
            if self.content_hash is None:
                raise ValueError(
                    f"content_hash required for source {self.source!r}"
                )
        if self.status is not Status.OPEN and self.modified is None:
            raise ValueError(
                f"modified required when status is {self.status.value!r} (not 'open')"
            )
        if self.modified is not None and self.modified_by is None:
            raise ValueError(
                "modified_by required whenever modified is set"
            )
        if not self.bodies:
            raise ValueError("annotation must have at least one body")


@dataclass(frozen=True)
class AuditLedger:
    id: str
    source: str
    audited_hashes: tuple[str, ...]
    modified: datetime
    source_text_hash: str | None = None


@dataclass(frozen=True)
class Sidecar:
    annotations: tuple[Annotation, ...] = ()
    ledgers: tuple[AuditLedger, ...] = ()
    shared_targets: tuple[SpecificResource, ...] = ()
