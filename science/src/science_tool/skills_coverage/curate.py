"""Correlate coverage candidates against feedback entries into a filing plan."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from science_tool.feedback import normalize_target

if TYPE_CHECKING:
    from science_model.skill_coverage.coverage import Candidate, CoverageReport
    from science_tool.feedback import FeedbackEntry

CONCERN = "tooling"
CATEGORY = "gap"
PROJECT = "science"
RESOLVED_STATUSES = ("addressed", "deferred", "wontfix")


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
