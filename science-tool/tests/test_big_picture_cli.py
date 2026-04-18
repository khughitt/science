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
