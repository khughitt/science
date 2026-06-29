from __future__ import annotations

import json
import re
from collections.abc import Generator
from pathlib import Path

import pytest
from click.testing import CliRunner
from jsonschema import validate as validate_json

from science_tool.cli import main
from science_tool.telemetry import read_events
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
    assert "--all" in result.output
    assert "--experimental-python-sidecar" not in result.output
    assert "--format [text|json]" in result.output
    assert "--profile [full|commit]" in result.output
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


def test_validate_json_emits_actionable_results_and_warns_do_not_fail(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [
            Result(Severity.WARN, Path("doc/demo.md"), 7, "watch this", "demo.warn", "task:t001"),
            Result(Severity.INFO, None, None, "noted", None, None),
        ]

    result = CliRunner().invoke(main, ["validate", "--format", "json", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"] == {"errors": 0, "warnings": 1, "infos": 0}
    assert payload["results"] == [
        {
            "severity": "warn",
            "path": "doc/demo.md",
            "line": 7,
            "message": "watch this",
            "rule": "demo.warn",
            "task": "task:t001",
        },
    ]


def test_validate_json_summary_counts_emitted_results_only(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "noted", "demo.info", None)]

    result = CliRunner().invoke(main, ["validate", "--format", "json", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "summary": {"errors": 0, "warnings": 0, "infos": 0},
        "results": [],
    }


def test_validate_filters_accepted_validation_warnings(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "health:",
                "  accepted_validation:",
                "    - rule: demo.warn",
                "      severity: warning",
                "      path: doc/demo.md",
                "      message_contains: watch this",
                "      reason: Reviewed residual warning.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [
            Result(Severity.WARN, Path("doc/demo.md"), 7, "watch this", "demo.warn", "task:t001"),
            Result(Severity.WARN, Path("doc/other.md"), 9, "keep this", "demo.other", None),
        ]

    result = CliRunner().invoke(main, ["validate", "--format", "json", "--project-root", str(project)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"] == {"errors": 0, "warnings": 1, "infos": 0}
    assert payload["results"] == [
        {
            "severity": "warn",
            "path": "doc/other.md",
            "line": 9,
            "message": "keep this",
            "rule": "demo.other",
            "task": None,
        },
    ]


def test_validate_filters_accepted_warnings_before_gate_evaluation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    project.joinpath("science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "health:",
                "  accepted_validation:",
                "    - rule: code.ghost",
                "      severity: warning",
                "      path: code/demo.py",
                "      reason: Reviewed ghost file during migration.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("code/demo.py"), None, "ghost", "code.ghost", None)]

    result = CliRunner().invoke(
        main,
        ["validate", "--fail-on", "ghost-files", "--format", "json", "--project-root", str(project)],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "summary": {"errors": 0, "warnings": 0, "infos": 0},
        "results": [],
    }


def test_validate_records_failure_summary_telemetry(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.ERROR, Path("secret/path.md"), 9, "private message", "demo.error", None)]

    project = tmp_path / "project"
    project.mkdir()
    telemetry_dir = tmp_path / "telemetry"
    result = CliRunner().invoke(
        main,
        ["validate", "--format", "json", "--project-root", str(_project(project))],
        env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
    )

    assert result.exit_code == 1, result.output
    events = [event for event in read_events(telemetry_dir) if event.get("event_type") == "validation_summary"]
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "fail"
    assert event["counts"] == {"error": 1, "warn": 0, "info": 0}
    assert event["top_checks"] == [{"check": "demo.error", "count": 1}]
    serialized = json.dumps(event)
    assert "secret/path.md" not in serialized
    assert "private message" not in serialized


def test_validate_records_warning_summary_telemetry(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.WARN, Path("doc/demo.md"), 7, "watch this", "demo.warn", None)]

    project = tmp_path / "project"
    project.mkdir()
    telemetry_dir = tmp_path / "telemetry"
    result = CliRunner().invoke(
        main,
        ["validate", "--format", "json", "--project-root", str(_project(project))],
        env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
    )

    assert result.exit_code == 0, result.output
    events = [event for event in read_events(telemetry_dir) if event.get("event_type") == "validation_summary"]
    assert len(events) == 1
    assert events[0]["status"] == "warn"
    assert events[0]["counts"] == {"error": 0, "warn": 1, "info": 0}
    assert events[0]["top_checks"] == [{"check": "demo.warn", "count": 1}]


def test_validate_records_clean_summary_telemetry(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    result = CliRunner().invoke(
        main,
        ["validate", "--format", "json", "--project-root", str(_project(tmp_path))],
        env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
    )

    assert result.exit_code == 0, result.output
    events = [event for event in read_events(telemetry_dir) if event.get("event_type") == "validation_summary"]
    assert len(events) == 1
    assert events[0]["status"] == "pass"
    assert events[0]["counts"] == {"error": 0, "warn": 0, "info": 0}
    assert events[0]["top_checks"] == []


def test_validate_commit_profile_skips_graph_backed_checks(tmp_path: Path) -> None:
    @Check(section="knowledge graph...", order=17)
    def check_graph(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "graph ran", "graph", None)]

    @Check(section="task queue...", order=18)
    def check_tasks(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "tasks ran", "tasks", None)]

    @Check(section="evidence lines", order=27)
    def check_belief_authoring(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "belief ran", "belief", None)]

    result = CliRunner().invoke(
        main,
        ["validate", "--profile", "commit", "--format", "json", "--project-root", str(_project(tmp_path))],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"] == {"errors": 0, "warnings": 0, "infos": 0}
    assert payload["results"] == []


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


def test_validate_all_is_passed_through_to_checks(tmp_path: Path) -> None:
    seen: list[bool] = []

    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        seen.append(ctx.include_all_checks)
        return []

    result = CliRunner().invoke(
        main,
        ["validate", "--all", "--format", "json", "--project-root", str(_project(tmp_path))],
    )

    assert result.exit_code == 0, result.output
    assert seen == [True]


def test_validate_text_uses_section_banners_and_color_policy(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [
            Result(Severity.ERROR, Path("science.yaml"), 1, "broken", "demo.error", None),
            Result(Severity.WARN, None, None, "warning", "demo.warn", None),
        ]

    result = CliRunner().invoke(
        main,
        ["--color", "always", "validate", "--verbose", "--project-root", str(_project(tmp_path))],
    )

    assert result.exit_code == 1, result.output
    assert f"{BANNER}\nScience Project Validation\n{BANNER}" in result.output
    assert "Checking demo" in result.output
    assert "ERROR science.yaml:1 [demo.error] broken" in result.output
    assert "WARN warning [demo.warn]" in result.output
    assert f"\n{BANNER}\n" in result.output
    assert "FAILED: 1 error(s), 1 warning(s)" in result.output
    assert ANSI_RE.search(result.output) is not None


def test_validate_text_suppresses_info_without_verbose(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [
            Result(Severity.INFO, Path("doc/demo.md"), None, "Checking doc/demo.md...", "demo.info", None),
            Result(Severity.WARN, None, None, "warning", "demo.warn", None),
        ]

    result = CliRunner().invoke(main, ["validate", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert "Checks: 1 included, 0 skipped (profile: full)" in result.output
    assert "Checking demo" not in result.output
    assert "INFO" not in result.output
    assert "Checking doc/demo.md" not in result.output
    assert "WARN warning [demo.warn]" in result.output
    assert "PASSED with 1 warning(s)" in result.output


def test_validate_text_shows_prose_lint_config_notice_without_verbose(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [
            Result(
                Severity.INFO,
                None,
                None,
                "prose lint checks limited by science.yaml: 1/5 enabled (unsupported-citation-syntax); "
                "disabled: bare-author-year, short-form-ids, frontmatter-inline-gap, numeric-anchor",
                "prose_lints.config",
                None,
            ),
            Result(Severity.INFO, None, None, "ordinary info", "demo.info", None),
        ]

    result = CliRunner().invoke(main, ["validate", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert (
        "NOTE prose lint checks limited by science.yaml: 1/5 enabled (unsupported-citation-syntax); "
        "disabled: bare-author-year, short-form-ids, frontmatter-inline-gap, numeric-anchor"
    ) in result.output
    assert "ordinary info" not in result.output
    assert "INFO" not in result.output
    assert "PASSED: all checks clean" in result.output


def test_validate_text_verbose_shows_info_without_duplicate_checking_location(tmp_path: Path) -> None:
    @Check(section="discussions", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [
            Result(
                Severity.INFO,
                Path("entities/discussions/0001-demo.md"),
                None,
                "Checking entities/discussions/0001-demo.md...",
                "discussions",
                None,
            )
        ]

    result = CliRunner().invoke(main, ["validate", "--verbose", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert "Checks: 1 included, 0 skipped (profile: full)" in result.output
    assert "Checking discussions" in result.output
    assert "INFO [discussions] Checking entities/discussions/0001-demo.md..." in result.output
    assert "INFO entities/discussions/0001-demo.md [discussions] Checking" not in result.output
    assert "\n\nChecking discussions" not in result.output


def test_validate_text_profile_summary_lists_skipped_checks(tmp_path: Path) -> None:
    @Check(section="knowledge graph...", order=10)
    def check_graph(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "graph ran", "graph", None)]

    @Check(section="task queue...", order=20)
    def check_tasks(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "tasks ran", "tasks", None)]

    @Check(section="evidence lines", order=30)
    def check_belief_authoring(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.INFO, None, None, "belief ran", "belief", None)]

    result = CliRunner().invoke(
        main,
        ["validate", "--profile", "commit", "--project-root", str(_project(tmp_path))],
    )

    assert result.exit_code == 0, result.output
    assert "Checks: 1 included, 2 skipped (profile: commit; skipped: knowledge graph..., evidence lines)" in result.output
    assert "graph ran" not in result.output
    assert "tasks ran" not in result.output
    assert "belief ran" not in result.output
    assert "PASSED: all checks clean" in result.output


def test_validate_default_text_has_no_ansi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.delenv("NO_COLOR", raising=False)

    result = CliRunner().invoke(main, ["validate", "--project-root", str(_project(tmp_path))])

    assert result.exit_code == 0, result.output
    assert f"{BANNER}\nScience Project Validation\n{BANNER}" in result.output
    assert "Checks: 0 included, 0 skipped (profile: full)" in result.output
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
