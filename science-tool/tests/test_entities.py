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
    create_entity,
    derive_slug,
    generate_entity_id,
    path_for_entity,
    resolve_entity_ref,
    resolve_path_policy,
    validate_slug,
)
from science_tool.graph.sources import load_project_sources


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


def test_create_entity_writes_question_source_and_loads_it(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing", "status": "open"},
    )

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="What explains model family overlap?",
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:q02-what-explains-model-family-overlap"
    assert result.path == tmp_path / "doc/questions/q02-what-explains-model-family-overlap.md"
    assert result.warnings == []
    sources = load_project_sources(tmp_path)
    assert "question:q02-what-explains-model-family-overlap" in {entity.canonical_id for entity in sources.entities}


def test_create_entity_rejects_existing_destination(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    with pytest.raises(EntityCommandError, match="already exists"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="Existing",
            entity_id="question:q01-existing",
            today=date(2026, 4, 28),
        )


def test_create_entity_with_unresolved_related_succeeds_with_warning(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="New Question",
        related=["hypothesis:h01"],
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:q02-new-question"
    assert any("unresolved_reference" in warning for warning in result.warnings)


def test_create_entity_rejects_concept_with_guidance(tmp_path: Path) -> None:
    seed_project(tmp_path)
    with pytest.raises(EntityCommandError, match="graph add concept"):
        create_entity(project_root=tmp_path, kind="concept", title="Local Concept", entity_id="concept:local")


def test_create_entity_prewrite_validation_removes_no_tmp_file(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    with pytest.raises(EntityCommandError, match="prefix"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="Bad",
            entity_id="hypothesis:h01-bad",
            today=date(2026, 4, 28),
        )
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_create_entity_prospective_audit_failure_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    calls = 0

    def fake_audit_project_sources(sources: object) -> tuple[list[dict[str, str]], bool]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return [], False
        return [
            {
                "check": "ambiguous_cross_kind_reference",
                "status": "fail",
                "source": "question:q02-new-question",
                "field": "related",
                "target": "q01",
                "details": "q01 resolves to multiple canonical identities",
            }
        ], True

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    with pytest.raises(EntityCommandError, match="ambiguous_cross_kind_reference"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="New Question",
            related=["q01"],
            today=date(2026, 4, 28),
        )

    assert not (tmp_path / "doc/questions/q02-new-question.md").exists()
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_create_entity_reports_preexisting_audit_failures_as_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "doc/questions/q01-existing.md",
        {"id": "question:q01-existing", "type": "question", "title": "Existing"},
    )
    preexisting_row = {
        "check": "unresolved_reference",
        "status": "fail",
        "source": "question:q01-existing",
        "field": "related",
        "target": "hypothesis:h-missing",
        "details": "pre-existing missing hypothesis",
    }

    def fake_audit_project_sources(sources: object) -> tuple[list[dict[str, str]], bool]:
        return [preexisting_row], True

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="New Question",
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:q02-new-question"
    assert any("pre-existing audit failure" in warning for warning in result.warnings)
