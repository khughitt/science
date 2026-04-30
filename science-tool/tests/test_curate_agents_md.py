from __future__ import annotations

from pathlib import Path
import textwrap

import pytest

from science_tool.curate.agents_md import parse_active_decision_ids


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")


def test_parse_active_decision_ids_returns_only_active(tmp_path: Path) -> None:
    decisions = tmp_path / "core" / "decisions.md"
    _write(
        decisions,
        """
        # Decisions

        ## D-001: First decision

        - **Date:** 2026-01-01
        - **Status:** active
        - **Decision:** First.

        ---

        ## D-002: Second decision

        - **Date:** 2026-01-02
        - **Status:** superseded by D-004
        - **Decision:** Second.

        ---

        ## D-003: Third decision

        - **Date:** 2026-01-03
        - **Status:** abandoned
        - **Decision:** Third.

        ---

        ## D-004: Fourth decision

        - **Date:** 2026-01-04
        - **Status:** active
        - **Decision:** Fourth.
        """,
    )

    assert parse_active_decision_ids(decisions) == ["D-001", "D-004"]


def test_parse_active_decision_ids_returns_empty_for_missing_file(tmp_path: Path) -> None:
    assert parse_active_decision_ids(tmp_path / "core" / "decisions.md") == []


def test_parse_active_decision_ids_handles_no_status_line(tmp_path: Path) -> None:
    decisions = tmp_path / "core" / "decisions.md"
    _write(
        decisions,
        """
        # Decisions

        ## D-001: A decision without a status line yet

        - **Date:** 2026-01-01
        - **Decision:** Pending.
        """,
    )
    # No `- **Status:** active` line means we cannot confirm active.
    assert parse_active_decision_ids(decisions) == []


from science_tool.curate.agents_md import (
    BEGIN_MARKER,
    END_MARKER,
    parse_digest_ids,
    parse_marker_state,
)


def test_parse_marker_state_detects_present_markers(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        ## Load-bearing constraints

        - **D-001:** Do the thing.
        {END_MARKER}
        """,
    )
    assert parse_marker_state(agents_md) is True


def test_parse_marker_state_detects_absent_markers(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(agents_md, "# P — Agent Guide\n\n## Conventions\n- be nice\n")
    assert parse_marker_state(agents_md) is False


def test_parse_marker_state_returns_false_when_only_one_marker(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(agents_md, f"# P\n\n{BEGIN_MARKER}\nstuff but no end\n")
    assert parse_marker_state(agents_md) is False


def test_parse_digest_ids_extracts_ids_between_markers(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        ## Load-bearing constraints

        - **D-001:** First rule.
        - **D-004:** Fourth rule.
        {END_MARKER}

        ## Pointers
        - **D-999:** This must NOT be picked up because it is outside the markers.
        """,
    )
    assert parse_digest_ids(agents_md) == ["D-001", "D-004"]


def test_parse_digest_ids_returns_empty_when_markers_missing(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(agents_md, "# P\n\n- **D-001:** ignored, no markers\n")
    assert parse_digest_ids(agents_md) == []


def test_parse_digest_ids_returns_empty_when_file_missing(tmp_path: Path) -> None:
    assert parse_digest_ids(tmp_path / "AGENTS.md") == []
