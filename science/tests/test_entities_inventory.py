from __future__ import annotations

import json

from science_model.contracts.inventory_v1 import InventoryPayload
from science_tool.entities_inventory import build_inventory


def test_build_inventory_includes_entities_aliases_dag_candidates_and_watch_paths(tmp_path) -> None:
    project = tmp_path / "project"
    for rel_path in ("doc", "knowledge", "notes", "papers", "results", "specs", "tasks"):
        (project / rel_path).mkdir(parents=True)
    (project / "science.yaml").write_text(
        """
id: test-project
knowledge_profiles:
  local: knowledge/profiles/local.yaml
""".strip(),
        encoding="utf-8",
    )
    (project / "doc" / "finding.md").write_text(
        """
---
kind: finding
id: finding:f001
aliases: [f001]
title: Test finding
---
Body.
""".strip(),
        encoding="utf-8",
    )
    dag_path = project / "doc" / "figures" / "dags" / "h1.edges.yaml"
    dag_path.parent.mkdir(parents=True)
    dag_path.write_text(
        """
edges:
  - id: e001
    source: a
    target: b
    relation: supports
    interpretation: Edge interpretation.
""".strip(),
        encoding="utf-8",
    )

    inventory = build_inventory(project)

    InventoryPayload.model_validate(json.loads(inventory.model_dump_json()))
    assert inventory.schema_version == "1"
    assert inventory.project_id == "test-project"
    assert inventory.content_hash
    assert inventory.audit_hash
    assert [entity.id for entity in inventory.entities] == ["finding:f001"]
    assert inventory.aliases[0].alias == "f001"
    assert inventory.graph_addresses[0].address == "dag-edge:h1:e001"
    assert inventory.finding_candidates[0].targets == ["dag-edge:h1:e001"]
    assert inventory.watch_paths == ["doc", "knowledge", "notes", "papers", "results", "specs", "tasks"]
