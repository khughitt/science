"""CLI: science entities consolidate scaffold / apply (P4)."""
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.entities import create_entity


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    return tmp_path


def test_scaffold_then_apply_via_cli(tmp_path: Path) -> None:
    root = _project(tmp_path)
    create_entity(root, "finding", "A", entity_id="finding:0001-a")
    runner = CliRunner()

    r1 = runner.invoke(main, [
        "entities", "consolidate", "scaffold",
        "--project-root", str(root),
        "--into", "synthesis:0001-d",
        "--members", "finding:0001-a",
        "--title", "Digest",
    ])
    assert r1.exit_code == 0, r1.output
    assert (root / "entities" / "synthesis" / "0001-d.md").exists()

    # dry-run apply: no mutation
    r2 = runner.invoke(main, [
        "entities", "consolidate", "apply", "synthesis:0001-d",
        "--project-root", str(root),
    ])
    assert r2.exit_code == 0, r2.output
    assert json.loads(r2.output)["applied"] == []
    assert (root / "entities" / "findings" / "0001-a.md").exists()

    # apply
    r3 = runner.invoke(main, [
        "entities", "consolidate", "apply", "synthesis:0001-d",
        "--project-root", str(root), "--apply",
    ])
    assert r3.exit_code == 0, r3.output
    assert json.loads(r3.output)["applied"] == ["finding:0001-a"]
    assert not (root / "entities" / "findings" / "0001-a.md").exists()
