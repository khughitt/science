r"""Validation check for reference integrity.

Ported from `data/validate.sh`:

```bash
echo "Checking reference integrity..."

if [ -n "${SCIENCE_TOOL:-}" ]; then
    # `science refs check` exits 1 when broken refs exist; capture stdout
    # regardless of exit code, then fall back only if invocation produced
    # no output (binary missing, project not loadable, etc.).
    refs_json=$($SCIENCE_TOOL refs check --root . --format json 2>/dev/null) || true
    if [ -z "$refs_json" ]; then
        refs_json='{"summary":{"broken":0,"by_type":{}},"broken":[],"markers":[]}'
    fi
    while IFS=$'\t' read -r ref_type count; do
        [ -z "$ref_type" ] && continue
        if [ "$count" -gt 0 ]; then
            warn "${count} broken refs: ${ref_type}"
        fi
    done < <(printf '%s' "$refs_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
by_type = data.get("summary", {}).get("by_type", {})
for ref_type, count in sorted(by_type.items()):
    print(f"{ref_type}\t{count}")
')
    total=$(printf '%s' "$refs_json" | python3 -c 'import json, sys; print(json.load(sys.stdin).get("summary", {}).get("broken", 0))')
    if [ "$total" -eq 0 ]; then
        info "Reference integrity check complete (no broken refs)"
    fi
elif [ -f "$PAPERS_DIR/references.bib" ] && [ -d "$DOC_DIR" ]; then
    # Fallback when SCIENCE_TOOL is unavailable: minimal bash bibtex check.
    cited_keys=$(grep -roh '\[@[A-Za-z0-9_-]*\]' "$DOC_DIR/" 2>/dev/null \
        | sed 's/\[@//;s/\]//' | sort -u || true)
    for key in $cited_keys; do
        [ -z "$key" ] && continue
        if ! grep -q "@.*{${key}," "$PAPERS_DIR/references.bib" 2>/dev/null; then
            warn "Citation [@${key}] used in docs but not found in $PAPERS_DIR/references.bib"
        fi
    done
fi
```
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING

from science_tool.refs import check_refs
from science_tool.validate.checks import Check
from science_tool.validate.result import Result, Severity

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


def _result(severity: Severity, message: str) -> Result:
    return Result(severity, None, None, message, "references", None)


@Check(section="reference integrity...", order=7)
def check_references(ctx: "ValidateContext") -> Iterable[Result]:
    broken = [issue for issue in check_refs(ctx.project_root) if issue.ref_type != "marker"]
    if not broken:
        return [_result(Severity.INFO, "Reference integrity check complete (no broken refs)")]

    by_type = Counter(issue.ref_type for issue in broken)
    return [_result(Severity.WARN, f"{count} broken refs: {ref_type}") for ref_type, count in sorted(by_type.items())]
