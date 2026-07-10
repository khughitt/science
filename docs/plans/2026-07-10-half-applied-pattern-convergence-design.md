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

## Phase 0 (pre-phase) — Dead-code investigation → **deletes nothing**

**Retracted.** This phase originally proposed deleting `plan_gate.py` (196 lines)
and `synthesis_payload.py` (324) as "confirmed dead code," on the strength of zero
production importers. Investigation on 2026-07-10 (git `-S` history + design-doc +
registry trace) found that inference wrong: *no importer* does not mean *dead* for
a tested, documented feature — it can equally mean *built ahead of its wiring*, and
here it does.

- `plan_gate.py` is the implemented planning-gate of reproducibility-gate-v1
  (`docs/plans/2026-07-01-reproducibility-gate-v1-design.md`), whose approved scope
  *deliberately defers* CLI surfacing. It is exercised by ~450 lines of tests
  including `test_workflow_registration_e2e.py`, which drives a real `dataset
  register-run` flow. **Keep.**
- `synthesis_payload.py` is a typed registry for a synthesis family the code marks
  as future work (`graph/sources.py:247` "intentionally refuses" it "in a later
  release"). Orphaned but ambiguous, not confirmed scrap. Deleting ambiguous
  built-and-tested code in a simplification pass is the wrong trade. **Keep unless
  the owner confirms abandonment.**

`codex_skills.py` — flagged as looking identical — is live via
`scripts/generate_codex_skills.py:10` and was never a candidate.

**Net effect: no deletion, no ledger, no code change.** The phase survives only as
the record that the deletion was considered and rejected on evidence, so a future
reader does not re-propose it. Everything below (Phase 1 onward) is unaffected —
the convergence work never depended on these removals.

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
`tests/graph/test_durable_write_boundary.py`. It must **not** key on the call
argument mentioning `science.yaml` — that idiom is already evaded in the tree:
`graph/io.py:353-357` binds `config_path = project_root / "science.yaml"` and then
calls `yaml.safe_load(config_path.read_text(...))`, whose argument names neither
the file nor the string. A call-argument matcher passes it straight through.

Two structural rules instead:

1. **The string is the tell.** Outside `data_root.py` / `project_config.py` /
   `science_model/frontmatter.py`, no module may contain the string literal
   `"science.yaml"` at all. This catches the aliased read (`io.py:353`), the raw
   builds, and the walk-up loops in one rule, because every one of them must name
   the file somewhere. **Two sanctioned forms absorb every real use** (the
   implementation plan found ~43 sites split between them): a *filename constant*
   `PROJECT_CONFIG_FILENAME = "science.yaml"` for relative-token uses (git args,
   file-inventory tuples, membership tests, display paths — ~10 sites where an
   absolute path would be the wrong type), and `project_config_path(root) = root /
   PROJECT_CONFIG_FILENAME` for the path builds (~33 sites). The literal itself
   appears only in the constant's definition. This corrects an over-simplification
   in an earlier draft of this rule, which assumed every use was a path build and
   would have had no correct target for the token sites.
2. **The loader is the tell.** No module outside those three may call
   `yaml.safe_load`/`yaml.load` on the result of a `.read_text()` whose receiver
   was assigned from an expression containing `"science.yaml"` — a one-hop
   backstop for any future config read that obtains the path from elsewhere.

Rule 1 does the real work and is trivially checkable (a literal-string scan, not
dataflow). Rule 2 exists only because rule 1 could in principle be dodged by
importing the path from a fourth module; state that limit in the docstring rather
than implying completeness.

---

## Phase 2 — One frontmatter reader, one frontmatter writer

This is the highest-value phase and the only one that adds a genuinely missing
abstraction.

**Current — reader.** `science_model.frontmatter.parse_frontmatter(path) ->
tuple[dict, str] | None` is canonical (12 importing modules). But
`markdown_utils.py:205` defines `parse_frontmatter(path) -> tuple[dict, int]` —
same name, *different return type* (body text vs. body start line). An author who
imports the wrong one gets a type error at best and a silent bug at worst. Beyond
the two canonical modules, 28 non-test modules touch the `"---"`/`"---\n"`
delimiter directly across 70 sites (see the writer subsection for how that count
was corrected upward from an earlier "16 / 31").

**Current — writer.** No canonical form exists, and **the set is larger than any
hand-list this doc drafted.** Three successive counts here said six, then seven,
then eight emitters — each undercounted, because each keyed on one delimiter
spelling (`"---"`) and missed the `"---\n"` form. Enumerated structurally instead —
*a module containing `yaml.safe_dump` adjacent to a `"---"` or `"---\n"` literal* —
there are **12 emitting modules** (and more functions, since `entities.py` alone
has two):

```
entities.py · datasets_identity.py · datasets_catalog.py · datasets_register.py
commons/promote.py · commons/reference_graph_promotion.py · commons/dataset_lifecycle.py
dag/workbench_apply.py · annotation/source_text.py · graph/decision_log.py
cli.py · model/templates.py
```

Do **not** migrate from this list. Regenerate the set with that structural query at
implementation time and migrate whatever it returns; a list transcribed into a plan
goes stale and re-undercounts. The list above is the count, not the worklist.

`model/templates.py` is the one to migrate **first**: it lives *inside*
`science_model`, the same package the canonical `render_frontmatter` will, and its
`Renderer` emits the most general case (arbitrary templated entities). If
`render_frontmatter` cannot serve it, the helper is underspecified. It is a
first-class caller, never an exclusion to carve around.

Separately, the delimiter is touched — read or write — by **28 non-test modules
across 70 sites** (both spellings; the umbrella's earlier "16 / 31" counted only
`"---"`). Every one spot-checked is real frontmatter handling, not markdown rules.

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

The emitters become one-line delegations. `entities.py` keeps
`render_entity_text` as its public name but implements it over
`render_frontmatter` — it adds entity-specific field ordering, which is policy
and belongs in `science_tool`.

**Migration risk — the real one.** Byte-for-byte equivalence across a dozen emitters
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
  `parse_frontmatter`. Assert that each legacy emitter in the structurally-derived
  set, given that input, produces output byte-identical to
  `render_frontmatter(fields, body)`.
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
read-modify-write. Audit the emitters' call sites for that pattern before
choosing; `dag/workbench_apply.py:251` and `commons/promote.py:2907` are the
likely cases.

**Guard.** Extend the Phase 1 AST guard: fail if any module outside
`science_model/frontmatter.py` and `markdown_utils.py` contains the string
literal `"---"` in a context adjacent to `yaml.safe_dump`, or defines a function
whose name matches `_?render_(entity|frontmatter)`. Note the allowlist is exactly
those two modules: after migration `model/templates.py`'s `Renderer` calls
`render_frontmatter` and no longer emits the sandwich itself, so it is **not**
allowlisted — if the guard would still flag it, the migration is incomplete. That
is the guard doing its job, not a carve-out to add.

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
