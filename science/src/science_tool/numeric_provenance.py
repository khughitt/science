"""Numeric-claim provenance assessment (Part A of the numeric-provenance redesign).

Pure core: `assess_numeric_claims(document, index, config)` classifies each numeric
claim in a document's body prose as exactly one of NotClaim / Exempt / Anchored /
Unanchored. The scanning layer builds the `DocumentContext` and `ResolutionIndex`
and passes them in, keeping this module free of disk I/O.

See docs/plans/2026-07-18-numeric-provenance-check-design.md (Part A).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NumericClaim:
    value: str
    line: int
    col: int
    paragraph_id: int
    section_id: int


@dataclass(frozen=True)
class SourceCandidate:
    reference: str
    origin: str          # "frontmatter" | "title" | "body"
    field_or_line: str
    resolution_status: str  # "resolved" | "unresolved"


@dataclass(frozen=True)
class NotClaim:
    claim: NumericClaim
    reason: str


@dataclass(frozen=True)
class Exempt:
    claim: NumericClaim
    reason: str
    scope: str           # "document" | "section" | "block"


@dataclass(frozen=True)
class Anchored:
    claim: NumericClaim
    candidates: tuple[SourceCandidate, ...]


@dataclass(frozen=True)
class Unanchored:
    claim: NumericClaim
    kind_hint: str | None
    local_evidence: bool


ClaimAssessment = NotClaim | Exempt | Anchored | Unanchored


@dataclass(frozen=True)
class NumericProvenanceConfig:
    anchor_patterns: tuple[str, ...]
    spec_class_kinds: frozenset[str]
    provenance_fields: tuple[str, ...]
