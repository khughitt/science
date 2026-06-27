"""Read-only catalog helpers for benchmark-capable dataset entities."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from science_model.frontmatter import parse_frontmatter

from science_tool.datasets.semantics import dataset_class_for

_BELIEF_TOKEN_RE = re.compile(r"[A-Za-z0-9:_-]+")


class CommonsUnavailable(Exception):
    """Raised when commons benchmark rows cannot be read."""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _task_mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _dataset_class(fm: Mapping[str, object]) -> str:
    try:
        return dataset_class_for(fm)
    except ValueError:
        return "deposit"


def _row_from_frontmatter(fm: Mapping[str, object], *, fallback_id: str, scope: str) -> dict | None:
    if (fm.get("kind") or fm.get("type")) != "dataset":
        return None

    benchmark = fm.get("benchmark")
    if not isinstance(benchmark, Mapping):
        return None

    tasks = _task_mappings(benchmark.get("tasks"))
    task_ids = _string_list([task.get("id") for task in tasks])

    return {
        "id": str(fm.get("id") or fallback_id),
        "title": str(fm.get("title") or ""),
        "scope": scope,
        "dataset_class": _dataset_class(fm),
        "domains": _string_list(benchmark.get("domains")),
        "modalities": _string_list(benchmark.get("modalities")),
        "signal_types": _string_list(benchmark.get("signal_types")),
        "benchmark_kinds": _string_list(benchmark.get("benchmark_kinds")),
        "source_datasets": _string_list(benchmark.get("source_datasets")),
        "related_beliefs": _string_list(benchmark.get("related_beliefs")),
        "task_count": len(tasks),
        "task_ids": task_ids,
    }


def _local_rows(project_root: Path) -> list[dict]:
    datasets_dir = project_root / "entities" / "datasets"
    if not datasets_dir.is_dir():
        return []

    rows: list[dict] = []
    for md in sorted(datasets_dir.glob("*.md")):
        parsed = parse_frontmatter(md)
        if parsed is None:
            continue
        fm, _ = parsed
        row = _row_from_frontmatter(fm, fallback_id=f"dataset:{md.stem}", scope="local")
        if row is not None:
            rows.append(row)
    return rows


def _commons_rows() -> list[dict]:
    """Return benchmark rows from the commons registry.

    Raises CommonsUnavailable so the CLI can report a single notice and still
    show local rows.
    """

    from science_tool.commons.config import resolve_commons_root
    from science_tool.commons.errors import CommonsRegistryError
    from science_tool.commons.query import CommonsQuery

    try:
        records = CommonsQuery(resolve_commons_root()).find("dataset")
    except (CommonsRegistryError, FileNotFoundError) as exc:
        raise CommonsUnavailable(str(exc)) from exc

    rows: list[dict] = []
    for record in records:
        row = _row_from_frontmatter(
            record.frontmatter or {},
            fallback_id=record.canonical_id,
            scope="commons",
        )
        if row is not None:
            rows.append(row)
    return rows


def _has_belief_token(row: Mapping[str, object], query: str) -> bool:
    needle = query.strip().lower()
    if not needle:
        return False
    for text in row.get("related_beliefs", []):
        if not isinstance(text, str):
            continue
        if any(token.lower() == needle for token in _BELIEF_TOKEN_RE.findall(text)):
            return True
    return False


def _matches(
    row: Mapping[str, object],
    *,
    domain: str | None,
    benchmark_kind: str | None,
    belief_ref_text: str | None,
) -> bool:
    if domain is not None and domain not in row["domains"]:
        return False
    if benchmark_kind is not None and benchmark_kind not in row["benchmark_kinds"]:
        return False
    if belief_ref_text is not None and not _has_belief_token(row, belief_ref_text):
        return False
    return True


def list_benchmarks(
    project_root: Path,
    *,
    domain: str | None = None,
    benchmark_kind: str | None = None,
    belief_ref_text: str | None = None,
    include_commons: bool = False,
) -> tuple[list[dict], str | None]:
    rows = _local_rows(project_root)
    notice: str | None = None
    if include_commons:
        try:
            rows.extend(_commons_rows())
        except CommonsUnavailable as exc:
            notice = str(exc)

    filtered = [
        row
        for row in rows
        if _matches(row, domain=domain, benchmark_kind=benchmark_kind, belief_ref_text=belief_ref_text)
    ]
    return sorted(filtered, key=lambda row: (row["scope"], row["id"])), notice


def coverage_summary(rows: list[dict]) -> dict[str, dict[str, int]]:
    counters = {
        "domains": Counter(),
        "modalities": Counter(),
        "signal_types": Counter(),
        "benchmark_kinds": Counter(),
        "dataset_class": Counter(),
        "tasks": Counter({"with_tasks": 0, "facets_only": 0}),
    }
    for row in rows:
        counters["domains"].update(row["domains"])
        counters["modalities"].update(row["modalities"])
        counters["signal_types"].update(row["signal_types"])
        counters["benchmark_kinds"].update(row["benchmark_kinds"])
        counters["dataset_class"].update([row["dataset_class"]])
        counters["tasks"].update(["with_tasks" if row["task_count"] else "facets_only"])

    return {name: dict(sorted(counter.items())) for name, counter in counters.items()}
