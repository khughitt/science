# Autonomy Envelope (Autonomous Research, slice S1) — Design

> **Status:** design / spec, revised after review. Slice S1 of the autonomous-research
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

1. **Who acted** — a durable, supervisor-attested run identity bound to an exact commit range.
2. **What they were permitted to touch** — an explicit, default-deny write surface, per tier.
3. **A guard that cannot be satisfied by manufacturing belief**, and whose authority lives
   outside the actor it constrains.

## Grounding findings that shape the design

Much of the substrate already exists. These findings are what make S1 a *hardening* slice
rather than a greenfield one.

- **`added_by` records a discovery mechanism, not an execution run.** `Entity.added_by`
  (`science/model/src/science_model/entities.py:362`) is documented "Discovery stamp: who/what
  surfaced this entity into the project", and `docs/user-guide/entities.md:722` describes these
  fields as recording "how an idea entered the project". A corpus survey finds `explore-ideas:…`
  values and at least one literal `user`. **It must not be narrowed to mean "the run that wrote
  this"** — doing so would force a choice between inventing false historical run records and
  invalidating truthful interactive provenance. S1 adds a separate field (§3) and leaves
  `added_by` semantics untouched.

- **`added_by` already materializes to the provenance layer, not knowledge.** The write at
  `graph/materialize.py:984-985` targets the `provenance` named graph; the layer split is
  established (`graph/io.py:129`, `graph/materialize.py:342,484`). Run records inherit this
  placement rather than proposing a new convention.

- **Provenance-that-must-not-affect-belief is an established contract.** `OriginRecord`
  (`entities.py:240-253`) is documented "Provenance metadata only; MUST NOT affect evidential
  weight." The envelope extends an existing doctrine, not a new one.

- **`RunFingerprint` is the wrong reuse.** `science/model/src/science_model/run_fingerprint.py`
  is workflow-run scoped: `ExecutorKind` is `local | commons | external` (`:61-64`), and the
  model carries seed policy and step seeds. It models *compute* executors and numeric
  reproducibility. Folding agent sessions into it would be a category error.

- **The belief basis is available in three named parts.** The gate in §5 compares them:
  - expanded target closure — `_evidence_targets_for_uri` (`graph/store/evidence_signals.py:192-195`);
    a hypothesis's closure includes its linked claims.
  - raw evidence-unit multiset — `collect_evidence_units(knowledge, provenance, targets)`
    (`graph/belief.py:123-131`), deduped by URI.
  - policy identity — the frozen `BeliefPolicy.policy_id` (`graph/belief_policy.py:36-40`,
    default `"core-default"` at `:99`); `bundle_belief.py:147` already treats
    `(policy_id, policy_version)` as an identity and raises `MixedBeliefPolicyError` across it.

- **The belief scalar is opt-in and silently absent when unconfigured.**
  `belief_scalar_enabled(project_root)` (`graph/belief_scalar.py:184-188`) reads an ACTIVE
  decision flag from `core/decisions.md` and returns `False` when the file or flag is missing.
  That is fail-closed *for the scalar feature*, but a **gate defined over the scalar would
  fail open** — silently passing in every project that has not opted in. The gate is therefore
  defined over the belief basis above, which is always computed. The scalar is compared
  additionally where enabled, never as the definition.

- **Guard integrity is reachable from the write surface.** Belief machinery reads flags from
  `core/decisions.md`, and dependency-resolution files determine which Science revision runs.
  Both must be outside the actor's authority (§4).

- **`graph.trig` has exactly one legitimate writer.** The kernel-closure work established that
  source is the only durable writer of `graph.trig`.

- **Report-first is an established pattern at the command layer.** `commands/wander.md:17`
  documents `--apply` as "consumed by this slash command; permits exactly one side [effect]",
  with a dedicated `## Phase 6: --apply`; `commands/explore-ideas.md` is structured the same
  way. Note the layer: `science wander`'s **CLI** has no `--apply` and always writes a walk
  report (`wander/cli.py:108-110`) — which is itself a clean instance of the `report-only`
  tier, not a counterexample to it.

- **Readiness resolution already exists.** `ReadinessResolver` (`tasks_readiness.py`) resolves
  `blocked_by` refs through entity readiness with cycle guarding. S3 builds task eligibility
  on this; S1 only needs to not conflict with it.

