# tests/test_dataset_prioritize_cli.py
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(root: Path) -> None:
    d = root / "entities" / "datasets"
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
    # dataset:a is controlled (gated) and hidden by default; --include-gated keeps
    # both rows so this test exercises the no-graph ranking path on a full set.
    res = _run(tmp_path, "--include-gated")
    assert res.exit_code == 0
    assert "dataset:a" in res.output and "dataset:b" in res.output
    # no graph present → a stderr warning is emitted but the command still ranks.
    # Click 8's CliRunner mixes stderr into res.output; the res.stderr_bytes guard keeps
    # this robust if a future Click version separates them.
    combined = res.output + (res.stderr if res.stderr_bytes else "")
    assert "graph" in combined.lower()


def test_prioritize_json(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "--include-gated", "--format", "json")
    assert res.exit_code == 0
    import json
    # Click 8 mixes stderr into output; strip any leading warning lines before parsing.
    json_text = "\n".join(
        line for line in res.output.splitlines() if not line.startswith("warning:")
    )
    rows = json.loads(json_text)
    assert any(r["id"] == "dataset:a" for r in rows)


def test_prioritize_excludes_gated_by_default(tmp_path: Path) -> None:
    # _seed() writes dataset:a (controlled, gated) and dataset:b (public).
    _seed(tmp_path)
    import json

    def _ids(*args: str) -> set[str]:
        res = _run(tmp_path, *args, "--format", "json")
        assert res.exit_code == 0
        text = "\n".join(
            ln for ln in res.output.splitlines() if not ln.startswith("warning:")
        )
        return {r["id"] for r in json.loads(text)}

    assert _ids() == {"dataset:b"}                       # gated controlled hidden
    assert _ids("--include-gated") == {"dataset:a", "dataset:b"}
    assert _ids("--level", "controlled") == {"dataset:a"}  # explicit level overrides


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
