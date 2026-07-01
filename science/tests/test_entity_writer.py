from datetime import date
from pathlib import Path

import pytest
from science_model.propositions import PropositionEntity

from science_tool.entities import (
    EntityCommandError,
    append_entity_source_ref,
    slug_for_claim_text,
    slug_from_raw,
    write_entity_file,
)


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


def test_render_entity_source_refs_computes_text_without_writing(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    original = (
        "---\n"
        "id: proposition:existing\n"
        "type: proposition\n"
        "title: Existing\n"
        "status: active\n"
        "source_refs:\n"
        '  - "paper:old"\n'
        'created: "2026-06-01"\n'
        'updated: "2026-06-01"\n'
        "---\n"
        "# Existing\n\nHand-authored prose.\n"
    )
    dest.write_text(original, encoding="utf-8")

    from science_tool.entities import render_entity_source_refs

    rendered, changed = render_entity_source_refs(
        dest,
        ["paper:old", "annotation:entities/papers/A.source#a1", "paper:A"],
        as_of=date(2026, 7, 1),
    )

    assert changed is True
    assert dest.read_text(encoding="utf-8") == original
    assert "Hand-authored prose." in rendered
    assert rendered.index("paper:old") < rendered.index("annotation:entities/papers/A.source#a1")
    assert rendered.index("annotation:entities/papers/A.source#a1") < rendered.index("paper:A")
    assert rendered.count("paper:old") == 1
    assert rendered.count("annotation:entities/papers/A.source#a1") == 1
    assert rendered.count("paper:A") == 1
    assert (
        "updated: 2026-07-01" in rendered
        or 'updated: "2026-07-01"' in rendered
        or "updated: '2026-07-01'" in rendered
    )


def test_render_entity_source_refs_noops_when_all_refs_exist(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    original = (
        "---\n"
        "id: proposition:existing\n"
        "type: proposition\n"
        "title: Existing\n"
        "status: active\n"
        "source_refs:\n"
        '  - "paper:old"\n'
        'updated: "2026-06-01"\n'
        "---\n"
        "Body.\n"
    )
    dest.write_text(original, encoding="utf-8")

    from science_tool.entities import render_entity_source_refs

    rendered, changed = render_entity_source_refs(dest, ["paper:old"], as_of=date(2026, 7, 1))

    assert changed is False
    assert rendered == original


def test_render_entity_frontmatter_updates_sets_supersession_without_writing(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "duplicate.md"
    original = (
        "---\n"
        "id: proposition:duplicate\n"
        "type: proposition\n"
        "title: Duplicate\n"
        "status: active\n"
        'updated: "2026-06-01"\n'
        "---\n"
        "Duplicate body.\n"
    )
    dest.write_text(original, encoding="utf-8")

    from science_tool.entities import render_entity_frontmatter_updates

    rendered, changed = render_entity_frontmatter_updates(
        dest,
        {"status": "superseded", "superseded_by": "proposition:canonical"},
        as_of=date(2026, 7, 1),
    )

    assert changed is True
    assert dest.read_text(encoding="utf-8") == original
    assert "Duplicate body." in rendered
    assert "status: superseded" in rendered
    assert "superseded_by: proposition:canonical" in rendered
    assert (
        "updated: 2026-07-01" in rendered
        or 'updated: "2026-07-01"' in rendered
        or "updated: '2026-07-01'" in rendered
    )
