# science/tests/test_entity_import.py
"""Import a loose markdown file as a canonical entity: propose, validate, apply."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from science_tool.entity_import import (
    EntityImportError,
    ImportMember,
    PlannedMember,
    _plan_member,
    apply_import,
    plan_import,
)


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _loose(root: Path, rel: str, text: str = "# A Thing\n\nbody\n") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _write_md(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_plan_member_from_cached_bytes(tmp_path: Path) -> None:
    root = _project(tmp_path)
    text = "# A Thing\n\nbody\n"

    planned = _plan_member(root, "doc/plans/x.md", text, kind="plan", number=7)

    assert isinstance(planned, PlannedMember)
    member = planned.member
    assert member.entity_id == "plan:0007-a-thing"
    assert member.number == 7
    assert member.dest_rel == "entities/plans/0007-a-thing.md"
    assert member.source_rel == "doc/plans/x.md"
    assert "id: plan:0007-a-thing" in member.rendered_text
    assert "kind" not in ImportMember.model_fields


def test_plan_member_honors_title_and_slug(tmp_path: Path) -> None:
    root = _project(tmp_path)

    planned = _plan_member(
        root,
        "doc/plans/x.md",
        "# Ignored\n\nbody\n",
        kind="plan",
        number=1,
        title="Custom Title",
        slug="custom-slug",
    )

    assert planned.member.title == "Custom Title"
    assert planned.member.entity_id == "plan:0001-custom-slug"


def test_plan_member_rejects_document_with_frontmatter(tmp_path: Path) -> None:
    root = _project(tmp_path)

    with pytest.raises(EntityImportError):
        _plan_member(
            root,
            "doc/plans/x.md",
            "---\nid: x\n---\n# T\n",
            kind="plan",
            number=1,
        )


def test_single_apply_translates_unknown_kind_in_tampered_plan(tmp_path):
    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    plan = plan_import(root, source, kind="plan")
    plan.kind = "notarealkind"
    plan.entity_id = "notarealkind:0001-a-thing"
    with pytest.raises(EntityImportError):
        apply_import(root, plan)


def test_single_apply_rejects_rendered_kind_tamper(tmp_path):
    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    plan = plan_import(root, source, kind="plan")
    plan.rendered_text = plan.rendered_text.replace("kind: plan", "kind: question")
    with pytest.raises(EntityImportError):
        apply_import(root, plan)


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


def test_apply_moves_file_and_writes_frontmatter(tmp_path: Path) -> None:
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\noriginal body\n")
    plan = plan_import(root, source, kind="plan", title="A Thing")

    report = apply_import(root, plan)

    assert not source.exists()
    dest = root / plan.dest_rel
    assert dest.read_text(encoding="utf-8") == plan.rendered_text, "apply wrote something the preview did not show"
    assert report["id"] == "plan:0001-a-thing"


def test_apply_claims_the_previewed_number(tmp_path: Path) -> None:
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    plan = plan_import(root, source, kind="plan", title="T1")

    apply_import(root, plan)

    assert (root / "entities" / "plans" / "0001-t1.md").exists()


def test_apply_refuses_when_the_previewed_number_was_taken(tmp_path: Path) -> None:
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    plan = plan_import(root, source, kind="plan", title="T1")
    (root / "entities" / "plans" / "0001-squatter.md").write_text("---\nid: plan:0001-squatter\n---\n", encoding="utf-8")

    with pytest.raises(Exception, match="0001"):
        apply_import(root, plan)

    assert source.exists(), "source was consumed by a refused apply"


def test_apply_rewrites_inbound_refs(tmp_path: Path) -> None:
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    referrer = root / "entities" / "plans" / "0001-ref.md"
    referrer.write_text(
        "---\nid: plan:0001-ref\nkind: plan\ntitle: Ref\nstatus: active\nrelated:\n- doc/plans/x.md\n---\n\nbody\n",
        encoding="utf-8",
    )
    plan = plan_import(root, source, kind="plan", title="T1")

    apply_import(root, plan)

    text = referrer.read_text(encoding="utf-8")
    assert plan.entity_id in text
    assert "doc/plans/x.md" not in text


def test_apply_restores_every_referrer_on_a_mid_rewrite_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The defect v1's monkeypatch could not see: partial failure INSIDE the rewrite."""
    from science_tool import entity_import as mod
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    source_bytes = source.read_bytes()

    referrers = {}
    for n in (1, 2, 3):
        path = root / "entities" / "plans" / f"000{n}-ref.md"
        path.write_text(
            f"---\nid: plan:000{n}-ref\nkind: plan\ntitle: R{n}\nstatus: active\n"
            "related:\n- doc/plans/x.md\n---\n\nbody\n",
            encoding="utf-8",
        )
        referrers[path] = path.read_bytes()

    plan = plan_import(root, source, kind="plan", title="T1")

    real = mod.apply_reference_rewrite
    calls = {"n": 0}

    def _partial(*args: object, **kwargs: object) -> object:
        calls["n"] += 1
        real(*args, **kwargs)  # let the real rewrite mutate referrers
        raise RuntimeError("exploded after writing some referrers")

    monkeypatch.setattr(mod, "apply_reference_rewrite", _partial)

    with pytest.raises(RuntimeError, match="exploded"):
        apply_import(root, plan)

    assert source.exists() and source.read_bytes() == source_bytes
    assert not (root / plan.dest_rel).exists()
    for path, before in referrers.items():
        assert path.read_bytes() == before, f"{path.name} was left modified after rollback"


