# science/src/science_tool/annotation/sources/lint.py
"""Lint-detector source adapters.

Three module-level LintSource instances wrap the prose-lint detector
functions and emit PlannedAnnotation rows. frontmatter-inline-gap is
deferred (file-level finding doesn't fit sentence-target selectors —
see spec §Module layout).

See spec docs/plans/2026-05-11-annotation-system-p3.2-spec.md
§sources/lint.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from science_tool.annotation.model import (
    Motivation,
    SpecificResource,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.prose_lint import (
    LintIssue,
    detect_bare_author_year,
    detect_numeric_anchor,
    detect_short_form_ids,
)

DETECTOR_VERSIONS: dict[str, str] = {
    "bare-author-year": "v2026-05-11",
    "short-form-ids":   "v2026-05-11",
    "numeric-anchor":   "v2026-05-11",
}

_SELECTOR_CONTEXT = 60
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def lint_source_name(short: str) -> str:
    return f"lint:{short}-{DETECTOR_VERSIONS[short]}"


@dataclass(frozen=True)
class LintSource:
    short_name: str
    name: str
    annotation_type: str
    detector: Callable[..., list[LintIssue]]

    def scan(self, md_path: Path) -> Iterable[PlannedAnnotation]:
        issues = self.detector(md_path)
        text = md_path.read_text(encoding="utf-8")
        out: list[PlannedAnnotation] = []
        for issue in issues:
            sel = _selector_for_issue(text, issue)
            if sel is None:
                continue
            target = SpecificResource(source=md_path.name, selector=sel)
            body = TextualBody(value=issue.message)
            out.append(
                PlannedAnnotation(
                    target=target,
                    annotation_type=self.annotation_type,
                    motivation=Motivation.CLASSIFYING,
                    body=body,
                    match_text=issue.match,
                    source_name=self.name,
                    lifted_from=None,
                )
            )
        return out


def _line_offsets(text: str) -> list[int]:
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _selector_for_issue(
    text: str, issue: LintIssue,
) -> TextQuoteSelector | None:
    """Build a sentence-level TextQuoteSelector for a LintIssue.

    Locates the sentence that covers the (line, col) char position
    in `text`; returns None if the position is out of range.
    """
    offsets = _line_offsets(text)
    if issue.line < 1 or issue.line > len(offsets):
        return None
    line_start = offsets[issue.line - 1]
    char_pos = line_start + max(0, issue.col - 1)
    cursor = 0
    for sent in _SENTENCE_SPLIT_RE.split(text):
        start = text.find(sent, cursor)
        if start == -1:
            continue
        end = start + len(sent)
        if start <= char_pos < end:
            return TextQuoteSelector(
                exact=text[start:end],
                prefix=text[max(0, start - _SELECTOR_CONTEXT):start],
                suffix=text[end:min(len(text), end + _SELECTOR_CONTEXT)],
            )
        cursor = end
    return None


def bare_author_year_source() -> LintSource:
    return LintSource(
        short_name="bare-author-year",
        name=lint_source_name("bare-author-year"),
        annotation_type="bare-author-year",
        detector=detect_bare_author_year,
    )


def short_form_ids_source() -> LintSource:
    return LintSource(
        short_name="short-form-ids",
        name=lint_source_name("short-form-ids"),
        annotation_type="short-form-ids",
        detector=detect_short_form_ids,
    )


def numeric_anchor_source() -> LintSource:
    return LintSource(
        short_name="numeric-anchor",
        name=lint_source_name("numeric-anchor"),
        annotation_type="numeric-anchor",
        detector=detect_numeric_anchor,
    )
