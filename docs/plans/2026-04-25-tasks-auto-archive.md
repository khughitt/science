# Tasks Auto-Archive Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science-tool tasks archive` so done/retired entries in `tasks/active.md` are moved to `tasks/done/YYYY-MM.md` deterministically, and surface archive lag in `science-tool health`, eliminating the operational drift seen in 3 of 4 audited downstream projects.

**Evidence (from `docs/audits/downstream-project-conventions/synthesis.md` §5.4 / §8.1):** done/retired/deferred entries accumulate in `tasks/active.md` across three projects:

- **natural-systems:** 114/232 = 49% with `status: done`.
- **mm30:** of 152 entries, 36 `done` + 5 `retired` + 3 `deferred` = 44/152 (29%) total terminal-state. The set this archiver actually moves (`done` + `retired`) is 41/152 = 27%; the 3 `deferred` deliberately stay in active for re-engagement (see Shape Decisions).
- **protein-landscape:** 44/101 = 44% with `status: done`.
- **cbioportal:** 0% — clean reference, proving the discipline is enforceable, but only because cbioportal moves entries on done.

The `## [tNNN] Title` + bullet-key/value shape is identical across all four projects, so a single archiver can serve all of them. P1 #6 in the audit synthesis.

**Architecture:** Reuse the existing `science_tool.tasks` parser/renderer. Add a focused `science_tool.tasks_archive` module that owns scan, classify, route-by-completed-date, and idempotent file writes. Expose it via the existing `tasks` Click group as `science-tool tasks archive`. Surface drift counts under a new `tasks.archive_lag` block in the health report so `/science:status` and `/science:next-steps` can prompt the user to run the archiver.

**Tech Stack:** Python >=3.11, Click, pathlib, dataclasses, pytest. Built on `science_model.tasks.Task` and the existing `parse_tasks` / `render_tasks` helpers in `science_tool/tasks.py`.

---

## Shape Decisions

- **Routing key.** Destination = `tasks/done/{YYYY-MM}.md` from the entry's `completed:` date. If `completed:` is missing: route to the current month, emit a per-entry warning, do not synthesize a `completed:` value. Matches `complete_task` / `retire_task` behavior in `science_tool/tasks.py`.
- **Order preservation.** Append moved entries to the end of the destination file. Do not re-sort. Preserve `active.md` order for non-archived entries.
- **Preamble preservation.** Any text above the first `## [tNNN]` heading is preserved byte-for-byte. The current `_write_active` would silently drop it; the archiver must round-trip it.
- **Idempotency.** Re-running with no qualifying entries is a no-op (zero writes). Duplicate ids in the destination file are skipped with a warning, not re-appended.
- **Default = dry-run.** Plain invocation prints the plan; `--apply` performs writes. Matches `graph migrate` / `graph migrate-tags`.
- **Status set.** Archive `done` and `retired`. Do not archive `deferred` — those stay visible in active for re-engagement.
- **Health-only mode.** `--check` emits archivable counts as JSON and exits **non-zero (exit 1)** when any of `done_in_active` / `retired_in_active` / `missing_completed` is non-zero; exits 0 when clean. Used by both `science-tool health` (which interprets the exit code) and CI gates that want to fail on lag. The health-report consumer reads counts from JSON output regardless of exit code.
- **Malformed entries.** Parse errors are collected and reported. Dry-run lists them and exits 0; `--apply` raises and writes nothing.

---

## File Structure

Create:

- `science-tool/src/science_tool/tasks_archive.py` — archiver module: `ArchivePlan`, `ArchiveEntry`, `plan_archive`, `apply_archive`, `count_archivable`. (Module name parallels `tasks_display.py` / `datasets_register.py`; the package style for tasks is flat-module, not subpackage. Do not create a `tasks/` subpackage — that would shadow `tasks.py`.)
- `science-tool/tests/test_tasks_archive.py` — unit + CLI tests covering dry-run, apply, idempotency, completed-date routing, missing-completed fallback, header preservation, mixed status values, malformed entries, JSON output.

Modify:

- `science-tool/src/science_tool/cli.py` — add `tasks archive` subcommand under the existing `@main.group() tasks` group (line 1928). Reuses `OUTPUT_FORMATS` and the `emit_query_rows` helper used by other commands.
- `science-tool/src/science_tool/graph/health.py` — add `TaskArchiveLag` TypedDict, add `archive_lag` field to `HealthReport`, populate it in `build_health_report` from the new archiver.
- `science-tool/tests/test_health.py` — health-report integration test that creates an `active.md` with one done + one retired + one proposed entry and asserts the lag counts.
- `commands/status.md` — add an "archive lag" bullet under §6 "Staleness Warnings" so `/science:status` calls out non-zero `tasks.archive_lag` from `science-tool health`.
- `commands/next-steps.md` — under "Task Tracking Gaps", note that any non-zero `tasks.archive_lag` should produce a Recommended Next Action: run `science-tool tasks archive --apply`.

