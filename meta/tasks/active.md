<!-- Task queue. Use /science:tasks to manage. -->

## [t001] Build H01 simulator for stochastic-revisiting vs hard-gating comparison
- type: implementation
- priority: P1
- status: proposed
- aspects: [software-development, hypothesis-testing]
- related: [hypothesis:h01-stochastic-revisiting, question:01-bioinformatics-generalizability]
- created: 2026-04-24

Build the simulator specified in `specs/h01-simulator.md`: Beta-Bernoulli signal model, at least three policies (hard-gate, constant-revisit, uncertainty-scaled), recall / calibration / regret metrics, and a parameter sweep that covers the defensible noise range plus a correlated-bias variant (H01 disputing-evidence path). Deliverables: `src/h01_simulator/`, `code/notebooks/h01-simulator-results.py`, sweep output under `results/h01-simulator/`, and an interpretation writeup in `doc/interpretations/`. Out of scope: any inference from simulator results to real tools — that belongs to the follow-up interpretation task.
