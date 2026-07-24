# Autonomy Envelope (Autonomous Research, slice S1) — Design

> **Status:** design / spec, approved for planning. Slice S1 of the autonomous-research
> program. S1 ships **no autonomous agent**: it is the contract, verified by tests, that
> the first one will run inside. Downstream slices (S2 recurrence, S3 task eligibility,
> S4 telemetry→estimates, S5 harness, S6 multi-agent design→plan, S7 context management)
> all consume this contract and are out of scope here.

## Motivation

Science today is built for an interactive flow: a human drives a coding agent, sees every
write, and merges deliberately. Extending it to unattended agents changes the risk profile
in a way that is specific to a *research* toolkit. The failure mode of an unattended coding
agent is bad code, which tests catch. The failure mode of an unattended **research** agent
is **manufactured belief** — an agent that closes a question, lifts a confidence, or authors
an evidence line that nobody asked for, in a corpus whose entire value is that its assertions
are trustworthy.

That hazard is not hypothetical in this codebase. Three instruments were previously found
fabricating findings about entities that did not exist, which is why `InstrumentResult` and
its `unwired` state exist at all. An unattended agent has strictly more leverage to do the
same thing, with nobody watching, on a schedule.

S1 therefore establishes three things before any agent runs unattended:

1. **Who acted** — a durable, queryable run identity attached to every autonomous write.
2. **What they were permitted to touch** — an explicit write surface, per tier.
3. **A guard that cannot be satisfied by manufacturing belief** — and, critically, a guard
   whose scope is *derived* rather than hand-maintained, so it cannot silently drift.

## Grounding findings that shape the design

Much of the substrate already exists. These findings are what make S1 a *certification*
slice rather than a greenfield one.

- **"Who wrote this" already exists, uncertified.** `Entity.added_by` (`science/model/src/science_model/entities.py:362`)
  is a free-text `str | None` documented as "Discovery stamp: who/what surfaced this entity
  into the project". It materializes as a plain literal onto `sci:addedBy`
  (`science/src/science_tool/graph/materialize.py:984-985`). It has **no validation and two
  incompatible spellings already in flight**:
  - `commands/research-topic.md:53` instructs `added_by: "llm:<model>:research-topic"`.
  - `science/src/science_tool/explore_ideas.py:741` writes `f"explore-ideas:{model_id}:{candidate_id}"`.

  Two spellings of one fact is precisely the collapse the D5 arc exists to undo. S1
  canonicalizes rather than invents.

- **`added_by` already materializes to the provenance layer, not knowledge.** The write at
  `materialize.py:984` targets the `provenance` named graph; the layer split is real and
  established (`graph/io.py:129`, `graph/materialize.py:342,484`). Run records inherit this
  placement rather than proposing a new convention.

- **Provenance-that-must-not-affect-belief is an established contract.** `OriginRecord`
  (`entities.py:240-253`) is documented "Provenance metadata only; MUST NOT affect
  evidential weight." The envelope extends an existing doctrine, not a new one.

- **`RunFingerprint` is the wrong reuse.** `science/model/src/science_model/run_fingerprint.py`
  exists but is workflow-run scoped: `ExecutorKind` is `local | commons | external`
  (`run_fingerprint.py:61-64`), and the model carries seed policy and step seeds. It models
  *compute* executors and reproducibility of numeric runs. Folding agent sessions into it
  would be a category error and would corrupt a well-scoped model.

- **The belief scalar is opt-in and fails open.** `belief_scalar_enabled(project_root)`
  (`graph/belief_scalar.py:184-188`) reads an ACTIVE decision flag from `core/decisions.md`
  and, per its own docstring, "a missing project root or decisions file silently disables the
  feature (returns False)". **A gate defined over the scalar would silently no-op in every
  project that has not opted in.** The gate is therefore defined over `BeliefResult` — the
  ordinal magnitude plus support/dispute unit multiset produced by `aggregate_belief` /
  `collect_evidence_units` (`graph/belief.py`, as consumed by `graph/attention.py`) — which is
  always computed.

- **Guard integrity is reachable from the write surface.** Because belief machinery reads a
  flag from `core/decisions.md`, an autonomous run permitted to edit that file could disable
  its own guard. The file must be denied.

- **`graph.trig` has exactly one legitimate writer.** The kernel-closure work established
  that source is the only durable writer of `graph.trig`. Autonomous runs never write it.

- **Readiness resolution already exists.** `ReadinessResolver`
  (`science/src/science_tool/tasks_readiness.py`) resolves `blocked_by` refs through entity
  readiness with cycle guarding. S3 will build task eligibility on this; S1 only needs to
  not conflict with it.

