"""Strict parsing for packaged skill frontmatter."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from science_tool.graph.skill_loads import SKILL_NAME_RE


class SkillInventoryError(ValueError):
    """The skills corpus, INDEX, or a skill's frontmatter is structurally invalid."""


_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _reject_dup_and_merge_keys(node: yaml.Node) -> None:
    if isinstance(node, yaml.MappingNode):
        seen: set[object] = set()
        loader = yaml.SafeLoader("")
        try:
            for key_node, value_node in node.value:
                if key_node.tag == "tag:yaml.org,2002:merge":
                    raise SkillInventoryError("YAML merge keys are not allowed in skill frontmatter")
                key = loader.construct_object(key_node, deep=True)
                if key in seen:
                    raise SkillInventoryError(f"duplicate frontmatter key {key!r}")
                seen.add(key)
                _reject_dup_and_merge_keys(value_node)
        finally:
            loader.dispose()
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            _reject_dup_and_merge_keys(item)


def parse_skill_frontmatter(text: str) -> dict:
    """Return the YAML mapping in a skill document's opening frontmatter block."""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        raise SkillInventoryError("missing frontmatter block")

    block = match.group(1)
    node = yaml.compose(block, Loader=yaml.SafeLoader)
    if node is not None:
        _reject_dup_and_merge_keys(node)

    data = yaml.safe_load(block)
    if not isinstance(data, dict):
        raise SkillInventoryError("frontmatter is not a mapping")
    return data


_INDEX_LINE_RE = re.compile(r"^\s*-\s*`([^`]+)`:\s*`(skills/[^`]+)`", re.MULTILINE)


def real_skill_paths(repo_root: Path) -> set[str]:
    out: set[str] = set()
    for path in (repo_root / "skills").rglob("*.md"):
        rel = path.relative_to(repo_root).as_posix()
        if rel == "skills/INDEX.md" or rel.startswith("skills/meta/templates/"):
            continue
        out.add(rel)
    return out


def load_index_registry(repo_root: Path) -> list[tuple[str, str]]:
    index_text = (repo_root / "skills" / "INDEX.md").read_text(encoding="utf-8")
    entries = _INDEX_LINE_RE.findall(index_text)
    ids: set[str] = set()
    paths: set[str] = set()
    for sid, rel in entries:
        if SKILL_NAME_RE.fullmatch(sid) is None:
            raise SkillInventoryError(f"INDEX id {sid!r} fails the canonical skill-id grammar")
        if sid in ids:
            raise SkillInventoryError(f"duplicate INDEX id {sid!r}")
        if rel in paths:
            raise SkillInventoryError(f"duplicate INDEX path {rel!r}")
        if not (repo_root / rel).is_file():
            raise SkillInventoryError(f"INDEX path {rel!r} does not exist")
        ids.add(sid)
        paths.add(rel)
    real = real_skill_paths(repo_root)
    orphan = real - paths
    if orphan:
        raise SkillInventoryError(f"real skills missing from INDEX: {sorted(orphan)}")
    extra = paths - real
    if extra:
        raise SkillInventoryError(f"INDEX lists paths that are not a real skill: {sorted(extra)}")
    return entries
