from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.feedback import load_all_entries
from science_tool.skills_lint.cli import skills_group


def _enrolled_project(root: Path) -> None:
    from _fixtures.entity_helpers import seed_project

    root.mkdir()
    seed_project(root)
    cfg = root / "science.yaml"
    cfg.write_text(
        cfg.read_text()
        + "\nentity_schema_version: 3\nskill_coverage:\n  domains:\n    molecular-measurement: enrolled\n",
        encoding="utf-8",
    )


def _registry(tmp_path: Path, entries: list[dict]) -> None:
    (tmp_path / "config.yaml").write_text(yaml.safe_dump({"projects": entries}), encoding="utf-8")


def _an_uncovered_term() -> str:
    """A real catalog term that no leaf skill covers (guarantees a candidate)."""
    from science_model.data_products import load_catalog
    from science_model.skill_coverage import LeafSkill, build_skill_overlay
    from science_tool.graph.skill_inventory import load_skill_inventory

    catalog = load_catalog()
    overlay = build_skill_overlay(load_skill_inventory(), catalog)
    covered = {term for skill in overlay if isinstance(skill, LeafSkill) for term in skill.covers}
    return next(term for term in catalog.by_id if term not in covered)


def _seed_gap(root: Path, term: str) -> None:
    from _fixtures.entity_helpers import write_markdown_entity

    write_markdown_entity(root, "entities/datasets/tagged.md", {
        "id": "dataset:tagged", "kind": "dataset", "title": "Tagged",
        "provided_capabilities": [{"data_product": term}],
    }, "A tagged dataset.")
    write_markdown_entity(root, "entities/plans/0001-p.md", {
        "id": "plan:0001-p", "kind": "plan", "title": "Plan p",
        "related": ["dataset:tagged"],
    }, "A plan that uses the tagged dataset.")


def _setup(tmp_path: Path, monkeypatch, *, seed_gap: bool = True) -> tuple[Path, str]:
    enrolled = tmp_path / "enrolled"
    _enrolled_project(enrolled)
    term = _an_uncovered_term()
    if seed_gap:
        _seed_gap(enrolled, term)
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path))
    fb = tmp_path / "feedback"
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(fb))
    _registry(tmp_path, [{"path": str(enrolled), "name": "enrolled", "id": "enrolled", "registered": "2026-07-25"}])
    return fb, term


def test_report_run_writes_no_feedback(tmp_path: Path, monkeypatch) -> None:
    fb, _ = _setup(tmp_path, monkeypatch)
    result = CliRunner().invoke(skills_group, ["curate", "--format", "json"])
    assert result.exit_code == 0, result.output
    obj = json.loads(result.output)
    assert obj["mode"] == "report"
    assert set(obj["context"]) == {"covered_not_loaded", "unmapped", "skipped_projects"}  # context shape wired through
    assert not fb.exists() or load_all_entries(fb) == []  # no writes


def test_apply_files_feedback(tmp_path: Path, monkeypatch) -> None:
    fb, term = _setup(tmp_path, monkeypatch)
    result = CliRunner().invoke(skills_group, ["curate", "--apply", "--format", "json"])
    assert result.exit_code == 0, result.output
    obj = json.loads(result.output)
    assert obj["mode"] == "apply"
    row = next(r for r in obj["rows"] if r["term"] == term)
    assert row["applied"] is True and row["result"]["action"] == "created"
    entries = load_all_entries(fb)
    assert any(e.target == f"skill-coverage:{term}" and e.project == "science" for e in entries)


def test_term_requires_apply(tmp_path: Path, monkeypatch) -> None:
    _setup(tmp_path, monkeypatch)
    result = CliRunner().invoke(skills_group, ["curate", "--term", "data-product:x"])
    assert result.exit_code != 0
    assert "requires --apply" in result.output


def test_output_untouched_on_failure(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path))
    _registry(tmp_path, [])  # empty registry -> hard error
    out = tmp_path / "plan.json"
    out.write_text("PRIOR", encoding="utf-8")
    result = CliRunner().invoke(skills_group, ["curate", "--output", str(out)])
    assert result.exit_code != 0
    assert out.read_text(encoding="utf-8") == "PRIOR"


def test_output_writes_full_payload_not_stdout(tmp_path: Path, monkeypatch) -> None:
    fb, term = _setup(tmp_path, monkeypatch)
    out = tmp_path / "plan.json"
    result = CliRunner().invoke(skills_group, ["curate", "--format", "json", "--output", str(out)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == ""  # payload went to the file, not stdout
    obj = json.loads(out.read_text(encoding="utf-8"))
    assert obj["mode"] == "report" and any(r["term"] == term for r in obj["rows"])


def test_apply_with_output_is_rejected(tmp_path: Path, monkeypatch) -> None:
    # --output is report-only; combined with --apply it must error BEFORE any write,
    # so no feedback is committed and no file is created (apply stays atomic).
    fb, _ = _setup(tmp_path, monkeypatch)
    out = tmp_path / "plan.json"
    result = CliRunner().invoke(skills_group, ["curate", "--apply", "--output", str(out)])
    assert result.exit_code != 0
    assert "cannot be combined with --apply" in result.output
    assert not out.exists()
    assert not fb.exists() or load_all_entries(fb) == []  # apply never ran


def test_bad_status_reports_click_error(tmp_path: Path, monkeypatch) -> None:
    # A persisted entry with an out-of-vocabulary status must surface as a clean
    # Click error, not an uncaught CurateStatusError traceback.
    from science_tool.feedback import FeedbackEntry, save_entry

    fb, term = _setup(tmp_path, monkeypatch)
    save_entry(fb, FeedbackEntry(id="fb-2026-07-28-900", target=f"skill-coverage:{term}",
                                 summary="s", concern="tooling", category="gap", status="bogus"))
    result = CliRunner().invoke(skills_group, ["curate", "--format", "json"])
    assert result.exit_code != 0
    assert "unknown status" in result.output
