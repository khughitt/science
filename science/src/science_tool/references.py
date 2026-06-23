"""Reference-record contract: BibTeX normalization, display formatting, the
citation-syntax grammar, and the app-export reference bundle (design doc
2026-06-23-science-citations-and-references)."""

from __future__ import annotations

import re

from science_tool.bibliography import BibEntry


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
