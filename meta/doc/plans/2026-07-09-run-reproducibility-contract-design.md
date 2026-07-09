# Analysis-Run Reproducibility Contract — Design (t077)

> **Status:** Accepted design, pending implementation plan.
> **Task:** `[t077]` (parent `[t075]`, group `reproducibility-validation`).
> **Question:** `question:0016-reproducibility-validation`.
> **Roadmap:** [`2026-07-08-epistemic-reproducibility-and-grounding-roadmap.md`](2026-07-08-epistemic-reproducibility-and-grounding-roadmap.md).
> **Scope:** toolkit code (`~/d/science/science/`), plus a format migration that
> sweeps `~/d/science-commons`.

## Problem

The Science creed says *"believe nothing until we re-analyze the data
ourselves."* Knowledge-**graph** rebuild is rigorously reproducible. An
empirical evidence line's **claim** is not: nothing forces it to resolve to a
reproducible analysis run.

Concretely, the fields that should carry that guarantee are dead:

- `EvidencePayloadCore.source_commit` (`evidence_payload.py:49`) is
  `str | None = None` and is read by no validator and no belief code.
- `DerivationBlock.git_commit` (`packages/schema.py:173`) is a bare `str` with
  no validator, so `""` is accepted. It is **caller-supplied, not captured**:
  `frontmatter.py:327` reads `raw.get("git_commit", "")`.
- There is **no** environment digest, seed policy, or run-level input/output
  hashing anywhere in `science/src/` or `science/model/src/`.

Two facts discovered while designing shape the whole solution:

1. **`workflow-run` is already a real entity kind** (`EntityType.WORKFLOW_RUN`,
   files at `entities/workflow-runs/<slug>.md`, typed `WorkflowRunEntity` at
   `entities.py:895`). It carries only `manifest_path` and `resources`. The run
   *object* exists; it has no fingerprint.
2. **`git_commit` is already a workflow-run frontmatter key**, merely *copied
   down* onto each dataset:
   `datasets_register.py:771` does `run_fm.get("git_commit", "")`, then writes
   it into the dataset's `DerivationBlock` (`:798`) and markdown (`:253`).

So this is not "invent a run record." It is: **give the existing run entity a
captured fingerprint, stop denormalizing run identity onto datasets, and require
belief-eligible empirical evidence to resolve to such a run.**

## Non-goals

- **No belief-code change.** `graph/belief.py` is not opened. A missing run is
  *absent required structure*, not a weak epistemic verdict; belief must not
  silently cap or exclude it, because that turns a malformed empirical line into
  a plausible-looking downstream result.
- Reproduction **verdicts** (`unverified` / `self-consistent` /
  `independently-reproduced` / `failed`) and their belief ceiling are `[t080]`.
- The stochastic-step / unpinned-environment **lint** is `[t079]`.
- Actually **re-executing** workflows (rerun-twice, seeded subsample) is `[t078]`.

## The `literature` / `empirical_data` boundary

The invariant is only coherent because published results are not empirical
evidence *of ours*:

- **`literature`** — a published paper's result, abstracted claim, reported
  effect, author conclusion, or extracted statement we have **not** independently
  reproduced. Remains belief-eligible as literature, with its existing lower
  ceiling and role semantics. **No run required.**
- **`empirical_data`** — evidence from our own analysis of data, or from a
  trusted in-project / commons workflow output, **resolving to a workflow-run
  bearing a reproducibility fingerprint.**

An external run verdict is useful metadata on a paper/package/workflow, but it
**never** promotes a line to `empirical_data` unless Science re-executes or
validates the run under this contract. Waivers, if ever added, must cap or
exclude from empirical strengthening rather than silently pass; none are
introduced here.

## Design

### A. Data model

New leaf module `model/src/science_model/run_fingerprint.py` (a leaf so
`entities.py` may import it without cycles, mirroring the `digests.py`
precedent). `WorkflowRunEntity` gains `fingerprint: RunFingerprint | None`.

```python
class ComponentProvenance(StrEnum):
    CAPTURED = "captured"    # a Science producer observed it directly
    ATTESTED = "attested"    # supplied by an executor Science does not own
    UNKNOWN  = "unknown"     # explicitly absent — never ""

class FingerprintComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value:        str | None = None
    provenance:   ComponentProvenance
    attested_by:  str | None = None
    attested_at:  datetime | None = None   # typed; ISO-serialized
    evidence_ref: str | None = None        # artifact/log ref
```