- **`Task.type` is a retired field.** `graph/health_checks/legacy_task_type.py` actively
  reports tasks still carrying `type:`; the field migrated to `aspects:`. Any reintroduction
  of a task-type vocabulary is an S3 question and must first establish why the original was
  retired. S1 adds no task fields.

## Design

### 1. Tiers

Two tiers, and deliberately no third.

| Tier | May write |
|---|---|
| `report-only` | Only the run's own report path, plus its own run record (§2). |
| `belief-neutral` | Anything the path gate allows, provided no pre-existing entity's belief moves. |

`report-only` is not a speculative addition: it is the existing house pattern. Both
`science wander` and `science explore-ideas` are report-first with a separate `--apply`,
and the first sweeps this program will actually run (audit docs, audit skills) are
report-shaped.

**There is no "full" tier.** Changing belief is human work by definition. Reserving a
future tier for autonomous belief modification would undercut the guarantee before it
ships, and a tier that exists "for later" is a tier something will eventually be granted.

### 2. Run record

A source-loaded record at `runs/<date>-<agent>-<short-id>.md`, materialized **exclusively
into `graph/provenance`**. It never appears in `graph/knowledge`, and therefore never
becomes a belief bearer, a freshness subject, an attention candidate, or a member of an
`rdf:type` hub. This placement is load-bearing: at weekly and fortnightly cadences across
several projects, run records would otherwise become one of the largest node populations
in the graph and would skew exactly the attention rankings the curation program depends on
(`graph/attention.py` — `NEEDS_REVIEW_MULTIPLIER = 3.0`, `STALE_MULTIPLIER = 2.0`).

The record carries:

| Field | Meaning |
|---|---|
| `id` | Canonical run id; the referent of `added_by` and of the commit trailer. |
| `agent` | Agent **role** (`curation-sweep`), not the model. |
| `model` | Model that executed the run, as a recorded property. |
| `tier` | `report-only` \| `belief-neutral`. |
| `triggered_by` | Schedule or trigger ref. Optional until S2 defines the vocabulary; omitted, not blank, when absent. |
| `branch` | `auto/<run-id>`. |
| `started`, `ended` | Time window. |
| `budget` | Tokens / wall-clock consumed (S4 consumes this). |
| `disposition` | `clean` \| `quarantined` \| `unwired`. |

Identity is the **role** rather than the model so that queries survive model changes; the
model is recorded, not identifying.

The record deliberately does **not** index what it wrote. Both directions are already
derivable — run→entities by querying `sci:addedBy` in the provenance graph, run→commits by
`git log --grep`. A maintained `wrote:` list would be a second spelling of a derivable fact
and would drift.

### 3. Attribution

**Commits.** Unattended commits set the git author to `<role> <agent@science.local>` and
carry exactly one structured trailer:

```
Author: curation-sweep <agent@science.local>

    docs: refresh stale status lines in conventions/

    Science-Run: run:2026-07-24-curation-sweep-a3f1
```

No credit language, no model name, no emoji, no `Co-Authored-By`. The author field is the
field git already provides for "who wrote this", so `git log --author`, `git blame`, and
`git shortlog` segregate autonomous work with no tooling; the trailer supplies the epoch
link that makes `git blame` on a bad line lead to the run that produced it, and makes
epoch revert a single `git log --grep`.

**This does not weaken the standing no-AI-attribution rule; it redraws its axis.** The rule
exists to keep vendor credit boilerplate off human-driven work, and for interactive commits
it applies unconditionally and unchanged. An unattended commit is a different category: no
human was in the loop, so the mark is not credit but provenance, and it is load-bearing for
revert and audit. The distinguishing test is *was a human in the loop for this commit*, not
*did an LLM touch it* — the latter is always true and therefore discriminates nothing.

**Entities.** `added_by` becomes a validated ref into a run record, replacing free text.
Migration must absorb the two spellings identified above, and the `research-topic` command
doc and `explore_ideas.py` write path both move onto the canonical form. The migration's
true scope must be **measured** at implementation: the D5 corpus survey observed 31
`added_by` values (`docs/plans/2026-07-12-d5-implementation-plan.md:213`), but that count is
from that survey's corpus at that time and is not a current measurement of the projects in
scope.

### 4. The path gate

Coarse, readable, per-tier, evaluated over repository paths and — for entities — over
frontmatter field names.

The gate is **not project-overridable**. A project that needs a different autonomous write
surface is a design conversation, not a config key; an override is a hole that will be
widened under deadline pressure by the very agents the gate constrains.

The deny list is explicit and each entry carries its reason:

