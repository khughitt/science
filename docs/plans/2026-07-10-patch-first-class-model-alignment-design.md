# Patch as a First-Class Object — Model Alignment Design

Date: 2026-07-10
Status: proposed
Umbrella: [Toolkit Convergence](2026-07-10-toolkit-convergence-umbrella.md)

Decision-ready. Low line-count, high conceptual weight.

## The problem

The working model (`meta` `hypothesis:0007-working-model`, RFC §2) makes **patch**
its central noun: "a federated patchwork of small epistemic neighborhoods … each a
local cluster around one research concern." `docs/user-guide/big-picture.md` repeats
it as the substrate's shape. D-006 rules that *a patch **is** a named graph*.

In code, "patch" is not an object. It is an emergent property of two modules in
two packages that never meet:

| | `graph/patch_membership.py` (382 lines) | `model/patch.py` (166 lines) |
|---|---|---|
| Answers | *Which entities belong to a patch?* | *What does a patch believe?* |
| Input | `PatchDefinitionEntity` (authored intent) | caller-minted `patch_iri` + `PatchEdge` specs |
| Output | `MembershipRecord`s emitted into an in-memory `Dataset` | a standalone TriG file |
| Writes files | never (`:1-6`) | yes (`:165`) |
| Knows about | closure policy, derivation reasons, member roles | belief fusion, provenance routes, opinion, PMI |
| Shared type | — none beyond `science_model.patch_definition` — | |

Both center on "patch = named graph." Both emit patch triples. Neither can see the
other. A reader must hold both files to understand one concept, and neither file
mentions the other exists.

This is not a bug — they answer genuinely different questions and should stay
separate. It is a *naming* failure: the model's central noun has no single
definition site.

## Three supporting faults

The audit found three structural problems that all obstruct the fix, and are worth
repairing regardless.

**1. Domain vocabulary lives in emission code.** The constants that *define* what a
patch member is sit inside the compiler and the emitters:

- `PATCH_MEMBERSHIP_POLICY_VERSION = "local-closure-v1"` is defined in
  `graph/materialize.py:2041` — a domain policy version living in the compiler,
  re-exported to `patch/cli.py:9`.
- `DIRECT_RELATION_PREDICATES`, `MemberRole`, `DerivationReason`
  (`graph/patch_membership.py:20-30`) define membership semantics.
- `DEPENDENCE_ROLES`, `VALIDATION_ROLE`, `OVERLAP_RANK`, `ROLE_RANK`
  (`graph/dataset_independence.py:19-24`) define independence semantics.
- `ladder_level` is passed as a bare `str` (`model/patch.py:101`, serialized at
  `:129`) even though the RFC defines a closed L0–L4 vocabulary.

`science_model` is otherwise a clean pure-schema layer with no `science_tool`
dependency. This vocabulary belongs there. It is schema, not emission mechanics.

**2. A real import cycle, papered over.** `materialize.py:56` imports `freshness`;
`freshness.py:420` imports back `materialize._build_dataset_from_sources` (plus
`migrate`, `source_snapshots`, `store`) from inside a function body. A
function-local import is a cycle, deferred.

**3. `store/validation.py` reaches into the orchestration layer.** It imports
`patch_membership` (`:18`), whose own imports reach `inquiry_compile` (`:19`) —
i.e. `store`, the persistence substrate, transitively depends on a derivation
module that sits well above it. No hard cycle results (`patch_membership` does not
import `store` back), but the substrate calling up into a derivation module is a
genuine layering inversion.

**A correction to an earlier draft of this doc.** That draft claimed `store/`'s
other imports — `belief` and `belief_weights` — were leaves importing "nothing
from `graph/`," and proposed a guard allowlisting them as such. Both claims are
false, and the guard would have landed red:

- `belief_weights` is a true leaf. `belief` is **not**: it imports
  `belief_policy`, `belief_weights`, and `dataset_independence` (`belief.py:11-14`,
  relative imports the earlier grep missed).
- Therefore `store/summary.py → belief → dataset_independence` is a real
  dependency, and `store/` cannot be a "clean bottom layer": `summary` legitimately
  needs `aggregate_belief` to compute belief summaries, `belief` legitimately needs
  independence primitives. That chain is correct, not a fault.

