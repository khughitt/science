# Agent Context Budget Program — Design

> **Status:** design / spec, approved for planning (2026-07-24). Umbrella design covering
> three sequenced slices: (1) CLI output budgets, (2) guidance + the archive-query capability
> it depends on, (3) task storage split. Slices 1 and 2 are independently shippable; slice 3
> is gated on both landing.

## Motivation

Agent context is a finite, repeatedly-paid resource, and the toolkit currently spends it in
three ways it did not intend to:

1. **Read-only CLI query commands emit unbounded output.** The largest emits 21 MB to stdout
   — roughly 6 million tokens, about 60× a 200k context window.
2. **The largest project files exceed the host's file-read cap**, so reading them returns a
   silently truncated prefix. For `tasks/active.md` that prefix is the *oldest* tasks, which
   is close to the least useful slice.
3. **The toolkit's own guidance instructs direct reads of the files it elsewhere declares
   CLI-owned**, and one of those instructions is unsatisfiable as written.

The `science tasks` CLI already exists and is well-factored; the problem is not a missing
abstraction but unbudgeted defaults, a handful of emitter bypasses, and guidance drift.

## Host mechanics this design depends on

Measured against Claude Code v2.1.218 (`~/.local/share/claude/versions/2.1.218`). These are
host internals and may change; the design should not become incorrect if the specific numbers
move, only less precisely tuned.

- **File reads are capped at 25,000 tokens** by default (`CLAUDE_CODE_FILE_READ_MAX_OUTPUT_TOKENS`
  overrides). Past the cap the read returns a paginated prefix with a warning, not an error.
- **On conversation compaction, previously-read files are restored.** A file that fits under
  the cap is re-injected **in full, on every compaction**. A file over the cap is downgraded
  to a path-only reference carrying a single note (~35 tokens) and no content.
- **Consequence — cost is non-monotonic in file size.** A file just under the cap is the most
  expensive thing to have read; a file far over it is nearly free at compaction time (though
  useless to read). Shrinking a very large file *into* that band makes matters worse.

At ~3.5 chars/token, the cap is ≈87,500 characters and the expensive band is ≈35,000–87,500
characters.

## Measurement method

All 47 read-only `science` query commands run against `~/d/natural-systems` (213 tasks, 369
entities — the largest adopting project), stdout measured in characters. Markdown swept across
`~/d/3d-attention-bias`, `~/d/cats`, `~/d/natural-systems`, `~/d/protein-landscape`,
`~/d/seq-feats`, and `~/d/science/meta`. No write, build, migrate, or reserve commands were
executed. Token figures throughout are chars ÷ 3.5 and are estimates, not tokenizer output.

## Grounding findings

### CLI output, by cost

| Command | chars | ~tokens | Referenced in agent-facing docs |
|---|---|---|---|
| `entities inventory` | 21,015,117 | ~6,000k | none |
| `data audit` | 12,325,523 | ~3,521k | 1 skill |
| `entity list` | 1,706,994 | ~487k | 1 command |
| `curate inventory` | 683,657 | ~195k | 1 command |
| `prose lint` | 550,226 | ~157k | 1 command |
| `health` | 426,926 | ~121k | **10 docs, incl. `templates/agents-md.md`** |
| `tasks list` | 144,655 | ~41k | 4 docs |
| `questions list` | 113,076 | ~32k | none |
| `validate` | 109,466 | ~31k | **50+ docs** |
| `interpretations list` | 97,281 | ~28k | none |
| `curate consolidation-candidates` | 71,553 | ~20k | none |
| `entity needs-review` | 59,697 | ~17k | none |
| `feedback list` | 44,307 | ~13k | 2 commands (`status`, `next-steps`) |
| `discussions list` | 30,780 | ~9k | none |

For contrast, the cheap task surfaces that already exist:

| Command | chars | ~tokens |
|---|---|---|
| `tasks list --status active` | 12,013 | ~3.4k |
| `tasks show <id>` | 1,713 | ~0.5k |
| `tasks summary` | 1,692 | ~0.5k |

Of 47 measured invocations, 15 exceed 20,000 chars (14 distinct commands plus `health --fast`)
and 32 are under. **The offender set is small and bounded**, which is what makes a budget
contract tractable.