- **`Task.type` is a retired field.** `graph/health_checks/legacy_task_type.py` reports tasks
  still carrying `type:`; it migrated to `aspects:`. Any reintroduction of a task-type
  vocabulary is an S3 question. S1 adds no task fields.

## Design

### 0. The control plane sits outside the actor

The single most important structural property, from which several rules below follow: **the
supervisor — the process that launches an autonomous run — owns everything the guard depends
on.** The agent's write surface never includes its own audit metadata, its own commit range
binding, or the code that evaluates it.

Concretely:

- The **run record** is created and finalized by the supervisor; `tier` and `disposition` are
  supervisor-attested, never self-declared (§2).
- The **commit range** `base_commit..head_commit` is recorded by the supervisor and is the
  authoritative binding. Author identity and the `Science-Run:` trailer are conveniences for
  `git blame`, not evidence — a process that can write commits can forge both (§3).
- The **authoritative gate executes from a supervisor-owned, pinned Science installation**,
  treating the run's worktree strictly as input. A run that edits toolkit code therefore
  cannot alter the code that judges it (§4).

### 1. Tiers

| Tier | May write |
|---|---|
| `report-only` | Only the run's own report path. |
| `belief-neutral` | What the path gate allows (§4), provided the belief basis does not change (§5). |

Neither tier writes run records, commit metadata, or gate policy — those are supervisor-owned
per §0.

`report-only` is not speculative: it is the existing house pattern at the command layer
(`wander`, `explore-ideas`), and `science wander`'s CLI already behaves exactly this way.

**There is no "full" tier.** Changing belief is human work by definition. A tier reserved
"for later" is a tier something will eventually be granted.

### 2. Run record

A supervisor-written record at `runs/<date>-<agent>-<short-id>.md`, loaded as a project source
and materialized **exclusively into `graph/provenance`**. It never appears in `graph/knowledge`,
and therefore never becomes a belief bearer, freshness subject, attention candidate, or
`rdf:type` hub member. That placement is load-bearing: at weekly and fortnightly cadences
across several projects, run records would otherwise become one of the largest node
populations in the graph and would skew the very attention rankings the curation program
depends on (`graph/attention.py` — `NEEDS_REVIEW_MULTIPLIER = 3.0`, `STALE_MULTIPLIER = 2.0`).

| Field | Meaning | Written by |
|---|---|---|
| `id` | Canonical run id; referent of `autonomous_run` and the commit trailer. | supervisor |
| `agent` | Agent **role** (`curation-sweep`), not the model. | supervisor |
| `model` | Model that executed the run. | supervisor |
| `tier` | `report-only` \| `belief-neutral`. **Attested, not self-declared.** | supervisor |
| `triggered_by` | Schedule or trigger ref. Optional until S2; omitted, not blank, when absent. | supervisor |
| `branch` | `auto/<run-id>`. | supervisor |
| `base_commit` | Exact commit the run started from. **The validation baseline.** | supervisor |
| `head_commit` | Exact commit the run ended at. | supervisor |
| `toolkit_revision` | Science revision the gate ran from. | supervisor |
| `policy_identity` | `(policy_id, policy_version)` in force. | supervisor |
| `basis_digest` | Digest of the belief basis at `base_commit`. Omitted exactly when `disposition` is `unwired`. | supervisor |
| `started`, `ended` | Time window. | supervisor |
| `budget` | Tokens / wall-clock consumed (S4 consumes this). | supervisor |
| `disposition` | `clean` \| `quarantined` \| `unwired`. **Attested, not self-declared.** | supervisor |

`base_commit`, `toolkit_revision`, `policy_identity`, and `basis_digest` exist so validation is
reproducible later. A merge-base is not a usable baseline: it moves under rebase and under
integration-branch advancement, and mixed human/autonomous history cannot be reliably
reconstructed by filtering commits.

**`basis_digest` and `unwired` are mutually exclusive.** `unwired` means the basis was not
computable, so requiring a digest there would force the supervisor to write a value it did
not compute — a fabricated field inside an attestation, which is the failure this whole
slice exists to prevent. The rule is conditional in *both* directions and is therefore
stricter than a plain optional: the digest is required when `disposition` is `clean` or
`quarantined`, and required to be **absent** when it is `unwired`. Plan D's writer must not
substitute a sentinel, a zero digest, or the digest of an empty basis.

