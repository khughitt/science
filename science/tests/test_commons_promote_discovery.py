"""Tests for science_tool.commons.promote — discovery + module surface."""

from __future__ import annotations

import pytest


def test_promote_module_imports() -> None:
    from science_tool.commons import promote  # noqa: F401


def test_promote_public_surface_exports() -> None:
    """Public types live on the science_tool.commons package surface."""
    from science_tool.commons import (
        ConflictResolution,
        DiscoveryResult,
        FailedCandidate,
        FieldConflict,
        OverlayRewrite,
        PromoteCandidate,
        PromoteDecision,
        PromotePlan,
        PromoteResult,
        apply_promote,
        discover_paper_candidates,
        plan_promote,
        prompt_resolve,
        resolve_project_by_id,
    )
    # Reference every name so pyright doesn't complain about unused imports.
    assert all([
        ConflictResolution, DiscoveryResult, FailedCandidate, FieldConflict,
        OverlayRewrite, PromoteCandidate, PromoteDecision, PromotePlan,
        PromoteResult, apply_promote, discover_paper_candidates, plan_promote,
        prompt_resolve, resolve_project_by_id,
    ])


def test_dataclass_surface_is_frozen() -> None:
    from science_tool.commons.promote import (
        ConflictResolution,
        DiscoveryResult,
        FailedCandidate,
        FieldConflict,
        OverlayRewrite,
        PromoteCandidate,
        PromoteDecision,
        PromotePlan,
        PromoteResult,
    )

    for cls in (
        PromoteCandidate,
        FieldConflict,
        ConflictResolution,
        OverlayRewrite,
        PromoteDecision,
        FailedCandidate,
        DiscoveryResult,
        PromotePlan,
        PromoteResult,
    ):
        # frozen=True is the authoritative flag on the dataclass params
        assert cls.__dataclass_params__.frozen, f"{cls.__name__} must be frozen"


def test_normalize_bibkey_for_match_casefolds() -> None:
    from science_tool.commons.promote import _normalize_bibkey_for_match
    assert _normalize_bibkey_for_match("Huh2024") == "huh2024"
    assert _normalize_bibkey_for_match("ADAMS2025") == "adams2025"
    assert _normalize_bibkey_for_match("Adams2025.md") == "adams2025"


def test_normalize_bibkey_for_match_rejects_empty() -> None:
    from science_tool.commons.promote import _normalize_bibkey_for_match
    from science_tool.commons.errors import PromoteCandidateError
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("")
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("   ")


def test_normalize_bibkey_for_match_rejects_regex_failing() -> None:
    from science_tool.commons.promote import _normalize_bibkey_for_match
    from science_tool.commons.errors import PromoteCandidateError
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("1leading-digit")
    with pytest.raises(PromoteCandidateError):
        _normalize_bibkey_for_match("has space")


def test_classify_paper_file_kind_explicit_paper() -> None:
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"kind": "paper"}) == "paper"
    assert _classify_paper_file_kind({"type": "paper"}) == "paper"


def test_classify_paper_file_kind_explicit_other_kind() -> None:
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"kind": "review-article"}) == "skip-other-kind"
    assert _classify_paper_file_kind({"type": "dataset"}) == "skip-other-kind"


def test_classify_paper_file_kind_no_kind_inferred_as_paper() -> None:
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"title": "Foo"}) == "paper"
    assert _classify_paper_file_kind({}) == "paper"


def test_classify_paper_file_kind_non_paper_id_prefix() -> None:
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"id": "dataset:foo"}) == "skip-other-id"
    assert _classify_paper_file_kind({"id": "paper:Adams2025"}) == "paper"


def test_classify_paper_file_kind_explicit_kind_overrides_contradictory_id() -> None:
    """Rule ordering: explicit `kind: paper` wins over a non-paper `id:` prefix
    (the id check is defense-in-depth against directory-inference, not
    against an explicit kind declaration)."""
    from science_tool.commons.promote import _classify_paper_file_kind
    assert _classify_paper_file_kind({"id": "dataset:foo", "kind": "paper"}) == "paper"
    assert _classify_paper_file_kind({"id": "paper:Adams2025", "kind": "dataset"}) == "skip-other-kind"


def test_parse_paper_file_returns_frontmatter_and_body(tmp_path) -> None:
    from science_tool.commons.promote import _parse_paper_file
    p = tmp_path / "Adams2025.md"
    p.write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "title: Hello\n"
        "---\n"
        "\n"
        "## Key Findings\n\nOne.\n",
        encoding="utf-8",
    )
    fm, body = _parse_paper_file(p)
    assert fm["id"] == "paper:Adams2025"
    assert fm["title"] == "Hello"
    assert "## Key Findings" in body


def test_parse_paper_file_no_frontmatter_raises(tmp_path) -> None:
    from science_tool.commons.promote import _parse_paper_file
    from science_tool.commons.errors import PromoteCandidateError
    p = tmp_path / "broken.md"
    p.write_text("just a body, no frontmatter\n", encoding="utf-8")
    with pytest.raises(PromoteCandidateError, match="no frontmatter"):
        _parse_paper_file(p)


