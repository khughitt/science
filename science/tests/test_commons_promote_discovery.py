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
        discover_candidates,
        plan_promote,
        prompt_resolve,
        resolve_project_by_id,
    )

    # Reference every name so pyright doesn't complain about unused imports.
    assert all(
        [
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
            discover_candidates,
            plan_promote,
            prompt_resolve,
            resolve_project_by_id,
        ]
    )


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
        params = getattr(cls, "__dataclass_params__", None)
        assert params is not None, f"{cls.__name__} must be a dataclass"
        assert params.frozen, f"{cls.__name__} must be frozen"


def test_normalize_slug_for_match_casefolds() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _normalize_slug_for_match

    assert _normalize_slug_for_match("Huh2024", PROMOTE_KIND_PAPER) == "huh2024"
    assert _normalize_slug_for_match("ADAMS2025", PROMOTE_KIND_PAPER) == "adams2025"
    assert _normalize_slug_for_match("Adams2025.md", PROMOTE_KIND_PAPER) == "adams2025"


def test_normalize_slug_for_match_rejects_empty() -> None:
    from science_tool.commons.errors import PromoteCandidateError
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _normalize_slug_for_match

    with pytest.raises(PromoteCandidateError):
        _normalize_slug_for_match("", PROMOTE_KIND_PAPER)
    with pytest.raises(PromoteCandidateError):
        _normalize_slug_for_match("   ", PROMOTE_KIND_PAPER)


def test_normalize_slug_for_match_rejects_regex_failing() -> None:
    from science_tool.commons.errors import PromoteCandidateError
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _normalize_slug_for_match

    with pytest.raises(PromoteCandidateError):
        _normalize_slug_for_match("1leading-digit", PROMOTE_KIND_PAPER)
    with pytest.raises(PromoteCandidateError):
        _normalize_slug_for_match("has space", PROMOTE_KIND_PAPER)


def test_normalize_slug_for_match_paper_casefolds() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _normalize_slug_for_match

    assert _normalize_slug_for_match("Adams2025", PROMOTE_KIND_PAPER) == "adams2025"
    assert _normalize_slug_for_match("Adams2025.md", PROMOTE_KIND_PAPER) == "adams2025"


def test_normalize_slug_for_match_topic_returns_stem_as_is() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _normalize_slug_for_match

    assert _normalize_slug_for_match("hypothesis", PROMOTE_KIND_TOPIC) == "hypothesis"
    assert _normalize_slug_for_match("hypothesis.md", PROMOTE_KIND_TOPIC) == "hypothesis"


def test_normalize_slug_for_match_topic_rejects_uppercase() -> None:
    from science_tool.commons.errors import PromoteCandidateError
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _normalize_slug_for_match

    with pytest.raises(PromoteCandidateError):
        _normalize_slug_for_match("Hypothesis", PROMOTE_KIND_TOPIC)


def test_normalize_slug_for_match_theme_returns_stem_as_is() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, _normalize_slug_for_match

    assert _normalize_slug_for_match("my-theme", PROMOTE_KIND_THEME) == "my-theme"


def test_classify_file_kind_existing_paper_explicit_paper() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    assert _classify_file_kind({"kind": "paper"}, PROMOTE_KIND_PAPER) == "match"
    assert _classify_file_kind({"type": "paper"}, PROMOTE_KIND_PAPER) == "match"


def test_classify_file_kind_existing_paper_explicit_other_kind() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    assert _classify_file_kind({"kind": "review-article"}, PROMOTE_KIND_PAPER) == "skip-other-kind"
    assert _classify_file_kind({"type": "dataset"}, PROMOTE_KIND_PAPER) == "skip-other-kind"
    assert _classify_file_kind({"kind": ""}, PROMOTE_KIND_PAPER) == "skip-other-kind"
    assert _classify_file_kind({"type": ""}, PROMOTE_KIND_PAPER) == "skip-other-kind"


def test_classify_file_kind_existing_paper_no_kind_inferred_as_match() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    assert _classify_file_kind({"title": "Foo"}, PROMOTE_KIND_PAPER) == "match"
    assert _classify_file_kind({}, PROMOTE_KIND_PAPER) == "match"


def test_classify_file_kind_existing_paper_non_paper_id_prefix() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    assert _classify_file_kind({"id": "dataset:foo"}, PROMOTE_KIND_PAPER) == "skip-other-id"
    assert _classify_file_kind({"id": "paper:Adams2025"}, PROMOTE_KIND_PAPER) == "match"


