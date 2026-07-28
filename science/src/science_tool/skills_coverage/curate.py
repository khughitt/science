"""Correlate coverage candidates against feedback entries into a filing plan."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import TYPE_CHECKING

from science_tool.feedback import (
    FeedbackEntry,
    load_entry,
    next_feedback_id,
    normalize_target,
    record_occurrence,
    save_entry,
)

if TYPE_CHECKING:
    from science_model.skill_coverage.coverage import Candidate, CoverageReport

CONCERN = "tooling"
CATEGORY = "gap"
PROJECT = "science"
RESOLVED_STATUSES = ("addressed", "deferred", "wontfix")
VALID_DISPOSITIONS = ("new", "recur", "skip", "skip-addressed-conflict")


def target_for(term: str) -> str:
    return f"skill-coverage:{term}"


class CurateConflictError(Exception):
    """More than one open feedback entry shares a term."""

    def __init__(self, term: str, ids: list[str]) -> None:
        self.term = term
        self.ids = ids
        super().__init__(
            f"{term}: {len(ids)} open skill-coverage entries ({', '.join(ids)}); "
            "merge them before curating"
        )


class CurateStatusError(Exception):
    """A matched feedback entry has an unknown status."""

    def __init__(self, term: str, offenders: list[tuple[str, str]]) -> None:
        self.term = term
        self.offenders = offenders
        detail = ", ".join(f"{entry_id}={status!r}" for entry_id, status in offenders)
        super().__init__(
            f"{term}: feedback entries with unknown status ({detail}); "
            f"expected open or one of {', '.join(RESOLVED_STATUSES)}"
        )


class CurateSelectionError(Exception):
    """A --term value names no row in the current plan."""

    def __init__(self, unknown: list[str]) -> None:
        self.unknown = unknown
        super().__init__(f"--term names no candidate in the current plan: {', '.join(unknown)}")


class CurateDispositionError(ValueError):
    """A curate plan row has an unknown disposition."""

    def __init__(self, offenders: list[tuple[str, str]]) -> None:
        self.offenders = offenders
        detail = ", ".join(
            f"{term}={disposition!r}" for term, disposition in offenders
        )
        super().__init__(
            f"unknown disposition in curate plan ({detail}); expected one of "
            f"{', '.join(VALID_DISPOSITIONS)}"
        )


@dataclass(frozen=True, slots=True)
class ExistingMatch:
    id: str
    status: str

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "status": self.status}


@dataclass
class CurateRow:
    term: str
    disposition: str
    score: float
    likely_archetype: str
    n_plans: int
    n_projects: int
    existing: tuple[ExistingMatch, ...]
    applied: bool | None = None
    result: dict[str, object] | None = None
    candidate: Candidate | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "term": self.term,
            "disposition": self.disposition,
            "score": self.score,
            "likely_archetype": self.likely_archetype,
            "n_plans": self.n_plans,
            "n_projects": self.n_projects,
            "existing": [match.to_dict() for match in self.existing],
        }
        if self.applied is not None:
            result["applied"] = self.applied
        if self.result is not None:
            result["result"] = self.result
        return result


@dataclass(frozen=True, slots=True)
class CurateContext:
    covered_not_loaded: int
    unmapped: int
    skipped_projects: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "covered_not_loaded": self.covered_not_loaded,
            "unmapped": self.unmapped,
            "skipped_projects": list(self.skipped_projects),
        }


@dataclass
class CuratePlan:
    mode: str
    scope: dict[str, object]
    rows: list[CurateRow]
    context: CurateContext

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode,
            "scope": self.scope,
            "rows": [row.to_dict() for row in self.rows],
            "context": self.context.to_dict(),
        }


def coverage_context(report: CoverageReport) -> CurateContext:
    covered_not_loaded = sum(
        occurrence.to_dict().get("state") == "covered-not-loaded"
        for occurrence in report.coverage_occurrences
    )
    unmapped = sum(
        occurrence.to_dict().get("state") == "unmapped"
        for occurrence in report.coverage_occurrences
    )
    return CurateContext(
        covered_not_loaded=covered_not_loaded,
        unmapped=unmapped,
        skipped_projects=tuple(project.path for project in report.skipped_projects),
    )


def build_curate_plan(
    candidates: Sequence[Candidate],
    entries: Sequence[FeedbackEntry],
    context: CurateContext,
    scope: Mapping[str, object],
) -> CuratePlan:
    entries_by_target: dict[str, list[FeedbackEntry]] = defaultdict(list)
    for entry in entries:
        if entry.concern == CONCERN:
            entries_by_target[normalize_target(entry.target)].append(entry)

    rows: list[CurateRow] = []
    for candidate in sorted(candidates, key=lambda candidate: (-candidate.score, candidate.proposed_scope)):
        term = candidate.proposed_scope
        matches = entries_by_target.get(normalize_target(target_for(term)), [])
        open_matches = [match for match in matches if match.status == "open"]
        resolved_matches = [match for match in matches if match.status in RESOLVED_STATUSES]
        unknown_matches = [
            match
            for match in matches
            if match.status != "open" and match.status not in RESOLVED_STATUSES
        ]
        if unknown_matches:
            raise CurateStatusError(
                term, sorted((match.id, match.status) for match in unknown_matches)
            )
        if len(open_matches) > 1:
            raise CurateConflictError(term, sorted(match.id for match in open_matches))

        if open_matches:
            disposition = "recur"
        elif any(match.status == "addressed" for match in resolved_matches):
            disposition = "skip-addressed-conflict"
        elif resolved_matches:
            disposition = "skip"
        else:
            disposition = "new"

        rows.append(
            CurateRow(
                term=term,
                disposition=disposition,
                score=candidate.score,
                likely_archetype=candidate.likely_archetype,
                n_plans=len({(evidence.project, evidence.plan_ref) for evidence in candidate.evidence}),
                n_projects=len({evidence.project for evidence in candidate.evidence}),
                existing=tuple(
                    ExistingMatch(match.id, match.status)
                    for match in sorted(matches, key=lambda match: match.id)
                ),
                candidate=candidate,
            )
        )
    return CuratePlan(mode="report", scope=dict(scope), rows=rows, context=context)


def _summary(row: CurateRow) -> str:
    return (
        f"skill corpus lacks coverage for {row.term} "
        f"({row.n_plans} plans / {row.n_projects} projects)"
    )


def _detail(row: CurateRow) -> str:
    cand = row.candidate
    assert cand is not None  # rows created by build_curate_plan always carry their candidate
    lines = [
        f"score: {cand.score}",
        f"likely_archetype: {cand.likely_archetype}",
        "evidence:",
    ]
    for triple in cand.evidence:
        lines.append(f"  - {triple.project} / {triple.plan_ref} / {triple.dataset_ref}")
    return "\n".join(lines)


def _open_id(row: CurateRow) -> str:
    return next(match.id for match in row.existing if match.status == "open")


def apply_plan(
    plan: CuratePlan,
    feedback_dir: Path,
    *,
    today: str,
    selected_terms: set[str] | None = None,
) -> CuratePlan:
    invalid_dispositions = sorted(
        (row.term, row.disposition)
        for row in plan.rows
        if row.disposition not in VALID_DISPOSITIONS
    )
    if invalid_dispositions:
        raise CurateDispositionError(invalid_dispositions)

    if selected_terms is not None:
        unknown = sorted(selected_terms - {row.term for row in plan.rows})
        if unknown:
            raise CurateSelectionError(unknown)

    plan.mode = "apply"
    for row in plan.rows:
        if row.disposition in ("skip", "skip-addressed-conflict"):
            row.applied = False
            continue
        if selected_terms is not None and row.term not in selected_terms:
            row.applied = False
            continue
        if row.disposition == "recur":
            entry = load_entry(feedback_dir, _open_id(row))
            record_occurrence(
                entry,
                date=today,
                project=PROJECT,
                category=CATEGORY,
                detail=_detail(row),
            )
            save_entry(feedback_dir, entry)
            row.result = {
                "action": "recurred",
                "id": entry.id,
                "recurrence_after": entry.recurrence,
            }
        elif row.disposition == "new":
            entry = FeedbackEntry(
                id=next_feedback_id(feedback_dir, today),
                created=today,
                project=PROJECT,
                target=target_for(row.term),
                category=CATEGORY,
                summary=_summary(row),
                detail=_detail(row),
                concern=CONCERN,
            )
            save_entry(feedback_dir, entry)
            row.result = {
                "action": "created",
                "id": entry.id,
                "recurrence_after": entry.recurrence,
            }
        else:
            raise CurateDispositionError([(row.term, row.disposition)])
        row.applied = True
    return plan


def serialize_curate_plan(plan: CuratePlan, fmt: str) -> str:
    if fmt == "json":
        return json.dumps(plan.to_dict(), indent=2, sort_keys=True) + "\n"
    return _render_text(plan)


def _render_text(plan: CuratePlan) -> str:
    header = f"skill-coverage curate ({plan.mode}) — scope {plan.scope.get('mode', '?')}"
    project = plan.scope.get("project")
    if project:
        header += f" · project {project}"
    lines = [header]
    if not plan.rows:
        lines.append("  no uncovered gaps")
    for row in plan.rows:
        tag = row.disposition
        if row.applied is not None:
            tag += " [applied]" if row.applied else " [not applied]"
        line = (
            f"  {tag}: {row.term}  [{row.likely_archetype}]  score={row.score}  "
            f"{row.n_plans} plans / {row.n_projects} projects"
        )
        if row.existing:
            line += "  existing=" + ",".join(f"{m.id}:{m.status}" for m in row.existing)
        if row.result is not None:
            line += f"  -> {row.result}"
        lines.append(line)
    ctx = plan.context
    lines.append(f"context: covered-not-loaded: {ctx.covered_not_loaded}  unmapped: {ctx.unmapped}")
    if ctx.skipped_projects:
        lines.append("  skipped: " + ", ".join(ctx.skipped_projects))
    return "\n".join(lines) + "\n"
