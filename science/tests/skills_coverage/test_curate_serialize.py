from __future__ import annotations

import json

from science_model.skill_coverage.coverage import Candidate, EvidenceTriple
from science_tool.skills_coverage.curate import (
    CurateContext,
    apply_plan,
    build_curate_plan,
    serialize_curate_plan,
)


def _plan(context=None):
    cand = Candidate(
        proposed_scope="data-product:x",
        likely_archetype="measurement-qa",
        score=0.5,
        evidence=(
            EvidenceTriple(project="p1", plan_ref="plan:a", dataset_ref="dataset:d"),
        ),
    )
    ctx = context or CurateContext(covered_not_loaded=4, unmapped=2, skipped_projects=("/gone",))
    return build_curate_plan([cand], [], ctx, {"mode": "portfolio"})


def test_json_report_is_parseable_with_context() -> None:
    obj = json.loads(serialize_curate_plan(_plan(), "json"))
    assert obj["mode"] == "report"
    assert obj["context"] == {"covered_not_loaded": 4, "unmapped": 2, "skipped_projects": ["/gone"]}
    assert obj["rows"][0]["disposition"] == "new"
    assert "applied" not in obj["rows"][0] and "result" not in obj["rows"][0]


def test_json_apply_reports_result(tmp_path) -> None:
    plan = _plan()
    apply_plan(plan, tmp_path, today="2026-07-28")
    obj = json.loads(serialize_curate_plan(plan, "json"))
    assert obj["mode"] == "apply"
    assert obj["rows"][0]["applied"] is True
    assert obj["rows"][0]["result"]["action"] == "created"


def test_text_render_names_gaps_counts_and_archetype() -> None:
    text = serialize_curate_plan(_plan(), "text")
    assert "data-product:x" in text
    assert "new" in text
    assert "measurement-qa" in text
    assert "covered-not-loaded: 4" in text and "unmapped: 2" in text


def test_text_render_header_names_scoped_project() -> None:
    cand = Candidate(
        proposed_scope="data-product:x",
        likely_archetype="measurement-qa",
        score=0.5,
        evidence=(
            EvidenceTriple(project="p1", plan_ref="plan:a", dataset_ref="dataset:d"),
        ),
    )
    plan = build_curate_plan([cand], [], CurateContext(0, 0, ()), {"mode": "project", "project": "mm30"})
    assert "project mm30" in serialize_curate_plan(plan, "text")
