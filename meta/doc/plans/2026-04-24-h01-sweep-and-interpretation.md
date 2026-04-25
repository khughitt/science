# H01 Sweep & Interpretation Implementation Plan (t002)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the H01 simulator engine on an expanded sweep grid that addresses the alternative-explanations the handoff note flagged, produce six headline figures, and write an interpretation tying findings to each H01 proposition (P1-P5) individually. The output is the empirical answer to whether stochastic revisiting beats hard-gating under noisy evidence — and under what conditions.

**Architecture:** Three engine extensions that ship with the default grid (UCB policy; optimistic-init priors as additional `hard_gate` entries; expanded `constant_revisit` r-axis), the runtime gate re-anchored to the new grid shape, then the analysis pipeline (sweep → marimo figures → interpretation writeup). The engine extensions are *permanent* additions to the default grid because they represent the level of detail every future H0x sweep will want; they are not `[t002]`-specific overrides.

**Tech Stack:** Existing — numpy, polars, click, pytest, marimo, altair. No new runtime deps. Uses the parallel `run_sweep` from `[t001b]` (`--workers`).

**Why these specific extensions, and not others:**
- **UCB** disentangles "any uncertainty representation helps" from "stochastic revisit mechanism specifically helps." Without it, a Thompson-vs-hard_gate gap could be attributed to either.
- **Optimistic-init** (`hard_gate` with `Beta(5,5)` prior) disentangles "uncertainty in priors helps" from "uncertainty in posteriors helps." Without it, an apparent Thompson advantage could really be a prior-shape effect.
- **Expanded r-axis** (`revisit_prob ∈ {0.05, 0.1, 0.2, 0.3}`, up from `{0.1, 0.3}`) maps the r → recall curve, addressing the handoff note's reframing that "optimal revisit rate is a function of uncertainty, not a constant."
- **Brier as headline metric** (already computed; just promoted to figure status) gives a calibration lens that is *not* compromised by the `signal_count_regret` shared-bias caveat. Independent corroboration of the recall finding.

**Out of scope:**
- Annealed revisit, restart, info-gain policies (handoff alternatives, deferred to future work).
- Gaussian effect-size variant of the simulator.
- A budget-aware recall oracle (deferred from `[t001b]`; revisit only if interpretation needs it).
- Detectability hypothesis (a successor question, not part of `[t002]`).

**Context docs:**
- Engine plan (completed): `meta/doc/plans/2026-04-24-h01-simulator.md`
- Engine follow-ups (completed): `meta/doc/plans/2026-04-24-h01-engine-followups.md`
- Handoff note (alternatives, framings): `meta/doc/plans/2026-04-24-h01-engine-handoff.md`
- Spec: `meta/specs/h01-simulator.md`
- Hypothesis: `meta/specs/hypotheses/h01-stochastic-revisiting.md`

---

## File Structure

**Modify:**
- `meta/src/h01_simulator/policies.py` — add `ucb_policy` and register in `POLICIES`.
- `meta/src/h01_simulator/config.py` — add `ucb_c: float = 1.0` to `PolicyConfig` with validation.
- `meta/src/h01_simulator/sweep.py` — restructure `build_default_grid` to support per-policy prior overrides; add UCB and optimistic-init entries; expand `constant_revisit` r-axis.
- `meta/src/h01_simulator/cli.py` — re-anchor `RUNTIME_BUDGET_SECONDS` for the larger grid.
- `meta/notebooks/h01_simulator_results.py` — populate the marimo notebook with six figures.
- `meta/tests/test_policies.py` — UCB selection tests.
- `meta/tests/test_config.py` — UCB-config validation tests.
- `meta/tests/test_sweep.py` — grid-shape assertions for new entries and the expanded r-axis.
- `meta/tasks/active.md` — close `[t002]` on completion.

**Create:**
- `meta/doc/interpretations/h01-simulator-2026-04-24.md` — interpretation writeup tying sweep findings to H01 propositions P1-P5 individually.
- `meta/results/h01-simulator/sweep-2026-04-24.parquet` — full-seed sweep output.

---

### Task 1: Add UCB policy

**Files:**
- Modify: `meta/src/h01_simulator/config.py` — add `ucb_c` field with validation.
- Modify: `meta/src/h01_simulator/policies.py` — implement and register `ucb_policy`.
- Modify: `meta/tests/test_config.py` — `ucb_c` validation tests.
- Modify: `meta/tests/test_policies.py` — UCB selection tests.

- [ ] **Step 1: Write the failing tests for UCB selection**

Append to `meta/tests/test_policies.py`:

```python
def test_ucb_policy_picks_highest_upper_bound():
    """UCB selects the proposition with the highest mean + exploration bonus."""
    from h01_simulator.config import PolicyConfig, SimConfig
    from h01_simulator.model import SignalModel, generate_propositions
    from h01_simulator.policies import POLICIES

    sim = SimConfig(n_propositions=3, budget=10, p_pos=0.9, p_neg=0.1, prior_true=0.5, seed=42)
    rng = np.random.default_rng(0)
    props = generate_propositions(sim, rng)
    model = SignalModel(props, sim, rng)
    # All three propositions start with identical priors → UCB should pick by exploration term;
    # initial pulls cycle through indices.
    pol = PolicyConfig(kind="ucb", warmup_actions=1, gate_threshold=0.5, ucb_c=1.0)
    fn = POLICIES["ucb"](pol)
    pulls = [fn(model, t, rng) for t in range(3)]
    assert set(pulls) == {0, 1, 2}, f"UCB warmup did not cover all arms: {pulls}"


def test_ucb_policy_exploration_bonus_decays_with_pulls():
    """Higher pull counts reduce the exploration bonus; arms with fewer pulls become more attractive."""
    from h01_simulator.config import PolicyConfig, SimConfig
    from h01_simulator.model import SignalModel, generate_propositions
    from h01_simulator.policies import POLICIES

    sim = SimConfig(n_propositions=2, budget=100, p_pos=0.9, p_neg=0.1, prior_true=0.5, seed=0)
    rng = np.random.default_rng(0)
    props = generate_propositions(sim, rng)
    model = SignalModel(props, sim, rng)
    pol = PolicyConfig(kind="ucb", warmup_actions=1, gate_threshold=0.5, ucb_c=1.0)
    fn = POLICIES["ucb"](pol)
    # Force arm 0 to have many pulls and a moderate posterior; arm 1 has one pull.
    for _ in range(20):
        model.observe(0, 1)
    model.observe(1, 1)
    # After warmup (t=2) UCB should prefer arm 1 (fewer pulls → larger bonus dominates).
    choice = fn(model, 22, rng)
    assert choice == 1, f"UCB failed to favor under-pulled arm: chose {choice}"
```

Append to `meta/tests/test_config.py`:

```python
def test_policy_config_rejects_negative_ucb_c():
    from h01_simulator.config import PolicyConfig

    with pytest.raises(ValueError, match="ucb_c"):
        PolicyConfig(kind="ucb", ucb_c=-0.1)


def test_policy_config_default_ucb_c_is_one():
    from h01_simulator.config import PolicyConfig

    pol = PolicyConfig(kind="ucb")
    assert pol.ucb_c == 1.0
```

- [ ] **Step 2: Run to confirm failures**

```
uv run --frozen pytest meta/tests/test_policies.py -k ucb meta/tests/test_config.py -k ucb -v
```
Expected: FAIL — UCB does not exist; `ucb_c` field missing.

- [ ] **Step 3: Add `ucb_c` to `PolicyConfig` and register `"ucb"` as a kind**

In `meta/src/h01_simulator/config.py`, update the type alias and the dataclass:

```python
PolicyKind = Literal["hard_gate", "constant_revisit", "thompson", "ucb"]
```

```python
_ALLOWED_KINDS = {"hard_gate", "constant_revisit", "thompson", "ucb"}
```

In the `PolicyConfig` dataclass body, add the new field after `revisit_prob`:

```python
    ucb_c: float = 1.0
```

In `__post_init__`, after the existing `revisit_prob` validation, add:

```python
        if self.ucb_c < 0.0:
            raise ValueError(f"ucb_c must be non-negative, got {self.ucb_c}")
```

- [ ] **Step 4: Implement `ucb_policy` and register in `POLICIES`**

In `meta/src/h01_simulator/policies.py`, add `ucb_policy` alongside the existing factory functions. Implementation: pick `argmax(posterior_mean + ucb_c * sqrt(log(t + 1) / n_i))` after warmup, where `t` is total actions taken so far (action_idx) and `n_i` is the per-proposition pull count. During warmup (`action_idx < warmup_actions * n_propositions`), cycle through indices for coverage.

Concrete implementation (read the existing module to match style — match whatever helper signatures and attribute names `thompson_policy` uses for `n_propositions` and `posterior_mean`). Use closure state to track per-arm pull counts rather than reaching into `SimConfig`; this keeps the policy interface free of cross-config coupling and matches how the existing factories work:

```python
def ucb_policy(config: PolicyConfig) -> Callable[[SignalModel, int, np.random.Generator], int]:
    pulls: np.ndarray | None = None

    def _select(model: SignalModel, action_idx: int, rng: np.random.Generator) -> int:
        nonlocal pulls
        n = model.alpha.shape[0]  # adapt to whatever the existing attribute is
        if pulls is None:
            pulls = np.zeros(n, dtype=np.int64)
        warmup_total = config.warmup_actions * n
        if action_idx < warmup_total:
            i = action_idx % n
        else:
            bonus = config.ucb_c * np.sqrt(np.log(action_idx + 1) / np.maximum(pulls, 1))
            score = model.posterior_mean() + bonus
            i = int(np.argmax(score))
        pulls[i] += 1
        return i

    return _select
```

The closure variable `pulls` is per-factory-call, and `run_single` calls the factory once per simulation run, so the state is correctly per-run (does not leak across runs in a sweep). The closure also pickles fine for `ProcessPoolExecutor` because the factory is invoked inside the worker process.

Then add to the `POLICIES` dispatch:

```python
POLICIES: dict[str, PolicyFactory] = {
    "hard_gate": hard_gate_policy,
    "constant_revisit": constant_revisit_policy,
    "thompson": thompson_policy,
    "ucb": ucb_policy,
}
```

(If the `Callable[[...], int]` type alias `PolicyFactory` is named differently in the existing module, match that.)

- [ ] **Step 5: Run UCB tests to confirm they pass**

```
uv run --frozen pytest meta/tests/test_policies.py -k ucb meta/tests/test_config.py -k ucb -v
```
Expected: all pass.

- [ ] **Step 6: Run full quality gates**

