from __future__ import annotations

import hashlib
import json

from science_tool.correspondence.extract import Polarity
from science_tool.correspondence.probe import Probe, ProbeResult, TaskState
from science_tool.correspondence.signature import evidence_signature


def _probe(target: str, result: ProbeResult, polarity: Polarity = Polarity.CREATE) -> Probe:
    return Probe(target, result, "", polarity)


def test_signature_is_versioned_full_sha256_of_canonical_json():
    probes = [_probe("b.py", ProbeResult.PRESENT), _probe("a.py", ProbeResult.ABSENT)]
    tasks = [("t2", TaskState.DONE), ("t1", TaskState.MISSING)]
    payload = {
        "v": 2,
        "claimed": "draft",
        "deliverables": [["a.py", "create", "absent"], ["b.py", "create", "present"]],
        "tasks": [["t1", "missing"], ["t2", "done"]],
        "adjudicated": "active",
    }
    expected_bytes = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    expected = "v2:" + hashlib.sha256(expected_bytes).hexdigest()
    assert evidence_signature(claimed="draft", probes=probes, task_states=tasks, adjudicated="active") == expected


def test_signature_is_order_independent_in_inputs():
    a = evidence_signature(
        claimed="draft",
        probes=[_probe("a.py", ProbeResult.PRESENT), _probe("b.py", ProbeResult.PRESENT)],
        task_states=[("t1", TaskState.DONE)],
        adjudicated="complete",
    )
    b = evidence_signature(
        claimed="draft",
        probes=[_probe("b.py", ProbeResult.PRESENT), _probe("a.py", ProbeResult.PRESENT)],
        task_states=[("t1", TaskState.DONE)],
        adjudicated="complete",
    )
    assert a == b


def test_signature_changes_when_any_covered_field_changes():
    # Every element of the payload must move the hash: claimed status, a probe target,
    # a probe result, a task ref, a task state, and the adjudicated status. One shared
    # baseline, mutate one axis at a time.
    def sig(**over):
        base = dict(
            claimed="draft",
            probes=[_probe("a.py", ProbeResult.PRESENT)],
            task_states=[("t1", TaskState.DONE)],
            adjudicated="complete",
        )
        base.update(over)
        return evidence_signature(**base)

    baseline = sig()
    assert sig(claimed="active") != baseline                                  # claimed status
    assert sig(probes=[_probe("b.py", ProbeResult.PRESENT)]) != baseline      # probe target
    assert sig(probes=[_probe("a.py", ProbeResult.ABSENT)]) != baseline       # probe result
    assert sig(task_states=[("t2", TaskState.DONE)]) != baseline              # task ref
    assert sig(task_states=[("t1", TaskState.MISSING)]) != baseline           # task state
    assert sig(adjudicated="active") != baseline                             # adjudicated status
    assert sig(probes=[_probe("a.py", ProbeResult.PRESENT, Polarity.REMOVE)]) != baseline  # polarity
