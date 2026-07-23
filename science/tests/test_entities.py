from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest
import yaml
from _fixtures.entity_helpers import seed_project, write_markdown_entity

from science_tool.entities import (
    EntityCommandError,
    append_entity_note,
    append_note_to_body,
    build_entity_markdown,
    create_entity,
    derive_slug,
    edit_entity,
    find_entity,
    generate_entity_id,
    graph_is_stale,
    list_entities,
    path_for_entity,
    resolve_entity_ref,
    resolve_path_policy,
    validate_slug,
)
from science_tool.graph.sources import load_project_sources
from science_tool.instruments import ValidationVerdict


def test_builtin_path_policy_maps_core_kinds() -> None:
    assert resolve_path_policy("question").root == Path("entities/questions")
    assert resolve_path_policy("hypothesis").root == Path("entities/hypotheses")
    assert resolve_path_policy("discussion").root == Path("entities/discussions")
    assert resolve_path_policy("discussion").strategy == "numeric"
    assert resolve_path_policy("interpretation").root == Path("entities/interpretations")
    assert resolve_path_policy("theme").root == Path("entities/themes")
    assert resolve_path_policy("proposition").root == Path("entities/propositions")
    assert resolve_path_policy("proposition").strategy == "slug"


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


def test_derive_slug_truncates_on_word_boundary_not_mid_word() -> None:
    # Slug is 74 chars; a hard 72-char cut lands inside the final token
    # ("...-myeloma-subclon"). Truncation must back up to the token boundary.
    slug = derive_slug("Convergence reduction versus dysregulation expression in myeloma subclones")
    assert slug == "convergence-reduction-versus-dysregulation-expression-in-myeloma"
    assert len(slug) <= 72
    assert not slug.endswith("-")


def test_derive_slug_single_long_token_falls_back_to_hard_cap() -> None:
    # No interior boundary to back up to: a single token longer than the cap
    # is hard-cut (cannot be split on a word boundary).
    assert derive_slug("a" * 100) == "a" * 72


def test_validate_slug_rejects_bad_override() -> None:
    with pytest.raises(EntityCommandError, match="Invalid slug"):
        validate_slug("Bad_Slug")


def test_generate_entity_id_respects_existing_numeric_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing"},
    )
    assert generate_entity_id(tmp_path, "question", "New Thing", None, None) == "question:0002-new-thing"


def test_generate_entity_id_picks_max_when_multiple_siblings(tmp_path: Path) -> None:
    """Auto-numbering picks max existing numeric prefix + 1, regardless of order."""
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0003-later.md",
        {"id": "question:0003-later", "kind": "question", "title": "Later"},
    )
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-earlier.md",
        {"id": "question:0001-earlier", "kind": "question", "title": "Earlier"},
    )
    assert generate_entity_id(tmp_path, "question", "New Thing", None, None) == "question:0004-new-thing"


def test_generate_entity_id_starts_at_0001_when_no_siblings(tmp_path: Path) -> None:
    """When no siblings exist, numbering starts at 0001."""
    seed_project(tmp_path)
    assert generate_entity_id(tmp_path, "question", "First Question", None, None) == "question:0001-first-question"


def test_generate_entity_id_uses_slug_override(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing"},
    )
    assert generate_entity_id(tmp_path, "question", "Ignored Title", None, "chosen-slug") == "question:0002-chosen-slug"


def test_path_for_entity_couples_filename_and_local_part() -> None:
    assert path_for_entity("question", "question:0002-new-thing", date(2026, 4, 28)) == Path(
        "entities/questions/0002-new-thing.md"
    )
    assert path_for_entity("discussion", "discussion:0001-topic", date(2026, 4, 28)) == Path(
        "entities/discussions/0001-topic.md"
    )


def test_path_for_entity_round_trips_canonical_numeric_id() -> None:
    assert path_for_entity("question", "question:0001-draft", date(2026, 4, 28)) == Path(
        "entities/questions/0001-draft.md"
    )