```
uv run --frozen ruff check meta/src meta/tests
uv run --frozen ruff format --check meta/src meta/tests
uv run --frozen pyright
uv run --frozen pytest
```
Expected: all pass (existing 67 + 4 new = 71 tests).

- [ ] **Step 7: Commit**

```
git add meta/src/h01_simulator/config.py meta/src/h01_simulator/policies.py \
        meta/tests/test_config.py meta/tests/test_policies.py
git commit -m "feat(meta/h01-sim): add UCB policy

UCB1 with configurable exploration constant c (default 1.0). After warmup
cycles through arms once, selects argmax(posterior_mean + c * sqrt(log(t+1)
/ n_i)) where n_i is the per-arm pull count. Disentangles 'any uncertainty
representation helps' from 'stochastic revisit specifically helps' in the
H01 sweep — without UCB, a Thompson-vs-hard_gate gap could be attributed
to either mechanism.

Part of [t002]; plan: meta/doc/plans/2026-04-24-h01-sweep-and-interpretation.md."
```

(Use a HEREDOC commit with the standard `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` trailer.)

---

### Task 2: Per-policy prior overrides + optimistic-init entries

**Files:**
- Modify: `meta/src/h01_simulator/sweep.py` — restructure `build_default_grid` to thread per-policy prior overrides; add optimistic-init entries.
- Modify: `meta/tests/test_sweep.py` — assert grid contains the optimistic-init cells.

The existing grid loop has `prior_alpha=1.0, prior_beta=1.0` baked in via `SimConfig` defaults. Optimistic-init requires `hard_gate` to also run with `Beta(5, 5)` priors. We add per-policy overrides rather than crossing a `(prior_alpha, prior_beta)` axis with all policies — the latter would 2× the grid for a comparison we only need for `hard_gate`.

- [ ] **Step 1: Write the failing test for optimistic-init coverage**

Append to `meta/tests/test_sweep.py`:

```python
def test_build_default_grid_includes_optimistic_init_hard_gate():
    """hard_gate appears with both Beta(1,1) and Beta(5,5) priors."""
    grid = list(build_default_grid(seeds=1, quick=False))
    hard_gate_priors = {
        (sim.prior_alpha, sim.prior_beta)
        for sim, pol in grid
        if pol.kind == "hard_gate"
    }
    assert (1.0, 1.0) in hard_gate_priors, "hard_gate(1,1) missing"
    assert (5.0, 5.0) in hard_gate_priors, "hard_gate(5,5) (optimistic-init) missing"


def test_build_default_grid_default_priors_for_non_hard_gate_policies():
    """Other policies use only Beta(1,1); optimistic-init is a hard_gate-specific comparison."""
    grid = list(build_default_grid(seeds=1, quick=False))
    for sim, pol in grid:
        if pol.kind == "hard_gate":
            continue
        assert (sim.prior_alpha, sim.prior_beta) == (1.0, 1.0), (
            f"non-hard_gate policy {pol.kind} got priors {(sim.prior_alpha, sim.prior_beta)}"
        )


def test_build_default_grid_expanded_revisit_rate_axis():
    """constant_revisit should appear with r in {0.05, 0.1, 0.2, 0.3} (expanded from {0.1, 0.3})."""
    grid = list(build_default_grid(seeds=1, quick=False))
    revisit_probs = {
        pol.revisit_prob for _sim, pol in grid if pol.kind == "constant_revisit"
    }
    assert revisit_probs == {0.05, 0.1, 0.2, 0.3}, (
        f"expected expanded r-axis {{0.05, 0.1, 0.2, 0.3}}, got {revisit_probs}"
    )


def test_build_default_grid_includes_ucb():
    """UCB appears as a default policy."""
    grid = list(build_default_grid(seeds=1, quick=False))
    kinds = {pol.kind for _sim, pol in grid}
    assert "ucb" in kinds, f"ucb missing from default grid kinds: {kinds}"
```

- [ ] **Step 2: Run to confirm failures**

```
uv run --frozen pytest meta/tests/test_sweep.py -k optimistic -v
```
Expected: FAIL.

- [ ] **Step 3: Restructure `build_default_grid` to thread prior overrides**

In `meta/src/h01_simulator/sweep.py`, replace the existing `build_default_grid` body so the policies list is paired with explicit prior overrides. Replace the existing `policies = [...]` block with:

```python
    # Each entry: (PolicyConfig, prior_alpha, prior_beta).
    # Only hard_gate gets the Beta(5,5) optimistic-init variant — that disentangles
    # "uncertainty in priors helps" from "stochastic revisit mechanism helps", which
    # is the comparison of interest. Crossing the prior axis with every policy
    # would 2x the grid for a comparison we don't need on Thompson/UCB.
    policy_configurations: list[tuple[PolicyConfig, float, float]] = [
        (PolicyConfig(kind="hard_gate", warmup_actions=1, gate_threshold=0.5), 1.0, 1.0),
        (PolicyConfig(kind="hard_gate", warmup_actions=1, gate_threshold=0.5), 5.0, 5.0),
        (PolicyConfig(
            kind="constant_revisit",
            warmup_actions=1,
            gate_threshold=0.5,
            revisit_prob=0.05,
        ), 1.0, 1.0),
        (PolicyConfig(
            kind="constant_revisit",
            warmup_actions=1,
            gate_threshold=0.5,
            revisit_prob=0.1,
        ), 1.0, 1.0),
        (PolicyConfig(
            kind="constant_revisit",
            warmup_actions=1,
            gate_threshold=0.5,
            revisit_prob=0.2,
        ), 1.0, 1.0),
        (PolicyConfig(
            kind="constant_revisit",
            warmup_actions=1,
            gate_threshold=0.5,
            revisit_prob=0.3,
        ), 1.0, 1.0),
        (PolicyConfig(kind="thompson", warmup_actions=1), 1.0, 1.0),
        (PolicyConfig(kind="ucb", warmup_actions=1, ucb_c=1.0), 1.0, 1.0),
    ]
```

