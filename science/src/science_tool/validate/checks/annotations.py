r"""Validation check for annotation drift.

Ported from `data/validate.sh`:

```bash
# ─── 19. Annotation drift ────────────────────────────────────────
echo ""
echo "Checking annotation drift..."

if [ -z "${SCIENCE_TOOL:-}" ]; then
    info "annotation drift skipped: SCIENCE_TOOL not available"
else
    # `science annotate verify` exits 1 when broken/parse-error issues
    # exist; capture stdout with `|| true` (Section 6 pattern) so a
    # nonzero exit doesn't truncate the assignment, then fall back to
    # an empty-summary stub only when stdout was empty (binary missing,
    # crash before output, etc.).
    annotate_json=$($SCIENCE_TOOL annotate verify --root . --format json --summary-only 2>/dev/null) || true
    if [ -z "$annotate_json" ]; then
        annotate_json='{"summary":{"broken":0,"degraded":0,"fuzzy":0,"source_missing":0,"parse_errors":0,"sidecars":0,"annotations":0,"superseded_skipped":0}}'
    fi

    # Extract counts via python3 (matches Section 6/18 pattern).
    annotate_counts=$(python3 -c "
import json, sys
data = json.loads(sys.stdin.read())
s = data.get('summary', {})
print(f\"{s.get('broken', 0)} {s.get('degraded', 0)} {s.get('fuzzy', 0)} {s.get('source_missing', 0)} {s.get('parse_errors', 0)} {s.get('sidecars', 0)} {s.get('annotations', 0)}\")
" <<< "$annotate_json")
    read -r ANNOT_BROKEN ANNOT_DEGRADED ANNOT_FUZZY ANNOT_SRC_MISSING ANNOT_PARSE ANNOT_SIDECARS ANNOT_TOTAL <<< "$annotate_counts"

    if [ "$ANNOT_SIDECARS" = "0" ]; then
        info "no annotation sidecars (*.anno.trig) in this project"
    else
        if [ "$ANNOT_BROKEN" -gt 0 ]; then
            warn "${ANNOT_BROKEN} annotation(s) with broken selectors (run \`science annotate verify --apply --actor <you>\` to mark superseded)"
        fi
        if [ "$ANNOT_PARSE" -gt 0 ]; then
            warn "${ANNOT_PARSE} sidecar parse error(s)"
        fi
        if [ "$ANNOT_DEGRADED" -gt 0 ]; then
            strict_warn "${ANNOT_DEGRADED} annotation(s) with degraded selectors (anchors no longer match)"
        fi
        if [ "$ANNOT_FUZZY" -gt 0 ]; then
            strict_warn "${ANNOT_FUZZY} annotation(s) resolved via fuzzy match"
        fi
        if [ "$ANNOT_SRC_MISSING" -gt 0 ]; then
            strict_warn "${ANNOT_SRC_MISSING} annotation(s) point at missing source files"
        fi
        if [ "$ANNOT_BROKEN" = "0" ] && [ "$ANNOT_PARSE" = "0" ] && [ "$ANNOT_DEGRADED" = "0" ] && [ "$ANNOT_FUZZY" = "0" ] && [ "$ANNOT_SRC_MISSING" = "0" ]; then
            info "${ANNOT_TOTAL} annotation(s) across ${ANNOT_SIDECARS} sidecar(s); all selectors clean"
        fi
    fi
fi
```
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from science_tool.annotation.verify import verify_path
from science_tool.validate.checks import Check
from science_tool.validate.result import Result, Severity

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


def _result(severity: Severity, message: str) -> Result:
    return Result(severity, None, None, message, "annotations", None)


@Check(section="annotation drift...", order=22)
def check_annotations(ctx: "ValidateContext") -> Iterable[Result]:
    report = verify_path(ctx.project_root)

    if report.sidecars == 0:
        return [_result(Severity.INFO, "no annotation sidecars (*.anno.trig) in this project")]

    results: list[Result] = []
    if report.broken > 0:
        results.append(
            _result(
                Severity.WARN,
                f"{report.broken} annotation(s) with broken selectors "
                "(run `science annotate verify --apply --actor <you>` to mark superseded)",
            )
        )
    if report.parse_errors > 0:
        results.append(_result(Severity.WARN, f"{report.parse_errors} sidecar parse error(s)"))

    if ctx.strict:
        if report.degraded > 0:
            results.append(
                _result(
                    Severity.WARN,
                    f"{report.degraded} annotation(s) with degraded selectors (anchors no longer match)",
                )
            )
        if report.fuzzy > 0:
            results.append(_result(Severity.WARN, f"{report.fuzzy} annotation(s) resolved via fuzzy match"))
        if report.source_missing > 0:
            results.append(
                _result(Severity.WARN, f"{report.source_missing} annotation(s) point at missing source files")
            )

    if (
        report.broken == 0
        and report.parse_errors == 0
        and report.degraded == 0
        and report.fuzzy == 0
        and report.source_missing == 0
    ):
        results.append(
            _result(
                Severity.INFO,
                f"{report.annotations} annotation(s) across {report.sidecars} sidecar(s); all selectors clean",
            )
        )

    return results
