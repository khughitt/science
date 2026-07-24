# Agent Context Budget Program — Design

> **Status:** design / spec, approved for planning (2026-07-24). Umbrella design covering
> three sequenced slices: (1) CLI output budgets, (2) guidance + the archive-query capability
> it depends on, (3) task storage split. Slices 1 and 2 are independently shippable; slice 3
> is gated on both landing.
>
> **Rev 2 (2026-07-24)** — revised after design review. Four findings, all verified against the
> code and accepted: the stdout escape hatch was self-contradictory; `emit_query_rows` is too
> narrow to carry a command-wide budget (there are two emitters and three payload shapes); the
> proposed AST guard would have failed on two out-of-scope modules; and `--since` was specified
> as file selection with no row-level date semantics.

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

### There is no single choke point — there are two emitters and three shapes

`science/src/science_tool/output.py` exposes **two** emitters, not one:

- `emit_query_rows` (line 73) — row-shaped output, owning both the JSON and Rich-table paths.
  12 modules adopt it.
- `emit` (line 18) — an arbitrary structured `payload` plus a `render_text` callback. 41 modules
  import from `output`. Its docstring pins a contract that matters here: *"Diagnostics must
  never reach stdout through this function: the JSON branch writes only `json.dumps(payload)`."*

Agent-facing output comes in three shapes, and the two worst offenders are **not** row-shaped:

| Shape | Example | Mechanism |
|---|---|---|
| Rows | `tasks list` | `emit_query_rows`, or a bypass |
| Heterogeneous report | `health` | `emit(payload=report, render_text=…)`, rendering **21 separate tables** (`graph/health_cli.py:75–436`) |
| Versioned document | `entities inventory` | `inventory.model_dump_json(indent=2)` + `click.echo` (`entities_inventory_cli.py:50`) — a pinned `schema_version: "2"` contract with `entities[]`, `content_hash`, `audit_hash` |

**Rich tables are constructed in six production modules**, not one plus three bypasses:
`benchmark_cli.py` (16 sites), `graph/health_cli.py` (21), `datasets/cli.py` (3), `output.py`,
`tasks_display.py`, `verdict/cli.py`. `benchmark_cli.py` and `datasets/cli.py` carry
agent-facing query tables that are all under 20k chars.

**Design consequences.** Flattening `health` or `entities inventory` into `{"rows": …}` would
break their consumers. Calling `emit_query_rows` once per `health` section would enforce 21
per-section ceilings rather than one command-total ceiling. And a blanket "no `Table` outside
`output.py`" guard would fail immediately on two modules this program has no reason to touch.
The budget therefore has to live **beneath** both emitters, at the command level.

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

**The core invariant.** One sentence governs everything below:

> **stdout is always budgeted; `--output PATH` is always complete.**

There is no flag that makes stdout unbounded. Completeness is obtained by choosing a sink, not
by defeating a ceiling. This is what makes the escape hatch honest — the previous draft promised
a "full set" on stdout while also enforcing an unconditional ceiling, which cannot both hold.

**Canonicalize — a `BoundedSink` beneath both emitters.** A command-level sink owns the
character budget for **the whole invocation**, not per-emitter-call. Both `emit` and
`emit_query_rows` accept it and write through it, so a command emitting 21 tables gets one
total ceiling rather than 21 independent ones. The sink is the new abstraction; the two
emitters keep their existing payload shapes.

Budgets are declared per command in **one registry module** — a single SSOT rather than
per-command constants.

**Payload shapes are preserved, not flattened.** `health` keeps its heterogeneous report and
`entities inventory` keeps its versioned `schema_version: "2"` document. The sink governs
*whether and how much* reaches stdout, never the payload's schema.

**Truncation semantics, per format.**

- *Text/table:* truncated output ends with a footer naming what was withheld and the exact
  command to obtain all of it.
- *JSON:* truncation is recorded **inside the payload** as a `truncation` object
  (`{omitted, total, complete_via}`), never as a side-channel `echo` — `emit`'s docstring
  forbids diagnostics on the JSON branch, and a consumer parsing stdout must be able to detect
  truncation from the document itself.
- *Versioned documents* (`entities inventory`): the sink **refuses** rather than truncates.
  Emitting a partial document under a `schema_version` contract would be a lie about the
  contract. Past budget the command exits non-zero telling the caller to pass `--output`.

**Counting semantics.** The budget counts **characters of rendered output**, measured after
rendering. For determinism, table rendering pins an explicit console width rather than
inheriting Rich's non-TTY default, so the same data costs the same budget regardless of
environment. This is for reproducible accounting, not size reduction — width was measured at
8% on `tasks list`.

**The file sink is uniform.** Every budgeted command accepts `--output PATH`, writes the
complete payload there, and prints a one-line summary plus the path. Today only
`entities inventory` has `--output`; `tasks list` and the rest gain it. `--all` keeps its
existing meaning on `tasks list` — *include done and retired* (`tasks_cli.py:491`), a
**selection** flag — and does not bypass the ceiling.

The corrected footer:

```
showing 12 of 209 rows (budget: 12 rows / 8,000 chars)
  widen selection:  science tasks list --status proposed
  complete output:  science tasks list --format json --output tasks.json
```

The defect being fixed is the host's *silent* truncation; the replacement must not reproduce
it. This follows the project's fail-early / explicit-over-defensive rule.

**Default filters shift to the working set.** `tasks list` defaults to active+blocked (~3.4k
vs ~41k tokens). `health` defaults to error severity, with a flag for warnings.

Precedent: `curate inventory` already ships `--recently-modified-top-k` (default 20), so this
pattern is established in the codebase rather than novel.

