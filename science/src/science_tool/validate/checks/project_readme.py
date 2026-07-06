"""Project README convention checks."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_LEGACY_SECTIONS = ("## Current Priorities", "## Next Review Trigger")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "project_readme", None)


@Check(section="project README conventions...", order=10)
def check_project_readme(ctx: ValidateContext) -> Iterator[Result]:
    readme_path = ctx.project_root / "README.md"
    if readme_path.is_file():
        yield _result(Severity.INFO, "README.md", "README.md exists")
        text = ctx.read_text_cached(readme_path)
        for section in _LEGACY_SECTIONS:
            if section in text:
                yield _result(
                    Severity.WARN,
                    "README.md",
                    f"README.md contains legacy task-queue section '{section}' — migrate tasks to tasks/active.md via /science:tasks",
                )
        return

    yield _result(
        Severity.INFO,
        "README.md",
        "README.md not found; use README.md for high-level project context and strategy",
    )
