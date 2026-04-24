@core/overview.md
@core/decisions.md

# science-meta — Agent Guide

## What this is

A Science project that takes the **Science toolkit itself** as its object of
study and development. The toolkit code lives at `../science-tool/`, `../aspects/`,
`../skills/`, `../commands/`, `../templates/`, `../references/`. This project
does not contain that code — it contains the research artifacts, decisions,
hypotheses, tasks, knowledge graph, and literature review that drive it.

## Profile

`software` with an embedded research layer (`doc/background/`,
`doc/questions/`, `specs/hypotheses/`, `doc/interpretations/`).

## Working directory convention

Science commands resolve the project from `science.yaml`. Always run them
from `meta/`, or pass `--project meta` / `--project-root .` as appropriate.
The tool lives at `../science-tool/` — `.env` points `SCIENCE_TOOL_PATH` there.

## Validation

```bash
bash validate.sh --verbose
```

## Conventions

- Paths to tool code use `../science-tool/...` from inside `meta/`.
- Hypotheses are about the tool's design and the research-workflow model it
  implements, not about an external scientific domain.
- Literature in `doc/background/papers/` focuses on: research-agent design,
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

- `meta/src/` is a placeholder to satisfy software-profile validation; the
  project has no installable package of its own.
- `meta/pyproject.toml` exists only so `uv` can manage project-local tooling
  if needed — it does not ship code.
