# Unifying bundle-membership emission on `cito:discusses` — design

**Status:** Proposed — not yet scheduled. **Follows** (does not replace)
[`2026-06-19-contextual-structural-roles-design.md`](./2026-06-19-contextual-structural-roles-design.md)
and its [`-membership-roles-implementation-plan.md`](./2026-06-19-membership-roles-implementation-plan.md).
**Created:** 2026-06-19. **Revised:** 2026-06-19 (v2) after code review — see §9 for what changed and why.

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
- **The membership node is plumbing, not a proposition** (contextual-roles §5): no belief, no evidence.

This doc adds **no new vocabulary and no new semantics**. It is purely about **where in the code the role
node is emitted**, so the role is honored no matter which authoring surface declares a *membership* edge.

## 0.1 Policy decision: `cito:discusses` stays general; membership is the bundle subtype

**The decision the review demanded, stated once and used everywhere below.** `cito:discusses` is a
**general structural predicate** and remains so. The framework already materializes non-membership
discusses edges and tests them — e.g. `paper → cito:discusses → question`
(`science/tests/test_graph_materialize.py:896`), and the predicate is registered as a "Structural link to
hypothesis/topic" (`store/constants.py:208`). This feature does **not** redefine `cito:discusses` as
membership-only.

A **bundle membership** is the *subtype* of `cito:discusses` whose **subject is a proposition** *and* whose
**object resolves to a bundle** (`hypothesis` or `mechanism`). Both sides matter: `bundle_members`
(`bundle_belief.py:47`) admits only `rdf:type sci:Proposition` subjects, so a membership node on a
non-proposition subject would be dead, invalid data. Only the proposition→bundle subtype:

- carries a `BundleMembership` role node,
- flows through the emission chokepoint (§2),
- participates in the bundle-belief conjunction (`bundle_belief.py`).

Every other discusses edge — `paper → question`, `paper → hypothesis`, `proposition → topic`,
discusses → external ontology term — is a plain structural link: materialized verbatim on the existing
generic path, **no membership node, no role, and no new restriction**. Note `paper → hypothesis` in
particular: the object *is* a bundle, but the subject is not a proposition, so it is **not** a membership. The frontmatter `discusses:` field is the one place that is membership *by
definition* (its declared purpose is bundle membership), which is why it already loud-fails a non-bundle
frame (`materialize.py:633-640`); that behavior is correct and unchanged. There is no "asymmetry to fix"
between surfaces — there are two legitimate uses of one predicate, and this design preserves both.

## 1. The gap: one role-aware emitter of bundle memberships out of three

`cito:discusses` is emitted from **three** independent code sites. For the **bundle-membership** subtype,
only one of them writes the role node:

| # | Surface | Emission site | Membership (prop→bundle) handling | Role-aware? |
|---|---|---|---|---|
| 1 | Proposition frontmatter `discusses:` | `graph/materialize.py:642–648` | emits `BundleMembership` node | ✅ honors `{frame, role}` |
| 2 | Authored-relations store (`relations.yaml`) | `graph/materialize.py:1208` (generic `_add_authored_relation`) | bare triple, **no node** | ❌ → silent `core` |
| 3 | Store CLI bridge (`science … --bridge-between`) | `graph/store/mutations.py:228` | bare triple, **no node** | ❌ → silent `core` |

So the relations.yaml gap the `mm30` audit hit and the store-CLI bridge gap are **the same defect, twice**:
`BundleMembership` emission is welded to emitter #1. A reader who patches only `_add_authored_relation`
fixes surface #2 and leaves surface #3 silently `core`. Per the framework's **"fail early / avoid silent
fallbacks"** discipline, the current "no membership node ⇒ assume `core`" default (`bundle_belief.py:72`) is
the silent fallback to demote from *primary mechanism* to *safety net*.

## 2. The principle: a single chokepoint for bundle-membership emission

There must be **exactly one function** that emits a **bundle-membership** discusses edge (proposition
subject, bundle object), and it **always** writes the role node. Each authoring surface decides *how it
sources the role* (frontmatter object form; a relations.yaml field; a CLI flag), gates on
*proposition→bundle*, and then calls the one chokepoint. Every other discusses edge keeps the existing
generic `graph.add` path untouched.

```
emit_discusses_membership(graph, *, prop_uri, frame_uri, prop_cid, frame_cid, role=CORE)
    │  precondition guard: frame_cid is a bundle (hypothesis|mechanism), else loud-fail   [§3.4]
    │  graph.add((prop_uri, cito:discusses, frame_uri))                # plain triple, as today
    └  emit BundleMembership node {membershipProposition, membershipFrame, membershipRole=role}
```

