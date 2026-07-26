# S1a — the reconciliation gate

Sub-project 1a of the system-cohesion program. Covers F1.

- Program inventory: [`2026-07-25-multi-surface-fact-inventory.md`](2026-07-25-multi-surface-fact-inventory.md)
- Program target: [`2026-07-25-ideal-core-target.md`](2026-07-25-ideal-core-target.md) §3, §8
- Preceding sub-project: [`2026-07-25-s7a-retired-command-surface-design.md`](2026-07-25-s7a-retired-command-surface-design.md)

**Scope ruling:** S1a is a **test gate plus one derivation fix**. It changes no
runtime validation behaviour and rejects no entity that loads today.

---

## 1. What the target document got wrong

The target says *"Every kind is reconciled, not 1 of 53."* Four corrections, all
measured against `d9e79f91`.

### 1.1 The partition is 50, not 53

| Set | Count | Members |
|---|---|---|
| Declared kinds (`CORE_PROFILE.entity_kinds`) | **50** | — |
| Explicit typed bindings (`CORE_KIND_MODELS`) | **20** | — |
| Schema mixins (`_MIXIN_VERSION_BY_GENERATION`) | **5** | dataset, hypothesis, paper, theme, topic |
| **Explicit overlap** (mixin ∧ explicit binding) | **4** | dataset, hypothesis, paper, theme |
| Mixin with fallback projection | **1** | topic → `ProjectEntity` |
| Model-only (typed binding, no mixin) | **16** | book, chain-audit, code-file, evidence-line, falsification, inquiry, mechanism, method, patch-definition, proposition, research-package, structural-chain, talk, task, workflow-run, workflow-step |
| Base-only (neither) | **29** | — |

Every `53`-based statement in the program docs is superseded by this table, not
only the headline. `20 + 29 = 49`, plus `topic` (a mixin with no explicit
binding) = 50.

**Reconciliation requires two authorities.** It is *possible* on 5 kinds and
*performed* on 1. "1 of 53" reads as 98% missing coverage; the truth is 1 of 5
possible, and the other 45 are a **declaration** problem (S1b/S2), not this
gate's coverage problem. A kind with no mixin has nothing to reconcile against;
adding one is authoring a contract, not widening a test.

### 1.2 `Entity` is `extra="allow"`

D3.3, shipped in `ae83241b`: *"Projections MUST preserve schema-valid extension
fields. Never return to `extra="ignore"` — that is the original defect."*
Verified: all 20 typed models and `Entity` itself are `extra="allow"`.

A schema-admitted field the model does not declare is therefore **no longer
dropped at `model_validate`**. It survives in `model_extra`. Three present-tense
statements in `science/model/tests/test_hypothesis_entity.py` still assert the
old failure mode (lines 8, 284–285, 327), and one comment there claims the
capability-field readers "re-parse RAW frontmatter and never go through the model
at all" — `skills_coverage/evidence.py:70,78` reads them from `model_extra`.
That prose is stale and S1a corrects it.

### 1.3 `undeclared_key` does not cover these gaps

An earlier draft of this design claimed the graph audit's `undeclared_key`
diagnostic surfaces undeclared fields. It does not, for two reasons documented at
`science/src/science_tool/graph/migrate.py:140-152`: it fires only for
`REFERENCE_FIELD_NAMES` — `{audits, blocked_by, chain, method, proposition_refs,
workflow}`, 6 fields — and the caller suppresses it for strict-schema kinds. The
intersection of those 6 with the 13 fields in this design's manifest is **empty**.

The accurate statement is: **preserved and untyped; unwired unless a named raw
reader exists.** No general diagnostic covers it.

### 1.4 The gaps are generation-scoped

There are **31 distinct `(kind, field)` gaps** but **62 `(generation, kind,
field)` gaps** across the two live generations. Today the two generations happen
to produce identical gap sets per kind, which is exactly why a pair-keyed
manifest would look correct and silently exempt the same gap in a generation 4.

The generations are not interchangeable: `mixin-hypothesis-1.0` (gen 2) and
`mixin-hypothesis-2.0` (gen 3) differ on `required_capabilities`, whose items
`$ref` moves from `capability_map` to `data_product_capability`. A battery
authored against gen 2 does not cover gen 3.

---

## 2. Move the composition derivation into `science_model`

The gate needs `admitted = base ∪ mixin − forbidden`. That derivation exists
today only as six lines inside `test_hypothesis_entity.py:54-57`, and the tool
suite cannot import a helper from the model suite's tests.

There is already a defect at the natural home,
`science/model/src/science_model/entity_schema/introspection.py:46-47`:

```python
for key, spec in properties.items():
    if not isinstance(spec, dict):
        continue          # a `false` schema is a bool -> skipped
```

