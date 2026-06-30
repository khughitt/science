# Inquiry Patch Profile Subsumption — design

**Status:** Design / approved direction — pre-implementation
**Created:** 2026-06-14
**Origin:** Continues Spec 4 (Patch Contract) of the patchwork kernel architecture
(`docs/plans/2026-06-14-patchwork-kernel-architecture-design.md`, lines 151–164:
"Patch subsumes inquiry-like epistemic neighborhoods"). Builds directly on the
shipped Patch Contract keystone
(`docs/audits/plans-cleanup/2026-06-08-epistemic-model-checkpoint.md`, with
operator-facing behavior in `docs/user-guide/graph-and-derived-state.md`).
The keystone deliberately deferred inquiry subsumption and shaped
`PatchDefinition.focal` to later absorb inquiry's focal/target structure; this is
that follow-on.

## 0. Thesis

> **Patch is the neighborhood substrate. Inquiry is an authored investigation
> *profile* on a patch.**

A `PatchDefinition` with `patch_type: inquiry` carries an authored `inquiry:`
block. The build compiler emits patch membership **plus** the existing
inquiry-shaped view triples. `sci:Inquiry` survives only as **compiled
compatibility vocabulary**, never an authored primitive. Direct graph mutation
(`science inquiry add-*`) is retired: authored truth lives in the source
declaration, compiled graph state is disposable — the load-bearing invariant of
the patchwork architecture ("No parallel stores"; "Direct graph mutation
commands → source transactions compiled into graph outputs").

This resolves the architecture overview's open migration choice (lines 160–164)
in favour of the **typed-role** option, sharpened: inquiry is a *profile* over a
patch definition, not a second named-graph primitive and not a flat rename.

### The real problem this solves

Inquiry and patch did not collide on RDF vocabulary; they collided on
**authoring model**. Inquiry was *interactively authored* by mutating
`graph.trig` directly (`science inquiry init/add-node/add-edge/...`). Patch is
*declaratively authored* (`PatchDefinitionEntity` markdown) → membership derived
at build. Subsumption retires the direct-mutation path without flattening
inquiry's genuinely useful semantics (boundaries, flow, assumptions,
transformations, causal estimand, validation, export).

### Narrowing "general" inquiry

The weak part of the old model was `inquiryType: general` — easily degenerating
into "miscellaneous patch with hand-authored edges." It is narrowed to a
disciplined `investigation` profile. The conceptual hierarchy:

- **Question** — the thing asked.
- **Hypothesis / proposition** — a possible truth-apt answer.
- **Patch** — the epistemic neighborhood around intent.
- **Inquiry** — the *investigation design* over a patch: boundaries, flow,
  assumptions, transformations, estimand, validation, export.

If there is no boundary/flow/assumption structure, it is **not** an inquiry — it
is a plain patch. There is no `profile: general`.

## 1. Scope

### In scope (this slice)

- Authored `inquiry:` block on `PatchDefinitionEntity`, covering **both**
  `investigation` and `causal` profiles, through one compile path.
- Compiler emission of patch membership **and** legacy-equivalent inquiry view
  triples (so all existing readers keep working unchanged).
- CLI rework: `inquiry init` (markdown scaffold), `inquiry import` (graph →
  source bridge), retirement of the granular graph mutators, unchanged read-only
  commands.

### Deferred (explicitly out of this slice)

- Markdown-editing mutators (structured-YAML round-trip editing is authoring
  *ergonomics*, not substrate architecture).
- Renaming `sci:Inquiry` / `sci:inquiryType` to first-class patch vocabulary in
  the readers (kept as compiled compatibility tokens here).
- Any new causal-analysis capability. The existing identifiability / adjustment
  set / pgmpy / chirho surface is preserved as-is by emitting the same triples.

### Migration surface

Empty in practice: `sci:Inquiry` currently appears only in pytest temp graphs;
no committed project `graph.trig` contains an authored inquiry. `inquiry import`
is therefore a **forward-safety bridge**, not a bulk migration, and retiring the
mutators breaks no real authored data.

