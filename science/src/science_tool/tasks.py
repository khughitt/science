"""Task markdown parser/renderer and CRUD operations for science.

The Task model is defined in science-model and re-exported here for convenience.
"""

from __future__ import annotations

import fcntl
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Iterator

import yaml
from science_model.frontmatter import atomic_write_text
from science_model.tasks import Task, TaskCreate, TaskStatus, TaskUpdate
from science_tool.markdown_utils import reject_duplicate_and_merge_keys

__all__ = [
    "Task",
    "TaskCreate",
    "TaskAspectValidationError",
    "TaskIntegrityError",
    "TaskLocation",
    "TaskStatus",
    "TaskUpdate",
    "StorageState",
    "append_task_note",
    "delete_task_file",
    "find_dangling_task_refs",
    "find_task_location",
    "parse_task_file",
    "parse_tasks_for_cli",
    "render_task_file",
    "retire_task",
    "validate_task_aspects",
    "write_task_file",
    "write_task_location",
]

_VALID_STATUSES = {s.value for s in TaskStatus}
_REQUIRED_KEYS = ("id", "title", "status", "priority", "aspects", "created")
_KNOWN_KEYS = frozenset(
    {
        "id",
        "project",
        "title",
        "type",
        "aspects",
        "priority",
        "status",
        "blocked_by",
        "related",
        "parent",
        "group",
        "artifacts",
        "findings",
        "created",
        "completed",
    }
)
_OPEN_STATUSES = frozenset({"proposed", "active", "blocked", "deferred"})
_MIGRATION_JOURNAL = Path(".science/task-storage-migration.journal")


class StorageState(Enum):
    """The authoritative task-storage layout state."""

    EMPTY = "empty"
    SPLIT = "split"
    LEGACY = "legacy"
    MIGRATING = "migrating"
    CONFLICT = "conflict"


class TaskIntegrityError(ValueError):
    """A task-file write would corrupt or lose data and was refused.

    Raised by the round-trip guard when the text about to be persisted does not
    re-parse to the tasks it was rendered from (e.g. a description line starting
    with ``## [`` is mistaken for a task header), so callers never silently
    write a self-corrupting file.
    """


_TASK_ID_PATTERN = r"t[0-9]{3,}"
_HEADER_RE = re.compile(rf"^##\s+\[({_TASK_ID_PATTERN})\]\s+(.+)$")
_ANY_TASK_HEADER_RE = re.compile(r"^##\s+\[([^\]]+)\]\s+(.+)$")
_FIELD_RE = re.compile(r"^-\s+([\w-]+):\s*(.*)$")
_LIST_RE = re.compile(r"^\[(.+)\]$")
_MARKDOWN_HEADING_RE = re.compile(r"^(#{1,3})\s+.+$")
_NOTES_HEADING_RE = re.compile(r"^###\s+Notes\s*$")
_LOCAL_PARENT_RE = re.compile(r"^task:t[0-9]{3,}$")
_TASK_HEADING_PREFIX_RE = re.compile(r"^##\s+\[", re.MULTILINE)
_SPLITLINES_BOUNDARIES = "\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029"
_KNOWN_DSL_FIELDS = frozenset(
    {
        "type",
        "priority",
        "status",
        "parent",
        "aspects",
        "related",
        "blocked-by",
        "group",
        "created",
        "completed",
        "project",
        "artifacts",
        "findings",
    }
)


def _render_list_value(items: list[str]) -> str:
    """Render a list as a JSON array so every string round-trips."""
    return json.dumps(items, ensure_ascii=True)


def _parse_list_value(raw: str, *, field: str = "list") -> list[str]:
    """Parse a JSON array, tolerating legacy bare bracketed lists."""
    raw = raw.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            m = _LIST_RE.match(raw)
            if not m or '"' in m.group(1) or "\\" in m.group(1):
                raise ValueError(f"malformed {field} list value: {raw!r}") from None
            return [item.strip() for item in m.group(1).split(",") if item.strip()]
        if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
            raise ValueError(f"{field} list must be a JSON array of strings: {raw!r}")
        return parsed
    raise ValueError(f"malformed {field} list value (expected '[...]'): {raw!r}")


def _render_scalar(value: str) -> str:
    """Render a scalar reversibly while keeping ordinary values readable."""
    if (
        value != value.strip()
        or any(char in value for char in _SPLITLINES_BOUNDARIES)
        or '"' in value
    ):
        return json.dumps(value, ensure_ascii=True)
    return value


def _parse_scalar(raw: str) -> str:
    """Parse a scalar emitted by :func:`_render_scalar`."""
    if raw.startswith('"'):
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed quoted scalar: {raw!r}") from exc
        if not isinstance(decoded, str):
            raise ValueError(f"scalar must decode to a string: {raw!r}")
        return decoded
    return raw


def _parse_task_header(line: str, *, path: Path | None = None) -> tuple[str, str]:
    """Parse and validate a task header line."""
    match = _HEADER_RE.match(line)
    if match:
        task_id, title = match.group(1), match.group(2).strip()
        _validate_task_title(title)
        return task_id, title

    loose = _ANY_TASK_HEADER_RE.match(line)
    if loose:
        task_id = loose.group(1)
        where = f" in {path}" if path is not None else ""
        msg = (
            f"Invalid task id '{task_id}'{where}: task ids must match tNNN. "
            "Use parent: task:t001 for fragments or subtasks."
        )
        raise ValueError(msg)

    where = f" in {path}" if path is not None else ""
    raise ValueError(f"Invalid task header{where}: {line}")


def _validate_task_title(title: str) -> None:
    """Reject titles that cannot be represented safely in either task format."""
    if (
        not title
        or title != title.strip()
        or any(char in title for char in _SPLITLINES_BOUNDARIES)
    ):
        raise ValueError(
            "task title must be non-empty, have no leading or trailing whitespace, "
            "and be single-line"
        )


