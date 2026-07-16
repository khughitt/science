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

1. **Collect.** Load and schema-validate every source into an unordered `SourceContribution` —
   a declaration **plus** a validated candidate. No arbitration, no deferral, no selection.
2. **Close.** Expand parsed-reference / commons closure to a **fixed point**, adding commons
   owners and overlays as contributions.
3. **Arbitrate.** Audit the complete contribution set as a **pure function**.
4. **Compose.** Produce final `ProjectSources.entities`. RDF Emit remains downstream, unchanged.

A single contribution type cannot hold both. An owner or external reference contributes a
validated `Entity`; a **borrower contributes an `OverlayRecord`** — a validated *partial*, which
is not an `Entity` and never was. Since Close explicitly adds overlays as contributions
(§2 step 2), the type must admit them:

```python
@dataclass(frozen=True)
class EntityContribution:
    """An owner or external reference: a whole, schema-validated candidate entity."""
    declaration: IdentityDeclaration     # carries participation_mode, owner_scope, AND source_ref
    candidate: Entity

    def __post_init__(self) -> None:
        if self.declaration.participation_mode is ParticipationMode.BORROWER:
            raise ValueError("a borrower contributes an attachment, not an entity")

@dataclass(frozen=True)
class AttachmentContribution:
    """A borrower: a validated partial that attaches to an owner's representative."""
    declaration: IdentityDeclaration
    record: OverlayRecord

    def __post_init__(self) -> None:
        if self.declaration.participation_mode is not ParticipationMode.BORROWER:
            raise ValueError("only a borrower contributes an attachment")

SourceContribution = EntityContribution | AttachmentContribution
```

**Invalid role/payload pairings are unconstructible.** The guards are not defensive ceremony:
`participation_mode` and the contribution type are two statements of the same fact, so the type
system cannot prevent them disagreeing and construction must.

**No `source_ref` field.** `IdentityDeclaration` already carries one, and a second copy is a
second source of truth that can disagree with the first. The declaration is the provenance
record; the contribution does not restate it.

**`candidate` is a fully schema-validated `Entity`, not a looser "payload".** Arbitration's job
is to **delay selection**, not to duplicate schema validation or invent a parallel pre-entity
type. Collection validates exactly as it does today; what changes is that validation no longer
implies *selection*. Several validated candidates may exist for one identity, and arbitration
composes the **representative** from them.

The distinction is *candidate* versus *representative*, not *unvalidated* versus *validated*. A
candidate that fails schema validation never becomes a contribution at all — that is collection's
ruling and A does not move it.

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
contributor roles*. A owes a **total** matrix over all four policies × all three roles.

**Owner-unset is treated as owner-absent for that field.** The owner wins every field it
*defines*; a field it declares but leaves empty is not a defended value. This is the general rule
that replaces the five hardcoded field names — it restores `meta`'s `sci:doi` and `dcterms:date`
without naming a single field.

"Unset" is **mechanical**, not a truthiness test:

```python
def is_unset(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()                      # "" and whitespace-only
    if isinstance(value, (list, tuple, set, frozenset, dict)):
        return len(value) == 0                        # empty collections
    return False                                      # False, 0, 0.0 are DEFENDED
```

| value | verdict |
|---|---|
| `None`, field absent | unset |
| `""`, `"   "` | unset |
| `[]`, `{}`, `set()`, `()` | unset |
| **`False`, `0`, `0.0`** | **defended value — the owner said so** |

The last row is the point of specifying this. Python's truthiness would silently classify
`False` and `0` as unset, letting a non-owner overwrite a value the owner deliberately set — and
`bool` being a subclass of `int` makes that easy to get wrong twice. The superseded
`_absorb_external_reference_metadata` used exactly this defect: `if getattr(owner, field_name,
None):` is a plain truthiness test. Left unspecified, the implementation re-invents it.

| `MergePolicy` | owner contributes | borrower contributes | external reference contributes |
|---|---|---|---|
| `REPLACE` | value wins | **error** — may not replace an owner's value | **error** |
| `REPLACE`, owner absent/unset | — | single permitted contributor supplies it | single permitted contributor supplies it |
| `APPEND` | values first | appends | appends |
| `APPEND`, owner absent/unset | — | contributors in `ContributionKey` order | contributors in `ContributionKey` order |
| `PROJECT_ONLY` | value is **overridden** by the project layer | **wins over the owner** — this is the policy's purpose | **error** — an external reference is not the project layer |
| `PROJECT_ONLY`, owner absent/unset | — | stands alone | **error** |
| `FORBIDDEN` | value only | **error** | **error** |
| `FORBIDDEN`, owner absent/unset | — | **error** | **error** |

**Conflicting equal-precedence non-owner values are an error** — never resolved by adapter rank
(§3.4). Two borrowers supplying different scalars for one `REPLACE` field is a defect to report,
not a race to win.

**`APPEND` ordering is by `ContributionKey`, never by load position**, or permutation invariance
(§4) fails on list fields.

### 3.3a fb-2026-07-12-006 is a landing dependency, not adjacent work

A owns borrower composition, and this matrix *is* the ruling fb-006 needs. Scoping its fix out
while making its branch reachable would be incoherent.

The mechanism, confirmed:

```python
policy = merge_policy.get(field) or overlay_policy.get(field)
...
else:  # REPLACE / FORBIDDEN — unreachable for a validated overlay
    raise OverlayMergeError(field=field, canonical_id=canonical.canonical_id)
```

`merge_entity` implements only `APPEND` and `PROJECT_ONLY`. `REPLACE` and `FORBIDDEN` both raise
from a branch whose comment asserts it is unreachable.

