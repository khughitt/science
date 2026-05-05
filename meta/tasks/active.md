<!-- Task queue. Use /science:tasks to manage. -->

## [t001] Build H01 simulator engine (policies + metrics + sweep + CLI)
- priority: P1
- status: done
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting, question:01-bioinformatics-generalizability]
- created: 2026-04-24

Implement the engine per `specs/h01-simulator.md`: Beta-Bernoulli signal model with configurable prior and three bias modes (none / independent / shared); three policies (hard-gate, constant-revisit, Thompson); recall / Brier / regret metrics; grid sweep producing a list-column parquet (allocations + final α, β arrays); Click CLI with a benchmark gate that validates runtime against the single-digit-minute budget. Quality gates: ruff check + format-check + pyright. Plan: `doc/plans/2026-04-24-h01-simulator.md`. Running the full sweep, populating notebook figures, and writing the interpretation are deliverables of [t002].

**COMPLETED 2026-04-24.** Engine shipped as `h01_simulator` package in `meta/src/`. Modules: config (with prior_alpha / prior_beta, bias_model ∈ {none, independent, shared}, bias_sigma), model (Propositions + SignalModel with configurable Beta prior), policies (hard_gate / constant_revisit / thompson), metrics (recall, brier, bias-aware regret). Sweep runner produces list-column parquet with allocations + final α/β arrays. CLI exposes `sweep` and `benchmark` subcommands. Benchmark projection: 981.6s for full grid at 100 seeds (72 000 runs; budget 600s — tighten grid or add parallelism in [t002] before running full sweep). Calibration sample: 200 runs in 2.73s. All quality gates pass (ruff, pyright, pytest 59/59, validate.sh). [t002] unblocked.

## [t001b] H01 engine follow-ups (grid, metrics, parallelism)
- priority: P1
- status: done
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t001]
- created: 2026-04-24

Resolve the three engine issues flagged in `meta/doc/plans/2026-04-24-h01-engine-handoff.md`: (1) parameterise the default grid in dimensionless budget-multiples with degenerate-cell filtering; (2) rename `regret` to `signal_count_regret` and document its decorrelation from recall under shared bias at high noise (no companion metric added; a budget-aware recall oracle is deferred until interpretation needs it); (3) parallelise `run_sweep` via `ProcessPoolExecutor` with validated `workers >= 1`, sample `benchmark_runtime` calibration stratified by `(n_propositions, budget)`, and re-anchor `RUNTIME_BUDGET_SECONDS` to honest serial CPU. Plan: `meta/doc/plans/2026-04-24-h01-engine-followups.md`. Unblocks [t002].

## [t002] Run H01 sweep and publish interpretation
- priority: P1
- status: done
- aspects: [hypothesis-testing, software-development]
- related: [hypothesis:h01-stochastic-revisiting, question:01-bioinformatics-generalizability]
- blocked_by: [t001b]
- created: 2026-04-24

Execute the engine from [t001] on the default grid and produce the deliverables `specs/h01-simulator.md` names as required: `results/h01-simulator/sweep-<date>.parquet` with full seed count; `notebooks/h01_simulator_results.py` populated with headline figures (recall-vs-noise per policy, reliability diagram, threshold-swept recall, `shared`-vs-`independent` bias comparison); `doc/interpretations/h01-simulator-<date>.md` tying sweep findings to each H01 proposition (P1-P5). Plan to be written after t001 closes, informed by observed engine behaviour.