This makes a **role-blind bundle-membership edge unrepresentable** in the codebase: any discusses edge from
a proposition to a bundle is minted here, with a role. `membership_role()`'s `CORE` default (`bundle_belief.py:72`)
then degrades to a **safety net** for the two cases that legitimately have no node — forward
`sci:hasProposition` members (authoritatively `core` by structure) and legacy graphs.

### 2.1 Invariant (narrowed from v1) and how it is verified

**Invariant:** every `(proposition, cito:discusses, bundle)` triple has a corresponding `BundleMembership`
node minted by `emit_discusses_membership`, and **no** `BundleMembership` node exists for a non-proposition
subject. All other discusses edges are deliberately *not* routed through the chokepoint.

Because the membership/non-membership split is dynamic (it depends on the resolved subject *and* object
kinds), a static grep for `graph.add((…, cito:discusses, …))` is **not** a sufficient check — it cannot tell
a proposition→hypothesis edge from a paper→question one. Verification is therefore a **coverage assertion
over a built graph** (a test / structural validate check): for every materialized `cito:discusses` triple
whose subject is a `proposition` and object is a `hypothesis`/`mechanism`, assert a `BundleMembership` node
exists for that pair; and assert none exists for any non-proposition subject. See the plan's Task 6.

## 3. Per-surface plumbing

### 3.1 Frontmatter (surface #1) — no behavior change

Already correct. Refactored to call the chokepoint instead of inlining the triple + node, so all three
surfaces share one implementation. Output byte-for-byte identical. The chokepoint's bundle guard *is* the
frontmatter field's existing non-bundle loud-fail, preserved.

### 3.2 Authored-relations store (surface #2)

- `SourceRelation` (`graph/sources.py:88`) gains an optional `role: MembershipRole | None = None`.
- In `_add_authored_relation`, route to the chokepoint **iff** `predicate == cito:discusses` *and the
  subject is a proposition* *and the object resolves to a **live** bundle entity* (`hypothesis`/`mechanism`,
  `isinstance(object_entity, Entity)`), with `role = relation.role or CORE`. All other predicates, and
  discusses edges with a non-proposition subject or a non-bundle / external / **archived** object, keep the
  existing generic `graph.add` path — so `paper → discusses → question`, `paper → discusses → hypothesis`,
  and discusses to an archived bundle are all unchanged.
- A `role` set on a `cito:discusses` edge whose `(subject, object)` is **not** a proposition→live-bundle
  pair is a loud-fail (§4) — a role is meaningless on a non-membership link.
- Authoring shape:
  ```yaml
  - subject: proposition:0011-…
    predicate: cito:discusses
    object: hypothesis:0001-…
    role: background          # optional; absent = core
  ```

### 3.3 Store CLI bridge (surface #3)

- `science … --bridge-between` (`cli.py:2367`) creates a proposition bridging hypotheses; each ref emits
  `(prop, cito:discusses, hyp)` plus `sci:bridgeBetween` provenance (`mutations.py:225–229`). A bridge
  target is a hypothesis ref, so it is always a bundle membership; the `core` default is correct, and the
  gap is only the inability to express a non-`core` bridge.
- Add **`--bridge-role <core|rival|background>`** (default `core`) — named `--bridge-role`, not `--role`, to
  scope it to the bridge frames and avoid colliding with other `--role`-style options on the command.
  Thread it to `mutations` and call the chokepoint. The `sci:bridgeBetween` provenance triple is unchanged.

### 3.4 The chokepoint's bundle guard (not a corpus-wide restriction)

