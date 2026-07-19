# science/tests/test_reference_rewrite.py
"""Substituting cross-reference rewriter (repoint, not drop), both surfaces."""
from __future__ import annotations

from collections.abc import Mapping  # noqa: F401  (documentation of the new param type)
from pathlib import Path

import pytest

from science_tool.reference_rewrite import (
    ReferenceDriftError,
    RewriteReport,
    apply_reference_rewrite,
    plan_reference_rewrite,
    rewrite_outbound_links,
)


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    return tmp_path


def _corpus(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\nknowledge_profiles: {local: local}\n", encoding="utf-8")
    return tmp_path


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _apply(root: Path, **subs) -> RewriteReport:
    """Plan, then apply the frozen plan. Apply never re-derives the edit set."""
    plan = plan_reference_rewrite(root, **subs)
    return apply_reference_rewrite(root, plan)


def test_override_drives_enumeration_for_absent_source(tmp_path):
    """An override is scanned even when its file no longer exists on disk."""
    root = _corpus(tmp_path)
    # No file at doc/loose.md exists; the override supplies its bytes. Its body
    # links to another loose doc's path, which we are substituting.
    report = plan_reference_rewrite(
        root,
        id_substitutions={"doc/other.md": "plan:0002-other"},
        path_substitutions={"doc/other.md": "entities/plans/0002-other.md"},
        source_overrides={"doc/loose.md": "# L\n\nsee [other](other.md)\n"},
    )
    # The override was examined: its link to other.md is reported (a hit),
    # proving enumeration used the virtual entry, not the (absent) disk file.
    assert any(h.rel_path == "doc/loose.md" for h in report.hits)


def test_override_examined_once_when_also_on_disk(tmp_path):
    """A key present both on disk and as an override is scanned once, from override bytes."""
    root = _corpus(tmp_path)
    (root / "doc").mkdir()
    (root / "doc/loose.md").write_text("# L\n\nno links here\n", encoding="utf-8")
    report = plan_reference_rewrite(
        root,
        id_substitutions={"doc/other.md": "plan:0002-other"},
        path_substitutions={"doc/other.md": "entities/plans/0002-other.md"},
        source_overrides={"doc/loose.md": "# L\n\nsee [other](other.md)\n"},
    )
    hits_for_loose = [h for h in report.hits if h.rel_path == "doc/loose.md"]
    assert len(hits_for_loose) == 1  # examined once, and from the override bytes (which DO link)


def test_exclude_wins_over_override(tmp_path):
    """An excluded path is not scanned even if an override names it."""
    root = _corpus(tmp_path)
    report = plan_reference_rewrite(
        root,
        id_substitutions={"doc/other.md": "plan:0002-other"},
        path_substitutions={"doc/other.md": "entities/plans/0002-other.md"},
        exclude=frozenset({(root / "doc/loose.md").resolve()}),
        source_overrides={"doc/loose.md": "# L\n\nsee [other](other.md)\n"},
    )
    assert not any(h.rel_path == "doc/loose.md" for h in report.hits)


def test_override_examines_oversize_file_the_disk_scan_would_drop(tmp_path):
    """A file too big for the disk size filter is still examined via its override."""
    from science_tool.text_scan import MAX_SCANNABLE_BYTES
    root = _corpus(tmp_path)
    (root / "doc").mkdir()
    # On-disk file exceeds the scan-size limit, so iter_scannable_files drops it.
    big = "# L\n\n" + ("x " * MAX_SCANNABLE_BYTES) + "\nsee [other](other.md)\n"
    (root / "doc/loose.md").write_text(big, encoding="utf-8")
    assert (root / "doc/loose.md").stat().st_size > MAX_SCANNABLE_BYTES
    # The override supplies a small text with the link; enumeration must include it.
    report = plan_reference_rewrite(
        root,
        id_substitutions={"doc/other.md": "plan:0002-other"},
        path_substitutions={"doc/other.md": "entities/plans/0002-other.md"},
        source_overrides={"doc/loose.md": "# L\n\nsee [other](other.md)\n"},
    )
    assert any(h.rel_path == "doc/loose.md" for h in report.hits)


# ---- frontmatter surface -------------------------------------------------


def test_rewrites_flat_frontmatter_list_key(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\nrelated:\n- doc/plans/old.md\n---\n\nbody\n",
    )

    report = _apply(
        root, id_substitutions={"doc/plans/old.md": "plan:0042-new"}, path_substitutions={}
    )

    assert [(h.surface, h.old, h.new) for h in report.hits] == [("related", "doc/plans/old.md", "plan:0042-new")]
    assert "- plan:0042-new" in path.read_text(encoding="utf-8")


def test_rewrites_scalar_frontmatter_key(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\nsuperseded_by: doc/plans/old.md\n---\n\nbody\n",
    )

    _apply(root, id_substitutions={"doc/plans/old.md": "plan:0042-new"}, path_substitutions={})

    assert "superseded_by: plan:0042-new" in path.read_text(encoding="utf-8")


def test_rewrites_nested_relations_target(tmp_path: Path) -> None:
    """_remove_frontmatter_ref ignores relations[].target; this must not."""
    root = _project(tmp_path)
    path = _write(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\n"
        "relations:\n- predicate: sci:consolidates\n  target: doc/plans/old.md\n---\n\nbody\n",
    )

    report = _apply(
        root, id_substitutions={"doc/plans/old.md": "plan:0042-new"}, path_substitutions={}
    )

    assert [h.surface for h in report.hits] == ["relations[].target"]
    assert "target: plan:0042-new" in path.read_text(encoding="utf-8")


def test_substitutes_rather_than_drops(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\nrelated:\n- doc/plans/old.md\n- task:t001\n---\n\nbody\n",
    )

    _apply(root, id_substitutions={"doc/plans/old.md": "plan:0042-new"}, path_substitutions={})

    text = path.read_text(encoding="utf-8")
    assert "- plan:0042-new" in text
    assert "- task:t001" in text, "unrelated ref was disturbed"


# ---- markdown-link surface ----------------------------------------------


def test_rewrites_referrer_relative_markdown_link(tmp_path: Path) -> None:
    """Bare targets resolve against the REFERRER's directory, never the repo root.

    v2's version of this test wrote the link `doc/plans/old.md` inside
    `doc/notes.md` and expected repo-root resolution -- which `_resolve_link`
    never does; it would have produced `doc/doc/plans/old.md` and failed. The
    test was wrong, not the resolver. Measured against the consumer corpus:

        dotted (./ ../):                    85
        bare, resolves referrer-relative:   11
        bare, resolves ONLY root-relative:   0

    Root-relative-without-a-slash is NOT a convention here, so it is not
    supported. `/doc/plans/old.md` (leading slash) is declined as non-local.
    Bare paths in prose that resolve to nothing are ManualHits, not silent
    rewrites -- which is how the .py/.ts references surface.
    """
    root = _project(tmp_path)
    path = _write(root, "doc/notes.md", "See [the plan](plans/old.md) for detail.\n")

    report = _apply(root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"})

    assert [h.surface for h in report.hits] == ["markdown-link"]
    assert "(../entities/plans/0042-new.md)" in path.read_text(encoding="utf-8")


def test_root_relative_bare_link_is_not_silently_reinterpreted(tmp_path: Path) -> None:
    """The convention the corpus does not use must not be invented here."""
    root = _project(tmp_path)
    path = _write(root, "doc/notes.md", "See [the plan](doc/plans/old.md).\n")

    report = _apply(root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"})

    assert report.hits == []
    assert "(doc/plans/old.md)" in path.read_text(encoding="utf-8"), "must not rewrite"
    assert [m.rel_path for m in report.manual] == ["doc/notes.md"], "but must be reported"


def test_rewrites_sibling_relative_link(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(root, "doc/plans/other.md", "See [sibling](./old.md).\n")

    _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    text = path.read_text(encoding="utf-8")
    assert "./old.md" not in text
    assert "0042-new.md" in text


def test_rewrites_parent_relative_link(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(root, "doc/reports/r.md", "See [up](../plans/old.md).\n")

    _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    assert "../plans/old.md" not in path.read_text(encoding="utf-8")


def test_preserves_link_anchor(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(root, "doc/notes.md", "See [x](doc/plans/old.md#section-3).\n")

    _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    assert "#section-3" in path.read_text(encoding="utf-8")


def test_unrelated_link_untouched(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(root, "doc/notes.md", "See [other](doc/plans/keep.md) and [ext](https://example.com/old.md).\n")
    before = path.read_bytes()

    _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    assert path.read_bytes() == before


# ---- outbound ------------------------------------------------------------


def test_rewrite_outbound_links_rebases_relative_targets() -> None:
    text = "See [sib](./sibling.md) and [up](../architecture/x.md) and [abs](/nope) and [ext](https://e.com/a.md).\n"

    out, hits = rewrite_outbound_links(text, Path("doc/plans"), Path("entities/plans"))

    assert "](../../doc/plans/sibling.md)" in out
    assert "](../../doc/architecture/x.md)" in out
    assert "](/nope)" in out, "absolute path was rebased"
    assert "https://e.com/a.md" in out, "external URL was rebased"
    assert len(hits) == 2


# ---- manual / safety -----------------------------------------------------


def test_prose_path_mention_is_reported_not_rewritten(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(root, "doc/notes.md", "The design used to live at doc/plans/old.md before the move.\n")
    before = path.read_bytes()

    report = _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    assert path.read_bytes() == before
    assert [(m.rel_path, m.line) for m in report.manual] == [("doc/notes.md", 1)]


def test_plan_is_read_only(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\nrelated:\n- doc/plans/old.md\n---\n\nbody\n",
    )
    before = path.read_bytes()

    report = plan_reference_rewrite(
        root, id_substitutions={"doc/plans/old.md": "plan:0042-new"}, path_substitutions={}
    )

    assert len(report.hits) == 1
    assert path.read_bytes() == before


def test_binary_file_does_not_break_the_scan(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "img.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe\xfd")
    path = _write(root, "doc/notes.md", "See [x](plans/old.md).\n")

    _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    assert "0042-new.md" in path.read_text(encoding="utf-8")


# ---- code visibility -----------------------------------------------------


def test_code_reference_is_reported_but_never_rewritten(tmp_path: Path) -> None:
    """18 .py/.ts files in the consumer corpus reference doc/plans/*.md."""
    root = _project(tmp_path)
    py = _write(root, "scripts/check.py", 'SPEC = "doc/plans/old.md"  # authority\n')
    ts = _write(root, "src/registry.ts", "// see doc/plans/old.md\n")
    before = (py.read_bytes(), ts.read_bytes())

    report = _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    assert (py.read_bytes(), ts.read_bytes()) == before, "code must never be auto-rewritten"
    assert {m.rel_path for m in report.manual} == {"scripts/check.py", "src/registry.ts"}


# ---- double-reporting ----------------------------------------------------


def test_structured_reference_is_not_also_reported_manual(tmp_path: Path) -> None:
    """A ref the frontmatter pass fixed must not also be flagged for hand-fixing."""
    root = _project(tmp_path)
    _write(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\nrelated:\n- doc/plans/old.md\n---\n\nbody with no refs\n",
    )

    report = _apply(
        root,
        id_substitutions={"doc/plans/old.md": "plan:0042-new"},
        path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"},
    )

    assert len(report.hits) == 1
    assert report.manual == []


# ---- drift: apply replays a frozen plan ----------------------------------


def test_apply_refuses_when_a_new_referrer_appeared(tmp_path: Path) -> None:
    """The exposure that made the transaction's snapshot incomplete."""
    root = _project(tmp_path)
    _write(root, "doc/a.md", "See [x](plans/old.md).\n")
    plan = plan_reference_rewrite(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    # A concurrent writer adds a referrer the reviewer never saw.
    latecomer = _write(root, "doc/b.md", "Also [x](plans/old.md).\n")
    before = latecomer.read_bytes()

    with pytest.raises(ReferenceDriftError, match="doc/b.md"):
        apply_reference_rewrite(root, plan)

    assert latecomer.read_bytes() == before, "wrote a file outside the snapshot"
    assert "plans/old.md" in (root / "doc/a.md").read_text(encoding="utf-8"), "wrote despite drift"


def test_apply_refuses_when_a_planned_file_changed_underneath(tmp_path: Path) -> None:
    """Same hit, different file: the preimage hash is what catches it."""
    root = _project(tmp_path)
    path = _write(root, "doc/a.md", "See [x](plans/old.md).\n")
    plan = plan_reference_rewrite(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )
    assert plan.hits[0].preimage_sha256, "hit must carry its preimage"

    path.write_text("Rewritten prose. See [x](plans/old.md).\n", encoding="utf-8")

    with pytest.raises(ReferenceDriftError):
        apply_reference_rewrite(root, plan)


def test_apply_refuses_while_a_file_is_unreadable(tmp_path: Path) -> None:
    """A file that could not be read may hold a reference; success would be a lie."""
    root = _project(tmp_path)
    _write(root, "doc/a.md", "See [x](plans/old.md).\n")
    bad = _write(root, "doc/bad.md", "x\n")
    bad.write_bytes(b"\xff\xfe\x00\x00not utf8")

    plan = plan_reference_rewrite(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )
    assert [s.rel_path for s in plan.skipped] == ["doc/bad.md"]

    with pytest.raises(ReferenceDriftError, match="doc/bad.md"):
        apply_reference_rewrite(root, plan)

    assert "plans/old.md" in (root / "doc/a.md").read_text(encoding="utf-8")


def test_apply_replays_an_unchanged_plan(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(root, "doc/a.md", "See [x](plans/old.md).\n")
    plan = plan_reference_rewrite(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    report = apply_reference_rewrite(root, plan)

    assert report.hits == plan.hits
    assert "(../entities/plans/0042-new.md)" in path.read_text(encoding="utf-8")


def test_apply_writes_the_plans_own_postimage(tmp_path: Path) -> None:
    """Apply must not recompute what to write; it replays what was approved."""
    root = _project(tmp_path)
    path = _write(root, "doc/a.md", "See [x](plans/old.md).\n")
    plan = plan_reference_rewrite(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )
    assert [e.rel_path for e in plan.edits] == ["doc/a.md"]

    apply_reference_rewrite(root, plan)

    assert path.read_text(encoding="utf-8") == plan.edits[0].postimage


def test_apply_refuses_a_file_changed_between_verification_and_its_write(tmp_path: Path) -> None:
    """The verify-to-write window, distinct from the preview-to-apply one.

    _scan reads file A early and writes it late. A change landing in that gap
    would be overwritten here and then erased AGAIN when the caller's rollback
    restored the older snapshot. Injects the change between the corpus-wide
    comparison and A's write by mutating during B's write.
    """
    root = _project(tmp_path)
    a = _write(root, "doc/a.md", "See [x](plans/old.md).\n")
    b = _write(root, "doc/b.md", "Also [x](plans/old.md).\n")
    plan = plan_reference_rewrite(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )
    assert [e.rel_path for e in plan.edits] == ["doc/a.md", "doc/b.md"], "edits must be ordered"

    import science_tool.reference_rewrite as mod

    real_write = mod._atomic_replace_text
    concurrent = "Rewritten by someone else. [x](plans/old.md)\n"

    def _write_then_mutate_b(path: Path, text: str) -> None:
        real_write(path, text)
        if path.name == "a.md":  # a is written first; simulate b changing now
            b.write_text(concurrent, encoding="utf-8")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(mod, "_atomic_replace_text", _write_then_mutate_b)
    try:
        with pytest.raises(ReferenceDriftError, match="doc/b.md"):
            apply_reference_rewrite(root, plan)
    finally:
        monkeypatch.undo()

    assert b.read_text(encoding="utf-8") == concurrent, "overwrote a concurrent change"
    assert "0042-new.md" in a.read_text(encoding="utf-8"), "a was written before the refusal"


# ---- prose vs literal ----------------------------------------------------


def test_link_inside_a_code_fence_is_never_rewritten(tmp_path: Path) -> None:
    """141 fenced lines in the consumer corpus carry links. They are quotations."""
    root = _project(tmp_path)
    path = _write(
        root,
        "doc/a.md",
        "Real [live](plans/old.md).\n\n```markdown\nExample: [x](plans/old.md)\n```\n",
    )

    report = _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    text = path.read_text(encoding="utf-8")
    assert "Example: [x](plans/old.md)" in text, "rewrote a fenced example"
    assert "[live](../entities/plans/0042-new.md)" in text, "failed to rewrite the live link"
    assert [h.old for h in report.hits] == ["plans/old.md"], "one hit, not two"


def test_fenced_mention_is_not_reported_as_a_manual_hit(tmp_path: Path) -> None:
    root = _project(tmp_path)
    _write(root, "doc/a.md", "```\nsee doc/plans/old.md\n```\n")

    report = _apply(
        root, id_substitutions={}, path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"}
    )

    assert report.manual == [], "a path inside a fence is an example, not a stale pointer"


def test_no_hits_leaves_corpus_byte_identical(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(root, "entities/plans/0001-a.md", "---\nid: plan:0001-a\nkind: plan\n---\n\nbody\n")
    before = path.read_bytes()

    report = _apply(
        root, id_substitutions={"doc/plans/absent.md": "plan:0042-new"}, path_substitutions={}
    )

    assert report.hits == []
    assert path.read_bytes() == before


def test_file_with_both_surfaces_gets_both_rewrites(tmp_path: Path) -> None:
    root = _project(tmp_path)
    path = _write(
        root,
        "entities/plans/0001-a.md",
        "---\nid: plan:0001-a\nkind: plan\nrelated:\n- doc/plans/old.md\n---\n\nSee [x](../../doc/plans/old.md).\n",
    )

    report = _apply(
        root,
        id_substitutions={"doc/plans/old.md": "plan:0042-new"},
        path_substitutions={"doc/plans/old.md": "entities/plans/0042-new.md"},
    )

    text = path.read_text(encoding="utf-8")
    assert "- plan:0042-new" in text
    assert "](0042-new.md)" in text
    assert report.manual == [], "neither surface should also demand a hand fix"
