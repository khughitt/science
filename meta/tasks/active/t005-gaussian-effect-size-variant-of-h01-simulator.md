---
id: t005
project: ''
title: Gaussian effect-size variant of H01 simulator
type: ''
aspects:
- software-development
- hypothesis-testing
priority: P3
status: proposed
blocked_by: []
related:
- hypothesis:0001-stochastic-revisiting
parent: ''
group: ''
artifacts: []
findings: []
created: '2026-04-24'
completed: null
---

The current H01 simulator emits binary Bernoulli signals — H01's recall finding is bounded to that abstraction. An earlier engine handoff note flagged "Beta-Bernoulli artifact" as a candidate alternative explanation that the Bernoulli sweep cannot rule out. Build a Gaussian-effect-size variant: signals drawn from `Normal(mu, sigma)` where `mu = mu_pos` for truth=1 and `mu_neg` for truth=0; conjugate posterior is normal-normal with running mean and variance; recall analog uses a posterior-mean threshold; calibration analog is MSE between posterior mean and truth-conditional effect size.

Tests whether the H01 finding generalises beyond binary signals. If it does, D-003's continuous-belief commitment has stronger empirical footing. If not, H01 is bounded to the Beta-Bernoulli regime and the design principle needs re-examination. Likely a substantial new package alongside `h01_simulator/` (or a parallel module within it) with its own sweep, notebook, and interpretation. Plan before implementation.
