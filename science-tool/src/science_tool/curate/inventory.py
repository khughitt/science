"""Deterministic inventory helpers for `/science:curate`."""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import TypeAlias

from pydantic import BaseModel, Field
import yaml

from science_model.frontmatter import parse_frontmatter

from science_tool.tasks import parse_tasks

ArtifactClass: TypeAlias = str

_RECENT_DAYS = 7
_LONG_IDLE_DAYS = 30
_RELATED_CLASSES = {"hypothesis", "interpretation", "paper", "question"}
_SOURCE_REF_CLASSES = {"interpretation", "paper"}


class InventoryArtifact(BaseModel):
    path: str
    artifact_class: ArtifactClass
    id: str | None = None
    title: str | None = None
    related_count: int = 0
    source_refs_count: int = 0
    modified_days_ago: int | None = None


class CandidateSignals(BaseModel):
    missing_related: list[str] = Field(default_factory=list)
    missing_source_refs: list[str] = Field(default_factory=list)
    no_outbound_links: list[str] = Field(default_factory=list)
    recently_modified: list[str] = Field(default_factory=list)
    long_idle: list[str] = Field(default_factory=list)


class CurationInventory(BaseModel):
    project_root: str
    artifact_counts: dict[str, int] = Field(default_factory=dict)
    artifacts: list[InventoryArtifact] = Field(default_factory=list)
    candidate_signals: CandidateSignals = Field(default_factory=CandidateSignals)


def collect_inventory(project_root: Path, today: date | None = None) -> CurationInventory:
    """Collect a deterministic inventory of curated project artifacts."""
    project_root = Path(project_root)
    today = today or datetime.now(tz=timezone.utc).date()

    records: list[InventoryArtifact] = []
    candidate_signals = CandidateSignals()

    for path in _collect_markdown_paths(project_root):
        record = _record_markdown(project_root, path, today)
        if record is None:
            continue
        records.append(record)
        _accumulate_markdown_signals(record, candidate_signals)

    for path in _collect_task_paths(project_root):
        records.extend(_record_tasks(project_root, path, today))

    for path in _collect_knowledge_source_paths(project_root):
        record = _record_knowledge_source(project_root, path, today)
        if record is not None:
            records.append(record)

    records.sort(key=lambda record: record.path)
    artifacts = records

    artifact_counts: dict[str, int] = {}
    for artifact in artifacts:
        artifact_counts[artifact.artifact_class] = artifact_counts.get(artifact.artifact_class, 0) + 1

    modified_lookup = {artifact.path: artifact.modified_days_ago for artifact in artifacts}
    candidate_signals.recently_modified = sorted(
        [
            artifact.path
            for artifact in artifacts
            if artifact.modified_days_ago is not None and artifact.modified_days_ago <= _RECENT_DAYS
        ],
        key=lambda path: (modified_lookup[path] or 0, path),
    )
    candidate_signals.long_idle = sorted(
        [
            artifact.path
            for artifact in artifacts
            if artifact.modified_days_ago is not None and artifact.modified_days_ago >= _LONG_IDLE_DAYS
        ],
        key=lambda path: (modified_lookup[path] or 0, path),
    )

    return CurationInventory(
        project_root=str(project_root),
        artifact_counts=artifact_counts,
        artifacts=artifacts,
        candidate_signals=candidate_signals,
    )


def _collect_markdown_paths(project_root: Path) -> list[Path]:
    paths: dict[Path, None] = {}
    for pattern in ("specs/**/*.md", "doc/**/*.md"):
        for path in project_root.glob(pattern):
            if path.is_file():
                paths[path] = None
    return sorted(paths)


def _collect_task_paths(project_root: Path) -> list[Path]:
    paths: dict[Path, None] = {}
    for pattern in ("tasks/active.md", "tasks/done/**/*.md"):
        for path in project_root.glob(pattern):
            if path.is_file():
                paths[path] = None
    return sorted(paths)


def _collect_knowledge_source_paths(project_root: Path) -> list[Path]:
    paths: dict[Path, None] = {}
    for path in project_root.glob("knowledge/sources/**/*.yaml"):
        if path.is_file():
            paths[path] = None
    return sorted(paths)


def _record_markdown(project_root: Path, path: Path, today: date) -> InventoryArtifact | None:
    fm_body = parse_frontmatter(path)
    if fm_body is None:
        return None
    fm, _body = fm_body
    rel_path = path.relative_to(project_root)
    artifact_class = _markdown_artifact_class(rel_path)
    if artifact_class is None:
        return None
    return InventoryArtifact(
        path=str(rel_path),
        artifact_class=artifact_class,
        id=str(fm["id"]) if fm.get("id") else None,
        title=str(fm["title"]) if fm.get("title") else None,
        related_count=_count_entries(fm.get("related")),
        source_refs_count=_count_entries(fm.get("source_refs")),
        modified_days_ago=_modified_days_ago(path, today),
    )


def _record_tasks(project_root: Path, path: Path, today: date) -> list[InventoryArtifact]:
    records: list[InventoryArtifact] = []
    for task in parse_tasks(path):
        records.append(
            InventoryArtifact(
                path=f"{path.relative_to(project_root)}#{task.id}",
                artifact_class="task",
                id=task.id,
                title=task.title,
                related_count=len(task.related),
                source_refs_count=0,
                modified_days_ago=_modified_days_ago(path, today),
            )
        )
    return records


def _record_knowledge_source(project_root: Path, path: Path, today: date) -> InventoryArtifact | None:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict) or not data.get("id"):
        return None
    rel_path = path.relative_to(project_root)
    return InventoryArtifact(
        path=str(rel_path),
        artifact_class="knowledge_source",
        id=str(data["id"]),
        title=str(data["title"]) if data.get("title") else None,
        related_count=_count_entries(data.get("related")),
        source_refs_count=_count_entries(data.get("source_refs")),
        modified_days_ago=_modified_days_ago(path, today),
    )


def _accumulate_markdown_signals(record: InventoryArtifact, signals: CandidateSignals) -> None:
    if record.artifact_class in _RELATED_CLASSES and record.related_count == 0:
        signals.missing_related.append(record.path)
    if record.artifact_class in _SOURCE_REF_CLASSES and record.source_refs_count == 0:
        signals.missing_source_refs.append(record.path)
    if record.related_count == 0 and record.source_refs_count == 0:
        signals.no_outbound_links.append(record.path)


def _count_entries(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, list):
        return len(value)
    return 1


def _modified_days_ago(path: Path, today: date) -> int | None:
    if not path.is_file():
        return None
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).date()
    return (today - modified).days


def _markdown_artifact_class(path: Path) -> str | None:
    parts = path.parts
    if len(parts) >= 3 and parts[0] == "specs" and parts[1] == "hypotheses":
        return "hypothesis"
    if len(parts) >= 3 and parts[0] == "doc":
        directory = parts[1]
        return {
            "questions": "question",
            "papers": "paper",
            "interpretations": "interpretation",
        }.get(directory)
    return None
