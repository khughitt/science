# The ideal core — target state

**Date:** 2026-07-25 (rev 2 — re-sequenced after review; rev 1 mis-stated the starting position)
**Status:** Working target. **Revised, not refuted.**
**Input:** [`2026-07-25-multi-surface-fact-inventory.md`](2026-07-25-multi-surface-fact-inventory.md) (rev 2)
**Optimizing for:** *agent legibility.* When principles conflict, the winner is whichever makes
a wrong answer harder to reach.

Thin by design. It states what "good" looks like so each sub-project can be judged against
something. It is not a spec, and it does not re-decide anything already ruled (D1–D5,
D-001…D-011).

## 1. The operating principle

> **Every fact has exactly one owner. Every other surface derives from that owner, and says so
> where it is read.**

Because the primary operator is an agent, the failure mode is specific. An agent reads one
surface and trusts it; it does not cross-check declarations for agreement, and has no way to
know a fourth exists. A stale copy is a wrong answer delivered with full confidence.

Three consequences, in priority order:

1. **Zero redundancy of authority.** Redundant *prose* is fine. A second place that can be
   *believed* is not.
2. **A wrong answer must be unreachable, not discouraged.** Documentation saying "retired" is
   not a retirement.
3. **Boring beats clever.** Explicit declarations an agent reads in one place beat an elegant
   derivation it must reconstruct. Derive for *consumers* of a fact, never for the *statement*
   of it.

**Where we actually start.** Rev 1 framed this as building a missing mechanism. That was wrong.
Two mechanisms exist and are well built — `test_hypothesis_entity.py` reconciles schema against
model field-by-field, and `test_supersedable_gate.py` ratchets the supersedability mismatch as
declared debt. **Their coverage is one kind and one fact.** The program generalizes a working
pattern.

## 2. Three layers, strictly

| Layer | Contains | Writable by |
|---|---|---|
| **Authored** | entity markdown + frontmatter; local YAML source surfaces | humans and agents |
| **Declared** | what a kind is: fields, states, placement, admissible relations | toolkit release only |
| **Derived** | graph, belief, snapshots, reports, renderings | rebuild only |

Authored and derived are the system's best existing property. The declared layer is where the
work is.

## 3. The declaration layer

Covers F1, F2, F4, F5.

D3/D5 ruled the shape: **JSON Schema is authoritative for entity fields, Pydantic is a projection
built after schema validation, and a reconciliation check binds them.** Generation was rejected.
That stands.

**Ownership matrix.** Rev 1 said "the declared layer is one thing" without saying who owns what,
which an implementer cannot act on. Authority stays distributed by *fact type*; what unifies is
the **read path**, not the storage:

| Fact | Authoritative artifact | Read through |
|---|---|---|
| Which fields a kind may carry | composed JSON Schema | `EntityValidator` / effective-fields API |
| Field types and invariants | composed JSON Schema | same |
| Status vocabulary | `EntityKind.statuses` | resolved declaration API |
| Placement (`home`) | `EntityKind.home` | resolved declaration API |
| Relation endpoint admissibility | `RelationKind` | `relation_allows_kinds` |
| Lineage capability | **currently split — S2 must rule it** | — |

Two rules make this legible rather than merely distributed:

- **One authoritative artifact per fact.** Not one artifact for all facts.
- **One resolved read API per fact, and consumers use only it.** No layer-3 module may carry its
  own table of a per-kind fact. The validator's legit-reader set and `mark_superseded`'s stamping
  policy are the current violations.

What the target adds beyond today:

- **Every kind is declared**, not 5 of 53.
- **Every kind is reconciled**, not 1 of 53.
- **The reverse supersedability direction is guarded** — `relation_allows ⇒ declares`, which
  today is unguarded and worked around defensively in `consolidation.py`.
- **Per-kind facts are written per kind**, explicitly, so one kind's declaration answers its own
  questions without a join.

The 12 half-wired kinds and the 3 unstampable kinds are S2's acceptance corpus: each ends up
carrying a real edge or losing a state it cannot reach, **by a written ruling per kind**.

## 4. Links and lineage

Covers F3, F7. **Rev 1 mandated deletions here on a false premise and this section is now
deliberately weaker.**

F3 is not seven spellings of one fact. It is at least four facts — replacement (`sci:supersedes`),
amendment (`sci:amends`, explicitly *without* replacing), identity resolution (`deprecated_ids`),
archive membership (`consolidated_into`) — plus a derived inverse D5 requires (`superseded_by`)
and a one-to-many split (`resynthesized_into`). Only the non-materializing top-level
`supersedes:` is clearly dead.

**Target:** a semantic taxonomy with an owner per fact, produced by S3 *before* any deletion is
specified. The only pre-committed constraint: each fact has one authored spelling, and derived
inverses are computed, never authored.

"Marked as such in-band" is left to S3 to specify concretely — the candidate mechanisms are a
read-only computed field, a schema annotation, or exclusion from the authored schema entirely.
Rev 1 asserted the requirement without a mechanism; naming one is S3's job.

F7 likewise: **six link surfaces is redundancy, not demonstrated divergence.** S4 begins as an
authority audit. Convergence is conditional on it showing conflict.

## 5. Claims and belief

Covers F8. **Mostly right; the target is conservative.**

Keep: belief derived and never authored; the versioned policy persisted with outputs; the refusal
to roll up across mixed policies; ceilings and caps; independence groups; propositions-as-edges.
The factoring of `belief_state` from verdict tokens is correct and stays.

Rev 1 proposed moving `derived_edge_status` to render time. **It is already there** — computed in
`render.py`, absent from the proposition-edge projection, stripped before output. The residual
gap is only that nothing *forbids* authoring `edge_status`, so the work is a guard, not a
migration.

