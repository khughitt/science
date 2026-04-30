"""Drift-detection helper for AGENTS.md and core/decisions.md.

Used by /science:curate to propose:
 - removal of legacy `@core/*` directives from AGENTS.md / CLAUDE.md
 - normalization of CLAUDE.md to a single `@AGENTS.md` pointer
 - insertion of the managed load-bearing-constraints digest markers
 - refresh of digest entries when active decisions change
"""

from __future__ import annotations

import re
from pathlib import Path

_DECISION_HEADING = re.compile(r"^##\s+(D-\d+)\b", re.MULTILINE)
_STATUS_LINE = re.compile(r"^-\s+\*\*Status:\*\*\s*(.+?)\s*$", re.MULTILINE)


def parse_active_decision_ids(decisions_md: Path) -> list[str]:
    """Return the IDs of decisions whose Status line is exactly `active`.

    Skips entries that are superseded, abandoned, or missing a Status line.
    """
    if not decisions_md.is_file():
        return []
    text = decisions_md.read_text(encoding="utf-8")
    sections = _split_decision_sections(text)
    active: list[str] = []
    for decision_id, body in sections:
        match = _STATUS_LINE.search(body)
        if match is None:
            continue
        if match.group(1).strip().lower() == "active":
            active.append(decision_id)
    return active


def _split_decision_sections(text: str) -> list[tuple[str, str]]:
    """Split a decisions.md file into (decision_id, section_body) pairs."""
    matches = list(_DECISION_HEADING.finditer(text))
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1), text[start:end]))
    return sections
