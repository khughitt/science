"""Port of validate.sh "Checking research scope..." block.

if [ "$PROFILE" = "research" ] && [ ! -f "$SPECS_DIR/research-question.md" ]; then
    error "$SPECS_DIR/research-question.md not found — every project needs a research question"
fi
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.paths import resolve_paths
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "research_scope", None)


@Check(section="research scope...", order=3)
def check_research_scope(ctx: ValidateContext) -> Iterator[Result]:
    if resolve_paths(ctx.project_root).profile != "research":
        return

    research_question = ctx.specs_dir / "research-question.md"
    if not research_question.is_file():
        yield _result(
            Severity.ERROR,
            "specs/research-question.md",
            "specs/research-question.md not found — every project needs a research question",
        )
