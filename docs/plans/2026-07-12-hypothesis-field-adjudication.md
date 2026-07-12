# Hypothesis Field Adjudication (D5 Task 2)

> **Status: proposed — two owner decisions are open (§5).** Every disposition below is backed by an
> opened reader, cited `file:line`. This is the artifact Task 6 (core mixin) and Task 6b (project
> extensions) are generated from. A key that is wrong here becomes a hard validation failure on real
> files the moment the schema closes.

**Corpus:** 147 authored hypotheses across 18 project roots / 15 git repositories
(`science entity field-inventory`, Task 1). **36 distinct authored keys.**

---

## 1. The admission rule — derived, not assumed

Rev 2 of the plan admitted a key to the **core** mixin because it was *observed somewhere*. Design
rev 8 rejected that for the belief cluster. The reader survey shows the same rule leaked in a second
time, through a different set of fields — so it needs replacing, not patching.

> ### The rule: **a key is core iff the toolkit reads it.**
> Ownership decides *where* a non-core key goes; it does not decide *whether* it is core.

The corpus corroborates this sharply. **Every key with zero readers is authored by exactly one
project** — and the one heavily-authored non-core key that *does* have readers (`required_capabilities`,
38 files) is authored **independently by three** (mm30 24, post-acute-infection 7, cbioportal 7).

| | has a toolkit reader | no reader |
|---|---|---|
| **authored by ≥2 projects** | `required_capabilities`, `datasets`, `origins`, … → **core** | *(empty)* |
| **authored by exactly 1 project** | `capability_scope`, `composition_rule` → core (real gates) | `identification`, `tags`, `priority`, `role`, `promoted_from`, `promotion_criteria`, `domain`, `external_hypothesis_id`, `confidence_label`, `confidence_mechanistic_label` → **not core** |

**Single-project authorship + zero readers is the signature of a project-local convention mistaken
for shared vocabulary.** That quadrant is where rev 2 would have put nine fields into the core schema
of all 22 projects.

---

## 2. CORE — structural and lifecycle

| key | files | reader | disposition |
|---|---|---|---|
| `id`, `kind`, `title`, `status` | 147 / 146 | everywhere | **core** |
| `created`, `updated` | 143 | freshness, materialize | **core** |
| `related`, `source_refs` | 147 / 128 | resolution, graph edges | **core** |
| `verdict`, `closure_basis`, `superseded_by`, `resynthesized_into`, `archive_ref` | **0** | *(new in D5)* | **core** — authored adjudication + terminal basis (design rev 8) |

`phase` folds into `status` (design rev 7); see §6.

## 3. CORE — real readers, keep

| key | files | reader (opened) | note |
|---|---|---|---|
| `origins` | 33 | `materialize.py:928-951` → `sci:Origin` nodes; `validate/checks/origins.py:73-101` | the structured provenance model |
| `added_by` | 31 | `materialize.py:954-955` → `sci:addedBy` | |
| `lens_views` | 28 | `materialize.py:1877-1894` → `sci:LensView`; `validate/checks/lens_views.py:33-59` | |
| `ontology_terms` | 22 | declared; resolution | |
| `datasets` | 17 | `dataset_prioritize.py:147`; `dataset_capabilities.py:177`; `dataset_influence.py:291`; `datasets_catalog.py:262-301` + CLI writer `:314-347` | **load-bearing on Q/H.** *Template gap: `datasets: []` is prescribed in `templates/question.md:8` but NOT in `templates/hypothesis.md`, though the code fully supports it here.* |
| `review_state` | 6 | `materialize.py:2043-2046` → `derive_freshness` → **attention ranking**; `entity_review.py:89-97` | strongest consumer of any key here |
| `aliases` | 3 | `sources.py:775-797` merges authored + derived; `entity_identity.py:73-75`; `prose_lint.py:782` | **authored values survive** — additive merge, not overwrite |
| `profile` | 3 | `sources.py:765-772` **fill-if-missing**; `materialize.py:640` → `sci:profile`; `entities_inventory.py:195-199` → `registration_state` | **⚠️ the plan said "strip them" — wrong.** An authored `profile` is *honored*, reaches the graph, and changes registration state. |
| `composition_rule` | 1 | `materialize.py:1849-1851` → `sci:compositionRule` → `bundle_belief.py:92-97` weakest-link → **`belief_snapshot.py:51` reproducibility hash** | fully live |

## 4. CORE — the capability side-channel (declare; P1 absorbs later)

| key | files | projects | reader |
|---|---|---|---|
| `required_capabilities` | **38** | **3** (mm30, post-acute-infection, cbioportal) | `dataset_capabilities.py:141` (validate WARN); `dataset_prioritize.py:525` → `science dataset prioritize --coverage` |
| `capability_scope` | 1 | mm30 | `dataset_capabilities.py:113` `_scope_gate` (suppresses `*-missing`); `dataset_prioritize.py:511,522` |