class TaskAspectValidationError(ValueError):
    """Raised when task-scoped aspects are malformed."""


def validate_task_aspects(aspects: list[str]) -> list[str]:
    """Validate task-scoped aspect labels.

    Task aspects are local routing metadata: they use the shared aspect
    vocabulary, but do not require the aspect to be enabled globally in
    science.yaml.
    """
    from science_model.aspects import KNOWN_ASPECTS

    if not aspects:
        raise TaskAspectValidationError("Task aspects list is empty; omit --aspects instead.")
    seen: set[str] = set()
    validated: list[str] = []
    for aspect in aspects:
        if aspect in seen:
            raise TaskAspectValidationError(f"duplicate task aspect: {aspect!r}")
        seen.add(aspect)
        if aspect not in KNOWN_ASPECTS:
            raise TaskAspectValidationError(
                f"{aspect!r} is not in the aspect vocabulary ({sorted(KNOWN_ASPECTS)})."
            )
        validated.append(aspect)
    return validated


def _parse_parent(raw: str, *, task_id: str) -> str:
    parent = raw.strip()
    if not parent:
        return ""
    if _LOCAL_PARENT_RE.match(parent):
        return parent
    raise ValueError(f"parent for task {task_id} must be local task ref like task:t001")


def _required_field(fields: dict[str, str], field: str, *, task_id: str, path: Path | None) -> str:
    try:
        return fields[field]
    except KeyError as exc:
        where = f" in {path}" if path is not None else ""
        raise ValueError(f"task {task_id}{where} missing required field: {field}") from exc


def _parse_task_block(lines: list[str], *, path: Path | None = None) -> Task:
    """Parse a single task block (header line + metadata + description)."""
    task_id, title = _parse_task_header(lines[0], path=path)

    fields: dict[str, str] = {}
    desc_start = 1
    seen_field = False
    for i, line in enumerate(lines[1:], start=1):
        fm = _FIELD_RE.match(line)
        if fm:
            seen_field = True
            key = fm.group(1)
            where = f" in {path}" if path is not None else ""
            if key in fields:
                raise ValueError(f"duplicate metadata key {key!r} for task {task_id}{where}")
            if key not in _KNOWN_DSL_FIELDS:
                raise ValueError(f"unknown metadata key {key!r} for task {task_id}{where}")
            fields[key] = fm.group(2).strip()
            desc_start = i + 1
        elif line.strip() == "":
            if not seen_field:
                desc_start = i + 1
                continue
            desc_start = i + 1
            break
        else:
            break

    # Collect description lines (skip leading/trailing blank lines)
    desc_lines = lines[desc_start:]
    description = "\n".join(desc_lines).strip()

    created = date.fromisoformat(_required_field(fields, "created", task_id=task_id, path=path))
    completed_raw = fields.get("completed")
    completed = date.fromisoformat(completed_raw) if completed_raw else None

    return Task(
        id=task_id,
        title=title,
        type=_parse_scalar(fields.get("type", "")),
        aspects=_parse_list_value(fields.get("aspects", ""), field="aspects"),
        priority=fields.get("priority", ""),
        status=fields.get("status", ""),
        created=created,
        description=description,
        related=_parse_list_value(fields.get("related", ""), field="related"),
        parent=_parse_parent(_parse_scalar(fields.get("parent", "")), task_id=task_id),
        blocked_by=_parse_list_value(fields.get("blocked-by", ""), field="blocked-by"),
        group=_parse_scalar(fields.get("group", "")),
        project=_parse_scalar(fields.get("project", "")),
        artifacts=_parse_list_value(fields.get("artifacts", ""), field="artifacts"),
        findings=_parse_list_value(fields.get("findings", ""), field="findings"),
        completed=completed,
    )


def _parse_tasks_text(text: str, *, path: Path | None = None) -> list[Task]:
    """Parse task blocks from markdown text (no file I/O)."""
    if not text.strip():
        return []

    lines = text.splitlines()
    # Split into blocks at task headers, including malformed task headers so
    # validation can fail with a task-ID-specific error.
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if _ANY_TASK_HEADER_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)

    return [_parse_task_block(block, path=path) for block in blocks]


def parse_tasks(path: Path) -> list[Task]:
    """Parse tasks from a markdown file. Returns empty list if file is missing or empty."""
    if not path.is_file():
        return []
    return _parse_tasks_text(path.read_text(), path=path)