def test_resolve_entity_ref_distinguishes_similar_local_parts(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-draft-alpha.md",
        {"id": "question:0001-draft-alpha", "kind": "question", "title": "DraftAlpha"},
    )
    write_markdown_entity(
        tmp_path,
        "entities/questions/0002-draft-beta.md",
        {"id": "question:0002-draft-beta", "kind": "question", "title": "DraftBeta"},
    )

    assert resolve_entity_ref(tmp_path, "question:0001-draft-alpha") == "question:0001-draft-alpha"
    assert resolve_entity_ref(tmp_path, "question:0002-draft-beta") == "question:0002-draft-beta"


def test_find_entity_discovers_local_extension_kind(tmp_project_with_design_kind: Path) -> None:
    """A local entity must resolve before its review-scope check can run."""
    write_markdown_entity(
        tmp_project_with_design_kind,
        "entities/design/0001.md",
        {"id": "design:0001", "kind": "design", "title": "Local design"},
    )

    location = find_entity(tmp_project_with_design_kind, "design:0001")

    assert location.kind == "design"
    assert location.rel_path == "entities/design/0001.md"


def test_find_entity_missing_local_extension_reports_project_aware_roots(
    tmp_project_with_design_kind: Path,
) -> None:
    with pytest.raises(EntityCommandError, match="Entity not found: design:9999") as exc_info:
        find_entity(tmp_project_with_design_kind, "design:9999")

    assert "entities/design" in str(exc_info.value)


def test_find_entity_wraps_invalid_policy_config_as_entity_command_error(tmp_path: Path) -> None:
    seed_project(tmp_path)
    config_path = tmp_path / "science.yaml"
    config = yaml.safe_load(config_path.read_text())
    config["entity_schema_version"] = "2"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    write_markdown_entity(
        tmp_path,
        "entities/hypotheses/0001.md",
        {"id": "hypothesis:0001", "kind": "hypothesis", "title": "Pinned lookup"},
    )

    with pytest.raises(EntityCommandError) as exc_info:
        find_entity(tmp_path, "hypothesis:0001")

    message = str(exc_info.value)
    assert message.startswith("Entity policy configuration is not valid")
    assert "entity_schema_version must be 1, 2, or 3 (an integer), not '2'" in message


@pytest.mark.parametrize(
    ("malformed_path", "malformed_yaml"),
    [
        ("science.yaml", "knowledge_profiles: [\n"),
        ("knowledge/sources/local/manifest.yaml", "entity_kinds: [\n"),
    ],
)
def test_find_entity_wraps_malformed_policy_yaml(
    tmp_path: Path,
    malformed_path: str,
    malformed_yaml: str,
) -> None:
    """Policy YAML parse failures stay on the public command-error route."""
    seed_project(tmp_path)
    path = tmp_path / malformed_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(malformed_yaml, encoding="utf-8")

    with pytest.raises(EntityCommandError) as exc_info:
        find_entity(tmp_path, "hypothesis:0001")

    assert type(exc_info.value) is EntityCommandError
    assert str(exc_info.value).startswith("Entity policy configuration is not valid:\n")
    assert isinstance(exc_info.value.__cause__, yaml.YAMLError)


