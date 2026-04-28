# Tasks Archive-Aware Show And Notes Design

**Date:** 2026-04-28
**Status:** Draft for review

## Problem

`science-tool tasks show <task-id>` only searches `tasks/active.md`. Once a task is completed or retired, it is moved to `tasks/done/YYYY-MM.md`, so `show` fails for canonical archived tasks with an error such as `Task t141 not found in active.md`.

Task descriptions also accumulate clarifications and decisions over time, but the CLI only supports replacing the description wholesale through `tasks edit --description`. That is useful for correction, but weak for project history because it does not encourage dated, append-only notes.

## Goals

- Make task lookup location-aware across `tasks/active.md` and `tasks/done/*.md`.
- Preserve the current task markdown format and archive layout.
- Let `tasks show <id>` display active, done, and retired tasks.
- Let safe task writes find the file that currently owns the task before updating it.
- Add `science-tool tasks note <id> <text>` as the formal journal mechanism for dated clarifications, observations, and follow-up context.
- Keep direct description editing available for deliberate replacement, not journal updates.

## Non-Goals

- Do not create a legacy or compatibility task store.
- Do not introduce a database, index file, or task-id cache.
- Do not migrate existing task descriptions into a new section.
- Do not change `tasks archive` routing or monthly archive semantics.
- Do not add interactive editor support in this increment.

## Desired File Structure

No package restructuring is required.

```text
science-tool/src/science_tool/
  tasks.py              # add location-aware task-file helpers and note append operation
  cli.py                # wire show/edit/note to location-aware operations
  tasks_archive.py      # unchanged archive planner/apply behavior
  tasks_display.py      # unchanged table rendering

science-tool/tests/
  test_tasks.py         # unit coverage for location-aware lookup/write and notes
  test_tasks_cli.py     # CLI coverage for show/edit/note against active and archived tasks
```

## Files To Remove

No files should be removed.

## Data Model

Keep the existing `Task` model unchanged. Notes are stored inside `Task.description` as markdown text.

`tasks note` appends a note block to the description:

```markdown
### Notes

- 2026-04-28: Clarification text.
```

Notes-section grammar:

- The notes heading is an exact, case-sensitive markdown heading matched by `^###\s+Notes\s*$`.
- If the description already contains a notes section, append the new dated bullet to that section.
- If another heading of equal or higher level follows the notes section, insert the new bullet immediately before that heading.
- If no notes section exists, append the notes section after the existing description.
- Note bullets preserve insertion order. `--date` backfills are not chronologically sorted because this is a journal, not a timeline normalizer.

Whitespace:

- A non-empty description gets one blank line before `### Notes`.
- The notes heading is followed by one blank line before the first bullet.
- No trailing blank line is included in `Task.description`; `render_task` owns the final file newline.
- An empty description starts directly with `### Notes`, with no leading blank line.

The note date defaults to `date.today()`. A `--date YYYY-MM-DD` option should exist for backfilling or recording a note from a prior or future work session. Invalid dates fail early with a Click error. Future dates are allowed.

Monthly archive files become append-mutable for notes and explicit metadata repairs. They are still canonical monthly completion archives, but downstream consumers should not assume a closed month file is immutable after month end.

## Location-Aware Task Access

Add focused helpers in `science_tool.tasks`:

- `TaskLocation`: immutable dataclass with `path: Path`, `task: Task`, and `tasks: list[Task]`.
- `find_task_location(tasks_dir: Path, task_id: str) -> TaskLocation`: search `active.md` first, then `done/*.md` in reverse filename order so recent monthly archives are checked first.
- `write_task_location(location: TaskLocation) -> None`: rewrite the owning file with the updated `location.tasks`.
- `append_task_note(tasks_dir: Path, task_id: str, note: str, note_date: date | None = None) -> Task`: append a dated note to the owning task and rewrite the owning file.

Existing active-only lifecycle commands remain active-only:

- `done`, `retire`, `defer`, `block`, and `unblock` continue to operate on `active.md` because they represent queue lifecycle transitions.
- `edit` becomes location-aware for metadata and description corrections, because archived task metadata may need repair.
- `edit --status` against an archived task may only set a closed status: `done` or `retired`. Reopening archived tasks is rejected in this increment to avoid a non-closed task living in `tasks/done/YYYY-MM.md` with a stale `completed:` date. Revival should be a separate command or workflow later.
- `show` becomes location-aware and read-only.
- `note` is location-aware and append-only.

If duplicate task IDs exist across active/done files, active wins. If duplicates exist only in done archives, the newest monthly archive wins because done files are searched in reverse filename order. Lookup emits a warning to stderr listing duplicate locations so silent precedence does not mask corruption. Duplicate repair is out of scope; the current ID generation already scans active and done to avoid creating new duplicates.

`find_task_location` is the primary lookup API. Callers that only need the task can use `find_task_location(...).task`; no separate `show_task` wrapper is needed.

## CLI Behavior

`science-tool tasks show t141` prints the same `render_task` output regardless of whether `t141` lives in `tasks/active.md` or `tasks/done/2026-04.md`.

`science-tool tasks edit t141 --description "..."` rewrites the task in its current file. This is a direct replacement operation and should remain explicit.

`science-tool tasks edit t141 --status active` fails when `t141` is archived. This avoids reopening a task in `tasks/done/YYYY-MM.md`. Active-file status edits keep their existing behavior.

`science-tool tasks note t141 "Clarification..."` appends a dated note and prints:

```text
Added note to [t141] (2026-04-28)
```

`science-tool tasks note t141 --date 2026-04-21 "Clarification..."` uses the supplied date.

Missing task errors should say the task was not found in `tasks/active.md` or `tasks/done/*.md`, and include the concrete archive filenames that were searched.

## Error Handling

- Empty or whitespace-only note text fails with a Click error after `note.strip()`.
- Invalid `--date` fails with a Click error.
- Missing task raises a `KeyError` in the library layer and a Click error in the CLI.
- Archived `edit --status` to a non-closed status fails with a Click error.
- Existing parse failures should continue to fail early through the parser instead of being silently skipped.

## Testing

Use TDD.

Unit tests:

- `find_task_location` finds active tasks.
- `find_task_location` finds archived tasks in `tasks/done/YYYY-MM.md`.
- `find_task_location` searches done archives newest first.
- `find_task_location` returns the active copy when the same ID exists in active and done.
- `find_task_location` warns when duplicate IDs are found.
- Missing lookup raises a clear error listing searched files.
- `edit_task` rewrites the archive file when the target is archived.
- `edit_task` rejects reopening an archived task with a non-closed status.
- `append_task_note` creates a `### Notes` section.
- `append_task_note` appends to an existing `### Notes` section.
- `append_task_note` supports explicit dates.
- `append_task_note` appends in insertion order, including backfilled dates.
- `append_task_note` handles descriptions with and without existing trailing newlines after parsing.
- `append_task_note` inserts before a following heading of equal or higher level.
- `parse_tasks` -> `render_tasks` is idempotent for parsed tasks, so rewriting a whole task file does not cause repeated whitespace churn.
- `parse_tasks` -> append note -> `render_tasks` -> `parse_tasks` preserves every task except the target task's expected description change.

CLI tests:

- `tasks show` displays archived tasks.
- `tasks edit --description` updates archived tasks in their owning done file.
- `tasks edit --status active` rejects archived tasks.
- `tasks note` appends a dated note to an active task.
- `tasks note` appends a dated note to an archived task.
- `tasks note --date` uses the supplied date.
- `tasks note` echoes the date it used.
- `tasks note` rejects empty and whitespace-only notes.

Focused verification:

```bash
cd science-tool
uv run --frozen pytest tests/test_tasks.py tests/test_tasks_cli.py -q
uv run --frozen ruff check .
uv run --frozen pyright
```

## Open Decisions

- `tasks note` should not infer note categories in this increment. Plain dated bullets are enough.
- `tasks note` should not auto-add notes from lifecycle commands yet. Existing `done --note`, `defer --reason`, and `retire --reason` continue to use the current `\n\n<text>` append behavior, not the `### Notes` format. A later cleanup task should evaluate whether lifecycle reasons should be normalized into notes.
