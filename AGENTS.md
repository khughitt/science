# science — Agent Guide

## What this is

This is the Science **toolkit** repo: the code, skills, and templates that
implement Science, not a Science-managed research project. It contains:

- `science/` — the `science` CLI package (code under `src/science_tool/`).
- `science/model/` — the `science-model` shared Pydantic package.
- `science/qa` — the `science-qa` package.
- `skills/`, `commands/`, `templates/`, `agents/` — the Claude/Codex-facing
  surface that projects adopt.

`meta/` is a **separate** Science research project that takes this toolkit as
its object of study (hypotheses, tasks, and decisions about the toolkit's own
design). Its guide is `meta/AGENTS.md` — don't confuse the two: this file is
about writing toolkit code, `meta/AGENTS.md` is about that research project.

## Layout / packages

There is **no root `pyproject.toml`**. This repo holds nested, independently
managed packages:

- CLI / package work runs from `science/` (`science/pyproject.toml`).
- Model work runs from `science/model/` (`science/model/pyproject.toml`);
  `science` consumes it as uv source `model`, editable.

Getting this wrong (running `uv run` from the repo root) is the most common
orientation mistake — always `cd` into the package directory first.

## Validation / tests

```bash
cd science && uv run --frozen pytest
cd science/model && uv run --frozen pytest
```

Default pytest runs exclude the `snapshot` and `real_projects` markers; opt in
explicitly with `-m snapshot` or `-m real_projects` when you need them.

Lint / types (from `science/`):

```bash
uv run ruff check
uv run pyright
```

## Conventions

Follow the project-wide rules: composition over inheritance; explicit over
defensive; fail early instead of silent fallbacks; no "legacy"/"compatibility"
layers unless asked; no `Unified` prefix on component names; no
AI-attribution trailers on commits, PRs, or comments.

## Docs

- User-facing manual: `docs/user-guide/`, starting at
  [`index.md`](docs/user-guide/index.md) →
  [`big-picture.md`](docs/user-guide/big-picture.md).
- Conventions and reference material: `docs/conventions/`.
- Design docs and implementation plans: `docs/plans/`.

## Pointers

- User guide: [`docs/user-guide/index.md`](docs/user-guide/index.md)
- Conceptual map: [`docs/user-guide/big-picture.md`](docs/user-guide/big-picture.md)
- Project scaffold this repo ships to adopters: [`templates/agents-md.md`](templates/agents-md.md)
- The toolkit-as-research-object project: [`meta/AGENTS.md`](meta/AGENTS.md)
