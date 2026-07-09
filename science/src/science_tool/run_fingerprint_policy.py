"""Obligation table for `science-run-fingerprint/v1`.

The model owns the vocabulary; this module owns the obligations — mirroring the
`belief_weights` / `_reconcile_evidence_vocab` split.

Obligation is a pure function of the DECLARED executor kind and the DECLARED
artifact locality. It is never a function of what validate can observe on disk.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType

from science_model.run_fingerprint import (
    ArtifactLocality,
    ExecutorKind,
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
                "container_digest": Obligation.MAY_ATTESTED,
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
                "container_digest": Obligation.MAY_ATTESTED,
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
