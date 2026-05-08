"""Evidence payload core schema and extension-contract validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ComparisonTarget = Literal["null-vs-alternative", "hypothesis-set", "model-set", "artifact-target", "n-a"]
SupportDirection = Literal[
    "supports",
    "disputes",
    "qualifies",
    "methodological-input",
    "quality-record",
    "operation-record",
]
ValidationRole = Literal[
    "strengthen-belief",
    "prioritize-attention",
    "create-hypothesis",
    "gate-update",
    "quality-record-only",
    "record-only",
]
ValidationStatus = Literal["validated", "pending", "failed", "not-applicable", "unknown"]
PropagationPolicy = Literal["propagate-all", "propagate-blocking", "propagate-tagged-only", "no-propagate"]


class PayloadValidationError(ValueError):
    """Raised when an evidence payload violates the core/extension contract."""


class EvidencePayloadCore(BaseModel):
    """Small, mandatory core carried by evidence, synthesis, evaluation, and operation payloads."""

    model_config = ConfigDict(extra="forbid")

    payload_id: str
    artifact_type: str
    extensions: list[str]
    created_at: datetime
    source_commit: str | None = None

    input_artifact_refs: list[str]
    method_ref: str | None = None
    agent_ref: str | None = None
    pipeline_provenance_ref: str | None = None

    proposition_refs: list[str]
    target_artifact_ref: str | None = None
    comparison_target: ComparisonTarget

    support_direction: SupportDirection
    validation_role: ValidationRole
    validation_status: ValidationStatus
    uncertainty_summary: str

    reason_codes: list[str]
    abstention_reason: str | None = None

    @field_validator("extensions")
    @classmethod
    def _extensions_non_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("core.extensions must list at least the primary extension")
        return value

    @model_validator(mode="after")
    def _has_attachment(self) -> "EvidencePayloadCore":
        if not self.proposition_refs and self.target_artifact_ref is None and not self.input_artifact_refs:
            raise ValueError(
                "payload must attach through proposition_refs, target_artifact_ref, or input_artifact_refs"
            )
        return self


class EvidencePayload(BaseModel):
    """A parsed evidence payload document.

    The preferred Python representation stores extension bodies in ``extension_sections``.
    For YAML documents that use plan-style keys such as ``extension/causal-graph``, those
    keys are folded into ``extension_sections`` during validation.
    """

    model_config = ConfigDict(extra="forbid")

    core: EvidencePayloadCore
    extension_sections: dict[str, dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _fold_plan_style_extension_keys(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        extension_sections = dict(data.get("extension_sections") or {})
        remaining: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(key, str) and key.startswith("extension/"):
                extension_sections[key.removeprefix("extension/")] = value
            else:
                remaining[key] = value
        if extension_sections:
            remaining["extension_sections"] = extension_sections
        return remaining


class ReasonCodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    blocking: bool = False


class ValidationRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ValidationRole
    required_fields: dict[str, Any] = Field(default_factory=dict)
    blocked_by_reason_codes: list[str] = Field(default_factory=list)


class ExtensionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    artifact_type: str
    required_fields: list[str] = Field(default_factory=list)
    optional_fields: list[str] = Field(default_factory=list)
    co_required_extensions: list[str] = Field(default_factory=list)
    validation_rules: list[ValidationRule] = Field(default_factory=list)
    static_reason_codes: list[str] = Field(default_factory=list)
    propagation_policy: PropagationPolicy = "propagate-blocking"
    owning_task: str | None = None
    uncertainty_summary_contract: str | None = None


@dataclass(frozen=True)
class ReasonCodeOccurrence:
    code: str
    origin: str
    chain: tuple[str, ...]


class EvidencePayloadRegistry:
    """Registry for extension specs, reason-code semantics, and payload validation."""

    def __init__(self) -> None:
        self._extensions: dict[str, ExtensionSpec] = {}
        self._reason_codes: dict[str, ReasonCodeSpec] = {}

    def register_reason_code(self, spec: ReasonCodeSpec) -> None:
        if spec.code in self._reason_codes:
            raise PayloadValidationError(f"reason code {spec.code!r} is already registered")
        self._reason_codes[spec.code] = spec

    def register_extension(self, spec: ExtensionSpec) -> None:
        if spec.name in self._extensions:
            raise PayloadValidationError(f"extension {spec.name!r} is already registered")
        self._extensions[spec.name] = spec

    def extension(self, name: str) -> ExtensionSpec:
        try:
            return self._extensions[name]
        except KeyError as exc:
            raise PayloadValidationError(f"extension {name!r} is not registered") from exc

    def reason_code(self, code: str) -> ReasonCodeSpec:
        return self._reason_codes.get(code, ReasonCodeSpec(code=code, blocking=False))

    def validate_payload(
        self,
        payload: EvidencePayload,
        *,
        payloads_by_id: dict[str, EvidencePayload] | None = None,
    ) -> None:
        self._validate_extension_contract(payload)
        codes = effective_reason_codes(payload, self, payloads_by_id=payloads_by_id)
        self._validate_reason_codes_known(codes)
        self._validate_role(payload, codes)

    def _validate_extension_contract(self, payload: EvidencePayload) -> None:
        primary_name = payload.core.extensions[0]
        primary = self.extension(primary_name)
        if payload.core.artifact_type != primary.artifact_type:
            raise PayloadValidationError(
                f"core.artifact_type {payload.core.artifact_type!r} does not match primary extension "
                f"{primary_name!r} artifact_type {primary.artifact_type!r}"
            )

        missing_sections = [name for name in payload.core.extensions if name not in payload.extension_sections]
        if missing_sections:
            missing = ", ".join(repr(name) for name in missing_sections)
            raise PayloadValidationError(f"missing extension section(s): {missing}")

        required = self._transitive_co_required_extensions(payload.core.extensions)
        listed = set(payload.core.extensions)
        for name in sorted(required - listed):
            raise PayloadValidationError(f"extension {primary_name!r} requires co-required extension {name!r}")

        for name in payload.core.extensions:
            spec = self.extension(name)
            section = payload.extension_sections[name]
            for field in spec.required_fields:
                if field not in section:
                    raise PayloadValidationError(f"extension {name!r} missing required field {field!r}")

    def _transitive_co_required_extensions(self, names: list[str]) -> set[str]:
        required: set[str] = set()
        stack = list(names)
        while stack:
            name = stack.pop()
            spec = self.extension(name)
            for co_required in spec.co_required_extensions:
                if co_required not in required:
                    required.add(co_required)
                    stack.append(co_required)
        return required

    def _validate_reason_codes_known(self, codes: list[ReasonCodeOccurrence]) -> None:
        unknown = sorted({item.code for item in codes if item.code not in self._reason_codes})
        if unknown:
            joined = ", ".join(repr(code) for code in unknown)
            raise PayloadValidationError(f"unknown reason code(s): {joined}")

    def _validate_role(self, payload: EvidencePayload, codes: list[ReasonCodeOccurrence]) -> None:
        if payload.core.validation_role == "strengthen-belief":
            blocking_codes = sorted({item.code for item in codes if self.reason_code(item.code).blocking})
            if blocking_codes:
                joined = ", ".join(blocking_codes)
                raise PayloadValidationError(
                    f"validation_role 'strengthen-belief' is blocked by effective reason code(s): {joined}"
                )

        for name in payload.core.extensions:
            spec = self.extension(name)
            section = payload.extension_sections[name]
            for rule in spec.validation_rules:
                if rule.role != payload.core.validation_role:
                    continue
                present_codes = {item.code for item in codes}
                blocked = sorted(set(rule.blocked_by_reason_codes) & present_codes)
                if blocked:
                    raise PayloadValidationError(
                        f"validation_role {rule.role!r} blocked by reason code(s): {', '.join(blocked)}"
                    )
                for field, expected in rule.required_fields.items():
                    actual = section.get(field)
                    if actual != expected:
                        raise PayloadValidationError(
                            f"validation_role {rule.role!r} requires extension {name!r} field "
                            f"{field!r}={expected!r}; got {actual!r}"
                        )


def effective_reason_codes(
    payload: EvidencePayload,
    registry: EvidencePayloadRegistry,
    *,
    payloads_by_id: dict[str, EvidencePayload] | None = None,
    max_depth: int = 8,
) -> list[ReasonCodeOccurrence]:
    """Return declared, extension-static, and inherited reason-code occurrences."""

    payloads = payloads_by_id or {}
    occurrences: list[ReasonCodeOccurrence] = []
    occurrences.extend(_declared_occurrences(payload))
    for name in payload.core.extensions:
        spec = registry.extension(name)
        occurrences.extend(_extension_section_occurrences(payload, name))
        for code in spec.static_reason_codes:
            occurrences.append(ReasonCodeOccurrence(code=code, origin=name, chain=(payload.core.payload_id,)))
    occurrences.extend(
        _inherited_occurrences(
            payload,
            registry,
            payloads_by_id=payloads,
            chain=(payload.core.payload_id,),
            max_depth=max_depth,
        )
    )
    return _dedupe_occurrences(occurrences)


def _declared_occurrences(payload: EvidencePayload) -> list[ReasonCodeOccurrence]:
    return [
        ReasonCodeOccurrence(code=code, origin="core", chain=(payload.core.payload_id,))
        for code in payload.core.reason_codes
    ]


def _extension_section_occurrences(payload: EvidencePayload, extension_name: str) -> list[ReasonCodeOccurrence]:
    section = payload.extension_sections.get(extension_name, {})
    raw_codes = section.get("reason_codes", [])
    if not isinstance(raw_codes, list) or any(not isinstance(code, str) for code in raw_codes):
        raise PayloadValidationError(f"extension {extension_name!r} reason_codes must be a list of strings")
    return [
        ReasonCodeOccurrence(code=code, origin=extension_name, chain=(payload.core.payload_id,)) for code in raw_codes
    ]


def _inherited_occurrences(
    payload: EvidencePayload,
    registry: EvidencePayloadRegistry,
    *,
    payloads_by_id: dict[str, EvidencePayload],
    chain: tuple[str, ...],
    max_depth: int,
) -> list[ReasonCodeOccurrence]:
    if len(chain) > max_depth:
        return []

    inherited: list[ReasonCodeOccurrence] = []
    for ref in payload.core.input_artifact_refs:
        upstream = payloads_by_id.get(ref)
        if upstream is None or upstream.core.payload_id in chain:
            continue
        upstream_chain = (*chain, upstream.core.payload_id)
        upstream_codes = effective_reason_codes(
            upstream,
            registry,
            payloads_by_id=payloads_by_id,
            max_depth=max_depth - 1,
        )
        policy = registry.extension(upstream.core.extensions[0]).propagation_policy
        for item in upstream_codes:
            if _propagates(item, registry, policy):
                inherited.append(ReasonCodeOccurrence(code=item.code, origin="inherited", chain=upstream_chain))
    return inherited


def _propagates(item: ReasonCodeOccurrence, registry: EvidencePayloadRegistry, policy: PropagationPolicy) -> bool:
    if policy == "propagate-all":
        return True
    if policy == "propagate-blocking":
        return registry.reason_code(item.code).blocking
    if policy in {"propagate-tagged-only", "no-propagate"}:
        return False
    raise AssertionError(f"unhandled propagation policy: {policy}")


def _dedupe_occurrences(items: list[ReasonCodeOccurrence]) -> list[ReasonCodeOccurrence]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    deduped: list[ReasonCodeOccurrence] = []
    for item in items:
        key = (item.code, item.origin, item.chain)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped
