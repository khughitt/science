from __future__ import annotations

import json
import textwrap
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.graph.article_ref_migration import plan_article_ref_migration


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def test_article_ref_migration_rewrites_only_markdown_reference_fields(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write(project / "science.yaml", "id: fixture\n")
    paper = project / "archive" / "project-layout-legacy" / "notes" / "articles" / "Cech2014.md"
    _write(
        paper,
        """
        ---
        id: "article:Cech2014"
        type: "article"
        title: "The Noncoding RNA Revolution"
        source_refs:
          - "cite:Cech2014"
        related: ["article:Rouskin2014"]
        ---

        Body prose mentions article:BodyOnly and BibTeX uses @article{Cech2014}.
        """,
    )

    dry_run = plan_article_ref_migration(project, apply=False)

    assert dry_run.changed_files == ("archive/project-layout-legacy/notes/articles/Cech2014.md",)
    assert dry_run.rewrite_count == 1
    assert "article:Rouskin2014" in paper.read_text(encoding="utf-8")

    applied = plan_article_ref_migration(project, apply=True)
    text = paper.read_text(encoding="utf-8")

    assert applied.changed_files == dry_run.changed_files
    assert applied.rewrite_count == 1
    assert 'id: "article:Cech2014"' in text
    assert 'type: "article"' in text
    assert 'related: ["paper:Rouskin2014"]' in text
    assert "article:BodyOnly" in text
    assert "@article{Cech2014}" in text


def test_article_ref_migration_rewrites_structured_json_and_yaml_reference_keys(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write(project / "science.yaml", "id: fixture\n")
    _write(
        project / ".labnote" / "app_export" / "entities" / "index.json",
        json.dumps(
            [
                {
                    "id": "article:live-article-kind",
                    "metadata": {"source_refs": ["article:Binder2024"]},
                    "source_refs": ["article:Binder2024"],
                    "type": "article",
                }
            ],
            indent=2,
        )
        + "\n",
    )
    _write(
        project / "knowledge" / "sources" / "local" / "relations.yaml",
        """
        relations:
        - subject: article:Smith2024
          predicate: skos:related
          object: article:Jones2023
        - id: article:real-article-entity
          kind: article
          title: Article kind remains live
        """,
    )

    report = plan_article_ref_migration(project, apply=True)

    assert report.rewrite_count == 4
    payload = json.loads((project / ".labnote" / "app_export" / "entities" / "index.json").read_text())
    assert payload[0]["id"] == "article:live-article-kind"
    assert payload[0]["type"] == "article"
    assert payload[0]["metadata"]["source_refs"] == ["paper:Binder2024"]
    assert payload[0]["source_refs"] == ["paper:Binder2024"]
    yaml_text = (project / "knowledge" / "sources" / "local" / "relations.yaml").read_text(encoding="utf-8")
    assert "subject: paper:Smith2024" in yaml_text
    assert "object: paper:Jones2023" in yaml_text
    assert "id: article:real-article-entity" in yaml_text
    assert "kind: article" in yaml_text


def test_article_ref_migration_cli_reports_pending_dry_run_and_writes_with_apply(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _write(project / "science.yaml", "id: fixture\n")
    _write(
        project / "entities" / "papers" / "Binder2024.md",
        """
        ---
        kind: paper
        id: paper:Binder2024
        title: Binder 2024
        source_refs:
        - article:Binder2024
        ---
        """,
    )

    runner = CliRunner()
    dry_run = runner.invoke(
        main,
        ["graph", "migrate-article-refs", "--project-root", str(project), "--format", "json"],
    )

    assert dry_run.exit_code == 10
    dry_payload = json.loads(dry_run.output)
    assert dry_payload["mode"] == "dry-run"
    assert dry_payload["changed_file_count"] == 1
    assert "article:Binder2024" in (project / "entities" / "papers" / "Binder2024.md").read_text(encoding="utf-8")

    applied = runner.invoke(
        main,
        ["graph", "migrate-article-refs", "--project-root", str(project), "--format", "json", "--apply"],
    )

    assert applied.exit_code == 0
    applied_payload = json.loads(applied.output)
    assert applied_payload["mode"] == "apply"
    assert applied_payload["changed_file_count"] == 1
    assert "paper:Binder2024" in (project / "entities" / "papers" / "Binder2024.md").read_text(encoding="utf-8")