The honest layering is not "leaf vs. non-leaf" but **computational core vs.
orchestration**. A closed core — `{io, errors, export_types, belief_weights,
belief_policy, belief, dataset_independence, run_resolution}` — imports only itself
and the three base leaves; every member's transitive imports stay inside the set
(verified: `belief→{belief_policy, belief_weights, dataset_independence, io}`,
`dataset_independence→{io}`, `run_resolution→{io}`). `store/` may depend on that
core freely. The single fault is the one edge that escapes it: `store →
patch_membership`, because `patch_membership → inquiry_compile` is orchestration.

## A fourth fault, found while writing this doc

The kernel-closure guard `tests/graph/test_durable_write_boundary.py` matches call
sites **by function name** (`save_graph_dataset` / `_save_dataset`), and its own
docstring is candid that an aliased or indirect call evades it.

`model/patch.py:165` and `model/federation.py:114` both call
`ds.serialize(destination=out_path, format="trig")`. Those are durable TriG writes
the guard cannot see.

It is arguably legitimate — it writes a standalone patch file, not `graph.trig`, so
it does not violate the source-of-truth boundary the kernel protects. But nothing
in the code *says* that, and nothing stops the next `ds.serialize` from targeting
`knowledge/graph.trig`. The distinction the kernel actually cares about is *which
file*, and the guard checks *which function*. See Phase 4.

## Approaches considered

**Merge `model/patch.py` into `graph/`.** Rejected. `science_tool/model/` is a
public surface: `meta` D-007 and three interpretations (`0002-l1-patch-prototype`,
`0003-t066-latent-correction`, `0004-t067-patch-federation`) cite it as shipped
machinery, and pan-disease's `code/scripts/h00_patch_demo.py` imports it. It has no
in-repo caller *by design* — its docstring states the framework owns semantics and
serialization while data processing belongs to the consuming project. Merging it
into `graph/` would break external consumers to satisfy an internal tidiness urge.

**Document the split, change nothing.** Cheapest, and defensible: neither module is
broken. Rejected because it leaves the model's central noun undefined in the layer
that already owns "what an entity is," and leaves the faults above in place.

**Name the concept once in `science_model`.** *(chosen)* Both modules keep their
distinct jobs; both consume one shared definition. The patch becomes a first-class
addressable object in the schema layer, which is exactly what the RFC's "promoted
to a first-class, addressable modeling unit" asks for, and what `model/patch.py`'s
own docstring claims it already is.

---

## Phase 1 — Cut `store/` off from the orchestration layer

**Not a prerequisite for anything else.** An earlier draft called this "make
`store/` a clean bottom layer" and "prerequisite for everything." Both are wrong.
`store/` cannot be a bottom layer — it computes belief summaries and legitimately
depends on the belief/independence core (above). And it is a prerequisite for
nothing: Phase 3 puts `Patch` in `science_model`, which imports **no**
`science_tool` code at all (verified: zero `from science_tool` / `import
science_tool` statements in `model/src/science_model/`). Phase 1 is a standalone
coherence fix worth doing on its own merits, and can land in any order relative to
the rest.

**Change.** Cut the single orchestration edge: `store/validation.py:18`'s import
of `patch_membership.validate_patch_membership_convenience`. The convenience
validator becomes injected — `validation.py` receives the membership facts it needs
as an argument, and its one caller (in `materialize`, which sits above both)
supplies them.

Leave the rest alone, because they are the computational core, not faults:
`store/summary.py:12`'s `belief`, `store/validation.py:11`'s `belief_weights`,
`:19`'s `run_resolution`, and `:250`'s lazy `dataset_independence`. All four are
inside the closed core defined above; `run_resolution` and `dataset_independence`
import only `io`. Injecting them would be churn in service of a "bottom layer" goal
that does not exist.

**Guard.** Extend `tests/test_store_package_structure.py` with a
*core-containment* assertion, in two coupled parts:

1. Every `graph/` module that a `store/` module imports must be a member of the
   core set `C = {io, errors, export_types, belief_weights, belief_policy, belief,
   dataset_independence, run_resolution}`.
2. `C` is closed: every member's own `graph/` imports land inside `C`. (This holds
   today — see the core derivation above — and check 2 is what keeps it holding.)

