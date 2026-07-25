"""Project a loaded ProjectSources into the pure `ProjectEvidence` the coverage engine consumes.

This is the only place `provided_capabilities`, `dataset_usage`, `related`, and `skill_loads`
are read off entities. The plan->dataset edge is `dataset_usage` UNION `related: dataset:*`,
resolved through the same ReferenceResolver semantics materialization uses; a commons-owned
dataset is identified by its owner adapter (`entity_source_adapters[id] == "commons-merged"`).
"""

from __future__ import annotations

from collections import defaultdict

from science_model.skill_coverage import EnrollmentStatus
from science_model.skill_coverage.coverage import (
    DatasetUse,
    PlanSkills,
    ProjectEvidence,
    TermUsage,
    UnresolvedRef,
)

from science_tool.datasets.capability_scope import is_valid_scope
from science_tool.datasets.capability_shape import parse_gen3_capabilities
from science_tool.graph.identity_table import build_identity_table
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import ProjectSources

_COMMONS_ADAPTER = "commons-merged"


class SkillCoverageScanError(Exception):
    """A coverage scan cannot proceed (bad registry entry, dangling typed usage, etc.)."""


def _resolve_dataset(ref: str, resolver: ReferenceResolver) -> str | None:
    resolution = resolver.resolve(ref)
    if (
        resolution.status == "resolved"
        and resolution.canonical_id is not None
        and resolution.canonical_id.startswith("dataset:")
    ):
        return resolution.canonical_id
    return None


def _is_dataset_reference(ref: str) -> bool:
    parts = ref.split(":", 2)
    return parts[0] == "dataset" or (
        len(parts) == 3 and parts[1] == "dataset"
    )


def project_evidence(project: str, sources: ProjectSources) -> ProjectEvidence:
    resolver = ReferenceResolver.from_entities(
        sources.entities,
        manual_aliases=sources.manual_aliases,
        archive_alias_tokens=sources.archive_alias_tokens,
        identity_table=build_identity_table(sources),
    )
    adapters = sources.entity_source_adapters

    # dataset canonical_id -> (terms, owned, scoped)
    dataset_terms: dict[str, frozenset[str]] = {}
    dataset_owned: dict[str, bool] = {}
    dataset_scoped: dict[str, bool] = {}
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        extra = entity.model_extra or {}
        raw_caps = extra.get("provided_capabilities")
        terms = (
            frozenset(cap.data_product for cap in parse_gen3_capabilities(raw_caps))
            if raw_caps else frozenset()
        )
        dataset_terms[entity.canonical_id] = terms
        dataset_owned[entity.canonical_id] = adapters.get(entity.canonical_id) != _COMMONS_ADAPTER
        dataset_scoped[entity.canonical_id] = is_valid_scope(
            extra.get("capability_scope")
        )

    loaded: dict[str, list[str]] = defaultdict(list)
    for record in sources.skill_loads:
        loaded[record.plan_id].append(record.canonical_skill_id)

    term_usages: list[TermUsage] = []
    untagged_usages: list[DatasetUse] = []
    unresolved: list[UnresolvedRef] = []

    for entity in sources.entities:
        if entity.kind != "plan":
            continue
        plan_ref = entity.canonical_id
        edges: set[str] = set()
        # typed dataset_usage: a dangling ref is a hard error
        for usage in getattr(entity, "dataset_usage", None) or []:
            resolved = _resolve_dataset(str(usage.ref), resolver)
            if resolved is None:
                raise SkillCoverageScanError(
                    f"{project}: plan {plan_ref} dataset_usage ref {usage.ref!r} does not resolve"
                )
            edges.add(resolved)
        # related dataset refs: a dangling ref is a reported diagnostic, not an abort
        for raw in entity.related or []:
            if not _is_dataset_reference(raw):
                continue
            resolved = _resolve_dataset(raw, resolver)
            if resolved is None:
                unresolved.append(UnresolvedRef(plan_ref, raw))
                continue
            edges.add(resolved)

        for dataset_ref in edges:
            terms = dataset_terms.get(dataset_ref)
            if terms is None:
                raise SkillCoverageScanError(
                    f"{project}: plan {plan_ref} references {dataset_ref!r}, "
                    "which resolved but is not a loaded dataset entity"
                )
            if terms:
                for term in terms:
                    term_usages.append(
                        TermUsage(plan_ref, dataset_ref, term, dataset_owned[dataset_ref])
                    )
            elif dataset_owned[dataset_ref] and not dataset_scoped[dataset_ref]:
                untagged_usages.append(DatasetUse(plan_ref, dataset_ref))

    plan_loaded_skills = tuple(
        PlanSkills(plan_ref, tuple(sorted(set(skill_ids))))
        for plan_ref, skill_ids in loaded.items()
    )

    return ProjectEvidence(
        project=project,
        enrollment=EnrollmentStatus.ENROLLED,
        term_usages=tuple(term_usages),
        untagged_usages=tuple(untagged_usages),
        plan_loaded_skills=plan_loaded_skills,
        unresolved_related_refs=tuple(unresolved),
    )
