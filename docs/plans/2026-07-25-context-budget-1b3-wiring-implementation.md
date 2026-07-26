# Context-budget slice 1b-3 wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development.
> Steps use checkbox (`- [ ]`) syntax. Execute batch-by-batch; each batch is one or more
> SDD implementer tasks with a review gate.

**Goal:** Wire the 56 doc-referenced growable commands from the 1b-3 audit
(`2026-07-25-context-budget-1b3-audit.md`) through the context-budget sink, so an agent
that runs any of them in a session gets bounded stdout + a complete `--output` escape.

**Architecture:** Reuse the slice-1a/1b machinery unchanged — `BUDGETS` registry,
`BoundedSink`, `project_rows` (ROWS), per-command projectors (REPORT), refuse-past-budget
(DOCUMENT). No new architecture; this is applying the established recipes to 56 more
commands. A shared `project_single_list_report` helper is added for the common REPORT
shape (summary + one growable list).

**Scope:** The 56 doc-referenced WIRE commands only. The 92 non-doc-referenced WIRE
commands stay `DEFERRED`. The 6 write-audit-leak commands are a separate plan
(`...-1b3-writeleak-implementation.md`). 1b-3a already reclassified the 44 EXEMPT.

## Global Constraints

- **Invariant:** stdout is always budgeted; `--output PATH` is always complete. Summary
  counts AND exit codes always derive from the FULL result, never the projected view.
- Every budgeted command constructs its OWN `BoundedSink(...)` in its callback body (AST
  guard `test_every_budgeted_command_constructs_its_own_sink`); a shared helper that builds
  the sink fails the guard. A shared *projector* is fine — only sink construction must be inline.
- Every budgeted command exposes `--output PATH` (AST guard
  `test_every_budgeted_command_offers_the_output_escape`).
- `--output` extension tracks the effective format via `hint_for(stem, output_format)`
  (never a hardcoded `.json`).
- Each command moved into `BUDGETS` is removed from `DEFERRED`, and
  `EXPECTED_CLASSIFICATION_COUNTS` in `tests/test_budget_boundary.py` is bumped
  (`budgeted += N`, `deferred -= N`) in the SAME commit.
- ROWS ceiling `max_chars=20_000`; REPORT ceiling `max_chars=30_000`. `max_rows` starts at
  40 and is LOWERED (never raise the ceiling, never shrink test seed data) if a wide row
  exceeds the ceiling at 40 — the 1b-1 `feedback list` lesson.
- Package dir is `science/`. Conventional commits, NO AI-attribution trailer.
- Python 3.11 floor: no PEP 695; use `from __future__ import annotations` + TYPE_CHECKING.

## Reference recipes

### Recipe R-ROWS-emitqueryrows (exact 1b-1 pattern, `entities_cli.py:215-268`)
For a command already rendering via `emit_query_rows`:
1. Register `BUDGETS["<path>"] = CommandBudget(max_chars=20_000, shape=ROWS, max_rows=40)`.
2. Add `--output/output_path` option (and `--format` if missing — see per-command table).
3. In the callback, after building `rows`:
   ```python
   from science_tool.budget.control import bounded_control_notice
   from science_tool.budget.invocation import build_complete_via, hint_for
   from science_tool.budget.registry import lookup
   from science_tool.budget.sink import BoundedSink
   complete_via = build_complete_via(click.get_current_context(), output_hint=hint_for("<stem>", output_format))
   control_notice = bounded_control_notice(f"wrote {len(rows)} <things> to {output_path}") if output_path is not None else None
   sink = BoundedSink(lookup("<path>"), output_path=output_path, command_path="<path>", complete_via=complete_via)
   emit_query_rows(..., rows=rows, sink=sink)
   sink.flush()
   if control_notice is not None:
       click.echo(control_notice)
   ```

### Recipe R-ROWS-emit / R-ROWS-echo
For ROWS commands that render via `emit(payload, render_text)` or direct `click.echo`:
- Ensure the callback builds a full `rows` list and a summary that is computed from the
  FULL list. Convert the render path to go through the sink: prefer switching to
  `emit_query_rows` when the output is a plain table; otherwise project the rows list with
  `project_rows(rows, sink.max_rows)`, render the projected view via `sink.console`/`sink.echo`,
  append the "showing N of M … complete output:" footer when truncated, and `sink.flush()`.
