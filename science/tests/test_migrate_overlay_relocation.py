"""Phase 3 of the adapter-entity-layout migration: relocate commons overlays out
of the prose-only doc/<type>/ tree into the dedicated overlays/<type>/ root.

See docs/audits/plans-cleanup/2026-06-03-entity-layout-v3-checkpoint.md.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from science_tool.entity_layout_migration import migrate_layout, plan_migration

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


def test_dataset_overlay_relocation_is_planned_dropping_data_prefix(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", _SCIENCE_YAML)
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # A commons dataset OVERLAY carrying the legacy data- filename prefix.
    _write(
        tmp_path,
        "doc/datasets/data-acme.md",
        '---\nid: "dataset:acme"\noverlay_of: "dataset:acme"\nrelevance: "used in H1"\n---\n\nProject notes.\n',
    )

    plan = plan_migration(tmp_path)

    overlay_targets = {(o.old_rel_path, o.new_rel_path, o.canonical_id) for o in plan.overlay_moves}
    # data- prefix dropped (filename follows the overlay_of local part); lands in overlays/.
    assert ("doc/datasets/data-acme.md", "overlays/datasets/acme.md", "dataset:acme") in overlay_targets
    # An overlay is NOT an owner move and must not be frontmatter-synthesized into entities/.
    assert all(m.new_rel_path != "entities/datasets/acme.md" for m in plan.moves)


def test_two_overlays_same_canonical_collide(tmp_path: Path) -> None:
    _write(tmp_path, "science.yaml", _SCIENCE_YAML)
    _write(tmp_path, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # Two overlay files for the SAME canonical → same overlays/ destination.
    _write(
        tmp_path,
        "doc/datasets/data-acme.md",
        '---\nid: "dataset:acme"\noverlay_of: "dataset:acme"\n---\n',
    )
    _write(
        tmp_path,
        "doc/datasets/acme.md",
        '---\nid: "dataset:acme"\noverlay_of: "dataset:acme"\n---\n',
    )

    plan = plan_migration(tmp_path)
    targets = {c.get("target") for c in plan.collisions}
    assert "overlays/datasets/acme.md" in targets


def test_paper_overlay_relocates_and_audit_passes_with_commons(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Faithful end-to-end: an owner+overlay split lands in two distinct roots and
    # the post-move audit (now reading overlays/ and resolving against commons) passes.
    import yaml

    from science_tool.commons.adapter import CommonsEntityAdapter
    from science_tool.commons.registry import RegistryBuilder

    src = Path(__file__).parent / "fixtures" / "commons" / "valid"
    commons_root = tmp_path / "commons"
    shutil.copytree(src, commons_root)
    RegistryBuilder(commons_root, CommonsEntityAdapter(commons_root)).rebuild()

    project_root = tmp_path / "project"
    project_root.mkdir()
    cfg_dir = tmp_path / "cfg"
    cfg_dir.mkdir()
    (cfg_dir / "config.yaml").write_text(
        yaml.dump({"projects": [{"path": str(project_root), "name": "project", "registered": "2026-05-14"}]}),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons_root))
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")

    _write(project_root, "science.yaml", _SCIENCE_YAML)
    _write(project_root, "knowledge/sources/local/manifest.yaml", _LOCAL_PROFILE)
    # An overlay onto the commons canonical paper:Adams2025, in the prose tree.
    _write(
        project_root,
        "doc/papers/Adams2025.md",
        '---\nid: "paper:Adams2025"\noverlay_of: "paper:Adams2025"\nrelevance: "H2 background"\n---\n\n'
        "## Project-Specific Notes\n\nLocal commentary.\n",
    )
    _git_init(project_root)

    report = migrate_layout(project_root, apply=True)

    assert report["applied"] is True
    assert report.get("graph_validation") == "passed"
    assert (project_root / "overlays/papers/Adams2025.md").is_file()
    assert not (project_root / "doc/papers/Adams2025.md").exists()
    # The overlay_of is preserved verbatim.
    moved = (project_root / "overlays/papers/Adams2025.md").read_text()
    assert "overlay_of: paper:Adams2025" in moved or 'overlay_of: "paper:Adams2025"' in moved
