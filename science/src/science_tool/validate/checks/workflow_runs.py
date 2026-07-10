"""Structural checks for workflow-run reproducibility fingerprints.

Frontmatter-local: a run's fingerprint is well-formed or not, independently of
any evidence line. Evidence -> run RESOLUTION is graph-phase; see
`science_tool.graph.store.validation`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from pydantic import ValidationError
from science_model.run_fingerprint import ExecutorKind, RunDeclaration, RunFingerprint

from science_tool.entities import resolve_path_policy
from science_tool.run_fingerprint_policy import RULE_AUTHORED_CAPTURABLE, evaluate_fingerprint
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

RULE_ORIGIN_UNVERIFIED = "run.fingerprint-origin-unverified"
RULE_MALFORMED = "run.fingerprint-malformed"
RULE_EXECUTION_MALFORMED = "run.execution-malformed"
RULE_DECLARATION_DRIFT = "run.fingerprint-declaration-drift"

#: The fields a run declares and `register-run` copies into the fingerprint it
#: captures. Held in both places so the fingerprint stands alone — which means
#: they can drift, and drift is what this module's `_check_drift` refuses.
_DECLARED_FIELDS: tuple[str, ...] = (
    "executor",
    "input_artifact_locality",
    "output_artifact_locality",
    "capture_origin",
)


def _runs(ctx: ValidateContext) -> list[tuple[Path, dict]]:
    root = ctx.project_root / resolve_path_policy("workflow-run").root
    if not root.is_dir():
        return []
    return [(p, ctx.frontmatter(p)) for p in sorted(root.glob("*.md"))]


def _verify_origin(ctx: ValidateContext, path: Path, fp: RunFingerprint) -> Result | None:
    if fp.executor is not ExecutorKind.COMMONS:
        return None
    origin = fp.capture_origin
    if origin is None:
        raise AssertionError("model invariant violated: executor='commons' requires capture_origin")
    if origin.source_ref is None:
        return None
    if Path(origin.source_ref).is_absolute():
        return Result(
            severity=Severity.ERROR, path=path, line=None,
            message=f"{path.name}: capture_origin.source_ref {origin.source_ref!r} must be relative to the project root",
            rule=RULE_ORIGIN_UNVERIFIED, task=None,
        )
    source = ctx.project_root / origin.source_ref
    if not source.is_file():
        return Result(
            severity=Severity.ERROR, path=path, line=None,
            message=f"{path.name}: capture_origin.source_ref {origin.source_ref!r} does not exist",
            rule=RULE_ORIGIN_UNVERIFIED, task=None,
        )
    if origin.source_digest is None:
        return None
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != origin.source_digest:
        return Result(
            severity=Severity.ERROR, path=path, line=None,
            message=(
                f"{path.name}: capture_origin.source_digest {origin.source_digest!r} does not "
                f"match sha256 of {origin.source_ref!r} ({actual!r})"
            ),
            rule=RULE_ORIGIN_UNVERIFIED, task=None,
        )
    return None


def _check_drift(path: Path, declaration: RunDeclaration | None, fp: RunFingerprint) -> Iterator[Result]:
    """The captured fingerprint must still agree with what the run declares.

    `register-run` copies the declaration into the fingerprint. Editing
    `execution:` afterwards leaves a fingerprint asserting it was captured under
    conditions that no longer hold — silently, since every digest still verifies.
    """
    if declaration is None:
        yield Result(
            severity=Severity.ERROR, path=path, line=None,
            message=(
                f"{path.name}: carries a captured fingerprint but declares no `execution:` "
                "block; the fingerprint records conditions nothing asserts"
            ),
            rule=RULE_DECLARATION_DRIFT, task=None,
        )
        return
    for field in _DECLARED_FIELDS:
        declared, captured = getattr(declaration, field), getattr(fp, field)
        if declared != captured:
            yield Result(
                severity=Severity.ERROR, path=path, line=None,
                message=(
                    f"{path.name}: execution.{field} is {declared!r} but the captured "
                    f"fingerprint records {captured!r}; re-register the run"
                ),
                rule=RULE_DECLARATION_DRIFT, task=None,
            )


@Check(section="workflow runs", order=10)
def check_run_fingerprint_obligations(ctx: ValidateContext) -> Iterator[Result]:
    """A workflow-run's declaration and its captured fingerprint must both hold.

    `execution:` is authored and stands alone — a run that declares one and has
    never been registered validates clean (t093). `fingerprint:` is captured:
    capturable components may not be attested (ERROR), missing required components
    warn until the P4 flip, and it must not have drifted from the declaration.
    """
    for path, fm in _runs(ctx):
        raw_execution = fm.get("execution")
        declaration: RunDeclaration | None = None
        if raw_execution:
            try:
                declaration = RunDeclaration.model_validate(raw_execution)
            except ValidationError as exc:
                yield Result(
                    severity=Severity.ERROR, path=path, line=None,
                    message=f"{path.name}: malformed execution declaration: {exc.errors()[0]['msg']}",
                    rule=RULE_EXECUTION_MALFORMED, task=None,
                )
                # An unparseable declaration cannot be compared against anything.
                continue

        raw = fm.get("fingerprint")
        if not raw:
            continue
        try:
            fingerprint = RunFingerprint.model_validate(raw)
        except ValidationError as exc:
            yield Result(
                severity=Severity.ERROR, path=path, line=None,
                message=f"{path.name}: malformed fingerprint: {exc.errors()[0]['msg']}",
                rule=RULE_MALFORMED, task=None,
            )
            continue

        yield from _check_drift(path, declaration, fingerprint)

        for finding in evaluate_fingerprint(fingerprint):
            severity = (
                Severity.ERROR if finding.rule == RULE_AUTHORED_CAPTURABLE else Severity.WARN
            )
            yield Result(
                severity=severity, path=path, line=None,
                message=f"{path.name}: {finding.message}", rule=finding.rule, task=None,
            )

        origin_result = _verify_origin(ctx, path, fingerprint)
        if origin_result is not None:
            yield origin_result