Notable specifics:

- **`entities inventory` writes a 21 MB pretty-printed JSON document (286,410 lines) to
  stdout by default.** It already accepts `--output PATH`; only the default is wrong. Nothing
  references it, so present exposure is low, but it is discoverable via `--help`.
- **`validate` is the systemic risk, not `health`.** At ~31k tokens it is only the 9th largest,
  but it is recommended in 50+ agent-facing docs and sits *just over* the read cap — so it is
  the command an agent actually runs, in nearly every session.
- **`health --fast` is not a context mitigation**: 425,549 vs 426,926 chars, 0.3% smaller. It
  skips checks that need project sources, but those were not producing the output.
- **99.5% of `health` is one table.** `Validation (361)` is 5,242 of 5,278 lines and 424,601 of
  426,926 chars — ≈1,176 chars per finding. The same findings as JSON are 163,343 chars
  (≈452/finding), so table rendering inflates 2.6×. `document_structure` emits one row per
  missing section, so one entity with five missing sections costs five rows ≈ 30 wrapped lines.

### A hypothesis the measurements killed

An early diagnosis blamed Rich wrapping into 80 columns (the non-TTY default; no `width=` is
set anywhere — see `_new_console`, `science/src/science_tool/styles.py:145`). **This is wrong
for `tasks list`**: 144,655 chars at `COLUMNS=80` vs 133,603 at `COLUMNS=400`, an 8% difference.
The cost is intrinsic content volume — of 209 rows, `related` refs are 38% of the payload and
titles 21%. Width *does* matter for `health` (426,926 → 275,770 at `COLUMNS=250`, −35%) because
long path strings are duplicated across the `Path` and `Message` columns.

**Design consequence:** the fix is row and column selection, not terminal width. Pinning a
console width would have produced an 8% improvement on the surface that most needed one.

### The emitter already exists, and the offenders bypass it

`emit_query_rows` (`science/src/science_tool/output.py:73`) is a shared emitter owning **both**
the JSON and Rich-table paths, adopted by 13 modules. Three modules bypass it —
`tasks_display.py`, `graph/health_cli.py`, `verdict/cli.py` — and the top offenders live
exactly there (`tasks list` via `render_tasks_table`, `health` via `graph/health_cli.py`).
`entities inventory` dumps raw JSON without passing through it.

This is the same **canonicalize → migrate → guard** shape used by the toolkit convergence
program, with the choke point already built and mostly adopted.

### Working set vs. backlog

In natural-systems, of 209 tasks: 180 `proposed`, 12 `active`, 10 `deferred`, 4 `blocked`,
3 carrying invalid statuses. **The default `tasks list` cost is proportional to the whole
backlog while the working set is ~6% of it** — hence ~41k tokens for the default view vs ~3.4k
for `--status active`.

### File surfaces

- **Over the cap (silent truncation).** natural-systems has 8 tracked markdown files over
  ~87,500 chars. `tasks/active.md` at 390,941 chars returns ≈23% on read; because tasks sort by
  id, that prefix is the ~48 oldest, overwhelmingly `proposed`. An agent answering "what should
  I work on" from that page is confidently wrong. **This is a correctness defect, not a cost
  defect**, and it is the primary justification for slice 3.
- **Inside the expensive band (compaction tax).** `meta/tasks/active.md` at 67,589 chars
  (~19k tokens) is re-injected in full on every compaction; natural-systems' 390,941-char file
  never is. The dominant population in this band across every project is `doc/plans/` —
  natural-systems has 10+ plan docs at 21–24k tokens each, and plans are read deliberately and
  held across long implementation sessions.
- **`tasks/done/` archives are large and unqueryable.** natural-systems totals 1,036,637 chars
  (~296k tokens) across 4 monthly files, each individually over the cap.
- **Toolkit-side markdown is healthy — no action needed.** 68 skills (largest 23,918 chars),
  39 commands (largest 25,152), 5 references (largest 7,303). Nothing near the cap.

### Guidance defects

The toolkit instructs direct reads of files it elsewhere declares CLI-owned:

