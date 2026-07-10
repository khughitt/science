# Method Representation and Stochasticity — Umbrella Design

**Status:** accepted, not yet planned
**Task group:** `task:t075` (reproducibility validation)
**Supersedes the framing of:** `task:t079`
**Builds on:** `task:t077` (run reproducibility contract, shipped `beeff218`)
**Feeds:** `task:t078` (rerun-twice), `task:t080` (reproduction verdict as belief ceiling)

## Motivation

Science cannot currently answer a question a reader of any derived dataset
should be able to ask: *which steps that produced this were stochastic, and
what seeds did the original run use?*

Nothing in the model records whether a method is stochastic. `t077` shipped a
run-level `SeedPolicy` — `seeded` / `deterministic` / `stochastic-unseeded` —
but it is a hand-authored assertion, one per run, that nothing can check. The
`t077` design says so in as many words:

> `seed_policy` is deliberately **not** a `FingerprintComponent`: it asserts how
> the code behaves, it is not an observation of a run.

A field the author asserts and the tool cannot verify is a field that will drift.
Worse, one policy per run cannot describe a five-step pipeline in which two steps
are stochastic: `{kind: seeded, seeds: {numpy: 42}}` says nothing about *which*
step consumed that seed.

The fix is to put each fact where it belongs. Stochasticity is a property of a
**method**. Seeding is an act performed at a **step**. A seed value is an
observation of a **run**. Once those are separated, the run-level policy stops
being asserted and starts being *derived*.

## Findings: the surface is declared, and inert

Every structure this design needs is already declared in
`science/model/src/science_model/profiles/core.py`, wired to nothing.

Relation kinds that exist today:

```
workflow      --realizes-->    method
workflow      --contains-->    workflow-step
workflow-step --feedsInto-->   workflow-step
code-file     --implements-->  workflow-step | method
```

`method` and `workflow-step` are both full `EntityKind` descriptors with homes,
templates, and status vocabularies. Neither has a typed entity class — there is
no `MethodEntity` and no `WorkflowStepEntity` — so neither carries any field
beyond the base entity, and `sci:realizes` is materialized nowhere.

Across every project on this machine there are **zero** `method`, `workflow`,
`workflow-step`, and `workflow-run` entities. `t077` therefore shipped an
enforceable contract over an empty population. This is the design's central
enabling fact: **there is nothing to migrate**, and the shape is free.

Four defects in the current representation, all in scope:

1. **`workflow-step` conflates definition and execution.** Its descriptor reads
   "Individual step within a workflow definition *or run*"; its template carries
   both `workflow:` and `run:`; its statuses are `pending` / `running` /
   `complete` / `failed` — execution states on what should be a plan-time
   record. This is the definition/execution split `t077` performed for
   `workflow` vs `workflow-run`, left undone one level down.

2. **`templates/workflow.md` declares `method: "<method-slug>"`, which no model
   reads.** An inert field, of the kind `task:t085` exists to sweep.

3. **`workflow-step`'s template mints the wrong ID prefix.** Its
   `canonical_prefix` is `workflow-step`; its template declares `id: "step:<slug>"`.
   Because `workflow`, `workflow-run`, and `workflow-step` are all
   `template_ready=False`, their templates are *hand-copied* rather than rendered
   — so an author following the template writes a non-canonical ID. The
   id-prefix validator would catch it, but only as a **warn**, and only after the
   author has already written the file.

   The sibling case is **not** a defect and is recorded here so it is not
   "fixed" by mistake: `templates/method.md` shows `id: "method:{{nn}}-{{slug}}"`,
   which looks wrong for a `strategy="slug"` kind, but `method` is
   `template_ready=True` and its `_template` block rebuilds the ID from
   `entity_id`. Rendering `method` yields `id: method:leiden`. The literal line
   is inert illustration; only its wording misleads.

