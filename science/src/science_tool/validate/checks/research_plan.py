"""Port of validate.sh "Checking research plan conventions..." block.

if [ -f "RESEARCH_PLAN.md" ]; then
    info "RESEARCH_PLAN.md exists"
    # warn for legacy task-queue sections
elif [ "$PROFILE" = "research" ]; then
    info "No RESEARCH_PLAN.md — high-level planning may be in README.md or $DOC_DIR/plans/"
fi
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.paths import resolve_paths
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_LEGACY_SECTIONS = ("## Current Priorities", "## Next Review Trigger")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "research_plan", None)


@Check(section="research plan conventions...", order=10)
def check_research_plan(ctx: ValidateContext) -> Iterator[Result]:
    plan_path = ctx.project_root / "RESEARCH_PLAN.md"
    readme_path = ctx.project_root / "README.md"
    if plan_path.is_file():
        yield _result(Severity.INFO, "RESEARCH_PLAN.md", "RESEARCH_PLAN.md exists")
        text = ctx.read_text_cached(plan_path)
        for section in _LEGACY_SECTIONS:
            if section in text:
                yield _result(
                    Severity.WARN,
                    "RESEARCH_PLAN.md",
                    f"RESEARCH_PLAN.md contains legacy task-queue section '{section}' — migrate tasks to tasks/active.md via /science:tasks",
                )
        return

    if resolve_paths(ctx.project_root).profile == "research":
        if readme_path.is_file():
            yield _result(Severity.INFO, "README.md", "README.md exists; RESEARCH_PLAN.md not required")
            return
        yield _result(
            Severity.INFO,
            None,
            "No RESEARCH_PLAN.md — high-level planning may be in README.md or doc/plans/",
        )
