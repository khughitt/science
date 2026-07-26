from __future__ import annotations

import re
from pathlib import Path

from science_tool.graph.health import build_health_report

_DRIFT = "plan.correspondence-drift"
_SCOPE = "accepted-validation.evidence-scope-required"


def _project(root: Path, accepted: str) -> None:
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "science.yaml").write_text(f"name: fixture\nprofile: research\n{accepted}", encoding="utf-8")
    plan = root / "entities" / "plans" / "0001-x.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        '---\nid: "plan:0001-x"\nkind: plan\ntitle: "T"\nstatus: "draft"\n---\n\n## Deliverables\n\nBuilds `src/a.py`.\n',
        encoding="utf-8",
    )


def _rules(findings: list[dict]) -> list[str]:
    return [f.get("rule") for f in findings]


def test_path_only_entry_keeps_drift_and_raises_scope_guard(tmp_path: Path):
    _project(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "path only"\n',
    )
    report = build_health_report(tmp_path, checks={"validate"})
    validation_rules = _rules(report["validation"])
    # Path-only entry does NOT suppress the drift finding, and the malformed guard fires.
    assert _DRIFT in validation_rules
    assert _SCOPE in validation_rules
    assert _DRIFT not in _rules(report["accepted_validation"])


def test_valid_signature_entry_suppresses_drift_in_health(tmp_path: Path):
    # Phase 1: emit once with no acceptance to capture the live evidence signature.
    _project(tmp_path, "")
    first = build_health_report(tmp_path, checks={"validate"})
    drift = next(f for f in first["validation"] if f.get("rule") == _DRIFT)
    token = re.search(r"evidence-signature: (v2:[0-9a-f]{64})", drift["message"]).group(1)

    # Phase 2: accept it with the complete labeled signature + project-relative path.
    _project(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "input file, not a deliverable"\n'
        f'      message_contains: "evidence-signature: {token}"\n',
    )
    report = build_health_report(tmp_path, checks={"validate"})
    assert _DRIFT not in _rules(report["validation"])
    accepted = [f for f in report["accepted_validation"] if f.get("rule") == _DRIFT]
    assert len(accepted) == 1
    assert accepted[0]["accepted_reason"] == "input file, not a deliverable"
    # A well-scoped entry satisfies the guard, so it does NOT also warn.
    assert _SCOPE not in _rules(report["validation"])
