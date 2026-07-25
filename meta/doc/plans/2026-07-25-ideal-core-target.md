# The ideal core — target state

**Date:** 2026-07-25
**Status:** Working target. **Revised, not refuted** — implementation evidence changes this
document; it does not get defended against.
**Input:** [`2026-07-25-multi-surface-fact-inventory.md`](2026-07-25-multi-surface-fact-inventory.md)
**Optimizing for:** *agent legibility.* When principles conflict, the winner is whichever makes
a wrong answer harder to reach.

This is deliberately thin. It states what "good" looks like and what has to go, so each
sub-project can be judged against something. It is not a spec, and it does not re-decide
anything already ruled (D1–D5, D-001…D-011).

## 1. The operating principle

> **Every fact has exactly one owner. Every other surface derives from that owner, and says
> so where it is read.**

The recurring defect is not complexity — it is *authority without a single source*. Six
inventory rows are the same failure: a fact stored where it was needed instead of declared once.

Because the primary operator is an agent, the failure mode is specific and severe. An agent
reads one surface and trusts it. It does not cross-check three declarations for agreement, and
it has no way to know a fourth exists. A stale copy is not a maintenance annoyance here; it is a
wrong answer delivered with full confidence.

Three consequences, in priority order:

1. **Zero redundancy of authority.** Redundant *prose* is fine and often good. A second place
   that can be *believed* is not.
2. **A wrong answer must be unreachable, not discouraged.** Documentation saying "this is
   retired" is not a retirement. If it can be called, it will be called.
3. **Boring beats clever.** Fifty-three explicit declarations an agent can read in one place
   beat one elegant derivation it has to reconstruct. Derivation is for *consumers* of a fact,
   never for the *statement* of it.

## 2. Three layers, strictly

| Layer | Contains | Writable by |
|---|---|---|
| **Authored** | entity markdown + frontmatter; the local YAML source surfaces | humans and agents |
| **Declared** | what a kind is: fields, states, placement, admissible relations, lineage | toolkit release only |
| **Derived** | graph, belief, snapshots, reports, renderings | rebuild only, never by hand |

Authored and derived are already right, and are the system's best existing property. **The
declared layer is the whole problem.** Today it is split three ways (`EntityKind` descriptors,
Pydantic classes, JSON Schema mixins) *and* partially embedded in layer-3 consumers — the
validator's legit-reader set, materialize's endpoint rules, `mark_superseded`'s stamping policy.
Facts about kinds live inside the code that reads them.

**Target: the declared layer is one thing, and no layer-3 module contains a fact about a kind.**
A consumer needing such a fact asks the declaration. If the declaration cannot express it, that
is a gap to close in the declaration, not a local table to add.

## 3. The declaration layer

Covers F1, F2, F4, F5, F9.

D3/D5 already ruled the shape: **JSON Schema is authoritative, Pydantic is a projection built
after schema validation, and a reconciliation check binds them.** Code generation was
considered and rejected. That ruling stands; this document does not reopen it.

What the target adds is completeness and the missing binding:

- **Every kind is declared.** Not 5 of 53. A kind with no schema is not a lightweight kind, it
  is an undeclared one.
- **Every per-kind fact is declared, explicitly, per kind.** Statuses today; also placement,
  which state axes apply, which relations it may source and target, and whether it carries
  lineage. Written out per kind rather than inferred from a family rule — an agent reading one
  kind's declaration should see its answers, not a join.
- **The reconciliation check exists and gates.** D3 point 4, unimplemented today. It is the
  mechanism that would have caught both F1 and F2, and it is the highest-leverage single item
  in the program.
- **Four state axes or one, but declared either way.** `status`, `phase`, `verdict`,
  `disposition`, `role` are in use; one is declared. D1/D2 already ruled the semantics; the
  declaration has not caught up.

The 12 dead-letter `superseded` terminals and the 3 unstampable kinds are the acceptance corpus.
Each must end up either carrying a real edge or losing a status it could never earn — **by a
written ruling per kind**, not by an implementation arc running out of room.

## 4. Links and lineage

Covers F3, F7.

**Lineage: one authored spelling.** Seven exist. The canonical edge (`relations:` with the
predicate) is the one; everything else is either derived-and-labelled or deleted. `superseded_by`
and friends survive only if they are *derived* and marked as such in-band.

**Links: two authored spellings, maximum.** One untyped associative and one typed. `discusses:`
becomes a typed relation carrying a role. The local YAML surfaces stay only as *compiled inputs*
with no independent authority — a link's meaning must not depend on which file it was written in.

## 5. Claims and belief

Covers F8. **This is the part that is mostly right**, and the target is conservative here.

Keep: belief derived and never authored; the versioned aggregation policy persisted with its
outputs; the refusal to roll up across mixed policies; ceilings and caps as first-class;
independence groups; propositions-as-edges. These are the system's best ideas and several are
rare. The factoring of `belief_state` (a reading of a proposition) from verdict tokens (a
conclusion about a test) is *correct* and stays.

