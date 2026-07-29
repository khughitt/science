"""Port of validate.sh "Checking paper summaries..." block.

Checks paper entities under ``entities/papers/`` for template section
conformance.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.findings import declare_validation_rules, validation_observation
from science_tool.validate.observations import ValidationNotice
from science_tool.validate.result import Severity


class BackgroundReviewQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ref: str
    task: str | None = None


SECTION, RULES = declare_validation_rules(
    section_id="papers",
    section_title="papers",
    section_order=110,
    rule_ids=(
        "papers.background-review-evidence-ref",
        "papers.background-review-source-typing",
        "papers.background-review-evidence-tier",
    ),
    severities=frozenset({"warn"}),
    subject_types=frozenset({"path"}),
    qualifier_schema=BackgroundReviewQualifiers,
    identity_qualifiers=("paper_ref",),
)

RULE_EVIDENCE_REF = RULES["papers.background-review-evidence-ref"]
RULE_SOURCE_TYPING = RULES["papers.background-review-source-typing"]
RULE_EVIDENCE_TIER = RULES["papers.background-review-evidence-tier"]


_REF_PREFIXES = ("paper", "cite")


def _paper_key(ref: Any) -> str | None:
    """Extract the paper key from a `paper:Key` / `cite:Key` reference scalar."""
    if not isinstance(ref, str):
        return None
    prefix, separator, key = ref.partition(":")
    if not separator or prefix not in _REF_PREFIXES:
        return None
    return key.strip() or None


def _background_papers(ctx: ValidateContext) -> set[str]:
    papers_root = ctx.project_root / resolve_path_policy("paper").root
    if not papers_root.is_dir():
        return set()
    return {
        path.stem
        for path in sorted(papers_root.glob("*.md"))
        if ctx.frontmatter(path).get("status") == "background"
    }


def _citation_roots(ctx: ValidateContext) -> tuple[Path, ...]:
    return tuple(
        ctx.project_root / resolve_path_policy(kind).root
        for kind in ("theme", "report", "hypothesis")
    )


def _evidence_ref_observations(
    ctx: ValidateContext, background: set[str]
) -> Iterator[CheckObservation]:
    for root in _citation_roots(ctx):
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            refs = ctx.frontmatter(path).get("evidence_refs")
            if not isinstance(refs, list):
                continue
            # Dedupe per (path, paper_ref) across the WHOLE file: finding identity
            # is (rule, path, paper_ref), so a repeated citation would emit two
            # identical identities and the producer boundary would reject them.
            seen: set[str] = set()
            for ref in refs:
                key = _paper_key(ref)
                if key is None or key not in background or key in seen:
                    continue
                seen.add(key)
                yield validation_observation(
                    severity=Severity.WARN,
                    path=path,
                    line=None,
                    message=(
                        f"evidence_refs cites paper:{key} (status:background); use a "
                        "primary citation or synthesis report instead of the review directly"
                    ),
                    rule=RULE_EVIDENCE_REF,
                    task=None,
                    qualifiers={"paper_ref": key},
                )


def _provenance_observations(
    ctx: ValidateContext, background: set[str]
) -> Iterator[CheckObservation]:
    provenance_root = ctx.doc_dir / "provenance"
    if not provenance_root.is_dir():
        return
    for path in sorted(provenance_root.glob("*.yaml")):
        record = ctx.read_yaml(path)
        if not isinstance(record, dict):
            continue
        key = _paper_key(record.get("source_ref"))
        if key is None or key not in background:
            continue

        if record.get("review_typed_source") is not True:
            yield validation_observation(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=(
                    f"source_ref names paper:{key} (status:background) without "
                    "review_typed_source: true"
                ),
                rule=RULE_SOURCE_TYPING,
                task=None,
                qualifiers={"paper_ref": key},
            )

        if record.get("evidence_tier") != "background":
            yield validation_observation(
                severity=Severity.WARN,
                path=path,
                line=None,
                message=(
                    f"source_ref names paper:{key} (status:background) without "
                    "evidence_tier: background"
                ),
                rule=RULE_EVIDENCE_TIER,
                task=None,
                qualifiers={"paper_ref": key},
            )


def _background_review_observations(ctx: ValidateContext) -> Iterator[CheckObservation]:
    background = _background_papers(ctx)
    if not background:
        yield ValidationNotice(
            path=None,
            line=None,
            message="no status:background papers; reviews-are-not-evidence checks pass",
        )
        return

    violations = 0
    for observation in _provenance_observations(ctx, background):
        violations += 1
        yield observation
    for observation in _evidence_ref_observations(ctx, background):
        violations += 1
        yield observation

    yield ValidationNotice(
        path=None,
        line=None,
        message=(
            f"{len(background)} status:background paper(s); "
            f"{violations} reviews-are-not-evidence violation(s)"
        ),
    )


def _result(severity: Severity, path: str | None, message: str) -> ValidationNotice:
    if severity is not Severity.INFO:
        raise ValueError("the papers observation is notice-only")
    return ValidationNotice(
        path=Path(path) if path is not None else None,
        line=None,
        message=message,
    )


@Check(section=SECTION, order=7, producer_id="validate.papers", rules=tuple(RULES.values()))
def check_papers(ctx: ValidateContext) -> Iterator[CheckObservation]:
    papers_root = resolve_path_policy("paper").root
    yield _result(
        Severity.INFO,
        papers_root.as_posix(),
        f"Paper summary structure is checked in {papers_root.as_posix()}/",
    )
    yield from _background_review_observations(ctx)