## 2. Authored model (`science_model`)

Extend `PatchDefinitionEntity` (`science/model/src/science_model/patch_definition.py`):

| Field | Required | v1 semantics |
|---|---|---|
| `patch_type` | yes (default) | `Literal["neighborhood", "inquiry"]`, default `"neighborhood"`. Plain patch is the default; `"inquiry"` unlocks the `inquiry:` block. |
| `inquiry` | conditional | `InquiryProfile \| None`. **Required iff** `patch_type == "inquiry"`; **forbidden otherwise** (model validation error). |
| `focal` | yes (existing) | doubles as the inquiry **target** (the hypothesis/question investigated). |

`InquiryProfile` (nested Pydantic model):

```
profile:         Literal["investigation", "causal"]
status:          Literal["sketch", "specified", "planned", "in-progress", "complete"]
boundary_roles:  list[BoundaryRole]      # { ref, role: "BoundaryIn" | "BoundaryOut" }
flow_edges:      list[FlowEdge]          # { subject, predicate, object, claim_refs: list[str] }
assumptions:     list[Assumption]        # { ref, statement, derived_from }
transformations: list[Transformation]    # { ref, tool, params: list[Param], validated_by }
treatment:       str | None              # causal only
outcome:         str | None              # causal only
```

- `FlowEdge.predicate` is one of the materialized flow predicates
  (`sci:feedsInto`, `sci:produces`, `scic:causes`). These feed **boundary
  reachability** and **pgmpy/chirho export** (both read the compiled inquiry
  graph). They do **not** feed the causal acyclicity / identifiability /
  adjustment-set validators, which read `graph/causal` (populated by causal
  *propositions*), unchanged from today — see §5.
- `Param` = `{ value, source, ref, note }` (matches today's `sci:paramValue` /
  `sci:paramSource` / `sci:paramRef` / `sci:paramNote`).

### Model validation (load-time, fail early)

- `patch_type == "inquiry"` ⇒ `inquiry` present; `patch_type == "neighborhood"`
  ⇒ `inquiry` absent.
- `profile == "causal"` ⇒ `treatment` and `outcome` **required**.
- `profile == "investigation"` ⇒ `treatment` and `outcome` **must be absent**
  (an investigation with an estimand is a causal inquiry).
- `BoundaryRole.role` restricted to the two boundary constants.
- Unresolved entity refs (`focal`, boundary/flow/estimand/assumption/
  transformation refs) are **not** caught here; they are caught graph-time by the
  deriver as a hard error, consistent with the existing patch contract
  (fail-early on resolution, but at the layer that owns the graph).

## 3. Membership derivation

Inquiry-referenced entities become **typed authored origins** fed into the
existing `local-closure-v1` deriver — the same mechanism as `seeds` — so
closure and direct-relation expansion run around them unchanged. The inquiry
block contributes the origin set; the standard policy then expands the
neighborhood.

**One new `derivationReason` value: `inquiry`.** Every entity pulled in by the
block (boundary nodes, flow-edge endpoints, treatment/outcome, assumption and
transformation nodes) is recorded with `derivationReason = "inquiry"`,
`memberRole = "member"`, depth 0. `memberKind` continues to come from `rdf:type`
(assumption/transformation nodes carry their own kinds via the emitted
`sci:Assumption` / `sci:Transformation` types).

Rationale for a single reason rather than granular
`inquiry_boundary`/`inquiry_flow`/`inquiry_estimand`/…: the *structural role* of
each member (boundary in/out, estimand, assumption, …) is already fully
recoverable from the emitted compat triples (§4), so a finer reason taxonomy
would duplicate that information. This preserves the keystone's deliberately
orthogonal axes — `memberRole` (role in patch) / `memberKind` (what it is) /
`derivationReason` (why included) — without overloading `derivationReason` with
structural-role detail.

