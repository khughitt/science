"""Project bibliography helpers."""

from __future__ import annotations

import fcntl
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_BIBLIOGRAPHY_PREFIX = "cite:"
_BIBTEX_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")

_BIB_HEADER = (
    "% references.bib — BibTeX database for this Science project\n"
    "% Add entries here for every paper cited in doc/ or papers/summaries/.\n"
    "% Use keys in the format: FirstAuthorLastNameYear (e.g., Smith2024)\n"
)


def bibliography_key_from_reference(raw: str) -> str | None:
    """Return the BibTeX key from ``cite:<key>``, or None for other refs."""
    if not raw.startswith(_BIBLIOGRAPHY_PREFIX):
        return None
    key = raw[len(_BIBLIOGRAPHY_PREFIX) :].strip()
    return key or None


def is_bibliography_reference(raw: str) -> bool:
    """Return True when ``raw`` names a project bibliography entry."""
    return bibliography_key_from_reference(raw) is not None


def load_bib_keys(project_root: Path) -> set[str]:
    """Extract BibTeX entry keys from ``papers/references.bib``."""
    bib_path = project_root / "papers" / "references.bib"
    if not bib_path.is_file():
        return set()
    keys: set[str] = set()
    for match in _BIBTEX_ENTRY_RE.finditer(bib_path.read_text(encoding="utf-8")):
        keys.add(match.group(1))
    return keys


_BIBTEX_AUTHOR_FIELD_RE = re.compile(r"author\s*=\s*[{\"]([^{}\"]*)[}\"]", re.IGNORECASE)


def _surname_of(author: str) -> str | None:
    """Extract the surname from one BibTeX author name, lowercased.

    Handles both ``Last, First`` (surname before the comma) and ``First Last``
    (surname is the last whitespace token). Returns None for an empty name.
    """
    author = author.strip().strip("{}").strip()
    if not author:
        return None
    surname = author.split(",")[0].strip() if "," in author else author.split()[-1]
    surname = surname.strip("{}.").strip().lower()
    return surname or None


def load_bib_author_surnames(project_root: Path) -> set[str] | None:
    """Return lowercased author surnames in ``papers/references.bib``.

    Returns ``None`` when the bibliography is absent, so a bib-aware lint can
    distinguish "no bibliography to check against" (fall back to flag-all) from
    "bibliography present but this surname is not in it" (skip). Co-authors from
    every entry's ``author`` field are included.
    """
    bib_path = project_root / "papers" / "references.bib"
    if not bib_path.is_file():
        return None
    text = bib_path.read_text(encoding="utf-8")
    surnames: set[str] = set()
    for field in _BIBTEX_AUTHOR_FIELD_RE.finditer(text):
        for author in re.split(r"\s+and\s+", field.group(1)):
            surname = _surname_of(author)
            if surname:
                surnames.add(surname)
    return surnames


@dataclass(frozen=True)
class BibAddResult:
    """Outcome of an ``add_bib_entry`` call."""

    key: str
    action: Literal["added", "exists", "replaced"]
    path: Path


def _entry_key(entry: str) -> str:
    """Parse the BibTeX key from a single entry, or fail early."""
    match = _BIBTEX_ENTRY_RE.search(entry)
    if not match:
        raise ValueError("entry does not contain a parseable BibTeX key (expected `@type{key, ...}`)")
    return match.group(1)


def _entry_span(text: str, key: str) -> tuple[int, int] | None:
    """Return ``(start, end)`` of the ``@type{key, ...}`` block, or None.

    Boundaries are found by matching the entry's outermost braces, so nested
    braces in field values (e.g. ``title={The {DNA} story}``) don't truncate it.
    Returns None if the key is absent or its braces never balance.
    """
    head = re.compile(r"@\w+\s*\{\s*" + re.escape(key) + r"\s*,")
    match = head.search(text)
    if not match:
        return None
    open_brace = text.index("{", match.start())
    depth = 0
    for i in range(open_brace, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return (match.start(), i + 1)
    return None  # unbalanced — truncated entry


def add_bib_entry(project_root: Path, entry: str, *, replace: bool = False) -> BibAddResult:
    """Append one BibTeX ``entry`` to ``papers/references.bib`` atomically.

    A single locked open-read-write-replace cycle eliminates the Read→Edit
    mtime race that the Edit tool hits when Dropbox touches the file mid-edit,
    and an exclusive ``flock`` serializes concurrent appends from parallel
    subagents (the same problem ``science question reserve`` solves for
    question files). Idempotent by key: an entry whose key already exists is a
    no-op unless ``replace=True``, which swaps the existing block in place.
    """
    entry = entry.strip()
    key = _entry_key(entry)
    if _entry_span(entry, key) is None:
        raise ValueError(f"entry for {key!r} has unbalanced braces (truncated?)")

    papers_dir = project_root / "papers"
    papers_dir.mkdir(parents=True, exist_ok=True)
    bib_path = papers_dir / "references.bib"
    lock_path = papers_dir / ".references.bib.lock"

    with open(lock_path, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            existing = bib_path.read_text(encoding="utf-8") if bib_path.is_file() else ""

            if key in load_bib_keys(project_root) or _entry_span(existing, key) is not None:
                if not replace:
                    return BibAddResult(key=key, action="exists", path=bib_path)
                span = _entry_span(existing, key)
                assert span is not None  # key present implies a locatable block
                start, end = span
                new_text = existing[:start] + entry + existing[end:]
                _atomic_write(bib_path, new_text)
                return BibAddResult(key=key, action="replaced", path=bib_path)

            if not existing:
                new_text = _BIB_HEADER + "\n" + entry + "\n"
            else:
                separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
                new_text = existing + separator + entry + "\n"
            _atomic_write(bib_path, new_text)
            return BibAddResult(key=key, action="added", path=bib_path)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via a temp file + rename (atomic for readers)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
