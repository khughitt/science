# Identity arbitration — completing the compiler seam

**Date:** 2026-07-16
**Status:** Design — proposed. Prerequisite for landing the fb-2026-07-16-005 fix.
**Motivating incident:** fb-2026-07-16-005 — a `references.bib` entry shadowed a commons
canonical. `merge_entity` and `validate_overlay_pin` were skipped for every paper a project also
cited; ~245 overlays across the federation were inert, and `science validate` reported success
in all of them.

**Relation to the arc:** this is **A** in the sequence recorded by
[`2026-07-16-claim-coverage-certification-design.md`](2026-07-16-claim-coverage-certification-design.md)
§9 — **A → B → C+D**. That document's §9.1 requires this design before A lands.

This is not "typed table now, compiler later." **A is the focused completion of the compiler
seam the substrate design already promised.**

---

## 1. The defect

Three parallel structures in the source-load loop (`graph/sources.py`):

```python
identity_table: dict[str, SourceRef] = {}          # :350
external_reference_ids: set[str] = set()           # :357
identity_declarations: list[IdentityDeclaration]   # :358
```

`IdentityDeclaration` carries `participation_mode`. `dict[str, SourceRef]` is a **lossy
projection** of it that drops exactly the field answering *"does this row own?"* —
and `external_reference_ids` was then added to reconstruct that dropped field. A shadow
membership set recovering data a value type discarded eight lines earlier.

The loss is twofold, and the second half is the deeper one:

| projection | drops | consequence |
|---|---|---|
| value is `SourceRef`, not the declaration | `participation_mode` | "materialized this id" reads as "owns this id" |
| key is `str`, not `(owner_scope, canonical_id)` | **scope** | owner, borrower, and external-reference rows for one id collapse into a single slot |

The identity key is `(owner_scope, canonical_id)` (substrate §B1/§B3). A bare-`str` key
structurally cannot hold the rows the model permits to coexist. Typing the *value* while leaving
the *key* wrong fixes one half of a two-half defect.

### 1.1 Provenance is decided by iteration order

`should_defer` is consulted **before** `identity_declarations.append(...)` and `continue`s past
it. So an external reference emits an `EXTERNAL_REFERENCE` row when loaded **before** its owner,
and **emits nothing at all** when loaded **after** it. Same federation, same bytes, different
provenance — decided by adapter iteration order.

`storage_adapters/bib.py` promises in its own docstring that "the load loop tags their identity
rows `ParticipationMode.EXTERNAL_REFERENCE`". That is true only on the branch where the adapter
does not defer.

Deferral must mean **do not own, do not materialize a competing representative**. It has never
meant *cease to exist*, and §B3 does not say it does.

### 1.2 What §B3 settles, and what it does not

The substrate design settles **participation and ownership**: what a row contributes, who may
own, that external references never own.

It does **not** settle **materialization arbitration**, **metadata precedence**, or **order
independence**. The current implementation decides all three by accident, none of them are
entailed, and all three are load-order-sensitive.

---

## 2. The contract

Four steps. Collection is unordered; arbitration is pure.

1. **Collect.** Load and validate every source into an unordered `SourceContribution` —
   a declaration **plus** a candidate payload. No arbitration, no deferral, no materialization.
2. **Close.** Expand parsed-reference / commons closure to a **fixed point**, adding commons
   owners and overlays as contributions.
3. **Arbitrate.** Audit the complete contribution set as a **pure function**.
4. **Compose.** Produce final `ProjectSources.entities`. RDF Emit remains downstream, unchanged.

```python
@dataclass(frozen=True)
class SourceContribution:
    declaration: IdentityDeclaration     # carries participation_mode + owner_scope
    payload: CandidatePayload            # the parsed record; not yet an Entity
    source_ref: SourceRef
```

Order-independence is **structural**, not defended: nothing materializes until every
contribution exists, so there is no encounter-order projection left to be wrong. Eviction and
placeholder-absorption both disappear — they were repairs for a temporal problem this contract
does not have.

### 2.1 `should_defer` is deleted from identity collection

Deferral is an **arbitration outcome**, not a collection-time permission. A contribution is
always collected and always declares. Arbitration then decides whether it materializes a
competing representative — which, for an external reference, is always no.

`StorageAdapter.should_defer(already_owned: bool)` asks a question no adapter is positioned to
answer, from a boolean derived from a lossy table, at a time when the answer is not yet known.
It goes.

`deferred_dataset_datapackage` — the `(id, path)` recorded so geneset member resolution can find
resources after a datapackage yields (§B4) — becomes an arbitration output rather than an
adapter callback.

---

## 3. Arbitration

### 3.1 Owners are not chosen by precedence

**Duplicate owners for the same `(owner_scope, canonical_id)` are an error.** Arbitration never
breaks that tie by precedence, adapter rank, or load position. Cross-scope ambiguity follows the
existing resolution rules (§B3a); it is not this design's to reopen.

