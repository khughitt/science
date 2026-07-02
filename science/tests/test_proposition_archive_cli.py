from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.archive import load_archive_index
from science_tool.cli import main


def _seed(root: Path) -> None:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")


def _proposition(root: Path, slug: str, *, status: str = "active", extra_frontmatter: str = "") -> Path:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\n"
        f"id: proposition:{slug}\n"
        "type: proposition\n"
        f"title: {slug}\n"
        f"status: {status}\n"
        f"{extra_frontmatter}"
        "---\n"
        "Claim.\n",
        encoding="utf-8",
    )
    return path


def test_archive_superseded_propositions_cli_json_dry_run(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")

    result = CliRunner().invoke(
        main,
        ["annotate", "archive-superseded-propositions", "--root", str(tmp_path), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"] == {"ready": 1, "blocked": 0, "skipped": 0}
    assert payload["candidates"][0]["id"] == "proposition:duplicate"
    assert load_archive_index(tmp_path).active_by_id == {}


def test_archive_superseded_propositions_cli_apply_moves_ready_candidate(tmp_path: Path) -> None:
    _seed(tmp_path)
    _proposition(tmp_path, "canonical")
    _proposition(tmp_path, "duplicate", status="superseded", extra_frontmatter="superseded_by: proposition:canonical\n")

    result = CliRunner().invoke(
        main,
        ["annotate", "archive-superseded-propositions", "--root", str(tmp_path), "--apply", "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["applied"] == ["proposition:duplicate"]
    assert "proposition:duplicate" in load_archive_index(tmp_path).active_by_id
