"""Projection for `dag audit` display: cap validation findings and fix mutations
independently.

Lives beside the command, mirroring `explore_ideas_projection.py`. ``AuditReport.to_json()``
carries two independently growable lists at once -- ``validation.findings`` (nested one level
down) and ``mutations`` (top-level); the single-list helper
(``budget.projection.project_single_list_report``) only knows how to cap one top-level key, so
it would leave one of the two unbounded here.
"""

from __future__ import annotations

from typing import Any

DAG_AUDIT_LIST_CAP = 40


def project_dag_audit(payload: dict[str, Any], cap: int = DAG_AUDIT_LIST_CAP) -> dict[str, Any]:
    """Return a display copy with ``validation.findings`` and ``mutations`` each capped.

    ``<key>_omitted`` is recorded only when something was actually withheld -- absence of
    the marker means "nothing dropped", matching the shared single-list helper's contract.
    """
    if cap < 0:
        raise ValueError(f"dag audit cap must be non-negative, got {cap}")

    projected = dict(payload)

    validation = dict(payload["validation"])
    findings = validation["findings"]
    capped_findings = list(findings[:cap])
    validation["findings"] = capped_findings
    findings_omitted = len(findings) - len(capped_findings)
    if findings_omitted:
        validation["findings_omitted"] = findings_omitted
    projected["validation"] = validation

    mutations = payload["mutations"]
    capped_mutations = list(mutations[:cap])
    projected["mutations"] = capped_mutations
    mutations_omitted = len(mutations) - len(capped_mutations)
    if mutations_omitted:
        projected["mutations_omitted"] = mutations_omitted

    return projected
