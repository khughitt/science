# Unifying `cito:discusses` emission across authoring surfaces — design

**Status:** Proposed — not yet scheduled. **Follows** (does not replace)
[`2026-06-19-contextual-structural-roles-design.md`](./2026-06-19-contextual-structural-roles-design.md)
and its [`-membership-roles-implementation-plan.md`](./2026-06-19-membership-roles-implementation-plan.md).
**Created:** 2026-06-19.

**Origin.** Surfaced during a pilot audit of the `mm30` project after the membership-roles feature shipped.
Two governance propositions (`0011`, `0012`) needed `role: background` in hypotheses `0001`/`0002`, but they
were authored as `cito:discusses` edges in the **authored-relations store** (`knowledge/sources/local/relations.yaml`),
not in proposition frontmatter — and the membership-roles feature only reads roles off the **frontmatter**
surface. The edges materialized as silent `core`. The workaround relocated those two memberships into
frontmatter (committed `mm30@1cfa2592`). This doc addresses the architectural gap that workaround stepped around.

## 0. Authority boundary (read first)

This doc is **subordinate to** the contextual-roles design and everything it is subordinate to
(`epistemic-edges`, the epistemic-data-model umbrella, `h00`). It **reuses without replacing**:

- **The closed role vocabulary** `core | rival | background` (contextual-roles §3.2). No new values.
- **Annotate, never replace** (contextual-roles §5): the plain `(prop, cito:discusses, frame)` triple is
  always emitted; the role rides alongside on a separate non-truth-apt `BundleMembership` node.
- **Migration default = `core`** (contextual-roles §3.3): an unlabeled membership is `core`, and the
  conjunction is unchanged on the existing corpus until a curator labels a member.
- **The membership node is plumbing, not a proposition** (contextual-roles §5): it carries no belief and
  takes no evidence.

This doc adds **no new vocabulary and no new semantics**. It is purely about **where in the code the role
node is emitted**, so that the role is honored no matter which authoring surface declares the edge.

## 1. The gap: one role-aware emitter out of three

The contextual-roles design assumed a single authoring path — proposition frontmatter `discusses:`. In
practice `cito:discusses` is emitted from **three** independent code sites, and only one writes the role
node:

| # | Surface | Emission site | `BundleMembership` node? | Role-aware? |
|---|---|---|---|---|
| 1 | Proposition frontmatter `discusses:` | `graph/materialize.py:642–648` | ✅ emitted | ✅ honors `{frame, role}` |
| 2 | Authored-relations store (`relations.yaml`) | `graph/materialize.py:1208` (generic `_add_authored_relation`) | ❌ | ❌ → silent `core` |
| 3 | Store CLI bridge (`science … --bridge-between`) | `graph/store/mutations.py:228` | ❌ | ❌ → silent `core` |

So the relations.yaml gap the `mm30` audit hit and the store-CLI bridge gap are **the same defect, twice**:
`BundleMembership` emission is welded to emitter #1. A reader who patches only `_add_authored_relation`
fixes surface #2 and leaves surface #3 silently `core` forever, and leaves the door open for a fourth
emitter to drift in. Per the framework's own **"fail early / avoid silent fallbacks"** discipline, the
current "no membership node ⇒ assume `core`" default (`bundle_belief.py:72`) is exactly the silent fallback
to eliminate as the primary mechanism.

### 1.1 A second, latent asymmetry the gap hides

The two surfaces already **disagree on what a valid `discusses` target is**:

- The frontmatter emitter **loud-fails** a frame that is not a `hypothesis`/`mechanism`
  (`materialize.py:633–640`, contextual-roles §5 rule 2).
- The relations.yaml path applies only the generic relation-profile endpoint check, and the predicate's
  own description advertises a broader range — `"Structural link to hypothesis/topic"`
  (`store/constants.py:208`).

So a `cito:discusses` edge to a **topic** is rejected via frontmatter but potentially accepted via
relations.yaml. Unifying emission forces this latent inconsistency to be resolved explicitly (§3.3) rather
than left to depend on which surface an author happened to use.

## 2. The principle: a single emission chokepoint

There must be **exactly one function** allowed to add a `cito:discusses` triple to the knowledge graph, and
it **always** emits the role node for a bundle frame. Each authoring surface decides *how it sources the
role* (frontmatter object form; a relations.yaml field; a CLI flag) and then calls the one chokepoint.
This is the DRY/composition fix: it makes a role-blind `cito:discusses` edge **unrepresentable in the
codebase**, so no future fourth surface can reintroduce the gap.

```
emit_discusses_membership(graph, *, prop_uri, frame_uri, prop_cid, frame_cid, role=CORE)
    │  loud-fail if frame_cid is not a bundle (hypothesis|mechanism)   [§3.3]
    │  graph.add((prop_uri, cito:discusses, frame_uri))                # plain triple, as today
    └  emit BundleMembership node {membershipProposition, membershipFrame, membershipRole=role}
```

`membership_role()`'s `CORE` default (`bundle_belief.py:72`) then degrades from *primary mechanism* to a
**safety net** for the two cases that legitimately have no membership node — forward `sci:hasProposition`
members (authoritatively `core`, contextual-roles, by structure) and legacy graphs compiled before this
change. Authored edges always carry an explicit role node.

## 3. Per-surface role plumbing

### 3.1 Frontmatter (surface #1) — no behavior change

Already correct. It is refactored to call the chokepoint instead of inlining the triple + node, so all
three surfaces share one implementation. Output is byte-for-byte identical.

