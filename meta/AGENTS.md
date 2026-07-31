# science-meta — Agent Guide

## What this is

A Science project that takes the **Science toolkit itself** as its object of
study and development. The toolkit code lives at `../science/`, `../aspects/`,
`../skills/`, `../commands/`, `../templates/`, `../references/`. This project
does not contain that code — it contains the research artifacts, decisions,
hypotheses, tasks, knowledge graph, and literature review that drive it.

## Profile

`software` with an embedded research layer. Under the unified entity layout
(`layout_version: 3`), research artifacts — papers, questions, hypotheses,
interpretations, syntheses, topics, talks — live under `entities/<kind>/`.
Design and handoff docs live under `doc/plans/`.

## Working directory convention

Science commands resolve the project from `science.yaml`. Always run them
from `meta/`, or pass `--project meta` / `--project-root .` as appropriate.
The tool lives at `../science/` — `.env` points `SCIENCE_TOOL_PATH` there.

## Validation

Use the narrowest project-specific check that covers the change while iterating.
When the project has application tests, run the tests for touched code plus
adjacent integration or contract guards before handoff. Run the full application
suite only when changes affect shared configuration, dependencies, schemas, or
cross-cutting behavior; touch multiple subsystems; produce unexpected broader
effects; prepare a release; or when explicitly requested.

Run Science structural validation once before handoff when Science-managed data,
configuration, references, workflows, or generated artifacts changed. Do not
repeat a passing validation after a fast-forward integration when the exact
commit and its base are unchanged.

```bash
uv run --frozen science validate --verbose
```

## Conventions

- Paths to tool code use `../science/...` from inside `meta/`.
- Hypotheses are about the tool's design and the research-workflow model it
  implements, not about an external scientific domain.
- Literature in `entities/papers/` focuses on: research-agent design,
  knowledge-graph modelling, causal inference workflows, scientific-process
  ontologies, and related tooling (e.g. CrossCompute, Galaxy, Nextflow,
  Jupyter, Obsidian-style PKMs).
- Decisions that constrain the tool's architecture go in `core/decisions.md`.
  Decisions about meta-project process only go in `doc/plans/`.

## Task execution

- Use `/science:tasks` for backlog management.
- Tasks that touch tool code should be done from the repo root (`..`) on a
  feature branch; keep the meta-project commits scoped to `meta/`.

## Known issues / nuances

- `meta/src/` holds project-shipped Python packages (starting with
  `h01_simulator`, the H01 test instrument). See `core/decisions.md` D-004.
- `meta/pyproject.toml` is a full package manifest: it declares the shipped
  packages, registers CLI entry points (e.g. `h01-sim`), and carries runtime
  plus dev dependencies. `uv sync` from `meta/` produces a working
  environment.
- Notebooks live at `meta/notebooks/` rather than `meta/code/notebooks/` —
  the software profile warns on top-level `code/`.

<!-- BEGIN: load-bearing-constraints (managed by /science:curate; edit core/decisions.md instead) -->
## Load-bearing constraints

- **D-001:** Run science commands from `meta/` (or with `--project meta`); commits touching tool code stay scoped to the repo root, not `meta/`.
- **D-002:** Implementation root is `src/`, not `code/`; strategic plan lives in `README.md`.
- **D-003:** Tool-level beliefs are continuous probabilities strictly bounded away from 0 and 1; do not collapse beliefs to 0 or 1 in code paths, and decisions that need a binary choice compute it from the belief at the decision point.
- **D-004:** Shipped Python packages live under `meta/src/` (e.g. `h01_simulator`); notebooks under `meta/notebooks/`; `uv sync` from `meta/` is the setup step.
<!-- END: load-bearing-constraints -->

## Pointers

- Decisions: `core/decisions.md`
- Project overview: `core/overview.md`
- Active tasks: `science tasks list` (`tasks/active/`, one file per open task)
- Hypotheses: `entities/hypotheses/`
- Strategic plan: `README.md`
