from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.graph.skill_inventory import (
    SkillInventoryError,
    companion_section,
    load_index_registry,
    parse_skill_frontmatter,
    real_skill_paths,
    resolve_companions,
)


def test_parse_frontmatter_reads_mapping() -> None:
    text = "---\nname: transcriptomics-scrna-qa\narchetype: measurement-qa\n---\n\nBody.\n"
    assert parse_skill_frontmatter(text) == {
        "name": "transcriptomics-scrna-qa",
        "archetype": "measurement-qa",
    }


def test_parse_frontmatter_missing_block() -> None:
    with pytest.raises(SkillInventoryError, match="frontmatter"):
        parse_skill_frontmatter("no frontmatter here\n")


def test_parse_frontmatter_rejects_duplicate_key() -> None:
    text = "---\nname: a\ncovers:\n  - data-product:x\ncovers:\n  - data-product:y\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_yaml_equivalent_duplicate_key() -> None:
    text = "---\n1: first\n01: second\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_merge_key() -> None:
    text = "---\nbase: &b\n  k: v\nname: <<\n<<: *b\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="merge"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_rejects_nested_duplicate_key() -> None:
    text = "---\nname: a\nmeta:\n  k: 1\n  k: 2\n---\n\nB\n"
    with pytest.raises(SkillInventoryError, match="duplicate"):
        parse_skill_frontmatter(text)


def test_parse_frontmatter_non_mapping() -> None:
    with pytest.raises(SkillInventoryError, match="mapping"):
        parse_skill_frontmatter("---\n- just\n- a list\n---\n\nB\n")


def _write(root: Path, rel: str, body: str = "---\nname: x\n---\n\nB\n") -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _write_corpus(
    root: Path, entries: list[tuple[str, str]], *, index_lines: list[str] | None = None
) -> None:
    for _sid, rel in entries:
        _write(root, rel)
    lines = index_lines if index_lines is not None else [f"- `{sid}`: `{rel}`" for sid, rel in entries]
    _write(root, "skills/INDEX.md", "---\nname: science-skill-index\n---\n\n" + "\n".join(lines) + "\n")


def test_registry_reads_pairs_in_index_order(tmp_path: Path) -> None:
    entries = [("bio", "skills/bio/SKILL.md"), ("bio-x-qa", "skills/bio/x-qa.md")]
    _write_corpus(tmp_path, entries)
    assert load_index_registry(tmp_path) == entries


def test_real_skill_paths_excludes_index_and_templates(tmp_path: Path) -> None:
    _write(tmp_path, "skills/bio/x-qa.md")
    _write(tmp_path, "skills/INDEX.md")
    _write(tmp_path, "skills/meta/templates/router.md")
    assert real_skill_paths(tmp_path) == {"skills/bio/x-qa.md"}


def test_registry_rejects_duplicate_id(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write(tmp_path, "skills/b.md")
    _write_corpus(tmp_path, [], index_lines=["- `dup`: `skills/a.md`", "- `dup`: `skills/b.md`"])
    with pytest.raises(SkillInventoryError, match="duplicate INDEX id"):
        load_index_registry(tmp_path)


def test_registry_rejects_duplicate_path(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write_corpus(tmp_path, [], index_lines=["- `one`: `skills/a.md`", "- `two`: `skills/a.md`"])
    with pytest.raises(SkillInventoryError, match="duplicate INDEX path"):
        load_index_registry(tmp_path)


def test_registry_rejects_bad_grammar(tmp_path: Path) -> None:
    _write(tmp_path, "skills/a.md")
    _write_corpus(tmp_path, [], index_lines=["- `Bad_Id`: `skills/a.md`"])
    with pytest.raises(SkillInventoryError, match="grammar"):
        load_index_registry(tmp_path)


def test_registry_rejects_missing_path(tmp_path: Path) -> None:
    _write_corpus(tmp_path, [], index_lines=["- `ghost`: `skills/ghost.md`"])
    with pytest.raises(SkillInventoryError, match="does not exist"):
        load_index_registry(tmp_path)


def test_registry_rejects_orphan_skill(tmp_path: Path) -> None:
    _write(tmp_path, "skills/listed.md")
    _write(tmp_path, "skills/orphan.md")
    _write_corpus(tmp_path, [], index_lines=["- `listed`: `skills/listed.md`"])
    with pytest.raises(SkillInventoryError, match="missing from INDEX"):
        load_index_registry(tmp_path)


def test_registry_rejects_extra_non_skill(tmp_path: Path) -> None:
    _write(tmp_path, "skills/real.md")
    _write(tmp_path, "skills/meta/templates/router.md")
    _write_corpus(
        tmp_path,
        [],
        index_lines=[
            "- `real`: `skills/real.md`",
            "- `tmpl`: `skills/meta/templates/router.md`",
        ],
    )
    with pytest.raises(SkillInventoryError, match="not a real skill"):
        load_index_registry(tmp_path)


_PATH_TO_ID = {
    "skills/bio/transcriptomics/cohort-qa.md": "transcriptomics-cohort-qa",
    "skills/bio/transcriptomics/SKILL.md": "transcriptomics",
    "skills/statistics/compositional-data.md": "statistics-compositional-data",
}


def test_companion_section_extracts_only_that_section() -> None:
    text = "# T\n\n## Companion Skills\n\n- [`a`](a.md)\n\n## Next\n\n- not this\n"
    assert "- [`a`](a.md)" in companion_section(text)
    assert "not this" not in companion_section(text)


def test_resolve_companions_typed_targets(tmp_path: Path) -> None:
    section = (
        "- [`cohort-qa.md`](cohort-qa.md) - x\n"
        "- [`SKILL.md`](SKILL.md) - the router\n"
        "- [`compositional-data`](../../statistics/compositional-data.md#anchor) - y\n"
        "- [`index`](../../INDEX.md) - the index\n"
    )
    edges = resolve_companions(tmp_path, "skills/bio/transcriptomics/scrna-qa.md", section, _PATH_TO_ID)
    assert edges == [
        {"target": "transcriptomics-cohort-qa", "role": "leaf"},
        {"target": "transcriptomics", "role": "router"},
        {"target": "statistics-compositional-data", "role": "leaf"},
        {"target": "science-skill-index", "role": "index"},
    ]


def test_resolve_companions_rejects_broken_target(tmp_path: Path) -> None:
    with pytest.raises(SkillInventoryError, match="non-skill"):
        resolve_companions(
            tmp_path,
            "skills/bio/transcriptomics/scrna-qa.md",
            "- [`x`](../../nope/ghost.md)\n",
            _PATH_TO_ID,
        )


def test_resolve_companions_rejects_duplicate_target(tmp_path: Path) -> None:
    section = "- [`a`](cohort-qa.md)\n- [`a again`](cohort-qa.md)\n"
    with pytest.raises(SkillInventoryError, match="duplicate companion"):
        resolve_companions(tmp_path, "skills/bio/transcriptomics/scrna-qa.md", section, _PATH_TO_ID)


def test_resolve_companions_empty_section() -> None:
    assert resolve_companions(Path("/x"), "skills/a.md", "", _PATH_TO_ID) == []
