"""Audit orchestrator: re-render all DAGs then run staleness check.

By default the audit is **read-only**: it returns a structured report and the
mutations that *would* be performed, but does not mutate ``tasks/active.md``,
``edges.yaml``, or any other input file.

With ``fix=True`` the caller asks for real side-effects:

- For each ``DriftedEdge`` — open a review task via ``_open_review_task``.
- For each ``UnpropagatedTask`` — write a reminder to
  ``<dag_dir>/.audit-unpropagated-<YYYY-MM-DD>.md`` (no auto-citation;
  that requires human judgement).

``-auto.dot`` and ``-auto.png`` regeneration is always allowed because
``render_all`` is idempotent on unchanged YAML — it only writes derived
artifacts, never source files.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from science_tool.dag.paths import DagPaths
from science_tool.dag.render import render_all
from science_tool.dag.staleness import (
    DriftedEdge,
    StalenessReport,
    UnpropagatedTask,
    check_staleness,
)
from science_tool import tasks as _tasks_mod


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
    """Complete audit result: staleness findings + optional mutation record."""

    staleness: StalenessReport
    mutations: tuple[ProposedMutation, ...]  # empty when fix=False

    @property
    def has_findings(self) -> bool:
        return self.staleness.has_findings

    def to_json(self) -> dict:  # type: ignore[type-arg]
        return {
            "staleness": self.staleness.to_json(),
            "mutations": [m.to_json() for m in self.mutations],
        }


# ---------------------------------------------------------------------------
# Internal side-effect helpers (monkeypatched in tests)
# ---------------------------------------------------------------------------


def _open_review_task(
    *,
    tasks_dir: Path,
    title: str,
    priority: str,
    aspects: list[str],
    group: str,
    related: list[str],
    description: str,
) -> None:
    """Thin wrapper around ``science_tool.tasks.add_task``.

    Isolated here so tests can monkeypatch without touching real tasks.
    """
    _tasks_mod.add_task(
        tasks_dir=tasks_dir,
        title=title,
        priority=priority,
        aspects=aspects,
        group=group,
        related=related,
        description=description,
    )


def _write_unpropagated_log(dag_dir: Path, today: date, tasks: tuple[UnpropagatedTask, ...]) -> None:
    """Write a reminder file listing unpropagated tasks for human review."""
    log_path = dag_dir / f".audit-unpropagated-{today.isoformat()}.md"
    lines = [
        f"# Unpropagated tasks — {today.isoformat()}",
        "",
        "Tasks that cite a hypothesis/inquiry/proposition but are not cited by any DAG edge.",
        "Review and add to `data_support` on the relevant edge, or document why they don't apply.",
        "",
    ]
    for task in tasks:
        related_str = ", ".join(task.related)
        lines.append(f"- **{task.id}** — {task.title}")
        lines.append(f"  - completed: {task.completed.isoformat()}")
        lines.append(f"  - related: [{related_str}]")
        lines.append("")
    log_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Mutation builders
# ---------------------------------------------------------------------------


def _build_drift_mutation(edge: DriftedEdge) -> ProposedMutation:
    candidate_ids = [c.id for c in edge.candidate_drift_tasks]
    target = f"{edge.dag}#{edge.id}"
    description = (
        f"Edge {target} ({edge.source} -> {edge.target}) has {len(candidate_ids)} "
        f"candidate drift task(s) completed after its anchor date: {candidate_ids}. "
        "Review whether these tasks change the edge's evidence status."
    )
    return ProposedMutation(
        kind="open_review_task",
        target=target,
        description=description,
        payload={
            "dag": edge.dag,
            "edge_id": edge.id,
            "source": edge.source,
            "target": edge.target,
            "candidate_task_ids": candidate_ids,
            "last_cited_date": edge.last_cited_date.isoformat() if edge.last_cited_date else None,
        },
    )


def _build_unpropagated_mutation(task: UnpropagatedTask) -> ProposedMutation:
    description = (
        f"Task {task.id} cites {list(task.related)} but is not referenced by any edge. "
        "Consider adding to data_support of a relevant edge or documenting why it doesn't apply."
    )
    return ProposedMutation(
        kind="propose_citation",
        target=task.id,
        description=description,
        payload={
            "task_id": task.id,
            "related": list(task.related),
            "title": task.title,
        },
    )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_audit(
    paths: DagPaths,
    *,
    today: date | None = None,
    recent_days: int = 28,
    include_curation_freshness: bool = False,
    fix: bool = False,
) -> AuditReport:
    """Re-render all DAGs (idempotent) + run drift-based staleness check.

    Read-only by default: returns the report and the mutations that *would* be
    performed if ``fix=True``, but does not actually perform them unless
    ``fix=True``.

    With ``fix=True``, opens review tasks for drifted edges and writes an
    unpropagated-task log file.  Unpropagated citations are NOT auto-applied
    (they require human judgement on which edge to cite in).

    Parameters
    ----------
    paths:
        Resolved project paths.
    today:
        Reference date (defaults to ``date.today()``).
    recent_days:
        Look-back window for unpropagated-task detection (default 28 days).
    include_curation_freshness:
        When True, also populate ``StalenessReport.under_reviewed_edges``.
    fix:
        When True, execute the mutations (open tasks, write log).
        When False (default), the report is fully read-only.
    """
    if today is None:
        today = date.today()

    # Re-render all DAGs — idempotent derived-artifact write, always safe.
    render_all(paths)

    # Run staleness check.
    staleness = check_staleness(
        paths,
        today=today,
        recent_days=recent_days,
        include_curation_freshness=include_curation_freshness,
    )

    if not fix:
        return AuditReport(staleness=staleness, mutations=())

    # ---- fix=True path: build mutations and execute -------------------------
    mutations: list[ProposedMutation] = []

    # Drifted edges → open review tasks.
    for edge in staleness.drifted_edges:
        mutation = _build_drift_mutation(edge)
        mutations.append(mutation)
        candidate_ids = [c.id for c in edge.candidate_drift_tasks]
        _open_review_task(
            tasks_dir=paths.tasks_dir,
            title=f"Review {edge.dag}#{edge.id}: drift candidates {candidate_ids}",
            priority="P2",
            aspects=["causal-modeling"],
            group="dag-refresh",
            related=[f"hypothesis:{edge.dag}"],
            description=mutation.description,
        )

    # Unpropagated tasks → record in log file (no auto-citation).
    if staleness.unpropagated_tasks:
        for task in staleness.unpropagated_tasks:
            mutations.append(_build_unpropagated_mutation(task))
        _write_unpropagated_log(paths.dag_dir, today, staleness.unpropagated_tasks)

    return AuditReport(staleness=staleness, mutations=tuple(mutations))
