<!--
core/decisions.md — load-bearing decisions and reasoning. APPEND-ONLY per
decision; supersede rather than rewrite. Length cap: ~150 lines.
See templates/core-decisions.md for full guidance.
-->

# Decisions

## D-001: Scaffold the meta-project at `meta/` inside the science repo

- **Date:** 2026-04-23
- **Status:** active
- **Decision:** The meta-project lives at `meta/science.yaml` inside the
  existing science repo rather than in a sibling repo or at the repo root.

**Why:**
The repo root already has `data/`, `docs/`, `knowledge/`, `templates/`,
`scripts/`, `tests/` serving the toolkit itself — a root-level Science
scaffold would collide. `resolve_paths()` anchors everything off whatever
directory contains `science.yaml`, so a nested project works with zero tool
changes. Co-locating keeps tool-code references as plain `../` paths and
ties meta-project history to tool history.

**Alternatives considered and rejected:**
- Sibling repo — clean separation, but meta commits drift from tool commits
  and cross-repo `../` references become fragile.
- Root-level scaffold — maximum collision with existing tool dirs.
- Modify science-tool to support out-of-root `science.yaml` — doable but
  only worth it if subdir layout hits a real limit. Start subdir; revisit
  if blocked.

**Implications:**
- Science commands must be run from `meta/` (or with `--project meta`).
- `.env` carries an absolute `SCIENCE_TOOL_PATH` so `validate.sh` works
  regardless of cwd.
- Commits that touch tool code stay scoped to the repo root on feature
  branches; meta-project commits stay scoped to `meta/`.

**Revisit if:**
- Tool operations against a nested `science.yaml` hit a path-resolution bug.
- science-tool gets split into its own repo (meta goes with it or sibling).

---

## D-002: `software` profile with embedded research layer under `doc/`

- **Date:** 2026-04-23
- **Status:** active
- **Decision:** Profile is `software`; research artifacts (hypotheses,
  literature, interpretations, discussions) live under `doc/` and
  `specs/hypotheses/` rather than using a `research`-profile layout.

**Why:**
The bulk of work is tool development, which is software. But the tool's
design warrants hypothesis-testing and literature grounding. The
software-profile scaffolder supports a research layer by populating
`doc/background/`, `doc/questions/`, `doc/interpretations/`, and
`specs/hypotheses/` while keeping the implementation root as `src/` rather
than `code/`. This matches the real shape of the work.

**Alternatives considered and rejected:**
- `research` profile — forces `code/` naming and `data/`, `models/`,
  `results/`, `papers/` directories that don't apply to a project that
  doesn't run its own experiments.
- Two Science projects (one per layer) — double bookkeeping for one body
  of work.

**Implications:**
- `meta/src/` initially held an empty placeholder; as of 2026-04-24 it holds
  shipped packages (see D-004).
- No `RESEARCH_PLAN.md`; strategic plan lives in `README.md`.
- Aspects enabled: `software-development`, `causal-modeling`,
  `hypothesis-testing`.

**Revisit if:**
- We start running actual experiments or analyses from this project
  (would justify `data/`, `results/`, `models/`).
- The empty `src/` becomes a friction point.

---

## D-003: Operational beliefs are continuous in (0, 1), never 0 or 100%

- **Date:** 2026-04-24
- **Status:** active
- **Decision:** All tool-level beliefs about propositions and hypotheses are
  represented as continuous probabilities strictly bounded away from 0 and 1.
  Decisions that require a binary choice (act or not, publish or not) are
  computed *from* those beliefs at the decision point; they do not collapse
  the underlying representation.

**Why:**
Grounded in applied Bayesian practice
(see `topic:bayesian-methods-continuous-belief`) and consistent with the
replication-crisis literature's demonstration that findings drift, replicate
at below-nominal rates, and accumulate both false and missed signals
(see `topic:analytic-flexibility-and-replication`). A continuous
representation lets the tool update smoothly on new evidence, combine
heterogeneous lines of support, and avoid locking in early mistakes that
hard-gating would enshrine. The principle is load-bearing for H01
(`hypothesis:h01-stochastic-revisiting`), whose entire motivation depends on
down-weighted claims remaining recoverable rather than excluded.

**Alternatives considered and rejected:**
- Hard gating with thresholds — simpler to reason about, but enshrines early
  evidence and cannot recover from noisy warm-ups. Directly disputed by H01.
- Threshold with hysteresis — a middle path, but still discards belief state
  rather than representing it; loses the calibration property.

**Implications:**
- Calibration must be treated as a first-class, audited property, not assumed
  from the framework (see *Calibration* in the Bayesian topic).
- Priors must be specified defensibly — not arbitrary, but also not invisible
  defaults. How priors are set for proposition-level claims is an open
  design question worth tracking separately.
- UX that surfaces probabilistic outputs must communicate them honestly,
  resisting the shortcut of re-binarising for display.
- Any hypothesis or feature that would force collapse of a belief to 0 or 1
  (e.g. permanent retirement of a claim) must make the collapse explicit and
  reversible.

**Revisit if:**
- Calibration proves unachievable at useful precision on any ground-truthable
  subset, suggesting the framework is costing more than it delivers.
- Researcher users consistently misinterpret probabilistic outputs in ways
  the UX cannot correct — at which point a constrained-representation
  interface layer may be warranted even if the internal representation stays
  continuous.

---

## D-004: `meta/` ships Python packages from `src/`

- **Date:** 2026-04-24
- **Status:** active
- **Decision:** `meta/src/` hosts real, shipped Python packages that
  implement the project's research instruments. The first is
  `h01_simulator`, which tests
  `hypothesis:h01-stochastic-revisiting`; others may follow. `meta/`'s
  `pyproject.toml` is a full package manifest with runtime dependencies,
  dev dependencies, and CLI entry points.

**Why:**
The project's hypotheses require computational instruments, not prose alone.
Treating `src/` as a permanent placeholder (D-002 Implications as originally
written) became stale the moment H01's simulator was specified. Shipping
from `src/` is idiomatic for the software profile already chosen in D-002.

**Alternatives considered and rejected:**
- Put simulators at `meta/code/` — conflicts with the software-profile
  validator, which warns on top-level `code/`.
- Ship from a sibling repository — breaks the co-location argument from
  D-001 and forces cross-repo imports for project-internal code.

**Implications:**
- Notebooks live at `meta/notebooks/` (top level), not `meta/code/notebooks/`.
- `meta/AGENTS.md` reflects this as current convention.
- `uv sync` from `meta/` is the expected setup step.

**Revisit if:**
- Shipped packages become substantial enough to warrant their own
  repository (then split out, leaving `meta/` with research artifacts only).
- A researcher-facing distribution channel (PyPI) is wanted — at which
  point the single-manifest-per-package convention may need revisiting.
