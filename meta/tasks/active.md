<!-- Task queue. Use /science:tasks to manage. -->

## [t001] Build H01 simulator engine (policies + metrics + sweep + CLI)
- type: implementation
- priority: P1
- status: in_progress
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting, question:01-bioinformatics-generalizability]
- created: 2026-04-24

Implement the engine per `specs/h01-simulator.md`: Beta-Bernoulli signal model with configurable prior and three bias modes (none / independent / shared); three policies (hard-gate, constant-revisit, Thompson); recall / Brier / regret metrics; grid sweep producing a list-column parquet (allocations + final α, β arrays); Click CLI with a benchmark gate that validates runtime against the single-digit-minute budget. Quality gates: ruff check + format-check + pyright. Plan: `doc/plans/2026-04-24-h01-simulator.md`. Running the full sweep, populating notebook figures, and writing the interpretation are deliverables of [t002].

## [t002] Run H01 sweep and publish interpretation
- type: analysis
- priority: P1
- status: proposed
- aspects: [hypothesis-testing, software-development]
- related: [hypothesis:h01-stochastic-revisiting, question:01-bioinformatics-generalizability]
- blocked_by: [t001]
- created: 2026-04-24

Execute the engine from [t001] on the default grid and produce the deliverables `specs/h01-simulator.md` names as required: `results/h01-simulator/sweep-<date>.parquet` with full seed count; `notebooks/h01_simulator_results.py` populated with headline figures (recall-vs-noise per policy, reliability diagram, threshold-swept recall, `shared`-vs-`independent` bias comparison); `doc/interpretations/h01-simulator-<date>.md` tying sweep findings to each H01 proposition (P1-P5). Plan to be written after t001 closes, informed by observed engine behaviour.
