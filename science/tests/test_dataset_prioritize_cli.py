# tests/test_dataset_prioritize_cli.py
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(root: Path) -> None:
    d = root / "doc" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "a.md").write_text(
        '---\nid: "dataset:a"\ntype: "dataset"\ntitle: "A"\norigin: "external"\n'
        'access: {level: "controlled", verified: true}\n---\n', encoding="utf-8")
    (d / "b.md").write_text(
        '---\nid: "dataset:b"\ntype: "dataset"\ntitle: "B"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n', encoding="utf-8")


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli, ["dataset", "prioritize", *args],
        catch_exceptions=False, env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
    )


def test_prioritize_runs_without_graph_and_warns(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path)
    assert res.exit_code == 0
    assert "dataset:a" in res.output and "dataset:b" in res.output
    # no graph present → a stderr warning is emitted but the command still ranks.
    # This repo's CliRunner captures stderr separately (see tests/test_datasets_cli.py:80).
    combined = res.output + (res.stderr if res.stderr_bytes else "")
    assert "graph" in combined.lower()


def test_prioritize_json_and_explain(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "--format", "json")
    assert res.exit_code == 0
    import json
    # Click 8 mixes stderr into output; strip any leading warning lines before parsing.
    json_text = "\n".join(
        line for line in res.output.splitlines() if not line.startswith("warning:")
    )
    rows = json.loads(json_text)
    assert any(r["id"] == "dataset:a" for r in rows)
