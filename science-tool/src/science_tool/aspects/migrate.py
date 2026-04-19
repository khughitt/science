"""Build and apply the one-shot aspect migration for legacy task entries."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from science_model.aspects import SOFTWARE_ASPECT, load_project_aspects
from science_tool.tasks import parse_tasks


@dataclass(frozen=True)
class TaskRewrite:
    task_id: str
    source_path: Path
    new_aspects: list[str]


@dataclass(frozen=True)
class TaskConflict:
    task_id: str
    source_path: Path
    reason: str


@dataclass(frozen=True)
class AspectsMigrationPlan:
    task_rewrites: list[TaskRewrite] = field(default_factory=list)
    conflicts: list[TaskConflict] = field(default_factory=list)


class AspectsMigrationConflict(RuntimeError):
    """Raised when migration cannot safely proceed without user action."""


def build_migration_plan(project_root: Path) -> AspectsMigrationPlan:
    """Scan project task files and produce a migration plan.

    Rules:
    - `type: dev` → `aspects: [software-development]`.
    - `type: research` → `aspects: <project.aspects \\ {software-development}>`.
      Falls back to full project.aspects if the set difference is empty.
    - Task already carrying `aspects:` and no `type:`: skipped.
    - Task carrying both `type:` and `aspects:`: reported as a conflict, no rewrite.
    - Project with no `aspects:` in science.yaml: raises
      ``AspectsMigrationConflict`` because there is no target vocabulary.
    """
    project_aspects = load_project_aspects(project_root)
    if not project_aspects:
        raise AspectsMigrationConflict(
            "Project science.yaml has no 'aspects:' declaration; "
            "migration has no target vocabulary."
        )
    non_software = [a for a in project_aspects if a != SOFTWARE_ASPECT]

    rewrites: list[TaskRewrite] = []
    conflicts: list[TaskConflict] = []

    tasks_dir = project_root / "tasks"
    task_files = [tasks_dir / "active.md"]
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        task_files.extend(sorted(done_dir.glob("*.md")))

    for path in task_files:
        if not path.is_file():
            continue
        for task in parse_tasks(path):
            legacy_type = (task.type or "").strip()
            has_aspects = bool(task.aspects)

            if not legacy_type:
                continue
            if has_aspects:
                conflicts.append(
                    TaskConflict(
                        task_id=task.id,
                        source_path=path,
                        reason=(
                            f"task carries both 'type: {legacy_type}' and "
                            f"'aspects: {task.aspects}'; manual cleanup required."
                        ),
                    )
                )
                continue

            if legacy_type == "dev":
                target = [SOFTWARE_ASPECT]
            elif legacy_type == "research":
                target = non_software or list(project_aspects)
            else:
                conflicts.append(
                    TaskConflict(
                        task_id=task.id,
                        source_path=path,
                        reason=f"unknown legacy task type: {legacy_type!r}",
                    )
                )
                continue

            rewrites.append(
                TaskRewrite(task_id=task.id, source_path=path, new_aspects=target)
            )

    return AspectsMigrationPlan(task_rewrites=rewrites, conflicts=conflicts)


def apply_migration_plan(plan: AspectsMigrationPlan) -> None:
    """Apply the rewrites in ``plan`` in place.

    For each `TaskRewrite`: parse the source file, find the task by ID,
    remove its `type` field and set `aspects` to the target list, then
    re-render the whole file. Preserves all other task content.
    """
    from collections import defaultdict

    from science_tool.tasks import parse_tasks, render_tasks

    rewrites_by_path: dict[Path, dict[str, list[str]]] = defaultdict(dict)
    for rewrite in plan.task_rewrites:
        rewrites_by_path[rewrite.source_path][rewrite.task_id] = rewrite.new_aspects

    for path, per_task in rewrites_by_path.items():
        tasks = parse_tasks(path)
        for task in tasks:
            if task.id in per_task:
                task.aspects = per_task[task.id]
                task.type = ""  # drop legacy field
        path.write_text(render_tasks(tasks))
