# Half-Applied Pattern Convergence — Design

Date: 2026-07-10
Status: proposed
Umbrella: [Toolkit Convergence](2026-07-10-toolkit-convergence-umbrella.md)

Decision-ready. Each phase names its target layout, its migration, and its guard.

## Goal

Collapse five duplicated concerns onto the canonical form that already exists for
each, and constrain each one so it cannot decay again. Concept-preserving: no
entity, relation, command name, or output schema changes.

## Non-goals

- No new CLI commands, no renamed flags. (`docs/conventions/cli-behavior.md`
  governs those and is untouched.)
- No behavior change to any command's stdout under `--format json`. The JSON
  payloads are a public automation contract; snapshot tests must pass unchanged.
- Not a `Plan`/`Apply` base class. See "Scoped-down: plan/apply" below.

## Sequencing rationale

Phases are ordered so each one *shrinks the work of the next*. Specifically, the
CLI extraction (Phase 4) is deliberately last among the large moves: once root
resolution, frontmatter I/O, and output formatting are canonical, the 22 inline
command groups become thin delegators, and their extraction is a near-pure code
move reviewable as such. Extracting first would relocate ~4,200 lines and then
require touching all of them again.

---

## Phase 0 (pre-phase) — Delete dead code

**This is the one phase with no guard**, and it is numbered 0 to say so. The
umbrella's rule — *a phase that migrates call sites without landing its guard is
not done* — governs exactly that: phases moving call sites onto a canonical form,
because those can decay. A deletion
cannot decay: there is no call site to regrow, and re-adding a deleted module
would be a deliberate act, not a bypass. What it *can* do is get resurrected from
the design docs that still describe the features as planned, so the ledger below
substitutes for a guard.

**Change.** Remove `src/science_tool/plan_gate.py` (196 lines),
`src/science_tool/synthesis_payload.py` (324), and their test files.

**Evidence.** Zero importers in `src/`, `model/`, or `scripts/`. Both are
referenced only by design docs under `docs/plans/` and by their own tests.

**Care.** `codex_skills.py` presents identically (no `src/` importer) but is live
via `scripts/generate_codex_skills.py:10`. Do not remove it. Before deleting
either target, re-run the check rather than trusting this doc:

```bash
rg -n 'plan_gate|synthesis_payload' src/ model/ ../scripts/ ../commands/ ../skills/
```

**Ledger, in place of a guard.** Add the two removed features to
`docs/plans/2026-07-08-current-frontier.md` under an explicit *Abandoned* heading,
naming the design docs that describe them, so those docs are not read as an open
backlog by the next person who greps `docs/plans/`. This is the phase's
deliverable and its acceptance criterion.

---

## Phase 1 — One project-root resolver, one config accessor

**Current.** Five root-finders: `data_root.discover_project_root:16` (the
intended one, 1 caller), `commons/config.py:251 resolve_project_root`,
`commons/config.py:273 resolve_project_by_id`, `graph/io.py:386
project_root_from_graph_path`, plus inline walk-up loops at `feedback.py:535` and
`science_model/frontmatter.py:359`. 44 files reference `science.yaml`; six load
it with a raw `yaml.safe_load` outside the typed loader
(`project_package/serialize.py:92`, `labnote_export.py:578`, `dag/paths.py:26`,
`project_artifacts/pin.py:25`, `cli.py:437`, `graph/io.py:354`).

**Target.** `science_tool/data_root.py` becomes the single entry point:

```python
def discover_project_root(start: Path | None = None) -> Path: ...   # existing, unchanged
def project_config_path(root: Path) -> Path: ...                    # new: root / "science.yaml"
```

`project_config.load_project_config(root)` stays the sole typed reader (15 call
sites already). The two *registry*-keyed functions in `commons/config.py` are
**not** merged — they resolve a root from a project *name*, a different question;
they are renamed `registry_root_for_name` / `registry_root_for_id` to stop them
reading as competing filesystem walk-ups. `graph/io.py:386` is likewise a
different question (root from a graph path) and stays.

The inline walk-ups at `feedback.py:535` and `science_model/frontmatter.py:359`
are replaced by `discover_project_root`. The `science_model` one is the awkward
case: `science_model` must not import `science_tool`. Resolve by moving the
walk-up *into* `science_model` (it is schema-adjacent — it locates the file the
schema describes) and having `science_tool.data_root` re-export it. That inverts
the dependency correctly and is the only import-direction change in this phase.

The six raw `yaml.safe_load` sites migrate to `load_project_config`. Where they
read a sub-key the typed config does not model, extend the Pydantic model rather
than keep the raw read — that is the point.

