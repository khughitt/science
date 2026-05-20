from __future__ import annotations

from pathlib import Path

from science_tool.validate import Severity
from science_tool.validate.legacy_parser import parse


def test_parse_plain_warn() -> None:
    results, log_lines = parse("WARN: advisory message\n")

    assert log_lines == []
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert results[0].path is None
    assert results[0].line is None
    assert results[0].message == "advisory message"
    assert results[0].rule is None
    assert results[0].task is None


def test_parse_ansi_wrapped_warn() -> None:
    results, log_lines = parse("\033[33mWARN: colored warning\033[0m\n")

    assert log_lines == []
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert results[0].message == "colored warning"


def test_parse_warn_with_path_prefix(tmp_path: Path) -> None:
    tmp_path.joinpath("doc").mkdir()
    tmp_path.joinpath("doc", "note.md").write_text("note\n", encoding="utf-8")

    results, log_lines = parse("WARN: doc/note.md: missing summary\n", project_root=tmp_path)

    assert log_lines == []
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert results[0].path == Path("doc/note.md")
    assert results[0].message == "missing summary"


def test_parse_warn_without_valid_path_prefix(tmp_path: Path) -> None:
    results, log_lines = parse("WARN: doc/missing.md: missing summary\n", project_root=tmp_path)

    assert log_lines == []
    assert len(results) == 1
    assert results[0].severity is Severity.WARN
    assert results[0].path is None
    assert results[0].message == "doc/missing.md: missing summary"


def test_parse_error_variants(tmp_path: Path) -> None:
    tmp_path.joinpath("science.yaml").write_text("name: demo\n", encoding="utf-8")

    results, log_lines = parse(
        "\n".join(
            [
                "ERROR: project-level failure",
                "\033[31mERROR: science.yaml: invalid manifest\033[0m",
                "",
            ]
        ),
        project_root=tmp_path,
    )

    assert log_lines == []
    assert len(results) == 2
    assert [result.severity for result in results] == [Severity.ERROR, Severity.ERROR]
    assert results[0].path is None
    assert results[0].message == "project-level failure"
    assert results[1].path == Path("science.yaml")
    assert results[1].message == "invalid manifest"


def test_parse_mixed_multiline_output() -> None:
    results, log_lines = parse(
        "\n".join(
            [
                "Science Project Validation",
                "",
                "WARN: first",
                "ordinary output",
                "ERROR: second",
                "",
            ]
        )
    )

    assert [result.message for result in results] == ["first", "second"]
    assert log_lines == ["Science Project Validation", "", "ordinary output"]


def test_parse_banner_only_input_yields_log_lines() -> None:
    results, log_lines = parse("====\nScience Project Validation\n====\n")

    assert results == []
    assert log_lines == ["====", "Science Project Validation", "===="]


def test_parse_empty_input() -> None:
    results, log_lines = parse("")

    assert results == []
    assert log_lines == []
