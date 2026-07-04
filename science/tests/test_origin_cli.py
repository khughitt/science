from __future__ import annotations

from pathlib import Path

import pytest
from _fixtures.entity_helpers import seed_project
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.entities import parse_origin_spec


def test_parse_user() -> None:
    assert parse_origin_spec("user") == {"type": "user"}


def test_parse_user_with_date() -> None:
    assert parse_origin_spec("user@2026-05-10") == {"type": "user", "date": "2026-05-10"}


def test_parse_literature_prefixed_ref() -> None:
    assert parse_origin_spec("literature:paper:smith2019@2019-03-01") == {
        "type": "literature",
        "ref": "paper:smith2019",
        "date": "2019-03-01",
    }


def test_parse_literature_bare_key_normalized_to_cite() -> None:
    assert parse_origin_spec("literature:Smith2019") == {"type": "literature", "ref": "cite:Smith2019"}


def test_parse_rejects_literature_without_ref() -> None:
    # Strictness: literature with no ref must raise here, BEFORE any file write.
    with pytest.raises(Exception):
        parse_origin_spec("literature")


def test_parse_independent_prefix_literature() -> None:
    assert parse_origin_spec("+literature:cite:K@2019-01-01") == {
        "type": "literature",
        "ref": "cite:K",
        "date": "2019-01-01",
        "independent": True,
    }


def test_parse_no_prefix_has_no_independent_key() -> None:
    # A plain spec must NOT carry an independent key (defaults False downstream).
    assert parse_origin_spec("literature:cite:K") == {"type": "literature", "ref": "cite:K"}


def test_parse_independent_prefix_on_user() -> None:
    assert parse_origin_spec("+user") == {"type": "user", "independent": True}


def test_hypothesis_create_writes_origins_and_added_by() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "hypotheses",
                "create",
                "Test H",
                "--origin",
                "user@2026-05-10",
                "--origin",
                "literature:Smith2019",
                "--added-by",
                "user",
            ],
        )

        assert result.exit_code == 0, result.output
        created = next((root / "entities" / "hypotheses").glob("*.md"))
        text = created.read_text(encoding="utf-8")
        assert "added_by: user" in text
        assert "type: user" in text
        assert "ref: cite:Smith2019" in text


def test_hypothesis_create_rejects_malformed_literature_origin() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["hypotheses", "create", "Bad", "--origin", "literature"])

        assert result.exit_code != 0
        hyp_dir = root / "entities" / "hypotheses"
        assert not (hyp_dir.exists() and list(hyp_dir.glob("*.md")))


def test_question_create_writes_origins_and_added_by() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "questions",
                "create",
                "Test Q",
                "--origin",
                "user@2026-05-10",
                "--origin",
                "literature:Smith2019",
                "--added-by",
                "user",
            ],
        )

        assert result.exit_code == 0, result.output
        created = next((root / "entities" / "questions").glob("*.md"))
        text = created.read_text(encoding="utf-8")
        assert "added_by: user" in text
        assert "type: user" in text
        assert "ref: cite:Smith2019" in text


def test_question_create_rejects_malformed_literature_origin() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(main, ["questions", "create", "Bad", "--origin", "literature"])

        assert result.exit_code != 0
        q_dir = root / "entities" / "questions"
        assert not (q_dir.exists() and list(q_dir.glob("*.md")))


def test_question_create_writes_independent_origin() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "questions",
                "create",
                "Convergent Q",
                "--origin",
                "assistant:explore-ideas-mechanism",
                "--origin",
                "+literature:cite:Smith2019",
                "--added-by",
                "explore-ideas:test:cand-mechanism-x",
            ],
        )

        assert result.exit_code == 0, result.output
        created = next((root / "entities" / "questions").glob("*.md"))
        text = created.read_text(encoding="utf-8")
        assert "ref: cite:Smith2019" in text
        assert "independent: true" in text
        assert "added_by: explore-ideas:test:cand-mechanism-x" in text
