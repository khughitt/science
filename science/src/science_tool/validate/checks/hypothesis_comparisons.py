"""Port of validate.sh hypothesis comparison document block.

for f in "$DOC_DIR/discussions/comparison-"*.md; do
    # require comparison sections
done
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_SECTIONS = ("Hypotheses Compared", "Evidence Inventory", "Discriminating Predictions", "Current Verdict")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "hypothesis_comparisons", None)


@Check(section="discussion documents...", order=13)
def check_hypothesis_comparisons(ctx: ValidateContext) -> Iterator[Result]:
    for path in sorted((ctx.doc_dir / "discussions").glob("comparison-*.md")):
        if not path.is_file():
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        text = ctx.read_text_cached(path)
        for section in _SECTIONS:
            if f"## {section}" not in text:
                yield _result(Severity.WARN, relative, f"Comparison {relative} missing section: {section}")