Model validators make `""` **unrepresentable**, which is the root cause of the
`git_commit` failure:

- `captured | attested` ⇒ `value` present and non-empty.
- `unknown` ⇒ `value is None`.
- `attested` ⇒ `attested_by` **and** `attested_at` present.
- `captured` ⇒ `attested_by` / `attested_at` absent.

`value` is always a string, so the one non-digest component encodes explicitly:
**`code_dirty.value` is the canonical lowercase `"true"` / `"false"`**, validated
against exactly those two tokens. It stays a `FingerprintComponent` rather than a
bare `bool` so that an external run may legitimately report it `unknown`.

```python
class ExecutorKind(StrEnum):
    LOCAL = "local"; COMMONS = "commons"; EXTERNAL = "external"

class ArtifactLocality(StrEnum):
    SCIENCE_MANAGED = "science-managed"   # landed / archived
    EXTERNAL         = "external"
```

`capture_origin` sits at the **fingerprint** level, not per component: a single
run's captured facts all come from one execution, so per-component origins would
be incoherent (a `code_sha` observed by project A and an `environment_digest` by
project B is not a run).

```python
class CaptureOrigin(BaseModel):
    origin_project: str
    origin_run_ref: str            # workflow-run:<slug>
    captured_at:    datetime
    captured_by:    str            # tool/agent/system — not necessarily a person
    capture_policy: str            # the ORIGIN's policy version
    source_ref:     str | None = None      # commons entity/bundle/artifact ref
    source_digest:  str | None = None      # hash of the imported record

class SeedPolicy(BaseModel):
    kind:      Literal["seeded", "deterministic", "stochastic-unseeded"]
    seeds:     dict[str, int] | None = None   # required iff kind == "seeded"
    rationale: str | None = None              # required iff "stochastic-unseeded"

class RunFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fingerprint_policy:       str                 # "science-run-fingerprint/v1"
    executor:                 ExecutorKind
    input_artifact_locality:  ArtifactLocality
    output_artifact_locality: ArtifactLocality
    capture_origin:           CaptureOrigin | None = None

    code_sha:               FingerprintComponent
    code_dirty:             FingerprintComponent
    environment_digest:     FingerprintComponent
    container_digest:       FingerprintComponent | None = None
    parameters_digest:      FingerprintComponent   # digests the existing config_snapshot
    input_manifest_digest:  FingerprintComponent
    output_manifest_digest: FingerprintComponent

    input_manifest_ref:  str | None = None   # per-file manifest lives here...
    output_manifest_ref: str | None = None   # ...not inside the component

    seed_policy: SeedPolicy
```

`seed_policy` is deliberately **not** a `FingerprintComponent`: it asserts how
the code behaves, it is not an observation of a run. `t077` validates its shape
only; `[t079]` tests it against pipeline plans.

`input_manifest_digest` / `output_manifest_digest` are named for what they hold
— a single digest over a canonical sorted per-file manifest. The manifest itself
is a sibling `*_manifest_ref` (the run's existing `manifest_path` / `resources`
are the natural target).

The two policy fields are distinct and both are needed:
`RunFingerprint.fingerprint_policy` is the version this record is **authored and
validated** under; `CaptureOrigin.capture_policy` is the version the **origin**
captured under. Recording the origin's version is what lets
`science-run-fingerprint/v2` tighten obligations without retroactively changing
the semantics of runs captured under `v1`.

### B. The obligation policy table — `science-run-fingerprint/v1`

Following the `belief_weights` / `_reconcile_evidence_vocab` precedent, the
**model owns the enums** and the **tool owns the obligation table**
(`science_tool/run_fingerprint_policy.py`), frozen and versioned like
`BeliefPolicy`'s `core-default/v1`.

```python
class Obligation(StrEnum):
    MUST_CAPTURED = "must-captured"
    MAY_ATTESTED  = "may-attested"
    MAY_UNKNOWN   = "may-unknown"
    NOT_APPLICABLE = "not-applicable"
```

Obligation is a pure function of **declared** `executor.kind` × declared
artifact locality. **Never** of what validate can observe on disk.

