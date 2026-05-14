from __future__ import annotations

import json
from types import SimpleNamespace

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

    inventory = build_inventory(project, schema_version="1")

    InventoryPayload.model_validate(json.loads(inventory.model_dump_json()))
    assert inventory.schema_version == "1"
    assert inventory.project_id == "test-project"
    assert inventory.project is not None
    assert inventory.project.last_activity is not None
    assert inventory.project.staleness_days is not None
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

    inventory = build_inventory(project, schema_version="1")

    assert inventory.project_id == "configured-project"
    assert inventory.project is not None
    assert inventory.project.name == "project-slug"
    assert inventory.project.path == "registry/projects/configured-project"
    assert inventory.project.created is None
    assert inventory.project.last_modified is None


def test_build_inventory_metadata_preserves_project_dates(tmp_path) -> None:
    project = tmp_path / "project-slug"
    project.mkdir()
    (project / "science.yaml").write_text(
        """
id: configured-project
created: 2026-03-01
last_modified: 2026-03-02
""".strip(),
        encoding="utf-8",
    )

    inventory = build_inventory(project, schema_version="1")

    assert inventory.project is not None
    assert inventory.project.created == "2026-03-01"
    assert inventory.project.last_modified == "2026-03-02"


def test_build_inventory_metadata_without_science_yaml_uses_project_root_name(tmp_path) -> None:
    project = tmp_path / "project-slug"
    project.mkdir()

    inventory = build_inventory(project, schema_version="1")

    assert inventory.project_id == "project-slug"
    assert inventory.project is not None
    assert inventory.project.id == "project-slug"
    assert inventory.project.name == "project-slug"
    assert inventory.project.path == project.resolve().as_posix()


def test_build_inventory_preserves_task_dsl_type_in_data(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "tasks").mkdir(parents=True)
    (project / "science.yaml").write_text("id: task-project\n", encoding="utf-8")
    (project / "tasks" / "active.md").write_text(
        "## [t001] T01\n"
        "- type: research\n"
        "- priority: P1\n"
        "- status: done\n"
        "- created: 2026-04-20\n"
        "- completed: 2026-04-21\n\n"
        "Body prose.\n",
        encoding="utf-8",
    )

    inventory = build_inventory(project, schema_version="1")

    task = next(entity for entity in inventory.entities if entity.id == "task:t001")
    assert task.data["task_type"] == "research"
    assert task.data["priority"] == "P1"
    assert task.data["completed"] == "2026-04-21"
    assert task.data["content_preview"] == "Body prose."


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
        build_inventory(project, schema_version="1")


def test_build_inventory_promotes_targets_without_duplicating_them_in_data(tmp_path, monkeypatch) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("id: target-project\n", encoding="utf-8")

    class EntityWithTargets:
        id = "finding:f001"
        canonical_id = "finding:f001"
        kind = "finding"
        title = "Finding"
        status = None
        profile = "core"
        file_path = "doc/finding.md"
        aliases: list[str] = []
        related: list[str] = []
        source_refs: list[str] = []
        review_state = None
        deprecated_ids: list[str] = []
        scope = "project"

        def model_dump(self, *, mode, exclude_none, exclude):
            data = {
                "id": self.id,
                "canonical_id": self.canonical_id,
                "kind": self.kind,
                "title": self.title,
                "project": "project",
                "ontology_terms": [],
                "related": [],
                "relations": [],
                "source_refs": [],
                "aliases": [],
                "deprecated_ids": [],
                "review_state": None,
                "file_path": self.file_path,
                "scope": self.scope,
                "targets": ["dag-edge:h1:e001"],
                "content_preview": "Finding preview.",
            }
            if exclude_none:
                data = {key: value for key, value in data.items() if value is not None}
            return {key: value for key, value in data.items() if key not in exclude}

    sources = SimpleNamespace(
        entities=[EntityWithTargets()],
        entity_source_adapters={"finding:f001": "fake-adapter"},
        markdown_documents=[],
        manual_aliases={},
        ontology_catalogs=[],
    )
    monkeypatch.setattr(entities_inventory, "load_project_sources", lambda _project_root: sources)

    inventory = build_inventory(project, schema_version="1")

    assert inventory.entities[0].targets == ["dag-edge:h1:e001"]
    assert inventory.entities[0].data == {"content_preview": "Finding preview."}


