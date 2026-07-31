"""Transactional migration from aggregate to split task storage.

The journal is the recovery authority.  Apply plans while holding the task
allocation lock, records the aggregate source hash plus every complete
post-image, writes those post-images atomically, and deletes ``active.md`` last.
Resume only replays the journal; it never derives a new plan from partial state.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from science_tool.markdown_scan import (
    iter_markdown_destinations,
    MarkdownDestinationScanError,
)
from science_tool.tasks import (
    _ANY_TASK_HEADER_RE,
    _MIGRATION_JOURNAL,
    _TASK_ID_PATTERN,
    _TASK_HEADING_PREFIX_RE,
    _parse_tasks_text,
    _slug_for,
    _task_allocation_lock,
    _tasks_equal,
    _tasks_storage_state,
    _validate_task_title,
    _verify_task_file_round_trip,
    render_task_file,
    StorageState,
    Task,
)
from science_tool.tasks_ledger import (
    _destination_for,
    _read_destination,
    plan_ledger_appends,
)

__all__ = [
    "MigrationEntry",
    "MigrationPlan",
    "MigrationRefused",
    "MigrationResumeEntry",
    "MigrationResumeResult",
    "apply_migration",
    "migration_mode_refusal",
    "plan_migration",
    "resume_migration",
]


_OPEN_STATUSES = frozenset({"proposed", "active", "blocked", "deferred"})
_TERMINAL_STATUSES = frozenset({"done", "retired"})
_JOURNAL_VERSION = 1
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_URI_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


class MigrationRefused(ValueError):
    """The migration cannot safely proceed without human resolution."""


@dataclass(frozen=True)
class MigrationEntry:
    """One source task and the migration action planned for it."""

    task: Task
    destination: Path | None
    action: str


@dataclass(frozen=True)
class MigrationPlan:
    """A complete, write-free migration plan."""

    tasks_dir: Path
    source_sha256: str | None
    entries: list[MigrationEntry]
    open_post_images: dict[Path, str]
    ledger_post_images: dict[Path, str]
    refusals: list[str]

    @property
    def post_images(self) -> dict[Path, str]:
        """All post-images in their relative-to-``tasks_dir`` namespace."""
        overlap = set(self.open_post_images) & set(self.ledger_post_images)
        if overlap:
            joined = ", ".join(path.as_posix() for path in sorted(overlap))
            raise ValueError(f"migration plan has colliding post-image paths: {joined}")
        return {**self.open_post_images, **self.ledger_post_images}


@dataclass(frozen=True)
class MigrationResumeEntry:
    """One journal target and the recovery action taken for it."""

    destination: Path
    action: str


@dataclass(frozen=True)
class MigrationResumeResult:
    """Complete recovery outcome, including exact targets that needed no write."""

    entries: list[MigrationResumeEntry]
    written: list[Path]


@dataclass(frozen=True)
class _JournalPostImage:
    relative_path: Path
    content: str


@dataclass(frozen=True)
class _Journal:
    source_sha256: str
    postimages: list[_JournalPostImage]


@dataclass(frozen=True)
class _ResolvedPostImage:
    relative_path: Path
    target: Path
    content: str


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _display_path(path: Path, *, tasks_dir: Path) -> str:
    try:
        return f"tasks/{path.relative_to(tasks_dir).as_posix()}"
    except ValueError:
        return str(path)


def _raise_if_symlink(path: Path, *, tasks_dir: Path) -> None:
    if path.is_symlink():
        raise MigrationRefused(
            f"{_display_path(path, tasks_dir=tasks_dir)} is a symlink; "
            "migration transaction paths must be real files and directories"
        )


def _validate_transaction_paths(tasks_dir: Path) -> None:
    """Reject redirected transaction paths before acquiring the allocation lock."""
    _raise_if_symlink(tasks_dir, tasks_dir=tasks_dir)
    paths = [
        tasks_dir / "active.md",
        tasks_dir / "active",
        tasks_dir / "done",
        tasks_dir / ".science",
        tasks_dir / _MIGRATION_JOURNAL,
        tasks_dir / ".tasks.lock",
    ]
    journal = tasks_dir / _MIGRATION_JOURNAL
    paths.append(journal.with_suffix(journal.suffix + ".tmp"))
    for path in paths:
        _raise_if_symlink(path, tasks_dir=tasks_dir)

    for namespace in (tasks_dir / "active", tasks_dir / "done"):
        if not namespace.is_dir():
            continue
        try:
            children = list(namespace.iterdir())
        except OSError as exc:
            raise MigrationRefused(
                f"cannot inspect {_display_path(namespace, tasks_dir=tasks_dir)}: {exc}"
            ) from exc
        for child in children:
            _raise_if_symlink(child, tasks_dir=tasks_dir)


def atomic_write_text(path: Path, text: str) -> None:
    """Atomically write one migration post-image through a private random temp."""
    tasks_dir = path.parent
    _raise_if_symlink(path.parent, tasks_dir=tasks_dir)
    _raise_if_symlink(path, tasks_dir=tasks_dir)
    legacy_temp = path.with_suffix(path.suffix + ".tmp")
    _raise_if_symlink(legacy_temp, tasks_dir=tasks_dir)

    descriptor: int | None = None
    temp_path: Path | None = None
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC
    for _attempt in range(100):
        candidate = path.parent / f".{path.name}.{secrets.token_hex(12)}.tmp"
        try:
            descriptor = os.open(candidate, flags, 0o666)
        except FileExistsError:
            continue
        temp_path = candidate
        break
    if descriptor is None or temp_path is None:
        raise MigrationRefused(f"could not reserve an atomic temp file for {path}")

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            descriptor = None
            stream.write(text)
            stream.flush()
        os.replace(temp_path, path)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temp_path.is_symlink() or temp_path.exists():
            temp_path.unlink()


def _empty_plan(tasks_dir: Path, *refusals: str) -> MigrationPlan:
    return MigrationPlan(
        tasks_dir=tasks_dir,
        source_sha256=None,
        entries=[],
        open_post_images={},
        ledger_post_images={},
        refusals=list(refusals),
    )


def _migration_filename(task: Task) -> str:
    slug = _slug_for(task.title)
    return f"{task.id}-{slug}.md" if slug else f"{task.id}.md"


def _done_occurrences(
    done_ledgers: dict[Path, tuple[str, list[Task]]],
) -> dict[str, list[tuple[Path, Task]]]:
    occurrences: dict[str, list[tuple[Path, Task]]] = {}
    for relative_path, (_preamble, tasks) in done_ledgers.items():
        for task in tasks:
            occurrences.setdefault(task.id, []).append((relative_path, task))
    return occurrences


def _relative_markdown_destinations(description: str) -> list[str]:
    destinations: list[str] = []
    for destination in iter_markdown_destinations(description):
        if (
            destination.startswith(("#", "/"))
            or _URI_SCHEME_RE.match(destination)
            or destination in destinations
        ):
            continue
        destinations.append(destination)
    return destinations


def plan_migration(tasks_dir: Path, *, today: date) -> MigrationPlan:
    """Build the whole migration plan without writing anything."""
    tasks_dir = Path(tasks_dir)
    refusals: list[str] = []
    if tasks_dir.is_symlink():
        return _empty_plan(
            tasks_dir,
            f"{tasks_dir} is a symlink; migration requires a real task-store directory",
        )
    source = tasks_dir / "active.md"
    active_dir = tasks_dir / "active"
    journal = tasks_dir / _MIGRATION_JOURNAL

    if journal.parent.is_symlink():
        refusals.append(
            "tasks/.science is a symlink; migration transaction paths must be real directories"
        )
    elif journal.is_symlink():
        refusals.append(
            f"tasks/{_MIGRATION_JOURNAL.as_posix()} is a symlink; "
            "migration transaction paths must be real files and directories"
        )
    elif journal.exists():
        refusals.append(
            f"{_MIGRATION_JOURNAL.as_posix()} exists; finish the interrupted migration "
            "with `science tasks migrate-storage --resume`"
        )

    if source.is_symlink():
        refusals.append(
            "tasks/active.md is a symlink; migration transaction paths must be real files"
        )
        return _empty_plan(tasks_dir, *refusals)

    if active_dir.is_symlink():
        refusals.append(
            "tasks/active is a symlink; migration transaction paths must be real directories"
        )
    elif active_dir.exists():
        if not active_dir.is_dir():
            refusals.append("tasks/active exists but is not a directory")
        elif any(active_dir.iterdir()):
            refusals.append("tasks/active/ is non-empty; refusing to overwrite split storage")

    if not source.is_file():
        refusals.append("tasks/active.md is absent; there is nothing to migrate")
        return _empty_plan(tasks_dir, *refusals)

    try:
        source_bytes = source.read_bytes()
        source_text = source_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _empty_plan(tasks_dir, f"cannot read tasks/active.md: {exc}")

    source_sha256 = _sha256(source_bytes)
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        if _TASK_HEADING_PREFIX_RE.match(line) and _ANY_TASK_HEADER_RE.match(line) is None:
            refusals.append(
                f"malformed task heading at tasks/active.md:{line_number}: {line!r}"
            )
    for line_number, line in enumerate(source_text.splitlines(), start=1):
        if _ANY_TASK_HEADER_RE.match(line):
            break
        stripped = line.strip()
        if (
            not stripped
            or line == "# Active Tasks"
            or re.fullmatch(r"<!--(?:(?!-->).)*-->", stripped)
        ):
            continue
        return MigrationPlan(
            tasks_dir=tasks_dir,
            source_sha256=source_sha256,
            entries=[],
            open_post_images={},
            ledger_post_images={},
            refusals=[
                *refusals,
                f"substantive preamble content at tasks/active.md:{line_number}: "
                f"{line!r}; preserve or reconcile it before migration",
            ],
        )
    try:
        source_tasks = _parse_tasks_text(source_text, path=source)
    except ValueError as exc:
        return MigrationPlan(
            tasks_dir=tasks_dir,
            source_sha256=source_sha256,
            entries=[],
            open_post_images={},
            ledger_post_images={},
            refusals=[f"cannot parse tasks/active.md: {exc}"],
        )

    source_id_counts = Counter(task.id for task in source_tasks)
    duplicate_ids = sorted(task_id for task_id, count in source_id_counts.items() if count > 1)
    if duplicate_ids:
        refusals.append(f"duplicate source task id(s): {', '.join(duplicate_ids)}")

    valid_titles: set[int] = set()
    for index, task in enumerate(source_tasks):
        if re.fullmatch(_TASK_ID_PATTERN, task.id) is None:
            refusals.append(f"non-canonical source task id {task.id!r}; expected tNNN")
        try:
            _validate_task_title(task.title)
        except ValueError as exc:
            refusals.append(f"task {task.id} has an invalid title: {exc}")
        else:
            valid_titles.add(index)
        try:
            relative_destinations = _relative_markdown_destinations(task.description)
        except MarkdownDestinationScanError:
            refusals.append(
                f"task {task.id} Markdown destination scan exceeded its "
                "bounded-work limit; simplify recursively nested or incomplete "
                "Markdown links before migration"
            )
            continue
        if relative_destinations:
            rendered = ", ".join(repr(destination) for destination in relative_destinations)
            refusals.append(
                f"task {task.id} has relative Markdown destination(s) whose meaning would "
                f"change when moving out of tasks/active.md: {rendered}; rewrite the "
                "link(s) before migration"
            )

    done_ledgers: dict[Path, tuple[str, list[Task]]] = {}
    done_ledgers_valid = True
    done_dir = tasks_dir / "done"
    if done_dir.is_symlink():
        refusals.append(
            "tasks/done is a symlink; migration transaction paths must be real directories"
        )
    else:
        root = tasks_dir.resolve()
        for path in sorted(done_dir.glob("*.md")):
            relative_path = path.relative_to(tasks_dir)
            if path.is_symlink():
                refusals.append(
                    f"tasks/{relative_path.as_posix()} is a symlink; "
                    "done ledgers must be regular in-store files"
                )
                continue
            if not path.is_file():
                refusals.append(
                    f"{relative_path.as_posix()} exists but is not a regular file"
                )
                continue
            try:
                resolved = path.resolve(strict=True)
                resolved.relative_to(root)
            except (OSError, ValueError) as exc:
                refusals.append(
                    f"done ledger {relative_path.as_posix()} is outside the task store: {exc}"
                )
                continue
            try:
                done_ledgers[relative_path] = _read_destination(resolved)
            except (OSError, ValueError) as exc:
                done_ledgers_valid = False
                refusals.append(f"cannot read {relative_path.as_posix()}: {exc}")

    ledger_occurrences = _done_occurrences(done_ledgers)
    entries: list[MigrationEntry] = []
    terminal_tasks: list[Task] = []
    open_post_images: dict[Path, str] = {}
    open_targets: dict[Path, list[str]] = {}

    for index, task in enumerate(source_tasks):
        if task.status in _OPEN_STATUSES:
            destination = Path("active") / _migration_filename(task)
            entries.append(MigrationEntry(task=task, destination=destination, action="write"))
            if index not in valid_titles:
                continue
            open_targets.setdefault(destination, []).append(task.id)
            target = tasks_dir / destination
            if target.exists():
                refusals.append(f"open target {destination.as_posix()} already exists")
            existing_done = ledger_occurrences.get(task.id, [])
            if existing_done:
                locations = ", ".join(path.as_posix() for path, _task in existing_done)
                refusals.append(
                    f"open task {task.id} already exists in done storage: {locations}"
                )
            text = render_task_file(task)
            try:
                _verify_task_file_round_trip(text, task, path=target)
            except ValueError as exc:
                refusals.append(str(exc))
                continue
            open_post_images[destination] = text
        elif task.status in _TERMINAL_STATUSES:
            terminal_tasks.append(task)
            occurrences = ledger_occurrences.get(task.id, [])
            if len(occurrences) == 1 and _tasks_equal(task, occurrences[0][1]):
                destination = occurrences[0][0]
                action = "already archived"
            else:
                destination, _missing_completed = _destination_for(task, today)
                action = "append"
            entries.append(MigrationEntry(task=task, destination=destination, action=action))
        else:
            refusals.append(f"task {task.id} has unknown status {task.status!r}")
            entries.append(MigrationEntry(task=task, destination=None, action="refused"))

    for destination, task_ids in sorted(open_targets.items()):
        if len(task_ids) > 1:
            refusals.append(
                f"open target collision at {destination.as_posix()}: "
                + ", ".join(task_ids)
            )

    ledger_post_images: dict[Path, str] = {}
    terminal_conflicts: list[str] = []
    if done_ledgers_valid:
        ledger_post_images, terminal_conflicts = plan_ledger_appends(
            terminal_tasks,
            done_ledgers,
            today=today,
        )
    for task_id in sorted(terminal_conflicts):
        refusals.append(
            f"terminal task {task_id} conflicts with existing done-ledger occurrence(s)"
        )

    return MigrationPlan(
        tasks_dir=tasks_dir,
        source_sha256=source_sha256,
        entries=entries,
        open_post_images=open_post_images,
        ledger_post_images=ledger_post_images,
        refusals=refusals,
    )


def migration_mode_refusal(state: StorageState, mode: str) -> str | None:
    """Return the state-specific refusal for an apply or resume request."""
    if mode == "apply":
        if state is StorageState.LEGACY:
            return None
        if state is StorageState.EMPTY:
            return "cannot apply task-storage migration: no tasks/active.md exists; nothing to do"
        if state is StorageState.SPLIT:
            return "cannot apply task-storage migration: task storage is already split"
        if state is StorageState.MIGRATING:
            return (
                "an interrupted storage migration is in progress; "
                "run `science tasks migrate-storage --resume`."
            )
        return (
            "both tasks/active.md and tasks/active/ exist with no migration journal; "
            "inspect and remove one by hand — this is not an auto-resumable migration."
        )
    if mode == "resume":
        if state is StorageState.MIGRATING:
            return None
        if state in {StorageState.EMPTY, StorageState.SPLIT}:
            return (
                "cannot resume task-storage migration: no migration journal exists; "
                "there is nothing to resume"
            )
        if state is StorageState.LEGACY:
            return (
                "cannot resume task-storage migration: no migration journal exists; "
                "use `science tasks migrate-storage --apply`"
            )
        return (
            "both tasks/active.md and tasks/active/ exist with no migration journal; "
            "inspect and remove one by hand — this is not an auto-resumable migration."
        )
    raise ValueError(f"unknown migration mode: {mode}")


def _raise_plan_refusal(plan: MigrationPlan) -> None:
    if not plan.refusals:
        return
    details = "\n".join(f"  {reason}" for reason in plan.refusals)
    raise MigrationRefused(
        "The task-storage migration was refused. NOTHING has been written.\n\n"
        + details
    )


def _validate_relative_journal_path(raw_path: str) -> Path:
    relative_path = Path(raw_path)
    parts = relative_path.parts
    file_shape_is_valid = False
    if len(parts) == 2 and parts[0] == "active":
        file_shape_is_valid = (
            re.fullmatch(
                rf"{_TASK_ID_PATTERN}(?:-[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)?\.md",
                parts[1],
            )
            is not None
        )
    elif len(parts) == 2 and parts[0] == "done":
        file_shape_is_valid = (
            re.fullmatch(r"[0-9]{4}-(?:0[1-9]|1[0-2])\.md", parts[1]) is not None
        )
    if (
        not raw_path
        or relative_path.is_absolute()
        or relative_path == Path(".")
        or ".." in relative_path.parts
        or not relative_path.parts
        or relative_path.parts[0] not in {"active", "done"}
        or not file_shape_is_valid
    ):
        raise MigrationRefused(
            f"unsafe journal path {raw_path!r}: expected a canonical relative "
            "active/<task>.md or done/YYYY-MM.md path with no '..'"
        )
    return relative_path


def _validate_postimages(postimages: list[_JournalPostImage]) -> None:
    seen: set[Path] = set()
    for postimage in postimages:
        relative_path = _validate_relative_journal_path(postimage.relative_path.as_posix())
        if relative_path in seen:
            raise MigrationRefused(
                f"unsafe journal path {relative_path.as_posix()!r}: duplicate target"
            )
        seen.add(relative_path)


def _resolve_postimages(
    tasks_dir: Path,
    postimages: list[_JournalPostImage],
) -> list[_ResolvedPostImage]:
    """Validate every persisted path, then resolve every target under the store."""
    _validate_postimages(postimages)
    root = tasks_dir.resolve()
    resolved: list[_ResolvedPostImage] = []
    targets: set[Path] = set()
    for postimage in postimages:
        relative_path = postimage.relative_path
        lexical_target = root / relative_path
        _raise_if_symlink(lexical_target.parent, tasks_dir=root)
        _raise_if_symlink(lexical_target, tasks_dir=root)
        _raise_if_symlink(
            lexical_target.with_suffix(lexical_target.suffix + ".tmp"),
            tasks_dir=root,
        )
        target = lexical_target.resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise MigrationRefused(
                f"unsafe journal path {relative_path.as_posix()!r}: target escapes tasks directory"
            ) from exc
        if target in targets:
            raise MigrationRefused(
                f"unsafe journal path {relative_path.as_posix()!r}: duplicate resolved target"
            )
        targets.add(target)
        resolved.append(
            _ResolvedPostImage(
                relative_path=relative_path,
                target=target,
                content=postimage.content,
            )
        )
    return resolved


def _write_journal(
    tasks_dir: Path,
    *,
    source_sha256: str,
    postimages: list[_JournalPostImage],
) -> None:
    _validate_postimages(postimages)
    payload = {
        "version": _JOURNAL_VERSION,
        "source_sha256": source_sha256,
        "postimages": [
            {
                "path": postimage.relative_path.as_posix(),
                "content": postimage.content,
            }
            for postimage in postimages
        ],
    }
    journal = tasks_dir / _MIGRATION_JOURNAL
    _raise_if_symlink(journal.parent, tasks_dir=tasks_dir)
    _raise_if_symlink(journal, tasks_dir=tasks_dir)
    _raise_if_symlink(
        journal.with_suffix(journal.suffix + ".tmp"),
        tasks_dir=tasks_dir,
    )
    journal.parent.mkdir(parents=True, exist_ok=True)
    _raise_if_symlink(journal.parent, tasks_dir=tasks_dir)
    atomic_write_text(journal, json.dumps(payload, indent=2) + "\n")


def _load_journal(tasks_dir: Path) -> _Journal:
    journal_path = tasks_dir / _MIGRATION_JOURNAL
    _raise_if_symlink(journal_path.parent, tasks_dir=tasks_dir)
    _raise_if_symlink(journal_path, tasks_dir=tasks_dir)
    if not journal_path.is_file():
        raise MigrationRefused(
            f"{_MIGRATION_JOURNAL.as_posix()} does not exist; there is nothing to resume"
        )
    try:
        payload = json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MigrationRefused(f"cannot read migration journal: {exc}") from exc
    if not isinstance(payload, dict):
        raise MigrationRefused("migration journal root must be an object")
    if set(payload) != {"version", "source_sha256", "postimages"}:
        raise MigrationRefused(
            "migration journal must contain exactly version, source_sha256, and postimages"
        )
    if payload["version"] != _JOURNAL_VERSION:
        raise MigrationRefused(
            f"unsupported migration journal version: {payload['version']!r}"
        )
    source_sha256 = payload["source_sha256"]
    if not isinstance(source_sha256, str) or _SHA256_RE.fullmatch(source_sha256) is None:
        raise MigrationRefused("migration journal source_sha256 must be a SHA-256 hex digest")
    raw_postimages = payload["postimages"]
    if not isinstance(raw_postimages, list):
        raise MigrationRefused("migration journal postimages must be a list")

    postimages: list[_JournalPostImage] = []
    for index, raw in enumerate(raw_postimages):
        if not isinstance(raw, dict) or set(raw) != {"path", "content"}:
            raise MigrationRefused(
                f"migration journal postimages[{index}] must contain exactly path and content"
            )
        raw_path = raw["path"]
        content = raw["content"]
        if not isinstance(raw_path, str) or not isinstance(content, str):
            raise MigrationRefused(
                f"migration journal postimages[{index}] path and content must be strings"
            )
        relative_path = _validate_relative_journal_path(raw_path)
        postimages.append(_JournalPostImage(relative_path=relative_path, content=content))

    _validate_postimages(postimages)
    return _Journal(source_sha256=source_sha256, postimages=postimages)


def _current_source_hash(tasks_dir: Path) -> str | None:
    source = tasks_dir / "active.md"
    if not source.is_file():
        return None
    return _sha256(source.read_bytes())


def _delete_source(tasks_dir: Path) -> None:
    source = tasks_dir / "active.md"
    if source.exists():
        source.unlink()
    if source.exists():
        raise MigrationRefused(
            "tasks/active.md could not be deleted; the migration journal is retained"
        )


def _clear_journal(tasks_dir: Path) -> None:
    journal = tasks_dir / _MIGRATION_JOURNAL
    journal.unlink()
    if journal.exists():
        raise MigrationRefused("migration journal could not be cleared")


def apply_migration(tasks_dir: Path, *, today: date) -> MigrationPlan:
    """Plan and apply one migration under one allocation-lock window."""
    tasks_dir = Path(tasks_dir)
    _validate_transaction_paths(tasks_dir)
    with _task_allocation_lock(tasks_dir):
        _validate_transaction_paths(tasks_dir)
        state = _tasks_storage_state(tasks_dir)
        refusal = migration_mode_refusal(state, "apply")
        if refusal is not None:
            raise MigrationRefused(refusal)

        plan = plan_migration(tasks_dir, today=today)
        _raise_plan_refusal(plan)
        if plan.source_sha256 is None:
            raise MigrationRefused("migration plan has no active.md source hash")

        postimages = [
            _JournalPostImage(relative_path=path, content=content)
            for path, content in sorted(plan.post_images.items())
        ]
        resolved = _resolve_postimages(tasks_dir, postimages)
        _write_journal(
            tasks_dir,
            source_sha256=plan.source_sha256,
            postimages=postimages,
        )

        for postimage in resolved:
            _raise_if_symlink(postimage.target.parent, tasks_dir=tasks_dir)
            postimage.target.parent.mkdir(parents=True, exist_ok=True)
            _raise_if_symlink(postimage.target.parent, tasks_dir=tasks_dir)
            atomic_write_text(postimage.target, postimage.content)

        if _current_source_hash(tasks_dir) != plan.source_sha256:
            raise MigrationRefused(
                "tasks/active.md changed after migration planning; it was not deleted and "
                "the migration journal is retained"
            )

        _delete_source(tasks_dir)
        _clear_journal(tasks_dir)
        return plan


def resume_migration(tasks_dir: Path) -> MigrationResumeResult:
    """Finish an interrupted apply from its journal without re-planning."""
    tasks_dir = Path(tasks_dir)
    _validate_transaction_paths(tasks_dir)
    with _task_allocation_lock(tasks_dir):
        _validate_transaction_paths(tasks_dir)
        state = _tasks_storage_state(tasks_dir)
        refusal = migration_mode_refusal(state, "resume")
        if refusal is not None:
            raise MigrationRefused(refusal)

        journal = _load_journal(tasks_dir)
        current_source_hash = _current_source_hash(tasks_dir)
        if (
            current_source_hash is not None
            and current_source_hash != journal.source_sha256
        ):
            raise MigrationRefused(
                "tasks/active.md changed after the interrupted migration was planned; "
                "the source and migration journal are retained"
            )

        resolved = _resolve_postimages(tasks_dir, journal.postimages)
        different: list[str] = []
        absent: list[_ResolvedPostImage] = []
        for postimage in resolved:
            if not postimage.target.exists():
                absent.append(postimage)
                continue
            if (
                not postimage.target.is_file()
                or postimage.target.read_bytes() != postimage.content.encode("utf-8")
            ):
                different.append(postimage.relative_path.as_posix())

        if different:
            raise MigrationRefused(
                "journal target(s) are present but different from their post-images: "
                + ", ".join(different)
                + "; the source and migration journal are retained"
            )

        written: list[Path] = []
        for postimage in absent:
            _raise_if_symlink(postimage.target.parent, tasks_dir=tasks_dir)
            postimage.target.parent.mkdir(parents=True, exist_ok=True)
            _raise_if_symlink(postimage.target.parent, tasks_dir=tasks_dir)
            atomic_write_text(postimage.target, postimage.content)
            written.append(postimage.target)

        for postimage in resolved:
            if (
                not postimage.target.is_file()
                or postimage.target.read_bytes() != postimage.content.encode("utf-8")
            ):
                raise MigrationRefused(
                    f"{postimage.relative_path.as_posix()} did not reach its journalled "
                    "post-image; the migration journal is retained"
                )

        _delete_source(tasks_dir)
        _clear_journal(tasks_dir)
        written_set = set(written)
        return MigrationResumeResult(
            entries=[
                MigrationResumeEntry(
                    destination=postimage.relative_path,
                    action="written" if postimage.target in written_set else "already exact",
                )
                for postimage in resolved
            ],
            written=written,
        )
