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
>
> **Rev 3 (2026-07-24)** — second review round, three findings, all verified and accepted:
> truncation cannot happen post-render in the sink (split into projection + sink); the `health`
> severity default was underdetermined across 17 heterogeneous sections; and pinning width alone
> does not make character counts environment-independent because color adds ANSI.
>
> **Rev 4 (2026-07-24)** — third review round. The rev-3 `health` section classification was
> factually wrong (`entity_identity` and `cross_paper_evidence` carry `severity`;
> `cross_paper_evidence` has no `counts_as_issue`; `prose_epistemics` carries both), and the
> premise that a severity default shrinks `health` was refuted by the data: all 361 of
> natural-systems' `validation` findings are warnings. Reclassified from the TypedDicts,
> `--severity` defined as a threshold defaulting to `warn`, and budget enforcement moved to
> per-section row caps.

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

**Two phases, and the split is load-bearing.** Budgeting happens in two stages that must not be
collapsed:

1. **Projection — semantic, before serialization, format-aware.** Decides *what* to include,
   knows how many items it dropped, and produces a payload that is still structurally valid.
2. **Sink — routing and measurement, after rendering.** Chooses stdout or file, measures the
   final size, and enforces the ceiling as a backstop.

A post-render sink holds only characters. It cannot count omitted rows, cannot insert
`truncation` metadata into an already-serialized document, and cannot cut without risking a
severed table box or a split ANSI escape. **Semantic truncation therefore never happens in the
sink.** If a projected payload still exceeds the ceiling, the sink raises — that is a budget
misconfiguration to fix, not something to trim blindly.

**Both phases are scoped to the whole command invocation, not to one emitter call.** A single
`BoundedSink` is constructed per invocation and threaded through both `emit` and
`emit_query_rows`, so `health` — which renders 21 tables through `emit`
(`graph/health_cli.py:75–436`) — gets **one command-total ceiling** rather than 21 independent
per-section ones. Projection likewise runs once over the whole report, not once per section.

**Budgets live in one registry module**, keyed by command path: a single SSOT rather than
constants scattered across call sites. The registry is also what the completeness guard below
walks.

**Projections, per payload shape.**

| Shape | Projection |
|---|---|
| Rows (`tasks list`) | Row projection: keep the first N by the command's sort, record `omitted`/`total`. |
| Heterogeneous report (`health`) | An explicit `health` projection — see below. Generic row-dropping cannot work across 17 differently-shaped sections. |
| Versioned document (`entities inventory`) | **No projection exists. Refuse.** A partial document under a `schema_version: "2"` contract would be a lie about the contract; past budget the command exits non-zero telling the caller to pass `--output`. |

Any future payload shape without a registered projection refuses rather than degrading — the
fail-early rule, applied to output.

**Emitters keep their payload shapes.** `health` keeps its heterogeneous report and
`entities inventory` keeps its versioned document. Projection narrows content within a shape;
it never flattens one shape into another.

**Truncation is visible in every format.** Text output ends with a footer naming what was
withheld and the exact command to obtain all of it. JSON carries a `truncation` object
(`{omitted, total, complete_via}`) **inside the payload** — `emit`'s docstring forbids
diagnostics on the JSON branch, and a consumer parsing stdout must be able to detect truncation
from the document itself. This is only possible because projection runs *before* serialization.

**Counting semantics.** The budget counts **ANSI-stripped visible characters**, at a pinned
console width.

- *Width* is pinned rather than inherited from Rich's non-TTY default so identical data costs
  identical budget. This is for reproducible accounting, not size reduction — width was
  measured at 8% on `tasks list`.
- *Color* is excluded from the count deliberately. `resolve_color_policy`
  (`styles.py:126`) returns `NEVER` unless `FORCE_COLOR` or `--color` is set, so the
  agent-facing path emits no ANSI at all and visible characters equal emitted characters there.
  Counting visible characters keeps **row selection identical across color modes**, which
  counting raw output would not.
- The stated trade-off: under `--color always` or `FORCE_COLOR`, emitted bytes exceed the
  budget by the ANSI overhead. That is a human at a terminal, not an agent, and the design
  accepts it rather than making budgets color-dependent. A test asserts the non-TTY default
  policy is `NEVER`, since that assumption is what makes the trade-off safe.

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
vs ~41k tokens).

**The `health` projection, specified.** The rev-3 classification was wrong on three sections
and rested on a false premise. Corrected from the TypedDicts:

