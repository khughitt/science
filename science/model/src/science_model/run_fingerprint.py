"""Analysis-run reproducibility fingerprint (science-run-fingerprint/v1).

Leaf module: imports nothing from `science_model.entities`, so `entities.py`
may import it without a cycle.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class ComponentProvenance(StrEnum):
    CAPTURED = "captured"
    ATTESTED = "attested"
    UNKNOWN = "unknown"


class FingerprintComponent(BaseModel):
    """One fingerprint fact plus how it was obtained.

    `""` is unrepresentable: a captured/attested component must carry a
    non-empty value, and an unknown component must carry none.
    """

    model_config = ConfigDict(extra="forbid")

    value: str | None = None
    provenance: ComponentProvenance
    attested_by: str | None = None
    attested_at: datetime | None = None
    evidence_ref: str | None = None

    @model_validator(mode="after")
    def _validate_tristate(self) -> "FingerprintComponent":
        if self.provenance is ComponentProvenance.UNKNOWN:
            if self.value is not None:
                raise ValueError("unknown component must not carry a value")
            if self.attested_by is not None or self.attested_at is not None:
                raise ValueError("unknown component must not carry attestation fields")
            return self

        if self.value is None or not self.value.strip():
            raise ValueError(f"{self.provenance.value} component requires a non-empty value")

        if self.provenance is ComponentProvenance.ATTESTED:
            if self.attested_by is None or self.attested_at is None:
                raise ValueError("attested component requires attested_by and attested_at")
        else:  # CAPTURED
            if self.attested_by is not None or self.attested_at is not None:
                raise ValueError("captured component must not carry attested_by/attested_at")
        return self


FINGERPRINT_POLICY_V1 = "science-run-fingerprint/v1"


class ExecutorKind(StrEnum):
    LOCAL = "local"
    COMMONS = "commons"
    EXTERNAL = "external"


class ArtifactLocality(StrEnum):
    SCIENCE_MANAGED = "science-managed"
    EXTERNAL = "external"


class SeedPolicy(BaseModel):
    """An assertion about how the code behaves — not an observation of a run."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["seeded", "deterministic", "stochastic-unseeded"]
    seeds: dict[str, int] | None = None
    rationale: str | None = None

    @model_validator(mode="after")
    def _validate_kind(self) -> "SeedPolicy":
        if self.kind == "seeded":
            if not self.seeds:
                raise ValueError("seed_policy kind='seeded' requires a non-empty seeds mapping")
            if self.rationale is not None:
                raise ValueError("seed_policy kind='seeded' must not carry a rationale")
        elif self.kind == "stochastic-unseeded":
            if not self.rationale:
                raise ValueError("seed_policy kind='stochastic-unseeded' requires a rationale")
            if self.seeds is not None:
                raise ValueError("seed_policy kind='stochastic-unseeded' must not carry seeds")
        else:  # deterministic
            if self.seeds is not None or self.rationale is not None:
                raise ValueError("seed_policy kind='deterministic' takes neither seeds nor rationale")
        return self


class CaptureOrigin(BaseModel):
    """Who captured the fingerprint, when, and under which policy version.

    Required when `executor == commons`: the producing Science project captured
    these facts; the consuming project imports a verifiable record.
    """

    model_config = ConfigDict(extra="forbid")

    origin_project: str
    origin_run_ref: str
    captured_at: datetime
    captured_by: str  # tool/agent/system — not necessarily a person
    capture_policy: str  # the ORIGIN's policy version
    source_ref: str | None = None
    source_digest: str | None = None

    @field_validator("origin_run_ref")
    @classmethod
    def _run_ref_prefix(cls, v: str) -> str:
        if not v.startswith("workflow-run:"):
            raise ValueError(f"origin_run_ref must be a workflow-run:<slug> reference, got {v!r}")
        return v


class RunFingerprint(BaseModel):
    """A captured reproducibility fingerprint for one workflow run.

    Which components must be `captured` (vs. `attested`/`unknown`) is decided
    elsewhere, by a frozen obligation table keyed on the declared `executor`
    and artifact localities — this model only enforces well-formedness.
    """

    model_config = ConfigDict(extra="forbid")

    # Spelled as a bare literal because `Literal[<variable>]` is not a valid type
    # expression; `_POLICY_LITERAL_MATCHES_CONSTANT` below keeps it tied to
    # FINGERPRINT_POLICY_V1 so the two cannot drift.
    fingerprint_policy: Literal["science-run-fingerprint/v1"]
    executor: ExecutorKind
    input_artifact_locality: ArtifactLocality
    output_artifact_locality: ArtifactLocality
    capture_origin: CaptureOrigin | None = None

    code_sha: FingerprintComponent
    code_dirty: FingerprintComponent
    environment_digest: FingerprintComponent
    container_digest: FingerprintComponent | None = None
    parameters_digest: FingerprintComponent
    input_manifest_digest: FingerprintComponent
    output_manifest_digest: FingerprintComponent

    input_manifest_ref: str | None = None
    output_manifest_ref: str | None = None

    seed_policy: SeedPolicy

    @field_validator("code_dirty")
    @classmethod
    def _dirty_token(cls, v: FingerprintComponent) -> FingerprintComponent:
        if v.value is not None and v.value not in ("true", "false"):
            raise ValueError(f'code_dirty.value must be "true" or "false", got {v.value!r}')
        return v

    @model_validator(mode="after")
    def _capture_origin_iff_commons(self) -> "RunFingerprint":
        is_commons = self.executor is ExecutorKind.COMMONS
        if is_commons and self.capture_origin is None:
            raise ValueError("executor='commons' requires capture_origin")
        if not is_commons and self.capture_origin is not None:
            raise ValueError(f"capture_origin is only valid for executor='commons', not {self.executor.value!r}")
        return self


def _reconcile_policy_literal() -> None:
    """Fail at import if the annotated literal and FINGERPRINT_POLICY_V1 drift apart."""
    (annotated,) = get_args(RunFingerprint.model_fields["fingerprint_policy"].annotation)
    if annotated != FINGERPRINT_POLICY_V1:
        raise RuntimeError(
            f"run-fingerprint drift: RunFingerprint.fingerprint_policy accepts {annotated!r} "
            f"but FINGERPRINT_POLICY_V1 is {FINGERPRINT_POLICY_V1!r}"
        )


_reconcile_policy_literal()
