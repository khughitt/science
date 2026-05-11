# science/src/science_tool/annotation/sources/marker_token.py
"""Marker-token source adapter.

Lifts the four phase-2 inline tokens ([UNVERIFIED], [MISSING_CITATION],
[SPECULATION], [INACCESSIBLE]) into PlannedAnnotation rows.

See spec docs/plans/2026-05-11-annotation-system-p3.2-spec.md
§sources/marker_token.py.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from science_tool.annotation.model import (
    Motivation,
    SpecificResource,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.markers import scan_text as _scan_markers_text

TOKEN_SCANNER_VERSION = "phase-2"
TOKEN_SOURCE_NAME = f"marker-scanner:{TOKEN_SCANNER_VERSION}"

# Canonical token → (annotation_type, body_message).
TOKEN_TYPE_MAP: dict[str, tuple[str, str]] = {
    "UNVERIFIED":       ("unverified", "verifiable claim, not yet checked"),
    "MISSING_CITATION": ("missing-citation", "claim needs source pointer"),
    "SPECULATION":      ("speculation", "author conjecture / brainstorming"),
    "INACCESSIBLE":     ("inaccessible", "paywalled / image-only / private source"),
}

_SELECTOR_CONTEXT = 60  # max prefix/suffix length, matches lint selector
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


class MarkerTokenSource:
    name: str = TOKEN_SOURCE_NAME
    short_name: str = "marker-token"

    def scan(self, md_path: Path) -> Iterable[PlannedAnnotation]:
        text = md_path.read_text(encoding="utf-8")
        return self.scan_text(md_path, text)

    def scan_text(
        self, md_path: Path, text: str,
    ) -> Iterable[PlannedAnnotation]:
        # strict=False: severity is informational here; we only care
        # about hit positions and tokens.
        hits = _scan_markers_text(md_path, text, strict=False)
        out: list[PlannedAnnotation] = []
        for hit in hits:
            if hit.in_documentation:
                continue
            atype, body_msg = TOKEN_TYPE_MAP[hit.token]
            literal = f"[{hit.token}]"
            sentence_range = _sentence_range_at(text, hit.line, literal)
            if sentence_range is None:
                continue
            sel = _build_selector(text, sentence_range, _SELECTOR_CONTEXT)
            target = SpecificResource(
                source=md_path.name,
                selector=sel,
            )
            body = TextualBody(value=f"{body_msg} (lifted from {literal})")
            out.append(
                PlannedAnnotation(
                    target=target,
                    annotation_type=atype,
                    motivation=Motivation.CLASSIFYING,
                    body=body,
                    match_text=literal,
                    source_name=TOKEN_SOURCE_NAME,
                    lifted_from=literal,
                )
            )
        return out


def _line_offsets(text: str) -> list[int]:
    """Return char offsets of the start of each 1-indexed line."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _sentence_range_at(
    text: str, line: int, anchor_literal: str,
) -> tuple[int, int] | None:
    """Return (start, end) char range of the sentence containing `line`.

    If the literal is present on that line, prefer the sentence
    containing the literal occurrence on the line. Otherwise fall back
    to the first sentence overlapping the line.
    """
    offsets = _line_offsets(text)
    if line < 1 or line > len(offsets):
        return None
    line_start = offsets[line - 1]
    line_end = offsets[line] if line < len(offsets) else len(text)
    line_text = text[line_start:line_end]
    anchor_pos_on_line = line_text.find(anchor_literal)
    anchor_pos = (
        line_start + anchor_pos_on_line if anchor_pos_on_line >= 0 else line_start
    )
    # Find the sentence that contains anchor_pos.
    cursor = 0
    for sent in _SENTENCE_SPLIT_RE.split(text):
        start = text.find(sent, cursor)
        if start == -1:
            continue
        end = start + len(sent)
        if start <= anchor_pos < end:
            return (start, end)
        cursor = end
    return None


def _build_selector(
    text: str, sentence_range: tuple[int, int], ctx: int,
) -> TextQuoteSelector:
    start, end = sentence_range
    prefix_start = max(0, start - ctx)
    suffix_end = min(len(text), end + ctx)
    return TextQuoteSelector(
        exact=text[start:end],
        prefix=text[prefix_start:start],
        suffix=text[end:suffix_end],
    )