Then in the inner loop, replace `for policy in policies:` and the `SimConfig(...)` construction with:

```python
    for p_pos, p_neg in noise_pairs:
        for k in budget_multiples:
            for n in n_props_values:
                budget = int(k * n)
                for prior_true in prior_true_values:
                    for bias_model, bias_fraction, bias_sigma in bias_settings:
                        for seed in range(seeds):
                            for policy, prior_alpha, prior_beta in policy_configurations:
                                warmup_total = policy.warmup_actions * n
                                if budget <= warmup_total:
                                    continue
                                sim = SimConfig(
                                    n_propositions=n,
                                    budget=budget,
                                    p_pos=p_pos,
                                    p_neg=p_neg,
                                    prior_true=prior_true,
                                    prior_alpha=prior_alpha,
                                    prior_beta=prior_beta,
                                    bias_model=bias_model,
                                    bias_fraction=bias_fraction,
                                    bias_sigma=bias_sigma,
                                    seed=seed,
                                )
                                yield sim, policy
```

(Note: `seed` and `policy` loops are swapped vs. the previous structure so that each seed produces all policies under identical SimConfig context — keeps results easier to group later. The sim is reconstructed inside the policy loop because the priors vary.)

For `quick=True`, also update its `policy_configurations` to a small subset, e.g.:

```python
        policy_configurations = [
            (PolicyConfig(kind="hard_gate", warmup_actions=1, gate_threshold=0.5), 1.0, 1.0),
            (PolicyConfig(kind="thompson", warmup_actions=1), 1.0, 1.0),
        ]
```

- [ ] **Step 4: Run new tests + full grid suite**

```
uv run --frozen pytest meta/tests/test_sweep.py -v
```
Expected: all pass. The pre-existing `test_build_default_grid_*` tests should still pass; the priors test (`test_build_default_grid_default_priors_for_non_hard_gate_policies`) and optimistic-init test (`test_build_default_grid_includes_optimistic_init_hard_gate`) should now pass.

- [ ] **Step 5: Run quality gates**

```
uv run --frozen ruff check meta/src meta/tests
uv run --frozen ruff format --check meta/src meta/tests
uv run --frozen pyright
uv run --frozen pytest
```
Expected: all pass.

- [ ] **Step 6: Commit**

```
git add meta/src/h01_simulator/sweep.py meta/tests/test_sweep.py
git commit -m "feat(meta/h01-sim): grid supports per-policy prior overrides; optimistic-init hard_gate

Adds the optimistic-init experiment (hard_gate with Beta(5,5) priors) as
a parallel grid entry to standard hard_gate(Beta(1,1)). UCB also lands
in the default policies list. Per-policy overrides chosen over a global
prior axis to keep grid growth proportional to the comparisons needed,
not crossed across all policies.

Part of [t002]; plan: meta/doc/plans/2026-04-24-h01-sweep-and-interpretation.md."
```

---

### Task 3: Re-anchor `RUNTIME_BUDGET_SECONDS` for the expanded grid

The grid grew from 4 policy entries to 8 (1 hard_gate + 1 hard_gate-optimistic + 4 constant_revisit + 1 thompson + 1 ucb). Roughly 2× the runs. The `[t001b]` projection of ~1740s serial against the 1800s budget will fail; we re-anchor honestly.

**Files:**
- Modify: `meta/src/h01_simulator/cli.py` — update `RUNTIME_BUDGET_SECONDS` based on a fresh measurement.

- [ ] **Step 1: Run the benchmark and observe the new projection**

```
uv run --frozen h01-sim benchmark --seeds 100
```

The current `RUNTIME_BUDGET_SECONDS = 1800` will likely cause a `ClickException` since the grid is roughly 2× larger. Capture the projection number from the output before the exception fires.

Run the benchmark **at least 5 times** to capture variance. Record all 5 projections.

- [ ] **Step 2: Choose the new budget**

`chosen = ceil(measured_max / 60) * 60 + 60`, capped at 4500 (75 minutes). Use the *maximum* of the 5 observed projections (not the average) so the gate has a real safety margin against timing noise.

If `measured_max > 4500`, do NOT raise the cap. Instead, BLOCK with a NEEDS_CONTEXT report describing the projection and asking whether to (a) tighten the grid (drop a noise pair, drop the highest budget multiple, drop one constant_revisit r value) or (b) accept a higher cap. The cap of 4500 reflects that beyond ~75 min serial CPU, the engine should be questioned, not the gate.

- [ ] **Step 3: Update `RUNTIME_BUDGET_SECONDS`**

In `meta/src/h01_simulator/cli.py`, replace the comment block + assignment near the top with the new value. Concrete example (numbers will differ — use what you actually measured):

