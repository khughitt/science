# H01 Engine Handoff Note — For the Next Session

> **Purpose:** seed a future session that picks up from the completed H01 simulator engine. Summarises what the project is, what has shipped, what is known-imperfect, and what alternative framings are worth considering before committing to `[t002]`.

## Where we are

- `meta/` is a Science-managed meta-project that applies the Science toolkit to itself (see `core/overview.md`, `core/decisions.md`).
- The first hypothesis, `H01` (`specs/hypotheses/h01-stochastic-revisiting.md`), claims that stochastic revisiting of down-weighted claims improves final recall of ground-truth-true propositions under noisy early evidence — with the advantage scaling in noise level, and the most discriminating disconfirmation route being a shared-latent-bias regime.
- `[t001]` — the simulator engine that will be used to test H01 — is complete as of 2026-04-24 (commit `e156605`). All 59 tests pass, all quality gates (ruff, pyright, pytest, validate.sh) are clean.
- `[t002]` — running the sweep, producing notebook figures, and writing the interpretation — has **not** been planned yet. It is intentionally deferred to a dedicated session informed by observed engine behaviour and by the open issues flagged below.

The engine is ready for scrutiny. It is not yet ready for a full sweep.

## Why this matters

The broader motivation: existing research-assistance tools (our own and others') risk falling into a hard-gating trap — once a claim drops below some support threshold, resources stop going to it, and the system cannot recover from early noisy signals. H01 formalises a candidate fix — stochastic revisiting — and the simulator provides the controlled environment in which to test it without confounding by human-workflow factors.

The domain-adjacent literature (`doc/background/topics/analytic-flexibility-and-replication.md`, `doc/background/topics/bayesian-methods-continuous-belief.md`, `doc/background/topics/structured-scientific-knowledge.md`) supplies the motivating premises: much of published science is fragile, analyst-dependent, and sensitive to where the gate sits. If the simulator shows that stochastic revisiting helps under plausible noise regimes, it strengthens the case for the tool's continuous-belief design principle (see `core/decisions.md` D-003). If it does not, H01's claim is bounded accordingly and the design should be revisited.

## Current engine state (what shipped)

| Module | Responsibility |
| --- | --- |
| `config.py` | `SimConfig`, `PolicyConfig`, `RunResult` with validation. Supports `prior_alpha`/`prior_beta`, three bias modes (`none`/`independent`/`shared`), configurable `bias_sigma`. |
| `model.py` | `Propositions`, `generate_propositions`, and `SignalModel`. Bias offsets are per-proposition; shared mode is a single Normal draw broadcast across the biased subset. |
| `policies.py` | `hard_gate_policy`, `constant_revisit_policy`, `thompson_policy`, and the `POLICIES` dispatch dict. |
| `metrics.py` | `recall` (threshold-parameterised), `brier`, bias-aware `regret` (uses per-proposition offsets). |
| `sweep.py` | `run_single`, `build_default_grid`, `run_sweep` (writes list-column parquet with allocations + final α/β arrays + ground truth), `benchmark_runtime` + `BenchmarkReport`. |
| `cli.py` | `h01-sim` Click entry point with `sweep` and `benchmark` subcommands. Benchmark gate raises `ClickException` when projection exceeds `--budget-seconds`. |

Deliverables still owed to `[t002]` (not engine gaps):
- `results/h01-simulator/sweep-<date>.parquet` produced by a real full-seed sweep.
- `notebooks/h01_simulator_results.py` populated with real figures (currently a stub).
- `doc/interpretations/h01-simulator-<date>.md` tying sweep findings back to H01 propositions P1-P5.

## Known issues from the final review

Three findings from the engine-wide review (ordered by materiality):

**1. Degenerate grid cell.** `build_default_grid` uses `budgets = [100, 400, 1600]`, unscaled relative to `n_propositions`. For `N=100, budget=100, warmup_actions=1`, the warmup consumes the entire budget and all four policy variants produce byte-identical allocations and metrics. This affects 12,000 of the 72,000 runs (~17 %). The spec explicitly says budgets should be "small/medium/large *relative to N*"; the implementation does not implement this. Either scale budgets (e.g. `[5n, 20n, 80n]`) or filter `budget > warmup_total` at grid-build time. The grid redesign likely also resolves the benchmark gate failure below.

**2. Regret oracle is misaligned with recall under `shared` bias.** The oracle in `metrics.regret` allocates the full budget to `argmax(effective_p)`. When `shared` bias pushes a `truth=0` proposition's effective probability above any `truth=1` proposition's (≈25–37 % probability at the two noisiest noise settings), the oracle targets a false proposition. A policy mimicking the oracle then has `regret=0` but `recall=0`. **This means `regret` and `recall` can be decorrelated in the `shared` regime at high noise** — precisely the regime where H01's most discriminating test lives. No code fix required, but: (a) the `regret` docstring should warn about this, and (b) the `[t002]` interpretation writeup needs an explicit note that regret is an unreliable corroborating signal in `shared` rows. If a corroborating metric is needed for recall, consider a recall-oracle (fraction of true-positives identifiable) rather than the signal-count oracle that `regret` currently implements.

**3. Benchmark gate fails at 100 seeds.** `h01-sim benchmark --seeds 100` projects ~988 s (exceeds the 600 s budget). The gate is working as designed — the spec requires that the engine fail loud rather than silently overrun. Additionally, `benchmark_runtime` samples the first 200 entries of the grid as its calibration slice, which under-represents high-N / high-budget configurations. The 988 s projection may therefore be an *under*-estimate. Before any real sweep, either:
- Redesign the grid (fixing issue 1 likely fixes this too),
- Sample calibration uniformly across the grid rather than from a prefix, or
- Parallelise `run_sweep` (e.g. `ProcessPoolExecutor`) — cheap to add since runs are embarrassingly parallel.

None of these are [t001] regressions — the plan's acceptance criteria are met. They are pre-work for [t002].

## Alternative explanations and framings to consider before [t002]

The rest of this document is the part the user asked to preserve: *before spending compute on a full sweep, what else should we consider?*

### Alternative explanations for any observed H01 effect

If the sweep shows stochastic revisiting outperforming hard-gating, the interpretation should not stop at "H01 confirmed." Plausible alternative mechanisms that would produce the same pattern:

- **Exploration of the prior-sampling distribution, not recovery from noise.** If a high `prior_alpha = prior_beta` (optimistic initialization) achieved similar results to stochastic revisiting, the effect is better explained as "uncertainty representation" than as "recovery from early mistakes." Test: run the sweep with `prior_alpha = prior_beta = 5.0` for `hard_gate` and compare its recall to `thompson` with `Beta(1, 1)` priors.
- **Artifact of the Beta-Bernoulli conjugate structure.** The effect might not generalise to continuous-reward signal models. A Gaussian-effect-size variant of the simulator would disambiguate. If the advantage holds there too, the claim is robust. If not, H01 is narrower than stated.
- **Budget-per-proposition effect, not noise effect.** The "noise" axis in our sweep covaries with effective information per sample. A regime where noise is high but total information is also high (e.g. larger budget) may not show the effect. Disentangling requires a sweep parameterised by `information_per_action = (p_pos − p_neg)²` held constant while varying budget.
- **Oracle artifact in regret.** The regret metric has the known misalignment described above. If observed "low regret" appears to corroborate "high recall," verify that the recall correlation holds across bias regimes, not only in `none`/`independent`.

### Alternative solutions worth having in the comparison set

Current policies: hard-gate, constant-revisit (two `r` values), Thompson. Worth considering before committing to the analysis:

- **UCB-style upper-confidence-bound.** A frequentist cousin of Thompson, potentially more stable under non-stationary bias. Cheap to add: one function.
- **Optimistic initialization.** A single parameter change (`prior_alpha = prior_beta = 5`) applied to each existing policy. Distinguishes "uncertainty in priors" from "stochastic-revisit mechanism" (see above).
- **Annealed revisit.** `revisit_prob` scheduled to decay with `action_idx`. Addresses the intuition that revisiting should be most aggressive early and taper off.
- **Restart policies.** After *K* consecutive low-reward observations on a gated proposition, fully reset its posterior to the prior. Models what a human analyst might do when the evidence feels stale.
- **Information-gain-directed sampling.** Allocate to the proposition with highest posterior variance regardless of mean. A purer "exploration" baseline against which Thompson's exploration+exploitation blend can be compared.

Including one or two of these as reference policies would significantly tighten the interpretation of any effect observed.

### Alternative framings of H01 itself

The current claim is "stochastic revisiting improves recall under noisy evidence, scaling monotonically with noise." Plausible re-framings that might fit the data better:

- **"The optimal revisit rate is a function of estimated per-proposition uncertainty, not a constant."** P5 of H01 already gestures at this, but the sweep grid only compares two constant `r` values to Thompson. A sweep over `r ∈ {0, 0.05, 0.1, 0.2, 0.3, 0.5}` would directly map the `r` → recall curve.
- **"In shared-bias regimes, the optimal revisit rate is *lower* than in independent-noise regimes."** This is a prediction the current simulator can directly test and would refine the scope of H01's disconfirmation route.
- **"The relevant continuous-belief metric is calibration, not recall."** If H01 supports recall but hurts Brier calibration, the design-principle claim in D-003 may need splitting. Run the analysis against Brier in addition to recall.

### Alternative simulator designs worth eventual investment (probably not [t002])

Not for the first sweep, but useful to record as candidates for later:

- **Gaussian effect-size model.** Real-valued evidence instead of binary, matching effect-size-based summaries in real literature. Tests whether H01 is an artifact of the binary abstraction.
- **Correlated truth structure.** Some propositions are implied by others. Evidence for A partially informs B. Closer to real research-evidence topology.
- **Time-varying bias.** Pipeline drift — the shared bias latent evolves over the run. Models real pipeline-change events.
- **Heterogeneous action costs.** Some evidence is cheap (literature lookup), some expensive (experiment). Changes the budget-allocation problem.
- **Multi-agent collaborative setting.** Multiple policies running against the same proposition set, sharing or not sharing observations. Connects to the long-range fork-and-share bet in `README.md`.

### Where this might *not* be the right problem

Worth interrogating explicitly: is H01 itself the right hypothesis to test first?

- If most real-world scientific error is shared-pipeline bias (the `question:01-bioinformatics-generalizability` angle), the stochastic-revisiting mechanism may help little in any regime. A hypothesis about *detecting* pipeline-level correlated error across claims might be a higher-value first test.
- The meta-project's design commitments (continuous beliefs, evidence-diversity weighting) are not equivalent claims. Testing only "stochastic revisiting helps" leaves diversity-weighting and calibration-auditing untested. A small rebalancing of priorities toward H02/H03 on evidence-diversity and calibration might be warranted before burning compute on H01.

Record rather than decide.

## Suggested next-session opening

A clean opening for the dedicated session that picks up from here:

1. Read this file + `doc/plans/2026-04-24-h01-simulator.md` (engine plan) + `specs/hypotheses/h01-stochastic-revisiting.md` (the hypothesis itself) + `specs/h01-simulator.md` (the spec).
2. Decide: fix the engine issues in place (option 2 from the end of this session) or defer them into [t002]'s plan (option 1).
3. Author `meta/doc/plans/<date>-h01-sweep-and-interpretation.md` covering the [t002] work, including the grid redesign, at least one reference policy from the alternatives list above, and the regret-interpretation caveat.
4. Re-run `h01-sim benchmark` after any grid change. Confirm it passes the 600-second gate before invoking `h01-sim sweep`.
5. Execute the full sweep, commit the dated parquet under `results/h01-simulator/`, and populate `notebooks/h01_simulator_results.py` with the planned figures.
6. Write the interpretation writeup, tying findings to each of H01's propositions P1–P5 individually and explicitly including the alternative-explanation checklist above.

## Loose ends not otherwise captured

- The `results/h01-simulator/` directory exists but contains only `.gitkeep`. The parquet file produced by `[t002]` should be committed explicitly.
- The marimo notebook at `notebooks/h01_simulator_results.py` is a stub. Its planned figures are listed in the spec.
- `core/decisions.md` D-004 blesses shipping packages from `meta/src/`; that decision can be cited unchanged by future work.
- `tasks/active.md` currently has `[t001]` marked `done` and `[t002]` marked `proposed` (blocked by t001). When `[t002]`'s plan lands, update t002's status to `in_progress`.
- Nothing in this document is load-bearing for future work beyond the existing repo state. If you disagree with a framing above, it is meant to be argued with.