**`autonomous_run` is forbidden on commons-canonical entities.** A run is project-local by
construction — it names one repository's branch, one `base_commit..head_commit` range, and
one toolkit revision. A commons record carrying the field would resolve against a `runs/`
directory no consuming project owns, so every consumer's graph build would fail over a
reference only the commons author can fix. The commons adapter rejects the field when it
builds the record, which is the path both `science commons validate` and every consumer's
commons scan take, so the failure lands on the commons author at authoring time.

The record deliberately does **not** index the entities it wrote. Each entity's *current*
writer is derivable by querying `autonomous_run` in the provenance graph, and full
history is derivable from the run's own `base_commit..head_commit` range — which is the
authoritative binding in any case (§0). A maintained list would be a second spelling that
drifts.

### 3. Attribution

**Commits.** Unattended commits set the git author to `<role> <agent@science.local>` and carry
one structured trailer:

```
Author: curation-sweep <agent@science.local>

    docs: refresh stale status lines in conventions/

    Science-Run: run:2026-07-24-curation-sweep-a3f1
```

No credit language, no model name, no emoji, no `Co-Authored-By`. The author field is git's own
field for "who wrote this", so `git log --author`, `git blame`, and `git shortlog` segregate
autonomous work with no extra tooling.

**These marks are not the security boundary.** A process that writes commits can set any author
and any trailer, so neither is evidence of anything. The authoritative binding is the
supervisor-recorded `base_commit..head_commit` range (§2); the supervisor verifies the marks
against that range at run end and quarantines on mismatch. The marks exist for human legibility.

**This does not weaken the standing no-AI-attribution rule; it redraws its axis.** The rule
keeps vendor credit boilerplate off human-driven work, and for interactive commits it applies
unconditionally and unchanged. An unattended commit is a different category: no human was in
the loop, so the mark is provenance, not credit. The distinguishing test is *was a human in the
loop for this commit* — not *did an LLM touch it*, which is always true and discriminates nothing.

**Entities.** A new field `autonomous_run` carries a validated reference to a run
record, materialized into `graph/provenance` alongside `added_by`. `added_by`
**keeps its existing discovery semantics unchanged** — it answers "how did this
idea enter the project", which is a different question from "which execution
wrote this file", and the corpus already contains values (`user`) that no run
record could ever explain.

> **Revised during implementation (Plan B).** This field was originally specified
> as `run_ref`. That name was already taken by `EvidenceLineEntity.run_refs`, which
> names fingerprinted workflow runs, materializes to `sci:runRef` in
> `graph/knowledge`, and **bears on belief** through `graph/store/validation.py`. A
> provenance field spelled `run_ref` beside a belief-bearing field spelled
> `run_refs` is a one-character path across the belief boundary. The predicate is
> `sci:autonomousRun` and the node type `sci:AutonomousRun` for the same reason;
> the persisted model is `AutonomousRunRecord`, since `qa_audit/runs.py` already
> owns `RunRecord`. The `run:` id prefix is unused and is kept as designed.

> **Not yet an attested binding (Plan B ships the field only).** Materialization checks
> that the run a value names *exists*; it does not check that this run wrote this file. An
> actor can therefore still attribute its work to an unrelated prior run. Plan D must close
> this by having the supervisor stamp `autonomous_run` itself, or by verifying every value
> it finds against the run's own recorded `base_commit..head_commit` range. Until then the
> field is a convenience for humans reading the corpus, and the commit range remains the
> only authoritative binding (§0).

Canonicalizing `added_by`'s discovery vocabulary — it currently has two spellings in flight,
`llm:<model>:research-topic` (`commands/research-topic.md:53`) and
`explore-ideas:<model>:<candidate>` (`explore_ideas.py:741`) — is a real problem but a separate
one. It is **deferred out of S1**; attempting it here is what produced the semantic narrowing
this revision removes.

### 4. The path gate — default-deny

Evaluated by the supervisor over repository paths and, for entities, over per-kind field names.
The gate is **not project-overridable**: a project needing a different autonomous write surface
is a design conversation, not a config key, and an override is a hole that will be widened under
pressure by the very agents it constrains.

