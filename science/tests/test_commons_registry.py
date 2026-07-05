"""Tests for science_tool.commons.registry."""
from __future__ import annotations

import os
import shutil
import sqlite3
from pathlib import Path

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.registry import (
    REGISTRY_FILENAME,
    REGISTRY_SCHEMA_VERSION,
    RebuildReport,
    RegistryBuilder,
)

FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _make_store(tmp_path: Path, subdir: str = "valid") -> Path:
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / subdir, root)
    return root


def test_rebuild_creates_registry_file(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    assert (root / REGISTRY_FILENAME).is_file()


def test_rebuild_report_counts_indexed_entities(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    report = builder.rebuild()
    assert isinstance(report, RebuildReport)
    assert report.entities_indexed == 5
    assert report.errors == []
    assert report.duration_ms >= 0


def test_rebuild_populates_entities_table(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    conn = sqlite3.connect(root / REGISTRY_FILENAME)
    try:
        rows = conn.execute(
            "SELECT canonical_id, type, slug, title, schema_profile, datapackage_path "
            "FROM entities ORDER BY canonical_id"
        ).fetchall()
    finally:
        conn.close()
    by_id = {r[0]: r for r in rows}
    assert by_id["paper:Adams2025"][1] == "paper"
    assert by_id["paper:Adams2025"][2] == "Adams2025"
    assert by_id["dataset:cath-domains"][5] is not None  # datapackage_path
    assert by_id["paper:Adams2025"][5] is None


def test_rebuild_populates_tags_and_ontology_terms(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    conn = sqlite3.connect(root / REGISTRY_FILENAME)
    try:
        tag_rows = conn.execute(
            "SELECT canonical_id, tag FROM entity_tags WHERE canonical_id = ?",
            ("dataset:rnaseq-example",),
        ).fetchall()
        ont_rows = conn.execute(
            "SELECT canonical_id, term FROM entity_ontology_terms "
            "WHERE canonical_id = ?",
            ("dataset:rnaseq-example",),
        ).fetchall()
    finally:
        conn.close()
    assert {row[1] for row in tag_rows} == {"rnaseq", "bulk"}
    assert {row[1] for row in ont_rows} == {"UBERON:0000178"}


def test_rebuild_writes_schema_meta(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    conn = sqlite3.connect(root / REGISTRY_FILENAME)
    try:
        meta = dict(conn.execute("SELECT key, value FROM schema_meta").fetchall())
    finally:
        conn.close()
    assert meta["schema_version"] == REGISTRY_SCHEMA_VERSION
    assert meta["store_root"] == str(root.resolve())
    assert int(meta["source_count"]) > 0
    assert int(meta["max_source_mtime_ns"]) > 0
    assert len(meta["source_paths_digest"]) == 64  # sha256 hex
    assert "T" in meta["built_at"]  # ISO-8601


def test_rebuild_is_idempotent(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    first = builder.rebuild()
    second = builder.rebuild()
    assert first.entities_indexed == second.entities_indexed


def test_is_stale_false_immediately_after_rebuild(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    assert builder.is_stale() is False


def test_is_stale_true_when_registry_missing(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    assert builder.is_stale() is True


def test_is_stale_detects_file_modification(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    paper = root / "papers" / "Adams2025.md"
    # bump mtime by writing the same content one nanosecond later
    paper.write_text(paper.read_text(encoding="utf-8"), encoding="utf-8")
    os.utime(paper, ns=(paper.stat().st_atime_ns, paper.stat().st_mtime_ns + 1_000_000))
    assert builder.is_stale() is True


def test_is_stale_detects_addition(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    new_topic = root / "topics" / "another-topic.md"
    new_topic.write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+topic/1.0"\n'
        'id: "topic:another-topic"\n'
        'kind: "topic"\n'
        'title: "Another"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    assert builder.is_stale() is True


def test_is_stale_detects_deletion(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    (root / "topics" / "single-cell-foundation-models.md").unlink()
    assert builder.is_stale() is True


def test_is_stale_detects_rename(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    builder = RegistryBuilder(root, CommonsEntityAdapter(root))
    builder.rebuild()
    src = root / "topics" / "single-cell-foundation-models.md"
    dst = root / "topics" / "renamed-topic.md"
    # Keep mtime identical so only the path-digest signal fires
    src_mtime = src.stat().st_mtime_ns
    src.rename(dst)
    os.utime(dst, ns=(src_mtime, src_mtime))
    assert builder.is_stale() is True