| component | `local` | `commons` | `external` |
|---|---|---|---|
| `code_sha` | MUST captured | MUST captured | MUST captured *(repo-owned ref)* |
| `code_dirty` | MUST captured | MUST captured | MAY unknown |
| `environment_digest` | MUST captured | MUST captured | MAY attested |
| `container_digest` | NOT APPLICABLE | MAY attested | MAY attested |
| `parameters_digest` | MUST captured | MUST captured | MAY attested |
| `input_manifest_digest` | *by `input_artifact_locality`* | ″ | ″ |
| `output_manifest_digest` | *by `output_artifact_locality`* | ″ | ″ |

Manifest-digest obligation, keyed on **its own** locality (inputs are commonly
external reference datasets while outputs are Science-managed — hence the split):

| locality | obligation |
|---|---|
| `science-managed` | MUST captured |
| `external` | MAY attested |

Validate **may** cross-check a captured digest against the manifest when one is
present, but the *obligation* never originates from a disk probe.

**Capture semantics by executor**, so `captured` always names an observer:

- **`local` captured** — the current project observed it.
- **`commons` captured** — the *producing* Science project captured it under its
  own `capture_policy`, and the consuming project imports a **verifiable**
  captured record. `capture_origin` is **required**. Validate verifies the value
  against the authored commons source record — by *reading* it, never by probing
  the local machine. It must never pretend the local project observed a commons
  fact.
- **`external` attested** — a non-Science executor or operator supplied it.

An **import-time reconciliation gate** asserts that, for every `ExecutorKind`,
the table's component names exactly equal the set of fields on `RunFingerprint`
annotated `FingerprintComponent` **or** `FingerprintComponent | None` (so
`container_digest` is covered). A field added without an obligation for every
executor fails at import. `NOT_APPLICABLE` ⇒ the field must be `None`; any other
obligation ⇒ it must be present.

### C. Resolution rule

A belief-eligible `empirical_data` line must satisfy **both** conditions:

1. **`dataset_usage` is non-empty.** This is the *existing* invariant, enforced
   as an ERROR by `check_belief_eligible_empirical_has_dataset_usage`
   (rule `evidence.empirical.requires_dataset_usage`,
   `validate/checks/evidence_lines.py:612`). **It is unchanged by `t077`.**
2. **At least one fingerprinted run is resolved**, where the resolved run set is

   ```
   resolved_runs(line) =
        ⋃ { resolved_empirical_runs(d) : d ∈ dependence_datasets_by_line(line) }
      ∪ run_refs(line)
   ```

`dependence_datasets_by_line` (`graph/dataset_independence.py:215`) is reused
**verbatim**, inheriting its `direct` / `virtual` paths and its exclusion of
`indirect-bears-on`. Both conditions are pure functions over authored source, so
validate is deterministic.

**`run_refs` are supplemental, never a standalone substitute.** The new field
`EvidenceLineEntity.run_refs: list[str]` (each validated to the `workflow-run:`
prefix, mirroring `DerivationBlock._wfrun_id`) *widens the resolved **run** set;
it never widens the **dataset** set and never waives condition 1.* A direct-only
`run_refs` line remains invalid, exactly as it is today.

This is a load-bearing choice, not a conservatism. Because condition 1 holds for
every belief-eligible empirical line, every such line necessarily passes through
`dependence_datasets_by_line` — the same function the dataset-QA ceiling uses
(`graph/dataset_qa.py:85`). Condition 2 is evaluated graph-phase and calls that
same function on the same materialized graphs (see §D). **Substrate parity is
therefore structural, not merely tested:** no line shape can reach run-resolution
while bypassing the QA ceiling. Allowing direct-only `run_refs` would have
created precisely that bypass.

`run_refs` is still consequential (it is not an inert field): it rescues a line
whose datasets carry sound dataset-level provenance but cannot themselves name a
fingerprinted run — e.g. a `produced_by`-only code-derived dataset, or a commons
dataset whose derivation is recipe-only but whose analysis this project actually
executed and registered.

Each dataset dispatches on the `derivation` discriminated union, contributing
zero or more runs to the union:

| derivation shape | contributes to `resolved_runs` | if it contributes nothing |
|---|---|---|
| `DerivationBlock` → `workflow_run` **with a fingerprint** | the run | — |
| `DerivationBlock` → `workflow_run` **without a fingerprint** | **nothing** | reason: `run-unfingerprinted` |
| `WorkflowRecipeDerivationBlock` (recipe only) | nothing | reason: `recipe-only` |
| commons dataset → fingerprinted `executor: commons` run | the run | — |
| `MemberOfDerivationBlock` | recurse to parent | reason inherited from parent |
| `derivation is None` **and** `produced_by` set | **nothing** | reason: `code-only-no-run` |
| `derivation is None`, no `produced_by` | nothing | reason: `no-provenance` |

