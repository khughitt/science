"""Tests for science_tool.commons.query."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.errors import CommonsEntityError
from science_tool.commons.query import CommonsQuery
from science_tool.commons.registry import RegistryBuilder

FIXTURES = Path(__file__).parent / "fixtures" / "commons"


def _make_store(tmp_path: Path) -> Path:
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    RegistryBuilder(root, CommonsEntityAdapter(root)).rebuild()
    return root


def test_show_returns_record_for_known_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    record = q.show("paper:Adams2025")
    assert record.canonical_id == "paper:Adams2025"
    assert record.frontmatter["bibkey"] == "Adams2025"


def test_show_raises_for_unknown_id(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    with pytest.raises(CommonsEntityError):
        q.show("paper:DoesNotExist")


def test_find_filters_by_type(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    results = q.find("dataset")
    ids = {r.canonical_id for r in results}
    assert ids == {"dataset:cath-domains", "dataset:rnaseq-example"}


def test_find_filters_by_tag(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    results = q.find("dataset", tags=("rnaseq",))
    assert [r.canonical_id for r in results] == ["dataset:rnaseq-example"]


def test_find_tags_use_and_semantics(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    # rnaseq-example has both tags; cath-domains has neither.
    results = q.find("dataset", tags=("rnaseq", "bulk"))
    assert [r.canonical_id for r in results] == ["dataset:rnaseq-example"]
    # AND across tags excludes anything not matching both
    none = q.find("dataset", tags=("rnaseq", "structure"))
    assert none == []


def test_find_filters_by_ontology_term(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    results = q.find("dataset", ontology_terms=("UBERON:0000178",))
    assert [r.canonical_id for r in results] == ["dataset:rnaseq-example"]


def test_find_filters_paper_by_year_range(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    in_range = q.find("paper", year_from=2024, year_to=2026)
    assert [r.canonical_id for r in in_range] == ["paper:Adams2025"]
    out_of_range = q.find("paper", year_from=2027, year_to=2030)
    assert out_of_range == []


def test_find_year_rejects_non_paper(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    with pytest.raises(ValueError, match="year"):
        q.find("dataset", year_from=2020)


def test_find_slug_glob(tmp_path: Path) -> None:
    root = _make_store(tmp_path)
    q = CommonsQuery(root)
    results = q.find("dataset", slug_glob="rnaseq-*")
    assert [r.canonical_id for r in results] == ["dataset:rnaseq-example"]


def test_show_warns_on_stale(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = _make_store(tmp_path)
    # Add a new file post-rebuild
    (root / "topics" / "new-topic.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+topic/1.0"\n'
        'id: "topic:new-topic"\n'
        'type: "topic"\n'
        'title: "New"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    q = CommonsQuery(root)
    q.show("paper:Adams2025")  # still works against old index
    err = capsys.readouterr().err
    assert "stale" in err
    assert "science commons index rebuild" in err


def test_show_without_registry_raises_registry_error(tmp_path: Path) -> None:
    """Querying before `index rebuild` must raise CommonsRegistryError,
    not a bare sqlite3.OperationalError from a phantom auto-created DB."""
    import shutil
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    # Note: no rebuild — registry.sqlite does not exist.
    from science_tool.commons.errors import CommonsRegistryError
    q = CommonsQuery(root)
    with pytest.raises(CommonsRegistryError):
        q.show("paper:Adams2025")


def test_find_without_registry_raises_registry_error(tmp_path: Path) -> None:
    import shutil
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    from science_tool.commons.errors import CommonsRegistryError
    q = CommonsQuery(root)
    with pytest.raises(CommonsRegistryError):
        q.find("paper")


def test_show_with_empty_registry_raises_registry_error(tmp_path: Path) -> None:
    """If registry.sqlite exists but lacks the entities table (e.g., the file
    was created by a stray sqlite3.connect call), surface a CommonsRegistryError."""
    import shutil
    import sqlite3
    root = tmp_path / "commons"
    shutil.copytree(FIXTURES / "valid", root)
    # Touch an empty DB at registry.sqlite (simulates partial init)
    conn = sqlite3.connect(root / "registry.sqlite")
    conn.close()
    from science_tool.commons.errors import CommonsRegistryError
    q = CommonsQuery(root)
    with pytest.raises(CommonsRegistryError):
        q.find("paper")


def test_stale_warning_suppressed_by_env(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _make_store(tmp_path)
    (root / "topics" / "x.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+topic/1.0"\n'
        'id: "topic:x"\n'
        'type: "topic"\n'
        'title: "X"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-05-13"\n'
        'updated: "2026-05-13"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "---\nbody\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("SCIENCE_COMMONS_QUIET_STALE", "1")
    q = CommonsQuery(root)
    q.show("paper:Adams2025")
    err = capsys.readouterr().err
    assert "stale" not in err
