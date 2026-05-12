# science/src/science_tool/annotation/text_segmentation.py
"""Sentence segmentation + TextQuoteSelector construction.

Single source of truth for sentence-boundary detection and selector
windowing across all annotation sources. See spec
docs/plans/2026-05-11-annotation-system-p3.3-spec.md §"Folded
follow-ups 1 + 7" for the consolidation rationale.

Two sentence-lookup functions are intentionally provided:
- `sentence_range_at(text, line, col)` for callers with both line
  and col (e.g. lint findings).
- `sentence_range_containing_literal(text, line, literal)` for
  callers that have a line and an anchoring substring but no col
  (e.g. marker tokens).

A single `sentence_range_at(text, line, col=1)` would silently
mis-anchor marker tokens that appear after the first sentence on a
line. `col` is REQUIRED on `sentence_range_at` to surface the
column-less use case as a distinct call site.
"""

from __future__ import annotations

import re
from typing import Optional

from science_tool.annotation.model import TextQuoteSelector


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences_with_offsets(text: str) -> list[tuple[int, int]]:
    """Return (start, end) char ranges of each sentence in `text`.

    Naive split on `[.!?]\\s+`; matches the segmentation strategy used
    by P3.2's marker_token / lint sources. Sentences that lack a
    terminator extend to the end of `text`.
    """
    if not text:
        return []
    out: list[tuple[int, int]] = []
    cursor = 0
    for sent in _SENTENCE_SPLIT_RE.split(text):
        if not sent:
            continue
        start = text.find(sent, cursor)
        if start == -1:
            continue
        end = start + len(sent)
        out.append((start, end))
        cursor = end
    return out


def _line_offsets(text: str) -> list[int]:
    """Return the char offset of each 1-based line start."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def sentence_range_at(
    text: str, line: int, col: int,
) -> Optional[tuple[int, int]]:
    """Return the (start, end) range of the sentence covering (line, col).

    - `line` and `col` are 1-based.
    - If (line, col) lands in inter-sentence whitespace, falls back to
      the nearest preceding sentence on the same or earlier line.
    - Returns None if `line` is past the last line of `text`.

    `col` is REQUIRED — see module docstring for rationale.
    """
    offsets = _line_offsets(text)
    if line < 1 or line > len(offsets):
        return None
    line_start = offsets[line - 1]
    cursor = line_start + (col - 1)
    if cursor < 0:
        cursor = 0
    if cursor > len(text):
        cursor = len(text)
    sentences = split_sentences_with_offsets(text)
    if not sentences:
        return None
    for start, end in sentences:
        if start <= cursor < end:
            return (start, end)
    for start, end in reversed(sentences):
        if start <= cursor:
            return (start, end)
    return None


def sentence_range_containing_literal(
    text: str, line: int, literal: str,
) -> Optional[tuple[int, int]]:
    """Return the sentence range of `literal` on the given 1-based `line`.

    Searches `line` (only) for `literal`; if found, maps the literal's
    char offset to the enclosing sentence range. Returns None if the
    literal is not on that line.

    Designed for callers without column info (e.g. MarkerHit, which
    carries `line` and `token` but no `col`). Picking the right
    sentence even when the line contains multiple sentences is
    load-bearing — a token in the second sentence on a line must NOT
    anchor to the first sentence.
    """
    offsets = _line_offsets(text)
    if line < 1 or line > len(offsets):
        return None
    line_start = offsets[line - 1]
    line_end = offsets[line] if line < len(offsets) else len(text)
    line_text = text[line_start:line_end]
    rel = line_text.find(literal)
    if rel == -1:
        return None
    abs_pos = line_start + rel
    sentences = split_sentences_with_offsets(text)
    for start, end in sentences:
        if start <= abs_pos < end:
            return (start, end)
    return None


def build_quote_selector(
    text: str,
    sent_start: int,
    sent_end: int,
    *,
    context: int = 60,
) -> TextQuoteSelector:
    """Build a TextQuoteSelector with `context`-char prefix/suffix windows.

    Windows are clipped at file boundaries (no padding).
    """
    prefix_start = max(0, sent_start - context)
    suffix_end = min(len(text), sent_end + context)
    return TextQuoteSelector(
        exact=text[sent_start:sent_end],
        prefix=text[prefix_start:sent_start],
        suffix=text[sent_end:suffix_end],
    )
