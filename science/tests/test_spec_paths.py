"""One resolver for spec documents across the canonical and legacy layouts.

`science entity migrate-specs` moves specs to `entities/specs/NNNN-<slug>.md`;
`create-project` still scaffolds `specs/<slug>.md`. Six commands read these
documents, and before `spec_paths` each named a path literally, so a migrated
project read nothing where the document existed and was reachable
(fb-2026-07-26-020).
"""

from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main
from science_tool.spec_paths import LAYOUT_CANONICAL, LAYOUT_LEGACY, resolve_spec


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "science.yaml").write_text("name: spec-path-test\n", encoding="utf-8")
    return root


def test_canonical_layout_is_found_by_numbered_filename(tmp_path: Path) -> None:
    root = _project(tmp_path)
    specs = root / "entities" / "specs"
    specs.mkdir(parents=True)
    (specs / "0037-scope-boundaries.md").write_text("# Scope\n", encoding="utf-8")

    location = resolve_spec(root, "scope-boundaries")
    assert location.path == "entities/specs/0037-scope-boundaries.md"
    assert location.layout == LAYOUT_CANONICAL


def test_canonical_layout_is_found_through_a_preserved_alias(tmp_path: Path) -> None:
    """Migration preserves the pre-migration id as an alias.

    A project that also renamed the document would otherwise read as absent
    while the file sits in plain view.
    """
    root = _project(tmp_path)
    specs = root / "entities" / "specs"
    specs.mkdir(parents=True)
    (specs / "0041-what-we-will-not-study.md").write_text(
        "---\nid: spec:0041-what-we-will-not-study\naliases:\n  - spec:scope-boundaries\n---\n# Scope\n",
        encoding="utf-8",
    )

    location = resolve_spec(root, "scope-boundaries")
    assert location.path == "entities/specs/0041-what-we-will-not-study.md"
    assert location.layout == LAYOUT_CANONICAL


def test_legacy_layout_is_found_and_reported_as_legacy(tmp_path: Path) -> None:
    """An unmigrated project still resolves, and says it is unmigrated."""
    root = _project(tmp_path)
    (root / "specs").mkdir()
    (root / "specs" / "scope-boundaries.md").write_text("# Scope\n", encoding="utf-8")

    location = resolve_spec(root, "scope-boundaries")
    assert location.path == "specs/scope-boundaries.md"
    assert location.layout == LAYOUT_LEGACY


def test_canonical_wins_when_a_project_holds_both(tmp_path: Path) -> None:
    """Mid-migration, the canonical copy is the one the migrator wrote."""
    root = _project(tmp_path)
    specs = root / "entities" / "specs"
    specs.mkdir(parents=True)
    (specs / "0037-scope-boundaries.md").write_text("# Canonical\n", encoding="utf-8")
    (root / "specs").mkdir()
    (root / "specs" / "scope-boundaries.md").write_text("# Stale\n", encoding="utf-8")

    assert resolve_spec(root, "scope-boundaries").layout == LAYOUT_CANONICAL


def test_absent_in_both_layouts_reports_not_found(tmp_path: Path) -> None:
    location = resolve_spec(_project(tmp_path), "scope-boundaries")
    assert not location.found
    assert location.path is None and location.layout is None


def test_cli_reports_the_resolved_path_and_layout(tmp_path: Path) -> None:
    root = _project(tmp_path)
    specs = root / "entities" / "specs"
    specs.mkdir(parents=True)
    (specs / "0002-research-question.md").write_text("# Q\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["project", "spec-path", "--project-root", str(root), "--slug", "research-question", "--format", "json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload == {
        "slug": "research-question",
        "path": "entities/specs/0002-research-question.md",
        "layout": LAYOUT_CANONICAL,
    }


def test_cli_fails_rather_than_reporting_an_absent_spec_as_empty(tmp_path: Path) -> None:
    """A failed lookup must not read as "the project declared nothing"."""
    result = CliRunner().invoke(
        main,
        ["project", "spec-path", "--project-root", str(_project(tmp_path)), "--slug", "scope-boundaries"],
    )
    assert result.exit_code != 0
    assert "no spec 'scope-boundaries'" in result.output
    assert "entities/specs" in result.output