- Add `--format` (Choice(OUTPUT_FORMATS)) where missing so JSON is a complete-output channel.

### Recipe R-REPORT (1b-2 pattern; `validate/`, `prose_lint`, `consolidation_candidates`)
1. Register `CommandBudget(max_chars=30_000, shape=REPORT)`.
2. Build the FULL report payload. `displayed = full if output_path is not None else project_X(full)`.
3. For summary+one-list reports use the shared helper (added in Task W4-0):
   `project_single_list_report(payload, list_key="<key>", cap=40)` — caps the one growable
   list, records `<key>_omitted`, passes the summary through untouched. For genuinely
   multi-list reports, write a bespoke `*_projection.py` beside the command (mirror
   `graph/health_projection.py`).
4. Render via `sink.console`/`sink.echo`; footer names withheld count + escape when projected.
5. `emit(..., sink=sink)`; `sink.flush()`. Summary counts + exit code from the FULL payload.

### Recipe R-DOCUMENT (`entities inventory` / `curate inventory` pattern)
Refuse past budget: serialize whole payload, `flush()` raises `BudgetExceeded` (prints
nothing) when over ceiling on stdout; `--output` writes complete. `inquiry export-pgmpy`
already has `--output`; add the sink + refuse path and a `--format`.

## Tasks (batches)

Each batch below is an SDD task (large batches split as noted). After each: register in
BUDGETS, remove from DEFERRED, bump the partition guard, add per-command regression
coverage in `tests/test_budget_regression.py` (ceiling honored on a fixture that overflows;
`--output` complete), and run `tests/test_budget_boundary.py tests/test_budget_registry.py
tests/test_budget_regression.py` plus the touched command's own tests. The boundary AST
guards auto-verify sink-ownership and `--output` presence.

### Batch W1a-graph-rows (11)

| Command | Callback | has --format? | has --output? |
|---|---|---|---|
| `graph attention-rank` | src/science_tool/graph/cli.py:667 | yes | no |
| `graph attention-sample` | src/science_tool/graph/cli.py:604 | yes | no |
| `graph audit` | src/science_tool/graph/cli.py:168 | yes | no |
| `graph dashboard-summary` | src/science_tool/graph/cli.py:439 | yes | no |
| `graph diff` | src/science_tool/graph/cli.py:240 | yes | no |
| `graph gaps` | src/science_tool/graph/cli.py:395 | yes | no |
| `graph inquiry-summary` | src/science_tool/graph/cli.py:536 | yes | no |
| `graph neighborhood-summary` | src/science_tool/graph/cli.py:478 | yes | no |
| `graph question-summary` | src/science_tool/graph/cli.py:508 | yes | no |
| `graph rehoming-debt` | src/science_tool/graph/cli.py:566 | yes | no |
| `graph uncertainty` | src/science_tool/graph/cli.py:415 | yes | no |

### Batch W1b-other-rows (9)

| Command | Callback | has --format? | has --output? |
|---|---|---|---|
| `datasets files` | src/science_tool/datasets_discovery_cli.py:126 | yes | no |
| `datasets search` | src/science_tool/datasets_discovery_cli.py:42 | yes | no |
| `datasets validate` | src/science_tool/datasets_discovery_cli.py:208 | yes | no |
| `entity rotation` | src/science_tool/entities_cli.py:687 | yes | no |
| `feedback regression-candidates` | src/science_tool/feedback_cli.py:462 | yes | no |
| `feedback targets` | src/science_tool/feedback_cli.py:442 | yes | no |
| `inquiry list` | src/science_tool/inquiry_cli.py:211 | yes | no |
| `project index` | src/science_tool/project_cli.py:257 | yes | no |
| `tasks archive` | src/science_tool/tasks_cli.py:312 | yes | no |

### Batch W2-rows-via-emit (7)

| Command | Callback | has --format? | has --output? |
|---|---|---|---|
| `annotate promote` | src/science_tool/annotation/cli.py:2468 | yes | no |
| `big-picture resolve-questions` | src/science_tool/big_picture/cli.py:39 | **no** | no |
| `book-split` | src/science_tool/book_split_cli.py:21 | yes | no |
| `dataset reconcile-links` | src/science_tool/datasets/cli.py:552 | yes | no |
| `qa-audit` | src/science_tool/qa_audit/cli.py:27 | yes | yes |
| `skills lint` | src/science_tool/skills_lint/cli.py:35 | yes | no |
| `tasks blockers` | src/science_tool/tasks_cli.py:182 | yes | no |

