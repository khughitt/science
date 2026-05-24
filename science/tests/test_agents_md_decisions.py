from pathlib import Path

from science_tool.curate.agents_md import active_decision_sections, parse_active_decision_ids

_DOC = """# Decisions

## D-001: Live one
- **Status:** active
- **Decision:** x

## D-002: Dead one
- **Status:** superseded
- **Decision:** y
"""


def test_active_decision_sections_returns_only_active(tmp_path: Path):
    p = tmp_path / "decisions.md"
    p.write_text(_DOC, encoding="utf-8")
    sections = active_decision_sections(p)
    assert [sid for sid, _ in sections] == ["D-001"]
    assert "Live one" in sections[0][1]
    # parse_active_decision_ids still works (refactored onto the same helper)
    assert parse_active_decision_ids(p) == ["D-001"]


def test_active_decision_sections_missing_file(tmp_path: Path):
    assert active_decision_sections(tmp_path / "nope.md") == []
