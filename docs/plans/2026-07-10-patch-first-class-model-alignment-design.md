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

**3. `store/` is not a clean bottom layer.** `store/validation.py` reaches *up*
into its conceptual superiors: `patch_membership` (`:18`), `run_resolution`
(`:19`), and lazily `dataset_independence` (`:250`). No hard cycle results — those
modules do not import `store` back — but `store/` cannot host a base type while it
depends on derivation modules.

## A fourth fault, found while writing this doc

The kernel-closure guard `tests/graph/test_durable_write_boundary.py` matches call
sites **by function name** (`save_graph_dataset` / `_save_dataset`), and its own
docstring is candid that an aliased or indirect call evades it.

`model/patch.py:165` calls `ds.serialize(destination=out_path, format="trig")`.
That is a durable TriG write the guard cannot see.

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
that already owns "what an entity is," and leaves the four faults above in place.

**Name the concept once in `science_model`.** *(chosen)* Both modules keep their
distinct jobs; both consume one shared definition. The patch becomes a first-class
addressable object in the schema layer, which is exactly what the RFC's "promoted
to a first-class, addressable modeling unit" asks for, and what `model/patch.py`'s
own docstring claims it already is.

---

## Phase 1 — Make `store/` a clean bottom layer

Prerequisite for everything else: nothing can be hosted below `store/` while
`store/` depends upward.

**Change.** `store/validation.py`'s three upward imports become injected
dependencies. The validation functions take the membership/run-resolution/
independence facts they need as arguments rather than importing the modules that
compute them. Callers (in `materialize`, which already sits above all four)
supply them.

**Guard.** Extend `tests/test_store_package_structure.py` with an import-direction
assertion: no module under `graph/store/` may import from `graph/` outside
`graph/io.py`, `graph/errors.py`, `graph/export_types.py`.

---

## Phase 2 — Break the `materialize ⇄ freshness` cycle

**Change.** `freshness.py:420` needs `materialize._build_dataset_from_sources`,
i.e. "build an in-memory Dataset from `ProjectSources`." That function is *not*
materialization — it is dataset construction, and `materialize` is merely where it
grew. Extract it to `graph/dataset_build.py`. Both `materialize` and `freshness`
then import downward from it, and the function-local import at `freshness.py:420`
becomes a module-level one.

`build_dataset_from_sources` (`materialize.py:291`, the public name) stays
re-exported from `materialize` for compatibility with `patch/cli.py:9` and
`validate/checks/graph.py:154`.

**Guard.** `tests/test_graph_import_layering.py`: an AST check that no module
under `graph/` contains a function-local `import` of another `graph/` module.
Function-local imports of *third-party* modules stay allowed. This makes the next
cycle visible at the moment it is introduced, which is the only time it is cheap
to fix.

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

Also moved: `DEPENDENCE_ROLES`, `VALIDATION_ROLE`, `OVERLAP_RANK`, `ROLE_RANK` from
`graph/dataset_independence.py:19-24` → `science_model/independence.py`. Same
argument, different vocabulary. `DIRECT_RELATION_PREDICATES`
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

**Guard.** `tests/test_patch_vocabulary_single_source.py`: fail if `LadderLevel`,
`MemberRole`, `DerivationReason`, or `PATCH_MEMBERSHIP_POLICY_VERSION` is defined
anywhere outside `science_model/patch.py`.

---

## Phase 4 — Re-scope the durable-writer guard to the file, not the function

**Change.** `tests/graph/test_durable_write_boundary.py` currently asks *which
function is called*. Add a complementary check that asks *which file is written*:
fail if any module outside the allowlist contains a call to `Dataset.serialize`,
`Graph.serialize`, or `.write_text` whose destination expression mentions
`graph.trig` or `knowledge/`.

`model/patch.py:165` passes — it serializes to a caller-supplied `out_path`. The
point is to make that fact *checked* rather than incidental.

**Also.** Document in `model/patch.py`'s docstring that `emit_patch_trig` writes a
standalone patch artifact and must never target `knowledge/graph.trig`, which
remains the compiler's sole output. Today nothing states this.

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

Phase 1 → Phase 2 → Phase 3. Phase 4 and Phase 5 are independent of all others and
of each other; either can land first as a standalone improvement.

This track is independent of the
[convergence track](2026-07-10-half-applied-pattern-convergence-design.md) and can
run concurrently.
