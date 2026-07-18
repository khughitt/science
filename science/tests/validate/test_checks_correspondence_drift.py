from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.correspondence_drift import check_correspondence_drift
from science_tool.validate.context import ValidateContext
from science_tool.validate.gates import cumulative_rules


def _plan(root: Path, rel: str, *, entity_id: str, status: str, body: str) -> None:
    p = root / "entities" / "plans" / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f'---\nid: "{entity_id}"\nkind: plan\ntitle: "T"\nstatus: "{status}"\n---\n\n{body}\n', encoding="utf-8")


def _run(root: Path):
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_correspondence_drift(ctx))


def test_draft_with_present_deliverable_fires_under_claim(tmp_path: Path):
    # One named deliverable, present, no task refs -> adjudicate() returns COMPLETE
    # (tasks_settled is vacuously true), and draft(0) < complete(2) is under-claim.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(tmp_path, "0001-x.md", entity_id="plan:0001", status="draft", body="Builds `src/a.py`.")
    results = _run(tmp_path)
    assert len(results) == 1
    r = results[0]
    assert r.rule == "plan.correspondence-drift"
    assert r.severity.value == "warn"
    assert not r.path.is_absolute()  # project-relative
    assert "plan:0001" in r.message and "draft" in r.message and "complete" in r.message
    assert "evidence-signature: v1:" in r.message


def test_draft_with_partial_deliverables_fires_as_active(tmp_path: Path):
    # One present, one absent -> adjudicate() returns ACTIVE; draft(0) < active(1) is under-claim.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(
        tmp_path, "0005-x.md", entity_id="plan:0005", status="draft",
        body="Builds `src/a.py` and `src/b.py`.",
    )
    results = _run(tmp_path)
    assert len(results) == 1
    assert "active" in results[0].message
    assert "src/a.py" in results[0].message and "src/b.py" in results[0].message


def test_active_with_all_present_fires_as_complete(tmp_path: Path):
    # The other measured under-claim transition (result.md: 1 of 22): claimed `active`,
    # everything present -> adjudicated COMPLETE, active(1) < complete(2).
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(tmp_path, "0006-x.md", entity_id="plan:0006", status="active", body="Builds `src/a.py`.")
    results = _run(tmp_path)
    assert len(results) == 1
    assert "active" in results[0].message and "complete" in results[0].message


def test_draft_with_absent_deliverable_is_silent(tmp_path: Path):
    _plan(tmp_path, "0002-x.md", entity_id="plan:0002", status="draft", body="Will build `src/missing.py`.")
    assert not _run(tmp_path)


def test_complete_with_present_deliverable_is_silent(tmp_path: Path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(tmp_path, "0003-x.md", entity_id="plan:0003", status="complete", body="Built `src/a.py`.")
    assert not _run(tmp_path)


def test_complete_claim_with_partial_deliverables_is_silent_not_over_claim(tmp_path: Path):
    # complete(2) vs adjudicated active(1): the claim is HIGHER than reality. This screen is
    # under-claim only (design §3), so an over-claim must be silent, not flagged.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(
        tmp_path, "0007-x.md", entity_id="plan:0007", status="complete",
        body="Built `src/a.py` and `src/b.py`.",
    )
    assert not _run(tmp_path)


def test_unknown_probe_is_indeterminate_and_silent(tmp_path: Path):
    # A `../`-escaping path extracts but probes UNKNOWN (probe.py: outside the project),
    # so adjudicate() returns INDETERMINATE -> off the lifecycle axis -> silent (design §6.3).
    _plan(tmp_path, "0008-x.md", entity_id="plan:0008", status="draft", body="Builds `../outside/a.py`.")
    assert not _run(tmp_path)


def test_terminal_claimed_status_is_off_axis_and_silent(tmp_path: Path):
    # `superseded` is not in the draft/active/complete lifecycle ranking, so the screen
    # never compares it -> silent even though `src/a.py` is present.
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    _plan(tmp_path, "0009-x.md", entity_id="plan:0009", status="superseded", body="Built `src/a.py`.")
    assert not _run(tmp_path)


def test_plan_naming_no_probeable_file_is_silent(tmp_path: Path):
    _plan(tmp_path, "0004-x.md", entity_id="plan:0004", status="draft", body="Some prose, no paths.")
    assert not _run(tmp_path)


def test_non_plan_kind_is_ignored(tmp_path: Path):
    p = tmp_path / "entities" / "hypotheses" / "0001-x.md"
    p.parent.mkdir(parents=True)
    p.write_text('---\nid: "hypothesis:0001"\nkind: hypothesis\ntitle: "T"\nstatus: "draft"\n---\n\nBuilds `src/a.py`.\n', encoding="utf-8")
    assert not _run(tmp_path)


def test_rule_is_never_gated(tmp_path: Path):
    assert "plan.correspondence-drift" not in cumulative_rules("hygiene")