def test_classify_file_kind_existing_paper_explicit_kind_overrides_contradictory_id() -> None:
    """Rule ordering: explicit `kind: paper` wins over a non-paper `id:` prefix
    (the id check is defense-in-depth against directory-inference, not
    against an explicit kind declaration)."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    assert _classify_file_kind({"id": "dataset:foo", "kind": "paper"}, PROMOTE_KIND_PAPER) == "match"
    assert _classify_file_kind({"id": "paper:Adams2025", "kind": "dataset"}, PROMOTE_KIND_PAPER) == "skip-other-kind"


def test_classify_file_kind_paper_explicit_match() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    assert _classify_file_kind({"kind": "paper"}, PROMOTE_KIND_PAPER) == "match"
    assert _classify_file_kind({"type": "paper"}, PROMOTE_KIND_PAPER) == "match"
    assert _classify_file_kind({"kind": "dataset", "type": "paper"}, PROMOTE_KIND_PAPER) == "match"


def test_classify_file_kind_topic_explicit_match() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _classify_file_kind

    assert _classify_file_kind({"kind": "topic"}, PROMOTE_KIND_TOPIC) == "match"
    assert _classify_file_kind({"type": "topic"}, PROMOTE_KIND_TOPIC) == "match"


def test_classify_file_kind_topic_disagreeing_kind_is_skip_other_kind() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _classify_file_kind

    assert _classify_file_kind({"kind": "paper"}, PROMOTE_KIND_TOPIC) == "skip-other-kind"
    assert _classify_file_kind({"type": "theme"}, PROMOTE_KIND_TOPIC) == "skip-other-kind"


def test_classify_file_kind_topic_id_prefix_disagreement_is_skip_other_id() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _classify_file_kind

    assert _classify_file_kind({"id": "paper:Adams2025"}, PROMOTE_KIND_TOPIC) == "skip-other-id"
    assert _classify_file_kind({"id": "topic:hypothesis"}, PROMOTE_KIND_TOPIC) == "match"


def test_classify_file_kind_no_kind_inferred() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, _classify_file_kind

    # No kind/type, no id -> infer "match" from directory placement.
    assert _classify_file_kind({"title": "Foo"}, PROMOTE_KIND_TOPIC) == "match"


def test_classify_file_kind_explicit_kind_overrides_contradictory_id() -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _classify_file_kind

    # Rule ordering: explicit kind/type wins over id-prefix.
    assert _classify_file_kind({"id": "dataset:foo", "kind": "paper"}, PROMOTE_KIND_PAPER) == "match"
    assert _classify_file_kind({"id": "dataset:foo", "type": "paper"}, PROMOTE_KIND_PAPER) == "match"


def test_parse_entity_file_returns_frontmatter_and_body(tmp_path) -> None:
    from science_tool.commons.promote import _parse_entity_file

    p = tmp_path / "Adams2025.md"
    p.write_text(
        "---\nid: paper:Adams2025\ntitle: Hello\n---\n\n## Key Findings\n\nOne.\n",
        encoding="utf-8",
    )
    fm, body = _parse_entity_file(p)
    assert fm["id"] == "paper:Adams2025"
    assert fm["title"] == "Hello"
    assert "## Key Findings" in body


def test_parse_entity_file_no_frontmatter_raises(tmp_path) -> None:
    from science_tool.commons.promote import _parse_entity_file
    from science_tool.commons.errors import PromoteCandidateError

    p = tmp_path / "broken.md"
    p.write_text("just a body, no frontmatter\n", encoding="utf-8")
    with pytest.raises(PromoteCandidateError, match="no frontmatter"):
        _parse_entity_file(p)


def test_parse_entity_file_malformed_yaml_raises(tmp_path) -> None:
    from science_tool.commons.promote import _parse_entity_file
    from science_tool.commons.errors import PromoteCandidateError

    p = tmp_path / "broken.md"
    p.write_text("---\nid: : :\n---\nbody\n", encoding="utf-8")
    with pytest.raises(PromoteCandidateError, match="frontmatter parse"):
        _parse_entity_file(p)


def test_scan_project_walks_doc_papers(tmp_path) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _scan_project

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

    candidates, failures = _scan_project(tmp_path, "test-project", PROMOTE_KIND_PAPER)
    bibkeys = sorted(c.slug for c in candidates)
    assert bibkeys == ["Adams2025", "Huh2024"]
    assert failures == []


def test_scan_project_skips_already_promoted(tmp_path) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _scan_project

    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Done2024.md").write_text(
        "---\nid: paper:Done2024\noverlay_of: paper:Done2024\npin_version: '1.0.0'\n---\n",
        encoding="utf-8",
    )
    candidates, failures = _scan_project(tmp_path, "test-project", PROMOTE_KIND_PAPER)
    assert candidates == []
    assert failures == []


def test_scan_project_records_failures_without_aborting(tmp_path) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _scan_project

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
    candidates, failures = _scan_project(tmp_path, "test-project", PROMOTE_KIND_PAPER)
    assert [c.slug for c in candidates] == ["Good2024"]
    assert len(failures) == 1
    assert failures[0].source_path.name == "Broken2024.md"
    assert failures[0].error_class == "PromoteCandidateError"


def test_scan_project_skips_other_kind_with_warning(tmp_path, caplog) -> None:
    import logging
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _scan_project

    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Misfiled.md").write_text(
        "---\nid: paper:Misfiled\ntitle: X\nkind: dataset\n---\n",
        encoding="utf-8",
    )
    caplog.set_level(logging.WARNING, logger="science_tool.commons.promote")
    candidates, failures = _scan_project(tmp_path, "test-project", PROMOTE_KIND_PAPER)
    assert candidates == []
    assert failures == []
    assert "kind/type is not 'paper'" in caplog.text


def test_scan_project_fails_when_id_does_not_match_stem(tmp_path) -> None:
    """Source files with an explicit `id:` that disagrees with the filename
    stem are rejected at discovery (design §4.1.3)."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, _scan_project

    papers = tmp_path / "doc" / "papers"
    papers.mkdir(parents=True)
    (papers / "Adams2025.md").write_text(
        "---\nid: paper:WrongStem\ntitle: A\n---\n",
        encoding="utf-8",
    )
    candidates, failures = _scan_project(tmp_path, "test-project", PROMOTE_KIND_PAPER)
    assert candidates == []
    assert len(failures) == 1
    assert failures[0].source_path.name == "Adams2025.md"
    assert "does not match filename stem" in failures[0].error_message


