from __future__ import annotations

import pytest

from science_model.entities import ThemeEntity


def _base() -> dict:
    return {
        "id": "theme:demo",
        "kind": "theme",
        "type": "theme",
        "title": "Demo theme",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "",
    }


@pytest.mark.parametrize("kind", ["conceptual", "empirical", "domain"])
def test_theme_entity_accepts_mixin_kinds(kind: str) -> None:
    entity = ThemeEntity.model_validate({**_base(), "theme_kind": kind})
    assert entity.theme_kind == kind


def test_theme_entity_accepts_cross_project_scope() -> None:
    entity = ThemeEntity.model_validate({**_base(), "theme_scope": "cross-project"})
    assert entity.theme_scope == "cross-project"


def test_theme_entity_rejects_unknown_kind() -> None:
    with pytest.raises(Exception):
        ThemeEntity.model_validate({**_base(), "theme_kind": "not-a-kind"})
