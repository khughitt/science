"""Aggregator for project health diagnostics.

Provides the data layer for `science-tool health` — groups unresolved refs
by target, surfaces stale tasks, knowledge gaps, and schema issues. Output
is a structured dict suitable for both human display and agent consumption.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import load_project_sources


class UnresolvedRef(TypedDict):
    target: str
    mention_count: int
    sources: list[str]
    looks_like: str  # "topic" | "task" | "hypothesis" | "unknown"


_TASK_ID_RE = re.compile(r"^topic:t\d+$", re.IGNORECASE)
_HYPOTHESIS_ID_RE = re.compile(r"^topic:h\d+", re.IGNORECASE)


def _classify(target: str) -> str:
    """Heuristic guess at what kind of entity a ref looks like it should be."""
    if _TASK_ID_RE.match(target):
        return "task"
    if _HYPOTHESIS_ID_RE.match(target):
        return "hypothesis"
    if target.startswith("topic:"):
        return "topic"
    return "unknown"


def collect_unresolved_refs(project_root: Path) -> list[UnresolvedRef]:
    """Walk a project, run the audit, group unresolved refs by target.

    Returns a list sorted by mention count (descending), then target (asc).
    Meta: refs are excluded (they're intentional metadata, not unresolved).
    """
    sources = load_project_sources(project_root.resolve())
    rows, _ = audit_project_sources(sources)

    # Group fail rows by target
    by_target: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["status"] != "fail":
            continue
        target = row["target"]
        source = row["source"]
        if source not in by_target[target]:
            by_target[target].append(source)

    result: list[UnresolvedRef] = [
        {
            "target": target,
            "mention_count": len(sources_list),
            "sources": sorted(sources_list),
            "looks_like": _classify(target),
        }
        for target, sources_list in by_target.items()
    ]
    result.sort(key=lambda r: (-r["mention_count"], r["target"]))
    return result
