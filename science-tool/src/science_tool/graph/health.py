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


# Heuristic patterns for classifying mis-prefixed `topic:` refs.
# All anchored at start; trailing slug (e.g. h01-some-suffix) is allowed since
# real entity IDs commonly have a numeric ID followed by a kebab-case slug.
_TASK_ID_RE = re.compile(r"^topic:t\d+", re.IGNORECASE)
_HYPOTHESIS_ID_RE = re.compile(r"^topic:h\d+", re.IGNORECASE)
_QUESTION_ID_RE = re.compile(r"^topic:q\d+", re.IGNORECASE)


def _classify(target: str) -> str:
    """Heuristic guess at what kind of entity a ref looks like it should be."""
    if _TASK_ID_RE.match(target):
        return "task"
    if _HYPOTHESIS_ID_RE.match(target):
        return "hypothesis"
    if _QUESTION_ID_RE.match(target):
        return "question"
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


class LingeringTagsRecord(TypedDict):
    file: str
    values: list[str]


_FRONTMATTER_TAGS_RE = re.compile(
    r"^tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE
)
_TASK_TAGS_RE = re.compile(
    r"^- tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE
)


def _parse_list_body(body: str) -> list[str]:
    items = [item.strip() for item in body.split(",") if item.strip()]
    cleaned: list[str] = []
    for item in items:
        if len(item) >= 2 and item[0] == item[-1] and item[0] in ('"', "'"):
            cleaned.append(item[1:-1])
        else:
            cleaned.append(item)
    return cleaned


def collect_lingering_tags(project_root: Path) -> list[LingeringTagsRecord]:
    """Find any files still containing `tags:` lines (frontmatter or task)."""
    project_root = project_root.resolve()
    results: list[LingeringTagsRecord] = []

    for scan_dir in ["doc", "specs"]:
        base = project_root / scan_dir
        if not base.is_dir():
            continue
        for md_file in sorted(base.rglob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            for match in _FRONTMATTER_TAGS_RE.finditer(text):
                results.append({
                    "file": str(md_file.relative_to(project_root)),
                    "values": _parse_list_body(match.group("body")),
                })

    tasks_dir = project_root / "tasks"
    candidate_task_files: list[Path] = []
    if (tasks_dir / "active.md").is_file():
        candidate_task_files.append(tasks_dir / "active.md")
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        candidate_task_files.extend(sorted(done_dir.glob("*.md")))

    for task_file in candidate_task_files:
        text = task_file.read_text(encoding="utf-8")
        for match in _TASK_TAGS_RE.finditer(text):
            results.append({
                "file": str(task_file.relative_to(project_root)),
                "values": _parse_list_body(match.group("body")),
            })

    return results


class HealthReport(TypedDict):
    unresolved_refs: list[UnresolvedRef]
    lingering_tags_lines: list[LingeringTagsRecord]


def build_health_report(project_root: Path) -> HealthReport:
    """Aggregate all health checks for a project."""
    return {
        "unresolved_refs": collect_unresolved_refs(project_root),
        "lingering_tags_lines": collect_lingering_tags(project_root),
    }
