"""Deterministic, versioned evidence signature (design §5.5).

Persisted into committed `science.yaml` via `accepted_validation`, so the byte
encoding is pinned exactly and the format is versioned: any change to what the
evidence covers is a NEW version, never a silent reinterpretation of old entries.
"""

from __future__ import annotations

import hashlib
import json

from science_tool.correspondence.probe import Probe, TaskState


def evidence_signature(
    *,
    claimed: str,
    probes: list[Probe],
    task_states: list[tuple[str, TaskState]],
    adjudicated: str,
) -> str:
    payload = {
        "v": 1,
        "claimed": claimed,
        "deliverables": sorted([p.target, p.result.value] for p in probes),
        "tasks": sorted([ref, state.value] for ref, state in task_states),
        "adjudicated": adjudicated,
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return "v1:" + hashlib.sha256(canonical).hexdigest()
