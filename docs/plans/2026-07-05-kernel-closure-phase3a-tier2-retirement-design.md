# Kernel Closure Phase 3a: Tier 2 (clean-source) + Tier 3 Writer Retirement

Date: 2026-07-05

Parent design: [`2026-07-05-kernel-closure-writer-boundary-design.md`](2026-07-05-kernel-closure-writer-boundary-design.md)
(Section 8, Phase 3). Predecessor: Phase 1 —
[`2026-07-05-kernel-closure-phase1-tier1-guard-plan.md`](2026-07-05-kernel-closure-phase1-tier1-guard-plan.md).

## 1. Context

Phase 1 landed the durable-writer boundary guard
(`tests/graph/test_durable_write_boundary.py`) and retired the 9 orphaned Tier 1
writers. The guard freezes the boundary at a ledger of **18 deferred writers**
(`EXPECTED_DEFERRED_WRITERS`): 15 Tier-2 `graph add *` mutators plus 3 Tier-3
writers (`migrate_addresses_direction`, `import_snapshot`, `stamp_revision`).

The parent design assumed Phase 3 could "retire the 15 mutators after confirming
each kind has a source-authoring path." A code audit found that assumption holds
for only **11 of the 15**. Four kinds have no clean source-authoring path and
require genuine per-kind capability decisions (add a source form vs. retire the
capability). Bundling those decisions with the mechanical retirement of the
clean 11 would couple a large, behavior-neutral test migration to unresolved
design calls on legacy constructs.

This phase (3a) therefore retires only what has a confirmed source path; the four
hard kinds are deferred to Phase 3b.

## 2. Goal

Retire the 11 Tier-2 mutators and all 3 Tier-3 writers, moving their durable
capability entirely onto the source-declaration → `science graph build` path.
Shrink the guard ledger from 18 to exactly the 4 deferred writers.

**Important correction (see §5.1 audit).** These mutators are *not* a
byte-identical alternative to the compiler. Most emit graph predicates the
compiler cannot produce from any authored source (structured proposition S-P-O,
concept `concept_type`/`skos:note`/arbitrary properties, observation
`metric`/`value`, finding `groundedBy`/`contains`, the proposition-provenance
payload, evidence `method`/`caveats`). Retiring them therefore makes the
source-built graph *deliberately smaller* — it removes a **redundant parallel
write path**, not an equivalent one. This is safe because a consumer-read audit
found **no production reader's source-built code path depends on any
mutator-exclusive predicate**: the one load-bearing shape (`sci:backedByClaim` +
reified statement behind causal export) is emitted by the *source compiler*
(`inquiry_compile.py`), and every other read-by-production predicate is one the
compiler never emits, so those readers already run as no-ops against real
projects today. The goal is closing the parallel path, not preserving its
byte output.

## 3. Non-Goals

- The four no-clean-source kinds (`add_article`, `add_falsification`,
  `add_story`, `add_paper_entity`) are **out of scope** — deferred to Phase 3b,
  which decides each (add a source form vs. retire the capability and its
  read-only consumers).
- No `sci:Inquiry` consumer repoint (parent Phase 4).
- No compatibility shim. Retirement uses the existing `_retired_mutator` pattern
  (a hard, actionable error), never a silent fallback.
- No belief / materialize-output change. The compiler's emission is unchanged;
  only the retired mutators' *extra* graph shape disappears, and the audit (§5.1)
  confirms nothing source-built reads it.
- **No new source forms.** We do NOT extend `science_model` schemas / the
  compiler to author `observability` on concepts or the proposition-provenance
  payload from source (the mutator-only predicates that *do* have live readers).
  That is deliberately out of scope — a separate future feature, not a
  retirement prerequisite. Those features stay unpopulated for source-built
  projects, exactly as they already are today.

## 4. The `--claim` decision (design rationale)

`add_edge --claim` reifies an arbitrary edge with a `sci:backedByClaim`
statement. Authored relations (`relations:` frontmatter / `relations.yaml`) have
no equivalent field, so retiring `add_edge` raises the question of what happens
to claim-backed edges.

Decision: **retire `--claim` with `add_edge`; add no relations-schema field.**

