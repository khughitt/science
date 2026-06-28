"""Read-only catalog helpers for benchmark-capable dataset entities."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping
from pathlib import Path
from typing import Any, TypedDict

from science_model.frontmatter import parse_frontmatter

from science_tool.datasets.semantics import dataset_class_for

_BELIEF_TOKEN_RE = re.compile(r"[A-Za-z0-9:_-]+")


class CommonsUnavailable(Exception):
    """Raised when commons benchmark rows cannot be read."""


class BenchmarkRow(TypedDict):
    id: str
    title: str
    scope: str
    dataset_class: str
    domains: list[str]
    modalities: list[str]
    signal_types: list[str]
    benchmark_kinds: list[str]
    source_datasets: list[str]
    related_beliefs: list[str]
    task_count: int
    task_ids: list[str]


class BenchmarkSource(TypedDict):
    frontmatter: Mapping[str, object]
    fallback_id: str
    scope: str


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


def _row_from_frontmatter(fm: Mapping[str, object], *, fallback_id: str, scope: str) -> BenchmarkRow | None:
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
        "task_count": len(task_ids),
        "task_ids": task_ids,
    }


def _source_from_frontmatter(
    fm: Mapping[str, object],
    *,
    fallback_id: str,
    scope: str,
) -> BenchmarkSource | None:
    if (fm.get("kind") or fm.get("type")) != "dataset":
        return None
    if not isinstance(fm.get("benchmark"), Mapping):
        return None
    return {"frontmatter": fm, "fallback_id": fallback_id, "scope": scope}


def _local_sources(project_root: Path) -> list[BenchmarkSource]:
    datasets_dir = project_root / "entities" / "datasets"
    if not datasets_dir.is_dir():
        return []

    sources: list[BenchmarkSource] = []
    for md in sorted(datasets_dir.glob("*.md")):
        parsed = parse_frontmatter(md)
        if parsed is None:
            continue
        fm, _ = parsed
        source = _source_from_frontmatter(fm, fallback_id=f"dataset:{md.stem}", scope="local")
        if source is not None:
            sources.append(source)
    return sources


def _commons_sources() -> list[BenchmarkSource]:
    """Return benchmark sources from the commons registry.

    Raises CommonsUnavailable so the CLI can report a single notice and still
    show local rows.
    """

    from science_tool.commons.config import resolve_commons_root
    from science_tool.commons.errors import CommonsError
    from science_tool.commons.query import CommonsQuery

    try:
        records = CommonsQuery(resolve_commons_root()).find("dataset")
    except (CommonsError, FileNotFoundError, ValueError) as exc:
        raise CommonsUnavailable(str(exc)) from exc

    sources: list[BenchmarkSource] = []
    for record in records:
        if not isinstance(record.frontmatter, Mapping):
            msg = f"{record.canonical_id}: frontmatter_json must decode to an object"
            raise CommonsUnavailable(msg)
        source = _source_from_frontmatter(
            record.frontmatter,
            fallback_id=record.canonical_id,
            scope="commons",
        )
        if source is not None:
            sources.append(source)
    return sources


def benchmark_sources(project_root: Path, *, include_commons: bool = False) -> tuple[list[BenchmarkSource], str | None]:
    sources = _local_sources(project_root)
    notice: str | None = None
    if include_commons:
        try:
            sources.extend(_commons_sources())
        except CommonsUnavailable as exc:
            notice = str(exc)
    return sources, notice


def _local_rows(project_root: Path) -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    for source in _local_sources(project_root):
        row = _row_from_frontmatter(
            source["frontmatter"],
            fallback_id=source["fallback_id"],
            scope=source["scope"],
        )
        if row is not None:
            rows.append(row)
    return rows


def _commons_rows() -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    for source in _commons_sources():
        row = _row_from_frontmatter(
            source["frontmatter"],
            fallback_id=source["fallback_id"],
            scope=source["scope"],
        )
        if row is not None:
            rows.append(row)
    return rows


def _has_belief_token(row: BenchmarkRow, query: str) -> bool:
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
    row: BenchmarkRow,
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
) -> tuple[list[BenchmarkRow], str | None]:
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


def coverage_summary(rows: list[BenchmarkRow]) -> dict[str, dict[str, int]]:
    counters: dict[str, Counter[str]] = {
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
