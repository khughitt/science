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


def test_scan_raises_layout_error_for_dataset_missing_datapackage(tmp_path: Path) -> None:
    root = _make_store(tmp_path, "invalid/dataset-missing-datapackage")
    adapter = CommonsEntityAdapter(root)
    with pytest.raises(CommonsLayoutError) as exc_info:
        list(adapter.scan())
    assert "datapackage.yaml" in exc_info.value.reason
    assert exc_info.value.path == root / "datasets" / "no-dp"


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
