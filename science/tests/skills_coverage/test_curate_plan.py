from __future__ import annotations

import pytest

from science_model.skill_coverage.coverage import Candidate, EvidenceTriple
from science_tool.feedback import FeedbackEntry
from science_tool.skills_coverage.curate import (
    CurateConflictError,
    CurateContext,
    CurateStatusError,
    build_curate_plan,
)


def _cand(term: str, *, score: float = 0.5, projects=(("p1", "plan:a"),)) -> Candidate:
    evidence = tuple(
        EvidenceTriple(project=proj, plan_ref=plan, dataset_ref="dataset:d")
        for proj, plan in projects
    )
    return Candidate(
        proposed_scope=term,
        likely_archetype="measurement-qa",
        score=score,
        evidence=evidence,
    )


def _entry(
    target: str, *, status: str = "open", concern: str = "tooling", n: int = 0
) -> FeedbackEntry:
    # `n` gives each fixture entry a distinct id; two entries that share a target
    # must still be two rows, so the conflict/status paths get real, non-colliding ids.
    return FeedbackEntry(
        id=f"fb-2026-07-28-{100 + n:03d}",
        target=target,
        summary="s",
        concern=concern,
        status=status,
        category="gap",
    )


_CTX = CurateContext(covered_not_loaded=0, unmapped=0, skipped_projects=())
_SCOPE = {"mode": "portfolio"}


def test_new_when_no_match() -> None:
    plan = build_curate_plan([_cand("data-product:x")], [], _CTX, _SCOPE)
    assert plan.mode == "report"
    assert [(r.term, r.disposition) for r in plan.rows] == [("data-product:x", "new")]
    assert plan.rows[0].existing == ()


def test_recur_when_open_match() -> None:
    entries = [_entry("skill-coverage:data-product:x", status="open")]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    assert plan.rows[0].disposition == "recur"
    assert [m.status for m in plan.rows[0].existing] == ["open"]


def test_normalized_target_dedup() -> None:
    entries = [_entry("Skill-Coverage:data-product:x", status="open")]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    assert plan.rows[0].disposition == "recur"  # case variant still matches


def test_cross_concern_is_not_a_match() -> None:
    entries = [
        _entry("skill-coverage:data-product:x", status="open", concern="methodology:qa", n=0),
        _entry("skill-coverage:data-product:x", status="open", concern="methodology:qa", n=1),
    ]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    assert plan.rows[0].disposition == "new"  # different concern ignored, no conflict


def test_multiple_open_fails_early() -> None:
    entries = [
        _entry("skill-coverage:data-product:x", status="open", n=0),
        _entry("skill-coverage:data-product:x", status="open", n=1),
    ]
    with pytest.raises(CurateConflictError) as exc:
        build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    assert exc.value.ids == ["fb-2026-07-28-100", "fb-2026-07-28-101"]  # both, sorted
    assert "merge" in str(exc.value)


def test_unknown_status_fails_early() -> None:
    # status is an unvalidated str on FeedbackEntry; an unexpected value must not
    # silently bucket as resolved/SKIP.
    entries = [_entry("skill-coverage:data-product:x", status="bogus")]
    with pytest.raises(CurateStatusError):
        build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)


def test_skip_addressed_conflict_lists_all_resolved() -> None:
    entries = [
        _entry("skill-coverage:data-product:x", status="wontfix", n=0),
        _entry("skill-coverage:data-product:x", status="addressed", n=1),
    ]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    row = plan.rows[0]
    assert row.disposition == "skip-addressed-conflict"
    assert sorted((m.id, m.status) for m in row.existing) == [
        ("fb-2026-07-28-100", "wontfix"),
        ("fb-2026-07-28-101", "addressed"),
    ]


def test_open_plus_resolved_is_recur_listing_both() -> None:
    entries = [
        _entry("skill-coverage:data-product:x", status="open", n=0),
        _entry("skill-coverage:data-product:x", status="wontfix", n=1),
    ]
    plan = build_curate_plan([_cand("data-product:x")], entries, _CTX, _SCOPE)
    row = plan.rows[0]
    assert row.disposition == "recur"
    assert sorted((m.id, m.status) for m in row.existing) == [
        ("fb-2026-07-28-100", "open"),
        ("fb-2026-07-28-101", "wontfix"),
    ]


def test_counts_and_ordering() -> None:
    cands = [
        _cand("data-product:a", score=0.2, projects=(("p1", "plan:a"),)),
        _cand(
            "data-product:b",
            score=0.9,
            projects=(("p1", "plan:a"), ("p2", "plan:b")),
        ),
    ]
    plan = build_curate_plan(cands, [], _CTX, _SCOPE)
    assert [r.term for r in plan.rows] == ["data-product:b", "data-product:a"]  # score desc
    assert (plan.rows[0].n_plans, plan.rows[0].n_projects) == (2, 2)


def test_coverage_context_counts_states_and_skips() -> None:
    # Real CoverageReport: coverage_context must count only covered-not-loaded and
    # unmapped (never uncovered), and carry the skipped-project paths — asserted at
    # exact nonzero values so a stub returning zeros would fail.
    from science_model.skill_coverage.coverage import (
        CoverageReport,
        CoveredNotLoadedOccurrence,
        ReportScope,
        SkippedProject,
        UncoveredOccurrence,
        UnmappedOccurrence,
    )
    from science_tool.skills_coverage.curate import coverage_context

    report = CoverageReport(
        scope=ReportScope(mode="portfolio"),
        coverage_occurrences=(
            CoveredNotLoadedOccurrence(
                project="p1", term="data-product:a", available_skill_ids=("skill:x",), evidence_refs=()
            ),
            CoveredNotLoadedOccurrence(
                project="p2", term="data-product:b", available_skill_ids=("skill:y",), evidence_refs=()
            ),
            UnmappedOccurrence(project="p1", dataset_ref="dataset:d", evidence_refs=()),
            UncoveredOccurrence(project="p1", term="data-product:c", evidence_refs=()),
        ),
        skill_reference_diagnostics=(),
        dataset_reference_diagnostics=(),
        candidates=(),
        skipped_projects=(SkippedProject(path="/gone", reason="unreadable"),),
    )
    ctx = coverage_context(report)
    assert (ctx.covered_not_loaded, ctx.unmapped) == (2, 1)
    assert ctx.skipped_projects == ("/gone",)
