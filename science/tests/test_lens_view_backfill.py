# science/tests/test_lens_view_backfill.py  (Task 7 appends to this file)
from __future__ import annotations

from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project
from science_tool.cli import main


def _write_entity(root, name, extra_fm) -> None:
    (root / "entities" / "questions").mkdir(parents=True, exist_ok=True)
    # Extract id from filename (remove .md extension)
    id_part = name.replace(".md", "")
    (root / "entities" / "questions" / name).write_text(
        "---\n"
        f"id: question:{id_part}\nkind: question\ntype: question\ntitle: X\nstatus: open\nproject: testproj\n"
        "ontology_terms: []\nrelated: []\nsource_refs: []\n"
        f"{extra_fm}"
        "created: '2026-07-04'\nupdated: '2026-07-04'\n"
        "---\n# X\n\n## Summary\n\nBody.\n",
        encoding="utf-8",
    )


def test_validate_warns_on_lens_origin_without_lens_views(tmp_path) -> None:
    root = tmp_path
    seed_project(root)
    _write_entity(root, "0001-x.md", "origins:\n  - type: assistant\n    ref: explore-ideas-mechanism\n")
    result = CliRunner().invoke(main, ["validate", "--project-root", str(root)])
    assert "but no lens_views" in result.output


def test_validate_does_not_warn_with_lens_views_populated(tmp_path) -> None:
    root = tmp_path
    seed_project(root)
    _write_entity(
        root,
        "0002-y.md",
        "origins:\n"
        "  - type: assistant\n"
        "    ref: explore-ideas-mechanism\n"
        "lens_views:\n"
        "  - lens: mechanism\n"
        "    rationale: m\n"
        "    origin_ref: explore-ideas-mechanism\n",
    )
    result = CliRunner().invoke(main, ["validate", "--project-root", str(root)])
    assert result.exit_code == 0, result.output
    assert "but no lens_views" not in result.output


def test_validate_does_not_warn_on_non_lens_origin(tmp_path) -> None:
    root = tmp_path
    seed_project(root)
    _write_entity(
        root,
        "0003-z.md",
        "origins:\n"
        "  - type: assistant\n"
        "    ref: explore-ideas-frobnicate\n",
    )
    result = CliRunner().invoke(main, ["validate", "--project-root", str(root)])
    assert result.exit_code == 0, result.output
    assert "but no lens_views" not in result.output