def test_find_entity_wraps_policy_io_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreadable policy source does not leak a raw OS exception."""
    seed_project(tmp_path)

    def unreadable_policies(_project_root: Path):
        raise OSError("policy file is unreadable")

    monkeypatch.setattr("science_tool.entities.entity_policies", unreadable_policies)

    with pytest.raises(EntityCommandError) as exc_info:
        find_entity(tmp_path, "hypothesis:0001")

    assert type(exc_info.value) is EntityCommandError
    assert str(exc_info.value) == (
        "Entity policy configuration is not valid:\npolicy file is unreadable"
    )
    assert isinstance(exc_info.value.__cause__, OSError)


def test_build_entity_markdown_uses_canonical_frontmatter_and_body() -> None:
    text = build_entity_markdown(
        kind="question",
        entity_id="question:0002-new-thing",
        title="New Thing",
        status="open",
        related=["hypothesis:0001-foo"],
        source_refs=[],
        today=date(2026, 4, 28),
    )
    _, frontmatter_text, _ = text.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_text)
    assert frontmatter["id"] == "question:0002-new-thing"
    assert frontmatter["kind"] == "question"
    assert frontmatter["status"] == "open"
    assert frontmatter["related"] == ["hypothesis:0001-foo"]
    assert "# New Thing" in text
    assert "## Why It Matters" in text
    assert "## Notes" not in text


def test_build_entity_markdown_rejects_extra_frontmatter_core_overrides() -> None:
    with pytest.raises(EntityCommandError, match="extra frontmatter cannot override core field"):
        build_entity_markdown(
            kind="evidence-line",
            entity_id="evidence-line:test",
            title="Test",
            status="draft",
            related=[],
            source_refs=[],
            today=date(2026, 6, 27),
            extra_frontmatter={"id": "evidence-line:other", "target": "proposition:p1", "stance": "supports"},
        )


def test_build_entity_markdown_for_discussion_uses_canonical_sections() -> None:
    """fb-2026-04-30-001: discussion bodies must match the science:discuss skill's
    canonical sections (Focus, Current Position, Critical Analysis, Evidence Needed,
    Prioritized Follow-Ups, Synthesis) so the shell is usable as-is."""
    text = build_entity_markdown(
        kind="discussion",
        entity_id="discussion:0001-test",
        title="Test discussion",
        status="active",
        related=[],
        source_refs=[],
        today=date(2026, 5, 3),
    )
    for section in (
        "## Focus",
        "## Current Position",
        "## Critical Analysis",
        "## Evidence Needed",
        "## Prioritized Follow-Ups",
        "## Synthesis",
    ):
        assert section in text, f"discussion shell missing canonical section {section!r}"
    assert "## Summary" not in text
    assert "## Notes" not in text


def test_build_entity_markdown_can_include_optional_template_section() -> None:
    text = build_entity_markdown(
        kind="discussion",
        entity_id="discussion:0001-test",
        title="Test discussion",
        status="active",
        related=[],
        source_refs=[],
        today=date(2026, 5, 3),
        with_sections=["double-blind-addendum"],
    )
    assert "## Double-Blind Addendum" in text


def test_build_entity_markdown_can_strip_template_hints() -> None:
    text = build_entity_markdown(
        kind="discussion",
        entity_id="discussion:0001-test",
        title="Test discussion",
        status="active",
        related=[],
        source_refs=[],
        today=date(2026, 5, 3),
        no_hints=True,
    )
    assert "<!--" not in text


def test_build_entity_markdown_hypothesis_defaults_to_the_ACTIVE_lifecycle() -> None:
    text = build_entity_markdown(
        kind="hypothesis",
        entity_id="hypothesis:0001-default-status",
        title="Default status hypothesis",
        status="active",
        related=[],
        source_refs=[],
        today=date(2026, 5, 28),
    )
    _, frontmatter_text, _ = text.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_text)
    assert frontmatter["status"] == "active"
    assert "phase" not in frontmatter          # the collapsed field is GONE, not merely unused
    assert "## Promotion criteria" not in text


def test_build_entity_markdown_hypothesis_DRAFT_includes_promotion_criteria() -> None:
    # `draft` is what `phase: candidate` folded into -- a trial framing, not yet committed.
    text = build_entity_markdown(
        kind="hypothesis",
        entity_id="hypothesis:0002-draft",
        title="Draft hypothesis",
        status="draft",
        related=[],
        source_refs=[],
        today=date(2026, 5, 28),
        with_sections=["promotion-criteria"],
    )
    _, frontmatter_text, _ = text.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_text)
    assert frontmatter["status"] == "draft"
    assert "## Promotion criteria" in text


def test_template_driven_create_entity_passes_prospective_audit_for_all_migrated_kinds(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-seed.md",
        {"id": "question:0001-seed", "kind": "question", "title": "Seed", "status": "active"},
    )

    cases: list[tuple[str, str, str | None]] = [
        ("question", "What should we test next?", None),
        ("hypothesis", "Template shell hypothesis", "hypothesis:0001-template-shell"),
        ("discussion", "Template shell discussion", None),
        ("interpretation", "Template shell interpretation", None),
        ("theme", "Template shell theme", "theme:0001-template-shell-theme"),
        ("proposition", "Template shell proposition", "proposition:0001-template-shell"),
    ]
    for kind, title, entity_id in cases:
        result = create_entity(
            project_root=tmp_path,
            kind=kind,
            title=title,
            entity_id=entity_id,
            related=[],
            source_refs=[],
            today=date(2026, 5, 3),
        )
        assert result.warnings == []
        assert result.path.exists()


def test_create_entity_fails_when_title_slug_would_truncate(tmp_path: Path) -> None:
    # A long title truncates the auto-derived id slug, dropping the discriminating
    # tail. The older warn-after-write (fb-2026-05-30-012) left the file on disk and
    # the warning arrived too late to act on (fb-2026-07-19-015). Fail early instead:
    # require an explicit --slug and write nothing.
    seed_project(tmp_path)
    long_title = (
        "Disentangling tumor mutational burden from immune infiltration "
        "as competing causes and confounding"
    )
    with pytest.raises(EntityCommandError) as excinfo:
        create_entity(
            project_root=tmp_path,
            kind="discussion",
            title=long_title,
            today=date(2026, 5, 30),
        )

    message = str(excinfo.value)
    assert "--slug" in message
    # The error names the dropped tail so the user knows what was being lost.
    assert "confounding" in message
    # Nothing was written — no orphan stub with the truncated id.
    assert not list((tmp_path / "entities").rglob("*disentangling*"))


def test_create_entity_truncating_title_succeeds_with_explicit_slug(tmp_path: Path) -> None:
    # The fail-early check fires only for auto-derived slugs; an explicit --slug
    # is honored regardless of title length.
    seed_project(tmp_path)
    long_title = (
        "Disentangling tumor mutational burden from immune infiltration "
        "as competing causes and confounding"
    )
    result = create_entity(
        project_root=tmp_path,
        kind="discussion",
        title=long_title,
        slug="tmb-vs-infiltration-confounding",
        today=date(2026, 5, 30),
    )
    assert result.warnings == []
    assert result.entity_id.endswith("tmb-vs-infiltration-confounding")


def test_create_entity_no_truncation_warning_for_short_title(tmp_path: Path) -> None:
    seed_project(tmp_path)
    result = create_entity(
        project_root=tmp_path,
        kind="discussion",
        title="A short discussion title",
        today=date(2026, 5, 30),
    )
    assert result.warnings == []


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
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing", "status": "open"},
    )

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="What explains model family overlap?",
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:0002-what-explains-model-family-overlap"
    assert result.path == tmp_path / "entities/questions/0002-what-explains-model-family-overlap.md"
    assert result.warnings == []
    sources = load_project_sources(tmp_path)
    assert "question:0002-what-explains-model-family-overlap" in {entity.canonical_id for entity in sources.entities}


def test_create_entity_writes_theme_source_and_loads_it(tmp_path: Path) -> None:
    seed_project(tmp_path)

    result = create_entity(
        project_root=tmp_path,
        kind="theme",
        title="Transportability Across Cancer Types",
        entity_id="theme:0001-transportability-across-cancer-types",
        related=[],
        source_refs=[],
        today=date(2026, 5, 4),
    )

    assert result.entity_id == "theme:0001-transportability-across-cancer-types"
    assert result.path == tmp_path / "entities/themes/0001-transportability-across-cancer-types.md"
    assert result.warnings == []
    text = result.path.read_text(encoding="utf-8")
    assert "kind: theme" in text or 'kind: "theme"' in text or "type: 'theme'" in text
    assert "theme_kind: methodological" in text or 'theme_kind: "methodological"' in text
    assert "## Definition" in text
    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}
    assert "theme:0001-transportability-across-cancer-types" in by_id


def test_create_entity_writes_proposition_source_and_loads_it(tmp_path: Path) -> None:
    seed_project(tmp_path)

    # slug strategy: id is derived from title with no numeric prefix
    result = create_entity(
        project_root=tmp_path,
        kind="proposition",
        title="Treatment exposure changes under sparse PSA monitoring",
        related=[],
        source_refs=[],
        today=date(2026, 5, 5),
    )

    assert result.entity_id == "proposition:treatment-exposure-changes-under-sparse-psa-monitoring"
    assert result.path == tmp_path / "entities/propositions/treatment-exposure-changes-under-sparse-psa-monitoring.md"
    assert result.warnings == []
    text = result.path.read_text(encoding="utf-8")
    assert "kind: proposition" in text or 'kind: "proposition"' in text or "type: 'proposition'" in text
    assert "claim_layer: empirical_regularity" in text or 'claim_layer: "empirical_regularity"' in text
    assert "identification_strength: observational" in text or 'identification_strength: "observational"' in text
    assert "## Claim" in text
    assert "## Evidence Summary" in text
    assert "## Caveats" in text
    sources = load_project_sources(tmp_path)
    by_id = {entity.canonical_id: entity for entity in sources.entities}
    assert "proposition:treatment-exposure-changes-under-sparse-psa-monitoring" in by_id


def test_create_entity_rejects_invalid_proposition_status(tmp_path: Path) -> None:
    seed_project(tmp_path)
    with pytest.raises(EntityCommandError, match="Invalid status"):
        create_entity(
            project_root=tmp_path,
            kind="proposition",
            title="Some claim",
            entity_id="proposition:some-claim",
            status="speculative",  # not in the proposition status enum
            related=[],
            source_refs=[],
            today=date(2026, 5, 5),
        )


def test_create_entity_accepts_all_proposition_statuses(tmp_path: Path) -> None:
    valid_statuses = {"draft", "active", "supported", "contested", "weakened", "retired", "superseded"}
    for status in valid_statuses:
        project_root = tmp_path / f"project-{status}"
        project_root.mkdir()
        seed_project(project_root)
        result = create_entity(
            project_root=project_root,
            kind="proposition",
            title=f"Claim under {status}",
            entity_id=f"proposition:claim-{status}",
            status=status,
            related=[],
            source_refs=[],
            today=date(2026, 5, 5),
        )
        assert result.warnings == []


def test_create_entity_rejects_existing_destination(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing"},
    )
    with pytest.raises(EntityCommandError, match="already exists"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="Existing",
            entity_id="question:0001-existing",
            today=date(2026, 4, 28),
        )


def test_create_entity_with_unresolved_related_succeeds_with_warning(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing"},
    )

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="New Question",
        related=["hypothesis:0001-foo"],
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:0002-new-question"
    assert any("unresolved_reference" in warning for warning in result.warnings)


def test_create_entity_unresolved_warning_names_failing_ref(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing"},
    )

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="New Question",
        related=["hypothesis:0099-missing"],
        today=date(2026, 4, 28),
    )

    unresolved = [w for w in result.warnings if "unresolved_reference" in w]
    assert unresolved
    # The warning must name both the failing field and the unresolved ref so the
    # author does not need a separate `science validate --format json` to locate it.
    assert any("related" in w and "hypothesis:0099-missing" in w for w in unresolved)


def test_create_entity_concept_writes_source(tmp_path: Path) -> None:
    seed_project(tmp_path)

    result = create_entity(
        project_root=tmp_path,
        kind="concept",
        title="Local Concept",
        entity_id="concept:local",
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "concept:local"
    assert result.path == tmp_path / "entities/concepts/local.md"
    assert result.path.is_file()
    frontmatter = yaml.safe_load(result.path.read_text(encoding="utf-8").split("---")[1])
    assert frontmatter["id"] == "concept:local"
    assert frontmatter["kind"] == "concept"
    assert frontmatter["status"] == "active"


def test_create_entity_prewrite_validation_removes_no_tmp_file(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing"},
    )
    with pytest.raises(EntityCommandError, match="prefix"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="Bad",
            entity_id="hypothesis:0001-bad",
            today=date(2026, 4, 28),
        )
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_create_entity_fails_closed_on_unwired_audit(tmp_path: Path, monkeypatch) -> None:
    from science_tool.instruments import ValidationVerdict

    seed_project(tmp_path)
    monkeypatch.setattr(
        "science_tool.entities.audit_project_sources",
        lambda _s: ValidationVerdict.unwired(code="x", reason="r"),
    )
    with pytest.raises(EntityCommandError, match="could not run"):
        create_entity(project_root=tmp_path, kind="question", title="New Question")


def test_create_entity_prospective_audit_failure_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing"},
    )
    calls = 0

    def fake_audit_project_sources(sources: object) -> ValidationVerdict[dict[str, str]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ValidationVerdict.passed([])
        return ValidationVerdict.from_has_failures(
            [
                {
                    "check": "ambiguous_cross_kind_reference",
                    "status": "fail",
                    "source": "question:0002-new-question",
                    "field": "related",
                    "target": "0001",
                    "details": "0001 resolves to multiple canonical identities",
                }
            ],
            True,
        )

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    with pytest.raises(EntityCommandError, match="ambiguous_cross_kind_reference"):
        create_entity(
            project_root=tmp_path,
            kind="question",
            title="New Question",
            related=["0001"],
            today=date(2026, 4, 28),
        )

    assert not (tmp_path / "entities/questions/0002-new-question.md").exists()
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_create_entity_reports_preexisting_audit_failures_as_warnings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-existing.md",
        {"id": "question:0001-existing", "kind": "question", "title": "Existing"},
    )
    preexisting_row = {
        "check": "unresolved_reference",
        "status": "fail",
        "source": "question:0001-existing",
        "field": "related",
        "target": "hypothesis:0099-missing",
        "details": "pre-existing missing hypothesis",
    }

    def fake_audit_project_sources(sources: object) -> ValidationVerdict[dict[str, str]]:
        return ValidationVerdict.from_has_failures([preexisting_row], True)

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    result = create_entity(
        project_root=tmp_path,
        kind="question",
        title="New Question",
        today=date(2026, 4, 28),
    )

    assert result.entity_id == "question:0002-new-question"
    assert any("pre-existing audit failure" in warning for warning in result.warnings)


def test_resolve_entity_ref_accepts_canonical_and_unique_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path, "entities/questions/0001-alpha.md", {"id": "question:0001-alpha", "kind": "question", "title": "Alpha"}
    )
    assert resolve_entity_ref(tmp_path, "question:0001-alpha") == "question:0001-alpha"
    assert resolve_entity_ref(tmp_path, "q01") == "question:0001-alpha"


def test_resolve_entity_ref_accepts_question_shortform_for_numbered_local_part(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-alpha.md",
        {"id": "question:0001-alpha", "kind": "question", "title": "Alpha"},
    )

    assert resolve_entity_ref(tmp_path, "q01") == "question:0001-alpha"


def test_resolve_entity_ref_rejects_ambiguous_prefix(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path, "entities/questions/0001-alpha.md", {"id": "question:0001-alpha", "kind": "question", "title": "Alpha"}
    )
    write_markdown_entity(
        tmp_path, "entities/questions/0001-beta.md", {"id": "question:0001-beta", "kind": "question", "title": "Beta"}
    )
    with pytest.raises(EntityCommandError, match="Ambiguous"):
        resolve_entity_ref(tmp_path, "q01")


def test_edit_entity_preserves_unknown_frontmatter_and_adds_related(tmp_path: Path) -> None:
    seed_project(tmp_path)
    path = write_markdown_entity(
        tmp_path,
        "entities/questions/0001-alpha.md",
        {
            "id": "question:0001-alpha",
            "kind": "question",
            "title": "Alpha",
            "status": "open",
            "tags": ["biology"],
            "related": ["hypothesis:0001-foo"],
            "source_refs": [],
            "created": "2026-04-27",
            "updated": "2026-04-27",
        },
        "# Alpha\n\n## Summary\n",
    )

    result = edit_entity(
        tmp_path,
        "question:0001-alpha",
        title="Alpha updated",
        related=["hypothesis:0002-bar"],
        today=date(2026, 4, 28),
    )

    assert any("unresolved_reference" in warning for warning in result.warnings)
    text = path.read_text(encoding="utf-8")
    assert "Alpha updated" in text
    assert "tags:" in text
    assert "hypothesis:0001-foo" in text
    assert "hypothesis:0002-bar" in text
    assert "updated: '2026-04-28'" in text or 'updated: "2026-04-28"' in text or "updated: 2026-04-28" in text


def test_edit_entity_rejects_invalid_question_status(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-alpha.md",
        {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
    )
    with pytest.raises(EntityCommandError, match="Invalid status"):
        edit_entity(tmp_path, "question:0001-alpha", status="closed")


def test_append_entity_note_creates_notes_section_and_updated_field(tmp_path: Path) -> None:
    seed_project(tmp_path)
    path = write_markdown_entity(
        tmp_path,
        "entities/questions/0001-alpha.md",
        {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
        "# Alpha\n\n## Summary\n\nBody.\n",
    )

    append_entity_note(tmp_path, "q01", "Clarified scope.", note_date=date(2026, 4, 28))

    text = path.read_text(encoding="utf-8")
    assert "## Notes\n\n- 2026-04-28: Clarified scope." in text
    assert "updated:" in text


def test_append_entity_note_rejects_blank(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path, "entities/questions/0001-alpha.md", {"id": "question:0001-alpha", "kind": "question", "title": "Alpha"}
    )
    with pytest.raises(EntityCommandError, match="cannot be empty"):
        append_entity_note(tmp_path, "q01", "   ", note_date=date(2026, 4, 28))


def test_edit_entity_prospective_audit_failure_rolls_back(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed_project(tmp_path)
    path = write_markdown_entity(
        tmp_path,
        "entities/questions/0001-alpha.md",
        {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
        "# Alpha\n",
    )
    original = path.read_text(encoding="utf-8")
    calls = 0

    def fake_audit_project_sources(sources: object) -> ValidationVerdict[dict[str, str]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ValidationVerdict.passed([])
        return ValidationVerdict.from_has_failures(
            [
                {
                    "check": "ambiguous_cross_kind_reference",
                    "status": "fail",
                    "source": "question:0001-alpha",
                    "field": "related",
                    "target": "0001",
                    "details": "0001 resolves to multiple canonical identities",
                }
            ],
            True,
        )

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    with pytest.raises(EntityCommandError, match="ambiguous_cross_kind_reference"):
        edit_entity(tmp_path, "q01", related=["0001"], today=date(2026, 4, 28))

    assert path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_append_entity_note_prospective_audit_failure_rolls_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_project(tmp_path)
    path = write_markdown_entity(
        tmp_path,
        "entities/questions/0001-alpha.md",
        {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
        "# Alpha\n",
    )
    original = path.read_text(encoding="utf-8")
    calls = 0

    def fake_audit_project_sources(sources: object) -> ValidationVerdict[dict[str, str]]:
        nonlocal calls
        calls += 1
        if calls == 1:
            return ValidationVerdict.passed([])
        return ValidationVerdict.from_has_failures(
            [
                {
                    "check": "invalid_registered_schema",
                    "status": "fail",
                    "source": "question:0001-alpha",
                    "field": "type",
                    "target": "question",
                    "details": "forced failure",
                }
            ],
            True,
        )

    monkeypatch.setattr("science_tool.entities.audit_project_sources", fake_audit_project_sources)

    with pytest.raises(EntityCommandError, match="invalid_registered_schema"):
        append_entity_note(tmp_path, "q01", "Clarified.", note_date=date(2026, 4, 28))

    assert path.read_text(encoding="utf-8") == original
    assert not list(tmp_path.rglob("*.md.tmp"))


def test_list_entities_filters_kind_and_exact_status(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-alpha.md",
        {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
    )
    write_markdown_entity(
        tmp_path,
        "entities/questions/0002-beta.md",
        {"id": "question:0002-beta", "kind": "question", "title": "Beta", "status": "answered"},
    )
    rows = list_entities(tmp_path, kind="question", status="answered")
    assert [row["id"] for row in rows] == ["question:0002-beta"]


def test_list_entities_orders_by_canonical_id(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/questions/0002-beta.md",
        {"id": "question:0002-beta", "kind": "question", "title": "Beta", "status": "open"},
    )
    write_markdown_entity(
        tmp_path,
        "entities/questions/0001-alpha.md",
        {"id": "question:0001-alpha", "kind": "question", "title": "Alpha", "status": "open"},
    )
    rows = list_entities(tmp_path, kind="question")
    assert [row["id"] for row in rows] == ["question:0001-alpha", "question:0002-beta"]


def test_graph_is_stale_when_source_newer_than_graph(tmp_path: Path) -> None:
    seed_project(tmp_path)
    graph_path = tmp_path / "knowledge" / "graph.trig"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text("", encoding="utf-8")
    source = write_markdown_entity(
        tmp_path, "entities/questions/0001-alpha.md", {"id": "question:0001-alpha", "kind": "question", "title": "Alpha"}
    )
    os.utime(graph_path, (1, 1))
    os.utime(source, (2, 2))
    assert graph_is_stale(tmp_path, graph_path) is True


def test_generate_entity_id_uses_numeric_for_discussion_and_interpretation(tmp_path: Path) -> None:
    seed_project(tmp_path)
    assert (
        generate_entity_id(tmp_path, "discussion", "Planning Session", None, None)
        == "discussion:0001-planning-session"
    )
    assert (
        generate_entity_id(tmp_path, "interpretation", "Run 1 Result", None, None)
        == "interpretation:0001-run-1-result"
    )


def test_generate_entity_id_strips_numeric_prefix_from_numeric_slug(tmp_path: Path) -> None:
    seed_project(tmp_path)
    assert (
        generate_entity_id(tmp_path, "interpretation", "Run 1 Result", None, "0007-run-1-result")
        == "interpretation:0001-run-1-result"
    )


def test_create_entity_auto_generates_discussion_id_without_siblings(tmp_path: Path) -> None:
    seed_project(tmp_path)
    result = create_entity(
        project_root=tmp_path,
        kind="discussion",
        title="Planning Session",
        today=date(2026, 4, 28),
    )
    assert result.entity_id == "discussion:0001-planning-session"
    assert result.path == tmp_path / "entities/discussions/0001-planning-session.md"


def test_create_entity_auto_generates_interpretation_id_without_siblings(tmp_path: Path) -> None:
    seed_project(tmp_path)
    result = create_entity(
        project_root=tmp_path,
        kind="interpretation",
        title="Run 1 Result",
        today=date(2026, 4, 28),
    )
    assert result.entity_id == "interpretation:0001-run-1-result"
    assert result.path == tmp_path / "entities/interpretations/0001-run-1-result.md"


def test_list_entities_hides_superseded_by_default(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/interpretations/0001-active.md",
        {"id": "interpretation:0001-active", "kind": "interpretation", "title": "Active", "status": "active"},
    )
    write_markdown_entity(
        tmp_path,
        "entities/interpretations/0002-old.md",
        {"id": "interpretation:0002-old", "kind": "interpretation", "title": "Old", "status": "superseded"},
    )

    ids = {row["id"] for row in list_entities(tmp_path)}
    assert "interpretation:0001-active" in ids
    assert "interpretation:0002-old" not in ids  # hidden by default

    all_ids = {row["id"] for row in list_entities(tmp_path, include_hidden=True)}
    assert "interpretation:0002-old" in all_ids


def test_list_entities_explicit_status_returns_hidden(tmp_path: Path) -> None:
    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/interpretations/0002-old.md",
        {"id": "interpretation:0002-old", "kind": "interpretation", "title": "Old", "status": "superseded"},
    )
    # An explicit status request is honored even though the status is hidden.
    rows = list_entities(tmp_path, status="superseded")
    assert [row["id"] for row in rows] == ["interpretation:0002-old"]


def test_cli_entity_list_include_hidden_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from click.testing import CliRunner

    from science_tool.cli import main

    seed_project(tmp_path)
    write_markdown_entity(
        tmp_path,
        "entities/interpretations/0002-old.md",
        {"id": "interpretation:0002-old", "kind": "interpretation", "title": "Old", "status": "superseded"},
    )
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    default = runner.invoke(main, ["entity", "list", "--format", "json"])
    assert default.exit_code == 0, default.output
    assert "interpretation:0002-old" not in default.output

    shown = runner.invoke(main, ["entity", "list", "--include-hidden", "--format", "json"])
    assert shown.exit_code == 0, shown.output
    assert "interpretation:0002-old" in shown.output


def test_create_prose_source_entity(tmp_path):
    import yaml

    from science_tool.entities import create_entity

    result = create_entity(
        project_root=tmp_path,
        kind="prose-source",
        title="Example Prose Source",
        slug="example-prose-source",
        no_hints=True,
    )

    path = tmp_path / "entities" / "prose-sources" / "example-prose-source.md"
    assert result.entity_id == "prose-source:example-prose-source"
    assert result.path == path
    text = path.read_text(encoding="utf-8")
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    assert frontmatter["id"] == "prose-source:example-prose-source"
    assert frontmatter["kind"] == "prose-source"
    assert frontmatter["status"] == "active"
