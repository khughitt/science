"""Validate health check: run canonical project validation and surface warnings/errors.

NOTE: this module's own name shadows the unrelated top-level ``science_tool.validate``
package. The imports below are ABSOLUTE (``from science_tool.validate import ...``),
never relative, so they resolve to that top-level package rather than to this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

from science_tool.graph.health_checks.base import HealthCheck
from science_tool.instruments import InstrumentResult


class ValidationFinding(TypedDict):
    severity: str
    path: str | None
    line: int | None
    message: str
    rule: str | None
    task: str | None


def collect_validation_findings(project_root: Path) -> InstrumentResult[ValidationFinding]:
    """Run canonical validation and return its warnings/errors as findings.

    This check has NO unwired state. A ``ValidateContextError`` — the one way it can
    fail to reach the validators — is already a RESULT: it is reported as an error
    finding, not laundered into "could not run".
    """
    from science_tool.validate import runner as validate_runner
    from science_tool.validate.context import ValidateContextError
    from science_tool.validate.result import Severity

    try:
        run_result = validate_runner.run(project_root, strict=False, verbose=False, enable_python_sidecar=False)
    except ValidateContextError as exc:
        return InstrumentResult.ok(
            [
                {
                    "severity": "error",
                    "path": None,
                    "line": None,
                    "message": str(exc),
                    "rule": "validate.context",
                    "task": None,
                }
            ]
        )
    findings: list[ValidationFinding] = [
        {
            "severity": _validation_health_severity(result.severity),
            "path": str(result.path) if result.path is not None else None,
            "line": result.line,
            "message": result.message,
            "rule": result.rule,
            "task": result.task,
        }
        for result in run_result.results
        if result.severity is not Severity.INFO
    ]
    return InstrumentResult.from_rows(findings)


def _validation_health_severity(severity: object) -> str:
    from science_tool.validate.result import Severity

    if severity is Severity.WARN:
        return "warning"
    if severity is Severity.ERROR:
        return "error"
    raise ValueError(f"unsupported validation severity: {severity!r}")


CHECK = HealthCheck(
    name="validate",
    description="Run canonical project validation and surface warnings/errors.",
    requires_sources=False,
    run=lambda context: collect_validation_findings(context.project_root),
    empty=lambda _root: [],
)
