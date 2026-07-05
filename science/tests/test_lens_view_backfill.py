# science/tests/test_lens_view_backfill.py  (Task 7 appends to this file)
from __future__ import annotations

from datetime import date

from click.testing import CliRunner

from _fixtures.entity_helpers import seed_project
from science_tool.cli import main
from science_tool.explore_ideas import backfill_lens_views


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


_APPLIED_REPORT = """\
---
id: explore-demo
---

```yaml
candidate_id: cand-hspc
proposed_kind: question
title: HSPC imprinting
lens: mechanism
rationale: mechanism framing
decision: applied
applied_as: question:0001-hspc
applied_at: '2026-07-04'
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
```
"""


def test_backfill_adds_views_for_lens_origins(tmp_path) -> None:
    root = tmp_path
    seed_project(root)
    (root / "entities" / "meta" / "explorations").mkdir(parents=True, exist_ok=True)
    (root / "entities" / "meta" / "explorations" / "explore-demo.md").write_text(
        _APPLIED_REPORT, encoding="utf-8"
    )
    _write_entity(
        root, "0001-hspc.md",
        "origins:\n"
        "  - type: assistant\n    ref: explore-ideas-mechanism\n"
        "  - type: assistant\n    ref: explore-ideas-analogy\n    independent: true\n",
    )
    # rename id inside the file to match applied_as
    p = root / "entities" / "questions" / "0001-hspc.md"
    p.write_text(p.read_text().replace("question:0001-x", "question:0001-hspc"), encoding="utf-8")

    backfill_date = date(2026, 7, 5)
    touched = backfill_lens_views(root, "explore-demo", backfill_date)
    assert ("question:0001-hspc", 2) in touched

    from science_model.frontmatter import parse_frontmatter
    fm, _ = parse_frontmatter(p)
    lenses = {v["lens"] for v in fm["lens_views"]}
    assert lenses == {"mechanism", "analogy"}
    assert fm["updated"] == backfill_date.isoformat()

    # Idempotency: re-running against the now-populated entity must be a true
    # no-op, touching neither the returned set nor the file's bytes.
    after_first = p.read_bytes()
    touched_again = backfill_lens_views(root, "explore-demo", backfill_date)
    assert touched_again == []
    assert p.read_bytes() == after_first
