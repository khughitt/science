from pathlib import Path

from science_model.audit import PathSubject, ReportedFinding

from science_tool.validate.acceptance import partition_health_acceptances
from science_tool.validate.checks.manifest import RULES


def _finding(message: str):
    return RULES["manifest.check"].build(
        subject=PathSubject(path="science.yaml"),
        severity="warn",
        qualifiers={"key": ["profile"]},
        message=message,
    )


def test_health_acceptance_partitions_current_shape_without_overlap(
    tmp_path: Path,
) -> None:
    (tmp_path / "science.yaml").write_text(
        """
name: test
health:
  accepted_validation:
    - rule: manifest.check
      severity: warning
      path: science.yaml
      message_contains: [missing profile]
      reason: reviewed
""".lstrip(),
        encoding="utf-8",
    )
    matched = ReportedFinding(
        producer_id="validate",
        finding=_finding("missing profile"),
    )
    other = ReportedFinding(
        producer_id="validate",
        finding=_finding("different warning"),
    )
    remaining, accepted = partition_health_acceptances(
        tmp_path,
        [matched, other],
    )
    accepted_ids = {item.acceptance_key for item in accepted}
    assert [item.finding.message for item in remaining] == ["different warning"]
    assert len(accepted_ids) == 1
    assert not ({item.finding.message for item in accepted} & {item.finding.message for item in remaining})


def test_non_validation_findings_are_never_accepted(tmp_path: Path) -> None:
    item = ReportedFinding(producer_id="other", finding=_finding("missing profile"))
    remaining, accepted = partition_health_acceptances(tmp_path, [item])
    assert remaining == [item]
    assert accepted == []
