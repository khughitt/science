"""Phase 3c: decision owner rendering + generated view + round-trip."""

from __future__ import annotations

from pathlib import Path

from science_tool.graph.decision_log import (
    DecisionSection,
    parse_decision_log,
    read_decision_owners,
    render_decisions_view,
    render_owner_file,
)


def _section(local_id: str, title: str, body: str, date=None, status=None) -> DecisionSection:
    return DecisionSection(f"decision:{local_id}", local_id, title, date, status, body)


def test_render_owner_file_shape():
    sec = _section("D1", "Z-score first", "**Why**: scale.\n", date="2026-03-31", status="active")
    text = render_owner_file(sec, promoted_from="knowledge/sources/local/entities.yaml", today="2026-06-09")
    assert text.startswith("---\n")
    assert "id: decision:D1\n" in text
    assert "type: decision\n" in text
    assert "title: Z-score first\n" in text
    assert "date: '2026-03-31'\n" in text or "date: 2026-03-31\n" in text
    assert "status: active\n" in text
    # created/updated derive from the parsed Date when present.
    assert "created: '2026-03-31'\n" in text or "created: 2026-03-31\n" in text
    assert "updated: '2026-03-31'\n" in text or "updated: 2026-03-31\n" in text
    assert "source_path: core/decisions.md\n" in text
    assert "promoted_from: knowledge/sources/local/entities.yaml\n" in text
    assert "**Why**: scale." in text


def test_render_owner_file_stamps_conformance_fields_when_log_metadata_absent():
    """No parsed Date/Status -> default status + run-date created/updated, but the
    informational `date:` field stays absent."""
    sec = _section("D9", "No metadata", "Prose.\n")
    text = render_owner_file(sec, promoted_from="x", today="2026-06-09")
    assert "date:" not in text  # no informational date when the log carried none
    assert "status: active\n" in text  # decision default
    assert "created: '2026-06-09'\n" in text or "created: 2026-06-09\n" in text
    assert "updated: '2026-06-09'\n" in text or "updated: 2026-06-09\n" in text


def test_generated_view_sorts_natural_and_has_banner(tmp_path: Path):
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    for local in ("D1", "D2", "D10"):
        (d / f"{local}.md").write_text(
            render_owner_file(
                _section(local, f"Title {local}", f"Body {local}.\n", status="active"),
                promoted_from="x",
                today="2026-06-09",
            ),
            encoding="utf-8",
        )
    out = render_decisions_view(read_decision_owners(d))
    assert out.startswith("<!-- GENERATED")
    # Natural order: D1, D2, D10 (not lexical D1, D10, D2).
    assert out.index("## D1.") < out.index("## D2.") < out.index("## D10.")
    # No duplicated id in the heading.
    assert "## D1. Title D1" in out
    assert "## D1. D1." not in out


def test_round_trip_semantic_equality(tmp_path: Path):
    original = """\
# Decisions

## D1. Z-score first (2026-03-31)

**Date**: 2026-03-31
**Status**: active

**Why**: scale differences.

---

## D10. Later decision (2026-05-01)

- **Date:** 2026-05-01
- **Status:** active

Body with an internal rule:

---

Tail note.

---
"""
    idx = parse_decision_log(original)
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    for sec in idx.sections.values():
        (d / f"{sec.local_id}.md").write_text(
            render_owner_file(sec, promoted_from="x", today="2026-06-09"), encoding="utf-8"
        )
    rendered = render_decisions_view(read_decision_owners(d))
    idx2 = parse_decision_log(rendered)
    assert idx2.sections == idx.sections  # frozen dataclass equality over all fields