def test_build_inventory_v2_returns_v2_payload_with_empty_overlays(tmp_path) -> None:
    from science_model.contracts.inventory_v2 import (
        InventoryPayload as InventoryPayloadV2,
    )

    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: v2-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\nid: finding:f001\ntitle: Finding\n---\n",
        encoding="utf-8",
    )

    inventory = build_inventory(project, schema_version="2")

    assert isinstance(inventory, InventoryPayloadV2)
    assert inventory.schema_version == "2"
    assert inventory.project_id == "v2-project"
    assert inventory.overlays == []
    assert [e.id for e in inventory.entities] == ["finding:f001"]
    assert inventory.content_hash
    assert inventory.audit_hash


def test_build_inventory_v2_scans_project_overlays(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc" / "papers").mkdir(parents=True)
    (project / "science.yaml").write_text("id: overlay-project\n", encoding="utf-8")
    (project / "doc" / "papers" / "Adams2025.md").write_text(
        "---\n"
        'id: "paper:Adams2025"\n'
        'overlay_of: "paper:Adams2025"\n'
        'relevance: "H2 — supports the homology-split argument"\n'
        'hypothesis_links: ["H2", "H4"]\n'
        'project_tags: ["high-priority"]\n'
        'tags: ["overlay-added"]\n'
        "---\n\n## Project-Specific Notes\n\nText.\n",
        encoding="utf-8",
    )

    inventory = build_inventory(project, schema_version="2")

    assert len(inventory.overlays) == 1
    overlay = inventory.overlays[0]
    assert overlay.overlay_of == "paper:Adams2025"
    assert overlay.project_id == "overlay-project"
    assert overlay.source.adapter == "commons-overlay"
    assert overlay.append_fields == {"tags": ["overlay-added"]}
    assert overlay.project_only_fields == {
        "relevance": "H2 — supports the homology-split argument",
        "hypothesis_links": ["H2", "H4"],
        "project_tags": ["high-priority"],
    }
    assert overlay.body_sections == ["\n## Project-Specific Notes\n\nText.\n"]


def test_build_inventory_v2_overlay_validation_error_becomes_warning(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc" / "papers").mkdir(parents=True)
    (project / "science.yaml").write_text("id: broken-overlay\n", encoding="utf-8")
    (project / "doc" / "papers" / "Adams2025.md").write_text(
        "---\n"
        'id: "paper:Wrong2025"\n'
        'overlay_of: "paper:Wrong2025"\n'
        'relevance: "mismatch"\n'
        "---\n\n## Notes\n",
        encoding="utf-8",
    )

    inventory = build_inventory(project, schema_version="2")

    assert inventory.overlays == []
    overlay_warnings = [w for w in inventory.warnings if w.code == "overlay-invalid"]
    assert len(overlay_warnings) == 1
    assert overlay_warnings[0].path.endswith("doc/papers/Adams2025.md")


def test_build_inventory_defaults_to_v2(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: default-project\n", encoding="utf-8")

    inventory = build_inventory(project)

    assert inventory.schema_version == "2"


def test_build_inventory_rejects_unknown_schema_version_before_loading(
    tmp_path, monkeypatch
) -> None:
    project = tmp_path / "project"
    project.mkdir()

    def _fail(_project_root):
        raise AssertionError(
            "load_project_sources must not run for a bad schema_version"
        )

    monkeypatch.setattr(entities_inventory, "load_project_sources", _fail)

    with pytest.raises(ValueError, match="schema_version"):
        build_inventory(project, schema_version="3")
