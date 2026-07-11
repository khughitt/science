from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.big_picture.cli import big_picture_group

FIXTURE = Path(__file__).parent / "fixtures" / "big_picture" / "minimal_project"


def test_knowledge_gaps_cli_emits_json() -> None:
    result = CliRunner().invoke(
        big_picture_group,
        ["knowledge-gaps", "--project-root", str(FIXTURE)],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    ids = [entry["topic_id"] for entry in payload]
    assert "topic:t02-thin" in ids


def test_knowledge_gaps_help_mentions_legacy_topic_coverage() -> None:
    result = CliRunner().invoke(big_picture_group, ["knowledge-gaps", "--help"])
    assert result.exit_code == 0, result.output
    assert "legacy topic-coverage gaps" in result.output


def test_knowledge_gaps_cli_respects_limit() -> None:
    result = CliRunner().invoke(
        big_picture_group,
        ["knowledge-gaps", "--project-root", str(FIXTURE), "--limit", "1"],
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert len(payload) <= 1


def test_knowledge_gaps_cli_empty_project(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: empty\naspects: []\n")
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    result = CliRunner().invoke(
        big_picture_group,
        ["knowledge-gaps", "--project-root", str(tmp_path)],
    )
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_knowledge_gaps_cli_fails_loudly_when_unwired(tmp_path: Path) -> None:
    """A project whose topic refs ALL dangle must not print [] and exit 0.

    That output is indistinguishable from "your topics are fully covered" -- the
    silent-instrument bug this command's instrument was migrated to stop.
    """
    (tmp_path / "science.yaml").write_text("name: dangling\naspects: []\n")
    (tmp_path / "entities" / "questions").mkdir(parents=True)
    (tmp_path / "entities" / "questions" / "q01.md").write_text(
        '---\nid: "question:q01"\nkind: "question"\nrelated:\n  - "topic:t99-nonexistent"\n---\nQ.\n'
    )

    result = CliRunner().invoke(
        big_picture_group,
        ["knowledge-gaps", "--project-root", str(tmp_path)],
    )

    assert result.exit_code != 0
    assert "did not run" in result.output
    assert "no_topic_entities" in result.output
