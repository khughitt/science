# Entity Origin Provenance — Design (v1)

**Date:** 2026-07-03
**Status:** Design approved; implementation plan pending
**Scope:** `science` (CLI) + `science-model`; templates, JSON schemas, graph
materialization, and minimal write-path wiring.

## Motivation

Science aims to treat all epistemic entities equally and evaluate them on
**evidence** (and, eventually, plausibility) — never on *who* proposed them.
That principle is about *belief*. It is fully compatible with, and in fact
depends on, recording *where an idea came from*.

Today hypotheses and questions carry `source_refs` (a flat list of citekeys),
which cannot express:

1. Whether an idea originated with the **user**, the **AI assistant**, or the
   **literature** — and the fact that more than one of these can be true at
   once (e.g. "I proposed it, and it turns out Smith 2019 proposed it first").
2. The difference between the **original** source of an idea and later sources
   that merely **mention or cite** it.

Without this, a future idea-expansion workflow (`/science:explore_ideas`, a
separate spec) would launder AI- and literature-mined candidates into the
substrate with their origins erased, where they would *look* identical to
human-authored, well-established ideas. Origin provenance is what makes
unbiased idea expansion **safe and auditable**: we can generate freely because
we can always answer "where did this come from?", dedup against prior art, and
give correct credit.

**Provenance is metadata only. It must not affect evidential weight.**

## Non-goals (v1)

- The `/science:explore_ideas` generation workflow — a **separate** spec that
  will *consume* this model.
- Proposition coverage. Propositions already carry `wasDerivedFrom` +
  `reasoning_source` provenance; adding `origins` there risks double-tracking.
- Plausibility / priors modeling.
- Full qualified PROV-O (`prov:qualifiedAttribution`, discovery activities).
- A `role`/`restatement` lineage *inside* `origins` (original-vs-citing is
  handled structurally — see below).
- Backfilling origins onto existing project content (e.g. the current PAIS
  hypotheses). Those read as "origin unrecorded", which is honest.

## Core model

### Two axes: origination vs. discovery

- **Origination** — where the idea *came from*. Recorded in `origins`.
- **Discovery** — who *surfaced it* into the project. Recorded in `added_by`.

These are distinct. When the assistant surfaces a hypothesis it found in a 2019
paper, the **origin is the paper** (`literature`, Smith 2019); the assistant is
merely the discovery agent (`added_by`). The assistant is an *originator* only
when it genuinely reasons up something novel with no literature source. This
keeps the AI from being credited as originator of ideas it merely retrieved.

### Original vs. citing — expressed structurally

- **Originators** live in `origins`.
- **Citing/mentioning sources** stay in `source_refs` (unchanged).
- Therefore any referenced source *not* in `origins` is, by construction, a
  non-originating mention. No `role` field is needed.

## Data model (`science-model`)

Two new fields on the base `ProjectEntity`, alongside `source_refs`, both
optional with empty defaults:

```python
class OriginType(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    LITERATURE = "literature"


class OriginRecord(BaseModel):
    type: OriginType                 # required
    ref: str | None = None           # "paper:<key>" or "cite:<key>" for
                                     # literature; optional stable
                                     # name/agent-run id otherwise
    date: str | None = None          # "YYYY-MM-DD", format-validated
                                     # (kept as str to match created/updated)
    independent: bool = False        # this record converged on the idea
                                     # independently of the other origins
    note: str | None = None          # free text, e.g.
                                     # "user proposed 2026-05; Smith 2019 predates"
```

```python
# On ProjectEntity:
origins: list[OriginRecord] = Field(default_factory=list)
# Known originators or independent proposers of this entity. Provenance
# metadata only; MUST NOT affect evidential weight. These are known
# originator *claims*, not a guarantee of metaphysical first origin.

added_by: str | None = None
# Discovery stamp: who/what surfaced this entity into the project.
# e.g. "user", "llm:<model>:explore-ideas-v1". Mirrors reasoning_source.
```

### Base-model placement vs. v1 surface (scope)

The fields live on the **base `ProjectEntity`**, so every entity kind can
*technically* carry `origins`/`added_by`: generic loaders, inventory, `Entity`
parsing, validation, and graph materialization all flow through the base model
and will accept, validate, and materialize the fields on **any** kind. This is
intentional — parsing/validation/materialization is uniform.

