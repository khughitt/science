# Multi-surface fact inventory

**Date:** 2026-07-25 (rev 2 — corrected after review; rev 1's headline was wrong, see §Corrections)
**Status:** Audit complete. Input to the system-cohesion design program; no rulings made here.
**Method:** Every quantity below was produced by running code against the shipped profiles and
models. Where a claim is argued rather than measured it is marked **(judgment)**.


> **Counts re-derived 2026-07-25 against `d9e79f91`** while designing S1a. The declared-kind
> count is **50**, not the 53 this document originally used, and three derived figures were
> wrong independently of that: typed bindings are **20** (not 17), kinds with no `home` are
> **14** (not 17), and kinds with an open status set are **16** (not 19). All figures below
> are corrected. See [`2026-07-25-s1a-reconciliation-gate-design.md`](2026-07-25-s1a-reconciliation-gate-design.md) §1.1
> for the full partition.

## Why this exists

Science grew by solving real problems as they arrived. Each solution needed some fact about the
system — what a kind is called, where it lives, what states it may hold, which edges it may
carry — and some took the cheapest route: store it where it is needed.

The resulting risk has one shape: **a fact answered by more than one surface.** Where nothing
compares the answers, they drift silently.

The important correction from review: **Science already has working mechanisms for exactly this,
and they are good.** The problem is not absence. It is *coverage* — the mechanisms cover one
kind and one fact.

### The instance that prompted it

`fb-2026-07-11-017` closed on 2026-07-15 with a check that errors on a top-level `supersedes:`.
The check told authors to re-author as a `relations:` entry — a form the graph rejects for most
kinds. Fixing that (`6cb39f23`) prompted this audit.

## The inventory

| # | Fact | Surfaces | Status |
|---|---|---|---|
| F1 | What fields may a kind carry? | 3 | reconciled for **1 of 50** kinds; schema covers 5 (so 1 of 5 *possible*) |
| F2 | Can this kind be superseded? | 4 | one direction **ratcheted**; the reverse is unguarded |
| F3 | Lineage, amendment, identity, archive | 7 fields | **not one fact** — needs a taxonomy |
| F4 | What state is an entity in? | 5 axes | D1/D2 **enforced** by schema for hypothesis |
| F5 | Where does a kind's files live? | 3 | 36/50 declare a home |
| F6 | How is an entity named? | 8 | no divergence measured |
| F7 | How is a link authored? | 6 | redundancy; divergence **not** measured |
| F8 | How good is a claim? | 5+ | projections already computed at render time |
| F9 | Relation endpoint admissibility | 2 mechanisms | **representation**, not a second authority |
| F10 | Where is an inquiry authored? | 2 | documented duality; divergence not measured |

---

### F1 — What fields may a kind carry?

| Surface | Kinds covered | What it declares |
|---|---|---|
| `EntityKind` descriptor | **50 / 50** | 15 metadata fields. **No field schema.** |
| Pydantic classes | **20 / 50** have an explicit binding | field types, on a 67-field base |
| JSON Schema mixins | **5 / 50** (dataset, hypothesis, paper, theme, topic) | versioned fields, `allOf`, conditional invariants |

**Rev 1 got the divergence badly wrong.** It reported "17 fields the Pydantic model has never
heard of." Measured correctly, the hypothesis mixin's 39 `properties` keys are:

```
22  admitted fields
17  FORBIDDEN — the property schema is literally `false`
```

The 17 include `phase`, `disposition`, `role`, `belief_state`. They are not fields the model is
missing; they are fields the schema **rejects outright**. Their absence from the model is the
design working, not drift.

Of the 22 admitted, **20 are on the model**. The 2 that are not —
`required_capabilities`, `capability_scope` — are a *documented, named exception* in
`model/tests/test_hypothesis_entity.py`, with the reader that consumes them identified and an
explicit rule against the set growing.

**D3 point 4 is implemented.** `test_hypothesis_entity.py` performs the field-by-field
reconciliation, deriving admitted fields from the **composed** profile (base ∪ mixin, minus
forbidden). Rev 1 derived from the mixin alone — the exact error that file's own comment warns
about: *"Deriving this from the mixin ALONE is how `description` hid for four drafts."*

**The real gap is coverage.** Grepping for the reconciliation pattern: `hypothesis` has it.
`dataset`, `paper`, `theme`, `topic` have schema tests that do **not** reference `model_fields`
— they test the schema, not schema↔model agreement. So:

- schema mixins: **5 / 50** kinds
- schema↔model reconciliation: **1 / 50** kinds — but only **5** kinds have two authorities to reconcile

That is a strong pattern applied narrowly, which is a much better starting position than a
missing mechanism.

### F2 — Can this kind be superseded?

| Surface | Answer | Mechanism |
|---|---|---|
| Status vocabulary | 18 kinds | `EntityKind.statuses ∋ "superseded"` |
| Relation admissibility | 9 kinds | `allowed_kind_pairs` on `supersedes` |
| `mark_superseded` policy | 18 kinds | `_supports_superseded` (consolidation.py:111) |
| Validator remediation | was 52 | fixed 2026-07-25 to derive from the relation |

**This is guarded in one direction.** `model/tests/test_supersedable_gate.py` derives the
mismatch — kinds declaring `superseded` that cannot author the canonical edge — and ratchets it
with a **subset** assertion, deliberately chosen so the 12 known half-wired kinds can be repaired
without failing the suite. It is declared, frozen debt with a guard, not silent drift. Rev 1's
"nothing noticed" framing was wrong; that test's comment says plainly that nothing noticed
*until it existed*.

**The reverse direction is unguarded, and is a real finding.** The gate asserts
`declares ⇒ relation_allows`. It does not assert `relation_allows ⇒ declares`. Three kinds —
`story`, `validation-report`, `workflow-run` — can author the edge but declare no `superseded`
status, so a real authored lineage can never reach the entity. `consolidation.py:105-111`
documents this and *skips* those kinds defensively rather than resolving it.

### F3 — Lineage, amendment, identity, and archive are four facts, not one

**Rev 1 listed seven "spellings of 'this replaced that'". That was a category error**, and it
made rev 1's proposal to delete six of them unsafe. Measured semantics:

| Field | What it actually means |
|---|---|
| `relations:` + `sci:supersedes` | "A newer entity **replaces** an older as canonical" |
| `sci:amends` | "revises, narrows, qualifies, or extends **without replacing**" |
| top-level `supersedes:` | non-materializing; genuinely dead (now flagged) |
| `superseded_by` | **derived inverse**, required by D5 |
| `resynthesized_into` | one-to-**many** lineage (a split), not replacement |
| `deprecated_ids` | **identity resolution** — prior ids for the *same* entity |
| `consolidated_into` | **archive** digest membership |

Only the third is clearly disposable. The rest express different relations between different
things. **F3 needs a semantic taxonomy and an ownership table before any deletion can be
specified.**

### F4 — What state is an entity in?

Five axes are in use: `status`, `phase`, `verdict`, `disposition`, `role`. (Rev 1 said "four"
while listing five.)

`EntityKind` declares one (`statuses`): 34/50 kinds declare a vocabulary, **16 have an open set**.
23 distinct status tokens exist corpus-wide.

**But the other axes are not undeclared drift — for hypothesis they are explicitly forbidden.**
`mixin-hypothesis-2.0` sets `phase`, `disposition`, and `role` to `false`. That is D1 (status is
the lifecycle) and D2 (delete `disposition`) being *enforced at the schema*. Rev 1 read the
forbiddance as a declaration and concluded the rulings hadn't landed. They had.

What remains open is narrower: whether the *other 52 kinds* enforce the same, given only 5 have
schemas at all.

### F5 — Where does a kind's files live?

`EntityKind.home` covers **36/50** kinds; 14 declare none; one (`research-question`) declares a
home that is a *file*, not a directory. `paths.py` carries an `entities_dir` default and the
`directory_structure` check has its own view. No divergence measured between them. **(judgment:
worth an audit, not yet a finding)**

### F6 — How is an entity named?

`id`, `canonical_id`, `aliases`, `deprecated_ids`, `file_path`, `local_path`,
`primary_external_id`, plus citekeys, derived slugs, and the `mappings.yaml` alias table. No
divergence measured. Listed because identity is load-bearing for resolution. **(judgment)**

### F7 — How is a link authored?

Six surfaces: `related:`, `relations:`, `source_refs:`, `discusses:`,
`knowledge/sources/local/relations.yaml`, `.edges.yaml` sidecars.

Redundancy of *spelling*. **No conflicting authority has been demonstrated.** Whether these
disagree is unmeasured, and convergence should be conditional on an audit that shows they do.
**(judgment)**

### F8 — How good is a claim?

`belief_state` (4), verdict tokens (5), `derived_edge_status` (5), plus `claim_layer`,
`identification_strength`, `polarity`, `evidence_stance`, `strength`, `confidence`.

Much of this is legitimate factoring: a verdict concerns a *test*, `belief_state` a
*proposition*. **And `derived_edge_status` is already computed at render time** — `render.py:171`
computes it, `proposition_edges.py:11-12` states it is "never carried here", and `render.py:333`
strips it before output. Rev 1 called it a stored projection. It is not.

The residual concern is only that nothing *forbids* authoring `edge_status`. **(judgment)**

### F9 — Relation endpoint admissibility (representation, not authority)

23 relation kinds; 2 use `allowed_kind_pairs`, 21 use `source_kinds` × `target_kinds`.

**By this document's own definition this is not a multi-surface fact** — both are read through
`relation_allows_kinds`, which is a single authority. Recorded as a *representation* finding: the
Cartesian form silently admits every combination, which is why the two relations with large
endpoint sets needed the precise form. Relabelled from rev 1.

### F10 — Where is an inquiry authored?

Two surfaces: `entities/inquiries/<slug>.md` and `entities/patches/<slug>.md` with
`patch_type: inquiry`. The user guide assigns them distinct roles and states the compiled graph
is a view, not a second store. **No divergence measured.** **(judgment)**

## The meta-finding (corrected)

Rev 1 claimed there is no check for declaration multiplicity and that every instance was found by
a person tripping over it. **Both are false.** Two mechanisms exist, both well built:

- `test_hypothesis_entity.py` — full schema↔model field reconciliation, composed-profile-derived.
- `test_supersedable_gate.py` — derives the F2 mismatch and ratchets it as declared debt.

The honest finding is narrower and more actionable:

> **The mechanisms are right and their coverage is 1 kind and 1 fact.** The program is to
> generalize a working pattern, not to build a missing one.

## Corrections from review (rev 1 → rev 2)

| Rev 1 claim | Reality |
|---|---|
| "17 fields the model has never heard of" | 17 are **forbidden** by the schema; real gap is 2, documented |
| "D3 point 4 has no implementation" | implemented in `test_hypothesis_entity.py` for hypothesis |
| "nothing binds the two declarations" | bound for hypothesis; **unbound for the other 52** |
| "seven spellings of 'this replaced that'" | four distinct facts; only one field is clearly dead |
| "four state axes" | five, and three are schema-**forbidden** for hypothesis (D1/D2 enforced) |
| "`derived_edge_status` is stored" | computed at render time and stripped before output |
| "47 CLI groups" | **46** top-level entries = 39 groups + 7 single commands |
| F2 "nothing noticed" | ratcheted by `test_supersedable_gate.py`; the *reverse* direction is unguarded |

**Root cause of the errors:** rev 1 derived admitted fields from the mixin alone and counted
`false` property schemas as declarations. The file it should have read first warns against
exactly that. Grounding the claim in the existing tests — rather than in a fresh script — would
have caught all of it.

## Scope and honesty

- A broad sweep, not an exhaustive audit. Facts not listed are unexamined, not cleared.
- Counts run 2026-07-25 against local `main` at `87ac7337`.
- **Measured divergence: F1 (coverage), F2 (reverse direction), F5 (partial declaration).**
  F3 is a taxonomy problem. F6–F10 are redundancy or representation with no demonstrated
  divergence — that distinction must survive into the design.
- Nothing here is a ruling.

## What this does not cover

The CLI surface, the checking/reporting systems, test-suite organisation, and the
commons/project boundary beyond its entity-schema aspect.
