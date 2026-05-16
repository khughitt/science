"""Tests for science_tool.commons.promote — plan phase + helpers."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from science_model.entity_schema import (
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
        slug="X",
        slug_normalized="x",
        project_slug=slug,
        project_root=Path("/tmp"),
        overlay_source_path=Path("/tmp/x.md"),
        canonical_fields=fields,
        project_only_fields={},
        canonical_body={},
        project_only_body={},
    )


def _case_cand(slug: str, bibkey: str) -> PromoteCandidate:
    """Build a PromoteCandidate with the given bibkey case. Used by
    _pick_canonical_bibkey_case tests."""
    return PromoteCandidate(
        slug=bibkey,
        slug_normalized=bibkey.casefold(),
        project_slug=slug,
        project_root=Path("/tmp"),
        overlay_source_path=Path("/tmp/x.md"),
        canonical_fields={},
        project_only_fields={},
        canonical_body={},
        project_only_body={},
    )


def test_plan_carries_kind(tmp_path) -> None:
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        DiscoveryResult,
        plan_promote,
    )

    discovery = DiscoveryResult(candidates_by_slug={}, failed_candidates=[])
    plan = plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_PAPER)
    assert plan.kind is PROMOTE_KIND_PAPER


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
    can_f, proj_f, can_b, proj_b = _classify_entity(fm, body, _PAPER_POLICY, _PAPER_SECTIONS)
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


def test_coerce_date_for_yaml() -> None:
    from science_tool.commons.promote import _coerce_date_for_yaml

    assert _coerce_date_for_yaml(date(2026, 5, 15)) == "2026-05-15"
    assert _coerce_date_for_yaml(datetime(2026, 5, 15, 12, 30)) == "2026-05-15"
    assert _coerce_date_for_yaml("2026-05-15") == "2026-05-15"
    assert _coerce_date_for_yaml("already-not-a-date") == "already-not-a-date"


def test_render_canonical_includes_base_required_fields() -> None:
    from science_tool.commons.promote import _render_canonical, PromoteDecision

    decision = PromoteDecision(
        slug="Adams2025",
        canonical_path=Path("/c/papers/Adams2025.md"),
        canonical_content="",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_canonical(
        decision,
        canonical_fields={"title": "T", "authors": ["A"], "year": 2025},
        canonical_body={"Key Findings": "\nOne.\n"},
        created=date(2026, 5, 15),
        updated=date(2026, 5, 15),
    )
    assert "schema_profile: science-entity-base/1.0+paper/2.0" in rendered
    assert 'version: "1.0.0"' in rendered
    assert "id: paper:Adams2025" in rendered
    assert "type: paper" in rendered
    assert "title: T" in rendered
    assert 'created: "2026-05-15"' in rendered
    assert "tags: []" in rendered
    assert "## Key Findings" in rendered
    assert "One." in rendered


def test_render_canonical_dates_are_quoted_strings() -> None:
    from science_tool.commons.promote import _render_canonical, PromoteDecision
    import yaml

    decision = PromoteDecision(
        slug="X",
        canonical_path=Path("/c/papers/X.md"),
        canonical_content="",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_canonical(
        decision,
        canonical_fields={"title": "T"},
        canonical_body={},
        created=date(2026, 5, 15),
        updated=date(2026, 5, 15),
    )
    fm_block = rendered.split("---", 2)[1]
    fm = yaml.safe_load(fm_block)
    assert isinstance(fm["created"], str)
    assert fm["created"] == "2026-05-15"


def test_render_overlay_preserves_project_dates_and_overlay_fields() -> None:
    from science_tool.commons.promote import _render_overlay, PromoteDecision

    decision = PromoteDecision(
        slug="Adams2025",
        canonical_path=Path("/c/papers/Adams2025.md"),
        canonical_content="",
        canonical_version="1.0.0",
        overlays={},
        resolved_conflicts=(),
    )
    rendered = _render_overlay(
        decision,
        project_slug="natural-systems",
        project_only_fields={
            "tags": ["foo", "bar"],
            "status": "active",
            "created": "2026-01-01",
            "updated": "2026-05-15",
            "related": ["question:q1"],
        },
        project_only_body={"Project Use": "\nused here\n"},
    )
    assert "id: paper:Adams2025" in rendered
    assert "overlay_of: paper:Adams2025" in rendered
    assert 'pin_version: "1.0.0"' in rendered
    assert 'created: "2026-01-01"' in rendered
    assert 'updated: "2026-05-15"' in rendered
    assert "## Project Use" in rendered
    assert "schema_profile" not in rendered


def test_plan_promote_groups_by_bibkey_and_carries_failures(tmp_path) -> None:
    from science_tool.commons.promote import (
        DiscoveryResult,
        FailedCandidate,
        PROMOTE_KIND_PAPER,
        plan_promote,
    )

    def _cand(slug, bibkey, fields):
        return PromoteCandidate(
            slug=bibkey,
            slug_normalized=bibkey.casefold(),
            project_slug=slug,
            project_root=Path("/tmp") / slug,
            overlay_source_path=Path("/tmp") / slug / "doc/papers" / f"{bibkey}.md",
            canonical_fields={},
            project_only_fields={},
            canonical_body={},
            project_only_body={
                "__raw_frontmatter__": {"id": f"paper:{bibkey}", "type": "paper", "title": "T", **fields},
                "__raw_body__": "",
            },
        )

    discovery = DiscoveryResult(
        candidates_by_slug={
            "adams2025": [_cand("A", "Adams2025", {"year": 2025})],
        },
        failed_candidates=[
            FailedCandidate(
                slug="x",
                project_slug="A",
                source_path=Path("/x"),
                error_class="PromoteCandidateError",
                error_message="bad",
            )
        ],
    )

    plan = plan_promote(
        discovery,
        commons_root=tmp_path,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
    )
    assert len(plan.decisions) == 1
    assert plan.decisions[0].slug == "Adams2025"
    assert len(plan.failed_candidates) == 1
    assert plan.failed_candidates[0].error_class == "PromoteCandidateError"


def test_plan_promote_invokes_resolver_on_conflict(tmp_path) -> None:
    from science_tool.commons.promote import (
        DiscoveryResult,
        PROMOTE_KIND_PAPER,
        plan_promote,
    )

    def _cand(slug, year):
        return PromoteCandidate(
            slug="Dang2023",
            slug_normalized="dang2023",
            project_slug=slug,
            project_root=Path("/tmp") / slug,
            overlay_source_path=Path("/tmp") / slug / "doc/papers/Dang2023.md",
            canonical_fields={},
            project_only_fields={},
            canonical_body={},
            project_only_body={
                "__raw_frontmatter__": {
                    "id": "paper:Dang2023",
                    "type": "paper",
                    "title": "T",
                    "year": year,
                },
                "__raw_body__": "",
            },
        )

    discovery = DiscoveryResult(
        candidates_by_slug={"dang2023": [_cand("A", 2023), _cand("B", 2024)]},
        failed_candidates=[],
    )

    resolved: list = []

    def picker(conflict):
        resolved.append(conflict.field)
        return conflict.candidates["A"]

    plan = plan_promote(
        discovery,
        commons_root=tmp_path,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=picker,
    )
    assert resolved == ["year"]
    decision = plan.decisions[0]
    assert len(decision.resolved_conflicts) == 1
    assert decision.resolved_conflicts[0].resolved_to == 2023


def test_plan_promote_case_collision_picks_first_from_order(tmp_path) -> None:
    from science_tool.commons.promote import DiscoveryResult, PROMOTE_KIND_PAPER, plan_promote

    def _cand(slug, bibkey):
        return PromoteCandidate(
            slug=bibkey,
            slug_normalized=bibkey.casefold(),
            project_slug=slug,
            project_root=Path("/tmp") / slug,
            overlay_source_path=Path("/tmp") / slug / "doc/papers" / f"{bibkey}.md",
            canonical_fields={},
            project_only_fields={},
            canonical_body={},
            project_only_body={
                "__raw_frontmatter__": {
                    "id": f"paper:{bibkey}",
                    "type": "paper",
                    "title": "T",
                },
                "__raw_body__": "",
            },
        )

    discovery = DiscoveryResult(
        candidates_by_slug={"huh2024": [_cand("A", "Huh2024"), _cand("B", "huh2024")]},
        failed_candidates=[],
    )
    plan = plan_promote(
        discovery,
        commons_root=tmp_path,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=lambda c: None,
        from_order=["A", "B"],
    )
    assert plan.decisions[0].slug == "Huh2024"
    b_overlay = plan.decisions[0].overlays["B"]
    assert b_overlay.rename_from is not None
    assert b_overlay.rename_from.name == "huh2024.md"
    assert b_overlay.path.name == "Huh2024.md"


def test_plan_promote_calls_profile_readers_with_kind_profile(tmp_path, monkeypatch) -> None:
    """Pin the per-kind profile lookups. Without this guard, plan_promote
    would silently use the paper policy for topic/theme runs and misclassify
    fields like topic 'datasets' or theme 'evidence_refs'."""
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        PROMOTE_KIND_TOPIC,
        DiscoveryResult,
        plan_promote,
    )
    import science_tool.commons.promote as promote_mod

    captured = {}
    real_read_merge_policy = promote_mod.read_merge_policy
    real_read_canonical_body_sections = promote_mod.read_canonical_body_sections

    def spy_merge_policy(profile, *a, **kw):
        captured["merge_policy_profile"] = profile
        return real_read_merge_policy(profile, *a, **kw)

    def spy_body_sections(profile, *a, **kw):
        captured["body_sections_profile"] = profile
        return real_read_canonical_body_sections(profile, *a, **kw)

    monkeypatch.setattr(promote_mod, "read_merge_policy", spy_merge_policy)
    monkeypatch.setattr(promote_mod, "read_canonical_body_sections", spy_body_sections)

    discovery = DiscoveryResult(candidates_by_slug={}, failed_candidates=[])
    plan_promote(discovery, commons_root=tmp_path, kind=PROMOTE_KIND_TOPIC)
    assert captured["merge_policy_profile"] == PROMOTE_KIND_TOPIC.default_profile
    assert captured["body_sections_profile"] == PROMOTE_KIND_TOPIC.default_profile
    assert PROMOTE_KIND_TOPIC.default_profile != PROMOTE_KIND_PAPER.default_profile
