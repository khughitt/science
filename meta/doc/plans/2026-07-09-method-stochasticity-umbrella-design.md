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

4. **A `workflow-run` cannot reach its `workflow`.** `WorkflowRunEntity` carries
   only `manifest_path`, `resources`, and `fingerprint` — there is no `workflow`
   field. The `sci:executes` relation (`workflow-run` → `workflow`) is declared in
   the core profile and materialized **nowhere**. Derived datasets *can* reach
   both (`DerivationBlock` names `workflow` and `workflow_run`), but the run
   itself cannot name what it ran. Any derivation of `seed_policy` from a
   workflow's steps requires this edge to exist first.

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

`method` gains a **trichotomy**, not a boolean, because "stochastic" hides two
materially different cases:

| `method.stochasticity` | meaning | step obligation |
|---|---|---|
| `deterministic` | same inputs, same outputs (a t-test) | none |
| `seedable` | stochastic, accepts a seed (UMAP, k-means, bootstrap) | must supply a seed |
| `nondeterministic` | stochastic and **cannot** be seeded (GPU atomics, parallel float reduction order) | must supply a rationale |

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
- Add `WorkflowRunEntity.workflow` (a `workflow:` ref) and materialize the
  already-declared `sci:executes` edge (defect 4), with a graph-validate check
  that the target resolves to a `workflow`. Without this edge, Spec 2 cannot
  traverse run → workflow → steps at all.
- Retire `sci:realizes`; delete the inert `method:` field from
  `templates/workflow.md` (defect 2).

The kind-descriptor reconciliation gate treats per-kind surfaces as derived by
**field presence**; adding typed classes must keep that three-way gate passing.

**Done when:** `method` and `workflow-step` have typed classes; `science validate`
and the reconciliation gate pass; no template/descriptor divergence remains.

### Spec 1 — Stochasticity and seeds (`t079`'s real content)

- `MethodEntity.stochasticity: Stochasticity` (required, defaultless — a default
  would make the contract fail open, exactly as `t077` reasoned about
  `is_fingerprinted`).
- `MethodEntity.seed_params: list[str]`, required iff `stochasticity == seedable`.
- `WorkflowStepEntity.method: str` (a `method:` ref) and
  `WorkflowStepEntity.seed_bindings: dict[str, str]` mapping a `seed_param` name
  to its source (a config key, or `literal:<n>`), plus `rationale` for
  `nondeterministic` methods. No seed **value** lives on the step.
- Add `sci:applies` and materialize it.
- **Warn-only** validate checks, per `t079`'s "ship as visibility warnings first":
  - `workflow-step.seed-binding-missing` — step applies a `seedable` method and leaves one of its `seed_params` unbound.
  - `workflow-step.rationale-missing` — step applies a `nondeterministic` method, supplies no rationale.
  - `workflow-step.seed-binding-on-deterministic-method` — a binding where none is meaningful.
  - `workflow-step.seed-binding-unknown-param` — a binding naming a parameter absent from the method's `seed_params`.
  - `method.seed-params-missing` — `seedable` method names no seed parameter.

**Done when:** a workflow whose step applies `method:leiden` without binding
`random_state` produces a warning, and no run is blocked.

### Spec 2 — Runs observe seeds

Depends on Spec 0's `sci:executes` edge: `register-run` reaches the workflow
through `WorkflowRunEntity.workflow`, then its steps through `sci:contains`.

- `RunFingerprint.step_seeds: dict[str, dict[str, int]]`, keyed by
  `workflow-step:` ref. This is the authoritative seed record.
- **Remove `SeedPolicy.seeds`** (lossy: `dict[str, int]` cannot hold two steps
  seeding `random_state` differently). `SeedPolicy` becomes `{kind, rationale}`.
  Move `t077`'s "`seeded` requires non-empty `seeds`" invariant up to
  `RunFingerprint`: `seed_policy.kind == "seeded"` requires non-empty
  `step_seeds`. This is a breaking change to `t077`'s model, and safe: the
  population is zero.
- `seed_policy` becomes **derived and captured** at `register-run` from the
  workflow's steps, their `seed_bindings`, and the realized values, per the table
  above. It is no longer authored.
- A run whose workflow declares no steps **fails closed** at `register-run`: the
  policy cannot be derived, and a defaulted policy would fail open. The empty
  entity population makes this safe to impose from day one.

**Done when:** `register-run` derives `seed_policy` and refuses to invent one;
two steps seeding the same parameter name with different values round-trip
without collision; `t077`'s fingerprint tests pass with `seed_policy` no longer
hand-authored and `SeedPolicy.seeds` gone.

### Spec 3 — Downstream transparency

The reader-facing payoff. Given `dataset:X`, traverse to its run, to
`step_seeds`, to each step, to its method's `stochasticity`, and answer:

> These two steps were stochastic. `cluster` used `random_state=42`.
> `embed` was `nondeterministic` (GPU atomics) and cannot be reproduced exactly.

**Done when:** a CLI surface reports the stochastic steps and realized seeds in
any derived dataset's provenance.

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

- **Binding source grammar.** `seed_bindings` maps a parameter to a source string
  (`config.seed`, `literal:42`). Whether that grammar needs more forms — an env
  var, a per-run override — and who resolves it at `register-run` time, is a
  Spec 1 question. The two forms above are sufficient for the checks specified.
- **Multi-seed steps.** `seed_params` is a list, so a method may take several
  seeds. The `seeded` derivation above requires **all** of a step's `seed_params`
  to be bound and realized; a partially-seeded step derives
  `stochastic-unseeded`. Whether a partial binding is ever legitimate is a Spec 1
  question.
- **Snakemake reconciliation.** `workflow-step.rule_name` names a snakemake rule.
  Nothing checks that the rule exists. A cross-check belongs with `t079`'s
  successor work, not here.
