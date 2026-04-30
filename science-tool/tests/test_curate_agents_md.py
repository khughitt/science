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


import os
from datetime import datetime, timezone

from science_tool.curate.agents_md import collect_agents_md_state


def _set_mtime_iso(path: Path, when_iso: str) -> None:
    stamp = datetime.fromisoformat(when_iso).replace(tzinfo=timezone.utc).timestamp()
    os.utime(path, (stamp, stamp))


def test_collect_agents_md_state_pristine_modern_project(tmp_path: Path) -> None:
    _write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    _write(
        tmp_path / "AGENTS.md",
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        - **D-001:** Stay calm.
        {END_MARKER}
        """,
    )
    _write(
        tmp_path / "core" / "decisions.md",
        """
        ## D-001: Stay calm

        - **Date:** 2026-04-01
        - **Status:** active
        """,
    )
    _set_mtime_iso(tmp_path / "core" / "decisions.md", "2026-04-01T00:00:00")
    _set_mtime_iso(tmp_path / "AGENTS.md", "2026-04-02T00:00:00")

    state = collect_agents_md_state(tmp_path)

    assert state.agents_md_present is True
    assert state.claude_md_present is True
    assert state.markers_present is True
    assert state.active_decision_ids == ["D-001"]
    assert state.digest_ids == ["D-001"]
    assert state.agents_md_legacy_at_includes == []
    assert state.claude_md_legacy_at_includes == []
    assert state.claude_md_normalizable is True  # pure `@AGENTS.md`
    assert state.drift_signals == []


def test_collect_agents_md_state_legacy_project_full_drift(tmp_path: Path) -> None:
    _write(
        tmp_path / "CLAUDE.md",
        """
        @AGENTS.md
        @core/overview.md
        @core/decisions.md
        """,
    )
    _write(
        tmp_path / "AGENTS.md",
        """
        @core/overview.md
        @core/decisions.md

        # P — Agent Guide

        Some prose, no markers.
        """,
    )
    _write(
        tmp_path / "core" / "decisions.md",
        """
        ## D-001: One

        - **Status:** active

        ---

        ## D-002: Two

        - **Status:** active
        """,
    )
    _set_mtime_iso(tmp_path / "AGENTS.md", "2026-01-01T00:00:00")
    _set_mtime_iso(tmp_path / "core" / "decisions.md", "2026-04-01T00:00:00")

    state = collect_agents_md_state(tmp_path)

    assert state.agents_md_legacy_at_includes == ["@core/overview.md", "@core/decisions.md"]
    assert state.claude_md_legacy_at_includes == ["@core/overview.md", "@core/decisions.md"]
    assert state.markers_present is False
    assert state.active_decision_ids == ["D-001", "D-002"]
    assert state.digest_ids == []
    assert state.claude_md_normalizable is True
    assert "agents_md_legacy_includes" in state.drift_signals
    assert "claude_md_legacy_includes" in state.drift_signals
    assert "markers_missing" in state.drift_signals
    assert "core_decisions_newer_than_agents_md" in state.drift_signals
    assert "active_decisions_differ_from_digest" in state.drift_signals


def test_collect_agents_md_state_mtime_drift_only(tmp_path: Path) -> None:
    _write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    _write(
        tmp_path / "AGENTS.md",
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        - **D-001:** Stay calm.
        {END_MARKER}
        """,
    )
    _write(
        tmp_path / "core" / "decisions.md",
        """
        ## D-001: Stay calm (wording updated)

        - **Status:** active
        """,
    )
    _set_mtime_iso(tmp_path / "AGENTS.md", "2026-04-01T00:00:00")
    _set_mtime_iso(tmp_path / "core" / "decisions.md", "2026-04-15T00:00:00")

    state = collect_agents_md_state(tmp_path)

    assert state.active_decision_ids == ["D-001"]
    assert state.digest_ids == ["D-001"]
    assert "core_decisions_newer_than_agents_md" in state.drift_signals
    assert "active_decisions_differ_from_digest" not in state.drift_signals


def test_collect_agents_md_state_no_agents_md(tmp_path: Path) -> None:
    state = collect_agents_md_state(tmp_path)
    assert state.agents_md_present is False
    assert state.claude_md_present is False
    assert state.drift_signals == []


def test_collect_agents_md_state_claude_md_with_extra_content_not_normalizable(tmp_path: Path) -> None:
    _write(
        tmp_path / "CLAUDE.md",
        """
        @AGENTS.md
        @core/overview.md

        # Project-specific guidance
        Always use uv.
        """,
    )
    _write(tmp_path / "AGENTS.md", "# P\n")
    state = collect_agents_md_state(tmp_path)
    assert state.claude_md_legacy_at_includes == ["@core/overview.md"]
    assert state.claude_md_normalizable is False
    assert "claude_md_legacy_includes" in state.drift_signals


def test_collect_agents_md_state_all_decisions_superseded_still_signals_drift(tmp_path: Path) -> None:
    # All active decisions are gone (all superseded) but the digest still lists
    # stale entries. The drift signal must fire so the user gets a chance to
    # clean the stale digest, instead of it silently rotting forever.
    _write(tmp_path / "CLAUDE.md", "@AGENTS.md\n")
    _write(
        tmp_path / "AGENTS.md",
        f"""
        # P — Agent Guide

        {BEGIN_MARKER}
        - **D-001:** Stale rule still in digest.
        {END_MARKER}
        """,
    )
    _write(
        tmp_path / "core" / "decisions.md",
        """
        ## D-001: First decision

        - **Status:** superseded by D-002

        ---

        ## D-002: Second decision

        - **Status:** abandoned
        """,
    )
    _set_mtime_iso(tmp_path / "AGENTS.md", "2026-04-15T00:00:00")
    _set_mtime_iso(tmp_path / "core" / "decisions.md", "2026-04-01T00:00:00")

    state = collect_agents_md_state(tmp_path)

    assert state.active_decision_ids == []
    assert state.digest_ids == ["D-001"]
    assert "active_decisions_differ_from_digest" in state.drift_signals


def test_agents_md_digest_state_does_not_expose_overview_mtime(tmp_path: Path) -> None:
    # overview_mtime_seconds was removed because no drift signal consumes it
    # and it added noise to the public JSON surface. Lock that decision in.
    state = collect_agents_md_state(tmp_path)
    assert "overview_mtime_seconds" not in state.model_dump()
