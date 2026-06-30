# Proposition Cross-Paper Evidence (Phase 4d, Half A) — Design

**Date:** 2026-06-30
**Status:** Design (approved in brainstorming; awaiting spec review before plan)
**Kind:** Feature design. Phase 4d of the lit-annot / sub-article-annotation arc
(follows 4a statement→proposition promotion, 4b question/hypothesis promotion,
4c proposition reasoning synthesis).

> **Scope note.** Phase 4d as originally framed (4c design §13) covers two
> semi-independent halves: **(A) cross-paper evidence aggregation / belief over
> synthesised propositions**, and **(B) reconciling factorizations proposed from
> different papers for the same proposition.** This design covers **Half A only**.
> Half B (factorization reconciliation, paraphrase/embedding dedup) is deferred to
> a later phase (4e).

---

## 1. Problem

After 4a–4c, a proposition promoted from *N* papers is **one entity carrying *N*
provenance refs but zero belief support**. 4a's mint-or-link spine already collapses
"the same proposition asserted by several papers" to a single `proposition:<slug>`
entity and accrues each contributing `paper:<citekey>` and `annotation:<id>` onto its
`source_refs`. But promotion is deliberately *no-inference*: it writes **provenance
only**, never an evidence-line. The belief engine
(`science/src/science_tool/graph/belief.py`) counts support/dispute **only** from
`cito:supports` / `cito:disputes` edges whose subject is typed `sci:EvidenceLine`.
A paper-promoted proposition has no such edges, so `aggregate_belief` returns empty
support and the proposition reads as ungrounded — even when a dozen papers assert it.

**Goal:** make a proposition's belief reflect *how many independent papers assert it,
and whether they agree*, by deriving literature evidence units from the existing
promoted-statement provenance. The proposition stays the belief-bearing entity; paper
statements become evidence units; the existing
`EvidenceLine → cito:supports/disputes → proposition` path does the belief work,
unchanged.

## 2. Model alignment

This is consistent with the larger epistemic model and requires **no change to the
belief engine**:

- Propositions remain the belief-bearing entities.
- A paper *asserting* a proposition is **literature**-type evidence — it can
  corroborate, but (per §5) cannot manufacture empirical-grade belief.
- Evidence is **materialize-time derived state**, not authored files — mirroring the
  existing `derive_bears_on_from_typed_edges` and snapshot/source-change derivation
  passes. The graph is the derived projection; the sidecars are the source of truth.

## 3. Architecture — virtual evidence lines, derived at materialize time

A new derivation pass in `graph/materialize.py`, running after propositions and
provenance are loaded, alongside the existing `derive_*` passes:

1. **Enumerate promoted-statement assertions.** For each paper `.anno.trig` sidecar,
   read annotations whose `promoted_to` is set. Each yields a
   `(proposition, paper, stance)` triple. This is a bounded sidecar read that reuses
   the existing `read_sidecar` I/O; only annotations with a `promoted_to` backlink
   participate. (The `.source.md`/`.anno.trig` sidecars already live inside entity
   roots; the markdown storage adapter already knows about `.source.md`.)
2. **Collapse per `(proposition, paper, stance)`.** Multiple annotations from the
   same paper restating the *same proposition with the same stance* count once — a
   single paper cannot inflate corroboration by restating. Crucially the collapse key
   includes **stance**, so a paper that both asserts *and* negates the same
   proposition is **not** silently reduced to one winning stance (see §4 same-paper
   mixed stance).
3. **Emit a virtual `sci:EvidenceLine` node** per surviving assertion, plus a
   `cito:supports` / `cito:disputes` edge to the proposition, with explicit provenance
   metadata (§4 table). These virtual lines feed `collect_evidence_units` →
   `aggregate_belief` exactly like authored lines.

**Why virtual, not persisted files.** Materialize-derived nodes are the cleanest Half A:
deterministic, rebuildable from sidecars each build, and traceable to their source.
Persisting evidence-line markdown files would make derived evidence look authored,
pollute `entities/evidence-lines/`, and add write/idempotency/dedup burden that
re-derivation already obviates.

**Deterministic, collision-proof IDs.** The virtual line URI is
`evidence-line:lit-assertion/<hash(proposition, paper, stance)>`, materialized
**URI-only** (never written to `entities/evidence-lines/`) and clearly namespaced
apart from authored lines. The same assertion derives the same URI on every build,
so de-duplication across rebuilds and across multiple targets is automatic
(`collect_evidence_units` de-dupes lines by URI).

## 4. Stance → edge & evidence metadata

Each derived virtual line carries explicit, real-vocabulary metadata
(`EvidenceRole`, `EvidenceStrength`, `IndependenceTag` are existing model enums):

| stance | edge | `evidence_type` | `evidence_role` | `strength` | `independence` | `independence_group` |
|---|---|---|---|---|---|---|
| `asserted` | `cito:supports` | `literature` | `proxy_support` | `moderate` | `independent` | `literature-paper:<citekey>` |
| `negated` | `cito:disputes` | `literature` | `proxy_support` | `moderate` | `independent` | `literature-paper:<citekey>` |
| `hypothesized` | `cito:supports` | `literature` | `background_constraint` | `weak` | `independent` | `literature-paper:<citekey>` |
| `open` | *(skip — a question, not an assertion)* | — | — | — | — | — |

