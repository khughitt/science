from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
import yaml

from _fixtures.entity_helpers import seed_project, write_markdown_entity
from science_tool.entities import (
    EntityCommandError,
    append_note_to_body,
    build_entity_markdown,
    derive_slug,
    generate_entity_id,
    path_for_entity,
    resolve_entity_ref,
    resolve_path_policy,
    validate_slug,
)


def test_builtin_path_policy_maps_core_kinds() -> None:
    assert resolve_path_policy("question").root == Path("doc/questions")
    assert resolve_path_policy("hypothesis").root == Path("specs/hypotheses")
    assert resolve_path_policy("discussion").filename == "date-local-part"
    assert resolve_path_policy("interpretation").filename == "date-local-part"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("What explains model family overlap?", "what-explains-model-family-overlap"),
        ("Model-family overlap: v2", "model-family-overlap-v2"),
        ("Café response -- Δ", "cafe-response"),
        ("the and what", "the-and-what"),
    ],
)
def test_derive_slug_is_deterministic(title: str, expected: str) -> None:
    assert derive_slug(title) == expected


def test_derive_slug_rejects_empty_or_too_short_values() -> None:
    with pytest.raises(EntityCommandError, match="requires --slug"):
        derive_slug("???")
    with pytest.raises(EntityCommandError, match="requires --slug"):
        derive_slug("Q?")


def test_derive_slug_truncates_to_72_characters_without_trailing_hyphen() -> None:
    slug = derive_slug(" ".join(["model"] * 30))
    assert len(slug) <= 72
    assert not slug.endswith("-")


def test_derive_slug_truncation_boundary_is_stable() -> None:
    assert derive_slug(("a" * 71) + " b") == "a" * 71


def test_validate_slug_rejects_bad_override() -> None:
    with pytest.raises(EntityCommandError, match="Invalid slug"):
        validate_slug("Bad_Slug")


def test_generate_entity_id_respects_existing_q_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    assert generate_entity_id(tmp_path, "question", "New Thing", None, None) == "question:q02-new-thing"


def test_generate_entity_id_respects_existing_numeric_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/01-existing.md",
        {"id": "question:01-existing", "type": "question", "title": "Existing"},
    )
    assert generate_entity_id(tmp_path, "question", "New Thing", None, None) == "question:02-new-thing"


def test_generate_entity_id_rejects_mixed_prefixes(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(tmp_path, "doc/questions/q01-a.md", {"id": "question:q01-a", "type": "question", "title": "A"})
    write_markdown_entity(tmp_path, "doc/questions/02-b.md", {"id": "question:02-b", "type": "question", "title": "B"})
    with pytest.raises(EntityCommandError, match="Mixed ID conventions"):
        generate_entity_id(tmp_path, "question", "New Thing", None, None)


def test_generate_entity_id_rejects_empty_siblings(tmp_path: Path) -> None:
    seed_project(tmp_path)
    with pytest.raises(EntityCommandError, match="No existing question siblings"):
        generate_entity_id(tmp_path, "question", "First Question", None, None)


def test_generate_entity_id_uses_slug_override(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    assert generate_entity_id(tmp_path, "question", "Ignored Title", None, "chosen-slug") == "question:q02-chosen-slug"


def test_path_for_entity_couples_filename_and_local_part() -> None:
    assert path_for_entity("question", "question:q02-new-thing", date(2026, 4, 28)) == Path(
        "doc/questions/q02-new-thing.md"
    )
    assert path_for_entity("discussion", "discussion:2026-04-28-topic", date(2026, 4, 28)) == Path(
        "doc/discussions/2026-04-28-topic.md"
    )


def test_path_for_entity_round_trips_dot_bearing_manual_id() -> None:
    assert path_for_entity("question", "question:q01.draft", date(2026, 4, 28)) == Path(
        "doc/questions/q01.draft.md"
    )


def test_resolve_entity_ref_distinguishes_dot_and_dash_local_parts(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01.draft.md",
        {"id": "question:q01.draft", "type": "question", "title": "Dot"},
    )
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-draft.md",
        {"id": "question:q01-draft", "type": "question", "title": "Dash"},
    )

    assert resolve_entity_ref(tmp_path, "q01.draft") == "question:q01.draft"
    assert resolve_entity_ref(tmp_path, "q01-draft") == "question:q01-draft"


def test_build_entity_markdown_uses_canonical_frontmatter_and_body() -> None:
    text = build_entity_markdown(
        kind="question",
        entity_id="question:q02-new-thing",
        title="New Thing",
        status="open",
        related=["hypothesis:h01"],
        source_refs=[],
        today=date(2026, 4, 28),
    )
    _, frontmatter_text, _ = text.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_text)
    assert frontmatter["id"] == "question:q02-new-thing"
    assert frontmatter["type"] == "question"
    assert frontmatter["status"] == "open"
    assert frontmatter["related"] == ["hypothesis:h01"]
    assert "# New Thing" in text
    assert "## Notes" in text


def test_append_note_to_body_creates_peer_notes_section() -> None:
    body = "# Title\n\n## Summary\n\nBody."
    updated = append_note_to_body(body, "- 2026-04-28: Clarified.")
    assert updated == "# Title\n\n## Summary\n\nBody.\n\n## Notes\n\n- 2026-04-28: Clarified."


def test_append_note_to_body_inserts_before_next_peer_heading() -> None:
    body = "# Title\n\n## Summary\n\nBody.\n\n## Notes\n\n- 2026-04-27: Earlier.\n\n## Evidence\n\nDetails."
    updated = append_note_to_body(body, "- 2026-04-28: Later.")
    assert "- 2026-04-28: Later.\n\n## Evidence" in updated