What v1 restricts is the **active authoring surface**: only hypothesis,
question, topic, and theme get template scaffolding and an `add-*`/creation
prompt. A dataset (or any other kind) that carries a hand-authored `origins`
block is **valid and materialized**, just not scaffolded or prompted. No kind
*rejects* the fields.

### Field semantics (precise)

- `origins` records **known originator claims**, not a guarantee of the true
  first origin. A `user`/`assistant` origin may later be found to have literature
  antecedents — expressed by *adding* a `literature` record, not by rewriting.
- `independent: true` means **this record** arrived at the idea independently of
  the others in the list (convergent origination) — it does **not** assert
  anything about the entity as a whole.
- `added_by` may eventually want a companion `added_at`; v1 does **not** add it
  (the entity already has `created`/`updated`). Deferred, not rejected.

### Validation (model-level; fail loud, "explicit > defensive")

- `type == literature` ⇒ `ref` is **required**, and must be a **graph-visible
  literature reference** — `paper:<key>` (a paper entity) or `cite:<key>` (a
  BibTeX key). A bare/unprefixed key or any other prefix is **rejected**. See
  "Literature `ref` resolution" under graph materialization for why: a raw
  `smith2019` or a source-style ref would silently fail to materialize, erasing
  the origin. Model-level validation checks only the *prefix*; existence is a
  graph/health concern.
- `type == assistant` ⇒ `ref` optional but **encouraged** to carry a stable
  run/agent id when available.
- `date`, if present, matches `YYYY-MM-DD`.
- **No bare-string shorthand.** Every origin is an explicit object. (Unlike
  `discusses`, a bare citekey is ambiguous — it cannot say whether the source is
  an original literature origin, a later citing source, or plain support.)

### The multi-origin example

"I proposed it, and Smith 2019 predates it independently":

```yaml
origins:
  - { type: user, date: "2026-05-10" }
  - { type: literature, ref: "paper:smith2019", date: "2019-03-01",
      independent: true, note: "predates the user proposal; not derived from it" }
added_by: user
```

## Templates + schemas + reconciliation

- Add `origins: []` and `added_by:` to the frontmatter and
  `_template.frontmatter` mappings of the four templates: **hypothesis,
  question, topic, theme** — each with an explanatory comment.
- Edit **both** template copies — the root `templates/` and the packaged
  `science/model/src/science_model/templates/` — and keep them byte-mirrored
  (this repo has a known root↔packaged template-drift gotcha).
- Add `origins` and `added_by` to the renderer's **`VALID_FIELD_NAMES`**
  allowlist (`science-model/.../templates.py`). The `_template.frontmatter`
  `{ from: <field> }` mappings validate against this set — omit it and the
  templates fail to render.
- Add both fields to the JSON schemas backing the four v1 kinds
  (`overlay-*`, `mixin-topic-*`, `mixin-theme-*`), with schema **version bumps**
  where the schema is versioned. The additions are additive. **Not** in scope:
  `science-pkg-entity-*` (dataset/datapackage-specific) and other kind schemas —
  they get no v1 surfacing.
- Satisfy the **strict 3-way reconciliation gate** (Pydantic model ↔ templates
  ↔ JSON schemas) from the Kind Descriptor keystone: all three must agree or the
  build fails. **Caveat for the implementation plan:** because the fields sit on
  the base model, if the gate requires every base field to appear in a kind's
  schema, additional schemas (e.g. `science-pkg-entity-*`) may need the fields
  as a *mechanical* consequence — resolve this when writing the plan. Even if a
  schema must list them, no dataset template or prompt is added.

## Graph materialization (minimal PROV-O → `provenance` graph)

The graph already uses PROV-O (`prov:wasDerivedFrom`, `prov:wasAttributedTo`,
`prov:Entity`, a dedicated `provenance` graph). Origin materialization reuses it:

- Canonical agent URIs `sci:agent/user`, `sci:agent/assistant`, typed
  `prov:Agent`, emitted once.
- Each origin becomes a light **`sci:Origin`** node hung off the entity:

  ```turtle
  <entity> sci:hasOrigin [
      a sci:Origin ;
      sci:originKind "literature" ;                 # user | assistant | literature
      prov:wasDerivedFrom  <source-uri> ;           # literature origins
      # -- or --
      prov:wasAttributedTo <sci:agent/user> ;       # user / assistant origins
      prov:generatedAtTime "2019-03-01"^^xsd:date ; # when date present
      sci:independentOrigination true               # when independent
  ] .
  <entity> sci:addedBy "llm:<model>:explore-ideas-v1" .
  ```

  One reified node **per origin** so a per-origin `date` survives — but **no**
  `prov:qualifiedAttribution` / activity ceremony (the "full PROV-O" option we
  rejected).
