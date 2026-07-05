# science/tests/test_lens_view_backfill.py  (Task 7 appends to this file)
from __future__ import annotations

from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project
from science_tool.cli import main


def _write_entity(root, name, extra_fm) -> None:
    (root / "entities" / "questions").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "questions" / name).write_text(
        "---\n"
        "id: question:0001-x\nkind: question\ntitle: X\nstatus: open\nproject: testproj\n"
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
    assert "no lens_views" in result.output or "lens_views" in result.output
