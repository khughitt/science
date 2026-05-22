"""Tests for science_tool.commons.promote — plan-time overlay_existing routing (t063).

These are integration-level tests: they build a real commons git repo with a
committed canonical paper + version tag, build source projects, and assert on
the PromotePlan that `plan_promote` actually produces (not mocks of internals).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@x"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)


def _init_commons(root: Path) -> None:
    _init_repo(root)
    (root / "papers").mkdir()
    (root / ".migrations").mkdir()
    (root / ".gitignore").write_text("registry.sqlite\n.registry-*.sqlite\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)


def _commit_canonical(
    commons: Path,
    *,
    case_slug: str,
    version: str,
    content: str,
) -> None:
    """Write papers/<case_slug>.md, commit it, and tag paper/<case_slug>/<version>."""
    path = commons / "papers" / f"{case_slug}.md"
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True)
    subprocess.run(["git", "-C", str(commons), "commit", "-q", "-m", f"add {case_slug}"], check=True)
    subprocess.run(
        ["git", "-C", str(commons), "tag", f"paper/{case_slug}/{version}"], check=True
    )


def _build_project(tmp_path: Path, name: str, papers: dict[str, str]) -> Path:
    root = tmp_path / name
    (root / "doc" / "papers").mkdir(parents=True)
    for filename, content in papers.items():
        (root / "doc" / "papers" / filename).write_text(content, encoding="utf-8")
    _init_repo(root)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)
    return root


# A committed canonical paper as the apply path would render it: a real
# schema_profile + bibkey/id, title, year, and a canonical body section.
_CANONICAL_FOO = (
    "---\n"
    "schema_profile: science-entity-base/1.0+paper/2.0\n"
    "id: paper:Foo\n"
    "type: paper\n"
    "bibkey: Foo\n"
    "version: 1.0.0\n"
    "title: A study of foo\n"
    "year: 2025\n"
    "tags: []\n"
    "---\n"
    "\n"
    "## Key Findings\n"
    "\n"
    "foo is real\n"
)


def _plan_for(tmp_path, monkeypatch, commons: Path, projects: dict[str, Path], from_order, resolve_conflict=None):
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda slug: projects[slug],
    )
    discovery = discover_candidates(list(projects), PROMOTE_KIND_PAPER)
    return plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=resolve_conflict if resolve_conflict is not None else (lambda c: None),
        from_order=from_order,
    )


def _decision_for(plan, slug: str):
    matches = [d for d in plan.decisions if d.slug == slug]
    assert len(matches) == 1, f"expected exactly one decision for {slug!r}, got {plan.decisions}"
    return matches[0]


def test_overlay_when_identical(tmp_path, monkeypatch) -> None:
    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical(commons, case_slug="Foo", version="1.0.0", content=_CANONICAL_FOO)

    proj = _build_project(
        tmp_path,
        "proj-b",
        {"Foo.md": "---\nid: paper:Foo\ntitle: A study of foo\nyear: 2025\n---\n\n## Key Findings\n\nfoo is real\n"},
    )
    plan = _plan_for(tmp_path, monkeypatch, commons, {"proj-b": proj}, ["proj-b"])

    d = _decision_for(plan, "Foo")
    assert d.mode == "overlay_existing"
    assert d.canonical_artifacts == []
    assert d.canonical_version == "1.0.0"
    assert d.existing_version == "1.0.0"
    overlay = d.overlays["proj-b"]
    assert overlay.pin_version == "1.0.0"


def test_case_insensitive_match_uses_committed_case(tmp_path, monkeypatch) -> None:
    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical(commons, case_slug="Foo", version="1.0.0", content=_CANONICAL_FOO)

    # Source file is lower-case foo.md; commons committed case is Foo.
    proj = _build_project(
        tmp_path,
        "proj-b",
        {"foo.md": "---\nid: paper:foo\ntitle: A study of foo\nyear: 2025\n---\n\n## Key Findings\n\nfoo is real\n"},
    )
    plan = _plan_for(tmp_path, monkeypatch, commons, {"proj-b": proj}, ["proj-b"])

    d = _decision_for(plan, "Foo")
    assert d.mode == "overlay_existing"
    overlay = d.overlays["proj-b"]
    assert "overlay_of: paper:Foo" in overlay.after_content
    assert "id: paper:Foo" in overlay.after_content


def test_mint_unchanged_when_no_existing_tag(tmp_path, monkeypatch) -> None:
    commons = tmp_path / "commons"
    _init_commons(commons)
    # No committed canonical / tag for Bar.

    proj = _build_project(
        tmp_path,
        "proj-a",
        {"Bar.md": "---\nid: paper:Bar\ntitle: B\nyear: 2025\n---\n\n## Key Findings\n\nbar\n"},
    )
    plan = _plan_for(tmp_path, monkeypatch, commons, {"proj-a": proj}, ["proj-a"])

    d = _decision_for(plan, "Bar")
    assert d.mode == "mint"
    assert d.canonical_artifacts != []
    assert d.canonical_version == "1.0.0"
    assert d.existing_version is None


def test_divergent_keep_existing_records_resolution(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import ExistingCanonicalConflict, KEEP_EXISTING

    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical(commons, case_slug="Foo", version="1.0.0", content=_CANONICAL_FOO)

    # Source introduces a new doi the committed entity lacks → divergent.
    proj = _build_project(
        tmp_path,
        "proj-b",
        {"Foo.md": "---\nid: paper:Foo\ntitle: A study of foo\nyear: 2025\ndoi: 10.1/xyz\n---\n\n## Key Findings\n\nfoo is real\n"},
    )

    seen: list = []

    def resolve(conflict):
        seen.append(conflict)
        assert isinstance(conflict, ExistingCanonicalConflict)
        return KEEP_EXISTING

    plan = _plan_for(tmp_path, monkeypatch, commons, {"proj-b": proj}, ["proj-b"], resolve_conflict=resolve)

    d = _decision_for(plan, "Foo")
    assert d.mode == "overlay_existing"
    assert any(c.field == "doi" for c in seen)
    res = [r for r in d.resolved_conflicts if r.field == "doi"]
    assert len(res) == 1
    r = res[0]
    assert set(r.candidates) == {"<commons-existing>", "<source-merged>"}
    assert r.candidates["<source-merged>"] == "10.1/xyz"
    assert r.source_project is None


def test_divergent_abort_propagates(tmp_path, monkeypatch) -> None:
    from science_tool.commons.errors import PromoteConflictAbort

    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical(commons, case_slug="Foo", version="1.0.0", content=_CANONICAL_FOO)

    proj = _build_project(
        tmp_path,
        "proj-b",
        {"Foo.md": "---\nid: paper:Foo\ntitle: A study of foo\nyear: 2025\ndoi: 10.1/xyz\n---\n\n## Key Findings\n\nfoo is real\n"},
    )

    def resolve(conflict):
        raise PromoteConflictAbort("user aborted")

    with pytest.raises(PromoteConflictAbort):
        _plan_for(tmp_path, monkeypatch, commons, {"proj-b": proj}, ["proj-b"], resolve_conflict=resolve)


def test_prompt_resolve_keep_existing(monkeypatch) -> None:
    import click

    from science_tool.commons.promote import (
        ExistingCanonicalConflict,
        KEEP_EXISTING,
        prompt_resolve,
    )

    conflict = ExistingCanonicalConflict(
        slug="Foo",
        kind="paper",
        field="doi",
        source_value="10.1/xyz",
        existing_value=None,
        existing_version="1.0.0",
    )
    monkeypatch.setattr(click, "prompt", lambda *a, **k: "k")
    assert prompt_resolve(conflict) is KEEP_EXISTING


def test_prompt_resolve_abort(monkeypatch) -> None:
    import click

    from science_tool.commons.errors import PromoteConflictAbort
    from science_tool.commons.promote import ExistingCanonicalConflict, prompt_resolve

    conflict = ExistingCanonicalConflict(
        slug="Foo",
        kind="paper",
        field="doi",
        source_value="10.1/xyz",
        existing_value=None,
        existing_version="1.0.0",
    )
    monkeypatch.setattr(click, "prompt", lambda *a, **k: "a")
    with pytest.raises(PromoteConflictAbort):
        prompt_resolve(conflict)
