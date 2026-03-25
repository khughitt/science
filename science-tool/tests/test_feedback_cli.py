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
                "feedback", "add",
                "--target", "command:discuss",
                "--summary", "Test feedback entry",
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
                "feedback", "add",
                "--target", "template:interpretation",
                "--category", "friction",
                "--summary", "Data quality section missing",
                "--detail", "Found two data bugs at interpretation time",
                "--project", "seq-feats",
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
