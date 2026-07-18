"""Corpus-eligibility and date-coercion tests for adaptive rotation."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pytest
from _fixtures.entity_helpers import write_markdown_entity

from science_tool.curate.rotation import RotationError, eligible_corpus


def _make_project(tmp_path: Path, files: list[tuple[str, dict[str, object]]]) -> Path:
    root = tmp_path / "proj"
    (root / "entities").mkdir(parents=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: core\n", encoding="utf-8")
    for rel, frontmatter in files:
        write_markdown_entity(root, rel, frontmatter)
    return root


def test_eligible_includes_plan_excludes_dataset(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            ("entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"}),
            ("entities/datasets/d1.md", {"id": "dataset:d1", "kind": "dataset", "title": "D", "status": "active"}),
        ],
    )
    ids = {e.id for e in eligible_corpus(root)}
    assert ids == {"plan:0001"}  # dataset is curation_scope none


def test_eligible_excludes_closed_lifecycle_statuses(tmp_path: Path) -> None:
    files = [
        (f"entities/plans/{i}.md", {"id": f"plan:{i}", "kind": "plan", "title": "P", "status": s})
        for i, s in enumerate(["complete", "superseded", "retired", "archived", "abandoned", "deprecated", "active"])
    ]
    root = _make_project(tmp_path, files)
    ids = {e.id for e in eligible_corpus(root)}
    assert ids == {"plan:6"}  # only the active plan survives


def test_eligible_excludes_unregistered_directory(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"})],
    )
    # A markdown file under a directory that is not a registered policy home.
    write_markdown_entity(root, "entities/random/x.md", {"id": "plan:x", "kind": "plan", "title": "X", "status": "active"})
    ids = {e.id for e in eligible_corpus(root)}
    assert ids == {"plan:0001"}


def test_eligible_excludes_archive(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"})],
    )
    # An archived plan under the reserved _archive/ subtree must never be eligible.
    write_markdown_entity(
        root,
        "entities/plans/_archive/old.md",
        {"id": "plan:old", "kind": "plan", "title": "Old", "status": "active"},
    )
    ids = {e.id for e in eligible_corpus(root)}
    assert ids == {"plan:0001"}


def test_eligible_reads_dates(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {
                    "id": "plan:0001",
                    "kind": "plan",
                    "title": "P",
                    "status": "active",
                    "created": "2026-01-02",
                    "review_state": {"last_reviewed": "2026-05-06"},
                },
            )
        ],
    )
    (entity,) = eligible_corpus(root)
    assert entity.created == date(2026, 1, 2)
    assert entity.last_reviewed == date(2026, 5, 6)


def test_eligible_accepts_yaml_date_object(tmp_path: Path) -> None:
    # An unquoted YAML date deserializes to a Python date object, not a string.
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active", "created": date(2026, 3, 4)},
            )
        ],
    )
    (entity,) = eligible_corpus(root)
    assert entity.created == date(2026, 3, 4)


def test_eligible_rejects_datetime(tmp_path: Path) -> None:
    # A YAML timestamp deserializes to a datetime; the date-only contract rejects it.
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {
                    "id": "plan:0001",
                    "kind": "plan",
                    "title": "P",
                    "status": "active",
                    "created": datetime(2026, 3, 4, 10, 0, 0),
                },
            )
        ],
    )
    with pytest.raises(RotationError) as excinfo:
        eligible_corpus(root)
    assert "plan:0001" in str(excinfo.value)


@pytest.mark.parametrize("bad", ["20260718", "2026-W29-6", "2026-7-8"])
def test_eligible_rejects_noncanonical_date_strings(tmp_path: Path, bad: str) -> None:
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active", "created": bad},
            )
        ],
    )
    with pytest.raises(RotationError) as excinfo:
        eligible_corpus(root)
    assert "plan:0001" in str(excinfo.value)


def test_eligible_missing_dates_are_none(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [("entities/plans/0001.md", {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active"})],
    )
    (entity,) = eligible_corpus(root)
    assert entity.created is None
    assert entity.last_reviewed is None


def test_eligible_malformed_date_raises_with_context(tmp_path: Path) -> None:
    root = _make_project(
        tmp_path,
        [
            (
                "entities/plans/0001.md",
                {"id": "plan:0001", "kind": "plan", "title": "P", "status": "active", "created": "not-a-date"},
            )
        ],
    )
    with pytest.raises(RotationError) as excinfo:
        eligible_corpus(root)
    message = str(excinfo.value)
    # All three context fields: entity id, path, and field name.
    assert "plan:0001" in message
    assert "created" in message
    assert "0001.md" in message  # path fragment
