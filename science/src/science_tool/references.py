"""Reference-record contract: BibTeX normalization, display formatting, the
citation-syntax grammar, and the app-export reference bundle (design doc
2026-06-23-science-citations-and-references)."""

from __future__ import annotations

import re


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
