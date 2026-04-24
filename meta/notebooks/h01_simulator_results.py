"""Marimo notebook: H01 simulator results.

Stub only — populated under [t002] from a real full-seed sweep. Planned
figures: recall-vs-noise curves per policy, reliability diagram from
final_alpha / final_beta, threshold-swept recall computed at analysis
time, and a shared-vs-independent bias comparison.
"""

import marimo

__generated_with = "stub"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell
def _(mo):
    mo.md(
        """
        # H01 Simulator Results

        Stub. See `doc/plans/2026-04-24-h01-simulator.md` and the follow-up
        task **[t002]** for how this notebook becomes real figures.
        """
    )
    return


@app.cell
def _():
    # Placeholder: load the most recent sweep parquet, compute threshold-swept
    # recall from final_alpha / final_beta, then plot with altair. Left blank
    # until the first full sweep lands.
    return


if __name__ == "__main__":
    app.run()
