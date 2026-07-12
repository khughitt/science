# The authoritative entity schema

**Date:** 2026-07-12
**Status:** Design, for review. Supersedes nothing; **subsumes** the field-vocabulary
(`extra="ignore"`) and status-vocabulary tracks, which are two symptoms of one root.

## 1. The root cause

Three surfaces must agree about any piece of entity frontmatter:

- the **template** that tells an author to write it,
- the **declaration** that models it,
- the **graph** that consumes it.

**Nothing in Science binds them.** That single missing contract produces two symptoms that
have been investigated separately and are the same defect:

| axis | symptom | mechanism |
|---|---|---|
| **fields** — which keys exist | 194 undeclared keys; 40% of files would fail strict validation | `Entity` is `extra="ignore"` → undeclared keys silently dropped at `model_validate` |
| **values** — what a key may hold | 472 status findings; `validate` broke in 2 projects | `EntityKind.statuses` never reconciled against templates/commands/usage |

**Proof they are one issue:** `templates/pre-registration.md` fails on *both* axes at once.
`status: "committed"` is an illegal **value**; `committed:` and `spec:` are undeclared
**keys**, silently dropped. One template. One missing contract. Two symptoms.

`meta/entities/hypotheses/0007-working-model.md` — the document that *defines* Science's
model of knowledge — carries `role:` and `phase:`. Both undeclared. Both dropped. The
working model is load-bearing on two fields the model cannot see.

## 2. There is no single authoritative schema

"What a hypothesis *is*" is declared in **four** places, none authoritative, plus a fifth
shadow surface:

| surface | declares | coverage |
|---|---|---|
| `EntityKind` (`profiles/schema.py`) | identity, placement, **status values** | all 33 kinds |
| `CORE_KIND_MODELS` → Pydantic class | **fields** | **20 of 33**; rest fall to bare `ProjectEntity` |
| template `_template.frontmatter` | **keys authors write** | per-template, unchecked |
| `graph/materialize.py` | **which fields become triples** | hand-written |
| *(shadow)* `fm.get()` in `validate/checks/*`, `big_picture/validator.py`, `qa_audit/runs.py` | keys consumed **bypassing the model entirely** | ad hoc |

That fifth surface is why naive fixes fail, and both were already tried and withdrawn
(`8f6587e9`): deriving the key vocabulary *from the loader* false-positives on ~40 real
entities whose keys are read by other modules; deriving it *tree-wide* false-negatives
because **the same key is live on one kind and dead on another** (`supersedes` is live on
QA-audit runs, dead on hypotheses).

`EntityKind` was declared "the sole per-kind SSOT" by the Kind Descriptor keystone — and
then **stopped short of fields**. This is a half-applied pattern, the same shape as the
convergence work already in the tree (canonicalize → migrate → guard).

**The fix is to finish it: make `EntityKind` declare the field schema, and derive every
other surface from it.**

## 3. `status` is one string doing the work of several axes

Decompose every declared vocabulary against the lifecycle words
`{draft, active, complete, superseded, retired, archived}`:

- **22 kinds are pure lifecycle** — and each hand-rolled a *different arbitrary subset of
  the same six words*. `finding`, `observation`, `mechanism`, `synthesis` have **identical**
  sets. `discussion`, `interpretation`, `inquiry` have **identical** sets. The variation
  encodes nothing. That is why `report` had no terminal state: not policy, an arbitrary draw.
- **11 kinds fuse a semantic axis into that same string.**

And the collapse is **measurable**: *the more semantic words a kind has, the fewer lifecycle
words survive*, because they compete for one field.

| kind | semantic values | lifecycle words left |
|---|---|---|
| `hypothesis` | 6 (`proposed`…`refuted`) | **1** — only `archived` |
| `story` | 2 | **1** — only `draft` |
| `workflow-run` | 2 (`running`, `failed`) | **1** — only `complete` |
| `question` | 3 | 3 |
| pure-lifecycle kinds | 0 | 4–6 |

**`hypothesis` has no `active`, no `draft`, no `superseded`.** So natural-systems writing
`status: active` on a hypothesis was never "drift" — **there was no lifecycle word available
to them.** They were reaching for an axis that does not exist. The same collapse hits the
most important kind in the model: **`proposition` fuses belief (`supported`, `contested`,
`weakened`) with lifecycle (`superseded`, `archived`) in one field, so a proposition cannot
be both *superseded* and *formerly supported* — one value silently overwrites the other.**

This is exactly the fb-2026-07-11-005 ruling (`status` = epistemic verdict, `disposition` =
workflow state) — which is therefore **not a hypothesis-specific patch but the general
law**, currently applied to one kind out of eleven.

## 4. The target model

An entity kind declares **typed fields on named axes**, in one place, and every surface
derives:

