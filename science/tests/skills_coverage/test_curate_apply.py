from __future__ import annotations

from pathlib import Path

import pytest

from science_model.skill_coverage.coverage import Candidate, EvidenceTriple
from science_tool.feedback import FeedbackEntry, list_entries, load_all_entries, save_entry
from science_tool.skills_coverage.curate import (
    CurateContext,
    CurateSelectionError,
    apply_plan,
    build_curate_plan,
)

_CTX = CurateContext(0, 0, ())
_SCOPE = {"mode": "portfolio"}


def _cand(term: str, *, projects=(("p1", "plan:a"),)) -> Candidate:
    return Candidate(
        proposed_scope=term,
        likely_archetype="measurement-qa",
        score=0.5,
        evidence=tuple(
            EvidenceTriple(project=p, plan_ref=pl, dataset_ref="dataset:d")
            for p, pl in projects
        ),
    )


def _open_entry(term: str) -> FeedbackEntry:
    return FeedbackEntry(
        id="fb-2026-07-28-500",
        target=f"skill-coverage:{term}",
        summary="s",
        concern="tooling",
        category="gap",
        status="open",
    )


def test_apply_new_creates_entry_with_fixed_fields(tmp_path: Path) -> None:
    plan = build_curate_plan(
        [_cand("data-product:x", projects=(("p1", "plan:a"), ("p2", "plan:b")))],
        [],
        _CTX,
        _SCOPE,
    )
    apply_plan(plan, tmp_path, today="2026-07-28")
    assert plan.mode == "apply"
    row = plan.rows[0]
    assert row.applied is True
    assert row.result["action"] == "created"
    assert row.result["recurrence_after"] == 1  # validator seeds one occurrence
    [entry] = load_all_entries(tmp_path)
    assert entry.target == "skill-coverage:data-product:x"
    assert (entry.project, entry.category, entry.concern) == ("science", "gap", "tooling")
    assert "2 plans / 2 projects" in entry.summary


def test_apply_recur_records_occurrence_with_metadata(tmp_path: Path) -> None:
    save_entry(tmp_path, _open_entry("data-product:x"))  # persisted -> recurrence 1 (seeded)
    plan = build_curate_plan(
        [_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE
    )
    apply_plan(plan, tmp_path, today="2026-07-28")
    row = plan.rows[0]
    assert row.result == {
        "action": "recurred",
        "id": "fb-2026-07-28-500",
        "recurrence_after": 2,
    }
    [entry] = load_all_entries(tmp_path)
    assert entry.recurrence == 2  # seeded 1 + one recurrence
    occ = entry.occurrences[-1]
    assert (occ.project, occ.category) == ("science", "gap")
    assert occ.detail is not None
    assert "score:" in occ.detail and "p1 / plan:a" in occ.detail  # evidence snapshot recorded


def test_apply_recur_targets_the_open_entry_when_resolved_also_present(tmp_path: Path) -> None:
    # A term with one open + one resolved entry recurs against the OPEN id, not the resolved one.
    save_entry(tmp_path, _open_entry("data-product:x"))  # id fb-2026-07-28-500, open
    save_entry(
        tmp_path,
        FeedbackEntry(
            id="fb-2026-07-28-400",
            target="skill-coverage:data-product:x",
            summary="s",
            concern="tooling",
            category="gap",
            status="wontfix",
        ),
    )
    plan = build_curate_plan(
        [_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE
    )
    apply_plan(plan, tmp_path, today="2026-07-28")
    assert plan.rows[0].result == {
        "action": "recurred",
        "id": "fb-2026-07-28-500",
        "recurrence_after": 2,
    }


def test_apply_twice_from_empty_is_new_then_recur(tmp_path: Path) -> None:
    # First apply on an empty store -> NEW (recurrence 1); second -> RECUR (recurrence 2).
    plan1 = build_curate_plan(
        [_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE
    )
    apply_plan(plan1, tmp_path, today="2026-07-28")
    assert plan1.rows[0].result["action"] == "created"
    plan2 = build_curate_plan(
        [_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE
    )
    apply_plan(plan2, tmp_path, today="2026-07-28")
    assert plan2.rows[0].result == {
        "action": "recurred",
        "id": plan1.rows[0].result["id"],
        "recurrence_after": 2,
    }
    [entry] = load_all_entries(tmp_path)  # one entry, never a duplicate
    assert entry.recurrence == 2


def test_scoped_apply_writes_only_selected(tmp_path: Path) -> None:
    cands = [_cand("data-product:a"), _cand("data-product:b")]
    plan = build_curate_plan(cands, [], _CTX, _SCOPE)
    apply_plan(plan, tmp_path, today="2026-07-28", selected_terms={"data-product:a"})
    by_term = {r.term: r for r in plan.rows}
    assert by_term["data-product:a"].applied is True
    assert by_term["data-product:b"].applied is False and by_term["data-product:b"].result is None
    assert {e.target for e in load_all_entries(tmp_path)} == {"skill-coverage:data-product:a"}


def test_unknown_selected_term_raises(tmp_path: Path) -> None:
    plan = build_curate_plan([_cand("data-product:a")], [], _CTX, _SCOPE)
    with pytest.raises(CurateSelectionError):
        apply_plan(plan, tmp_path, today="2026-07-28", selected_terms={"data-product:zzz"})


def test_unknown_disposition_raises_before_any_write(tmp_path: Path) -> None:
    plan = build_curate_plan(
        [_cand("data-product:a"), _cand("data-product:b")],
        [],
        _CTX,
        _SCOPE,
    )
    plan.rows[1].disposition = "unexpected"

    with pytest.raises(ValueError, match="unknown disposition"):
        apply_plan(plan, tmp_path, today="2026-07-28")

    assert plan.mode == "report"
    assert all(row.applied is None for row in plan.rows)
    assert list(tmp_path.iterdir()) == []


def test_skip_row_writes_nothing(tmp_path: Path) -> None:
    resolved = FeedbackEntry(
        id="fb-2026-07-28-600",
        target="skill-coverage:data-product:x",
        summary="s",
        concern="tooling",
        category="gap",
        status="wontfix",
    )
    save_entry(tmp_path, resolved)
    plan = build_curate_plan(
        [_cand("data-product:x")], list_entries(tmp_path, status=None), _CTX, _SCOPE
    )
    apply_plan(plan, tmp_path, today="2026-07-28")
    row = plan.rows[0]
    assert row.disposition == "skip" and row.applied is False and row.result is None
    entries = load_all_entries(tmp_path)
    assert len(entries) == 1 and entries[0].id == "fb-2026-07-28-600" and entries[0].recurrence == 1
