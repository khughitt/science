"""Port of validate.sh pre-registration document block.

for f in "$DOC_DIR/meta/pre-registration-"*.md "$DOC_DIR/pre-registrations/"*.md; do
    # require sections, then require committed/spec when type is pre-registration
done
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_SECTIONS = ("Hypotheses Under Test", "Expected Outcomes", "Decision Criteria", "Null Result Plan")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "prereg", None)


@Check(section="discussion documents...", order=12)
def check_prereg(ctx: ValidateContext) -> Iterator[Result]:
    entities_root = ctx.project_root / resolve_path_policy("pre-registration").root
    paths = sorted(entities_root.glob("*.md")) if entities_root.is_dir() else []
    for path in paths:
        if not path.is_file():
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        text = ctx.read_text_cached(path)
        for section in _SECTIONS:
            if f"## {section}" not in text:
                yield _result(Severity.WARN, relative, f"Pre-registration {relative} missing section: {section}")

        # Keyed on `kind`, which is what the template writes. This read `type:`
        # until 2026-07-20, so the two checks below had never fired: all 27
        # pre-registrations in the corpus declare `kind:` and none declare `type:`.
        frontmatter = ctx.frontmatter(path)
        if str(frontmatter.get("kind", "")) != "pre-registration":
            continue

        if "committed" not in frontmatter:
            yield _result(
                Severity.WARN,
                relative,
                f"{relative} kind 'pre-registration' should declare a 'committed:' date in frontmatter",
            )
        if "spec" not in frontmatter:
            yield _result(
                Severity.WARN,
                relative,
                f"{relative} kind 'pre-registration' should declare a 'spec:' field (empty string is OK if no paired design doc)",
            )
