# Reference Collection, Keyed Member & Promoted Member (Foundation primitive)

Date: 2026-05-26

Status: design for review (foundation primitive; consumed by Pillars C and D, and later non-molecular identity work)

Related (builds on):
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` — umbrella; routes here
- `docs/plans/2026-04-19-dataset-entity-lifecycle-design.md` — dataset mixin (`origin`, `derivation`, `parent_dataset`)
- `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` — Pillar C; the assembly registry is an instance
- `docs/plans/2026-05-26-bio-geneset-type-design.md` — Pillar D; the gene-set collection is the first instance
- `docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md` — Pillar A; collections are typically `source_class: reference`

---

## 1. Purpose & scope

Several parts of the bio data layer need the *same* shape: a large, pinned reference resource that is a
**set of individually-addressable rows**, where most rows never need their own entity, but any row may
become evidence-bearing and require a stable, citable identity. Gene-set collections (D), the assembly
registry (C), the variant-label registry (C4), and the identifier crosswalks (C2/C3) are all this shape.

Rather than re-derive it per resource — or make assemblies "an instance of the gene-set type", which
inverts the dependency — this doc defines the mechanism **once**, as a foundation primitive. The durable
noun is the **model** (reference collection / keyed member / promoted member), not the operation. Pillar D
is its first concrete instance; C's assembly registry is its second; the crosswalks and the variant-label
registry follow.

**Non-goals.** This doc does not define molecular identity (C), the epistemic source class (A), influence
tracking (B), or any specific extension schema. It defines only the collection→member→promotion model and
its invariants. Each consumer supplies its own key, its own domain extension, and its own resolver.

---

## 2. The model

A **reference collection** is a `dataset` whose bulk artifact is a table of **keyed member rows**. An
individual **member** is, by default, *not* an entity — it is the row addressed by its key. A member is
**promoted** to its own child `dataset` entity only on demand. Three layers, one mechanism:

| Layer | Is | Identity | Cost |
|---|---|---|---|
| Reference collection | a `dataset` (+ a domain extension), `source_class: reference` (A) | the dataset id | one entity per resource |
| Keyed member | a row addressed by a mechanism-specific key | the key (resolves in the collection) | none — data columns only |
| Promoted member | an on-demand child `dataset` | the key, as the entity's canonical identity attribute | one entity, minted only when needed |

---

## 3. Locked decisions

### RCM-D1 — Reference collection = a `dataset` with keyed member rows

A reference collection is a `dataset` (typically `origin: external` or `derived`, `source_class:
reference` per A) carrying a domain extension and a bulk artifact whose rows are addressed by a
**mechanism-specific key column**. The key is the member's identity *within* the collection; the
collection's `datapackage` hash pins the row contents. Nothing about the mechanism is gene-set-specific:
the key may be a gene-set `set_key`, an assembly `seqcol_digest`, a computed VRS id, or a crosswalk
canonical-id/tuple (§4).

### RCM-D2 — A keyed reference must resolve, or be `declared_unresolved` (guardrail 1)

Any reference to a member *by key* — declared inline on a consuming dataset, or carried inside a reified
usage record — **must resolve against the pinned collection**, or carry a first-class
`resolution_status: declared_unresolved`. It must never float as an unchecked free string. **The
collection row is mandatory; the promoted entity is optional.** `resolution_status` is therefore a
validated, queryable state (`resolved` | `declared_unresolved`), not an absence. This is what lets
identity be *checked* without forcing an entity per row, and what keeps "we do not yet resolve this
space" (a key in a namespace a later pillar will own) an **explicit** state rather than a silent pass.

### RCM-D3 — Promoted member = an on-demand child `dataset`

When a member becomes evidence-bearing it is promoted to its **own child `dataset`** whose
**canonical identity attribute is the member key** and whose `parent_dataset` is the collection. Promotion
gives the member a stable, citable id (`dataset:<…>`) for evidence lines and for B's per-member
provenance. Promotion **never changes identity** — the key was already the identity; promotion only mints
an entity for it.

### RCM-D4 — Promotion triggers (only on demand)

Promote a member only when it needs one of: **citation** by an evidence line (`source:
dataset:<member>`); **independent provenance** (its own `dataset_usage` / `set_definition_source`
declarations, per B); **asset packaging** (its own materialized artifact, distinct from a slice of the
parent); or **review / lifecycle state** of its own. The never-promoted long tail stays collection rows.
(D's "promote when cited or needs independent provenance" and C's "promote when an assembly needs
citation, provenance, asset packaging, or review state" are the same trigger set, stated once here.)

### RCM-D5 — `derivation.kind: member_of` + virtual member resolution

A promoted member has no workflow — its derivation *is* "member `<key>` of `parent_dataset`". The dataset
schema's `derivation` becomes a **discriminated union on `kind`**; the `member_of` kind carries
`parent_dataset` + `member_key`, satisfying `origin: derived` without a `workflow_recipe`:

```yaml
derivation:
  kind: member_of
  parent_dataset: dataset:<collection>
  member_key: "<the key>"        # set_key value, seqcol_digest, VRS id, crosswalk id/tuple
