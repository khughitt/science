"""Deterministic, versioned evidence signature (design §5.5).

Persisted into committed `science.yaml` via `accepted_validation`, so the byte
encoding is pinned exactly and the format is versioned: any change to what the
evidence covers is a NEW version, never a silent reinterpretation of old entries.
"""

from __future__ import annotations

import hashlib
import json

from science_tool.correspondence.probe import Probe, TaskState

#: The current encoding version, as it appears in the emitted token. The acceptance
#: guard derives its matcher from this rather than repeating the literal, so bumping
#: the version cannot leave a second copy behind that silently honours stale entries.
SIGNATURE_VERSION = "v2"


def evidence_signature(
    *,
    claimed: str,
    probes: list[Probe],
    task_states: list[tuple[str, TaskState]],
    adjudicated: str,
) -> str:
    # v2 (fb-2026-07-26-014/015): `result` no longer means "the file exists", it
    # means "the plan's claim about this path holds", so polarity is part of what
    # the evidence covers. Extraction also narrowed to declared regions, which
    # changes the deliverable set for essentially every plan. Both are exactly the
    # "change to what the evidence covers" this module versions rather than
    # silently reinterpreting: a v1 `accepted_validation` entry no longer matches,
    # which surfaces the stale acceptance instead of honouring it.
    payload = {
        "v": int(SIGNATURE_VERSION.removeprefix("v")),
        "claimed": claimed,
        "deliverables": sorted([p.target, p.polarity.value, p.result.value] for p in probes),
        "tasks": sorted([ref, state.value] for ref, state in task_states),
        "adjudicated": adjudicated,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return f"{SIGNATURE_VERSION}:" + hashlib.sha256(canonical).hexdigest()
