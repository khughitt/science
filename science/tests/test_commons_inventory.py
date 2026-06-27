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


def test_build_commons_inventory_projects_benchmark_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_store(tmp_path)
    dataset_dir = root / "datasets" / "benchmark-example"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "entity.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+dataset/1.0"\n'
        'id: "dataset:benchmark-example"\n'
        'type: "dataset"\n'
        'title: "Benchmark Example"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-06-27"\n'
        'updated: "2026-06-27"\n'
        'origin: "external"\n'
        'dataset_class: "reference"\n'
        'tier: "track"\n'
        "access:\n"
        '  level: "public"\n'
        "  verified: true\n"
        '  verification_method: "landing-confirmed"\n'
        '  source_url: "https://example.org/benchmark"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "benchmark:\n"
        "  domains: [biology]\n"
        "  modalities: [single-cell-rna-seq]\n"
        "  signal_types: [perturbation]\n"
        "  benchmark_kinds: [perturbation-response]\n"
        "  limitations:\n"
        "    - Portal record; a concrete export becomes a deposit later.\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    # reference dataset: no datapackage.yaml sibling (allowed after Task 5a)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    payload = build_commons_inventory()

    assert payload.warnings == []
    entity = next(e for e in payload.entities if e.id == "dataset:benchmark-example")
    assert entity.scope == "cross-project"
    assert entity.data["benchmark"]["benchmark_kinds"] == ["perturbation-response"]


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


def test_build_commons_inventory_projects_dataset_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_store(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    cath = next(e for e in payload.entities if e.id == "dataset:cath-domains")
    assert cath.data["resources"] == [
        {
            "path": "cath_domains.parquet",
            "hash": "sha256:" + "0" * 64,
            "bytes": 4521339201,
            "format": "parquet",
            "mediatype": "application/vnd.apache.parquet",
            "source": None,
        }
    ]
    rnaseq = next(e for e in payload.entities if e.id == "dataset:rnaseq-example")
    assert rnaseq.data["resources"][0]["mediatype"] is None
    paper = next(e for e in payload.entities if e.id == "paper:Adams2025")
    assert "resources" not in paper.data


def test_build_commons_inventory_reserves_resources_for_datapackages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_store(tmp_path)
    paper_path = root / "papers" / "Adams2025.md"
    paper_path.write_text(
        paper_path.read_text(encoding="utf-8").replace(
            'tags: ["evaluation", "homology"]\n',
            'tags: ["evaluation", "homology"]\nresources: ["not-inventory-resources"]\n',
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    paper = next(e for e in payload.entities if e.id == "paper:Adams2025")
    assert "resources" not in paper.data


def test_build_commons_inventory_warns_on_malformed_datapackage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _make_store(tmp_path)
    (root / "datasets" / "cath-domains" / "datapackage.yaml").write_text("resources: [unclosed\n", encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))
    payload = build_commons_inventory()

    dp_warnings = [w for w in payload.warnings if w.code == "commons-datapackage-invalid"]
    assert len(dp_warnings) == 1
    assert dp_warnings[0].canonical_id == "dataset:cath-domains"
    cath = next(e for e in payload.entities if e.id == "dataset:cath-domains")
    assert "resources" not in cath.data


def test_build_commons_inventory_missing_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "nope"))
    with pytest.raises(CommonsRootNotFoundError):
        build_commons_inventory()


def test_build_commons_inventory_preserves_resource_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A sourced resource's `source` survives end-to-end into the inventory."""
    root = _make_store(tmp_path)
    (root / "datasets" / "cath-domains" / "datapackage.yaml").write_text(
        "name: cath-domains\n"
        'profile: "data-package"\n'
        "resources:\n"
        "  - name: cath_domains\n"
        "    path: cath_domains.parquet\n"
        '    hash: "sha256:' + "0" * 64 + '"\n'
        "    bytes: 4521339201\n"
        '    format: "parquet"\n'
        '    mediatype: "application/vnd.apache.parquet"\n'
        "    source:\n"
        "      type: local\n"
        "      ref: ${OUTPUT_ROOT}/cath/cath_domains.parquet\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    payload = build_commons_inventory()

    cath = next(e for e in payload.entities if e.id == "dataset:cath-domains")
    assert cath.data["resources"][0]["source"] == {
        "type": "local",
        "ref": "${OUTPUT_ROOT}/cath/cath_domains.parquet",
    }
