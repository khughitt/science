from __future__ import annotations

import importlib
from collections.abc import Iterable
from pathlib import Path

from science_tool.validate import Result, Severity, ValidateContext
from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests


def _write_manifest(root: Path, *, profile: str = "research") -> None:
    root.mkdir(parents=True, exist_ok=True)
    root.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "created: 2026-01-01",
                "last_modified: 2026-01-02",
                "status: active",
                "summary: Demo project",
                f"profile: {profile}",
                "layout_version: 1",
                "knowledge_profiles:",
                "  local: knowledge/local",
            ]
        ),
        encoding="utf-8",
    )


def _ctx(root: Path, *, profile: str = "research") -> ValidateContext:
    _write_manifest(root, profile=profile)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _messages(results: Iterable[Result]) -> list[str]:
    return [result.message for result in results]


def test_new_research_document_checks_register_after_hypotheses() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.bias_audits as bias_audits
    import science_tool.validate.checks.discussions as discussions
    import science_tool.validate.checks.hypotheses as hypotheses
    import science_tool.validate.checks.hypothesis_comparisons as hypothesis_comparisons
    import science_tool.validate.checks.prereg as prereg
    import science_tool.validate.checks.research_plan as research_plan

    importlib.reload(hypotheses)
    importlib.reload(research_plan)
    importlib.reload(discussions)
    importlib.reload(prereg)
    importlib.reload(hypothesis_comparisons)
    importlib.reload(bias_audits)

    assert [(entry.section, entry.order) for entry in CANONICAL_CHECKS[-6:]] == [
        ("hypotheses...", 5),
        ("research plan conventions...", 10),
        ("discussion documents...", 11),
        ("discussion documents...", 12),
        ("discussion documents...", 13),
        ("discussion documents...", 14),
    ]


def test_research_plan_exists_info_and_legacy_section_warnings(tmp_path: Path) -> None:
    from science_tool.validate.checks.research_plan import check_research_plan

    ctx = _ctx(tmp_path)
    tmp_path.joinpath("RESEARCH_PLAN.md").write_text(
        "\n".join(["# Plan", "## Current Priorities", "## Next Review Trigger"]),
        encoding="utf-8",
    )

    results = list(check_research_plan(ctx))

    assert [(result.severity, result.message) for result in results] == [
        (Severity.INFO, "RESEARCH_PLAN.md exists"),
        (
            Severity.WARN,
            "RESEARCH_PLAN.md contains legacy task-queue section '## Current Priorities' — migrate tasks to tasks/active.md via /science:tasks",
        ),
        (
            Severity.WARN,
            "RESEARCH_PLAN.md contains legacy task-queue section '## Next Review Trigger' — migrate tasks to tasks/active.md via /science:tasks",
        ),
    ]


def test_research_plan_absence_depends_on_effective_profile(tmp_path: Path) -> None:
    from science_tool.validate.checks.research_plan import check_research_plan

    research_messages = _messages(check_research_plan(_ctx(tmp_path / "research", profile="research")))
    software_messages = _messages(check_research_plan(_ctx(tmp_path / "software", profile="software")))

    assert research_messages == ["No RESEARCH_PLAN.md — high-level planning may be in README.md or doc/plans/"]
    assert software_messages == []


def test_research_plan_check_accepts_readme_when_plan_is_missing(tmp_path: Path) -> None:
    from science_tool.validate.checks.research_plan import check_research_plan

    ctx = _ctx(tmp_path, profile="research")
    tmp_path.joinpath("README.md").write_text("# Demo\n", encoding="utf-8")

    messages = _messages(check_research_plan(ctx))

    assert messages == ["README.md exists; RESEARCH_PLAN.md not required"]


