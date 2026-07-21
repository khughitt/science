"""Tests for the commons owner-collision check.

A project entity that locally OWNS an id a commons canonical already owns
(a cross-scope shadow) makes ownership ambiguous: it can drop edges and make a
commons entity's reference to that id resolve to nothing (surfacing as a
misleading `unresolved_reference`). The correct form is an overlay.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import RegistryBuilder
from science_tool.validate.checks.commons_owner_collision import (
    check_commons_owner_collision,
)
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

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


def _local_dataset(root: Path, slug: str) -> None:
    _write(
        root,
        f"entities/datasets/{slug}.md",
        f"---\nkind: dataset\nid: dataset:{slug}\ntitle: {slug}\n---\n\n# {slug}\n",
    )


def _commons_root(tmp_path: Path, *, papers: tuple[str, ...] = (), datasets: tuple[str, ...] = ()) -> Path:
    commons = tmp_path / "commons"
    for slug in papers:
        _write(
            commons,
            f"papers/{slug}.md",
            "---\n"
            "schema_profile: science-entity-base/1.0+paper/1.0\n"
            f"id: paper:{slug}\n"
            "kind: paper\n"
            f"title: {slug}\n"
            'version: "1.0.0"\n'
            "created: \"2026-05-13\"\n"
            "updated: \"2026-05-13\"\n"
            "ontology_terms: []\n"
            "tags: []\n"
            "---\nbody\n",
        )
    for slug in datasets:
        _write(
            commons,
            f"datasets/{slug}/entity.md",
            "---\n"
            "schema_profile: science-entity-base/1.0+dataset/1.0\n"
            f"id: dataset:{slug}\n"
            "kind: dataset\n"
            f"title: {slug}\n"
            'version: "1.0.0"\n'
            "created: \"2026-05-13\"\n"
            "updated: \"2026-05-13\"\n"
            "status: active\n"
            "datapackage: datapackage.yaml\n"
            "origin: derived\n"
            "tier: use-now\n"
            "derivation:\n"
            "  kind: workflow\n"
            "  workflow_recipe: workflow:demo\n"
            "  inputs: []\n"
            "---\nbody\n",
        )
        _write(commons, f"datasets/{slug}/datapackage.yaml", f"name: {slug}\nresources: []\n")
    RegistryBuilder(commons, CommonsEntityAdapter(commons)).rebuild()
    return commons


def test_local_owner_shadowing_commons_canonical_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_commons_root(tmp_path, papers=("Adams2025",))))
    _local_paper(tmp_path, "Adams2025")

    results = list(check_commons_owner_collision(_ctx(tmp_path)))

    assert len(results) == 1
    r = results[0]
    assert r.severity is Severity.ERROR
    assert r.path == Path("entities/papers/Adams2025.md")
    assert "paper:Adams2025" in r.message
    assert "overlay" in r.message.lower()


def test_overlay_of_commons_id_does_not_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_commons_root(tmp_path, papers=("Adams2025",))))
    _overlay_paper(tmp_path, "Adams2025")

    assert list(check_commons_owner_collision(_ctx(tmp_path))) == []


def test_local_owner_without_commons_canonical_does_not_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_commons_root(tmp_path, papers=("Adams2025",))))
    _local_paper(tmp_path, "LocalOnly2025")

    assert list(check_commons_owner_collision(_ctx(tmp_path))) == []


def test_missing_commons_root_does_not_warn(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "does-not-exist"))
    _local_paper(tmp_path, "Adams2025")

    assert list(check_commons_owner_collision(_ctx(tmp_path))) == []


def test_dataset_owner_collision_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(_commons_root(tmp_path, datasets=("uk-biobank",))))
    _local_dataset(tmp_path, "uk-biobank")

    results = list(check_commons_owner_collision(_ctx(tmp_path)))

    assert [r.severity for r in results] == [Severity.ERROR]
    assert "dataset:uk-biobank" in results[0].message
