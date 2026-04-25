"""Marimo notebook: H01 simulator results.

Six headline figures over the 2026-04-24 grid sweep (144,000 rows).
Each figure bears on one or more H01 propositions (P1-P5) or the
alternative-explanation checklist from the session handoff note.
"""

import marimo

__generated_with = "0.23.3"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    import altair as alt
    import numpy as np
    from pathlib import Path

    # Resolve parquet path relative to this file's location (meta/notebooks/),
    # falling back to a path relative to the repo root if running from there.
    _nb_dir = Path(__file__).parent
    _candidate = _nb_dir.parent / "results" / "h01-simulator" / "sweep-2026-04-24.parquet"
    PARQUET_PATH = _candidate if _candidate.exists() else Path("meta/results/h01-simulator/sweep-2026-04-24.parquet")

    return alt, mo, np, pl, Path, PARQUET_PATH


@app.cell
def _(mo):
    mo.md(
        """
        # H01 Simulator Results — Sweep 2026-04-24

        This notebook visualises the full grid sweep of the H01 epistemics simulator
        (144,000 rows; 8 policies × 3 bias models × 5 noise levels × 2 n_props × 3
        budget multiples × 2 prior_true settings × 100 seeds).

        **H01** (the "human oracle inference" hypothesis) asserts that a rational agent
        can infer latent proposition truth from behavioural evidence even when signals
        are noisy and biased.  Five sub-propositions (P1–P5) make specific predictions:

        | Prop | Claim |
        |------|-------|
        P1 | Recall rises with signal reliability (noise ↓) |
        P2 | Adaptive policies outperform the hard gate on recall |
        P3 | Shared bias hurts recall relative to independent noise |
        P4 | Larger revisit budgets improve recall on the r-curve |
        P5 | Calibration (Brier ↓) co-varies with recall improvement |

        Six figures are presented in order.  The interpretation of specific numerical
        findings belongs in the Task 6 write-up; captions here describe *what* the
        figure tests and *what outcome would falsify* the corresponding proposition.
        """
    )
    return


@app.cell
def _(pl, np, PARQUET_PATH):
    """Load parquet and add derived columns used across all figures."""
    _raw = pl.read_parquet(PARQUET_PATH)

    # noise_level = signal-to-noise gap (p_pos - p_neg).
    # Values in sweep: 0.1, 0.2, 0.4, 0.6, 0.8  (higher = easier inference).
    _with_noise = _raw.with_columns((pl.col("p_pos") - pl.col("p_neg")).alias("noise_level"))

    # policy_label: human-readable legend string combining policy + key params.
    def _make_label(row: dict) -> str:  # type: ignore[type-arg]
        p = row["policy"]
        if p == "hard_gate":
            if row["prior_alpha"] == 5.0:
                return "hard_gate (Beta(5,5))"
            return "hard_gate"
        if p == "constant_revisit":
            r = row["revisit_prob"]
            return f"constant_revisit (r={r:.2f})"
        if p == "thompson":
            return "thompson"
        if p == "ucb":
            c = row["ucb_c"]
            return f"ucb (c={c:.1f})"
        return p

    _labels = _with_noise.select(["policy", "prior_alpha", "revisit_prob", "ucb_c"]).map_rows(
        lambda row: (_make_label({"policy": row[0], "prior_alpha": row[1], "revisit_prob": row[2], "ucb_c": row[3]}),)
    )

    df = _with_noise.with_columns(_labels.to_series(0).alias("policy_label"))

    # Quick sanity check
    assert df.height == 144_000, f"Unexpected row count: {df.height}"
    assert "noise_level" in df.columns
    assert "policy_label" in df.columns

    return (df, np)


