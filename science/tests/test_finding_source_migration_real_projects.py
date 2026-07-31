"""Step 3 -- the `finding` source migration, asserted on the REAL file.

The procedure's rule for this slice is exactly `updated = created`, with migration date,
file mtime, and current date rejected BY NAME. All four candidates produce a schema-valid
`format: date` string, so schema validation cannot tell honest provenance from fabrication.
These tests therefore assert the provenance SEMANTICS directly and mutation-test each
rejected alternative, which is the only thing that can distinguish them.

The slice added a second field to the same migration: `status`. The 149 rows authored none,
and `mixin-finding-1.0` requires it -- see the ruling in
docs/plans/2026-07-30-schema-closure-finding-slice-inventory.md.
"""

import datetime
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.real_projects

SOURCE = (
    Path.home()
    / "d"
    / "natural-systems"
    / "knowledge"
    / "sources"
    / "project_specific"
    / "finding.yaml"
)
ROW_COUNT = 149
AUTHORED_CREATED = "2026-04-30"


def _rows() -> list[dict]:
    if not SOURCE.exists():
        pytest.fail(
            f"{SOURCE} is missing. Under `-m real_projects` a missing project FAILS "
            "rather than skips, so '149 rows migrated' cannot silently degrade into "
            "'the file we could find was fine'."
        )
    return json.loads(SOURCE.read_text())["finding"]


def test_the_row_count_is_the_one_the_inventory_froze():
    assert len(_rows()) == ROW_COUNT


def test_every_row_carries_updated_equal_to_created():
    """The migration rule itself."""
    rows = _rows()
    assert all(r["updated"] == r["created"] for r in rows)


def test_every_row_still_carries_the_authored_created_date():
    """The migration adds; it must not have rewritten what the author wrote."""
    assert {r["created"] for r in _rows()} == {AUTHORED_CREATED}


def test_updated_is_not_the_migration_date():
    """Rejected alternative 1, by name.

    The migration ran on 2026-07-30. A row stamped with that date would claim the audit
    verdict was revised on the day a schema slice touched the file, which is false.
    """
    assert {r["updated"] for r in _rows()} == {AUTHORED_CREATED}
    assert "2026-07-30" not in {r["updated"] for r in _rows()}


def test_updated_is_not_the_file_mtime():
    """Rejected alternative 2, by name.

    The mtime moves every time anything rewrites the file -- including this migration --
    so it records when the CONTAINER changed, never when the record did.
    """
    mtime = datetime.date.fromtimestamp(SOURCE.stat().st_mtime).isoformat()
    assert mtime != AUTHORED_CREATED, (
        "the file's mtime coincides with the authored created date, so this test cannot "
        "currently distinguish the two -- it is not evidence either way today"
    )
    assert mtime not in {r["updated"] for r in _rows()}


def test_updated_is_not_the_current_date():
    """Rejected alternative 3, by name. Recomputed per run, so it cannot go stale."""
    today = datetime.date.today().isoformat()
    if today == AUTHORED_CREATED:
        pytest.fail("today == the authored created date; this probe is blind right now")
    assert today not in {r["updated"] for r in _rows()}


def test_every_row_carries_the_backfilled_status():
    """The slice's own ruling. `active` is the descriptor's default_status for `finding`."""
    assert {r["status"] for r in _rows()} == {"active"}


def test_the_migration_added_exactly_two_keys_per_row():
    """Guards against a migration that quietly carried a third change.

    The frozen pre-migration key set is what step 1 measured over all 149 rows.
    """
    expected = {
        "canonical_id",
        "kind",
        "title",
        "status",
        "profile",
        "source_path",
        "created",
        "updated",
        "description",
        "evidence_refs",
    }
    assert all(set(r) == expected for r in _rows())


def test_the_source_path_still_points_at_this_file():
    """`source_path` normalizes to `file_path`, which the mixin admits as authored."""
    assert {r["source_path"] for r in _rows()} == {
        "knowledge/sources/project_specific/finding.yaml"
    }
