"""Pure types and canonical serialization for skill-coverage reports.

No I/O and no corpus/graph access: ``science_tool`` projects entities into
``ProjectEvidence`` and calls the coverage engine. ``science_model`` never
imports ``science_tool``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from science_model.skill_coverage import EnrollmentStatus


class SkillCoverageError(ValueError):
    """A structural violation in the coverage inputs."""


@dataclass(frozen=True, slots=True)
class TermUsage:
    plan_ref: str
    dataset_ref: str
    term: str
    owned: bool


@dataclass(frozen=True, slots=True)
class DatasetUse:
    plan_ref: str
    dataset_ref: str


@dataclass(frozen=True, slots=True)
class PlanSkills:
    plan_ref: str
    skill_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class UnresolvedRef:
    plan_ref: str
    ref: str


@dataclass(frozen=True, slots=True)
class ProjectEvidence:
    project: str
    enrollment: "EnrollmentStatus | Literal['undeclared']"
    term_usages: tuple[TermUsage, ...] = ()
    untagged_usages: tuple[DatasetUse, ...] = ()
    plan_loaded_skills: tuple[PlanSkills, ...] = ()
    unresolved_related_refs: tuple[UnresolvedRef, ...] = ()

    def __post_init__(self) -> None:
        if self.enrollment != "enrolled" and (
            self.term_usages
            or self.untagged_usages
            or self.plan_loaded_skills
            or self.unresolved_related_refs
        ):
            raise SkillCoverageError(
                f"{self.project}: a non-enrolled ProjectEvidence must carry no facts"
            )


@dataclass(frozen=True, slots=True)
class EvidencePair:
    plan_ref: str
    dataset_ref: str

    def to_dict(self) -> dict[str, str]:
        return {"plan_ref": self.plan_ref, "dataset_ref": self.dataset_ref}


@dataclass(frozen=True, slots=True)
class EvidenceTriple:
    project: str
    plan_ref: str
    dataset_ref: str

    def to_dict(self) -> dict[str, str]:
        return {
            "project": self.project,
            "plan_ref": self.plan_ref,
            "dataset_ref": self.dataset_ref,
        }


@dataclass(frozen=True, slots=True)
class OutOfDomainResult:
    project: str

    def to_dict(self) -> dict[str, str]:
        return {"state": "out-of-domain", "project": self.project}


@dataclass(frozen=True, slots=True)
class UndeclaredDomainResult:
    project: str

    def to_dict(self) -> dict[str, str]:
        return {"state": "undeclared-domain", "project": self.project}


@dataclass(frozen=True, slots=True)
class UnmappedOccurrence:
    project: str
    dataset_ref: str
    evidence_refs: tuple[EvidencePair, ...]
    observation_level: str = "analysis-usage"

    def to_dict(self) -> dict[str, object]:
        return {
            "state": "unmapped",
            "project": self.project,
            "dataset_ref": self.dataset_ref,
            "observation_level": self.observation_level,
            "evidence_refs": [evidence.to_dict() for evidence in self.evidence_refs],
        }


@dataclass(frozen=True, slots=True)
class UncoveredOccurrence:
    project: str
    term: str
    evidence_refs: tuple[EvidencePair, ...]
    observation_level: str = "analysis-usage"

    def to_dict(self) -> dict[str, object]:
        return {
            "state": "uncovered",
            "project": self.project,
            "term": self.term,
            "observation_level": self.observation_level,
            "evidence_refs": [evidence.to_dict() for evidence in self.evidence_refs],
        }


@dataclass(frozen=True, slots=True)
class CoveredNotLoadedOccurrence:
    project: str
    term: str
    available_skill_ids: tuple[str, ...]
    evidence_refs: tuple[EvidencePair, ...]
    observation_level: str = "analysis-usage"

    def to_dict(self) -> dict[str, object]:
        return {
            "state": "covered-not-loaded",
            "project": self.project,
            "term": self.term,
            "observation_level": self.observation_level,
            "available_skill_ids": list(self.available_skill_ids),
            "evidence_refs": [evidence.to_dict() for evidence in self.evidence_refs],
        }


Occurrence = (
    OutOfDomainResult
    | UndeclaredDomainResult
    | UnmappedOccurrence
    | UncoveredOccurrence
    | CoveredNotLoadedOccurrence
)


@dataclass(frozen=True, slots=True)
class SkillReferenceDiagnostic:
    project: str
    plan_ref: str
    skill_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "project": self.project,
            "plan_ref": self.plan_ref,
            "skill_id": self.skill_id,
        }


@dataclass(frozen=True, slots=True)
class DatasetReferenceDiagnostic:
    project: str
    plan_ref: str
    ref: str

    def to_dict(self) -> dict[str, str]:
        return {"project": self.project, "plan_ref": self.plan_ref, "ref": self.ref}


@dataclass(frozen=True, slots=True)
class Candidate:
    proposed_scope: str
    likely_archetype: str
    score: float
    evidence: tuple[EvidenceTriple, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "proposed_scope": self.proposed_scope,
            "likely_archetype": self.likely_archetype,
            "score": self.score,
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True, slots=True)
class ReportScope:
    mode: str
    project: str | None = None

    def to_dict(self) -> dict[str, str]:
        result = {"mode": self.mode}
        if self.project is not None:
            result["project"] = self.project
        return result


@dataclass(frozen=True, slots=True)
class SkippedProject:
    path: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"path": self.path, "reason": self.reason}


def _occurrence_sort_key(occurrence: Occurrence) -> tuple[object, ...]:
    evidence_pairs = tuple(
        sorted(
            (evidence.plan_ref, evidence.dataset_ref)
            for evidence in getattr(occurrence, "evidence_refs", ())
        )
    )
    return (
        occurrence.to_dict()["state"],
        occurrence.project,
        getattr(occurrence, "term", "") or "",
        getattr(occurrence, "dataset_ref", "") or "",
        evidence_pairs,
    )


def _candidate_sort_key(candidate: Candidate) -> tuple[object, ...]:
    evidence = tuple(
        sorted(
            (item.project, item.plan_ref, item.dataset_ref) for item in candidate.evidence
        )
    )
    return (
        -candidate.score,
        candidate.proposed_scope,
        candidate.likely_archetype,
        evidence,
    )


@dataclass(frozen=True, slots=True)
class CoverageReport:
    scope: ReportScope
    coverage_occurrences: tuple[Occurrence, ...]
    skill_reference_diagnostics: tuple[SkillReferenceDiagnostic, ...]
    dataset_reference_diagnostics: tuple[DatasetReferenceDiagnostic, ...]
    candidates: tuple[Candidate, ...]
    skipped_projects: tuple[SkippedProject, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": self.scope.to_dict(),
            "coverage_occurrences": [
                occurrence.to_dict()
                for occurrence in sorted(
                    self.coverage_occurrences, key=_occurrence_sort_key
                )
            ],
            "skill_reference_diagnostics": [
                diagnostic.to_dict()
                for diagnostic in sorted(
                    self.skill_reference_diagnostics,
                    key=lambda diagnostic: (
                        diagnostic.project,
                        diagnostic.plan_ref,
                        diagnostic.skill_id,
                    ),
                )
            ],
            "dataset_reference_diagnostics": [
                diagnostic.to_dict()
                for diagnostic in sorted(
                    self.dataset_reference_diagnostics,
                    key=lambda diagnostic: (
                        diagnostic.project,
                        diagnostic.plan_ref,
                        diagnostic.ref,
                    ),
                )
            ],
            "candidates": [
                candidate.to_dict()
                for candidate in sorted(
                    self.candidates,
                    key=_candidate_sort_key,
                )
            ],
            "skipped_projects": [
                skipped.to_dict()
                for skipped in sorted(self.skipped_projects, key=lambda skipped: skipped.path)
            ],
        }


def serialize_coverage_report(report: CoverageReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"
