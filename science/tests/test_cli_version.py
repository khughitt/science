from __future__ import annotations

import json
import tomllib
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main


ROOT = Path(__file__).resolve().parents[2]


def _package_version() -> str:
    package = tomllib.loads((ROOT / "science" / "pyproject.toml").read_text(encoding="utf-8"))
    return package["project"]["version"]


def test_root_version_option_reports_the_declared_package_version() -> None:
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert result.output == f"science {_package_version()}\n"


def test_package_and_plugin_establish_0_3_0_baseline() -> None:
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

    assert _package_version() == "0.3.0"
    assert plugin["version"] == _package_version()
