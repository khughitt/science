"""Tests for the feedback CLI command group."""

from __future__ import annotations

import json

import pytest
from click.testing import CliRunner

from science_tool.cli import main


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
