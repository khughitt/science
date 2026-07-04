from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entities import OriginRecord, OriginType, ProjectEntity


def test_user_origin_minimal():
    rec = OriginRecord.model_validate({"type": "user"})
    assert rec.type is OriginType.USER
    assert rec.ref is None and rec.independent is False


def test_literature_origin_requires_ref():
    with pytest.raises(ValidationError, match="literature origin requires a ref"):
        OriginRecord.model_validate({"type": "literature"})


def test_literature_ref_must_be_paper_or_cite():
    with pytest.raises(ValidationError, match="paper:<key>' or 'cite:<key>'"):
        OriginRecord.model_validate({"type": "literature", "ref": "smith2019"})
    assert (
        OriginRecord.model_validate({"type": "literature", "ref": "paper:smith2019"}).ref
        == "paper:smith2019"
    )
    assert (
        OriginRecord.model_validate({"type": "literature", "ref": "cite:Smith2019"}).ref
        == "cite:Smith2019"
    )


def test_date_format_validated():
    OriginRecord.model_validate({"type": "user", "date": "2026-05-10"})
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        OriginRecord.model_validate({"type": "user", "date": "May 2026"})


def test_bare_string_and_unknown_keys_rejected():
    with pytest.raises(ValidationError):
        OriginRecord.model_validate("smith2019")
    with pytest.raises(ValidationError):
        OriginRecord.model_validate({"type": "user", "bogus": 1})


def test_entity_carries_origins_and_added_by():
    ent = ProjectEntity.model_validate(
        {
            "id": "hypothesis:0001-x",
            "kind": "hypothesis",
            "type": "hypothesis",  # REQUIRED: _validate_kind_type_consistency
            "title": "X",
            "project": "p",
            "ontology_terms": [],
            "related": [],
            "source_refs": [],
            "content_preview": "",
            "file_path": "entities/hypotheses/0001-x.md",
            "origins": [
                {"type": "user", "date": "2026-05-10"},
                {"type": "literature", "ref": "paper:smith2019", "independent": True},
            ],
            "added_by": "user",
        }
    )
    assert ent.added_by == "user"
    assert [o.type.value for o in ent.origins] == ["user", "literature"]
    assert ent.origins[1].independent is True


def test_frontmatter_parses_origins(tmp_path):
    from science_model.frontmatter import parse_entity_file  # confirm real entry-point name

    p = tmp_path / "0001-x.md"
    p.write_text(
        "---\n"
        "id: hypothesis:0001-x\n"
        "type: hypothesis\n"
        "title: X\n"
        "origins:\n"
        "  - {type: user, date: '2026-05-10'}\n"
        "  - {type: literature, ref: 'paper:smith2019', independent: true}\n"
        "added_by: user\n"
        "---\n\n# X\n",
        encoding="utf-8",
    )
    ent = parse_entity_file(p, project_slug="p")
    assert ent is not None and ent.added_by == "user"
    assert [o.type.value for o in ent.origins] == ["user", "literature"]
    assert ent.origins[1].ref == "paper:smith2019"


from pathlib import Path

from science_model.templates import Renderer

_PKG_TEMPLATES = Path("src/science_model/templates")
_ROOT_TEMPLATES = Path(__file__).resolve().parents[3] / "templates"
_MAPPING_KINDS = ["hypothesis", "question", "theme"]


@pytest.mark.parametrize("kind", _MAPPING_KINDS)
def test_mapping_template_scaffolds_origins(kind):
    text = (_PKG_TEMPLATES / f"{kind}.md").read_text(encoding="utf-8")
    assert "origins: []" in text
    assert "origins: { from: origins, default: [] }" in text


def test_topic_template_scaffolds_origins():
    text = (_PKG_TEMPLATES / "background-topic.md").read_text(encoding="utf-8")
    assert "origins: []" in text  # plain line; topic has no _template mapping


@pytest.mark.parametrize("kind", _MAPPING_KINDS)
def test_mapping_templates_scaffold_origins_in_both_dirs(kind):
    for base in (_PKG_TEMPLATES, _ROOT_TEMPLATES):
        text = (base / f"{kind}.md").read_text(encoding="utf-8")
        assert "origins: []" in text
        assert "origins: { from: origins, default: [] }" in text


def test_topic_template_scaffolds_origins_in_both_dirs():
    for base in (_PKG_TEMPLATES, _ROOT_TEMPLATES):
        assert "origins: []" in (base / "background-topic.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", _MAPPING_KINDS)
def test_render_defaults_origins_to_empty_list(kind):
    # No `origins` passed → must render `origins: []`, NOT `origins: null`.
    out = Renderer(template_root=_PKG_TEMPLATES).render(
        kind,
        fields={
            "entity_id": f"{kind}:01-x",
            "title": "X",
            "slug": "x",
            "nn": "01",
            "status": "active",
        },
    )
    assert "origins: []" in out
    assert "origins: null" not in out


from science_model.entity_schema.validator import EntityValidationError, EntityValidator


def _topic(**extra):
    entity = {
        "id": "topic:immune-set-point",
        "type": "topic",
        "schema_profile": "science-entity-base/1.0+topic/2.0",
        "title": "T",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-05-10",
        "updated": "2026-05-10",
        "source_refs": [],
        "related": [],
    }
    entity.update(extra)
    return entity


def _theme(**extra):
    entity = {
        "id": "theme:reproducibility",
        "type": "theme",
        "schema_profile": "science-entity-base/1.0+theme/2.0",
        "title": "T",
        "version": "1.0.0",
        "status": "active",
        "created": "2026-05-10",
        "updated": "2026-05-10",
        "theme_kind": "conceptual",
        "theme_scope": "project",
        "source_refs": [],
        "related": [],
    }
    entity.update(extra)
    return entity


def test_topic_schema_accepts_valid_origins():
    EntityValidator().validate(
        _topic(
            origins=[{"type": "literature", "ref": "paper:smith2019"}],
            added_by="user",
        )
    )


def test_topic_schema_rejects_literature_without_ref():
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(_topic(origins=[{"type": "literature"}]))


def test_topic_schema_rejects_unknown_origin_key():
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(_topic(origins=[{"type": "user", "bogus": 1}]))


def test_theme_schema_accepts_valid_origins():
    EntityValidator().validate(
        _theme(
            origins=[{"type": "literature", "ref": "cite:Smith2019"}],
            added_by="assistant",
        )
    )


def test_theme_schema_rejects_literature_without_ref():
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(_theme(origins=[{"type": "literature"}]))


def test_theme_schema_rejects_unknown_origin_key():
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(_theme(origins=[{"type": "user", "bogus": 1}]))
