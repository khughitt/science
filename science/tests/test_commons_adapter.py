"""Tests for science_tool.commons.adapter."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.commons.adapter import (
    CommonsEntityAdapter,
    CommonsEntityRecord,
)
from science_tool.commons.errors import CommonsEntityError, CommonsLayoutError

FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _make_store(tmp_path: Path, source_subdir: str) -> Path:
    """Copy a fixture subtree into tmp_path/commons and return that root."""
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / source_subdir, root)
    return root


def test_scan_yields_records_for_all_valid_entities(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    canonical_ids = {r.canonical_id for r in records}
    assert canonical_ids == {
        "dataset:cath-domains",
        "dataset:rnaseq-example",
        "paper:Adams2025",
        "topic:single-cell-foundation-models",
        "theme:research-hygiene",
    }
    assert errors == []


def test_scan_skips_hidden_and_meta_files(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    # Sprinkle distractors
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("ignore me")
    (root / ".migrations").mkdir()
    (root / ".migrations" / "log.json").write_text("[]")
    (root / "registry.sqlite").write_text("ignore me")
    (root / "datasets" / "__pycache__").mkdir()
    (root / "datasets" / "__pycache__" / "x.pyc").write_text("x")

    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    assert len(records) == 5  # same as the clean valid case


def test_scan_yields_entity_error_for_dataset_missing_datapackage(
    tmp_path: Path,
) -> None:
    root = _make_store(tmp_path, "valid")
    no_dp = root / "datasets" / "no-dp"
    no_dp.mkdir()
    (no_dp / "entity.md").write_text(
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
        "---\nbody\n",
        encoding="utf-8",
    )
    items = list(CommonsEntityAdapter(root).scan())
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    assert len(errors) == 1
    assert errors[0].path == no_dp
    assert errors[0].canonical_id == "dataset:no-dp"
    assert isinstance(errors[0].cause, CommonsLayoutError)
    assert "dataset:rnaseq-example" in {r.canonical_id for r in records}
    assert "paper:Adams2025" in {r.canonical_id for r in records}


def test_record_captures_paths_and_mtime(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    by_id = {
        r.canonical_id: r
        for r in adapter.scan()
        if isinstance(r, CommonsEntityRecord)
    }
    cath = by_id["dataset:cath-domains"]
    assert cath.body_path == root / "datasets" / "cath-domains" / "entity.md"
    assert cath.datapackage_path == root / "datasets" / "cath-domains" / "datapackage.yaml"
    assert cath.type == "dataset"
    assert cath.slug == "cath-domains"
    assert cath.mtime_ns > 0

    paper = by_id["paper:Adams2025"]
    assert paper.body_path == root / "papers" / "Adams2025.md"
    assert paper.datapackage_path is None
    assert paper.type == "paper"
    assert paper.slug == "Adams2025"


def test_scan_populates_frontmatter_and_schema_profile(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    by_id = {
        r.canonical_id: r
        for r in adapter.scan()
        if isinstance(r, CommonsEntityRecord)
    }
    paper = by_id["paper:Adams2025"]
    assert paper.schema_profile == "science-entity-base/1.0+paper/1.0"
    assert paper.frontmatter["bibkey"] == "Adams2025"
    assert paper.frontmatter["year"] == 2025

    rnaseq = by_id["dataset:rnaseq-example"]
    assert rnaseq.schema_profile.endswith("+bio.rnaseq/1.0")
    assert rnaseq.frontmatter["species"] == "Homo sapiens"


def test_scan_yields_error_for_bad_bibkey(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "invalid/paper-bad-bibkey")
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    assert records == []
    assert len(errors) == 1
    assert errors[0].path == root / "papers" / "badname.md"


def test_scan_yields_error_for_bad_schema_profile(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "invalid/topic-bad-profile")
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    assert len(errors) == 1
    assert errors[0].path == root / "topics" / "x.md"


def test_scan_continues_after_per_entity_error(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    # Inject a bad paper (hyphenated bibkey violates the paper-mixin pattern)
    # alongside good ones.
    bad = root / "papers" / "bad-name.md"
    bad.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:bad-name"\n'
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
        "---\nbody\n",
        encoding="utf-8",
    )
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    records = [it for it in items if isinstance(it, CommonsEntityRecord)]
    errors = [it for it in items if isinstance(it, CommonsEntityError)]
    assert "paper:Adams2025" in {r.canonical_id for r in records}
    assert len(errors) == 1
    assert errors[0].path == bad


def test_scan_rejects_id_path_mismatch(tmp_path: Path) -> None:
    """A schema-valid paper at papers/Adams2025.md whose frontmatter says
    id: paper:Other2025 must be reported as an error — not silently indexed
    under the path-derived id."""
    root = _make_store(tmp_path, "valid")
    impostor = root / "papers" / "Adams2025.md"
    impostor.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:Other2025"\n'        # contradicts path-derived paper:Adams2025
        'type: "paper"\n'
        'title: "Impostor"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "Other2025"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    paper_records = [
        r for r in items
        if isinstance(r, CommonsEntityRecord) and r.type == "paper"
    ]
    paper_errors = [
        e for e in items
        if isinstance(e, CommonsEntityError) and e.path == impostor
    ]
    assert paper_records == [], "impostor should not appear in records"
    assert len(paper_errors) == 1
    assert "does not match path-derived" in str(paper_errors[0].cause)


def test_scan_rejects_type_path_mismatch(tmp_path: Path) -> None:
    """An entity in papers/Foo2025.md claiming type: dataset must error."""
    root = _make_store(tmp_path, "valid")
    impostor = root / "papers" / "Adams2025.md"
    impostor.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+paper/1.0"\n'
        'id: "paper:Adams2025"\n'
        'type: "dataset"\n'
        'title: "Misfiled"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        'bibkey: "Adams2025"\n'
        'authors: ["X"]\n'
        "year: 2025\n"
        'journal: "T"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    adapter = CommonsEntityAdapter(root)
    items = list(adapter.scan())
    errors = [e for e in items if isinstance(e, CommonsEntityError) and e.path == impostor]
    # Either the schema mixin guards this directly, or our consistency check fires.
    assert errors, "type mismatch must produce an error"
    records = [r for r in items if isinstance(r, CommonsEntityRecord) and r.body_path == impostor]
    assert records == []


def test_load_returns_record_for_known_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    record = adapter.load("paper:Adams2025")
    assert isinstance(record, CommonsEntityRecord)
    assert record.canonical_id == "paper:Adams2025"


def test_load_dataset_missing_datapackage_raises_layout_error(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "invalid/dataset-missing-datapackage")
    adapter = CommonsEntityAdapter(root)
    with pytest.raises(CommonsLayoutError, match="datapackage.yaml"):
        adapter.load("dataset:no-dp")


def test_load_raises_entity_error_for_unknown_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    with pytest.raises(CommonsEntityError) as exc_info:
        adapter.load("paper:DoesNotExist")
    assert exc_info.value.canonical_id == "paper:DoesNotExist"


def test_load_raises_on_malformed_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "valid")
    adapter = CommonsEntityAdapter(root)
    with pytest.raises(CommonsEntityError):
        adapter.load("not-a-canonical-id")
