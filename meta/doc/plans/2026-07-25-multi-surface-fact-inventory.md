# Multi-surface fact inventory

**Date:** 2026-07-25
**Status:** Audit complete. Input to the system-cohesion design program; no rulings made here.
**Method:** Every quantity below was produced by running code against the shipped profiles and
models, not read out of documentation. Where a claim is argued rather than measured it is
marked **(judgment)**.

## Why this exists

Science grew by solving real problems as they arrived. Each solution needed some fact about the
system — what a kind is called, where it lives, what states it may hold, which edges it may
carry — and each took the cheapest route to that fact: store it where it is needed. The second
consumer copied rather than reached, because reaching requires a layer that may not exist yet.

The result is a recurring defect with one shape: **a fact answered independently by more than
one surface, with nothing comparing the answers.** The copies drift silently. Every instance
found so far was found by a person tripping over it, not by a check.

This document inventories those facts. It is deliberately descriptive — the design work of
deciding who should own each one comes after.

### The instance that prompted it

`fb-2026-07-11-017` closed on 2026-07-15 with a check that errors on a top-level `supersedes:`
key, correctly, because it materializes no triples. The check told authors to re-author it as a
`relations:` entry — a form the graph rejects for most kinds. Fixing that (`6cb39f23`) surfaced
the general pattern: **four** surfaces answer "can this kind be superseded", and no two agree.

## The inventory

Each row is one question the system must answer. "Surfaces" counts places that answer it
independently — not places that read a shared answer.

| # | Fact | Surfaces | Divergence observed |
|---|---|---|---|
| F1 | What fields may a kind carry? | 3 | schema covers 5/53 kinds; model covers 17/53; descriptor covers 0 |
| F2 | Can this kind be superseded? | 4 | 18 vs 9 vs 18 vs (was) 52 |
| F3 | How is "this replaced that" spelled? | 7 | 5 of 7 spellings are not model fields |
| F4 | What state is an entity in? | 3+ | 4 state axes exist; 1 is declared in the profile |
| F5 | Where does a kind's files live? | 3 | 36/53 declare a home; 1 home is a file, not a directory |
| F6 | How is an entity named? | 8+ | — **(judgment: not yet shown to diverge)** |
| F7 | How is a link between entities authored? | 6 | — **(judgment: redundancy, not measured drift)** |
| F8 | How good is a claim? | 5+ | one is self-described as a "lossy compatibility projection" |
| F9 | Which relations may a kind participate in? | 2 mechanisms | 21 relations use the loose form, 2 the precise one |
| F10 | Where is an inquiry authored? | 2 | documented in the user guide as a known duality |

---

### F1 — What fields may a kind carry?

**The most consequential row.** Three systems describe entity shape, and none covers the corpus.

| Surface | Kinds covered | What it declares |
|---|---|---|
| `EntityKind` descriptor (`profiles/core.py`) | **53 / 53** | 15 metadata fields — home, category, statuses, prefix. **No field schema.** |
| Pydantic classes (`science_model/entities.py`) | **17 / 53** have a subclass | field types, on a **67-field base** every kind inherits whole |
| JSON Schema mixins (`schemas/mixin-*.json`) | **5 / 53** (dataset, hypothesis, paper, theme, topic) | versioned fields, `allOf` composition, conditional invariants |

Measured divergence, `hypothesis`:

```
mixin-hypothesis-2.0 properties: 39
HypothesisEntity fields:         74
shared:                          22
only in the schema:              17   phase, disposition, belief_state, role,
                                      evidence_stance, promotion_criteria, ...
```

36 of 53 kinds have no type of their own, so a `topic` formally carries `parent_dataset` and
`accessions` from the shared base.