**Guard — scoped by derivation, not by blanket rule.** Three tests:

1. **Registry completeness.** Walk the click command tree from `main` and assert every leaf
   command is either registered with a budget or carries an explicit exemption with a reason.
   Scope is derived from the CLI tree, so a new command cannot silently escape — a guard that
   hand-lists its own scope has a hole by construction.
2. **Sink routing.** For commands *in the registry*, assert output reaches stdout only through
   a `BoundedSink`. Deliberately **not** a blanket "no `Table` outside `output.py`" rule: six
   modules construct tables, and `benchmark_cli.py` / `datasets/cli.py` are under 20k chars and
   out of scope by design.
3. **Budget regression.** Per-command character ceilings asserted against a fixture project.

### Slice 2 — guidance, and the capability it depends on

**Add the missing query first.** Extend `tasks list` with `--since <date>`, reusing the
existing `--related` / `--group` / `--aspect` filters; `list_tasks` gains an archive-reading
path. Month-file selection is **only a read optimization** — the authoritative filter is
row-level, and the two must not be confused:

- **Row filter.** A task matches when `task.completed >= since`. Selecting archive months that
  intersect the window narrows which files are parsed; it never decides membership. A boundary
  month legitimately holds tasks on both sides of the cutoff.
- **`completed` is a *closed* date, not a success date.** Both `complete_task`
  (`tasks.py:599`) and `retire_task` (`tasks.py:631`) set `task.completed = date.today()`.
  So `--since` means "closed on or after D", and retired tasks participate by default;
  `--status done` narrows to successful completions.
- **Missing `completed` is excluded and reported, never guessed.** `_destination_for`
  (`tasks_archive.py:120`) routes a task with no `completed:` date to *today's* month file and
  flags `missing_completed`. File location is therefore not evidence of date — an undated task
  finished in April can sit in `done/2026-07.md`. Such tasks are excluded from `--since` results
  and their count is reported on stderr, so a caller learns the answer is incomplete instead of
  silently receiving a wrong window. natural-systems already has one (`missing_completed: 1` in
  its current `health` output).
- **`--since` implies closed tasks.** Open tasks have no `completed` date, so combining
  `--since` with a non-terminal `--status` (`active`, `proposed`, `blocked`, `deferred`) is a
  usage error and fails early rather than returning a confusingly empty set.

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
- Reducing output size by widening the console. Measured at 8% on the surface that needed it
  most. (A width *is* pinned in slice 1, but for deterministic budget accounting, not savings.)
- Migrating `benchmark_cli.py` (16 table sites) or `datasets/cli.py` (3) onto the sink. Both are
  under 20k chars; they fall under the registry-completeness guard as explicit exemptions.
- Reducing `entities/` document sizes (4 files over the cap in natural-systems).
- Any change to the 33 CLI commands already under 20k chars.
- Fixing the three invalid task statuses in natural-systems (`t873: closed-unbuilt`,
  `t878: complete`, `t881: complete`). Real, surfaced by `parse_tasks_for_cli` on stderr, but a
  data defect in one project rather than part of this program.

## Risks

- **Budget defaults that hide needed data.** Mitigated by the explicit footer and `--output`, but
  the per-command defaults need review against how each command is actually invoked in
  `commands/` and `skills/`, not chosen from output size alone.
- **The emitter refactor touches `health`**, whose output shape is asserted by tests. Expect to
  update assertions; check them before refactoring rather than after.
- **Slice 3 migration spans six repos**, several Dropbox-synced with volatile branches. Verify
  the branch before committing in each, and treat the roster as derived rather than listed.
- **Token estimates are chars ÷ 3.5**, not tokenizer output. Budgets should be set with margin
  and the regression test should assert characters, which are measurable, rather than tokens.

## Testing

- Registry completeness: every leaf command in the click tree is budgeted or explicitly exempt,
  with the command set derived by walking `main`.
- Sink routing: registered commands reach stdout only through a `BoundedSink`.
- Budget regression: per-command character ceilings asserted against a fixture project.
- Total-vs-per-section accounting: a multi-table command (`health`, 21 tables) respects one
  command-total ceiling, not one per table.
- Footer behaviour: truncated text output names the withheld count and the escape command.
- JSON truncation metadata: the `truncation` object appears **in the payload**, stdout on the
  JSON branch stays a single parseable document, and no diagnostics leak into it.
- Versioned-document refusal: `entities inventory` past budget exits non-zero rather than
  emitting a partial `schema_version: "2"` document.
- `--output` completeness: the file sink is never truncated, for every budgeted command.
- Width determinism: identical data costs identical budget across `COLUMNS` values.
- `tasks list --since`: exact cutoff (`completed == since` is included); a boundary month
  holding tasks on both sides of the cutoff; a task with no `completed:` date is excluded and
  counted on stderr; retired tasks included by default and excluded under `--status done`;
  `--since` with a non-terminal `--status` fails early; a window intersecting a month with no
  archive file.
- Content guard: no agent-facing doc instructs a direct read of a CLI-owned file.
- Migration: journal/resume correctness on an interrupted run; round-trip fidelity of task
  metadata and body prose; `graph/storage_adapters/task.py` reads the new layout.

## Sequencing

1. **Slice 1** — budget contract, emitter migration, defaults, guards. Independently shippable.
2. **Slice 2** — `tasks list --since`, then the eight guidance rewrites and the content guard.
   Independently shippable; depends on slice 1 only for having cheap forms to point at.
3. **Slice 3** — storage split and migration. Gated on 1 and 2.
