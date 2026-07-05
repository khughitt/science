# science/tests/test_archive_frozen_edits.py
"""Archived members are frozen (G1): tool-mediated content edits are rejected with
a helpful 'unarchive first' error, so the index digest_insight cannot silently
drift from the relocated file. Editing an archived id was already incidentally
blocked (the live scan skips _archive/, so find_entity raised a bare
'Entity not found'); this turns that into an explicit, intentional contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.archive import archive_entities
from science_tool.entities import EntityCommandError, append_entity_note, edit_entity


def _write(root: Path, name: str, fm: str) -> None:
    d = root / "entities" / "interpretations"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.md").write_text(fm, encoding="utf-8")


def _seed_archived(root: Path) -> str:
    _write(root, "0001-x", "---\nid: interpretation:0001-x\nkind: interpretation\nstatus: superseded\n---\nbody\n")
    archive_entities(root, apply=True, now="T1")
    return "interpretation:0001-x"


def test_edit_entity_rejects_archived_member(tmp_path: Path) -> None:
    eid = _seed_archived(tmp_path)
    with pytest.raises(EntityCommandError, match="archived"):
        edit_entity(tmp_path, eid, title="new title")


def test_append_note_rejects_archived_member(tmp_path: Path) -> None:
    eid = _seed_archived(tmp_path)
    with pytest.raises(EntityCommandError, match="archived"):
        append_entity_note(tmp_path, eid, "a note")


def test_edit_rejects_archived_member_by_alias(tmp_path: Path) -> None:
    # The guard resolves through the index's alias/same_as keys, so an edit that
    # names the archived entity by an alias is blocked too.
    _write(
        tmp_path,
        "0001-x",
        "---\nid: interpretation:0001-x\nkind: interpretation\nstatus: superseded\n"
        "aliases:\n  - interpretation:old-x\n---\nbody\n",
    )
    archive_entities(tmp_path, apply=True, now="T1")
    with pytest.raises(EntityCommandError, match="archived"):
        edit_entity(tmp_path, "interpretation:old-x", title="new title")


def test_unknown_ref_is_not_treated_as_archived(tmp_path: Path) -> None:
    # Narrowness guard: a ref absent from the archive index falls through to the
    # normal 'Entity not found' path, NOT the archived rejection.
    _seed_archived(tmp_path)
    with pytest.raises(EntityCommandError, match="not found"):
        edit_entity(tmp_path, "interpretation:9999-other", title="x")