def _split_frontmatter_text(text: str) -> tuple[str, str]:
    """Return raw YAML frontmatter and Markdown body from a fenced document."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", text
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return "".join(lines[1:index]), "".join(lines[index + 1 :])
    return "", text


def _load_task_frontmatter(text: str, *, path: Path) -> tuple[dict[str, object], str]:
    """Load strict YAML frontmatter and body from one file-text snapshot."""
    frontmatter_text, body = _split_frontmatter_text(text)

    try:
        node = yaml.compose(frontmatter_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML frontmatter: {exc}") from exc
    if node is not None:
        reject_duplicate_and_merge_keys(
            node,
            on_error=lambda message: ValueError(f"{path}: {message}"),
        )

    try:
        loaded = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: invalid YAML frontmatter: {exc}") from exc
    if loaded is None:
        return {}, body
    if not isinstance(loaded, dict):
        raise ValueError(f"{path}: frontmatter must be a mapping")
    return loaded, body


def _task_id_from_frontmatter(data: dict[str, object], *, path: Path) -> str:
    if "id" not in data:
        raise ValueError(f"{path}: missing required key: id")
    task_id = data["id"]
    if not isinstance(task_id, str):
        raise ValueError(f"{path}: id must be a string")
    if not re.fullmatch(_TASK_ID_PATTERN, task_id):
        raise ValueError(f"{path}: non-canonical task id {task_id!r}")
    return task_id


def _validate_active_filename(path: Path, task_id: str) -> None:
    """Require an active filename to carry the same canonical id as its task."""
    if not path.name.startswith(f"{task_id}-") and path.name != f"{task_id}.md":
        raise ValueError(f"{path}: filename does not match id {task_id!r}")


def parse_task_file(path: Path) -> Task:
    """Parse one canonical open-task file with strict identity validation."""
    text = path.read_text(encoding="utf-8")
    data, body = _load_task_frontmatter(text, path=path)

    unknown = set(data) - _KNOWN_KEYS
    if unknown:
        raise ValueError(f"{path}: unknown frontmatter key(s): {sorted(unknown)}")

    for key in _REQUIRED_KEYS:
        if key not in data:
            raise ValueError(f"{path}: missing required key: {key}")

    task_id = _task_id_from_frontmatter(data, path=path)
    _validate_active_filename(path, task_id)

    title = str(data["title"])
    try:
        _validate_task_title(title)
    except ValueError as exc:
        raise ValueError(f"{path}: {exc}") from exc

    if str(data["status"]) not in _OPEN_STATUSES:
        raise ValueError(
            f"{path}: status {data['status']!r} not open; active/ holds open tasks only"
        )

    return Task.model_validate({**data, "description": body.strip()})


def _canonical_description(text: str) -> str:
    return text.strip()


def _tasks_equal(a: Task, b: Task) -> bool:
    return a.model_copy(update={"description": _canonical_description(a.description)}) == b.model_copy(
        update={"description": _canonical_description(b.description)}
    )


def _move_recovery_equivalent(
    active: Task,
    ledger: Task,
    *,
    target_status: str,
) -> bool:
    """Return whether ``ledger`` is the prior append for this terminal move."""
    if active.id != ledger.id or ledger.status != target_status:
        return False

    ignored_transition_fields = {
        "status": "",
        "completed": None,
        "description": "",
    }
    stable_fields_match = _tasks_equal(
        active.model_copy(update=ignored_transition_fields),
        ledger.model_copy(update=ignored_transition_fields),
    )
    description_extends_active = _canonical_description(ledger.description).startswith(
        _canonical_description(active.description)
    )
    return stable_fields_match and description_extends_active


def _verify_round_trip(text: str, expected: list[Task], *, path: Path | None) -> None:
    """Guard against silent task-file corruption / data loss.

    Re-parse the text we are about to persist and confirm it yields exactly the
    tasks it was rendered from (all fields). The common failure
    is a description line starting with ``## [`` (a task-header shape) which the
    parser would split into a phantom block on the next read.
    """
    try:
        reparsed = _parse_tasks_text(text, path=path)
    except ValueError as exc:
        raise TaskIntegrityError(
            f"refusing to write {path}: the rendered task file does not parse back "
            f"({exc}). A task description likely contains a line starting with "
            f"'## [' — indent or rephrase it so it is not read as a task header."
        ) from exc
    got = [t.id for t in reparsed]
    want = [t.id for t in expected]
    if got != want:
        raise TaskIntegrityError(
            f"refusing to write {path}: task set changed on round-trip "
            f"(expected {want}, got {got}); aborting to avoid data loss."
        )
    for original, parsed in zip(expected, reparsed):
        if not _tasks_equal(original, parsed):
            raise TaskIntegrityError(
                f"refusing to write {path}: task {original.id} does not round-trip "
                f"(a field is being mangled by the DSL grammar); aborting to avoid data loss."
            )


def _verify_task_file_round_trip(text: str, task: Task, path: Path) -> None:
    """Refuse a per-task file whose rendered text does not fully re-parse."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        candidate = Path(temporary_directory) / path.name
        candidate.write_text(text, encoding="utf-8")
        try:
            reparsed = parse_task_file(candidate)
        except (OSError, ValueError) as exc:
            raise TaskIntegrityError(
                f"refusing to write {path}: rendered task file failed round-trip "
                f"parsing ({exc})"
            ) from exc

    if not _tasks_equal(reparsed, task):
        raise TaskIntegrityError(
            f"refusing to write {path}: task {task.id} does not round-trip "
            f"(a field changed during serialization)"
        )


def _active_dir(tasks_dir: Path) -> Path:
    """Return the canonical per-file open-task directory.

    Mutation callers must hold ``_task_allocation_lock``; this helper never
    acquires it.
    """
    return tasks_dir / "active"


def _tasks_storage_state(tasks_dir: Path) -> StorageState:
    """Classify task storage, treating a migration journal as authoritative."""
    if (tasks_dir / _MIGRATION_JOURNAL).exists():
        return StorageState.MIGRATING

    has_legacy = (tasks_dir / "active.md").is_file()
    has_split = any(path.is_file() for path in _active_dir(tasks_dir).glob("*.md"))
    if has_legacy and has_split:
        return StorageState.CONFLICT
    if has_legacy:
        return StorageState.LEGACY
    if has_split:
        return StorageState.SPLIT
    return StorageState.EMPTY


def _require_split(tasks_dir: Path) -> None:
    """Allow normal commands only against empty or split task storage."""
    state = _tasks_storage_state(tasks_dir)
    if state in {StorageState.EMPTY, StorageState.SPLIT}:
        return
    if state is StorageState.LEGACY:
        raise ValueError(
            "tasks/active.md predates the storage split; "
            "run `science tasks migrate-storage --apply`."
        )
    if state is StorageState.MIGRATING:
        raise ValueError(
            "an interrupted storage migration is in progress; "
            "run `science tasks migrate-storage --resume`."
        )
    raise ValueError(
        "both tasks/active.md and tasks/active/ exist with no migration journal; "
        "inspect and remove one by hand — this is not an auto-resumable migration."
    )


