"""Phase 3c: CLI surface for decision promotion + the generated view."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.decision_log import DecisionSection, render_owner_file

def test_generate_decisions_write(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    (d / "D1.md").write_text(
        render_owner_file(
            DecisionSection("decision:D1", "D1", "First", "2026-01-01", "active", "Why.\n"),
            promoted_from="x",
            today="2026-06-09",
        ),
        encoding="utf-8",
    )
    res = CliRunner().invoke(main, ["entities", "generate-decisions", "--project-root", str(tmp_path), "--write"])
    assert res.exit_code == 0, res.output
    out = (tmp_path / "core" / "decisions.md").read_text(encoding="utf-8")
    assert out.startswith("<!-- GENERATED")
    assert "## D1. First" in out


def test_generate_decisions_dry_run_does_not_write(tmp_path: Path):
    (tmp_path / "science.yaml").write_text(
        "name: t\nprofile: research\nlayout_version: 3\nknowledge:\n  local_profile: local\n",
        encoding="utf-8",
    )
    d = tmp_path / "entities" / "decision"
    d.mkdir(parents=True)
    (d / "D1.md").write_text(
        render_owner_file(
            DecisionSection("decision:D1", "D1", "First", None, None, "Why.\n"), promoted_from="x", today="2026-06-09"
        ),
        encoding="utf-8",
    )
    res = CliRunner().invoke(main, ["entities", "generate-decisions", "--project-root", str(tmp_path)])
    assert res.exit_code == 0, res.output
    assert "## D1. First" in res.output
    assert not (tmp_path / "core" / "decisions.md").exists()
