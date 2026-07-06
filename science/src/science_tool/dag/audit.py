"""Audit orchestrator: validate and re-render proposition-backed DAGs.

By default the audit is **read-only**: it returns a structured report and does
not mutate source files. ``fix=True`` is a no-op after validation succeeds.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

from science_tool.dag.paths import DagPaths
from science_tool.dag.proposition_edges import load_proposition_edges
from science_tool.dag.render import render_all
from science_tool.dag.validate import ValidationReport, validate_project

# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProposedMutation:
    """A mutation that ``--fix`` would perform. Emitted for audit trail and tests."""

    kind: Literal["open_review_task", "propose_citation"]
    target: str  # e.g. "h1-prognosis#5" or "t100"
    description: str
    payload: dict  # type: ignore[type-arg]

    def to_json(self) -> dict:  # type: ignore[type-arg]
        return {
            "kind": self.kind,
            "target": self.target,
            "description": self.description,
            "payload": self.payload,
        }


@dataclass(frozen=True)
class AuditReport:
    """Complete audit result: validation findings + mutation record."""

    validation: ValidationReport
    mutations: tuple[ProposedMutation, ...]  # empty when fix=False

    @property
    def has_findings(self) -> bool:
        return not self.validation.ok

    def to_json(self) -> dict:  # type: ignore[type-arg]
        return {
            "today": self.validation.today.isoformat(),
            "strict": self.validation.strict,
            "validation": self.validation.to_json(),
            "mutations": [m.to_json() for m in self.mutations],
        }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_audit(
    paths: DagPaths,
    *,
    today: date | None = None,
    fix: bool = False,
    strict: bool = False,
) -> AuditReport:
    """Validate + re-render proposition-backed DAGs.

    With ``fix=False`` (default), audit is read-only aside from derived DAG
    render outputs. With ``fix=True``, validation must pass first; failure
    raises RuntimeError.

    Parameters
    ----------
    paths:
        Resolved project paths.
    today:
        Reference date (defaults to ``date.today()``).
    fix:
        Accepted for CLI/API continuity; no-op after validation succeeds.
    strict:
        When True, strict validation gates are enabled.
    """
    if today is None:
        today = date.today()

    validation = validate_project(paths, strict=strict, today=today)

    if not validation.ok:
        if not fix:
            return AuditReport(validation=validation, mutations=())

        blocking = [f for f in validation.findings if validation._blocks(f)]
        raise RuntimeError(
            "dag audit --fix refused: validation failed with "
            f"{len(blocking)} blocking finding(s). Run `science dag validate` first."
        )

    project_root = paths.project_root or paths.dag_dir.parents[2]
    render_all(paths, proposition_edges=load_proposition_edges(project_root))

    return AuditReport(validation=validation, mutations=())
