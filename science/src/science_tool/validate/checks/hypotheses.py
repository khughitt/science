"""Port of validate.sh "Checking hypotheses..." and review horizon blocks.

Checks direct "$SPECS_DIR/hypotheses/"h*.md hypothesis files for
Falsifiability, Status, and phase shape, then scans "$DOC_DIR" and
"$SPECS_DIR" markdown frontmatter for non-positive review horizons.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import re
from typing import Any

import yaml

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_PHASE_RE = re.compile(r"^phase:\s*['\"]?([^'\"\s#]*)['\"]?\s*(?:#.*)?$")
_STATUS_RE = re.compile(r"^status:")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "hypotheses", None)


@Check(section="hypotheses...", order=5)
def check_hypotheses(ctx: ValidateContext) -> Iterator[Result]:
    hypotheses_dir = ctx.specs_dir / "hypotheses"
    if hypotheses_dir.is_dir():
        for path in sorted(hypotheses_dir.glob("h*.md")):
            if path.is_file():
                yield from _check_hypothesis(ctx, path)

    yield from _check_review_horizon_days(ctx)


def _check_hypothesis(ctx: ValidateContext, path: Path) -> Iterator[Result]:
    relative = path.relative_to(ctx.project_root).as_posix()
    text = ctx.read_text_cached(path)
    lines = text.splitlines()

    yield _result(Severity.INFO, relative, f"Checking {relative}...")

    if not _has_falsifiability_heading(lines):
        yield _result(Severity.ERROR, relative, f"{relative} missing ## Falsifiability section")
    elif _is_falsifiability_empty(lines):
        yield _result(Severity.WARN, relative, f"{relative} has empty Falsifiability section")

    try:
        frontmatter = ctx.frontmatter(path)
    except yaml.YAMLError:
        frontmatter = {}
    if not _has_status(frontmatter, lines):
        yield _result(Severity.WARN, relative, f"{relative} missing Status field")

    phase = _phase_value(frontmatter, lines)
    if phase is not None and phase not in {"candidate", "active"}:
        yield _result(
            Severity.WARN,
            relative,
            f"{relative} has invalid phase '{phase}' (must be 'candidate' or 'active')",
        )


def _has_falsifiability_heading(lines: list[str]) -> bool:
    return any(line == "## Falsifiability" for line in _non_fenced_lines(lines))


def _is_falsifiability_empty(lines: list[str]) -> bool:
    in_section = False
    in_html_comment = False
    for line in _non_fenced_lines(lines):
        if not in_section:
            if line == "## Falsifiability":
                in_section = True
            continue

        if line.startswith("## "):
            return True
        stripped = line.strip()

        if in_html_comment:
            if "-->" in stripped:
                in_html_comment = False
            continue
        if stripped.startswith("<!--"):
            if "-->" not in stripped:
                in_html_comment = True
            continue
        if stripped == "" or stripped.startswith("#"):
            continue
        return False

    return True


def _non_fenced_lines(lines: list[str]) -> Iterator[str]:
    fence_char: str | None = None
    for line in lines:
        match = _FENCE_RE.match(line)
        if match is not None:
            marker = match.group(1)
            char = marker[0]
            if fence_char is None:
                fence_char = char
                continue
            if char == fence_char:
                fence_char = None
                continue
        if fence_char is not None:
            continue
        yield line


def _has_status(frontmatter: dict[str, Any], lines: list[str]) -> bool:
    return "status" in frontmatter or any(line.startswith("- **Status:**") or _STATUS_RE.match(line) for line in lines)


def _phase_value(frontmatter: dict[str, Any], lines: list[str]) -> str | None:
    phase = frontmatter.get("phase")
    if phase is not None:
        return str(phase)

    for line in lines:
        match = _PHASE_RE.match(line)
        if match is not None:
            return match.group(1)
    return None


def _check_review_horizon_days(ctx: ValidateContext) -> Iterator[Result]:
    for root in (ctx.doc_dir, ctx.specs_dir):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            if not path.is_file():
                continue
            try:
                frontmatter = ctx.frontmatter(path)
            except yaml.YAMLError:
                continue

            horizon = _review_horizon_days(frontmatter)
            if horizon is None or horizon > 0:
                continue

            relative = path.relative_to(ctx.project_root).as_posix()
            yield _result(
                Severity.WARN,
                relative,
                f"{relative}: review_state.review_horizon_days must be positive (got {horizon:g})",
            )


def _review_horizon_days(frontmatter: dict[str, Any]) -> float | None:
    review_state = frontmatter.get("review_state")
    if not isinstance(review_state, dict):
        return None

    value = review_state.get("review_horizon_days")
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None
