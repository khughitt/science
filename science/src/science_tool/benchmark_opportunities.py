"""Read-only benchmark opportunity reports."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
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
FACET_HINT_TERMS: dict[str, str] = {
    "drug": "perturbation",
    "compound": "perturbation",
    "knockout": "perturbation",
    "perturb": "perturbation",
    "perturbation": "perturbation",
    "time-series": "time-series",
    "timeseries": "time-series",
    "temporal": "time-series",
    "dynamic": "time-series",
    "longitudinal": "longitudinal",
    "trajectory": "time-series",
    "proteomic": "proteomics",
    "proteomics": "proteomics",
    "protein": "proteomics",
    "phosphoproteomic": "proteomics",
    "phosphoproteomics": "proteomics",
    "spatial": "spatial",
    "region": "spatial",
    "microenvironment": "spatial",
    "neighborhood": "spatial",
    "multimodal": "multimodal",
    "multi-modal": "multimodal",
    "multiomic": "multi-omic",
    "multi-omic": "multi-omic",
    "proteogenomic": "multimodal",
    "proteogenomics": "multimodal",
    "singlecell": "single-cell-rna-seq",
    "scrna": "single-cell-rna-seq",
    "scrna-seq": "single-cell-rna-seq",
    "single-cell-rna-seq": "single-cell-rna-seq",
    "transfer": "cross-context-generalization",
    "generalization": "cross-context-generalization",
    "cross-context": "cross-context-generalization",
}
FACET_HINT_PHRASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("cross", "context"), "cross-context-generalization"),
    (("external", "validation"), "cross-context-generalization"),
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
_UNMAPPED_TERM_EXCLUSIONS = frozenset(
    {
        *_STOP_TOKENS,
        *ENTITY_SUPPRESSED_TOKENS,
        *_ENTITY_KINDS,
        "benchmark",
        "gap",
        "tested",
        "testing",
        "validation",
        "validate",
        "needed",
        "should",
    }
)


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


@dataclass(frozen=True)
class OpportunityAnalysis:
    entities: list[ProjectBenchmarkEntity]
    contexts: list[DatasetOpportunityContext]
    report: OpportunityReport


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
    candidate_score: int
    matched_missing_facets: list[str]
    matched_hint_facets: list[str]
    reason_notes: list[str]


@dataclass(frozen=True)
class CandidateScore:
    total: int
    components: dict[str, int]
    reason_notes: list[str]
    matched_missing_facets: list[str]
    matched_hint_facets: list[str]


CandidateScoreIndex = dict[tuple[str, str], CandidateScore]


class GapEntityDroppedTokens(TypedDict):
    stop: list[str]
    broad_entity: list[str]
    short: list[str]


class GapEntityEvidence(TypedDict):
    entity_tokens: list[str]
    dropped_tokens: GapEntityDroppedTokens
    facet_hints: list[str]
    gap_level_reason: str


class GapCandidateEvidence(TypedDict):
    entity_id: str
    benchmark_id: str
    candidate_score: int
    dropped_dataset_facets: list[str]
    components: dict[str, int]
    reason_notes: list[str]


class GapCalibrationPayload(TypedDict):
    enabled: bool
    gap_entity_evidence: NotRequired[dict[str, GapEntityEvidence]]
    candidate_evidence: NotRequired[list[GapCandidateEvidence]]


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


CandidateMode = Literal["entity-specific", "fallback-only", "none"]


class TermCountRow(TypedDict):
    term: str
    count: int
    example_entities: list[str]


class EvidenceEntityRow(TypedDict):
    candidate_mode: CandidateMode
    tokens: list[str]
    facet_hints: list[str]
    matched_facets: list[str]
    suggested_search_facets: list[str]
    unmapped_high_value_terms: list[str]
    why_no_specific_candidate: list[str]


class EvidenceSummary(TypedDict):
    entities_total: int
    entities_with_no_facet_hints: int
    entities_with_fallback_only_candidates: int
    top_unmapped_project_terms: list[TermCountRow]


class EvidenceReport(TypedDict):
    enabled: bool
    summary: NotRequired[EvidenceSummary]
    entities: NotRequired[dict[str, EvidenceEntityRow]]
    lexicon_candidates: NotRequired[list[TermCountRow]]


class BenchmarkGapReport(TypedDict):
    benchmark_gaps: list[BenchmarkGapRow]
    summary: BenchmarkGapSummary
    calibration: GapCalibrationPayload
    evidence_report: EvidenceReport
    commons_notice: str | None


class FacetCountRow(TypedDict):
    facet: str
    count: int


class BenchmarkCountRow(TypedDict):
    benchmark_id: str
    count: int


class ReasonCountRow(TypedDict):
    reason: str
    count: int


class BenchmarkShareRow(TypedDict):
    benchmark_id: str
    count: int
    share: float


class GapCalibrationSummary(TypedDict):
    gap_rows: int
    rows_with_suggested_facets: int
    candidate_rows: int
    entity_specific_candidate_rows: int
    fallback_candidate_rows: int
    score_min: int | None
    score_median: float | None
    score_max: int | None
    top_suggested_facets: list[FacetCountRow]
    top_matched_hint_facets: list[FacetCountRow]
    top_fallback_benchmarks: list[BenchmarkCountRow]
    top_fallback_reasons: list[ReasonCountRow]
    top_fallback_selection_reasons: list[ReasonCountRow]
    top_fallback_benchmark_shares: list[BenchmarkShareRow]
    fallback_concentration_warning: bool


class GapCalibrationProjectRow(TypedDict):
    label: str
    project_root: str
    summary: BenchmarkGapSummary
    calibration_summary: GapCalibrationSummary
    commons_notice: str | None


class GapCalibrationAggregate(TypedDict):
    project_count: int
    gap_rows: int
    candidate_rows: int
    entity_specific_candidate_rows: int
    fallback_candidate_rows: int
    fallback_candidate_ratio: float | None
    top_suggested_facets: list[FacetCountRow]
    top_matched_hint_facets: list[FacetCountRow]
    top_fallback_benchmarks: list[BenchmarkCountRow]
    top_fallback_reasons: list[ReasonCountRow]
    top_fallback_selection_reasons: list[ReasonCountRow]
    top_fallback_benchmark_shares: list[BenchmarkShareRow]
    fallback_concentration_warning: bool


class GapCalibrationCommonsNotice(TypedDict):
    label: str
    notice: str


class GapCalibrationBatchReport(TypedDict):
    projects: list[GapCalibrationProjectRow]
    aggregate: GapCalibrationAggregate
    commons_notices: list[GapCalibrationCommonsNotice]


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


def _token_sequence_from_text(
    *values: str,
    include_stop_tokens: bool = False,
    broad_tokens: frozenset[str] = frozenset(),
) -> list[str]:
    tokens: list[str] = []
    for value in values:
        for raw in _TOKEN_RE.findall(value):
            token = _normalize_token(raw)
            if token in broad_tokens:
                continue
            if not include_stop_tokens and token in _STOP_TOKENS:
                continue
            if len(token) < 3 and not re.fullmatch(r"[hq]\d+", token):
                continue
            tokens.append(token)
    return tokens


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


def _facet_sort_key(facet: str) -> tuple[int, str]:
    try:
        return (BENCHMARK_GAP_HINT_FACETS.index(facet), facet)
    except ValueError:
        return (len(BENCHMARK_GAP_HINT_FACETS), facet)


def _sorted_facets(facets: set[str] | list[str]) -> list[str]:
    return sorted({_normalize_token(facet) for facet in facets}, key=_facet_sort_key)


def _phrase_tokens() -> set[str]:
    return {token for phrase, _hint in FACET_HINT_PHRASES for token in phrase}


def _entity_facet_hints(entity: ProjectBenchmarkEntity) -> list[str]:
    hints: set[str] = set()
    for token in entity.tokens:
        hint = FACET_HINT_TERMS.get(token)
        if hint is not None and hint in BENCHMARK_GAP_HINT_FACET_SET:
            hints.add(hint)
    sequence = _token_sequence_from_text(
        entity.title,
        entity.content_preview,
        broad_tokens=ENTITY_SUPPRESSED_TOKENS,
    )
    for phrase, hint in FACET_HINT_PHRASES:
        phrase_len = len(phrase)
        has_phrase = any(
            tuple(sequence[index : index + phrase_len]) == phrase
            for index in range(len(sequence) - phrase_len + 1)
        )
        if has_phrase:
            hints.add(hint)
    return _sorted_facets(hints)


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


def _matched_facets_for_gap(row: BenchmarkGapRow, current_matches: list[OpportunityRow]) -> list[str]:
    facets: set[str] = set()
    for match in current_matches:
        facets.update(_normalize_token(value) for value in match["modalities"])
        facets.update(_normalize_token(value) for value in match["signal_types"])
    for candidate in row["candidate_benchmarks"]:
        facets.update(candidate["matched_missing_facets"])
        facets.update(candidate["matched_hint_facets"])
    return _sorted_facets(facets)


def _candidate_mode(candidates: list[GapCandidateBenchmarkRow]) -> CandidateMode:
    if any(candidate["matched_missing_facets"] or candidate["matched_hint_facets"] for candidate in candidates):
        return "entity-specific"
    if candidates:
        return "fallback-only"
    return "none"


def _unmapped_high_value_terms(entity: ProjectBenchmarkEntity, matched_facets: list[str]) -> list[str]:
    excluded = set(_UNMAPPED_TERM_EXCLUSIONS)
    excluded.update(_phrase_tokens())
    excluded.update(FACET_HINT_TERMS)
    excluded.update(BENCHMARK_GAP_HINT_FACET_SET)
    excluded.update(matched_facets)
    excluded.update(entity.id_tokens)
    return sorted(
        token
        for token in entity.tokens
        if token not in excluded and ":" not in token and not re.fullmatch(r"\d+.*", token)
    )


def _why_no_specific_candidate(row: BenchmarkGapRow, mode: CandidateMode) -> list[str]:
    reasons: list[str] = []
    if row["gap_level"] == "weak":
        reasons.append("current-match-too-weak")
    if not row["suggested_search_facets"]:
        reasons.append("no-facet-hints")
    elif mode != "entity-specific":
        reasons.append("hints-have-no-candidate-facet-overlap")
    if mode == "fallback-only":
        reasons.append("only-fallback-candidates")
    if mode == "none":
        reasons.append("no-candidates")
    return reasons


def _top_unmapped_terms(by_entity: dict[str, list[str]], *, top: int = 10) -> list[TermCountRow]:
    counts = Counter(term for terms in by_entity.values() for term in terms)
    examples: dict[str, list[str]] = {}
    for entity_id, terms in by_entity.items():
        for term in terms:
            bucket = examples.setdefault(term, [])
            if len(bucket) < 3:
                bucket.append(entity_id)
    return [
        {"term": term, "count": count, "example_entities": examples.get(term, [])}
        for term, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top]
    ]


def _gap_evidence_report(
    rows: list[BenchmarkGapRow],
    *,
    entities: list[ProjectBenchmarkEntity],
    matched: dict[str, list[OpportunityRow]],
    enabled: bool,
) -> EvidenceReport:
    if not enabled:
        return {"enabled": False}

    entity_by_id = {entity.id: entity for entity in entities}
    evidence_entities: dict[str, EvidenceEntityRow] = {}
    unmapped_by_entity: dict[str, list[str]] = {}
    no_hints = 0
    fallback_only = 0
    for row in rows:
        entity = entity_by_id.get(row["entity_id"])
        if entity is None:
            continue
        mode = _candidate_mode(row["candidate_benchmarks"])
        if mode == "fallback-only":
            fallback_only += 1
        if not row["suggested_search_facets"]:
            no_hints += 1
        matched_facets = _matched_facets_for_gap(row, matched.get(row["entity_id"], []))
        unmapped_terms = _unmapped_high_value_terms(entity, matched_facets)
        unmapped_by_entity[row["entity_id"]] = unmapped_terms
        evidence_entities[row["entity_id"]] = {
            "candidate_mode": mode,
            "tokens": sorted(entity.tokens),
            "facet_hints": _entity_facet_hints(entity),
            "matched_facets": matched_facets,
            "suggested_search_facets": list(row["suggested_search_facets"]),
            "unmapped_high_value_terms": unmapped_terms,
            "why_no_specific_candidate": _why_no_specific_candidate(row, mode),
        }

    top_terms = _top_unmapped_terms(unmapped_by_entity)
    return {
        "enabled": True,
        "summary": {
            "entities_total": len(rows),
            "entities_with_no_facet_hints": no_hints,
            "entities_with_fallback_only_candidates": fallback_only,
            "top_unmapped_project_terms": top_terms,
        },
        "entities": evidence_entities,
        "lexicon_candidates": top_terms,
    }


def _is_weak_gap(rows: list[OpportunityRow]) -> bool:
    if not rows:
        return False
    all_low_score = all(row["relative_score"] < WEAK_RELATIVE_SCORE_THRESHOLD for row in rows)
    all_taskless = all(row["task_id"] is None for row in rows)
    return all_low_score or all_taskless


def _context_declared_facets(context: DatasetOpportunityContext) -> set[str]:
    return {
        _normalize_token(value)
        for value in (
            *context.dataset.modalities,
            *context.dataset.signal_types,
        )
    } & BENCHMARK_GAP_HINT_FACET_SET


def _reason_note_sort_key(note: str) -> tuple[int, str]:
    family_order = {
        "missing-facet": 0,
        "entity-hint": 1,
        "task-ready": 2,
        "high-baseline": 3,
        "fallback": 4,
        "selected": 5,
    }
    family = note.split(":", 1)[0]
    return (family_order.get(family, 99), note)


def _candidate_score(
    context: DatasetOpportunityContext,
    *,
    missing_facets: set[str],
    hint_facets: set[str],
) -> CandidateScore:
    declared_facets = _context_declared_facets(context)
    matched_missing = set(missing_facets) & declared_facets
    matched_hints = set(hint_facets) & declared_facets
    baseline_components = context.baseline.components
    missing_points = min(len(matched_missing) * 10, 30)
    hint_points = min(len(matched_hints) * 10, 35)
    task_completeness = baseline_components.get("task_completeness", 0)
    readiness = baseline_components.get("readiness", 0)
    task_readiness = round(((task_completeness / 30) * 12) + ((readiness / 15) * 8))
    baseline_quality = round(
        (
            (
                baseline_components.get("signal_value", 0)
                + baseline_components.get("modality_value", 0)
                + baseline_components.get("limitations", 0)
            )
            / 55
        )
        * 15
    )
    components = {
        "missing_facet_overlap": missing_points,
        "hint_facet_overlap": hint_points,
        "task_readiness": task_readiness,
        "baseline_quality": baseline_quality,
    }
    reason_notes = [f"missing-facet:{facet}" for facet in _sorted_facets(matched_missing)]
    reason_notes.extend(f"entity-hint:{facet}" for facet in _sorted_facets(matched_hints))
    if task_readiness >= 12:
        reason_notes.append("task-ready")
    if baseline_quality >= 8:
        reason_notes.append("high-baseline")
    return CandidateScore(
        total=min(sum(components.values()), 100),
        components=components,
        reason_notes=sorted(set(reason_notes), key=_reason_note_sort_key),
        matched_missing_facets=_sorted_facets(matched_missing),
        matched_hint_facets=_sorted_facets(matched_hints),
    )


def _has_entity_specific_candidate_evidence(score: CandidateScore) -> bool:
    return bool(score.matched_missing_facets or score.matched_hint_facets)


def _fallback_reason_notes(score: CandidateScore) -> list[str]:
    notes: list[str] = []
    if score.components.get("task_readiness", 0) > 0:
        notes.append("fallback:task-ready")
    if score.components.get("baseline_quality", 0) > 0:
        notes.append("fallback:baseline-quality")
    if not notes:
        notes.append("fallback:positive-score" if score.total > 0 else "fallback:available-benchmark")
    return notes


def _is_fallback_candidate(candidate: GapCandidateBenchmarkRow) -> bool:
    return any(note.startswith("fallback:") for note in candidate["reason_notes"])


def _selection_reason_note(row: GapCandidateBenchmarkRow, *, rotated: bool) -> str:
    if rotated:
        return "selected:diversity-rotation"
    if "fallback:baseline-quality" in row["reason_notes"]:
        return "selected:generic-baseline"
    if "fallback:task-ready" in row["reason_notes"]:
        return "selected:task-ready"
    return "selected:available-benchmark"


def _with_selection_reason(row: GapCandidateBenchmarkRow, *, rotated: bool) -> GapCandidateBenchmarkRow:
    notes = {*row["reason_notes"], _selection_reason_note(row, rotated=rotated)}
    return {**row, "reason_notes": sorted(notes, key=_reason_note_sort_key)}


def _stable_rotation_offset(entity_id: str, size: int) -> int:
    if size <= 1:
        return 0
    digest = hashlib.sha1(entity_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % size


def _rotated(rows: list[GapCandidateBenchmarkRow], *, entity_id: str) -> tuple[list[GapCandidateBenchmarkRow], bool]:
    if len(rows) <= 1:
        return rows, False
    offset = _stable_rotation_offset(entity_id, len(rows))
    if offset == 0:
        return rows, False
    return [*rows[offset:], *rows[:offset]], True


def _select_fallback_rows(
    entity_id: str,
    fallback: list[GapCandidateBenchmarkRow],
    *,
    limit: int,
) -> list[GapCandidateBenchmarkRow]:
    selected: list[GapCandidateBenchmarkRow] = []
    remaining = min(3, limit)
    ordered = sorted(
        fallback,
        key=lambda row: (-row["candidate_score"], -row["baseline_score"], row["benchmark_id"]),
    )
    while ordered and remaining > 0:
        first = ordered[0]
        tier_key = (first["candidate_score"], first["baseline_score"])
        tier = [
            row
            for row in ordered
            if (row["candidate_score"], row["baseline_score"]) == tier_key
        ]
        ordered = [
            row
            for row in ordered
            if (row["candidate_score"], row["baseline_score"]) != tier_key
        ]
        rotated_tier, rotated = _rotated(tier, entity_id=entity_id)
        for row in rotated_tier[:remaining]:
            selected.append(_with_selection_reason(row, rotated=rotated and len(tier) > remaining))
        remaining = min(3, limit) - len(selected)
    return selected


def _candidate_rows(
    entity_id: str,
    contexts: list[DatasetOpportunityContext],
    current_matches: list[OpportunityRow],
    missing_facets: set[str],
    hint_facets: set[str],
    score_index: CandidateScoreIndex,
    *,
    limit: int = 5,
) -> list[GapCandidateBenchmarkRow]:
    matched_benchmark_ids = {row["benchmark_id"] for row in current_matches}
    scored: list[tuple[GapCandidateBenchmarkRow, CandidateScore]] = []
    fallback: list[GapCandidateBenchmarkRow] = []
    for context in contexts:
        dataset = context.dataset
        if dataset.id in matched_benchmark_ids:
            continue
        score = _candidate_score(context, missing_facets=missing_facets, hint_facets=hint_facets)
        score_index[(entity_id, dataset.id)] = score
        row: GapCandidateBenchmarkRow = {
            "benchmark_id": dataset.id,
            "benchmark_title": dataset.title,
            "baseline_score": context.baseline.total,
            "candidate_score": score.total,
            "matched_missing_facets": score.matched_missing_facets,
            "matched_hint_facets": score.matched_hint_facets,
            "reason_notes": score.reason_notes,
        }
        if _has_entity_specific_candidate_evidence(score):
            scored.append((row, score))
        else:
            fallback.append(
                {
                    **row,
                    "reason_notes": _fallback_reason_notes(score),
                }
            )
    if scored:
        ordered = [
            row
            for row, _score in sorted(
                scored,
                key=lambda item: (
                    -item[0]["candidate_score"],
                    -len(item[0]["matched_hint_facets"]),
                    -item[0]["baseline_score"],
                    item[0]["benchmark_id"],
                ),
            )
        ]
        return ordered[:limit]
    return _select_fallback_rows(entity_id, fallback, limit=limit)


def _gap_summary(rows: list[BenchmarkGapRow], entities_total: int) -> BenchmarkGapSummary:
    return {
        "entities_total": entities_total,
        "entities_with_gaps": len(rows),
        "uncovered_entities": sum(1 for row in rows if row["gap_level"] == "uncovered"),
        "weakly_covered_entities": sum(1 for row in rows if row["gap_level"] == "weak"),
        "missing_facet_entities": sum(1 for row in rows if row["gap_level"] == "missing-facet"),
    }


def _median_score(scores: list[int]) -> float | None:
    if not scores:
        return None
    ordered = sorted(scores)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[midpoint])
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _top_facet_counts(counter: Counter[str], *, top: int) -> list[FacetCountRow]:
    return [
        {"facet": facet, "count": count}
        for facet, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top]
    ]


def _top_benchmark_counts(counter: Counter[str], *, top: int) -> list[BenchmarkCountRow]:
    return [
        {"benchmark_id": benchmark_id, "count": count}
        for benchmark_id, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top]
    ]


def _top_reason_counts(counter: Counter[str], *, top: int) -> list[ReasonCountRow]:
    return [
        {"reason": reason, "count": count}
        for reason, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top]
    ]


def _top_benchmark_shares(counter: Counter[str], *, total: int, top: int) -> list[BenchmarkShareRow]:
    if total <= 0:
        return []
    return [
        {"benchmark_id": benchmark_id, "count": count, "share": round(count / total, 3)}
        for benchmark_id, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:top]
    ]


def _has_fallback_concentration(counter: Counter[str], *, total: int) -> bool:
    return bool(total > 0 and counter and (max(counter.values()) / total) >= 0.5)


def gap_calibration_summary(report: BenchmarkGapReport, *, top: int = 10) -> GapCalibrationSummary:
    rows = report["benchmark_gaps"]
    candidates = [candidate for row in rows for candidate in row["candidate_benchmarks"]]
    entity_specific_candidates = [
        candidate
        for candidate in candidates
        if candidate["matched_missing_facets"] or candidate["matched_hint_facets"]
    ]
    fallback_candidates = [candidate for candidate in candidates if _is_fallback_candidate(candidate)]
    scores = [candidate["candidate_score"] for candidate in candidates]
    suggested_facets = Counter(facet for row in rows for facet in row["suggested_search_facets"])
    matched_hint_facets = Counter(facet for candidate in candidates for facet in candidate["matched_hint_facets"])
    fallback_benchmarks = Counter(candidate["benchmark_id"] for candidate in fallback_candidates)
    fallback_reasons = Counter(
        reason
        for candidate in fallback_candidates
        for reason in candidate["reason_notes"]
        if reason.startswith("fallback:")
    )
    fallback_selection_reasons = Counter(
        reason
        for candidate in fallback_candidates
        for reason in candidate["reason_notes"]
        if reason.startswith("selected:")
    )
    return {
        "gap_rows": len(rows),
        "rows_with_suggested_facets": sum(1 for row in rows if row["suggested_search_facets"]),
        "candidate_rows": len(candidates),
        "entity_specific_candidate_rows": len(entity_specific_candidates),
        "fallback_candidate_rows": len(fallback_candidates),
        "score_min": min(scores) if scores else None,
        "score_median": _median_score(scores),
        "score_max": max(scores) if scores else None,
        "top_suggested_facets": _top_facet_counts(suggested_facets, top=top),
        "top_matched_hint_facets": _top_facet_counts(matched_hint_facets, top=top),
        "top_fallback_benchmarks": _top_benchmark_counts(fallback_benchmarks, top=top),
        "top_fallback_reasons": _top_reason_counts(fallback_reasons, top=top),
        "top_fallback_selection_reasons": _top_reason_counts(fallback_selection_reasons, top=top),
        "top_fallback_benchmark_shares": _top_benchmark_shares(
            fallback_benchmarks,
            total=len(fallback_candidates),
            top=top,
        ),
        "fallback_concentration_warning": _has_fallback_concentration(
            fallback_benchmarks,
            total=len(fallback_candidates),
        ),
    }


def _display_path(path: Path) -> str:
    resolved = path.expanduser().resolve()
    home_d = (Path.home() / "d").resolve()
    try:
        return f"~/d/{resolved.relative_to(home_d).as_posix()}"
    except ValueError:
        return str(resolved)


def _merged_top_facets(rows: list[BenchmarkGapRow], *, top: int) -> tuple[list[FacetCountRow], list[FacetCountRow]]:
    suggested = Counter(facet for row in rows for facet in row["suggested_search_facets"])
    matched = Counter(
        facet
        for row in rows
        for candidate in row["candidate_benchmarks"]
        for facet in candidate["matched_hint_facets"]
    )
    return _top_facet_counts(suggested, top=top), _top_facet_counts(matched, top=top)


def _top_fallback_benchmarks(rows: list[BenchmarkGapRow], *, top: int) -> list[BenchmarkCountRow]:
    fallback = Counter(
        candidate["benchmark_id"]
        for row in rows
        for candidate in row["candidate_benchmarks"]
        if _is_fallback_candidate(candidate)
    )
    return _top_benchmark_counts(fallback, top=top)


def _fallback_candidates_from_rows(rows: list[BenchmarkGapRow]) -> list[GapCandidateBenchmarkRow]:
    return [
        candidate
        for row in rows
        for candidate in row["candidate_benchmarks"]
        if _is_fallback_candidate(candidate)
    ]


def benchmark_gap_calibration_batch(
    projects: list[tuple[str, Path]],
    *,
    include_commons: bool = False,
    domain: str | None = None,
    facet: str | None = None,
    top: int = 10,
) -> GapCalibrationBatchReport:
    project_rows: list[GapCalibrationProjectRow] = []
    notices: list[GapCalibrationCommonsNotice] = []
    all_gap_rows: list[BenchmarkGapRow] = []
    for label, project_root in projects:
        report = gaps_report(
            project_root,
            include_commons=include_commons,
            domain=domain,
            facet=facet,
        )
        summary = gap_calibration_summary(report, top=top)
        notice = report["commons_notice"]
        if notice:
            notices.append({"label": label, "notice": notice})
        project_rows.append(
            {
                "label": label,
                "project_root": _display_path(project_root),
                "summary": report["summary"],
                "calibration_summary": summary,
                "commons_notice": notice,
            }
        )
        all_gap_rows.extend(report["benchmark_gaps"])

    gap_rows = sum(row["calibration_summary"]["gap_rows"] for row in project_rows)
    candidate_rows = sum(row["calibration_summary"]["candidate_rows"] for row in project_rows)
    entity_specific = sum(row["calibration_summary"]["entity_specific_candidate_rows"] for row in project_rows)
    fallback = sum(row["calibration_summary"]["fallback_candidate_rows"] for row in project_rows)
    top_suggested, top_matched = _merged_top_facets(all_gap_rows, top=top)
    fallback_candidates = _fallback_candidates_from_rows(all_gap_rows)
    fallback_benchmarks = Counter(candidate["benchmark_id"] for candidate in fallback_candidates)
    fallback_reasons = Counter(
        reason
        for candidate in fallback_candidates
        for reason in candidate["reason_notes"]
        if reason.startswith("fallback:")
    )
    fallback_selection_reasons = Counter(
        reason
        for candidate in fallback_candidates
        for reason in candidate["reason_notes"]
        if reason.startswith("selected:")
    )
    return {
        "projects": project_rows,
        "aggregate": {
            "project_count": len(project_rows),
            "gap_rows": gap_rows,
            "candidate_rows": candidate_rows,
            "entity_specific_candidate_rows": entity_specific,
            "fallback_candidate_rows": fallback,
            "fallback_candidate_ratio": round(fallback / candidate_rows, 3) if candidate_rows else None,
            "top_suggested_facets": top_suggested,
            "top_matched_hint_facets": top_matched,
            "top_fallback_benchmarks": _top_fallback_benchmarks(all_gap_rows, top=top),
            "top_fallback_reasons": _top_reason_counts(fallback_reasons, top=top),
            "top_fallback_selection_reasons": _top_reason_counts(fallback_selection_reasons, top=top),
            "top_fallback_benchmark_shares": _top_benchmark_shares(
                fallback_benchmarks,
                total=len(fallback_candidates),
                top=top,
            ),
            "fallback_concentration_warning": _has_fallback_concentration(
                fallback_benchmarks,
                total=len(fallback_candidates),
            ),
        },
        "commons_notices": notices,
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


def _dataset_broad_facets(context: DatasetOpportunityContext) -> list[str]:
    evidence = _token_evidence_from_text(
        *context.dataset.domains,
        *context.dataset.modalities,
        *context.dataset.signal_types,
        *context.dataset.benchmark_kinds,
        broad_tokens=BROAD_NON_SCOREABLE_FACETS,
    )
    return sorted(evidence.broad)


def _gap_calibration_payload(
    rows: list[BenchmarkGapRow],
    *,
    entities: list[ProjectBenchmarkEntity],
    contexts: list[DatasetOpportunityContext],
    candidate_scores: CandidateScoreIndex,
    enabled: bool,
) -> GapCalibrationPayload:
    if not enabled:
        return {"enabled": False}
    entity_by_id = {entity.id: entity for entity in entities}
    context_by_id = {context.dataset.id: context for context in contexts}
    gap_entity_evidence: dict[str, GapEntityEvidence] = {}
    candidate_evidence: list[GapCandidateEvidence] = []
    for row in rows:
        entity = entity_by_id.get(row["entity_id"])
        if entity is not None:
            evidence = _token_evidence_from_text(
                entity.id,
                entity.title,
                entity.content_preview,
                broad_tokens=ENTITY_SUPPRESSED_TOKENS,
            )
            gap_entity_evidence[row["entity_id"]] = {
                "entity_tokens": sorted(entity.tokens),
                "dropped_tokens": {
                    "stop": sorted(evidence.stop),
                    "broad_entity": sorted(evidence.broad),
                    "short": sorted(evidence.short),
                },
                "facet_hints": list(row["suggested_search_facets"]),
                "gap_level_reason": row["reason"],
            }
        for candidate in row["candidate_benchmarks"]:
            context = context_by_id.get(candidate["benchmark_id"])
            if context is None:
                continue
            score = candidate_scores[(row["entity_id"], candidate["benchmark_id"])]
            candidate_evidence.append(
                {
                    "entity_id": row["entity_id"],
                    "benchmark_id": candidate["benchmark_id"],
                    "candidate_score": score.total,
                    "dropped_dataset_facets": _dataset_broad_facets(context),
                    "components": dict(score.components),
                    "reason_notes": list(candidate["reason_notes"]),
                }
            )
    return {
        "enabled": True,
        "gap_entity_evidence": gap_entity_evidence,
        "candidate_evidence": candidate_evidence,
    }


def _build_opportunity_report(
    entities: list[ProjectBenchmarkEntity],
    contexts: list[DatasetOpportunityContext],
    notice: str | None,
    *,
    calibration_report: bool,
) -> OpportunityReport:
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


def _opportunity_analysis(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    calibration_report: bool = False,
    include_prose_tokens: bool | None = None,
) -> OpportunityAnalysis:
    entities = load_project_entities(project_root)
    if entity_id is not None:
        entities = [entity for entity in entities if entity.id == entity_id]
    datasets, notice = load_opportunity_datasets(project_root, include_commons=include_commons)
    if domain is not None:
        datasets = [dataset for dataset in datasets if domain in dataset.domains]
    should_include_prose = calibration_report if include_prose_tokens is None else include_prose_tokens
    contexts = [_dataset_context(dataset, include_prose_tokens=should_include_prose) for dataset in datasets]
    report = _build_opportunity_report(
        entities,
        contexts,
        notice,
        calibration_report=calibration_report,
    )
    return OpportunityAnalysis(entities=entities, contexts=contexts, report=report)


def opportunity_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    calibration_report: bool = False,
) -> OpportunityReport:
    return _opportunity_analysis(
        project_root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        calibration_report=calibration_report,
    ).report


def gaps_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    facet: str | None = None,
    calibration_report: bool = False,
    evidence_report: bool = False,
) -> BenchmarkGapReport:
    normalized_facet = _normalized_gap_facet(facet)
    analysis = _opportunity_analysis(
        project_root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        include_prose_tokens=False,
    )
    opportunity = analysis.report
    matched = _matched_by_entity(opportunity["matched_opportunities"])
    coverage = _coverage_gap_by_entity(opportunity["coverage_gaps"])
    titles = _entity_title_map(opportunity)
    unmapped_ids = {row["entity_id"] for row in opportunity["unmapped_project_entities"]}
    entity_ids = sorted(set(matched) | set(coverage) | unmapped_ids)
    entity_by_id = {entity.id: entity for entity in analysis.entities}
    candidate_score_index: CandidateScoreIndex = {}

    rows: list[BenchmarkGapRow] = []
    for current_entity_id in entity_ids:
        current_matches = matched.get(current_entity_id, [])
        gap = coverage.get(current_entity_id)
        missing_modalities = list(gap["missing_modalities"]) if gap is not None else []
        missing_signal_types = list(gap["missing_signal_types"]) if gap is not None else []
        missing_facets = {_normalize_token(value) for value in missing_modalities + missing_signal_types}
        entity = entity_by_id.get(current_entity_id)
        hint_facets = set(_entity_facet_hints(entity)) if entity is not None else set()
        weak_match_facets: set[str] = set()
        if _is_weak_gap(current_matches):
            for match in current_matches:
                weak_match_facets.update(_normalize_token(value) for value in match["modalities"])
                weak_match_facets.update(_normalize_token(value) for value in match["signal_types"])
            weak_match_facets &= BENCHMARK_GAP_HINT_FACET_SET
        suggested_facets = _sorted_facets(missing_facets | hint_facets | weak_match_facets)

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

        if normalized_facet is not None and normalized_facet not in suggested_facets:
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
                    current_entity_id,
                    analysis.contexts,
                    current_matches,
                    missing_facets,
                    hint_facets,
                    candidate_score_index,
                ),
                "suggested_search_facets": suggested_facets,
                "reason": reason,
            }
        )

    rows.sort(key=lambda row: (_gap_level_sort_key(row["gap_level"]), row["entity_id"]))
    calibration = _gap_calibration_payload(
        rows,
        entities=analysis.entities,
        contexts=analysis.contexts,
        candidate_scores=candidate_score_index,
        enabled=calibration_report,
    )
    return {
        "benchmark_gaps": rows,
        "summary": _gap_summary(rows, entities_total=len(entity_ids)),
        "calibration": calibration,
        "evidence_report": _gap_evidence_report(
            rows,
            entities=analysis.entities,
            matched=matched,
            enabled=evidence_report,
        ),
        "commons_notice": opportunity["commons_notice"],
    }