def test_discover_groups_by_normalized_bibkey(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, discover_candidates

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

    result = discover_candidates(["proj_a", "proj_b"], PROMOTE_KIND_PAPER)
    assert set(result.candidates_by_slug) == {"huh2024"}
    assert len(result.candidates_by_slug["huh2024"]) == 2
    assert result.failed_candidates == []


def test_discover_rejects_null_id_via_resolver(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import CommonsError
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, discover_candidates

    def fake_resolve(slug: str):
        raise CommonsError(f"project {slug!r} is registered with id: null; ...")

    monkeypatch.setattr("science_tool.commons.promote.resolve_project_by_id", fake_resolve)
    with pytest.raises(CommonsError, match="id: null"):
        discover_candidates(["legacy-slug"], PROMOTE_KIND_PAPER)


def test_discover_carries_failures(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, discover_candidates

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

    result = discover_candidates(["proj"], PROMOTE_KIND_PAPER)
    assert set(result.candidates_by_slug) == {"good"}
    assert len(result.failed_candidates) == 1
    assert result.failed_candidates[0].source_path.name == "Broken.md"


def test_discover_candidates_paper_kind_returns_expected_result(tmp_path, monkeypatch) -> None:
    """Calling discover_candidates(..., PROMOTE_KIND_PAPER) returns paper candidates."""
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, discover_candidates

    proj = tmp_path / "proj_x"
    (proj / "doc" / "papers").mkdir(parents=True)
    (proj / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntitle: A\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_x"], PROMOTE_KIND_PAPER)
    assert set(result.candidates_by_slug) == {"adams2025"}
    assert len(result.candidates_by_slug["adams2025"]) == 1


def test_discover_candidates_iterates_multiple_source_subdirs(tmp_path, monkeypatch) -> None:
    """Topic kind walks both doc/topics and doc/background/topics."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    proj = tmp_path / "proj_y"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "hypothesis.md").write_text(
        "---\nid: topic:hypothesis\ntitle: H\n---\n",
        encoding="utf-8",
    )
    (proj / "doc" / "background" / "topics").mkdir(parents=True)
    (proj / "doc" / "background" / "topics" / "primitives.md").write_text(
        "---\nid: topic:primitives\ntitle: P\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_y"], PROMOTE_KIND_TOPIC)
    assert set(result.candidates_by_slug) == {"hypothesis", "primitives"}


def test_discover_candidates_rejects_explicit_id_with_wrong_prefix(tmp_path, monkeypatch) -> None:
    """An explicit `kind: topic` + `id: paper:foo` slipped through Phase E's
    paper-only classifier (id check only ran when prefix already matched).
    Phase F discovery records a FailedCandidate so contradictory ids never
    reach plan_promote."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    proj = tmp_path / "proj_w"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "trapped.md").write_text(
        "---\nkind: topic\nid: paper:trapped\ntitle: X\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_w"], PROMOTE_KIND_TOPIC)
    assert result.candidates_by_slug == {}
    assert len(result.failed_candidates) == 1
    msg = result.failed_candidates[0].error_message
    assert "paper:trapped" in msg and "topic:" in msg


def test_discover_candidates_rejects_explicit_id_with_invalid_slug(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    proj = tmp_path / "proj_bad_slug"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "valid.md").write_text(
        "---\nid: topic:BadSlug\ntitle: X\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_bad_slug"], PROMOTE_KIND_TOPIC)
    assert result.candidates_by_slug == {}
    assert len(result.failed_candidates) == 1
    assert "BadSlug" in result.failed_candidates[0].error_message


def test_discover_candidates_rejects_non_string_explicit_id(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    proj = tmp_path / "proj_non_string_id"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "valid.md").write_text(
        "---\nid: 123\ntitle: X\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_non_string_id"], PROMOTE_KIND_TOPIC)
    assert result.candidates_by_slug == {}
    assert len(result.failed_candidates) == 1
    assert "id" in result.failed_candidates[0].error_message
    assert "string" in result.failed_candidates[0].error_message


