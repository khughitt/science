# Contextual membership roles on hypothesis bundles — design

**Status:** Proposed — not yet scheduled. **Extends** (does not replace) the `epistemic-edges` facet
[`2026-06-08-epistemic-edges-design.md`](./2026-06-08-epistemic-edges-design.md) and resolves one
open question in the bundle-belief roll-up [`2026-06-11-bundle-belief-rollup-design.md`](./2026-06-11-bundle-belief-rollup-design.md).
**Created:** 2026-06-19. **Revised:** 2026-06-19 (v2) after review against the June 8 facet; v1 wrongly
proposed a second causal-edge vocabulary — see §8 for what changed and why.

**Origin.** Surfaced during a literature review of menopause × immune-state × post-acute-infection
syndromes (PAIS) in the `~/d/health` family. A recurring need: a single causal claim ("reproductive-stage
transition affects post-infectious recovery") has a plausible **reverse** ("infection/PAIS perturbs the
reproductive axis"), and the truth is likely *bidirectional*. The user asked the general question: **what
is the best way to represent a statement that plays a different role (rival explanation, reverse-cause,
background) in different hypotheses, while treating every proposition equally and evaluating it on
evidence rather than provenance?**

## 0. Authority boundary (read first)

This doc is **subordinate to** the `epistemic-edges` facet, the epistemic-data-model umbrella, and `h00`.
Where it and a reused authority disagree, the authority wins. In particular it **reuses without
replacing**:

- **The edge *is* the proposition.** A truth-apt causal-DAG edge is a relational `proposition`
  (`subject·predicate·object` + `polarity` + `claim_layer` + `identification_strength`), not linked to a
  separate edge (epistemic-edges §1, Invariant 1). There is **no separate `scic:*` causal layer to bridge
  to** — `*.edges.yaml` is dissolved, not synchronized.
- **No second edge vocabulary** (epistemic-edges Invariant 4 / D-005). `predicate` is the one new
  controlled vocabulary; `polarity` is the sole sign carrier; `epistemic_role` is t034 payload.
- **Graph roles are derived, not authored.** `mediator` / `confounder` / `collider` describe a
  proposition's *position in a patch relative to a focal effect*; they are **derived from patch topology +
  the query**, never written on a node or edge (epistemic-edges §2.1).
- **Bidirectional is already expressible.** Multiple relational propositions may share a
  `(subject, object)` pair (Invariant 3, D-006 multi-edge). A higher-order claim ("A *mediates* the effect
  of X on Y") is genuinely n-ary and is **deferred** (epistemic-edges §2.1, object-ranges-over-proposition
  extension).

The single thing this doc adds lives **off the causal edge entirely**: it is membership metadata on the
`cito:discusses` (proposition→hypothesis) relation. See §3.

## 1. The principle the model already encodes

Most of what the user wants is already the design, which sharply constrains what is left to add:

- **Polarity is on the edge, not the node**, and **belief aggregates over edges, not authorship**
  (`belief.py`). Provenance-neutrality — "a pet hypothesis is evaluated exactly like a literature-mined
  one" — is therefore already guaranteed: a proposition's warrant comes only from the evidence-lines
  targeting its IRI, never from who minted it.
- **Propositions are first-class and reusable.** One proposition can be `discusses`-linked to multiple
  hypotheses and targeted by multiple evidence-lines with different stances. "One statement, many
  contexts" is native.
- **The reverse-cause case needs no new machinery.** `P→` (reproductive stage → recovery) and `P←`
  (infection → reproductive axis) are simply two relational propositions over related endpoints; each
  accrues support/dispute independently; "truth in the middle" is *both* edges carrying moderate support.
  A strict DAG forbids the literal cycle, so the principled encoding is time-indexing
  (`menopause_t0 → PAIS`, `PAIS → menopause_t1`) — still two ordinary propositions, no "bidirectional"
  object.

**What is genuinely missing** is *not* on the causal edge. It is that the `cito:discusses` edge — a
proposition's membership in a hypothesis bundle — carries **no label for how the proposition participates
in that bundle**. `P←` is a *core* member of a hypothesis about infection-driven reproductive perturbation
and, simultaneously, a *rival* that a forward-only hypothesis (h0005) must rule out. Today both
memberships are the same unlabeled `discusses` triple.

## 2. The gap (precisely, and only this)

1. **`discusses` carries no role.** `PropositionEntity.discusses` is `list[str]`
   (`science/model/src/science_model/propositions.py:52`); materialization emits a bare
   `(prop, cito:discusses, hyp)` triple (`science/src/science_tool/graph/materialize.py:599`) with no
   payload; the generic authored-relation model carries only `predicate`/`target`/`graph_layer`
   (`science/model/src/science_model/source_contracts.py:19`). So "how this proposition participates in
   this hypothesis" lives only implicitly in hypothesis prose.
2. **The roll-up reads every member as conjunctive.** The bundle-belief member enumerator unions "forward
   `sci:hasProposition` ∪ reverse `cito:discusses`" with **no role distinction**
   (`science/src/science_tool/graph/bundle_belief.py:36`), then applies weakest-link `min` across all
   members. A proposition discussed *as a rival* is therefore silently counted as a conjunctive member the
   bundle stands or falls on — the wrong semantics. The June 11 design flags whether non-core members
   belong in the roll-up as an open question (§7); this doc closes it.

## 3. Proposal: an authored `membership_role` on `cito:discusses`

Add a small, closed, **frame-relative** role to the proposition→hypothesis membership relation — and
**nowhere else**. The role answers "what part does this proposition play *in this hypothesis's bundle*,"
not "what causal position does it occupy" (that is derived, §0).

### 3.1 The role-assignment is per-membership, not per-node

Because the same proposition participates differently in different bundles, the role cannot live on the
proposition. It is a property of the `(proposition, frame)` membership pair — a role-assignment object
`{proposition, frame, role}`, where `frame` is the bundle IRI. **`frame` ranges over any bundle frame —
hypothesis *or* mechanism** — because the roll-up (`bundle_members`) unions `sci:hasProposition`
(mechanisms) with reverse `cito:discusses` (hypotheses); the field is named `frame` (not `hypothesis`)
for exactly that reason. This is the literal implementation of "one statement, multiple contextual roles,"
and it stays inside the patch/membership machinery epistemic-edges §4–§5 already establishes (patch
membership is durable on the proposition / its named-graph), so it introduces **no new store**.

### 3.2 Vocabulary (closed, deliberately small)

- `core` — a conjunctive member the bundle's truth depends on (the default; preserves today's behavior).
- `rival` — a competing / alternative account the hypothesis is contrasted *against* (includes the
  reverse-causal case relative to a forward-only hypothesis). **Not** part of the conjunction.