Do not modify: `science_tool/tasks.py` itself (the parser/renderer is reused unchanged), `science.yaml`, project content, or any downstream project files.

---

## Task 1: Implement Archive Planner

**Files:** Create `science-tool/src/science_tool/tasks_archive.py`; create `science-tool/tests/test_tasks_archive.py`.

- [x] **Step 1: Write failing planner tests** covering: empty `active.md`; single `done` with `completed: 2026-03-15` routes to `tasks/done/2026-03.md`; single `retired` with `completed: 2026-04-02` routes to `tasks/done/2026-04.md`; `done` with no `completed:` routes to current-month with `missing_completed=True`; `deferred` stays in active; mixed file (`proposed`/`done`/`retired`/`blocked`) moves only terminal entries; preamble preservation (`# Active Tasks\n\nNote.\n\n` before first heading); malformed block records a `ParseError` and continues.

- [x] **Step 2: Implement planner** in `tasks_archive.py`:
  - `@dataclass(frozen=True) ArchiveEntry`: `task: Task`, `destination: Path`, `missing_completed: bool`.
  - `@dataclass(frozen=True) ParseError`: `heading: str`, `message: str`.
  - `@dataclass(frozen=True) ArchivePlan`: `tasks_dir: Path`, `preamble: str`, `entries: list[ArchiveEntry]`, `parse_errors: list[ParseError]`, `remaining: list[Task]`.
  - `plan_archive(tasks_dir, *, today=None) -> ArchivePlan`: split preamble (text before first `## [`); walk task blocks using a forgiving variant of `_parse_task_block` (catch `ValueError`, record, continue); classify terminal vs. remaining; destination = `tasks_dir / "done" / f"{(task.completed or today).strftime('%Y-%m')}.md"`; `today = today or date.today()` for testability.

- [x] **Step 3: Run** `cd science-tool && uv run --frozen pytest tests/test_tasks_archive.py -q -k planner` — expect pass.

- [x] **Step 4: Commit** `feat(tasks-archive): plan archivable terminal-state entries`.

---

## Task 2: Implement Idempotent Apply

**Files:** Modify `science-tool/src/science_tool/tasks_archive.py` and `science-tool/tests/test_tasks_archive.py`.

