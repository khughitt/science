"""Non-interactive skip-and-continue on promote conflicts (fb-2026-05-30-009).

When a citekey collides with a DIFFERENT existing commons entity, an interactive
run prompts (keep/abort). A non-interactive run (piped/redirected stdin) cannot
answer, and previously aborted the whole batch on the first collision. With
``skip_on_conflict=True`` the colliding slug is skipped and recorded as a
``PromoteConflictSkipped`` soft-failure while the rest of the batch proceeds.

The commons/project scaffolding mirrors test_commons_promote_overlay_plan.py
(a real commons git repo with a committed canonical paper + version tag).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.commons.errors import PromoteConflictAbort


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


def _commit_canonical(commons: Path, *, case_slug: str, version: str, content: str) -> None:
    path = commons / "papers" / f"{case_slug}.md"
    path.write_text(content, encoding="utf-8")
    subprocess.run(["git", "-C", str(commons), "add", "."], check=True)
    subprocess.run(["git", "-C", str(commons), "commit", "-q", "-m", f"add {case_slug}"], check=True)
    subprocess.run(["git", "-C", str(commons), "tag", f"paper/{case_slug}/{version}"], check=True)


def _build_project(tmp_path: Path, name: str, papers: dict[str, str]) -> Path:
    root = tmp_path / name
    (root / "entities" / "papers").mkdir(parents=True)
    for filename, content in papers.items():
        (root / "entities" / "papers" / filename).write_text(content, encoding="utf-8")
    _init_repo(root)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)
    return root


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

# A source paper that shares the committed citekey (Foo) but is a DIFFERENT paper
# (introduces a doi the committed entity lacks) → divergence → conflict prompt.
_SOURCE_FOO_DIVERGENT = (
    "---\n"
    "id: paper:Foo\n"
    "title: A study of foo\n"
    "year: 2025\n"
    "doi: 10.1/xyz\n"
    "---\n"
    "\n## Key Findings\n\nfoo is real\n"
)


def _discovery_for(monkeypatch, projects: dict[str, Path]):
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, discover_candidates

    monkeypatch.setattr(
        "science_tool.commons.promote.registry_root_for_id",
        lambda slug: projects[slug],
    )
    return discover_candidates(list(projects), PROMOTE_KIND_PAPER)


def _always_abort(_conflict: object) -> object:
    raise PromoteConflictAbort("non-interactive: cannot prompt")


def test_conflict_aborts_batch_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, plan_promote

    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical(commons, case_slug="Foo", version="1.0.0", content=_CANONICAL_FOO)
    proj = _build_project(tmp_path, "proj-b", {"Foo.md": _SOURCE_FOO_DIVERGENT})

    discovery = _discovery_for(monkeypatch, {"proj-b": proj})
    with pytest.raises(PromoteConflictAbort):
        plan_promote(
            discovery,
            commons_root=commons,
            kind=PROMOTE_KIND_PAPER,
            resolve_conflict=_always_abort,
            from_order=["proj-b"],
        )


def test_skip_on_conflict_records_soft_failure_and_continues(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from science_tool.commons.promote import PROMOTE_KIND_PAPER, plan_promote

    commons = tmp_path / "commons"
    _init_commons(commons)
    _commit_canonical(commons, case_slug="Foo", version="1.0.0", content=_CANONICAL_FOO)
    proj = _build_project(tmp_path, "proj-b", {"Foo.md": _SOURCE_FOO_DIVERGENT})

    discovery = _discovery_for(monkeypatch, {"proj-b": proj})
    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_PAPER,
        resolve_conflict=_always_abort,
        from_order=["proj-b"],
        skip_on_conflict=True,
    )

    # The colliding slug is skipped (no decision minted) and recorded as a soft-failure.
    assert all(d.slug != "Foo" for d in plan.decisions)
    skipped = [fc for fc in plan.failed_candidates if fc.error_class == "PromoteConflictSkipped"]
    assert len(skipped) == 1
    assert skipped[0].slug == "Foo"