4. **A `workflow-run`'s `workflow` is authored but never retained.** The
   convention already exists: `templates/workflow-run.md` declares
   `workflow: "<workflow-slug>"`, and `qa_audit/runs.py` errors with
   `missing 'workflow'` when a run omits it. What is missing is everything
   downstream of authoring. `WorkflowRunEntity` carries only `manifest_path`,
   `resources`, and `fingerprint`, so — because `Entity` does not set
   `extra="forbid"` — the authored key is silently dropped on parse. The
   `sci:executes` relation (`workflow-run` → `workflow`) is declared in the core
   profile and materialized **nowhere**; the template's comment claiming it
   "materializes the executes link the audit walks" is false today. Derived
   datasets *can* reach both (`DerivationBlock` names `workflow` and
   `workflow_run`), but the run itself cannot name what it ran.

   So the defect is narrower than "add a field": the three missing pieces are
   **typed retention** on `WorkflowRunEntity`, **audit and materialization** of
   the edge, and **canonical template syntax** for the ref. Any derivation of
   `seed_policy` from a workflow's steps requires this edge to exist first.

   A note for implementers on where **not** to look: `validate/checks/id_prefixes.py`
   opens with a raw docstring containing a `PREFIX_RULES` dict — a fossil of the
   retired bash validator. It is not code. The live rule is `prefix_rules()`,
   derived from `markdown_entity_kinds()`, and it **already covers** `workflow`,
   `workflow-run`, `workflow-step`, and `method`. Nothing needs registering.

Separately, the word **transformation is overloaded three ways**:

- `EntityType.TRANSFORMATION` / `inquiry.transformations` — analysis-design
  steps carrying `tool` and `params`. **Zero non-empty instances authored
  anywhere**; the single patch carrying the key has `transformations: []`.
  `commands/plan-pipeline.md` instructs agents to write them, and none have.
- `workflow-step` — the implementation-level step. Declared, unused.
- `derivation.transformations` on derived datasets (`datasets_register.py`) —
  *identity* transforms such as `symbol_remap` and assembly liftover. Unrelated
  meaning, same word. Exactly one derived dataset carries it. This is the only
  live usage of the word anywhere.

This umbrella therefore **does not touch `transformation`**: it is neither
extended nor retired. Stochasticity attaches to `method`; the seed obligation
discharges at `workflow-step`, the thing that executes. Wiring design intent to
implementation is a small, later change that should be made when a project
actually authors a transformation and can tell us what the edge is for. Renaming
the `derivation.transformations` collision is likewise deferred.

## Non-goals

- **No belief-code change.** `graph/belief.py` is not opened, in this umbrella or
  in any spec under it. Consistent with `t077`.
- **No reproduction verdict, and no belief ceiling.** Those are `t080`.
- **No re-execution.** Rerun-twice and seeded-subsample checks are `t078`.
- **No change to `transformation`.** Neither extended nor retired; see Findings.
- **No renaming of `derivation.transformations`.** Noted above, deferred.
- **No promotion of methods to `science-commons`.** Methods are reusable records
  and are plausible commons citizens; the slug ID strategy chosen below keeps
  that door open. Actually moving them is future work.

## The model

Three levels, three different facts.

### Stochasticity is a property of a method

`stochasticity` is a **seed-control classification**, not a reproducibility
verdict. It answers one question — can this method's stochastic behavior be
pinned by seed parameters? — and nothing else. Whether a run actually reproduced
is `t080`'s question.

`method` gains a **trichotomy**, not a boolean, because "stochastic" hides two
materially different cases:

| `method.stochasticity` | meaning | step obligation |
|---|---|---|
| `deterministic` | no stochastic degree of freedom relevant to the output (a t-test) | none |
| `seedable` | stochastic, and *all* relevant stochastic degrees of freedom are controlled by the declared `seed_params` (UMAP, k-means, bootstrap) | must supply a seed |
| `nondeterministic` | stochastic behavior **remains after inputs, config, and environment are fixed**, or no complete seed interface exists | must supply a rationale |

`nondeterministic` is deliberately wider than "cannot be seeded". A method that
*accepts* a seed but retains residual nondeterminism — GPU kernels, parallel
float reduction order, `atomicAdd` — is `nondeterministic`, because binding its
seed would not make the run reproducible. The distinction is *fully*
seed-controlled versus not.

A boolean would force `nondeterministic` methods to either claim a seed they
cannot honor, or masquerade as deterministic. Both are lies the graph would
carry downstream.