**COMPLETED 2026-04-24.** Sweep ran with engine extensions: UCB policy added, optimistic-init `hard_gate(Beta(5,5))` variant added as a parallel grid entry, `constant_revisit` r-axis expanded to {0.05, 0.1, 0.2, 0.3}. `RUNTIME_BUDGET_SECONDS` re-anchored to 3180s for the larger grid (measured projection: 2967s avg, 3115s max across 5 runs). Output: `meta/results/h01-simulator/sweep-2026-04-24.parquet` (144,000 rows, 23 MB). Notebook: `meta/notebooks/h01_simulator_results.py` with six figures (recall-vs-noise, brier-vs-noise, reliability diagram, threshold-swept recall, shared-vs-independent delta, r-curve). Interpretation: `meta/doc/interpretations/h01-simulator-2026-04-24.md` — H01 broadly confirmed (every exploration-based policy strictly beats hard-gating; gap widens monotonically with noise), with the load-bearing mechanism refined to "uncertainty-guided exploration" rather than "stochastic revisiting per se" (UCB's deterministic variant outperforms Thompson). P5 not testable at the chosen r-axis upper bound; future work to extend r > 0.3.

## [t003] Decide hierarchical task ID convention for science-tool
- priority: P3
- status: proposed
- aspects: [software-development]
- related: []
- created: 2026-04-24

Decide a convention for hierarchical / derivative task identifiers in `/science:tasks` and either enforce it via tool validation or explicitly declare flat IDs and locate parent/child structure elsewhere. Surfaced when authoring `[t001b]` in this project — the ad-hoc `b` suffix worked but the design space wasn't actually considered.

Three distinct semantics share the identifier space today and probably shouldn't:
- **Versioning** — a revision of the same work (e.g. `[t001]` → `[t001v2]`).
- **Decomposition** — sub-work of a parent (e.g. `[t001.1]`, `[t001/01]`).
- **Fragment** — follow-up work that emerged after the parent closed but before the next major task starts (e.g. how `[t001b]` was used here).

**Questions to resolve before prescribing:**
- What is the goal? Each of the three semantics above implies a different scheme.
- Is the identifier even the right place for this structure? Alternatives: a `parent:` field, the existing `related:` / `blocked_by:` fields, an external tracker.
- What do existing Science projects already do? Survey at minimum `natural-systems`, `mm30`, `protein-landscape` before prescribing.

**Possible outputs:**
- A `/science:tasks` convention doc + a validation rule (e.g. a `science health` check that flags ID format deviations).
- OR an explicit decision that identifiers stay flat and structure goes elsewhere — and that decision recorded somewhere durable.

Tracked under meta because `science-tool/` is not a Science-managed project itself (no `science.yaml`, no `tasks/active.md`); design intent and decisions about tool behaviour are recorded in meta per `meta/AGENTS.md`.

## [t004] Extend H01 r-curve to resolve P5
- priority: P2
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t002]
- created: 2026-04-24

`[t002]`'s sweep tested `constant_revisit` at `revisit_prob ∈ {0.05, 0.1, 0.2, 0.3}` and the r-curve was monotonically increasing through the upper bound — meaning P5 ("optimal r is a function of uncertainty, not a constant") could not be evaluated. Either the optimum lies above r=0.3 or there is no optimum within sensible bounds. Extend the axis to e.g. `{0.3, 0.4, 0.5, 0.7, 0.9}`, re-run a focused sweep (no need to repeat the existing rows — append new r values for the existing seeds), and update the interpretation with the resolved finding. Specifically: does the optimum vary with `bias_model` × `noise_level` (P5 supported) or land at a single r across all conditions (P5 disconfirmed in the simpler form)?

Lightweight enough to keep within the existing `RUNTIME_BUDGET_SECONDS = 3180s` budget if scoped only to the new r values; re-anchor the gate if the full grid is re-run. Deliverable: an updated interpretation section addressing P5 specifically, with a figure showing the full r-curve.

## [t005] Gaussian effect-size variant of H01 simulator
- priority: P3
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t002]
- created: 2026-04-24

The current H01 simulator emits binary Bernoulli signals — H01's recall finding is bounded to that abstraction. The handoff note (`meta/doc/plans/2026-04-24-h01-engine-handoff.md`) flagged "Beta-Bernoulli artifact" as a candidate alternative explanation that the Bernoulli sweep cannot rule out. Build a Gaussian-effect-size variant: signals drawn from `Normal(mu, sigma)` where `mu = mu_pos` for truth=1 and `mu_neg` for truth=0; conjugate posterior is normal-normal with running mean and variance; recall analog uses a posterior-mean threshold; calibration analog is MSE between posterior mean and truth-conditional effect size.

Tests whether the H01 finding generalises beyond binary signals. If it does, D-003's continuous-belief commitment has stronger empirical footing. If not, H01 is bounded to the Beta-Bernoulli regime and the design principle needs re-examination. Likely a substantial new package alongside `h01_simulator/` (or a parallel module within it) with its own sweep, notebook, and interpretation. Plan before implementation.

## [t006] Fix `parse_tasks` blank-line-after-header silently dropping fields
- priority: P2
- status: proposed
- aspects: [software-development]
- related: []
- created: 2026-04-25

