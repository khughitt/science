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
- `meta/src/` exists as an empty placeholder to satisfy validation.
- No `RESEARCH_PLAN.md`; strategic plan lives in `README.md`.
- Aspects enabled: `software-development`, `causal-modeling`,
  `hypothesis-testing`.

**Revisit if:**
- We start running actual experiments or analyses from this project
  (would justify `data/`, `results/`, `models/`).
- The empty `src/` becomes a friction point.