`method.seed_params: list[str]` names the parameters through which a `seedable`
method is seeded (e.g. `["random_state"]`). It is required when and only when
`stochasticity == seedable`.

### Seeding is an act performed at a step

`workflow-step` becomes **definition-only**. Its statuses become the definition
lifecycle (`active` / `superseded` / `retired`); the `run:` field leaves the
template.

A definition-only step must not carry a seed **value**. Two runs of the same
workflow may legitimately use different seeds — that is the point of a seed. What
the step declares is the *binding*: which of the method's `seed_params` are
supplied, and from where. The realized value is a run observation.

```yaml
# entities/workflow-steps/cluster.md
id: "workflow-step:cluster"
kind: "workflow-step"
workflow: "workflow:scrna-pipeline"
rule_name: "cluster"                  # the snakemake rule that executes it
method: "method:leiden"               # sci:applies
seed_bindings:
  random_state: "config.seed"         # a source, not a value
```

A binding's source may be a config key, or the literal form `literal:42` when a
step pins its seed. Either way the *declaration* says the parameter is supplied;
the *run* says what it was supplied with.

The step is where the obligation is discharged because the step is what
executes — it is the thing whose code SHA and environment `t077` fingerprints.

### A seed value is an observation of a run

The run records the seeds actually realized, per step, inside the fingerprint.
`step_seeds` is the **authoritative** record of seed values:

```yaml
fingerprint:
  step_seeds:
    workflow-step:cluster: {random_state: 42}
    workflow-step:embed:   {random_state: 7}   # same param name, different value
  seed_policy:                # DERIVED, not authored
    kind: seeded
```

### `seed_policy.kind` becomes derived

| steps of the workflow | derived `seed_policy.kind` |
|---|---|
| every step's method is `deterministic` | `deterministic` |
| every `seedable` step bound and realized all its `seed_params`, no `nondeterministic` step | `seeded` |
| any `seedable` step left a `seed_param` unbound, **or** any step's method is `nondeterministic` | `stochastic-unseeded` |

This lands on `t077`'s **existing** three-value vocabulary — no token is added or
removed. What changes is provenance: `seed_policy` stops being an assertion the
author makes and becomes a fact the tool captures, computed from declared
methods, declared bindings, and realized values.

**`SeedPolicy.seeds` is removed.** As shipped it is `dict[str, int]` — one value
per parameter name — so two steps that both seed `random_state` with different
values cannot both be represented. Any run-level summary of per-step seeds is
either lossy or a namespaced duplicate of `step_seeds`. `SeedPolicy` therefore
becomes `{kind, rationale}`, and the invariant `t077` placed on it (`kind ==
seeded` requires non-empty `seeds`) moves up to `RunFingerprint`: `kind ==
seeded` requires non-empty `step_seeds`. `SeedPolicy.rationale` (required for
`stochastic-unseeded`) is composed from the offending steps.

Removing `seeds` leaves `seed_policy.kind` as a **coarse run classification**,
and that is the intended weight. It does not distinguish "a step left a seed
unbound" from "a step's method is inherently nondeterministic" — both derive
`stochastic-unseeded`. The explanation lives one level down, in `step_seeds` and
in the `rationale` composed from the offending steps; a downstream consumer that
needs the distinction inspects those steps and their methods. **No enum values
are added to `SeedPolicy.kind`** to carry that distinction. Widening the
top-level policy would recreate exactly the summary-versus-record duplication
that `SeedPolicy.seeds` was removed for.

This resolves the discomfort `t077`'s design recorded. Once methods carry
stochasticity, the run no longer has to assert how the code behaves. It observes.

### The shape

```
workflow:scrna-pipeline
    |
    | sci:contains                       (exists today)
    v
workflow-step:cluster  (implementation — the thing that executes)
    rule_name: cluster                   snakemake rule
    seed_bindings:                       obligation discharged here
      random_state: config.seed          a source, never a value
    |
    | sci:applies                        (new)
    v
method:leiden
    stochasticity: seedable
    seed_params: [random_state]


workflow-run:r1 --sci:executes--> workflow:scrna-pipeline   (edge added in Spec 0)
    fingerprint.step_seeds:
      workflow-step:cluster: {random_state: 42}             the realized value
```

