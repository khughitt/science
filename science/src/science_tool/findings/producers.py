"""Producer registration and the derived frozen registry (design §6).

Rules are declared beside the producer that emits them; this module derives one
immutable lookup authority from those declarations. There is no hand-maintained
central table, so no repeated rule-id string can drift.

Not project-overridable by construction: nothing here reads project
configuration, the environment, or any file. A project needing different audit
rules is a design conversation, not a config key.

Registration is generic -- deliberately not HealthCheck-shaped -- so health
checks, validation modules, data_audit, and later Pi lenses all participate
without making health the ontology owner.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator
from science_model.audit import FindingRule, FindingSection

#: Every namespace contributing producers to the derived registry. Each one must
#: have a filesystem-derived completeness guard (design §6); see
#: tests/test_findings_producer_namespaces.py.
PRODUCER_NAMESPACES: tuple[str, ...] = (
    "health_checks",
    "validate_checks",
    "data_audit",
)


class RegistryError(ValueError):
    """The derived registry is inconsistent, or a lookup names something undeclared."""


class FindingProducer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    producer_id: str
    namespace: str
    rules: tuple[FindingRule, ...]
    sections: tuple[FindingSection, ...] = ()
    metrics_schema: type[BaseModel] | None = None
    remediators: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _validate_metrics_schema(self) -> FindingProducer:
        if (
            self.metrics_schema is not None
            and self.metrics_schema.model_config.get("extra") != "forbid"
        ):
            raise ValueError(
                f"{self.producer_id!r} metrics schema "
                f"{self.metrics_schema.__name__} must set model_config extra='forbid'"
            )
        return self


@dataclass(frozen=True)
class FindingRegistry:
    """The one immutable lookup authority."""

    rules_by_id: Mapping[str, FindingRule]
    sections_by_id: Mapping[str, FindingSection]
    producers_by_id: Mapping[str, FindingProducer]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "rules_by_id",
            MappingProxyType(dict(self.rules_by_id)),
        )
        object.__setattr__(
            self,
            "sections_by_id",
            MappingProxyType(dict(self.sections_by_id)),
        )
        object.__setattr__(
            self,
            "producers_by_id",
            MappingProxyType(dict(self.producers_by_id)),
        )

    def rule(self, rule_id: str) -> FindingRule:
        try:
            return self.rules_by_id[rule_id]
        except KeyError:
            raise RegistryError(
                f"undeclared rule {rule_id!r}; a producer may only emit findings built "
                "from a declared FindingRule (design §6)"
            ) from None

    def section(self, section_id: str) -> FindingSection:
        try:
            return self.sections_by_id[section_id]
        except KeyError:
            raise RegistryError(f"undeclared section {section_id!r}") from None

    def sort_key(self, rule_id: str) -> tuple[int, int]:
        rule = self.rule(rule_id)
        return (self.section(rule.section).section_order, rule.display_order)

    def validate_metrics(self, producer_id: str, metrics: dict[str, object]) -> None:
        """Strictly validate metrics without mutating the original mapping."""
        producer = self.producers_by_id.get(producer_id)
        if producer is None:
            raise RegistryError(f"unregistered producer {producer_id!r}")
        if producer.metrics_schema is None:
            if metrics:
                raise RegistryError(
                    f"{producer_id!r} declared no metrics schema but emitted metrics"
                )
            return
        try:
            producer.metrics_schema.model_validate(dict(metrics), strict=True)
        except ValidationError as exc:
            raise RegistryError(f"{producer_id!r} metrics invalid: {exc}") from exc


def build_registry(producers: list[FindingProducer]) -> FindingRegistry:
    """Derive the frozen registry, failing early on every §6 condition."""
    rules_by_id: dict[str, FindingRule] = {}
    sections_by_id: dict[str, FindingSection] = {}
    producers_by_id: dict[str, FindingProducer] = {}
    order_claims: dict[tuple[str, int], str] = {}
    section_order_claims: dict[int, str] = {}

    for producer in producers:
        if producer.producer_id in producers_by_id:
            raise RegistryError(f"duplicate producer id {producer.producer_id!r}")
        if producer.namespace not in PRODUCER_NAMESPACES:
            raise RegistryError(
                f"{producer.producer_id!r} declares namespace {producer.namespace!r}, "
                "which is not in PRODUCER_NAMESPACES"
            )
        producers_by_id[producer.producer_id] = producer

        for section in producer.sections:
            existing = sections_by_id.get(section.id)
            if existing is not None and existing != section:
                raise RegistryError(f"conflicting declarations for section {section.id!r}")
            claimed = section_order_claims.get(section.section_order)
            if claimed is not None and claimed != section.id:
                raise RegistryError(
                    f"section_order {section.section_order} claimed by both "
                    f"{claimed!r} and {section.id!r}"
                )
            section_order_claims[section.section_order] = section.id
            sections_by_id[section.id] = section

        for rule in producer.rules:
            if rule.id in rules_by_id:
                raise RegistryError(f"duplicate rule id {rule.id!r}")
            rules_by_id[rule.id] = rule
            if rule.remediation == "producer":
                if not rule.remediator or rule.remediator not in producer.remediators:
                    raise RegistryError(
                        f"{rule.id!r} declares remediation='producer' but its remediator "
                        f"{rule.remediator!r} is not registered by "
                        f"{producer.producer_id!r}"
                    )

    for rule in rules_by_id.values():
        if rule.section not in sections_by_id:
            raise RegistryError(f"{rule.id!r} names undeclared section {rule.section!r}")
        claim = (rule.section, rule.display_order)
        claimed_by = order_claims.get(claim)
        if claimed_by is not None:
            raise RegistryError(
                f"display_order {rule.display_order} in section {rule.section!r} is "
                f"claimed by both {claimed_by!r} and {rule.id!r}"
            )
        order_claims[claim] = rule.id

    return FindingRegistry(
        rules_by_id=MappingProxyType(dict(rules_by_id)),
        sections_by_id=MappingProxyType(dict(sections_by_id)),
        producers_by_id=MappingProxyType(dict(producers_by_id)),
    )
