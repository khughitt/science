"""The evidence broker's model vocabulary, shared by the baseline and the run record.

This is a MODEL module and not a tool module because `EvidenceExposure` (design §4.1) hangs on
`AutonomousRunRecord`, which lives here, and `science_model` cannot import `science_tool`. The
session-side types of §4.3 name the same classes, so one definition serves both sides of the
control plane.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

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
