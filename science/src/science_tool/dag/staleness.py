"""Drift-based staleness audit for DAG edges.

For each edge in ``<dag_dir>/<slug>.edges.yaml``, cross-references completed
tasks against:

  A. **Drift** — tasks completed after the edge's anchor date whose ``related:``
     field names the edge's hypothesis, a cited proposition, the source node, or
     the target node.  If any such tasks exist, the edge is flagged as a
     ``DriftedEdge``.  This is a drift-based rule, NOT an age-based rule.

  B. **Unresolved refs** — task / interpretation / discussion refs cited in
     ``data_support``, ``lit_support``, or ``eliminated_by`` that cannot be
     resolved on disk.  Reported as ``UnresolvedRef``.

  C. **Unpropagated tasks** (orphans) — recently-completed tasks whose
     ``related:`` names a ``hypothesis:``, ``inquiry:``, or ``proposition:``
     but whose ID is not cited by any edge in any DAG.  Reported as
     ``UnpropagatedTask``.

  D. **Curation freshness** (opt-in) — edges whose ``last_reviewed`` is missing
     or older than ``today - recent_days``.  Reported as ``UnderReviewedEdge``.

Parse-resilience: this module reads YAML dicts directly (``yaml.safe_load``),
NOT through ``EdgesYamlFile.model_validate``, so it works even on fixtures that
fail Pydantic schema validation.
"""

from __future__ import annotations

import logging
import re
import warnings
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

