"""Port of validate.sh hypothesis comparison document block.

for f in "$DOC_DIR/discussions/comparison-"*.md; do
    # require comparison sections
done
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_SECTIONS = ("Hypotheses Compared", "Evidence Inventory", "Discriminating Predictions", "Current Verdict")
_COMPARISON_MARKER = f"## {_SECTIONS[0]}"


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "hypothesis_comparisons", None)


def _check_comparison_sections(ctx: ValidateContext, path: Path) -> Iterator[Result]:
    """Emit a warning for each required section missing from a comparison doc."""
    relative = path.relative_to(ctx.project_root).as_posix()
    text = ctx.read_text_cached(path)
    for section in _SECTIONS:
        if f"## {section}" not in text:
            yield _result(Severity.WARN, relative, f"Comparison {relative} missing section: {section}")


@Check(section="discussion documents...", order=13)
def check_hypothesis_comparisons(ctx: ValidateContext) -> Iterator[Result]:
    # entities/discussions/*.md — identified by the '## Hypotheses Compared' marker,
    # because filenames are NNNN-slug.md (no 'comparison-' prefix).
    entities_discussions = ctx.project_root / resolve_path_policy("discussion").root
    if entities_discussions.is_dir():
        for path in sorted(entities_discussions.glob("*.md")):
            if not path.is_file():
                continue
            text = ctx.read_text_cached(path)
            if _COMPARISON_MARKER in text:
                yield from _check_comparison_sections(ctx, path)
