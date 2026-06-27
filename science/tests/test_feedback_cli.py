"""Tests for the feedback CLI command group."""

from __future__ import annotations

import json

import pytest
import yaml
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.telemetry import append_event


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestFeedbackAdd:
    def test_add_creates_entry(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(
            main,
            [
                "feedback",
                "add",
                "--target",
                "command:discuss",
                "--summary",
                "Test feedback entry",
            ],
            env=env,
        )
        assert result.exit_code == 0
        assert "fb-" in result.output
        files = list(tmp_path.glob("fb-*.yaml"))
        assert len(files) == 1

    def test_add_with_all_options(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(
            main,
            [
                "feedback",
                "add",
                "--target",
                "template:interpretation",
                "--category",
                "friction",
                "--summary",
                "Data quality section missing",
                "--detail",
                "Found two data bugs at interpretation time",
                "--project",
                "seq-feats",
            ],
            env=env,
        )
        assert result.exit_code == 0
        assert "fb-" in result.output

    def test_add_requires_target(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(
            main,
            ["feedback", "add", "--summary", "No target"],
            env=env,
        )
        assert result.exit_code != 0

    def test_add_requires_summary(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(
            main,
            ["feedback", "add", "--target", "command:test"],
            env=env,
        )
        assert result.exit_code != 0

    def test_add_from_recent_command_error_uses_telemetry_defaults(self, runner: CliRunner, tmp_path):
        telemetry_dir = tmp_path / "telemetry"
        feedback_dir = tmp_path / "feedback"
        append_event(
            telemetry_dir,
            {
                "event_id": "err1",
                "timestamp": "2026-06-27T10:00:00-04:00",
                "event_type": "command_error",
                "command": "dataset verify-access",
                "argv_shape": [
                    "dataset",
                    "verify-access",
                    "dataset:sciplex3",
                    "--source",
                    "<url:redacted>",
                    "--path",
                    "<path:redacted>",
                ],
                "error_class": "ClickException",
            },
        )
        env = {"SCIENCE_FEEDBACK_DIR": str(feedback_dir), "SCIENCE_TELEMETRY_DIR": str(telemetry_dir)}

        result = runner.invoke(
            main,
            ["feedback", "add", "--from-recent", "--summary", "verify-access failed after bad source input"],
            env=env,
        )

        assert result.exit_code == 0, result.output
        entry_path = next(feedback_dir.glob("fb-*.yaml"))
        entry = yaml.safe_load(entry_path.read_text(encoding="utf-8"))
        assert entry["target"] == "command:dataset"
        assert entry["category"] == "friction"
        assert entry["summary"] == "verify-access failed after bad source input"
        assert "Telemetry context:" in entry["detail"]
        assert "- event: err1" in entry["detail"]
        assert "<url:redacted>" in entry["detail"]
        assert "<path:redacted>" in entry["detail"]

    def test_add_from_recent_validation_summary_appends_user_detail(self, runner: CliRunner, tmp_path):
        telemetry_dir = tmp_path / "telemetry"
        feedback_dir = tmp_path / "feedback"
        append_event(
            telemetry_dir,
            {
                "event_id": "val1",
                "timestamp": "2026-06-27T10:00:00-04:00",
                "event_type": "validation_summary",
                "surface": "validation",
                "command": "validate",
                "status": "fail",
                "counts": {"error": 1, "warn": 2, "info": 0},
                "top_checks": [{"check": "dataset.unstaged-deposit", "count": 2}],
            },
        )
        env = {"SCIENCE_FEEDBACK_DIR": str(feedback_dir), "SCIENCE_TELEMETRY_DIR": str(telemetry_dir)}

        result = runner.invoke(
            main,
            [
                "feedback",
                "add",
                "--from-recent",
                "1",
                "--summary",
                "validation failure needs a clearer nudge",
                "--detail",
                "This happened while preparing a dataset catalog patch.",
            ],
            env=env,
        )

        assert result.exit_code == 0, result.output
        entry_path = next(feedback_dir.glob("fb-*.yaml"))
        entry = yaml.safe_load(entry_path.read_text(encoding="utf-8"))
        assert entry["target"] == "command:validate"
        assert entry["category"] == "gap"
        assert entry["detail"].startswith("This happened while preparing a dataset catalog patch.\n\nTelemetry context:")
        assert "- validation_status: fail" in entry["detail"]
        assert "- validation_counts: error=1, warn=2, info=0" in entry["detail"]
        assert "- top_checks: dataset.unstaged-deposit=2" in entry["detail"]

    def test_add_from_recent_fails_without_eligible_telemetry(self, runner: CliRunner, tmp_path):
        telemetry_dir = tmp_path / "telemetry"
        feedback_dir = tmp_path / "feedback"
        append_event(
            telemetry_dir,
            {
                "event_id": "ok1",
                "timestamp": "2026-06-27T10:00:00-04:00",
                "event_type": "command_finish",
                "command": "feedback list",
                "exit_code": 0,
            },
        )
        env = {"SCIENCE_FEEDBACK_DIR": str(feedback_dir), "SCIENCE_TELEMETRY_DIR": str(telemetry_dir)}

        result = runner.invoke(
            main,
            ["feedback", "add", "--from-recent", "--summary", "nothing eligible"],
            env=env,
        )

        assert result.exit_code != 0
        assert "No eligible recent telemetry events" in result.output
        assert list(feedback_dir.glob("fb-*.yaml")) == []


class TestFeedbackList:
    def test_list_empty(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(main, ["feedback", "list"], env=env)
        assert result.exit_code == 0

    def test_list_json_format(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:test", "--summary", "Test"],
            env=env,
        )
        result = runner.invoke(
            main,
            ["feedback", "list", "--format", "json"],
            env=env,
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data["rows"]) == 1


class TestFeedbackUpdate:
    def test_update_status(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:test", "--summary", "Test"],
            env=env,
        )
        files = list(tmp_path.glob("fb-*.yaml"))
        entry_id = files[0].stem

        result = runner.invoke(
            main,
            ["feedback", "update", entry_id, "--status", "addressed", "--resolution", "Fixed in v2"],
            env=env,
        )
        assert result.exit_code == 0
        assert "updated" in result.output.lower() or entry_id in result.output

    def test_update_requires_resolution_for_addressed(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:test", "--summary", "Test"],
            env=env,
        )
        files = list(tmp_path.glob("fb-*.yaml"))
        entry_id = files[0].stem

        result = runner.invoke(
            main,
            ["feedback", "update", entry_id, "--status", "addressed"],
            env=env,
        )
        assert result.exit_code != 0


class TestFeedbackTriage:
    def test_triage_shows_grouped_output(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:discuss", "--summary", "Issue A", "--project", "proj-a"],
            env=env,
        )
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:discuss", "--summary", "Issue B", "--project", "proj-b"],
            env=env,
        )
        result = runner.invoke(main, ["feedback", "triage"], env=env)
        assert result.exit_code == 0
        assert "command:discuss" in result.output

    def test_triage_with_target_glob(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:discuss", "--summary", "A"],
            env=env,
        )
        runner.invoke(
            main,
            ["feedback", "add", "--target", "template:discussion", "--summary", "B"],
            env=env,
        )
        result = runner.invoke(main, ["feedback", "triage", "--target", "command:*"], env=env)
        assert result.exit_code == 0
        assert "command:discuss" in result.output
        assert "template:discussion" not in result.output

    def test_triage_cluster_json_reports_suggested_next_test_target(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            [
                "feedback",
                "add",
                "--target",
                "command:next-steps",
                "--category",
                "friction",
                "--summary",
                "Stale-window completions hide in prior month done-file",
                "--project",
                "proj-a",
            ],
            env=env,
        )
        runner.invoke(
            main,
            [
                "feedback",
                "add",
                "--target",
                "command:next-steps",
                "--category",
                "friction",
                "--summary",
                "Stale window completion hides in the prior month's done file",
                "--project",
                "proj-b",
            ],
            env=env,
        )

        result = runner.invoke(main, ["feedback", "triage", "--cluster", "--format", "json"], env=env)

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["format"] == "json"
        assert payload["rows"][0]["entry_ids"]
        assert payload["rows"][0]["count"] == 2
        assert payload["rows"][0]["suggested_status"] == "quick-win"
        assert payload["rows"][0]["suggested_next_test_target"] == "science/tests/test_command_docs.py"

    def test_triage_cluster_json_can_include_telemetry_context(self, runner: CliRunner, tmp_path):
        telemetry_dir = tmp_path / "telemetry"
        feedback_dir = tmp_path / "feedback"
        append_event(
            telemetry_dir,
            {
                "event_id": "v1",
                "timestamp": "2026-06-27T10:00:00-04:00",
                "event_type": "validation_summary",
                "surface": "validation",
                "command": "validate",
                "status": "warn",
                "counts": {"error": 0, "warn": 1, "info": 0},
                "top_checks": [{"check": "demo.warn", "count": 1}],
            },
        )
        env = {"SCIENCE_FEEDBACK_DIR": str(feedback_dir), "SCIENCE_TELEMETRY_DIR": str(telemetry_dir)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:validate", "--summary", "Validation warnings are recurring"],
            env=env,
        )

        result = runner.invoke(main, ["feedback", "triage", "--cluster", "--with-telemetry", "--format", "json"], env=env)

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        assert payload["rows"][0]["telemetry"]["validation"]["runs"] == 1
        assert payload["rows"][0]["telemetry"]["validation"]["statuses"] == {"warn": 1}
        assert payload["rows"][0]["telemetry"]["validation"]["top_checks"] == {"demo.warn": 1}

    def test_triage_table_can_include_telemetry_context(self, runner: CliRunner, tmp_path):
        telemetry_dir = tmp_path / "telemetry"
        feedback_dir = tmp_path / "feedback"
        append_event(
            telemetry_dir,
            {
                "event_id": "v1",
                "timestamp": "2026-06-27T10:00:00-04:00",
                "event_type": "validation_summary",
                "surface": "validation",
                "command": "validate",
                "status": "fail",
                "counts": {"error": 1, "warn": 0, "info": 0},
                "top_checks": [{"check": "demo.error", "count": 1}],
            },
        )
        env = {"SCIENCE_FEEDBACK_DIR": str(feedback_dir), "SCIENCE_TELEMETRY_DIR": str(telemetry_dir)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:validate", "--summary", "Validation fails repeatedly"],
            env=env,
        )

        result = runner.invoke(main, ["feedback", "triage", "--with-telemetry"], env=env)

        assert result.exit_code == 0, result.output
        assert "command:validate" in result.output
        assert "validate:" in result.output


class TestFeedbackScaffoldTest:
    def test_scaffold_test_creates_failing_pytest_file(self, runner: CliRunner, tmp_path, monkeypatch):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path / "feedback")}
        add_result = runner.invoke(
            main,
            [
                "feedback",
                "add",
                "--target",
                "command:feedback",
                "--category",
                "friction",
                "--summary",
                "Need regression scaffold helper",
                "--detail",
                "The feedback loop needs a one-command test stub.",
            ],
            env=env,
        )
        assert add_result.exit_code == 0, add_result.output
        entry_id = next((tmp_path / "feedback").glob("fb-*.yaml")).stem
        project_root = tmp_path / "project"
        project_root.mkdir()
        monkeypatch.chdir(project_root)

        result = runner.invoke(main, ["feedback", "scaffold-test", entry_id], env=env)

        assert result.exit_code == 0, result.output
        scaffold = project_root / "science" / "tests" / "scaffolded" / f"test_{entry_id.replace('-', '_')}.py"
        assert scaffold.is_file()
        text = scaffold.read_text(encoding="utf-8")
        assert "Need regression scaffold helper" in text
        assert "science/tests/test_feedback_cli.py" in text
        assert "pytest.fail" in text
        assert str(scaffold) in result.output

    def test_scaffold_test_dry_run_reports_path_without_writing(self, runner: CliRunner, tmp_path, monkeypatch):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path / "feedback")}
        add_result = runner.invoke(
            main,
            [
                "feedback",
                "add",
                "--target",
                "framework:benchmarks",
                "--summary",
                "Needs design",
            ],
            env=env,
        )
        assert add_result.exit_code == 0, add_result.output
        entry_id = next((tmp_path / "feedback").glob("fb-*.yaml")).stem
        project_root = tmp_path / "project"
        project_root.mkdir()
        monkeypatch.chdir(project_root)

        result = runner.invoke(main, ["feedback", "scaffold-test", entry_id, "--dry-run"], env=env)

        assert result.exit_code == 0, result.output
        scaffold = project_root / "science" / "tests" / "scaffolded" / f"test_{entry_id.replace('-', '_')}.py"
        assert not scaffold.exists()
        assert "[dry run]" in result.output


class TestFeedbackReport:
    def test_report_generates_markdown(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        runner.invoke(
            main,
            ["feedback", "add", "--target", "command:discuss", "--summary", "Test issue"],
            env=env,
        )
        result = runner.invoke(main, ["feedback", "report"], env=env)
        assert result.exit_code == 0
        assert "Feedback Report" in result.output
        assert "Test issue" in result.output

    def test_report_empty(self, runner: CliRunner, tmp_path):
        env = {"SCIENCE_FEEDBACK_DIR": str(tmp_path)}
        result = runner.invoke(main, ["feedback", "report"], env=env)
        assert result.exit_code == 0
        assert "No feedback entries" in result.output
