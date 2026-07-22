"""Tests for the overlay/local-owner duplicate check.

A project that holds BOTH ``entities/<type>/<slug>.md`` (a local owner) AND
``overlays/<type>/<slug>.md`` (an overlay of the same id) has a genuine
duplicate: the overlay is the correct form and the local owner shadows it. This
is a purely local invariant — it needs no commons store to decide (fb-2026-07-11-019).
"""
from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.overlay_local_duplicate import (
    check_overlay_local_duplicate,
)
from science_tool.validate.context import ValidateContext

_MANIFEST = (
    "name: demo-project\n"
    "created: 2026-01-01\n"
    "last_modified: 2026-01-02\n"
    "status: active\n"
    "summary: Demo project\n"
    "profile: research\n"
    "layout_version: 1\n"
    "knowledge_profiles:\n"
    "  local: knowledge/local\n"
)


def _ctx(root: Path) -> ValidateContext:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _local_paper(root: Path, slug: str) -> None:
    _write(
        root,
        f"entities/papers/{slug}.md",
        f"---\nkind: paper\nid: paper:{slug}\ntitle: {slug}\n---\n\n# {slug}\n",
    )


def _overlay_paper(root: Path, slug: str) -> None:
    _write(
        root,
        f"overlays/papers/{slug}.md",
        f'---\nid: "paper:{slug}"\noverlay_of: "paper:{slug}"\npin_version: "1.0.0"\n---\n\n## Notes\n',
    )


def test_both_local_and_overlay_for_same_id_flags(tmp_path: Path) -> None:
    _local_paper(tmp_path, "Karczewski2024")
    _overlay_paper(tmp_path, "Karczewski2024")

    results = list(check_overlay_local_duplicate(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.path == Path("entities/papers/Karczewski2024.md")
    assert "paper:Karczewski2024" in r.message
    # The remedy must be to DELETE the local copy, not "convert to an overlay"
    # (an overlay already exists — converting would collide).
    assert "delete" in r.message.lower()
    assert "overlays/papers/Karczewski2024.md" in r.message


def test_overlay_only_does_not_flag(tmp_path: Path) -> None:
    _overlay_paper(tmp_path, "Karczewski2024")

    assert list(check_overlay_local_duplicate(_ctx(tmp_path))) == []


def test_local_only_does_not_flag(tmp_path: Path) -> None:
    _local_paper(tmp_path, "Karczewski2024")

    assert list(check_overlay_local_duplicate(_ctx(tmp_path))) == []


def test_needs_no_commons_store(tmp_path: Path) -> None:
    # No SCIENCE_COMMONS_ROOT set, no commons dir: the check still fires because
    # the duplicate is a purely local fact.
    _local_paper(tmp_path, "Karczewski2024")
    _overlay_paper(tmp_path, "Karczewski2024")

    assert len(list(check_overlay_local_duplicate(_ctx(tmp_path)))) == 1
