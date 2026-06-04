from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import shutil

import pytest

from _copy_filters import oversized_payload_names


@pytest.fixture
def isolated_copy(tmp_path: Path) -> Callable[[Path], Path]:
    copy_count = 0

    def copy_project(project_path: Path) -> Path:
        nonlocal copy_count
        copy_count += 1
        destination = tmp_path / f"{project_path.name}-{copy_count}"

        def ignore_sidecars(directory: str, names: list[str]) -> set[str]:
            sidecars = {name for name in names if name in {"validate.local.sh", "validate_local.py"}}
            return sidecars | oversized_payload_names(directory, names)

        return shutil.copytree(project_path, destination, ignore=ignore_sidecars)

    return copy_project