**Guard.** `tests/test_project_root_boundary.py`, an AST guard in the shape of
`tests/graph/test_durable_write_boundary.py`: fail if any module outside
`data_root.py` / `project_config.py` / `science_model/frontmatter.py` contains a
`yaml.safe_load` whose argument path mentions `science.yaml`, or a `while` loop
testing `(_ / "science.yaml").exists()`.

---

## Phase 2 — One frontmatter reader, one frontmatter writer

This is the highest-value phase and the only one that adds a genuinely missing
abstraction.

**Current — reader.** `science_model.frontmatter.parse_frontmatter(path) ->
tuple[dict, str] | None` is canonical (12 importing modules). But
`markdown_utils.py:205` defines `parse_frontmatter(path) -> tuple[dict, int]` —
same name, *different return type* (body text vs. body start line). An author who
imports the wrong one gets a type error at best and a silent bug at worst. Beyond
the two canonical modules, 16 non-test modules touch `"---"` directly across 31
sites.

**Current — writer.** No canonical form exists. Six re-emitters:
`entities.py:405 render_entity_text`, `entities.py:1356 _render_markdown`,
`datasets_identity.py:31 _render_entity`, `datasets_catalog.py:192
_render_entity`, `commons/promote.py:3051 _render_frontmatter`,
`dag/workbench_apply.py:260 _render_entity_text_from_frontmatter`,
`commons/reference_graph_promotion.py:121 _render_entity`.

**Target.** `science_model/frontmatter.py` owns both directions:

```python
def parse_frontmatter(path: Path) -> tuple[dict, str] | None: ...   # unchanged
def render_frontmatter(fields: Mapping[str, Any], body: str) -> str: ...  # new, canonical
def write_entity_file(path: Path, fields: Mapping, body: str) -> None: ...  # new, atomic
```

`render_frontmatter` must reproduce today's emission byte-for-byte:
`yaml.safe_dump(sort_keys=False, allow_unicode=True)`, the force-quoting rules
currently in `promote.py:3051`, and a trailing newline. `write_entity_file`
absorbs the `os.replace` atomic-write dance now duplicated in
`entities.py:1368 _atomic_replace_text` and `datasets_identity.py:41`.

Rename `markdown_utils.parse_frontmatter` → `frontmatter_span(path) ->
tuple[dict, int]`, which says what it returns. It has a legitimate distinct
purpose (line-accurate lint anchoring); it just must not share a name.

The six re-emitters become one-line delegations. `entities.py` keeps
`render_entity_text` as its public name but implements it over
`render_frontmatter` — it adds entity-specific field ordering, which is policy
and belongs in `science_tool`.

**Migration risk — the real one.** Byte-for-byte equivalence across six emitters
that today differ subtly (quoting, key order, trailing newlines). Do not trust
review; characterize before migrating.

**The obvious test does not work.** An earlier draft of this doc asserted
`render_frontmatter(*parse_frontmatter(f)) == f.read_text()` over a corpus. That
is unsatisfiable with `parse_frontmatter` "unchanged": it ends with
`body = parts[2].strip()` (`science_model/frontmatter.py:52`). The parser is
**lossy by design** — it discards leading/trailing body whitespace — so no writer
can reconstruct the original bytes from its output. The test would fail on nearly
every file for a reason that has nothing to do with emitter divergence, and the
temptation would be to weaken it until it passed.

Two tests, each measuring the thing it names:

- **Test A — emitter equivalence (the actual risk).** For every entity file in
  `meta/entities/` and `fixtures/`, harvest `(fields, body)` via
  `parse_frontmatter`. Assert that each of the six legacy emitters, given that
  input, produces output byte-identical to `render_frontmatter(fields, body)`.
  A failure is a *real* divergence between two emitters — a quoting or key-order
  difference that a caller migration would silently impose on a project's source
  of truth. Fix it deliberately, or exclude that emitter with a named reason.
  This test needs no round-trip and is unaffected by the `.strip()`.

- **Test B — writer idempotence.** `render_frontmatter(*parse_frontmatter(p))`
  applied twice yields a fixed point. This is the property `write_entity_file`
  actually needs: re-writing an already-canonical file must not churn it.

**Consequence for the reader/writer contract.** Because the canonical parser is
lossy, `write_entity_file` is only safe on a file that has *already* been
normalized, or on freshly-constructed content. Do not use the pair as a
read-modify-write primitive on arbitrary user files without first landing a
non-lossy `split_frontmatter(text) -> tuple[str, str]` that preserves the body
verbatim. That is a small addition and belongs in this phase if any caller does
read-modify-write. Audit the six emitters' call sites for that pattern before
choosing; `dag/workbench_apply.py:251` and `commons/promote.py:2907` are the
likely cases.