@app.cell
def _(df, alt, mo, pl):
    """Figure 1: recall-vs-noise per policy, faceted by bias model.

    **Analytical purpose (P1, P2):**
    P1 predicts recall increases monotonically with noise_level (= p_pos - p_neg),
    because higher signal reliability means the agent receives more discriminating
    evidence.  P2 predicts that adaptive policies (thompson, ucb, constant_revisit
    at any r) should trace a higher recall curve than the baseline hard_gate.

    **Falsification route:** If recall does not rise with noise_level for *any*
    policy, P1 is falsified.  If hard_gate matches or beats every adaptive policy
    at every noise level, P2 is falsified.

    Mean is taken over seeds, n_props, and budget_multiple (all 12 parameter
    combinations per noise × policy × bias cell) to give a single representative
    curve per legend entry.
    """
    _agg1 = (
        df.group_by(["policy_label", "bias_model", "noise_level"])
        .agg(pl.col("recall").mean().alias("mean_recall"))
        .sort(["bias_model", "policy_label", "noise_level"])
    )

    _fig1 = (
        alt.Chart(_agg1)
        .mark_line(point=True)
        .encode(
            x=alt.X("noise_level:Q", title="Noise level (p_pos − p_neg)", scale=alt.Scale(zero=False)),
            y=alt.Y("mean_recall:Q", title="Mean recall", scale=alt.Scale(zero=False)),
            color=alt.Color("policy_label:N", title="Policy"),
            facet=alt.Facet("bias_model:N", columns=3, title="Bias model"),
        )
        .properties(width=220, height=180, title="Figure 1 — Recall vs noise level per policy")
        .resolve_scale(y="shared")
    )

    mo.vstack(
        [
            mo.md("## Figure 1: Recall vs noise level per policy [P1, P2]"),
            _fig1,
            mo.md(
                f"_N = {_agg1.height} aggregated rows "
                f"({_agg1['policy_label'].n_unique()} policies × "
                f"{_agg1['bias_model'].n_unique()} bias models × "
                f"{_agg1['noise_level'].n_unique()} noise levels). "
                "Each point is the mean recall over 100 seeds, 2 n_props values, and "
                "3 budget multiples. Rising curves across noise_level support P1; "
                "adaptive policies above hard_gate supports P2._"
            ),
        ]
    )


@app.cell
def _(df, alt, mo, pl):
    """Figure 2: brier-vs-noise per policy, faceted by bias model.

    **Analytical purpose (calibration, P5):**
    Brier score (lower = better) measures probabilistic calibration — whether the
    agent's posterior means match actual proposition frequencies.  P5 predicts that
    policies with higher recall also exhibit lower Brier scores, i.e. improved
    discrimination and calibration co-occur.

    Note: signal_count_regret can decorrelate from recall in the shared bias rows
    (because shared bias inflates apparent signal counts uniformly), so Brier is
    the more reliable co-equal lens for calibration quality.

    **Falsification route:** If Brier rises (worsens) even as recall rises with
    noise, the agent is guessing correctly on average but is miscalibrated — P5
    would be partially falsified.
    """
    _agg2 = (
        df.group_by(["policy_label", "bias_model", "noise_level"])
        .agg(pl.col("brier").mean().alias("mean_brier"))
        .sort(["bias_model", "policy_label", "noise_level"])
    )

    _fig2 = (
        alt.Chart(_agg2)
        .mark_line(point=True)
        .encode(
            x=alt.X("noise_level:Q", title="Noise level (p_pos − p_neg)", scale=alt.Scale(zero=False)),
            y=alt.Y("mean_brier:Q", title="Mean Brier score (↓ better)", scale=alt.Scale(zero=False)),
            color=alt.Color("policy_label:N", title="Policy"),
            facet=alt.Facet("bias_model:N", columns=3, title="Bias model"),
        )
        .properties(width=220, height=180, title="Figure 2 — Brier score vs noise level per policy")
        .resolve_scale(y="shared")
    )

    mo.vstack(
        [
            mo.md("## Figure 2: Brier score vs noise level per policy [P5, calibration]"),
            _fig2,
            mo.md(
                f"_N = {_agg2.height} aggregated rows. "
                "Brier score = mean squared error between posterior mean and ground truth "
                "(lower is better). Declining Brier with increasing noise_level (alongside "
                "rising recall from Figure 1) would corroborate P5. "
                "Brier is preferred to signal_count_regret as the calibration lens here "
                "because shared bias inflates signal counts without improving accuracy._"
            ),
        ]
    )