**A run is not a fingerprinted run.** Naming a `workflow-run` satisfies nothing by
itself; the run must *bear a fingerprint*. This applies equally to a `run_refs`
entry. Enforcing it graph-phase requires the fingerprint to be **visible in the
graph**, so materialization emits `sci:fingerprintPolicy` on every workflow-run
node that carries one, and run-resolution admits only runs bearing that
predicate. Without this marker the invariant would fail open: a run entity with
no fingerprint block emits no `validate` finding (§D — fingerprint checks are
skipped when the block is absent), so an unfingerprinted run would silently
satisfy resolution.

**The whole resolution walk must be graph-visible.** Because resolution runs
graph-phase (§D), it sees RDF nodes, not `DatasetEntity` objects. Today
materialization emits only `sci:producedBy` from a dataset's code-only
`produced_by` (`graph/materialize.py:1183-1197`); the `derivation` union reaches
the graph **not at all**. Resolution therefore also requires materializing the
derivation itself — a `sci:derivationKind` discriminator plus `sci:workflowRun`
and `sci:memberOfParent` edges — so that every arm of the table above is
decidable from triples. Without them the resolver has dataset URIs and no way to
reach a run.

**Code is not a run, either.** `produced_by` is constrained by the model to
`code-file:<id>` references (`entities.py:479-481`); it names *source code*, not
an execution. A code-file ref carries no fingerprint — no environment digest, no
seed policy, no input/output hashes. It therefore contributes **no** run, for
exactly the reason a recipe contributes none. A dataset whose only provenance is
`produced_by` (`_derived_readiness` calls this `derived-via-code`) can be used by
an empirical line only if that line's `run_refs` names a fingerprinted run.

The same holds for a raw `origin: external` dataset, which by invariant carries
neither `derivation` nor `produced_by`: an empirical line depending *directly* on
raw input data resolves only via `run_refs` naming the analysis run. This is the
principal reason `run_refs` exists.

Findings are computed on the **line**, from the union — never per dataset. If
`resolved_runs(line)` is non-empty the line resolves, whatever individual
datasets contributed. If it is empty, the collected reasons pick the finding:

- any `recipe-only` reason → `evidence.empirical-run-recipe-only` (the most
  specific diagnosis, and the only reason with its own code);
- otherwise → `evidence.empirical-run-unresolved`, whose message names the
  collected reasons, distinguishing *a run was named but bears no fingerprint*
  (`run-unfingerprinted`) from *dataset provenance is code-only, not
  run-produced* (`code-only-no-run`) from *no dataset provenance at all*
  (`no-provenance`).

**Recipe is not a run.** `workflow_recipe` + `recipe_lockfile` is reproducible
*recipe provenance* — it says the computation *could* be re-run, not that a
specific execution happened with an observed fingerprint. It therefore never
satisfies an invariant that says empirical evidence resolves to a **run**, and it
earns a distinct finding rather than being silently lumped with "no provenance at
all." A `run_ref` naming a genuinely fingerprinted run may legitimately resolve
such a line — that is not a loophole, because the referenced run must itself
satisfy the full obligation table (a `local` run with a hand-authored `code_sha`
is a day-1 ERROR).

**Two helpers, not one.** A single `run_code_sha(dataset) -> str | None` would
smuggle the edge-level `member_of` exemption into evidence resolution:

- `own_derivation_run(dataset) -> WorkflowRunRef | None` — the dataset's *own*
  derivation edge. Returns `None` for `member_of`, because a membership edge is
  not run-produced.
- `resolved_empirical_runs(dataset) -> list[WorkflowRunRef]` — recurses through
  `member_of` to the parent chain. **This is what evidence validation uses**, so
  evidence resting on a member dataset resolves through its parent rather than
  terminating at `None`.

Consumers choose explicitly instead of inheriting a hidden exemption. The
`member_of` walk carries a `visited` set; a repeat is a hard error
(`dataset.member-of-cycle`), and the terminal rule is that the first
non-`member_of` ancestor decides.

### D. Validation surfaces and capture

The contract is enforced at **two layers**, because the information each needs
lives at a different layer.

