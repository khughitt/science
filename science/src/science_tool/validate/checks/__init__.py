from __future__ import annotations

import importlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel
from science_model.audit import FindingRule, FindingSection

from science_tool.findings.producers import (
    FindingProducer,
    FindingProducerResult,
    KindRuleFactory,
)
from science_tool.validate.observations import (
    ValidationMetricObservation,
    ValidationNotice,
    ValidationObservationBatch,
)
from science_tool.validate.result import Result

if TYPE_CHECKING:
    from science_tool.validate.context import ValidateContext


CheckObservation = Result | ValidationMetricObservation | ValidationNotice
InternalCheckFn = Callable[["ValidateContext"], Iterable[CheckObservation]]
RegisteredCheckFn = Callable[[ValidationObservationBatch], FindingProducerResult]


@dataclass(frozen=True)
class CheckEntry:
    section: str
    order: int
    fn: InternalCheckFn
    produce: RegisteredCheckFn
    producer: FindingProducer


CANONICAL_CHECKS: list[CheckEntry] = []
CANONICAL_CHECK_MODULES = (
    "tooling",
    "manifest",
    "registration_consistency",
    "directory_structure",
    "code_files",
    "research_scope",
    "document_structure",
    "hypotheses",
    "references",
    "papers",
    "unresolved_markers",
    "gap_analysis",
    "project_readme",
    "discussions",
    "prereg",
    "prereg_vehicles",
    "prereg_schedule",
    "hypothesis_comparisons",
    "bias_audits",
    "notes",
    "graph",
    "tasks",
    "id_prefixes",
    "status_vocabulary",
    "entity_conformance",
    "cross_references",
    "reference_collections",
    "identity_context",
    "dataset_taxonomy",
    "dataset_acquisition",
    "dataset_metadata",
    "dataset_capabilities",
    "aggregation_support",
    "benchmark_metadata",
    "dataset_lineage",
    "dataset_promotion_contract",
    "orphan_datapackage_owner",
    "identity_collision",
    "commons_owner_collision",
    "overlay_local_duplicate",
    "variant_identity",
    "genesets",
    "reference_graphs",
    "dataset_influence",
    "labnote_export",
    "prose_lints",
    "annotations",
    "evidence_lines",
    "verdict_agreement",
    "propositions",
    "origins",
    "lens_views",
    "workflow_runs",
    "workflow_steps",
    "methods",
    "relations",
    "supersession",
    "materialization",
    "correspondence_drift",
    "review_confirmations",
    "accepted_validation",
    "autonomous_runs",
    "boundary",
)


class Check:
    def __init__(
        self,
        section: FindingSection,
        order: int,
        *,
        producer_id: str,
        rules: tuple[FindingRule, ...],
        metrics_schema: type[BaseModel] | None = None,
        kind_rule_factory: KindRuleFactory | None = None,
    ) -> None:
        self.section = section
        self.order = order
        self.producer_id = producer_id
        self.rules = rules
        self.metrics_schema = metrics_schema
        self.kind_rule_factory = kind_rule_factory

    def __call__(self, fn: InternalCheckFn) -> InternalCheckFn:
        producer = FindingProducer(
            producer_id=self.producer_id,
            namespace="validate_checks",
            source_module=(fn.__module__.removeprefix("science_tool.").replace(".", "/") + ".py"),
            rules=self.rules,
            sections=(self.section,),
            metrics_schema=self.metrics_schema,
            kind_rule_factory=self.kind_rule_factory,
        )

        def produce(batch: ValidationObservationBatch) -> FindingProducerResult:
            return batch.producer_result()

        CANONICAL_CHECKS.append(
            CheckEntry(
                section=self.section.title,
                order=self.order,
                fn=fn,
                produce=produce,
                producer=producer,
            )
        )
        CANONICAL_CHECKS.sort(key=lambda entry: entry.order)
        return fn


def clear_checks_for_tests() -> None:
    CANONICAL_CHECKS.clear()


def _load_canonical_checks() -> None:
    for module_name in CANONICAL_CHECK_MODULES:
        importlib.import_module(f"{__name__}.{module_name}")


_load_canonical_checks()