The focal/target is recorded as today (`memberRole = "focal"`,
`derivationReason = "focal"`, depth 0). Excludes apply as in the keystone.

**Ordering requirement (load-bearing).** The keystone deriver skips candidates
whose `memberKind` resolves to `"unknown"` (the provenance-node-leak guard). The
inquiry block mints new typed nodes for assumptions and transformations
(`sci:Assumption` / `sci:Transformation`). Therefore the inquiry view triples
**must be emitted before** `derive_patch_memberships` runs, so those nodes carry
their `rdf:type` when the deriver resolves `memberKind`. The dataflow (§7) is
ordered accordingly: emit inquiry view → derive membership → emit membership.
Inquiry origins themselves come from the authored block (not the graph);
boundary/flow/estimand refs must resolve to existing project entities (hard error
if not), while assumption/transformation nodes are compiler-minted and always
typed.

## 4. Compiler emission (compatibility views) — zero reader changes

The compiler reproduces the **exact legacy inquiry triples** from the authored
block, so `list` / `show` / `validate` / `export-pgmpy` / `export-chirho` work
untouched:

- `<inquiry> rdf:type sci:Inquiry`, `sci:inquiryStatus`, `sci:target <focal>`,
  **and** `sci:focalEntity <focal>` (the patch focal — the keystone vocabulary).
  One tiny reader change is required for the latter: `get_inquiry` builds its edge
  list by excluding a `metadata_predicates` set, so `sci:focalEntity` must be
  added to that set (else it surfaces as a bogus flow edge). This is the single
  exception to "zero reader changes" — a metadata-exclusion addition, not a
  behavior change.
- `sci:inquiryType` mapped from `profile`: `causal → "causal"`,
  `investigation → "general"`. This is a **disposable compiled compat token**
  only — authored truth is `profile`. Promoting readers to a first-class
  `sci:inquiryProfile` predicate is a deferred cleanup, intentionally not done
  here to keep reader changes at zero.
- `sci:boundaryRole` on boundary entities; flow-edge triples
  (`subject predicate object`) with optional `sci:backedByClaim`;
  `sci:treatment` / `sci:outcome` for causal; `sci:Assumption` and
  `sci:Transformation` nodes with their params; unknowns where applicable.

**Emission target (load-bearing — preserves zero reader change).** The view is
emitted into a **dedicated compiled named graph whose identifier equals the
inquiry URI `PROJECT_NS["inquiry/<slug>"]`**, reproducing the legacy
"dedicated per-inquiry named graph" layout — now compiler-generated from source
instead of written by interactive mutators. This is required, not incidental:

- `_discover_inquiries` only accepts subjects under the `PROJECT_NS + "inquiry/"`
  prefix (`graph/store/inquiry.py:48`);
- `get_inquiry` only reads the boundary/edge subgraph when
  `home_graph.identifier == inquiry_uri` (`inquiry.py:119`);
- `export_pgmpy` opens `PROJECT_NS["inquiry/<slug>"]` directly
  (`causal/export_pgmpy.py:104`).

So the inquiry URI is `PROJECT_NS["inquiry/<slug>"]` and the home graph
identifier is the same URI. This compiled inquiry graph is regenerated every
build and is distinct from the patch membership context (which lives on the
patch-definition URI); the two are tied by the shared slug, and `focal` is
emitted on both (`sci:target` + `sci:focalEntity` on the inquiry URI; membership
on the patch URI). Member *content* triples remain in their scope/semantic
graphs, per the keystone's "membership is a relation, not a partition" decision.

## 5. Validation

- **Model-level (load-time, Pydantic):** `patch_type`/`inquiry` block coherence;
  `profile` enum; causal-requires-estimand; investigation-forbids-estimand;
  boundary-role enum. (§2.)