A JSON Schema `false` is a **forbidden** field. Skipping it means a base field
the mixin forbids stays in `read_effective_frontmatter_fields()`'s output as if
admitted. Measured on hypothesis: 6 of its 17 forbidden fields
(`contributors`, `licenses`, `schema_profile`, `sources`, `tags`, `version`)
leak — exactly the base-declared ones, since the other 11 appear only in the
mixin and are dropped by the same `continue`.

This is the rev-1 error of the inventory itself — counting `false` as declared —
live in the CLI's authoring surface.

**S1a adds `admitted_field_names(profile) -> frozenset[str]` to
`introspection.py` and fixes `read_effective_frontmatter_fields` to honour
boolean schemas.** One derivation then serves three consumers: the existing
hypothesis reconciliation test, the new gate, and `science` CLI effective-field
display. Fixing the display is a user-visible correction, not scope creep — it
is the same fact, read by a third surface, currently answering differently.

---

## 3. The gate

New file: `science/tests/test_kind_reconciliation.py`.

It lives in the **tool** package, not `model/tests/`, because the kind→model
binding is `science_tool/graph/entity_registry.py:58` (`CORE_KIND_MODELS`) and
`science_model` may not import its consumer. Entity subclasses do not
self-declare their kind — `kind` is a plain `str` with no default on every one —
so that dict is the only map.

*That the binding between a declared kind and its projection lives in neither
authority's package is a real finding. S1a records it and does not move it;
relocating it is S2's call, alongside the other per-kind facts.*

### 3.1 The derived surface

```
PROFILES = [(generation, kind) for generation in _MIXIN_VERSION_BY_GENERATION
                               for kind in _MIXIN_VERSION_BY_GENERATION[generation]]
```

10 pairs today. A sixth mixin or a generation 4 enters the parametrization the
moment it is declared — nothing in this file enumerates kinds or generations by
hand.

### 3.2 Field-declaration gate

`test_every_admitted_field_is_declared_on_the_projection[generation, kind]`

For each profile: `admitted_field_names(profile) - set(model.model_fields)` must
equal exactly the manifest's entries for that `(generation, kind)`. **Exact
equality, not subset** — a stale exemption fails as loudly as a new gap. This is
`test_the_BATTERY_is_EXACTLY_the_shared_surface`'s lesson: the hand-written half
is the half that falls behind, and it falls behind in both directions.

### 3.3 The manifest

`UNHELD: dict[tuple[int, str, str], Exemption]` — keyed by
`(generation, kind, field)`, 62 entries.

Entries are authored as `(kind, field) -> (generations, reason)` and **expanded
to triples before comparison**, so a new generation inherits nothing implicitly:
its gaps must be declared or the gate fails.

Two reason forms:

- **`Reader(symbol)`** — the field is read from a mapping by name somewhere. The
  gate proves this mechanically: import the symbol, parse its source, and require
  an AST subscript or `.get()` call with that literal field name. **What this
  proves is existence and a keyed read of that name — not that the mapping is
  this kind's frontmatter.** That last step is human judgment and the spec says
  so rather than implying the check is stronger than it is.
- **`PendingRuling(note)`** — explicit debt. It asserts that someone looked and
  that no reader was found; it is *not* evidence that the gap is benign. S1b/S2
  resolves each by adding the model field, forbidding it in the mixin, or
  producing a reader.

Initial classification — **9 `Reader`, 22 `PendingRuling`** per `(kind, field)`,
each present in both generations:

| Field | Kinds | Reason |
|---|---|---|
| `required_capabilities` | hypothesis | `Reader` — `dataset_prioritize` reads `target_fm["required_capabilities"]` |
| `capability_scope` | hypothesis | `Reader` — `validate.checks.dataset_capabilities` reads `fm["capability_scope"]` |
| `provided_capabilities` | dataset | `Reader` — `skills_coverage.evidence` reads it from `model_extra` |
| `runtime_state` | dataset | `Reader` — `dataset_prioritize` reads `row["runtime_state"]` |
| `paper_kind` | paper | `Reader` — `validate.checks.document_structure` reads `ctx.frontmatter(path)["paper_kind"]` |
| `tags` | dataset, paper, theme, topic | `Reader` — `entities_inventory` reads `data["tags"]` |
| `contributors`, `licenses`, `schema_profile`, `sources`, `version` | dataset, paper, theme, topic | `PendingRuling` — commons record fields. `hypothesis` **forbids** all five; the other four mixins are silent. Which is right is S1b's ruling. |
| `arxiv`, `pmcid` | paper | `PendingRuling` — `paper_fetch` handles same-named keys, but from a fetched API record, not entity frontmatter. Not a reader. |

A claimed `Reader` that fails its AST check at implementation time becomes a
`PendingRuling`. The gate adjudicates its own manifest; this table is the
starting classification, not an assertion that all nine will survive.

### 3.4 Composition self-check

