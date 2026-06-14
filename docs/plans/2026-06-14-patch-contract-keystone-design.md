# Patch Contract keystone (v1) — design

**Status:** SHIPPED 2026-06-14 — merged to local `main` (`0b15c7ec`, `--no-ff`),
not pushed. Convenience-edge invariant promoted to a build gate in `science
validate` / `graph validate` (`00c89308`). Implementation plan:
`docs/plans/2026-06-14-patch-contract-keystone-plan.md`. Deferred follow-ons
remain: `PatchSnapshot`, remote/commons scopes, inquiry↔patch subsumption.
**Created:** 2026-06-14
**Origin:** First implementation-facing slice of Spec 4 (Patch Contract) from
`docs/plans/2026-06-14-patchwork-kernel-architecture-design.md` (lines 215, 224,
252–260). The overview frames Patch as an existing concept carrying a
durable-membership gap, and sequences a *minimal* patch slice first: durable
compiled membership + named-graph emission on top of today's `PropositionEntity`
and the orphaned `science_tool.model.patch` prototype, without waiting for the
broader belief/registry cleanup.

## 0. Purpose & scope

Make `Patch` real under one contract:

> The authored source-of-truth is a **`PatchDefinition`** (focal intent + scope
> set + neighborhood policy + seeds + excludes). Patch **membership is compiled,
> derived state** emitted into the project graph. Manual member lists are never
> the primary membership model; manual curation enters only as seeds or excludes
> (with reasons), which are derivation *constraints*, not authored membership.

This preserves the long-term derived-neighborhood contract (remote scopes,
ontology/latent glue, leads, snapshots, maturity) while keeping the first
implementation narrow enough to land.

### In scope (v1)

- A new authored entity kind `patch-definition` (`PatchDefinitionEntity`).
- A **pure local-scope deriver** over the materialized knowledge graph.
- Membership emission as a patch **named-graph context inside the project
  `Dataset`**, serialized as part of the single `graph.trig` build artifact.
- A **diagnostic-only** CLI facade (`patch explain`, `patch check`) over the same
  deriver — never a second writer.

### Deferred (schema reserves room; v1 code does not implement)

Remote/commons scopes; ontology glue; latent similarity; leads/candidate
workflow; scoring/rank; `PatchSnapshot` publication artifact; L0–L4 maturity
computation; inquiry subsumption. In v1, `PatchDefinition` patches and the live
`sci:Inquiry` system **coexist**; inquiry subsumption is the designated next
plan, so `PatchDefinition.focal` is shaped to later absorb inquiry's
focal/treatment/outcome structure.

## 1. Substrate (what exists today)

- `science_model.propositions.PropositionEntity` — the typed relational
  proposition (subject/object/predicate/polarity), the epistemic edge
  source-of-truth (`dag/proposition_edges.py`).
- Materialized RDF predicates already in the knowledge graph: `sci:bearsOn`
  (freshness/attention dependency), `cito:discusses` (proposition→hypothesis),
  `cito:supports` / `cito:disputes` (evidence-line→target).
- `science_tool.model.patch` — an **orphaned** TriG emitter (exported from
  `model/__init__.py`, **zero production callers**): provides patch vocabulary
  (`sci:EpistemicPatch`, `sci:focalEntity`), the edge-as-node pattern, and
  `signature_fusion`. v1 **reuses/refactors its vocabulary and triple-emission
  logic** into the Dataset emitter (§5). Its standalone file-writer
  `emit_patch_trig` is **not** wired into the build or the CLI — that would be a
  second writer. CLI diagnostics render to stdout (or a temp file in tests only),
  never the build artifact.
- `science_tool.graph.store.inquiry` — the live, fully wired named-graph
  neighborhood system (`sci:Inquiry`: discovery, CRUD, validate, render). Left
  untouched in v1; the subsumption target for the follow-on plan.

## 2. Authored model — `PatchDefinition`

A new entity kind. Path `entities/patches/<slug>.md`; model class
`PatchDefinitionEntity` in `science_model`. Naming is deliberate: the authored
*definition* is distinct from the derived patch graph/context.

Fields:

| Field | Required | v1 semantics |
|---|---|---|
| `id` / slug | yes | patch identity |
| `focal` | yes | entity ref the neighborhood is built around (unresolved → hard error) |
| `scope_set` | yes | v1: local project only; uses the future shape; any non-local scope → hard error ("remote deferred") |
| `neighborhood_policy` | yes | named, versioned policy; v1 ships `local-closure-v1` |
| `seeds` | no | list of entity refs forced in as derivation starting points (unresolved → hard error) |
| `excludes` | no | list of `{ref, reason}`; `reason` is **required** (missing → model validation error) |

`seeds` and `excludes` are **not** member-list authoring. A seed says "start
neighborhood discovery here"; an exclude says "even if the policy would include
this, suppress it, for this reason." The emitted membership set remains compiled
output.

### `local-closure-v1` policy

A declared, versioned policy object:

```
local-closure-v1:
  dependency:                    # sci:bearsOn neighborhood
    via: sci:BearsOnEdge         # the reified, depth-stamped closure edges
    max_depth: 2                 # matched against the precomputed
                                 # sci:bearsOnDepth, NOT a re-walk of edges
  direct_relations:              # one-hop, un-closed epistemic edges
    predicates: [cito:discusses, cito:supports, cito:disputes]
  scope: local
```

`max_depth` is **explicit** in the policy, not a hidden constant.

> **Why depth is matched, not walked.** Materialization (`graph/freshness.py`
> `close_bears_on`, called from `materialize.py`) already **transitively closes**
> `sci:bearsOn` and emits reified `sci:BearsOnEdge` nodes carrying
> `sci:bearsOnSource`, `sci:bearsOnTarget`, and `sci:bearsOnDepth` (the shortest
> path across all routes). A naive BFS over `sci:bearsOn` *after* closure would
> treat already-closed edges as single hops, so `max_depth: 2` would silently
> mean a far broader neighborhood than intended. The deriver therefore selects
> dependency members by querying `sci:BearsOnEdge` where `sci:bearsOnDepth <=
> max_depth` — reusing the precomputed depth instead of re-deriving it. (Patch
> derivation runs *after* `close_bears_on`; see §5.)

## 3. Derived model — `PatchMembershipSet`

Compiled output, never authored. Per (patch, member) pair, a reified
`sci:PatchMembership` node (edge-as-node, consistent with `model/patch.py`)
**strongly tied to both endpoints** and carrying:

| Property | Vocab | Values / notes |
|---|---|---|
| patch | `sci:patch` | the owning patch IRI (ties the node to the pair) |
| member | `sci:member` | the member entity IRI |
| member role | `sci:memberRole` | `focal \| member` — the node's role *in the patch* |
| member kind | `sci:memberKind` | `proposition \| evidence \| ...` — what the entity *is* (from `rdf:type`) |
| reason | `sci:derivationReason` | `focal \| seed \| closure \| direct_relation` — *why* it is a member |
| predicate | `sci:derivationPredicate` | the actual path-step RDF term (`sci:bearsOn`, `cito:discusses`, `cito:supports`, `cito:disputes`); absent for `focal`/`seed` |
| depth | `sci:derivationDepth` | shortest hop count from any focal/seed origin (focal/seed = 0) |
| policy_version | `sci:policyVersion` | **never omitted** — the reproducibility anchor until `SourceSnapshot` exists |
| build_id | `sci:buildId` | best-effort; recorded when the materializer exposes one, omitted otherwise |

Three orthogonal axes, deliberately separated (per review): **`memberRole`** is
the membership role (focal vs ordinary member); **`memberKind`** is what the
entity is (a seed may be a proposition, an evidence-line, or another kind — so
"seed" is not a kind); **`derivationReason`** is why it was included (`seed` is a
reason, not a role or a kind). Keeping `reason` separate from `predicate` (the
RDF path step) likewise stops `reason` from becoming half policy-concept,
half-predicate once ontology/latent glue arrive with their own predicates.

## 4. Derivation algorithm (pure)

```
derive_patch_memberships(dataset, patch_definitions, policy_version)
    -> list[MembershipRecord]
```

Pure, no I/O. Runs after `close_bears_on` (§5), so `sci:BearsOnEdge` depth is
available. For each definition:

1. **Origins.** Resolve `focal` and `seeds` in the materialized `Dataset`.
   Unresolved → hard error (fail early). Emit `focal` (memberRole=focal,
   reason=focal, depth 0) and each seed (memberRole=member, reason=seed, depth 0).