def _find_active_file(tasks_dir: Path, task_id: str) -> Path | None:
    """Find the unique active file for ``task_id``, refusing duplicates.

    Mutation callers must hold ``_task_allocation_lock``; this helper never
    acquires it.
    """
    if re.fullmatch(_TASK_ID_PATTERN, task_id) is None:
        raise ValueError(f"non-canonical task id {task_id!r}; expected tNNN")
    active = _active_dir(tasks_dir)
    matches = sorted(active.glob(f"{task_id}-*.md"))
    slugless = active / f"{task_id}.md"
    if slugless.is_file():
        matches.append(slugless)
    if len(matches) > 1:
        locations = ", ".join(str(path) for path in matches)
        raise ValueError(f"duplicate active task files for {task_id}: {locations}")
    active_index = _active_task_index(tasks_dir)
    existing = active_index.get(task_id)
    if existing is None:
        return None
    parse_task_file(existing)
    return existing


def _slug_for(title: str) -> str | None:
    """Derive a task filename slug, deliberately choosing no slug if impossible."""
    # Deferred to avoid tasks -> entities -> graph.sources -> tasks at import time.
    from science_tool.entities import EntityCommandError, derive_slug  # noqa: PLC0415

    try:
        return derive_slug(title)
    except EntityCommandError:
        return None


def write_task_file(tasks_dir: Path, task: Task) -> None:
    """Atomically write one open task file.

    The caller must hold ``_task_allocation_lock``; this helper does not acquire
    the lock itself.
    """
    active = _active_dir(tasks_dir)
    active.mkdir(parents=True, exist_ok=True)
    text = render_task_file(task)
    _verify_task_file_round_trip(text, task, path=active / f"{task.id}.md")
    existing = _find_active_file(tasks_dir, task.id)
    slug = _slug_for(task.title)
    target = active / (f"{task.id}-{slug}.md" if slug else f"{task.id}.md")

    if existing is None:
        atomic_write_text(target, text)
        return
    if existing == target:
        atomic_write_text(target, text)
        return

    atomic_write_text(existing, text)
    if target.exists():
        raise ValueError(f"rename target already exists: {target}")
    os.replace(existing, target)


def delete_task_file(tasks_dir: Path, task_id: str) -> None:
    """Delete one active task file.

    The caller must hold ``_task_allocation_lock``; this helper does not acquire
    the lock itself.
    """
    existing = _find_active_file(tasks_dir, task_id)
    if existing is None:
        raise FileNotFoundError(f"active task file not found: {task_id}")
    existing.unlink()


def _task_ref_number(ref: str) -> str | None:
    """Extract a bare tNNN id from a task ref like 'task:t001' or 't001'."""
    candidate = ref.strip()
    if candidate.startswith("task:"):
        candidate = candidate[len("task:") :]
    return candidate if re.fullmatch(_TASK_ID_PATTERN, candidate) else None


def find_dangling_task_refs(tasks_dir: Path) -> dict[str, list[str]]:
    """Map task-id -> blocked_by/parent task refs that do not resolve to a known task.

    A post-write self-check: if a sibling task block was dropped, a surviving
    `blocked-by: [task:tNNN]` (or `parent:`) is reported here so the problem is
    caught at the task layer rather than only at `graph build`.
    """
    _require_split(tasks_dir)
    known = known_task_ids(tasks_dir, require_split=False)
    dangling: dict[str, list[str]] = {}
    for path in _task_search_paths(tasks_dir, require_split=False):
        for task in _parse_path_tasks(path):
            bad: list[str] = []
            for ref in [*task.blocked_by, task.parent]:
                if not ref:
                    continue
                num = _task_ref_number(ref)
                if num is not None and num not in known:
                    bad.append(ref)
            if bad:
                dangling[task.id] = bad
    return dangling


def parse_tasks_for_cli(
    tasks_dir: Path,
    *,
    require_split: bool = True,
) -> tuple[list[Task], list[str]]:
    """Parse tasks AND surface user-facing warnings.

    Detects legacy untyped blocker refs and returns them as warning strings.
    Programmatic callers should prefer `_read_active` to avoid noise.
    """
    # Deferred import to avoid a circular dependency:
    # tasks_blockers -> entities -> graph -> tasks
    from science_tool.tasks_blockers import is_typed_ref  # noqa: PLC0415

    tasks = _read_active(tasks_dir, require_split=require_split)
    warnings: list[str] = []
    for task in tasks:
        for ref in task.blocked_by:
            if not is_typed_ref(ref):
                warnings.append(
                    f"task {task.id}: legacy untyped blocker {ref!r} — run 'science tasks fix-blockers' to retype"
                )
    return tasks, warnings


def render_task(task: Task) -> str:
    """Render a single task to markdown."""
    lines = [f"## [{task.id}] {task.title}"]
    if task.type:
        lines.append(f"- type: {_render_scalar(task.type)}")
    lines.append(f"- priority: {task.priority}")
    lines.append(f"- status: {task.status}")
    if task.parent:
        lines.append(f"- parent: {_render_scalar(task.parent)}")
    if task.project:
        lines.append(f"- project: {_render_scalar(task.project)}")
    # aspects is a validate-required field, so emit it even when empty
    # (a task added without --aspects must still be validate-clean).
    lines.append(f"- aspects: {_render_list_value(task.aspects)}")
    if task.related:
        lines.append(f"- related: {_render_list_value(task.related)}")
    if task.blocked_by:
        lines.append(f"- blocked-by: {_render_list_value(task.blocked_by)}")
    if task.group:
        lines.append(f"- group: {_render_scalar(task.group)}")
    if task.artifacts:
        lines.append(f"- artifacts: {_render_list_value(task.artifacts)}")
    if task.findings:
        lines.append(f"- findings: {_render_list_value(task.findings)}")
    lines.append(f"- created: {task.created.isoformat()}")
    if task.completed is not None:
        lines.append(f"- completed: {task.completed.isoformat()}")
    lines.append("")
    lines.append(task.description)
    return "\n".join(lines) + "\n"


