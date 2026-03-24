from __future__ import annotations

import json
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.migrate import audit_project_graph, migrate_project_ids, write_local_sources


def test_audit_project_graph_reports_unresolved_related_refs(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "specs" / "hypotheses").mkdir(parents=True)
    (root / "specs" / "hypotheses" / "h01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "hypothesis:h01-demo"',
                'type: "hypothesis"',
                'title: "Demo hypothesis"',
                'status: "proposed"',
                'related: ["question:Q99"]',
                "source_refs: []",
                'created: "2026-03-12"',
                'updated: "2026-03-12"',
                "---",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["unresolved_reference_count"] == 1
    assert report["has_failures"] is True


def test_migrate_project_ids_rewrites_short_refs() -> None:
    mapping = {"H01": "hypothesis:h01-demo", "Q16": "question:16-demo"}

    updated = migrate_project_ids("related: [H01, question:Q16]\n", mapping)

    assert updated == "related: [hypothesis:h01-demo, question:16-demo]\n"


def test_migrate_project_ids_does_not_cross_entity_kinds() -> None:
    mapping = {"T001": "task:t001"}

    updated = migrate_project_ids("related: [question:T001]\n", mapping)

    assert updated == "related: [question:T001]\n"


def test_audit_project_graph_suggests_aliases_from_question_file_stems(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "doc" / "questions").mkdir(parents=True)
    (root / "doc" / "questions" / "q16-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "question:16-demo"',
                'type: "question"',
                'title: "Demo question"',
                'status: "open"',
                'related: ["question:Q16"]',
                "source_refs: []",
                'created: "2026-03-12"',
                'updated: "2026-03-12"',
                "---",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["unresolved_reference_count"] == 0
    assert report["alias_map"]["Q16"] == "question:16-demo"


def test_audit_project_graph_serializes_report(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    report = audit_project_graph(root)

    payload = json.dumps(report, sort_keys=True)

    assert "unresolved_reference_count" in payload


def test_audit_project_graph_loads_local_entities_and_manual_aliases(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Explore evaluation topic",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [topic:evaluation, Q31]",
                "- created: 2026-03-12",
                "",
                "Do it.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    local_sources = root / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "topic:evaluation",
                        "kind": "topic",
                        "title": "Evaluation",
                    },
                    {
                        "canonical_id": "question:q31-legacy-open-question",
                        "kind": "question",
                        "title": "Legacy open question",
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (local_sources / "mappings.yaml").write_text(
        yaml.safe_dump({"aliases": {"Q31": "question:q31-legacy-open-question"}}, sort_keys=True),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["unresolved_reference_count"] == 0
    assert report["has_failures"] is False


def test_audit_project_graph_uses_configured_local_profile_directory(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  curated: []",
                "  local: lab_local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Explore evaluation topic",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [topic:evaluation]",
                "- created: 2026-03-12",
                "",
                "Do it.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    local_sources = root / "knowledge" / "sources" / "lab_local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "topic:evaluation",
                        "kind": "topic",
                        "title": "Evaluation",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["local_profile"] == "lab_local"
    assert report["unresolved_reference_count"] == 0
    assert report["has_failures"] is False


def test_audit_project_graph_reports_unresolved_structured_relation_refs(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    local_sources = root / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "paper:legatiuk2021",
                        "kind": "paper",
                        "title": "Legatiuk 2021",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (local_sources / "relations.yaml").write_text(
        yaml.safe_dump(
            {
                "relations": [
                    {
                        "subject": "paper:legatiuk2021",
                        "predicate": "cito:discusses",
                        "object": "question:q99-missing",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["unresolved_reference_count"] == 1
    assert report["has_failures"] is True
    assert any(row["field"] == "object" and row["target"] == "question:q99-missing" for row in report["rows"])


def test_audit_project_graph_reports_unresolved_binding_refs(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    local_sources = root / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "models.yaml").write_text(
        yaml.safe_dump(
            {
                "models": [
                    {
                        "canonical_id": "model:navier-stokes",
                        "title": "Navier-Stokes equations",
                        "profile": "local",
                        "source_path": "knowledge/sources/local/models.yaml",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (local_sources / "bindings.yaml").write_text(
        yaml.safe_dump(
            {
                "bindings": [
                    {
                        "model": "model:navier-stokes",
                        "parameter": "parameter:kinematic-viscosity",
                        "source_path": "knowledge/sources/local/bindings.yaml",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["unresolved_reference_count"] == 1
    assert report["has_failures"] is True
    assert any(
        row["field"] == "parameter" and row["target"] == "parameter:kinematic-viscosity" for row in report["rows"]
    )


def test_write_local_sources_preserves_existing_curation_and_deduplicates(tmp_path: Path) -> None:
    root = tmp_path / "project"
    local_sources = root / "knowledge" / "sources" / "local"
    local_sources.mkdir(parents=True)
    (local_sources / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "topic:evaluation",
                        "kind": "topic",
                        "title": "Evaluation",
                        "profile": "local",
                        "source_path": "manual",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (local_sources / "relations.yaml").write_text(
        yaml.safe_dump({"relations": [{"kind": "related_to"}]}, sort_keys=False),
        encoding="utf-8",
    )
    (local_sources / "mappings.yaml").write_text(
        yaml.safe_dump({"aliases": {"legacy:q31": "question:q31-legacy-open-question"}}, sort_keys=True),
        encoding="utf-8",
    )
    report = {
        "alias_map": {
            "Q31": "question:q31-legacy-open-question",
            "Q32": "question:q32-other-question",
        },
        "manual_aliases": {"Q31": "question:q31-legacy-open-question"},
        "rows": [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": "task:t001",
                "field": "related",
                "target": "topic:evaluation",
                "details": "tasks/active.md references an unknown canonical entity",
            },
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": "task:t001",
                "field": "related",
                "target": "question:q31-legacy-open-question",
                "details": "tasks/active.md references an unknown canonical entity",
            },
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": "task:t001",
                "field": "related",
                "target": "question:q31-legacy-open-question",
                "details": "tasks/active.md references an unknown canonical entity",
            },
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": "task:t001",
                "field": "related",
                "target": "Q31",
                "details": "tasks/active.md references an unknown canonical entity",
            },
        ],
    }

    write_local_sources(root, report)

    entities = yaml.safe_load((local_sources / "entities.yaml").read_text(encoding="utf-8"))
    relations = yaml.safe_load((local_sources / "relations.yaml").read_text(encoding="utf-8"))
    mappings = yaml.safe_load((local_sources / "mappings.yaml").read_text(encoding="utf-8"))

    assert entities == {
        "entities": [
            {
                "canonical_id": "question:q31-legacy-open-question",
                "kind": "question",
                "title": "Q31 Legacy Open Question",
                "profile": "local",
                "source_path": "migration:audit",
            },
            {
                "canonical_id": "topic:evaluation",
                "kind": "topic",
                "title": "Evaluation",
                "profile": "local",
                "source_path": "manual",
            },
        ]
    }
    assert relations == {"relations": [{"kind": "related_to"}]}
    assert mappings == {
        "aliases": {
            "Q31": "question:q31-legacy-open-question",
            "legacy:q31": "question:q31-legacy-open-question",
        }
    }


def test_write_local_sources_uses_configured_local_profile_directory(tmp_path: Path) -> None:
    root = tmp_path / "project"
    report = {
        "local_profile": "lab_local",
        "manual_aliases": {},
        "rows": [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": "task:t001",
                "field": "related",
                "target": "topic:evaluation",
                "details": "tasks/active.md references an unknown canonical entity",
            }
        ],
    }

    write_local_sources(root, report)

    local_sources = root / "knowledge" / "sources" / "lab_local"
    entities = yaml.safe_load((local_sources / "entities.yaml").read_text(encoding="utf-8"))

    assert entities == {
        "entities": [
            {
                "canonical_id": "topic:evaluation",
                "kind": "topic",
                "title": "Evaluation",
                "profile": "lab_local",
                "source_path": "migration:audit",
            }
        ]
    }
    assert not (root / "knowledge" / "sources" / "local").exists()


def test_graph_migrate_command_rewrites_alias_refs_and_writes_report(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  curated: []",
                "  local: local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "specs" / "hypotheses").mkdir(parents=True)
    (root / "specs" / "hypotheses" / "h01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "hypothesis:h01-demo"',
                'type: "hypothesis"',
                'title: "Demo hypothesis"',
                'status: "proposed"',
                "source_refs: []",
                "related: []",
                'created: "2026-03-12"',
                'updated: "2026-03-12"',
                "---",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Explore evaluation topic",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [H01, topic:evaluation]",
                "- created: 2026-03-12",
                "",
                "Do it.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "migrate", "--project-root", str(root), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["report_path"].endswith("knowledge/reports/kg-migration-audit.json")
    assert payload["rewritten_file_count"] == 1
    assert payload["has_failures"] is False
    assert payload["unresolved_reference_count"] == 0

    task_text = (root / "tasks" / "active.md").read_text(encoding="utf-8")
    assert "hypothesis:h01-demo" in task_text
    assert "[H01" not in task_text

    report_path = root / "knowledge" / "reports" / "kg-migration-audit.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["has_failures"] is False

    entities_path = root / "knowledge" / "sources" / "local" / "entities.yaml"
    entities = yaml.safe_load(entities_path.read_text(encoding="utf-8"))
    assert entities == {
        "entities": [
            {
                "canonical_id": "topic:evaluation",
                "kind": "topic",
                "title": "Evaluation",
                "profile": "local",
                "source_path": "migration:audit",
            }
        ]
    }


def test_graph_migrate_command_uses_configured_local_profile_paths(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  curated: []",
                "  local: lab_local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "specs" / "hypotheses").mkdir(parents=True)
    (root / "specs" / "hypotheses" / "h01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "hypothesis:h01-demo"',
                'type: "hypothesis"',
                'title: "Demo hypothesis"',
                'status: "proposed"',
                "source_refs: []",
                "related: []",
                'created: "2026-03-12"',
                'updated: "2026-03-12"',
                "---",
                "",
                "Body.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Explore evaluation topic",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [H01, topic:evaluation]",
                "- created: 2026-03-12",
                "",
                "Do it.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "migrate", "--project-root", str(root), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["local_profile"] == "lab_local"

    entities_path = root / "knowledge" / "sources" / "lab_local" / "entities.yaml"
    report_path = root / "knowledge" / "reports" / "kg-migration-audit.json"

    assert entities_path.exists()
    assert report_path.exists()
    assert not (root / "knowledge" / "sources" / "local").exists()