### 3.2 Authored-relations store (surface #2)

- `SourceRelation` (`graph/sources.py:88`) gains an optional `role: MembershipRole | None = None`.
- `_add_authored_relation` special-cases `predicate == cito:discusses` with a resolved **live entity**
  object → call the chokepoint with `role = relation.role or MembershipRole.CORE`. All other predicates,
  and discusses edges whose object is external/archived rather than a live bundle, keep the existing
  generic `graph.add` path (membership applies only to live bundle entities).
- Authoring shape in `relations.yaml`:
  ```yaml
  - subject: proposition:0011-…
    predicate: cito:discusses
    object: hypothesis:0001-…
    role: background          # optional; absent = core
  ```

### 3.3 Store CLI bridge (surface #3)

- `science … --bridge-between` (`cli.py:2367`) creates a proposition that bridges hypotheses; each ref
  emits `(prop, cito:discusses, hyp)` plus `sci:bridgeBetween` provenance (`mutations.py:225–229`).
  Semantically a bridge is a **`core`** cross-hypothesis member, so the default is correct; the gap is only
  the *inability to express a non-core bridge*.
- Add `--role <core|rival|background>` to the command; thread it into `mutations` and call the chokepoint.
  The `sci:bridgeBetween` provenance triple is unchanged.

### 3.4 Resolving the topic-target asymmetry (§1.1)

The canonical decision, inherited from contextual-roles §5 rule 2: **`cito:discusses` targets must be
bundles (hypothesis/mechanism).** The chokepoint enforces this uniformly with a loud-fail, so relations.yaml
discusses-to-non-bundle stops being silently accepted. The implementation plan includes a **corpus audit
task** to find any existing non-bundle discusses edges in relations.yaml before the loud-fail lands, so the
change cannot silently break a project at compile time. (`mm30` already has none after the pilot cleanup.)

## 4. Validation (loud-fail at load, per framework discipline)

In addition to the contextual-roles §5 rules (already enforced on the frontmatter surface), the new field
adds:

1. `SourceRelation.role` set **and** `predicate != cito:discusses` → reject. A role is meaningless on a
   non-membership relation.
2. `SourceRelation.role` set **and** the object does not resolve to a bundle → reject (same rule the
   chokepoint enforces; validate surfaces it earlier with a clearer message).
3. `SourceRelation.role` value ∉ `{core, rival, background}` → reject (closed enum, reuse
   `MEMBERSHIP_ROLE_VALUES`).
4. A frame labeled with **conflicting roles across surfaces** — e.g. frontmatter says `background` and
   relations.yaml says `core` for the same `(proposition, frame)` — → reject. This generalizes
   contextual-roles §5 rule 3 ("one role per `(proposition, frame)`") across surfaces, since the chokepoint
   would otherwise mint two membership nodes for one pair.

## 5. Why not the alternatives

- **Two-line patch to `_add_authored_relation` only.** Fixes surface #2, leaves #3 silently `core`, and
  leaves the role node welded to a second site — the divergence simply moves. Rejected: doesn't fix the
  class of bug.
- **Collapse to one surface (frontmatter-only `discusses`; ban relations.yaml / store-CLI discusses).**
  Conceptually cleanest — membership becomes a property of the proposition with zero divergence by
  construction. But it removes a legitimate bulk/structured-authoring path and the bridge workflow, and is
  a larger, breaking policy change. Reasonable as a *future* deprecation if relations-store memberships
  never materialize in practice; not the right default for closing this gap now. Rejected as the default.
- **Make the membership node truth-apt / an edge-as-node.** Forbidden by contextual-roles §5 and the
  epistemic-edges boundary. The node is plumbing. Rejected.

## 6. Migration & corpus impact

- **Frontmatter:** zero change (output identical).
- **Relations.yaml & bridge:** discusses edges from these surfaces **begin emitting** a `role: core`
  `BundleMembership` node where none existed. This is additive and benign — `core` is the existing default
  behavior — but it changes graph output (more triples) and must be accompanied by a graph rebuild. The
  conjunction result is unchanged because every new node is `core`.
- **Corpus audit (plan task):** before the non-bundle loud-fail lands, scan all projects' `relations.yaml`
  for `cito:discusses` edges whose object is not a bundle; reconcile each (retarget or remove). The roles
  doc (`skills/research/proposition-schema.md`) is updated to drop the "relations.yaml is always core,
  author in frontmatter" caveat once the surface supports roles.

## 7. Open questions

- **Sequencing.** The chokepoint refactor (§2–§3.1, routing all three emitters through one always-explicit
  emitter) is worth landing **independently of demand** — it is a small DRY/correctness win that kills the
  silent fallback. The surface ergonomics (`SourceRelation.role`, `--role`) can follow when a real
  non-frontmatter non-core membership appears. The plan orders tasks so the refactor is shippable on its
  own (Tasks 1–3) and the surface fields are additive (Tasks 4–5).
- **Resolves a contextual-roles open question.** Contextual-roles §7 asked: "Should `core` be implicit
  (absence of role) or always materialized explicitly? (Lean: explicit after compile.)" The chokepoint
  implements **explicit after compile for every surface** — the recommended answer, now uniform rather than
  frontmatter-only.
- **Should `bridge_between` keep its `sci:bridgeBetween` provenance** once a `BundleMembership` node also
  exists, or is the membership node sufficient? (Lean: keep both — `bridgeBetween` is consumed by the
  causal exporters `export_pgmpy.py` / `export_chirho.py`; do not disturb them in this work.)
