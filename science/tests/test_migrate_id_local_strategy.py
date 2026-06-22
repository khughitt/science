"""Phase 1 of the adapter-entity-layout migration: the `id-local` strategy.

`id-local` preserves a kind's authoritative frontmatter `id:` and derives the
destination *filename* from the id's local part (rather than the file stem, as
`slug`/`verbatim` do). This is what lets dataset/workflow owners move
doc/<type>/data-<slug>.md -> entities/<kind>/<slug>.md with ZERO id/reference
rewrites — see docs/plans/2026-06-21-adapter-entity-layout-and-overlay-root-design.md
Key decision 1.

These tests exercise the strategy through a *local* kind so they do not depend on
the Phase 2 core-profile wiring of `dataset`/`workflow`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.entity_layout_migration import migrate_layout

# Local profile with an `id-local` kind whose legacy files carry a `data-` prefix
# and an id whose local part differs from the file stem (stem "data-acme-thing"
# vs id local part "acme-thing"). A stem-derived strategy would mint
# "gadget:data-acme-thing"; id-local must preserve "gadget:acme-thing".
_LOCAL_PROFILE = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds:
  - name: gadget
    canonical_prefix: gadget
    layer: layer/local
    description: Gadget.
    home: entities/gadgets
    strategy: id-local
relation_kinds: []
"""

_SCIENCE_YAML = "name: t\nlayout_version: 2\nknowledge_profiles:\n  local: local\n"


def _write(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def _git_init(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "seed"],
        cwd=root,
        check=True,
    )


def test_id_local_preserves_id_and_renames_file_to_id_local_part(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", _SCIENCE_YAML)
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # Owner: stem "data-acme-thing", id local part "acme-thing".
    _write(
        tmp_path,
        "doc/gadgets/data-acme-thing.md",
        '---\nid: "gadget:acme-thing"\ntype: gadget\ncreated: "2026-01-02"\n'
        'title: Acme Thing\nstatus: active\nupdated: "2026-01-02"\n---\nbody\n',
    )
    # A separate core entity referencing the gadget by id — must NOT be rewritten.
    _write(
        tmp_path,
        "specs/hypotheses/h01-x.md",
        '---\nid: "hypothesis:h01-x"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: X\nstatus: proposed\nupdated: "2026-01-01"\nrelated: ["gadget:acme-thing"]\n---\n'
        "Depends on gadget:acme-thing.\n",
    )
    _git_init(tmp_path)

    report = migrate_layout(tmp_path, apply=True)

    assert report["applied"] is True
    assert report.get("graph_validation") == "passed"
    # File renamed: data- prefix dropped, filename = id local part, under entities/.
    assert (tmp_path / "entities/gadgets/acme-thing.md").is_file()
    assert not (tmp_path / "doc/gadgets/data-acme-thing.md").exists()
    # Id preserved verbatim in the moved file.
    moved = (tmp_path / "entities/gadgets/acme-thing.md").read_text()
    assert 'id: "gadget:acme-thing"' in moved or "id: gadget:acme-thing" in moved
    # Zero reference rewrites: the referencing hypothesis still says gadget:acme-thing,
    # and id_map records identity (or omits the unchanged id) — never a renamed id.
    hyp = (tmp_path / "entities/hypotheses/0001-h01-x.md").read_text()
    assert "gadget:acme-thing" in hyp
    assert "gadget:data-acme-thing" not in hyp
    assert report["id_map"].get("gadget:acme-thing", "gadget:acme-thing") == "gadget:acme-thing"


def test_id_local_file_without_explicit_id_is_a_planning_error(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", _SCIENCE_YAML)
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # No `id:` — id-local has no stem fallback, so planning must refuse.
    _write(
        tmp_path,
        "doc/gadgets/data-orphan.md",
        '---\ntype: gadget\ncreated: "2026-01-02"\ntitle: Orphan\nstatus: active\nupdated: "2026-01-02"\n---\nbody\n',
    )
    _git_init(tmp_path)

    with pytest.raises(ValueError, match="id-local"):
        migrate_layout(tmp_path, apply=False)
