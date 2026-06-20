from __future__ import annotations

from science_tool.entity_migrations import audit_identifiers


def test_audit_identifiers_reports_baselined_missing_ids(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "doc" / "finding.md").write_text("---\nkind: finding\ntitle: Legacy\n---\n", encoding="utf-8")

    report = audit_identifiers(project)

    assert report["missing_canonical_ids"] == ["doc/finding.md"]


def test_audit_identifiers_ignores_project_template_markdown(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "templates").mkdir(parents=True)
    (project / "templates" / "gene-note.md").write_text(
        "---\nsymbol: {{SYMBOL}}\n---\n\n# {{SYMBOL}}\n",
        encoding="utf-8",
    )

    report = audit_identifiers(project)

    assert report == {"missing_canonical_ids": [], "invalid_canonical_ids": []}


def test_doc_templates_markdown_is_still_audited(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc" / "templates").mkdir(parents=True)
    path = project / "doc" / "templates" / "foo.md"
    path.write_text("---\nkind: finding\ntitle: Foo\n---\n", encoding="utf-8")

    audit_report = audit_identifiers(project)

    assert audit_report["missing_canonical_ids"] == ["doc/templates/foo.md"]


def test_malformed_non_entity_frontmatter_does_not_crash_audit(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "notes").mkdir(parents=True)
    (project / "notes" / "command.md").write_text("---\nrun: [unterminated\n---\n", encoding="utf-8")

    audit_report = audit_identifiers(project)

    assert audit_report == {"missing_canonical_ids": [], "invalid_canonical_ids": []}


def test_present_falsey_id_is_invalid(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    path = project / "doc" / "finding.md"
    original = "---\nkind: finding\nid: 0\ntitle: Legacy\n---\n"
    path.write_text(original, encoding="utf-8")

    audit_report = audit_identifiers(project)

    assert audit_report["missing_canonical_ids"] == []
    assert audit_report["invalid_canonical_ids"] == ["doc/finding.md"]