## 6. The operator surface

Measured 2026-07-25: **46 top-level entries — 39 groups plus 7 single commands — and 278 leaf
commands**; 59 check modules emitting roughly 124 distinct rule names. (Rev 1 said "47 groups";
that was eyeballed, not counted.)

**The CLI is not excess.** 243 of 278 leaf commands (87%) are named in agent-facing docs. Size
alone is not the defect and "delete commands" is not the goal.

The original baseline here was wrong. As measured in
[S7a §1](2026-07-25-s7a-retired-command-surface-design.md#1-what-the-target-document-got-wrong),
all 22 retired callback bodies already raised replacement-naming errors; seven was the user
guide's list, not the retirement count. The actual defects were that help and discovery
presented those commands as live, and Click parameter validation could prevent the retirement
error from being reached
([S7a §2](2026-07-25-s7a-retired-command-surface-design.md#2-the-defect-that-is-actually-there)).

Target: **retired commands are absent or hidden from discovery, and every invocation rejects
before parameter validation with an error naming the replacement.** Also: every check message
must name an action its own system accepts — the `fb-2026-07-11-017` follow-on was exactly that
failure.

Not yet measured, therefore not claimed: whether the 39 groups carve the space well, whether
plural-kind groups duplicate `entity`, whether the check vocabulary overlaps. S7's audit.

## 7. What goes / what stays

| Goes | Why |
|---|---|
| Retired-but-registered commands | principle 2 — reachable wrong answers |
| Top-level `supersedes:` | materializes nothing; already flagged |
| Per-kind fact tables inside layer-3 consumers | §3 — one resolved read API per fact |
| States a kind cannot reach (the 12 + the 3) | promises the machinery does not keep |
| Undeclared kinds (48 of 53 today) | a kind with no schema is undeclared, not lightweight |

| Stays | Why |
|---|---|
| Authored-is-truth, derived-is-rebuildable | the foundation, and it works |
| Belief derived under a versioned, persisted policy | best idea in the system |
| Ceilings, caps, independence groups | encode what evidence *cannot* buy |
| Propositions-as-edges | the unification others should imitate |
| status/verdict as orthogonal axes | D1 ruled it; the matrix is right |
| The existing reconciliation and ratchet tests | the pattern the program generalizes |
| The large CLI, in the main | measured as documented and used |

Rev 1 listed "the 67-field god-object base" as going. Softened: it is a real legibility problem,
but the corrected F1 shows the schema layer — not the Python base class — is the authority for
fields. Whether the base shrinks is a *consequence* of S1b's coverage work, not a goal of its own.

## 8. How we get there

| | Sub-project | Covers | Depends on |
|---|---|---|---|
| **S7a** | Enforce existing retirements (unregister or error) | §6 | — **can ship now** |
| **S1a** | Generalize the reconciliation mechanism; make it a gate | F1 | — |
| **S1b** | Widen schema + reconciliation coverage toward 53 kinds | F1 | S1a |
| **S2** | Per-kind facts declared per kind; guard the reverse direction | F2, F4, F5 | S1a |
| **S3** | Lineage/amendment/identity/archive taxonomy, then convergence | F3 | S2 |
| **S4** | Link-authority **audit**; convergence only if divergence shown | F7 | — |
| **S5** | Guard forbidding authored/persisted `edge_status` | F8 | — |
| **S6** | Inquiry **audit**; unification only if divergence shown | F10 | — |
| **S7b** | Operator-surface audit (groups, duplication, rule vocabulary) | §6 | — |
| **S0** | Generalize the ratchet across fact classes | meta-finding | S1a |

Changes from rev 1's sequence, all from review:

- **S1 split.** S1a ships the mechanism as a gate over existing coverage; S1b widens coverage
  under it. Rev 1 bundled two very different bodies of work on the program's critical path.
- **S7a promoted to first.** The retirement fix is a principle-2 violation with no dependencies
  and a small diff. It should not wait behind the keystone.
- **S4 and S6 are audits first.** Rev 1 mandated convergence without demonstrated divergence,
  contradicting the inventory's own multiplicity-vs-divergence rule.
- **S5 shrank** from a migration to a guard, because the migration is already done.
- **S3 starts with a taxonomy**, not a deletion list.

**Breaking changes are expected.** Downstream projects pin toolkit revisions in `uv.lock`;
migrations ship with the change. No compatibility layers.

## 9. How we would know it worked

- The reconciliation gate covers every declared kind, not one.
- No layer-3 module contains a per-kind fact table.
- **Every derived surface carries a machine-readable pointer to its authoritative source** —
  the "says so where it is read" half of the principle, which rev 1 stated and then failed to
  test for.
- Every documented retirement is unreachable in-band.
- A newly added kind cannot arrive half-wired; the ratchet refuses it.
- No kind declares a state it cannot reach.

## 10. Open questions

1. Which kinds *should* carry supersession lineage? (S2 — the 12 + 3 are the corpus.)
2. Do the other 52 kinds enforce D1/D2 as `mixin-hypothesis-2.0` does, and what enforces it for
   kinds with no schema? (S1b.) *Rev 1 asked whether the axes survive; they were already ruled,
   and this is the real remaining question.*
3. Do the six link surfaces actually disagree? (S4 — measurement precedes design.)
4. Does the commons/project entity boundary survive S1, or does convergence dissolve it? (S1b.)
5. Are the plural-kind CLI groups duplicates of `entity`? (S7b.)

---

*One stance, not a technical row: an honest yellow warning is often the correct state of the
science. Nothing in this program should make a dashboard greener than the evidence.*
