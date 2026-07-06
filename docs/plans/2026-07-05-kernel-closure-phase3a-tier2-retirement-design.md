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

Retire the 11 clean-source Tier-2 mutators and all 3 Tier-3 writers, moving their
capability entirely onto the source-declaration → `science graph build` path.
Shrink the guard ledger from 18 to exactly the 4 deferred writers. The compiled
`graph.trig` stays byte-identical for equivalent source input — this changes the
*write path*, not the graph.

## 3. Non-Goals

- The four no-clean-source kinds (`add_article`, `add_falsification`,
  `add_story`, `add_paper_entity`) are **out of scope** — deferred to Phase 3b,
  which decides each (add a source form vs. retire the capability and its
  read-only consumers).
- No `sci:Inquiry` consumer repoint (parent Phase 4).
- No compatibility shim. Retirement uses the existing `_retired_mutator` pattern
  (a hard, actionable error), never a silent fallback.
- No belief / materialize-output change. Behavior-neutral for the compiled graph.

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

Same rule as Phase 1: **preserve what each test proves.** Never weaken an
assertion; migrate a mutator-built graph to the real source→build path, or delete
a mutator-only test with a pointer to existing coverage.

### Shared helper

Add `build_entity_graph` to `tests/conftest.py` — the general-entity sibling of
Phase 1's `build_inquiry_graph`. It authors `entities/<kind>/<id>.md` (and
`relations.yaml` / `relations:` where an edge is needed) and runs
`materialize_graph`, returning the compiled path/dataset. Tests then assert
against the honestly-compiled graph — the same path users take.

### Direct-import tests (build graph via mutator functions)

Migrate off the deleted functions: `test_causal.py` (heavy `add_edge` /
`add_concept`, incl. `scic:causes` into `graph/causal` → `relations:` with
`graph_layer: graph/causal`), `test_paper_model.py` (`add_finding`,
`add_hypothesis`, `add_interpretation`, `add_observation`, `add_proposition`),
`test_graph_export.py`, `test_layered_claim_migration.py`,
`test_provenance_evidence.py`, `test_membership_bridge.py`,
`test_meta_reference.py`, `test_inquiry.py`, `test_graph_materialize.py`.

**Mixed clean+deferred files:** several files import both retiring-clean and
deferred mutators — `test_causal` (also `add_falsification`) and
`test_paper_model` (also `add_paper_entity`, `add_story`). 3a migrates only the
clean-mutator usage in these files and leaves the deferred imports intact — those
functions still exist and stay in the ledger until 3b. There is **no**
deferred-only test file that 3a can skip entirely; every file importing a
retiring-clean mutator is in scope.

### CLI-invocation tests (`CliRunner`)

- `test_graph_cli.py`: convert "state gets written" cases to `entity create` /
  author + `graph build` then assert graph state; convert "command exists" cases
  to assert the `_retired_mutator` error.
- `test_entities_cli.py`: the warning/tip-text assertions become
  retirement-message assertions.
- `test_distill.py`: migrate off `graph import` (`import_snapshot`). A task
  confirms distill has no live non-test dependency on it; if it does, that is a
  finding to surface, not a silent workaround.
- `test_command_docs.py`: tracks the docs sweep (§9).

## 9. Docs / skills sweep

`commands/`, `skills/`, `codex-skills/`, and `docs/` that instruct
`science graph add *` get repointed to source authoring (`entity create` / edit
`entities/<kind>/*.md` / `relations:` + `graph build`). `test_command_docs`
enforces the doc guidance, so the docs change in the same phase.

## 10. Phase shape (RED → GREEN)

Mirror Phase 1's proof discipline:

1. Shrink `EXPECTED_DEFERRED_WRITERS` to the 4 deferred writers → guard **RED**
   (14 unexpected sites). This names the exact retirement target.
2. Land `build_entity_graph`; migrate the direct-import and CLI-invocation tests.
3. Add the 3 forward-path templates.
4. Convert the 14 CLI bodies to `_retired_mutator`, delete the 14 functions +
   dead helpers, prune every re-export/import.
5. Guard **GREEN**: `actual == EXPECTED_DEFERRED_WRITERS` = the 4 deferred.
6. Docs/skills sweep; full suite + ruff + pyright green.

## 11. Success criteria

- Guard demonstrably RED-then-GREEN; ledger = exactly `{add_article,
  add_falsification, add_story, add_paper_entity}`.
- The 14 functions are deleted; no removed name remains in any `__all__` / import
  block / `cli.py` import.
- Every retired `graph add X` (and the 3 Tier-3 commands) raises the generic
  `_retired_writer` with a working forward path, and surfaces that guidance
  **regardless of arguments** (obsolete Click validation relaxed — e.g.
  `graph import missing.ttl` shows the message, not a path error).
- `science entity create concept|observation|mechanism` succeeds from the
  **packaged** `science_model/templates/<kind>.md`; the packaged and repo-root
  `templates/` copies are byte-identical, and the descriptor reconciliation gate
  passes with the three kinds `template_ready` / in `MIGRATED_KINDS`.
- The migrated test files build state through `build_entity_graph` / authored
  relations, with assertions preserved (or deleted-with-pointer).
- Compiled `graph.trig` byte-identical across the phase for equivalent source.
- Full pytest suite, `ruff check`, and `pyright` pass.

## 12. Approaches considered

- **Split 3a (clean) / 3b (hard). Chosen.** Isolates the mechanical,
  behavior-neutral retirement of 11+3 writers from the genuine capability
  decisions on the 4 legacy/no-source kinds. Each half is independently
  shippable behind the guard.
- **One phase, all 15 + Tier 3.** Rejected: couples a large test migration to
  unresolved design calls (falsification source form, legacy `sci:Paper`
  retirement), with no intermediate safe state.
- **Narrow 3a: 6 "warn" mutators only.** Rejected: splits on advertising, not on
  whether a source path exists — the property that actually governs retireability.
