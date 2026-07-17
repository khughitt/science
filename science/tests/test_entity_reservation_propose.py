# science/tests/test_entity_reservation_propose.py
"""Read-only id proposal, and the atomic claim of an exact number."""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.entity_reservation import claim_number_in_dir, propose_number


def _project(tmp_path: Path) -> Path:
    (tmp_path / "science.yaml").write_text("name: t\n", encoding="utf-8")
    (tmp_path / "entities" / "plans").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_propose_is_read_only(tmp_path: Path) -> None:
    root = _project(tmp_path)
    plans = root / "entities" / "plans"

    assert propose_number(root, "plan") == 1

    assert list(plans.iterdir()) == [], "propose created something"


def test_propose_is_idempotent(tmp_path: Path) -> None:
    root = _project(tmp_path)

    assert propose_number(root, "plan") == propose_number(root, "plan") == 1


def test_propose_skips_live_numbers(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "entities" / "plans" / "0001-a.md").write_text("---\nid: plan:0001-a\n---\n", encoding="utf-8")

    assert propose_number(root, "plan") == 2


def test_propose_is_archive_aware(tmp_path: Path) -> None:
    """_max_number cannot see entities/_archive/; propose_number must."""
    root = _project(tmp_path)
    archive_dir = root / "entities" / "_archive" / "plans"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "0007-gone.md").write_text("---\nid: plan:0007-gone\n---\n", encoding="utf-8")
    (root / "entities" / "_archive" / "archive-index.jsonl").write_text(
        '{"op": "archive", "id": "plan:0007-gone", "kind": "plan", '
        '"original_path": "entities/plans/0007-gone.md"}\n',
        encoding="utf-8",
    )

    assert propose_number(root, "plan") == 8


def test_propose_respects_in_flight_sentinels(tmp_path: Path) -> None:
    root = _project(tmp_path)
    (root / "entities" / "plans" / ".0003.reserving").write_text("", encoding="utf-8")

    assert propose_number(root, "plan") == 4


def test_claim_writes_the_exact_number(tmp_path: Path) -> None:
    root = _project(tmp_path)
    plans = root / "entities" / "plans"

    path = claim_number_in_dir(root, "plan", 5, "0005-thing", "---\nid: plan:0005-thing\n---\n\nbody\n")

    assert path == plans / "0005-thing.md"
    assert "id: plan:0005-thing" in path.read_text(encoding="utf-8")
    assert not (plans / ".0005.reserving").exists(), "sentinel leaked"


def test_claim_refuses_a_taken_number(tmp_path: Path) -> None:
    root = _project(tmp_path)
    plans = root / "entities" / "plans"
    (plans / "0005-other.md").write_text("---\nid: plan:0005-other\n---\n", encoding="utf-8")

    with pytest.raises(Exception, match="0005"):
        claim_number_in_dir(root, "plan", 5, "0005-thing", "x")


def test_claim_refuses_a_number_under_an_active_sentinel(tmp_path: Path) -> None:
    root = _project(tmp_path)
    plans = root / "entities" / "plans"
    (plans / ".0005.reserving").write_text("", encoding="utf-8")

    with pytest.raises(Exception, match="0005"):
        claim_number_in_dir(root, "plan", 5, "0005-thing", "x")

    assert (plans / ".0005.reserving").exists(), "another reserver's sentinel was destroyed"


def test_claim_refuses_a_number_archived_since_the_preview(tmp_path: Path) -> None:
    """The claim must check everything propose_number checked, not less.

    Sequence: propose sees 0007 free -> something else claims 0007 and archives
    it -> apply claims 0007. No live file exists, so a directory-only check finds
    it free and REISSUES an id the archive owns.
    """
    root = _project(tmp_path)
    assert propose_number(root, "plan") == 1

    archive_dir = root / "entities" / "_archive" / "plans"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "0001-taken.md").write_text("---\nid: plan:0001-taken\n---\n", encoding="utf-8")
    (root / "entities" / "_archive" / "archive-index.jsonl").write_text(
        '{"op": "archive", "id": "plan:0001-taken", "kind": "plan", '
        '"original_path": "entities/plans/0001-taken.md"}\n',
        encoding="utf-8",
    )
    assert not (root / "entities" / "plans" / "0001-taken.md").exists(), "no live file to collide with"

    with pytest.raises(Exception, match="archived"):
        claim_number_in_dir(root, "plan", 1, "0001-thing", "x")

    assert not (root / "entities" / "plans" / "0001-thing.md").exists()
    assert not (root / "entities" / "plans" / ".0001.reserving").exists(), "sentinel leaked on refusal"
