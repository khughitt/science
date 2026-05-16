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
    _merge_canonical_fields,
    _pick_canonical_bibkey_case,
)


_PAPER_PROFILE = default_profile_for_kind("paper")
_PAPER_POLICY = read_merge_policy(_PAPER_PROFILE)
_PAPER_SECTIONS = read_canonical_body_sections(_PAPER_PROFILE)


def _merge_cand(slug: str, fields: dict) -> PromoteCandidate:
    """Build a PromoteCandidate with the given canonical_fields. Used by
    _merge_canonical_fields tests where only fields + slug matter."""
    return PromoteCandidate(
        bibkey="X", bibkey_normalized="x", project_slug=slug,
        project_root=Path("/tmp"), overlay_source_path=Path("/tmp/x.md"),
        canonical_fields=fields, project_only_fields={},
        canonical_body={}, project_only_body={},
    )


def _case_cand(slug: str, bibkey: str) -> PromoteCandidate:
    """Build a PromoteCandidate with the given bibkey case. Used by
    _pick_canonical_bibkey_case tests."""
    return PromoteCandidate(
        bibkey=bibkey, bibkey_normalized=bibkey.casefold(),
        project_slug=slug, project_root=Path("/tmp"),
        overlay_source_path=Path("/tmp/x.md"),
        canonical_fields={}, project_only_fields={},
        canonical_body={}, project_only_body={},
    )


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


def test_merge_canonical_fields_one_sided_auto_takes() -> None:
    a = _merge_cand("A", {"title": "T", "authors": ["a"]})
    b = _merge_cand("B", {"title": "T", "doi": "10.x"})

    merged, conflicts = _merge_canonical_fields([a, b], _PAPER_POLICY)
    assert merged["title"] == "T"
    assert merged["authors"] == ["a"]
    assert merged["doi"] == "10.x"
    assert conflicts == []


def test_merge_canonical_fields_identical_auto_takes() -> None:
    a = _merge_cand("A", {"year": 2025})
    b = _merge_cand("B", {"year": 2025})
    merged, conflicts = _merge_canonical_fields([a, b], _PAPER_POLICY)
    assert merged["year"] == 2025
    assert conflicts == []


def test_merge_canonical_fields_emits_conflict_on_differing_values() -> None:
    a = _merge_cand("A", {"year": 2023})
    b = _merge_cand("B", {"year": 2024})
    merged, conflicts = _merge_canonical_fields([a, b], _PAPER_POLICY)
    assert "year" not in merged
    assert len(conflicts) == 1
    assert conflicts[0].field == "year"
    assert conflicts[0].candidates == {"A": 2023, "B": 2024}


def test_merge_canonical_fields_append_unions_deterministically() -> None:
    a = _merge_cand("A", {"ontology_terms": ["foo", "bar"], "datasets": ["dataset:d1"]})
    b = _merge_cand("B", {"ontology_terms": ["bar", "baz"], "datasets": ["dataset:d2", "dataset:d1"]})
    merged, conflicts = _merge_canonical_fields([a, b], _PAPER_POLICY)
    assert merged["ontology_terms"] == ["bar", "baz", "foo"]
    assert merged["datasets"] == ["dataset:d1", "dataset:d2"]
    assert conflicts == []


def test_pick_canonical_bibkey_case_from_order_first() -> None:
    cands = [_case_cand("B", "huh2024"), _case_cand("A", "Huh2024")]
    assert _pick_canonical_bibkey_case(cands, ["A", "B"]) == "Huh2024"
    assert _pick_canonical_bibkey_case(cands, ["B", "A"]) == "huh2024"


def test_pick_canonical_bibkey_case_tiebreaks_by_slug() -> None:
    cands = [_case_cand("z-proj", "huh2024"), _case_cand("a-proj", "Huh2024")]
    assert _pick_canonical_bibkey_case(cands, ["a-proj", "z-proj"]) == "Huh2024"