Part 2 is the substitute for "belief is a leaf." It does not assert `belief`
imports nothing; it asserts the whole permitted set reaches nothing *outside
itself*, so `store/` can never touch orchestration through a permitted door. Run
part 2 first so a violation names the core member that broke closure rather than
the innocent `store/` module that imported it. `patch_membership ∉ C`, so the guard
turns green exactly when the one change above lands, and red the moment `store/`
reacquires an orchestration import.

---

## Phase 2 — Break *both* cycles through `freshness`

`freshness.py` defers four `graph/` imports into function bodies (`:420-421`,
`:434-435`). They are not one problem but three, and only one is a cycle at all.
An earlier draft of this doc proposed extracting `_build_dataset_from_sources` and
declared the phase done; that would have left the guard red. All four must be
resolved:

| Deferred import | Why deferred | Fix |
|---|---|---|
| `materialize._build_dataset_from_sources` (`:420`) | real cycle — `materialize.py:56` imports `freshness` | extract to `graph/dataset_build.py` |
| `source_snapshots.compute_source_snapshots` (`:434`) | real cycle — `source_snapshots.py:21` imports `_emit_bears_on_edge` **from `freshness`** | extract `_emit_bears_on_edge` to `graph/bears_on.py` |
| `migrate.audit_project_sources` (`:421`) | **not a cycle** — `migrate` imports no `freshness`, no `materialize` | promote to a module-level import |
| `store.DEFAULT_GRAPH_PATH` (`:435`) | **not a cycle** — `store` does not import `freshness` | promote to a module-level import |

**Change 1 — `graph/dataset_build.py`.** `_build_dataset_from_sources` is not
materialization; it is dataset construction, and `materialize` is merely where it
grew. Both `materialize` and `freshness` then import downward from it.
`build_dataset_from_sources` (`materialize.py:291`, the public name) stays
re-exported from `materialize` for `patch/cli.py:9` and
`validate/checks/graph.py:154`.

**Change 2 — `graph/bears_on.py`.** This is the cycle the earlier draft missed.
`_emit_bears_on_edge` (`freshness.py:48`) is a pure triple emitter with eleven
call sites, ten of them inside `freshness` and one in `source_snapshots.py:134`.
Because `source_snapshots` imports it at *module* level, `freshness` cannot import
`source_snapshots` at module level — hence the deferral at `:434`, which the
existing comment at `freshness.py:432-433` documents precisely. Moving
`_emit_bears_on_edge` down to its own leaf module breaks the cycle at its actual
edge. It loses its underscore on the way (`emit_bears_on_edge`) since it acquires
a cross-module caller.

**Changes 3 and 4.** Promote the `migrate` and `store` imports to module level.
Verified cycle-free: `migrate.py` imports only `identity_table`,
`reference_resolution`, `sources`, `store` — none of which reach `freshness`.

**Guard.** `tests/test_graph_import_layering.py`: an AST check that no module
under `graph/` contains a function-local `import` of another `graph/` module.
Function-local imports of third-party modules stay allowed. The guard must be
written *after* all four changes land, or it fails on the three it does not cover
— which is exactly the trap the earlier draft set. A phase whose guard is broader
than its migration lands red.

---

## Phase 3 — Hoist the patch vocabulary into `science_model`

**New module: `model/src/science_model/patch.py`**, sibling to the existing
`patch_definition.py` (which keeps authored-intent schema: `PatchScope`,
`LocalClosurePolicy`, `FlowEdge`, `InquiryProfile`).

It owns the vocabulary and the identity, and nothing else:

```python
LadderLevel = Literal["L0", "L1", "L2", "L3", "L4"]   # RFC ladder, was a bare str
MemberRole = Literal["focal", "member"]
DerivationReason = Literal["focal", "seed", "closure", "direct_relation", "inquiry"]
ProvenanceRoute = Literal["discovered", "elicited"]

PATCH_MEMBERSHIP_POLICY_VERSION = "local-closure-v1"   # moved from materialize.py:2041

class Patch(BaseModel):
    """A patch: one epistemic neighborhood, addressable as a named graph (D-006)."""
    patch_id: str
    focal_ref: str                    # the entity the neighborhood surrounds
    ladder_level: LadderLevel
    policy_version: str

    def graph_iri(self, project_ns: str) -> str: ...   # the single IRI-minting rule
```

`Patch` is the definition site. It deliberately carries **neither** membership
records **nor** belief — those are the two different questions, computed by the two
different modules, both of which now take a `Patch` and return their own result
type. The type says "a patch is identified by these four facts and addressed at
this IRI," which is precisely what was previously implicit in two places.