| Site | Problem |
|---|---|
| `commands/tasks.md:23` | The **Setup step of the tasks command itself** says "Read `tasks/active.md` if it exists" — 13 lines after declaring the CLI authoritative. |
| `commands/review-tasks.md:28` | "Read `tasks/active.md` for full task descriptions." |
| `commands/discuss.md:22` | Lists `tasks/active.md` as a source to read. |
| `commands/create-graph.md:48` | Reads task files directly. |
| `commands/big-picture.md:68` | Globs `tasks/*.md` and `tasks/done/*.md`. |
| `references/role-prompts/discussant.md:17` | Reads `tasks/active.md`. |
| `references/role-prompts/research-assistant.md:15` | Reads `tasks/active.md`. |
| `templates/agents-md.md:88` | Recommends bare `uv run science health` (~121k tokens) as the failure fallback. |

`commands/next-steps.md:160` is the worst case and is **unsatisfiable as written**: it directs
the agent to scan every `tasks/done/YYYY-MM.md` intersecting the window and explicitly says
"Do not stop at the current month file or assume the prior month is irrelevant *just because it
is large*." Each such file is over the read cap, so each read silently returns a 25k prefix.
The instruction overrides the one heuristic that would have limited the damage.

**This instruction exists because no capability backs it.** `list_tasks`
(`science/src/science_tool/tasks.py:751`) reads only `_read_active`; the done archives have no
list-or-filter surface at all. `find_task` (line 451) does search `done/*.md`, so
`tasks show <id>` works on archived tasks. Rewriting the doc without adding the query would
make it unfollowable rather than merely expensive.

## Design

### Slice 1 — the context-budget contract

**Canonicalize.** `emit_query_rows` becomes the sole emitter for row-shaped output and gains a
budget parameter. Every agent-facing query command declares its budget (row count and a
character ceiling) in **one registry module** — a single SSOT rather than per-command constants.

**Migrate.** Route the three bypasses (`tasks_display.py`, `graph/health_cli.py`,
`verdict/cli.py`) through the emitter. `entities inventory` gains the same treatment for its
JSON path.

**Enforcement: per-command defaults plus an emitter backstop.** Sensible per-command defaults
do the real work; the emitter also enforces an absolute ceiling so a project several times the
size of natural-systems cannot blow context on an unfiltered command. The backstop exists
because a CI-only regression test catches growth in the fixture, not in the field.

**Truncation is explicit, never silent.** Past budget, the emitter prints the budgeted rows
and a footer naming what was withheld and exactly how to obtain it:

```
showing 12 of 209 rows (budget: 12 active/blocked)
  full set:  science tasks list --all
  machine:   science tasks list --format json --output tasks.json
```

The defect being fixed is the host's *silent* truncation; the replacement must not reproduce
it. This follows the project's fail-early / explicit-over-defensive rule.

**Bulk dumps get a file, not stdout.** `entities inventory` and `data audit` refuse to write
past-budget payloads to stdout, requiring `--output PATH` and printing a one-line summary plus
the path. For `entities inventory` this is a default change only.

**Default filters shift to the working set.** `tasks list` defaults to active+blocked (~3.4k
vs ~41k tokens). `health` defaults to error severity, with `--all` for warnings.

Precedent: `curate inventory` already ships `--recently-modified-top-k` (default 20), so this
pattern is established in the codebase rather than novel.

**Guard.** Two tests:

1. An **AST guard** asserting no module outside `output.py` constructs a `rich.table.Table` or
   prints one, with scope **derived from the import closure** rather than a hand-listed set of
   modules — a guard that enumerates its own scope has a hole by construction.
2. A **budget regression test** over a fixture project asserting every declared ceiling holds.

### Slice 2 — guidance, and the capability it depends on

**Add the missing query first.** Extend `tasks list` with `--since <date>`, reading
`done/*.md` for months intersecting the window and merging with `active.md`. This keeps one
task-query surface and reuses the existing `--related` / `--group` / `--aspect` filters;
`list_tasks` gains an archive-reading path.

**Then rewrite the eight guidance sites** in the table above to use filtered CLI forms, and
fix `commands/next-steps.md:160` to use `tasks list --status done --since` instead of scanning
archives.