def test_apply_leaves_no_reservation_sentinel(tmp_path: Path) -> None:
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    plan = plan_import(root, source, kind="plan", title="T1")

    apply_import(root, plan)

    strays = [p.name for p in (root / "entities" / "plans").iterdir() if p.name.startswith(".")]
    assert strays == [], f"reservation sentinel left behind: {strays}"


def test_rollback_leaves_no_sentinel_either(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool import entity_import as mod
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    plan = plan_import(root, source, kind="plan", title="T1")

    monkeypatch.setattr(mod, "apply_reference_rewrite", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        apply_import(root, plan)

    strays = [p.name for p in (root / "entities" / "plans").iterdir() if p.name.startswith(".")]
    assert strays == []


# ---- rollback restores the TREE, not just the files ----------------------


def _tree(root: Path) -> dict[str, tuple]:
    """Every path under root as (kind, mode, content).

    Directories are entries, not omissions -- a file-only comparison cannot see
    the empty directory a failed import leaves behind. Mode and symlink target
    are entries for the same reason one level down: atomic_write_text writes a
    temp file and os.replace()s it, so it takes the temp file's mode and turns a
    symlink into a regular file. A bytes-only comparison calls both of those a
    successful rollback.
    """
    out: dict[str, tuple] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            out[rel] = ("symlink", path.lstat().st_mode & 0o777, os.readlink(path))
        elif path.is_dir():
            out[rel] = ("dir", path.stat().st_mode & 0o777, None)
        else:
            out[rel] = ("file", path.stat().st_mode & 0o777, path.read_bytes())
    return out


def test_rollback_removes_a_kind_directory_it_created(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every other fixture precreates entities/plans, so none of them can see this."""
    from science_tool import entity_import as mod
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    import shutil

    shutil.rmtree(root / "entities" / "plans")
    assert not (root / "entities" / "plans").exists(), "fixture must not precreate the kind dir"

    source = _loose(root, "doc/plans/x.md")
    plan = plan_import(root, source, kind="plan", title="T1")
    before = _tree(root)

    monkeypatch.setattr(mod, "apply_reference_rewrite", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    with pytest.raises(RuntimeError):
        apply_import(root, plan)

    assert _tree(root) == before, "rollback left the tree changed"
    assert not (root / "entities" / "plans").exists(), "empty kind directory survived rollback"


def test_rollback_restores_whole_tree_after_partial_rewrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool import entity_import as mod
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    for n in (1, 2, 3):
        (root / "entities" / "plans" / f"000{n}-ref.md").write_text(
            f"---\nid: plan:000{n}-ref\nkind: plan\ntitle: R{n}\nstatus: active\n"
            "related:\n- doc/plans/x.md\n---\n\nbody\n",
            encoding="utf-8",
        )
    plan = plan_import(root, source, kind="plan", title="T1")
    before = _tree(root)

    real = mod.apply_reference_rewrite

    def _partial(*args: object, **kwargs: object) -> object:
        real(*args, **kwargs)
        raise RuntimeError("exploded after writing some referrers")

    monkeypatch.setattr(mod, "apply_reference_rewrite", _partial)

    with pytest.raises(RuntimeError, match="exploded"):
        apply_import(root, plan)

    assert _tree(root) == before


# ---- the post-move audit (design section 2.2) ----------------------------


def test_audit_is_clean_after_a_successful_import(tmp_path: Path) -> None:
    from science_tool.entity_import import apply_import, audit_moved_references

    root = _project(tmp_path)
    _write_md(root, "doc/plans/sibling.md", "# Sibling\n\n## Some Section\n\nbody\n")
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\nSee [sib](./sibling.md#some-section).\n")
    plan = plan_import(root, source, kind="plan", title="A Thing")

    apply_import(root, plan)

    assert audit_moved_references(root, plan.dest_rel) == []


def test_audit_reports_an_outbound_link_whose_target_is_missing(tmp_path: Path) -> None:
    from science_tool.entity_import import audit_moved_references

    root = _project(tmp_path)
    _write_md(root, "entities/plans/0001-a.md", "---\nid: plan:0001-a\nkind: plan\n---\n\n[gone](./nope.md)\n")

    problems = audit_moved_references(root, "entities/plans/0001-a.md")

    assert any("nope.md" in p for p in problems)


def test_audit_reports_a_missing_anchor(tmp_path: Path) -> None:
    from science_tool.entity_import import audit_moved_references

    root = _project(tmp_path)
    _write_md(root, "entities/plans/0002-t.md", "# Target\n\n## Real Section\n")
    _write_md(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\n---\n\n[x](./0002-t.md#section-gone)\n",
    )

    problems = audit_moved_references(root, "entities/plans/0001-a.md")

    assert any("section-gone" in p for p in problems)
    assert audit_moved_references(root, "entities/plans/0002-t.md") == []


def test_import_rolls_back_when_the_audit_fails(tmp_path: Path) -> None:
    """A move that breaks a link must not be committed and reported as success."""
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\n[dangling](./never-existed.md)\n")
    plan = plan_import(root, source, kind="plan", title="A Thing")
    before = _tree(root)

    with pytest.raises(Exception, match="audit"):
        apply_import(root, plan)

    assert _tree(root) == before, "a failed audit must roll the move back"


def test_rollback_restores_a_non_default_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """atomic_write_text takes the TEMP file's mode; a bytes-only restore keeps the change."""
    from science_tool import entity_import as mod
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    referrer = root / "entities" / "plans" / "0001-ref.md"
    referrer.write_text(
        "---\nid: plan:0001-ref\nkind: plan\ntitle: Ref\nstatus: active\nrelated:\n- doc/plans/x.md\n---\n\nbody\n",
        encoding="utf-8",
    )
    referrer.chmod(0o640)
    plan = plan_import(root, source, kind="plan", title="T1")
    before = _tree(root)

    real = mod.apply_reference_rewrite

    def _partial(*args: object, **kwargs: object) -> object:
        real(*args, **kwargs)
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "apply_reference_rewrite", _partial)

    with pytest.raises(RuntimeError):
        apply_import(root, plan)

    assert referrer.stat().st_mode & 0o777 == 0o640, "rollback lost the file mode"
    assert _tree(root) == before


def test_rollback_restores_a_symlink_as_a_symlink(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """os.replace turns a symlink into a regular file; restoring bytes hides that."""
    from science_tool import entity_import as mod
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    # The link target carries a suffix outside TEXT_SUFFIXES (`.dat`, not `.md`) and
    # lives outside entities/ (a MarkdownAdapter scan root): a scannable, entities/-
    # resident target would give the corpus loader two owners of one id (the symlink
    # and its target both decode to the same frontmatter) and give the reference
    # scanner two referrers of one file (writing the target changes what the symlink
    # reads back, corrupting the OTHER edit's preimage) -- neither is the rollback
    # behavior this test targets. Only the symlink itself is scanned or rewritten.
    real_target = root / "doc" / "other" / "0002-real.dat"
    real_target.parent.mkdir(parents=True, exist_ok=True)
    real_target.write_text(
        "---\nid: plan:0002-real\nkind: plan\ntitle: Real\nstatus: active\nrelated:\n- doc/plans/x.md\n---\n\nbody\n",
        encoding="utf-8",
    )
    link = root / "entities" / "plans" / "0001-link.md"
    link.symlink_to("../../doc/other/0002-real.dat")
    plan = plan_import(root, source, kind="plan", title="T1")
    before = _tree(root)

    real = mod.apply_reference_rewrite

    def _partial(*args: object, **kwargs: object) -> object:
        real(*args, **kwargs)
        raise RuntimeError("boom")

    monkeypatch.setattr(mod, "apply_reference_rewrite", _partial)

    with pytest.raises(RuntimeError):
        apply_import(root, plan)

    assert link.is_symlink(), "rollback replaced a symlink with a regular file"
    assert _tree(root) == before


# ---- the audit does not mistake examples for links -----------------------


def test_audit_ignores_links_inside_code_fences(tmp_path: Path) -> None:
    """73 unresolvable fenced links live in the consumer corpus.

    Without this, the audit fails on every import -- including the import of the
    very plan document that carries ./nope.md as fixture data.
    """
    from science_tool.entity_import import audit_moved_references

    root = _project(tmp_path)
    _write_md(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\n---\n\n"
        "Prose is fine.\n\n```python\nlink = \"[x](./never-existed.md)\"\n```\n",
    )

    assert audit_moved_references(root, "entities/plans/0001-a.md") == []


def test_audit_reports_a_structured_frontmatter_ref_to_a_missing_path(tmp_path: Path) -> None:
    """The claim is a link/reference audit; frontmatter refs are references."""
    from science_tool.entity_import import audit_moved_references

    root = _project(tmp_path)
    _write_md(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\nrelated:\n- ./gone.md\n---\n\nbody\n",
    )

    problems = audit_moved_references(root, "entities/plans/0001-a.md")

    assert any("gone.md" in p and "related" in p for p in problems)


def test_audit_does_not_flag_canonical_ids_as_missing_paths(tmp_path: Path) -> None:
    """Ids are resolved by the entity graph; re-resolving them here would be a weaker copy."""
    from science_tool.entity_import import audit_moved_references

    root = _project(tmp_path)
    _write_md(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\nrelated:\n- plan:0099-absent\n---\n\nbody\n",
    )

    assert audit_moved_references(root, "entities/plans/0001-a.md") == []


def test_audit_covers_tier_a_archival_moves_too(tmp_path: Path) -> None:
    """Design section 2.2 says EVERY move, and archival is Plan 3's caller."""
    from science_tool.entity_import import audit_moved_references

    root = _project(tmp_path)
    _write_md(root, "entities/plans/0001-live.md", "---\nid: plan:0001-live\nkind: plan\n---\n\n[x](./0002-gone.md)\n")
    archived = root / "entities" / "_archive" / "plans"
    archived.mkdir(parents=True, exist_ok=True)
    (archived / "0002-gone.md").write_text("# Gone\n", encoding="utf-8")

    problems = audit_moved_references(root, "entities/_archive/plans/0002-gone.md")

    assert any("0002-gone.md" in p and "0001-live.md" in p for p in problems), (
        "archival left an inbound link pointing at the vacated path"
    )


# ---- content integrity of the source, and honest rollback under concurrency ----


def test_apply_refuses_a_source_edited_after_the_preview(tmp_path: Path) -> None:
    """A plan's rendered_text is fixed; a newer source must not be silently lost."""
    from science_tool.entity_import import EntityImportError, apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\noriginal body\n")
    plan = plan_import(root, source, kind="plan", title="A Thing")

    edited = "# A Thing\n\nEDITED AFTER PREVIEW\n"
    source.write_text(edited, encoding="utf-8")  # the operator kept working

    with pytest.raises(EntityImportError, match="changed since the preview"):
        apply_import(root, plan)

    assert source.read_text(encoding="utf-8") == edited, "the newer source was clobbered"
    assert not (root / plan.dest_rel).exists(), "a rejected import still created the destination"


def test_apply_does_not_restore_a_referrer_a_concurrent_writer_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rollback restores what THIS transaction wrote, never a bystander's edit.

    Two referrers point at the source. We let the first rewrite land, then have a
    concurrent writer edit the second referrer before its own write. Its per-write
    recheck fails and aborts. The second referrer must keep the concurrent edit --
    this transaction never wrote it -- while the first is rolled back.
    """
    import science_tool.reference_rewrite as rr
    from science_tool.reference_rewrite import ReferenceDriftError
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\nbody\n")
    a = _write_md(
        root, "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\ntitle: A\n---\n\nsee [x](../../doc/plans/x.md)\n",
    )
    b = _write_md(
        root, "entities/plans/0002-b.md",
        "---\nid: plan:0002-b\nkind: plan\ntitle: B\n---\n\nsee [x](../../doc/plans/x.md)\n",
    )
    plan = plan_import(root, source, kind="plan", title="A Thing")
    a_before = a.read_text(encoding="utf-8")
    concurrent = "---\nid: plan:0002-b\nkind: plan\n---\n\nA CONCURRENT EDIT\n"

    real = rr._atomic_replace_text

    def _tamper(path: Path, text: str) -> None:
        real(path, text)
        if path.name == "0001-a.md":  # after our first write, a bystander edits b
            b.write_text(concurrent, encoding="utf-8")

    monkeypatch.setattr(rr, "_atomic_replace_text", _tamper)

    with pytest.raises(ReferenceDriftError):
        apply_import(root, plan)

    assert b.read_text(encoding="utf-8") == concurrent, "rollback erased the concurrent writer's edit"
    assert a.read_text(encoding="utf-8") == a_before, "our own write was not rolled back"
    assert source.exists(), "source not restored after a failed apply"
    assert not (root / plan.dest_rel).exists(), "destination not removed after a failed apply"


# ---- a persisted plan is untrusted input to a filesystem mutation --------


def test_apply_rejects_a_source_path_that_escapes_the_project(tmp_path: Path) -> None:
    """A validly-typed plan must not be able to unlink a file outside the project.

    `Path(root) / "/etc/x"` discards the root and `Path(root) / "../x"` escapes it,
    so an absolute or traversing source_rel would otherwise reach apply's unlink.
    """
    from science_tool.entity_import import EntityImportError, apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\nbody\n")
    good = plan_import(root, source, kind="plan", title="A Thing")

    for evil_rel in ("/etc/passwd", "../../etc/passwd"):
        tampered = good.model_copy(update={"source_rel": evil_rel})
        with pytest.raises(EntityImportError, match="project-relative|escapes"):
            apply_import(root, tampered)
    assert source.exists(), "a rejected plan still touched the real source"


def test_apply_rejects_a_non_canonical_destination(tmp_path: Path) -> None:
    """dest_rel is fully determined by (kind, number, slug); any other value is tampering."""
    from science_tool.entity_import import EntityImportError, apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\nbody\n")
    good = plan_import(root, source, kind="plan", title="A Thing")

    tampered = good.model_copy(update={"dest_rel": "entities/plans/0001-somewhere-else.md"})
    with pytest.raises(EntityImportError, match="canonical"):
        apply_import(root, tampered)
    assert source.exists()
    assert not (root / "entities" / "plans" / "0001-somewhere-else.md").exists()


def test_rollback_does_not_delete_a_destination_a_concurrent_writer_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A claim that loses the number race must not let rollback delete the winner's file."""
    from science_tool import entity_import as mod
    from science_tool.entity_import import EntityImportError, apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\nbody\n")
    plan = plan_import(root, source, kind="plan", title="A Thing")
    dest = root / plan.dest_rel

    def _claim_loses_the_race(*_args: object, **_kwargs: object) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("OTHER WRITER'S ENTITY\n", encoding="utf-8")  # they won the number
        raise EntityImportError("number already claimed")

    monkeypatch.setattr(mod, "claim_number_in_dir", _claim_loses_the_race)

    with pytest.raises(EntityImportError):
        apply_import(root, plan)

    assert dest.read_text(encoding="utf-8") == "OTHER WRITER'S ENTITY\n", "rollback deleted a bystander's entity"
    assert source.exists(), "source consumed despite a failed claim"


def test_rollback_does_not_revert_a_concurrent_source_edit_on_claim_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If claim fails after a bystander edits the source, that edit must survive."""
    from science_tool import entity_import as mod
    from science_tool.entity_import import EntityImportError, apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md", "# A Thing\n\nbody\n")
    plan = plan_import(root, source, kind="plan", title="A Thing")
    edited = "# A Thing\n\nEDITED BY ANOTHER WRITER\n"

    def _claim_edits_source_then_fails(*_args: object, **_kwargs: object) -> None:
        source.write_text(edited, encoding="utf-8")
        raise EntityImportError("number already claimed")

    monkeypatch.setattr(mod, "claim_number_in_dir", _claim_edits_source_then_fails)

    with pytest.raises(EntityImportError):
        apply_import(root, plan)

    assert source.read_text(encoding="utf-8") == edited, "rollback reverted a concurrent source edit"


def test_self_referential_source_does_not_drift(tmp_path: Path) -> None:
    """A loose doc that mentions its own path in prose must still import.

    Its self-mention is scanned neither inbound (excluded) nor as a ManualHit, so
    the preview and the post-unlink replay agree.
    """
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(
        root, "doc/plans/x.md", "# A Thing\n\nThis document lives at doc/plans/x.md today.\n"
    )
    plan = plan_import(root, source, kind="plan", title="A Thing")

    report = apply_import(root, plan)  # must not raise ReferenceDriftError

    assert report["id"] == "plan:0001-a-thing"
    assert not source.exists()


def test_apply_does_not_delete_a_concurrent_writers_reservation_sentinel(tmp_path: Path) -> None:
    """Lost number race: our claim fails because another writer holds the sentinel; that sentinel must survive."""
    from science_tool.entities import EntityCommandError
    from science_tool.entity_import import apply_import

    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    plan = plan_import(root, source, kind="plan", title="A Thing")

    # Another writer already holds the reservation for this exact number.
    sentinel = root / "entities" / "plans" / f".{plan.number:04d}.reserving"
    sentinel.parent.mkdir(parents=True, exist_ok=True)
    sentinel.write_text("", encoding="utf-8")

    with pytest.raises(EntityCommandError):
        apply_import(root, plan)

    assert sentinel.exists(), "apply deleted the concurrent writer's reservation sentinel"
    assert not (root / plan.dest_rel).exists(), "our transaction created a dest despite losing the race"
    assert source.exists(), "our source was unlinked despite the claim failing"


def test_plan_import_non_utf8_source_raises_entity_import_error(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = root / "doc" / "plans" / "bad.md"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"\xff\xfe\x00\x00 not utf8")
    with pytest.raises(EntityImportError):
        plan_import(root, source, kind="plan", title="A Thing")


def test_plan_import_malformed_frontmatter_raises_entity_import_error(tmp_path: Path) -> None:
    root = _project(tmp_path)
    source = _loose(root, "doc/plans/bad-fm.md", "---\n : : bad yaml : :\n- [unbalanced\n---\n\nbody\n")
    with pytest.raises(EntityImportError):
        plan_import(root, source, kind="plan", title="A Thing")
