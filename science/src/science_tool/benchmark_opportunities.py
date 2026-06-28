"""Read-only benchmark opportunity reports."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, NotRequired, TypedDict

from science_tool.benchmark_catalog import benchmark_sources
from science_tool.dataset_prioritize import readiness_weight
from science_tool.datasets.semantics import dataset_class_for
from science_tool.entities import (
    load_markdown_entities,
    numeric_variants,
    parse_markdown_entity_file,
    shortform_for_kind,
)

_TOKEN_RE = re.compile(r"[A-Za-z0-9:_-]+")
_SYNONYMS = {
    "intervention": "perturbation",
    "single-cell": "single-cell-rna-seq",
    "transcriptomics": "rna-seq",
}

HIGH_VALUE_SIGNAL_POINTS = {
    "perturbation": 10,
    "time-series": 10,
    "longitudinal": 8,
    "cross-context-generalization": 7,
    "multi-omic": 7,
}

HIGH_VALUE_MODALITY_POINTS = {
    "proteomics": 7,
    "spatial": 6,
    "multimodal": 6,
    "perturbation": 4,
    "single-cell-rna-seq": 4,
}

HIGH_VALUE_SIGNALS = frozenset(HIGH_VALUE_SIGNAL_POINTS)
HIGH_VALUE_MODALITIES = frozenset(HIGH_VALUE_MODALITY_POINTS)
GAP_MODALITIES = ("proteomics", "spatial", "multimodal")
GAP_SIGNAL_TYPES = ("perturbation", "time-series", "cross-context-generalization")
GAP_FACETS = frozenset((*GAP_MODALITIES, *GAP_SIGNAL_TYPES))
BENCHMARK_GAP_HINT_FACETS = (
    "proteomics",
    "spatial",
    "multimodal",
    "perturbation",
    "time-series",
    "cross-context-generalization",
    "longitudinal",
    "multi-omic",
    "single-cell-rna-seq",
)
BENCHMARK_GAP_HINT_FACET_SET = frozenset(BENCHMARK_GAP_HINT_FACETS)
BROAD_NON_SCOREABLE_FACETS = frozenset({"biology", "cancer", "varies"})
ENTITY_SUPPRESSED_TOKENS = frozenset(
    {
        "claim",
        "statement",
        "summary",
        "question",
        "hypothesis",
        "proposition",
    }
)
KIND_SIGNAL_RULES = {
    "perturbation": ("perturbation-response", 10),
    "dynamic": ("time-series", 8),
    "temporal": ("time-series", 8),
    "spatial": ("static-association", 5),
    "proteomics": ("mechanism-discrimination", 5),
}
_ENTITY_KINDS = ("question", "hypothesis", "proposition")
_STOP_TOKENS = {
    "analysis",
    "cell",
    "data",
    "dataset",
    "evidence",
    "model",
    "result",
    "response",
}


def _normalize_token(token: str) -> str:
    token = token.lower().strip()
    return _SYNONYMS.get(token, token)


def _normalized_values(values: list[str]) -> list[str]:
    return [_normalize_token(value) for value in values]


@dataclass(frozen=True)
class OpportunityTask:
    id: str
    canonical_task_id: str
    task_type: str
    prediction_target: str
    held_out_unit: str
    metric: str
    baseline: str
    ground_truth_type: str
    ground_truth_description: str
    prose: list[str]


@dataclass(frozen=True)
class OpportunityDataset:
    id: str
    title: str
    scope: str
    dataset_class: str
    frontmatter: Mapping[str, object]
    domains: list[str]
    modalities: list[str]
    signal_types: list[str]
    benchmark_kinds: list[str]
    source_datasets: list[str]
    related_beliefs: list[str]
    notes: list[str]
    limitations: list[str]
    tasks: list[OpportunityTask]


@dataclass(frozen=True)
class Score:
    total: int
    components: dict[str, int]
    notes: list[str]


@dataclass(frozen=True)
class ProjectBenchmarkEntity:
    id: str
    kind: str
    title: str
    content_preview: str
    frontmatter: Mapping[str, object]
    tokens: frozenset[str]
    id_tokens: frozenset[str]


@dataclass(frozen=True)
class DatasetOpportunityContext:
    dataset: OpportunityDataset
    baseline: Score
    readiness_penalty: int
    controlled_facet_tokens: frozenset[str]
    scoreable_facet_tokens: frozenset[str]
    prose_tokens: frozenset[str]
    related_belief_tokens: frozenset[str]


@dataclass(frozen=True)
class TokenEvidence:
    kept: frozenset[str]
    stop: frozenset[str]
    broad: frozenset[str]
    short: frozenset[str]


class OpportunityScoreComponents(TypedDict):
    baseline: dict[str, int]
    relative: dict[str, int]


class OpportunityRow(TypedDict):
    entity_id: str
    entity_title: str
    benchmark_id: str
    benchmark_title: str
    task_id: str | None
    match_reasons: list[str]
    benchmark_kinds: list[str]
    signal_types: list[str]
    modalities: list[str]
    baseline_score: int
    relative_score: int
    score_components: OpportunityScoreComponents
    score_notes: list[str]


class UnmappedBenchmarkRow(TypedDict):
    benchmark_id: str
    benchmark_title: str
    baseline_score: int
    unmapped_facets: list[str]


class CoverageGapRow(TypedDict):
    entity_id: str
    missing_modalities: list[str]
    missing_signal_types: list[str]
    reason: str


class UnmappedProjectEntityRow(TypedDict):
    entity_id: str
    entity_title: str
    observed_tokens: list[str]


class DroppedTokenPayload(TypedDict):
    stop: dict[str, list[str]]
    broad_entity: dict[str, list[str]]
    broad_dataset_facet: dict[str, list[str]]
    short: dict[str, list[str]]


class UnmatchedTokenPayload(TypedDict):
    entities: dict[str, list[str]]
    benchmarks: dict[str, list[str]]


class CalibrationMatchEvidence(TypedDict):
    entity_id: str
    benchmark_id: str
    task_id: str | None
    id_overlap: list[str]
    facet_overlap: list[str]
    score_components: OpportunityScoreComponents


class CalibrationPayload(TypedDict):
    enabled: bool
    stop_tokens: NotRequired[list[str]]
    excluded_benchmark_prose_tokens: NotRequired[dict[str, list[str]]]
    entity_tokens: NotRequired[dict[str, list[str]]]
    benchmark_controlled_facet_tokens: NotRequired[dict[str, list[str]]]
    dropped_tokens: NotRequired[DroppedTokenPayload]
    matched_token_evidence: NotRequired[list[CalibrationMatchEvidence]]
    unmatched_tokens: NotRequired[UnmatchedTokenPayload]


class OpportunityReport(TypedDict):
    matched_opportunities: list[OpportunityRow]
    coverage_gaps: list[CoverageGapRow]
    available_unmapped_benchmarks: list[UnmappedBenchmarkRow]
    unmapped_project_entities: list[UnmappedProjectEntityRow]
    calibration: CalibrationPayload
    commons_notice: str | None


WEAK_RELATIVE_SCORE_THRESHOLD = 15
GapLevel = Literal["uncovered", "weak", "missing-facet"]


class GapCurrentMatchRow(TypedDict):
    benchmark_id: str
    task_id: str | None
    relative_score: int
    baseline_score: int


class GapCandidateBenchmarkRow(TypedDict):
    benchmark_id: str
    benchmark_title: str
    baseline_score: int
    matched_missing_facets: list[str]


class BenchmarkGapRow(TypedDict):
    entity_id: str
    entity_title: str
    gap_level: GapLevel
    missing_modalities: list[str]
    missing_signal_types: list[str]
    current_matches: list[GapCurrentMatchRow]
    candidate_benchmarks: list[GapCandidateBenchmarkRow]
    suggested_search_facets: list[str]
    reason: str


class BenchmarkGapSummary(TypedDict):
    entities_total: int
    entities_with_gaps: int
    uncovered_entities: int
    weakly_covered_entities: int
    missing_facet_entities: int


class BenchmarkGapReport(TypedDict):
    benchmark_gaps: list[BenchmarkGapRow]
    summary: BenchmarkGapSummary
    commons_notice: str | None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _task_from_mapping(dataset_id: str, task: Mapping[str, object]) -> OpportunityTask | None:
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        return None
    ground_truth = task.get("ground_truth")
    gt_type = ""
    gt_description = ""
    if isinstance(ground_truth, Mapping):
        gt_type = str(ground_truth.get("type") or "")
        gt_description = str(ground_truth.get("description") or "")
    prose = [
        value
        for value in (
            str(task.get("task_type") or ""),
            str(task.get("prediction_target") or ""),
            str(task.get("held_out_unit") or ""),
            str(task.get("metric") or ""),
            str(task.get("baseline") or ""),
            gt_type,
            gt_description,
        )
        if value
    ]
    return OpportunityTask(
        id=task_id,
        canonical_task_id=f"{dataset_id}#{task_id}",
        task_type=str(task.get("task_type") or ""),
        prediction_target=str(task.get("prediction_target") or ""),
        held_out_unit=str(task.get("held_out_unit") or ""),
        metric=str(task.get("metric") or ""),
        baseline=str(task.get("baseline") or ""),
        ground_truth_type=gt_type,
        ground_truth_description=gt_description,
        prose=prose,
    )


def _tasks(dataset_id: str, value: object) -> list[OpportunityTask]:
    if not isinstance(value, list):
        return []
    tasks: list[OpportunityTask] = []
    for item in value:
        if isinstance(item, Mapping):
            task = _task_from_mapping(dataset_id, item)
            if task is not None:
                tasks.append(task)
    return tasks


def _dataset_class(fm: Mapping[str, object]) -> str:
    try:
        return dataset_class_for(fm)
    except ValueError:
        return "deposit"


def _dataset_from_source(source: Mapping[str, object]) -> OpportunityDataset | None:
    fm = source["frontmatter"]
    if not isinstance(fm, Mapping):
        return None
    benchmark = fm.get("benchmark")
    if not isinstance(benchmark, Mapping):
        return None
    dataset_id = str(fm.get("id") or source["fallback_id"])
    return OpportunityDataset(
        id=dataset_id,
        title=str(fm.get("title") or ""),
        scope=str(source["scope"]),
        dataset_class=_dataset_class(fm),
        frontmatter=fm,
        domains=_string_list(benchmark.get("domains")),
        modalities=_string_list(benchmark.get("modalities")),
        signal_types=_string_list(benchmark.get("signal_types")),
        benchmark_kinds=_string_list(benchmark.get("benchmark_kinds")),
        source_datasets=_string_list(benchmark.get("source_datasets")),
        related_beliefs=_string_list(benchmark.get("related_beliefs")),
        notes=_string_list(benchmark.get("notes")),
        limitations=_string_list(benchmark.get("limitations")),
        tasks=_tasks(dataset_id, benchmark.get("tasks")),
    )


def load_opportunity_datasets(
    project_root: Path,
    *,
    include_commons: bool,
) -> tuple[list[OpportunityDataset], str | None]:
    sources, notice = benchmark_sources(project_root, include_commons=include_commons)
    datasets = [dataset for source in sources if (dataset := _dataset_from_source(source)) is not None]
    return sorted(datasets, key=lambda row: (row.scope, row.id)), notice


def _task_completeness(dataset: OpportunityDataset) -> int:
    if not dataset.tasks:
        return 0
    best = 0
    for task in dataset.tasks:
        points = 0
        points += 6 if task.prediction_target else 0
        points += 6 if task.held_out_unit else 0
        points += 6 if task.metric else 0
        points += 6 if task.baseline else 0
        points += 6 if task.ground_truth_type or task.ground_truth_description else 0
        best = max(best, points)
    return best


def _facet_points(values: list[str], weights: Mapping[str, int], cap: int) -> tuple[int, list[str]]:
    total = 0
    notes: list[str] = []
    for value in _normalized_values(values):
        points = weights.get(value, 0)
        if points:
            total += points
            notes.append(value)
    return min(total, cap), notes


def baseline_score(dataset: OpportunityDataset, *, readiness: tuple[float, list[str]] | None = None) -> Score:
    task = _task_completeness(dataset)
    signal, signal_notes = _facet_points(dataset.signal_types, HIGH_VALUE_SIGNAL_POINTS, 25)
    modality, modality_notes = _facet_points(dataset.modalities, HIGH_VALUE_MODALITY_POINTS, 20)
    readiness_float, readiness_flags = readiness if readiness is not None else readiness_weight(dict(dataset.frontmatter))
    readiness_points = round(readiness_float * 15)
    limitations = 10 if dataset.limitations else 0
    components = {
        "task_completeness": task,
        "signal_value": signal,
        "modality_value": modality,
        "readiness": readiness_points,
        "limitations": limitations,
    }
    notes = [f"signal:{value}" for value in signal_notes]
    notes.extend(f"modality:{value}" for value in modality_notes)
    notes.extend(readiness_flags)
    if limitations:
        notes.append("limitations-present")
    return Score(total=min(sum(components.values()), 100), components=components, notes=notes)


def _token_evidence_from_text(
    *values: str,
    include_stop_tokens: bool = False,
    broad_tokens: frozenset[str] = frozenset(),
) -> TokenEvidence:
    kept: set[str] = set()
    stop: set[str] = set()
    broad: set[str] = set()
    short: set[str] = set()
    for value in values:
        for raw in _TOKEN_RE.findall(value):
            token = _normalize_token(raw)
            if token in broad_tokens:
                broad.add(token)
                continue
            if not include_stop_tokens and token in _STOP_TOKENS:
                stop.add(token)
                continue
            if len(token) < 3 and not re.fullmatch(r"[hq]\d+", token):
                short.add(token)
                continue
            kept.add(token)
    return TokenEvidence(
        kept=frozenset(kept),
        stop=frozenset(stop),
        broad=frozenset(broad),
        short=frozenset(short),
    )


def _tokens_from_text(
    *values: str,
    include_stop_tokens: bool = False,
    broad_tokens: frozenset[str] = frozenset(),
) -> frozenset[str]:
    return _token_evidence_from_text(
        *values,
        include_stop_tokens=include_stop_tokens,
        broad_tokens=broad_tokens,
    ).kept


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _id_tokens(entity_id: str, kind: str, fm: Mapping[str, object]) -> frozenset[str]:
    tokens = {entity_id.lower()}
    local = entity_id.split(":", 1)[1] if ":" in entity_id else entity_id
    tokens.add(local.lower())
    tokens.update(value.lower() for value in numeric_variants(local))
    numeric_prefix = re.match(r"^0*(\d+)(.*)$", local)
    if numeric_prefix is not None:
        number, suffix = numeric_prefix.groups()
        tokens.add(f"{number}{suffix}".lower())
        tokens.add(f"{kind}:{number}{suffix}".lower())
    shortform = shortform_for_kind(kind)
    if shortform is not None and numeric_prefix is not None:
        number, suffix = numeric_prefix.groups()
        tokens.add(f"{shortform}{number}".lower())
        tokens.add(f"{kind}:{shortform}{number}".lower())
        if suffix:
            tokens.add(f"{shortform}{number}{suffix}".lower())
            tokens.add(f"{kind}:{shortform}{number}{suffix}".lower())
    for field in ("same_as", "source_refs"):
        tokens.update(value.lower() for value in _as_string_list(fm.get(field)))
    return frozenset(tokens)


def load_project_entities(project_root: Path) -> list[ProjectBenchmarkEntity]:
    entities: list[ProjectBenchmarkEntity] = []
    for kind in _ENTITY_KINDS:
        for row in load_markdown_entities(project_root, kind=kind):
            fm = row["frontmatter"]
            if not isinstance(fm, Mapping):
                continue
            entity_id = str(row["id"])
            title = str(fm.get("title") or "")
            _frontmatter, body = parse_markdown_entity_file(row["path"])
            content_preview = str(fm.get("content_preview") or body[:200])
            tokens = _tokens_from_text(
                entity_id,
                title,
                content_preview,
                broad_tokens=ENTITY_SUPPRESSED_TOKENS,
            )
            entities.append(
                ProjectBenchmarkEntity(
                    id=entity_id,
                    kind=str(row["kind"]),
                    title=title,
                    content_preview=content_preview,
                    frontmatter=fm,
                    tokens=tokens,
                    id_tokens=_id_tokens(entity_id, kind, fm),
                )
            )
    return sorted(entities, key=lambda entity: entity.id)


def _controlled_facet_tokens(dataset: OpportunityDataset) -> frozenset[str]:
    return _tokens_from_text(
        *dataset.domains,
        *dataset.modalities,
        *dataset.signal_types,
        *dataset.benchmark_kinds,
        include_stop_tokens=False,
    )


def _scoreable_facet_tokens(controlled_facet_tokens: frozenset[str]) -> frozenset[str]:
    return frozenset(token for token in controlled_facet_tokens if token not in BROAD_NON_SCOREABLE_FACETS)


def _benchmark_prose_tokens(dataset: OpportunityDataset) -> frozenset[str]:
    task_prose: list[str] = []
    for task in dataset.tasks:
        task_prose.extend(task.prose)
    return _tokens_from_text(*dataset.notes, *dataset.limitations, *task_prose)


def _dataset_evidence_values(dataset: OpportunityDataset) -> list[str]:
    values = [
        dataset.id,
        dataset.title,
        *dataset.domains,
        *dataset.modalities,
        *dataset.signal_types,
        *dataset.benchmark_kinds,
        *dataset.source_datasets,
        *dataset.related_beliefs,
        *dataset.notes,
        *dataset.limitations,
    ]
    for task in dataset.tasks:
        values.extend(task.prose)
    return values


def _related_belief_tokens(dataset: OpportunityDataset) -> frozenset[str]:
    return _tokens_from_text(*dataset.related_beliefs, include_stop_tokens=True)


def _dataset_context(dataset: OpportunityDataset, *, include_prose_tokens: bool) -> DatasetOpportunityContext:
    dataset_readiness = readiness_weight(dict(dataset.frontmatter))
    readiness_float, _readiness_flags = dataset_readiness
    controlled_facet_tokens = _controlled_facet_tokens(dataset)
    return DatasetOpportunityContext(
        dataset=dataset,
        baseline=baseline_score(dataset, readiness=dataset_readiness),
        readiness_penalty=0 if readiness_float >= 0.5 else -10,
        controlled_facet_tokens=controlled_facet_tokens,
        scoreable_facet_tokens=_scoreable_facet_tokens(controlled_facet_tokens),
        prose_tokens=_benchmark_prose_tokens(dataset) if include_prose_tokens else frozenset(),
        related_belief_tokens=_related_belief_tokens(dataset),
    )


def _kind_signal_points(entity_tokens: frozenset[str], dataset: OpportunityDataset) -> tuple[int, list[str]]:
    total = 0
    notes: list[str] = []
    kinds = set(dataset.benchmark_kinds)
    for token, (kind, points) in KIND_SIGNAL_RULES.items():
        if token in entity_tokens and kind in kinds:
            total += points
            notes.append(f"kind-signal:{token}->{kind}")
    return min(total, 20), notes


def _relative_score(
    entity: ProjectBenchmarkEntity,
    context: DatasetOpportunityContext,
    seen_facets: set[tuple[str, str]],
) -> Score | None:
    dataset = context.dataset
    id_hits = sorted(entity.id_tokens & context.related_belief_tokens)
    facet_hits = sorted(entity.tokens & context.scoreable_facet_tokens)
    if not id_hits and not facet_hits:
        return None

    related_points = 40 if id_hits else 0
    facet_points = min(len(facet_hits) * 8, 25)
    kind_points, kind_notes = _kind_signal_points(entity.tokens, dataset)
    has_specific_match = bool(id_hits or facet_hits or kind_notes)

    diversity_points = 0
    diversity_notes: list[str] = []
    if has_specific_match:
        for value in (*_normalized_values(dataset.modalities), *_normalized_values(dataset.signal_types)):
            key = (entity.id, value)
            if key not in seen_facets:
                seen_facets.add(key)
                if value in HIGH_VALUE_MODALITIES or value in HIGH_VALUE_SIGNALS:
                    diversity_points += 5
                    diversity_notes.append(f"diversity:{value}")
    diversity_points = min(diversity_points, 15)

    components = {
        "related_belief_id": related_points,
        "facet_overlap": facet_points,
        "kind_signal_fit": kind_points,
        "diversity_added": diversity_points,
        "readiness_penalty": context.readiness_penalty,
    }
    notes = [f"related-belief-id:{hit}" for hit in id_hits]
    notes.extend(f"facet-token:{hit}" for hit in facet_hits)
    notes.extend(kind_notes)
    notes.extend(diversity_notes)
    return Score(total=max(0, min(sum(components.values()), 100)), components=components, notes=notes)


def _row_for(
    entity: ProjectBenchmarkEntity,
    dataset: OpportunityDataset,
    task_id: str | None,
    baseline: Score,
    relative: Score,
) -> OpportunityRow:
    return {
        "entity_id": entity.id,
        "entity_title": entity.title,
        "benchmark_id": dataset.id,
        "benchmark_title": dataset.title,
        "task_id": task_id,
        "match_reasons": relative.notes,
        "benchmark_kinds": list(dataset.benchmark_kinds),
        "signal_types": list(dataset.signal_types),
        "modalities": list(dataset.modalities),
        "baseline_score": baseline.total,
        "relative_score": relative.total,
        "score_components": {"baseline": baseline.components, "relative": relative.components},
        "score_notes": baseline.notes + relative.notes,
    }


def _rows_for_match(
    entity: ProjectBenchmarkEntity,
    context: DatasetOpportunityContext,
    seen_facets: set[tuple[str, str]],
) -> list[OpportunityRow]:
    dataset = context.dataset
    relative = _relative_score(entity, context, seen_facets)
    if relative is None:
        return []
    task_ids: list[str | None] = [task.canonical_task_id for task in dataset.tasks] or [None]
    rows: list[OpportunityRow] = []
    for task_id in task_ids:
        rows.append(_row_for(entity, dataset, task_id, context.baseline, relative))
    return rows


def _available_unmapped_benchmarks(
    contexts: list[DatasetOpportunityContext],
    matched_ids: set[str],
) -> list[UnmappedBenchmarkRow]:
    rows: list[UnmappedBenchmarkRow] = []
    for context in contexts:
        dataset = context.dataset
        if dataset.id in matched_ids:
            continue
        rows.append(
            {
                "benchmark_id": dataset.id,
                "benchmark_title": dataset.title,
                "baseline_score": context.baseline.total,
                "unmapped_facets": sorted(set(dataset.modalities + dataset.signal_types)),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["baseline_score"]), str(row["benchmark_id"])))


def _coverage_gaps(
    entities: list[ProjectBenchmarkEntity],
    matched_rows: list[OpportunityRow],
) -> list[CoverageGapRow]:
    matched_by_entity: dict[str, set[str]] = {}
    for row in matched_rows:
        facets = matched_by_entity.setdefault(row["entity_id"], set())
        facets.update(_normalize_token(value) for value in row["modalities"])
        facets.update(_normalize_token(value) for value in row["signal_types"])
    gaps: list[CoverageGapRow] = []
    for entity in entities:
        matched_facets = matched_by_entity.get(entity.id, set())
        missing_modalities = sorted(token for token in GAP_MODALITIES if token in entity.tokens and token not in matched_facets)
        missing_signal_types = sorted(
            token for token in GAP_SIGNAL_TYPES if token in entity.tokens and token not in matched_facets
        )
        if missing_modalities or missing_signal_types:
            gaps.append(
                {
                    "entity_id": entity.id,
                    "missing_modalities": missing_modalities,
                    "missing_signal_types": missing_signal_types,
                    "reason": "No matched benchmark has these facets.",
                }
            )
    return sorted(
        gaps,
        key=lambda row: (
            str(row["entity_id"]),
            ",".join(row["missing_modalities"]),
            ",".join(row["missing_signal_types"]),
        ),
    )


def _gap_level_sort_key(level: GapLevel) -> int:
    order = {"uncovered": 0, "weak": 1, "missing-facet": 2}
    return order[level]


def _normalized_gap_facet(facet: str | None) -> str | None:
    if facet is None:
        return None
    normalized = _normalize_token(facet)
    if not normalized:
        raise ValueError("facet must not be blank")
    if normalized not in BENCHMARK_GAP_HINT_FACET_SET:
        raise ValueError(f"unknown benchmark gap facet: {facet}")
    return normalized


def _matched_by_entity(rows: list[OpportunityRow]) -> dict[str, list[OpportunityRow]]:
    grouped: dict[str, list[OpportunityRow]] = {}
    for row in rows:
        grouped.setdefault(row["entity_id"], []).append(row)
    return grouped


def _coverage_gap_by_entity(rows: list[CoverageGapRow]) -> dict[str, CoverageGapRow]:
    return {row["entity_id"]: row for row in rows}


def _entity_title_map(report: OpportunityReport) -> dict[str, str]:
    titles: dict[str, str] = {}
    for row in report["matched_opportunities"]:
        titles.setdefault(row["entity_id"], row["entity_title"])
    for row in report["unmapped_project_entities"]:
        titles.setdefault(row["entity_id"], row["entity_title"])
    return titles


def _current_match_rows(rows: list[OpportunityRow]) -> list[GapCurrentMatchRow]:
    return [
        {
            "benchmark_id": row["benchmark_id"],
            "task_id": row["task_id"],
            "relative_score": row["relative_score"],
            "baseline_score": row["baseline_score"],
        }
        for row in rows
    ]


def _is_weak_gap(rows: list[OpportunityRow]) -> bool:
    if not rows:
        return False
    all_low_score = all(row["relative_score"] < WEAK_RELATIVE_SCORE_THRESHOLD for row in rows)
    all_taskless = all(row["task_id"] is None for row in rows)
    return all_low_score or all_taskless


def _candidate_rows(
    available: list[UnmappedBenchmarkRow],
    missing_facets: set[str],
) -> list[GapCandidateBenchmarkRow]:
    candidates: list[GapCandidateBenchmarkRow] = []
    for row in available:
        candidate_facets = {_normalize_token(value) for value in row["unmapped_facets"]}
        matched_facets = sorted(candidate_facets & missing_facets)
        candidates.append(
            {
                "benchmark_id": row["benchmark_id"],
                "benchmark_title": row["benchmark_title"],
                "baseline_score": row["baseline_score"],
                "matched_missing_facets": matched_facets,
            }
        )
    return sorted(
        candidates,
        key=lambda row: (-len(row["matched_missing_facets"]), -row["baseline_score"], row["benchmark_id"]),
    )


def _gap_summary(rows: list[BenchmarkGapRow], entities_total: int) -> BenchmarkGapSummary:
    return {
        "entities_total": entities_total,
        "entities_with_gaps": len(rows),
        "uncovered_entities": sum(1 for row in rows if row["gap_level"] == "uncovered"),
        "weakly_covered_entities": sum(1 for row in rows if row["gap_level"] == "weak"),
        "missing_facet_entities": sum(1 for row in rows if row["gap_level"] == "missing-facet"),
    }


def _calibration_benchmark_tokens(context: DatasetOpportunityContext) -> frozenset[str]:
    return frozenset({context.dataset.id.lower(), *context.controlled_facet_tokens})


def _score_components_copy(row: OpportunityRow) -> OpportunityScoreComponents:
    components = row["score_components"]
    return {"baseline": dict(components["baseline"]), "relative": dict(components["relative"])}


def _calibration_match_evidence(
    entities: list[ProjectBenchmarkEntity],
    contexts: list[DatasetOpportunityContext],
    matched_rows: list[OpportunityRow],
) -> list[CalibrationMatchEvidence]:
    entity_by_id = {entity.id: entity for entity in entities}
    context_by_id = {context.dataset.id: context for context in contexts}
    evidence: list[CalibrationMatchEvidence] = []
    for row in matched_rows:
        entity = entity_by_id.get(row["entity_id"])
        context = context_by_id.get(row["benchmark_id"])
        if entity is None or context is None:
            continue
        evidence.append(
            {
                "entity_id": row["entity_id"],
                "benchmark_id": row["benchmark_id"],
                "task_id": row["task_id"],
                "id_overlap": sorted(entity.id_tokens & context.related_belief_tokens),
                "facet_overlap": sorted(entity.tokens & context.scoreable_facet_tokens),
                "score_components": _score_components_copy(row),
            }
        )
    return evidence


def _unmatched_tokens(
    entity_tokens: dict[str, list[str]],
    benchmark_tokens: dict[str, list[str]],
    evidence: list[CalibrationMatchEvidence],
) -> UnmatchedTokenPayload:
    matched_by_entity: dict[str, set[str]] = {entity_id: set() for entity_id in entity_tokens}
    matched_by_benchmark: dict[str, set[str]] = {benchmark_id: set() for benchmark_id in benchmark_tokens}
    for item in evidence:
        entity_matches = matched_by_entity.setdefault(item["entity_id"], set())
        entity_matches.update(item["id_overlap"])
        entity_matches.update(item["facet_overlap"])
        matched_by_benchmark.setdefault(item["benchmark_id"], set()).update(item["facet_overlap"])
    return {
        "entities": {
            entity_id: sorted(set(tokens) - matched_by_entity.get(entity_id, set()))
            for entity_id, tokens in entity_tokens.items()
        },
        "benchmarks": {
            benchmark_id: sorted(set(tokens) - matched_by_benchmark.get(benchmark_id, set()))
            for benchmark_id, tokens in benchmark_tokens.items()
        },
    }


def _calibration_payload(
    entities: list[ProjectBenchmarkEntity],
    contexts: list[DatasetOpportunityContext],
    matched_rows: list[OpportunityRow],
    *,
    enabled: bool,
) -> CalibrationPayload:
    if not enabled:
        return {"enabled": False}
    entity_token_evidence = {
        entity.id: _token_evidence_from_text(
            entity.id,
            entity.title,
            entity.content_preview,
            broad_tokens=ENTITY_SUPPRESSED_TOKENS,
        )
        for entity in entities
    }
    benchmark_token_evidence = {
        context.dataset.id: _token_evidence_from_text(*_dataset_evidence_values(context.dataset))
        for context in contexts
    }
    benchmark_facet_evidence = {
        context.dataset.id: _token_evidence_from_text(
            *context.dataset.domains,
            *context.dataset.modalities,
            *context.dataset.signal_types,
            *context.dataset.benchmark_kinds,
            broad_tokens=BROAD_NON_SCOREABLE_FACETS,
        )
        for context in contexts
    }
    entity_tokens = {entity.id: sorted(entity.tokens) for entity in entities}
    benchmark_tokens = {
        context.dataset.id: sorted(_calibration_benchmark_tokens(context)) for context in contexts
    }
    matched_evidence = _calibration_match_evidence(entities, contexts, matched_rows)
    benchmark_broad_facets = {
        stable_id: sorted(evidence.broad)
        for stable_id, evidence in benchmark_facet_evidence.items()
        if evidence.broad
    }
    return {
        "enabled": True,
        "stop_tokens": sorted(_STOP_TOKENS),
        "entity_tokens": entity_tokens,
        "benchmark_controlled_facet_tokens": benchmark_tokens,
        "dropped_tokens": {
            "stop": {
                stable_id: sorted(evidence.stop)
                for stable_id, evidence in {
                    **entity_token_evidence,
                    **benchmark_token_evidence,
                }.items()
                if evidence.stop
            },
            "broad_entity": {
                stable_id: sorted(evidence.broad)
                for stable_id, evidence in entity_token_evidence.items()
                if evidence.broad
            },
            "broad_dataset_facet": benchmark_broad_facets,
            "short": {
                stable_id: sorted(evidence.short)
                for stable_id, evidence in {
                    **entity_token_evidence,
                    **benchmark_token_evidence,
                }.items()
                if evidence.short
            },
        },
        "matched_token_evidence": matched_evidence,
        "unmatched_tokens": _unmatched_tokens(entity_tokens, benchmark_tokens, matched_evidence),
        "excluded_benchmark_prose_tokens": {
            context.dataset.id: sorted(context.prose_tokens) for context in contexts if context.prose_tokens
        },
    }


def opportunity_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    calibration_report: bool = False,
) -> OpportunityReport:
    entities = load_project_entities(project_root)
    if entity_id is not None:
        entities = [entity for entity in entities if entity.id == entity_id]
    datasets, notice = load_opportunity_datasets(project_root, include_commons=include_commons)
    if domain is not None:
        datasets = [dataset for dataset in datasets if domain in dataset.domains]
    contexts = [_dataset_context(dataset, include_prose_tokens=calibration_report) for dataset in datasets]

    # Diversity credit is entity-relative across benchmarks. Because rows are
    # produced in dataset sort order, the first matched benchmark for an entity
    # claims each high-value facet; later rows with the same facet receive no
    # additional diversity credit.
    seen_facets: set[tuple[str, str]] = set()
    matched: list[OpportunityRow] = []
    for entity in entities:
        for context in contexts:
            matched.extend(_rows_for_match(entity, context, seen_facets))
    matched.sort(
        key=lambda row: (
            -row["relative_score"],
            -row["baseline_score"],
            row["entity_id"],
            row["benchmark_id"],
            "" if row["task_id"] is None else row["task_id"],
        )
    )
    matched_entity_ids = {row["entity_id"] for row in matched}
    matched_benchmark_ids = {row["benchmark_id"] for row in matched}
    return {
        "matched_opportunities": matched,
        "coverage_gaps": _coverage_gaps(entities, matched),
        "available_unmapped_benchmarks": _available_unmapped_benchmarks(contexts, matched_benchmark_ids),
        "unmapped_project_entities": [
            {"entity_id": entity.id, "entity_title": entity.title, "observed_tokens": sorted(entity.tokens)}
            for entity in entities
            if entity.id not in matched_entity_ids
        ],
        "calibration": _calibration_payload(entities, contexts, matched, enabled=calibration_report),
        "commons_notice": notice,
    }


def gaps_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    facet: str | None = None,
) -> BenchmarkGapReport:
    normalized_facet = _normalized_gap_facet(facet)
    opportunity = opportunity_report(
        project_root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
    )
    matched = _matched_by_entity(opportunity["matched_opportunities"])
    coverage = _coverage_gap_by_entity(opportunity["coverage_gaps"])
    titles = _entity_title_map(opportunity)
    unmapped_ids = {row["entity_id"] for row in opportunity["unmapped_project_entities"]}
    entity_ids = sorted(set(matched) | set(coverage) | unmapped_ids)

    rows: list[BenchmarkGapRow] = []
    for current_entity_id in entity_ids:
        current_matches = matched.get(current_entity_id, [])
        gap = coverage.get(current_entity_id)
        missing_modalities = list(gap["missing_modalities"]) if gap is not None else []
        missing_signal_types = list(gap["missing_signal_types"]) if gap is not None else []
        missing_facets = {_normalize_token(value) for value in missing_modalities + missing_signal_types}

        if current_entity_id in unmapped_ids:
            gap_level = "uncovered"
            reason = "No matched benchmark opportunities for this entity."
        elif _is_weak_gap(current_matches):
            gap_level = "weak"
            reason = "Matched benchmarks are taskless or below the weak relative-score threshold."
        elif gap is not None:
            gap_level = "missing-facet"
            reason = gap["reason"]
        else:
            continue

        if normalized_facet is not None and normalized_facet not in missing_facets:
            continue

        rows.append(
            {
                "entity_id": current_entity_id,
                "entity_title": titles.get(current_entity_id, current_entity_id),
                "gap_level": gap_level,
                "missing_modalities": missing_modalities,
                "missing_signal_types": missing_signal_types,
                "current_matches": _current_match_rows(current_matches),
                "candidate_benchmarks": _candidate_rows(
                    opportunity["available_unmapped_benchmarks"],
                    missing_facets,
                ),
                "suggested_search_facets": sorted(missing_facets),
                "reason": reason,
            }
        )

    rows.sort(key=lambda row: (_gap_level_sort_key(row["gap_level"]), row["entity_id"]))
    return {
        "benchmark_gaps": rows,
        "summary": _gap_summary(rows, entities_total=len(entity_ids)),
        "commons_notice": opportunity["commons_notice"],
    }
