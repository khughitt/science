from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml
from science_model.propositions import PropositionEntity

from science_tool.dag.workbench import workbench_entity_body
from science_tool.entities import (
    parse_markdown_entity_file_preserving_body,
    render_entity_text,
    write_entity_file,
)


def _seed_project(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: workbench-apply-test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _frontmatter(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    _, fm_text, _body = text.split("---\n", 2)
    loaded = yaml.safe_load(fm_text) or {}
    assert isinstance(loaded, dict)
    return loaded


def _proposition(entity_id: str = "proposition:a-affects-b") -> PropositionEntity:
    return PropositionEntity(
        id=entity_id,
        subject="a",
        predicate="affects",
        object="b",
        polarity="positive",
        claim_layer="causal_effect",
        identification_strength="observational",
    )


def test_render_entity_text_matches_write_entity_file_output(tmp_path: Path) -> None:
    _seed_project(tmp_path)
    entity = _proposition()
    body = workbench_entity_body(entity)

    write_entity_file(entity, project_root=tmp_path, body=body, as_of=date(2026, 7, 4))

    path = tmp_path / "entities/propositions/a-affects-b.md"
    written = path.read_text(encoding="utf-8")
    rendered = render_entity_text(
        entity,
        body=body,
        created="2026-07-04",
        updated="2026-07-04",
    )
    assert written == rendered


def test_parse_markdown_entity_file_preserving_body_keeps_body_bytes(tmp_path: Path) -> None:
    path = tmp_path / "entity.md"
    path.write_text(
        "---\nid: proposition:x\ntype: proposition\n---\n\n# Title\n\nBody.\n",
        encoding="utf-8",
    )

    frontmatter, body = parse_markdown_entity_file_preserving_body(path)

    assert frontmatter["id"] == "proposition:x"
    assert body == "\n# Title\n\nBody.\n"


def test_parse_markdown_entity_file_preserving_body_keeps_crlf_body_bytes(tmp_path: Path) -> None:
    path = tmp_path / "entity.md"
    path.write_bytes(
        b"---\r\nid: proposition:x\r\ntype: proposition\r\n---\r\n\r\n# Title\r\n\r\nBody.\r\n"
    )

    frontmatter, body = parse_markdown_entity_file_preserving_body(path)

    assert frontmatter["id"] == "proposition:x"
    assert body == "\r\n# Title\r\n\r\nBody.\r\n"
