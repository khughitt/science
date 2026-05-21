from __future__ import annotations

import json
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from jsonschema import validate as validate_json

from science_tool.cli import main
from science_tool.validate import Check, Result, Severity, ValidateContext
from science_tool.validate.checks import clear_checks_for_tests
from science_tool.validate.runner import clear_hooks_for_tests


ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
BANNER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


@pytest.fixture(autouse=True)
def clean_validate_registries() -> Generator[None]:
    clear_checks_for_tests()
    clear_hooks_for_tests()
    yield
    clear_hooks_for_tests()
    clear_checks_for_tests()


def _project(root: Path) -> Path:
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    return root


def test_validate_help_is_registered() -> None:
    result = CliRunner().invoke(main, ["validate", "--help"])

    assert result.exit_code == 0, result.output
    assert "--strict" in result.output
    assert "--experimental-python-sidecar" not in result.output
    assert "--format [text|json]" in result.output
    assert "--project-root PATH" in result.output


def test_validate_json_on_minimal_project_matches_schema(tmp_path: Path) -> None:
    schema = json.loads((Path(__file__).parent / "fixtures" / "output.schema.json").read_text(encoding="utf-8"))

    result = CliRunner().invoke(main, ["validate", "--format", "json", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert ANSI_RE.search(result.output) is None
    payload = json.loads(result.output)
    validate_json(instance=payload, schema=schema)
    assert payload == {
        "summary": {"errors": 0, "warnings": 0, "infos": 0},
        "results": [],
    }


def test_validate_json_emits_results_and_warns_do_not_fail(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [
            Result(Severity.WARN, Path("doc/demo.md"), 7, "watch this", "demo.warn", "task:t001"),
            Result(Severity.INFO, None, None, "noted", None, None),
        ]

    result = CliRunner().invoke(main, ["validate", "--format", "json", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"] == {"errors": 0, "warnings": 1, "infos": 1}
    assert payload["results"] == [
        {
            "severity": "warn",
            "path": "doc/demo.md",
            "line": 7,
            "message": "watch this",
            "rule": "demo.warn",
            "task": "task:t001",
        },
        {
            "severity": "info",
            "path": None,
            "line": None,
            "message": "noted",
            "rule": None,
            "task": None,
        },
    ]


def test_validate_imports_local_hook_by_default(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, "cli sidecar warning", "local.extra", None)]',
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, ["validate", "--format", "json", "--project-root", str(project)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "summary": {"errors": 0, "warnings": 1, "infos": 0},
        "results": [
            {
                "severity": "warn",
                "path": None,
                "line": None,
                "message": "cli sidecar warning",
                "rule": "local.extra",
                "task": None,
            }
        ],
    }


def test_validate_json_redirects_sidecar_stdout_to_stderr(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                'print("sidecar import chatter")',
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    print("sidecar hook chatter")',
                '    return [Result(Severity.WARN, None, None, "cli sidecar warning", "local.extra", None)]',
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(main, ["validate", "--format", "json", "--project-root", str(project)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["summary"] == {"errors": 0, "warnings": 1, "infos": 0}
    assert result.stderr == "sidecar import chatter\nsidecar hook chatter\n"


def test_validate_disable_sidecar_env_skips_python_and_bash_sidecars(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("validate_local.py").write_text(
        "\n".join(
            [
                "from science_tool.validate import Result, Severity, hook",
                "",
                '@hook("extra_checks")',
                "def extra(ctx):",
                '    return [Result(Severity.WARN, None, None, "python sidecar warning", "local.extra", None)]',
            ]
        ),
        encoding="utf-8",
    )
    project.joinpath("validate.local.sh").write_text(
        "\n".join(
            [
                "legacy_warning() {",
                '  warn "bash sidecar warning"',
                "}",
                "register_validation_hook extra_checks legacy_warning",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        ["validate", "--format", "json", "--project-root", str(project)],
        env={"SCIENCE_VALIDATE_DISABLE_SIDECAR": "1"},
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "summary": {"errors": 0, "warnings": 0, "infos": 0},
        "results": [],
    }


def test_validate_rejects_removed_experimental_python_sidecar_flag() -> None:
    result = CliRunner().invoke(main, ["validate", "--experimental-python-sidecar"])

    assert result.exit_code != 0
    assert "No such option: --experimental-python-sidecar" in result.output


def test_validate_exits_nonzero_when_errors_exist(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.ERROR, Path("science.yaml"), 1, "broken", "demo.error", None)]

    result = CliRunner().invoke(main, ["validate", "--format", "json", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 1, result.output
    assert json.loads(result.output)["summary"] == {"errors": 1, "warnings": 0, "infos": 0}


def test_validate_strict_is_passed_through_without_promoting_warnings(tmp_path: Path) -> None:
    seen: list[bool] = []

    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        seen.append(ctx.strict)
        return [Result(Severity.WARN, None, None, "strict warning", "demo.warn", None)]

    result = CliRunner().invoke(
        main,
        ["validate", "--strict", "--format", "json", "--project-root", str(_project(tmp_path))],
    )

    assert result.exit_code == 0, result.output
    assert seen == [True]
    assert json.loads(result.output)["summary"] == {"errors": 0, "warnings": 1, "infos": 0}


def test_validate_text_uses_section_banners_and_color_policy(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [
            Result(Severity.ERROR, Path("science.yaml"), 1, "broken", "demo.error", None),
            Result(Severity.WARN, None, None, "warning", "demo.warn", None),
        ]

    result = CliRunner().invoke(main, ["--color", "always", "validate", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 1, result.output
    assert f"{BANNER}\nScience Project Validation\n{BANNER}" in result.output
    assert "Checking demo" in result.output
    assert "ERROR science.yaml:1 [demo.error] broken" in result.output
    assert "WARN warning [demo.warn]" in result.output
    assert f"\n{BANNER}\n" in result.output
    assert "FAILED: 1 error(s), 1 warning(s)" in result.output
    assert ANSI_RE.search(result.output) is not None


def test_validate_default_text_has_no_ansi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    result = CliRunner().invoke(main, ["validate", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert f"{BANNER}\nScience Project Validation\n{BANNER}" in result.output
    assert "Checking Science project" in result.output
    assert result.output.rstrip().endswith("PASSED: all checks clean")
    assert ANSI_RE.search(result.output) is None


def test_validate_text_warns_only_passes_with_bash_summary(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, None, None, "warning", "demo.warn", None)]

    result = CliRunner().invoke(main, ["validate", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert "PASSED with 1 warning(s)" in result.output


def test_validate_missing_science_yaml_reports_click_error(tmp_path: Path) -> None:
    result = CliRunner().invoke(main, ["validate", "--project-root", str(tmp_path)])

    assert result.exit_code != 0
    assert "science.yaml not found" in result.output


def test_fail_on_ghost_files_exits_nonzero(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/x.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(
        main,
        ["validate", "--fail-on", "ghost-files", "--project-root", str(_project(tmp_path))],
    )
    assert result.exit_code == 1, result.output
    assert "gated at tier 'ghost-files'" in result.output


def test_fail_on_does_not_change_json_payload(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/x.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(
        main,
        ["validate", "--fail-on", "ghost-files", "--format", "json", "--project-root", str(_project(tmp_path))],
    )
    assert result.exit_code == 1, result.output
    payload = json.loads(result.output)
    assert set(payload.keys()) == {"summary", "results"}
    assert payload["summary"] == {"errors": 0, "warnings": 1, "infos": 0}


def test_default_gate_is_report_and_does_not_fail_on_ghost(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/x.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(main, ["validate", "--project-root", str(_project(tmp_path))])
    assert result.exit_code == 0, result.output


def test_code_gate_in_manifest_is_honored(tmp_path: Path) -> None:
    project = tmp_path
    (project / "science.yaml").write_text("name: demo\ncode_gate: ghost-files\n", encoding="utf-8")

    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/x.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(main, ["validate", "--project-root", str(project)])
    assert result.exit_code == 1, result.output


def test_unknown_code_gate_in_manifest_is_clean_error(tmp_path: Path) -> None:
    project = tmp_path
    (project / "science.yaml").write_text("name: demo\ncode_gate: bogus\n", encoding="utf-8")

    result = CliRunner().invoke(main, ["validate", "--project-root", str(project)])
    assert result.exit_code != 0
    assert "unknown code gate tier" in result.output


def test_fail_on_rejects_unknown_tier_value() -> None:
    result = CliRunner().invoke(main, ["validate", "--fail-on", "bogus"])
    assert result.exit_code != 0
    assert "Invalid value for '--fail-on'" in result.output