Also moved: the **entire** role/rank block from `graph/dataset_independence.py:19-27`
→ `science_model/independence.py` — `DEPENDENCE_ROLES`, `VALIDATION_ROLE`,
`CITED_ROLE`, `OVERLAP_RANK`, `ROLE_RANK`. Same argument, different vocabulary.
Move the block wholesale rather than enumerating members: `CITED_ROLE` was omitted
from an earlier draft of this list purely by oversight, and it is the same kind of
constant (a semantic role name, also a key in `ROLE_RANK`). Leaving one role
behind would recreate the exact two-definition-sites problem this phase exists to
fix. `DIRECT_RELATION_PREDICATES`
(`patch_membership.py:24`) stays in `graph/` — it is a tuple of `rdflib.URIRef`,
i.e. emission mechanics, and `science_model` must not depend on rdflib.

**Consumers.**

- `graph/patch_membership.py` takes `Patch`, returns `tuple[MembershipRecord, ...]`
  as today. Its `MemberRole`/`DerivationReason` literals are re-imported, not
  redefined.
- `model/patch.py` takes `Patch` in place of the loose `patch_iri: URIRef` +
  `ladder_level: str` pair (`:98-103`). `ladder_level` becomes type-checked. IRI
  minting moves from the caller to `Patch.graph_iri`, which is the actual bug this
  phase fixes: today `model/patch.py` requires callers to mint their own patch IRI,
  so two consumers can address the same patch differently.
- `patch/cli.py:9` imports `PATCH_MEMBERSHIP_POLICY_VERSION` from `science_model`
  instead of from the compiler.

**Compatibility.** `model/patch.py`'s signature change is a breaking change to a
public API with known external consumers (pan-disease `h00_patch_demo.py`). Per
the repo's no-compatibility-layers rule, do not add a shim. Instead: land the
change, then update the consumer in the same session, and record the break in
`meta/core/decisions.md` as an amendment to D-007. Verify first:

```bash
rg -n 'emit_patch_trig|PatchNode|PatchEdge' ~/d/pan-disease ~/d/science-commons
```

**Guard.** `tests/test_patch_vocabulary_single_source.py`. The guard must cover
**every** name this phase relocates, not just the patch names — an earlier draft's
guard protected `LadderLevel` / `MemberRole` / `DerivationReason` /
`PATCH_MEMBERSHIP_POLICY_VERSION` but left the five independence constants
unguarded, so `ROLE_RANK` and friends could be redefined in a second place with the
test still green, recreating the exact duplication this phase removes.

Fail if any of these is bound (assigned or annotated) outside its single sanctioned
module:

- in `science_model/patch.py`: `LadderLevel`, `MemberRole`, `DerivationReason`,
  `ProvenanceRoute`, `PATCH_MEMBERSHIP_POLICY_VERSION`;
- in `science_model/independence.py`: `DEPENDENCE_ROLES`, `VALIDATION_ROLE`,
  `CITED_ROLE`, `OVERLAP_RANK`, `ROLE_RANK`.

Drive it from a `{name: owning_module}` table so adding a relocated constant is a
one-line change and no name can be dropped by omission. A re-import
(`from science_model.independence import ROLE_RANK`) is not a binding and must pass;
only a fresh assignment fails.

---

## Phase 4 — Re-scope the durable-writer guard to the file, not the function

**Do not** implement this as a text match on the destination expression. A guard
that greps the call site for `graph.trig` is defeated by the codebase's own idiom:
`materialize.py:579` and `freshness.py:437` both write
`project_root / DEFAULT_GRAPH_PATH`, where the constant lives in
`graph/store/constants.py:24`. A new `ds.serialize(destination=graph_path)` with
`graph_path = root / DEFAULT_GRAPH_PATH` mentions neither `graph.trig` nor
`knowledge/` at the call site, yet is exactly the forbidden write. Matching text
shape reproduces the blind spot this phase exists to close.

A conservative ban is cheap here because the surface is tiny. There are exactly
**four** `.serialize(` call sites in `src/`, none under `graph/`:

- `distill/__init__.py:39,96` — Turtle, unrelated artifacts
- `model/patch.py:165` — standalone patch TriG
- `model/federation.py:114` — standalone federation TriG (also durable TriG, and
  also invisible to the current name-based guard)

