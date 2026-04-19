"""Pure-function core for migrating legacy ``article:`` IDs to ``paper:``.

See docs/specs/2026-04-19-manuscript-paper-rename-design.md for the
canonical rewrite rules.
"""

from __future__ import annotations

import re

# Entity-ID character class per the spec: [A-Za-z0-9_\-.]
_ENTITY_ID_CLASS = r"[A-Za-z0-9_\-.]"

# YAML-style rewrites for the `article:` prefix embedded in entity IDs.
ID_REWRITE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"id: article:"), "id: paper:"),
    (re.compile(r'id: "article:'), 'id: "paper:'),
    (re.compile(r"- article:"), "- paper:"),
    (re.compile(r"\[article:"), "[paper:"),
    (re.compile(r'"article:'), '"paper:'),
    (re.compile(r"'article:"), "'paper:"),
]

# Frontmatter `type:` rewrites — must be applied ONLY to the top YAML block.
TYPE_REWRITE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^type: article\s*$", re.MULTILINE), "type: paper"),
    (re.compile(r'^type: "article"\s*$', re.MULTILINE), 'type: "paper"'),
    (re.compile(r"^type: 'article'\s*$", re.MULTILINE), "type: 'paper'"),
]

# Prose fallback: `article:<id>` anywhere in body/YAML values.
# Word boundary avoids rewriting `particle:` and similar substrings.
PROSE_REWRITE_RULE: tuple[re.Pattern[str], str] = (
    re.compile(rf"\barticle:(?={_ENTITY_ID_CLASS})"),
    "paper:",
)