```

A `member_of` dataset is a **virtual derived dataset**: the required `datapackage` is satisfied by a
descriptor that resolves the payload by **slicing `parent_dataset` on `member_key`**, not by separate bulk
bytes. A member is materialized to its own artifact only when explicitly needed (RCM-D4's asset trigger).
This virtual-member rule lives **here**, in the primitive — every consumer inherits it; it is not a
D-only rule. The default (workflow) `kind` still requires `workflow_recipe` + `inputs`. This keeps
`origin: derived` explicit and machine-checkable, and is preferred over relaxing `derivation` validation
by profile (which would let an extension silently weaken a core dataset invariant) or mislabeling a member
`origin: external` (it is not — we extracted it from a parent).

### RCM-D6 — Exact key equality is identity; compatibility is a separate relation (guardrail 2)

Two members are the **same identity** iff their keys are byte-equal. Any weaker notion — two *distinct*
keys that are nonetheless *compatible* — is a **relation between distinct identities**, recorded
separately and **never** a collapse of two keys into one. Examples each consumer must honor: a seqcol
*comparison* yielding `compatible_coordinate_system` / `liftover_possible` (C4) relates two distinct
assembly digests; a crosswalk many-to-one, or a deprecated/merged/withdrawn map (C2/C3), relates two
distinct canonical ids *with provenance*. Identity-by-equality is cheap and ships first; compatibility
relations are a later, richer layer per consumer. The primitive **forbids** ever using a compatibility
relation to mint a single shared key.

---

## 4. Instances

| Instance | Collection (`dataset` +) | Member key | Promoted when | Owner / phase |
|---|---|---|---|---|
| Gene-set collection | `bio.geneset` | `set_key` | cited by an evidence line / needs independent provenance | Pillar D |
| Assembly registry | assembly-registry extension | `seqcol_digest` | needs citation / provenance / asset packaging / review | Pillar C — C1 |
| Identifier crosswalk | crosswalk extension | namespace-specific canonical id or tuple | a specific mapping needs its own provenance | Pillar C — C2/C3 |
| Variant-label registry | (C4 extension) | computed VRS id or pinned external label | a labelled variant becomes evidence-bearing | Pillar C — C4 |

Each instance supplies only its key, its domain extension, and its resolver. The collection→member→
promotion model, the resolve-or-`declared_unresolved` invariant (RCM-D2), the `member_of` derivation and
virtual-member rule (RCM-D5), and the equality-vs-compatibility guardrail (RCM-D6) are inherited
unchanged.

---

## 5. Relationship to Pillars C and D

- **D is the first concrete instance.** Its `bio.geneset` collection, `set_key` member addressing, and
  promotion-on-citation are this primitive with `member_key = set_key`. D adds only the gene-set-specific
  fields — `identifier_space`, `n_members`, set-size summaries, per-set provenance columns — and the
  heterogeneous-collection per-set source-class override. The virtual-member rule it previously stated as
  its own (D-D7) is inherited from RCM-D5.
- **C's assembly registry is the second instance**, keyed by `seqcol_digest` and consumed through the
  `bio.identity_context` declaration (C-D6). C1 ships exact resolution (RCM-D2 + RCM-D6 equality); C4
  adds the compatibility/liftover relations (RCM-D6, second half).
- **Later non-molecular identity** (cell line, disease, ontology) will likely add further instances; the
  `resolution_status: declared_unresolved` state (RCM-D2) is already the seam for keys whose space C does
  not yet resolve.

---

## 6. Status & next step

Foundation primitive for review. On approval it is the substrate that the Pillar C update (assembly
registry as an instance) and the Pillar D reconciliation (gene-set collection as an instance) both cite.
The C1 implementation plan defines it concretely — the `member_of` derivation variant (a small,
discriminated-union change to the core dataset `derivation` schema) and the resolve-or-`declared_unresolved`
validation — so that D and the assembly registry consume **one** mechanism rather than two look-alikes.
