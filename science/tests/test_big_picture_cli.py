from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_big_picture_group_registered() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["big-picture", "--help"])
    assert result.exit_code == 0
    assert "resolve-questions" in result.output
    assert "validate" in result.output


def test_resolve_questions_emits_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["big-picture", "resolve-questions", "--project-root", str(FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert "question:q01-direct-to-h1" in payload
    q04 = payload["question:q04-cross-cutting"]
    assert {h["id"] for h in q04["hypotheses"]} == {
        "hypothesis:h1-alpha",
        "hypothesis:h2-beta",
    }
    assert payload["question:q05-orphan"]["primary_hypothesis"] is None


def test_resolve_questions_empty_output_reports_status(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["big-picture", "resolve-questions", "--project-root", str(tmp_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload == {
        "status": "empty",
        "reason": "no question entities found",
        "questions": {},
    }


def test_validate_exits_nonzero_on_issues(tmp_path: Path) -> None:
    # Copy fixture entities into tmp_path so referenced IDs are available.
    import shutil

    shutil.copytree(FIXTURE / "entities", tmp_path / "entities")
    synth_dir = tmp_path / "entities" / "synthesis"
    synth_dir.mkdir(parents=True)
    (synth_dir / "0004-h1-alpha.md").write_text(
        """---
id: "synthesis:0004-h1-alpha"
report_kind: "hypothesis-synthesis"
hypothesis: "hypothesis:h1-alpha"
provenance_coverage: "high"
---

## Arc

Built on interpretation:i99-fake.
"""
    )

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["big-picture", "validate", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 1
    assert "nonexistent_reference" in result.output
    assert "i99-fake" in result.output


def test_validate_passes_on_clean_project(tmp_path: Path) -> None:
    import shutil

    shutil.copytree(FIXTURE / "entities", tmp_path / "entities")
    (tmp_path / "entities" / "synthesis").mkdir(parents=True, exist_ok=True)

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["big-picture", "validate", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0
