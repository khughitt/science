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

A new derivation pass in `graph/materialize.py`. **Ordering is load-bearing: the pass
runs inside `_derive_phase`, after the emit phase has loaded propositions + provenance
and after `emit_source_snapshots`, but *before* `_derive_bears_on_layer`.** The virtual
`cito:supports`/`disputes` edges must exist before the bears-on derivation so they
participate in `sci:bearsOn` closure and the freshness/closure consumers that read it —
not only in `collect_evidence_units` (which reads the cito edges directly). Emitting the
pass after `_derive_bears_on_layer` would silently exclude the virtual evidence from
those derived layers.

The pass:

1. **Enumerate active promoted-statement assertions.** For each paper `.anno.trig`
   sidecar, read annotations and keep only those that are **active proposition
   assertions promoted to a proposition** — i.e. `annotation_type == "proposition"`,
   `status in {"open", "ack"}`, and `promoted_to` is set and
   `promoted_to.startswith("proposition:")` (resolves the scope question below).
   Inactive promoted annotations (`fixed`, `dismissed`, `superseded`) are **skipped**:
   their backlink remains useful history, but they no longer contribute belief.
   Annotations of type `question`/`hypothesis` (4b) legitimately carry
   `promoted_to = "question:…"` / `"hypothesis:…"` and are **skipped** silently — they
   are valid promotions, simply not literature evidence *for a proposition*. Each kept
   annotation yields a `(proposition, paper, stance)` triple. This is a bounded sidecar
   read that reuses the existing `read_sidecar` I/O. (The `.source.md`/`.anno.trig`
   sidecars already live inside entity roots; the markdown storage adapter already
   knows about `.source.md`.)

   **Scope rule (closed).** Only `annotation_type == "proposition"` annotations whose
   `promoted_to` targets a `proposition:` count. This keeps future relation/entity
   annotation types from accidentally becoming literature evidence. A *proposition*-type
   annotation whose `promoted_to` points at a **non-`proposition:`** target is a
   corruption and is an error (§6) — distinct from the benign skip of a
   question/hypothesis annotation.

2. **Resolve and verify the owning paper (ownership contract).** The candidate
   `paper:<citekey>` for an assertion is resolved **from the owning sidecar via the P1
   `TextSourceAdapter` contract** —
   `resolve_adapter(sidecar_markdown_path).source_ref(...)`. That is the default 4a
   path, but 4a also allowed an explicit `--paper-ref`, so Phase 4d must verify rather
   than blindly trust the adapter-derived id: the derived `paper:<citekey>` must appear
   in the target proposition's `source_refs` alongside the annotation ref. If it does
   not, the scanner reports an ownership mismatch (§6) instead of emitting evidence
   under the wrong paper. This keeps `wasDerivedFrom = paper:<citekey>` and
   `independence_group = literature-paper:<citekey>` aligned with the proposition
   provenance that promotion actually recorded. (A sidecar whose adapter cannot
   resolve a source ref is an error, not a silent skip — §6.)

3. **Collapse per `(proposition, paper, stance)`.** Multiple annotations from the
   same paper restating the *same proposition with the same stance* count once — a
   single paper cannot inflate corroboration by restating. Crucially the collapse key
   includes **stance**, so a paper that both asserts *and* negates the same
   proposition is **not** silently reduced to one winning stance (see §4 same-paper
   mixed stance).
4. **Emit a virtual `sci:EvidenceLine` node** per surviving assertion, plus a
   `cito:supports` / `cito:disputes` edge to the proposition, with explicit provenance
   metadata (§4 table). These virtual lines feed `collect_evidence_units` →
   `aggregate_belief` exactly like authored lines.

**Why virtual, not persisted files.** Materialize-derived nodes are the cleanest Half A:
deterministic, rebuildable from sidecars each build, and traceable to their source.
Persisting evidence-line markdown files would make derived evidence look authored,
pollute `entities/evidence-lines/`, and add write/idempotency/dedup burden that
re-derivation already obviates.

