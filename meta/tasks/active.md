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
- status: done
- aspects: [hypothesis-testing, software-development]
- related: [hypothesis:h01-stochastic-revisiting, question:01-bioinformatics-generalizability]
- blocked_by: [t001b]
- created: 2026-04-24

Execute the engine from [t001] on the default grid and produce the deliverables `specs/h01-simulator.md` names as required: `results/h01-simulator/sweep-<date>.parquet` with full seed count; `notebooks/h01_simulator_results.py` populated with headline figures (recall-vs-noise per policy, reliability diagram, threshold-swept recall, `shared`-vs-`independent` bias comparison); `doc/interpretations/h01-simulator-<date>.md` tying sweep findings to each H01 proposition (P1-P5). Plan to be written after t001 closes, informed by observed engine behaviour.

**COMPLETED 2026-04-24.** Sweep ran with engine extensions: UCB policy added, optimistic-init `hard_gate(Beta(5,5))` variant added as a parallel grid entry, `constant_revisit` r-axis expanded to {0.05, 0.1, 0.2, 0.3}. `RUNTIME_BUDGET_SECONDS` re-anchored to 3180s for the larger grid (measured projection: 2967s avg, 3115s max across 5 runs). Output: `meta/results/h01-simulator/sweep-2026-04-24.parquet` (144,000 rows, 23 MB). Notebook: `meta/notebooks/h01_simulator_results.py` with six figures (recall-vs-noise, brier-vs-noise, reliability diagram, threshold-swept recall, shared-vs-independent delta, r-curve). Interpretation: `meta/doc/interpretations/h01-simulator-2026-04-24.md` — H01 broadly confirmed (every exploration-based policy strictly beats hard-gating; gap widens monotonically with noise), with the load-bearing mechanism refined to "uncertainty-guided exploration" rather than "stochastic revisiting per se" (UCB's deterministic variant outperforms Thompson). P5 not testable at the chosen r-axis upper bound; future work to extend r > 0.3.

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

## [t004] Extend H01 r-curve to resolve P5
- type: implementation
- priority: P2
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t002]
- created: 2026-04-24

`[t002]`'s sweep tested `constant_revisit` at `revisit_prob ∈ {0.05, 0.1, 0.2, 0.3}` and the r-curve was monotonically increasing through the upper bound — meaning P5 ("optimal r is a function of uncertainty, not a constant") could not be evaluated. Either the optimum lies above r=0.3 or there is no optimum within sensible bounds. Extend the axis to e.g. `{0.3, 0.4, 0.5, 0.7, 0.9}`, re-run a focused sweep (no need to repeat the existing rows — append new r values for the existing seeds), and update the interpretation with the resolved finding. Specifically: does the optimum vary with `bias_model` × `noise_level` (P5 supported) or land at a single r across all conditions (P5 disconfirmed in the simpler form)?

Lightweight enough to keep within the existing `RUNTIME_BUDGET_SECONDS = 3180s` budget if scoped only to the new r values; re-anchor the gate if the full grid is re-run. Deliverable: an updated interpretation section addressing P5 specifically, with a figure showing the full r-curve.

## [t005] Gaussian effect-size variant of H01 simulator
- type: implementation
- priority: P3
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting]
- blocked_by: [t002]
- created: 2026-04-24

The current H01 simulator emits binary Bernoulli signals — H01's recall finding is bounded to that abstraction. The handoff note (`meta/doc/plans/2026-04-24-h01-engine-handoff.md`) flagged "Beta-Bernoulli artifact" as a candidate alternative explanation that the Bernoulli sweep cannot rule out. Build a Gaussian-effect-size variant: signals drawn from `Normal(mu, sigma)` where `mu = mu_pos` for truth=1 and `mu_neg` for truth=0; conjugate posterior is normal-normal with running mean and variance; recall analog uses a posterior-mean threshold; calibration analog is MSE between posterior mean and truth-conditional effect size.

Tests whether the H01 finding generalises beyond binary signals. If it does, D-003's continuous-belief commitment has stronger empirical footing. If not, H01 is bounded to the Beta-Bernoulli regime and the design principle needs re-examination. Likely a substantial new package alongside `h01_simulator/` (or a parallel module within it) with its own sweep, notebook, and interpretation. Plan before implementation.