def render_task_file(task: Task) -> str:
    """Render one task as full YAML frontmatter followed by its description."""
    frontmatter = task.model_dump(mode="json")
    del frontmatter["description"]
    rendered_frontmatter = yaml.safe_dump(
        frontmatter,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    )
    description = _canonical_description(task.description)
    if not description:
        return f"---\n{rendered_frontmatter}---\n"
    return f"---\n{rendered_frontmatter}---\n\n{description}\n"


def render_tasks(tasks: list[Task]) -> str:
    """Render a list of tasks to markdown."""
    return "\n".join(render_task(t) for t in tasks)


def _strict_task_ids_in_text(text: str) -> list[str]:
    ids: list[str] = []
    for line in text.splitlines():
        match = _HEADER_RE.match(line)
        if match:
            ids.append(match.group(1))
    return ids


def _strict_task_ids_in_path(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    if path.parent.name == "active":
        data, _body = _load_task_frontmatter(text, path=path)
        task_id = _task_id_from_frontmatter(data, path=path)
        _validate_active_filename(path, task_id)
        return [task_id]
    return _strict_task_ids_in_text(text)


def _active_task_index(tasks_dir: Path) -> dict[str, Path]:
    """Index active files by semantic id after validating store-wide identity."""
    active = _active_dir(tasks_dir)
    index: dict[str, Path] = {}
    for path in sorted(active.glob("*.md")):
        task_ids = _strict_task_ids_in_path(path)
        for task_id in task_ids:
            prior = index.get(task_id)
            if prior is not None:
                raise ValueError(
                    f"duplicate task id {task_id} in active files: {prior}, {path}"
                )
            index[task_id] = path
    return index


@contextmanager
def _task_allocation_lock(tasks_dir: Path) -> Iterator[None]:
    """Serialize all ``active/`` and ``done/`` writes across processes.

    Acquire once at the top level and never re-acquire in a helper: ``flock``
    deadlocks when the same process takes the lock through a second file
    descriptor. The lock auto-releases if its holder crashes.
    """
    if tasks_dir.is_symlink():
        raise ValueError(f"{tasks_dir} is a symlink; refusing to create a task lock through it")
    tasks_dir.mkdir(parents=True, exist_ok=True)
    lock_path = tasks_dir / ".tasks.lock"
    try:
        descriptor = os.open(
            lock_path,
            os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o666,
        )
    except OSError as exc:
        raise ValueError(
            f"cannot safely open task allocation lock {lock_path}: {exc}"
        ) from exc
    with os.fdopen(descriptor, "w") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def next_task_id(tasks_dir: Path, *, require_split: bool = True) -> str:
    """Determine the next task ID by scanning active/ and done/."""
    if require_split:
        _require_split(tasks_dir)
    max_num = 0

    for task_id in _active_task_index(tasks_dir):
        max_num = max(max_num, int(task_id[1:]))

    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        for path in done_dir.glob("*.md"):
            for task_id in _strict_task_ids_in_path(path):
                max_num = max(max_num, int(task_id[1:]))

    return f"t{max_num + 1:03d}"


def _parse_path_tasks(path: Path) -> list[Task]:
    """Parse one task search path according to its storage format."""
    if path.parent.name == "active":
        return [parse_task_file(path)]
    return parse_tasks(path)


def _read_active(tasks_dir: Path, *, require_split: bool = True) -> list[Task]:
    if require_split:
        _require_split(tasks_dir)
    active = _active_dir(tasks_dir)
    if not active.is_dir():
        return []
    tasks = [parse_task_file(path) for path in sorted(active.glob("*.md"))]
    task_ids = [task.id for task in tasks]
    duplicates = {task_id for task_id in task_ids if task_ids.count(task_id) > 1}
    if duplicates:
        raise ValueError(f"duplicate task ids in {active}: {sorted(duplicates)}")
    return sorted(tasks, key=lambda task: task.id)


def _task_file_preamble(path: Path) -> str:
    if not path.is_file():
        return ""
    text = path.read_text()
    match = _TASK_HEADING_PREFIX_RE.search(text)
    if match is None:
        return text
    return text[: match.start()]


def _render_task_file(path: Path, tasks: list[Task]) -> str:
    preamble = _task_file_preamble(path)
    rendered = render_tasks(tasks) if tasks else ""
    return preamble + rendered


@dataclass(frozen=True)
class TaskLocation:
    """A task plus the markdown file that currently owns it."""

    path: Path
    task: Task
    tasks: list[Task]


def _task_search_paths(tasks_dir: Path, *, require_split: bool = True) -> list[Path]:
    if require_split:
        _require_split(tasks_dir)
    paths = sorted(_active_dir(tasks_dir).glob("*.md"))
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        paths.extend(sorted(done_dir.glob("*.md"), reverse=True))
    return paths


def known_task_ids(tasks_dir: Path, *, require_split: bool = True) -> set[str]:
    """Every valid task id (tNNN) declared in active/*.md and done/*.md.

    An ID-only scan (not full parse): a field-level problem in one task must not
    crash callers that only need the set of declared ids. Active files provide
    IDs in frontmatter; done ledgers provide them in task headers.
    """
    if require_split:
        _require_split(tasks_dir)
    ids: set[str] = set()
    for path in _task_search_paths(tasks_dir, require_split=False):
        if not path.is_file():
            continue
        ids.update(_strict_task_ids_in_path(path))
    return ids


def task_status_index(
    tasks_dir: Path,
    *,
    require_split: bool = True,
) -> dict[str, str]:
    """Map every declared task id to its status across the split task store.

    Active files contribute their frontmatter ``id`` and ``status``. Done ledgers
    use a header-plus-contiguous-field-block scan so a ``- status:`` line in a
    description is not mistaken for record metadata. Missing status fields are
    omitted. Any duplicate occurrence is rejected rather than assigned precedence.
    """
    if require_split:
        _require_split(tasks_dir)

    statuses: dict[str, str] = {}
    occurrences: dict[str, Path] = {}

    for task_id, path in _active_task_index(tasks_dir).items():
        occurrences[task_id] = path
        data, _body = _load_task_frontmatter(
            path.read_text(encoding="utf-8"),
            path=path,
        )
        status = data.get("status")
        if isinstance(status, str):
            statuses[task_id] = status

    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        for path in sorted(done_dir.glob("*.md"), reverse=True):
            task_id: str | None = None
            for line in path.read_text(encoding="utf-8").splitlines():
                header = _HEADER_RE.match(line)
                if header:
                    declared_id = header.group(1)
                    prior = occurrences.get(declared_id)
                    if prior is not None:
                        raise ValueError(
                            f"duplicate task id {declared_id} found in {prior}, {path}"
                        )
                    occurrences[declared_id] = path
                    task_id = declared_id
                    continue
                if task_id is None:
                    continue
                field = _FIELD_RE.match(line)
                if not field:
                    task_id = None
                    continue
                if field.group(1) == "status":
                    statuses[task_id] = field.group(2).strip()

    return statuses


def _find_matches(
    tasks_dir: Path,
    task_id: str,
    *,
    require_split: bool = True,
) -> list[TaskLocation]:
    matches: list[TaskLocation] = []
    for path in _task_search_paths(tasks_dir, require_split=require_split):
        tasks = _parse_path_tasks(path)
        for task in tasks:
            if task.id == task_id:
                matches.append(TaskLocation(path=path, task=task, tasks=tasks))
    return matches


def find_task_location(
    tasks_dir: Path,
    task_id: str,
    *,
    require_split: bool = True,
) -> TaskLocation:
    """Find the unique occurrence of a task in active/*.md or done/*.md."""
    matches = _find_matches(tasks_dir, task_id, require_split=require_split)
    if not matches:
        searched = ", ".join(
            str(path)
            for path in _task_search_paths(tasks_dir, require_split=False)
        )
        msg = (
            f"Task {task_id} not found in tasks/active/*.md or tasks/done/*.md "
            f"(searched: {searched})"
        )
        raise KeyError(msg)
    if len(matches) > 1:
        locations = ", ".join(str(match.path) for match in matches)
        raise ValueError(f"duplicate task id {task_id} found in {locations}")
    return matches[0]


def write_task_location(location: TaskLocation) -> None:
    """Rewrite the ledger that owns a task location.

    The caller must hold ``_task_allocation_lock``; this helper does not acquire
    the lock itself.
    """
    location.path.parent.mkdir(parents=True, exist_ok=True)
    text = _render_task_file(location.path, location.tasks)
    _verify_round_trip(text, location.tasks, path=location.path)
    atomic_write_text(location.path, text)


def _format_note(note_date: date, note: str) -> str:
    cleaned = note.strip()
    if not cleaned:
        msg = "Task note cannot be empty"
        raise ValueError(msg)
    return f"- {note_date.isoformat()}: {cleaned}"


def _heading_level(line: str) -> int | None:
    match = _MARKDOWN_HEADING_RE.match(line)
    if match is None:
        return None
    return len(match.group(1))


def _append_note_to_description(description: str, note_line: str) -> str:
    description = description.strip()
    if not description:
        return f"### Notes\n\n{note_line}"

    lines = description.splitlines()
    notes_index = next((i for i, line in enumerate(lines) if _NOTES_HEADING_RE.match(line)), None)
    if notes_index is None:
        return f"{description}\n\n### Notes\n\n{note_line}"

    insert_index = len(lines)
    for i in range(notes_index + 1, len(lines)):
        level = _heading_level(lines[i])
        if level is not None and level <= 3:
            insert_index = i
            break

    before = lines[:insert_index]
    while before and before[-1] == "":
        before.pop()
    after = lines[insert_index:]
    if after:
        return "\n".join([*before, note_line, "", *after]).strip()
    return "\n".join([*before, note_line]).strip()


def append_task_note(tasks_dir: Path, task_id: str, note: str, note_date: date | None = None) -> Task:
    """Append a dated journal note to an active task file or done ledger."""
    with _task_allocation_lock(tasks_dir):
        _require_split(tasks_dir)
        location = find_task_location(tasks_dir, task_id, require_split=False)
        task = location.task
        line = _format_note(note_date or date.today(), note)
        task.description = _append_note_to_description(task.description, line)
        if location.path.parent == _active_dir(tasks_dir):
            write_task_file(tasks_dir, task)
        else:
            write_task_location(location)
    return task


def _find_task(tasks: list[Task], task_id: str) -> Task:
    for t in tasks:
        if t.id == task_id:
            return t
    msg = f"Task {task_id} not found in tasks/active/*.md"
    raise KeyError(msg)


def add_task(
    project_root: Path,
    tasks_dir: Path,
    title: str,
    priority: str,
    task_type: str = "",
    aspects: list[str] | None = None,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    group: str = "",
    description: str = "",
    *,
    force: bool = False,
) -> Task:
    """Create a proposed task in its own active file."""
    from science_tool.tasks_blockers import validate_blocker_refs  # noqa: PLC0415

    with _task_allocation_lock(tasks_dir):
        _require_split(tasks_dir)
        _validate_task_title(title)
        validated_blockers = validate_blocker_refs(project_root, blocked_by, force=force) if blocked_by else []
        task_id = next_task_id(tasks_dir, require_split=False)
        task = Task(
            id=task_id,
            title=title,
            type=task_type,
            aspects=aspects or [],
            priority=priority,
            status="proposed",
            created=date.today(),
            related=related or [],
            blocked_by=validated_blockers,
            group=group,
            description=description,
        )
        write_task_file(tasks_dir, task)
    return task


def _move_task_to_done(tasks_dir: Path, task: Task, *, target_status: str) -> None:
    """Append a terminal task to its ledger, then delete its active file.

    The caller must already hold ``_task_allocation_lock``. This helper must
    never acquire it again because a second ``flock`` file descriptor deadlocks.
    """
    from science_tool.tasks_ledger import _destination_for, _read_destination  # noqa: PLC0415

    done_dir = tasks_dir / "done"
    occurrences: list[tuple[Path, Task]] = []
    for path in _task_search_paths(tasks_dir, require_split=False):
        if path.parent != done_dir or not path.is_file():
            continue
        _preamble, ledger_tasks = _read_destination(path)
        occurrences.extend((path, ledger) for ledger in ledger_tasks if ledger.id == task.id)

    if len(occurrences) > 1:
        locations = ", ".join(str(path) for path, _ledger in occurrences)
        raise ValueError(
            f"multiple done-ledger occurrences for task {task.id}: {locations}"
        )
    if occurrences:
        path, ledger = occurrences[0]
        if not _move_recovery_equivalent(
            task,
            ledger,
            target_status=target_status,
        ):
            raise ValueError(
                f"conflicting done-ledger occurrence for task {task.id}: {path}"
            )
        delete_task_file(tasks_dir, task.id)
        return

    relative_destination, _missing_completed = _destination_for(task, date.today())
    done_path = tasks_dir / relative_destination
    done_path.parent.mkdir(parents=True, exist_ok=True)
    preamble, ledger_tasks = _read_destination(done_path)
    ledger_tasks.append(task)
    done_text = preamble + render_tasks(ledger_tasks)
    _verify_round_trip(done_text, ledger_tasks, path=done_path)

    # Commit the recoverable side first: a retry can recognize this ledger entry.
    atomic_write_text(done_path, done_text)
    delete_task_file(tasks_dir, task.id)


def complete_task(tasks_dir: Path, task_id: str, note: str | None = None) -> Task:
    """Mark an active task done and move it to the monthly ledger."""
    with _task_allocation_lock(tasks_dir):
        _require_split(tasks_dir)
        tasks = _read_active(tasks_dir, require_split=False)
        task = _find_task(tasks, task_id)

        task.status = "done"
        task.completed = date.today()
        if note:
            task.description = f"{task.description}\n\n{note}".strip()

        _move_task_to_done(tasks_dir, task, target_status="done")
    return task


def defer_task(tasks_dir: Path, task_id: str, reason: str | None = None) -> Task:
    """Set status to 'deferred', append reason to description."""
    with _task_allocation_lock(tasks_dir):
        _require_split(tasks_dir)
        location = find_task_location(tasks_dir, task_id, require_split=False)
        if location.path.parent != _active_dir(tasks_dir):
            raise KeyError(f"Task {task_id} not found in tasks/active/*.md")
        task = location.task

        task.status = "deferred"
        if reason:
            task.description = f"{task.description}\n\n{reason}".strip()

        write_task_file(tasks_dir, task)
    return task


def retire_task(tasks_dir: Path, task_id: str, reason: str | None = None) -> Task:
    """Set status to 'retired', append reason. Moves to done/ archive like complete_task."""
    with _task_allocation_lock(tasks_dir):
        _require_split(tasks_dir)
        tasks = _read_active(tasks_dir, require_split=False)
        task = _find_task(tasks, task_id)

        task.status = "retired"
        task.completed = date.today()
        if reason:
            task.description = f"{task.description}\n\n**Retired:** {reason}".strip()

        _move_task_to_done(tasks_dir, task, target_status="retired")
    return task


def block_task(
    project_root: Path,
    tasks_dir: Path,
    task_id: str,
    blocked_by: list[str],
    *,
    force: bool = False,
) -> Task:
    """Add typed blockers to a task, set status to 'blocked'."""
    from science_tool.tasks_blockers import validate_blocker_refs  # noqa: PLC0415

    with _task_allocation_lock(tasks_dir):
        _require_split(tasks_dir)
        validated = validate_blocker_refs(project_root, blocked_by, force=force)
        location = find_task_location(tasks_dir, task_id, require_split=False)
        if location.path.parent != _active_dir(tasks_dir):
            raise KeyError(f"Task {task_id} not found in tasks/active/*.md")
        task = location.task

        task.status = "blocked"
        for ref in validated:
            if ref not in task.blocked_by:
                task.blocked_by.append(ref)

        write_task_file(tasks_dir, task)
    return task


def unblock_task(tasks_dir: Path, task_id: str) -> Task:
    """Clear blocked_by list, set status to 'active'."""
    with _task_allocation_lock(tasks_dir):
        _require_split(tasks_dir)
        location = find_task_location(tasks_dir, task_id, require_split=False)
        if location.path.parent != _active_dir(tasks_dir):
            raise KeyError(f"Task {task_id} not found in tasks/active/*.md")
        task = location.task

        task.status = "active"
        task.blocked_by = []

        write_task_file(tasks_dir, task)
    return task


def edit_task(
    project_root: Path,
    tasks_dir: Path,
    task_id: str,
    title: str | None = None,
    description: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    aspects: list[str] | None = None,
    related: list[str] | None = None,
    blocked_by: list[str] | None = None,
    group: str | None = None,
    *,
    force: bool = False,
) -> Task:
    """Update specified fields on a task."""
    from science_tool.tasks_blockers import validate_blocker_refs  # noqa: PLC0415

    with _task_allocation_lock(tasks_dir):
        _require_split(tasks_dir)
        location = find_task_location(tasks_dir, task_id, require_split=False)
        task = location.task
        is_active = location.path.parent == _active_dir(tasks_dir)

        if is_active and status in _CLOSED_STATUS_VALUES:
            raise ValueError("use science tasks done/retire to close a task")
        if not is_active and status is not None and status not in _CLOSED_STATUS_VALUES:
            msg = f"Cannot set archived task {task_id} to non-closed status '{status}'"
            raise ValueError(msg)
        if title is not None:
            _validate_task_title(title)
            task.title = title
        if description is not None:
            task.description = description
        if priority is not None:
            task.priority = priority
        if status is not None:
            task.status = status
        if aspects is not None:
            task.aspects = aspects
        if related is not None:
            # --related REPLACES the list (deduped, order-preserving) rather than
            # accumulating -- appending gave no way to remove a stale ref, and a bare
            # non-canonical short id silently entered the list and later failed graph
            # validation (fb-2026-07-07-001).
            deduped: list[str] = []
            for ref in related:
                if ":" not in ref or not ref.split(":", 1)[1]:
                    raise ValueError(
                        f"related ref {ref!r} is not canonical; use a '<kind>:<id>' ref "
                        "(e.g. 'hypothesis:h01', 'task:t010')"
                    )
                if ref not in deduped:
                    deduped.append(ref)
            task.related = deduped
        if blocked_by is not None:
            task.blocked_by = validate_blocker_refs(project_root, blocked_by, force=force)
        if group is not None:
            task.group = group

        if is_active:
            write_task_file(tasks_dir, task)
        else:
            write_task_location(location)
    return task


def warn_invalid_statuses(tasks: list[Task]) -> None:
    """Print warnings to stderr for tasks with non-canonical statuses."""
    for t in tasks:
        if t.status not in _VALID_STATUSES:
            print(
                f"WARNING: [{t.id}] has invalid status '{t.status}' "
                f"(expected one of: {', '.join(sorted(_VALID_STATUSES))})",
                file=sys.stderr,
            )


def warn_missing_completed(n: int) -> None:
    """Print a stderr note for closed tasks excluded from `--since` results.

    A closed task with no ``completed:`` date is never guessed into the
    window -- it is dropped and its count is surfaced here instead.
    """
    if n > 0:
        print(
            f"WARNING: {n} closed task(s) have no 'completed' date and were "
            "excluded from --since results",
            file=sys.stderr,
        )


# Statuses that represent closed tasks (excluded from default listing)
_CLOSED_STATUSES = {TaskStatus.DONE, TaskStatus.RETIRED}
_CLOSED_STATUS_VALUES = {TaskStatus.DONE.value, TaskStatus.RETIRED.value}


def _since_window_months(since: date, today: date) -> list[str]:
    """Enumerate 'YYYY-MM' strings from `since`'s month to `today`'s month, inclusive."""
    months: list[str] = []
    year, month = since.year, since.month
    while (year, month) <= (today.year, today.month):
        months.append(f"{year:04d}-{month:02d}")
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
    return months


def _read_since_candidates(tasks_dir: Path, since: date) -> list[Task]:
    """Open tasks from ``active/`` unioned with done ledgers in ``[since, today]``.

    Month-file selection is only a read optimization; the row predicate in
    `list_tasks` is the authoritative membership test. Monthly done ledgers may be
    missing for any month in the window -- that is not an error. Duplicate
    task IDs across split active files and selected done ledgers are rejected.
    """
    from science_tool.tasks_ledger import _read_destination

    by_id: dict[str, Task] = {
        t.id: t for t in _read_active(tasks_dir, require_split=False)
    }
    for month in _since_window_months(since, date.today()):
        _preamble, archive_tasks = _read_destination(tasks_dir / "done" / f"{month}.md")
        for t in archive_tasks:
            if t.id in by_id:
                raise ValueError(
                    f"entity 'task:{t.id}' produced by multiple sources"
                )
            by_id[t.id] = t
    return list(by_id.values())


def list_tasks(
    tasks_dir: Path,
    project_root: Path | None = None,
    priority: str | None = None,
    status: str | None = None,
    related: str | None = None,
    group: str | None = None,
    aspects: list[str] | None = None,
    include_done: bool = False,
    since: date | None = None,
) -> list[Task]:
    """Filter active tasks by optional criteria.

    By default, done and retired statuses are excluded from the active store.
    ``include_done=True`` includes every status present in that active store;
    it does not read done ledgers.

    ``since`` queries closed tasks by completion date instead: it also reads
    `tasks/done/YYYY-MM.md` archive months overlapping `[since, today]`, and
    (after the other filters below) keeps only tasks with
    ``completed is not None and completed >= since``. Closed tasks with no
    ``completed:`` date are excluded and counted via `warn_missing_completed`
    rather than guessed. When ``since`` is set, closed tasks participate by
    default (the `include_done`/default-hiding behavior below is bypassed --
    ``since`` is itself the closed-task selector).
    """
    _require_split(tasks_dir)
    tasks = (
        _read_since_candidates(tasks_dir, since)
        if since is not None
        else _read_active(tasks_dir, require_split=False)
    )

    warn_invalid_statuses(tasks)

    if priority is not None:
        tasks = [t for t in tasks if t.priority == priority]
    if status is not None:
        tasks = [t for t in tasks if t.status == status]
    elif not include_done and since is None:
        tasks = [t for t in tasks if t.status not in _CLOSED_STATUSES]
    if related is not None:
        tasks = [t for t in tasks if any(related in r for r in t.related)]
    if group is not None:
        tasks = [t for t in tasks if t.group == group]
    if aspects:
        from science_model.aspects import (
            load_project_aspects,
            matches_aspect_filter,
            resolve_entity_aspects,
        )

        project_aspects = load_project_aspects(project_root or tasks_dir.parent)
        filter_set = set(aspects)
        tasks = [
            t
            for t in tasks
            if matches_aspect_filter(
                resolve_entity_aspects(t.aspects or None, project_aspects),
                filter_set,
            )
        ]

    if since is not None:
        missing = sum(1 for t in tasks if t.status in _CLOSED_STATUSES and t.completed is None)
        warn_missing_completed(missing)
        tasks = [
            t
            for t in tasks
            if t.status in _CLOSED_STATUSES and t.completed is not None and t.completed >= since
        ]

    return tasks