**This is already ruled on.** The D5 design (`docs/plans/2026-07-12-authoritative-entity-schema-design.md`
§2) identified exactly this, named the JSON Schema system as already authoritative, and ruled
**converge, do not invent a third**. D3 was adopted with a five-point contract: schema validates
first, Pydantic is a projection built after, projections preserve extension fields, **a CI
reconciliation check verifies every projected field against the effective composed schema**, and
invariants JSON Schema cannot express are enumerated escape hatches. D3 explicitly **rejects
generating** one system from the other.

**What shipped and what did not.** The silent-drop symptom is fixed: `Entity` moved from
`extra="ignore"` to `extra="allow"`, so `phase`, `role`, `disposition` now survive
`model_validate` instead of vanishing. Verified. But:

- **D3 point 4 has no implementation.** No test or check compares composed schema properties to
  Pydantic model fields. `read_effective_frontmatter_fields` exists and is called by exactly one
  CLI report (`entity sections`, meta D-011) and one model test — nothing gates on it.
- **Schema coverage stalled at 5 kinds.** The system to converge *on* describes under 10% of the
  corpus.

So the drift is no longer silent at the *value* layer, but nothing binds the two *declarations*.
That unbuilt clause is the single highest-leverage item in this inventory. **(judgment)**

### F2 — Can this kind be superseded?

| Surface | Answer | Mechanism |
|---|---|---|
| Status vocabulary | **18 kinds** | `EntityKind.statuses ∋ "superseded"` |
| Relation admissibility | **9 kinds** | `allowed_kind_pairs` on the `supersedes` RelationKind |
| `mark_superseded` stamping policy | **18 kinds** | `_supports_superseded` reads `_STATUS_VALUES` (consolidation.py:111) |
| Validator remediation | was **52 kinds** | `_LEGIT_TOP_LEVEL` — fixed 2026-07-25 to derive from the relation |

Two live consequences:

- **12 dead-letter terminals.** `decision, inquiry, mechanism, method, observation, plan,
  pre-registration, proposition, synthesis, theme, topic, workflow-step` each declare a
  `superseded` status they cannot legitimately reach, because no canonical edge can exist for
  them. The RelationKind comment calls this set "declared, frozen debt" — implementation history
  stored where a rule belongs.
- **3 unstampable kinds.** `story`, `validation-report`, `workflow-run` can author the edge but
  declare no `superseded` status, so a real lineage never reaches the entity.
  `consolidation.py:105-111` documents this and *skips* them defensively rather than resolving it.

`core.py:729-745` records the same disagreement being found and repaired **by hand for
`hypothesis`** — one kind, not the class. This is the third such repair.

### F3 — How is "this replaced that" spelled?

Seven spellings, two of which are declared model fields:

| Spelling | Declared on `Entity`? | Modules referencing |
|---|---|---|
| `relations:` + `sci:supersedes` | n/a (canonical edge) | 15 |
| top-level `supersedes:` | no | 15 |
| `superseded_by` | no | 14 |
| `resynthesized_into` | no | 7 |
| `replaced_by` | **yes** | 6 |
| `amends` | no | 6 |
| `consolidated_into` | no | 4 |
| `deprecated_ids` | **yes** | 5 |
| `status: superseded` (terminal) | via `status` | — |

### F4 — What state is an entity in?

`EntityKind` declares exactly one state axis: `statuses`. 34/53 kinds declare a vocabulary;
**19 have an open set** (no declared vocabulary at all). 23 distinct status tokens exist
corpus-wide.

But four state axes are in use. `mixin-hypothesis-2.0` declares `status`, `phase`, `verdict`,
`disposition`, and `role`. Of these, only `status` has any declaration in the profile; `phase`,
`verdict`, `disposition` and `role` are **not** declared fields on the Pydantic model either
(verified — they survive only via `extra="allow"`).

D1/D2 ruled the semantics here (`status` is lifecycle; delete `disposition`, keep
`closure_basis`) — the rulings exist; the declaration layer has not caught up.

### F5 — Where does a kind's files live?

`EntityKind.home` covers **36/53** kinds. 17 declare none. One (`research-question`) declares a
home that is a *file*, not a directory — a special case inside a field that otherwise means
directory. `paths.py` separately carries an `entities_dir` default, and the
`directory_structure` validate check has its own view.