Rationale (from [`docs/user-guide/big-picture.md`](../user-guide/big-picture.md)):
the epistemic model has one truth-apt, belief-bearing carrier — the
**proposition** (`question → hypothesis → proposition → observation /
evidence-line → belief`). A structured proposition *is* an S-P-O edge that
carries its own claim identity; evidence-lines are what back it. Authored
relations are structural plumbing (`contains`, `produces`, `feedsInto`,
`has_participant`) and are deliberately not truth-apt. A general `claim_refs`
field on relations would stand up a **second, parallel way** to express asserted
edges, competing with the proposition spine — exactly the parallelism
kernel-closure exists to remove. The one legitimate claim-cited edge form in
source, inquiry `flow_edges` with `claim_refs`, already exists in the compiler
(Phase 1). So: relations stay plumbing-only; anything needing a backing claim is
authored as a structured proposition.

## 5. Scope inventory

All mutator paths relative to `science/src/science_tool/`.

### Retire in 3a — 11 Tier-2 (confirmed source path)

| mutator | forward path |
|---|---|
| `add_concept` | `entity create concept` (template added, §7) / edit `entities/concepts/*.md` |
| `add_proposition` | `entity create proposition` / `propositions create` |
| `add_observation` | `entity create observation` (template added, §7) |
| `add_evidence_edge` | `entity create evidence-line` (compiler emits superset: `cito:supports/disputes` + strength/independence) |
| `add_finding` | `entity create finding` |
| `add_interpretation` | `entity create interpretation` |
| `add_discussion` | `entity create discussion` |
| `add_mechanism` | `entity create mechanism` (template added, §7) |
| `add_hypothesis` | `entity create hypothesis` |
| `add_question` | `entity create question` |
| `add_edge` (incl. `--claim`) | `relations:` frontmatter / `relations.yaml` (arbitrary predicate + `graph_layer`); `--claim` retired (§4) |

### Retire in 3a — 3 Tier-3 writers

| writer | CLI | note |
|---|---|---|
| `migrate_addresses_direction` | `graph migrate-addresses --apply` | completed idempotent one-shot; only CLI tests reference it |
| `import_snapshot` | `graph import` | writes raw triples with no backing source — the boundary bypass kernel-closure targets; distill tests migrate off it (§6) |
| `stamp_revision` | `graph stamp-revision` | redundant — the compiler write phase already stamps revisions |

### Deferred to 3b — 4 Tier-2 (no clean source path)

`add_article` (loadable, no home/template; DOIs carried by `paper`),
`add_falsification` (no `Falsification` EntityKind; has read-only consumers),
`add_story` (loadable + template but no `home`), `add_paper_entity` (writes
legacy graph-only `sci:Paper`/`sci:comprises`).

After 3a, `EXPECTED_DEFERRED_WRITERS` = exactly these 4.

## 5.1 Predicate-level audit (what source can and cannot reproduce)

A code audit (write side: `graph/materialize.py`; read side: all of
`src/science_tool/`) established, per mutator-emitted predicate, whether the
compiler emits it from authored source and whether any production consumer reads
it. This is the evidence base for §2's correction and for the §8 delete-vs-migrate
rule.

