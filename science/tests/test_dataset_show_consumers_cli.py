"""Tests for `science dataset show` and `dataset consumers`."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _seed(root: Path) -> None:
    d = root / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "foo.md").write_text(
        '---\nid: "dataset:foo"\ntype: "dataset"\ntitle: "Foo"\nstatus: "candidate"\n'
        'origin: "external"\ntier: "track"\nconsumed_by: ["plan:p1", "workflow-run:r1"]\n'
        'access: {level: "public", verified: false}\n---\n\nBody text here.\n',
        encoding="utf-8",
    )


def _run(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli, list(args), catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def test_show_accepts_bare_and_prefixed_ref(tmp_path: Path) -> None:
    _seed(tmp_path)
    for ref in ("foo", "dataset:foo"):
        res = _run(tmp_path, "dataset", "show", ref)
        assert res.exit_code == 0, res.output
        assert "dataset:foo" in res.output
        assert "Body text here." in res.output


def test_show_missing_exits_2_naming_scopes(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "dataset", "show", "nope")
    assert res.exit_code == 2
    assert "local" in res.output.lower() and "commons" in res.output.lower()


def test_show_traversal_ref_is_miss(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "dataset", "show", "../../etc/passwd")
    assert res.exit_code == 2  # invalid slug → clean not-found, no path escape


def test_consumers_lists_consumed_by(tmp_path: Path) -> None:
    _seed(tmp_path)
    res = _run(tmp_path, "dataset", "consumers", "dataset:foo")
    assert res.exit_code == 0
    assert "plan:p1" in res.output
    assert "workflow-run:r1" in res.output


def test_consumers_empty(tmp_path: Path) -> None:
    d = tmp_path / "entities" / "datasets"
    d.mkdir(parents=True, exist_ok=True)
    (d / "bar.md").write_text(
        '---\nid: "dataset:bar"\ntype: "dataset"\ntitle: "Bar"\nstatus: "candidate"\n---\n',
        encoding="utf-8",
    )
    res = _run(tmp_path, "dataset", "consumers", "bar")
    assert res.exit_code == 0
    assert "no recorded consumers" in res.output.lower()
