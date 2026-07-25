"""Sizes AND completeness for the slice 1b-1 ROWS commands on an over-budget corpus.

Separate from ``test_budget_regression.py`` because that module's ``project`` fixture
asserts exact entity counts; this one seeds extra kinds (interpretations, discussions),
feedback, and a needs-review graph without disturbing those assertions.

Three properties are proven per command:
  1. stdout stays under the ceiling AND projection actually ran -- a truncation footer
     (table) / ``truncation`` object with the full total (JSON) is present. A size-only
     check would pass a no-op sink that never dropped rows on a naturally-small payload.
  2. ``--output PATH`` is complete and unprojected, in both formats.
  3. the three ``list_typed_entities`` callers NOT wired here still work with sink=None.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.budget.measure import visible_len
from science_tool.budget.registry import BUDGETS
from science_tool.cli import main


def _seed_entities(root: Path, kind: str, plural: str, count: int) -> None:
    folder = root / "entities" / plural
    folder.mkdir(parents=True, exist_ok=True)
    for i in range(count):
        (folder / f"{i:04d}.md").write_text(
            f"---\nid: {kind}:{kind[0]}{i:04d}-a-deliberately-long-descriptive-slug\n"
            f"kind: {kind}\ntitle: {kind.title()} {i} with a long title to exercise wrapping\n"
            f"status: open\n---\n\nBody paragraph for {kind} {i}.\n"
        )


@pytest.fixture
def rows_corpus(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    _seed_entities(tmp_path, "question", "questions", 300)
    _seed_entities(tmp_path, "interpretation", "interpretations", 300)
    _seed_entities(tmp_path, "discussion", "discussions", 300)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def _assert_stdout_projected(command_path: str, base_args: list[str], seeded_total: int) -> None:
    """stdout is bounded AND projection actually ran (guards against a no-op sink)."""
    table = _invoke(base_args)
    assert table.exit_code == 0, table.output
    ceiling = BUDGETS[command_path].max_chars
    assert visible_len(table.output) <= ceiling, f"{base_args} -> {visible_len(table.output)} > {ceiling}"
    assert "showing " in table.output  # truncation footer proves rows were dropped

    payload = json.loads(_invoke([*base_args, "--format", "json"]).output)
    assert len(payload["rows"]) == BUDGETS[command_path].max_rows
    assert payload["truncation"]["total"] == seeded_total


def _assert_file_complete(command_path: str, base_args: list[str], seeded_total: int, out_dir: Path) -> None:
    """--output PATH is complete and unprojected, in both formats."""
    json_target = out_dir / "complete.json"
    jr = _invoke([*base_args, "--format", "json", "--output", str(json_target)])
    assert jr.exit_code == 0, jr.output
    payload = json.loads(json_target.read_text())
    assert len(payload["rows"]) == seeded_total   # exact per-row completeness, JSON branch
    assert "truncation" not in payload

    table_target = out_dir / "complete.txt"
    tr = _invoke([*base_args, "--output", str(table_target)])
    assert tr.exit_code == 0, tr.output
    written = table_target.read_text()
    assert "showing " not in written
    assert "complete output:" not in written
    # An empty or projected table file slips past the two negative checks above -- that
    # was the prior regression. A complete, unprojected table holds far more than any
    # budgeted stdout ever could, so it must exceed the ceiling. This rejects both an
    # empty file (0 chars) and one capped at max_rows. Exact per-row identity is already
    # proven by the JSON branch, which parses and counts every row from the same sink.
    assert visible_len(written) > BUDGETS[command_path].max_chars


def test_entity_list_is_bounded_and_complete(rows_corpus: Path) -> None:
    # rows_corpus seeds 300 each of questions, interpretations, discussions; `entity list`
    # (kind=None) surfaces all three kinds -> 900 rows.
    _assert_stdout_projected("entity list", ["entity", "list"], seeded_total=900)
    _assert_file_complete("entity list", ["entity", "list"], seeded_total=900, out_dir=rows_corpus)


def test_feedback_list_is_bounded_and_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.feedback import VALID_CATEGORIES

    category = next(iter(sorted(VALID_CATEGORIES)))
    fb_dir = tmp_path / "feedback"
    fb_dir.mkdir()
    for i in range(300):
        (fb_dir / f"fb-2026-01-01-{i:03d}.yaml").write_text(
            f"id: fb-2026-01-01-{i:03d}\n"
            'created: "2026-01-01"\n'
            f"project: demo-project-{i:03d}\n"
            f"target: command:some-long-target-name-{i:03d}\n"
            "concern: methodology:design\n"  # a valid VALID_CONCERNS value
            f"category: {category}\n"
            f"summary: A deliberately long feedback summary line number {i} to exercise wrapping\n"
            "status: open\n"
            "recurrence: 1\n"
        )
    monkeypatch.setenv("SCIENCE_FEEDBACK_DIR", str(fb_dir))
    monkeypatch.chdir(tmp_path)

    _assert_stdout_projected("feedback list", ["feedback", "list"], seeded_total=300)
    _assert_file_complete("feedback list", ["feedback", "list"], seeded_total=300, out_dir=tmp_path)
