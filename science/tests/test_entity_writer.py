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
    assert "created: 2026-06-16" in text or 'created: "2026-06-16"' in text or "created: '2026-06-16'" in text


def test_append_entity_source_ref_preserves_body_and_updates_timestamp(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    dest.write_text(
        "---\n"
        "id: proposition:existing\n"
        "kind: proposition\n"
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

    assert append_entity_source_ref(dest, "annotation:papers/p.source#a-1", as_of=date(2026, 6, 16)) is True
    text = dest.read_text(encoding="utf-8")
    assert "Hand-authored prose." in text
    assert "annotation:papers/p.source#a-1" in text
    assert "updated: 2026-06-16" in text or 'updated: "2026-06-16"' in text or "updated: '2026-06-16'" in text


def test_append_entity_source_ref_noops_when_ref_exists(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    original = (
        "---\n"
        "id: proposition:existing\n"
        "kind: proposition\n"
        "title: Existing\n"
        "status: draft\n"
        "source_refs:\n"
        '  - "paper:old"\n'
        'updated: "2026-06-01"\n'
        "---\n"
        "Body.\n"
    )
    dest.write_text(original, encoding="utf-8")

    assert append_entity_source_ref(dest, "paper:old", as_of=date(2026, 7, 1)) is False
    assert dest.read_text(encoding="utf-8") == original


def test_render_entity_source_refs_computes_text_without_writing(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    original = (
        "---\n"
        "id: proposition:existing\n"
        "kind: proposition\n"
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
        "updated: 2026-07-01" in rendered or 'updated: "2026-07-01"' in rendered or "updated: '2026-07-01'" in rendered
    )


def test_render_entity_source_refs_noops_when_all_refs_exist(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    original = (
        "---\n"
        "id: proposition:existing\n"
        "kind: proposition\n"
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


def test_render_entity_source_refs_preserves_leading_body_blank_lines(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "existing.md"
    original = (
        "---\n"
        "id: proposition:existing\n"
        "kind: proposition\n"
        "title: Existing\n"
        "status: active\n"
        "source_refs:\n"
        '  - "paper:old"\n'
        'updated: "2026-06-01"\n'
        "---\n"
        "\n\n# Existing\n\nBody.\n"
    )
    dest.write_text(original, encoding="utf-8")

    from science_tool.entities import render_entity_source_refs

    rendered, changed = render_entity_source_refs(dest, ["paper:new"], as_of=date(2026, 7, 1))

    assert changed is True
    assert rendered.split("---\n", 2)[2].startswith("\n\n# Existing\n")


def test_render_entity_frontmatter_updates_sets_supersession_without_writing(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "duplicate.md"
    original = (
        "---\n"
        "id: proposition:duplicate\n"
        "kind: proposition\n"
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
        "updated: 2026-07-01" in rendered or 'updated: "2026-07-01"' in rendered or "updated: '2026-07-01'" in rendered
    )


def test_render_entity_frontmatter_updates_noops_when_values_unchanged(tmp_path: Path):
    root = _project(tmp_path)
    dest = root / "entities" / "propositions" / "duplicate.md"
    original = (
        "---\n"
        "id: proposition:duplicate\n"
        "kind: proposition\n"
        "title: Duplicate\n"
        "status: superseded\n"
        "superseded_by: proposition:canonical\n"
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

    assert changed is False
    assert rendered == original


def test_entity_removal_treats_resynthesized_into_as_managed_frontmatter_ref(tmp_path: Path):
    from science_tool.entities import plan_entity_removal, remove_entity

    root = tmp_path
    (root / "science.yaml").write_text("name: test\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    original = root / "entities" / "propositions" / "broad.md"
    replacement = root / "entities" / "propositions" / "narrow.md"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text(
        "---\n"
        "id: proposition:broad\n"
        "kind: proposition\n"
        "title: Broad\n"
        "status: superseded\n"
        "resynthesized_into:\n"
        "  - proposition:narrow\n"
        "---\n\n"
        "Broad body.\n",
        encoding="utf-8",
    )
    replacement.write_text(
        "---\n"
        "id: proposition:narrow\n"
        "kind: proposition\n"
        "title: Narrow\n"
        "status: active\n"
        "---\n\n"
        "Narrow body.\n",
        encoding="utf-8",
    )

    plan = plan_entity_removal(root, "proposition:narrow")

    assert any(
        hit.path == original and hit.kind == "safe structured reference" and "resynthesized_into" in hit.detail
        for hit in plan.safe_hits
    )

    remove_entity(root, "proposition:narrow")

    assert "resynthesized_into" not in original.read_text(encoding="utf-8")
