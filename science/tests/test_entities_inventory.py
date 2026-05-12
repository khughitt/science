from __future__ import annotations

import json

import pytest
from science_model.contracts.inventory_v1 import InventoryPayload
from science_tool import entities_inventory
from science_tool.entities_inventory import build_inventory
from science_tool.graph.sources import load_project_sources


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


def test_build_inventory_metadata_uses_config_path_and_project_name_default(tmp_path) -> None:
    project = tmp_path / "project-slug"
    project.mkdir()
    (project / "science.yaml").write_text(
        """
id: configured-project
path: registry/projects/configured-project
""".strip(),
        encoding="utf-8",
    )

    inventory = build_inventory(project)

    assert inventory.project_id == "configured-project"
    assert inventory.project is not None
    assert inventory.project.name == "project-slug"
    assert inventory.project.path == "registry/projects/configured-project"


def test_build_inventory_metadata_without_science_yaml_uses_project_root_name(tmp_path) -> None:
    project = tmp_path / "project-slug"
    project.mkdir()

    inventory = build_inventory(project)

    assert inventory.project_id == "project-slug"
    assert inventory.project is not None
    assert inventory.project.id == "project-slug"
    assert inventory.project.name == "project-slug"
    assert inventory.project.path == project.resolve().as_posix()


def test_build_inventory_fails_when_entity_source_adapter_mapping_is_missing(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: adapter-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\nid: finding:f001\ntitle: Finding\n---\n",
        encoding="utf-8",
    )
    sources = load_project_sources(project)

    def fake_load_project_sources(_project_root):
        return sources.model_copy(update={"entity_source_adapters": {}})

    monkeypatch.setattr(entities_inventory, "load_project_sources", fake_load_project_sources)

    with pytest.raises(ValueError, match="finding:f001.*source adapter"):
        build_inventory(project)