Vocabulary changes required:

- **Add** `sci:applies`: `workflow-step` → `method`.
- **Retire** `sci:realizes` (`workflow` → `method`). A workflow no longer names
  one method; its steps each apply one. Retiring this is what makes the inert
  `method:` field in `templates/workflow.md` (defect 2) go away rather than get
  quietly implemented.

`sci:contains` (`workflow` → `workflow-step`) and `sci:feedsInto`
(`workflow-step` → `workflow-step`) already exist and are unchanged.

## Decomposition

Four specs. Each ships independently and leaves the tree green.

### Spec 0 — Coherent method and step representation

Representation hygiene. **No new behavior**; nothing about stochasticity yet.

- Add `MethodEntity` and `WorkflowStepEntity` typed classes, with the fields the
  templates already imply (`workflow`, `rule_name` for the step).
- Resolve the definition/execution conflation: `workflow-step` becomes
  definition-only; statuses become `active` / `superseded` / `retired`; `run:`
  leaves the template.
- Correct `templates/workflow-step.md` to `id: "workflow-step:<slug>"` (defect 3).
  `templates/method.md`'s illustrative `{{nn}}` line is reworded to
  `method:<slug>` to stop misleading readers, but this is cosmetic — the rendered
  ID is already correct. `method` keeps `strategy="slug"`: slug IDs are portable
  across projects, which is what a reusable method record needs and what a future
  move to `science-commons` requires. Do **not** touch `id_prefixes.py`: the live
  `prefix_rules()` already covers these kinds. Making the `template_ready=False`
  workflow kinds generator-rendered is a plausible follow-up, not required here.
- Retain the already-authored `workflow:` ref as a typed
  `WorkflowRunEntity.workflow` field, audit it, and materialize the
  already-declared `sci:executes` edge (defect 4). Without this edge, Spec 2
  cannot traverse run → workflow → steps at all.

  The field is **optional** (`str = ""`) in this spec. Spec 0 is behavior-neutral:
  it preserves existing fixtures and already-authored runs, while a value that is
  present but unresolvable fails loudly. Requiring the field belongs to Spec 2,
  where deriving `seed_policy` actually depends on run → workflow → steps.

  The resolution guard lives in the **compiler** — the boundary where an authored
  ref becomes graph structure — and nowhere else. A post-hoc check in
  `graph/store/validation.py` would re-read `graph.trig` to assert what the
  compiler had just refused to emit; under kernel closure that only guards against
  out-of-band mutation of `graph.trig`, which does not justify a second validation
  surface.
- Retire `sci:realizes`; delete the inert `method:` field from
  `templates/workflow.md` (defect 2).

The kind-descriptor reconciliation gate treats per-kind surfaces as derived by
**field presence**; adding typed classes must keep that three-way gate passing.

**Done when:** `method` and `workflow-step` have typed classes; `science validate`
and the reconciliation gate pass; no template/descriptor divergence remains.

### Spec 1 — Stochasticity and seeds (`t079`'s real content)

The vocabulary lives on the **method**; the bindings live on the **step**; no seed
*value* appears on either.

- `Stochasticity` — a new `StrEnum` in `science_model.entities`:
  `deterministic | seedable | nondeterministic`.
- `MethodEntity.stochasticity: Stochasticity | None = None` — **optional on the
  model, required at the point of use.**

  This spec originally called the field "required, defaultless," reasoning by
  analogy to `t077`'s `is_fingerprinted`. A survey of the live corpus refuted the
  premise. 51 `method` entities exist — `cancer` 27, `protein-landscape` 13,
  `health` 6, `seq-feats` 5 — and **46 of them are not computational procedures at
  all.** Twenty are glossary terms auto-promoted from
  `knowledge/sources/local/terms.yaml` (`method:chip-seq` is a one-line definition
  of a wet-lab assay); the rest are design documents — `CC-2: ResponseDefinition
  ontology`, `Coverage Denominators and Allowed Claims`, `UK Biobank data-field
  specification & access plan`. Only 4 are `seedable` and 1 `deterministic`, and
  none names a seed parameter.

  Requiring the field on the model would hard-fail the graph build in four live
  projects — `load_project_sources` runs with `strict_core_schema=True` under
  `validate` and the compiler, so a missing required field raises — until 46
  category errors had been authored. That is the same unverifiable assertion this
  umbrella exists to remove, at 90% of the corpus.

  So the contract is enforced **where it is consumed, not where it is declared**:
  `workflow-step.method-stochasticity-missing` is a validate **ERROR** when a step
  applies a method that declares no `stochasticity`. `None` means *unclassified*
  and is distinguishable from every classification, so nothing fails open. A
  method gets classified when someone first wires it into a workflow — which is
  also the first moment the answer is both knowable and checkable. Spec 2's
  `register-run` fails closed on the same condition. Zero `workflow-step` entities
  exist today, so this ships green and imposes no migration.