- **Graph-level (existing `validate_inquiry` over the compiled graph,
  unchanged):** these keep working because the compiler emits the same triples
  into the same graphs the validators already read:
  - **From the compiled inquiry graph:** boundary reachability, no cycles over
    flow edges (`sci:feedsInto` / `sci:produces` / `scic:causes`), unknown
    resolution, target exists, orphaned interior, provenance completeness.
  - **From `graph/causal` (populated by causal *propositions*, not inquiry flow
    edges):** causal acyclicity, confounders declared, identifiability,
    adjustment sets (`inquiry.py:659`). This coupling is **unchanged from
    today**: a causal inquiry's identifiability validation has always read
    `graph/causal`, so the causal DAG must be authored as causal propositions.
    This slice does not change that and does not emit inquiry flow edges into
    `graph/causal` (whether causal structure should migrate into the inquiry
    block is a Spec 5 / proposition-as-edge concern — §11).

  The `investigation` profile runs the light subset; `causal` runs the full set
  — gated, as today, by the emitted `inquiryType`.
- **Patch convenience-edge build gate (existing):** the
  `patch_membership_convenience` check (`graph/store/validation.py`, shipped
  `00c89308`) continues to apply to inquiry patches.

## 6. CLI (`science inquiry`)

Source-of-truth migration now; authoring ergonomics later.

- `science inquiry init <slug> --profile {investigation|causal} --focal <ref>
  [--status <s>] [--label <l>]` — creates `entities/patches/<slug>.md` with
  `type: patch-definition`, `patch_type: inquiry`, and a skeleton `inquiry:`
  block. **Does not write `graph.trig`.**
- `science inquiry import <slug> [--force]` — reads an existing compiled/legacy
  `sci:Inquiry` named graph and writes a `patch-definition` markdown source.
  Refuses to overwrite an existing source without `--force`. The migration
  bridge (near-zero real targets today).
- **Retired mutators** — the five graph-writing commands `add-node` (incl. its
  `--role` boundary assignment), `add-edge`, `add-assumption`,
  `add-transformation`, and `set-estimand` fail loudly:
  > `Inquiry graph mutation is retired. Edit entities/patches/<slug>.md and run
  > science graph build.`
  with the resolved source path appended when it can be located. (Option 3 —
  keeping graph-writing mutators "deprecated" — is **rejected**, not deferred:
  it would let one inquiry have two authored realities, contradicting the
  patchwork contract.)
- **Unchanged read-only/derived commands:** `list`, `show`, `validate`,
  `export-pgmpy`, `export-chirho` — all read the compiled graph.

## 7. Dataflow & integration

```
source declarations (entities/patches/<slug>.md, patch_type: inquiry)
  -> load_project_sources()
  -> base graph materialization
  -> close_bears_on()  ->  sci:BearsOnEdge / sci:bearsOnDepth available
  -> emit inquiry view triples (compat)       [new: dedicated inquiry/<slug> graph; mints typed nodes]
  -> derive_patch_memberships(...)            [keystone phase; inquiry origins added, kinds read from view]
  -> emit_patch_memberships(...)              [keystone emitter]
  -> serialize graph.trig
```