def test_discover_candidates_theme_cross_project_scope_is_candidate(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    proj = tmp_path / "proj_theme_candidate"
    (proj / "doc" / "themes").mkdir(parents=True)
    (proj / "doc" / "themes" / "shared-method.md").write_text(
        "---\nid: theme:shared-method\ntheme_scope: cross-project\ntitle: T\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_theme_candidate"], PROMOTE_KIND_THEME)
    assert set(result.candidates_by_slug) == {"shared-method"}
    assert result.failed_candidates == []


def test_discover_candidates_theme_project_scope_is_silently_skipped(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    proj = tmp_path / "proj_theme_project"
    (proj / "doc" / "themes").mkdir(parents=True)
    (proj / "doc" / "themes" / "local-method.md").write_text(
        "---\nid: theme:local-method\ntheme_scope: project\ntitle: T\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_theme_project"], PROMOTE_KIND_THEME)
    assert result.candidates_by_slug == {}
    assert result.failed_candidates == []


def test_discover_candidates_theme_missing_scope_is_failed_candidate(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    proj = tmp_path / "proj_theme_missing"
    (proj / "doc" / "themes").mkdir(parents=True)
    (proj / "doc" / "themes" / "missing-scope.md").write_text(
        "---\nid: theme:missing-scope\ntitle: T\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_theme_missing"], PROMOTE_KIND_THEME)
    assert result.candidates_by_slug == {}
    assert len(result.failed_candidates) == 1
    assert "eligibility filter rejected" in result.failed_candidates[0].error_message


def test_discover_candidates_theme_malformed_scope_is_failed_candidate(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_THEME, discover_candidates

    proj = tmp_path / "proj_theme_malformed"
    (proj / "doc" / "themes").mkdir(parents=True)
    (proj / "doc" / "themes" / "bad-scope.md").write_text(
        "---\nid: theme:bad-scope\ntheme_scope: [cross-project]\ntitle: T\n---\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_theme_malformed"], PROMOTE_KIND_THEME)
    assert result.candidates_by_slug == {}
    assert len(result.failed_candidates) == 1
    assert "eligibility filter rejected" in result.failed_candidates[0].error_message


def test_discover_candidates_same_project_intra_kind_collision(tmp_path, monkeypatch) -> None:
    """A slug appearing in BOTH doc/topics/ and doc/background/topics/ within
    the same project is a hard failure (cannot resolve canonical source)."""
    from science_tool.commons.promote import PROMOTE_KIND_TOPIC, discover_candidates

    proj = tmp_path / "proj_z"
    (proj / "doc" / "topics").mkdir(parents=True)
    (proj / "doc" / "topics" / "collide.md").write_text("---\nid: topic:collide\n---\n", encoding="utf-8")
    (proj / "doc" / "background" / "topics").mkdir(parents=True)
    (proj / "doc" / "background" / "topics" / "collide.md").write_text(
        "---\nid: topic:collide\n---\n", encoding="utf-8"
    )
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: proj,
    )

    result = discover_candidates(["proj_z"], PROMOTE_KIND_TOPIC)
    assert result.candidates_by_slug == {}
    assert len(result.failed_candidates) >= 1
    msgs = [fc.error_message for fc in result.failed_candidates]
    assert any("collide" in m and "both" in m.lower() for m in msgs)
