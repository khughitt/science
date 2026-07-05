"""CLI tests for `science curate consolidation-candidates` (read-only)."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner


def _write(root: Path, kind_dir: str, name: str, fm: dict) -> None:
    d = root / "entities" / kind_dir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(
        "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\nbody\n", encoding="utf-8"
    )


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: cli-test\n", encoding="utf-8")


def _fixture(root: Path) -> None:
    _seed(root)
    _write(root, "interpretations", "0001-foo-v1", {"id": "interpretation:0001-foo-v1", "kind": "interpretation"})
    _write(root, "interpretations", "0002-foo-v2", {"id": "interpretation:0002-foo-v2", "kind": "interpretation"})


def test_cli_json_format(tmp_path: Path) -> None:
    _fixture(tmp_path)
    from science_tool.cli import main

    result = CliRunner().invoke(
        main, ["curate", "consolidation-candidates", "--project-root", str(tmp_path), "--format", "json"]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["counts"]["semantic"] == 1
    assert payload["semantic_clusters"][0]["members"] == [
        "interpretation:0001-foo-v1",
        "interpretation:0002-foo-v2",
    ]


def test_cli_text_format(tmp_path: Path) -> None:
    _fixture(tmp_path)
    from science_tool.cli import main

    result = CliRunner().invoke(
        main, ["curate", "consolidation-candidates", "--project-root", str(tmp_path), "--format", "text"]
    )
    assert result.exit_code == 0, result.output
    assert "structural-family" in result.output
    assert "interpretation:0001-foo-v1" in result.output


def test_cli_is_read_only(tmp_path: Path) -> None:
    _fixture(tmp_path)
    from science_tool.cli import main

    paths = sorted((tmp_path / "entities").rglob("*.md"))
    before = {p: p.stat().st_mtime_ns for p in paths}

    result = CliRunner().invoke(
        main, ["curate", "consolidation-candidates", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    after = {p: p.stat().st_mtime_ns for p in paths}
    assert before == after  # no file was written
