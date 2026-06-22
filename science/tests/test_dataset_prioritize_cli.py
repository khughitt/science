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
    # Click 8's CliRunner mixes stderr into res.output; the res.stderr_bytes guard keeps
    # this robust if a future Click version separates them.
    combined = res.output + (res.stderr if res.stderr_bytes else "")
    assert "graph" in combined.lower()


def test_prioritize_json(tmp_path: Path) -> None:
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


def test_prioritize_explain_shows_reason_column(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "--explain")
    assert res.exit_code == 0
    # The "reason" column header is appended ONLY under --explain (it is NOT one of
    # the always-present columns rank/id/score/readiness/reach/gap-flags), and the
    # top_reason cell renders a "reach=" token. Both discriminate explain from plain.
    assert "reason" in res.output
    assert "reach=" in res.output
    # Contrast: a plain (non-explain) run must NOT carry the reason column.
    plain = _run(tmp_path)
    assert plain.exit_code == 0
    assert "reason" not in plain.output
    assert "reach=" not in plain.output
