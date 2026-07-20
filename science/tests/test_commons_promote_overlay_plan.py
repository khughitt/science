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
    (root / "entities" / "papers").mkdir(parents=True)
    for filename, content in papers.items():
        (root / "entities" / "papers" / filename).write_text(content, encoding="utf-8")
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
    "kind: paper\n"
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


def _plan_for(monkeypatch, commons: Path, projects: dict[str, Path], from_order, resolve_conflict=None):
    from science_tool.commons.promote import (
        PROMOTE_KIND_PAPER,
        discover_candidates,
        plan_promote,
    )

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: projects[slug],
    )
    discovery = discover_candidates(list(projects), PROMOTE_KIND_PAPER)
    return plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=resolve_conflict if resolve_conflict is not None else (lambda _c: None),
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
    plan = _plan_for(monkeypatch, commons, {"proj-b": proj}, ["proj-b"])

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
    plan = _plan_for(monkeypatch, commons, {"proj-b": proj}, ["proj-b"])

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
    plan = _plan_for(monkeypatch, commons, {"proj-a": proj}, ["proj-a"])

    d = _decision_for(plan, "Bar")
    assert d.mode == "mint"
    assert d.canonical_artifacts != []
    assert d.canonical_version == "1.0.0"
    assert d.existing_version is None


def test_divergent_keep_existing_records_resolution(tmp_path, monkeypatch) -> None:
    from science_tool.commons.promote import KEEP_EXISTING, ExistingCanonicalConflict

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

    plan = _plan_for(monkeypatch, commons, {"proj-b": proj}, ["proj-b"], resolve_conflict=resolve)

    d = _decision_for(plan, "Foo")
    assert d.mode == "overlay_existing"
    assert any(c.field == "doi" for c in seen)
    res = [r for r in d.resolved_conflicts if r.field == "doi"]
    assert len(res) == 1
    r = res[0]
    assert set(r.candidates) == {"<commons-existing>", "<source-merged>"}
    assert r.candidates["<source-merged>"] == "10.1/xyz"
    assert r.source_project is None


def test_conflict_carries_the_body_content_keep_existing_would_discard(tmp_path, monkeypatch) -> None:
    """fb-2026-07-16-004: [k] dropped 347 real lines with no diff, warning, or count.

    The source carries a Methods section commons entirely lacks, and a richer
    Key Findings. Keep-existing preserves neither, so the conflict must say so
    before the operator chooses.
    """
    from science_tool.commons.promote import KEEP_EXISTING, ExistingCanonicalConflict

    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical(commons, case_slug="Foo", version="1.0.0", content=_CANONICAL_FOO)

    rich_findings = "\n".join(f"finding {n}" for n in range(20))
    methods = "\n".join(f"step {n}" for n in range(15))
    proj = _build_project(
        tmp_path,
        "proj-b",
        {
            "Foo.md": (
                "---\nid: paper:Foo\ntitle: A study of foo\nyear: 2025\n---\n\n"
                f"## Key Findings\n\n{rich_findings}\n\n## Methods\n\n{methods}\n"
            )
        },
    )

    seen: list = []

    def resolve(conflict):
        seen.append(conflict)
        return KEEP_EXISTING

    _plan_for(monkeypatch, commons, {"proj-b": proj}, ["proj-b"], resolve_conflict=resolve)

    assert seen, "expected an ExistingCanonicalConflict"
    conflict = seen[0]
    assert isinstance(conflict, ExistingCanonicalConflict)
    loss = conflict.body_loss
    assert loss is not None and loss.has_loss

    by_section = {entry.section: entry for entry in loss.entries}
    assert by_section["Methods"].disposition == "dropped"
    assert by_section["Methods"].source_lines == 15
    assert by_section["Methods"].existing_lines == 0
    assert by_section["Key Findings"].disposition == "downgraded"
    assert by_section["Key Findings"].source_lines == 20


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

    def resolve(_conflict):
        raise PromoteConflictAbort("user aborted")

    with pytest.raises(PromoteConflictAbort):
        _plan_for(monkeypatch, commons, {"proj-b": proj}, ["proj-b"], resolve_conflict=resolve)


def test_prompt_resolve_keep_existing(monkeypatch) -> None:
    import click

    from science_tool.commons.cli import prompt_resolve
    from science_tool.commons.promote import (
        KEEP_EXISTING,
        ExistingCanonicalConflict,
    )

    conflict = ExistingCanonicalConflict(
        slug="Foo",
        kind="paper",
        field="doi",
        source_value="10.1/xyz",
        existing_value=None,
        existing_version="1.0.0",
    )
    monkeypatch.setattr(click, "prompt", lambda *_a, **_k: "k")
    assert prompt_resolve(conflict) is KEEP_EXISTING


def test_prompt_resolve_shows_the_body_content_it_would_discard(monkeypatch, capsys) -> None:
    """The operator must see the count before answering, not discover it later."""
    import click

    from science_tool.commons.cli import prompt_resolve
    from science_tool.commons.promote import KEEP_EXISTING, ExistingCanonicalConflict
    from science_tool.commons.promote_body_loss import canonical_body_loss

    conflict = ExistingCanonicalConflict(
        slug="Haigis2019",
        kind="paper",
        field="Key Findings",
        source_value="x" * 40,
        existing_value="y" * 20,
        existing_version="1.0.0",
        body_loss=canonical_body_loss(
            source_body={"Key Findings": "line\n" * 112, "Methods": "line\n" * 81},
            existing_body={"Key Findings": "line\n" * 39},
        ),
    )
    monkeypatch.setattr(click, "prompt", lambda *_a, **_k: "k")

    assert prompt_resolve(conflict) is KEEP_EXISTING

    out = capsys.readouterr().out
    assert "DISCARD" in out
    assert "Methods" in out and "PURE LOSS" in out
    assert "112" in out and "81" in out
    assert "193 source lines discarded" in out
    # The huge raw body values must not be dumped in place of the count.
    assert "line\\nline\\n" not in out


def test_prompt_resolve_omits_the_loss_block_when_nothing_is_discarded(monkeypatch, capsys) -> None:
    import click

    from science_tool.commons.cli import prompt_resolve
    from science_tool.commons.promote import ExistingCanonicalConflict

    conflict = ExistingCanonicalConflict(
        slug="Foo",
        kind="paper",
        field="doi",
        source_value="10.1/xyz",
        existing_value=None,
        existing_version="1.0.0",
    )
    monkeypatch.setattr(click, "prompt", lambda *_a, **_k: "k")
    prompt_resolve(conflict)

    assert "DISCARD" not in capsys.readouterr().out


def test_prompt_resolve_abort(monkeypatch) -> None:
    import click

    from science_tool.commons.cli import prompt_resolve
    from science_tool.commons.errors import PromoteConflictAbort
    from science_tool.commons.promote import ExistingCanonicalConflict

    conflict = ExistingCanonicalConflict(
        slug="Foo",
        kind="paper",
        field="doi",
        source_value="10.1/xyz",
        existing_value=None,
        existing_version="1.0.0",
    )
    monkeypatch.setattr(click, "prompt", lambda *_a, **_k: "a")
    with pytest.raises(PromoteConflictAbort):
        prompt_resolve(conflict)
