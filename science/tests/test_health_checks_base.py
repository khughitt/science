from pathlib import Path

from science_model.audit import ProjectSubject

from science_tool.graph.health_checks.base import HealthContext, composed_result
from science_tool.graph.health_checks.tooling_scaffold import RULE
from science_tool.instruments import InstrumentResult


def test_health_context_records_timing(tmp_path: Path) -> None:
    context = HealthContext(project_root=tmp_path, collect_timings=True)
    assert context.run("probe", lambda: 3) == 3
    assert context.timings[0]["name"] == "probe"
    assert context.timings[0]["duration_seconds"] >= 0


def test_composed_result_preserves_unwired_status() -> None:
    source = InstrumentResult[object].unwired(code="missing", reason="no input")
    result = composed_result(source, [])
    assert result.instrument.status == "unwired"
    assert result.instrument.code == "missing"


def test_composed_result_replaces_observation_rows_with_findings() -> None:
    source = InstrumentResult.from_rows([{"old": "row"}])
    finding = RULE.build(
        subject=ProjectSubject(),
        severity="error",
        qualifiers={"code": "pyproject_missing"},
        message="missing",
    )
    result = composed_result(source, [finding])
    assert result.instrument.rows == [finding]
