# science/tests/test_entity_import.py
"""Import a loose markdown file as a canonical entity: propose, validate, apply."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.entity_import import EntityImportError, plan_import


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _loose(root: Path, rel: str, text: str = "# A Thing\n\nbody\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_proposes_id_and_destination(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _loose(root, "doc/plans/2026-01-01-a-thing.md")

    plan = plan_import(root, root / "doc/plans/2026-01-01-a-thing.md", kind="plan", title="A Thing")

    assert plan.entity_id == "plan:0001-a-thing"
    assert plan.number == 1
    assert plan.dest_rel == "entities/plans/0001-a-thing.md"
    assert plan.source_rel == "doc/plans/2026-01-01-a-thing.md"


def test_planner_creates_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    before = source.read_bytes()

    plan = plan_import(root, source, kind="plan", title="T1")

    assert source.read_bytes() == before
    assert not (root / plan.dest_rel).exists()
    assert list((root / "entities" / "plans").iterdir()) == [], "planner touched the entity tree"


def test_planner_is_idempotent(tmp_path: Path) -> None:
    """Two previews must propose the SAME id -- v1's reserve_entity would give 0001 then 0002."""
    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")

    first = plan_import(root, source, kind="plan", title="T1")
    second = plan_import(root, source, kind="plan", title="T1")

    assert first.entity_id == second.entity_id


def test_id_proposal_is_archive_aware(tmp_path: Path) -> None:
    root = _project(tmp_path)
    archive_dir = root / "entities" / "_archive" / "plans"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "0001-gone.md").write_text("---\nid: plan:0001-gone\n---\n", encoding="utf-8")
    (root / "entities" / "_archive" / "archive-index.jsonl").write_text(
        '{"op": "archive", "id": "plan:0001-gone", "kind": "plan", '
        '"original_path": "entities/plans/0001-gone.md"}\n',
        encoding="utf-8",
    )
    _loose(root, "doc/plans/x.md")

    plan = plan_import(root, root / "doc/plans/x.md", kind="plan", title="Gone")

    assert plan.number == 2
    assert plan.entity_id == "plan:0002-gone"


def test_defaults_title_from_first_heading(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _loose(root, "doc/plans/x.md", "# Curatorial Lens Migration\n\nbody\n")

    plan = plan_import(root, root / "doc/plans/x.md", kind="plan")

    assert plan.title == "Curatorial Lens Migration"


def test_missing_heading_and_no_title_fails_early(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _loose(root, "doc/plans/x.md", "no heading here\n")

    with pytest.raises(EntityImportError, match="title"):
        plan_import(root, root / "doc/plans/x.md", kind="plan")


def test_rendered_text_carries_the_canonical_fields(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _loose(root, "doc/plans/x.md", "# A Thing\n\noriginal body\n")

    plan = plan_import(root, root / "doc/plans/x.md", kind="plan", title="A Thing")

    for key in ("kind", "title", "status", "created", "updated", "id"):
        assert key in plan.frontmatter, f"missing {key}"
    assert plan.status == "active"
    assert "original body" in plan.rendered_text


def test_invalid_status_fails_early(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _loose(root, "doc/plans/x.md")

    with pytest.raises(EntityImportError, match="status"):
        plan_import(root, root / "doc/plans/x.md", kind="plan", title="T", status="proposed")


def test_source_with_existing_frontmatter_is_refused(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _loose(root, "doc/plans/x.md", "---\nid: spec:2026-01-01-x\ntype: spec\n---\n\nbody\n")

    with pytest.raises(EntityImportError, match="frontmatter"):
        plan_import(root, root / "doc/plans/x.md", kind="plan", title="T")


def test_missing_source_fails_early(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(EntityImportError, match="not found"):
        plan_import(root, root / "doc/plans/ghost.md", kind="plan", title="T")


def test_plan_reports_inbound_reference_hits(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _loose(root, "doc/plans/x.md")
    referrer = root / "entities" / "plans" / "0001-ref.md"
    referrer.write_text(
        "---\nid: plan:0001-ref\nkind: plan\ntitle: Ref\nstatus: active\n"
        "related:\n- doc/plans/x.md\n---\n\nSee [it](../../doc/plans/x.md).\n",
        encoding="utf-8",
    )

    plan = plan_import(root, root / "doc/plans/x.md", kind="plan", title="T1")

    surfaces = {h.surface for h in plan.ref_report.hits}
    assert "related" in surfaces
    assert "markdown-link" in surfaces


def test_plan_rebases_outbound_links(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _loose(root, "doc/plans/x.md", "# T\n\nSee [sib](./sibling.md).\n")
    _loose(root, "doc/plans/sibling.md", "# Sib\n")

    plan = plan_import(root, root / "doc/plans/x.md", kind="plan", title="T1")

    assert "../../doc/plans/sibling.md" in plan.rendered_text


def test_plan_import_unknown_kind_raises_entity_import_error(tmp_path: Path) -> None:
    """A bad --kind must surface as EntityImportError, not a raw KeyError/EntityCommandError."""
    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    with pytest.raises(EntityImportError):
        plan_import(root, source, kind="not-a-real-kind", title="A Thing")


def test_plan_import_unsluggable_title_raises_entity_import_error(tmp_path: Path) -> None:
    """A 1-char/unsluggable title with no --slug must surface as EntityImportError."""
    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    with pytest.raises(EntityImportError):
        plan_import(root, source, kind="plan", title="T")
