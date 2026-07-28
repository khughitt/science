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
from pathlib import Path
from typing import TYPE_CHECKING

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.markers import scan_markers
from science_tool.markers_lifted import filter_lifted
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.result import Severity

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


SECTION, RULES = declare_validation_rules(
    section_id="unresolved-markers",
    section_title="unresolved markers",
    section_order=111,
    rule_ids=("unresolved-markers.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(token: str, message: str) -> CheckObservation:
    return validation_observation(
        severity=Severity.WARN,
        path=None,
        line=None,
        message=message,
        rule=RULES["unresolved-markers.check"],
        task=None,
        qualifiers={"key": ["token", token]},
    )


@Check(section=SECTION, order=8, producer_id="validate.unresolved-markers", rules=tuple(RULES.values()))
def check_unresolved_markers(ctx: "ValidateContext") -> Iterable[CheckObservation]:
    if not ctx.doc_dir.is_dir():
        return []

    filtered_hits = filter_lifted(scan_markers(ctx.project_root, strict=ctx.strict, include_documentation=False))

    counts = Counter(hit.token for hit in filtered_hits)
    severity_by_token: dict[str, str] = {}
    for hit in filtered_hits:
        severity_by_token.setdefault(hit.token, hit.severity)

    results: list[CheckObservation] = []
    for token, count in sorted(counts.items()):
        if count > 0 and severity_by_token.get(token, "warn") == "warn":
            examples = _marker_examples(ctx.project_root, [hit for hit in filtered_hits if hit.token == token])
            results.append(
                _result(
                    token,
                    f"{count} [{token}] marker(s) found in documents; examples: {examples}",
                )
            )
    return results


def _marker_examples(project_root: Path, hits: list, *, limit: int = 5) -> str:
    examples: list[str] = []
    for hit in sorted(hits, key=lambda item: (item.file, item.line)):
        try:
            path = hit.file.resolve().relative_to(project_root.resolve())
        except (OSError, ValueError):
            path = hit.file
        examples.append(f"{path.as_posix()}:{hit.line}")
        if len(examples) == limit:
            break
    if len(hits) > limit:
        examples.append("...")
    return ", ".join(examples)
