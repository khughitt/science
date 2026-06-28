"""Validation check for prose quality lints.

Ported from `data/validate.sh`:

```bash
# ─── 18. Prose lints ──────────────────────────────────────────────
echo ""
echo "Checking prose quality lints..."

if [ -n "${SCIENCE_TOOL:-}" ] && [ -d "$DOC_DIR" ]; then
    SCIENCE_PROSE_FLAGS=()
    if [ "$STRICT" -eq 1 ]; then
        SCIENCE_PROSE_FLAGS+=("--strict")
    fi
    prose_json=$($SCIENCE_TOOL prose lint --root . --format json "${SCIENCE_PROSE_FLAGS[@]}" 2>/dev/null || echo '{"counts":{},"hits":[]}')
    while IFS=$'\t' read -r check count severity; do
        [ -z "$check" ] && continue
        if [ "$severity" = "warn" ] && [ "$count" -gt 0 ]; then
            warn "${count} prose lint issue(s): ${check}"
        elif [ "$count" -gt 0 ]; then
            info "${count} prose lint issue(s): ${check} (use --strict to promote)"
        fi
    done < <(printf '%s' "$prose_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
sev = {}
for h in data.get("hits", []):
    sev.setdefault(h["check"], h["severity"])
for check, count in sorted(data.get("counts", {}).items()):
    s = sev.get(check, "warn")
    print(f"{check}\t{count}\t{s}")
')
fi
```
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from science_tool.bibliography import load_bib_author_surnames
from science_tool.project_config import DEFAULT_ANCHOR_PATTERNS, load_project_config
from science_tool.prose_lint import CHECKS, LintIssue, build_short_form_resolver, scan_root
from science_tool.validate.checks import Check
from science_tool.validate.result import Result, Severity

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


def _result(
    severity: Severity,
    message: str,
    *,
    path: Path | None = None,
    line: int | None = None,
    rule: str = "prose_lints",
) -> Result:
    return Result(severity, path, line, message, rule, None)


@Check(section="prose quality lints...", order=21)
def check_prose_lints(ctx: "ValidateContext") -> Iterable[Result]:
    if not ctx.doc_dir.is_dir():
        return []

    configured_checks: list[str] | None = None
    selected: list[str] | None = None
    anchor_patterns = list(DEFAULT_ANCHOR_PATTERNS)
    short_form_ids_deny: list[str] = []
    bare_author_year_deny: list[str] = []
    if (ctx.project_root / "science.yaml").is_file():
        config = load_project_config(ctx.project_root)
        if config.prose_lint is not None:
            anchor_patterns = config.prose_lint.anchor_patterns
            configured_checks = config.prose_lint.enabled_checks
            if not ctx.include_all_checks:
                selected = configured_checks
            short_form_ids_deny = config.prose_lint.short_form_ids_deny
            bare_author_year_deny = config.prose_lint.bare_author_year_deny

    effective_checks = selected if selected is not None else list(CHECKS)
    resolver = (
        build_short_form_resolver(ctx.project_root)
        if "short-form-ids" in effective_checks
        else None
    )
    bib_surnames = (
        load_bib_author_surnames(ctx.project_root)
        if "bare-author-year" in effective_checks
        else None
    )

    lint_result = scan_root(
        ctx.project_root,
        checks=selected,
        strict=ctx.strict,
        anchor_patterns=anchor_patterns,
        short_form_ids_deny=short_form_ids_deny,
        resolver=resolver,
        bare_author_year_deny=bare_author_year_deny,
        bib_surnames=bib_surnames,
    )

    severity_by_check: dict[str, str] = {}
    for hit in lint_result.get("hits", []):
        severity_by_check.setdefault(hit.check, hit.severity)

    results: list[Result] = []
    if configured_checks is not None and set(configured_checks) != set(CHECKS):
        results.append(_configured_checks_result(configured_checks, include_all_checks=ctx.include_all_checks))
    for hit in sorted(lint_result.get("hits", []), key=lambda item: (item.file, item.line, item.col, item.check)):
        if hit.severity != "warn":
            continue
        results.append(_hit_result(ctx, hit))
    for check, count in sorted(lint_result.get("counts", {}).items()):
        if count <= 0:
            continue
        if severity_by_check.get(check, "warn") != "warn":
            results.append(
                _result(
                    Severity.INFO,
                    f"{count} prose lint issue(s): {check} (use --strict to promote)",
                    rule=f"prose_lints.{check}",
                )
            )
    return results


def _configured_checks_result(selected: list[str], *, include_all_checks: bool) -> Result:
    disabled = [check for check in CHECKS if check not in selected]
    enabled = ", ".join(selected)
    if include_all_checks:
        message = (
            f"prose lint checks limited by science.yaml but --all is active; "
            f"running all {len(CHECKS)} checks (science.yaml enabled: {enabled})"
        )
        return _result(Severity.INFO, message, rule="prose_lints.config")
    disabled_text = ", ".join(disabled)
    message = (
        f"prose lint checks limited by science.yaml: {len(selected)}/{len(CHECKS)} enabled "
        f"({enabled}); disabled: {disabled_text}"
    )
    return _result(Severity.INFO, message, rule="prose_lints.config")


def _hit_result(ctx: "ValidateContext", hit: LintIssue) -> Result:
    return _result(
        Severity.WARN,
        hit.message,
        path=_relative_path(ctx, hit.file),
        line=hit.line,
        rule=f"prose_lints.{hit.check}",
    )


def _relative_path(ctx: "ValidateContext", path: Path) -> Path:
    try:
        return path.resolve().relative_to(ctx.project_root.resolve())
    except (OSError, ValueError):
        return path