- `background` — a contextualizing constraint that informs but does not test the bundle. **Not** part of
  the conjunction.

Named distinctly from the evidence-line `evidence_role` enum (`direct_test | proxy_support |
background_constraint | negative_control | model_criticism`) on purpose: `evidence_role` classifies how a
*piece of evidence* bears on a claim; `membership_role` classifies how a *claim* participates in a
*hypothesis bundle*. They live on different edges and must not be conflated.

Explicitly **out of scope** (ceded to epistemic-edges, per §0): `confounding_path`, `mediating_path`,
`collider`, `effect_modifier`. These are causal-graph roles derived from topology + query, or higher-order
n-ary claims — never authored labels. v1 of this doc does not mint them.

### 3.3 Bundle-belief semantics (must gate from day one — not left open)

The roll-up changes the moment a role exists, so the conjunction must be gated atomically with the schema
change. **Exactly one consumer changes in v1; everything else stays role-blind:**

- **Conjunctive belief** (`bundle_belief.py` `bundle_members` → weakest-link `min`) enumerates **`core`
  members only**. `rival` and `background` members are **excluded from the conjunction** so they cannot
  raise or lower a bundle's warranted belief.
- **Coverage stays role-blind in v1.** The coverage signal (June 11 §7) and the linked-claim consumers
  (`evidence_signals._linked_claims_for_hypothesis`, `summary._hypotheses_for_claim`) **continue to count
  every linked claim regardless of role** — a rival being discussed *is* coverage of the hypothesis's
  neighborhood, which is what coverage is meant to measure. This is deliberate, not an oversight: it keeps
  v1 to a single behavioral change and avoids re-tuning coverage semantics.
- A dedicated **rival-contrast channel** (surfacing `rival` members as explicit alternatives rather than
  folding them into coverage) is **deferred** — see §7.
- **Migration default = `core`.** Every existing unlabeled `discusses` edge becomes `core`, so the
  conjunction is byte-for-byte unchanged until a curator marks a member `rival`/`background`. No silent
  reinterpretation of the existing corpus.

## 4. Why not the alternatives

- **Role on the proposition node** — rebinds role to the statement; breaks reuse; contradicts the
  edge-not-node discipline. Rejected.
