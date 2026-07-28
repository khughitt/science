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

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.entities import resolve_path_policy
from science_tool.entity_scan import iter_entity_markdown
from science_tool.run_fingerprint_policy import (
    RULE_AUTHORED_CAPTURABLE,
    RULE_INCOMPLETE,
    evaluate_fingerprint,
)
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

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


SECTION, RULES = declare_validation_rules(
    section_id="workflow-runs",
    section_title="workflow runs",
    section_order=153,
    rule_ids=(
        "run.execution-malformed",
        "run.fingerprint-authored-capturable",
        "run.fingerprint-declaration-drift",
        "run.fingerprint-incomplete",
        "run.fingerprint-malformed",
        "run.fingerprint-origin-unverified",
    ),
    severities=frozenset({"error", "warn", "info"}),
)

FINGERPRINT_RULES = {
    RULE_INCOMPLETE: RULES["run.fingerprint-incomplete"],
    RULE_AUTHORED_CAPTURABLE: RULES["run.fingerprint-authored-capturable"],
}


def _runs(ctx: ValidateContext) -> list[tuple[Path, dict]]:
    """Every workflow-run under the kind's root, at any depth.

    Recursive, because entity discovery is: `load_project_sources` keys on the
    frontmatter `kind`, not the directory, so a run in a subdirectory is a real,
    loaded entity. Globbing one level deep would exempt it from every rule below.
    """
    root = ctx.project_root / resolve_path_policy("workflow-run").root
    return [(p, ctx.frontmatter(p)) for p in iter_entity_markdown(root)]


def _verify_origin(ctx: ValidateContext, path: Path, fp: RunFingerprint) -> CheckObservation | None:
    if fp.executor is not ExecutorKind.COMMONS:
        return None
    origin = fp.capture_origin
    if origin is None:
        raise AssertionError("model invariant violated: executor='commons' requires capture_origin")
    if origin.source_ref is None:
        return None
    if Path(origin.source_ref).is_absolute():
        return validation_observation(
            severity=Severity.ERROR,
            path=path,
            line=None,
            message=f"{path.name}: capture_origin.source_ref {origin.source_ref!r} must be relative to the project root",
            rule=RULES["run.fingerprint-origin-unverified"],
            task=None,
            qualifiers={"key": ["source-ref"]},
        )
    source = ctx.project_root / origin.source_ref
    if not source.is_file():
        return validation_observation(
            severity=Severity.ERROR,
            path=path,
            line=None,
            message=f"{path.name}: capture_origin.source_ref {origin.source_ref!r} does not exist",
            rule=RULES["run.fingerprint-origin-unverified"],
            task=None,
            qualifiers={"key": ["source-ref"]},
        )
    if origin.source_digest is None:
        return None
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    if actual != origin.source_digest:
        return validation_observation(
            severity=Severity.ERROR,
            path=path,
            line=None,
            message=f"{path.name}: capture_origin.source_digest {origin.source_digest!r} does not match sha256 of {origin.source_ref!r} ({actual!r})",
            rule=RULES["run.fingerprint-origin-unverified"],
            task=None,
            qualifiers={"key": ["source-digest"]},
        )
    return None


def _check_drift(path: Path, declaration: RunDeclaration | None, fp: RunFingerprint) -> Iterator[CheckObservation]:
    """The captured fingerprint must still agree with what the run declares.

    `register-run` copies the declaration into the fingerprint. Editing
    `execution:` afterwards leaves a fingerprint asserting it was captured under
    conditions that no longer hold — silently, since every digest still verifies.
    """
    if declaration is None:
        yield validation_observation(
            severity=Severity.ERROR,
            path=path,
            line=None,
            message=f"{path.name}: carries a captured fingerprint but declares no `execution:` block; the fingerprint records conditions nothing asserts",
            rule=RULES["run.fingerprint-declaration-drift"],
            task=None,
            qualifiers={"key": ["execution"]},
        )
        return
    for field in _DECLARED_FIELDS:
        declared, captured = getattr(declaration, field), getattr(fp, field)
        if declared != captured:
            yield validation_observation(
                severity=Severity.ERROR,
                path=path,
                line=None,
                message=f"{path.name}: execution.{field} is {declared!r} but the captured fingerprint records {captured!r}; re-register the run",
                rule=RULES["run.fingerprint-declaration-drift"],
                task=None,
                qualifiers={"key": ["execution", field]},
            )


@Check(section=SECTION, order=10, producer_id="validate.workflow-runs", rules=tuple(RULES.values()))
def check_run_fingerprint_obligations(ctx: ValidateContext) -> Iterator[CheckObservation]:
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
                yield validation_observation(
                    severity=Severity.ERROR,
                    path=path,
                    line=None,
                    message=f"{path.name}: malformed execution declaration: {exc.errors()[0]['msg']}",
                    rule=RULES["run.execution-malformed"],
                    task=None,
                    qualifiers={"key": ["execution"]},
                )
                # An unparseable declaration cannot be compared against anything.
                continue

        raw = fm.get("fingerprint")
        if not raw:
            continue
        try:
            fingerprint = RunFingerprint.model_validate(raw)
        except ValidationError as exc:
            yield validation_observation(
                severity=Severity.ERROR,
                path=path,
                line=None,
                message=f"{path.name}: malformed fingerprint: {exc.errors()[0]['msg']}",
                rule=RULES["run.fingerprint-malformed"],
                task=None,
                qualifiers={"key": ["fingerprint"]},
            )
            continue

        yield from _check_drift(path, declaration, fingerprint)

        for finding in evaluate_fingerprint(fingerprint):
            severity = Severity.ERROR if finding.rule == RULE_AUTHORED_CAPTURABLE else Severity.WARN
            yield validation_observation(
                severity=severity,
                path=path,
                line=None,
                message=f"{path.name}: {finding.message}",
                rule=FINGERPRINT_RULES[finding.rule],
                task=None,
                qualifiers={"key": [finding.component]},
            )

        origin_result = _verify_origin(ctx, path, fingerprint)
        if origin_result is not None:
            yield origin_result