**Both readers deliberately re-parse the markdown bytes** (`_helpers.py:146-169` `entity_frontmatters`,
whose docstring says it exists "to inspect malformed fields without strict-loading the closed graph
Entity model") — **precisely because the Entity model would eat the field.** This is a raw-frontmatter
side channel around `extra="ignore"`, and it is the single strongest piece of evidence for D5's whole
thesis: when a schema silently drops what authors write, consumers grow a second way in.

> **These MUST be declared before strictness lands, or 38 real files hard-fail.** They are declared,
> not absorbed — P1 owns the subsystem.
>
> **Authoring-guidance gap (file it):** `required_capabilities` is the most-authored non-core key in
> the corpus and is prescribed by **no template and no command** — only by `docs/user-guide/entities.md`.
> Authors reverse-engineered it from prose. *That is how a side channel forms.*

## 5. PROJECT-EXTENSION — real, but owned by one project

Composed via Task 6b. **Two of these are the owning project's call, not the toolkit's** (marked ⚠️).

| key | files | owner | extension |
|---|---|---|---|
| `confidence_label`, `confidence_mechanistic_label` | 12 each | mm30 | `extension-mm30.assessment` — the MM exporter reads them and emits them *separately* from derived `bundle_belief`. **Zero toolkit readers.** |
| `identification` | 12 | mm30 | values are a causal-identification vocabulary (`observational` \| `interventional` \| `longitudinal` \| `structural` \| `methodological`; one file leaks the enum in an inline comment). The lookalike `identification_strength` is a **real declared field on `PropositionEntity`** — a different kind. Bare `identification` is dead: its only route was the **retired** `.edges.yaml` (`workbench_apply.py:171` now raises); only the stale prompt `agents/hypothesis-synthesizer.md:58` still mentions it. → `extension-mm30.identification_strategy` |
| `external_hypothesis_id` | 13 | evolution | `EH-###` — an external system's key. Zero readers. → `extension-evolution.external-ids` |
| ⚠️ `evidence_stance` | 13 | evolution | **provenance, not magnitude** (design rev 8). Keep as `evidence_scope` **or delete — owner's call.** Either way: **removed from `_authored_magnitude`** (Task 2b). |
| ⚠️ `confidence` | 2 | 3d-attention-bias | **A per-kind narrowing, not a delete.** `confidence` is declared on `Entity` (`entities.py:331`) and materialized as `sci:confidence` for *all* kinds, feeding `low_confidence` risk signals (`store/summary.py:101-126`), the evidence export (`store/export.py:213-250`), both causal exporters, and `graph uncertainty`. It stays core **for other kinds**; the *hypothesis* mixin simply does not admit it. Migrate the 2 files to a project-local prior or an `expert_judgment` evidence line. **This narrowing is only expressible because the schema is per-kind — it could not be said before D5.** |

## 6. RENAME / MIGRATE

| key | files | owner | target |
|---|---|---|---|
| `author_stated_evidence` | 13 | evolution | → structured `origins`, or project-local `source_stated_evidence`. **Must never influence computed belief** (design rev 8). |
| `promoted_from` | 3 | protein-landscape | → **`origins`**. Its values are literally source paths (`knowledge/sources/local/entities.yaml`) — which is exactly what the structured origin model holds. Today it is **write-only and emitted on `decision` entities** (`decision_log.py:157`), not hypotheses; nothing reads it back. |
| `description` | 3 | protein-landscape | → keep as a **core generic** field. It is *not* inert: `sources.py:748-755` uses it as the `content_preview` fallback, which becomes `schema:description` in the graph (`materialize.py:639`). Declare it rather than lose the effect. |

## 7. DERIVED / DELETE  *(no **semantic** reader — see §7b)*

| key | files | why |
|---|---|---|
| `phase` | **107** | **Folds into `status`** (design rev 7 — `phase` *is* the lifecycle). Confirmed: **no model or graph reader.** `Entity` drops it at `sources.py:377`; `materialize.py:649-650` says so in a comment ("`phase` stops at the model, which is exactly why it could not have carried this — fb-2026-07-11-005"). Its only code reader is one shape WARN (`validate/checks/hypotheses.py:64-70,128`). **Its real consumers are LLM agents reading raw YAML** — `commands/big-picture.md:213,217` builds the Arc and Candidate-frames sections from it. Those must migrate with it (Task 10). |
| `belief_state` | 13 | **The second-source-of-truth defect.** Belief is computed: `belief.py`'s `_claims()` iterates `(Proposition, Hypothesis)`. See Task 2b. |
| `tags` | 11 | **Already ruled legacy by the toolkit itself.** `graph/health_checks/lingering_tags.py:64-79` is a health check whose entire purpose is to report `tags:` as "Legacy `tags:` fields to migrate" (`health_cli.py:317`). D5 does not decide this — it *finishes* it. (The name is separately owned by project config and by commons.) |
| `priority` | 8 | **No reader.** The name is wholly owned by `task` (`tasks.py:169,300,555`; `validate/checks/tasks.py:19`). |
| `role` | 2 | **No reader.** Every `role` in the codebase belongs to something else (membership entries, `dataset_usage`, inquiry boundaries, `ProjectConfig.role`). `science/meta/entities/hypotheses/0007-working-model.md:9` authors `role: working-model` and it is silently dropped. |
| `promotion_criteria` | 2 | **Not a frontmatter key at all.** It is a body **section** (`templates/hypothesis.md:36,92`, explicitly "a documentation convention, not a validator-enforced rule"). Two authors mistook a section for a field — which is itself evidence that `extra="ignore"` teaches authors that anything is accepted. |
| `domain` | 2 | **Write-only.** `materialize.py:643-644` emits `sci:domain`; **nothing reads the triple back**, and `GraphNode.domain` has zero call sites. The two loaders even disagree — `frontmatter.py:514` hardcodes `domain: None`. *(Declared on `Entity`, so this is a per-kind narrowing + a defect to file, not a global delete.)* |
| `rival_model_packet` | 1 | Declared on `ProjectEntity` and materialized for any kind, but **every reader is proposition-scoped** (`evidence_signals.py:90-92`, `health.py:318-327`). On a hypothesis it is write-only. **Keep declared** (it is core for propositions); the hypothesis mixin need not require it. |

---

## 7b. ⚠️ "No reader" means *no semantic reader* — one schema-blind passthrough consumes them all

`labnote_export.py:805-823` builds an entity's exported `metadata` as **every frontmatter key not in a
small exclusion set** (`{id, type, title, name, label, sensitivity, aliases, tags, status, discusses,
related, relations}`):

```python
metadata = {key: value for key, value in frontmatter.items()
            if key not in {...} and isinstance(value, (str, int, float, bool, list, dict))}
```

So **every key in §7 is exported today** — `role`, `priority`, `domain`, `identification`, `phase`,
`external_hypothesis_id`, all of them. Deleting them shrinks that `metadata` dict. The export carries
**no semantics** (it is a verbatim passthrough; nothing downstream keys off these fields), so this is
not a blocker — but the claim must be stated honestly: **no semantic reader, one schema-blind sink.**
Task 11's graph diff will not see it; a labnote export diff would.

> **This is the third independent workaround for `extra="ignore"` in the codebase**, and together they
> are the strongest argument for D5:
> 1. **Deliberate re-parse** — `dataset_capabilities` / `dataset_prioritize` re-read the raw markdown
>    *because the model would eat the field* (`_helpers.py:146-169` says so in its docstring).
> 2. **Pre-validation read** — `_enrich_raw:748-755` consumes `description` before Pydantic sees it.
> 3. **Schema-blind passthrough** — this one: export whatever the author wrote, ask no questions.
>
> When a schema silently drops what authors write, **consumers do not go without — they grow a second
> way in.** Each of these is individually reasonable and collectively a shadow schema that no one
> declared and no one can validate.

## 8. Consequences to carry into other tasks

1. **Task 6's mixin is materially smaller than rev 2's.** Nine keys drop out of core:
   `identification`, `tags`, `priority`, `role`, `promoted_from`, `promotion_criteria`, `domain`,
   `external_hypothesis_id`, `confidence_label`/`confidence_mechanistic_label`.
2. **Task 6b is a hard prerequisite for strictness** — not optional. Without the mm30 and evolution
   extensions, closing the schema leaves only two wrong options: reject their files, or promote their
   fields to core.
3. **Task 9 must fix the packaged template.** `templates/hypothesis.md:18-29` (and its
   `science_model/templates/` shadow — **there are two**) prescribes `disposition` and `phase`, both of
   which D5 deletes. A migrated repo would **re-grow them on the next `science entity create`.**
4. **Task 10 must migrate `commands/big-picture.md:213,217`**, which is the only substantive consumer
   of `phase`, and reads it from raw YAML rather than the graph.
5. **New defects to file** (independent of this arc):
   - `domain` is materialized and never read; `parse_entity_file` and the graph loader disagree about it.
   - `datasets` is load-bearing on hypotheses but absent from the hypothesis template.
   - `required_capabilities` (38 files) is prescribed by no template or command.

## 9. Open — owner decisions (Task 2 Step 2)

1. **evolution:** is `evidence_stance` preserved as `evidence_scope`, or deleted? (13 files)
2. **3d-attention-bias:** where do the 2 authored `confidence` values go — project-local prior, or an
   `expert_judgment` evidence line?

Everything else is decided by the reader evidence above.