Change one thing: **derived projections are computed at the point of use, never stored.**
`derived_edge_status` is self-described as "a lossy compatibility projection over canonical
state." Under principle 1 that is a second believable answer. It becomes a rendering function or
it goes.

## 6. The operator surface

The agent's real interface. Measured 2026-07-25: **278 leaf commands** across 39 groups plus 7
top-level; **59 check modules** emitting roughly **124 distinct rule names**.

**A correction to an earlier impression.** I had assumed this surface was substantially excess.
It is not: **243 of 278 commands (87%) are named in agent-facing docs.** The CLI is large and
*documented*, not orphaned. Size alone is not the defect, and "delete commands" is not the goal.

The defect is narrower and worse:

> **Retirement is prose-only.** The user guide states that `inquiry add-node`, `add-edge`,
> `add-assumption`, `add-transformation`, `set-estimand`, `graph add concept`, and
> `graph add proposition --bridge-between` are retired. All are fully registered, callable, and
> advertise themselves with encouraging help text. `set-estimand --help` documents required
> options. Nothing in-band tells an agent not to use them.

This is principle 2 violated exactly. An agent reading `--help` is reading the wrong answer with
no signal. The target:

- **A retired command is unregistered, or it errors telling you what to do instead.** There is no
  third state.
- **Every check's message names an action its own system will accept.** The `fb-2026-07-11-017`
  follow-on was precisely this failure: an ERROR prescribing a form the graph rejects. A check
  that cannot name a valid remedy must say so rather than invent one.
- **Rule names are a declared vocabulary**, not 124 strings that happen to appear in `Result(...)`
  calls.

**Not yet measured, and therefore not yet claimed:** whether the 39 groups carve the space well,
whether plural-kind groups duplicate the `entity` group, and whether the check vocabulary has
overlaps. Those need their own audit before this chapter earns a stronger opinion.

## 7. What goes

| Goes | Why |
|---|---|
| Retired-but-registered commands | principle 2 — reachable wrong answers |
| Stored derived projections (`derived_edge_status`) | principle 1 — a second believable answer |
| Six of the seven lineage spellings | principle 1 |
| Per-kind facts embedded in layer-3 consumers | §2 — declaration belongs in the declared layer |
| Declared-but-unreachable vocabulary (12 terminals, 2 reserved composition rules) | promises the machinery does not keep |
| The 67-field god-object base | §3 — undeclared kinds wearing a shared coat |

| Stays | Why |
|---|---|
| Authored-is-truth, derived-is-rebuildable | the system's foundation, and it works |
| Belief derived under a versioned, persisted policy | best idea in the system |
| Ceilings, caps, independence groups | encode what evidence *cannot* buy |
| Propositions-as-edges | the unification everything else should imitate |
| status/verdict as orthogonal axes | D1 ruled it; the matrix is right |
| The large CLI, in the main | measured as documented and used, not excess |
| Honest yellow | a stance, not a slogan |

## 8. How we get there

Sub-projects, each its own design → plan → implementation cycle:

| | Sub-project | Covers | Depends on |
|---|---|---|---|
| **S1** | Bind the two entity-shape declarations (D3 point 4, then widen coverage) | F1 | — |
| **S2** | Per-kind facts declared per kind, not embedded in consumers | F2, F4, F5, F9 | S1 |
| **S3** | Collapse lineage to one authored spelling | F3 | S2 |
| **S4** | Link-authoring convergence | F7 | S1 |
| **S5** | Demote stored projections to render-time | F8 | — |
| **S6** | Inquiry store unification | F10 | — |
| **S7** | Operator-surface audit, then retirement enforcement | §6 | — |
| **S0** | Generalize S1's reconciliation into a multiplicity ratchet | meta-finding | S1 |

S1 first: it is the keystone, and its direction is already ruled, so it is implementation of an
adopted contract rather than a new decision. S5, S6, S7 are independent and can run any time.

**Breaking changes are expected.** Downstream projects pin toolkit revisions in `uv.lock`, so
each upgrades on its own schedule; migrations ship with the change. No compatibility layers —
that is what produced `derived_edge_status`.

## 9. How we would know it worked

- The reconciliation check exists, gates, and covers every kind.
- No layer-3 module contains a per-kind fact table.
- Every documented retirement is unreachable in-band.
- A new kind added to the profile cannot arrive half-wired — the ratchet refuses it.
- The dead-letter corpus is empty: no kind declares a state it cannot reach.

## 10. Open questions

Deliberately unresolved; each belongs to a sub-project, not here.

1. Which kinds *should* carry supersession lineage? (S2 — the 12 dead letters are the corpus.)
2. Do the four state axes survive as four, or collapse under D1/D2? (S2.)
3. Are the plural-kind CLI groups duplicates of `entity`? (S7 — needs measurement.)
4. Does the commons/project entity boundary survive S1, or does convergence dissolve it? (S1.)