**Deterministic, collision-proof IDs.** The virtual line URI is
`evidence-line:lit-assertion/<digest>`, where `<digest>` is the **full SHA-256 hex**
of the canonical NUL-joined key `f"{proposition}\0{paper}\0{stance}"` (the proposition
ref, paper citekey, and stance token, each in its canonical string form). The full
digest is used — no truncation, so no collision policy is needed. The URI is
materialized **URI-only** (never written to `entities/evidence-lines/`) and clearly
namespaced apart from authored lines. The same assertion derives the same URI on every
build, so de-duplication across rebuilds and across multiple targets is automatic
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
  `independence_group=literature-paper:<citekey>`. The reducer then sees a single real
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
science annotate cross-paper-evidence [--source proposition:<slug>] [--root PATH] [--format table|json]
```

The `--source` option (optional) mirrors the sibling `ground-prose-decomposition`
command's surface for consistency across the `annotate` group; omitting it gives the
project-wide view.

- **With `--source proposition:<slug>`:** lists the derived units (paper, stance, edge,
  role/strength), the resulting belief magnitude, the `contested` flag, and any
  intra-paper mixed-stance `contested_group` flags. The belief verdict is computed by
  emitting the proposition's derived virtual lines into an in-memory graph and running
  the same `collect_evidence_units` → `aggregate_belief` path (no dependence on a built
  `graph.trig`).
- **Without `--source` (project-wide):** lists every proposition that gained literature
  belief, and every derivation error (§6) in **report mode** — without raising.

This is a diagnostic/reporting surface, not an authoring workflow.

## 6. Error handling — fail loud, via one shared scanner

`promoted_to` is now an **epistemic input**, not just UI metadata, so derivation
fails loud rather than silently dropping evidence. To reconcile "derivation raises"
(§3) with "the diagnostic lists all errors" (§5), both go through **one scanner with
two modes**:

- The scanner walks every candidate assertion and accumulates **all** offending
  records `(sidecar, annotation_id, reason)` — it does not stop at the first.
- **Materialize (strict mode):** if the accumulated list is non-empty, the derivation
  raises a single aggregate `CrossPaperEvidenceError` enumerating every offending
  record. The graph build fails loud, and the message names all problems at once (not
  fail-on-first).
- **Diagnostic (report mode):** `science annotate cross-paper-evidence` (no ref) runs
  the same scanner and prints the accumulated list **without raising**, so an operator
  can see and fix every stale/corrupt reference before the next build.

The offending conditions (all are corruptions of an epistemic input, never silent
skips). Note these are distinct from the **benign skip** of a `question`/`hypothesis`-
*typed* annotation, which is valid 4b output and never an error:

- A kept `proposition`-typed annotation whose `promoted_to = proposition:x` does not
  resolve to an existing entity (**stale ref**).
- A `proposition`-typed annotation whose `promoted_to` points at a **non-`proposition:`**
  target (e.g. `question:…` on a `proposition`-typed annotation) — a factoring
  corruption, distinct from a question/hypothesis-typed annotation legitimately
  targeting its own kind.
- A kept assertion with an unknown/invalid `stance` (closed vocabulary; out-of-vocab
  is corruption).
- A sidecar whose `TextSourceAdapter` cannot resolve a `source_ref` (paper id
  unresolvable — §3 step 2).
- A kept assertion whose adapter-derived `paper:<citekey>` is not present in the target
  proposition's `source_refs` (**ownership mismatch**). This can happen only if the
  original promotion used an explicit `--paper-ref` that diverges from the sidecar's
  adapter-derived owner, or if proposition provenance was edited afterward. In either
  case, deriving literature evidence under the adapter id would misattribute
  independence, so strict mode fails loud.

Inactive promoted annotations are not errors: `fixed`, `dismissed`, and `superseded`
proposition annotations are skipped because the annotation lifecycle has withdrawn them
from the active assertion set. The project-wide diagnostic may report them as skipped
rows for visibility, but they never emit virtual evidence.

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
  a group); deterministic full-SHA-256 URI derivation; paper-id resolution via the
  `TextSourceAdapter` contract is accepted only when the target proposition's
  `source_refs` also contain that `paper:<citekey>`.
- **Scope filter:** a `question`/`hypothesis`-typed annotation (4b output) is **skipped,
  not errored**; only `proposition`-typed annotations targeting `proposition:` are
  derived.
- **Lifecycle filter:** `open`/`ack` promoted proposition annotations derive evidence;
  `fixed`/`dismissed`/`superseded` promoted proposition annotations are skipped and do
  not affect belief.
- **Error scanner (both modes):** stale `proposition:x` target, a `proposition`-typed
  annotation targeting a non-`proposition:` ref, invalid `stance`, and an
  adapter-unresolvable sidecar, and a paper ownership mismatch each appear in the
  accumulated list; strict mode raises one aggregate `CrossPaperEvidenceError` naming
  **all** of them (not fail-on-first); report mode returns the same list without
  raising.
- **Ordering:** virtual `cito:supports`/`disputes` edges are present in the `sci:bearsOn`
  closure (proves the pass runs before `_derive_bears_on_layer`, not only feeding
  `collect_evidence_units`).
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