| Denied | Reason |
|---|---|
| `data/` | Payload boundary; autonomous runs never touch measurement payload. |
| `graph.trig` | Source is its only durable writer (kernel closure). |
| `science.yaml` | The schema-version pin is sole write authority. |
| `core/decisions.md` | **Guard integrity** — belief machinery reads its flags, so a run editing it could disable its own guard. |
| other runs' records | A run writes its own record and no other. |
| belief-bearing entity fields | Derived, not enumerated — see §5. |

### 5. The belief gate, and mutual certification

**The gate.** Per **pre-existing** entity, compare `BeliefResult` before the run against
`BeliefResult` after. New entities have no before-value, so a run filing a question or a
task passes; a run adding an evidence line that lifts an existing hypothesis does not.
Where `belief_scalar_enabled()` is true the scalar is compared additionally — never as the
definition, for the fail-open reason above.

If belief cannot be computed — the graph did not build, the instrument returned `unwired` —
the gate result is `unwired`, and **`unwired` blocks the merge**. A guard that cannot see
must not report clean.

**Mutual certification.** The two gates certify each other by reconciliation, in the same
shape as the kind-descriptor three-way gate. A perturbation test walks each field of each
kind, perturbs it, and observes whether `BeliefResult` moves:

> **The set of fields whose perturbation moves `BeliefResult` must equal the set of entity
> fields the path gate denies.**

Neither list is hand-maintained against drift. A new belief-bearing field added anywhere in
the model fails this test until the path gate accounts for it, and a path-gate entry that
no longer bears on belief fails it as over-broad. This is what makes the guard something
that can genuinely fail rather than something that asserts — the standing requirement for
any instrument in this codebase.

**Accepted risk.** If the perturbation test proves impractical over the real kind surface
(combinatorics, fields with no cheap perturbation, kinds whose belief depends on cross-entity
state), the guard degrades to a maintained deny-list plus a weaker drift alarm. This is
accepted as a first attempt and revisited if it does not hold; the fallback is strictly
worse but not unsafe, because the run-boundary belief comparison in §6 is independent of it.

### 6. Lifecycle and quarantine

```
run start   →  per-entity BeliefResult snapshot
run work    →  commits on auto/<run-id>, authored + trailered per §3
run end     →  recompute, diff against snapshot

  clean       →  eligible to merge
  moved       →  branch held intact, NOT merged;
                 `science feedback` item filed naming entity + delta
  unwired     →  blocked; belief was not computable
```

Nothing is discarded. A quarantined run keeps its branch and its work; a human triages it
with the exact entity and delta in hand. This matters because the first violations will
mostly be *design* discoveries — a sweep that legitimately needs to touch something the
gate forbids — and destroying the evidence would destroy the signal.

The same comparison is exposed as a `science validate` check, so the violation is catchable
by anyone, on any branch, independent of the run harness. The run boundary is where it is
*authoritative*; validate is where it is *available*.

The two differ in what they compare against, and this must be explicit. The run boundary has
a real snapshot taken at run start. Validate has none, so it compares against the branch's
merge-base with the integration branch, considering only commits whose author or
`Science-Run:` trailer marks them autonomous. When no merge-base is determinable — a detached
head, an orphan branch, a shallow clone — validate reports `unwired` rather than clean, for
the same reason the run-boundary gate does.

Escalation reuses the existing `science feedback` surface rather than inventing a second
channel — feedback already has a triage program behind it.

## Testing

1. **Perturbation reconciliation** (§5) — the load-bearing test. Fails on any drift between
   belief-bearing fields and the path gate's entity-field denials.
2. **Fail-closed on unwired** — a project with no computable belief yields `unwired`, and
   `unwired` blocks. Asserted directly, because this is the failure mode the design exists
   to prevent.
3. **Scalar-independence** — the gate detects a belief move in a project where
   `belief_scalar_enabled()` is false. Guards against the fail-open regression.
4. **Guard integrity** — a run attempting to write `core/decisions.md` is refused.
5. **Provenance-layer isolation** — after materializing a project with run records, no run
   triple appears in `graph/knowledge`, and run records are absent from attention candidates.
6. **`added_by` resolution** — a canonical `added_by` ref resolves through `refs-check`; a
   dangling one fails.
7. **Interactive commits unaffected** — no author rewrite and no trailer on human-driven
   commits.

## Open questions deferred to later slices

- What triggers a run, and how schedules emit tasks (S2).
- Whether task eligibility reintroduces a type vocabulary, and how it relates to the retired
  `Task.type` (S3).
- Budget caps, kill switch, and loop convergence criteria — the envelope defines the tier a
  loop runs in, not the loop (S5).
- Whether autonomous curation measurably improves project health. This is a research
  question about the toolkit, and `meta/` is its natural home.
