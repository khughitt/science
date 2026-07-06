# Kernel Closure Phase 3b — Deferred-Writer Retirement (guard to zero)

**Status:** design accepted (2026-07-06), pending user review before plan.
**Predecessors:** [`2026-07-05-kernel-closure-writer-boundary-design.md`](2026-07-05-kernel-closure-writer-boundary-design.md) (program design), Phase 1 (guard + Tier 1), [`2026-07-05-kernel-closure-phase3a-tier2-retirement-design.md`](2026-07-05-kernel-closure-phase3a-tier2-retirement-design.md) (11 Tier-2 + 3 Tier-3 writers, SHIPPED).

## 1. Context & Goal

Phase 3a shrank the durable-writer guard ledger (`science/tests/graph/test_durable_write_boundary.py`) from 18 to the 4 writers that were deferred for lacking "a clean source-authoring file path": `add_article`, `add_falsification`, `add_story`, `add_paper_entity`.

**Goal:** retire all four, shrinking `EXPECTED_DEFERRED_WRITERS` to **empty**. After 3b the guard asserts that *no* durable writer of `knowledge/graph.trig` exists outside the compiler allowlist (`graph/materialize.py`, `graph/store/dataset.py`) — source declarations become the sole durable writer. This completes the kernel-closure program's writer-retirement arc.

A blind-code audit (2026-07-06) resolved the four into three difficulty tiers: two are pure surface cleanup, one is a straight delete, one needs a new source kind. The design below is grounded in that audit.

## 2. Non-Goals

- **No behavior change to the read side.** Summary risk-scoring, belief overlay, and the causal exporters read falsifications via the `sci:falsifies` edge; that query is form-agnostic and stays untouched.
- **No `manuscript`/publication-draft kind.** The `add_paper_entity` composition concept (`sci:comprises` paper→story) has zero readers and no authored instances; it is deleted, not re-homed. If a real manuscript-drafting consumer is ever built, a `manuscript` kind is its own future work.
- **No deletion of the `article` or `paper` entity kinds.** Only their ad-hoc *graph writers* retire (see §3). Both kinds remain live for their real roles (reference/citation classification; external-literature notes).
- **No template-completeness sweep.** Beyond wiring `story` and adding `falsification`, other kinds' templates are out of scope (that remains a separate deferred workstream).

## 3. The four dispositions

| Writer | Emits | Live readers? | Disposition | CLI shape |
|---|---|---|---|---|
| `add_article` | `sci:Article` + `schema:identifier` (DOI) | none | **retire writer; keep `article` kind** — DOI notes served by the `paper` kind | message-only retired → `entity create paper` |
| `add_story` | `sci:Story` + label/status + `sci:synthesizes`/`sci:organizedBy` | none read a Story node uniquely; `synthesizes` consumed writer-agnostically | **retire writer; wire `story` kind** for `entity create story` | message-only retired → `entity create story` (+ relations) |
| `add_paper_entity` | `sci:Paper` composition via `sci:comprises` → stories | **none** (`sci:comprises` unread; no instances) | **delete outright** (+ delete legacy `comprises` RelationKind) | delete-outright (command removed) |
| `add_falsification` | `sci:Falsification` + predicted/observed/decision/sourceOfPrediction + `sci:falsifies` (+ optional `sci:supersedesClaim`) | **yes** — summary risk, belief overlay, both causal exporters | **build `falsification` kind + compiler emission, then retire writer** | message-only retired → `entity create falsification` |

**CLI retirement shapes (explicit):**
- **Message-only retired** = the Click command *remains* registered but its body `raise _retired_writer(command, forward_path)`; it performs no durable write. Tests assert non-zero exit + the retirement message. (Same pattern as Phase 3a.) Applies to `graph add article`, `graph add story`, `graph add falsification`.
- **Delete outright** = the Click command is *removed*; tests assert `science graph add paper …` yields Click's "No such command" (there is no forward path to point at — the concept is gone). Applies to `graph add paper` (`add_paper_entity`).

### 3.1 `add_article` — retire the writer, keep the kind

`add_article` (`graph/store/mutations.py`) emits only `(article/doi_<slug>, rdf:type, sci:Article)` + `schema:identifier` into `graph/knowledge`. **Zero readers** of `sci:Article` exist. The DOI-note use case is served richly by the source-authored `paper` kind (`entities/papers/<citekey>.md` + `doi:` → compiler emits `sci:doi`, `materialize.py:643-650`).

