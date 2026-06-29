# science/src/science_tool/annotation/sources/lint.py
"""Lint-detector source adapters.

Three module-level LintSource instances wrap the prose-lint detector
functions and emit PlannedAnnotation rows. frontmatter-inline-gap is
deferred because a file-level finding doesn't fit sentence-target selectors.

See docs/conventions/prose-lints.md for the prose-lint convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from science_tool.annotation.model import (
    Motivation,
    SpecificResource,
    TextualBody,
)
from science_tool.annotation.sources.base import PlannedAnnotation
from science_tool.annotation.text_segmentation import (
    build_quote_selector,
    sentence_range_at,
)
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
            rng = sentence_range_at(text, issue.line, issue.col)
            if rng is None:
                continue
            sent_start, sent_end = rng
            selector = build_quote_selector(text, sent_start, sent_end, context=60)
            target = SpecificResource(source=md_path.name, selector=selector)
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
