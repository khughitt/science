from pathlib import Path

from science_model.audit import PathSubject, ReportedFinding

from science_tool.correspondence.signature import SIGNATURE_VERSION
from science_tool.validate.acceptance import partition_health_acceptances
from science_tool.validate.checks.correspondence_drift import (
    RULE_CORRESPONDENCE_DRIFT,
)


def test_correspondence_acceptance_moves_finding_to_accepted_channel(
    tmp_path: Path,
) -> None:
    signature = f"{SIGNATURE_VERSION}:{'a' * 64}"
    message = f"drift evidence-signature: {signature}"
    (tmp_path / "science.yaml").write_text(
        f"""
name: test
health:
  accepted_validation:
    - rule: plan.correspondence-drift
      severity: warning
      path: entities/plans/p.md
      message_contains: ["evidence-signature: {signature}"]
      reason: reviewed
""".lstrip(),
        encoding="utf-8",
    )
    finding = RULE_CORRESPONDENCE_DRIFT.build(
        subject=PathSubject(path="entities/plans/p.md"),
        severity="warn",
        qualifiers={"task": None, "evidence_signature": signature},
        message=message,
    )
    remaining, accepted = partition_health_acceptances(
        tmp_path,
        [ReportedFinding(producer_id="validate", finding=finding)],
    )
    assert remaining == []
    assert len(accepted) == 1
    assert accepted[0].finding == finding
