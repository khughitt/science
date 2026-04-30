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

from pydantic import BaseModel, Field

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


class AgentsMdDigestState(BaseModel):
    agents_md_present: bool = False
    claude_md_present: bool = False
    markers_present: bool = False
    agents_md_legacy_at_includes: list[str] = Field(default_factory=list)
    claude_md_legacy_at_includes: list[str] = Field(default_factory=list)
    claude_md_normalizable: bool = False
    active_decision_ids: list[str] = Field(default_factory=list)
    digest_ids: list[str] = Field(default_factory=list)
    decisions_mtime_seconds: float | None = None
    agents_md_mtime_seconds: float | None = None
    drift_signals: list[str] = Field(default_factory=list)


def collect_agents_md_state(project_root: Path) -> AgentsMdDigestState:
    """Gather the inputs `/science:curate` needs to propose AGENTS.md edits."""
    project_root = Path(project_root)
    agents_md = project_root / "AGENTS.md"
    claude_md = project_root / "CLAUDE.md"
    decisions_md = project_root / "core" / "decisions.md"

    state = AgentsMdDigestState(
        agents_md_present=agents_md.is_file(),
        claude_md_present=claude_md.is_file(),
        markers_present=parse_marker_state(agents_md),
        agents_md_legacy_at_includes=detect_legacy_at_includes(agents_md),
        claude_md_legacy_at_includes=detect_legacy_at_includes(claude_md),
        claude_md_normalizable=is_claude_md_normalizable(claude_md),
        active_decision_ids=parse_active_decision_ids(decisions_md),
        digest_ids=parse_digest_ids(agents_md),
        decisions_mtime_seconds=_mtime_seconds(decisions_md),
        agents_md_mtime_seconds=_mtime_seconds(agents_md),
    )
    state.drift_signals = _compute_drift_signals(state)
    return state


def _mtime_seconds(path: Path) -> float | None:
    return path.stat().st_mtime if path.is_file() else None


def _compute_drift_signals(state: AgentsMdDigestState) -> list[str]:
    if not state.agents_md_present:
        return []
    signals: list[str] = []
    if state.agents_md_legacy_at_includes:
        signals.append("agents_md_legacy_includes")
    if state.claude_md_legacy_at_includes:
        signals.append("claude_md_legacy_includes")
    if not state.markers_present:
        signals.append("markers_missing")
    if (
        state.decisions_mtime_seconds is not None
        and state.agents_md_mtime_seconds is not None
        and state.decisions_mtime_seconds > state.agents_md_mtime_seconds
    ):
        signals.append("core_decisions_newer_than_agents_md")
    if state.active_decision_ids != state.digest_ids and (
        state.active_decision_ids or state.digest_ids
    ):
        signals.append("active_decisions_differ_from_digest")
    return signals