**Guard.** Extend the Phase 1 AST guard: fail if any module outside
`science_model/frontmatter.py` and `markdown_utils.py` contains the string
literal `"---"` in a context adjacent to `yaml.safe_dump`, or defines a function
whose name matches `_?render_(entity|frontmatter)`.

---

## Phase 3 — One output emitter

**Current.** `output.py` (47 lines) exports `OUTPUT_FORMATS` and
`emit_query_rows` (55 call sites — the tabular-query path is genuinely shared).
Everything else branches inline: 89 `== "json"` sites across 23 files, 42
`json.dumps` calls and 37 `Table(` constructions in `cli.py` alone.

**Target.** Extend `output.py` with the non-tabular case, which is why authors
bypass it:

```python
def emit(*, output_format: str, payload: Mapping[str, Any], render_text: Callable[[], None]) -> None:
    """Emit `payload` as JSON, or invoke `render_text` for human output."""
```

That is the entire abstraction. It captures the ubiquitous shape
`if output_format == "json": echo(json.dumps(payload)); return` followed by table
construction, and it makes the JSON payload the *declared* thing rather than an
incidental one. `emit_query_rows` is reimplemented on top of `emit`.

**Deliberately not solved.** A generic table DSL. The 37 tables in `cli.py` are
genuinely different; forcing them through one renderer is the kind of abstraction
this doc exists to avoid. They move with their command groups in Phase 4 and stay
hand-written.

**Contract.** `--format json` stdout must be byte-identical before and after.
`docs/conventions/cli-behavior.md` requires JSON-only on stdout; `emit` enforces
it by construction (diagnostics cannot reach stdout through it).

**Guard.** `tests/test_output_boundary.py`. Matching the literal
`click.echo(json.dumps(...))` is **not** sufficient — the codebase already evades
it. `cli.py` uses a function-local `import json as _json` in seven places and then
calls `click.echo(_json.dumps(...))` (`cli.py:4642,4653,4679`; also `:5064,5077`,
`:5269,5287`, `:5354,5373`). A guard keyed to the name `json` would pass over the
very sites this phase exists to migrate.

A blanket ban on `json.dumps` is equally wrong: it has 159 call sites, and most
are legitimate — writing artifact files (`archive.py:87`,
`datasets_identity.py:204`), building stable hashes (`openalex.py:87`), producing
strings that never reach stdout. The concern is *emission*, not serialization.

**Rule.** Outside `output.py`, no function may contain both a call to
`click.echo`/`print` and a call to any attribute named `dumps`.

Keying on the *attribute* name rather than the module binding makes it alias-blind:
`json.dumps`, `_json.dumps`, and any future alias all match. Scoping to the
enclosing function permits the file-writing and hashing uses (which live in
functions with no `echo`) while catching the one-hop assignment form
(`payload = _json.dumps(...)` … `click.echo(payload)`) that a nested-call matcher
would miss.

**Known gap, stated rather than hidden.** A helper that returns a JSON string,
echoed by a different function, evades this. So does `sys.stdout.write`. That is
the same class of limit the durable-write guard documents candidly in its own
docstring — a ratchet against accidental regrowth, not a sandbox. Add
`sys.stdout.write` to the banned set; leave the cross-function case uncovered and
say so in the test's docstring rather than implying a completeness the check does
not have.

---

## Phase 4 — Finish the CLI extraction

**Current.** `cli.py` is 7,386 lines. 24 groups are already registered from their
own modules (`cli.py:244-267`), exactly the target pattern —
`from science_tool.annotation.cli import annotate_group` then
`main.add_command(annotate_group)`. 22 groups remain inline. `annotation/cli.py`
(2,701 lines) and `commons/cli.py` (1,338) prove domain CLIs of any size live
fine outside the root file.

**Target.** Every inline `@main.group` moves to `science_tool/<domain>/cli.py`
exposing a `<domain>_group`, registered with one `add_command` line. Order by
size, largest first, one commit each:

| Group | Lines | Destination |
|---|---|---|
| `benchmark` | 1,250 | `benchmark/cli.py` |
| `graph` | 1,166 | `graph/cli.py` |
| `tasks` | 691 | `tasks_cli.py` |
| `dataset` | 629 | `datasets/cli.py` (joins the existing `dataset_identity_group`) |
| `health` | 435 | `graph/health_cli.py` |
| `entity` | 364 | `entities_cli.py` |
| `explore-ideas` | 339 | `explore_ideas_cli.py` |
| `inquiry`, `datasets`, `project`, `entities`, `questions`, `sync`, `belief`, `evidence-lines`, `bib`, `hypotheses`, `propositions`, `discussions`, `interpretations`, `paper` | ~1,600 combined | one module each |