`ValidateContext` (`validate/context.py:25-39`) carries only paths, the manifest,
and frontmatter/YAML caches — no RDF graph — while `dependence_datasets_by_line`
requires materialized `knowledge` / `provenance` graphs. A validate check *can*
reach them anyway by loading `knowledge/graph.trig` directly; `check_belief_authoring`
(`validate/checks/evidence_lines.py:429-432`) does exactly this. **But it silently
`return`s when the graph is absent.** Placing run-resolution there would inherit
that behavior: no `graph.trig`, invariant silently unenforced — the precise silent
fallback this contract forbids. Graph-phase placement is the only surface where
the `Dataset` exists by construction and the invariant cannot be skipped.

Re-deriving dataset resolution from frontmatter inside `validate` is the other
rejected option: it would duplicate the traversal and destroy substrate parity,
the property this design most wants to keep.

**Layer 1 — `validate` (frontmatter-local).** Fingerprint *well-formedness*
needs nothing but the workflow-run entity's own frontmatter, so it is an ordinary
check in `validate/checks/`. Condition 1 (`dataset_usage` non-empty) is the
existing check, untouched.

**Layer 2 — `graph/store/validation.py` (graph-phase).** Run *resolution* is a
traversal, so it becomes a row in `validate_graph_dataset` beside
`patch_membership_convenience` (`graph/store/validation.py:137`), which is the
established precedent for a structural invariant surfaced by both
`science validate` and `graph validate`. Its `pass` / `warn` / `fail` row status
maps directly onto the phased rollout.

| finding | layer | severity |
|---|---|---|
| `evidence.empirical-run-unresolved` | graph-phase | WARN → ERROR *(phased)* |
| `evidence.empirical-run-recipe-only` | graph-phase | WARN → ERROR *(phased)* |
| `dataset.member-of-cycle` | graph-phase | **ERROR always** |
| `run.fingerprint-incomplete` | validate | WARN → ERROR *(phased)* |
| `run.fingerprint-authored-capturable` | validate | **ERROR from day 1** |
| `run.fingerprint-origin-unverified` | validate | **ERROR from day 1** |

The three fingerprint findings are renamed from `evidence.*` to `run.*`: they are
properties of a **workflow-run entity**, not of an evidence line, and they fire
whether or not any evidence line references the run.

`dataset.member-of-cycle` is raised by `resolved_empirical_runs`' parent walk, so
it surfaces wherever resolution runs (graph-phase). The two `evidence.*` findings
are emitted by the graph-phase resolution row.

The phased findings can fire on **existing** projects (old missing structure), so
they start warn-only. The day-1 errors can only arise from **newly authored**
fingerprints — no legacy project can trip them — so they are hard errors
immediately. This is what honors *"an authored claim for a capturable field is a
validation failure, not a fallback."*

**Capture** attaches at `science dataset register-run` (`cli.py:7291`), which
already runs `preflight_register_run_identity`. It writes components with
`provenance: captured`:

| component | source |
|---|---|
| `code_sha` | `git rev-parse HEAD` |
| `code_dirty` | working-tree dirty check |
| `environment_digest` | `sha256` of the lockfile (`uv.lock`) |
| `parameters_digest` | `sha256` of the existing `config_snapshot` |
| `input_manifest_digest` | `sha256` of the canonical sorted input manifest |
| `output_manifest_digest` | ″ over declared outputs |

A hand-authored MUST-captured component is rejected at `register-run` **and** at
validate.

**No belief-local fallback.** Run-resolution joins the build gate that already
carries the convenience-edge invariant in `science validate` / `graph validate`,
so `graph build` surfaces the finding or fails early rather than letting belief
proceed on malformed empirical structure.

### E. Migration — `DerivationBlock.git_commit`

`git_commit` on `DerivationBlock` is a second, uncaptured copy of run identity
living on an authored derivation edge. Even documented as read-only it would sit
in source files and schemas where agents can fill it, stale it, or diff it
against the run. It is **removed**; the run's captured `code_sha` becomes the
sole run-code fact.

Investigation showed the removal is far cheaper than feared: **`DerivationBlock.git_commit`
has zero attribute readers.** The only `.git_commit` reads
(`project_package/verify.py:295-297`) belong to the *unrelated* `Provenance`
model (`packages/schema.py:65`), which genuinely captures and audits its commit
against `HEAD`. `plan_gate.py` and `graph/dataset_usage.py` consume the
`DerivationBlock` **type**, never this field, and need no migration.

