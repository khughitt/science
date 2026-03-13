from __future__ import annotations

import json
from pathlib import Path

import yaml

from science_tool.graph.migrate import audit_project_graph, migrate_project_ids, write_project_specific_sources


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
                'source_refs: []',
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
                'source_refs: []',
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


def test_audit_project_graph_loads_project_specific_entities_and_manual_aliases(tmp_path: Path) -> None:
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
    project_specific = root / "knowledge" / "sources" / "project_specific"
    project_specific.mkdir(parents=True)
    (project_specific / "entities.yaml").write_text(
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
    (project_specific / "mappings.yaml").write_text(
        yaml.safe_dump({"aliases": {"Q31": "question:q31-legacy-open-question"}}, sort_keys=True),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["unresolved_reference_count"] == 0
    assert report["has_failures"] is False


def test_write_project_specific_sources_preserves_existing_curation_and_deduplicates(tmp_path: Path) -> None:
    root = tmp_path / "project"
    project_specific = root / "knowledge" / "sources" / "project_specific"
    project_specific.mkdir(parents=True)
    (project_specific / "entities.yaml").write_text(
        yaml.safe_dump(
            {
                "entities": [
                    {
                        "canonical_id": "topic:evaluation",
                        "kind": "topic",
                        "title": "Evaluation",
                        "profile": "project_specific",
                        "source_path": "manual",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    (project_specific / "relations.yaml").write_text(
        yaml.safe_dump({"relations": [{"kind": "related_to"}]}, sort_keys=False),
        encoding="utf-8",
    )
    (project_specific / "mappings.yaml").write_text(
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

    write_project_specific_sources(root, report)

    entities = yaml.safe_load((project_specific / "entities.yaml").read_text(encoding="utf-8"))
    relations = yaml.safe_load((project_specific / "relations.yaml").read_text(encoding="utf-8"))
    mappings = yaml.safe_load((project_specific / "mappings.yaml").read_text(encoding="utf-8"))

    assert entities == {
        "entities": [
            {
                "canonical_id": "question:q31-legacy-open-question",
                "kind": "question",
                "title": "Q31 Legacy Open Question",
                "profile": "project_specific",
                "source_path": "migration:audit",
            },
            {
                "canonical_id": "topic:evaluation",
                "kind": "topic",
                "title": "Evaluation",
                "profile": "project_specific",
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
