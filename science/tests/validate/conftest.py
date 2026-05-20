from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import shutil

import pytest


@pytest.fixture
def isolated_copy(tmp_path: Path) -> Callable[[Path], Path]:
    def copy_project(project_path: Path) -> Path:
        destination = tmp_path / project_path.name

        def ignore_sidecars(_directory: str, names: list[str]) -> set[str]:
            return {name for name in names if name in {"validate.local.sh", "validate_local.py"}}

        return shutil.copytree(project_path, destination, ignore=ignore_sidecars)

    return copy_project