| Signal | Sections |
|---|---|
| `severity` | `validation` (`validate.py`), `schema_invalid` (`health.py:43`, always `"error"`), `dataset_anomalies`, `entity_identity` (`entity_identity.py:13`), `cross_paper_evidence.findings` (`cross_paper_evidence.py:15`) |
| `severity` **and** `counts_as_issue` | `prose_epistemics.findings` (`prose_epistemics.py:41`) |
| `counts_as_issue` only | `managed_artifacts` (`project_artifacts/health_integration.py:20`) |
| neither | `agent_context`, `archive_lag`, `identity_policy`, `invalid_entity_aspects`, `layered_claims`, `legacy_task_type`, `lingering_tags_lines`, `tooling_scaffold`, `unregistered_ref_kinds`, `unresolved_refs` |

**`counts_as_issue` is issue-count membership, not severity.** The two are orthogonal:
`prose_epistemics` emits `severity: "warning"` with `counts_as_issue: True`
(`prose_epistemics.py:~62`). It determines whether a row feeds `total_issues`
(`health.py:370`) and is **never** used as a display filter. Rev 3 treated it as "their
severity signal," which would have hidden `cross_paper_evidence` errors (that section has no
`counts_as_issue` at all) and shown `prose_epistemics` warnings under an error-only default.

**`--severity` is a threshold, not an equality filter.** `error` = errors only; `warn` =
warnings **and** errors; `all` = everything including info. Threshold semantics are what make
`warn` safe — an equality filter would hide errors while displaying warnings.

**Severity does not solve the size problem, and the default reflects that.** All 361 of
natural-systems' `validation` findings are `severity: "warning"`, with `total_issues` = 366.
So `--severity error` would display essentially nothing while the report announced 366 issues —
the exact "claims issues exist without showing them" failure. Rev 3's claim that a severity
default shrinks the JSON path was therefore wrong for the project that motivated this program.

Consequently:

- **Default is `warn`** (warnings and errors), not `error`. An error-only default blanks the
  report on a project whose findings are all warnings.
- **Budget enforcement comes from per-section row caps in the projection**, applied after the
  severity threshold and independent of it. Severity is a user-facing lens; row caps are the
  mechanism that actually bounds output. This is what shrinks both the table and the JSON path
  (163,343 chars today).
- **Sections with neither signal are always shown in full.** They are small and are not the
  cost problem.
- **`unwired_checks` is never filtered, at any severity or row cap.** `health.py:60`
  deliberately keeps unwired checks out of `total_issues` so a report containing one cannot
  claim the project is clean. Hiding them would defeat that.

**`total_issues` keeps meaning *total*, not *displayed*.** It is the clean-report gate
(`health_cli.py:158`) and is summed across all sections (`health.py:357`). Redefining it as a
displayed count would let `health` announce "Project is clean" while findings were merely
filtered out — the same class of defect as a silent read truncation. The projection adds a
sibling `displayed_issues` plus per-section `omitted` counts, and the text footer reads:

```
showing 40 of 361 validation findings (severity: warn, cap: 40/section)
  321 hidden — science health --severity all --output health.json
```

So the invariant is: `total_issues` answers "is this project clean?", `displayed_issues`
answers "how much am I looking at?", and the two never silently diverge.

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
- Projection-before-serialization: a truncated table is never cut mid-box and a truncated JSON
  document always parses.
- Unregistered payload shapes refuse rather than degrade.
- Versioned-document refusal: `entities inventory` past budget exits non-zero rather than
  emitting a partial `schema_version: "2"` document.
- Sink backstop: a projected payload that still exceeds the ceiling raises rather than being
  blindly trimmed.
- `--output` completeness: the file sink is never truncated, for every budgeted command.
- `health` projection: `--severity` is a threshold (`warn` retains errors as well as warnings,
  never errors-only-hidden); `counts_as_issue` never filters display, so a
  `severity: warning, counts_as_issue: True` prose finding is hidden at `--severity error` and a
  `cross_paper_evidence` error is retained despite having no `counts_as_issue` field; sections
  with neither signal are shown in full; `unwired_checks` survives every severity level and row
  cap; per-section row caps bound output independently of severity; `total_issues` stays the
  unfiltered clean-report gate while `displayed_issues` tracks what was shown; a filtered report
  never prints "Project is clean".
- Regression fixture reproducing natural-systems' shape (all-warning `validation`,
  `total_issues` > 0): the default view must not be empty, and must not claim clean.
- Width determinism: identical data costs identical budget across `COLUMNS` values.
- Color independence: row selection is identical under `NO_COLOR`, default, and
  `FORCE_COLOR=1`; the non-TTY default color policy is `NEVER`.
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