```python
# Serial CPU budget, re-anchored after [t002] grid expansion (UCB + optimistic-init
# + expanded r-axis). Measured projection averages ~3500s, max 3580s across 5 runs
# at n_calibration_runs=400. Wall-clock feasibility via --workers is the actual
# sweep's concern; the gate intentionally measures serial cost only.
RUNTIME_BUDGET_SECONDS = 3700
```

- [ ] **Step 4: Re-run benchmark to confirm gate passes**

```
uv run --frozen h01-sim benchmark --seeds 100
```
Expected: no `ClickException`. Run twice more to confirm stability.

- [ ] **Step 5: Run full quality gates**

```
uv run --frozen ruff check meta/src meta/tests
uv run --frozen ruff format --check meta/src meta/tests
uv run --frozen pyright
uv run --frozen pytest
bash meta/validate.sh --verbose
```
Expected: all pass (or pre-existing `knowledge/` warning, which is unrelated and documented in `core/overview.md`).

- [ ] **Step 6: Commit**

```
git add meta/src/h01_simulator/cli.py
git commit -m "feat(meta/h01-sim): re-anchor RUNTIME_BUDGET_SECONDS for [t002] grid

Grid grew ~2x with UCB + optimistic-init + expanded r-axis (Tasks 1-2 of
[t002]). Measured serial projection averaged ~<X>s, max ~<Y>s across 5
runs. Budget set to <chosen>s; wall-clock feasibility via --workers
remains [t002]'s sweep-time concern, not the gate's."
```

(Replace `<X>`, `<Y>`, `<chosen>` with the actual numbers from your measurement.)

---

### Task 4: Run the full sweep

The sweep is run from the worktree. Output goes to `meta/results/h01-simulator/sweep-2026-04-24.parquet`.

**Files:**
- Create: `meta/results/h01-simulator/sweep-2026-04-24.parquet`.

- [ ] **Step 1: Confirm benchmark gate passes one more time**

```
uv run --frozen h01-sim benchmark --seeds 100
```
Expected: passes.

- [ ] **Step 2: Run the sweep with parallelism**

Choose worker count based on the host machine's CPU. A reasonable default is `nproc / 2` (or fewer) so the host stays responsive; on an 8-core host, `--workers 4` is a good baseline. Confirm available cores:

```
nproc
```

Then:

```
uv run --frozen h01-sim sweep --seeds 100 --workers <chosen>
```