Edits:

| file | change |
|---|---|
| `model/.../packages/schema.py:173` | drop `git_commit` field |
| `model/.../frontmatter.py:327` | drop the `raw.get("git_commit", "")` parse |
| `src/science_tool/datasets_register.py:208,253,771,798` | stop threading/emitting it |
| `model/.../schemas/science-pkg-entity-1.0.json:85,89` | drop from `required` + `properties` → **`1.1`** |
| `model/.../templates/dataset.md:41` | drop the commented field |
| `src/science_tool/commons/promote.py:2175,2184` | docstring only (it already drops it) |
| `~/d/science-commons` | sweep per `AGENTS.md` |

`member_of` derivations are explicitly exempt: they are classification/membership
edges, not run-produced derivations.

## Phasing

Each phase lands independently green.

1. **P1** — model + frozen policy table + reconciliation gate + capture in
   `register-run`. Behavior-neutral; no gate fires.
2. **P2** — the validate check: phased findings WARN, day-1 findings ERROR.
3. **P3** — `git_commit` removal, schema bump to `1.1`, commons sweep.
4. **P4** — flip the phased findings WARN → ERROR.

**P1 + P2 are the core contract** and form one implementation plan. **P3** is a
separable format migration (it is the only phase that touches the published
schema and `~/d/science-commons`), and **P4** is a one-line severity flip gated
on P2 having run warn-only against real projects. The implementation plan should
sequence them as such rather than as a single change.

## Testing

- **`FingerprintComponent` validator matrix** — tri-state × `attested_*`
  presence × `captured`/`attested_*` mutual exclusion; assert `""` is rejected
  in every position.
- **Policy-table reconciliation** — import-time gate; a `RunFingerprint`
  component field added without an obligation for every `ExecutorKind` fails.
- **Resolution table** — one test per row of the derivation-union table above,
  including `member_of` recursion to a resolving parent and a `member_of` cycle
  raising `dataset.member-of-cycle`.
- **Determinism (the load-bearing test)** — validate returns an **identical
  verdict with the run's data files present and absent**. This mechanically
  forbids a disk probe from ever creeping into the obligation logic.
- **Capture** — `register-run` writes `provenance: captured`; a hand-authored
  MUST-captured component is rejected at both `register-run` and validate.
- **Commons origin** — a `commons` captured component without a verifiable
  `capture_origin` raises `run.fingerprint-origin-unverified`; a
  verifiable one passes by *reading* the authored commons record.
- **Substrate parity** — run-resolution and the dataset-QA ceiling resolve the
  same dataset set for a given line (both go through `dependence_datasets_by_line`).
  Includes a **regression test that a `run_refs`-only line still fails**
  `evidence.empirical.requires_dataset_usage`, pinning the property that
  `run_refs` cannot open a bypass around the QA substrate.
- **Union semantics** — a line whose datasets contribute no run but whose
  `run_refs` names a fingerprinted one resolves; a line with an empty union and a
  recipe-only dataset reports `evidence.empirical-run-recipe-only` rather than
  the generic `evidence.empirical-run-unresolved`.
- **Code is not a run** — a `produced_by`-only (`derived-via-code`) dataset
  contributes no run; the line fails with `evidence.empirical-run-unresolved`
  carrying the `code-only-no-run` reason, and passes once `run_refs` names a
  fingerprinted run. Same for a line depending directly on a raw
  `origin: external` dataset (`no-provenance` reason).

## Consequences

- `empirical_data` acquires an enforceable meaning: *we ran it, and here is the
  fingerprint that lets you re-run it.*
- `""` becomes unrepresentable in run provenance; absence is explicit `unknown`.
- Run identity stops being denormalized onto datasets.
- Because `dataset_usage` remains mandatory, every belief-eligible empirical line
  passes through `dependence_datasets_by_line`. Run-resolution and the dataset-QA
  ceiling therefore **cannot** see different empirical substrate — parity is a
  structural property of the line shape, not a test we must remember to keep
  passing. `t077` adds **no** new bypass around the QA ceiling.
- `[t080]` inherits a resolved, fingerprinted run on which to hang a reproduction
  **verdict** and its belief ceiling — and, per the `[t080]` note, must still
  distinguish *not yet checked* (`unverified`) from *checked and failed*
  (`failed`).
