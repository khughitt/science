"""Tolerant frontmatter readers shared by graph and validate code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def raw_frontmatter(path: Path) -> dict[str, Any]:
    """Raw frontmatter for either a fenced markdown entity or a YAML descriptor.

    Reads directly and tolerates malformed input by returning {}. Callers that
    need schema-critical guarantees must enforce those rules themselves.
    """
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(text) or {}
        elif text.startswith("---"):
            end = text.find("\n---", 3)
            data = yaml.safe_load(text[3:end]) if end != -1 else {}
        else:
            data = {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}
