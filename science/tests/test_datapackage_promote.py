"""Tests for `science data-package promote-orphans` (design §B4, Phase 2a)."""

from __future__ import annotations

from pathlib import Path

from science_model.frontmatter import parse_frontmatter

from science_tool.datapackage_promote import plan_orphan_promotions, promote_orphan_datapackages
from science_tool.graph.sources import load_project_sources


def _scaffold(tmp_path: Path) -> None:
    """Build the minimal project manifest the loader tests use.

    Mirrors the `_seed` helper in test_load_project_sources_unified.py exactly.
    """
    (tmp_path / "science.yaml").write_text(
        "name: unified\nprofile: research\nprofiles: {local: local}\n",
        encoding="utf-8",
    )


def _write_orphan_external_datapackage(tmp_path: Path, slug: str = "z") -> Path:
    p = tmp_path / f"data/{slug}/datapackage.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        'profiles: ["science-pkg-entity-1.0"]\n'
        f'id: "dataset:{slug}"\n'
        'type: "dataset"\n'
        f'title: "Z {slug}"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n'
        'created: "2026-02-02"\n'
        'updated: "2026-02-02"\n',
        encoding="utf-8",
    )
    return p


def test_plan_lists_orphan_datapackage(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    plans = plan_orphan_promotions(tmp_path)
    ids = {p.canonical_id for p in plans}
    assert "dataset:z" in ids
    plan = next(p for p in plans if p.canonical_id == "dataset:z")
    assert plan.datapackage_rel == "data/z/datapackage.yaml"
    assert plan.owner_rel == "entities/datasets/z.md"


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    report = promote_orphan_datapackages(tmp_path, apply=False)
    assert [p.canonical_id for p in report["promotions"]] == ["dataset:z"]
    assert not (tmp_path / "entities/datasets/z.md").exists()


def test_apply_writes_owner_with_pointer_and_no_resource_fields(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    promote_orphan_datapackages(tmp_path, apply=True)
    owner = tmp_path / "entities/datasets/z.md"
    assert owner.exists()
    fm, _ = parse_frontmatter(owner)
    assert fm["id"] == "dataset:z"
    assert fm["type"] == "dataset"
    assert fm["origin"] == "external"
    assert fm["access"]["level"] == "public"
    assert fm["datapackage"] == "data/z/datapackage.yaml"
    assert fm["created"] == "2026-02-02"
    assert fm["updated"] == "2026-02-02"
    assert "resources" not in fm
    assert "members_resource" not in fm
    assert "profiles" not in fm


def test_after_apply_datapackage_defers_and_orphan_check_clean(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    promote_orphan_datapackages(tmp_path, apply=True)
    sources = load_project_sources(
        tmp_path,
        include_commons=False,
        strict_core_schema=False,
        strict_identity=False,
    )
    assert sources.entity_source_adapters["dataset:z"] == "markdown"
    assert sources.dataset_datapackages["dataset:z"] == "data/z/datapackage.yaml"
    assert plan_orphan_promotions(tmp_path) == []


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    promote_orphan_datapackages(tmp_path, apply=True)
    first = (tmp_path / "entities/datasets/z.md").read_text(encoding="utf-8")
    report2 = promote_orphan_datapackages(tmp_path, apply=True)
    assert report2["promotions"] == []
    assert (tmp_path / "entities/datasets/z.md").read_text(encoding="utf-8") == first


def test_undated_datapackage_promotes_with_sentinel(tmp_path: Path) -> None:
    _scaffold(tmp_path)
    p = tmp_path / "data/u/datapackage.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        'profiles: ["science-pkg-entity-1.0"]\n'
        'id: "dataset:u"\n'
        'type: "dataset"\n'
        'title: "U"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n',
        encoding="utf-8",
    )
    promote_orphan_datapackages(tmp_path, apply=True)
    fm, _ = parse_frontmatter(tmp_path / "entities/datasets/u.md")
    assert fm["created"] == "9999-99-99"


def test_path_traversal_id_is_rejected_not_written(tmp_path: Path) -> None:
    # HIGH finding: the dataset-id schema only requires a `dataset:` prefix, so a
    # traversal id must be rejected before it can write outside entities/datasets/.
    _scaffold(tmp_path)
    p = tmp_path / "data/evil/datapackage.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        'profiles: ["science-pkg-entity-1.0"]\n'
        'id: "dataset:../../escape"\n'
        'type: "dataset"\n'
        'title: "Evil"\n'
        'status: "active"\n'
        'origin: "external"\n'
        'access:\n'
        '  level: "public"\n'
        '  verified: false\n',
        encoding="utf-8",
    )
    # Rejection happens in the scan (before the apply gate), so it fires for dry-run too.
    dry = promote_orphan_datapackages(tmp_path, apply=False)
    assert ("dataset:../../escape", "data/evil/datapackage.yaml") in dry["rejected"]
    report = promote_orphan_datapackages(tmp_path, apply=True)
    assert report["promotions"] == []
    assert ("dataset:../../escape", "data/evil/datapackage.yaml") in report["rejected"]
    assert not (tmp_path.parent / "escape.md").exists()
    assert not (tmp_path / "entities/datasets/escape.md").exists()


def test_cli_promote_orphans_dry_run_then_apply(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from science_tool.cli import main as cli

    _scaffold(tmp_path)
    _write_orphan_external_datapackage(tmp_path)
    runner = CliRunner()

    dry = runner.invoke(cli, ["data-package", "promote-orphans", "--project-root", str(tmp_path)])
    assert dry.exit_code == 0, dry.output
    assert "[dry-run] would write entities/datasets/z.md" in dry.output
    assert not (tmp_path / "entities/datasets/z.md").exists()

    applied = runner.invoke(
        cli,
        ["data-package", "promote-orphans", "--apply", "--project-root", str(tmp_path)],
    )
    assert applied.exit_code == 0, applied.output
    assert "wrote entities/datasets/z.md" in applied.output
    assert (tmp_path / "entities/datasets/z.md").exists()
