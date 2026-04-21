"""TaskAdapter — wraps the existing task DSL parser and emits TaskEntity raw records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter
from science_tool.tasks import parse_tasks


class TaskAdapter(StorageAdapter):
    name = "task"

    def discover(self, project_root: Path) -> list[SourceRef]:
        tasks_dir = project_root / "tasks"
        if not tasks_dir.is_dir():
            return []
        refs: list[SourceRef] = []
        for path in sorted(tasks_dir.rglob("*.md")):
            try:
                rel = str(path.relative_to(project_root))
            except ValueError:
                rel = str(path)
            parsed = parse_tasks(path)
            for idx, _task in enumerate(parsed):
                refs.append(SourceRef(adapter_name=self.name, path=rel, line=idx))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        assert ref.line is not None, "TaskAdapter SourceRef must carry line (task index)"
        path = Path(ref.path)
        if not path.is_absolute():
            path = Path.cwd() / path
        tasks = parse_tasks(path)
        task = tasks[ref.line]
        return {
            "id": f"task:{task.id}",
            "canonical_id": f"task:{task.id}",
            "kind": "task",
            "type": "task",
            "title": task.title,
            "project": task.project or "",
            "priority": task.priority,
            "status": task.status,
            "blocked_by": task.blocked_by,
            "related": task.related,
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
