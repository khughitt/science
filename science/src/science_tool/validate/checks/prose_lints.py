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

import unicodedata
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from science_model.audit import (
    Evidence,
    FindingRule,
    FindingSection,
    LocationEvidence,
    ProducerMetrics,
    Span,
    TextEvidence,
)
from science_model.audit.evidence import MAX_EVIDENCE_ENTRIES

from science_tool.validate.findings import (
    EmptyQualifiers,
    NumericVerificationMetrics,
    ProseAdvisoryQualifiers,
    ProseHitQualifiers,
    validation_observation,
)
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
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.observations import ValidationMetricObservation
from science_tool.validate.result import Severity

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


SECTION = FindingSection(
    id="prose-lints",
    title="prose lints",
    section_order=146,
)
RULE_HIT = FindingRule(
    id="prose-lints.hit",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"path"}),
    qualifier_schema=ProseHitQualifiers,
    identity_qualifiers=("check", "match"),
    title="Prose lint hit",
    section=SECTION.id,
    display_order=14601,
    default_visibility="visible",
)
RULE_ADVISORY = FindingRule(
    id="prose-lints.advisory",
    severities=frozenset({"info"}),
    subject_types=frozenset({"project"}),
    qualifier_schema=ProseAdvisoryQualifiers,
    identity_qualifiers=("check",),
    title="Prose lint advisory",
    section=SECTION.id,
    display_order=14602,
    default_visibility="hidden",
)
RULE_CONFIG = FindingRule(
    id="prose-lints.config",
    severities=frozenset({"info"}),
    subject_types=frozenset({"project"}),
    qualifier_schema=EmptyQualifiers,
    title="Prose lint configuration",
    section=SECTION.id,
    display_order=14603,
    default_visibility="visible",
)


@Check(
    section=SECTION,
    order=21,
    producer_id="validate.prose-lints",
    rules=(RULE_HIT, RULE_ADVISORY, RULE_CONFIG),
    metrics_schema=NumericVerificationMetrics,
)
def check_prose_lints(ctx: "ValidateContext") -> Iterable[CheckObservation]:
    if not ctx.doc_dir.is_dir():
        return [
            ValidationMetricObservation(
                metrics=ProducerMetrics.model_validate(
                    {
                        "verified": 0,
                        "unverifiable": 0,
                        "mismatch": 0,
                        "error": 0,
                    }
                )
            )
        ]

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
    resolver = build_short_form_resolver(ctx.project_root) if resolver_checks & set(effective_checks) else None
    bib_surnames = load_bib_author_surnames(ctx.project_root) if "bare-author-year" in effective_checks else None

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

    results: list[CheckObservation] = []
    if configured_checks is not None and set(configured_checks) != set(CHECKS):
        results.append(_configured_checks_result(configured_checks, include_all_checks=ctx.include_all_checks))
    warn_hits = sorted(
        (hit for hit in lint_result.get("hits", []) if hit.severity == "warn"),
        key=lambda item: (
            _relative_path(ctx, item.file).as_posix(),
            item.check,
            item.line,
            item.col,
        ),
    )
    grouped_hits: dict[tuple[str, str, str], list[LintIssue]] = {}
    for hit in warn_hits:
        identity = (
            _relative_path(ctx, hit.file).as_posix(),
            hit.check,
            _normalize_hit_match(hit.match),
        )
        grouped_hits.setdefault(identity, []).append(hit)
    for (_, _, normalized_match), grouped in grouped_hits.items():
        results.append(
            _hit_result(
                ctx,
                grouped,
                normalized_match=normalized_match,
            )
        )
    numeric_coverage = lint_result.get("coverage", {}).get("numeric-verification") or {}
    results.append(
        ValidationMetricObservation(
            metrics=ProducerMetrics.model_validate(
                NumericVerificationMetrics(
                    verified=numeric_coverage.get("verified", 0),
                    unverifiable=numeric_coverage.get("unverifiable", 0),
                    mismatch=numeric_coverage.get("mismatch", 0),
                    error=numeric_coverage.get("error", 0),
                ).model_dump(mode="json")
            )
        )
    )
    for check, count in sorted(lint_result.get("counts", {}).items()):
        if count <= 0:
            continue
        if severity_by_check.get(check, "warn") != "warn":
            detail = "graph metadata advisory" if check == "frontmatter-inline-gap" else "use --strict to promote"
            results.append(
                validation_observation(
                    severity=Severity.INFO,
                    path=None,
                    line=None,
                    message=f"{count} prose lint issue(s): {check} ({detail})",
                    rule=RULE_ADVISORY,
                    task=None,
                    qualifiers={"check": check, "count": count},
                )
            )
    return results


def _configured_checks_result(selected: list[str], *, include_all_checks: bool) -> CheckObservation:
    disabled = [check for check in CHECKS if check not in selected]
    enabled = ", ".join(selected)
    if include_all_checks:
        message = (
            f"prose lint checks limited by science.yaml but --all is active; "
            f"running all {len(CHECKS)} checks (science.yaml enabled: {enabled})"
        )
        return validation_observation(
            severity=Severity.INFO,
            path=None,
            line=None,
            message=message,
            rule=RULE_CONFIG,
            task=None,
            qualifiers={},
        )
    disabled_text = ", ".join(disabled)
    message = (
        f"prose lint checks limited by science.yaml: {len(selected)}/{len(CHECKS)} enabled "
        f"({enabled}); disabled: {disabled_text}"
    )
    return validation_observation(
        severity=Severity.INFO,
        path=None,
        line=None,
        message=message,
        rule=RULE_CONFIG,
        task=None,
        qualifiers={},
    )


def _hit_result(
    ctx: "ValidateContext",
    hits: list[LintIssue],
    *,
    normalized_match: str,
) -> CheckObservation:
    first = hits[0]
    message = (
        first.message
        if len(hits) == 1
        else (f"{len(hits)} semantically identical {first.check} prose lint issues for match {normalized_match!r}")
    )
    return validation_observation(
        severity=Severity.WARN,
        path=_relative_path(ctx, first.file),
        line=None,
        message=message,
        rule=RULE_HIT,
        task=None,
        qualifiers={
            "check": first.check,
            "match": normalized_match,
        },
        evidence=_hit_evidence(ctx, hits),
    )


def _normalize_hit_match(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()


def _hit_evidence(
    ctx: "ValidateContext",
    hits: list[LintIssue],
) -> tuple[Evidence, ...]:
    path = _relative_path(ctx, hits[0].file).as_posix()
    if len(hits) <= MAX_EVIDENCE_ENTRIES:
        return tuple(LocationEvidence(path=path, line=hit.line) for hit in hits)

    first_line = min(hit.line for hit in hits)
    last_line = max(hit.line for hit in hits)
    return (
        LocationEvidence(
            path=path,
            span=Span(start_line=first_line, end_line=last_line),
        ),
        TextEvidence(
            label="location summary",
            text=(
                f"{len(hits)} semantically identical prose-lint locations "
                f"summarized across lines {first_line}-{last_line} to stay "
                f"within the {MAX_EVIDENCE_ENTRIES}-entry evidence bound."
            ),
        ),
    )


def _relative_path(ctx: "ValidateContext", path: Path) -> Path:
    try:
        return path.resolve().relative_to(ctx.project_root.resolve())
    except (OSError, ValueError):
        return path