**Pre-existing entities — default-deny.** Only fields on an explicit **per-kind allowlist of
fields known to be belief-neutral** may be written. Every unknown field, and every newly
introduced field, is denied automatically with no action required. Overbreadth — denying a field
that turns out to be harmless — is an accepted and visible cost.

**New entity creation — its own policy.** Which kinds an autonomous run may create, and which
fields it may set at creation, is a separate allowlist. Creation is not merely "editing a file
with no before-value"; a created entity can change another entity's belief basis, and §5 catches
that independently.

**Non-entity paths.** Denied, with reasons:

| Denied | Reason |
|---|---|
| `data/` | Payload boundary; autonomous runs never touch measurement payload. |
| `graph.trig` | Source is its only durable writer (kernel closure). |
| `science.yaml` | The schema-version pin is sole write authority. |
| `core/decisions.md` | Guard integrity — belief machinery reads its flags. |
| `runs/` | Supervisor-owned (§0). |
| `pyproject.toml`, `uv.lock`, and other dependency-resolution files | Toolchain selection; high blast radius, and out of scope for curation sweeps. |

The dependency-file denial is **defense in depth, not the primary control**. The primary control
is §0: the gate runs from a supervisor-owned pinned installation, so worktree toolchain edits
cannot reach the code that judges the run. Without that property, denying these files would be
load-bearing and still incomplete.

> **Revised during implementation (Plan C).** Four rulings the design did not settle:
>
> 1. **The seed allowlist is `paper` / `book` / `talk` bibliographic fields only** —
>    `venue`, `pmid`, `publisher`, `isbn`, `duration_minutes` (which materialize no
>    triple at all) plus `year` and `url` on `paper`/`book` (which materialize to
>    `dcterms:date` and `dcat:downloadURL` in `graph/knowledge`, and are read by no
>    evidence unit and no target closure). Every entry is covered by a Layer 3 case,
>    enforced by a ratchet test that fails when an entry has none.
> 2. **`aliases` is denied.** It feeds reference resolution (`graph/sources.py:787-793`),
>    so an alias can re-point a reference and move the target closure. `doi` is denied
>    too, as identity-adjacent — accepted overbreadth per §4.
> 3. **`task` fields cannot be gated at all.** `task` has no markdown home
>    (`CORE_PROFILE`: `home=None`), so it has no frontmatter file for a path-and-field
>    gate to decide over. Extending the gate to structured sources is a separate design
>    conversation.
> 4. **Entity kind is derived from the path, never from the file's own `kind:`
>    frontmatter**, and renames are extracted as deletion-plus-addition (`--no-renames`).
>    An actor that could choose its own kind could choose its own allowlist; a
>    similarity-scored rename would hide the addition half.

### 5. Layered enforcement

The earlier draft of this section claimed the path gate and a perturbation test could *mutually
certify* each other. **That claim is withdrawn.** Perturbation cannot prove completeness:
whether a field bears on belief depends on its value, its entity kind, sibling fields, and
cross-entity topology, so a single mutation can observe "no movement" and misclassify a
genuinely belief-bearing field as safe — silently, with the reconciliation test green.
Structural derivation is not currently available either, because source→graph→belief
dependencies are procedural and context-sensitive; attempting it now would create another
incomplete registry and relocate the drift problem rather than solve it.

Enforcement is therefore layered, with each layer sound on its own terms:

**Layer 1 — default-deny path gate (§4).** Syntactic, cheap, and complete by construction:
anything not explicitly allowed is denied. Its failure mode is over-restriction.

**Layer 2 — authoritative semantic gate.** Compare the **canonical belief basis** before and
after the run, per pre-existing entity:

- the expanded target closure (`_evidence_targets_for_uri`),
- the raw evidence-unit multiset (`collect_evidence_units`),
- the policy identity (`policy_id`, `policy_version`).

**Any difference quarantines the run** — not merely a difference in the final ordinal magnitude.
Comparing only the magnitude would pass a run whose evidence units changed but happened to
cancel, or one that swapped policy identity underneath an unchanged headline. This layer is
authoritative: it does not depend on the field allowlist being correct, which is exactly why it
catches what Layer 1 misses.

