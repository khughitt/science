"""The persisted shape of one FINALIZED autonomous run (autonomy envelope §2).

A run record is a supervisor-written attestation: who acted, under which tier and
policy, over which exact commit range, and how it was dispositioned. It is
deliberately NOT an entity kind -- it is provenance about an execution, never a
belief bearer, freshness subject, attention candidate, or `rdf:type` hub member.

Named `AutonomousRunRecord`, not `RunRecord`: `science_tool/qa_audit/runs.py`
already owns that name for fingerprinted *workflow* runs, which model compute
reproducibility rather than agent authority.

This module imports nothing from `science_model`. `entities.py` imports
RUN_ID_PREFIX from here, and the loader that needs `parse_frontmatter` lives in
`science_tool.graph.autonomous_runs` -- keeping this module import-free is what
makes that safe.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

RUN_ID_PREFIX = "run:"

_AGENT_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHORT_ID_RE = re.compile(r"^[a-z0-9]{4,}$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_DATE_LENGTH = len("YYYY-MM-DD")


class RunRecordError(ValueError):
    """A run record file is unreadable, malformed, or misfiled."""


class RunTier(StrEnum):
    """The write surface a run was granted. Attested by the supervisor.

    There is deliberately no `full` tier. A tier reserved "for later" is a tier
    something will eventually be granted.
    """

    REPORT_ONLY = "report-only"
    BELIEF_NEUTRAL = "belief-neutral"


class RunDisposition(StrEnum):
    """The verdict rendered on a finished run. Attested, never self-declared.

    `unwired` is not a weaker `clean`: it means the basis was not computable, and
    a guard that cannot see must not report clean.
    """

    CLEAN = "clean"
    QUARANTINED = "quarantined"
    UNWIRED = "unwired"


class PolicyIdentity(BaseModel):
    """The frozen `(policy_id, policy_version)` pair in force for a run.

    One model rather than two flat fields because the pair IS the identity --
    `bundle_belief` already refuses to mix records across it.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    version: str

    @model_validator(mode="after")
    def _validate(self) -> PolicyIdentity:
        for field_name in ("id", "version"):
            value: str = getattr(self, field_name)
            if not value.strip():
                raise ValueError(f"policy_identity {field_name} may not be blank")
        return self


