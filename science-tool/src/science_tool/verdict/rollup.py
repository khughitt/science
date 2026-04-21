"""Rollup helpers for parsed verdict interpretations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Literal
import re

import yaml

from science_tool.verdict.models import ParseResult
from science_tool.verdict.parser import NoVerdictBlockError, parse_file
from science_tool.verdict.registry import IndexedClaimRegistry
from science_tool.verdict.tokens import Token


Scope = Literal["all", "claim"]

_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def walk_interpretations(
    directory: Path | str,
    *,
    registry: IndexedClaimRegistry | None = None,
) -> Iterator[ParseResult]:
    """Yield parsed verdict interpretation files from one directory level."""
    for md_path in sorted(Path(directory).glob("*.md")):
        if not _has_verdict_key(md_path):
            continue
        try:
            yield parse_file(md_path, registry=registry)
        except NoVerdictBlockError:
            continue


def _has_verdict_key(md_path: Path) -> bool:
    """Return True when markdown frontmatter structurally declares `verdict:`."""
    content = md_path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(content)
    if match is None:
        return False

    try:
        frontmatter = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return True
    if not isinstance(frontmatter, dict):
        return False
    return "verdict" in frontmatter


def group_by(
    results: Iterator[ParseResult] | list[ParseResult],
    scope: Scope,
    *,
    registry: IndexedClaimRegistry | None = None,
) -> dict[str, list[ParseResult]]:
    """Group parse results by rollup scope."""
    result_list = list(results)
    if scope == "all":
        return {"all": result_list}
    if scope != "claim":
        raise ValueError(f"Unsupported rollup scope: {scope}")
    if registry is None:
        raise ValueError("Claim scope requires a registry")

    grouped: dict[str, list[ParseResult]] = {}
    for result in result_list:
        seen: set[str] = set()
        for claim in result.claims:
            canonical_id = registry.resolve(claim.id) or claim.id
            if canonical_id in seen:
                continue
            seen.add(canonical_id)
            grouped.setdefault(canonical_id, []).append(result)
    return grouped


def tally_polarities(results: Iterator[ParseResult] | list[ParseResult]) -> dict[Token, int]:
    """Count parse results by composite verdict token."""
    return Counter(result.composite_token for result in results)
