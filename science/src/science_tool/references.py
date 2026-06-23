"""Reference-record contract: BibTeX normalization, display formatting, the
citation-syntax grammar, and the app-export reference bundle (design doc
2026-06-23-science-citations-and-references)."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from science_tool.bibliography import BibEntry, load_bib_entries, raw_bib_entry_keys
from science_tool.markdown_utils import is_fence_line, strip_inline_code


def _split_authors(raw: str) -> list[str]:
    """Split a BibTeX author field on top-level ` and `, respecting braces."""
    parts: list[str] = []
    depth = 0
    start = 0
    i = 0
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth = max(0, depth - 1)
        elif depth == 0 and raw[i : i + 5].lower() == " and ":
            parts.append(raw[start:i])
            i += 5
            start = i
            continue
        i += 1
    parts.append(raw[start:])
    return [p.strip() for p in parts if p.strip()]


def _initials(given: str) -> str:
    """Initials from a given-name string: 'Donald R.' -> 'DR', 'Paul-Christian' -> 'P-C'."""
    out: list[str] = []
    for token in given.split():
        hyphen_parts = [p for p in token.split("-") if p]
        letters = [p[0].upper() for p in hyphen_parts if p[0].isalpha()]
        if letters:
            out.append("-".join(letters))
    return "".join(out)


def _format_one_author(name: str) -> str:
    """Render one BibTeX author name as 'Family II'."""
    name = name.strip()
    if name.startswith("{") and name.endswith("}"):
        return name[1:-1].strip()  # corporate/literal author
    if "," in name:
        fields = [f.strip() for f in name.split(",")]
        family = fields[0]
        given = fields[-1] if len(fields) >= 2 else ""  # 'Last, Jr, First' -> given is 'First'
    else:
        tokens = name.split()
        family = tokens[-1] if tokens else ""
        given = " ".join(tokens[:-1])
    initials = _initials(given)
    return f"{family} {initials}".strip() if initials else family


def format_authors(raw_author: str | None) -> str:
    """Render a BibTeX author field per design §5 (max 6, else first 3 + et al.)."""
    if not raw_author or not raw_author.strip():
        return ""
    authors = _split_authors(raw_author)
    if len(authors) > 6:
        rendered = [_format_one_author(a) for a in authors[:3]]
        return ", ".join(rendered) + ", et al."
    return ", ".join(_format_one_author(a) for a in authors)


CONTRACT = "science.references"
SCHEMA_VERSION = "1"

# BibTeX entry_type -> normalized record kind (design §4: article|book|chapter|preprint|misc).
# Driven solely by entry_type, NOT by container name: the design's §4 example maps a
# PsyArXiv @article to kind "article", so container sniffing would contradict the contract.
# "preprint" is emitted only for entry types that explicitly mean preprint.
_KIND_MAP = {
    "article": "article",
    "book": "book",
    "inbook": "chapter",
    "incollection": "chapter",
    "inproceedings": "chapter",
    "conference": "chapter",
    "preprint": "preprint",
    "unpublished": "preprint",
    "misc": "misc",
}


def _normalize_kind(entry: BibEntry) -> str:
    return _KIND_MAP.get(entry.entry_type, "misc")


def _authors_struct(raw_author: str | None) -> list[dict[str, str]]:
    if not raw_author:
        return []
    out: list[dict[str, str]] = []
    for name in _split_authors(raw_author):
        if name.startswith("{") and name.endswith("}"):
            out.append({"family": name[1:-1].strip(), "given": ""})
            continue
        if "," in name:
            fields = [f.strip() for f in name.split(",")]
            family, given = fields[0], (fields[-1] if len(fields) >= 2 else "")
        else:
            tokens = name.split()
            family = tokens[-1] if tokens else ""
            given = " ".join(tokens[:-1])
        out.append({"family": family, "given": given})
    return out


def format_display(entry: BibEntry) -> str:
    """Conservative numeric-style display string (design §5)."""
    authors = format_authors(entry.author) or entry.key
    container = entry.journal or entry.booktitle or entry.publisher
    head = f"{authors}."
    parts = [head]
    if entry.title:
        parts.append(f"{entry.title}.")
    if container:
        parts.append(f"{container}.")
    tail = ""
    if entry.year is not None:
        tail = str(entry.year)
        if entry.volume:
            tail += f";{entry.volume}"
            if entry.number:
                tail += f"({entry.number})"
            if entry.pages:
                tail += f":{entry.pages}"
        tail += "."
        parts.append(tail)
    if entry.doi:
        parts.append(f"doi:{entry.doi}.")
    return " ".join(parts)


def reference_record(entry: BibEntry) -> dict:
    """Build the design §4 reference record dict for one bibliography entry."""
    source = {"path": "papers/references.bib", "entry_type": entry.entry_type}
    if entry.author:
        source["raw_author"] = entry.author
    return {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "id": f"cite:{entry.key}",
        "citekey": entry.key,
        "kind": _normalize_kind(entry),
        "title": entry.title or entry.key,
        "authors": _authors_struct(entry.author),
        "issued": {"year": entry.year} if entry.year is not None else {},
        "container_title": entry.journal or entry.booktitle,
        "publisher": entry.publisher,
        "volume": entry.volume,
        "issue": entry.number,
        "pages": entry.pages,
        "doi": entry.doi,
        "pmid": entry.pmid,
        "url": entry.url,
        "display": format_display(entry),
        "source": source,
    }


# Outer block detector (design §6): a bracketed run whose first non-space char is '@'.
_BLOCK_RE = re.compile(r"\[\s*@[^\]]*\]")
# Any @citekey-shaped token, used for unsupported-syntax detection.
_BARE_AT_RE = re.compile(r"@([A-Za-z][A-Za-z0-9_:.\-]*)")
# A bare citekey within an item: text after '@' until whitespace/comma/semicolon/bracket.
_ITEM_KEY_RE = re.compile(r"@\s*([^\s,;\]]+)")


@dataclass(frozen=True)
class Citation:
    citekey: str
    locator: str | None


@dataclass(frozen=True)
class CitationScan:
    citations: list[Citation]
    unsupported: list[str]


def _parse_block(inner: str) -> tuple[list[Citation], list[str]]:
    """Parse the inside of a recognized `[@...]` block.

    Returns (citations, unsupported). A `;`-separated item that does not begin
    with `@<citekey>` is malformed (e.g. `see @Jones2021` in
    `[@Smith2020; see @Jones2021]`). Such an item is NOT silently dropped — its
    `@`-tokens (or, failing that, its raw text) are reported as unsupported so
    Science export fails closed instead of losing a citation.
    """
    citations: list[Citation] = []
    unsupported: list[str] = []
    for raw_item in inner.split(";"):
        item = raw_item.strip()
        if not item:
            continue
        key_match = _ITEM_KEY_RE.match(item)
        if key_match:
            citekey = key_match.group(1)
            rest = item[key_match.end():].strip()
            locator = None
            if rest:
                if not rest.startswith(","):
                    unsupported.append(item.lstrip("@"))
                    continue
                locator = rest[1:].strip() or None
            citations.append(Citation(citekey=citekey, locator=locator))
            continue
        ats = _BARE_AT_RE.findall(item)
        unsupported.extend(ats if ats else [item])
    return citations, unsupported


def _prose_lines(markdown: str) -> list[str]:
    """Lines with inline code stripped and fenced-code blocks removed."""
    lines: list[str] = []
    in_fence = False
    for line in markdown.splitlines():
        if is_fence_line(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        lines.append(strip_inline_code(line))
    return lines


def parse_citations(markdown: str) -> CitationScan:
    """Parse Markdown into the v1 citation grammar (design §6).

    Recognizes only `[@key ...]` blocks. `@key` tokens that are not inside a
    recognized block (bare `@key`, `[see @key]`, `[-@key]`) are reported as
    unsupported syntax, never silently dropped.
    """
    citations: list[Citation] = []
    unsupported: list[str] = []
    for line in _prose_lines(markdown):
        consumed_spans: list[tuple[int, int]] = []
        for block in _BLOCK_RE.finditer(line):
            block_citations, block_unsupported = _parse_block(block.group(0)[1:-1])
            citations.extend(block_citations)
            unsupported.extend(block_unsupported)
            consumed_spans.append(block.span())
        for at in _BARE_AT_RE.finditer(line):
            if any(start <= at.start() < end for start, end in consumed_spans):
                continue
            unsupported.append(at.group(1))
    return CitationScan(citations=citations, unsupported=unsupported)


class UnsupportedCitationSyntaxError(ValueError):
    """Raised when exported prose uses citation syntax outside the v1 grammar."""


class UnresolvedCitationError(ValueError):
    """Raised when exported prose cites a key absent from the bibliography."""

    def __init__(self, unresolved: dict[str, list[dict]]) -> None:
        self.unresolved = unresolved
        keys = ", ".join(sorted(unresolved))
        super().__init__(f"unresolved citation keys in exported prose: {keys}")


@dataclass(frozen=True)
class MarkdownPayload:
    path: str
    field: str
    text: str


def _snippet(text: str, citekey: str) -> str:
    idx = text.find(citekey)
    if idx == -1:
        return text[:60]
    start = max(0, idx - 20)
    end = min(len(text), idx + len(citekey) + 20)
    return f"... {text[start:end]} ..."


def validate_exported_markdown(
    payloads: list[MarkdownPayload],
    known_citekeys: set[str],
    *,
    allow_partial: bool = False,
) -> dict[str, list[dict]]:
    """Scan exported Markdown for citation keys (design §7). Fail-closed.

    - Any unsupported-syntax token (`[see @x]`, `[-@x]`, bare `@x`) raises
      UnsupportedCitationSyntaxError regardless of allow_partial.
    - Unknown citekeys raise UnresolvedCitationError unless allow_partial, in
      which case the design §7 `unresolved` map is returned instead.
    """
    unsupported_hits: list[str] = []
    unresolved: dict[str, list[dict]] = {}
    for payload in payloads:
        scan = parse_citations(payload.text)
        for token in scan.unsupported:
            unsupported_hits.append(f"{payload.path}:{payload.field} @{token}")
        for cite in scan.citations:
            if cite.citekey in known_citekeys:
                continue
            unresolved.setdefault(cite.citekey, []).append(
                {
                    "citekey": cite.citekey,
                    "reason": "unknown-citekey",
                    "path": payload.path,
                    "field": payload.field,
                    "snippet": _snippet(payload.text, cite.citekey),
                }
            )
    if unsupported_hits:
        raise UnsupportedCitationSyntaxError(
            "unsupported citation syntax (use [@key] only): " + "; ".join(unsupported_hits)
        )
    if unresolved and not allow_partial:
        raise UnresolvedCitationError(unresolved)
    return unresolved


class DuplicateCitekeyError(ValueError):
    """Raised when papers/references.bib declares the same citekey more than once."""

    def __init__(self, duplicates: dict[str, int]) -> None:
        self.duplicates = duplicates
        listed = ", ".join(f"{key} (x{count})" for key, count in sorted(duplicates.items()))
        super().__init__(f"duplicate citekeys in papers/references.bib: {listed}")


def build_reference_bundle(project_root: Path) -> dict:
    """Build the app-export reference bundle from papers/references.bib (design §7).

    Includes ALL normalized bibliography records, not only cited ones (locked
    decision §16.1). Fails closed on duplicate citekeys (design §5). `unresolved`
    is empty here; partial-export callers populate it via validate_exported_markdown.
    """
    counts = Counter(raw_bib_entry_keys(project_root))
    duplicates = {key: n for key, n in counts.items() if n > 1}
    if duplicates:
        raise DuplicateCitekeyError(duplicates)
    entries = load_bib_entries(project_root)
    references = {key: reference_record(entry) for key, entry in entries.items()}
    return {
        "contract": CONTRACT,
        "schema_version": SCHEMA_VERSION,
        "style": "numeric",
        "references": references,
        "unresolved": {},
    }
