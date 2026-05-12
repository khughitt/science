from __future__ import annotations

import yaml

from science_tool.entity_migrations import audit_identifiers, migrate_identifiers


def test_audit_identifiers_reports_baselined_missing_ids(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "doc" / "finding.md").write_text("---\nkind: finding\ntitle: Legacy\n---\n", encoding="utf-8")

    report = audit_identifiers(project)

    assert report["missing_canonical_ids"] == ["doc/finding.md"]


def test_migrate_identifiers_dry_run_reports_changes_without_rewriting(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "finding.md"
    path.write_text("---\nkind: finding\ntitle: Legacy\n---\n", encoding="utf-8")

    report = migrate_identifiers(project, apply=False)

    assert report["planned_changes"][0]["new_id"] == "finding:finding"
    assert "id: finding:finding" not in path.read_text(encoding="utf-8")


def test_migrate_identifiers_apply_inserts_id_without_rewriting_body(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "finding.md"
    path.write_text(
        "---\nkind: finding\n# keep this comment\ntitle: Legacy\n---\n\nBody text.\n",
        encoding="utf-8",
    )

    report = migrate_identifiers(project, apply=True)

    text = path.read_text(encoding="utf-8")
    assert report["applied"] is True
    assert "kind: finding\nid: finding:finding\n# keep this comment\n" in text
    assert text.endswith("\nBody text.\n")


def test_migrate_identifiers_reports_collisions_without_rewriting(tmp_path) -> None:
    project = tmp_path / "project"
    left = project / "doc" / "a" / "summary.md"
    right = project / "doc" / "b" / "summary.md"
    left.parent.mkdir(parents=True)
    right.parent.mkdir(parents=True)
    for path in (left, right):
        path.write_text("---\nkind: finding\ntitle: Summary\n---\n", encoding="utf-8")

    report = migrate_identifiers(project, apply=False)

    assert report["collisions"] == [{"new_id": "finding:summary", "paths": ["doc/a/summary.md", "doc/b/summary.md"]}]


def test_migrate_identifiers_reports_collision_with_existing_id(tmp_path) -> None:
    project = tmp_path / "project"
    existing = project / "doc" / "a" / "summary.md"
    new = project / "doc" / "b" / "summary.md"
    existing.parent.mkdir(parents=True)
    new.parent.mkdir(parents=True)
    existing.write_text("---\nkind: finding\nid: finding:summary\ntitle: Existing\n---\n", encoding="utf-8")
    new.write_text("---\nkind: finding\ntitle: New\n---\n", encoding="utf-8")

    report = migrate_identifiers(project, apply=False)

    assert report["collisions"] == [{"new_id": "finding:summary", "paths": ["doc/a/summary.md", "doc/b/summary.md"]}]


def test_audit_identifiers_ignores_project_template_markdown(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "templates").mkdir(parents=True)
    (project / "templates" / "gene-note.md").write_text(
        "---\nsymbol: {{SYMBOL}}\n---\n\n# {{SYMBOL}}\n",
        encoding="utf-8",
    )

    report = audit_identifiers(project)

    assert report == {"missing_canonical_ids": [], "invalid_canonical_ids": []}


def test_doc_templates_markdown_is_still_audited_and_migrated(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc" / "templates").mkdir(parents=True)
    path = project / "doc" / "templates" / "foo.md"
    path.write_text("---\nkind: finding\ntitle: Foo\n---\n", encoding="utf-8")

    audit_report = audit_identifiers(project)
    migration_report = migrate_identifiers(project, apply=False)

    assert audit_report["missing_canonical_ids"] == ["doc/templates/foo.md"]
    assert migration_report["planned_changes"] == [{"path": "doc/templates/foo.md", "new_id": "finding:foo"}]


def test_malformed_non_entity_frontmatter_does_not_crash_audit_or_migrate(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "notes").mkdir(parents=True)
    (project / "notes" / "command.md").write_text("---\nrun: [unterminated\n---\n", encoding="utf-8")

    audit_report = audit_identifiers(project)
    migration_report = migrate_identifiers(project, apply=False)

    assert audit_report == {"missing_canonical_ids": [], "invalid_canonical_ids": []}
    assert migration_report["planned_changes"] == []
    assert migration_report["collisions"] == []


def test_present_falsey_id_is_invalid_and_not_rewritten(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "finding.md"
    original = "---\nkind: finding\nid: 0\ntitle: Legacy\n---\n"
    path.write_text(original, encoding="utf-8")

    audit_report = audit_identifiers(project)
    migration_report = migrate_identifiers(project, apply=True)

    assert audit_report["missing_canonical_ids"] == []
    assert audit_report["invalid_canonical_ids"] == ["doc/finding.md"]
    assert migration_report["planned_changes"] == []
    assert path.read_text(encoding="utf-8") == original


def test_unsafe_generated_id_is_reported_without_rewriting(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "bad#name.md"
    original = "---\nkind: finding\ntitle: Bad Name\n---\n"
    path.write_text(original, encoding="utf-8")

    report = migrate_identifiers(project, apply=False)

    assert report["planned_changes"] == []
    assert report["invalid_generated_ids"] == [{"path": "doc/bad#name.md", "new_id": "finding:bad#name"}]
    assert path.read_text(encoding="utf-8") == original


def test_generated_id_inserted_by_apply_parses_as_exact_yaml_scalar(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "finding.md"
    path.write_text("---\nkind: finding\ntitle: Finding\n---\n", encoding="utf-8")

    migrate_identifiers(project, apply=True)

    text = path.read_text(encoding="utf-8")
    _, frontmatter_text, _ = text.split("---\n", 2)
    assert yaml.safe_load(frontmatter_text)["id"] == "finding:finding"
