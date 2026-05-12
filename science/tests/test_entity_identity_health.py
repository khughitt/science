from __future__ import annotations

from science_tool.entity_identity import collect_identity_warnings
from science_tool.graph.health import build_health_report
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import KnowledgeProfiles, MarkdownSourceDocument, ProjectSources, load_project_sources


def _sources_with_documents(project, documents: list[MarkdownSourceDocument]) -> ProjectSources:
    return ProjectSources(
        project_name="project",
        project_root=str(project),
        profiles=KnowledgeProfiles(),
        entities=[],
        registry=EntityRegistry.with_core_types(),
        markdown_documents=documents,
    )


def test_identity_health_resolves_markdown_manual_aliases(tmp_path) -> None:
    project = tmp_path / "project"
    sources = _sources_with_documents(
        project,
        [MarkdownSourceDocument(path="doc/summary.md", frontmatter={}, body="This cites [[h999]] in prose.\n")],
    ).model_copy(update={"manual_aliases": {"h999": "hypothesis:h999"}})

    warnings = collect_identity_warnings(project, sources=sources)

    assert not [warning for warning in warnings if warning.code == "unresolved-prose-reference"]


def test_identity_health_reports_baselined_missing_id_through_real_health_flow(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "knowledge").mkdir(parents=True)
    (project / "science.yaml").write_text("id: missing-id-project\n", encoding="utf-8")
    (project / "knowledge" / "entity-identity-baseline.yaml").write_text(
        """
records:
  - path: doc/finding.md
    accepted_at: "2026-05-12T10:00:00Z"
""".strip(),
        encoding="utf-8",
    )
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\ntitle: Legacy\n---\n",
        encoding="utf-8",
    )

    report = build_health_report(project, checks={"entity_identity"})

    assert report["entity_identity"][0]["code"] == "missing-canonical-id"
    assert report["entity_identity"][0]["severity"] == "warning"
    assert report["total_issues"] == 1


def test_identity_health_reports_unbaselined_missing_id_as_error_through_real_health_flow(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: missing-id-project\n", encoding="utf-8")
    (project / "doc" / "finding.md").write_text(
        "---\nkind: finding\ntitle: Current\n---\n",
        encoding="utf-8",
    )

    report = build_health_report(project, checks={"entity_identity"})

    assert report["entity_identity"][0]["code"] == "missing-canonical-id"
    assert report["entity_identity"][0]["severity"] == "error"
    assert report["total_issues"] == 1


def test_identity_health_flags_missing_canonical_id_as_warning_for_baselined_record(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "knowledge").mkdir(parents=True)
    (project / "knowledge" / "entity-identity-baseline.yaml").write_text(
        """
records:
  - path: doc/finding.md
    accepted_at: "2026-05-12T10:00:00Z"
""".strip(),
        encoding="utf-8",
    )
    sources = _sources_with_documents(
        project,
        [
            MarkdownSourceDocument(
                path="doc/finding.md",
                frontmatter={"kind": "finding", "title": "Legacy"},
                body="",
            )
        ],
    )

    warnings = collect_identity_warnings(project, sources=sources)

    assert warnings[0].code == "missing-canonical-id"
    assert warnings[0].severity == "warning"


def test_identity_health_accepts_canonical_id_when_id_is_absent(tmp_path) -> None:
    project = tmp_path / "project"
    sources = _sources_with_documents(
        project,
        [
            MarkdownSourceDocument(
                path="doc/concept.md",
                frontmatter={"kind": "concept", "canonical_id": "concept:c1", "title": "Concept"},
                body="",
            )
        ],
    )

    warnings = collect_identity_warnings(project, sources=sources)

    assert not [warning for warning in warnings if warning.code in {"missing-canonical-id", "invalid-canonical-id"}]


def test_identity_health_flags_invalid_canonical_id_when_id_is_absent(tmp_path) -> None:
    project = tmp_path / "project"
    sources = _sources_with_documents(
        project,
        [
            MarkdownSourceDocument(
                path="doc/concept.md",
                frontmatter={"kind": "concept", "canonical_id": "not canonical", "title": "Concept"},
                body="",
            )
        ],
    )

    warnings = collect_identity_warnings(project, sources=sources)

    assert warnings[0].code == "invalid-canonical-id"
    assert warnings[0].canonical_id == "not canonical"


def test_identity_health_flags_unresolved_markdown_prose_reference_as_warning(tmp_path) -> None:
    project = tmp_path / "project"
    sources = _sources_with_documents(
        project,
        [MarkdownSourceDocument(path="doc/summary.md", frontmatter={}, body="This cites [[h999]] in prose.\n")],
    )

    warnings = collect_identity_warnings(project, sources=sources)

    assert any(warning.code == "unresolved-prose-reference" and warning.severity == "warning" for warning in warnings)


def test_identity_health_resolves_markdown_aliases_from_loaded_sources(tmp_path) -> None:
    project = tmp_path / "project"
    (project / "doc").mkdir(parents=True)
    (project / "science.yaml").write_text("id: alias-project\n", encoding="utf-8")
    (project / "doc" / "h001.md").write_text(
        "---\nkind: hypothesis\nid: hypothesis:h001\naliases: [h001]\ntitle: H001\n---\n",
        encoding="utf-8",
    )
    (project / "doc" / "summary.md").write_text("This cites [[h001]] in prose.\n", encoding="utf-8")

    warnings = collect_identity_warnings(project, sources=load_project_sources(project))

    assert not [warning for warning in warnings if warning.code == "unresolved-prose-reference"]


def test_identity_health_resolves_uppercase_short_refs_case_insensitively(tmp_path) -> None:
    project = tmp_path / "project"
    sources = _sources_with_documents(
        project,
        [MarkdownSourceDocument(path="doc/summary.md", frontmatter={}, body="This cites [[H001]] in prose.\n")],
    ).model_copy(update={"manual_aliases": {"h001": "hypothesis:h001"}})

    warnings = collect_identity_warnings(project, sources=sources)

    assert not [warning for warning in warnings if warning.code == "unresolved-prose-reference"]
