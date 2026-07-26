from __future__ import annotations

from pathlib import Path

from science_tool.correspondence.signature import SIGNATURE_VERSION
from science_tool.graph.health import _partition_accepted_validation_findings

_SIG = f"{SIGNATURE_VERSION}:" + "a" * 64


def _finding(rule: str, path: str, message: str) -> dict:
    return {"severity": "warn", "path": path, "line": None, "message": message, "rule": rule, "task": None}


def _manifest(root: Path, health: str) -> None:
    (root / "science.yaml").write_text(f"name: f\nprofile: research\n{health}", encoding="utf-8")


def test_path_only_entry_does_not_suppress_scoped_rule_in_health(tmp_path: Path):
    _manifest(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "x"\n',
    )
    finding = _finding("plan.correspondence-drift", "entities/plans/0001-x.md", f"... evidence-signature: {_SIG}")
    remaining, accepted = _partition_accepted_validation_findings(tmp_path, [finding])
    assert remaining == [finding] and accepted == []


def test_valid_signature_entry_suppresses_in_health(tmp_path: Path):
    _manifest(
        tmp_path,
        'health:\n  accepted_validation:\n    - rule: "plan.correspondence-drift"\n'
        '      path: "entities/plans/0001-x.md"\n      reason: "input not deliverable"\n'
        f'      message_contains: "evidence-signature: {_SIG}"\n',
    )
    finding = _finding("plan.correspondence-drift", "entities/plans/0001-x.md", f"... evidence-signature: {_SIG}")
    remaining, accepted = _partition_accepted_validation_findings(tmp_path, [finding])
    assert remaining == [] and len(accepted) == 1
    assert accepted[0]["accepted_reason"] == "input not deliverable"
