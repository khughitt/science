"""Split a book PDF into a chapter manifest from its embedded outline/bookmarks.

Used by the `science book-split` CLI and the /review-books command. Pure outline
extraction — no page rendering. Fails early (BookSplitError) when the PDF has no
outline, which is the caller's signal to fall back to reading the ToC pages.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader


class BookSplitError(Exception):
    """Raised when a book PDF cannot be split (e.g. no outline/bookmarks)."""


@dataclass(frozen=True)
class ChapterEntry:
    n: int
    title: str
    start_page: int  # 1-based, inclusive
    end_page: int  # 1-based, inclusive
    level: int  # 0 = top-level chapter, 1 = chapter nested under a Part/Volume
    part: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


# A level-0 entry is a container (its children are the chapters) only when its title
# explicitly reads as a division. Otherwise a parent entry is a *chapter* whose children
# are sections — which must NOT be dispatched as separate chapters.
_PART_RE = re.compile(r"^\s*(part|volume)\b", re.IGNORECASE)


def _collect_chapters(nodes: list[Any], reader: PdfReader, part: str | None = None) -> list[dict]:
    """Walk the (possibly nested) outline and return chapter entries in document order.

    pypdf represents hierarchy as a Destination optionally followed by a list of its
    children. The summarization unit is the *chapter*:
    - A destination is a chapter by default — even if it has section children
      (e.g. "Chapter 1" -> "1.1", "1.2"); the section children are skipped, not emitted.
    - A destination is treated as a *Part* (container) only when its title matches
      ``_PART_RE`` AND it has children; then its children are the chapters and carry
      ``part`` = the Part title.
    """
    chapters: list[dict] = []
    i = 0
    while i < len(nodes):
        node = nodes[i]
        if isinstance(node, list):
            # A stray child list with no preceding destination at this level.
            chapters.extend(_collect_chapters(node, reader, part))
            i += 1
            continue
        title = str(node.title).strip()
        start = reader.get_destination_page_number(node) + 1  # 0-based -> 1-based
        has_children = i + 1 < len(nodes) and isinstance(nodes[i + 1], list)
        if has_children and _PART_RE.match(title):
            # Container Part: descend; its children are the chapters.
            chapters.extend(_collect_chapters(nodes[i + 1], reader, part=title))
            i += 2
        else:
            # Chapter: emit it, and skip its section children (if any).
            chapters.append({"title": title, "start_page": start, "part": part})
            i += 2 if has_children else 1
    return chapters


def split_book(pdf_path: str | Path) -> list[ChapterEntry]:
    reader = PdfReader(str(pdf_path))
    try:
        outline = reader.outline
    except Exception as exc:  # pypdf raises various errors on malformed outlines
        raise BookSplitError(f"could not read outline: {exc}") from exc
    if not outline:
        raise BookSplitError("no outline/bookmarks in PDF")

    raw = _collect_chapters(outline, reader)
    if not raw:
        raise BookSplitError("no chapters found in outline")

    total_pages = len(reader.pages)
    chapters: list[ChapterEntry] = []
    for idx, item in enumerate(raw):
        start = item["start_page"]
        end = raw[idx + 1]["start_page"] - 1 if idx + 1 < len(raw) else total_pages
        if end < start:
            end = start
        chapters.append(
            ChapterEntry(
                n=idx + 1,
                title=item["title"],
                start_page=start,
                end_page=end,
                level=1 if item["part"] else 0,
                part=item["part"],
            )
        )
    return chapters
