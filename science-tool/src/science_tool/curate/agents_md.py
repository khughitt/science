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


BEGIN_MARKER = "<!-- BEGIN: load-bearing-constraints (managed by /science:curate; edit core/decisions.md instead) -->"
END_MARKER = "<!-- END: load-bearing-constraints -->"

_DIGEST_ENTRY = re.compile(r"^-\s+\*\*(D-\d+):\*\*", re.MULTILINE)


def parse_marker_state(agents_md: Path) -> bool:
    """Return True iff both BEGIN and END markers are present."""
    if not agents_md.is_file():
        return False
    text = agents_md.read_text(encoding="utf-8")
    return BEGIN_MARKER in text and END_MARKER in text


def parse_digest_ids(agents_md: Path) -> list[str]:
    """Return D-NNN IDs listed inside the load-bearing-constraints markers."""
    if not agents_md.is_file():
        return []
    text = agents_md.read_text(encoding="utf-8")
    begin = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER, begin + len(BEGIN_MARKER)) if begin != -1 else -1
    if begin == -1 or end == -1:
        return []
    section = text[begin + len(BEGIN_MARKER) : end]
    return [match.group(1) for match in _DIGEST_ENTRY.finditer(section)]


_AT_INCLUDE_LINE = re.compile(r"^@(\S+)\s*$")


def detect_legacy_at_includes(markdown_file: Path) -> list[str]:
    """Return `@core/*` directives that appear in the top-of-file include block.

    Claude Code only treats `@path` lines at the very top of a markdown file
    (before any non-include content) as include directives. We mirror that:
    walk lines from the top, collect `@path` lines, stop at the first
    non-include, non-blank line, then filter for `core/` paths.
    """
    if not markdown_file.is_file():
        return []
    legacy: list[str] = []
    for line in markdown_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        match = _AT_INCLUDE_LINE.match(line)
        if match is None:
            break
        path = match.group(1)
        if path.startswith("core/"):
            legacy.append(f"@{path}")
    return legacy


def is_claude_md_normalizable(claude_md: Path) -> bool:
    """Return True iff CLAUDE.md is safe to overwrite with a bare `@AGENTS.md`.

    Safe means: every non-blank line is either `@AGENTS.md` or a legacy
    `@core/*` directive. Anything else (project-specific guidance, other
    `@`-includes, prose) means manual review is required.
    """
    if not claude_md.is_file():
        return False
    seen_pointer = False
    for line in claude_md.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        if line == "@AGENTS.md":
            seen_pointer = True
            continue
        match = _AT_INCLUDE_LINE.match(line)
        if match is None:
            return False
        if not match.group(1).startswith("core/"):
            return False
    return seen_pointer
