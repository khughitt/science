"""Port of validate.sh bias audit document block.

for f in "$DOC_DIR/meta/bias-audit-"*.md; do
    # require bias audit sections
done
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_SECTIONS = ("Cognitive Biases", "Methodological Biases", "Summary")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "bias_audits", None)


@Check(section="discussion documents...", order=14)
def check_bias_audits(ctx: ValidateContext) -> Iterator[Result]:
    for path in sorted((ctx.doc_dir / "meta").glob("bias-audit-*.md")):
        if not path.is_file():
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        text = ctx.read_text_cached(path)
        for section in _SECTIONS:
            if f"## {section}" not in text:
                yield _result(Severity.WARN, relative, f"Bias audit {relative} missing section: {section}")