- [x] **Step 1: Failing apply tests** — `apply_archive(plan)` writes `active.md` as preamble + remaining; no disk writes if `plan.entries` is empty; archived tasks appended in plan-order with existing destination entries preserved first; **destination preamble preservation** (when `tasks/done/2026-03.md` already has its own preamble text above the first `## [tNNN]`, that preamble survives byte-for-byte after the apply); **prior-month routing precedence** (entry with `completed: 2026-03-15` routes to `tasks/done/2026-03.md` even when `today = 2026-04-25`; the entry's `completed:` always wins over `today`); idempotency (capture mtimes, second run leaves them unchanged); duplicate id in destination is skipped, destination file untouched, `duplicate_ids` returned; `parse_errors` non-empty → `RuntimeError`, no writes.

- [x] **Step 2: Implement apply**:
  - `@dataclass(frozen=True) ArchiveResult`: `moved: list[Task]`, `skipped_duplicates: list[str]`, `destinations_written: list[Path]`.
  - `apply_archive(plan)`: raise on `plan.parse_errors`; no-op on empty `plan.entries`; group by destination; for each dest read via `parse_tasks` (empty list if missing), build id-set, append non-duplicates, write via `render_tasks`; rewrite `active.md` as `plan.preamble + render_tasks(plan.remaining)` (empty string if both empty, matching `_write_active`); `mkdir(parents=True, exist_ok=True)` for `done/`.

- [x] **Step 3: Add `count_archivable`** (thin counter so `health.py` does not import the writer):

```python
def count_archivable(tasks_dir: Path) -> dict[str, int]:
    plan = plan_archive(tasks_dir)
    return {
        "done_in_active": sum(1 for e in plan.entries if e.task.status == "done"),
        "retired_in_active": sum(1 for e in plan.entries if e.task.status == "retired"),
        "missing_completed": sum(1 for e in plan.entries if e.missing_completed),
    }
```

- [x] **Step 4: Run** `cd science-tool && uv run --frozen pytest tests/test_tasks_archive.py -q` — expect pass.

- [x] **Step 5: Commit** `feat(tasks-archive): idempotent apply with duplicate detection`.

---

## Task 3: Add `tasks archive` CLI Command

**Files:** Modify `science-tool/src/science_tool/cli.py` and `science-tool/tests/test_tasks_archive.py`.

- [ ] **Step 1: CLI tests** (use `CliRunner`, mirror `test_tasks_cli.py`): default (no `--apply`) prints "would move N" preview, exit 0, `active.md` byte-identical; `--apply` moves entries, second `--apply` reports zero moves; `--check` exits **non-zero (1)** when lag is non-zero and **zero** when clean, JSON shape matches `count_archivable` regardless of exit code; `--format json` on dry-run emits an array with `id`, `status`, `destination`, `missing_completed`; missing `completed:` prints a stderr warning with the task id; malformed `active.md` → `--apply` exits non-zero, dry-run exits 0 with parse errors listed.

- [ ] **Step 2: Add command** below `tasks_unblock` (around `cli.py` line 2046):

```python
@tasks.command("archive")
@click.option("--apply", "do_apply", is_flag=True, help="Write changes to disk (default is dry-run).")
@click.option("--check", is_flag=True, help="Print archivable counts and exit (used by science-tool health).")
@click.option("--format", "output_format", type=click.Choice(OUTPUT_FORMATS), default="table", show_default=True)
@click.option("--tasks-dir", default=DEFAULT_TASKS_DIR, show_default=True,
              type=click.Path(path_type=Path, file_okay=False, dir_okay=True))
def tasks_archive(do_apply: bool, check: bool, output_format: str, tasks_dir: Path) -> None:
    """Move done/retired tasks from active.md to done/YYYY-MM.md."""
    from science_tool.tasks_archive import apply_archive, count_archivable, plan_archive
    if check:
        emit_query_rows(output_format=output_format, title="Tasks Archive Lag",
            columns=[("metric", "Metric"), ("count", "Count")],
            rows=[{"metric": k, "count": v} for k, v in count_archivable(tasks_dir).items()])
        return
    plan = plan_archive(tasks_dir)
    # render plan rows; warn for missing_completed; surface parse_errors
    if do_apply:
        if plan.parse_errors:
            raise click.ClickException("Refusing to apply: parse errors in active.md")
        apply_archive(plan)  # render summary
```

Render style matches `graph migrate` (table or JSON; reference `graph_migrate` in `cli.py`).

- [ ] **Step 3: Run** `cd science-tool && uv run --frozen pytest tests/test_tasks_archive.py -q` — expect pass.

- [ ] **Step 4: Commit** `feat(tasks-archive): CLI command with dry-run default`.

---

## Task 4: Surface Archive Lag In Health Report

**Files:** Modify `science-tool/src/science_tool/graph/health.py`, `cli.py`, `tests/test_health.py`.

- [ ] **Step 1: Failing health test** (append to `TestBuildHealthReport`): scaffold a project with one done + one proposed entry in `active.md`; assert `report["archive_lag"] == {"done_in_active": 1, "retired_in_active": 0, "missing_completed": 0}`.

- [ ] **Step 2: Extend `HealthReport`** in `health.py`:

```python
class TaskArchiveLag(TypedDict):
    done_in_active: int
    retired_in_active: int
    missing_completed: int
```

Append `archive_lag: TaskArchiveLag` to `HealthReport`. In `build_health_report`, before the return:

```python
from science_tool.tasks_archive import count_archivable
archive_lag = count_archivable(project_root / "tasks")
```

Add `"archive_lag": archive_lag,` to the returned dict. The planner returns zero counts when `active.md` is absent (verify in Task 1).

- [ ] **Step 3: Render in `health_command`** — before the unresolved-refs table, render a "Tasks Archive Lag" `Table` if `any(archive_lag.values())`, append a "Next: run `science-tool tasks archive`" hint, and include archive lag in `total_issues` when non-zero.

- [ ] **Step 4: Run** `cd science-tool && uv run --frozen pytest tests/test_health.py tests/test_tasks_archive.py -q` — expect pass.

- [ ] **Step 5: Commit** `feat(tasks-archive): surface archive lag in health report`.

---

## Task 5: Update Slash-Command Guidance

**Files:** Modify `commands/status.md` and `commands/next-steps.md`.

- [ ] **Step 1:** In `commands/status.md` §6 "Staleness Warnings", append a bullet recommending `science-tool tasks archive --apply` when `tasks.archive_lag.{done_in_active, retired_in_active}` is non-zero.

- [ ] **Step 2:** In `commands/next-steps.md` under "Task Tracking Gaps (if any)", append guidance: when `science-tool health --format json` shows non-zero `archive_lag.done_in_active` or `archive_lag.retired_in_active`, add a Recommended Next Action — preview with `science-tool tasks archive`, then `--apply`. Call out `missing_completed` entries so the user backfills `completed:` first.

- [ ] **Step 3: Verify no orphan guidance** — `rg -n "move.*done.*active\.md|manually archive|tasks/done/YYYY-MM" commands/ docs/ README.md` returns nothing recommending manual moves.

- [ ] **Step 4: Commit** `docs(tasks-archive): surface archive lag in status and next-steps`.

---

## Task 6: Verification

**Files:** Verify only.

- [ ] **Step 1: Focused tests** — `cd science-tool && uv run --frozen pytest tests/test_tasks_archive.py tests/test_health.py tests/test_tasks_cli.py tests/test_tasks.py -q` — expect pass.

- [ ] **Step 2: Format and lint** — `uv run --frozen ruff format` + `ruff check` over `science-tool/src/science_tool` — expect no errors.

- [ ] **Step 3: Type check** — `uv run --frozen pyright` — no new errors.

- [ ] **Step 4: Read-only smoke-test against downstream projects** — run `science-tool tasks archive --tasks-dir <project>/tasks --format json` against `natural-systems`, `mm30`, `protein-landscape`. Do **not** pass `--apply`. Expect dry-run plans of ~114, ~44, ~44 entries respectively (audit's 49% / ~30% / 44%) routed to monthly buckets matching `completed:` dates.

- [ ] **Step 5: Smoke-test health surfacing** — `science-tool health --project-root /home/keith/d/r/natural-systems --format json | jq .archive_lag` shows non-zero `done_in_active`; the table view renders the "Next:" hint.

- [ ] **Step 6: Final commit if formatting changed** — `chore(tasks-archive): format archive implementation`. Skip if no diff.

---

## Self-Review Checklist

- Convention coverage: addresses §5.4 / §8.1 / P1 #6 from the audit synthesis. cbioportal's clean shape (`status: done|retired` always lives in `tasks/done/YYYY-MM.md`) is the existence proof; the archiver enforces it.
- Reuse over duplication: leans on the existing `parse_tasks` / `render_tasks` / `Task` model; the archiver is a thin orchestrator, not a parser fork.
- Safety: dry-run default; idempotent apply; duplicate-id detection prevents data loss when re-running against partially-archived state; malformed entries fail loud rather than corrupting files.
- Header / preamble preservation: explicit; current `_write_active` would silently drop preamble — the new module reads, preserves, and re-emits it.
- Health closure: `archive_lag` block surfaces in `science-tool health`, `/science:status`, and `/science:next-steps` so the convention has both an enforcement mechanism and a reminder loop.
- Scope discipline: no changes to project content, `science.yaml`, downstream task files, or the existing `tasks` parser/renderer. The archiver is additive.

---

## Open Questions / Edge Cases For Reviewer

- **Duplicate id with different `completed:` date.** Skip with a warning; do not auto-rewrite. Operator reconciles manually.
- **Cross-month repair.** Archiver does not move already-archived entries to the "correct" month if hand-archived to the wrong file. Acceptable for v1.
- **Round-trip cleanliness.** Verify `parse_tasks` + `render_tasks` is byte-identical on a clean file, or document the diff; the idempotency test will catch any drift.
- **Preamble shapes.** Both "no preamble" (file starts with `## [t001]`) and "with preamble + blank line" must be covered.
- **Concurrent edits.** No locking. Document in slash-command guidance that uncommitted `active.md` edits should be committed or stashed first.

---

## Follow-on actions (NOT part of this plan)

- **`tasks.py` preamble bug.** `_write_active` at `science_tool/tasks.py:164-166` (`(tasks_dir / "active.md").write_text(render_tasks(tasks) if tasks else "")`) silently drops any text above the first `## [tNNN]` heading. The same bug affects `complete_task`, `retire_task`, `add_task`, and `defer_task` — all of which call `_write_active`. The archiver in this plan reads + re-emits preamble correctly, but the preamble bug remains for any other caller. File a separate task to apply the same preamble-preserving rewrite to `tasks.py` so all writers behave consistently.