| mutator-emitted shape | source-emitted? | production reader? | disposition |
|---|---|---|---|
| generic node (`rdf:type`, `prefLabel`, `description`←`summary`, `projectStatus`←`status`, `wasDerivedFrom`←file) | **yes** (`_add_entity`) | yes | **migrate** — author the entity `.md` |
| `mechanism` `hasParticipant`/`hasProposition` | **yes** (`_add_relations`) | yes | **migrate** — author `participants:`/`propositions:` |
| arbitrary edge into a layer (`add_edge` s-p-o + `graph_layer`, incl. `scic:causes`/`confounds` → `graph/causal`) | **yes** (`_add_authored_relation`, honors `graph_layer`) | yes | **migrate** — `relations.yaml` / `relations:` |
| evidence stance/strength/independence | **yes** (evidence-line entity → `cito:supports/disputes` + `_add_evidence_line_metadata`) | yes | **migrate** — author `evidence-lines/*.md` (note: edge *subject* is the evidence-line node, not the source entity) |
| proposition reasoning metadata (`claimLayer`, `identificationStrength`, `proxyDirectness`, `supportsScope`, `independenceGroup`, `evidenceRole`, `measurementModel`, `rivalModelPacket`, `polarity`) | **yes** (`_add_reasoning_metadata`) | yes | **migrate** — author proposition frontmatter |
| `cito:discusses` bridge (proposition `discusses:` / `bridge_between`) | **yes** (membership emitter) | yes | **migrate** |
| `sci:backedByClaim` + reified `rdf:Statement` (edge claim) | **yes** (`inquiry_compile._emit_edge_claims`) | yes (causal export, summary) | **migrate** — inquiry `flow_edges` with `claim_refs` (the §4 sanctioned form) |
| `propSubject`/`propPredicate`/`propObject` | no | **no** (mutator-internal only) | **delete-with-pointer** |
| concept 2nd `rdf:type` (`concept_type`, e.g. `scic:Variable`) | no | summary + validation only (NOT causal export) | **delete-with-pointer** |
| concept `skos:note`/`skos:definition` | no | no (validation set-membership only) | **delete-with-pointer** |
| concept arbitrary props incl. `sci:observability` | no | **causal export** (degrades to latent when absent) | **delete-with-pointer** (unpopulated for source projects today) |
| finding/interp/discussion `groundedBy`/`contains` | no | cross-impact + freshness (no-op on source) | **delete-with-pointer** |
| observation `dataSource`/`metric`/`value`/`uncertainty`/`conditions` | no | **no** | **delete-with-pointer** |
| question `maturity` | no | viz only (no-op on source) | **delete-with-pointer** |
| `schema:text` (prop/hyp/question) | no | many (all fall back to `prefLabel`/`description`) | **delete-with-pointer** |
| proposition-provenance payload — `compositionalStatus`, `platformPattern`, `datasetEffects`, `statisticalSupport`, `mechanisticSupport`, `replicationScope`, `claimStatus`, `bridgeBetween`, `interactionTerm`, `preRegisteredIn`, `evidenceLine` | no | evidence overlay + causal-export *comments* | **delete-with-pointer** |
| evidence `method`/`caveats`, reified evidence statement | no | **no** | **delete-with-pointer** |

**Rule this table encodes:** a test assertion migrates iff the shape it asserts
is source-emitted (top group); an assertion over a mutator-only shape (bottom
group) is deleted with a pointer to where the surviving behavior is proven — it
was testing mutator output that this phase removes, so "preserving" it is
impossible and wrong.

## 6. Retirement mechanics

1. **Generic retirement-error helper.** The existing `_retired_mutator(slug)`
   (`cli.py`) is inquiry-specific — it hard-codes
   `Edit entities/patches/{slug}.md`. Add a generic helper, e.g.
   `_retired_writer(command: str, forward_path: str) -> click.ClickException`,
   that emits `"<command> is retired. <forward_path>, then run `science graph
   build`."`. Each retired command raises it with its own forward-path hint
   (`entity create concept`, `relations:` authoring, etc.). The inquiry-specific
   `_retired_mutator` stays for Phase 1's inquiry commands (or is refactored to
   delegate to `_retired_writer`).
2. **CLI subcommands stay, bodies raise — and obsolete arg validation is
   relaxed.** Each live `graph add <kind>` and the three Tier-3 commands keep
   their names but their bodies `raise _retired_writer(...)`. Click validates
   arguments/options **before** the body runs, so any now-obsolete validation
   would preempt the retirement message: e.g. `graph import` declares
   `click.argument("snapshot_path", type=click.Path(exists=True))`
   (`cli.py:2309`), so `graph import missing.ttl` fails Click path-validation
   instead of showing the guidance. For every retired command, strip obsolete
   validation and requirements — drop `exists=True`, make formerly-required
   arguments optional (`required=False` / `nargs=-1`), and remove now-defunct
   `type=click.Choice(...)` / mutually-required options — so the body is always
   reached and the retirement guidance always surfaces regardless of arguments.
