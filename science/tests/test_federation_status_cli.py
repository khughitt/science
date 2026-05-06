from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


def test_federation_status_walks_children(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    meta = tmp_path / "meta"
    a = tmp_path / "a"
    b = tmp_path / "b"
    for directory in (meta, a, b):
        directory.mkdir()

    (meta / "science.yaml").write_text(
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "Umbrella."
children:
  - id: a
    path: {a}
    role: data-source
  - id: b
    path: {b}
    role: cancer-type
""",
        encoding="utf-8",
    )
    for child_dir, child_id, child_role, question in (
        (a, "a", "data-source", "child a question"),
        (b, "b", "cancer-type", "child b question"),
    ):
        (child_dir / "science.yaml").write_text(
            f"""
name: {child_id}
id: {child_id}
role: {child_role}
parent: {meta}
profile: research
research_question: "{question}"
""",
            encoding="utf-8",
        )

    monkeypatch.chdir(meta)
    runner = CliRunner()
    result = runner.invoke(main, ["federation", "status"])
    assert result.exit_code == 0, result.output
    assert "Federation:" in result.output or "federation" in result.output.lower()
    assert "data-source" in result.output
    assert "cancer-type" in result.output
    assert "child a question" in result.output
    assert "child b question" in result.output


def test_federation_status_refuses_non_meta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    a = tmp_path / "a"
    a.mkdir()
    (a / "science.yaml").write_text(
        """
name: a
id: a
role: data-source
profile: research
research_question: "..."
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(a)
    runner = CliRunner()
    result = runner.invoke(main, ["federation", "status"])
    assert result.exit_code != 0
    assert "not a meta" in result.output.lower() or "not a meta" in (result.stderr or "").lower()


def test_federation_status_handles_missing_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(tmp_path / "cfg"))
    meta = tmp_path / "meta"
    meta.mkdir()
    missing = tmp_path / "missing"
    (meta / "science.yaml").write_text(
        f"""
name: meta
id: meta
role: meta
profile: research
research_question: "..."
children:
  - id: missing
    path: {missing}
    role: data-source
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(meta)
    runner = CliRunner()
    result = runner.invoke(main, ["federation", "status"])
    assert result.exit_code == 0, result.output
    assert "missing" in result.output
