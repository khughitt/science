<!-- Task queue. Use /science:tasks to manage. -->

## [t001] Build H01 simulator engine (policies + metrics + sweep + CLI)
- type: implementation
- priority: P1
- status: done
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting, question:01-bioinformatics-generalizability]
- created: 2026-04-24

Implement the engine per `specs/h01-simulator.md`: Beta-Bernoulli signal model with configurable prior and three bias modes (none / independent / shared); three policies (hard-gate, constant-revisit, Thompson); recall / Brier / regret metrics; grid sweep producing a list-column parquet (allocations + final α, β arrays); Click CLI with a benchmark gate that validates runtime against the single-digit-minute budget. Quality gates: ruff check + format-check + pyright. Plan: `doc/plans/2026-04-24-h01-simulator.md`. Running the full sweep, populating notebook figures, and writing the interpretation are deliverables of [t002].

**COMPLETED 2026-04-24.** Engine shipped as `h01_simulator` package in `meta/src/`. Modules: config (with prior_alpha / prior_beta, bias_model ∈ {none, independent, shared}, bias_sigma), model (Propositions + SignalModel with configurable Beta prior), policies (hard_gate / constant_revisit / thompson), metrics (recall, brier, bias-aware regret). Sweep runner produces list-column parquet with allocations + final α/β arrays. CLI exposes `sweep` and `benchmark` subcommands. Benchmark projection: 981.6s for full grid at 100 seeds (72 000 runs; budget 600s — tighten grid or add parallelism in [t002] before running full sweep). Calibration sample: 200 runs in 2.73s. All quality gates pass (ruff, pyright, pytest 59/59, validate.sh). [t002] unblocked.

## [t001b] H01 engine follow-ups (grid, metrics, parallelism)
- type: implementation
- priority: P1
- status: done
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t001]
- created: 2026-04-24

Resolve the three engine issues flagged in `meta/doc/plans/2026-04-24-h01-engine-handoff.md`: (1) parameterise the default grid in dimensionless budget-multiples with degenerate-cell filtering; (2) rename `regret` to `signal_count_regret` and document its decorrelation from recall under shared bias at high noise (no companion metric added; a budget-aware recall oracle is deferred until interpretation needs it); (3) parallelise `run_sweep` via `ProcessPoolExecutor` with validated `workers >= 1`, sample `benchmark_runtime` calibration stratified by `(n_propositions, budget)`, and re-anchor `RUNTIME_BUDGET_SECONDS` to honest serial CPU. Plan: `meta/doc/plans/2026-04-24-h01-engine-followups.md`. Unblocks [t002].

## [t002] Run H01 sweep and publish interpretation
- type: analysis
- priority: P1
- status: proposed
- aspects: [hypothesis-testing, software-development]
- related: [hypothesis:h01-stochastic-revisiting, question:01-bioinformatics-generalizability]
- blocked_by: [t001b]
- created: 2026-04-24

Execute the engine from [t001] on the default grid and produce the deliverables `specs/h01-simulator.md` names as required: `results/h01-simulator/sweep-<date>.parquet` with full seed count; `notebooks/h01_simulator_results.py` populated with headline figures (recall-vs-noise per policy, reliability diagram, threshold-swept recall, `shared`-vs-`independent` bias comparison); `doc/interpretations/h01-simulator-<date>.md` tying sweep findings to each H01 proposition (P1-P5). Plan to be written after t001 closes, informed by observed engine behaviour.

## [t003] Decide hierarchical task ID convention for science-tool
- type: research
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