3. **Delete the 14 functions** from `mutations.py` / `snapshot.py`, plus helpers
   that become dead: `_attach_edge_claims` (add_edge-only), and
   `_warn_on_relation_direction_mismatch` **iff** verified unused by
   authored-relation compilation (`graph/sources.py` / `materialize.py`).
4. **Same-commit re-export prune.** Remove every retired name from
   `graph/__init__.py` `__all__` + import block, `graph/store/__init__.py` import
   block, and the `cli.py` top-level imports. The exported surface never lists a
   missing symbol.
5. **External-importer preflight** (parent §6): grep `~/d/science-commons`,
   `meta/`, and any `import science_tool` consumer for the 14 names before
   deletion. Product surface is the `science` CLI, not the package; expect a
   clean internal-API removal.

## 7. Forward-path templates

Retirement must point to a real authoring path. `proposition`, `finding`,
`interpretation`, `discussion`, `hypothesis`, `question`, and `evidence-line` are
already `entity create`-scaffoldable (`template_ready`). `concept`,
`observation`, and `mechanism` are compiler-loadable but template-less.

Add three minimal templates so every retired `graph add X` has a symmetric
`entity create X`. **Location matters:** `Renderer._read_template`
(`science_model/templates.py`) loads the **packaged** resource
`science_model/templates/<kind>.md` when no `template_root` override is given —
i.e. `science entity create <kind>` reads the *packaged* copy, not the repo-root
`templates/`. So the authoritative files are
`science/model/src/science_model/templates/{concept,observation,mechanism}.md`;
mirror them into repo-root `templates/` per the existing root↔packaged template
mirror convention, and the plan must assert both copies stay byte-identical.
Mark the three kinds `template_ready` in `CORE_PROFILE` and add them to
`MIGRATED_KINDS`, satisfying the descriptor reconciliation gate in the same
change. `add_edge` points to `relations:` authoring (no scaffold — relations are
not an entity kind).

## 8. Test-migration strategy

The rule is the §5.1 disposition, **not** "preserve every assertion" (that is
impossible here — see §2). For each test:

1. **Migrate** assertions over source-emitted shapes: re-author the setup as
   entity `.md` (+ `relations.yaml` / inquiry `flow_edges`) and `materialize`,
   then keep the assertion.
2. **Delete-with-pointer** assertions over mutator-only shapes (§5.1 bottom
   group): remove the test (or the specific assertion), leaving a one-line
   comment pointing to where the surviving behavior is proven (usually the
   compiler/`inquiry_compile` tests). A test whose *entire* point is a
   mutator-only predicate is deleted outright.
3. Never *weaken* a migrated assertion; never fabricate a source form for a
   deleted one.

### Shared helper

Add `build_entity_graph` to `tests/conftest.py` — the general-entity sibling of
Phase 1's `build_inquiry_graph`. It authors `entities/<kind>/<id>.md` (and
`relations.yaml` / `relations:` where an edge is needed) via
`tests/_fixtures/entity_helpers.write_markdown_entity` and runs
`materialize_graph`, returning the compiled path/dataset. Causal edges author as
`relations.yaml` at `graph_layer: graph/causal`; claim-cited causal edges author
as inquiry `flow_edges` with `claim_refs` (reuse `build_inquiry_graph`). Tests
assert against the honestly-compiled graph — the same path users take.

### Direct-import test files (build graph via mutator functions)

Every file importing a retiring mutator is in scope. Per-file disposition
(from the audit inventory):

- `test_causal.py` — migrate structural causal tests: concepts → authored
  `concepts/*.md`; `scic:causes`/`confounds` edges → `relations.yaml`
  (`graph/causal`); claim-cited edges (`TestEdgeProvenance`, export-provenance)
  → inquiry `flow_edges` with `claim_refs` referencing authored propositions
  (their `reasoning_metadata` migrates; the **mutator-only proposition payload**
  — compositional/platform/dataset-effects/statistical-support/bridge/
  interaction/prereg — and concept `observability` are **delete-with-pointer**,
  so the edge-provenance *payload* assertions are dropped). `add_falsification`
  usage (2 tests) is **deferred** — leave those tests calling it; the function
  stays until 3b.