This will write `meta/results/h01-simulator/sweep-2026-04-24.parquet` (the date is the current date, set by the CLI's default).

Expected: completes without error. Print row count = total grid rows from the benchmark output.

If the sweep fails midway (worker crash, OOM, etc.), report BLOCKED with the full traceback. Do NOT retry blindly with fewer workers — investigate first.

- [ ] **Step 3: Sanity-check the parquet**

A quick inline sanity check via `uv run python -c '...'` to confirm shape, column presence, and that all expected `(policy, prior_alpha)` combinations appear:

```
uv run --frozen python -c "
import polars as pl
df = pl.read_parquet('meta/results/h01-simulator/sweep-2026-04-24.parquet')
print('rows:', df.height)
print('policies:', df['policy'].unique().to_list())
print('priors:', df.select(['policy', 'prior_alpha', 'prior_beta']).unique().sort(['policy', 'prior_alpha']).to_dicts())
print('budget multiples:', sorted(df['budget_multiple'].unique().to_list()))
print('bias_models:', df['bias_model'].unique().to_list())
print('null check:')
print(df.null_count().to_dicts())
"
```

Verify:
- Row count matches benchmark projection.
- 4 distinct policies (`hard_gate`, `constant_revisit`, `thompson`, `ucb`).
- Two `(policy=hard_gate, prior_alpha)` pairs: `(1.0, 1.0)` and `(5.0, 5.0)`.
- All other policies have only `(1.0, 1.0)`.
- Budget multiples: `{2.0, 8.0, 32.0}`.
- Bias models: `{none, independent, shared}`.
- No null cells in scalar columns.

- [ ] **Step 4: Commit the parquet**

```
git add meta/results/h01-simulator/sweep-2026-04-24.parquet
git commit -m "data(meta/h01-sim): full-seed sweep parquet (t002)

<rows> rows across 5 noise levels x 3 budget multiples x 2 N x 2 prior_true
x 3 bias modes x 100 seeds x 8 policy/prior entries. Hard-gate appears
twice (Beta(1,1) and Beta(5,5) optimistic-init); constant_revisit covers
revisit_prob in {0.05, 0.1, 0.2, 0.3}; thompson and ucb at default settings.
Generated by 'h01-sim sweep --seeds 100 --workers <N>'.

Part of [t002]; plan: meta/doc/plans/2026-04-24-h01-sweep-and-interpretation.md."
```

(Replace `<rows>` and `<N>` with actual numbers.)

**Note:** The parquet is committed to git intentionally — it is the empirical artifact this whole project is anchored to. If the file is unusually large (>50 MB), pause and report; we may need to split or use git-lfs.

---

### Task 5: Build the marimo notebook with six headline figures

`meta/notebooks/h01_simulator_results.py` is currently a stub. Populate it with six figures that map to specific claims in H01.

**Files:**
- Modify: `meta/notebooks/h01_simulator_results.py`.

The notebook is marimo (cells are Python; rendering uses altair). Read the existing stub first to confirm structure.

The six figures, with their analytical purpose:

| # | Figure | x-axis | y-axis | color | facet | What it tests |
|---|--------|--------|--------|-------|-------|---------------|
| 1 | recall-vs-noise per policy | `p_pos - p_neg` (noise level, descending = noisier) | mean recall (over seeds) | policy | `bias_model` | P1, P2 directly: does revisiting beat gating? Does the gap scale with noise? |
| 2 | brier-vs-noise per policy | noise | mean brier | policy | `bias_model` | Recall-independent calibration corroboration. Critical because `signal_count_regret` is unreliable in `shared` rows. |
| 3 | reliability diagram | predicted-probability bin | empirical fraction true | policy | `bias_model` | Calibration quality per policy — H01 implicitly assumes continuous beliefs are calibrated; this checks that. |
| 4 | threshold-swept recall | `threshold ∈ [0.3, 0.4, ..., 0.7]` | recall at threshold | policy | `bias_model` | Robustness of the recall claim to the threshold choice. |
| 5 | shared-vs-independent delta | noise | `recall(shared) - recall(independent)` | policy | (none) | P3 directly: is shared bias the most discriminating regime? |
| 6 | r-curve recall | `revisit_prob` (continuous, 0 = hard_gate) | recall | noise level (color) | `bias_model` | Reframing test: is optimal r a function of uncertainty? |

- [ ] **Step 1: Read the existing notebook stub**

```
cat meta/notebooks/h01_simulator_results.py
```

Note the marimo cell structure (`@app.cell` decorators, app construction). Match it.

- [ ] **Step 2: Populate the notebook**

Replace the stub with a populated version. The full expected structure:

1. **Imports cell** — `polars`, `altair`, `marimo`, `numpy`, plus a constant for the parquet path.
2. **Load cell** — read `meta/results/h01-simulator/sweep-2026-04-24.parquet` into a polars `LazyFrame`. Add a `noise_level = p_pos - p_neg` column for cleaner x-axis labelling. Add a `policy_label` column that combines `policy` with `revisit_prob` (for `constant_revisit`), `prior_alpha` (for `hard_gate(5,5)` vs `hard_gate(1,1)`), and `ucb_c` (for `ucb`) so legends are readable.
3. **Figure 1 cell** — recall-vs-noise. Aggregate `mean(recall)` over `seed`. Encode as `altair.Chart` with `x=noise_level:Q`, `y=mean_recall:Q`, `color=policy_label:N`, `facet=bias_model:N`. Save chart to a variable and `mo.ui.altair_chart(chart)` for marimo display. Caption clearly states P1, P2 connection.
4. **Figure 2 cell** — same structure as Figure 1 but `y=mean_brier:Q`. Brier is on a different scale (lower is better) — note that in the caption.
5. **Figure 3 cell** — reliability. Per-row, the parquet has `final_alpha` and `final_beta` arrays (from `[t001]`). Compute per-proposition `posterior_mean = alpha / (alpha + beta)`, bin into `[0, 0.1, 0.2, ..., 1.0]`, group by `(policy_label, bias_model, bin)`, compute `(empirical_fraction_true = mean of ground_truth in bin, n_in_bin)`. Plot as line chart `x=bin_midpoint:Q`, `y=empirical_fraction_true:Q`, plus the diagonal `y=x` reference, `color=policy_label:N`, `facet=bias_model:N`. Bins with `n_in_bin < 30` should be dropped or shown with reduced opacity.
6. **Figure 4 cell** — threshold-swept recall. Re-compute recall at thresholds `{0.3, 0.4, 0.5, 0.6, 0.7}` from the stored `final_alpha`, `final_beta`, and `ground_truth` columns. Aggregate `mean(recall_at_t)` over seed × bias × N × budget × noise (all rows). Plot `x=threshold:Q`, `y=mean_recall:Q`, `color=policy_label:N`, `facet=bias_model:N`.
7. **Figure 5 cell** — shared-vs-independent delta. Pivot so `recall_shared` and `recall_independent` are columns; compute `delta = recall_shared - recall_independent` per `(policy_label, noise_level, seed)`. Aggregate `mean(delta)` over seed. Plot `x=noise_level:Q`, `y=mean_delta:Q`, `color=policy_label:N`. (No facet — bias_model is the lens being computed.)
8. **Figure 6 cell** — r-curve. Filter to `policy in {hard_gate, constant_revisit}` and add `revisit_prob = 0` for hard_gate(1,1) rows (treat hard_gate as r=0). Aggregate `mean(recall)` over seed for each `(revisit_prob, noise_level, bias_model)`. Plot `x=revisit_prob:Q`, `y=mean_recall:Q`, `color=noise_level:O`, `facet=bias_model:N`.

Each figure cell should display the chart and a markdown caption that states (a) what the figure shows, (b) which H01 proposition it bears on, and (c) any caveats specific to that figure (e.g., Figure 6's r=0 mapping to hard_gate).

Concrete code skeleton for one cell to anchor the style; adapt for the others:

```python
@app.cell
def figure_1_recall_vs_noise(df, mo):
    import altair as alt

    agg = (
        df.lazy()
        .with_columns((pl.col("p_pos") - pl.col("p_neg")).alias("noise_level"))
        .group_by(["policy_label", "bias_model", "noise_level"])
        .agg(pl.col("recall").mean().alias("mean_recall"))
        .collect()
    )
    chart = (
        alt.Chart(agg.to_pandas())
        .mark_line(point=True)
        .encode(
            x=alt.X("noise_level:Q", title="Noise level (p_pos - p_neg)"),
            y=alt.Y("mean_recall:Q", title="Mean recall (avg over seeds)"),
            color=alt.Color("policy_label:N", title="Policy"),
        )
        .facet(column=alt.Column("bias_model:N", title="Bias model"))
        .properties(title="Recall vs. noise — P1 (revisiting helps) and P2 (gap scales with noise)")
    )
    mo.md("""**Figure 1: Recall vs. noise per policy, faceted by bias model.**
    Tests P1 directly (does any policy with revisit beat hard_gate?) and P2 (does the gap widen as noise increases?).
    The `none` bias panel shows the baseline; `independent` and `shared` show the two bias regimes.""")
    chart
    return agg, chart
```

(Adapt to the existing notebook's marimo idioms; if the stub uses a different cell-return convention, follow that.)

- [ ] **Step 3: Run the notebook to confirm it executes end-to-end**

```
uv run --frozen marimo run meta/notebooks/h01_simulator_results.py --no-browser &
sleep 5
kill %1
```

(Or use `marimo edit` interactively. The point is to confirm no exceptions on cell execution. Marimo's "run" mode is non-interactive.)

If marimo's run mode is awkward to verify in CI, alternatively:

```
uv run --frozen python -c "
import importlib.util
spec = importlib.util.spec_from_file_location('nb', 'meta/notebooks/h01_simulator_results.py')
mod = importlib.util.module_from_spec(spec)
# Don't actually exec marimo cells — just verify imports + the load cell work.
"
```

The actual figure rendering is verified visually by opening the notebook.

- [ ] **Step 4: Run quality gates**

```
uv run --frozen ruff check meta/notebooks
uv run --frozen ruff format --check meta/notebooks
uv run --frozen pyright
uv run --frozen pytest
```
Expected: all pass.

- [ ] **Step 5: Commit**

```
git add meta/notebooks/h01_simulator_results.py
git commit -m "feat(meta/h01-sim): populate H01 results notebook with six figures

Figures: (1) recall-vs-noise per policy [P1, P2], (2) brier-vs-noise per
policy [calibration corroboration], (3) reliability diagram [continuous-
belief sanity check], (4) threshold-swept recall [robustness], (5) shared-
vs-independent recall delta [P3], (6) r-curve [reframing: optimal r
function of uncertainty].

Part of [t002]; plan: meta/doc/plans/2026-04-24-h01-sweep-and-interpretation.md."
```

---

### Task 6: Write the interpretation document

This is the most important deliverable. It is the artifact that turns the sweep numbers into knowledge about the hypothesis. Treat the writing seriously — the per-proposition structure is non-negotiable.

**Files:**
- Create: `meta/doc/interpretations/h01-simulator-2026-04-24.md`.

The interpretation must:

1. State the high-level finding in one sentence at the top.
2. Walk through each H01 proposition (P1-P5) individually, citing specific figures + numbers.
3. Address the alternative-explanation checklist from the handoff note explicitly.
4. State the explicit caveat that `signal_count_regret` is unreliable in `shared` bias rows; recall + Brier are the load-bearing metrics.
5. Identify follow-up work (which alternative framings are now worth testing; which were ruled out).

- [ ] **Step 1: Read the H01 hypothesis spec**

```
cat meta/specs/hypotheses/h01-stochastic-revisiting.md
```

Note the propositions P1-P5 verbatim. The interpretation must address each one individually, in order.

- [ ] **Step 2: Read the alternative-explanation section of the handoff note**

The handoff note's "Alternative explanations and framings to consider" section lists four alternatives the interpretation must address explicitly:
- Exploration of prior-sampling distribution (now testable via the optimistic-init cells).
- Beta-Bernoulli artifact (still untestable in this sweep — note as future work).
- Budget-per-proposition vs. noise-effect (partly addressed via budget_multiple axis).
- Oracle artifact in regret (addressed by the rename + caveat from `[t001b]`).

The writeup confirms or refutes each.

- [ ] **Step 3: Write `meta/doc/interpretations/h01-simulator-2026-04-24.md`**

Structure:

```markdown
# H01 Sweep Interpretation — 2026-04-24

> Test artifact: `meta/results/h01-simulator/sweep-2026-04-24.parquet` (<rows> rows).
> Figures: `meta/notebooks/h01_simulator_results.py`.
> Hypothesis: `meta/specs/hypotheses/h01-stochastic-revisiting.md`.

## Headline finding

[One sentence. Examples — pick the one that matches the data:
- "H01 confirmed: stochastic revisiting beats hard-gating across noise levels, with the gap widening monotonically and most discriminating in the shared-bias regime."
- "H01 partially confirmed: revisiting beats gating in independent-noise regimes but gap closes / reverses under shared bias."
- "H01 disconfirmed: ..."]

## Per-proposition findings

### P1: [verbatim from spec]
[2-3 sentences, citing Figure N, with specific numbers (e.g. "mean recall 0.74 vs 0.62 at p_pos-p_neg=0.2 under independent bias").]

### P2: [verbatim from spec]
[Likewise.]

### P3: [verbatim from spec]
[Likewise. This is the shared-bias-as-disconfirmation-route claim. Cite Figure 5 specifically.]

### P4: [verbatim from spec]
[Likewise.]

### P5: [verbatim from spec]
[Likewise. If the r-curve (Figure 6) shows an optimum that is not constant, note this.]

## Alternative-explanation checklist

### Exploration of the prior-sampling distribution, not recovery from noise
Optimistic-init cells (`hard_gate` with `Beta(5,5)` priors) [confirm/rule out] this. Specifically: [state recall of `hard_gate(5,5)` vs `hard_gate(1,1)` under each bias regime].

### Artifact of the Beta-Bernoulli conjugate structure
Not testable in this sweep. A Gaussian effect-size variant of the simulator is needed; recorded as future work.

### Budget-per-proposition vs. noise effect
[Address using the budget_multiple axis. If recall-vs-noise patterns are similar across budget_multiple values, the noise effect is robust to budget.]

### Oracle artifact in regret
Addressed structurally by `[t001b]`: `signal_count_regret` is renamed and documented as unreliable in `shared` rows. Recall and Brier are the load-bearing metrics in the interpretation above; `signal_count_regret` is reported in the parquet but treated as a diagnostic.

## Calibration check

Figure 3 (reliability diagram) shows [continuous beliefs are well-calibrated / are not / are calibrated under independent but not shared bias / etc.]. This bears on D-003 (continuous beliefs as a load-bearing principle): [if calibration holds, D-003 is supported; if not, D-003 may need the calibration-auditing successor work prioritised].

## Follow-up work surfaced

- [List specific framings that are now worth testing — e.g., "if r-curve shows non-constant optimum, an uncertainty-aware revisit policy is the natural successor."]
- [List alternatives that this sweep ruled out — e.g., "optimistic-init alone does not close the hard_gate gap, so D-003's continuous-belief commitment matters more than just prior shape."]
- [Any methodological gaps — e.g., "Brier-Gaussian variant remains untested."]

## Confidence

[State your confidence in the headline finding, separately for each proposition. The honest range is "this is what the simulator showed; whether it generalises beyond the binary Bernoulli abstraction is bounded."]
```

Write specific numbers from the figures. Hand-waving like "considerably better" is unacceptable — replace with "0.74 vs 0.62" or "a 12-point absolute gap."

The writing must follow `science:writing` conventions: claims with provenance, no hype, calibration-honest. Invoke the skill before drafting if needed.

- [ ] **Step 4: Run the science:writing skill on the draft**

(Optional but recommended.) The `science:writing` skill provides scientific-writing conventions. Invoke it if you want a writing-style review before commit.

- [ ] **Step 5: Quality gates**

```
uv run --frozen pytest
bash meta/validate.sh --verbose
```

Expected: pytest passes; validate may have the pre-existing `knowledge/` warning unrelated to this work.

- [ ] **Step 6: Commit**

```
git add meta/doc/interpretations/h01-simulator-2026-04-24.md
git commit -m "doc(meta/h01-sim): H01 sweep interpretation — [confirmed/partial/disconfirmed]

[1-2 sentence summary of the headline finding from the writeup.]

Per-proposition findings (P1-P5) cite specific figures and numbers.
Addresses alternative-explanation checklist from handoff note. Notes
calibration evidence bearing on D-003.

Closes the analysis half of [t002]."
```

(Replace `[confirmed/partial/disconfirmed]` and the summary with the actual finding.)

---

### Task 7: Close `[t002]` in the task backlog

**Files:**
- Modify: `meta/tasks/active.md`.

- [ ] **Step 1: Update `[t002]`'s status and add a completion note**

Edit `meta/tasks/active.md`. Change `[t002]`'s `status: proposed` to `status: done` and append a completion note describing what shipped:

```markdown
**COMPLETED 2026-04-24.** Sweep ran with engine extensions (UCB policy, optimistic-init hard_gate variant, expanded constant_revisit r-axis ∈ {0.05, 0.1, 0.2, 0.3}). Output: `meta/results/h01-simulator/sweep-2026-04-24.parquet` (<rows> rows). Notebook: `meta/notebooks/h01_simulator_results.py` with six figures (recall-vs-noise, brier-vs-noise, reliability, threshold-swept recall, shared-vs-independent delta, r-curve). Interpretation: `meta/doc/interpretations/h01-simulator-2026-04-24.md` — [headline finding in one sentence]. RUNTIME_BUDGET_SECONDS re-anchored to <X>s for the larger grid.
```

(Replace `<rows>`, `<X>`, and the headline finding with actuals.)

- [ ] **Step 2: Commit**

```
git add meta/tasks/active.md
git commit -m "docs(meta): close [t002]; H01 sweep + interpretation shipped"
```

---

## Self-Review Checklist

- [x] Each H01 proposition (P1-P5) has a dedicated section in the interpretation, with specific numbers cited from the figures.
- [x] The alternative-explanation checklist from the handoff note is addressed item-by-item.
- [x] `signal_count_regret`'s shared-bias unreliability is explicitly noted; recall + brier carry the load.
- [x] Optimistic-init experiment is included (disentangles prior effect from revisit mechanism).
- [x] UCB is included (disentangles uncertainty-rep effect from revisit mechanism).
- [x] r-curve is included (tests the "optimal r is uncertainty-dependent" reframing).
- [x] Brier is promoted to headline figure status (calibration corroboration of recall).
- [x] Runtime gate re-anchored honestly to honest serial CPU; capped at 4500s.
- [x] No silent fallbacks: `workers >= 1`, gate failures BLOCK rather than auto-raising the cap.
- [x] All file paths use `meta/...` prefix.
- [x] Out of scope (annealed revisit, restart, info-gain, Gaussian variant, budget-aware recall oracle, detectability) is recorded for future work.
