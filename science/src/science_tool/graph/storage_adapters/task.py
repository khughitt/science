"""TaskAdapter — parses strict YAML active-task files and DSL done ledgers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef
from science_model.tasks import Task

from science_tool.graph.storage_adapters.base import StorageAdapter
from science_tool.tasks import _require_split, parse_task_file, parse_tasks


def _parse_task_path(path: Path) -> list[Task]:
    """Parse a task path according to its canonical storage location."""
    if path.parent.name == "active" and path.parent.parent.name == "tasks":
        return [parse_task_file(path)]
    if path.parent.name == "done" and path.parent.parent.name == "tasks":
        return parse_tasks(path)
    raise ValueError(f"unsupported task storage path: {path}")


class TaskAdapter(StorageAdapter):
    name = "task"

    def __init__(self) -> None:
        self._tasks_by_path: dict[str, list[Task]] = {}

    def discover(self, project_root: Path) -> list[SourceRef]:
        self._tasks_by_path.clear()
        tasks_dir = project_root / "tasks"
        _require_split(tasks_dir)
        if not tasks_dir.is_dir():
            return []
        refs: list[SourceRef] = []
        task_paths = [
            *(tasks_dir / "active").glob("*.md"),
            *(tasks_dir / "done").glob("*.md"),
        ]
        for path in sorted(task_paths):
            try:
                rel = str(path.relative_to(project_root))
            except ValueError:
                rel = str(path)
            parsed = _parse_task_path(path)
            self._tasks_by_path[rel] = parsed
            for idx, _task in enumerate(parsed):
                refs.append(SourceRef(adapter_name=self.name, path=rel, line=idx))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        assert ref.line is not None, "TaskAdapter SourceRef must carry line (task index)"
        path = Path(ref.path)
        if not path.is_absolute():
            path = Path.cwd() / path
        tasks = self._tasks_by_path.get(ref.path)
        if tasks is None:
            tasks = _parse_task_path(path)
        task = tasks[ref.line]
        return {
            "id": f"task:{task.id}",
            "canonical_id": f"task:{task.id}",
            "kind": "task",
            "type": "task",
            "task_type": task.type,
            "title": task.title,
            "project": task.project or "",
            "priority": task.priority,
            "status": task.status,
            "blocked_by": task.blocked_by,
            "related": task.related,
            "parent": task.parent,
            "group": task.group,
            "aspects": task.aspects,
            "artifacts": task.artifacts,
            "findings": task.findings,
            "created": task.created,
            "completed": task.completed,
            "content": task.description,
            "content_preview": task.description[:200] if task.description else "",
            "file_path": ref.path,
            "ontology_terms": [],
            "source_refs": [],
        }