from science_tool.dag.paths import DagPaths
from science_tool.dag.refs import RefResolutionError, _task_exists, validate_ref_entry
from science_tool.dag.schema import RefEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Task parsing (lifted and adapted from mm30's _dag_staleness.py)
# ---------------------------------------------------------------------------

TASK_HEADER_RE = re.compile(r"^## \[(t\d+)\]\s+(.*)$")
COMPLETED_RE = re.compile(r"^- completed:\s+(\d{4}-\d{2}-\d{2})\s*$")
RELATED_RE = re.compile(r"^- related:\s*\[([^\]]*)\]\s*$")


def _parse_task_block(lines: list[str], start: int) -> tuple[dict, int]:
    """Parse one task block starting at ``lines[start]``.

    Returns ``(task_dict, next_start_index)``.
    """
    m = TASK_HEADER_RE.match(lines[start])
    assert m is not None
    tid, title = m.group(1), m.group(2).strip()
    block: dict = {"id": tid, "title": title, "completed": None, "related": []}
    i = start + 1
    while i < len(lines) and not lines[i].startswith("## ["):
        line = lines[i]
        mc = COMPLETED_RE.match(line)
        if mc:
            block["completed"] = datetime.strptime(mc.group(1), "%Y-%m-%d").date()
        mr = RELATED_RE.match(line)
        if mr:
            block["related"] = [x.strip() for x in mr.group(1).split(",") if x.strip()]
        i += 1
    return block, i


def _load_tasks(path: Path) -> dict[str, dict]:
    """Parse all task blocks from a single markdown file."""
    tasks: dict[str, dict] = {}
    if not path.exists():
        return tasks
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        if TASK_HEADER_RE.match(lines[i]):
            block, i = _parse_task_block(lines, i)
            tasks[block["id"]] = block
        else:
            i += 1
    return tasks


def _load_all_tasks(tasks_dir: Path) -> dict[str, dict]:
    """Load tasks from ``tasks/done/*.md`` and ``tasks/active.md``."""
    out: dict[str, dict] = {}
    done_dir = tasks_dir / "done"
    if done_dir.exists():
        for md in sorted(done_dir.glob("*.md")):
            out.update(_load_tasks(md))
    out.update(_load_tasks(tasks_dir / "active.md"))
    return out


# ---------------------------------------------------------------------------
# Hypothesis-from-slug mapping (mm30 specific; heuristic per spec §"Drift rule")
# ---------------------------------------------------------------------------

_SLUG_TO_HYPOTHESES: dict[str, tuple[str, ...]] = {
    "h1-prognosis": ("hypothesis:h1-epigenetic-commitment",),
    "h1-progression": ("hypothesis:h1-epigenetic-commitment",),
    "h2-subtype-architecture": ("hypothesis:h2-cytogenetic-distinct-entities",),
    "h1-h2-bridge": (
        "hypothesis:h1-epigenetic-commitment",
        "hypothesis:h2-cytogenetic-distinct-entities",
    ),
}


def _hypotheses_for_slug(slug: str) -> tuple[str, ...]:
    """Return hypothesis IDs that the DAG slug is associated with.

    Hard-codes the mm30 mapping.  For unrecognised slugs returns an empty
    tuple so drift can still match via source/target node names.
    """
    if slug in _SLUG_TO_HYPOTHESES:
        return _SLUG_TO_HYPOTHESES[slug]
    # Generic fallback: try to map hNNN-* → hypothesis:hNNN-*
    m = re.match(r"^(h\d+)-", slug)
    if m:
        return (f"hypothesis:{slug}",)
    return ()


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateTask:
    """A completed task that may represent unreviewed evidence for an edge."""

    id: str
    completed: date
    related: tuple[str, ...]
    title: str


@dataclass(frozen=True)
class DriftedEdge:
    """An edge for which new potentially-relevant tasks have appeared since its anchor."""

    dag: str
    id: int
    source: str
    target: str
    last_cited_date: date | None
    last_reviewed: date | None
    candidate_drift_tasks: tuple[CandidateTask, ...]


@dataclass(frozen=True)
class UnderReviewedEdge:
    """An edge whose ``last_reviewed`` is missing or older than the recency window."""

    dag: str
    id: int
    last_reviewed: date | None
    age_days: int | None  # None if never reviewed


@dataclass(frozen=True)
class UnpropagatedTask:
    """A recently-completed task that touches a DAG hypothesis but is not cited by any edge."""

    id: str
    completed: date
    related: tuple[str, ...]
    title: str


@dataclass(frozen=True)
class UnresolvedRef:
    """A ref entry in an edge that could not be resolved on disk."""

    dag: str
    edge_id: int
    kind: str
    value: str
    reason: str


@dataclass(frozen=True)
class StalenessReport:
    """Complete staleness report for all DAGs in a project."""

    today: date
    recent_days: int
    drifted_edges: tuple[DriftedEdge, ...]
    under_reviewed_edges: tuple[UnderReviewedEdge, ...]
    unresolved_refs: tuple[UnresolvedRef, ...]
    unpropagated_tasks: tuple[UnpropagatedTask, ...]

    @property
    def has_findings(self) -> bool:
        return bool(self.drifted_edges or self.unpropagated_tasks or self.unresolved_refs)

    def to_json(self) -> dict:
        """Emit a stable JSON schema with all ``date`` fields as ISO strings."""

        def _candidate(c: CandidateTask) -> dict:
            return {
                "id": c.id,
                "completed": c.completed.isoformat(),
                "related": list(c.related),
                "title": c.title,
            }

        def _drifted(d: DriftedEdge) -> dict:
            return {
                "dag": d.dag,
                "id": d.id,
                "source": d.source,
                "target": d.target,
                "last_cited_date": d.last_cited_date.isoformat() if d.last_cited_date else None,
                "last_reviewed": d.last_reviewed.isoformat() if d.last_reviewed else None,
                "candidate_drift_tasks": [_candidate(c) for c in d.candidate_drift_tasks],
            }

        def _under_reviewed(u: UnderReviewedEdge) -> dict:
            return {
                "dag": u.dag,
                "id": u.id,
                "last_reviewed": u.last_reviewed.isoformat() if u.last_reviewed else None,
                "age_days": u.age_days,
            }

        def _unresolved(r: UnresolvedRef) -> dict:
            return {
                "dag": r.dag,
                "edge_id": r.edge_id,
                "kind": r.kind,
                "value": r.value,
                "reason": r.reason,
            }

        def _unpropagated(u: UnpropagatedTask) -> dict:
            return {
                "id": u.id,
                "completed": u.completed.isoformat(),
                "related": list(u.related),
                "title": u.title,
            }

        return {
            "today": self.today.isoformat(),
            "recent_days": self.recent_days,
            "drifted_edges": [_drifted(d) for d in self.drifted_edges],
            "under_reviewed_edges": [_under_reviewed(u) for u in self.under_reviewed_edges],
            "unresolved_refs": [_unresolved(r) for r in self.unresolved_refs],
            "unpropagated_tasks": [_unpropagated(u) for u in self.unpropagated_tasks],
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _edge_cited_task_ids(edge: dict) -> list[str]:
    """Return all task IDs cited in data_support and eliminated_by."""
    ids: list[str] = []
    for support_key in ("data_support", "eliminated_by"):
        for entry in edge.get(support_key) or []:
            if isinstance(entry, dict) and "task" in entry:
                ids.append(str(entry["task"]).strip())
    return ids


def _parse_last_reviewed(edge: dict) -> date | None:
    """Parse edge.last_reviewed as a date, returning None if absent or invalid."""
    raw = edge.get("last_reviewed")
    if raw is None:
        return None
    if isinstance(raw, date):
        return raw
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        logger.warning("Could not parse last_reviewed=%r on edge id=%s", raw, edge.get("id"))
        return None


def _compute_last_cited_date(edge: dict, tasks: dict[str, dict]) -> date | None:
    """Return the max completion date of all cited tasks in data_support + eliminated_by."""
    dates: list[date] = []
    for tid in _edge_cited_task_ids(edge):
        t = tasks.get(tid)
        if t and t.get("completed"):
            dates.append(t["completed"])
    return max(dates) if dates else None


def _task_matches_edge(
    task: dict,
    edge_hypotheses: tuple[str, ...],
    edge_source: str,
    edge_target: str,
    edge_props: set[str],
) -> bool:
    """Return True if the task's related field overlaps with this edge's context."""
    related: list[str] = task.get("related") or []
    for r in related:
        # (a) matches the hypothesis the DAG belongs to
        if r in edge_hypotheses:
            return True
        # (b) matches a proposition cited by the edge
        if r in edge_props:
            return True
        # (c) matches source or target node name via "node:<name>" convention
        if r == f"node:{edge_source}" or r == f"node:{edge_target}":
            return True
        # Also match inquiry: refs that match the DAG slug or hypothesis ids
        if r.startswith("inquiry:"):
            inquiry_id = r[len("inquiry:") :]
            for hyp in edge_hypotheses:
                if inquiry_id in hyp or hyp.endswith(inquiry_id):
                    return True
    return False


def _extract_edge_propositions(edge: dict) -> set[str]:
    """Extract all proposition: refs cited in data_support and lit_support."""
    props: set[str] = set()
    for support_key in ("data_support", "lit_support", "eliminated_by"):
        for entry in edge.get(support_key) or []:
            if isinstance(entry, dict) and "proposition" in entry:
                val = entry["proposition"]
                if val is not None:
                    props.add(f"proposition:{val}")
    return props


def _validate_edge_refs(
    dag: str,
    edge: dict,
    project_root: Path,
) -> list[UnresolvedRef]:
    """Attempt ref resolution for all ref entries in an edge.

    Works on raw YAML dicts.  Tries to construct a ``RefEntry`` for entries
    that have a known kind tag; catches schema errors and ``RefResolutionError``
    and emits ``UnresolvedRef`` records.
    """
    results: list[UnresolvedRef] = []
    edge_id: int = edge.get("id", 0)

    from science_tool.dag.schema import REF_KINDS

    for support_key in ("data_support", "lit_support", "eliminated_by"):
        for entry_dict in edge.get(support_key) or []:
            if not isinstance(entry_dict, dict):
                continue

            # Identify the kind tag from the raw dict (skip null values)
            found_kinds = {k: v for k, v in entry_dict.items() if k in REF_KINDS and v is not None}

            if len(found_kinds) == 0:
                # No resolvable kind tag (e.g. doi=null, or author_year-only)
                # Not an unresolved ref error — schema issue, not resolution issue.
                continue
            if len(found_kinds) > 1:
                # Multiple kind tags — schema error, skip.
                continue

            kind, value = next(iter(found_kinds.items()))
            value_str = str(value)

            # Try to build a RefEntry and validate it.
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    ref_entry = RefEntry.model_validate(entry_dict)
                validate_ref_entry(ref_entry, project_root)
            except RefResolutionError as exc:
                results.append(UnresolvedRef(dag=dag, edge_id=edge_id, kind=kind, value=value_str, reason=str(exc)))
            except Exception:
                # Schema validation failure (e.g. extra kind tags, null doi).
                # Fall back: for task refs, check directly.
                if kind == "task":
                    if not _task_exists(value_str, project_root):
                        results.append(
                            UnresolvedRef(
                                dag=dag,
                                edge_id=edge_id,
                                kind="task",
                                value=value_str,
                                reason=f"task {value_str} not found in tasks/active.md or tasks/done/*.md",
                            )
                        )

    return results


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def check_staleness(
    paths: DagPaths,
    *,
    today: date | None = None,
    recent_days: int = 28,
    include_curation_freshness: bool = False,
) -> StalenessReport:
    """Run the full staleness audit over all DAGs in ``paths``.

    Parameters
    ----------
    paths:
        Resolved project paths from ``DagPaths``.
    today:
        Reference date (defaults to ``date.today()``).
    recent_days:
        Look-back window for unpropagated-task detection (default 28 days).
    include_curation_freshness:
        When True, also populate ``StalenessReport.under_reviewed_edges``.

    Returns
    -------
    StalenessReport
        Frozen report object with all findings.
    """
    if today is None:
        today = date.today()

    project_root = paths.tasks_dir.parent

    # ---- Load tasks -------------------------------------------------------
    all_tasks: dict[str, dict] = _load_all_tasks(paths.tasks_dir)

    # ---- Discover DAG slugs -----------------------------------------------
    if paths.dags is not None:
        slugs = list(paths.dags)
    else:
        slugs = sorted(p.stem.replace(".edges", "") for p in paths.dag_dir.glob("*.edges.yaml"))

    # ---- Per-edge audit ---------------------------------------------------
    all_cited_ids: set[str] = set()
    drifted_edges: list[DriftedEdge] = []
    under_reviewed_edges: list[UnderReviewedEdge] = []
    unresolved_refs: list[UnresolvedRef] = []

    for slug in slugs:
        yaml_path = paths.dag_dir / f"{slug}.edges.yaml"
        if not yaml_path.exists():
            logger.warning("edges.yaml missing for DAG %r; skipping", slug)
            continue

        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
        edges: list[dict] = data.get("edges") or []

        hypotheses = _hypotheses_for_slug(slug)

        for edge in edges:
            if not isinstance(edge, dict):
                continue

            edge_id: int = edge.get("id", 0)
            source: str = str(edge.get("source", ""))
            target: str = str(edge.get("target", ""))

            # Collect all cited task IDs globally
            cited_ids = _edge_cited_task_ids(edge)
            all_cited_ids.update(cited_ids)

            # --- Unresolved refs -------------------------------------------
            unresolved_refs.extend(_validate_edge_refs(slug, edge, project_root))

            # --- Eliminated edges are frozen — skip drift/curation ---------
            if edge.get("edge_status") == "eliminated":
                continue

            # --- Compute anchor date ---------------------------------------
            last_cited_date = _compute_last_cited_date(edge, all_tasks)
            last_reviewed = _parse_last_reviewed(edge)

            anchor: date | None = None
            if last_cited_date is not None and last_reviewed is not None:
                anchor = max(last_cited_date, last_reviewed)
            elif last_cited_date is not None:
                anchor = last_cited_date
            elif last_reviewed is not None:
                anchor = last_reviewed
            # else anchor = None → include all completed tasks as candidates

            # --- Extract propositions cited by this edge -------------------
            edge_props = _extract_edge_propositions(edge)

            # --- Candidate drift tasks ------------------------------------
            candidates: list[CandidateTask] = []
            for tid, task in all_tasks.items():
                completed = task.get("completed")
                if not isinstance(completed, date):
                    continue
                # Strictly newer than anchor (or anchor is None → include all)
                if anchor is not None and completed <= anchor:
                    continue
                if _task_matches_edge(task, hypotheses, source, target, edge_props):
                    candidates.append(
                        CandidateTask(
                            id=tid,
                            completed=completed,
                            related=tuple(task.get("related") or []),
                            title=task.get("title", ""),
                        )
                    )

            if candidates:
                drifted_edges.append(
                    DriftedEdge(
                        dag=slug,
                        id=edge_id,
                        source=source,
                        target=target,
                        last_cited_date=last_cited_date,
                        last_reviewed=last_reviewed,
                        candidate_drift_tasks=tuple(sorted(candidates, key=lambda c: c.completed)),
                    )
                )

            # --- Curation freshness (opt-in) --------------------------------
            if include_curation_freshness:
                if last_reviewed is None:
                    under_reviewed_edges.append(
                        UnderReviewedEdge(dag=slug, id=edge_id, last_reviewed=None, age_days=None)
                    )
                elif (today - last_reviewed).days > recent_days:
                    under_reviewed_edges.append(
                        UnderReviewedEdge(
                            dag=slug,
                            id=edge_id,
                            last_reviewed=last_reviewed,
                            age_days=(today - last_reviewed).days,
                        )
                    )

    # ---- Unpropagated tasks -----------------------------------------------
    recent_cutoff = today - timedelta(days=recent_days)
    unpropagated: list[UnpropagatedTask] = []

    for tid, task in all_tasks.items():
        completed = task.get("completed")
        if not isinstance(completed, date):
            continue
        if completed < recent_cutoff:
            continue
        if tid in all_cited_ids:
            continue
        related: list[str] = task.get("related") or []
        if any(
            r.startswith("hypothesis:") or r.startswith("inquiry:") or r.startswith("proposition:") for r in related
        ):
            unpropagated.append(
                UnpropagatedTask(
                    id=tid,
                    completed=completed,
                    related=tuple(related),
                    title=task.get("title", ""),
                )
            )

    return StalenessReport(
        today=today,
        recent_days=recent_days,
        drifted_edges=tuple(drifted_edges),
        under_reviewed_edges=tuple(under_reviewed_edges),
        unresolved_refs=tuple(unresolved_refs),
        unpropagated_tasks=tuple(unpropagated),
    )
