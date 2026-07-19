from pathlib import Path

from science_tool.skills_lint.discovery import iter_skill_files


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "---\nname: x\ndescription: y\nprovenance: internal\n---\n",
        encoding="utf-8",
    )


def test_iter_skill_files_excludes_meta_templates_keeps_index(tmp_path: Path) -> None:
    for rel in (
        "INDEX.md",
        "data/SKILL.md",
        "meta/SKILL.md",
        "meta/skill-taxonomy.md",
        "meta/templates/router.md",
        "meta/templates/measurement-qa.md",
    ):
        _touch(tmp_path / rel)
    found = {p.relative_to(tmp_path).as_posix() for p in iter_skill_files(tmp_path)}
    assert "meta/templates/router.md" not in found
    assert "meta/templates/measurement-qa.md" not in found
    assert "INDEX.md" in found  # NOT excluded: the linter must inspect it
    assert {"data/SKILL.md", "meta/SKILL.md", "meta/skill-taxonomy.md"} <= found


def test_iter_skill_files_is_sorted(tmp_path: Path) -> None:
    for rel in ("b/SKILL.md", "a/SKILL.md", "INDEX.md"):
        _touch(tmp_path / rel)
    rels = [p.relative_to(tmp_path).as_posix() for p in iter_skill_files(tmp_path)]
    assert rels == sorted(rels)
