"""Python migration step adapter: import-and-dispatch."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from science_tool.project_artifacts.registry_schema import MigrationStep, PythonImpl


class PythonStepAdapter:
    """Wraps a MigrationStep whose impl is `kind: python`."""

    def __init__(self, step: MigrationStep) -> None:
        if not isinstance(step.impl, PythonImpl):
            raise TypeError(f"PythonStepAdapter requires PythonImpl, got {type(step.impl).__name__}")
        self.step = step
        self._module = importlib.import_module(step.impl.module)

    def check(self, project_root: Path) -> bool:
        return bool(self._module.check(project_root))

    def apply(self, project_root: Path) -> Any:
        return self._module.apply(project_root)

    def unapply(self, project_root: Path, applied: Any) -> None:
        if not self.step.reversible:
            raise RuntimeError(f"step {self.step.id!r} is not reversible")
        unapply_fn = getattr(self._module, "unapply", None)
        if unapply_fn is None:
            raise RuntimeError(f"step {self.step.id!r} declared reversible but module has no unapply()")
        unapply_fn(project_root, applied)
