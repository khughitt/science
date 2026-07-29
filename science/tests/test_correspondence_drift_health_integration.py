from pathlib import Path

from science_model.audit import PathSubject, ReportedFinding

from science_tool.correspondence.signature import SIGNATURE_VERSION
from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import validate_finding
from science_tool.validate.acceptance import partition_accepted_findings
from science_tool.validate.checks.correspondence_drift import (
    RULE_CORRESPONDENCE_DRIFT,
)


def test_correspondence_acceptance_moves_finding_to_accepted_channel(
    tmp_path: Path,
) -> None:
    signature = f"{SIGNATURE_VERSION}:{'a' * 64}"
    message = f"drift evidence-signature: {signature}"
    finding = RULE_CORRESPONDENCE_DRIFT.build(
        subject=PathSubject(path="entities/plans/p.md"),
        severity="warn",
        qualifiers={"task": None, "evidence_signature": signature},
        message=message,
    )
    registry = build_project_registry(tmp_path)
    finding_id = validate_finding(registry, "validate", finding)
    (tmp_path / "science.yaml").write_text(
        f"""
name: test
health:
  accepted_validation:
    - finding_id: {finding_id}
      fingerprint_version: 1
      severity_scope: [warn]
      reason: reviewed
""".lstrip(),
        encoding="utf-8",
    )
    remaining, accepted = partition_accepted_findings(
        tmp_path,
        [ReportedFinding(producer_id="validate", finding=finding)],
        registry=registry,
    )
    assert remaining == []
    assert len(accepted) == 1
    assert accepted[0].finding == finding
