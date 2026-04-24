<!--
core/overview.md — curated project orientation, loaded at session start.
Length cap: ~150 lines. Keep durable. See templates/core-overview.md for full guidance.
-->

# Project Overview

## What this project is

A Science-managed meta-project sitting alongside (not inside) the Science
toolkit code. It treats the toolkit as its research object: designing,
evaluating, and evolving the knowledge model, research agent, aspects,
skills, and causal-inference tooling under the same evidence-discipline the
toolkit was built to impose on others.

## Why it exists

The toolkit has grown organically through dogfooding on external research
projects. It is now mature enough — and opinionated enough — that its own
design deserves the same scrutiny: falsifiable hypotheses about what the
model should contain, literature grounding, explicit decisions with recorded
"why", and a task queue that tracks research work alongside engineering.

## Current state

- Project just scaffolded (2026-04-23). No hypotheses, tasks, or graph yet.
- Tool code at `../science-tool/`, aspects at `../aspects/`, skills at
  `../skills/`, templates at `../templates/`, references at `../references/`.
- Recent tool work (see parent repo `git log`): entity identity model,
  ontology consumption, registry identity collision warnings, multi-project
  sync.

## Open fronts

1. **Tool development** — continues in the parent repo; design intent and
   decisions recorded here.
2. **Knowledge model audit** — does the current ontology cover scientific
   practice? (not yet started)
3. **Research-agent evaluation** — failure modes, value add, failure
   signatures. (not yet started)
4. **Literature grounding** — prior art on scientific-workflow systems and
   knowledge-graph research assistants. (not yet started)

## Domain context an outsider would miss

- This project lives **inside** the science repo at `meta/`, not as a
  sibling. `science.yaml` at `meta/science.yaml` roots the project there;
  `resolve_paths()` hangs everything off that location with no tool changes.
- The toolkit is not imported as a Python package here — it is invoked via
  `uv run --project ../science-tool science-tool ...`, driven by
  `SCIENCE_TOOL_PATH` in `.env`.
- `meta/src/` exists only to satisfy software-profile validation and is
  currently empty.
- Commits that change tool code belong to the repo root, not to `meta/`.
  Keep meta-project commits scoped to `meta/` whenever possible.

## Pointers

- Strategic plan: `README.md`
- Active tasks: `tasks/active.md`
- Hypotheses: `specs/hypotheses/`
- Decisions log: `core/decisions.md`
- Knowledge graph: `knowledge/graph.trig` (not yet built)