The chokepoint loud-fails a non-bundle `frame_cid`. This is a **precondition guard on the membership
emitter**, reached only when a caller has already decided the edge is a membership: it is *load-bearing* for
the frontmatter `discusses:` field (where it enforces the field's bundle-only contract, as today) and
*defensive* for surfaces #2/#3 (which pre-gate on proposition→bundle). It is **not** a new restriction on
`cito:discusses` in general — non-bundle discusses never reaches the chokepoint and is never rejected (§0.1).

## 4. Validation (loud-fail at load, per framework discipline)

Beyond the contextual-roles §5 rules already enforced on the frontmatter surface, the new field adds:

1. `SourceRelation.role` set **and** `predicate != cito:discusses` → reject (role only valid on discusses).
2. `SourceRelation.role` set **and** the `(subject, object)` is not a proposition→live-bundle membership
   pair → reject (role only valid on a membership; surfaces the chokepoint guard earlier with a clearer
   message).
3. The same `(subject, frame)` pair labeled with **conflicting roles across surfaces** (e.g. frontmatter
   `background`, relations.yaml `core`) → reject. Generalizes contextual-roles §5 rule 3 across surfaces,
   since two nodes for one pair would otherwise be minted.

(The role *value* enum is enforced by the Pydantic `MembershipRole` type at load — no separate check.)

## 5. Why not the alternatives

- **Two-line patch to `_add_authored_relation` only.** Fixes surface #2, leaves #3 silently `core`, and
  leaves the role node welded to a second site. Rejected: doesn't fix the class of bug.
- **Redefine `cito:discusses` as membership-only (loud-fail every non-bundle target).** This was v1's
  implicit §3.4 stance; it breaks the existing, tested `paper → discusses → question` case
  (`test_graph_materialize.py:896`) and the predicate's registered "hypothesis/topic" range. Rejected — see
  §0.1 and §9.
- **Collapse to one surface (frontmatter-only `discusses`; ban relations.yaml / store-CLI discusses).**
  Conceptually clean but removes a legitimate bulk/structured-authoring path and the bridge workflow, and is
  a larger breaking change. Reasonable as a *future* deprecation, not the right default now. Rejected as the
  default.
- **Make the membership node truth-apt.** Forbidden by contextual-roles §5 / the epistemic-edges boundary.
  Rejected.

## 6. Migration & corpus impact

- **Frontmatter:** zero change (output identical).
- **Relations.yaml & bridge:** *proposition→bundle* discusses edges begin emitting a `role: core`
  `BundleMembership` node where none existed. Additive and benign (`core` = existing default), but it
  changes graph output (more triples) and needs a graph rebuild. The conjunction result is unchanged.
- **All other discusses edges are untouched** — non-proposition subjects (`paper → hypothesis`), non-bundle
  objects (`paper → question`), and archived bundle objects all keep the generic path. No breakage, nothing
  to reconcile (this is why High #2 from review does not bite: the routing gates on proposition→live-bundle).
- **Rebuild (plan task):** for each project that authored a *prop→bundle* discusses edge in `relations.yaml`,
  rebuild `knowledge/graph.trig` + `composite.trig` and confirm belief is unchanged. The roles doc
  (`skills/research/proposition-schema.md`) is updated to drop the "relations.yaml is always core, author in
  frontmatter" caveat.

## 7. Open questions

- **Sequencing.** The chokepoint refactor (§2–§3.1) is worth landing **independently of demand** — a small
  DRY/correctness win that kills the silent fallback. The surface ergonomics (`SourceRelation.role`,
  `--bridge-role`) can follow when a real non-frontmatter non-core membership appears. The plan orders tasks
  so the refactor is shippable on its own (Tasks 1–3) and the surface fields are additive (Tasks 4–5).
- **Resolves a contextual-roles open question.** Contextual-roles §7 asked whether `core` should be implicit
  or always materialized explicitly (lean: explicit after compile). The chokepoint implements **explicit
  after compile for every membership surface** — uniform rather than frontmatter-only.
- **Should `bridge_between` keep `sci:bridgeBetween` provenance** once a `BundleMembership` node also exists?
  Lean: keep both — `bridgeBetween` is consumed by the causal exporters (`export_pgmpy.py`,
  `export_chirho.py`); do not disturb them here.

## 8. (reserved)

## 9. What changed from v1 (and why)

v1 argued, in different sections, **both** that `cito:discusses` is a general structural predicate and that
"discusses targets must be bundles" (v1 §1.1 + §3.4), and proposed a corpus-wide non-bundle loud-fail.
Review found this contradictory and breaking:

- **Policy made explicit (§0.1).** `cito:discusses` stays general; membership is the *object-is-a-bundle*
  subtype. v1's "targets must be bundles" is deleted.
- **High #1 — invariant narrowed (§2.1).** "Exactly one emitter of *all* `cito:discusses`" was false (the
  generic path legitimately emits non-membership discusses). Narrowed to "one emitter of *bundle-membership*
  discusses," verified by a graph-coverage assertion, not a grep.
- **High #2 — no breakage (§6).** v1's non-bundle loud-fail would have failed the tested
  `paper → discusses → question` materialization. v2 gates routing on object-is-bundle, so that case is
  untouched; the change to the plan is in routing logic, not a deferred corpus audit.
- **Medium — CLI naming (§3.3).** Standardized on `--bridge-role` everywhere (v1 mixed `--role` and
  `--bridge-role`).
- **Medium — bridge canonical IDs (plan Task 3).** v1 referenced a non-existent `_canonical_for`; v2
  specifies `prop_cid = f"proposition:{token}"` and `frame_cid = bridge_ref`.

A second review pass tightened membership to **proposition→bundle** (both sides), not any-subject→bundle:
`bundle_members` admits only `sci:Proposition` subjects (`bundle_belief.py:47`), so a paper→hypothesis
membership node would be dead data. Routing now also gates on `subject` being a proposition and the object
being a **live** `Entity` bundle (archived bundles keep the generic path); the coverage invariant and
validation rule 2 were tightened to match.
