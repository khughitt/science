"""Port of validate.sh discussion document and synthesis frontmatter blocks.

Checks discussion files under both ``entities/discussions/`` (new layout) and
the legacy ``$DOC_DIR/discussions/`` root, skipping comparison-* files and
requiring discussion sections; double-blind mode requires addendum sections.

Checks synthesis frontmatter under ``entities/synthesis/``, validating
report_kind and related fields for files with ``kind: synthesis``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_REQUIRED_SECTIONS = (
    "## Focus",
    "## Current Position",
    "## Critical Analysis",
    "## Evidence Needed",
    "## Prioritized Follow-Ups",
    "## Synthesis",
)
_DOUBLE_BLIND_SECTIONS = (
    "## Double-Blind Addendum (If mode = double-blind)",
    "### Agent Independent Draft",
    "### User Independent Draft",
    "### Comparison",
    "### Combined Synthesis",
)
_VALID_SYNTHESIS_KINDS = {
    "hypothesis-synthesis",
    "synthesis-rollup",
    "emergent-threads",
    "cluster-digest",
    "paper-batch-synthesis",
}
_DOUBLE_BLIND_RE = re.compile(r'^mode:\s*"?double-blind"?', re.MULTILINE)
_RAW_FIELD_RE = re.compile(r"^{field}:\s*['\"]?([^'\"\n]*)['\"]?\s*$", re.MULTILINE)


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "discussions", None)


@Check(section="discussion documents...", order=11)
def check_discussions(ctx: ValidateContext) -> Iterator[Result]:
    roots = (ctx.project_root / "entities" / "discussions",)
    for discussions_dir in roots:
        if not discussions_dir.is_dir():
            continue
        for path in sorted(discussions_dir.glob("*.md")):
            if path.is_file():
                relative = path.relative_to(ctx.project_root).as_posix()
                if path.name.startswith("comparison-"):
                    continue
                yield from _check_discussion(ctx, path, relative)

    yield from _check_synthesis_frontmatter(ctx)


def _check_discussion(ctx: ValidateContext, path: Path, relative: str) -> Iterator[Result]:
    text = ctx.read_text_cached(path)
    yield _result(Severity.INFO, relative, f"Checking {relative}...")

    for section in _REQUIRED_SECTIONS:
        if section not in text:
            yield _result(Severity.WARN, relative, f"{relative} missing section: {section}")

    if _DOUBLE_BLIND_RE.search(text) is None:
        return

    for section in _DOUBLE_BLIND_SECTIONS:
        if section not in text:
            yield _result(Severity.WARN, relative, f"{relative} double-blind mode missing section: {section}")


def _check_synthesis_frontmatter(ctx: ValidateContext) -> Iterator[Result]:
    synth_roots = (ctx.project_root / "entities" / "synthesis",)
    candidates = [p for root in synth_roots if root.is_dir() for p in sorted(root.glob("*.md"))]
    for path in candidates:
        if not path.is_file():
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        text = ctx.read_text_cached(path)
        parsed_kind = _raw_field_value(text, "kind")
        if parsed_kind != "synthesis":
            continue

        parsed_report_kind = _raw_field_value(text, "report_kind")
        if parsed_report_kind in _VALID_SYNTHESIS_KINDS:
            pass
        elif parsed_report_kind == "":
            yield _result(Severity.WARN, relative, f"{relative}: missing report_kind")
        else:
            yield _result(Severity.WARN, relative, f"{relative}: invalid report_kind '{parsed_report_kind}'")

        if not _has_raw_key(text, "source_commit"):
            yield _result(Severity.WARN, relative, f"{relative}: missing source_commit")

        if parsed_report_kind == "synthesis-rollup":
            if not _has_raw_key(text, "synthesized_from"):
                yield _result(Severity.WARN, relative, f"{relative}: missing synthesized_from")
        elif parsed_report_kind == "hypothesis-synthesis":
            if not _has_raw_key(text, "hypothesis"):
                yield _result(Severity.WARN, relative, f"{relative}: missing hypothesis")
            if not _has_raw_key(text, "provenance_coverage"):
                yield _result(Severity.WARN, relative, f"{relative}: missing provenance_coverage")
        elif parsed_report_kind == "emergent-threads":
            if not _has_raw_key(text, "orphan_question_count"):
                yield _result(Severity.WARN, relative, f"{relative}: missing orphan_question_count")
            if not _has_raw_key(text, "orphan_interpretation_count"):
                yield _result(Severity.WARN, relative, f"{relative}: missing orphan_interpretation_count")
            if not _has_raw_key(text, "orphan_ids"):
                yield _result(Severity.WARN, relative, f"{relative}: missing orphan_ids")


def _raw_field_value(text: str, field: str) -> str:
    match = re.search(_RAW_FIELD_RE.pattern.format(field=re.escape(field)), text, re.MULTILINE)
    if match is None:
        return ""
    return match.group(1)


def _has_raw_key(text: str, key: str) -> bool:
    return re.search(rf"^{re.escape(key)}:", text, re.MULTILINE) is not None