def test_discussions_warn_for_missing_sections_and_skip_legacy_comparison_docs(tmp_path: Path) -> None:
    from science_tool.validate.checks.discussions import check_discussions

    ctx = _ctx(tmp_path)
    discussions_dir = tmp_path / "entities" / "discussions"
    discussions_dir.mkdir(parents=True)
    discussions_dir.joinpath("0001-topic.md").write_text("## Focus\n", encoding="utf-8")
    discussions_dir.joinpath("comparison-topic.md").write_text("", encoding="utf-8")
    discussions_dir.joinpath("0002-comparison-topic.md").write_text("## Focus\n", encoding="utf-8")

    messages = _messages(check_discussions(ctx))

    assert "Checking entities/discussions/0001-topic.md..." in messages
    assert "Checking entities/discussions/comparison-topic.md..." not in messages
    assert "Checking entities/discussions/0002-comparison-topic.md..." in messages
    assert "entities/discussions/0001-topic.md missing section: ## Current Position" in messages
    assert "entities/discussions/0001-topic.md missing section: ## Critical Analysis" in messages
    assert "entities/discussions/0001-topic.md missing section: ## Evidence Needed" in messages
    assert "entities/discussions/0001-topic.md missing section: ## Prioritized Follow-Ups" in messages
    assert "entities/discussions/0001-topic.md missing section: ## Synthesis" in messages
    assert "entities/discussions/0002-comparison-topic.md missing section: ## Current Position" in messages


def test_discussions_double_blind_mode_requires_addendum_sections(tmp_path: Path) -> None:
    from science_tool.validate.checks.discussions import check_discussions

    ctx = _ctx(tmp_path)
    discussions_dir = tmp_path / "entities" / "discussions"
    discussions_dir.mkdir(parents=True)
    discussions_dir.joinpath("0001-double.md").write_text(
        "\n".join(
            [
                'mode: "double-blind"',
                "## Focus",
                "## Current Position",
                "## Critical Analysis",
                "## Evidence Needed",
                "## Prioritized Follow-Ups",
                "## Synthesis",
                "### Combined Synthesis",
            ]
        ),
        encoding="utf-8",
    )

    messages = _messages(check_discussions(ctx))

    assert (
        "entities/discussions/0001-double.md double-blind mode missing section: ## Double-Blind Addendum (If mode = double-blind)"
        in messages
    )
    assert "entities/discussions/0001-double.md double-blind mode missing section: ### Agent Independent Draft" in messages
    assert "entities/discussions/0001-double.md double-blind mode missing section: ### User Independent Draft" in messages
    assert "entities/discussions/0001-double.md double-blind mode missing section: ### Comparison" in messages
    assert "entities/discussions/0001-double.md double-blind mode missing section: ### Combined Synthesis" not in messages


def test_prereg_warns_for_missing_sections_and_required_frontmatter_fields(tmp_path: Path) -> None:
    from science_tool.validate.checks.prereg import check_prereg

    ctx = _ctx(tmp_path)
    prereg_dir = tmp_path / "entities" / "pre-registrations"
    prereg_dir.mkdir(parents=True)
    prereg_dir.joinpath("0001-a.md").write_text(
        "---\ntype: 'pre-registration'\n---\n## Hypotheses Under Test\n",
        encoding="utf-8",
    )
    prereg_dir.joinpath("0002-b.md").write_text(
        "\n".join(
            [
                "---",
                "type: pre-registration",
                "committed: 2026-01-01",
                "spec: ''",
                "---",
                "## Hypotheses Under Test",
                "## Expected Outcomes",
                "## Decision Criteria",
                "## Null Result Plan",
            ]
        ),
        encoding="utf-8",
    )

    messages = _messages(check_prereg(ctx))

    assert "Pre-registration entities/pre-registrations/0001-a.md missing section: Expected Outcomes" in messages
    assert "Pre-registration entities/pre-registrations/0001-a.md missing section: Decision Criteria" in messages
    assert "Pre-registration entities/pre-registrations/0001-a.md missing section: Null Result Plan" in messages
    assert (
        "entities/pre-registrations/0001-a.md type 'pre-registration' should declare a 'committed:' date in frontmatter"
        in messages
    )
    assert (
        "entities/pre-registrations/0001-a.md type 'pre-registration' should declare a 'spec:' field (empty string is OK if no paired design doc)"
        in messages
    )
    assert not any(message.startswith("Pre-registration entities/pre-registrations/0002-b.md") for message in messages)


