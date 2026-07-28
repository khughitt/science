from pathlib import Path

import pytest

from science_tool.graph.health import build_health_report
from science_tool.graph.sources import load_project_sources


def _project_with_bad_dataset(root: Path) -> Path:
    (root / "science.yaml").write_text("name: test\n", encoding="utf-8")
    dataset = root / "entities" / "datasets" / "bad.md"
    dataset.parent.mkdir(parents=True)
    dataset.write_text(
        "---\nid: dataset:bad\nkind: dataset\ntitle: bad\norigin: derived\nsource_class: derived\n---\n",
        encoding="utf-8",
    )
    return root


def test_strict_load_still_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="schema validation failed"):
        load_project_sources(_project_with_bad_dataset(tmp_path), strict_core_schema=True)


def test_health_emits_schema_invalid_path_finding(tmp_path: Path) -> None:
    report = build_health_report(
        _project_with_bad_dataset(tmp_path),
        ingestion_ref="health:test",
        generated_at="2026-07-28T12:00:00+00:00",
        checks={"unresolved_refs"},
    )
    rows = [item for item in report.findings if item.producer_id == "schema_invalid"]
    assert len(rows) == 1
    assert rows[0].finding.rule_id == "entity.schema-invalid"
    assert rows[0].finding.subject.type == "path"