- **A second causal-edge vocabulary / `structural_role` on causal edges** (v1's mistake) — forbidden by
  epistemic-edges Invariant 4, and redundant: confounder/mediator/collider are *derived* from patch
  topology, not authored. Rejected.
- **A dedicated "reverse-causation" entity** — unnecessary; reverse causation is just a second relational
  proposition (multi-edge), optionally `rival`-roled relative to a forward hypothesis. Rejected.
- **Leaving roll-up gating "open"** — would let rivals inflate/deflate conjunctive belief silently.
  Rejected; §3.3 closes it.

## 5. Storage contract & migration

Concrete shape (final form deferred to the v3 entity layout, but the contract is fixed here):

- **Authoring:** `discusses` widens from `list[str]` to accept either a bare string (sugar for
  `{frame: <bundle IRI>, role: core}`) or a `{frame, role}` object. Bare strings remain valid and mean
  `core`.
- **Materialization — annotate, never replace.** The plain triple `(prop, cito:discusses, frame)` is
  **always emitted**, exactly as today, so every existing consumer that pattern-matches it keeps working
  unchanged: `bundle_members` (`bundle_belief.py:35`), `_linked_claims_for_hypothesis`
  (`store/evidence_signals.py:22`), `_hypotheses_for_claim` (`store/summary.py:243`), cross-impact, patch
  membership, and mutations. The role is carried **alongside** as a separate **membership statement**
  — a dedicated `MembershipAssignment` node (or an RDF-star qualified-relation annotation on the
  `cito:discusses` statement), holding `(proposition, frame, membership_role)`.
- **This is plumbing, not a proposition.** The membership statement is a **non-truth-apt organizational
  link** (epistemic-edges §2.4): it carries **no belief**, takes **no evidence**, and is **not** an
  edge-as-node. It must *not* borrow the epistemic-edges "edge-node IRI = relational proposition" model —
  there the edge node *is* a truth-apt causal claim; here `cito:discusses` is membership plumbing. Keeping
  them distinct is the whole point of the §0 boundary.
- **Consumption:** in v1, **only** `bundle_belief.py`'s conjunction reads `membership_role` (gating `core`
  members into the weakest-link `min`, §3.3). Coverage and linked-claim consumers stay role-blind (§3.3).
  Belief on the proposition itself is untouched — it still derives purely from evidence-lines targeting
  its IRI.
- **Migration:** mechanical and lossless — every existing edge keeps its plain triple and gains a
  `role: core` membership statement. No curation gate required to land the schema; curators add
  `rival`/`background` opportunistically.

**Validation (loud-fail at load, per the framework's loud-fail discipline):**

1. `membership_role` ∉ {`core`, `rival`, `background`} → reject (closed enum).
2. A `{frame, role}` object missing `frame`, or with a `frame` that does not resolve to a bundle entity
   (hypothesis or mechanism), → reject. A `frame` resolving to a non-bundle entity → reject.
3. Duplicate memberships for the same `(proposition, frame)` pair with **conflicting** roles → reject
   (a proposition plays exactly one role per bundle). Identical duplicates may be deduped or rejected;
   pick one and state it in the `-plan`.
4. Mixing bare-string and object entries is allowed (string = `core` sugar), but a string and an object
   naming the **same** `frame` is a duplicate and falls under rule 3.

## 6. Prerequisite: a real test case

Exercising this needs a hypothesis with genuine rival/bidirectional structure as first-class entities.
The motivating case, `post-acute-infection:hypothesis:0005-reproductive-stage-immune-homeostatic-margin`,
is still in the **unmigrated prose style** (a "Proposition Bundle" inside the hypothesis file). A migration
task (PAIS project) promotes h0005's bundle to first-class `proposition` + `evidence-line` entities —
forward `P→`, reverse `P←` (roled `rival` relative to h0005), plus the confounding/collider cautions in
DAG task `t014` (which, per §0, are *derived* once the patch topology exists, not authored here). That
becomes the first test bed.

## 7. Open questions (genuinely open)

- Should `core` be implicit (absence of role) or always materialized explicitly? (Lean: implicit at
  authoring, explicit after compile, matching the workbench round-trip in epistemic-edges §5.)
- **Rival-contrast channel (deferred from §3.3):** should `rival` members be surfaced as explicit
  alternatives a bundle is tested against (a contrast view), rather than folded into the role-blind
  coverage count? v1 folds them; a dedicated channel is post-v1 work once curators have actually labeled
  rivals in the corpus.
- Does `background` warrant a separate coverage sub-channel, or fold into the existing June 11 coverage
  signal? (Lean: fold.)
- Relationship to the active **prose-epistemics** workstream: is `membership_role` better surfaced as a
  prose-derived label first, then formalized? (Likely yes — derive before authoring.)

## 8. What changed from v1 (and why)

v1 proposed a `structural_role` enum on `discusses` *and on causal edges*, plus a join between
propositions and a separate `scic:*` causal layer. Review against the June 8 epistemic-edges facet found
this conflated two things and violated the facet's invariants:

- v1's causal-edge vocabulary is the **second edge vocabulary** Invariant 4 forbids; v2 adds nothing to
  causal edges.
- v1's `confounding_path`/`mediating_path`/`collider`/`effect_modifier` are **derived graph roles** (§2.1)
  or higher-order n-ary claims, not authorable edge labels; v2 drops them entirely.
- v1's §3.3 "bridge the epistemic and causal layers" assumed two stores to join; the facet **dissolves**
  the causal store into propositions, so there is nothing to bridge; v2 deletes it.
- v1 left bundle-belief gating as an open question; v2 closes it (§3.3) because the roll-up reinterprets
  membership the instant a role exists.

What survives is the genuinely uncovered piece: a frame-relative **membership role on the hypothesis
bundle edge**, which is exactly "a statement plays different roles in different contexts" expressed where
the model actually lacked it.
