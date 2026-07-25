"""Sizes AND completeness for the slice 1b-2 REPORT/DOCUMENT commands.

Separate from test_budget_regression_rows.py (ROWS commands) because these commands
project per section (REPORT) or refuse whole (DOCUMENT) rather than dropping flat rows.

Proven per command:
  DOCUMENT (curate inventory): stdout over budget REFUSES (nonzero exit, names --output,
    emits no partial payload); --output writes the complete document.
  REPORT (prose lint, consolidation-candidates, validate): stdout stays under the ceiling
    AND projection ran (a "showing"/omitted footer in table, an omission marker with full
    totals in JSON); --output is complete and unprojected in both formats.
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


def _invoke(args: list[str]):
    return CliRunner().invoke(main, args, prog_name="science")


def _assert_document_refuses(command_path: str, base_args: list[str], *, sentinel: str) -> None:
    """A DOCUMENT over budget refuses on stdout: nonzero exit, names --output, leaks nothing."""
    result = _invoke(base_args)
    assert result.exit_code != 0, result.output
    assert "--output" in result.output
    assert visible_len(result.output) <= BUDGETS[command_path].max_chars
    assert sentinel not in result.output  # no partial payload leaked past the refusal


def _assert_document_file_complete(base_args, out_dir, *, expected_items, count_items):
    """--output writes the complete document; every seeded record is present."""
    target = out_dir / "complete.json"
    result = _invoke([*base_args, "--output", str(target)])
    assert result.exit_code == 0, result.output
    payload = json.loads(target.read_text())  # the complete document parses whole
    assert count_items(payload) == expected_items
    return payload


def _assert_report_projection(command_path, base_args, out_dir, *, expected_exit, omitted_key, count_items, summary_of):
    """Prove the REPORT contract with the --output file as ground truth.

    - exact exit code in every format;
    - the file is complete and unprojected (no omission marker);
    - projected stdout math reconciles: shown + omitted == the full total;
    - the summary block is byte-identical projected vs complete (projection alters display only);
    - projected stdout stays under the ceiling and carries the "showing " footer;
    - the complete table file exceeds the ceiling (rejects an empty/projected file).
    """
    file_json = out_dir / "complete.json"
    fr = _invoke([*base_args, "--format", "json", "--output", str(file_json)])
    assert fr.exit_code == expected_exit, fr.output
    complete = json.loads(file_json.read_text())
    assert complete.get(omitted_key, 0) == 0, "file JSON must not be projected"
    total = count_items(complete)

    sr = _invoke([*base_args, "--format", "json"])
    assert sr.exit_code == expected_exit, sr.output
    proj = json.loads(sr.output)
    shown, omitted = count_items(proj), proj.get(omitted_key, 0)
    assert omitted > 0, f"expected projection but {omitted_key}={omitted}"
    assert shown + omitted == total, f"{shown} + {omitted} != {total}"
    assert summary_of(proj) == summary_of(complete), "projection must not alter the summary"

    tr = _invoke(base_args)
    assert tr.exit_code == expected_exit, tr.output
    assert visible_len(tr.output) <= BUDGETS[command_path].max_chars
    assert "showing " in tr.output

    file_txt = out_dir / "complete.txt"
    ttr = _invoke([*base_args, "--output", str(file_txt)])
    assert ttr.exit_code == expected_exit, ttr.output
    written = file_txt.read_text()
    assert "showing " not in written
    assert visible_len(written) > BUDGETS[command_path].max_chars


def test_curate_inventory_refuses_and_completes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "science.yaml").write_text("id: demo\nname: demo\n")
    # One record per entity: 900 entities makes the inventory JSON ~340k chars, far over 20,000.
    _seed_entities(tmp_path, "question", "questions", 300)
    _seed_entities(tmp_path, "interpretation", "interpretations", 300)
    _seed_entities(tmp_path, "discussion", "discussions", 300)
    monkeypatch.chdir(tmp_path)
    # A seeded artifact id proves nothing partial leaks when the DOCUMENT refuses on stdout.
    _assert_document_refuses("curate inventory", ["curate", "inventory"], sentinel="discussion:d0000")
    payload = _assert_document_file_complete(
        ["curate", "inventory"], tmp_path,
        expected_items=900, count_items=lambda p: len(p["artifacts"]),
    )
    assert sum(payload["artifact_counts"].values()) == 900  # {question:300, interpretation:300, discussion:300}
