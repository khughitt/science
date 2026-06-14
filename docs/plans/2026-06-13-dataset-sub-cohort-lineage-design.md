# Dataset Sub-Cohort Lineage Design

Date: 2026-06-13

Status: design / scoping. Paired implementation plan: `docs/plans/2026-06-13-dataset-sub-cohort-lineage-plan.md` (not yet executed).

Related:
- `docs/plans/2026-05-29-b2-dataset-independence-design.md` — B2 collapse semantics this extends; §10 names cross-dataset overlap an explicit non-goal
- `docs/plans/2026-06-05-dataset-first-class-entity-design.md` — dataset entity model (origin/access/derivation, `parent_dataset`/`siblings` fields)
- `~/d/science/science/model/src/science_model/entities.py` — `Entity.parent_dataset` / `Entity.siblings` (lines 329–330), `DatasetEntity` invariants #7/#8
- `~/d/science/science/model/src/science_model/packages/schema.py` — `DerivationBlock` / `WorkflowRecipeDerivationBlock` / `MemberOfDerivationBlock`
- `~/d/science/science/src/science_tool/graph/dataset_independence.py` — B2 collapse grouping (`by_dataset` at lines 267, 317)
- `~/d/science/science/src/science_tool/graph/health.py` — existing lineage-symmetry invariant (#5, line 1540)
- Motivating case: `~/d/health/meta` UKB / UKB-PPP reconciliation (commit on `main`, 2026-06-13)

---

## 1. Purpose And Scope

Some datasets are **sub-cohorts of** other datasets: a participant- or modality-restricted slice of a
larger resource, defined externally (not produced by one of our workflows). The canonical case is the
**UK Biobank Pharma Proteomics Project (UKB-PPP)** — the Olink Explore plasma-proteomics sub-study drawn
from ~54k of UK Biobank's ~500k participants. UKB-PPP is its own access-controlled resource with its own
accession and embargo, yet every UKB-PPP participant is a UK Biobank participant. Evidence lines resting
on UKB-PPP and evidence lines resting on UK Biobank are therefore **not statistically independent** — they
share a participant pool.

This document scopes a first-class **sub-cohort-of lineage** relation between dataset entities and the
work needed to make the belief/independence machinery (B2) honor it. The relation must:

1. be **declarable**, not inferred — an authored canonical fact, so it stays inside B2's principle of
   "interpret declared refs, never infer biological overlap" (B2 design §10);
2. be **origin-orthogonal** — a sub-cohort is frequently itself an `origin: external` access-controlled
   resource (UKB-PPP is), so the relation must not require `origin: derived` or a workflow provenance block;
3. **collapse evidence correctly** in B2 — a child-on-parent line pair must stop double-counting.

It is explicitly **not** the `member_of` derivation (a single row within a reference collection, e.g. one
gene-set member); see §3.

---

## 2. Current State — What Already Exists

The primitive is roughly half-built; the field exists but is epistemically inert.

**Schema (present).** `parent_dataset: str` (a single `dataset:` ref) and `siblings: list[str]` are already
real fields on the base `Entity` (`entities.py:329-330`) and in the dataset JSON mixin
(`mixin-dataset-1.0.json:18-19`), alongside `consumed_by`. They carry **no origin coupling**: the dataset
invariants (#7 external→access, #8 derived→derivation; `entities.py:661-694`) constrain only
`access`/`derivation`/`accessions`/`local_path`, never `parent_dataset`. So an `origin: external` dataset
may legally declare `parent_dataset` today. This is the field UKB-PPP should use; the `derivation:` block is
the wrong tool (it failed validation during the motivating reconciliation precisely because UKB-PPP is not a
workflow output).

**Validation (partial).** One health invariant exists — "lineage symmetry: `parent_dataset ↔ siblings`"
(`health.py:1540-1554`, severity `warning`): if `A.siblings` lists `B`, then `B.parent_dataset` must equal
`A`. It fires only when both files are present and only checks the back-link direction. There is **no** check
that `parent_dataset` resolves to an existing entity, and **no** acyclicity check.

**Graph materialization (absent).** Top-level `parent_dataset` is **not** emitted into the materialized
graph. Its only readers are health/commons/validate frontmatter passes
(`health.py`, `reference_graphs.py`, `commons/member.py`, …). `graph/materialize.py`, `graph/sources.py`,
and `graph/dataset_usage.py` do not emit a lineage edge. (The `parent_dataset` that *is* graph-visible
belongs to the unrelated `member_of` derivation, via the reference-collection path.)

**B2 independence (lineage-blind).** Collapse groups evidence lines by **exact dataset-ref equality**:
`by_dataset[ancestor.dataset]` in both `_commitment_components` (via `_components_from_ancestors`,
`dataset_independence.py:315-317`) and `_candidate_edges` (`:263-267`). A line on `dataset:ukb-ppp` and a
line on `dataset:uk-biobank` land in different buckets and are treated as independent sources. The B2 design
doc lists this as a deliberate non-goal (§10: "does not infer biological overlap between distinct datasets …
only interprets shared canonical dataset refs"). A **declared** lineage edge dissolves that objection: it is
a ref, not an inference.

### Net gap

| Layer | State | Work |
| --- | --- | --- |
| Field (`parent_dataset`) | exists, origin-orthogonal | none |
| Semantics / docs | undocumented | bless as sub-cohort-of (§3) |
| Referential integrity + acyclicity | missing | add validate check (§4) |
| Symmetry (`↔ siblings`) | health WARN only | keep; optionally promote (§4) |
| Graph materialization | absent | emit lineage edge (§5.1) |
| B2 collapse | lineage-blind | lineage-aware grouping (§5.2) |

---

## 3. The Relation — Semantics

`parent_dataset: dataset:<slug>` on child **C** asserts: *every observational unit of C is an observational
unit of its parent P* — C is a subset/restriction of P (by participant set, modality, assay, ancestry, or
tissue). `siblings: [dataset:…]` on P is the optional denormalized inverse.

Authoritative direction is **child → parent** (`parent_dataset`). `siblings` is convenience for the parent
side and is validated for symmetry when present (§4); it is not required.

Properties:
- **Acyclic.** The `parent_dataset` relation forms a forest (a dataset has at most one parent). Chains are
  allowed (a sub-cohort of a sub-cohort); cycles are an error.
- **Origin-orthogonal.** Independent of `origin`/`derivation`/`source_class`. UKB-PPP: `origin: external`,
  access-controlled, `parent_dataset: dataset:uk-biobank`.
- **Transitive for dependence** (§5.2): ancestor/descendant lines depend; this is what B2 consumes.

**Distinct from `member_of` derivation.** `MemberOfDerivationBlock` (`schema.py:174`) promotes a *single row*
of a reference collection to an entity (`derivation.kind: member_of`, `parent_dataset`, `member_key`). That
is a one-of-many membership with a row key, validated against the parent's reference graph
(`reference_graphs.py`). A sub-cohort is a *whole dataset that is a slice of another whole dataset*, with no
row key and no reference-graph parent. The two share the word "parent" but are different relations: keep
sub-cohort lineage on the **top-level** `parent_dataset` field, never inside `derivation`.

---

## 4. Validation

Add a dataset-lineage check (new `validate/checks/` module, or extend the dataset-metadata check). It must
flag, as ERROR:

- `parent_dataset` that does not resolve to an existing `dataset:` entity (referential integrity);
- a cycle in the `parent_dataset` chain (`A→B→…→A`);
- `parent_dataset` pointing at a `member_of`-derived collection member (category error — a sub-cohort's
  parent must be a plain dataset, not a collection row).

Keep the existing `health.py` symmetry warning. **Open call (recommend: yes):** promote the
`parent_dataset ↔ siblings` symmetry from a health WARN to a validate check so it gates `science validate`
and is enforced even when `siblings` is omitted (i.e. parent silently missing the back-link is at most a
hint, never required — `parent_dataset` alone is sufficient and authoritative).

No new required fields. `parent_dataset` stays optional; absence means "not a sub-cohort," which is the
common case.

---

## 5. B2 Integration

Two steps, mirroring B1→B2 layering: materialize the lineage into the graph, then teach collapse to use it.
B2 continues to read **only** the materialized graph, never frontmatter.

### 5.1 Materialize the lineage edge

In dataset materialization (`graph/materialize.py` / `graph/sources.py`), emit a lineage triple for each
`parent_dataset`:

```
<dataset:C>  sci:subCohortOf  <dataset:P>
```

A dedicated `sci:subCohortOf` predicate is preferred over reusing `prov:wasDerivedFrom` so that B2 can
distinguish a *subset* relation (this design) from a *compute-derived* relation (which has different
overlap semantics and already flows through `derivation`). The materializer computes, per dataset, its
ancestor chain to the lineage root; cycles are rejected upstream by §4 so materialization can assume a
forest.

### 5.2 Lineage-aware collapse

Today collapse keys on `ancestor.dataset` and pairs lines only within the same exact dataset. Extend the
pairing so two lines on **lineage-related** datasets are also considered, with the relationship deciding
commitment vs candidate. Per the scoping decision:

- **Ancestor–descendant pair (subset chain), both direct dependence → COMMITMENT.**
  A line on C and a line on any ancestor P of C are treated as a **full-overlap shared-source** dependence:
  the subset fully rests on the parent's participants, so it cannot be an independent replication. This
  extends `_is_committable_pair` (`dataset_independence.py:283`) to accept a pair whose datasets are in an
  ancestor/descendant relation (not only datasets that are identical). The committed group's
  `independence_group`/justification records the lineage root plus both datasets.

- **Co-descendant pair (siblings/cousins — common ancestor, neither an ancestor of the other) → CANDIDATE.**
  Two distinct sub-cohorts of the same parent (e.g. UKB-PPP proteomics vs a UKB metabolomics sub-cohort)
  share participants only partially, so they are a reviewable **candidate**, never an auto-collapse. Add a
  `lineage-sibling` reason to `_candidate_reason` (`:291`), ranked with the existing `partial-overlap`
  class (reviewer signal; does not alter belief).

- **No lineage relation → unchanged.** Lines on `dataset:ukb-ppp` and `dataset:finngen` stay independent.

Mechanically this means grouping by **lineage root** (so cross-dataset pairs within a family are surfaced),
then classifying each pair by its pairwise lineage relation (ancestor-of vs co-descendant) rather than by
raw dataset equality. The existing identical-dataset case is the degenerate "ancestor-or-self" branch and
keeps its current behavior.

### Overlap-semantics note (considered and deferred)

A child's `dataset_usage.overlap` describes coverage of the *child* resource, not the fraction of the
*parent* it represents (a line using all of UKB-PPP uses ~10% of UKB participants). The scoping decision is
to treat a subset edge as **full** dependence regardless of the child's internal overlap value — the
conservative choice (a subset cannot independently corroborate its superset). The finer alternative —
deriving an *effective* parent-overlap from relative sample sizes — is **rejected for this iteration**: it
requires participant-count/sample-level data B2 does not hold and would re-introduce exactly the
biological-overlap *inference* B2's design forbids. If a future need arises, it belongs behind an explicit
declared `overlap`-on-the-lineage-edge field, not an inference.

---

## 6. Worked Example (UKB family)

```
dataset:uk-biobank            (parent; ~500k)
  ├─ dataset:ukb-ppp          parent_dataset: dataset:uk-biobank   (Olink proteomics, ~54k)
  └─ dataset:ukb-metabolomics parent_dataset: dataset:uk-biobank   (NMR, hypothetical)
```

- line_A (`ukb-ppp`) + line_B (`uk-biobank`), both direct full dependence on the same target
  → **commitment** (subset → shared source); belief stops double-counting.
- line_A (`ukb-ppp`) + line_C (`ukb-metabolomics`) → **candidate** `lineage-sibling`; reviewer-visible,
  belief unchanged.
- line_A (`ukb-ppp`) + line_D (`finngen`) → independent; unchanged.

This reproduces, at the belief layer, the manual reconciliation already done in `~/d/health/meta` (where
UKB-PPP and UK Biobank were split into distinct entities) — but makes the non-independence *automatic*
instead of relying on a curator having merged or remembered the relationship.

---

## 7. Non-Goals

- **No sample-level or participant-id matching**, and no inference of overlap fraction between datasets
  (B2 design §10 stands). Lineage is declared, full/partial is decided by lineage *role* (ancestor vs
  sibling), not by counting.
- **No automatic lineage discovery.** The tool will not guess that UKB-PPP descends from UK Biobank;
  a curator declares `parent_dataset`.
- **Not `member_of`.** Reference-collection membership (row-keyed) is untouched.
- **No belief-formula change.** Aggregation keeps reading committed independence only; this design only
  changes *which* line pairs become committed/candidate.
- **No migration of existing `paper.datasets`.** Orthogonal (B-migration).

---

## 8. Acceptance Criteria (for the paired plan)

The implementation plan should cover:

- model/validate tests: `parent_dataset` referential-integrity ERROR; cycle ERROR; `parent_dataset` →
  `member_of` collection member ERROR; symmetry promotion behavior;
- a test proving an `origin: external` dataset with `access` may legally carry `parent_dataset` (no
  invariant #7/#8 regression);
- materialization test: `parent_dataset` emits `sci:subCohortOf`; ancestor chain resolved; forest assumed;
- graph tests: ancestor–descendant line pair → **committed** shared-source group with lineage justification;
  co-descendant pair → **candidate** `lineage-sibling`, never committed; unrelated datasets → independent;
- a chain test (sub-cohort of a sub-cohort) proving transitivity of the ancestor–descendant commitment;
- a regression test proving identical-dataset collapse (the pre-existing behavior) is unchanged;
- an end-to-end test reproducing the UKB/UKB-PPP example in §6.

---

## 9. Decisions Taken (this scoping)

- **Collapse rule:** child⊂parent = full (commitment); siblings = partial (candidate). [decided]
- **Field:** reuse the existing top-level `parent_dataset` / `siblings`; do **not** add a derivation variant
  and do **not** add a new field. [decided]
- **Overlap of subset edge:** treated as full, no sample-size inference. [decided]
- **Symmetry check promotion (health WARN → validate):** recommended, left to the plan. [open]
- **Predicate:** new `sci:subCohortOf` rather than reusing `prov:wasDerivedFrom`. [recommended]