**Change.** Two coupled rules, both structural rather than textual:

1. **Rule A (capability).** A `.serialize(` call may appear only in the allowlist
   `{distill/__init__.py, model/patch.py, model/federation.py}`. Any new
   serialization site anywhere else fails, whatever its destination.
2. **Rule B (reachability).** No allowlisted module may import or reference
   `DEFAULT_GRAPH_PATH`, transitively or otherwise.

Rule B is the substitute for dataflow analysis, and it is a genuine proof rather
than a heuristic: a module that never names the constant, and never receives a
path from a module that does, cannot address `knowledge/graph.trig` except by
hard-coding the literal — which Rule A's allowlist review would catch, and which
a trivial companion assertion (`"graph.trig" not in module_source`) rules out
outright. Neither rule inspects the destination *expression*, so neither is
defeated by aliasing a path into a variable.

Together with the existing name-based check on `save_graph_dataset`, the boundary
becomes: *`materialize` is the only module that can name the file, and it is the
only module that can call the primitive that writes it.*

**Also.** Document in `model/patch.py` and `model/federation.py` that
`emit_patch_trig` / the federation emitter write standalone artifacts to a
caller-supplied `out_path`, and must never target `knowledge/graph.trig`, which
remains the compiler's sole output. Today nothing states this, in either module.

---

## Phase 5 — Stop `science_tool/model/` from rotting

It has no in-repo importer, so nothing catches a break. It has three external
consumers who will find out at run time.

**Change.**

1. `tests/test_model_public_api.py` — assert the exported surface of
   `science_tool.model` (`__init__.py:21-` re-exports `CorrectedAssociation`,
   `attention`, `Opinion`, `emit_patch_trig`, `Patch*`, federation entry points)
   is importable and signature-stable. A signature change must break a test in
   *this* repo, not in pan-disease.
2. A short section in `docs/user-guide/` — most likely appended to
   `graph-and-derived-state.md`, or a new `working-model.md` — stating that
   `science_tool.model` is a *public library for consuming projects*, that the
   framework owns semantics and serialization while data processing belongs to the
   consumer, and that its stability contract is D-007. Today this is stated only
   in a module docstring, where no adopter will find it.

**Not done.** Wiring `science_tool/model/` into the CLI. It has no in-repo caller
because it is *supposed* to have none. Adding a `science model …` command group to
make it look used would be inventing a consumer.

---

## What this buys

After Phase 3, `Patch` is a real type in the layer that owns the data model, with
one IRI-minting rule and a type-checked ladder level. `graph/patch_membership.py`
and `model/patch.py` remain two modules answering two questions — but they now
answer them *about the same object*, and a reader meets that object once.

That is the whole claim. It is a small diff. Its value is that the working model's
central noun stops being an emergent property of two files that have never been
introduced.

## Test strategy

```bash
cd science && uv run --frozen pytest
cd science/model && uv run --frozen pytest
cd science && uv run ruff check && uv run pyright
```

Phase 3 is the only phase with real regression risk: `PATCH_MEMBERSHIP_POLICY_VERSION`
is written into every `MembershipRecord` (`patch_membership.py:45`) and therefore
into `graph.trig`. Moving the constant must not change its *value*. Assert this
directly — a snapshot test over a materialized `graph.trig` from `fixtures/`,
compared before and after the move — rather than trusting that a moved string
literal stayed equal.

Phases 1, 2, 4, 5 are behavior-preserving; the existing suite plus each phase's
guard is sufficient.

## Dependency order

**All five phases are independent.** An earlier draft asserted `Phase 1 → Phase 2
→ Phase 3`, on the premise that `store/` had to become a clean bottom layer before
`Patch` could be hosted. That premise was false: `Patch` lands in `science_model`,
which imports no `science_tool` code, so it needs neither the `store/` cleanup
(Phase 1) nor the `freshness` de-cycling (Phase 2). The five phases touch a few
files in common — `materialize.py` in Phases 2 and 3, `patch_membership.py` in
Phases 1 and 3 — but never in conflicting ways, and none establishes a
precondition for another. Sequence them by appetite, not by dependency; each is a
standalone improvement.

This track is independent of the
[convergence track](2026-07-10-half-applied-pattern-convergence-design.md) and can
run concurrently.