def test_parse_paper_file_malformed_yaml_raises(tmp_path) -> None:
    from science_tool.commons.promote import _parse_paper_file
    from science_tool.commons.errors import PromoteCandidateError
    p = tmp_path / "broken.md"
    p.write_text("---\nid: : :\n---\nbody\n", encoding="utf-8")
    with pytest.raises(PromoteCandidateError, match="frontmatter parse"):
        _parse_paper_file(p)


def test_scan_project_papers_walks_doc_papers(tmp_path) -> None:
    from science_tool.commons.promote import _scan_project_papers

    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\n---\n\nbody\n",
        encoding="utf-8",
    )
    (papers / "Huh2024.md").write_text(
        "---\nid: paper:Huh2024\ntitle: H\nkind: paper\n---\n",
        encoding="utf-8",
    )

    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    bibkeys = sorted(c.slug for c in candidates)
    assert bibkeys == ["Adams2025", "Huh2024"]
    assert failures == []


def test_scan_project_papers_skips_already_promoted(tmp_path) -> None:
    from science_tool.commons.promote import _scan_project_papers
    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Done2024.md").write_text(
        "---\nid: paper:Done2024\noverlay_of: paper:Done2024\npin_version: '1.0.0'\n---\n",
        encoding="utf-8",
    )
    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    assert candidates == []
    assert failures == []


def test_scan_project_papers_records_failures_without_aborting(tmp_path) -> None:
    from science_tool.commons.promote import _scan_project_papers
    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Good2024.md").write_text(
        "---\nid: paper:Good2024\ntitle: G\n---\n",
        encoding="utf-8",
    )
    (papers / "Broken2024.md").write_text(
        "no frontmatter\n",
        encoding="utf-8",
    )
    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    assert [c.slug for c in candidates] == ["Good2024"]
    assert len(failures) == 1
    assert failures[0].source_path.name == "Broken2024.md"
    assert failures[0].error_class == "PromoteCandidateError"


def test_scan_project_papers_skips_other_kind_with_warning(tmp_path, caplog) -> None:
    import logging
    from science_tool.commons.promote import _scan_project_papers
    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Misfiled.md").write_text(
        "---\nid: paper:Misfiled\ntitle: X\nkind: dataset\n---\n",
        encoding="utf-8",
    )
    caplog.set_level(logging.WARNING, logger="science_tool.commons.promote")
    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    assert candidates == []
    assert failures == []
    assert "kind/type is not 'paper'" in caplog.text


def test_scan_project_papers_fails_when_id_does_not_match_stem(tmp_path) -> None:
    """Source files with an explicit `id:` that disagrees with the filename
    stem are rejected at discovery (design §4.1.3)."""
    from science_tool.commons.promote import _scan_project_papers
    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Adams2025.md").write_text(
        "---\nid: paper:WrongStem\ntitle: A\n---\n",
        encoding="utf-8",
    )
    candidates, failures = _scan_project_papers(tmp_path, "test-project")
    assert candidates == []
    assert len(failures) == 1
    assert failures[0].source_path.name == "Adams2025.md"
    assert "does not match filename stem" in failures[0].error_message


def test_discover_groups_by_normalized_bibkey(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import discover_paper_candidates

    proj_a = tmp_path / "proj_a"
    (proj_a / "doc" / "papers").mkdir(parents=True)
    (proj_a / "doc" / "papers" / "Huh2024.md").write_text(
        "---\nid: paper:Huh2024\ntitle: A\n---\n",
        encoding="utf-8",
    )
    proj_b = tmp_path / "proj_b"
    (proj_b / "doc" / "papers").mkdir(parents=True)
    (proj_b / "doc" / "papers" / "huh2024.md").write_text(
        "---\nid: paper:huh2024\ntitle: B\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: {"proj_a": proj_a, "proj_b": proj_b}[slug],
    )

    result = discover_paper_candidates(["proj_a", "proj_b"])
    assert set(result.candidates_by_slug) == {"huh2024"}
    assert len(result.candidates_by_slug["huh2024"]) == 2
    assert result.failed_candidates == []


def test_discover_rejects_null_id_via_resolver(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import CommonsError
    from science_tool.commons.promote import discover_paper_candidates

    def fake_resolve(slug: str):
        raise CommonsError(f"project {slug!r} is registered with id: null; ...")

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id", fake_resolve
    )
    with pytest.raises(CommonsError, match="id: null"):
        discover_paper_candidates(["legacy-slug"])


def test_discover_carries_failures(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import discover_paper_candidates

    proj = tmp_path / "proj"
    (proj / "doc" / "papers").mkdir(parents=True)
    (proj / "doc" / "papers" / "Good.md").write_text(
        "---\nid: paper:Good\ntitle: G\n---\n",
        encoding="utf-8",
    )
    (proj / "doc" / "papers" / "Broken.md").write_text(
        "no frontmatter\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_paper_candidates(["proj"])
    assert set(result.candidates_by_slug) == {"good"}
    assert len(result.failed_candidates) == 1
    assert result.failed_candidates[0].source_path.name == "Broken.md"
