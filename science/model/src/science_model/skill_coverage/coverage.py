"""Pure types and canonical serialization for skill-coverage reports.

No I/O and no corpus/graph access: ``science_tool`` projects entities into
``ProjectEvidence`` and calls the coverage engine. ``science_model`` never
imports ``science_tool``.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from science_model.skill_coverage.enrollment import (
    ENROLLMENT_STATUSES,
    EnrollmentStatus,
)
from science_model.skill_coverage.overlay import LeafSkill, SkillOverlay

if TYPE_CHECKING:
    from science_model.data_products import DataProductCatalog


class SkillCoverageError(ValueError):
    """A structural violation in the coverage inputs."""


_UNDECLARED_ENROLLMENT = "undeclared"
_VALID_ENROLLMENTS = ENROLLMENT_STATUSES | frozenset({_UNDECLARED_ENROLLMENT})


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
        if self.enrollment not in _VALID_ENROLLMENTS:
            raise SkillCoverageError(
                f"{self.project}: unknown enrollment {self.enrollment!r}"
            )
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


def _covering_leaf_ids(term: str, overlay: SkillOverlay) -> set[str]:
    return {skill.id for skill in overlay if isinstance(skill, LeafSkill) and term in skill.covers}


def _infer_archetype(
    term: str, overlay: SkillOverlay, catalog: "DataProductCatalog"
) -> str:
    entry = catalog.by_id.get(term)
    if entry is None or not entry.broader:
        return "indeterminate"
    parents = set(entry.broader)
    sibling_ids = {
        catalog_term.id
        for catalog_term in catalog.terms
        if catalog_term.id != term and (set(catalog_term.broader) & parents)
    }
    archetypes = {
        skill.archetype
        for skill in overlay
        if isinstance(skill, LeafSkill) and any(covered in sibling_ids for covered in skill.covers)
    }
    if len(archetypes) == 1:
        return next(iter(archetypes))
    return "indeterminate"


def _build_candidates(
    uncovered: dict[str, list[EvidenceTriple]],
    overlay: SkillOverlay,
    catalog: "DataProductCatalog",
) -> tuple[Candidate, ...]:
    candidates: list[Candidate] = []
    for term, triples in uncovered.items():
        unique = sorted({(triple.project, triple.plan_ref, triple.dataset_ref) for triple in triples})
        n_occurrences = len(unique)
        n_projects = len({project for project, _, _ in unique})
        score = round(1 - 1 / (1 + n_occurrences + (n_projects - 1)), 3)
        evidence = tuple(EvidenceTriple(project, plan_ref, dataset_ref) for project, plan_ref, dataset_ref in unique)
        candidates.append(Candidate(
            proposed_scope=term,
            likely_archetype=_infer_archetype(term, overlay, catalog),
            score=score,
            evidence=evidence,
        ))
    return tuple(candidates)


def compute_coverage(
    projects: list[ProjectEvidence],
    overlay: SkillOverlay,
    catalog: "DataProductCatalog",
    *,
    scope: ReportScope,
    skipped_projects: tuple[SkippedProject, ...] = (),
) -> CoverageReport:
    catalog_ids = catalog.by_id
    occurrences: list[Occurrence] = []
    skill_diags: list[SkillReferenceDiagnostic] = []
    dataset_diags: list[DatasetReferenceDiagnostic] = []
    uncovered: dict[str, list[EvidenceTriple]] = defaultdict(list)

    for evidence in projects:
        if evidence.enrollment == "out-of-domain":
            occurrences.append(OutOfDomainResult(evidence.project))
            continue
        if evidence.enrollment == "undeclared":
            occurrences.append(UndeclaredDomainResult(evidence.project))
            continue

        for unresolved in evidence.unresolved_related_refs:
            dataset_diags.append(
                DatasetReferenceDiagnostic(evidence.project, unresolved.plan_ref, unresolved.ref)
            )
        unmapped_by_dataset: dict[str, set[tuple[str, str]]] = defaultdict(set)
        for untagged in evidence.untagged_usages:
            unmapped_by_dataset[untagged.dataset_ref].add(
                (untagged.plan_ref, untagged.dataset_ref)
            )
        for dataset_ref in sorted(unmapped_by_dataset):
            occurrences.append(
                UnmappedOccurrence(
                    evidence.project,
                    dataset_ref,
                    tuple(
                        EvidencePair(plan_ref, evidence_dataset_ref)
                        for plan_ref, evidence_dataset_ref in sorted(
                            unmapped_by_dataset[dataset_ref]
                        )
                    ),
                )
            )
        for plan_skills in evidence.plan_loaded_skills:
            for skill_id in plan_skills.skill_ids:
                if overlay.get(skill_id) is None:
                    skill_diags.append(
                        SkillReferenceDiagnostic(evidence.project, plan_skills.plan_ref, skill_id)
                    )
        loaded_by_plan = {
            plan_skills.plan_ref: set(plan_skills.skill_ids)
            for plan_skills in evidence.plan_loaded_skills
        }

        by_term: dict[str, list[TermUsage]] = defaultdict(list)
        for usage in evidence.term_usages:
            if usage.term not in catalog_ids:
                if usage.owned:
                    raise SkillCoverageError(
                        f"{evidence.project}: dataset {usage.dataset_ref} declares off-catalog "
                        f"data_product {usage.term!r}"
                    )
                continue
            by_term[usage.term].append(usage)

        for term, usages in by_term.items():
            covering = _covering_leaf_ids(term, overlay)
            all_pairs = tuple(EvidencePair(plan_ref, dataset_ref) for plan_ref, dataset_ref in sorted(
                {(usage.plan_ref, usage.dataset_ref) for usage in usages}
            ))
            if not covering:
                occurrences.append(UncoveredOccurrence(evidence.project, term, all_pairs))
                for usage in usages:
                    uncovered[term].append(
                        EvidenceTriple(evidence.project, usage.plan_ref, usage.dataset_ref)
                    )
                continue
            plans_touching = {usage.plan_ref for usage in usages}
            not_loaded = {
                plan_ref
                for plan_ref in plans_touching
                if not (loaded_by_plan.get(plan_ref, set()) & covering)
            }
            if not_loaded:
                not_loaded_pairs = tuple(
                    EvidencePair(plan_ref, dataset_ref)
                    for plan_ref, dataset_ref in sorted(
                        {
                            (usage.plan_ref, usage.dataset_ref)
                            for usage in usages
                            if usage.plan_ref in not_loaded
                        }
                    )
                )
                occurrences.append(CoveredNotLoadedOccurrence(
                    evidence.project,
                    term,
                    tuple(sorted(covering)),
                    not_loaded_pairs,
                ))

    return CoverageReport(
        scope=scope,
        coverage_occurrences=tuple(occurrences),
        skill_reference_diagnostics=tuple(skill_diags),
        dataset_reference_diagnostics=tuple(dataset_diags),
        candidates=_build_candidates(uncovered, overlay, catalog),
        skipped_projects=skipped_projects,
    )
