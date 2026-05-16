"""Tests for science_tool.commons.promote — plan phase + helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from science_model.entity_schema import (
    MergePolicy,
    default_profile_for_kind,
    read_canonical_body_sections,
    read_merge_policy,
)
from science_tool.commons.promote import (
    PromoteCandidate,
    _classify_entity,
)


_PAPER_PROFILE = default_profile_for_kind("paper")
_PAPER_POLICY = read_merge_policy(_PAPER_PROFILE)
_PAPER_SECTIONS = read_canonical_body_sections(_PAPER_PROFILE)


def test_classify_entity_splits_canonical_vs_project_only() -> None:
    fm = {
        "id": "paper:Adams2025",
        "type": "paper",
        "bibkey": "Adams2025",
        "title": "A title",
        "authors": ["Adams, J."],
        "year": 2025,
        "tags": ["foo", "bar"],
        "related": ["question:q1"],
        "status": "active",
        "created": "2026-01-01",
        "updated": "2026-05-15",
    }
    body = "## Key Findings\n\nfoo\n\n## Project Use\n\nbar\n"
    can_f, proj_f, can_b, proj_b = _classify_entity(
        fm, body, _PAPER_POLICY, _PAPER_SECTIONS
    )
    assert can_f["title"] == "A title"
    assert can_f["authors"] == ["Adams, J."]
    assert can_f["year"] == 2025
    assert "id" not in can_f
    assert "type" not in can_f
    assert "bibkey" not in can_f
    assert "id" not in proj_f
    assert "type" not in proj_f
    assert "bibkey" not in proj_f
    assert "tags" in proj_f
    assert "related" in proj_f
    assert "status" in proj_f
    assert "created" in proj_f
    assert "Key Findings" in can_b
    assert "Project Use" in proj_b


def test_classify_entity_drops_id_even_on_case_divergent_input() -> None:
    fm_upper = {"id": "paper:Adams2025", "type": "paper", "title": "T"}
    fm_lower = {"id": "paper:adams2025", "type": "paper", "title": "T"}
    upper_can, _, _, _ = _classify_entity(fm_upper, "", _PAPER_POLICY, _PAPER_SECTIONS)
    lower_can, _, _, _ = _classify_entity(fm_lower, "", _PAPER_POLICY, _PAPER_SECTIONS)
    assert "id" not in upper_can
    assert "id" not in lower_can


def test_classify_entity_coerces_string_authors_to_single_element_list() -> None:
    fm = {
        "id": "paper:X",
        "type": "paper",
        "title": "T",
        "authors": "Wang et al.",
    }
    can_f, _, _, _ = _classify_entity(fm, "", _PAPER_POLICY, _PAPER_SECTIONS)
    assert can_f["authors"] == ["Wang et al."]


def test_classify_entity_renames_journal_to_venue() -> None:
    fm = {"id": "paper:X", "type": "paper", "title": "T", "journal": "Cell"}
    can_f, _, _, _ = _classify_entity(fm, "", _PAPER_POLICY, _PAPER_SECTIONS)
    assert can_f.get("venue") == "Cell"
    assert "journal" not in can_f


def test_classify_entity_strips_overlay_only_keys_from_input() -> None:
    fm = {
        "id": "paper:X",
        "type": "paper",
        "title": "T",
        "overlay_of": "paper:X",
        "pin_version": "1.0.0",
    }
    can_f, proj_f, _, _ = _classify_entity(fm, "", _PAPER_POLICY, _PAPER_SECTIONS)
    assert "overlay_of" not in can_f
    assert "overlay_of" not in proj_f
    assert "pin_version" not in can_f
    assert "pin_version" not in proj_f


def test_classify_entity_body_section_match_is_case_insensitive() -> None:
    fm = {"id": "paper:X", "type": "paper", "title": "T"}
    body = "## key findings\n\nlowercase heading\n"
    _, _, can_b, _ = _classify_entity(fm, body, _PAPER_POLICY, _PAPER_SECTIONS)
    assert any(k.casefold() == "key findings" for k in can_b)
