"""Analysis-run reproducibility fingerprint (science-run-fingerprint/v1).

Leaf module: imports nothing from `science_model.entities`, so `entities.py`
may import it without a cycle.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

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