- Register every new term — `sci:Origin`, `sci:hasOrigin`, `sci:originKind`,
  `sci:independentOrigination`, `sci:addedBy`, and the `sci:agent/*` URIs —
  wherever the graph export / metadata layer **enumerates** `sci:` predicates
  and classes (namespace bindings, any predicate allowlist / export type list),
  not merely at the emission site. Emitting a term the export layer doesn't know
  about is a silent gap.

### Literature `ref` resolution (important)

`source_refs` and `origins` deliberately diverge here. In `source_refs`,
`materialize.py` **skips** `cite:<key>` bibliography refs (`is_bibliography_
reference` → `continue`) — they never become graph edges. If origins reused that
path verbatim, every `cite:`-style literature origin would **silently vanish**,
erasing exactly the provenance we set out to record.

So origins defines its own resolution, and only two ref forms are accepted:

- **`paper:<key>`** — resolves to the paper **entity** URI via the existing
  resolver (the preferred form when a paper entity exists). Materializes as
  `prov:wasDerivedFrom <paper-entity-uri>` on the `sci:Origin` node.
- **`cite:<key>`** — a bibliography-only origin (common for mined review
  articles not yet imported as paper entities). Materialized as a stable
  `prov:Entity` bib node keyed by the BibTeX key (e.g. `sci:cite/<key>`),
  **unlike** `source_refs` which drops it. This keeps mined-but-not-imported
  literature origins graph-visible.

Anything else (bare key, other prefix) is a validation error (see model
validation above).

This makes the unbiased-audit queries answerable in SPARQL, e.g. "all
AI-originated hypotheses", "hypotheses with no recorded originator",
"literature-originated vs. user-originated mix".

## Write-path wiring (so the field is not inert)

A field that no normal write path populates is dead weight. Minimal wiring:

- `add-hypothesis` and `add-question` gain **one** elicitation step —
  "origin: user / literature / assistant?". For a literature origin the prompt
  accepts either a `paper:<key>` reference or a bare BibTeX key; the command
  **normalizes a bare key to `cite:<key>`** before storing, so it never writes
  the bare, validation-rejected form. It populates `origins` and sets
  `added_by`. Nothing else in those commands changes.
- Topic/theme creation gets the same minimal prompt.

## Health / validation surfacing

- **Unresolved `paper:<key>` origin `ref`** → checked with the **same
  seriousness** as an unresolved `source_refs` entry (reuse the existing
  reference-resolution machinery and its severity).
- **Unknown `cite:<key>` origin `ref`** → checked against the project
  bibliography (`bibliography.load_bib_keys` → `papers/references.bib`) and
  flagged at the **same seriousness** when the key is absent. Materialization
  still mints a stable bib URI regardless (so nothing is silently dropped), but
  health must **not** treat every `cite:<key>` as valid — otherwise a typo like
  `cite:Smtih2019` becomes a graph-visible but bogus origin.
- **Soft warn:** `independent: true` on a single-origin entity (the flag is only
  meaningful with ≥2 origins).
- Entities with empty `origins` are **not** an error — "origin unrecorded" is a
  valid, honest state.

## Migration

None required. Both fields are optional with empty defaults; existing entities
(including the current PAIS hypotheses) read as "origin unrecorded". Backfilling
project content is out of scope for this toolkit spec and is a downstream
project activity (and a natural byproduct of the future explore-ideas workflow).

## Testing

- **Model:** `OriginRecord` validation — literature-needs-`ref`, `date` format,
  `OriginType` enum; multi-origin round-trip; no-bare-string rejection.
- **Frontmatter:** parse/serialize `origins` (list of objects) and `added_by`.
- **Graph:** golden triples for each origin type, `date`, `independent`, and
  `added_by`; literature-`ref` resolution to a source/paper URI.
- **Reconciliation gate:** stays green after the field additions.
- **Health:** unresolved literature `ref` finding (mirrors `source_refs`
  severity); soft warn on lone-origin `independent`.

## Open follow-ups (out of scope, noted for the record)

- `/science:explore_ideas` workflow (next spec) — the primary consumer.
- Optional `added_at` companion to `added_by`.
- Proposition-level origin, if ever wanted, must reconcile with the existing
  `wasDerivedFrom` / `reasoning_source` provenance rather than duplicate it.
