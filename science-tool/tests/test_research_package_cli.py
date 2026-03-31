"""Tests for research-package CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.cli import main


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestResearchPackageInit:
    def test_init_creates_scaffold(self, runner: CliRunner, tmp_path: Path) -> None:
        output = tmp_path / "pkg"
        result = runner.invoke(
            main,
            ["research-package", "init", "--name", "test-pkg", "--title", "Test Package", "--output", str(output)],
        )
        assert result.exit_code == 0, result.output
        assert (output / "datapackage.json").is_file()
        assert (output / "cells.json").is_file()
        assert (output / "data").is_dir()
        assert (output / "figures").is_dir()
        assert (output / "prose").is_dir()
        assert (output / "excerpts").is_dir()

        descriptor = json.loads((output / "datapackage.json").read_text())
        assert descriptor["name"] == "test-pkg"
        assert descriptor["profile"] == "science-research-package"

    def test_init_with_workflow(self, runner: CliRunner, tmp_path: Path) -> None:
        workflow_dir = tmp_path / "workflows" / "test"
        workflow_dir.mkdir(parents=True)
        (workflow_dir / "config.yaml").write_text(
            "lens: theme\nsection: chaos\nrepository: https://github.com/test\nscripts:\n  - scripts/foo.ts\nprovenance_inputs:\n  - src/bar.ts\n"
        )

        output = tmp_path / "pkg"
        result = runner.invoke(
            main,
            [
                "research-package", "init",
                "--name", "test-pkg",
                "--title", "Test",
                "--workflow", str(workflow_dir),
                "--output", str(output),
            ],
        )
        assert result.exit_code == 0, result.output
        descriptor = json.loads((output / "datapackage.json").read_text())
        assert descriptor["research"]["provenance"]["scripts"] == ["scripts/foo.ts"]


class TestResearchPackageValidate:
    def _make_valid_package(self, pkg_dir: Path) -> None:
        """Helper to create a minimal valid package for testing."""
        pkg_dir.mkdir(parents=True, exist_ok=True)
        (pkg_dir / "data").mkdir(exist_ok=True)
        (pkg_dir / "prose").mkdir(exist_ok=True)
        (pkg_dir / "data" / "scores.csv").write_text("a,b\n1,2\n")
        (pkg_dir / "prose" / "01.md").write_text("# Intro\n")

        descriptor = {
            "name": "test",
            "title": "Test",
            "profile": "science-research-package",
            "version": "1.0.0",
            "resources": [{"name": "scores", "path": "data/scores.csv"}],
            "research": {
                "cells": "cells.json",
                "figures": [],
                "vegalite_specs": [],
                "code_excerpts": [],
                "provenance": {
                    "workflow": "w", "config": "c", "last_run": "2026-01-01",
                    "git_commit": "abc", "repository": "", "inputs": [], "scripts": [],
                },
            },
        }
        (pkg_dir / "datapackage.json").write_text(json.dumps(descriptor))
        cells = [
            {"type": "narrative", "content": "prose/01.md"},
            {"type": "data-table", "resource": "scores"},
        ]
        (pkg_dir / "cells.json").write_text(json.dumps(cells))

    def test_validate_valid_package(self, runner: CliRunner, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        self._make_valid_package(pkg_dir)
        result = runner.invoke(main, ["research-package", "validate", str(pkg_dir)])
        assert result.exit_code == 0, result.output

    def test_validate_invalid_package(self, runner: CliRunner, tmp_path: Path) -> None:
        pkg_dir = tmp_path / "pkg"
        pkg_dir.mkdir()
        (pkg_dir / "datapackage.json").write_text(json.dumps({
            "name": "bad", "title": "Bad", "profile": "science-research-package",
            "version": "1.0.0", "resources": [{"name": "missing", "path": "data/missing.csv"}],
            "research": {
                "cells": "cells.json", "figures": [], "vegalite_specs": [],
                "code_excerpts": [], "provenance": {
                    "workflow": "w", "config": "c", "last_run": "t",
                    "git_commit": "x", "repository": "", "inputs": [], "scripts": [],
                },
            },
        }))
        (pkg_dir / "cells.json").write_text("[]")
        result = runner.invoke(main, ["research-package", "validate", str(pkg_dir)])
        assert result.exit_code == 1

    def test_validate_no_packages_found(self, runner: CliRunner, tmp_path: Path) -> None:
        result = runner.invoke(main, ["research-package", "validate", str(tmp_path)])
        assert result.exit_code == 0
        assert "No research packages found" in result.output
