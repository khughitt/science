"""Project bibliography helpers."""

from __future__ import annotations

import re
from pathlib import Path

_BIBLIOGRAPHY_PREFIX = "cite:"
_BIBTEX_ENTRY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")


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
