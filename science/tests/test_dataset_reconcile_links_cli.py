"""Tests for `science dataset reconcile-links`."""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _write_entity(tmp_path: Path, rel: str, frontmatter: str, body: str = "# Body\n") -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n\n{body}", encoding="utf-8")
    return path


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "reconcile-links", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_reconcile_links_reports_free_text_dataset_entry_resolving_to_slug(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "entities/datasets/boiarsky2022.md",
        'id: "dataset:boiarsky2022"\nkind: "dataset"\ntitle: "Boiarsky 2022"\n',
    )
    _write_entity(
        tmp_path,
        "entities/questions/q.md",
        'id: "question:q"\nkind: "question"\ntitle: "Q"\ndatasets:\n  - Boiarsky2022\n',
    )

    res = _run(tmp_path, "--format", "json")

    assert res.exit_code == 1, res.output
    payload = json.loads(res.output)
    assert payload["rows"] == [
        {
            "file": "entities/questions/q.md",
            "entity_id": "question:q",
            "entry": "Boiarsky2022",
            "resolved_dataset": "dataset:boiarsky2022",
            "reason": "slug",
        }
    ]


def test_reconcile_links_fix_rewrites_entries_idempotently(tmp_path: Path) -> None:
    target = _write_entity(
        tmp_path,
        "entities/datasets/gse136410.md",
        'id: "dataset:gse136410"\nkind: "dataset"\ntitle: "GSE136410"\naccessions:\n  - GSE136410\n',
    )
    assert target.exists()
    question = _write_entity(
        tmp_path,
        "entities/questions/q.md",
        'id: "question:q"\nkind: "question"\ntitle: "Q"\ndatasets: [GSE136410]\n',
        body="# Q\n\nBody stays.\n",
    )

    res = _run(tmp_path, "--fix")

    assert res.exit_code == 0, res.output
    text = question.read_text(encoding="utf-8")
    assert "datasets:\n- dataset:gse136410\n" in text
    assert "# Q\n\nBody stays.\n" in text

    second = _run(tmp_path, "--format", "json")
    assert second.exit_code == 0, second.output
    assert json.loads(second.output)["rows"] == []


def test_reconcile_links_ignores_unresolved_free_text_entries(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "entities/questions/q.md",
        'id: "question:q"\nkind: "question"\ntitle: "Q"\ndatasets:\n  - Unknown cohort\n',
    )

    res = _run(tmp_path, "--format", "json")

    assert res.exit_code == 0, res.output
    assert json.loads(res.output)["rows"] == []