@app.cell
def _(df, alt, mo, np, pl):
    """Figure 3: reliability diagram — predicted probability vs empirical frequency.

    **Analytical purpose (D-003, continuous-belief calibration):**
    A well-calibrated Bayesian agent should satisfy: among all propositions assigned
    posterior probability p̂, approximately fraction p̂ should be true.  This figure
    plots binned posterior means (from final_alpha / final_beta) against the empirical
    fraction of true propositions in each bin, per policy and bias model.  The
    diagonal y = x is perfect calibration.

    **Falsification route:** Systematic deviation above or below the diagonal
    indicates over- or under-confidence.  If adaptive policies deviate more than
    hard_gate, P2's claim of superiority requires qualification.

    **Sampling note:** The full explode of 144,000 rows × up to 100 propositions
    = ~8.6M data points.  A uniform 10% sample (14,400 rows, ~860k propositions)
    is used to keep memory tractable; results are representative given 100 seeds.
    """
    _sample = df.sample(fraction=0.1, seed=42)
    _exploded = _sample.explode(["final_alpha", "final_beta", "ground_truth"]).with_columns(
        (pl.col("final_alpha") / (pl.col("final_alpha") + pl.col("final_beta"))).alias("posterior_mean")
    )

    # Bin posterior_mean into 10 equal-width bins on [0, 1].
    _bin_edges_inner = np.linspace(0, 1, 11)[1:-1].tolist()  # 9 breakpoints → 10 bins
    _exploded = _exploded.with_columns(
        pl.col("posterior_mean").cut(_bin_edges_inner, labels=[str(i) for i in range(10)]).alias("bin_idx")
    )
    # Bin midpoints for x-axis: bin i spans [i/10, (i+1)/10], midpoint = (i+0.5)/10
    # cut() returns Enum dtype; cast to Utf8 first before numeric replacement.
    _bin_mid_map = {str(i): str(round((i + 0.5) / 10, 3)) for i in range(10)}
    _exploded = _exploded.with_columns(
        pl.col("bin_idx").cast(pl.Utf8).replace(_bin_mid_map).cast(pl.Float64).alias("bin_midpoint")
    )

    _reliability = (
        _exploded.group_by(["policy_label", "bias_model", "bin_idx", "bin_midpoint"])
        .agg(
            pl.col("ground_truth").mean().alias("empirical_frac"),
            pl.col("ground_truth").count().alias("n"),
        )
        .filter(pl.col("n") >= 30)
        .sort(["bias_model", "policy_label", "bin_midpoint"])
    )

    # Perfect calibration reference line
    _diag = pl.DataFrame({"x": [0.0, 1.0], "y": [0.0, 1.0]})

    _base3 = alt.Chart(_reliability)
    _points3 = (
        _base3.mark_point()
        .encode(
            x=alt.X("bin_midpoint:Q", title="Predicted probability (bin midpoint)", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("empirical_frac:Q", title="Empirical fraction true", scale=alt.Scale(domain=[0, 1])),
            color=alt.Color("policy_label:N", title="Policy"),
            size=alt.Size("n:Q", title="Bin count", scale=alt.Scale(range=[20, 150])),
        )
        .properties(width=220, height=200)
    )
    _diag_line = alt.Chart(_diag).mark_line(color="gray", strokeDash=[4, 4]).encode(x="x:Q", y="y:Q")
    _fig3 = (
        alt.layer(_diag_line, _points3, data=_reliability)
        .facet("bias_model:N", columns=3)
        .resolve_scale(x="shared", y="shared")
        .properties(title="Figure 3 — Reliability diagram (10% sample, bins with n ≥ 30)")
    )

    mo.vstack(
        [
            mo.md("## Figure 3: Reliability diagram [D-003, calibration]"),
            _fig3,
            mo.md(
                f"_Posterior means computed from final_alpha / final_beta per proposition. "
                f"10-bin equal-width histogram on [0, 1]. Bins with fewer than 30 propositions "
                f"filtered. Dashed diagonal = perfect calibration (y = x). "
                f"Based on a 10% uniform sample ({_sample.height:,} rows, ~{_exploded.height:,} "
                f"propositions) to keep memory tractable. "
                "Points above the diagonal indicate over-confidence (agent assigns higher "
                "probability than warranted); points below indicate under-confidence._"
            ),
        ]
    )


@app.cell
def _(df, alt, mo, np, pl):
    """Figure 4: threshold-swept recall across decision thresholds 0.3–0.7.

    **Analytical purpose (threshold robustness):**
    The simulator uses a fixed gate_threshold to label a proposition as 'recalled'.
    This figure asks whether policy rankings are stable across alternative threshold
    choices.  If a policy's advantage over hard_gate depends critically on a
    particular threshold, the finding is fragile.

    **Falsification route:** If the best-performing policy changes with threshold,
    any policy comparison at a single threshold overstates certainty.

    Recall at threshold t is computed per row from stored final_alpha / final_beta /
    ground_truth and then averaged over seeds and other nuisance parameters.
    """
    _thresholds = [0.3, 0.4, 0.5, 0.6, 0.7]
    _rows4: list[dict] = []  # type: ignore[type-arg]

    for _r in df.iter_rows(named=True):
        _alpha = np.array(_r["final_alpha"], dtype=np.float64)
        _beta_v = np.array(_r["final_beta"], dtype=np.float64)
        _truth = np.array(_r["ground_truth"], dtype=np.int64)
        _posterior = _alpha / (_alpha + _beta_v)
        _n_pos = int((_truth == 1).sum())
        if _n_pos == 0:
            continue
        for _t in _thresholds:
            _rec = float(((_posterior >= _t) & (_truth == 1)).sum()) / _n_pos
            _rows4.append(
                {
                    "policy_label": _r["policy_label"],
                    "bias_model": _r["bias_model"],
                    "noise_level": _r["noise_level"],
                    "threshold": float(_t),
                    "recall_at_t": _rec,
                }
            )

    _recalls4 = pl.DataFrame(_rows4)

    _agg4 = (
        _recalls4.group_by(["policy_label", "bias_model", "threshold"])
        .agg(pl.col("recall_at_t").mean().alias("mean_recall"))
        .sort(["bias_model", "policy_label", "threshold"])
    )

    _fig4 = (
        alt.Chart(_agg4)
        .mark_line(point=True)
        .encode(
            x=alt.X("threshold:Q", title="Decision threshold", scale=alt.Scale(domain=[0.25, 0.75])),
            y=alt.Y("mean_recall:Q", title="Mean recall at threshold", scale=alt.Scale(zero=False)),
            color=alt.Color("policy_label:N", title="Policy"),
            facet=alt.Facet("bias_model:N", columns=3, title="Bias model"),
        )
        .properties(width=220, height=180, title="Figure 4 — Threshold-swept recall per policy")
        .resolve_scale(y="shared")
    )

    mo.vstack(
        [
            mo.md("## Figure 4: Threshold-swept recall [robustness check]"),
            _fig4,
            mo.md(
                f"_Recall recomputed at thresholds {{0.3, 0.4, 0.5, 0.6, 0.7}} from stored "
                "final_alpha/final_beta/ground_truth per row. "
                f"N_threshold_rows = {_recalls4.height:,}; aggregated to {_agg4.height} "
                "mean-recall cells. "
                "Stable ordering across thresholds indicates that policy rankings from "
                "Figures 1–2 (which use a fixed gate_threshold per policy) are robust. "
                "Crossing lines would suggest threshold-dependent advantages._"
            ),
        ]
    )


@app.cell
def _(df, alt, mo, pl):
    """Figure 5: shared-vs-independent bias delta in recall, per policy.

    **Analytical purpose (P3):**
    P3 predicts that shared (correlated) bias across signals should reduce recall
    relative to independent noise of the same magnitude, because correlated errors
    cannot be averaged away across actions.  This figure computes
    delta = recall(shared) - recall(independent) and plots it against noise_level.

    **Falsification route:** If delta is consistently near zero or positive for
    most policies, correlated bias is not the performance bottleneck and P3 is
    not supported.  If delta is strongly negative only at low noise, it suggests
    bias matters more when the signal-to-noise ratio is already unfavourable.
    """
    _sub5 = df.filter(pl.col("bias_model").is_in(["shared", "independent"]))

    # Average over all nuisance parameters (n_props, budget_multiple, prior_true)
    # within each (policy_label, noise_level, bias_model, seed) cell.
    _agg5_pre = _sub5.group_by(["policy_label", "noise_level", "bias_model", "seed"]).agg(pl.col("recall").mean())

    _pivot5 = _agg5_pre.pivot(
        on="bias_model",
        index=["policy_label", "noise_level", "seed"],
        values="recall",
    ).with_columns((pl.col("shared") - pl.col("independent")).alias("delta"))

    _agg5 = (
        _pivot5.group_by(["policy_label", "noise_level"])
        .agg(pl.col("delta").mean().alias("mean_delta"))
        .sort(["policy_label", "noise_level"])
    )

    _fig5 = (
        alt.Chart(_agg5)
        .mark_line(point=True)
        .encode(
            x=alt.X("noise_level:Q", title="Noise level (p_pos − p_neg)", scale=alt.Scale(zero=False)),
            y=alt.Y("mean_delta:Q", title="Recall(shared) − Recall(independent)"),
            color=alt.Color("policy_label:N", title="Policy"),
        )
        .properties(
            width=380,
            height=260,
            title="Figure 5 — Shared-vs-independent recall delta per policy [P3]",
        )
    )

    _zero = alt.Chart(pl.DataFrame({"y": [0.0]})).mark_rule(strokeDash=[4, 4], color="gray").encode(y="y:Q")

    mo.vstack(
        [
            mo.md("## Figure 5: Shared-vs-independent recall delta [P3]"),
            alt.layer(_zero, _fig5),
            mo.md(
                f"_Delta = mean_recall(bias_model=shared) − mean_recall(bias_model=independent), "
                f"averaged over 100 seeds per (policy_label, noise_level) cell. "
                f"N_delta_cells = {_agg5.height}. "
                "Dashed line = zero delta. Negative delta (below the line) means shared "
                "bias hurts recall relative to independent noise, supporting P3. "
                "Policies above zero exhibit recall gains from correlation — e.g. if "
                "correlated bias consistently points toward true propositions._"
            ),
        ]
    )


@app.cell
def _(df, alt, mo, pl):
    """Figure 6: r-curve — recall as a function of revisit probability.

    **Analytical purpose (P4, reframing test):**
    The r-curve reframes the hard_gate vs constant_revisit comparison as a
    continuous question: 'what is the optimal revisit probability r?'
    hard_gate(1,1) appears as r = 0 (no revisits); constant_revisit at r ∈
    {0.05, 0.1, 0.2, 0.3} fill the rest of the curve.  P4 predicts that recall
    rises with r up to some optimal, then may plateau or fall if revisits crowd
    out exploratory actions.

    hard_gate(Beta(5,5)) is excluded because it represents a separate prior
    manipulation, not a point on the revisit curve.

    **Falsification route:** A flat or declining r-curve would suggest revisits
    do not help, falsifying P4.  A peak at intermediate r would indicate
    diminishing returns from over-revisiting.
    """
    _sub6 = (
        df.filter(
            pl.col("policy").is_in(["hard_gate", "constant_revisit"])
            & ~((pl.col("policy") == "hard_gate") & (pl.col("prior_alpha") == 5.0))
        )
        # hard_gate already has revisit_prob = 0.0
    )

    _agg6 = (
        _sub6.group_by(["revisit_prob", "noise_level", "bias_model"])
        .agg(pl.col("recall").mean().alias("mean_recall"))
        .sort(["bias_model", "noise_level", "revisit_prob"])
        .with_columns(pl.col("noise_level").cast(pl.Utf8).alias("noise_level_str"))
    )

    _fig6 = (
        alt.Chart(_agg6)
        .mark_line(point=True)
        .encode(
            x=alt.X("revisit_prob:Q", title="Revisit probability r  (0 = hard_gate)"),
            y=alt.Y("mean_recall:Q", title="Mean recall", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "noise_level_str:O",
                title="Noise level",
                sort=sorted(_agg6["noise_level_str"].unique().to_list()),
            ),
            facet=alt.Facet("bias_model:N", columns=3, title="Bias model"),
        )
        .properties(width=220, height=180, title="Figure 6 — R-curve: recall vs revisit probability [P4]")
        .resolve_scale(y="shared")
    )

    mo.vstack(
        [
            mo.md("## Figure 6: R-curve — recall vs revisit probability [P4, reframing]"),
            _fig6,
            mo.md(
                f"_Policies: hard_gate(Beta(1,1)) at r=0.0 and constant_revisit at "
                f"r ∈ {{0.05, 0.10, 0.20, 0.30}}. hard_gate(Beta(5,5)) excluded (separate "
                "prior manipulation). "
                f"N_rcurve_cells = {_agg6.height} (revisit_prob × noise_level × bias_model). "
                "Colour encodes noise level (ordinal) so per-noise r-curves are visually "
                "distinct. An upward slope supports P4; a peak followed by decline suggests "
                "revisit saturation; a flat curve indicates revisits neither help nor hurt._"
            ),
        ]
    )


if __name__ == "__main__":
    app.run()
