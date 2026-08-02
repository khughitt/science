from datetime import date
from pathlib import Path

import pytest

import science_tool.entities as entities
from science_tool.entities import (
    EntityCommandError,
    EntityDegradationError,
    render_entity_frontmatter_updates,
    render_entity_source_refs,
    slug_for_claim_text,
    slug_from_raw,
)


VALID = (
    "---\n"
    "id: proposition:x\n"
    "kind: proposition\n"
    "title: a real claim\n"
    "created: '2026-01-01'\n"
    "updated: '2026-01-01'\n"
    "---\n"
    "body\n"
)

# Empty `title` is the base-2.0 violation 769 of piece 3's 792 repaired records carried:
# `title` is required with minLength 1.
INVALID = VALID.replace("title: a real claim", "title: ''")


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


def test_append_entity_source_ref_is_gone():
    """The obsolete writing adapter is deleted with its production callers."""
    assert not hasattr(entities, "append_entity_source_ref")


def test_render_entity_source_refs_takes_text_not_a_path(tmp_path: Path):
    text = (
        "---\n"
        "id: proposition:x\n"
        "kind: proposition\n"
        "title: a claim\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n"
        "body\n"
    )

    rendered, changed = render_entity_source_refs(
        text,
        ["paper:new"],
        entity_path=tmp_path / "x.md",
        as_of=date(2026, 6, 16),
    )

    assert changed is True
    assert "paper:new" in rendered
    # No file was ever created: the renderer does no filesystem I/O.
    assert not (tmp_path / "x.md").exists()


def test_render_entity_frontmatter_updates_returns_input_text_when_unchanged(tmp_path: Path):
    text = (
        "---\n"
        "id: proposition:x\n"
        "kind: proposition\n"
        "title: a claim\n"
        "status: superseded\n"
        "created: '2026-01-01'\n"
        "updated: '2026-01-01'\n"
        "---\n"
        "body\n"
    )

    rendered, changed = render_entity_frontmatter_updates(
        text,
        {"status": "superseded"},
        entity_path=tmp_path / "x.md",
        as_of=date(2026, 6, 16),
    )

    assert changed is False
    assert rendered == text


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
        dest.read_text(encoding="utf-8"),
        ["paper:old", "annotation:entities/papers/A.source#a1", "paper:A"],
        entity_path=dest,
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

    rendered, changed = render_entity_source_refs(
        dest.read_text(encoding="utf-8"),
        ["paper:old"],
        entity_path=dest,
        as_of=date(2026, 7, 1),
    )

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

    rendered, changed = render_entity_source_refs(
        dest.read_text(encoding="utf-8"),
        ["paper:new"],
        entity_path=dest,
        as_of=date(2026, 7, 1),
    )

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
        dest.read_text(encoding="utf-8"),
        {"status": "superseded", "superseded_by": "proposition:canonical"},
        entity_path=dest,
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
        dest.read_text(encoding="utf-8"),
        {"status": "superseded", "superseded_by": "proposition:canonical"},
        entity_path=dest,
        as_of=date(2026, 7, 1),
    )

    assert changed is False
    assert rendered == original


def test_valid_to_valid_writes(tmp_path: Path):
    rendered, changed = render_entity_frontmatter_updates(
        VALID, {"status": "superseded"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
    )
    assert changed is True
    assert "status: superseded" in rendered


def test_valid_to_invalid_refuses(tmp_path: Path):
    with pytest.raises(EntityDegradationError) as excinfo:
        render_entity_frontmatter_updates(
            VALID, {"title": ""}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
        )
    assert "x.md" in str(excinfo.value)


def test_invalid_to_invalid_writes(tmp_path: Path):
    """A record that already fails base shape stays writable. 183 records across 13 kinds
    fail it today; refusing writes to those would couple this work to migrating them."""
    rendered, changed = render_entity_frontmatter_updates(
        INVALID, {"status": "superseded"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
    )
    assert changed is True
    assert "status: superseded" in rendered


def test_invalid_to_valid_writes(tmp_path: Path):
    """No INTENTIONAL backfill, but a write whose own content happens to satisfy base shape
    is allowed through."""
    rendered, changed = render_entity_frontmatter_updates(
        INVALID, {"title": "a real claim"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
    )
    assert changed is True
    assert "title: a real claim" in rendered


def test_source_refs_renderer_carries_the_same_guard(tmp_path: Path, monkeypatch):
    """Both renderers, not just one: append_entity_source_ref already reaches `hypothesis`
    through promotion LINK, and `hypothesis` is an armed kind.

    This renderer cannot degrade a base-valid record through its own logic -- base 2.0 does
    not constrain `source_refs` at all, and `updated` is always stamped as a valid ISO date.
    Its guard is protection against FUTURE change, so the corruption is injected at the one
    seam both renderers share.
    """
    real_render_markdown = entities._render_markdown

    def corrupt_the_title(frontmatter, body):
        return real_render_markdown({**frontmatter, "title": ""}, body)

    monkeypatch.setattr(entities, "_render_markdown", corrupt_the_title)

    with pytest.raises(EntityDegradationError):
        render_entity_source_refs(
            VALID, ["paper:new"], entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
        )


def test_guard_validates_the_rendered_text_not_the_in_memory_mapping(tmp_path: Path, monkeypatch):
    """§2.1 requires the guard to validate what will be PERSISTED, not the mapping that was
    dumped. The corruption is injected at `_render_markdown` -- after the mapping is built --
    so a guard reading the mapping sees a perfectly good `title` and lets the write through,
    while a guard reading the rendered text refuses.

    A `date(...)` value does NOT discriminate, though the design's §5 suggested it would:
    measured 2026-08-02, `validate_persisted_base_shape` refuses `datetime.date` identically
    whether it reads the in-memory mapping or the reparsed text, because `type: string`
    rejects the date object in both. A test built on it would pass under the mutation and
    certify nothing.
    """
    real_render_markdown = entities._render_markdown

    def corrupt_the_title(frontmatter, body):
        return real_render_markdown({**frontmatter, "title": ""}, body)

    monkeypatch.setattr(entities, "_render_markdown", corrupt_the_title)

    with pytest.raises(EntityDegradationError):
        render_entity_frontmatter_updates(
            VALID, {"status": "superseded"}, entity_path=tmp_path / "x.md", as_of=date(2026, 6, 16)
        )


def test_a_date_object_is_refused_on_an_otherwise_valid_record(tmp_path: Path):
    """Base 2.0 requires `created` to be a string with format: date, and 23 of piece 3's 792
    records were date-quoting alone. This asserts the transition is refused; it does NOT
    certify the round trip -- see the test above for why."""
    with pytest.raises(EntityDegradationError):
        render_entity_frontmatter_updates(
            VALID,
            {"created": date(2026, 3, 4)},
            entity_path=tmp_path / "x.md",
            as_of=date(2026, 6, 16),
        )


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
