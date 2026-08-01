"""The evidence broker's model vocabulary, shared by the baseline and the run record.

This is a MODEL module and not a tool module because `EvidenceExposure` (design §4.1) hangs on
`AutonomousRunRecord`, which lives here, and `science_model` cannot import `science_tool`. The
session-side types of §4.3 name the same classes, so one definition serves both sides of the
control plane.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from science_model.audit.subjects import SubjectError, normalize_project_path, normalize_utf8_nfc


class SurfacePolicy(BaseModel):
    """What the broker will not show, and what it says instead.

    DENY PREFIXES ARE A PARAMETER, NOT A CONSTANT. 2a guarantees only that a supplied policy is
    HONOURED. Proving a policy COMPLETE -- that it covers every artifact a study must withhold --
    stays the caller's obligation, and a default here would look like the toolkit had discharged
    it.

    `notice` is what the requester sees and is policy-supplied, because this toolkit's existing
    denials are deliberately informative -- a human triages them -- while a blinding study needs
    them uniform and information-free, since a specific reason confirms the denied thing exists.
    2a cannot decide which is correct for a caller, so it does not.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    deny_prefixes: tuple[str, ...] = ()
    notice: str

    @field_validator("deny_prefixes")
    @classmethod
    def _normalized(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Normalized HERE, so `authorize` compares two paths in one spelling.

        A prefix normalized at match time would be normalized once per request and could differ
        between serving and replay if the normalizer ever changed. Doing it on construction means
        the policy that reaches the baseline is already the policy that will be compared.

        A PREFIX WHOSE NFC FORM DIFFERS FROM WHAT WAS WRITTEN IS REFUSED, NOT QUIETLY WEAKENED.
        `normalize_project_path` folds to NFC; git matches pathspecs BYTE-exactly. MEASURED, git
        2.55: against a tree holding an NFD `café/x.txt`, a deny prefix written in NFD is stored
        as NFC, `:(top,literal,exclude)café` in NFC then matches nothing, and `search` serves the
        file AND its content -- while `read` of the same path normalizes the request too and
        misses. The two mechanisms disagree, and the caller who asked for the denial is the last
        to know. There is no spelling of this policy that expresses the NFD path, so the caller
        learns that here rather than receiving a weaker policy than the one they wrote.
        """
        try:
            prefixes = tuple(normalize_project_path(raw) for raw in value)
        except SubjectError as exc:
            raise ValueError(f"deny prefix is not a project path: {exc}") from exc
        for raw in value:
            if normalize_utf8_nfc(raw) != raw:
                raise ValueError(
                    f"deny prefix {raw!r} is not in NFC and cannot be expressed: git matches "
                    "pathspecs byte-exactly, so the NFC spelling stored here would exclude "
                    "nothing from `search` while `read` denied the same path"
                )
        return prefixes


#: Bumped only when serving or parsing changes: defined misses, canonical argv, or hit parsing.
#: It is not the toolkit revision; a signal that fires on every release is ignored.
#:
#: 2 (plan 4a): serving is now bounded per request, and the child environment pins
#: `GIT_SHALLOW_FILE` and `GIT_NO_LAZY_FETCH`. Both change what an identical request returns
#: -- an oversized payload refuses where it used to be served, and a partial clone fails where
#: it used to be silently completed from its promisor remote -- so a v1 exposure replayed under
#: v2 rules is not comparable, which is what this number exists to say.
REPLAY_PROTOCOL_VERSION = 2

#: Character bounds make the journal's byte ceiling derivable before it is read. Pydantic counts
#: characters, not bytes; journal encoding accounts separately for the worst-case byte expansion.
MAX_TARGET_CHARS = 4096
MAX_BUDGET = 100
MAX_INLINE_INPUTS = 100
MAX_INLINE_LINES = (1 << 63) - 1

#: DERIVED FROM WHAT A REVIEWER COULD HAVE CONSUMED, not chosen for roundness. A payload no agent
#: can read is not evidence of exposure, and at roughly four bytes per token a mebibyte already
#: exceeds the context of the reviewers this program contemplates. Serving more would inflate
#: §5.1 coverage over material nobody saw.
MAX_SERVED_BYTES = 1 << 20

#: The disk one run can occupy: `run_git` holds a payload whole in memory, the session writes it
#: to `served/`, and replay reads it again, so the per-request bound is spent at least twice per
#: request and `MAX_BUDGET` times per run.
MAX_RUN_SERVED_BYTES = MAX_BUDGET * MAX_SERVED_BYTES

COMMIT_PATTERN = r"^[0-9a-f]{40}$"
ENTRY_COMMIT_PATTERN = r"^(?:[0-9a-f]{40})?$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class Outcome(StrEnum):
    """What one request produced.

    This lives in the model package because sealed entries use it and ``science_model`` cannot
    import ``science_tool``.
    """

    SERVED = "served"
    MISS_ABSENT = "miss-absent"
    MISS_NO_MATCH = "miss-no-match"
    MISS_NO_COMMITS = "miss-no-commits"
    REFUSED = "refused"


class InstrumentIdentity(BaseModel):
    """What defined the judgement procedure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ref: str
    sha256: str
    prompt_hash: str


class InlineInput(BaseModel):
    """One input the opening prompt already supplied.

    ``lines`` is carried because inline bytes are not in the tree and cannot be re-derived later.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target: str = Field(max_length=MAX_TARGET_CHARS)
    sha256: str = Field(pattern=SHA256_PATTERN)
    lines: int = Field(ge=0, le=MAX_INLINE_LINES)


class ExposureEntry(BaseModel):
    """One journal event, sealed.

    Matched line numbers stay unstored and are re-derived during replay. Outcome is stored because
    replay checks it; without it, a refusal's empty payload is indistinguishable from a served empty
    file and can be misclassified as full coverage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    op: Literal["read", "search", "history", "inline"]
    target: str = Field(max_length=MAX_TARGET_CHARS)
    pathspec: str | None = Field(default=None, max_length=MAX_TARGET_CHARS)
    commit: str = Field(pattern=ENTRY_COMMIT_PATTERN)
    sha256: str = Field(pattern=SHA256_PATTERN)
    outcome: Outcome


class EvidenceExposure(BaseModel):
    """The sealed record of what an agent was shown.

    It contains every input replay needs so a repository and the record are sufficient to recheck a
    run after its control-plane directory has gone.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    commit: str = Field(pattern=COMMIT_PATTERN)
    budget: int = Field(ge=0, le=MAX_BUDGET)
    requests_used: int = Field(ge=0)
    instrument: InstrumentIdentity
    surface_policy: SurfacePolicy
    inline: tuple[InlineInput, ...] = Field(default=(), max_length=MAX_INLINE_INPUTS)
    replay_protocol: int
    entries: tuple[ExposureEntry, ...] = ()

    @model_validator(mode="after")
    def _spend_is_derived_then_bounded(self) -> EvidenceExposure:
        """Recompute the spend before applying its bound."""
        counted = len([entry for entry in self.entries if entry.op != "inline"])
        if self.requests_used != counted:
            raise ValueError(
                f"requests_used is {self.requests_used} but {counted} non-inline entries are "
                "recorded; the spend is derived from the log, not asserted beside it"
            )
        if self.requests_used > self.budget:
            raise ValueError(f"requests_used {self.requests_used} exceeds budget {self.budget}")
        return self

    @model_validator(mode="after")
    def _one_evidence_surface(self) -> EvidenceExposure:
        """A run that read two trees did not have one evidence surface."""
        for entry in self.entries:
            if entry.commit != self.commit:
                raise ValueError(
                    f"entry {entry.target!r} is at commit {entry.commit} but the exposure is at "
                    f"{self.commit}"
                )
        return self

    @model_validator(mode="after")
    def _inline_entries_were_served(self) -> EvidenceExposure:
        """Inline entries are supervisor seeding and therefore served by construction."""
        for entry in self.entries:
            if entry.op == "inline" and entry.outcome is not Outcome.SERVED:
                raise ValueError(
                    f"inline entry {entry.target!r} carries outcome {entry.outcome}; the "
                    "supervisor's own seeding is served by construction"
                )
        return self


class EvidenceSession(BaseModel):
    """The live session declared in a run baseline.

    None of these values is actor-settable on the command line.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    session_id: str
    journal_path: Path
    commit: str = Field(pattern=COMMIT_PATTERN)
    budget: int = Field(ge=0, le=MAX_BUDGET)
    surface_policy: SurfacePolicy
    instrument: InstrumentIdentity
    inline: tuple[InlineInput, ...] = Field(default=(), max_length=MAX_INLINE_INPUTS)


class EvidenceSessionSpec(BaseModel):
    """The supervisor's declaration, read from JSON at run start.

    Inline paths are paths rather than claimed hashes: run start reads and measures the bytes.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    budget: int = Field(ge=0, le=MAX_BUDGET)
    surface_policy: SurfacePolicy
    instrument: InstrumentIdentity
    inline_paths: tuple[Path, ...] = Field(default=(), max_length=MAX_INLINE_INPUTS)