The new inquiry-view emission runs inside the existing
`materialize._derive_patch_membership_layer`, **before** membership derivation,
so assumption/transformation nodes carry their `rdf:type` when the deriver
resolves `memberKind` (avoiding the keystone's unknown-kind skip guard — §3).
There is still a single writer and a single build artifact.

## 8. Files touched

- `science/model/src/science_model/patch_definition.py` — `patch_type` field;
  `InquiryProfile` + nested `BoundaryRole` / `FlowEdge` / `Assumption` /
  `Transformation` / `Param` models; cross-field validation (§2).
- `science/src/science_tool/graph/patch_membership.py` — extend the deriver to
  accept inquiry-block entity refs as typed origins
  (`derivationReason = "inquiry"`); minimal change reusing the seed path.
- `science/src/science_tool/graph/inquiry_compile.py` *(new)* — pure emitter
  that renders an `InquiryProfile` into the legacy-equivalent inquiry view
  triples (§4), emitted into a dedicated named graph whose identifier equals the
  inquiry URI `PROJECT_NS["inquiry/<slug>"]`. Keeps inquiry-view emission
  isolated from the membership emitter.
- `science/src/science_tool/graph/materialize.py` — call the inquiry-view
  emitter for inquiry-typed patch definitions **before** membership derivation
  (so minted assumption/transformation nodes are typed — §3/§7).
- `science/src/science_tool/cli.py` — rework the `inquiry` group: `init`
  scaffold, `import` bridge, retire granular mutators, keep read-only.
- `science/src/science_tool/graph/store/constants.py` — no new authored
  predicates expected (reuses existing `sci:*` inquiry vocabulary as compat);
  add a `sci:inquiryProfile` constant only if §4's deferred-cleanup decision is
  pulled forward (not in this slice).

## 9. Testing (TDD)

- **Model:** `patch_type`/`inquiry` coherence (block required iff inquiry;
  forbidden otherwise); `profile` enum; causal requires treatment+outcome;
  investigation forbids them; boundary-role enum.
- **Deriver:** inquiry-block refs become members with
  `derivationReason = "inquiry"`, depth 0; closure/direct-relation expand around
  them; focal recorded as `focal`; excludes still suppress; minted
  assumption/transformation nodes resolve `memberKind` from `rdf:type` because
  the view is emitted first (ordering regression guard — §3/§7).
- **Compiler (golden):** an authored `inquiry:` block compiles into a dedicated
  `inquiry/<slug>` named graph (identifier == inquiry URI) carrying the
  legacy-equivalent triple set — `sci:Inquiry`, `sci:inquiryStatus`,
  `sci:target` + `sci:focalEntity`, `sci:inquiryType` mapped from profile,
  `sci:boundaryRole`, flow edges + `sci:backedByClaim`, `sci:treatment` /
  `sci:outcome`, `sci:Assumption` / `sci:Transformation` + params.
- **Readers unchanged:** existing `validate` / `render` / `export-pgmpy` /
  `export-chirho` assertions pass against compiler-produced graphs (re-pointed
  from the old mutator-built fixtures to markdown→build fixtures).
- **CLI:** `init` writes a valid scaffold and no graph; `import` writes source
  from a graph inquiry and refuses overwrite without `--force`; each retired
  mutator exits non-zero with the retirement message (and source path when
  resolvable).
- **Integration:** `science graph build` over an inquiry patch definition
  produces both the membership context and the inquiry view triples;
  re-running is idempotent; the convenience-edge gate passes.

## 10. Migration

- Real surface is empty (test fixtures only). No bulk migration required.
- Existing `test_inquiry*.py`: **mutation** tests are rewritten to author
  markdown → build; **validation / render / export** tests are re-pointed at
  compiler-produced graphs (they assert on graph shape, which is preserved).
- `inquiry import` covers any future/straggler graph inquiry.

## 11. Open questions (non-blocking)

- Whether to pull the `sci:inquiryProfile` predicate forward and update readers
  now versus keeping the `investigation → "general"` compat token (§4). Deferred:
  kept as a token to hold reader changes at zero this slice.
- Whether `derivationReason = "inquiry"` should later split into granular
  reasons for richer `patch explain` output (§3). Deferred: structural role is
  already recoverable from compat triples.
- Whether causal DAG structure should migrate out of `graph/causal`
  (causal-proposition-authored) and into the inquiry block, unifying the two
  causal-edge homes (§5). Deferred: that is a Spec 5 proposition-as-edge concern;
  this slice preserves today's coupling rather than redesigning causal authoring.

## Next step

On approval: produce a phased implementation plan (writing-plans), executed
subagent-driven. Natural phasing: (1) authored model + validation; (2) deriver
inquiry-origins; (3) inquiry-view compiler + materialization wiring; (4) CLI
rework (`init`, `import`, mutator retirement); (5) reader test re-pointing. Each
phase leaves the tree green.
