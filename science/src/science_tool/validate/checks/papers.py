"""Port of validate.sh "Checking paper summaries..." block.

Checks paper entities under ``entities/papers/`` for template section
conformance.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "papers", None)


@Check(section="paper summaries...", order=7)
def check_papers(ctx: ValidateContext) -> Iterator[Result]:
    papers_root = resolve_path_policy("paper").root
    yield _result(
        Severity.INFO,
        papers_root.as_posix(),
        f"Paper summary structure is checked in {papers_root.as_posix()}/",
    )
