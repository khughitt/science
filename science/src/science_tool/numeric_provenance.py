"""Numeric-claim provenance assessment (Part A of the numeric-provenance redesign).

Pure core: `assess_numeric_claims(document, index, config)` classifies each numeric
claim in a document's body prose as exactly one of NotClaim / Exempt / Anchored /
Unanchored. The scanning layer builds the `DocumentContext` and `ResolutionIndex`
and passes them in, keeping this module free of disk I/O.

See docs/plans/2026-07-18-numeric-provenance-check-design.md (Part A).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.markdown_utils import frontmatter_span, is_fence_line

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
_TITLE_RE = re.compile(r"^#\s+(.+?)\s*$")


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


@dataclass(frozen=True)
class Section:
    section_id: int
    heading_level: int          # 0 for the pre-first-heading preamble
    start_line: int             # 1-based, inclusive
    end_line: int               # 1-based, inclusive


@dataclass(frozen=True)
class DocumentContext:
    path: Path
    kind: str | None
    frontmatter: dict
    title: str | None
    body_start: int
    lines: tuple[str, ...]              # full file lines, 1-based via lines[i-1]
    paragraph_id_per_line: tuple[int, ...]   # index by line number; [0] unused
    paragraph_text: dict[int, str]
    sections: tuple[Section, ...]
    section_id_per_line: tuple[int, ...]


def build_document_context(path: Path) -> DocumentContext | None:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    frontmatter, body_start = frontmatter_span(path)
    kind = frontmatter.get("kind") if isinstance(frontmatter, dict) else None
    lines = text.splitlines()
    n = len(lines)

    # Paragraphs: blank-line separated, mirroring detect_numeric_anchor's counter.
    paragraph_id_per_line = [0] * (n + 1)
    para_id = 0
    for idx, line in enumerate(lines, start=1):
        if not line.strip():
            para_id += 1
        paragraph_id_per_line[idx] = para_id
    paragraph_text: dict[int, str] = {}
    for idx, line in enumerate(lines, start=1):
        pid = paragraph_id_per_line[idx]
        paragraph_text[pid] = paragraph_text.get(pid, "") + line + "\n"

    # Sections: fail-closed at the next equal-or-higher heading. Fences are skipped
    # so a `#` inside a code block is not read as a heading.
    section_id_per_line = [0] * (n + 1)
    sections: list[Section] = []
    stack: list[tuple[int, int]] = []  # (heading_level, section_id)
    next_id = 1
    in_fence = False
    title: str | None = None
    for idx, raw in enumerate(lines, start=1):
        if is_fence_line(raw):
            in_fence = not in_fence
        heading = None if in_fence else _HEADING_RE.match(raw)
        if heading is not None:
            level = len(heading.group(1))
            if title is None:
                t = _TITLE_RE.match(raw)
                if t is not None:
                    title = t.group(1).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            sid = next_id
            next_id += 1
            stack.append((level, sid))
            sections.append(Section(section_id=sid, heading_level=level, start_line=idx, end_line=idx))
        section_id_per_line[idx] = stack[-1][1] if stack else 0

    # Fix up each section's end_line to the last line it owns.
    end_by_id: dict[int, int] = {}
    for idx in range(1, n + 1):
        end_by_id[section_id_per_line[idx]] = idx
    sections = tuple(
        Section(s.section_id, s.heading_level, s.start_line, end_by_id.get(s.section_id, s.start_line))
        for s in sections
    )

    return DocumentContext(
        path=path,
        kind=kind if isinstance(kind, str) else None,
        frontmatter=frontmatter if isinstance(frontmatter, dict) else {},
        title=title,
        body_start=body_start,
        lines=tuple(lines),
        paragraph_id_per_line=tuple(paragraph_id_per_line),
        paragraph_text=paragraph_text,
        sections=sections,
        section_id_per_line=tuple(section_id_per_line),
    )
