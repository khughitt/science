"""Port of validate.sh "Checking paper summaries..." block.

# ─── 7. Paper summary template conformance ───────────────────────
echo ""
echo "Checking paper summaries..."
info "Paper summary structure is checked in $DOC_DIR/background/papers/"
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "papers", None)


@Check(section="paper summaries...", order=7)
def check_papers(ctx: ValidateContext) -> Iterator[Result]:
    yield _result(
        Severity.INFO,
        "doc/background/papers",
        "Paper summary structure is checked in doc/background/papers/",
    )