```
EntityKind (the SINGLE authoritative per-kind schema)
  ├─ identity      : name, canonical_prefix, layer, entity_class, category   [today]
  ├─ placement     : home, strategy, shortform                               [today]
  └─ FIELDS        : name → { type, required, axis, vocabulary, predicate }  [NEW]
                       axis ∈ identity | lifecycle | semantic | disposition
                                | relation | provenance | project-local
```

Derived, never re-declared:

- **Pydantic model** ← generated/reconciled from the field schema. Kills both the
  `extra="ignore"` silent drop *and* the 20-of-33 typing gap.
- **template `_template.frontmatter`** ← checked against it. (The value-axis instance of
  this check already ships: §4 of the status design.)
- **`materialize.py`** ← derives triples. **A declared field cannot fail to reach the
  graph** — which is precisely how `phase` came to rank a retired hypothesis #1.
- **`validate`** ← checks values against the declared vocabulary, for *every* enum field,
  not just `status`.

Axes become **separate fields**, so they cannot compete:

- **lifecycle** — shared vocabulary, not re-invented per kind. Scoped by `entity_class` /
  consolidatability (see §6 — this is *not* fully uniform, and the existing
  `test_reference_kind_does_not_gain_archived` guard proves it).
- **semantic** — declared per kind, *only where one genuinely exists*: hypothesis verdict,
  proposition belief, question answeredness, workflow-run outcome, dataset fitness.
- **disposition** — workflow closure (`open|closed` + basis). Already shipped on
  hypothesis; generalizes.

The undeclared keys fall out of the same law: `phase`, `role`, `focus_type`, `report_kind`,
`provided_capabilities` are all **axes someone needed and jammed into an undeclared key,
because there was no declared place to put one.** One `status` string plus a bag of
undeclared keys, where the model needs several typed, declared axes.

## 5. Phasing — strictness comes LAST

Certify the instrument, then depend on it. The 472-error regression is what happens when
that order is inverted.

- **P0 — Certify (toolkit-only, zero downstream churn).** Every field a shipped template or
  toolkit code writes is **declared and wired to the graph, or deleted from the template.
  No third option.** `phase`, `role`, `input`, `report_kind`, `committed`, `spec`,
  `promoted_from` get adjudicated one at a time. Downstream projects change nothing; this
  phase only makes Science honest about what it tells authors to write.
- **P1 — Absorb the real subsystems.** `provided_capabilities`/`required_capabilities` is a
  fully designed capability-matching subsystem with its own validator and seven design docs,
  reading raw frontmatter, bypassing the model, invisible to the graph. Make it first-class.
- **P2 — Declare every kind's axes** (not merely "add a Pydantic class per kind" — otherwise
  all 33 kinds get typed and `proposition` still collapses belief into lifecycle).
- **P3 — Then turn on strictness**, WARN first, **ratcheting to ERROR per kind** as each
  kind's schema is certified and its projects migrated. Severity is a property of the
  **kind**, not of `layout_version` (the axis that failed).

Project-local vocabulary (mm30's `mm30_treatment_axis`, cancer-evolution's literature-import
fields) is a **real need** — `commands/discuss.md` documents it as a feature. The fix is not
to forbid it but to make it **explicit**: a declared `project-local` axis, not an
undeclared key that happens to survive.

## 6. Open questions for review

1. **How uniform is the lifecycle, really?** The 22 pure-lifecycle kinds *look* like noise,
   but `test_reference_kind_does_not_gain_archived` pins `paper`/`book`/`talk` as
   deliberately **not** consolidatable — so at least some per-kind variation is real intent.
   A first draft of this design proposed steamrolling all 22 into one uniform set; that
   guard test would have caught it. **The variation must be excavated kind by kind, not
   assumed to be noise.** This is the same "certify before depending" discipline applied to
   this design itself.
2. **Does `disposition` generalize to all epistemic kinds, or only to those with a semantic
   axis?** A `finding` has no verdict to be open or closed about.
3. **Is the Pydantic model *generated* from the descriptor, or *reconciled* against it by a
   gate?** Generation is stronger; reconciliation is less invasive and matches the existing
   3-way gate pattern.
4. **Migration cost of splitting `status`.** Splitting means new fields on ~11 kinds and a
   rewrite of authored `status:` values across every project. It cannot be additive-only,
   and it needs a per-kind ratchet with a real migration command.

## 7. What already shipped toward this

- The value-axis P0 contract: `test_template_status_is_declared_by_the_kind` (no
  `template_ready` exemption).
- The per-kind ratchet principle, and the deletion of the `layout_version` severity axis.
- `disposition` on `hypothesis` — the first axis correctly split out of `status`.
- The status check at WARN: an uncertified instrument advises, it does not block.
