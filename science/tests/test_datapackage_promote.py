"""Retirement guards for the legacy `science data-package` migration surface."""

from __future__ import annotations

import importlib.util

from science_tool.cli import main as cli


def test_data_package_cli_group_is_removed() -> None:
    assert "data-package" not in cli.commands


def test_datapackage_promote_module_is_removed() -> None:
    assert importlib.util.find_spec("science_tool.datapackage_promote") is None
