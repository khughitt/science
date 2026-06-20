"""Port of validate.sh "Checking research gap analysis..." block.

# ─── 9. Research gap analysis conformance ────────────────────────
echo ""
echo "Checking research gap analysis..."

for f in "$DOC_DIR/meta/next-steps-"*.md; do
    [ -f "$f" ] || continue
    for section in "Recent Progress" "Current State" "Coverage Gaps" "Recommended Next Actions"; do
        if ! grep -q "## $section" "$f"; then
            warn "Next-steps $f missing section: $section"
        fi
    done

    # Chain link resolution. Accept entity-id (meta:next-steps-YYYY-MM-DD)
    # or relative path (doc/meta/next-steps-YYYY-MM-DD.md). Absence is fine.
    # We deliberately do NOT parse `prior_analyses:` (block- or inline-list);
    # protein-landscape's variant is accepted by silence — broken-link
    # resolution for that field is a future cycle.
    prior_value=$(sed -n "s/^prior:[[:space:]]*['\"]\\{0,1\\}\\([^'\"]*\\)['\"]\\{0,1\\}[[:space:]]*$/\\1/p" "$f" | head -n 1 || true)
    if [ -n "$prior_value" ]; then
        candidate_path=""
        case "$prior_value" in
            meta:next-steps-*) candidate_path="$DOC_DIR/meta/${prior_value#meta:}.md" ;;
            *.md) candidate_path="$prior_value" ;;
            *) candidate_path="$prior_value" ;;
        esac
        if [ ! -f "$candidate_path" ]; then
            warn "${f}: broken prior link '${prior_value}' (resolved to ${candidate_path})"
        fi
    fi
done

if ! ls "$DOC_DIR/meta/next-steps-"*.md 1>/dev/null 2>&1; then
    info "No next-steps analysis found ($DOC_DIR/meta/next-steps-*.md)"
fi
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_REQUIRED_SECTIONS = (
    "Recent Progress",
    "Current State",
    "Coverage Gaps",
    "Recommended Next Actions",
)
_PRIOR_RE = re.compile(r"^prior:[ \t]*['\"]?([^'\"]*?)['\"]?[ \t]*$")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "gap_analysis", None)


@Check(section="research gap analysis...", order=9)
def check_gap_analysis(ctx: ValidateContext) -> Iterator[Result]:
    paths = [path for path in sorted((ctx.doc_dir / "meta").glob("next-steps-*.md")) if path.is_file()]
    if not paths:
        yield _result(Severity.INFO, None, "No next-steps analysis found (doc/meta/next-steps-*.md)")
        return

    for path in paths:
        yield from _check_next_steps_file(ctx, path)


def _check_next_steps_file(ctx: ValidateContext, path: Path) -> Iterator[Result]:
    relative = path.relative_to(ctx.project_root).as_posix()
    text = ctx.read_text_cached(path)

    for section in _REQUIRED_SECTIONS:
        if f"## {section}" not in text:
            yield _result(Severity.WARN, relative, f"Next-steps {relative} missing section: {section}")

    prior_value = _prior_value(text)
    if prior_value is None or prior_value == "":
        return

    candidate_path, candidate_path_string = _resolve_prior(ctx, prior_value)
    if not candidate_path.is_file():
        yield _result(
            Severity.WARN,
            relative,
            f"{relative}: broken prior link '{prior_value}' (resolved to {candidate_path_string})",
        )


def _prior_value(text: str) -> str | None:
    for line in text.splitlines():
        match = _PRIOR_RE.match(line)
        if match is not None:
            return match.group(1)
    return None


def _resolve_prior(ctx: ValidateContext, prior_value: str) -> tuple[Path, str]:
    if prior_value.startswith("meta:next-steps-"):
        candidate_path_string = f"doc/meta/{prior_value.removeprefix('meta:')}.md"
        return ctx.project_root / candidate_path_string, candidate_path_string

    candidate = Path(prior_value)
    if candidate.is_absolute():
        return candidate, prior_value

    return ctx.project_root / candidate, prior_value