`science_tool.tasks._parse_task_block` (`science-tool/src/science_tool/tasks.py:33-77`) walks lines after the `## [tNNN] Title` header collecting `- key: value` field bullets, but breaks on the *first* blank line (lines 50–52). When a task is authored with a blank line between the header and the field list — a natural shape and one not rejected by `validate.sh` — every field is silently dropped, then `KeyError: 'created'` is raised at line 60, which crashes any caller that touches the file (`science-tool health`, `science-tool tasks list`, the `task` storage adapter, and the curation flows that load tasks). This was hit in `natural-systems` on 3 newly-authored tasks (t335, t336, t337) and required hand-patching the file before `science-tool health` would run.

Fix: skip leading blank lines between the header and the first `- key: value` line rather than terminating field collection. A defensive companion fix is to raise a clearer error than `KeyError: 'created'` if `created` truly is missing — it should at minimum name the offending task id and file.

Add a regression test in `science-tool/tests/test_tasks.py` covering both shapes (blank-after-header and contiguous), plus a "header but truly no fields" negative case to confirm the new error message.

Surfaced by: `natural-systems /science:health` 2026-04-25.

## [t007] Fix `_write_active` silently dropping `tasks/active.md` preamble
- priority: P2
- status: proposed
- aspects: [software-development]
- related: []
- created: 2026-04-25

`science_tool.tasks._write_active` writes `render_tasks(tasks) if tasks else ""` to `tasks/active.md`, which silently discards any text above the first `## [tNNN]` heading (the file preamble). The same bug affects every caller of `_write_active`: `add_task`, `complete_task`, `defer_task`, `retire_task`, and `edit_task`. A user who keeps a file-level note above the first task heading loses it on the next mutation.

