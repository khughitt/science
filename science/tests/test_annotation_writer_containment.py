"""Containment of the annotation writers (design 2026-07-31, §4.2-§4.4)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from science_model.propositions import PropositionEntity

from science_tool.dag.entity_frontmatter import (
    EntityWriteError,
    Ownership,
    create_entity_file,
    update_entity_file,
)

OWNERSHIP = Ownership(frozenset({"id", "kind", "subject", "object"}), frozenset({"title", "status"}))


def _seed(tmp_path: Path) -> Path:
    # `resolve_path_policy` needs no science.yaml for the default layout -- see
    # test_annotation_promote.py:265, which seeds exactly this and nothing else.
    (tmp_path / "entities" / "propositions").mkdir(parents=True)
    return tmp_path


def _prop(**kw) -> PropositionEntity:
    base = dict(id="proposition:p", title="A affects B", subject="concept:a", object="concept:b")
    base.update(kw)
    return PropositionEntity(**base)


def test_create_entity_file_refuses_existing_destination(tmp_path: Path) -> None:
    root = _seed(tmp_path)
    entity = _prop()
    create_entity_file(entity, project_root=root, ownership=OWNERSHIP,
                       create_body="# body\n", as_of=date(2026, 7, 31))

    with pytest.raises(EntityWriteError, match="already exists"):
        create_entity_file(entity, project_root=root, ownership=OWNERSHIP,
                           create_body="# body\n", as_of=date(2026, 7, 31))


def test_update_entity_file_refuses_missing_destination(tmp_path: Path) -> None:
    root = _seed(tmp_path)
    with pytest.raises(EntityWriteError, match="does not exist"):
        update_entity_file(_prop(), project_root=root, ownership=OWNERSHIP, as_of=date(2026, 7, 31))


def test_update_entity_file_takes_no_create_body(tmp_path: Path) -> None:
    """An update-only writer has no body to supply; the signature must not accept one."""
    root = _seed(tmp_path)
    with pytest.raises(TypeError):
        update_entity_file(_prop(), project_root=root, ownership=OWNERSHIP,
                           create_body="# nope\n")  # type: ignore[call-arg]
