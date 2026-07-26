# Context-budget Slice 2 — `tasks list --since` + guidance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax. Execute task-by-task with a review gate.

**Goal:** Add the archive-querying capability (`tasks list --since <date>`) the guidance
needs, then rewrite the 8 agent-facing sites that instruct direct reads of CLI-owned task
files, and add a content guard so the drift cannot recur.

**Architecture:** Extend `list_tasks` with a row-level `--since` filter plus an
archive-reading path; month-file selection is only a read optimization, the authoritative
filter is `task.completed >= since`. Then edit docs to use filtered CLI forms. No new
subsystem — this reuses the existing `tasks.py` / `tasks_archive.py` machinery.

**Design reference:** `docs/plans/2026-07-24-agent-context-budget-program-design.md` §"Slice 2".

## Global Constraints
- `--since` filters on `task.completed` (a *closed* date — both `complete_task` and
  `retire_task` set `completed = date.today()`), so `--since D` means "closed on or after D";
  retired tasks participate by default, `--status done` narrows to successful completions.
- Month-file selection narrows which archive files are parsed; it NEVER decides membership.
  A boundary month legitimately holds tasks on both sides of the cutoff — filter every parsed
  task by the row predicate.
- A task with no `completed:` date is EXCLUDED from `--since` results and its count is
  reported on stderr — never guessed. (`_destination_for` routes an undated closed task to
  today's month and flags `missing_completed`; file location is not evidence of date.)
- `--since` with a non-terminal `--status` (`active`/`proposed`/`blocked`/`deferred`) is a
  usage error and fails early (open tasks have no `completed` date).
- Package dir `science/`. Conventional commits, NO AI-attribution trailer. Python 3.11 floor.
- Content-guard work: **READ `tests/test_command_docs.py` and `tests/test_codex_skills.py`
  FIRST** — they assert skill/command markdown by file and reshaping docs without checking
  them has broken this repo before. Codex skills are generated mirrors — regenerate them, do
  not hand-edit.

## Task 1: `list_tasks` gains an archive-reading `--since` path

**Files:**
- Modify: `science/src/science_tool/tasks.py` (`list_tasks`, ~line 751; reuse
  `tasks_archive._read_destination` at ~line 197 and the `done/` glob pattern at ~414).
- Test: `science/tests/test_tasks_since.py` (new).

**Interfaces:**
- Produces: `list_tasks(..., since: date | None = None) -> list[Task]`. When `since` is None,
  behavior is unchanged. When set, it also reads `tasks/done/YYYY-MM.md` files whose month
  intersects `[since, today]`, parses them (via the archive parser), unions with active, and
  returns only tasks with `completed is not None and completed >= since`.

- [ ] **Step 1: failing tests** (`tests/test_tasks_since.py`) covering, against a fixture
  `tasks/` dir with an `active.md` and two `done/YYYY-MM.md` archives:
  - exact cutoff: a task with `completed == since` IS included.
  - a boundary month file holding tasks on both sides of `since`: only the >= ones returned.
  - a closed task with no `completed:` date is excluded AND its count is surfaced (return it
    via a stderr warning / a returned count — see Step 3 for the exact mechanism).
  - retired tasks (status retired, completed set) included by default; `--status done` narrows.
  - a window intersecting a month with no archive file present: no error, returns what exists.
- [ ] **Step 2: run tests, verify they fail.**
- [ ] **Step 3: implement.** Add `since: date | None = None`. When set:
  - Collect candidate tasks: active (`_read_active`) + parsed archive months whose `YYYY-MM`
    is in `[since.strftime('%Y-%m') .. today]`. Reuse `_read_destination` for parsing; guard
    missing files.
  - Filter: keep tasks with `completed is not None and completed >= since`. Count the closed
    tasks with `completed is None` that would otherwise match the other filters and emit a
    single stderr note (`warn_missing_completed(n)` style, mirroring `warn_invalid_statuses`).
  - Apply the existing `priority`/`related`/`group`/`aspects` filters on top.
- [ ] **Step 4: run tests, verify pass.**
- [ ] **Step 5: commit** (`feat(tasks): list --since filters closed tasks by completion date`).

## Task 2: wire `--since` into the `tasks list` CLI (fail-early on non-terminal status)

**Files:**
- Modify: `science/src/science_tool/tasks_cli.py` (`tasks list` callback — already budget-wired;
  add the option, do not disturb the sink wiring).
- Test: `science/tests/test_tasks_cli.py` (or the existing tasks-list CLI test module).

- [ ] **Step 1: failing test** — `tasks list --since 2026-01-01 --status active` exits non-zero
  with a clear usage error; `tasks list --since 2026-06-01` returns only closed tasks >= that
  date; `--since` output still respects the budget sink.
- [ ] **Step 2: run, verify fail.**
- [ ] **Step 3: implement.** Add `@click.option("--since", type=<date>, default=None)`. If
  `since` is set and `status` is a non-terminal value, `raise click.UsageError(...)`. Pass
  `since` to `list_tasks`. Keep the existing `BoundedSink` wiring intact.
- [ ] **Step 4: run, verify pass.**
- [ ] **Step 5: commit** (`feat(tasks): expose --since on tasks list`).

## Task 3: rewrite the 8 guidance sites + retarget the health fallback

**Files (edit each; then regenerate codex mirrors):**
- `commands/tasks.md:23`, `commands/review-tasks.md:28`, `commands/discuss.md:22`,
  `commands/create-graph.md:48`, `commands/big-picture.md:68`,
  `references/role-prompts/discussant.md:17`, `references/role-prompts/research-assistant.md:15`
  — replace "read `tasks/active.md`" with the filtered CLI form (`science tasks list --status active`,
  or `tasks show <id>` for a single task, as fits each site).
- `commands/next-steps.md:160` — replace the "scan every `tasks/done/YYYY-MM.md`" instruction
  with `science tasks list --status done --since <window-start>`.
- `templates/agents-md.md:88` — retarget bare `science health` to a scoped form
  (e.g. `science health --severity error` or the `--output` file escape).

- [ ] **Step 1:** read `tests/test_command_docs.py` + `tests/test_codex_skills.py` to learn
  which files are asserted and how codex mirrors are regenerated.
- [ ] **Step 2:** edit the 8 sites + the health fallback.
- [ ] **Step 3:** regenerate the codex-skills mirrors for any edited command.
- [ ] **Step 4:** run `tests/test_command_docs.py tests/test_codex_skills.py` — verify green.
- [ ] **Step 5: commit** (`docs(tasks): point guidance at filtered CLI forms, not raw file reads`).

## Task 4: content guard — no agent-facing doc reads a CLI-owned file directly

**Files:**
- Test: `science/tests/test_no_raw_task_file_reads_in_docs.py` (new; mirror the existing
  content-guard pattern in `test_command_docs.py`).

- [ ] **Step 1: failing test** that greps `commands/`, `skills/`, `templates/`, `agents/`,
  `references/` for instructions to read `tasks/active.md` / glob `tasks/*.md` / `tasks/done/`
  and asserts none remain (allow-list the design/plan docs under `docs/` which legitimately
  discuss the files). Confirm it FAILS before Task 3's edits (or run it against a reverted copy)
  and PASSES after.
- [ ] **Step 2: run, confirm it passes post-Task-3.**
- [ ] **Step 3: commit** (`test(tasks): guard against raw task-file read instructions in docs`).

## Testing
- `--since` row semantics (exact cutoff, boundary month, missing-completed excluded+counted,
  retired included / `--status done` narrows, absent month file).
- `--since` + non-terminal `--status` fails early.
- `tasks list --since` output respects the budget sink; `--output` complete.
- Content guard passes; codex mirrors regenerated and byte-matching.