**Critical correction to keep the change safe:** the `article` *EntityKind* (`profiles/core.py`, `entity_class=REFERENCE`) is **not** vestigial — it is the reference/citation classification for BibTeX `@article` records and is load-bearing:
- present in `INTENDED_ADDITIONS` (`tests/test_kind_reconciliation_registry.py:43`), `FROZEN_KIND_CLASSES` as `"article": "reference"` (`tests/test_kind_map_equivalence.py:186`), and `known_kinds()`;
- exercised by `test_kind_class.py:39` (`kind_class("article") == REFERENCE`), `test_references.py`, `test_knowledge_gaps.py`, `tests/validate/test_checks_notes.py`, `test_downstream_legacy_inventory.py`.

Therefore Phase 3b retires **only the `add_article` writer** and leaves the `article` kind untouched. Consequence: `add_article` touches **no** reconciliation gate. After retirement, ad-hoc `sci:Article` graph nodes simply stop being minted (nothing read them); the kind persists for citation classification, which never emitted a graph node from source anyway.

### 3.2 `add_story` — retire the writer, wire the kind

Authored `entities/stories/<id>.md` (`kind: story`) + `synthesizes`/`organizedBy` entries in `knowledge/sources/<local>/relations.yaml` already compile to the identical `sci:Story` node and edges (proven end-to-end by `tests/test_graph_freshness_integration.py`). `story` is already `EPISTEMIC` + `AUTHORED_CORE` and already in `PRE_EXPANSION_CORE_KINDS` / `FROZEN_KIND_CLASSES` (`"story": "epistemic"`), so the class/delta gates do **not** move.

**Wiring gap to close:** the `story` descriptor lacks `home`/`template_ready`/`strategy`/`default_status`/`statuses`, so `science entity create story` cannot yet scaffold the forward-path file. Add them, mirroring an existing epistemic authored kind (`interpretation` for `home`, `evidence-line` for `strategy="slug"` + statuses). A packaged `story.md` template already exists.

**Forward-path parity risk (must be handled):** `entity create story` scaffolds only the entity *file*. Its edges — `sci:synthesizes` → interpretations, `sci:organizedBy` → the about-target — are authored in `relations.yaml`, which a template cannot produce. To avoid silently losing those edges relative to the old writer, the story **template body and the retirement message must direct authors to add the `synthesizes`/`organizedBy` relations in `relations.yaml`** (the `synthesizes`/`organized_by` RelationKinds already exist, `core.py:695-709`).

Only gate touched: `FROZEN_MIGRATED_KINDS += "story"`.

### 3.3 `add_paper_entity` — delete outright

