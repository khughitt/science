from __future__ import annotations

import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_hatch_wheel_uses_package_tree_without_forced_includes() -> None:
    pyproject = tomllib.loads(REPO_ROOT.joinpath("pyproject.toml").read_text(encoding="utf-8"))

    assert pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/science_tool"]
    assert "force-include" not in pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]