`stance` is the existing closed vocabulary on the statement candidate
(`{asserted, negated, hypothesized, open}`); `section` is **not** consumed in Half A
(section→strength grading is deferred — see §7). The `independence_group` token is
keyed per paper (`<citekey>` matches the `wasDerivedFrom = paper:<citekey>` provenance).
It is global, but `collect_evidence_units` reduces belief **per target proposition**, so
a paper that asserts many propositions contributes at most one support + one dispute unit
to *each* proposition's reduction — there is no cross-proposition interference.

### Consequences (all from the unchanged engine)

- **Corroboration.** *N* distinct papers asserting a proposition produce *N*
  independent support units (distinct `independence_group`s, one per paper), lifting
  the proposition `speculative/fragile → supported`.
- **Different-paper conflict.** When some papers support and others dispute, the
  surviving dispute unit causes `aggregate_belief()` to set `contested=True`. Because
  the supporting and disputing units belong to **different** papers — and therefore
  **different `independence_group`s** — this is *not* a `contested_group`. It is a
  general contested verdict, surfaced via the `BeliefResult.contested` flag.
- **Same-paper mixed stance** (the explicit semantic fork). The collapse key includes
  stance, so a paper with both an `asserted` and a `negated` annotation on the same
  proposition emits **both** a support and a dispute unit, sharing one
  `independence_group=literature-paper:<id>`. The reducer then sees a single real
  group holding both a support winner and a dispute winner → it records a genuine
  **`contested_group`**, and does **not** count the paper as two independent
  corroborations. No silent winner-pick; the diagnostic (§5) reports the intra-paper
  ambiguity.
- **Ceiling — literature cannot reach `well_supported`.** `well_supported` requires a
  clean qualifying `direct_test` (`is_qualifying_direct_test`, role-gated). Derived
  literature lines carry `proxy_support` / `background_constraint`, never
  `direct_test`, so cross-paper corroboration lifts a proposition to **`supported`**
  but never to `well_supported` absent empirical/direct-test evidence. This is the
  intended epistemic shape: many papers stating a claim is real corroboration, but it
  is not a substitute for a test.

## 5. User-facing surface

Because the evidence is derived, there is **nothing to author**. The derived lines
flow automatically into `science validate`, P3 proposition grounding, and P4 prose
health. One new **read-only diagnostic** command is the window into this otherwise-
invisible derived state:

```
science annotate cross-paper-evidence <proposition-ref> [--format table|json]
```

- **With a proposition ref:** lists the derived units (paper, stance, edge,
  role/strength), the resulting belief magnitude, the `contested` flag, and any
  intra-paper mixed-stance `contested_group` flags.
- **Project-wide (no ref):** lists every proposition that gained literature belief,
  and every **stale `promoted_to`** error (§6).

This is a diagnostic/reporting surface, not an authoring workflow.

## 6. Error handling — fail loud

`promoted_to` is now an **epistemic input**, not just UI metadata, so derivation
fails loud rather than silently dropping evidence:

- A sidecar `promoted_to=proposition:x` where `x` does not resolve to an existing
  entity → raise during derivation (a project-wide diagnostic enumerates all such
  stale references).
- A `promoted_to` pointing at a non-`proposition` entity → raise.
- An annotation with `promoted_to` set but an unknown/invalid `stance` → raise
  (stance is a closed vocabulary; an out-of-vocab value is a corruption, not a skip).

## 7. Non-goals (deferred to Phase 4e or later)

- **Factorization reconciliation (Half B)** — reconciling propositions that are the
  same claim factored differently `(subject, predicate, polarity, object)`, or minted
  separately because 4a's precision-first dedup under-linked paraphrases.
- **Paraphrase / embedding dedup** of propositions.
- **Citation-graph independence.** Each paper is treated as an independent source;
  detecting papers that merely cite a shared primary source is out of scope.
- **Promoting `identification_strength`** (left to the template default).
- **Persisted evidence-line files.** Derived evidence is URI-only.
- **`section`→strength grading.** Half A is stance-aware only; using `section`
  (results/methods vs intro/abstract) to grade evidence strength is a later refinement.

## 8. Testing

- **Unit:** stance→edge/metadata mapping; the `(proposition, paper, stance)` collapse
  (same paper + same stance → one unit; same paper + mixed stance → two units sharing
  a group); deterministic URI derivation; stale-`promoted_to` fail-loud; non-`proposition`
  target fail-loud; invalid-stance fail-loud.
- **Belief integration:** different-paper support+dispute → `contested=True` without a
  `contested_group`; same-paper mixed stance → a real `contested_group`; literature-only
  support capped below `well_supported`.
- **End-to-end** (per the real-data scale lesson — exercised on a real multi-paper
  fixture, not a stub): persist two papers' `.source.md` → extract → promote both
  asserting + a third disputing the same proposition → materialize → assert the
  proposition's belief magnitude, `contested` verdict, and the
  `cross-paper-evidence` diagnostic output.
- **Behavior-neutral guarantee:** no proposition in the current corpus has a resolved
  `promoted_to` with a non-`open` stance, so zero virtual lines are derived and the
  full belief regression net stays green until the feature is exercised.
