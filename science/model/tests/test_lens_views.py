from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.entities import LensView, OriginRecord, OriginType


def _entity(**overrides):
    from science_model.entities import Entity, EntityType
    base = dict(
        id="question:0001-x", kind="question", type=EntityType.QUESTION, title="X", project="p",
        ontology_terms=[], related=[], source_refs=[], content_preview="",
        file_path="entities/questions/0001-x.md",
    )
    base.update(overrides)
    return Entity(**base)


def test_lens_view_rejects_unknown_lens() -> None:
    with pytest.raises(ValidationError):
        LensView(lens="holistic", rationale="r")


def test_lens_view_requires_nonempty_rationale() -> None:
    with pytest.raises(ValidationError):
        LensView(lens="mechanism", rationale="  ")


def test_entity_accepts_convergent_lens_views() -> None:
    e = _entity(
        origins=[
            OriginRecord(type=OriginType.ASSISTANT, ref="explore-ideas-mechanism"),
            OriginRecord(type=OriginType.ASSISTANT, ref="explore-ideas-analogy", independent=True),
        ],
        lens_views=[
            LensView(lens="mechanism", rationale="m", origin_ref="explore-ideas-mechanism"),
            LensView(lens="analogy", rationale="a", origin_ref="explore-ideas-analogy"),
        ],
    )
    assert [v.lens for v in e.lens_views] == ["mechanism", "analogy"]


def test_entity_rejects_dangling_origin_ref() -> None:
    with pytest.raises(ValidationError):
        _entity(
            origins=[OriginRecord(type=OriginType.ASSISTANT, ref="explore-ideas-mechanism")],
            lens_views=[LensView(lens="analogy", rationale="a", origin_ref="explore-ideas-analogy")],
        )


def test_entity_rejects_duplicate_lens() -> None:
    with pytest.raises(ValidationError):
        _entity(
            origins=[OriginRecord(type=OriginType.ASSISTANT, ref="explore-ideas-mechanism")],
            lens_views=[
                LensView(lens="mechanism", rationale="a", origin_ref="explore-ideas-mechanism"),
                LensView(lens="mechanism", rationale="b"),
            ],
        )
