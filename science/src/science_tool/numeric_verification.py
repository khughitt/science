"""Numeric-claim verification runner (Part B of the numeric-provenance redesign).

`run_numeric_verification` is the integration point that ties the binding
parser (numeric_binding.py), the artifact resolver + scalar reader
(artifact_value_reader.py), and the prose-literal grammar (numeric_literal.py)
together into one per-binding outcome. It never re-derives their fail-closed
logic -- a resolver `ArtifactError` or reader `ReaderError` always becomes
`"error"`, and an `opaque` locator or a `%`-unit literal always becomes
`"unverifiable"` (never a silent pass and never a hidden read).

Resolution always happens first, even for opaque/percent claims: a missing or
root-escaping artifact is an error, not a silently-skipped unverifiable. Only
after a successful resolve does the opaque/percent short-circuit apply.

See docs/plans/2026-07-18-numeric-provenance-check-design.md (Part B).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from science_tool.artifact_value_reader import (
    ArtifactError,
    ReaderError,
    read_scalar,
    resolve_artifact,
)
from science_tool.numeric_binding import OpaqueLocator, parse_claim_bindings
from science_tool.numeric_literal import compare_at_precision, parse_prose_literal

if TYPE_CHECKING:
    from pathlib import Path

    from science_tool.numeric_provenance import DocumentContext
    from science_tool.prose_lint import LintIssue

ERROR: Final = "error"

_CHECK: Final = "numeric-verification"


@dataclass(frozen=True)
class VerificationResult:
    id: str | None
    line: int
    outcome: str  # "verified" | "mismatch" | "unverifiable" | "error"
    detail: str


def run_numeric_verification(
    document: "DocumentContext",
    project_root: "Path",
    data_root: "Path",
    *,
    max_json_bytes: int,
    max_feather_bytes: int,
) -> "tuple[list[LintIssue], list[VerificationResult]]":
    from science_tool.prose_lint import LintIssue  # noqa: PLC0415

    bindings, binding_errors = parse_claim_bindings(document)

    issues: list[LintIssue] = []
    results: list[VerificationResult] = []

    for err in binding_errors:
        line = err.line if err.line is not None else 1
        results.append(VerificationResult(id=err.id, line=line, outcome=ERROR, detail=err.message))
        issues.append(
            LintIssue(
                file=document.path,
                line=line,
                col=1,
                check=_CHECK,
                severity="warn",
                message=err.message,
                match=err.id if err.id is not None else "numeric_claims",
            )
        )

    for binding in bindings:
        line, col_start, _col_end = binding.span
        parsed_literal = parse_prose_literal(binding.value_text)
        is_percent = parsed_literal is not None and parsed_literal.unit == "%"
        is_opaque = isinstance(binding.locator, OpaqueLocator)
        content = not (is_opaque or is_percent)

        resolved = resolve_artifact(
            binding.artifact,
            project_root,
            data_root,
            max_json_bytes=max_json_bytes,
            max_feather_bytes=max_feather_bytes,
            content=content,
        )
        if isinstance(resolved, ArtifactError):
            results.append(VerificationResult(id=binding.id, line=line, outcome=ERROR, detail=resolved.detail))
            issues.append(
                LintIssue(
                    file=document.path,
                    line=line,
                    col=col_start,
                    check=_CHECK,
                    severity="warn",
                    message=resolved.detail,
                    match=binding.value_text,
                )
            )
            continue

        if is_opaque or is_percent:
            results.append(VerificationResult(id=binding.id, line=line, outcome="unverifiable", detail=""))
            continue

        assert parsed_literal is not None
        value = read_scalar(resolved, binding.locator)
        if isinstance(value, ReaderError):
            results.append(VerificationResult(id=binding.id, line=line, outcome=ERROR, detail=value.detail))
            issues.append(
                LintIssue(
                    file=document.path,
                    line=line,
                    col=col_start,
                    check=_CHECK,
                    severity="warn",
                    message=value.detail,
                    match=binding.value_text,
                )
            )
            continue

        outcome = compare_at_precision(parsed_literal, value, binding.tolerance)
        detail = ""
        if outcome == "mismatch":
            detail = f"prose value {binding.value_text!r} does not match artifact value {value} at {binding.artifact}"
            issues.append(
                LintIssue(
                    file=document.path,
                    line=line,
                    col=col_start,
                    check=_CHECK,
                    severity="warn",
                    message=detail,
                    match=binding.value_text,
                )
            )
        results.append(VerificationResult(id=binding.id, line=line, outcome=outcome, detail=detail))

    return issues, results


def coverage_from_results(results: list[VerificationResult]) -> dict[str, int]:
    coverage = {"verified": 0, "unverifiable": 0, "mismatch": 0, ERROR: 0}
    for result in results:
        coverage[result.outcome] += 1
    return coverage
