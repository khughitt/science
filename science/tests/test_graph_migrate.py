from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml
from click.testing import CliRunner

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.cli import main
from science_tool.graph.migrate import (
    audit_project_graph,
    audit_project_sources,
    migrate_project_ids,
    write_local_sources,
)
from science_tool.graph.sources import load_project_sources


def test_audit_project_graph_reports_unresolved_related_refs(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "entities" / "hypotheses" / "h01-demo.md").write_text(
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


def test_audit_project_graph_allows_tag_refs_in_related(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Draft analysis",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [tag:draft]",
                "- created: 2026-04-21",
                "",
                "Track a draft task.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["has_failures"] is False
    assert report["rows"] == []


def _write_paper_dataset_project(root: Path, *, conflict: bool = False) -> Path:
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    (root / "entities" / "papers").mkdir(parents=True)
    paper = root / "entities" / "papers" / "smith.md"
    if conflict:
        paper.write_text(
            "\n".join(
                [
                    "---",
                    "id: paper:smith",
                    "type: paper",
                    "title: Smith",
                    "dataset_usage:",
                    "  - ref: dataset:gtex-v8",
                    "    role: cited",
                    "datasets:",
                    "  - dataset:gtex-v8",
                    "---",
                    "",
                    "Body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        paper.write_text(
            "\n".join(
                [
                    "---",
                    "id: paper:smith",
                    "type: paper",
                    "title: Smith",
                    "datasets:",
                    "  - dataset:gtex-v8",
                    "---",
                    "",
                    "Body.",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    return paper


def test_graph_migrate_paper_datasets_dry_run_json_exit_10_for_pending(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json"],
    )

    assert result.exit_code == 10
    payload = json.loads(result.output)
    assert payload["apply"] is False
    assert payload["changed_files"] == [str(paper)]
    assert payload["conflict_count"] == 0
    assert "datasets:" in paper.read_text(encoding="utf-8")


def test_graph_migrate_paper_datasets_apply_rewrites_and_exits_zero(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json", "--apply"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["apply"] is True
    assert payload["changed_files"] == [str(paper)]
    text = paper.read_text(encoding="utf-8")
    assert "datasets:" not in text
    assert "dataset_usage:" in text


def test_graph_migrate_paper_datasets_conflict_exits_20_and_leaves_file(tmp_path: Path) -> None:
    root = tmp_path / "project"
    paper = _write_paper_dataset_project(root, conflict=True)
    original = paper.read_text(encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "json", "--apply"],
    )

    assert result.exit_code == 20
    payload = json.loads(result.output)
    assert payload["conflicts"][0]["reason"] == "role-conflict"
    assert paper.read_text(encoding="utf-8") == original


def test_graph_migrate_paper_datasets_table_mentions_mode_and_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "project"
    _write_paper_dataset_project(root, conflict=True)

    result = CliRunner().invoke(
        main,
        ["graph", "migrate-paper-datasets", "--project-root", str(root), "--format", "table"],
    )

    assert result.exit_code == 20
    assert "Paper Dataset Migration" in result.output
    assert "role-conflict" in result.output


def test_audit_project_graph_rejects_tag_refs_in_same_as(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "entities" / "topics").mkdir(parents=True)
    (root / "entities" / "topics" / "evaluation.md").write_text(
        "\n".join(
            [
                "---",
                'id: "topic:evaluation"',
                'type: "topic"',
                'title: "Evaluation"',
                "related: []",
                "source_refs: []",
                'same_as: ["tag:draft"]',
                "---",
                "",
                "Evaluation topic body.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["has_failures"] is True
    assert any(row["field"] == "same_as" and row["target"] == "tag:draft" for row in report["rows"])


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
    (root / "entities" / "questions").mkdir(parents=True)
    (root / "entities" / "questions" / "q16-demo.md").write_text(
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


def test_audit_project_graph_resolves_cross_kind_slug_reference(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Explore treatment response",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [topic:treatment-response]",
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
                        "canonical_id": "concept:treatment-response",
                        "kind": "concept",
                        "title": "Treatment response",
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["unresolved_reference_count"] == 0
    assert report["has_failures"] is False


def test_audit_project_graph_reports_ambiguous_cross_kind_slug_reference(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    (root / "tasks").mkdir(parents=True)
    (root / "tasks" / "active.md").write_text(
        "\n".join(
            [
                "## [t001] Explore treatment response",
                "- type: research",
                "- priority: P1",
                "- status: active",
                "- related: [topic:treatment-response]",
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
                        "canonical_id": "concept:treatment-response",
                        "kind": "concept",
                        "title": "Treatment response concept",
                    },
                    {
                        "canonical_id": "method:treatment-response",
                        "kind": "method",
                        "title": "Treatment response method",
                    },
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["has_failures"] is True
    assert any(
        row["check"] == "ambiguous_cross_kind_reference"
        and row["field"] == "related"
        and row["target"] == "topic:treatment-response"
        for row in report["rows"]
    )


def test_audit_project_graph_uses_configured_local_profile_directory(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
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


def test_audit_project_graph_accepts_declared_gene_entities(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\nontologies: [biology]\n", encoding="utf-8")
    (root / "entities" / "genes").mkdir(parents=True)
    (root / "entities" / "genes" / "tp53.md").write_text(
        "\n".join(
            [
                "---",
                'id: "gene:tp53"',
                'type: "gene"',
                'title: "TP53"',
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "entities" / "hypotheses" / "h01-demo.md").write_text(
        "\n".join(
            [
                "---",
                'id: "hypothesis:h01-demo"',
                'type: "hypothesis"',
                'title: "Demo hypothesis"',
                'related: ["gene:tp53"]',
                "---",
                "",
            ]
        ),
        encoding="utf-8",
    )

    report = audit_project_graph(root)

    assert report["unresolved_reference_count"] == 0
    assert report["has_failures"] is False


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


def test_graph_migrate_command_is_dry_run_by_default(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  local: local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "entities" / "hypotheses" / "h01-demo.md").write_text(
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
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "migrate", "--project-root", str(root), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["apply"] is False
    assert payload["rewritten_file_count"] == 1
    assert payload["has_failures"] is False
    assert payload["unresolved_reference_count"] == 0

    task_text = (root / "tasks" / "active.md").read_text(encoding="utf-8")
    assert "related: [H01, topic:evaluation]" in task_text
    assert "hypothesis:h01-demo" not in task_text

    report_path = root / "knowledge" / "reports" / "kg-migration-audit.json"
    assert not report_path.exists()
    assert payload["report_path"] is None

    entities_path = root / "knowledge" / "sources" / "local" / "entities.yaml"
    entities = yaml.safe_load(entities_path.read_text(encoding="utf-8"))
    assert entities == {
        "entities": [
            {
                "canonical_id": "topic:evaluation",
                "kind": "topic",
                "title": "Evaluation",
            }
        ]
    }


def test_graph_migrate_command_rewrites_alias_refs_and_writes_report_with_apply(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "science.yaml").write_text(
        "\n".join(
            [
                "name: demo",
                "knowledge_profiles:",
                "  local: local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "entities" / "hypotheses" / "h01-demo.md").write_text(
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
    result = runner.invoke(main, ["graph", "migrate", "--project-root", str(root), "--format", "json", "--apply"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["apply"] is True
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
                "  local: lab_local",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (root / "entities" / "hypotheses").mkdir(parents=True)
    (root / "entities" / "hypotheses" / "h01-demo.md").write_text(
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

    runner = CliRunner()
    result = runner.invoke(main, ["graph", "migrate", "--project-root", str(root), "--format", "json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["apply"] is False
    assert payload["local_profile"] == "lab_local"

    entities_path = root / "knowledge" / "sources" / "lab_local" / "entities.yaml"
    report_path = root / "knowledge" / "reports" / "kg-migration-audit.json"

    assert entities_path.exists()
    assert not report_path.exists()
    assert not (root / "knowledge" / "sources" / "local").exists()

    result = runner.invoke(main, ["graph", "migrate", "--project-root", str(root), "--format", "json", "--apply"])

    assert result.exit_code == 0
    assert entities_path.exists()
    assert report_path.exists()


def test_audit_unresolved_topic_includes_commons_hint(tmp_path: Path, monkeypatch) -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "commons" / "valid"
    commons_root = tmp_path / "commons"
    shutil.copytree(fixture_root, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))

    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    hypothesis_path = project / "entities" / "hypotheses" / "h1.md"
    hypothesis_path.parent.mkdir(parents=True)
    hypothesis_path.write_text(
        """---
id: "hypothesis:h1"
type: "hypothesis"
title: "H1"
related: ["topic:does-not-exist"]
source_refs: []
created: "2026-03-12"
updated: "2026-03-12"
---

Body.
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    bad = next(row for row in rows if row["target"] == "topic:does-not-exist")
    assert bad["check"] == "unresolved_reference"
    assert "topics/does-not-exist.md" in bad["details"]
    assert "science commons promote" in bad["details"]


def _scaffold_project_with_related(project: Path, related: str) -> None:
    project.mkdir()
    (project / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    hypothesis_path = project / "entities" / "hypotheses" / "h1.md"
    hypothesis_path.parent.mkdir(parents=True)
    hypothesis_path.write_text(
        f"""---
id: "hypothesis:h1"
type: "hypothesis"
title: "H1"
related: [{related}]
source_refs: []
created: "2026-03-12"
updated: "2026-03-12"
---

Body.
""",
        encoding="utf-8",
    )


def test_audit_unresolved_nonpromotable_kind_omits_promote_hint(tmp_path: Path) -> None:
    """A non-promotable kind (e.g. question) must not be told to run commons
    promote; the hint should point to prose linking instead."""
    project = tmp_path / "project"
    _scaffold_project_with_related(project, '"question:does-not-exist"')

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    bad = next(row for row in rows if row["target"] == "question:does-not-exist")
    assert bad["check"] == "unresolved_reference"
    assert "science commons promote" not in bad["details"]
    assert "prose" in bad["details"].lower()


def test_audit_unresolved_cross_project_address_omits_promote_hint(tmp_path: Path) -> None:
    """A peer-addressed cross-project ref in `related` must not suggest commons
    promote (you cannot promote a peer's entity); point to prose linking."""
    project = tmp_path / "project"
    _scaffold_project_with_related(project, '"health-meta:research-question:foo"')

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    bad = next(row for row in rows if row["target"] == "health-meta:research-question:foo")
    assert bad["check"] == "unresolved_reference"
    assert "science commons promote" not in bad["details"]
    assert "prose" in bad["details"].lower()


def test_audit_unresolved_dataset_includes_dataset_commons_hint(tmp_path: Path, monkeypatch) -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "commons" / "valid"
    commons_root = tmp_path / "commons"
    shutil.copytree(fixture_root, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))

    project = tmp_path / "project"
    project.mkdir()
    (project / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    manifest_path = project / "knowledge" / "sources" / "local" / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("", encoding="utf-8")
    hypothesis_path = project / "entities" / "hypotheses" / "h1.md"
    hypothesis_path.parent.mkdir(parents=True)
    hypothesis_path.write_text(
        """---
id: "hypothesis:h1"
type: "hypothesis"
title: "H1"
related: ["dataset:does-not-exist"]
source_refs: []
created: "2026-03-12"
updated: "2026-03-12"
---

Body.
""",
        encoding="utf-8",
    )

    sources = load_project_sources(project)
    rows, _ = audit_project_sources(sources)

    bad = next(row for row in rows if row["target"] == "dataset:does-not-exist")
    assert bad["check"] == "unresolved_reference"
    assert "datasets/does-not-exist/entity.md" in bad["details"]
    assert "science commons promote dataset --slug does-not-exist --from <project>" in bad["details"]
