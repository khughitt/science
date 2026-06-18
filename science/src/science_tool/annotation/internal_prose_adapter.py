from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from science_tool.annotation.prose_decomposition import MarkdownLocator, Quote
from science_tool.annotation.text_source_adapter import LocatorRegime, TextSourceAdapter
from science_tool.entities import normalize_to_slug


class LocatorStatus(Enum):
    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class LocatorResolution:
    status: LocatorStatus
    text: str = ""
    message: str = ""


class InternalProseAdapter(TextSourceAdapter):
    name = "internal-prose"
    locator_regime = LocatorRegime.REGENERABLE
    can_fetch = False
    can_seed = False

    def handles(self, source_md: Path) -> bool:
        return source_md.suffix.lower() == ".md" and not source_md.name.endswith(".source.md")

    def source_ref(self, source_md: Path) -> str:
        return f"prose-source:{normalize_to_slug(source_md.stem)}"

    def source_ref_from_slug(self, slug: str) -> str:
        return f"prose-source:{slug}"

    def resolve_unit(self, source_md: Path, locator: MarkdownLocator, quote: Quote) -> LocatorResolution:
        return resolve_markdown_locator(source_md, locator, quote)


_HEADING_RE = re.compile(r"^(#{1,6})(?:\s+|$)(.*?)\s*$")
_SUPPORTED_REGIMES = frozenset({"markdown-heading-path", "markdown-heading-path-with-quote"})


@dataclass
class _MarkdownSection:
    level: int
    heading: str
    heading_path: tuple[str, ...]
    body_start: int
    body_end: int

    def body(self, source_text: str) -> str:
        return source_text[self.body_start : self.body_end]


@dataclass(frozen=True)
class _QuoteSearchResult:
    exact_occurrences: int
    context_matches: int


def resolve_markdown_locator(source_md: Path, locator: MarkdownLocator, quote: Quote) -> LocatorResolution:
    if locator.regime not in _SUPPORTED_REGIMES:
        raise ValueError(f"unsupported markdown locator regime: {locator.regime}")
    if not locator.heading_path:
        raise ValueError("markdown locator heading_path must not be empty")

    source_text = source_md.read_text(encoding="utf-8")
    matching_sections = [
        section
        for section in _parse_markdown_sections(source_text)
        if _heading_path_matches(section.heading_path, locator.heading_path)
    ]
    if not matching_sections:
        return LocatorResolution(
            LocatorStatus.UNRESOLVED,
            message=f"heading path not found: {' > '.join(locator.heading_path)}",
        )

    if quote.exact:
        quote_result = _search_quote_in_sections(source_text, matching_sections, quote)
        if quote_result.context_matches == 1:
            return LocatorResolution(LocatorStatus.RESOLVED, text=quote.exact)
        if quote_result.context_matches > 1:
            return LocatorResolution(
                LocatorStatus.AMBIGUOUS,
                message=f"quote matched multiple occurrences: {quote.exact}",
            )
        if quote_result.exact_occurrences > 0:
            return LocatorResolution(
                LocatorStatus.UNRESOLVED,
                message=f"quote context mismatch in matched section: {quote.exact}",
            )
        return LocatorResolution(
            LocatorStatus.UNRESOLVED,
            message=f"quote not found in matched section: {quote.exact}",
        )

    if len(matching_sections) > 1:
        return LocatorResolution(
            LocatorStatus.AMBIGUOUS,
            message=f"multiple sections match heading path: {' > '.join(locator.heading_path)}",
        )

    return LocatorResolution(LocatorStatus.RESOLVED, text=matching_sections[0].body(source_text).strip())


def _search_quote_in_sections(
    source_text: str,
    sections: list[_MarkdownSection],
    quote: Quote,
) -> _QuoteSearchResult:
    exact_occurrences = 0
    context_matches = 0

    for section in sections:
        body = section.body(source_text)
        start = body.find(quote.exact)
        while start != -1:
            exact_occurrences += 1
            end = start + len(quote.exact)
            if _quote_context_matches(body, start, end, quote):
                context_matches += 1
            start = body.find(quote.exact, start + 1)

    return _QuoteSearchResult(exact_occurrences=exact_occurrences, context_matches=context_matches)


def _quote_context_matches(body: str, start: int, end: int, quote: Quote) -> bool:
    if quote.prefix and not body[:start].endswith(quote.prefix):
        return False
    if quote.suffix and not body[end:].startswith(quote.suffix):
        return False
    return True


def _parse_markdown_sections(source_text: str) -> list[_MarkdownSection]:
    sections: list[_MarkdownSection] = []
    active: list[_MarkdownSection] = []
    offset = 0

    for line in source_text.splitlines(keepends=True):
        heading = _parse_atx_heading(line)
        if heading is not None:
            level, title = heading
            while active and active[-1].level >= level:
                active.pop().body_end = offset

            heading_path = (*[section.heading for section in active], title)
            section = _MarkdownSection(
                level=level,
                heading=title,
                heading_path=heading_path,
                body_start=offset + len(line),
                body_end=len(source_text),
            )
            sections.append(section)
            active.append(section)
        offset += len(line)

    for section in active:
        section.body_end = len(source_text)
    return sections


def _parse_atx_heading(line: str) -> tuple[int, str] | None:
    if not line.startswith("#"):
        return None
    match = _HEADING_RE.match(line.rstrip("\r\n"))
    if match is None:
        return None
    title = re.sub(r"\s+#+\s*$", "", match.group(2)).strip()
    return len(match.group(1)), title


def _heading_path_matches(active_heading_path: tuple[str, ...], requested_heading_path: tuple[str, ...]) -> bool:
    if len(requested_heading_path) > len(active_heading_path):
        return False
    normalized_active = tuple(_norm(part) for part in active_heading_path)
    normalized_requested = tuple(_norm(part) for part in requested_heading_path)
    return normalized_active[-len(normalized_requested) :] == normalized_requested


def _norm(value: str) -> str:
    return " ".join(value.strip().casefold().split())
