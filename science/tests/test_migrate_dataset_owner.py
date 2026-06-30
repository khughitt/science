"""Phase 2 of the adapter-entity-layout migration: wire the dataset/workflow
family to entities/ via the id-local strategy, and confirm owner destination
collisions block --apply.

See docs/audits/plans-cleanup/2026-06-03-entity-layout-v3-checkpoint.md.
These exercise the *core* `dataset` kind (now home=entities/datasets,
strategy=id-local), so they depend on the Phase 2 core-profile wiring.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from science_tool.entity_layout_migration import migrate_layout

# Core-only project: an empty local profile (just imports core) so dataset/workflow
# come from the builtin policy table.
_LOCAL_PROFILE = """\
name: t-local
imports:
  - core
strictness: typed-extension
entity_kinds: []
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


def _dataset_owner(slug: str) -> str:
    return (
        f'---\nid: "dataset:{slug}"\ntype: "dataset"\ncreated: "2026-01-02"\n'
        f'title: "{slug}"\nstatus: "active"\nupdated: "2026-01-02"\n---\nbody\n'
    )


def test_dataset_owner_migrates_to_entities_via_id_local(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", _SCIENCE_YAML)
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # Owner with the legacy data- prefix; id local part "acme" != stem "data-acme".
    _write(tmp_path, "doc/datasets/data-acme.md", _dataset_owner("acme"))
    # A hypothesis referencing the dataset by id — must NOT be rewritten.
    _write(
        tmp_path,
        "specs/hypotheses/h01-x.md",
        '---\nid: "hypothesis:h01-x"\ntype: hypothesis\ncreated: "2026-01-01"\n'
        'title: X\nstatus: proposed\nupdated: "2026-01-01"\nrelated: ["dataset:acme"]\n---\n'
        "Uses dataset:acme.\n",
    )
    _git_init(tmp_path)

    report = migrate_layout(tmp_path, apply=True)

    assert report["applied"] is True
    assert report.get("graph_validation") == "passed"
    # data- prefix dropped; filename = id local part; under entities/datasets/.
    assert (tmp_path / "entities/datasets/acme.md").is_file()
    assert not (tmp_path / "doc/datasets/data-acme.md").exists()
    moved = (tmp_path / "entities/datasets/acme.md").read_text()
    assert 'id: "dataset:acme"' in moved or "id: dataset:acme" in moved
    # Zero reference rewrites.
    hyp = (tmp_path / "entities/hypotheses/0001-h01-x.md").read_text()
    assert "dataset:acme" in hyp
    assert "dataset:data-acme" not in hyp


def test_dataset_owner_destination_collision_blocks_apply(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", _SCIENCE_YAML)
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # Two owners with the SAME id (one prefixed, one not) → both target
    # entities/datasets/acme.md. Must be caught as a collision and abort --apply.
    _write(tmp_path, "doc/datasets/data-acme.md", _dataset_owner("acme"))
    _write(tmp_path, "doc/datasets/acme.md", _dataset_owner("acme"))
    _git_init(tmp_path)

    # Dry run surfaces the collision in the report...
    report = migrate_layout(tmp_path, apply=False)
    targets = {c.get("target") for c in report["collisions"]}
    assert "entities/datasets/acme.md" in targets

    # ...and --apply refuses, leaving the tree untouched.
    with pytest.raises(ValueError, match="collisions block"):
        migrate_layout(tmp_path, apply=True)
    assert (tmp_path / "doc/datasets/data-acme.md").is_file()
    assert not (tmp_path / "entities/datasets/acme.md").exists()