Today's collision check is keyed on the bare `canonical_id` and gated behind `strict_identity`.
Under the correct key, a genuine cross-scope pair is no longer a collision at all, and a true
duplicate is unconditional.

### 3.2 Precedence governs only the materialized representative

Precedence answers one question: **given all contributions for an identity, what does the single
materialized node look like?**

| role | contributes to the representative |
|---|---|
| **owner** | the primary payload |
| **borrower** | attaches |
| **external reference** | permitted metadata only (§3.3) |
| **external reference, no owner present** | materializes a **minimal node** so citation edges resolve |

The last row is what keeps bib-only citations working: an id with no owner anywhere is still a
legitimate metadata node. That is a materialization rule, not an ownership claim — the row
remains `EXTERNAL_REFERENCE` and never becomes an owner.

### 3.3 The role × policy matrix

The hardcoded `_EXTERNAL_REFERENCE_SUPPORTING_FIELDS` five-tuple is **deleted**.
`read_merge_policy(parse_profile(...))` already exists and `commons_sources.py` already calls it:
the schema declares field policy, and inventing a parallel field list to sit beside it was the
error.

But the schema supplies **field policy only**. It does not say how that policy applies *between
contributor roles*. A still owes a small matrix:

| `MergePolicy` | owner present | owner absent |
|---|---|---|
| `REPLACE` | owner value wins; a non-owner may not replace it | the single permitted contributor supplies it |
| `APPEND` | owner value first, then contributors in a **deterministic order** | contributors in deterministic order |

Two requirements fall out:

- **`REPLACE` must define owner-present versus owner-absent behavior explicitly.** This is the
  live edge of **fb-2026-07-12-006**, where `commons/overlay.py:286-288` raises
  `OverlayMergeError` on `REPLACE` from a branch its own comment calls "unreachable for a
  validated overlay". A routes more overlays through `merge_entity` than have ever reached it,
  so that branch stops being hypothetical.
- **`APPEND` ordering must be deterministic**, or permutation invariance (§4) fails on list
  fields — which would make the acceptance test the thing that catches it.

The deterministic order is by identity key, never by load position.

---

## 4. Acceptance: permutation invariance

The decisive test:

> **Every ordering of the same contribution set must yield identical identity rows, composed
> entities, provenance, and errors.**

All four, not just entities. Provenance is included because §1.1 is a provenance defect and would
otherwise pass. Errors are included because "which duplicate is reported" must not depend on
order either.

This makes the former order-dependence **structurally testable** rather than a property someone
must reason about. Arbitration being a pure function over an unordered set is what makes the test
meaningful: given the contract, permutation invariance is close to a tautology, and any failure
indicates the contract has been breached somewhere concrete.

Regression acceptance, from the motivating incident:

- A commons paper cited by `references.bib` merges its overlay and validates its pin — the
  fb-005 defect, which is the shadow closing.
- The `meta` metadata regression does not recur: `sci:doi` 23, `dcterms:date` 18. Not by an
  absorb helper, but because an owner-absent `REPLACE` now has a declared answer (§3.3).
- Bib-only citations still materialize minimal nodes (§3.2).

---

## 5. Scope

**In:** the four-step contract; `SourceContribution`; deletion of `should_defer`,
`external_reference_ids`, and `_EXTERNAL_REFERENCE_SUPPORTING_FIELDS`; correct
`(owner_scope, canonical_id)` keying; the role × policy matrix; permutation invariance.

**Out:**

- **B's topology declaration.** A does not unify `_TYPE_TO_DIR` / `OverlayAdapter` /
  `CommonsQuery`.
- **Cross-scope resolution rules (§B3a).** Followed, not reopened.
- **RDF Emit.** Downstream and unchanged.
- **fb-2026-07-12-006's fix.** A must *define* `REPLACE` owner-present/absent behavior; whether
  `overlay.py:286` still raises is that entry's to settle.
- **C's census.** A makes the pin check *reachable*. It does not make its coverage *attestable* —
  that is C, and A shipping is precisely what turns ~245 overlays from inert into traffic.

## 6. Known consequences of landing A

A is a **breaking change for pinned consumers**, and deliberately so: overlays that have silently
done nothing will begin merging and pin-checking. Four stale pins are already known
(`Boyle2023`, `Lutz2025` in `mechanisms/evolution` and `cancer-types/multiple-myeloma`) against
commons `84139e4`, which corrected Key Findings — projects pinned to superseded content and were
never told.

Two data defects surface the moment A lands, both of which D (see the C design §8) exists to
catch permanently:

- `paper:Persi2025 → dataset:persi2025-myeloma` resolves in `mechanisms/evolution` via a
  project-local `status: candidate` entity and fails in `cancer-types/multiple-myeloma`. Name
  capture.
- `dataset:wang2025-mri-gwas` exists nowhere in the federation. Awaits **E**.

These are not A regressions. They are pre-existing defects A stops concealing.