Where `belief_scalar_enabled()` is true the scalar is compared additionally, never as the
definition. If the basis cannot be computed — the graph did not build, an instrument returned
`unwired` — the result is `unwired`, and **`unwired` blocks the merge**. A guard that cannot see
must not report clean.

**Layer 3 — one-way perturbation alarm.** Perturb every **allowed** field across representative
contexts. If a perturbation changes the belief basis, the test **fails** and the field must come
off the allowlist. The inverse is deliberately **not** asserted: observing no change never makes
a field writable, and an apparently neutral denied field is acceptable overbreadth. This
asymmetry is what makes the alarm sound despite perturbation's incompleteness — false negatives
can only ever leave a field denied.

**Layer 4 — explicit promotion.** Adding a field to an allowlist requires human review of its
materialization path and belief dependencies, plus targeted tests. **Mutation results alone
cannot authorize a promotion.** This is the rule that keeps Layer 3 from quietly becoming the
certification mechanism it cannot be.

### 6. Lifecycle and quarantine

```
run start   →  supervisor records base_commit, toolkit_revision,
               policy_identity, basis_digest
run work    →  commits on auto/<run-id>
run end     →  supervisor records head_commit; recomputes basis
               from the pinned install; verifies commit marks

  clean       →  eligible to merge
  moved       →  branch held intact, NOT merged;
                 `science feedback` item filed naming entity + delta
  unwired     →  blocked; basis was not computable
```

Nothing is discarded. A quarantined run keeps its branch and its work, and a human triages with
the exact entity and delta in hand. This matters because the first violations will mostly be
*design* discoveries — a sweep that legitimately needs something the gate forbids — and
destroying the evidence destroys the signal.

The same comparison is exposed as a `science validate` check, so violations are catchable by
anyone, independent of the run harness. **It validates the exact recorded transition**
`base_commit → head_commit` read from the run record — not a merge-base, which moves under
rebase and integration-branch advancement. When there is no run record for the autonomous
commits under inspection, or the recorded commits are unreachable, validate reports `unwired`
rather than clean.

Escalation reuses the existing `science feedback` surface rather than inventing a second
channel; feedback already has a triage program behind it.

## Testing

1. **Semantic gate detects a basis change with unchanged magnitude** — the Layer 2 test that
   distinguishes this design from a magnitude comparison. Evidence units change and cancel;
   the gate must still quarantine.
2. **Fail-closed on unwired** — a project with no computable basis yields `unwired`, and
   `unwired` blocks.
3. **Scalar-independence** — the gate detects a basis change where `belief_scalar_enabled()`
   is false. Guards the fail-open regression.
4. **Default-deny** — a field absent from every allowlist is denied, with no registration
   required and no test edit.
5. **One-way alarm asymmetry** — an allowed field whose perturbation moves the basis fails the
   suite; a denied field whose perturbation moves nothing does **not** become allowed.
6. **Self-attestation is impossible** — a run writing its own run record, or forging an author
   or trailer outside its recorded commit range, is quarantined.
7. **Gate independence from the worktree** — a run that edits toolkit code or dependency files
   does not change the judgment rendered on it.
8. **Baseline reproducibility** — validation against a recorded `base_commit` yields the same
   verdict after the integration branch advances and after a rebase.
9. **Provenance-layer isolation** — no run triple appears in `graph/knowledge`, and run records
   are absent from attention candidates.
10. **`autonomous_run` resolution** — a canonical `autonomous_run` resolves through `refs check`;
    a dangling one fails. `added_by` values such as `user` remain valid and untouched.
11. **Interactive commits unaffected** — no author rewrite and no trailer on human-driven commits.

## Open questions deferred to later slices

- What triggers a run, and how schedules emit tasks (S2).
- Whether task eligibility reintroduces a type vocabulary, and how it relates to the retired
  `Task.type` (S3).
- Budget caps, kill switch, and loop convergence criteria — the envelope defines the tier a loop
  runs in, not the loop (S5).
- Canonicalizing the `added_by` discovery vocabulary (§3) — real, but separable from autonomy.
- Whether autonomous curation measurably improves project health. This is a research question
  about the toolkit, and `meta/` is its natural home.