**Note the `dataset` / `datasets` collision.** Two sibling groups exist
(`dataset` 629 lines, `datasets` 385). They are not synonyms — `dataset` is
entity lifecycle, `datasets` is catalog/discovery — but the names do not say so.
This phase does **not** rename them (that is a CLI-contract change, out of
scope); it records the collision as a follow-up and places them in modules whose
names disambiguate.

**Business logic that must move, not relocate.** Five commands hold domain logic
in the CLI layer; extracting them verbatim would enshrine that. Each gets its
logic pushed down as part of its commit:

- `health_command` (`cli.py:4632-5025`) recomputes the aggregate issue tally
  inline — `layered_claim_issue_count` (:4696), a ~20-term `total_issues` sum
  (:4739-4759), `archive_lag_total` (:4732). That rollup belongs in
  `build_health_report`, which should return it.
- `dataset_prioritize` (`cli.py:6868`) reaches into private store internals
  `graph.store.dataset._load_dataset` and `graph.store.identity._graph_uri`
  (:6889-6890). Those need public accessors before the move.
- `graph_build` (`cli.py:1606`) calls `ensure_registered` as a side effect
  (:1611-1618) — registration policy embedded in a command.
- The benchmark review-file cluster (`cli.py:6316-6458`) computes output paths and
  serializes review artifacts; that is domain output, belongs in
  `benchmark_opportunities`.
- `_create_typed_entity` / `_show_typed_entity` / `_list_typed_entities`
  (`cli.py:1414-1484`) are an entity service layer for five kinds, living in the
  CLI. Move to `science_tool.entities`.

The 95 `raise click.ClickException(str(exc))` wrappers stay as-is. They are the
correct CLI-layer job (domain error → exit code) and a decorator would obscure it.

**Guard.** `tests/test_cli_is_registration_only.py`: parse `cli.py` and fail if
it contains any `@main.group`/`@main.command` whose body exceeds a small line
budget, or if the module exceeds ~400 lines. Modeled on
`tests/test_store_package_structure.py`.

---

## Phase 5 — Split `health.py` into a checks package

**Current.** `graph/health.py` (1,976 lines) *already has the right seam*: a
`HealthCheck` dataclass (`:392`, fields `name/description/requires_sources/run`),
a `HEALTH_CHECKS` tuple of 16 entries (`:1877-1976`), and `_select_health_checks`
(`:593`) driving `--fast`/`--check`/`--skip`. Dispatch is pluggable; the 16 check
bodies just all live in the same file. `check_dataset_anomalies` alone spans
`:1356-1714`.

**Target.** `graph/health_checks/`, one module per check, mirroring
`validate/checks/` (50 files). `HEALTH_CHECKS` is assembled by explicit import in
`health_checks/__init__.py` — *not* by filesystem discovery, which would make
ordering implicit. `health.py` retains only `HealthContext`, the registry,
`_run_health_checks`, `_select_health_checks`, and report assembly (~250 lines).
The TypedDict result types (`:283-578`) move with their checks.

**Why it is safe.** No check calls another; all state routes through
`HealthContext`. The move is mechanical.

**Guard.** `tests/test_health_checks_package.py`: assert every module under
`health_checks/` contributes exactly one `HealthCheck` to `HEALTH_CHECKS`, and
that `health.py` defines no `HealthCheck` bodies itself.

---

## Phase 6 — Decompose `commons/promote.py`

**Current.** 3,543 lines mixing all four concerns: domain rules (eligibility,
mixin stacking, `:177-314`), an *interactive click prompt* (`prompt_resolve`
`:542-610`), a git/subprocess transaction engine (`:1251-1871`, `:3192-3543`,
~27% of the file), YAML renderers (`:2906-3110`, `:3248-3408`), and a
dataset/datapackage verification subsystem (`:2025-2905`) threaded through the
generic pipeline via `dataset`-kind conditionals inside `plan_promote`
(`:981-1020`). It imports `click` (`:28`) into a domain module.

**Target.** Four extractions, in this order:

1. `commons/promote_render.py` — the frontmatter/body/canonical/overlay/audit-yaml
   renderers. Pure string builders, no callbacks. After Phase 2 these delegate to
   `science_model.frontmatter.render_frontmatter`.
