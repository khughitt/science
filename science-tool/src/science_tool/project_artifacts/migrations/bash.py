"""Bash migration step runner with declared working_dir + timeout."""

from __future__ import annotations

import subprocess
from pathlib import Path

from science_tool.project_artifacts.registry_schema import BashImpl, MigrationStep


class BashStepAdapter:
    """Wraps a MigrationStep whose impl is `kind: bash`."""

    def __init__(self, step: MigrationStep) -> None:
        if not isinstance(step.impl, BashImpl):
            raise TypeError(f"BashStepAdapter requires BashImpl, got {type(step.impl).__name__}")
        self.step = step

    def _run(self, body: str, project_root: Path) -> subprocess.CompletedProcess[str]:
        impl = self.step.impl
        assert isinstance(impl, BashImpl)
        cwd = (project_root / impl.working_dir).resolve()
        return subprocess.run(
            [impl.shell, "-c", body],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=impl.timeout_seconds,
            check=False,
        )

    def check(self, project_root: Path) -> bool:
        impl = self.step.impl
        assert isinstance(impl, BashImpl)
        result = self._run(impl.check, project_root)
        return result.returncode == 0

    def apply(self, project_root: Path) -> dict:
        impl = self.step.impl
        assert isinstance(impl, BashImpl)
        result = self._run(impl.apply, project_root)
        if result.returncode != 0:
            raise RuntimeError(
                f"bash apply for step {self.step.id!r} exited {result.returncode}\nstderr: {result.stderr}"
            )
        return {"stdout": result.stdout, "stderr": result.stderr}

    def unapply(self, project_root: Path, applied: dict) -> None:
        raise RuntimeError(f"bash step {self.step.id!r} cannot be unapplied (Python steps only)")