- `MethodEntity.seed_params: list[str] = []`. It is deliberately **not** a
  model-level invariant that `seedable` implies non-empty `seed_params`: all four
  seedable methods in the corpus describe their stochastic step without naming its
  parameter, so a hard requirement would outlaw the honest record *"seedable, and I
  have not yet identified the parameter."* `method.seed-params-missing` reports it
  as a warning instead.

- `WorkflowStepEntity.method: str = ""` (a `method:` ref),
  `seed_bindings: dict[str, str]`, and `rationale: str = ""`.
- `seed_bindings` maps a `seed_param` name to its **source**, never its value:
  `config.<key>` or `literal:<int>`. Any other form is a model-level `ValueError`.
  A malformed source is a syntax error, not an epistemic gap, and the population is
  zero — so it fails early and costs no migration.
- Add `sci:applies` (`workflow-step` → `method`) and materialize it. The resolution
  guard mirrors `sci:executes`: a ref that does not resolve, or resolves to a
  non-`method`, is a hard compiler error.
- Delete the `inquiry:` key from `templates/workflow-step.md` (carried over from
  Spec 0). No `RelationKind` in `CORE_PROFILE` names `inquiry` as a source or
  target, and the template's `inquiry AnnotatedParam` hint points at a mechanism
  `test_inquiry.py` records as retired. The key is untyped, unaudited, and silently
  dropped at parse — precisely the defect class Spec 0 closed.
- **Warn-only** validate checks, per `t079`'s "ship as visibility warnings first":
  - `workflow-step.seed-binding-missing` — step applies a `seedable` method and leaves one of its `seed_params` unbound.
  - `workflow-step.rationale-missing` — step applies a `nondeterministic` method, supplies no rationale.
  - `workflow-step.seed-binding-on-deterministic-method` — a binding where none is meaningful.
  - `workflow-step.seed-binding-unknown-param` — a binding naming a parameter absent from the method's `seed_params`. **Suppressed** when the method declares no `seed_params` at all: `method.seed-params-missing` already reports that, and firing both would report one defect twice.
  - `method.seed-params-missing` — `seedable` method names no seed parameter.

**Done when:** a workflow whose step applies `method:leiden` without binding
`random_state` produces a warning and blocks no run; a step applying a method with
no `stochasticity` is an error; `science validate` stays green in all four
consumer projects with zero entity edits.

### Spec 2 — Runs observe seeds

`register-run` reaches the workflow through `WorkflowRunEntity.workflow`, then
its steps through a **source-layer reverse index** over `WorkflowStepEntity.workflow`.

Not through `sci:contains`, as an earlier draft of this section claimed. Two
things are wrong with that path. `WorkflowEntity` has no `steps` field, so a
workflow never *declares* its steps — containment is authored bottom-up, by each
step naming its workflow. And `sci:contains` is declared in `CORE_PROFILE`
(`workflow → workflow-step`) but **never emitted by `materialize.py`**: three
call sites in `cross_impact.py` and `freshness.py` read the predicate, nothing
writes it. It is exactly the declared-and-inert surface this document's Findings
section was written about. `register-run` operates on `load_project_sources`, not
on the graph, so it needs no edge; materializing `sci:contains` is real work with
real value and belongs to its own task, not to this one.

- `RunFingerprint.step_seeds: dict[str, dict[str, int]]`, keyed by
  `workflow-step:` ref. This is the authoritative seed record.