2. **Dependency members (closure).** For each origin, select members `t` where a
   `sci:BearsOnEdge` connects the origin to `t` with `sci:bearsOnDepth d <=
   max_depth`. Record reason=`closure`, predicate=`sci:bearsOn`, depth=`d` (the
   precomputed shortest path — not a re-walk).
3. **Direct-relation members.** For each origin and each dependency member,
   attach nodes one hop away over `cito:discusses` / `cito:supports` /
   `cito:disputes`. Record reason=`direct_relation`, predicate=the cito term,
   depth=origin/anchor depth + 1.
4. **memberKind** for every non-focal member comes from its `rdf:type`
   (`proposition`, `evidence`, …). memberRole is `member` for all non-focal.
5. **De-dup & rank.** A member reachable several ways keeps the record with the
   smallest depth (ties broken deterministically: `closure` before
   `direct_relation`, then by predicate IRI).
6. **Excludes.** Suppress matching members (record nothing). An exclude matching
   no derived member → **warn**, not error (harmless constraint), naming the
   unused exclusion.
7. Sort records by member IRI for stable, reproducible output.

> Edge directionality (which subject/object end to follow per predicate) is
> pinned in the plan against the materialized directions (`cito:discusses` is
> proposition→hypothesis, `cito:supports` is evidence→target, `sci:BearsOnEdge`
> carries explicit `sci:bearsOnSource`/`sci:bearsOnTarget`). The contract here is
> a depth-bounded dependency neighborhood plus one-hop direct relations.

## 5. Dataflow & integration (one build artifact)

Derivation is a **materialization phase**, not a separate build path — so there
is never a stale-`graph.trig` second writer:

```
source declarations
  -> load_project_sources()
  -> base graph materialization
  -> close_bears_on()  ->  sci:BearsOnEdge + sci:bearsOnDepth available
  -> cito:discusses / cito:supports / cito:disputes available
  -> derive_patch_memberships(dataset, defs, policy_version)   [new phase]
  -> emit patch named-graph context: patch metadata
                                     + sci:PatchMembership nodes (authoritative)
                                     + sci:hasMember / sci:inPatch (convenience)
  -> serialize graph.trig
```

Each patch is a **named-graph context inside the project `Dataset`** (the same
mechanism inquiries already use), holding only patch metadata + membership.
Member *content* triples stay in their scope/semantic graphs — the overview's
decided home-graph shape (membership is a relation, not a partition). v1 omits
`sci:ladderLevel` (maturity deferred).

Emitted patch metadata (about the patch IRI, derived from the authored
`PatchDefinition`): `rdf:type sci:EpistemicPatch`, `sci:focalEntity`,
`sci:neighborhoodPolicy`, `sci:patchScope "local"`, seeds, and reified
exclusions (`sci:PatchExclusion` with `sci:excludedEntity` + `sci:excludeReason`).

## 6. Membership predicates & canonical record

The reified **`sci:PatchMembership` node is the authoritative record** (per
review): it is strongly tied to its pair via `sci:patch` + `sci:member` and
carries memberRole / memberKind / reason / predicate / depth / policy_version /
build_id. The two direct edges are **generated convenience**, both derived from
the membership nodes and not treated as independent sources by validation:

- `sci:hasMember` — patch → member (the simple, queryable edge).
- `sci:inPatch` — member → patch (its inverse).

Validation authoritativeness flows one way: a `sci:hasMember` / `sci:inPatch`
edge with no backing `sci:PatchMembership` node is an error (orphan convenience
edge), and every `sci:PatchMembership` node must have both edges generated.

## 7. CLI (diagnostic only — no second writer)

Neither command writes the build artifact; both call the same deriver:

- `science patch explain <id>` — report the derived membership set with
  memberRole / memberKind / reason / predicate / depth; surfaces seeds
  prominently.
- `science patch check` — re-derive over the current `Dataset`, diff against the
  patch context in `graph.trig`, and exit non-zero on drift. Explicitly a
  no-write dry-run/diff command. (Named `check`, not `build --check`, because it
  does not build.)

## 8. Error handling (fail-early; no silent fallback)