The new `science_tool.tasks_archive` module (Plan #6, 2026-04-25) reads + re-emits the preamble correctly, but does not fix the underlying writer — Plan #6 was scoped tightly to its own surface. Apply the same preamble-preserving rewrite to `tasks.py`'s `_write_active` so all writers behave consistently.

Add regression tests in `science-tool/tests/test_tasks.py` covering each writer (`add_task`, `complete_task`, `defer_task`, `retire_task`, `edit_task`) round-tripping a file with a non-empty preamble. The `tasks_archive` test fixtures show the canonical preamble shape (text before `## [`).

Surfaced by: code-review pass on `docs/plans/2026-04-25-tasks-auto-archive.md` 2026-04-25 (master rollout follow-on action #3).

## [t008] Validator: warn on inline-dict synthesized_from items
- priority: P3
- status: proposed
- aspects: [software-development]
- related: []
- created: 2026-04-25

Per the 2026-04-25 synthesis-shape investigation Q2, the canonical form for `synthesized_from:` items in `type: synthesis` + `report_kind: synthesis-rollup` files is **block-list** (one field per line):

```yaml
synthesized_from:
  - hypothesis: "hypothesis:<slug>"
    file: "doc/reports/synthesis/<slug>.md"
    sha: "<SHA>"
```

The inline-dict form (`synthesized_from: [{hypothesis: "...", file: "...", sha: "..."}]`) is deprecated. Currently `meta/validate.sh` § 11a only checks for the presence of the `synthesized_from:` field, not item shape.

Extend the validator (both `meta/validate.sh` and `scripts/validate.sh` per the lockstep convention) to warn (not error) when `synthesized_from:` items are inline-dict shape on a `report_kind: synthesis-rollup` file. Use the warn severity (matches surrounding validator conventions per the master rollout plan).

Add a regression test in `science-tool/tests/test_validate_script.py` covering the inline-dict warn case + the block-list silent case + the absent-field skip case.

Surfaced by: `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md` Q2 resolution.

## [t009] Entity-rename / declarative-migrations primitive (Q5 follow-up)
- priority: P2
- status: proposed
- aspects: [software-development]
- related: []
- created: 2026-04-26

Land the long-term ideal articulated as Q5 in the 2026-04-25 synthesis-shape investigation: entity-id references become first-class citizens of the knowledge graph, and migrations become **declarative** rather than imperative. Concrete deliverables to scope when this lands:

- `science-tool entity rename <old-id> <new-id>` as a primitive that rewrites every reference graph-wide (not regex-driven; uses the actual reference index).
- A declarative migration shape: "transition entity instances of kind K from shape S₀ to shape S₁" — a registry-like description that the tool can plan, dry-run, and apply, rather than ad-hoc Python scripts.
- Composes WITH the managed-artifact system (per `docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md` — to be written): managed-artifact version bumps that need entity-shape changes ride into the same declarative migration channel. The managed-artifact system is one delivery surface; entity-rename / declarative migrations are the other.

**Why this is its own track:** The 2026-04-25 conventions audit's Bucket C (P1 #1, #3, #5, #8 — design-pass items) defines the abstract entity data model that this primitive needs. Bucket C must land first, or at least its load-bearing pieces (the multi-axis profile shape and the sanctioned entity-kind extension surface). Until that, entity-rename has no stable referent shape to operate over.

**Sequencing recommendation:**
1. Bucket C design session (P1 #1/#3/#5/#8 — separate cycle, with user).
2. Implement Bucket C decisions.
3. Implement managed-artifact long-term system (per the 2026-04-26 design spec).
4. Then this task: entity-rename primitive + declarative migration registry.

Phase 2 of `scripts/migrate_downstream_conventions.py` (shape-driven rules, landed `fe8d974`) is the first concrete step toward this; it should be cited as the prior art when planning the declarative migration shape.

Surfaced by: 2026-04-26 brainstorm of the managed-artifact long-term design (Q5 referenced from `docs/audits/downstream-project-conventions/synthesis-shape-investigation-2026-04-25.md` and `docs/plans/2026-04-25-rollout-and-migration-handoff.md` decision #6).

## [t010] Epistemic dependency graph — Phase 1 (taxonomy + bears_on + freshness)
- priority: P2
- status: done
- aspects: [software-development, framework-design]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-03
- completed: 2026-05-03

Implement Phase 1 of `docs/plans/2026-05-03-epistemic-dependency-graph-design.md`: explicit epistemic/operational/reference entity taxonomy on `EntityKind`, the `bears_on` relation kind with auto-derivation rules, and per-entity `EpistemicFreshness` state with a graph-build propagation step.

Companion to the typed-entity-blockers work (`feature/typed-entity-blockers` branch). The two land independently — typed-blockers covers forward operational dependencies ("why can't this task proceed?"), this covers backward epistemic dependencies ("when upstream X changes, what beliefs downstream need review?"). Together they make the project knowledge graph live rather than static.

Anchors in existing project decisions: D-003 (continuous beliefs in (0,1), never 0 or 1) and H01's validated stochastic-revisiting finding (`[t002]`). Phase 1 here is the structural surface those decisions need; Phase 2 (`[t011]`) is the behavioral payoff.

Plan to be written in implementation form (task-by-task) when this is picked up; the design sketch is the input. Quality gates: ruff + pyright + pytest + validate.sh; downstream projects unmodified.

## [t011] Epistemic dependency graph — Phase 2 (weighted sampling for attention)
- priority: P2
- status: deferred
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-03

Phase 2 of `docs/plans/2026-05-03-epistemic-dependency-graph-design.md`: replace deterministic top-N selection in `science:next-steps`, `science:curate`, `science:big-picture`, and task-prioritization sweeps with **weighted random sampling** over candidate epistemic entities. Weight function uses observable graph properties (incoming `bears_on` count, days-since-review, freshness state, evidence-imbalance skew) plus an `ε` floor so nothing collapses to zero — operationalizing D-003 at the attention layer.

This is the entity-graph-layer implementation of H01's validated mechanism: the H01 simulator (`[t002]`) showed exploration-based policies strictly beat hard-gating on noisy evidence, with UCB-style uncertainty-guided exploration outperforming pure Thompson sampling. Phase-2 weights should be proxies for uncertainty/contestedness, not noise — track that interpretation refinement.

**Crucial constraint:** weights are derived from observable graph state, not from LLM-estimated probabilities. The continuous-belief framing manifests as continuous *attention probability*, not as fake-precise posteriors stored on entities.

Originally blocked on `[t010]`; Phase 1 is now done, so this is unblocked but still deferred until we deliberately design the sampling policy and integration surface.

Surfaced by: 2026-05-03 design discussion on continuous-belief flow / hard-gate brittleness in pre-registration semantics.

## [t012] Pre-registration semantics recast (epistemic vs operational targets)
- priority: P2
- status: proposed
- aspects: [skills, framework-design]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-03

Update `science:pre-register` and `science:interpret-results` skills (and the project-level docs `docs/claim-and-evidence-model.md`, `docs/proposition-and-evidence-model.md`) to reflect the recast articulated in `docs/plans/2026-05-03-epistemic-dependency-graph-design.md` § Part 4: a pre-registration over an *operational* claim ("we will run pipeline P with params X before unblinding") stays binary and gating; a pre-reg over an *epistemic* claim ("if we observe Y we will treat hypothesis H as supported") becomes evidence input to H's standing rather than a verdict on H.

Zero schema change to pre-reg entities. Behavioral changes:
- `science:pre-register` prompts the user to identify whether the target is operational or epistemic, and frames the commitment language accordingly.
- `science:interpret-results` reads the pre-reg's commitment, evaluates the result against it, and emits a `bears_on` edge into the epistemic target — weighted by pre-reg commitment, not as a binary verdict.
- Skill prose explicitly drops "kill switch" framing for null results against epistemic targets.

Independent of `[t010]`/`[t011]`: can land before, during, or after the code changes since it touches only skills and prose. Do *not* land before downstream projects (myeloma, natural-systems) have a chance to surface objections — the recast changes how their existing pre-regs are interpreted.

Surfaced by: 2026-05-03 design discussion on continuous-belief flow.

## [t013] Phase 1 follow-ups: tighten freshness and registry surface
- priority: P3
- status: done
- aspects: [software-development]
- related: []
- created: 2026-05-03
- completed: 2026-05-04

Bundle of follow-ups surfaced by the final code review of `[t010]` (commit `d2c4fd2` on branch `feature/epistemic-dependency-graph`). Phase 1 is functionally complete — these are quality/forward-compat items that should land before `[t011]` Phase 2 builds on top.

1. **`review_state` validator** — `Entity.review_state` accepts the field on any kind today. Add a model-side validator that rejects `review_state` on a closed list of clearly-not-epistemic core kinds (`task`, `dataset`, `workflow-run`, `data-package`, `paper`, `experiment`). Avoids registry coupling at the science-model layer.
2. **`entity review` epistemic check** — `science-tool entity review dataset:foo` silently mutates frontmatter the freshness engine ignores. Reject non-epistemic targets at the CLI with the same message as the validator from #1.
3. **Profile/extension classification through `_classify_entities`** — `materialize.py:_classify_entities` builds a fresh `EntityRegistry.with_core_types()` per call, so profile- and extension-registered kinds always default OPERATIONAL. Thread the project's full registry (with profile/catalog/extension classifications) through `ProjectSources` so an extension that declared `entity_class=EPISTEMIC` actually classifies that way at materialize time.
4. **Audit gate on `propagate-freshness`** — `propagate_freshness_in_memory` skips the `audit_project_sources` failure check that `materialize_graph` enforces. In a project with broken refs (e.g. natural-systems today), the sweep silently produces a partial picture. Either share the gate or document the divergence.
5. **`bears_on` `target_kinds` reconciliation** — `profiles/core.py` declares targets `{hypothesis, question, proposition, observation, finding, interpretation, discussion, story, mechanism}` but the freshness engine treats `assumption`, `model`, `report`, `validation-report` as EPISTEMIC too. Either expand the relation declaration or document why the runtime classification is intentionally broader.
6. **Phase-2 prep triples** — emit `sci:lastReviewed` per epistemic entity (so phase-2 sampling can read it from the graph without re-parsing markdown) and `sci:bearsOnDepth` per closure-emitted triple (so phase-2 attention can weight directness without re-deriving depth). Both add ~3 lines and are zero-cost in Phase 1.
7. **Migration heads-up or opt-out** — first `graph build` on existing downstream projects (myeloma, natural-systems) will likely flag many entities as `needs-review` because `last_reviewed=None` everywhere. Document this in the design's Migration section, OR implement the `freshness.enabled: false` opt-out the design promised but Phase 1 didn't ship.
8. **Integration test gaps** — add tests for: extension EPISTEMIC kind through materialize_graph; provenance + closure end-to-end; `propagate_freshness_in_memory` and `materialize_graph` agree on the same project; `entity review` on non-epistemic target.
9. **`derive_freshness` boundary tests** — test `review_horizon_days=1` and `today == baseline + horizon` to lock the `>` vs `>=` boundary.

Each item is small (most are 1–3 hours of work). Bundle is P3 because Phase 1 is functionally complete and these are quality/forward-compat tightening rather than missing functionality.

Surfaced by: final code review of `feature/epistemic-dependency-graph` 2026-05-03.

## [t014] Epistemic freshness: content-hash upstream change detection
- priority: P3
- status: proposed
- aspects: [software-development, framework-design]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-05

Phase 1 freshness uses frontmatter `updated` / `created` dates as the upstream change marker. `docs/plans/2026-05-03-epistemic-dependency-graph-design.md` explicitly deferred content-hash-based change detection to a later phase. Add a graph/materialization path that can detect upstream content changes even when authors forget to bump `updated:`, without replacing the current date-based convention prematurely.

Scope to design first: which authored fields participate in the hash, whether hashes live in the graph only or in a sidecar manifest, how to avoid noise from formatting-only edits, and how this interacts with existing managed-artifact hash utilities.

Surfaced by: EDG design § Decisions, item 5.

## [t015] Cross-project freshness propagation
- priority: P3
- status: proposed
- aspects: [software-development, federation, framework-design]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-05

Extend epistemic freshness beyond a single project: a paper, dataset, workflow-run, observation, proposition, or other epistemic upstream added in a parent/child/sibling project should be able to mark downstream hypotheses, questions, propositions, inquiries, and interpretations as `needs-review` across project boundaries.

This is distinct from current federation graph assembly/status. The missing design pieces are cross-project entity address syntax, resolver source of truth (live child sweep vs. federated graph snapshot), stale-graph behavior, and audit semantics when a downstream project is not locally available.

Surfaced by: EDG design trajectory item 2.

## [t016] Derived qualitative standing for epistemic entities
- priority: P3
- status: deferred
- aspects: [software-development, framework-design, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t011]
- created: 2026-05-05

Explore replacing implicit binary verdict-state with an explicit qualitative ladder such as `dormant` / `contested` / `supported` / `well-supported`, derived from evidence edges, pre-registered interpretation outcomes, and freshness/attention signals.

Deliberately deferred until `[t011]` weighted sampling shows whether sampling-driven attention is sufficient or whether the data model needs a visible standing field. The implementation must stay qualitative and derived from observable graph state, not LLM-estimated probabilities.

Surfaced by: EDG design trajectory item 3.

## [t017] Needs-review resolution and conclusion-amendment workflow
- priority: P2
- status: proposed
- aspects: [framework-design, skills, software-development]
- related: [hypothesis:h01-stochastic-revisiting]
- created: 2026-05-05

Define the protocol for what happens after a reviewer inspects a `needs-review` epistemic entity and concludes the new upstream evidence changes its standing. Likely shape: author a new interpretation or finding, connect it with an `amends` / `supersedes` relation to the prior interpretation/finding, and then run `science-tool entity review <ref>` to record that the entity was reconsidered.

Deliverables should include a small design note, command/skill prose updates, and any graph-store support needed for first-class amendment/supersession semantics. Avoid making freshness itself mutate conclusions; freshness remains a flag that prompts review.

Surfaced by: EDG design trajectory item 4.

## [t018] Cross-project typed blockers
- priority: P3
- status: proposed
- aspects: [software-development, federation]
- related: []
- created: 2026-05-05

Extend typed task blockers from local entity refs to cross-project refs: a task in project A blocked by an entity in project B, including parent/child/sibling project shapes.

Open design questions: cross-project address syntax, resolver source (live entity-store sweep vs. federated graph snapshot), stale-graph behavior, audit semantics, and how `validate_blocker_refs` / `ReadinessResolver` grow a project-scope parameter without weakening the current strict local validation.

Surfaced by: typed-entity-blockers trajectory item 1.

## [t019] Auto-unblock sweep for ready blocked tasks
- priority: P3
- status: proposed
- aspects: [software-development, task-management]
- related: []
- created: 2026-05-05

Add a command that flips `status: blocked` to `status: active` for tasks whose typed blockers all report `ready`. Current behavior only nudges in display output (`all ready — run 'tasks unblock <id>'`), which was the right manual-first implementation.

Design before implementation: dry-run by default, explicit `--apply`, clear audit output, no action on unresolved/forced blockers, and a policy for preserving notes about why the task had been blocked. This should land only after the manual readiness workflow has proven stable enough to automate.

Surfaced by: typed-entity-blockers trajectory item 2.