class RunBudget(BaseModel):
    """What the run consumed. Slice S4 turns these into estimates."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tokens: int | None = None
    wall_clock_seconds: float | None = None

    @model_validator(mode="after")
    def _validate(self) -> RunBudget:
        if self.tokens is None and self.wall_clock_seconds is None:
            raise ValueError("budget must record tokens, wall_clock_seconds, or both")
        if self.tokens is not None and self.tokens < 0:
            raise ValueError(f"budget tokens may not be negative, got {self.tokens}")
        if self.wall_clock_seconds is not None:
            # Order matters: `nan < 0` and `inf < 0` are both False, so a sign check
            # alone admits both. Finiteness is checked first and separately.
            if not math.isfinite(self.wall_clock_seconds):
                raise ValueError(
                    f"budget wall_clock_seconds must be finite, got {self.wall_clock_seconds}"
                )
            if self.wall_clock_seconds < 0:
                raise ValueError(
                    f"budget wall_clock_seconds may not be negative, "
                    f"got {self.wall_clock_seconds}"
                )
        return self


class AutonomousRunRecord(BaseModel):
    """One finalized unattended run.

    Every attested field is required. There is no in-flight shape: a supervisor
    that dies mid-run leaves no record, so its branch reads as unattested rather
    than clean. That is the intended failure direction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    agent: str
    model: str
    tier: RunTier
    branch: str
    base_commit: str
    head_commit: str
    toolkit_revision: str
    policy_identity: PolicyIdentity
    # Required, EXCEPT when `disposition` is `unwired` — which the design defines as
    # "blocked; basis was not computable". Requiring a digest there would force the
    # supervisor to fabricate one, and a fabricated value inside an attestation is the
    # exact failure this slice exists to prevent. The rule is stricter than a plain
    # optional: absent is REQUIRED when unwired, and forbidden otherwise.
    basis_digest: str | None = None
    started: datetime
    ended: datetime
    budget: RunBudget
    disposition: RunDisposition
    # The ONLY optional field, and only because the design marks it
    # "Optional until S2; omitted, not blank, when absent".
    triggered_by: str | None = None

    @property
    def slug(self) -> str:
        """The id without its `run:` prefix — the filename stem and branch suffix."""
        return self.id[len(RUN_ID_PREFIX) :]

    @model_validator(mode="after")
    def _validate(self) -> AutonomousRunRecord:
        self._validate_identity()
        if not self.model.strip():
            raise ValueError("model may not be blank")
        if not self.agent.strip():
            raise ValueError("agent may not be blank")
        for field_name in ("base_commit", "head_commit", "toolkit_revision"):
            value: str = getattr(self, field_name)
            if not _SHA_RE.fullmatch(value):
                raise ValueError(
                    f"{field_name} must be a full 40-character lowercase hex sha, "
                    f"got {value!r}"
                )
        if self.disposition is RunDisposition.UNWIRED:
            if self.basis_digest is not None:
                raise ValueError(
                    "basis_digest must be omitted when disposition is 'unwired' — "
                    "an unwired run is one whose basis was not computable, so any "
                    f"digest is fabricated, got {self.basis_digest!r}"
                )
        elif self.basis_digest is None:
            raise ValueError(
                f"basis_digest is required when disposition is {self.disposition.value!r}"
            )
        elif not _DIGEST_RE.fullmatch(self.basis_digest):
            raise ValueError(
                f"basis_digest must be a 64-character lowercase sha256, "
                f"got {self.basis_digest!r}"
            )
        for field_name in ("started", "ended"):
            stamp: datetime = getattr(self, field_name)
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                raise ValueError(f"{field_name} must carry a timezone offset")
        if self.ended < self.started:
            raise ValueError(
                f"ended {self.ended.isoformat()} precedes started {self.started.isoformat()}"
            )
        if self.triggered_by is not None and not self.triggered_by.strip():
            raise ValueError("triggered_by must be omitted, not blank")
        return self

    def _validate_identity(self) -> None:
        """Check id, agent, and branch against each other.

        Constructive, not a parse: the agent slug contains hyphens, so
        `<date>-<agent>-<short>` has more than one reading. The record names its
        own agent, so validation rebuilds the id it must have and compares.
        """
        if not self.id.startswith(RUN_ID_PREFIX):
            raise ValueError(f"run id must start with {RUN_ID_PREFIX!r}, got {self.id!r}")
        if not _AGENT_RE.fullmatch(self.agent):
            raise ValueError(f"agent must be a kebab-case slug, got {self.agent!r}")
        slug = self.slug
        if len(slug) <= _DATE_LENGTH or slug[_DATE_LENGTH] != "-":
            raise ValueError(f"run id must begin with a YYYY-MM-DD date, got {self.id!r}")
        day_text = slug[:_DATE_LENGTH]
        try:
            date.fromisoformat(day_text)
        except ValueError as exc:
            raise ValueError(
                f"run id must begin with a real YYYY-MM-DD date, got {day_text!r}"
            ) from exc
        remainder = slug[_DATE_LENGTH + 1 :]
        agent_prefix = f"{self.agent}-"
        if not remainder.startswith(agent_prefix):
            raise ValueError(f"run id {self.id!r} must name its agent {self.agent!r}")
        short_id = remainder[len(agent_prefix) :]
        if not _SHORT_ID_RE.fullmatch(short_id):
            raise ValueError(
                f"run id short suffix must be at least 4 lowercase alphanumerics, "
                f"got {short_id!r}"
            )
        expected_branch = f"auto/{slug}"
        if self.branch != expected_branch:
            raise ValueError(f"branch must be {expected_branch!r}, got {self.branch!r}")
