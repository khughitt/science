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


from science_tool.curate.agents_md import (
    detect_legacy_at_includes,
    is_claude_md_normalizable,
)


def test_detect_legacy_at_includes_finds_directives(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        """
        @core/overview.md
        @core/decisions.md

        # P — Agent Guide
        """,
    )
    assert detect_legacy_at_includes(agents_md) == ["@core/overview.md", "@core/decisions.md"]


def test_detect_legacy_at_includes_only_matches_at_top(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        """
        # P — Agent Guide

        ## Some section

        @core/overview.md
        """,
    )
    # Directive in the middle of the file is not a Claude Code include directive
    # (those must be at the top of the file). Treat as content, not legacy include.
    assert detect_legacy_at_includes(agents_md) == []


def test_detect_legacy_at_includes_returns_empty_for_missing(tmp_path: Path) -> None:
    assert detect_legacy_at_includes(tmp_path / "AGENTS.md") == []


def test_detect_legacy_at_includes_finds_only_core_paths(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        """
        @AGENTS.md
        @core/overview.md
        @other/file.md
        """,
    )
    assert detect_legacy_at_includes(agents_md) == ["@core/overview.md"]


def test_is_claude_md_normalizable_pure_pointer(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(claude_md, "@AGENTS.md\n")
    assert is_claude_md_normalizable(claude_md) is True


def test_is_claude_md_normalizable_pointer_plus_legacy_includes(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(
        claude_md,
        """
        @AGENTS.md
        @core/overview.md
        @core/decisions.md
        """,
    )
    assert is_claude_md_normalizable(claude_md) is True


def test_is_claude_md_normalizable_with_extra_content(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(
        claude_md,
        """
        @AGENTS.md
        @core/overview.md

        # Project-specific Claude Code guidance

        Always use uv, never pip.
        """,
    )
    assert is_claude_md_normalizable(claude_md) is False


def test_is_claude_md_normalizable_with_extra_at_include(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(
        claude_md,
        """
        @AGENTS.md
        @other/notes.md
        """,
    )
    assert is_claude_md_normalizable(claude_md) is False


def test_is_claude_md_normalizable_returns_false_for_missing(tmp_path: Path) -> None:
    assert is_claude_md_normalizable(tmp_path / "CLAUDE.md") is False


def test_detect_legacy_at_includes_rejects_indented_directive(tmp_path: Path) -> None:
    agents_md = tmp_path / "AGENTS.md"
    _write(
        agents_md,
        """
          @core/overview.md
        @core/decisions.md

        # P
        """,
    )
    # First line is `  @core/overview.md` (indented) — Claude Code would not
    # treat it as an include. We mirror that strictness: detection must stop
    # at the first non-include non-blank line, which here is the indented one.
    assert detect_legacy_at_includes(agents_md) == []


def test_is_claude_md_normalizable_rejects_indented_directive(tmp_path: Path) -> None:
    claude_md = tmp_path / "CLAUDE.md"
    _write(
        claude_md,
        """
        @AGENTS.md
          @core/overview.md
        """,
    )
    # The indented `@core/overview.md` is NOT a Claude Code include directive,
    # so this CLAUDE.md carries non-include content beyond `@AGENTS.md` and is
    # not safe to silently overwrite.
    assert is_claude_md_normalizable(claude_md) is False
