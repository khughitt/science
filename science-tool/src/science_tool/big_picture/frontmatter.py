"""YAML frontmatter parser for Science project markdown files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def read_frontmatter(path: Path) -> dict[str, Any] | None:
    """Read YAML frontmatter from a markdown file.

    Returns the parsed frontmatter as a dict, or None if the file has no
    frontmatter, the frontmatter block is unterminated, or the YAML is invalid.
    An empty frontmatter block returns an empty dict.
    """
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    block = text[3:end]
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        return None
    if data is None:
        return {}
    if not isinstance(data, dict):
        return None
    return data