- `test_paper_model.py` — migrate node + composition that is source-emitted;
  `groundedBy`/`contains` assertions are mutator-only → delete-with-pointer to
  `test_graph_materialize` composition coverage. Its `add_story`/`add_paper_entity`
  tests are **deferred** (leave intact).
- `test_provenance_evidence.py` — migrate stance/strength/**independence** (all
  source-emitted via authored `evidence-lines/*.md`); the invalid-independence
  `ClickException` case moves to the evidence-line authoring/validation path.
- `test_meta_reference.py` — only `TestMetaRefsInAddEdge` (2) + the
  `add_question`/`add_hypothesis` meta-skip test use retiring mutators; the
  meta-rejection intent already has a source-build analogue in the file
  (`TestMetaRefsInInquiryFlowEdge`) — convert to author-source rejection or
  delete-with-pointer there.
- `test_graph_export.py` — the shared `graph_path` fixture rebuilds via authored
  concepts + `relations.yaml` (causal) + authored proposition + inquiry
  `flow_edges`; evidence-overlay assertions that read the mutator-only payload
  are delete-with-pointer; `add_mechanism` node test migrates (source-emitted).
- `test_layered_claim_migration.py` — the two mutator tests: the reasoning-
  metadata bundle is source-emitted (migrate via authored proposition +
  `relations.yaml` edge + inquiry `flow_edges` claim); `test_add_proposition_
  validates_raw_reasoning_metadata_dicts` tests the **entity model validator**,
  so re-target it at `PropositionEntity` construction (the validator now lives
  on the schema, not the mutator).
- `test_graph_materialize.py` — one test
  (`..._graph_added_hypothesis_do_not_double_count`) uses `add_hypothesis`; its
  premise (mutator vs source double-count) is moot post-retirement →
  delete-with-pointer.
- `test_membership_bridge.py` — `TestBridgeBetweenMembership` (3, `cito:discusses`
  + `BundleMembership`) is source-emitted → migrate via authored proposition
  with `bridge_between`. `TestBridgeRoleCli` invokes the CLI → see below.
- `test_inquiry.py` — the single `add_concept` seed → author a `concepts/*.md`
  file + build.

### CLI-invocation tests (`CliRunner`)

- `test_graph_cli.py` — **migrate the ~30 "setup-only" tests first** (they use
  `graph add *` only to seed state for query/summary/validate/coverage/gaps/
  uncertainty/dashboard/neighborhood/question-summary surfaces that **stay**):
  re-author their setup via `build_entity_graph` / `entity create` + `graph
  build`. Assertions over query columns that read a **mutator-only payload**
  (dashboard-summary statistical/bridge/interaction/prereg) are dropped
  (delete-with-pointer) — those columns are already empty for real projects.
  Then the ~35 "unit-under-test" tests (asserting mutator-only triples —
  `propSubject`, `skos:note`, properties, `maturity`, the payload) are
  **deleted**; the handful asserting the ephemerality warning become
  retirement-message assertions.
- `test_entities_cli.py` — the 5 `graph add *` ephemerality/tip tests become
  retirement-message assertions (the durable `entity`/`entities`/`*s create`
  tests are untouched — they are the surviving path).
- `test_membership_bridge.py::TestBridgeRoleCli` — drive setup through `entity
  create` / authored source + `graph build`, then assert `BundleMembership`
  role, OR fold into the migrated `TestBridgeBetweenMembership` and delete the
  CLI variant with a pointer.
- `test_distill.py` — the 3 `graph import` tests assert the retirement message.
  Confirmed: **distill has no live non-test dependency on `import_snapshot`**
  (the tests use a hand-authored 2-triple Turtle via `_write_test_snapshot`, not
  distill output); the distill unit/CLI tests are untouched.
- `test_graph_cli.py` Tier-3: `test_graph_stamp_revision_*` and
  `test_graph_migrate_addresses_*` become retirement-message assertions.
- `test_command_docs.py` / `test_codex_skills.py` — already steer authors away
  from `graph add *` toward `entity create` / `*s create`; they stay green and
  are reinforced. The docs sweep (§9) keeps them passing.

## 9. Docs / skills sweep

`commands/`, `skills/`, `codex-skills/`, and `docs/` that instruct
`science graph add *` get repointed to source authoring (`entity create` / edit
`entities/<kind>/*.md` / `relations:` + `graph build`). `test_command_docs`
enforces the doc guidance, so the docs change in the same phase.

## 10. Phase shape (RED → GREEN)

Mirror Phase 1's proof discipline:

1. Shrink `EXPECTED_DEFERRED_WRITERS` to the 4 deferred writers → guard **RED**
   (14 unexpected sites). This names the exact retirement target.
2. Add the 3 forward-path templates + descriptor gate; add the generic
   `_retired_writer` helper.
3. Land `build_entity_graph`; **migrate the "setup-only" CLI tests to
   source-authored setup first** (so they stop invoking `graph add *`).
4. Convert the 14 CLI bodies to `raise _retired_writer(...)` (+ relax obsolete
   Click validation); dispose of the CLI unit-under-test tests per §8
   (delete mutator-only, convert warnings → retirement message).
5. Migrate/dispose the direct-import test files per §8 (guard still RED — the
   functions still exist and are imported).
6. Delete the 14 functions + dead helpers (`_attach_edge_claims`,
   `_warn_on_relation_direction_mismatch`), prune every re-export/import →
   guard **GREEN**: `actual == EXPECTED_DEFERRED_WRITERS` = the 4 deferred.
7. Docs/skills sweep; full suite + ruff + pyright green.

## 11. Success criteria

- Guard demonstrably RED-then-GREEN; ledger = exactly `{add_article,
  add_falsification, add_story, add_paper_entity}`.
- The 14 functions are deleted; no removed name remains in any `__all__` / import
  block / `cli.py` import (verified by `ruff check` finding no unused/undefined
  imports).
- Every retired `graph add X` (and the 3 Tier-3 commands) raises the generic
  `_retired_writer` with a working forward path, and surfaces that guidance
  **regardless of arguments** (obsolete Click validation relaxed — e.g.
  `graph import missing.ttl` shows the message, not a path error).
- `science entity create concept|observation|mechanism` succeeds from the
  **packaged** `science_model/templates/<kind>.md`; the packaged and repo-root
  `templates/` copies are byte-identical, and the descriptor reconciliation gate
  passes with the three kinds `template_ready` / in `MIGRATED_KINDS`.
- Migrated tests build state through `build_entity_graph` / authored relations
  and assert only source-emitted shapes; every deleted assertion is a
  mutator-only shape (§5.1) removed with a pointer to surviving coverage — no
  assertion is silently weakened.
- **No production regression for source-built projects:** the compiler's
  emission is unchanged, and (per the §5.1 read audit) no source-built consumer
  path depended on a deleted predicate. (We do **not** claim byte-identical
  `graph.trig` — the mutator-only shape is intentionally gone.)
- Full pytest suite, `ruff check`, and `pyright` pass.

## 12. Approaches considered

- **Split 3a (source-file path) / 3b (no source file). Chosen.** Isolates
  retirement of the 11+3 writers whose kinds have a source-authoring *file* path
  from the genuine capability decisions on the 4 legacy/no-source kinds. The
  §5.1 audit later showed the split is about the *file* path, not predicate
  parity — several 3a kinds emit mutator-only predicates — but the disposition
  (migrate source-emitted, delete mutator-only) keeps 3a well-defined and
  independently shippable behind the guard.
- **Add source forms for the live-reader mutator-only predicates
  (`observability`, proposition payload) as part of 3a.** Rejected for 3a
  (§3): that is new schema/compiler feature work, not retirement, and those
  features are already unpopulated for real projects — bundling them would
  couple a clean retirement to a design program. Left as a possible future
  effort.
- **One phase, all 15 + Tier 3.** Rejected: couples a large test migration to
  unresolved design calls (falsification source form, legacy `sci:Paper`
  retirement), with no intermediate safe state.
- **Narrow 3a: 6 "warn" mutators only.** Rejected: splits on advertising, not on
  whether a source path exists — the property that actually governs retireability.
