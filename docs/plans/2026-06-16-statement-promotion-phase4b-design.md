# Phase 4b — Question/Hypothesis Promotion (design)

**Project:** `lit-annot` sub-article annotation (EXTEND `science`). Phase 4 = promotion of
raw span annotations into epistemic entities. This spec is **slice 4b**: extending the
statement-promotion spine to `question` and `hypothesis` statement annotations.

**Status:** approved design (brainstorming complete; scope + 2 architectural forks resolved
with the user). Next step: implementation plan.

**Builds on:** Phase 4a (`2026-06-16-statement-promotion-phase4a-design.md`) — the
proposition spine: `science annotate promote`, `normalize_claim` title-dedup, two-carrier
provenance, two-guard idempotency, candidate→review→apply with `--input` override,
skip-and-count fail-loud.

---

## Goal

Make `question`- and `hypothesis`-type **statement annotations** (Phase 3a output) on a
paper's `.source.md` sidecar promotable into `question` / `hypothesis` **entities** — minting
new ones or linking to existing ones — reusing the 4a spine wholesale and adding only what
the two new target kinds genuinely require. 4a already left the door open: it skips these
annotations with `promote-not-proposition-type`.

## Where it fits

```
Phase 3a/3b (DONE): statement annotations (type ∈ {proposition, question, hypothesis})
                    + figurative annotations (metaphor, analogy)

Phase 4a (DONE):    proposition-type statement annotation → proposition entity
Phase 4b (THIS):    question/hypothesis statement annotation → question/hypothesis entity
Phase 4c (later):   predicate/polarity/claim_layer synthesis (factoring)
Phase 4d (later):   cross-paper evidence (cito:supports/disputes) → belief layer
```

## What 4b consumes and produces

**Consumes** — `question`- and `hypothesis`-type statement annotations on a single paper's
`.source.md` sidecar. Each carries the same shape Phase 3a emits for all statement kinds: a
`TextQuoteSelector` whose `exact` is the **claim text** (the question/hypothesis span), a JSON
`TextualBody` (`{section, stance, subject?, object?, subject_concept?, object_concept?}`), and
a lifecycle `Status`.

**Produces** — `question` entities (`entities/questions/NNNN-slug.md`) and `hypothesis`
entities (`entities/hypotheses/NNNN-slug.md`), each a minimal **template-faithful** entity
(all required sections present, claim text in the lead section), plus the same two-carrier
provenance and sidecar backlink as 4a.

---

## The structural difference that drives the design

The two new target kinds differ from `proposition` in exactly the ways the kind descriptor
records:

| | proposition (4a) | question / hypothesis (4b) |
|---|---|---|
| identity strategy | `slug` (content-addressed) | **`numeric`** (`NNNN-slug.md`, atomic reservation) |
| model class | `PropositionEntity` (typed relational axes) | **generic `ProjectEntity`** (no subject/object/predicate fields) |
| default_status | `draft` | question→`active`, hypothesis→`proposed` |
| mint primitive | `write_entity_file` at `proposition:<slug>` | **`reserve_number_in_dir` + template render** |
| required sections | 3 (Claim/Evidence Summary/Caveats) | question 6, hypothesis ~9 |
| extra frontmatter | reasoning axes (left unset) | hypothesis `phase: candidate \| active` |

Two consequences:
1. **The 4a slug-collision hazard dissolves for numeric kinds.** `reserve_number_in_dir`
   locks on the *number* (atomic O_EXCL sentinel), writes the `.md` with mode `"x"` (never
   overwrites), recomputes on contention, and fails loud after `max_attempts`. Two different
   claims that share a descriptive slug simply get different numbers. `promote-slug-collision`
   stays **proposition-only**.
2. **`subject`/`object` from the statement body have no typed home** in a generic
   `ProjectEntity`, so they are **dropped** at mint (the claim text — title + lead section —
   carries the meaning). This is intentional; relational factoring is Phase 4c.

---

## Decision 1 — extend `science annotate promote`, don't add a command

`question`/`hypothesis` become promotable alongside `proposition` on the **existing**
`science annotate promote <source.md>` subcommand. The entire spine (read-only candidate list,
`--apply`, `--apply --input <edited.json>` override, output shape) is reused unchanged. The
promotable-kind gate generalizes to `{proposition, question, hypothesis}`; figurative
(metaphor/analogy) and the seeder kinds (entity/relation) stay non-promotable — no
truth/inquiry-apt target.

