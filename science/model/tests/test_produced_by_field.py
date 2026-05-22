from pathlib import Path

import pytest

from science_model.entities import Entity, core_entity_type_for_kind
from science_model.frontmatter import parse_entity_file


def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def _base_kwargs(kind: str, id_: str) -> dict:
    # Include `type` so the entity passes the kind/type-consistency validator;
    # otherwise the test depends on validator ordering to surface the
    # produced_by error before the type-mismatch error.
    return dict(
        id=id_, kind=kind, type=core_entity_type_for_kind(kind), title="X", project="demo",
        ontology_terms=[], related=[], source_refs=[], content_preview="", file_path=f"doc/{kind}/x.md",
    )


def test_produced_by_parsed_from_frontmatter(tmp_path: Path) -> None:
    md = _write(
        tmp_path / "d.md",
        "---\n"
        "id: dataset:x\n"
        "kind: dataset\n"
        "title: X\n"
        "status: active\n"
        "produced_by:\n"
        "  - code-file:stages/run.py\n"
        "---\nbody\n",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity.produced_by == ["code-file:stages/run.py"]


def test_produced_by_defaults_empty(tmp_path: Path) -> None:
    md = _write(
        tmp_path / "d.md",
        "---\nid: dataset:y\nkind: dataset\ntitle: Y\nstatus: active\n---\nbody\n",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity.produced_by == []


def test_produced_by_rejected_on_non_data_artifact() -> None:
    with pytest.raises(ValueError, match="dataset/data-package"):
        Entity(**_base_kwargs("hypothesis", "hypothesis:h1"), produced_by=["code-file:x.py"])


def test_produced_by_must_be_code_file_refs() -> None:
    with pytest.raises(ValueError, match="code-file:"):
        Entity(**_base_kwargs("dataset", "dataset:x"), produced_by=["workflow-run:wf-r1"])
