"""Tests for science_tool.commons.inventory."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.commons.errors import CommonsRootNotFoundError
from science_tool.commons.inventory import build_commons_inventory

FIXTURES = Path(__file__).parent / "fixtures" / "commons"

_NO_DP_ENTITY = (
    "---\n"
    'schema_profile: "science-entity-base/1.0+dataset/1.0"\n'
    'id: "dataset:no-dp"\n'
    'type: "dataset"\n'
    'title: "No datapackage"\n'
    'version: "1.0.0"\n'
    'status: "active"\n'
    'created: "2026-05-13"\n'
    'updated: "2026-05-13"\n'
    'datapackage: "datapackage.yaml"\n'
    'origin: "external"\n'
    'tier: "use-now"\n'
    "access:\n"
    '  level: "public"\n'
    "  verified: true\n"
    '  source_url: "https://example.org"\n'
    "ontology_terms: []\n"
    "tags: []\n"
    "---\nbody\n"
)

_BAD_PAPER = (
    "---\n"
    'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
    'id: "paper:badname"\n'
    'type: "paper"\n'
    'title: "Bad"\n'
    'version: "1.0.0"\n'
    'status: "active"\n'
    'created: "2026-05-13"\n'
    'updated: "2026-05-13"\n'
    'bibkey: "bad-name"\n'
    'authors: ["X"]\n'
    "year: 2025\n"
    'journal: "T"\n'
    "ontology_terms: []\n"
    "tags: []\n"
    "---\nbody\n"
)


def _make_store(tmp_path: Path) -> Path:
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    return root


def test_build_commons_inventory_clean_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    assert payload.schema_version == "2"
    assert payload.project_id == "commons"
    assert payload.project is None
    assert payload.project_path == str(root)
    assert payload.overlays == []
    assert payload.content_hash
    assert payload.audit_hash
    assert {e.id for e in payload.entities} == {
        "dataset:cath-domains",
        "dataset:rnaseq-example",
        "paper:Adams2025",
        "topic:single-cell-foundation-models",
        "theme:research-hygiene",
    }
    assert all(e.scope == "cross-project" for e in payload.entities)
    paper = next(e for e in payload.entities if e.id == "paper:Adams2025")
    assert paper.kind == "paper"
    assert paper.local_id == "Adams2025"
    assert paper.source.adapter == "commons-entity"
    assert paper.data["schema_profile"] == "science-entity-base/1.0+paper/1.0"
    assert sorted(payload.watch_paths) == ["datasets", "papers", "themes", "topics"]


def test_build_commons_inventory_warns_on_malformed_entity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_store(tmp_path)
    bad_path = root / "papers" / "badname.md"
    bad_path.write_text(_BAD_PAPER, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    warning = next(w for w in payload.warnings if w.code == "commons-entity-invalid")
    assert warning.severity == "error"
    assert warning.canonical_id == "paper:badname"
    assert warning.path == str(bad_path)
    assert len(payload.entities) == 5


def test_build_commons_inventory_rejects_scalar_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_store(tmp_path)
    paper_path = root / "papers" / "Adams2025.md"
    paper_path.write_text(
        paper_path.read_text(encoding="utf-8").replace(
            'tags: ["evaluation", "homology"]\n',
            'tags: ["evaluation", "homology"]\naliases: ABC\n',
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    warning = next(w for w in payload.warnings if w.canonical_id == "paper:Adams2025")
    assert warning.code == "commons-entity-invalid"
    assert warning.severity == "error"
    assert warning.path == str(paper_path)
    assert "aliases" in warning.message
    assert "paper:Adams2025" not in {e.id for e in payload.entities}
    assert {alias.alias for alias in payload.aliases}.isdisjoint({"A", "B", "C"})


def test_build_commons_inventory_rejects_scalar_related(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_store(tmp_path)
    paper_path = root / "papers" / "Adams2025.md"
    paper_path.write_text(
        paper_path.read_text(encoding="utf-8").replace(
            'tags: ["evaluation", "homology"]\n',
            'tags: ["evaluation", "homology"]\nrelated: dataset:x\n',
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    warning = next(w for w in payload.warnings if w.canonical_id == "paper:Adams2025")
    assert warning.code == "commons-entity-invalid"
    assert warning.severity == "error"
    assert warning.path == str(paper_path)
    assert "related" in warning.message
    assert "paper:Adams2025" not in {e.id for e in payload.entities}
    related_targets = {reference.target_id for entity in payload.entities for reference in entity.related}
    assert related_targets.isdisjoint(set("dataset:x"))


def test_build_commons_inventory_warns_on_missing_datapackage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_store(tmp_path)
    no_dp = root / "datasets" / "no-dp"
    no_dp.mkdir()
    (no_dp / "entity.md").write_text(_NO_DP_ENTITY, encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    dp_warnings = [w for w in payload.warnings if w.code == "commons-datapackage-invalid"]
    assert len(dp_warnings) == 1
    assert dp_warnings[0].severity == "error"
    assert dp_warnings[0].canonical_id == "dataset:no-dp"
    assert dp_warnings[0].path == str(no_dp)
    assert "dataset:rnaseq-example" in {e.id for e in payload.entities}


def test_build_commons_inventory_missing_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    with pytest.raises(CommonsRootNotFoundError):
        build_commons_inventory()