2. `commons/git.py` — `_git` (`:3192`), the restore/rollback helpers, and the
   `_commons_is_clean`/`_repo_is_idle` guards. A transaction layer.
3. `commons/promote_dataset.py` — the dataset/datapackage subsystem. It shares no
   logic with paper/theme promotion; it is a second module inlined into the first.
4. Move `prompt_resolve` to `commons/cli.py`. This is the load-bearing one: it
   removes `click` from the domain module's imports.

`apply_promote` (`:1482-1871`, a 390-line transaction orchestrator) stays where it
is. It touches every cluster and is the hardest target; after (1)-(4) it becomes a
readable sequence of calls into named layers, which is enough.

**Guard.** `tests/test_commons_domain_purity.py`: fail if any module under
`commons/` other than `cli.py` imports `click`.

---

## Scoped-down: plan/apply

The audit found ten independent `*Plan` + `*Apply`/`*Report` dataclass families
with parallel builder/apply signatures (`explore_ideas.py:48,60,77`,
`annotation/proposition_reconciliation_plan.py:56`, `dag/workbench_apply.py:105`,
`commons/promote.py:440`, `entities.py:318`, `tasks_archive.py:60`,
`annotation/synthesize.py:289`, `annotation/prose_promotion_batch.py:43`,
`annotation/proposition_reconciliation_decisions.py:94`). Only one pair shares
code, by subclassing (`proposition_resynthesis_apply.py:44`).

**Decision: do not introduce a shared `Plan` protocol or base class.** The
*shape* rhymes but the *edits* are heterogeneous — a planned entity removal, a
planned RDF membership rewrite, and a planned git-backed commons promotion have
nothing substantive in common. A unifying base class would be abstraction for the
sake of a naming coincidence, and would couple ten features that currently change
independently.

**Do extract two narrow things**, each of which is genuinely shared:

- A common `ApplyReport` result shape (counts of written / skipped / failed, plus
  a list of touched paths) so `--format json` output is consistent across the ten
  features. Today each invents its own keys.
- A `@dry_run_option` click decorator encoding the `--apply` / check-only
  contract that `docs/conventions/cli-behavior.md` already specifies in prose.

This is recorded as a decision, not an omission. Revisit only if a third feature
needs to *consume* another's plan.

---

## Deferred: `benchmark_opportunities.py`

4,239 lines, and the audit's verdict is that it is **not** a cohesion problem: a
pure functional core, ~3% filesystem I/O (`load_opportunity_datasets:1059`,
`load_project_entities:1214`), zero rendering, no `click`. All five public entry
points fan in through `_opportunity_analysis:3848`.

If it is split, the seams are: a `types.py` (`:237-896`, ~650 lines of pure
dataclass/TypedDict declarations, zero logic) and a `fallback_triage.py` holding
the ~13 private symbols that `tests/test_benchmark_opportunities.py` already
imports white-box (`_fallback_display_group_for_gap_candidate`,
`_benchmark_test_triage_bucket`, `_dedupe_benchmark_test_rows`, …). Those
internals are white-box-tested precisely because they are pure, branchy
classification that the report facade makes awkward to reach — which is the
signal they want to be a submodule with its own public API.

Scheduled last, and **may be dropped**. Splitting a healthy module to hit a line
count is not a goal.

---

## Test strategy

Each phase is behavior-preserving, so the existing suite is the primary oracle:

```bash
cd science && uv run --frozen pytest
cd science/model && uv run --frozen pytest
cd science && uv run ruff check && uv run pyright
```

Two additions carry the real risk:

- **Phase 2** requires the round-trip characterization test described above,
  landed *before* any caller migrates. It is the only phase where a silent
  regression is plausible (a quoting change in a written entity file would pass
  every existing test and corrupt a project's source of truth).
- **Phases 3 and 4** must not change `--format json` stdout. Run the snapshot
  suite (`-m snapshot`, excluded by default) at each commit, not just at the end.

Every phase from 1 onward adds exactly one guard test; Phase 0 is a deletion and
ships a ledger entry instead (see its heading). The guards are the deliverable as
much as the migrations are: a phase that moves call sites without landing its
guard has bought a temporary improvement at the cost of a permanent one.

**Write each guard last, against the migrated tree.** A guard authored from this
document rather than from the code will out-scope its migration and land red —
Model-track Phase 2 originally made exactly that mistake, banning all
function-local `graph/` imports while migrating only one of the four.

## Order and independence

Phases 0-3 are strictly ordered (each shrinks the next). Phase 4 depends on 1-3.
Phases 5 and 6 depend only on Phase 2. Phase 6 is independent of Phase 4.