**Two defaults collide.** `read_merge_policy` defaults an unannotated field to `REPLACE`
(`merge.py:29`); `read_overlay_merge_policy` defaults one to `PROJECT_ONLY` (`merge.py:41`).
Because `REPLACE` is truthy, `merge_policy.get(field) or overlay_policy.get(field)` means **the
entity schema silently preempts the overlay for every field it declares.** A field's fate is
decided by which schema happens to declare it — not by any ruling anyone made.

**The dataset crash is an incomplete migration:**

| schema | `status` |
|---|---|
| `mixin-paper-2.0`, `mixin-theme-2.0`, `mixin-topic-2.0` | `science:merge: project_only` |
| `mixin-dataset-1.0` | **does not declare `status`** |
| `science-entity-base-2.0` | declared, **unannotated → `REPLACE`** |

Paper, theme, and topic were migrated to v2.0 mixins carrying `project_only`. Dataset was left at
1.0, inherits `status` from the base, and lands on `REPLACE`. Since `_iter_components` is
last-write-wins, the paper mixin overrides the base and the dataset mixin has nothing to override
it with. **Every commons dataset overlay carrying `status` raises; every paper overlay carrying
`status` is fine.** That is why fb-006's report and the observed green `meta`/`evolution` builds
were both true.

**A's correction: `mixin-dataset-2.0`.** Shared schema versioning is **real** — the authoritative
entity schema design records that `mixin-paper-1.0` and `2.0` ship side by side — so editing
`mixin-dataset-1.0` in place would **silently change the semantics of every profile pinned to
it**. A meaning change requires an atomic versioned migration. The work:

- Add **`mixin-dataset-2.0`**; **do not mutate `1.0`**.
- Declare `status: project_only`, matching paper/theme/topic.
- Update the **dataset default profile** and **promotion paths**.
- Migrate **explicit dataset profiles in `science-commons`**.
- Run **toolkit, commons, compatibility, and graph-output** checks.

This is the established mechanism, not a new one: paper, theme, and topic each went to 2.0 for
precisely this. The cross-repo cost is real, bounded, and explicit.

**A does not close fb-2026-07-12-006.** The distinction matters and the wording should not blur
it:

- **A closes** the dataset-status crashing *instance*, through the established versioned
  mechanism.
- **fb-006 stays open** for the broader entity-policy/overlay-policy precedence contract, until
  its callers and defaults are redesigned together.

`read_merge_policy` is **unchanged by A**. That restraint is justified by its caller surface, not
by convenience: it is not merely an overlay helper — `promote.py` uses its **key set for routing**
and its **values for canonical/project classification**. Changing its return semantics is a
**shared-interface change**, not a local bug fix, and the declared-versus-defaulted redesign is
separately scoped.

So A fixes the crash and **does not certify the wider precedence contract**.

### 3.4 Contribution order must be total

The identity key `(owner_scope, canonical_id)` **groups** contributions. It cannot **order** the
owner, borrower, and external-reference rows that share it — they all have the same identity key,
which is what makes them one entity's contributions.

Ordering requires a distinct, total key:

```python
@dataclass(frozen=True, order=True)
class ContributionKey:
    role: ParticipationMode      # owner < borrower < external-reference
    authority: AuthorityRank     # adapter / authority identity
    location: SourceLocation     # path, then position within it
```

Total, deterministic, and independent of load order — which is what `APPEND` needs to satisfy
§4.

**`ContributionKey` orders; it does not adjudicate.** Equal-precedence contributors supplying
conflicting scalar values **error**. Using adapter rank to silently pick a winner would
reintroduce exactly the arbitrary-authority defect A exists to remove, with a tidier name.

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
  absorb helper, but because **owner-unset is owner-absent** (§3.3) — a general rule, not five
  field names.
- Bib-only citations still materialize minimal nodes (§3.2).
- **A commons dataset overlay carrying `status` merges instead of raising** (§3.3a) — the
  fb-006 dataset instance, closed by `mixin-dataset-2.0`.
- **A borrower attempting to replace an owner's `REPLACE` field errors**, and reports which
  contributor did it (§3.3).
- **An owner field set to `False` or `0` is not overwritten** by any contributor (§3.3) — the
  truthiness defect the superseded absorb helper carried.
- **A profile pinned to `mixin-dataset-1.0` keeps 1.0 semantics** (§3.3a) — the versioned
  migration is atomic, not an in-place meaning change.

---

## 5. Scope

**In:** the four-step contract; the `SourceContribution` union (§2); deletion of `should_defer`,
`external_reference_ids`, and `_EXTERNAL_REFERENCE_SUPPORTING_FIELDS`; correct
`(owner_scope, canonical_id)` keying; the total role × policy matrix and the `is_unset`
predicate (§3.3); `ContributionKey` (§3.4); **`mixin-dataset-2.0` and its migration** (§3.3a);
permutation invariance.

**Out:**

- **B's topology declaration.** A does not unify `_TYPE_TO_DIR` / `OverlayAdapter` /
  `CommonsQuery`.
- **Cross-scope resolution rules (§B3a).** Followed, not reopened.
- **RDF Emit.** Downstream and unchanged.
- **`read_merge_policy`.** Unchanged by A. Its declared-versus-defaulted redesign is a
  shared-interface change (`promote.py` routes on its key set and classifies on its values), not
  a local fix.
- **fb-2026-07-12-006's wider defect.** A closes the dataset-status crashing *instance*. The
  entity-policy/overlay-policy precedence contract stays open under that entry until its callers
  and defaults are redesigned together (§3.3a).
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
