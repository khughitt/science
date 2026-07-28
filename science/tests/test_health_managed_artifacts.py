from pathlib import Path

from science_tool.findings.catalog import build_project_registry
from science_tool.findings.producers import validate_producer_result
from science_tool.graph.health_checks.base import HealthContext
from science_tool.graph.health_checks.managed_artifacts import CHECK


def test_managed_artifacts_keep_complete_inventory_in_metrics(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text("name: test\n", encoding="utf-8")
    result = CHECK.run(HealthContext(project_root=tmp_path))
    validated = validate_producer_result(
        build_project_registry(tmp_path),
        CHECK.producer.producer_id,
        result,
    )
    inventory = validated.metrics.model_dump(mode="json")["inventory"]
    assert inventory
    assert all("counts_as_issue" in row for row in inventory)
    assert all(
        item.rule_id.startswith("managed-artifact.")
        for item in validated.instrument.rows
    )
    assert len(validated.instrument.rows) == sum(
        row["counts_as_issue"] is True for row in inventory
    )
