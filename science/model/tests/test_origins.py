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
