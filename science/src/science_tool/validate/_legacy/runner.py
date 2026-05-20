from __future__ import annotations

import os
from importlib import resources
from pathlib import Path
import subprocess
from typing import Literal

from science_tool.validate import legacy_parser
from science_tool.validate.result import Result, Severity

_MAX_STDERR_CHARS = 2000
LegacyDispatchPhase = Literal["pre_validation", "extra_checks", "both"]


def run_legacy_sidecar(
    project_root: Path,
    *,
    phase: LegacyDispatchPhase | None = None,
    count_post_validation: bool = True,
) -> tuple[list[Result], list[str]]:
    script = resources.files("science_tool.validate._legacy") / "validate_legacy.sh"
    env = {
        **os.environ,
        "SCIENCE_LEGACY_SIDECAR_ONLY": "1",
        "SCIENCE_VALIDATE_NO_COLOR": "1",
    }
    if phase is not None:
        env["SCIENCE_LEGACY_DISPATCH_PHASE"] = phase
    if not count_post_validation:
        env["SCIENCE_LEGACY_COUNT_POST_VALIDATION"] = "0"
    with resources.as_file(script) as script_path:
        completed = subprocess.run(
            ["bash", str(script_path)],
            cwd=project_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    results, log_lines = legacy_parser.parse(completed.stdout, project_root=project_root)
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        if len(stderr) > _MAX_STDERR_CHARS:
            stderr = f"{stderr[:_MAX_STDERR_CHARS]}..."
        message = f"legacy sidecar exited with code {completed.returncode}"
        if stderr:
            message = f"{message}: {stderr}"
        results.append(Result(Severity.ERROR, None, None, message, None, None))
    return results, log_lines
