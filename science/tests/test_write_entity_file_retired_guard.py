"""Guard: `write_entity_file` stays retired (design 2026-07-31, §4.4).

Scope is a TREE WALK with no allowlist -- a guard that enumerates its own scope has a hole
by construction, and this programme has already been bitten by one.

This guard proves one symbol stayed gone. It does NOT prove the full-model dump stayed gone:
a writer reintroduced under another name passes it. That half belongs to the containment
tests in test_annotation_writer_containment.py.
"""
from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "science_tool"


def test_write_entity_file_appears_nowhere_in_src() -> None:
    offenders = [
        f"{path.relative_to(SRC)}:{n}"
        for path in sorted(SRC.rglob("*.py"))
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"(?<!_)\bwrite_entity_file\b", line)
    ]
    assert offenders == [], (
        "`write_entity_file` was retired by the annotation-writer-containment slice; "
        "route the write through dag.entity_frontmatter's create/update/upsert entry points "
        f"instead. Found: {offenders}"
    )


def test_symbol_is_absent_from_the_entities_module() -> None:
    import science_tool.entities as entities

    assert not hasattr(entities, "write_entity_file")