**MINT-row slug semantics differ by identity strategy** (the read-only candidate list cannot
know a numeric entity's final `NNNN` before `--apply` reserves it):
- A **slug-strategy MINT** (proposition) row carries a **full id** `proposition:<slug>` — the
  slug *is* the address, known pre-apply (4a behavior, unchanged).
- A **numeric-strategy MINT** (question/hypothesis) row carries only a **proposed descriptive
  slug** (the `-slug` suffix); the `NNNN-` number is allocated at `--apply` time by the
  reservation. The row's `kind` disambiguates which home it mints into.
- A **LINK** row (any kind) carries a **full same-kind entity id** (the resolved target).

Override (`--input`) accordingly: editing a numeric MINT row's slug changes only the
descriptive suffix; flipping a row to LINK requires a full **same-kind** id (a wrong-kind or
non-existent id fails loud).

## Decision 2 — kind-parameterized promotion (`PromotionTarget`, composition not hierarchy)

4a's engine is proposition-hardcoded (slug minting, `PropositionEntity`, slug-collision). 4b
factors the per-kind differences behind one small, concrete **`PromotionTarget`** — a
**frozen dataclass plus callables, no class hierarchy** (matching the codebase: 4a `promote.py`
uses frozen dataclasses; `Protocol`s like `ReadinessResolverProtocol` are the only abstraction
precedent — no inheritance trees).

```
PromotionTarget (frozen dataclass), one per promotable kind:
  kind / type / canonical_prefix      "question" | "hypothesis" | "proposition"
  default_status                      from the kind descriptor (active / proposed / draft)
  link_corpus(project_root)           -> { normalize_claim(title): [entity_id, ...] }  (THIS kind only)
                                         (a key mapping to >1 id is an ambiguous link target — Decision 4)
  mint(claim, slug, source_refs, as_of) -> new entity id   (writes the file)
```

Built by two concrete factories:
- **`proposition_target()`** — a **behavior-neutral extraction** of 4a's existing proposition
  path (slug-addressed `write_entity_file`, slug-collision guard, `PropositionEntity` mint).
  4a's full test suite is a **regression gate** for this refactor.
- **`numeric_target(kind)`** — owns numeric reservation + template-faithful render +
  lead-section insertion (Decision 3), for `kind ∈ {question, hypothesis}`.

The shared spine — queue, decide, provenance, idempotency, override — becomes kind-agnostic:
it asks the dispatched target to `mint` or links within that target's own `link_corpus`.

## Decision 3 — numeric, template-faithful mint (question & hypothesis)

A single numeric-mint helper inside `numeric_target`, parameterized by kind. Ordering is
chosen so **everything that can fail does so before any number is consumed**, and any failure
*after* reservation is loud with an explicit rollback (no silent fallback):

1. `slug = slug_for_claim_text(claim)` (reuse 4a's word-boundary slug + `len < 2` guard →
   skip `promote-claim-unsluggable`). **Before reservation.**
2. **Preflight the template (pure read, before reservation).** Confirm the kind's packaged
   template is renderable — it exists and its frontmatter + declared required sections parse
   (`Renderer` raises `EntityTemplateError` otherwise). No number is consumed. This moves the
   only realistic render failure out of the post-reserve window. **Render itself cannot run
   yet:** `Renderer` reads `id` from `{from: entity_id}` via `context.get(...)`, so an absent
   `entity_id` renders literal `id: null` (NOT a `{{}}` placeholder that could be substituted
   afterward). The real `entity_id` must therefore be present at render time, which is why the
   single render happens *after* reservation (step 4).
3. **Reserve atomically:** `number, local_part, path = reserve_number_in_dir(home_dir, slug,
   stub="", label=kind)`. The reservation commits an **empty placeholder `.md`** (`stub=""`)
   whose only job is to back the claimed number; the real content is written in step 5. Fails
   loud (`EntityCommandError`) after `max_attempts`.
4. **Render once, with the real id:** `Renderer().render(kind, fields={entity_id:
   f"{kind}:{local_part}", …})`, then insert the claim text into the lead section. After a
   successful step-2 preflight this render is total — only the step-5 IO write can realistically
   fail.
5. **Final write:** `_atomic_replace_text(path, rendered)` — overwrites the empty placeholder
   with the full entity. This is the **last step**.

   **Post-reservation failure policy (explicit, pick-one):** if step 4 or 5 raises (e.g. an IO
   error), the helper **unlinks the just-reserved placeholder `path` (intentional rollback) and
   re-raises loudly** (`PromotionApplyError`). The number+path were claimed by this process, so
   removing our own empty placeholder is safe and leaves the corpus clean and re-runnable — no
   orphaned half-entity, no silent swallow. Earlier candidates already applied in the run stay
   applied (idempotent re-run resumes), consistent with 4a's per-candidate model.

**Render fields** (`Renderer().render(kind, fields=…)` from `science_model.templates`, an
existing-but-unused helper — clean reuse, no new parallel machinery):

| field | value |
|---|---|
| `entity_id` | `<kind>:<NNNN-slug>` (from reservation) |
| `title` | the claim text (verbatim) |
| `status` | the kind's descriptor default (`active` / `proposed`) |
| `phase` | `"candidate"` for **hypothesis** (see below); omitted for question |
| `source_refs` | `[paper:<paper-id>, annotation:<entity-relpath>#<frag>]` (Decision 4) |
| `related` | `[]` |
| `created` / `updated` | `as_of` (today), passed explicitly (the templates pull `{from: created/updated}`) |

After render, the **claim text is inserted into the lead section** (question → `## Summary`,
hypothesis → `## Organizing Conjecture`) so the verbatim claim survives even if a curator later
edits the title. All other required sections render as their template placeholders (the entity
is structurally identical to a hand-authored stub, ready for a curator to fill).

**Hypothesis `phase: candidate`.** A hypothesis lifted from someone else's paper is by
definition a *trial framing the project has not yet committed to* — exactly the template's
definition of `candidate` ("trial framings being promoted to organize work but not yet
committed") versus `active` ("committed frames"). This is accurate classification from the
promotion *context*, not inference about content, and it keeps the project's committed
hypothesis frame uncluttered by external claims. A curator promotes `candidate → active`
deliberately. Questions have no `phase`.

**Reasoning/relational fields stay unset** (4c), consistent with 4a's discipline: the spine
mints minimal valid entities, never premature factoring.

## Decision 4 — mint-or-link, strictly kind-local dedup

For each promotable annotation, dispatch on its `annotation_type` to the matching target, then:

1. `key = normalize_claim(claim_exact)` — the **same** promotion-specific normalizer as 4a
   (`" ".join(t.casefold().split())`, deliberately separate from Phase-3 `_normalize_text`,
   which must not change).
2. If `key` matches exactly one existing entity **of the same kind** (the target's own
   `link_corpus` only) → **LINK** to that id.
3. If `key` matches **two or more** existing same-kind entities (the corpus already holds
   duplicate normalized titles) → **skip-and-count `promote-link-ambiguous`**. The shared spine
   never silently collapses an ambiguous target to one id; the curator resolves it by supplying
   an explicit same-kind id via `--input`. (Additive: this reason fires only when the corpus
   actually contains duplicate-title entities, so it does not alter 4a's tested single-match
   behavior — the proposition regression gate stays green.)
4. Else → **MINT** via that target.

**Dedup is target-local by construction:** a normalized `question` title can only link to an
existing question, never to a same-text proposition or hypothesis — each target's
`link_corpus` scans only its own kind's home. Cross-kind collisions are impossible.

## Decision 5 — provenance & idempotency (reuse 4a, generalized)

Unchanged two-carrier contract, now kind-agnostic:
- **Entity side:** minted entity lists `paper:<paper-id>` (→ `prov:wasDerivedFrom paper` via
  the resolver) and `annotation:<entity-relpath>#<frag>` (→ `prov:wasDerivedFrom annotation`
  via 4a's `graph/materialize` bypass branch + the `graph/migrate.py` `_audit_reference`
  non-entity skip — both already kind-agnostic).
- **Annotation side:** `sci:promotedTo "<kind>:<id>"` backlink (the value now holds any
  promoting kind's id, not just `proposition:`). Status untouched (promotion is a
  materialization fact, orthogonal to disposition).

**Idempotency** — the same two independent, order-free guards: an annotation is already
promoted iff its sidecar `promoted_to` is set **OR** its `annotation:` ref already appears in
some entity's `source_refs` (`derived_refs`). A second `--apply` is a genuine no-op; a
half-written pair still suppresses re-mint.

## Decision 6 — fail-loud reasons (updated set)

Skip-and-count per-annotation; hard-fail on structural problems (unchanged ethos):

- `promote-non-promotable-type` — metaphor/analogy/entity/relation (**renamed** from
  `promote-not-proposition-type`; clearer now that three kinds promote).
- `promote-inactive-status` — not `OPEN`/`ACK`. (all-kind)
- `promote-already-promoted` — backlink or derived entity present. (all-kind)
- `promote-claim-unsluggable` — claim cannot derive a stable slug (`len < 2`). (all-kind)
- `promote-link-ambiguous` — the claim's normalized title matches ≥2 existing same-kind
   entities; never silently collapsed, curator resolves with an explicit id via `--input`.
   (all-kind)
- `promote-slug-collision` — **proposition-only** (numeric kinds cannot collide).

A malformed/unparseable statement body remains a hard, loud failure (`PromotionReadError`),
not a skip.

---

## Architecture summary (files)

- **`annotation/promote.py`** — the bulk of the work: introduce `PromotionTarget` +
  `proposition_target()` (behavior-neutral extraction of the current proposition path) +
  `numeric_target(kind)` (reservation + template render + lead-section insertion + rollback);
  make `decide_candidates` / `apply_candidates` / the queue dispatch on `annotation_type` to a
  target; rename the skip reason.
- **`annotation/cli.py`** — `promote_cmd` gate widens to the three promotable kinds; no new
  flags.
- **Reused as-is:** `science_tool.entity_reservation.reserve_number_in_dir`,
  `science_model.templates.Renderer`, `science_tool.entities.slug_for_claim_text` /
  `append_entity_source_ref` / `write_entity_file`,
  `graph/materialize` annotation bypass, `graph/migrate.py` audit skip, the `sci:promotedTo`
  io round-trip. No changes to Phase-3 extraction or `_normalize_text`.

## Testing strategy

- **Behavior-neutral extraction:** the full Phase-4a proposition-promotion suite stays green
  after `proposition_target()` extraction (**regression gate**).
- **Numeric mint-or-link (per kind):** identical normalized claim → LINK to same-kind entity;
  novel claim → MINT a `NNNN-slug`; **cross-kind same-text does NOT link** (question vs
  proposition vs hypothesis with identical text → independent entities).
- **Ambiguous link target:** a corpus with two same-kind entities sharing a normalized title →
  a matching claim is skipped `promote-link-ambiguous` (never silently collapsed to one id);
  an explicit `--input` id resolves it.
- **Reservation under stress (riskiest new behavior):** existing-file cases (a number already
  taken → next number), and a post-reservation write failure → loud `PromotionApplyError` +
  the reserved placeholder is unlinked (no orphan); `max_attempts` exhaustion fails loud.
- **Template-faithful render:** minted question/hypothesis pass `validate` (all required
  section headers present); claim text appears in the lead section; hypothesis carries
  `phase: candidate`; question carries no `phase`; `status` = descriptor default.
- **subject/object dropped:** a statement body with `subject`/`object` mints an entity that
  carries neither as a field (claim still in title + lead section).
- **Provenance/idempotency parity:** q/h minted entity carries both refs; sidecar gains
  `sci:promotedTo "<kind>:<id>"`; status unchanged; second `--apply` is a no-op; half-written
  pair suppresses; materialize emits `wasDerivedFrom` for the annotation ref for q/h too.
- **Override (`--input`):** editing a numeric MINT row's descriptive slug changes the minted
  `-slug` suffix (number still allocated at apply); an edited `MINT`→`LINK <same-kind id>` is
  honored; a LINK target of the wrong kind or a non-existent id fails loud.
- **CLI round-trip:** `science annotate promote <path>` lists q/h candidates; `--apply` writes
  the entities + backlinks; malformed input fails loud.

## Out of scope (later slices)

- `predicate` / `polarity` / `claim_layer` / `identification_strength` synthesis (4c).
- Cross-paper evidence aggregation (`cito:supports`/`disputes`) and belief-layer wiring (4d).
- Embedding / paraphrase dedup.
- Figurative (metaphor/analogy) promotion — no truth/inquiry-apt target.
- Edges between promoted entities (hypothesis→question, proposition→hypothesis) — later.
- Any agent/LLM in the loop (4b is fully deterministic).