- **Remove `SeedPolicy.seeds`** (lossy: `dict[str, int]` cannot hold two steps
  seeding `random_state` differently). `SeedPolicy` becomes `{kind, rationale}`.
  Move `t077`'s "`seeded` requires non-empty `seeds`" invariant up to
  `RunFingerprint`: `seed_policy.kind == "seeded"` requires non-empty
  `step_seeds`. This is a breaking change to `t077`'s model, and safe — though
  not for the reason first given. The run population is **not** zero: 15
  `workflow` and 47 `workflow-run` entities live across 6 of 23 project roots.
  What is zero is the **fingerprint** population: no run anywhere carries a
  `fingerprint`, so no `SeedPolicy` has ever been persisted. The conclusion
  stands; the noun was wrong.
- `seed_policy` becomes **derived and captured** at `register-run` from the
  workflow's steps, their `seed_bindings`, and the realized values, per the table
  above. It is no longer authored.
- A run whose workflow has no steps **fails closed** at `register-run`: the
  policy cannot be derived, and defaulting it — to `deterministic`, to `seeded`,
  or to an "unknown but acceptable" value — would reintroduce the unverifiable
  assertion this umbrella exists to remove. Zero `workflow-step` entities exist
  in any of the 23 project roots, so this is safe to impose from day one.

**A methodless step is an error on both surfaces** (ruled 2026-07-10; carried
over from Spec 1, which left it unruled because it had no consumer until
`seed_policy` was derived). A step with no `method:` ref contributes no
stochasticity classification, so the derivation table above cannot read it:

- `validate` reports `workflow-step.method-missing` as an **ERROR**, symmetric
  with Spec 1's `workflow-step.method-stochasticity-missing`.
- `register-run` fails closed on the same condition, and on a step whose method
  is unclassified (`stochasticity is None`).

The two rejected alternatives collapse into one another. Deriving `deterministic`
from a methodless step asserts a reproducibility fact about code that was never
named. *Skipping* methodless steps in the derivation reaches the same assertion
by a quieter route: a workflow whose steps are all methodless yields an empty
step set, and an empty set satisfies "every step's method is `deterministic`"
vacuously. Same false claim, no rule fired. The cost of erroring is that a
pure-I/O step (a file copy, a format conversion) must name a method — one entity
per project, `stochasticity: deterministic` — which states out loud what was
already being assumed.

  Adoption pressure is answered by **phasing and a legible error**, never by a
  soft fallback. The error must name the fix, not the invariant:

  > `register-run` cannot derive `seed_policy`: `workflow:X` declares no
  > `workflow-step`. Declare at least one step before registering a run.

  The **minimum adoption unit is one step**. A one-step workflow is fully valid:
  it names a method, and if that method is `seedable` it binds a seed. Because
  Spec 1's `seed-binding-missing` is warn-only, an adopter can declare that step
  with no bindings at all and still register runs — the graph then reports
  `stochastic-unseeded`, which is true, rather than a defaulted `seeded`, which
  would not be. Migration is: add one step, then tighten.

**Done when:** `register-run` derives `seed_policy` and refuses to invent one;
a zero-step workflow errors with the message above; a methodless step errors at
both `validate` and `register-run`; a step whose method is unclassified errors at
`register-run` as it already does at `validate`; two steps seeding the same
parameter name with different values round-trip without collision; `t077`'s
fingerprint tests pass with `seed_policy` no longer hand-authored and
`SeedPolicy.seeds` gone.

