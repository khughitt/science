from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


def test_datasets_hydrate_worktree_cli_links_data_dir(tmp_path: Path) -> None:
    source = tmp_path / "source"
    worktree = tmp_path / "worktree"
    (source / "data" / "processed" / "arxiv").mkdir(parents=True)
    (source / "data" / "processed" / "arxiv" / "datapackage.json").write_text("{}", encoding="utf-8")
    worktree.mkdir()

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "datasets",
            "hydrate-worktree",
            "--project-root",
            str(worktree),
            "--source-root",
            str(source),
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert {"path": "data/processed", "status": "linked"} in [
        {"path": row["path"], "status": row["status"]} for row in payload["rows"]
    ]
    assert (worktree / "data" / "processed" / "arxiv" / "datapackage.json").exists()
