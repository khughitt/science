# Git-Sourced Science Dependency and Worktree Design

**Date:** 2026-07-13  
**Status:** Approved  
**Scope:** Science toolkit scaffolding, dependency health checks, agent guidance,
and the registered downstream projects on this machine

## Problem

Science-managed projects currently install the toolkit through an external,
relative editable uv source:

```toml
[tool.uv.sources]
science = { path = "../science/science", editable = true }
```

The path is resolved from the consumer checkout. A linked worktree under the
preferred `.worktrees/<name>/` location is two directory levels deeper, so the
same source entry resolves to a nonexistent path. `uv run`, the pre-commit
hook, `validate.sh`, and tests then fail before they can run.

The current guidance recommends sibling worktrees at the same filesystem depth
as the main checkout. That preserves the relative source path, but places the
worktree outside the project root used by Codex and Claude Code. Agents then
need repeated permission grants to edit the sibling worktree.

The goal is for ordinary nested worktrees to support the complete project
toolchain without sandbox exceptions or environment-routing workarounds.

## Decision

External Science-managed projects will consume the `science` distribution from
the public Science Git repository rather than from a relative editable path:

```toml
[dependency-groups]
dev = ["science"]

[tool.uv.sources]
science = { git = "https://github.com/khughitt/science.git", subdirectory = "science" }
```

The tracked `uv.lock` is the exact revision pin. `pyproject.toml` identifies the
source repository but does not duplicate the resolved commit SHA. This follows
uv's normal Git-dependency model: an existing lock retains its selected commit
until Science is upgraded explicitly.

HTTPS is the canonical transport because the repository is public. It avoids
requiring SSH credentials in agent sandboxes and CI.

## Dependency Operations

Normal project operations remain unchanged:

```bash
uv sync --frozen
uv run science health
bash validate.sh --verbose
```

Advance a consumer project to the latest compatible Science commit explicitly:

```bash
uv lock --upgrade-package science
uv sync --frozen
bash validate.sh --verbose
```

No update helper is added initially. A helper that only wraps this stable uv
command would add another maintained surface without removing meaningful
complexity.

When work intentionally needs uncommitted changes from the local toolkit,
overlay the local package for that invocation without changing the consumer's
manifest or lock:

```bash
uv run --with-editable ~/d/science/science <command>
```

This is an explicit local-development exception, not the default dependency
configuration.

## Monorepo Exception

A path source is valid when the source and consumer are in the same Git
repository. Such a source moves with the linked worktree and does not have the
external path-depth failure.

The `meta/` research project is the concrete exception in this repository:

```toml
[tool.uv.sources]
science = { path = "../science", editable = true }
```

`meta/` retains that source so toolkit worktrees test the matching in-worktree
Science code. Health and validation checks must distinguish this in-repository
case from an external relative path instead of rejecting every path source.

## Toolkit Changes

The implementation updates the authoritative surfaces together:

1. `commands/create-project.md`, `commands/import-project.md`, and
   `references/project-structure.md` install Science from the canonical Git
   source and commit the resulting lock.
2. `templates/agents-md.md` recommends nested `.worktrees/` and explains that
   the Git source makes them location-independent. The sibling-worktree and
   `--no-verify` workarounds are removed.
3. The root `AGENTS.md` mirrors the new consumer-project rule while preserving
   its explanation that this toolkit's in-repository package sources are safe.
4. `references/command-preamble.md` removes the `UV_PROJECT=$MAIN` and main
   checkout environment workarounds. Generated Codex skills are regenerated
   from the authoritative command inputs.
5. Tooling health and validation parse `pyproject.toml` structurally. They
   continue to require `science` in `[dependency-groups].dev`, accept a Git
   source, accept a path source that resolves within the same Git repository,
   and report an external path source as worktree-unsafe with a concrete fix.
6. `.env` and `SCIENCE_TOOL_PATH` are no longer required for normal Science
   invocation. Existing `.env` files are not deleted or rewritten because they
   may contain unrelated project configuration.
