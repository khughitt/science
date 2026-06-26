# tests/test_dataset_prioritize_cli.py
from __future__ import annotations

import json
import os
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli
from science_tool.graph.materialize import materialize_graph


def _seed(root: Path) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "a.md").write_text(
        '---\nid: "dataset:a"\ntype: "dataset"\ntitle: "A"\norigin: "external"\n'
        'access: {level: "controlled", verified: true}\n---\n',
        encoding="utf-8",
    )
    (d / "b.md").write_text(
        '---\nid: "dataset:b"\ntype: "dataset"\ntitle: "B"\norigin: "external"\n'
        'access: {level: "public", verified: false}\n---\n',
        encoding="utf-8",
    )


def _json_payload(res):
    text = "\n".join(line for line in res.output.splitlines() if not line.startswith("warning:"))
    return json.loads(text)


def _json_rows(res) -> list[dict]:
    payload = _json_payload(res)
    if isinstance(payload, dict):
        return payload["rows"]
    return payload


def _seed_paper_reach(root: Path, *, include_paper: bool = True) -> None:
    (root / "science.yaml").write_text('slug: "tp"\n', encoding="utf-8")
    d = root / "entities" / "datasets"
    h = root / "entities" / "hypotheses"
    p = root / "entities" / "papers"
    d.mkdir(parents=True, exist_ok=True)
    h.mkdir(parents=True, exist_ok=True)
    (d / "d.md").write_text(
        '---\nid: "dataset:d"\ntype: "dataset"\ntitle: "D"\norigin: "external"\n'
        'access: {level: "public", verified: true}\n---\n',
        encoding="utf-8",
    )
    (h / "h.md").write_text(
        '---\nid: "hypothesis:h"\ntype: "hypothesis"\ntitle: "H"\n---\n',
        encoding="utf-8",
    )
    if include_paper:
        p.mkdir(parents=True, exist_ok=True)
        (p / "p.md").write_text(
            '---\nid: "paper:p"\ntype: "paper"\ntitle: "P"\n'
            'related: ["hypothesis:h"]\n'
            "dataset_usage:\n"
            '  - ref: "dataset:d"\n'
            '    role: "analyzed"\n'
            '    overlap: "full"\n---\n',
            encoding="utf-8",
        )


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["dataset", "prioritize", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path)},
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
    payload = _json_payload(res)
    rows = payload["rows"]
    assert any(r["id"] == "dataset:a" for r in rows)
    assert payload["excluded_summary"] == {"gated": 0, "reference": 0, "pointer": 0}


def test_prioritize_excludes_gated_by_default(tmp_path: Path) -> None:
    # _seed() writes dataset:a (controlled, gated) and dataset:b (public).
    _seed(tmp_path)

    def _ids(*args: str) -> set[str]:
        res = _run(tmp_path, *args, "--format", "json")
        assert res.exit_code == 0
        return {r["id"] for r in _json_rows(res)}

    assert _ids() == {"dataset:b"}  # gated controlled hidden
    assert _ids("--include-gated") == {"dataset:a", "dataset:b"}
    assert _ids("--level", "controlled") == {"dataset:a"}  # explicit level overrides


def test_prioritize_include_reference_pointer_and_runtime_filter(tmp_path: Path) -> None:
    _seed(tmp_path)
    d = tmp_path / "entities" / "datasets"
    (d / "ref.md").write_text(
        '---\nid: "dataset:ref"\ntype: "dataset"\ntitle: "Ref"\norigin: "external"\n'
        'dataset_class: "reference"\naccess: {level: "public", verified: true, source_url: "https://example.org"}\n---\n',
        encoding="utf-8",
    )
    (d / "ptr.md").write_text(
        '---\nid: "dataset:ptr"\ntype: "dataset"\ntitle: "Ptr"\norigin: "external"\n'
        'dataset_class: "pointer"\naccess: {level: "public", verified: true, source_url: "https://example.org/p"}\n---\n',
        encoding="utf-8",
    )

    default = _run(tmp_path, "--format", "json")
    assert default.exit_code == 0
    payload = _json_payload(default)
    assert {r["id"] for r in payload["rows"]} == {"dataset:b"}
    assert payload["excluded_summary"] == {"gated": 1, "reference": 1, "pointer": 1}

    with_reference = _run(tmp_path, "--include-reference", "--format", "json")
    assert {r["id"] for r in _json_rows(with_reference)} == {"dataset:b", "dataset:ref"}

    only_pointer = _run(tmp_path, "--runtime-state", "pointer-only", "--format", "json")
    assert {r["id"] for r in _json_rows(only_pointer)} == {"dataset:ptr"}


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


def test_prioritize_coverage_json_reports_per_target_gaps(tmp_path: Path) -> None:
    _seed(tmp_path)
    qdir = tmp_path / "entities" / "questions"
    qdir.mkdir(parents=True, exist_ok=True)
    (qdir / "q-covered.md").write_text(
        '---\nid: "question:q-covered"\ntype: "question"\ntitle: "Covered"\nrelated: ["dataset:b"]\n---\n',
        encoding="utf-8",
    )
    (qdir / "q-gap.md").write_text(
        '---\nid: "question:q-gap"\ntype: "question"\ntitle: "Gap"\n---\n',
        encoding="utf-8",
    )

    res = _run(tmp_path, "--coverage", "--format", "json")

    assert res.exit_code == 0
    rows = _json_rows(res)
    by_id = {row["target"]: row for row in rows}
    assert by_id["question:q-covered"]["datasets"] == ["dataset:b"]
    assert by_id["question:q-covered"]["coverage_state"] == "unverified"
    assert by_id["question:q-covered"]["gap_reason"] == "only-unverified"
    assert by_id["question:q-gap"]["datasets"] == []
    assert by_id["question:q-gap"]["coverage_state"] == "no-candidate"
    assert by_id["question:q-gap"]["gap_reason"] == "no-candidate"


def test_prioritize_coverage_uses_paper_usage_frontmatter_without_graph(tmp_path: Path) -> None:
    _seed_paper_reach(tmp_path)

    res = _run(tmp_path, "--coverage", "--format", "json")

    assert res.exit_code == 0
    assert "no materialized graph" in res.output.lower()
    rows = _json_rows(res)
    by_id = {row["target"]: row for row in rows}
    assert by_id["hypothesis:h"]["datasets"] == ["dataset:d"]
    assert by_id["hypothesis:h"]["coverage_state"] == "covered-unstaged"
    assert by_id["hypothesis:h"]["gap_reason"] == "unstaged-deposit"


def test_prioritize_coverage_uses_current_frontmatter_when_graph_is_stale(tmp_path: Path) -> None:
    _seed_paper_reach(tmp_path, include_paper=False)
    graph_path = materialize_graph(tmp_path)
    _seed_paper_reach(tmp_path, include_paper=True)
    os.utime(graph_path, (1, 1))

    res = _run(tmp_path, "--coverage", "--format", "json")

    assert res.exit_code == 0
    assert "graph may be stale" in res.output.lower()
    rows = _json_rows(res)
    by_id = {row["target"]: row for row in rows}
    assert by_id["hypothesis:h"]["datasets"] == ["dataset:d"]
    assert by_id["hypothesis:h"]["coverage_state"] == "covered-unstaged"
