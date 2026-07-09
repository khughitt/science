"""Obligation table for `science-run-fingerprint/v1`.

The model owns the vocabulary; this module owns the obligations — mirroring the
`belief_weights` / `_reconcile_evidence_vocab` split.

Obligation is a pure function of the DECLARED executor kind and the DECLARED
artifact locality. It is never a function of what validate can observe on disk.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from science_model.run_fingerprint import (
    ArtifactLocality,
    ComponentProvenance,
    ExecutorKind,
    FingerprintComponent,
    RunFingerprint,
)


class Obligation(StrEnum):
    MUST_CAPTURED = "must-captured"
    MAY_ATTESTED = "may-attested"
    MAY_UNKNOWN = "may-unknown"
    NOT_APPLICABLE = "not-applicable"
    BY_LOCALITY = "by-locality"  # resolved by `obligation_for`; never returned


COMPONENT_FIELDS: tuple[str, ...] = (
    "code_sha",
    "code_dirty",
    "environment_digest",
    "container_digest",
    "parameters_digest",
    "input_manifest_digest",
    "output_manifest_digest",
)

#: Which fingerprint scalar decides a locality-scoped component's obligation.
_LOCALITY_FIELD: Mapping[str, str] = MappingProxyType(
    {
        "input_manifest_digest": "input_artifact_locality",
        "output_manifest_digest": "output_artifact_locality",
    }
)

LOCALITY_OBLIGATION: Mapping[ArtifactLocality, Obligation] = MappingProxyType(
    {
        ArtifactLocality.SCIENCE_MANAGED: Obligation.MUST_CAPTURED,
        ArtifactLocality.EXTERNAL: Obligation.MAY_ATTESTED,
    }
)

OBLIGATIONS: Mapping[ExecutorKind, Mapping[str, Obligation]] = MappingProxyType(
    {
        ExecutorKind.LOCAL: MappingProxyType(
            {
                "code_sha": Obligation.MUST_CAPTURED,
                "code_dirty": Obligation.MUST_CAPTURED,
                "environment_digest": Obligation.MUST_CAPTURED,
                "container_digest": Obligation.NOT_APPLICABLE,
                "parameters_digest": Obligation.MUST_CAPTURED,
                "input_manifest_digest": Obligation.BY_LOCALITY,
                "output_manifest_digest": Obligation.BY_LOCALITY,
            }
        ),
        ExecutorKind.COMMONS: MappingProxyType(
            {
                "code_sha": Obligation.MUST_CAPTURED,
                "code_dirty": Obligation.MUST_CAPTURED,
                "environment_digest": Obligation.MUST_CAPTURED,
                # No standalone "we used no container" state existed under MAY_ATTESTED
                # (a present-but-unknown component still failed as incomplete), so a
                # legitimately containerless commons run had no way to say so.
                "container_digest": Obligation.MAY_UNKNOWN,
                "parameters_digest": Obligation.MUST_CAPTURED,
                "input_manifest_digest": Obligation.BY_LOCALITY,
                "output_manifest_digest": Obligation.BY_LOCALITY,
            }
        ),
        ExecutorKind.EXTERNAL: MappingProxyType(
            {
                "code_sha": Obligation.MUST_CAPTURED,
                "code_dirty": Obligation.MAY_UNKNOWN,
                "environment_digest": Obligation.MAY_ATTESTED,
                # See the COMMONS comment above — same rationale.
                "container_digest": Obligation.MAY_UNKNOWN,
                "parameters_digest": Obligation.MAY_ATTESTED,
                "input_manifest_digest": Obligation.BY_LOCALITY,
                "output_manifest_digest": Obligation.BY_LOCALITY,
            }
        ),
    }
)


def obligation_for(
    executor: ExecutorKind, component: str, fingerprint: RunFingerprint
) -> Obligation:
    """Resolve a component's obligation, collapsing BY_LOCALITY to a concrete one."""
    declared = OBLIGATIONS[executor][component]
    if declared is not Obligation.BY_LOCALITY:
        return declared
    locality: ArtifactLocality = getattr(fingerprint, _LOCALITY_FIELD[component])
    return LOCALITY_OBLIGATION[locality]


def _reconcile_obligation_table() -> None:
    """Fail at import if the table and the model have drifted apart."""
    model_components = {
        name
        for name, field in RunFingerprint.model_fields.items()
        if "FingerprintComponent" in str(field.annotation)
    }
    if set(COMPONENT_FIELDS) != model_components:
        raise RuntimeError(
            "run-fingerprint drift: COMPONENT_FIELDS "
            f"{sorted(COMPONENT_FIELDS)} != RunFingerprint components {sorted(model_components)}"
        )
    for executor in ExecutorKind:
        declared = set(OBLIGATIONS[executor])
        if declared != model_components:
            missing = sorted(model_components - declared)
            extra = sorted(declared - model_components)
            raise RuntimeError(
                f"run-fingerprint drift for executor={executor.value}: missing={missing} extra={extra}"
            )
    if set(LOCALITY_OBLIGATION) != set(ArtifactLocality):
        raise RuntimeError("run-fingerprint drift: LOCALITY_OBLIGATION must cover every ArtifactLocality")


_reconcile_obligation_table()


RULE_INCOMPLETE = "run.fingerprint-incomplete"
RULE_AUTHORED_CAPTURABLE = "run.fingerprint-authored-capturable"


@dataclass(frozen=True, slots=True)
class FingerprintFinding:
    rule: str
    message: str


def _evaluate_component(
    name: str, component: FingerprintComponent | None, obligation: Obligation
) -> FingerprintFinding | None:
    if obligation is Obligation.NOT_APPLICABLE:
        if component is not None:
            return FingerprintFinding(
                RULE_INCOMPLETE, f"{name} is not applicable for this executor but is present"
            )
        return None

    if component is None:
        return FingerprintFinding(RULE_INCOMPLETE, f"{name} is required but absent")

    if obligation is Obligation.MUST_CAPTURED:
        if component.provenance is ComponentProvenance.CAPTURED:
            return None
        if component.provenance is ComponentProvenance.ATTESTED:
            return FingerprintFinding(
                RULE_AUTHORED_CAPTURABLE,
                f"{name} must be captured for this executor but is attested",
            )
        return FingerprintFinding(RULE_INCOMPLETE, f"{name} must be captured but is unknown")

    if obligation is Obligation.MAY_ATTESTED:
        if component.provenance is ComponentProvenance.UNKNOWN:
            return FingerprintFinding(
                RULE_INCOMPLETE, f"{name} must be captured or attested but is unknown"
            )
        return None

    if obligation is Obligation.MAY_UNKNOWN:
        # Any present state is acceptable.
        return None

    raise AssertionError(f"unhandled obligation {obligation!r} for component {name!r}")


def evaluate_fingerprint(fingerprint: RunFingerprint) -> list[FingerprintFinding]:
    """Findings for one run's fingerprint. Pure; reads no disk state."""
    findings: list[FingerprintFinding] = []
    for name in COMPONENT_FIELDS:
        obligation = obligation_for(fingerprint.executor, name, fingerprint)
        finding = _evaluate_component(name, getattr(fingerprint, name), obligation)
        if finding is not None:
            findings.append(finding)
    return sorted(findings, key=lambda f: f.message)