**Corpus note.** `register-run` takes a run *id* and reads
`entities/workflow-runs/<slug>.md`; the 37 run entities synthesized by the
datapackage adapter are not its input and are out of scope here. Of the 11
authored run files, 9 name their workflow correctly. Two do not, and one is this
umbrella's own doing: `post-acute-infection` authors `workflow:
"t035-cross-trigger-pathway-overlap"` — a bare slug, no `workflow:` prefix —
which Spec 0 began auditing when it typed the field, so `science graph audit`
fails in that project today. `natural-systems` leaves `workflow:` empty, which
silently skips the `sci:executes` edge; that project has ~50 unresolved
references already. Neither is fixed by this spec. Both are tracked separately.

### Spec 3 — Downstream transparency

The reader-facing payoff. Given `dataset:X`, reach its run, its `step_seeds`,
each step, and that step's method `stochasticity`, and answer:

> These two steps were stochastic. `cluster` used `random_state=42`.
> `embed` was `nondeterministic` (GPU atomics) and cannot be reproduced exactly.

**Was blocked by `t093`; `t093` is done (2026-07-10), so Spec 3 is ready.** Spec 2
left *no run in any project carrying a `fingerprint`*: `register-run` demanded an
authored fingerprint stub that strict loading — the default for `validate` and
`graph build` — rejected, so Spec 3 would have been built against a surface nobody
could populate. `t093` split the run's **declarations** into an authored
`execution:` block (`RunDeclaration`: executor, both artifact localities, and
`capture_origin`) and left `fingerprint:` **wholly captured** by `register-run` —
this umbrella's own thesis applied one level up. A run now validates before it is
ever registered.

Two consequences Spec 3 inherits. `capture_origin` moved to the declaration, which
made `executor: commons` registrable for the first time (the model required it and
nothing could supply it). And because the declared fields are copied into the
fingerprint so it stands alone, they can now **drift**: `validate` emits
`run.fingerprint-declaration-drift` when `execution:` is edited after registering.
Spec 3 reads the captured fingerprint, so it inherits that guarantee rather than
re-checking it.

**Not a graph-only traversal.** `materialize.py` emits exactly one fingerprint
fact — `sci:fingerprintPolicy`, a presence marker (`materialize.py:1234`). It
emits no `step_seeds`, no method `stochasticity`, no `seed_bindings`. So the CLI
uses the **graph** to resolve `dataset → fingerprinted run`, and the **source
layer** for the fingerprint, steps, and methods — the same reverse index over
`WorkflowStepEntity.workflow` that Spec 2's `register-run` uses. That split keeps
`t092` (`sci:contains` declared but never emitted) off the critical path;
materializing a query surface for these fields is a real alternative, and the
thing that would make `t092` blocking.

**Own run vs inherited provenance.** `graph/run_resolution.py:51` deliberately
separates `own_derivation_run` from `resolved_empirical_runs`, which walks
`member_of` to a parent. The reader-facing command should use *inherited*
resolution — a member dataset's reproducibility really is its parent run's — but
must **display the chain**, so it never implies the member was directly
run-produced.

**Done when:** a CLI surface reports the stochastic steps and realized seeds in
any derived dataset's provenance, and names the run it inherited them from.

## Consequences

- Stochasticity becomes a first-class, queryable property rather than tribal
  knowledge held in a pipeline author's head.
- `seed_policy` moves from asserted to observed, closing the gap `t077`'s design
  flagged and could not close alone.
- `t080` gains real leverage: a failed reproduction against a step whose method is
  `nondeterministic` is *explained*, not mysterious — which is exactly the
  `unverified` vs `failed` distinction the `t080` note demands be preserved.
- `t078` gains a target: the steps worth re-running twice are precisely the
  `seedable` ones.
- The `method` record becomes portable and reusable, and therefore a candidate for
  `science-commons` — the first shared entity kind that is neither a dataset nor
  a paper summary.

## Open questions

- ~~**Binding source grammar.**~~ *Settled in Spec 1:* exactly two forms,
  `config.<key>` and `literal:<int>`. Any other value is a model-level `ValueError`.
  Env vars and per-run overrides are deferred until a real workflow needs one; who
  resolves the source at `register-run` time is Spec 2's question.
- ~~**Multi-seed steps.**~~ *Settled in Spec 1:* a partial binding stays a warning
  (`seed-binding-missing`, one per unbound parameter). The `seeded` derivation
  requires **all** of a step's `seed_params` to be bound and realized; a partially
  bound step derives `stochastic-unseeded`. This follows from the definition of
  `seedable` — a method is `seedable` only if its declared `seed_params` control
  *all* relevant stochastic degrees of freedom, so leaving one unbound leaves the
  step uncontrolled.
- **Snakemake reconciliation.** `workflow-step.rule_name` names a snakemake rule.
  Nothing checks that the rule exists. A cross-check belongs with `t079`'s
  successor work, not here.