### F6 — How is an entity named?

Identity-bearing fields on the base model: `id`, `canonical_id`, `aliases`, `deprecated_ids`,
`file_path`, `local_path`, `primary_external_id` — plus `citekey` for bibliographic kinds,
derived slugs, and the `knowledge/sources/local/mappings.yaml` alias table.

No divergence measured. Listed because the surface count is high and identity is load-bearing
for resolution; it deserves a targeted audit rather than an assumption. **(judgment)**

### F7 — How is a link between entities authored?

Six surfaces: `related:` (untyped), `relations:` (typed predicate + target), `source_refs:`,
`discusses:` (bundle membership carrying roles), `knowledge/sources/local/relations.yaml`, and
`.edges.yaml` sidecars — alongside `entities.yaml`, `terms.yaml`, `mappings.yaml` as further
local source files the graph reads.

This is redundancy of *spelling* rather than measured disagreement. It matters because each
spelling is a place a future fact can be stored inconsistently. **(judgment)**

### F8 — How good is a claim?

Parallel vocabularies: `belief_state` (4 levels), verdict tokens (5), `derived_edge_status`
(5), plus `claim_layer`, `identification_strength`, `polarity`, `evidence_stance`, `strength`,
`confidence`.

Some of this is legitimate factoring — a verdict is a conclusion about a *test*, `belief_state`
is a reading of a *proposition*, and they should not be merged. But `derived_edge_status` is
described in the user guide as "a lossy compatibility projection over canonical state": a
compatibility layer that became permanent. **(judgment)**

### F9 — Which relations may a kind participate in?

23 declared relation kinds, expressed through **two mechanisms in the same field set**:

- `allowed_kind_pairs` — an explicit non-Cartesian allow-list. Used by **2** relations
  (`supersedes`, `amends`).
- `source_kinds` × `target_kinds` — the Cartesian product. Used by **21**.

The Cartesian form is harmless where the sets are 1×1 (most of them). It is exactly the two
relations with large endpoint sets that needed the precise form — and those are precisely where
the frozen debt sits. The mechanism duality is not the defect; the content is. **(judgment)**

### F10 — Where is an inquiry authored?

Two source surfaces: `entities/inquiries/<slug>.md` (prose-first entity) and
`entities/patches/<slug>.md` with `patch_type: inquiry` (the compiled, graph-backed path). The
user guide names the second "a compatibility view over the patch-definition source path, not a
second truth-owning inquiry store" — an accurate description of intent and a known duality.

## The meta-finding

Every instance above was found by a person hitting it. **There is no check for declaration
multiplicity**, and D3's reconciliation clause — the one mechanism that would have caught F1 and
F2 — was adopted and never built.

This matters more than any individual row. The toolkit is *good* at ratcheting: AST guards,
frozen allowlists, RED-by-construction tests, reconciliation gates. That machinery works and is
used well. It just gets aimed at each fact after that fact has already broken something.

## Scope and honesty

- This is a broad sweep, not an exhaustive audit. Facts not listed here are unexamined, not
  cleared.
- All counts were produced by running code on 2026-07-25 against local `main` at `87ac7337`.
- Rows F6–F9 record surface *multiplicity*; only F1, F2, F4 and F5 have measured *disagreement*.
  That distinction should survive into the design — redundancy is a smell, divergence is a bug.
- Nothing here is a ruling. In particular, F1's direction was already settled by D3/D5 and this
  document does not reopen it: the finding is that the adopted contract is **incompletely
  implemented**, not that it was wrong.

## What this does not cover

Deliberately out of scope, and worth their own passes: the CLI surface (47 command groups), the
checking/reporting systems (`validate`, `qa_audit`, `curate`, `big_picture`, `wander`,
`distill`, `skills_coverage`), test-suite organisation, and the commons/project boundary beyond
its entity-schema aspect.