`test_the_forbidden_fields_are_excluded_from_the_admitted_set`

Both hypothesis mixins declare exactly **17** `false` properties, identically:

```
author_stated_evidence, belief_state, confidence, contributors, disposition,
disposition_basis, domain, evidence_stance, licenses, phase, priority,
promotion_criteria, role, schema_profile, sources, tags, version
```

The test asserts the derived false-property set equals that explicit 17 and is
disjoint from `admitted_field_names`. Changing any one to `{}` fails.

Guarding all 17 rather than the 6 that overlap other kinds' gaps matters: `phase`,
`disposition`, and `role` are **D1/D2 being enforced**, and the inventory's rev 1
misread exactly this — counting `false` schemas as declared and reporting "17
fields the model never heard of." The check makes that misreading unrepeatable
instead of merely documented.

### 3.5 Status partition

Field-declaration coverage and value coverage are different depths, and
conflating them is how "reconciled" comes to mean two things.

§3.2 is unconditional: **every** derived profile is field-gated, with no opt-out.
The status mapping therefore records only the *value* depth on top of it.

`VALUE_RECONCILIATION: dict[tuple[int, str], Status]` — a **total** mapping over
the derived `PROFILES`, with `Status` one of exactly two values:

- `RECONCILED` — the deep battery of §3.6 also applies. Today exactly
  `{(2, "hypothesis")}`.
- `PENDING` — the exact remainder: the other 9 profiles, including
  **`(3, "hypothesis")`**, whose `required_capabilities` schema differs materially
  from the gen-2 form the battery was written against.

The gate asserts the mapping's key set equals `PROFILES` exactly. A newly
declared mixin or generation has no status and fails until classified.

The hand-written part declares **classification**; membership is derived. That is
the program's own rule — a hand-written declaration is appropriate when it
records a non-derivable judgment and its domain is checked exactly against a
derived set.

### 3.6 What the battery is, and where it stays

The deep properties — *the schema is at least as strict as the projection* and
*every admitted value survives the projection* — need per-field probe values.
They cannot be derived: each probe encodes a judgment about what the schema ought
to refuse. Authoring them for all 5 kinds is ~104 fields, of which hypothesis
covers 27, leaving ~77.

**S1a authors none of them.** `test_hypothesis_entity.py` keeps its battery and
its own equality ratchet; S1a changes only its stale prose and repoints its
composition derivation at §2's shared helper. The other 9 profiles are marked
`PENDING`, which is a declaration in code rather than an absence, and is S1b's
queue.

---

## 4. Out of scope, stated in the file

- **The 16 model-only kinds.** No schema to reconcile against. Authoring mixins
  is S1b.
- **The 29 base-only kinds.**
- **The ~77 unauthored battery entries.** S1b.
- **The runtime schema-first gap.** `PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})`,
  so the *schema-goes-first* half of the D3.3 contract runs for 1 kind while the
  *projection-preserves* half runs for all 50. `entities.py:315-321` states the
  consequence: for the other 49, extra keys "are preserved unvouched," and
  `extra="allow"` without a schema in front of it is the preserve-every-typo state
  that same docstring warns against. **This is the more serious defect and S1a
  does not touch it** — closing it changes what loads across 22 projects. It is
  named here so it is not mistaken for something this gate covers.
- **Relocating `CORE_KIND_MODELS`.** S2.

---

## 5. Verification

Every assertion must be shown able to fail, by breaking the thing it guards —
never by re-deriving the expectation and comparing it to itself. S7a shipped a
verbatim check that was the identity function and reported 17/17 on it; the
comparison here is always **model vs schema** or **manifest vs derived set**,
never manifest vs manifest.

Mutation proofs, each run and recorded:

| Mutation | Must fail |
|---|---|
| Delete a declared field from `PaperEntity` | §3.2 for `(*, paper)` |
| Remove one `UNHELD` entry | §3.2, "undeclared gap" |
| Add a spurious `UNHELD` entry | §3.2, "stale exemption" |
| Clone generation 3's mixin table into a generation 4 | §3.2 and §3.5 — proves the manifest is generation-keyed, not pair-keyed |
| Flip one hypothesis `false` property to `{}` | §3.4 |
| Point a `Reader` at a symbol that does not read the field | the AST reader check |
| Add a 6th mixin without a status | §3.5 |
| Revert the `introspection.py` boolean fix | §3.4, via the shared derivation |

---

## 6. Deliverables

1. `admitted_field_names()` in `introspection.py`, plus the boolean-schema fix to
   `read_effective_frontmatter_fields`.
2. `science/tests/test_kind_reconciliation.py` — the gate, the 62-entry manifest,
   the 17-field composition check, the status partition.
3. `test_hypothesis_entity.py`: stale `extra="ignore"` prose corrected, local
   composition derivation replaced by the shared helper, battery untouched.
4. The mutation-proof record from §5.
