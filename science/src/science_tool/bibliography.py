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
# Superset of _BIBTEX_ENTRY_RE: also captures the entry type (group 1); key is group 2.
# Kept separate so load_bib_keys / _entry_key keep their group-1 == key contract.
_BIBTEX_ENTRY_TYPED_RE = re.compile(r"@(\w+)\s*\{\s*([^,\s]+)\s*,")

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
class BibEntry:
    """One balanced bibliography entry — the subset Phase 4b materializes."""

    key: str
    entry_type: str = "misc"
    title: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    author: str | None = None
    journal: str | None = None
    booktitle: str | None = None
    publisher: str | None = None
    volume: str | None = None
    number: str | None = None
    pages: str | None = None
    pmid: str | None = None


def _field_value(entry_text: str, field: str) -> str | None:
    """Extract a BibTeX field value from a single entry block, brace-aware.

    Handles the brace form ``field = {The {DNA} story}`` (matched by depth so
    nested braces do not truncate), the quoted form ``field = "..."``, and the
    bare form ``field = 2024``. Returns None when the field is absent.
    """
    match = re.search(
        r"^[ \t]*" + re.escape(field) + r"\s*=\s*",
        entry_text,
        re.IGNORECASE | re.MULTILINE,
    )
    if not match:
        return None
    i = match.end()
    if i >= len(entry_text):
        return None
    if entry_text[i] == "{":
        depth = 0
        for j in range(i, len(entry_text)):
            if entry_text[j] == "{":
                depth += 1
            elif entry_text[j] == "}":
                depth -= 1
                if depth == 0:
                    return entry_text[i + 1 : j].strip()
        return None  # unbalanced field value
    if entry_text[i] == '"':
        close = entry_text.find('"', i + 1)
        return entry_text[i + 1 : close].strip() if close != -1 else None
    bare = re.match(r"([^,\n}]*)", entry_text[i:])
    value = bare.group(1).strip() if bare else ""
    return value or None


def load_bib_entries(project_root: Path) -> dict[str, "BibEntry"]:
    """Parse ``papers/references.bib`` into balanced entries keyed by citekey.

    Only entries whose braces balance (via ``_entry_span``) are admitted, so the
    returned key set is exactly the set of entries that produce a real
    external-reference node — the invariant the retirement backed/un-backed test
    relies on. A truncated entry contributes no key. Missing fields are None.
    """
    bib_path = project_root / "papers" / "references.bib"
    if not bib_path.is_file():
        return {}
    text = bib_path.read_text(encoding="utf-8")
    entries: dict[str, BibEntry] = {}
    for match in _BIBTEX_ENTRY_TYPED_RE.finditer(text):
        entry_type = match.group(1).lower()
        key = match.group(2)
        span = _entry_span(text, key)
        if span is None:
            continue  # unbalanced/truncated — cannot be "backed", excluded
        block = text[span[0] : span[1]]
        year_raw = _field_value(block, "year")
        # Clamp to None unless it is a valid PaperEntity.year (ge=1800, le=2200).
        # This guarantees the synthesized PaperEntity validates, so a returned key
        # always yields a node (the retirement "backed" invariant).
        year_int = int(year_raw) if year_raw is not None and year_raw.isdigit() else None
        year = year_int if year_int is not None and 1800 <= year_int <= 2200 else None
        entries[key] = BibEntry(
            key=key,
            entry_type=entry_type,
            title=_field_value(block, "title"),
            year=year,
            doi=_field_value(block, "doi"),
            url=_field_value(block, "url"),
            author=_field_value(block, "author"),
            journal=_field_value(block, "journal"),
            booktitle=_field_value(block, "booktitle"),
            publisher=_field_value(block, "publisher"),
            volume=_field_value(block, "volume"),
            number=_field_value(block, "number"),
            pages=_field_value(block, "pages"),
            pmid=_field_value(block, "pmid"),
        )
    return entries


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
    subagents (the same problem ``science questions reserve`` solves for
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
