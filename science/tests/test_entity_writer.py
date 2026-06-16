from datetime import date
from pathlib import Path

from science_model.propositions import PropositionEntity
from science_tool.entities import (
    append_entity_source_ref,
    slug_for_claim_text,
    slug_from_raw,
    write_entity_file,
)
from science_tool.entities import EntityCommandError
import pytest


def _project(tmp_path: Path) -> Path:
    # resolve_path_policy needs a project; entities/propositions is the proposition home.
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    return tmp_path


def test_slug_from_raw_basic():
    assert slug_from_raw("The cat sat on the mat") == "the-cat-sat-on-the-mat"


def test_slug_for_claim_text_basic():
    assert slug_for_claim_text("The cat sat on the mat") == "the-cat-sat-on-the-mat"


def test_slug_for_claim_text_unsluggable_raises():
    with pytest.raises(EntityCommandError):
        slug_for_claim_text("…")  # normalizes to <2 chars


def test_write_entity_file_places_custom_body(tmp_path: Path):
    root = _project(tmp_path)
    prop = PropositionEntity(id="proposition:demo-claim", title="Demo claim")
    body = "# Demo claim\n\n## Claim\n\nDemo claim.\n\n## Evidence Summary\n\n\n## Caveats\n"
    write_entity_file(prop, project_root=root, body=body, as_of=date(2026, 6, 16))
    dest = root / "entities" / "propositions" / "demo-claim.md"
    text = dest.read_text(encoding="utf-8")
    assert "## Claim\n\nDemo claim." in text
    assert "id: proposition:demo-claim" in text or 'id: "proposition:demo-claim"' in text
    assert (
        "created: 2026-06-16" in text
        or 'created: "2026-06-16"' in text
        or "created: '2026-06-16'" in text
    )


def test_append_entity_source_ref_preserves_body_and_updates_timestamp(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    dest.write_text(
        "---\n"
        "id: proposition:existing\n"
        "type: proposition\n"
        "title: Existing\n"
        "status: draft\n"
        "source_refs:\n"
        '  - "paper:old"\n'
        'created: "2026-06-01"\n'
        'updated: "2026-06-01"\n'
        "---\n"
        "# Existing\n\n## Claim\n\nHand-authored prose.\n",
        encoding="utf-8",
    )

    assert (
        append_entity_source_ref(dest, "annotation:papers/p.source#a-1", as_of=date(2026, 6, 16))
        is True
    )
    text = dest.read_text(encoding="utf-8")
    assert "Hand-authored prose." in text
    assert "annotation:papers/p.source#a-1" in text
    assert (
        "updated: 2026-06-16" in text
        or 'updated: "2026-06-16"' in text
        or "updated: '2026-06-16'" in text
    )