| Condition | Behavior |
|---|---|
| `focal` or a `seed` does not resolve in the graph | hard error |
| `exclude` entry missing `reason` | model validation error |
| `scope_set` contains a non-local scope | hard error ("remote scopes deferred to a later spec") |
| policy names an unknown predicate | hard error |
| `exclude` matches no derived member | warn (named), continue |
| focal resolves but neighborhood is empty | valid (a small patch) |

## 9. Files touched

- `science/model/src/science_model/` — new `patch_definition.py`
  (`PatchDefinitionEntity` + validation: required `focal`/`scope_set`/
  `neighborhood_policy`, exclude-reason required, non-local scope rejected);
  register in the entity registry.
- `science/src/science_tool/entities.py` — path policy + status vocabulary for
  the `patch-definition` kind (`entities/patches/<slug>.md`).
- `science/src/science_tool/graph/patch_membership.py` — new: the pure deriver
  (`derive_patch_memberships`) + the Dataset emitter (lays the authoritative
  `sci:PatchMembership` nodes + generated `sci:hasMember` / `sci:inPatch` +
  patch metadata into the patch context). Reuses the `model/patch.py`
  vocabulary/emission logic (refactored to emit into a provided `Dataset`).
- `science/src/science_tool/graph/materialize.py` — wire the derivation phase
  **after `close_bears_on`** (so `sci:BearsOnEdge`/`sci:bearsOnDepth` exist),
  before serialization.
- `science/src/science_tool/graph/store/constants.py` (`SCI_NS`) — new
  predicates: `PatchMembership`, `patch`, `member`, `hasMember`, `inPatch`,
  `memberRole`, `memberKind`, `derivationReason`, `derivationPredicate`,
  `derivationDepth`, `policyVersion`, `buildId`, `neighborhoodPolicy`,
  `patchScope`, `patchSeed`, `PatchExclusion`, `excludedEntity`, `excludeReason`.
  (`EpistemicPatch`, `focalEntity`, and `BearsOnEdge`/`bearsOnSource`/
  `bearsOnTarget`/`bearsOnDepth` already exist.)
- CLI command module — `patch explain`, `patch check`.

## 10. Testing (TDD)

- **Deriver (pure):** dependency inclusion via `sci:BearsOnEdge` respects
  `bearsOnDepth <= max_depth` (and a depth-3 edge is excluded at max_depth 2 —
  the §"Why depth is matched" guard); direct-relation one-hop attach; seeds
  forced in (reason=seed, depth 0); excludes suppress + warn on unused; reason
  classification (`closure` vs `direct_relation`); predicate recorded; memberKind
  from `rdf:type`; de-dup keeps smallest depth; sorted determinism;
  empty-neighborhood valid; unresolved focal/seed → hard error.
- **Model:** `PatchDefinitionEntity` validation (required fields; exclude reason
  required; non-local scope rejected).
- **Emission:** authoritative `sci:PatchMembership` node carries
  `sci:patch`+`sci:member`+memberRole/memberKind/reason/predicate/depth/
  policy_version; generated `sci:hasMember`/`sci:inPatch` both present; an orphan
  convenience edge with no backing node fails validation; `policy_version` always
  present; `build_id` present only when supplied.
- **Integration:** `science graph build` (and the `/science:update-graph`
  harness alias) produces the patch named-graph context inside `graph.trig`;
  re-running is idempotent.
- **CLI:** `patch explain` output (seeds surfaced); `patch check` exits non-zero
  on injected drift, zero when consistent.

## 11. Open questions (non-blocking)

- `build_id` provenance is best-effort until Spec 3's `SourceSnapshot` lands;
  `policy_version` carries reproducibility in the interim.
- Exact subject/object edge directions per predicate (`cito:*` and the
  `sci:BearsOnEdge` source/target ends) are pinned in the plan (§4 note).
- Whether `patch explain` should also show *excluded* candidates (suppressed by
  excludes) for transparency — minor, defer to the plan.

## Next step

On approval of this spec: produce a phased implementation plan (writing-plans),
executed subagent-driven. Natural phasing: (1) `PatchDefinitionEntity` + kind
registration + validation; (2) pure deriver + `SCI_NS` predicates; (3) emitter +
materialization-phase wiring; (4) diagnostic CLI (`explain`, `check`). Each phase
leaves the tree green.
