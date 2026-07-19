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
from science_tool.data_root import project_config_path
from science_tool.project_config import (
    DEFAULT_ANCHOR_PATTERNS,
    DEFAULT_PROVENANCE_FIELDS,
    DEFAULT_SPEC_CLASS_KINDS,
    ProseLintConfig,
    load_project_config,
)
from science_tool.prose_lint import (
    CHECKS,
    LintIssue,
    build_short_form_resolver,
    couple_checks,
    merge_anchor_patterns,
    scan_root,
)
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
    additional_anchor_patterns: list[str] = []
    spec_class_kinds = list(DEFAULT_SPEC_CLASS_KINDS)
    provenance_fields = list(DEFAULT_PROVENANCE_FIELDS)
    exclude_paths: list[str] = []
    short_form_ids_deny: list[str] = []
    bare_author_year_deny: list[str] = []
    prose_lint_config: ProseLintConfig | None = None
    if project_config_path(ctx.project_root).is_file():
        config = load_project_config(ctx.project_root)
        if config.prose_lint is not None:
            prose_lint_config = config.prose_lint
            anchor_patterns = prose_lint_config.anchor_patterns
            additional_anchor_patterns = prose_lint_config.additional_anchor_patterns
            spec_class_kinds = prose_lint_config.spec_class_kinds
            provenance_fields = prose_lint_config.provenance_fields
            configured_checks = prose_lint_config.enabled_checks
            if configured_checks is not None:
                # `numeric-anchor`/`numeric-verification` are an atomic pair
                # (see `couple_checks`); coupling here makes BOTH the scan
                # selection and the "disabled checks" message below coupling-
                # aware, so enabling one no longer reports the other as
                # disabled when it in fact ran.
                configured_checks = couple_checks(configured_checks)
            if not ctx.include_all_checks:
                selected = configured_checks
            exclude_paths = prose_lint_config.exclude_paths
            short_form_ids_deny = prose_lint_config.short_form_ids_deny
            bare_author_year_deny = prose_lint_config.bare_author_year_deny
    if prose_lint_config is None:
        # No science.yaml / no `prose_lint:` section: fall back to the same
        # `ProseLintConfig` defaults a configured project would get, rather
        # than letting validate's own notion of "default" silently diverge.
        prose_lint_config = ProseLintConfig()

    effective_anchor_patterns = merge_anchor_patterns(anchor_patterns, additional_anchor_patterns)
    effective_checks = selected if selected is not None else list(CHECKS)
    # The resolver doubles as the alias map for frontmatter-inline-gap (a body
    # mention via a project shorthand satisfies a canonical `related:` entry),
    # so build it when either check is active.
    resolver_checks = {"short-form-ids", "frontmatter-inline-gap"}
    resolver = (
        build_short_form_resolver(ctx.project_root)
        if resolver_checks & set(effective_checks)
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
        anchor_patterns=effective_anchor_patterns,
        spec_class_kinds=spec_class_kinds,
        provenance_fields=provenance_fields,
        exclude_paths=exclude_paths,
        short_form_ids_deny=short_form_ids_deny,
        resolver=resolver,
        bare_author_year_deny=bare_author_year_deny,
        bib_surnames=bib_surnames,
        max_json_bytes=prose_lint_config.max_json_bytes,
        max_feather_bytes=prose_lint_config.max_feather_bytes,
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
    numeric_coverage = lint_result.get("coverage", {}).get("numeric-verification")
    if numeric_coverage is not None and any(numeric_coverage.values()):
        # Standalone advisory, independent of the `counts`-derived "use
        # --strict to promote" path below: it reports the verification tally
        # whenever at least one claim was bound (a fully-`verified` project
        # still shows, since `verified` > 0). Suppressed when every tally is
        # zero — i.e. the project uses no `numeric_claims` at all — so the
        # check stays silent on projects that don't opt in, like every other
        # prose lint.
        results.append(
            _result(
                Severity.INFO,
                "numeric-verification coverage: "
                f"{numeric_coverage.get('verified', 0)} verified, "
                f"{numeric_coverage.get('unverifiable', 0)} unverifiable, "
                f"{numeric_coverage.get('mismatch', 0)} mismatch, "
                f"{numeric_coverage.get('error', 0)} error",
                rule="prose_lints.numeric-verification.coverage",
            )
        )
    for check, count in sorted(lint_result.get("counts", {}).items()):
        if count <= 0:
            continue
        if severity_by_check.get(check, "warn") != "warn":
            detail = (
                "graph metadata advisory"
                if check == "frontmatter-inline-gap"
                else "use --strict to promote"
            )
            results.append(
                _result(
                    Severity.INFO,
                    f"{count} prose lint issue(s): {check} ({detail})",
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