def test_hypothesis_comparisons_warn_for_missing_sections(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypothesis_comparisons import check_hypothesis_comparisons

    ctx = _ctx(tmp_path)
    comparisons_dir = tmp_path / "entities" / "discussions"
    comparisons_dir.mkdir(parents=True)
    # Marker-based detection (entities layout — no filename prefix required)
    comparisons_dir.joinpath("0001-comparison-a.md").write_text("## Hypotheses Compared\n", encoding="utf-8")

    messages = _messages(check_hypothesis_comparisons(ctx))

    assert "Comparison entities/discussions/0001-comparison-a.md missing section: Evidence Inventory" in messages
    assert "Comparison entities/discussions/0001-comparison-a.md missing section: Discriminating Predictions" in messages
    assert "Comparison entities/discussions/0001-comparison-a.md missing section: Current Verdict" in messages


def test_hypothesis_comparisons_normalizes_required_section_headings(tmp_path: Path) -> None:
    from science_tool.validate.checks.hypothesis_comparisons import check_hypothesis_comparisons

    ctx = _ctx(tmp_path)
    comparisons_dir = tmp_path / "entities" / "discussions"
    comparisons_dir.mkdir(parents=True)
    comparisons_dir.joinpath("0001-comparison-a.md").write_text(
        "\n".join(
            [
                "## Hypotheses Compared",
                "## Evidence inventory",
                "## Discriminating predictions",
                "## Current verdict",
            ]
        ),
        encoding="utf-8",
    )

    assert _messages(check_hypothesis_comparisons(ctx)) == []


# ---------------------------------------------------------------------------
# Task 8: dual-root tests — entities/ locations are discovered (prereg)
# ---------------------------------------------------------------------------

def test_prereg_discovers_entities_pre_registrations(tmp_path: Path) -> None:
    """entities/pre-registrations/0001-x.md is found and section-checked."""
    from science_tool.validate.checks.prereg import check_prereg

    ctx = _ctx(tmp_path)
    ent_dir = tmp_path / "entities" / "pre-registrations"
    ent_dir.mkdir(parents=True)
    # Only has one section → should warn for the missing three
    ent_dir.joinpath("0001-x.md").write_text(
        "---\ntype: pre-registration\ncommitted: 2026-01-01\nspec: ''\n---\n"
        "## Hypotheses Under Test\n",
        encoding="utf-8",
    )

    messages = _messages(check_prereg(ctx))

    assert any("0001-x.md" in m and "Expected Outcomes" in m for m in messages), messages
    assert any("0001-x.md" in m and "Decision Criteria" in m for m in messages), messages
    assert any("0001-x.md" in m and "Null Result Plan" in m for m in messages), messages


# ---------------------------------------------------------------------------
# Task 8: dual-root tests — entities/ locations are discovered (comparisons)
# ---------------------------------------------------------------------------

def test_hypothesis_comparisons_entities_marker_based_detection(tmp_path: Path) -> None:
    """A migrated comparison at entities/discussions/NNNN-slug.md with the
    '## Hypotheses Compared' marker is recognized and section-checked."""
    from science_tool.validate.checks.hypothesis_comparisons import check_hypothesis_comparisons

    ctx = _ctx(tmp_path)
    ent_dir = tmp_path / "entities" / "discussions"
    ent_dir.mkdir(parents=True)
    # Marker present but remaining three sections absent → three warnings
    ent_dir.joinpath("0001-comparison-h1-vs-h2.md").write_text(
        "---\nid: discussion:0001-comparison-h1-vs-h2\n---\n## Hypotheses Compared\n",
        encoding="utf-8",
    )

    messages = _messages(check_hypothesis_comparisons(ctx))

    assert any("0001-comparison-h1-vs-h2.md" in m and "Evidence Inventory" in m for m in messages), messages
    assert any("0001-comparison-h1-vs-h2.md" in m and "Discriminating Predictions" in m for m in messages), messages
    assert any("0001-comparison-h1-vs-h2.md" in m and "Current Verdict" in m for m in messages), messages


def test_hypothesis_comparisons_entities_plain_discussion_not_flagged(tmp_path: Path) -> None:
    """A plain discussion without the marker is NOT treated as a comparison."""
    from science_tool.validate.checks.hypothesis_comparisons import check_hypothesis_comparisons

    ctx = _ctx(tmp_path)
    ent_dir = tmp_path / "entities" / "discussions"
    ent_dir.mkdir(parents=True)
    ent_dir.joinpath("0002-notes.md").write_text(
        "---\nid: discussion:0002-notes\n---\n## Background\n",
        encoding="utf-8",
    )

    messages = _messages(check_hypothesis_comparisons(ctx))

    assert not any("0002-notes.md" in m for m in messages), messages


def test_hypothesis_comparisons_entities_marker_no_legacy_doc_scan(tmp_path: Path) -> None:
    """After cutover, doc/discussions/comparison-*.md files are NOT scanned.
    Only entities/discussions/*.md files with the marker are checked."""
    from science_tool.validate.checks.hypothesis_comparisons import check_hypothesis_comparisons

    ctx = _ctx(tmp_path)
    # Legacy location: should produce no results
    legacy_dir = tmp_path / "doc" / "discussions"
    legacy_dir.mkdir(parents=True)
    legacy_dir.joinpath("comparison-old.md").write_text("## Hypotheses Compared\n", encoding="utf-8")

    messages = _messages(check_hypothesis_comparisons(ctx))

    assert not any("comparison-old.md" in m for m in messages), messages


def test_bias_audits_warn_for_missing_sections(tmp_path: Path) -> None:
    from science_tool.validate.checks.bias_audits import check_bias_audits

    ctx = _ctx(tmp_path)
    meta_dir = tmp_path / "doc" / "meta"
    meta_dir.mkdir(parents=True)
    meta_dir.joinpath("bias-audit-a.md").write_text("## Cognitive Biases\n", encoding="utf-8")

    messages = _messages(check_bias_audits(ctx))

    assert "Bias audit doc/meta/bias-audit-a.md missing section: Methodological Biases" in messages
    assert "Bias audit doc/meta/bias-audit-a.md missing section: Summary" in messages


def test_synthesis_frontmatter_gates_on_type_and_validates_report_kind(tmp_path: Path) -> None:
    from science_tool.validate.checks.discussions import check_discussions

    ctx = _ctx(tmp_path)
    synthesis_dir = tmp_path / "entities" / "synthesis"
    synthesis_dir.mkdir(parents=True)
    synthesis_dir.joinpath("ignored.md").write_text("type: report\n", encoding="utf-8")
    synthesis_dir.joinpath("missing-kind.md").write_text("type: synthesis\n", encoding="utf-8")
    synthesis_dir.joinpath("invalid-kind.md").write_text(
        "\n".join(["type: synthesis", "report_kind: other", "source_commit: abc"]),
        encoding="utf-8",
    )

    messages = _messages(check_discussions(ctx))

    assert "entities/synthesis/ignored.md: missing report_kind" not in messages
    assert "entities/synthesis/missing-kind.md: missing report_kind" in messages
    assert "entities/synthesis/missing-kind.md: missing source_commit" in messages
    assert "entities/synthesis/invalid-kind.md: invalid report_kind 'other'" in messages
    assert "entities/synthesis/invalid-kind.md: missing source_commit" not in messages


def test_research_question_found_in_entities(tmp_path: Path) -> None:
    from science_tool.validate.checks.research_scope import check_research_scope

    ctx = _ctx(tmp_path)
    entities_dir = tmp_path / "entities"
    entities_dir.mkdir(parents=True)
    entities_dir.joinpath("research-question.md").write_text("# Research Question\n", encoding="utf-8")

    results = list(check_research_scope(ctx))
    assert not any(r.severity is Severity.ERROR and "research-question" in r.message for r in results)


def test_synthesis_frontmatter_requires_per_kind_fields(tmp_path: Path) -> None:
    from science_tool.validate.checks.discussions import check_discussions

    ctx = _ctx(tmp_path)
    synthesis_dir = tmp_path / "entities" / "synthesis"
    synthesis_dir.mkdir(parents=True)
    synthesis_dir.joinpath("rollup.md").write_text(
        "\n".join(["type: synthesis", "report_kind: synthesis-rollup", "source_commit: abc"]),
        encoding="utf-8",
    )
    synthesis_dir.joinpath("hypothesis.md").write_text(
        "\n".join(["type: synthesis", "report_kind: hypothesis-synthesis", "source_commit: abc", "hypothesis: h1"]),
        encoding="utf-8",
    )
    synthesis_dir.joinpath("emergent.md").write_text(
        "\n".join(["type: synthesis", "report_kind: emergent-threads", "source_commit: abc", "orphan_ids: []"]),
        encoding="utf-8",
    )

    messages = _messages(check_discussions(ctx))

    assert "entities/synthesis/rollup.md: missing synthesized_from" in messages
    assert "entities/synthesis/hypothesis.md: missing provenance_coverage" in messages
    assert "entities/synthesis/emergent.md: missing orphan_question_count" in messages
    assert "entities/synthesis/emergent.md: missing orphan_interpretation_count" in messages
    assert "entities/synthesis/emergent.md: missing orphan_ids" not in messages
