"""Validation check for unresolved annotation markers.

Ported from `data/validate.sh`:

```bash
# ─── 8. Unresolved annotation markers ──────────────────────────────
echo ""
echo "Checking for unresolved markers..."

if command -v science >/dev/null 2>&1 && [ -d "$DOC_DIR" ]; then
    SCIENCE_MARKERS_FLAGS=(--ignore-lifted)
    if [ "$STRICT" -eq 1 ]; then
        SCIENCE_MARKERS_FLAGS+=("--strict")
    fi
    markers_json=$(science markers scan --root . --format json "${SCIENCE_MARKERS_FLAGS[@]}" 2>/dev/null || echo '{"counts":{},"hits":[]}')
    while IFS=$'\t' read -r token count severity; do
        [ -z "$token" ] && continue
        if [ "$severity" = "warn" ] && [ "$count" -gt 0 ]; then
            warn "${count} [${token}] marker(s) found in documents"
        fi
    done < <(printf '%s' "$markers_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
sev = {}
for h in data.get("hits", []):
    sev.setdefault(h["token"], h["severity"])
for token, count in sorted(data.get("counts", {}).items()):
    s = sev.get(token, "warn")
    print(f"{token}\t{count}\t{s}")
')
fi
```
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from typing import TYPE_CHECKING

from science_tool.markers import scan_markers
from science_tool.markers_cli import _filter_lifted
from science_tool.validate.checks import Check
from science_tool.validate.result import Result, Severity

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


def _result(message: str) -> Result:
    return Result(Severity.WARN, None, None, message, "unresolved_markers", None)


@Check(section="for unresolved markers...", order=8)
def check_unresolved_markers(ctx: "ValidateContext") -> Iterable[Result]:
    if not ctx.doc_dir.is_dir():
        return []

    filtered_hits = _filter_lifted(scan_markers(ctx.project_root, strict=ctx.strict, include_documentation=False))

    counts = Counter(hit.token for hit in filtered_hits)
    severity_by_token: dict[str, str] = {}
    for hit in filtered_hits:
        severity_by_token.setdefault(hit.token, hit.severity)

    results: list[Result] = []
    for token, count in sorted(counts.items()):
        if count > 0 and severity_by_token.get(token, "warn") == "warn":
            results.append(_result(f"{count} [{token}] marker(s) found in documents"))
    return results
