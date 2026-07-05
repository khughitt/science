"""`science project index` must discover questions/hypotheses in the v3 layout.

Regression: project_index globbed fixed `specs/hypotheses` and `doc/questions`
dirs, so a layout_version-3 project (entities live under `entities/<kind>/`)
produced an empty index even with questions on disk.
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool import cli


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _question(slug: str, title: str, status: str) -> str:
    return (
        "---\n"
        "kind: question\n"
        f"title: {title}\n"
        f"status: {status}\n"
        "created: '2026-05-01'\n"
        "updated: '2026-05-02'\n"
        f"id: question:{slug}\n"
        "related: []\n"
        "---\n\n"
        "## Question\n\nBody.\n"
    )


def _hypothesis(slug: str, title: str, status: str) -> str:
    return (
        "---\n"
        "kind: hypothesis\n"
        f"title: {title}\n"
        f"status: {status}\n"
        "created: '2026-05-01'\n"
        "updated: '2026-05-02'\n"
        f"id: hypothesis:{slug}\n"
        "related: []\n"
        "---\n\n"
        "## Hypothesis\n\nBody.\n"
    )


def _seed_v3(root: Path) -> None:
    _write(
        root,
        "science.yaml",
        "name: t\nprofile: research\nlayout_version: 3\nknowledge_profiles:\n  local: local\n",
    )
    _write(root, "entities/questions/0001-recurring.md", _question("0001-recurring", "Q one", "active"))
    _write(root, "entities/questions/0002-second.md", _question("0002-second", "Q two", "open"))
    _write(root, "entities/hypotheses/0001-h.md", _hypothesis("0001-h", "H one", "proposed"))


def test_project_index_lists_v3_entities(tmp_path: Path) -> None:
    _seed_v3(tmp_path)
    result = CliRunner().invoke(
        cli.main, ["project", "index", "--format", "json", "--project-root", str(tmp_path)]
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    rows = payload["rows"]
    by_kind = {(r["kind"], r["title"]): r for r in rows}

    assert ("question", "Q one") in by_kind
    assert ("question", "Q two") in by_kind
    assert ("hypothesis", "H one") in by_kind
    assert by_kind[("question", "Q one")]["status"] == "active"
    assert by_kind[("hypothesis", "H one")]["status"] == "proposed"