`add_paper_entity` emits `sci:Paper` + `sci:comprises` → story refs (project's own publication draft, status `outline/draft/revision/final`). `sci:comprises` has **zero readers** (grep of summary/query/export/belief/validate is clean), there are **no authored instances**, the CLI command already self-warns it is graph-only/legacy, and the concept **collides** with the source `paper` kind (external literature). Per the accepted decision, it is deleted with no replacement:
- delete `add_paper_entity` (`mutations.py`) and the `graph add paper` command (`cli.py`);
- delete the legacy `comprises` RelationKind (`core.py:727`) and its predicate-manifest entry (`constants.py:374`) — its only references are the write site, the manifest, and two `test_paper_model` asserts;
- the `paper` kind, `paper` template, and `entity create paper` are untouched.

No reconciliation gate moves (no kind added or removed; `comprises` is a RelationKind with no frozen-gate membership — confirm no relation-enumeration test freezes it during implementation).

### 3.4 `add_falsification` — build a source kind, then retire

The only real build. `add_falsification` emits, per `mutations.py:53-61`, into `graph/knowledge`:
```
(falsification/<token>, rdf:type, sci:Falsification)
(…, sci:predicted, Literal(predicted))
(…, sci:observed, Literal(observed))
(…, sci:decision, Literal(decision))
(…, sci:sourceOfPrediction, Literal(source_of_prediction))
(…, sci:falsifies, <proposition_uri>)                 # target validated to be a sci:Proposition
(…, sci:supersedesClaim, _resolve_term(supersedes_claim))   # optional, resolved URI
```
This shape is **load-bearing**: `_load_proposition_falsifications` (`evidence_signals.py:158-174`) rehydrates it per proposition for summary risk-scoring (`summary.py:120-122`, `+3.0` risk + `"falsified"` signal), the belief/evidence overlay export (`export.py:267-269`), and both causal exporters (`causal/export_pgmpy.py`, `causal/export_chirho.py`). It has no source form today.

**Model it as a first-class kind, parallel to `evidence-line`** (accepted decision): a falsification is a structured record about a proposition, exactly the shape evidence-line already established.

**`FalsificationEntity` schema** (`science_model`, mirror `EvidenceLineEntity`):
- `falsifies: str` — target proposition ref (**required**; the only field validated to resolve to a `sci:Proposition`).
- `predicted: str`, `observed: str`, `decision: str`, `source_of_prediction: str` — free-text, emitted as **literals**.
- `supersedes_claim: str | None` — optional; emitted as a **resolved URI**.
- standard entity fields (`id`, `kind`, `title`/label, `status`, `related`, `source_refs`, `created`, `updated`).

**Descriptor** (`profiles/core.py`, mirror evidence-line): `EPISTEMIC`, `AUTHORED_CORE`, `template_ready=True`, `home="entities/falsifications"`, `canonical_prefix="falsification"`, `strategy="slug"`, `default_status` + `statuses` mirroring evidence-line.

**Template** `science_model/templates/falsification.md` (+ repo-root mirror) with sections cueing predicted/observed/decision and a `falsifies:` frontmatter field.

**Compiler emission** (`materialize.py`, mirror the evidence-line emitters):
- `_add_falsification_metadata(uri, provenance, entity)` — a field→predicate map (`predicted→sci:predicted`, `observed→sci:observed`, `decision→sci:decision`, `source_of_prediction→sci:sourceOfPrediction` as **literals**; `supersedes_claim→sci:supersedesClaim` as a **resolved URI** when present), modeled on `_add_evidence_line_metadata` (`materialize.py:1050`).
- `_add_falsification_relations(...)` — emits `(uri, sci:falsifies, <resolved proposition uri>)`, modeled on `_add_evidence_line_relations` (`materialize.py:1010`); validates the target resolves to a proposition (fail-loud, mirroring the writer's guard).
- dispatch both from `_add_entity` (`materialize.py:611`), guarded by `isinstance(entity, FalsificationEntity)`, alongside the existing `EvidenceLineEntity` branch.

**Byte-parity requirement (explicit):** the emitted triples must match the old writer term-for-term — `sourceOfPrediction` a literal, `supersedesClaim` a resolved URI, node URI `falsification/<slug>` (source id `falsification:<slug>` → same URI form). Only `falsifies` is proposition-validated; the four metadata fields are unvalidated literals. The read helper is unchanged, so consumers see identical data.

Reconciliation gates touched: `INTENDED_ADDITIONS += "falsification"`, `FROZEN_KIND_CLASSES += "falsification": "epistemic"`, `FROZEN_MIGRATED_KINDS += "falsification"`. (`test_assertion4_authored_core_equals_registry_core` stays balanced automatically — both registry-core and authored-core gain the kind.)

## 4. Reconciliation gates — exact impact

| Change | `FROZEN_MIGRATED_KINDS` | `FROZEN_KIND_CLASSES` | `INTENDED_ADDITIONS` (+delta test) | Other |
|---|---|---|---|---|
| retire `add_article` (keep kind) | — | — | — | — |
| `story` → template_ready + home/strategy/statuses | **+story** | — | — | `entity create story` gains a template |
| new `falsification` kind | **+falsification** | **+`"falsification":"epistemic"`** | **+falsification** | authored-core=registry-core stays balanced |
| delete `add_paper_entity` (+`comprises`) | — | — | — | confirm no relation-enumeration gate freezes `comprises` |

Also update any doc generated from `CORE_PROFILE` (kind listings in `docs/user-guide/entities.md` and any command-doc/skill guards) to add `falsification` and reflect `story` becoming create-scaffoldable. The `article` id-prefix / cross-reference allowlists are **unchanged** (kind retained).

## 5. Guard to zero

`EXPECTED_DEFERRED_WRITERS` becomes empty. Use `set()` (or `frozenset()`) — **not** `{}` (which is an empty dict and would silently change the set-difference semantics). Update the guard's module docstring to record that the ledger is empty and the program's writer-retirement arc is complete: the guard now asserts the allowlist is the *entire* set of durable-writer sites.

## 6. Test disposition

- **`test_causal.py`** — migrate `test_enriched_edges_include_linked_falsifications` and `test_export_pgmpy_includes_falsification_comments` from `add_falsification(...)` to an authored `entities/falsifications/<id>.md` fixture built through the compiler (reuse the `build_entity_graph` helper from 3a). Assertions on the read-side overlay/export are preserved.
- **New materialization parity test** (`test_graph_materialize.py` or a focused test): author one falsification and assert the compiler emits `rdf:type sci:Falsification`, all four metadata predicates (`predicted`/`observed`/`decision`/`sourceOfPrediction`), `sci:falsifies` → the proposition, and `sci:supersedesClaim` when present.
- **`test_paper_model.py`** — delete `test_add_paper_entity`, `test_add_paper_entity_invalid_status`, and drop the `add_story`/`add_paper_entity` composition tail of `test_full_composition_chain` (delete-with-pointer; no authored `sci:comprises` equivalent). `test_add_story*` → delete-with-pointer to `test_graph_freshness_integration` (source coverage) or convert to authored source.
- **`test_graph_cli.py`** — delete `test_graph_add_article_records_reference`; convert `test_graph_add_story_warns_graph_only_not_durable` to a message-only retirement assertion; add a `graph add paper` "no such command" assertion (delete-outright shape). Add the retired `graph add article/story/falsification` to the parametrized retirement-surface test (extend 3a's `test_retired_writer_commands_all_report_retirement`).
- **Gate tests** — update `FROZEN_MIGRATED_KINDS`, `FROZEN_KIND_CLASSES`, `INTENDED_ADDITIONS` per §4.
- **Guard** — RED at the start of the phase (ledger emptied before functions deleted), GREEN after §7 Step "delete + prune".

## 7. Sequencing (same ratchet shape as 3a)

1. **Guard RED** — set `EXPECTED_DEFERRED_WRITERS = set()`; expect exactly 4 unexpected sites.
2. **Build forward paths** — `FalsificationEntity` schema + descriptor + template + compiler emitters (with the parity test); wire the `story` kind (home/template_ready/strategy/statuses + template body pointing at `relations.yaml`); update the reconciliation-gate literals.
3. **Migrate/dispose tests** — `test_causal` falsification migration; `test_paper_model` deletions; `test_graph_cli` conversions; parametrized retirement-surface extension.
4. **Retire CLI surfaces** — message-only for `graph add article/story/falsification`; delete `graph add paper`.
5. **Delete + prune** — delete the 4 writer functions + the `comprises` RelationKind + its manifest entry; prune re-exports/imports in `graph/store/__init__.py`, `graph/__init__.py`, `cli.py`; ruff to catch stragglers → **guard GREEN**.
6. **Docs/skills sweep + final gate** — repoint any live `graph add article/story/paper/falsification` guidance to source authoring; add `falsification` to CORE_PROFILE-generated kind docs; full `pytest`/`ruff`/`pyright` + model suite.

## 8. Success criteria

- `EXPECTED_DEFERRED_WRITERS == set()` and the durable-write boundary guard is GREEN — no durable writer outside the compiler allowlist.
- Authored `entities/falsifications/*.md` produces byte-identical `sci:Falsification` graph shape to the retired writer; summary risk / belief overlay / causal exports are unchanged for a source-built project.
- `entity create story` and `entity create falsification` scaffold valid entities; the story path documents the `relations.yaml` step for `synthesizes`/`organizedBy`.
- `article` and `paper` kinds remain fully functional (citation classification; external-literature notes).
- Full suite + ruff + pyright + model suite green.

## 9. Approaches considered / rejected

- **Delete the `article` kind** (as an earlier framing assumed) — **rejected**: the kind is load-bearing for BibTeX/citation classification (§3.1). Only the writer retires.
- **`falsification` as proposition frontmatter** — rejected in favor of a first-class kind, for parity with `evidence-line` and to give falsifications independent identity/lifecycle/provenance (accepted decision).
- **Introduce a `manuscript` kind for `add_paper_entity`** — rejected (no reader, no instances); deleted outright, deferred to future work if a drafting consumer appears.
- **Split 3b into trivial-removals + falsification-build phases** — rejected; the three removals are small enough that one combined phase reaches the ledger-zero milestone in a single merge, with falsification isolated in its own tasks.