7. The managed `validate.sh` shim remains:

   ```bash
   exec uv run science validate "$@"
   ```

   Correcting the dependency source makes this command work from both main and
   linked worktrees without a shim change.

No migration guide is added. The repository has not yet been distributed to
external users, so maintaining a public migration surface would be premature.

## Downstream Conversion Pass

The live registry is `~/.config/science/config.yaml`. At design time it contains
22 persistent project entries:

- 20 external consumers with relative editable Science sources;
- `meta/`, which retains its deliberate in-repository editable source; and
- `science-commons`, which has no root `pyproject.toml` and is not an ordinary
  Science-managed consumer project.

After the toolkit change is committed and reachable through GitHub, perform a
separate pass over the registry. For each of the 20 external consumers:

1. Replace the external path source with the canonical HTTPS Git source.
2. Regenerate and commit `uv.lock`.
3. Replace stale sibling-worktree guidance in `AGENTS.md` when present.
4. Run the project's normal sync and validation from its main checkout.

Record `meta/` and `science-commons` as explicit exclusions with the reasons
above. Do not silently skip registered entries. Keep each downstream repository
change separate from the toolkit commit, and do not write an unpublished local
SHA into consumer locks.

The downstream pass does not modify ignored `.env` files unless a project has
an independent reason to do so.

## Failure Behavior

- A missing `science` dev dependency remains a tooling-scaffold finding.
- A malformed `pyproject.toml` fails parsing and reports that error without a
  second misleading source finding.
- An external path source reports that nested worktrees are unsupported and
  points to the canonical Git-source configuration.
- A Git fetch failure remains visible as a uv error. There is no silent fallback
  to a local checkout or a different Science revision.
- `uv sync --frozen` continues to fail when the lock is absent or stale.
- An unpushed Science commit cannot be selected by normal consumers; use the
  explicit `--with-editable` overlay while developing it.

## Verification

Toolkit verification includes:

1. Unit tests for missing, malformed, Git-sourced, external-path, and same-repo
   path-source manifests.
2. Documentation tests for the canonical Git source and the absence of retired
   editable-install and sibling-worktree guidance.
3. Generated Codex skill parity checks after regeneration.
4. An integration fixture that creates a local Git repository containing a
   package in a `science/` subdirectory, locks a consumer to that Git source,
   creates a nested `.worktrees/<name>/` checkout, and proves that frozen sync,
   CLI execution, tests, and validation work there. The fixture uses a local
   Git URL so the test is deterministic and network-independent.
5. The normal toolkit gates from `science/`: pytest, Ruff, and Pyright.

During the downstream pass, every changed project runs its normal validation.
Representative shallow and deep consumer layouts also receive an actual nested
worktree smoke test. The integration fixture establishes the layout-independent
property without creating and syncing a heavyweight temporary environment for
every registered project.

## Alternatives Considered

### Pin the commit in both `pyproject.toml` and `uv.lock`

This makes the SHA more visible but requires coordinated edits to two tracked
files for every update and forces scaffolding to discover or embed a revision.
The lockfile already provides the immutable resolution record.

### Pin release tags

Release tags would provide a stronger public compatibility contract, but the
repository has no release-tag cadence yet. Release engineering is independent
of the worktree failure and is not introduced as a prerequisite.

### Route nested worktrees through the main environment

`UV_PROJECT`, `UV_NO_SYNC`, a shared `.venv`, or a tracked runner can bypass the
broken source. These approaches make dependency changes and editable project
imports easy to test against the wrong checkout, and they require every hook and
command to honor the wrapper. They mitigate the symptom rather than removing
the location-dependent dependency.

### Rewrite the path source locally in each worktree

Patching `pyproject.toml` or `uv.lock` and hiding the change with Git index flags
would make dependency edits invisible or leave every worktree dirty. It is not
an acceptable default workflow.

### Keep sibling worktrees and widen sandbox permissions

This couples project guidance to multiple agent-specific permission systems and
grants broader filesystem access than the task requires. Nested worktrees keep
the checkout, edits, and permissions within the project boundary.