**Retarget `templates/agents-md.md:88`** from bare `science health` to a scoped form.

**Guard.** A content test asserting no agent-facing doc instructs a direct read of a
CLI-owned file. This extends the existing content-guard pattern (`test_command_docs.py`,
`test_codex_skills.py`); **read those tests before reshaping any doc** — they assert
skill/command markdown by file, and reshaping without checking them has broken this repo before.

### Slice 3 — task storage

**Model.** `tasks/active/tNNN-slug.md`, one file per open task, frontmatter plus body,
mirroring the `entities/` convention. `active.md` is removed outright — no dual-read
compatibility layer.

**Why splitting rather than shrinking.** The compaction band makes the middle the worst place
to sit. Per-task files land at ≈1,800 chars each: cheap to read, cheap to re-inject, and
complete rather than silently truncated. Trimming a large `active.md` toward the cap would move
it *into* the expensive band.

**Done archives stay monthly ledgers.** `tasks/done/YYYY-MM.md` is append-only and not
individually worked; splitting would turn natural-systems' 4 files into ~700 for no read
benefit, and slice 2 gives it a query surface. The asymmetry is deliberate: open tasks are
addressable working documents, closed tasks are a ledger.

**Migration** follows the transactional migrator pattern used by `dataset migrate-capabilities`
— journal, pin-last, resume — so a failure partway through 200 tasks is recoverable.
`graph/storage_adapters/task.py` reads the current layout and is updated in the same slice.

**Scope.** Six projects carry `tasks/active.md`: natural-systems (390,941 chars),
protein-landscape (91,663), `science/meta` (67,589), 3d-attention-bias (37,057), seq-feats
(33,480), cats (15). `science-commons` has none. The plan must enumerate targets from the
sibling roster, not this list, which is a snapshot.

**Gating.** Slice 3 waits on 1 and 2. Migrating storage while agents are still directed to read
files directly would change where the bytes live without changing what agents do.

## Non-goals

- Changing `doc/plans/` document sizes or splitting plan documents. They are the dominant
  compaction-band population and worth a later look, but plan authoring is a separate concern
  from task storage and CLI budgets.
- Pinning a Rich console width. Measured at 8% on the surface that needed it most.
- Reducing `entities/` document sizes (4 files over the cap in natural-systems).
- Any change to the 33 CLI commands already under 20k chars.
- Fixing the three invalid task statuses in natural-systems (`t873: closed-unbuilt`,
  `t878: complete`, `t881: complete`). Real, surfaced by `parse_tasks_for_cli` on stderr, but a
  data defect in one project rather than part of this program.

## Risks

- **Budget defaults that hide needed data.** Mitigated by the explicit footer and `--all`, but
  the per-command defaults need review against how each command is actually invoked in
  `commands/` and `skills/`, not chosen from output size alone.
- **The emitter refactor touches `health`**, whose output shape is asserted by tests. Expect to
  update assertions; check them before refactoring rather than after.
- **Slice 3 migration spans six repos**, several Dropbox-synced with volatile branches. Verify
  the branch before committing in each, and treat the roster as derived rather than listed.
- **Token estimates are chars ÷ 3.5**, not tokenizer output. Budgets should be set with margin
  and the regression test should assert characters, which are measurable, rather than tokens.

## Testing

- AST guard: no `Table` construction or printing outside `output.py`, scope derived from the
  import closure.
- Budget regression: per-command character ceilings asserted against a fixture project.
- Footer behaviour: truncated output always names the withheld count and the escape command.
- `tasks list --since`: window arithmetic across a month boundary, including a window that
  intersects a month with no archive file.
- Content guard: no agent-facing doc instructs a direct read of a CLI-owned file.
- Migration: journal/resume correctness on an interrupted run; round-trip fidelity of task
  metadata and body prose; `graph/storage_adapters/task.py` reads the new layout.

## Sequencing

1. **Slice 1** — budget contract, emitter migration, defaults, guards. Independently shippable.
2. **Slice 2** — `tasks list --since`, then the eight guidance rewrites and the content guard.
   Independently shippable; depends on slice 1 only for having cheap forms to point at.
3. **Slice 3** — storage split and migration. Gated on 1 and 2.