### Batch W3-rows-via-echo (8)

| Command | Callback | has --format? | has --output? |
|---|---|---|---|
| `annotate list` | src/science_tool/annotation/cli.py:1953 | yes | no |
| `big-picture validate` | src/science_tool/big_picture/cli.py:94 | **no** | no |
| `dataset register-run` | src/science_tool/datasets/cli.py:632 | **no** | no |
| `datasets download` | src/science_tool/datasets_discovery_cli.py:172 | **no** | no |
| `feedback add` | src/science_tool/feedback_cli.py:41 | **no** | no |
| `research-package build` | src/science_tool/research_package/cli.py:139 | **no** | no |
| `sync projects` | src/science_tool/sync_cli.py:79 | **no** | no |
| `tasks fix-blockers` | src/science_tool/tasks_cli.py:225 | **no** | no |

### Batch W4-report (20)

| Command | Callback | has --format? | has --output? |
|---|---|---|---|
| `annotate synthesize` | src/science_tool/annotation/cli.py:2598 | yes | no |
| `benchmark list` | src/science_tool/benchmark_cli.py:48 | yes | no |
| `commons promote dataset` | src/science_tool/commons/cli.py:1235 (shared impl _promote_kind_cmd at cli.py:1309) | **no** | no |
| `dag audit` | src/science_tool/dag/cli.py:184 | yes | no |
| `dag validate` | src/science_tool/dag/cli.py:294 | yes | no |
| `dataset prioritize` | src/science_tool/datasets/cli.py:133 | yes | no |
| `explore-ideas apply` | src/science_tool/explore_ideas_cli.py:38 | yes | no |
| `explore-ideas gaps` | src/science_tool/explore_ideas_cli.py:127 | yes | no |
| `explore-ideas resolve-anchors` | src/science_tool/explore_ideas_cli.py:146 | yes | no |
| `inquiry show` | src/science_tool/inquiry_cli.py:241 | yes | no |
| `inquiry validate` | src/science_tool/inquiry_cli.py:286 | yes | no |
| `peers list` | src/science_tool/peers_cli.py:49 | yes | no |
| `project topic-coverage` | src/science_tool/project_cli.py:38 | yes | no |
| `refs check` | src/science_tool/refs_cli.py:85 | yes | no |
| `research-package validate` | src/science_tool/research_package/cli.py:61 | yes | no |
| `sync rebuild` | src/science_tool/sync_cli.py:94 | **no** | no |
| `sync run` | src/science_tool/sync_cli.py:17 | **no** | no |
| `sync status` | src/science_tool/sync_cli.py:50 | **no** | no |
| `tasks summary` | src/science_tool/tasks_cli.py:710 | yes | no |
| `wander` | src/science_tool/wander/cli.py:60 | yes | yes |

### Batch W5-DOCUMENT (1)

| Command | Callback | has --format? | has --output? |
|---|---|---|---|
| `inquiry export-pgmpy` | src/science_tool/inquiry_cli.py:307 | **no** | yes |

## Sequencing

1. **W1a** graph ROWS (11) — most uniform, highest doc-exposure (big-picture/create-graph). First.
2. **W1b** other ROWS-emitqueryrows (9).
3. **W2** ROWS-via-emit (7).
4. **W3** ROWS-via-echo (8) — add `--format` to the 6 that lack it.
5. **W4-0** add `project_single_list_report` helper + its unit test. Then **W4** REPORT (20),
   split by group into ~3 implementer tasks (annotate/benchmark/dataset/explore;
   dag/inquiry/peers/refs/research-package; sync/tasks/wander/project/commons).
6. **W5** DOCUMENT (1).

Each batch: `budgeted += N` / `deferred -= N`. End state after all: budgeted 70,
exempt 111, deferred 98 (154 − 56). Verify the full suite once at the end from the controller.

## Testing (per the design's Slice-1 test list)

- Per-command ceiling honored against an overflowing fixture; `--output` file complete.
- Footer/JSON-truncation metadata present when projected; summary + exit from full result.
- Boundary guards (sink ownership, `--output` presence, partition cardinality) stay green.
