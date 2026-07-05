from __future__ import annotations

import importlib.util
import sys
import textwrap
from datetime import date
from pathlib import Path
from types import ModuleType

from science_tool.commons.config import CommonsSettings
from science_tool.registry.config import GlobalConfig, RegisteredProject, save_global_config


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_script(relative_path: str) -> ModuleType:
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


downstream_inventory = _load_script("scripts/audit_downstream_project_inventory.py")
registered_inventory = _load_script("scripts/audit_registered_projects_legacy_surfaces.py")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).strip() + "\n", encoding="utf-8")


def _science_yaml(project: Path, text: str = "id: fixture\n") -> None:
    _write(project / "science.yaml", text)


def test_legacy_scan_reports_precise_project_surfaces(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _science_yaml(
        project,
        """
        id: fixture
        profiles:
          local: profiles/local.yaml
        parent: old-parent
        """,
    )
    _write(
        project / "doc" / "findings" / "f001.md",
        """
        ---
        type: finding
        id: finding:f001
        title: Legacy finding
        access: public
        related:
          - article:smith2020
        ---
        Body with [NEEDS CITATION].
        """,
    )
    _write(
        project / "entities" / "articles" / "article.md",
        """
        ---
        kind: article
        id: article:local-news
        title: Live article entity
        deprecated_ids:
          - article:old-local-news
        status: retired
        ---
        This is not a paper alias.
        """,
    )
    _write(project / "tasks" / "active.md", "- status: retired\n")
    _write(project / "workflow" / "graph.edges.yaml", "edges: []\n")
    _write(project / "knowledge" / "sources" / "local" / "entities.yaml", "[]\n")
    _write(project / "validate.local.sh", "#!/usr/bin/env bash\n")

    result = downstream_inventory.scan_legacy_surfaces(project)

    assert result.counts_by_surface() == {
        "article_prefix_alias": 1,
        "bare_profiles_config": 1,
        "legacy_entity_roots": 1,
        "legacy_marker_alias": 1,
        "parent_children_config": 1,
        "retired_edges_yaml": 1,
        "scalar_access": 1,
        "aggregate_manifest": 1,
        "validate_local_sh": 1,
    }
    assert result.paths_for("article_prefix_alias") == ["doc/findings/f001.md"]
    assert result.paths_for("legacy_entity_roots") == ["doc/findings/f001.md"]
    assert "entities/articles/article.md" not in result.paths_for("article_prefix_alias")


def test_legacy_entity_roots_reports_only_registered_markdown_entity_kinds(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _science_yaml(project)
    _write(
        project / "doc" / "plans" / "design.md",
        """
        ---
        type: spec
        id: spec:design
        title: Design note
        ---
        This is doc metadata, not a registered entity kind.
        """,
    )
    _write(
        project / "specs" / "datasets" / "reference.md",
        """
        ---
        type: dataset
        id: dataset:reference
        title: Reference dataset
        status: active
        created: "2026-07-04"
        updated: "2026-07-04"
        ---
        This is a real markdown entity in a legacy root.
        """,
    )

    result = downstream_inventory.scan_legacy_surfaces(project)

    assert result.paths_for("legacy_entity_roots") == ["specs/datasets/reference.md"]


def test_type_frontmatter_reports_live_entities_not_archived_legacy_notes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _science_yaml(project)
    _write(
        project / "archive" / "project-layout-legacy" / "notes" / "articles" / "smith.md",
        """
        ---
        type: paper
        id: paper:smith
        title: Archived paper
        ---
        Archived legacy layout note.
        """,
    )
    _write(
        project / "entities" / "papers" / "smith.md",
        """
        ---
        type: paper
        id: paper:smith
        title: Live paper
        ---
        Current entity.
        """,
    )

    result = downstream_inventory.scan_legacy_surfaces(project)

    assert result.paths_for("type_frontmatter") == ["entities/papers/smith.md"]


def test_legacy_scan_ignores_nested_worktrees_and_git_dirs(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _science_yaml(project)
    _write(
        project / ".worktrees" / "copy" / "doc" / "findings" / "f002.md",
        """
        ---
        type: finding
        id: finding:f002
        ---
        """,
    )
    _write(project / ".git" / "shadow.edges.yaml", "edges: []\n")

    result = downstream_inventory.scan_legacy_surfaces(project)

    assert result.counts_by_surface() == {}


def test_registered_project_scan_deduplicates_resolved_paths(tmp_path: Path) -> None:
    project = tmp_path / "project"
    _science_yaml(project)
    _write(project / "workflow" / "graph.edges.yaml", "edges: []\n")
    alias = tmp_path / "alias"
    alias.symlink_to(project, target_is_directory=True)
    config_path = tmp_path / "config.yaml"
    save_global_config(
        GlobalConfig(
            projects=[
                RegisteredProject(
                    path=str(project),
                    name="project",
                    registered=date(2026, 7, 4),
                ),
                RegisteredProject(
                    path=str(alias),
                    name="project-copy",
                    registered=date(2026, 7, 4),
                ),
            ],
        ),
        config_path,
    )

    report = registered_inventory.scan_registered_projects(
        config_path=config_path,
        search_roots=[],
    )

    assert report.summary["registered_entries"] == 2
    assert report.summary["scanned_projects"] == 1
    assert report.summary["duplicate_registered_entries"] == 1
    assert report.surface_totals == {"retired_edges_yaml": 1}


def test_registered_project_scan_reports_skipped_registered_projects(tmp_path: Path) -> None:
    missing_science_yaml = tmp_path / "missing-science-yaml"
    missing_science_yaml.mkdir()
    config_path = tmp_path / "config.yaml"
    save_global_config(
        GlobalConfig(
            projects=[
                RegisteredProject(
                    path=str(missing_science_yaml),
                    name="missing",
                    registered=date(2026, 7, 4),
                ),
            ],
        ),
        config_path,
    )

    report = registered_inventory.scan_registered_projects(
        config_path=config_path,
        search_roots=[],
    )

    assert report.summary["skipped_registered_projects"] == 1
    assert report.skipped_registered_projects == (
        {
            "path": str(missing_science_yaml.resolve()),
            "reason": "missing science.yaml",
        },
    )


def test_coverage_sweep_excludes_nested_worktrees_and_reports_unregistered(
    tmp_path: Path,
) -> None:
    registered = tmp_path / "registered"
    unregistered = tmp_path / "unregistered"
    nested = registered / ".worktrees" / "copy"
    for project in (registered, unregistered, nested):
        _science_yaml(project)
    config_path = tmp_path / "config.yaml"
    save_global_config(
        GlobalConfig(
            projects=[
                RegisteredProject(
                    path=str(registered),
                    name="registered",
                    registered=date(2026, 7, 4),
                ),
            ],
        ),
        config_path,
    )

    report = registered_inventory.scan_registered_projects(
        config_path=config_path,
        search_roots=[tmp_path],
    )

    assert [entry["path"] for entry in report.unregistered_science_yaml] == [str(unregistered.resolve())]


def test_configured_commons_root_is_scanned_as_shared_repository(tmp_path: Path) -> None:
    commons = tmp_path / "science-commons"
    _science_yaml(commons, "id: science-commons\n")
    _write(
        commons / "datasets" / "reference" / "entity.md",
        """
        ---
        type: dataset
        id: dataset:reference
        title: Reference dataset
        ---
        """,
    )
    config_path = tmp_path / "config.yaml"
    save_global_config(
        GlobalConfig(commons=CommonsSettings(root=commons)),
        config_path,
    )

    report = registered_inventory.scan_registered_projects(
        config_path=config_path,
        search_roots=[tmp_path],
    )

    assert report.summary["shared_repository_entries"] == 1
    assert report.summary["scanned_projects"] == 1
    assert report.summary["unregistered_science_yaml"] == 0
    assert report.surface_totals == {"type_frontmatter": 1}
