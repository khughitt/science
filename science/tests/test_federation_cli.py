from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


def _write_yaml(path: Path, body: str) -> None:
    (path / "science.yaml").write_text(body, encoding="utf-8")


def test_federation_validate_clean(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    meta.mkdir()
    a.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
""",
    )
    _write_yaml(
        a,
        f"""
name: a
id: a
role: data-source
parent: {meta}
profile: research
research_question: "..."
""",
    )
    monkeypatch.chdir(meta)
    runner = CliRunner()
    result = runner.invoke(main, ["federation", "validate"])
    assert result.exit_code == 0, result.output
    assert "ok" in result.output.lower() or "no issues" in result.output.lower()


def test_federation_validate_surfaces_issues(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    meta.mkdir()
    a.mkdir()
    _write_yaml(
        meta,
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: a
    path: {a}
    role: data-source
""",
    )
    _write_yaml(
        a,
        """
name: a
id: a
role: data-source
profile: research
research_question: "..."
""",
    )
    monkeypatch.chdir(meta)
    runner = CliRunner()
    result = runner.invoke(main, ["federation", "validate"])
    assert result.exit_code != 0
    assert "missing_parent" in result.output


def test_federation_validate_refuses_non_meta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    a = tmp_path / "a"
    a.mkdir()
    _write_yaml(
        a,
        """
name: a
id: a
role: data-source
profile: research
research_question: "..."
""",
    )
    monkeypatch.chdir(a)
    runner = CliRunner()
    result = runner.invoke(main, ["federation", "validate"])
    assert result.exit_code != 0
    assert "not a meta" in result.output.lower() or "not a meta" in (result.stderr or "").lower()
