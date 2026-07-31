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

The sibling `~/d/science-commons` repo is also part of the Science ecosystem,
but it is not an ordinary research project. It is the shared canonical entity
store for reusable records such as datasets and paper summaries, and future
base knowledge representations may live there. Toolkit changes that migrate or
tighten entity/source formats must include commons in compatibility and
migration checks when its files are affected.

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

The full default suite (~12k tests) takes ~10 min on this Dropbox-backed checkout
— longer than the default 120s command timeout. When you dispatch a subagent to
verify a change, have it run a scoped selection (the affected test modules plus
any guards), not the whole suite: a
foreground full run times out, auto-backgrounds, and a subagent that yields waiting on
it will not reliably resume. Reserve the full-suite run for the top-level agent, or pass
an explicit long `timeout`. Never run two suites concurrently in the same worktree — they
race on shared test-output paths.

Lint / types (from `science/`):

```bash
uv run ruff check
uv run pyright
```

Pyright is configured **once**, by `pyrightconfig.json` at the repo root. Pyright
walks up from the working directory to find it, so that one config governs no
matter which package you run from — a `[tool.pyright]` block in a package's
`pyproject.toml` would be silently ignored. It covers all three source trees
(`science/src`, `science/model/src`, `science/qa/src`) and resolves imports
against `science/.venv`, which has `science-model` and `science-qa` installed
editable. Test directories are **not** type-checked.

Widening coverage means editing `include` in that one file. Ruff, unlike pyright,
is configured per package — run it from the package you changed.

## Worktrees

Worktrees of *this* repo are safe: the `science-model` / `science-qa` uv sources
are **in-repo** (`model/`, `qa/`), so a linked worktree carries its own copies
and `uv run` resolves normally wherever the worktree lives. The `meta/` project
is safe for the same reason: its editable Science source stays within this Git
worktree.

Science-managed external consumers install this toolkit from its public Git
source, with the exact revision pinned in their `uv.lock`. Their dependency is
location-independent, so nested `.worktrees/<name>/` directories are the normal
default and support `uv sync --frozen`, tests, and `validate.sh` directly. This
rule is shipped to adopters in [`templates/agents-md.md`](templates/agents-md.md)
— mirror any change to the phrasing there.

## Conventions

Follow the project-wide rules: composition over inheritance; explicit over
defensive; fail early instead of silent fallbacks; no "legacy"/"compatibility"
layers unless asked; no `Unified` prefix on component names; no
AI-attribution trailers on commits, PRs, or comments.

## Task system

This repo has **no self-hosted task backlog** — there is no root `science.yaml`,
so do not run `science tasks` against it. Toolkit work is tracked through the
design and implementation-plan docs under `docs/plans/`. The sibling `meta/`
project *does* self-host a `science tasks` backlog (studying this toolkit) —
see [`meta/AGENTS.md`](meta/AGENTS.md) for that.

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
