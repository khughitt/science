"""Strict parsing for packaged skill frontmatter."""

from __future__ import annotations

import re

import yaml


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
