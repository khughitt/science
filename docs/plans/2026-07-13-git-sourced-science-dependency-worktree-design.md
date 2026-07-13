# Git-Sourced Science Dependency and Worktree Design

**Date:** 2026-07-13

**Status:** Revised after design review

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

This introduces a first-use network dependency: a fresh machine or uncached
environment must fetch the Git repository before it can sync. Design review
measured roughly 30 seconds for the initial resolve and clone. uv caches the
source per machine, but a fresh no-egress sandbox or CI runner will fail until
the source has been prefetched or network access is provided. This is an
accepted tradeoff and is reported directly; Science does not fall back to a
different revision or a local checkout.

Design review verified the dependency path end to end against the real
repository: uv pinned the primary package to a Git SHA, rewrote the nested
`science-model` and `science-qa` path sources to Git subdirectories at that same
SHA, installed and ran the non-editable CLI, and included the package's non-Python
data files. The installed CLI resolves consumer templates independently of a
toolkit checkout. Review also confirmed that `SCIENCE_TOOL_PATH` has no runtime
consumer; only the current health and validation checks inspect it.

## Plugin–CLI Compatibility Contract

The Git source separates two interfaces that the editable checkout previously
kept in lockstep:

- the agent surface in `commands/` and `skills/`, delivered by the Claude plugin
  or generated Codex skills; and
- the `science` Python package selected by each consumer's `uv.lock`.

Agent commands call specific CLI subcommands, so compatibility between these
interfaces is a public contract. This change establishes a unified `0.3.0`
baseline in `science/pyproject.toml`, `.claude-plugin/plugin.json`, and the
minimum CLI version declared by `references/command-preamble.md`. The CLI gains
a root `science --version` option backed by installed package metadata.

Before an agent command invokes the CLI, the shared command preamble checks the
installed version. If it is below the declared floor, the command stops before
doing project work and reports:

```text
This Science agent command requires science >=0.3.0, but this project pins
<installed-version>. Run `uv lock --upgrade-package science && uv sync --frozen`,
then retry.
```

Generated Codex skills embed the same preamble and therefore the same floor.
Tests require every command that invokes `science` to load the shared preamble
or perform the equivalent check explicitly.

After the baseline, any change to an agent command that depends on a new or
changed CLI interface must bump the package version, plugin version, and
preamble floor together. CLI interfaces remain additive within a major version;
removing or incompatibly changing a command requires a coordinated major-version
migration. Tests assert that the three current release versions agree.

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

## Publication Boundary

`origin/main`, not local `main`, becomes the deployment boundary for downstream
projects. A toolkit commit must be pushed before any consumer lock or downstream
work may depend on it. In particular, a compatibility-changing toolkit merge is
not considered available merely because it has landed on local `main`.

The standing workflow is:

1. Commit and validate the toolkit change locally.
2. Push the required commit to `origin/main`.
3. Confirm that the commit is reachable from `origin/main`.
4. Only then upgrade consumer locks or begin downstream work that needs it.

The local checkout was 16 commits ahead of `origin/main` during design review,
so this is an active operational constraint rather than an edge case. The
editable overlay remains appropriate for deliberate cross-repository testing
before publication, but it must not become the default way ordinary consumer
work accesses current Science behavior.

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
   checkout environment workarounds, declares the minimum compatible CLI
   version, and checks `science --version` before command execution. Generated
   Codex skills are regenerated from the authoritative command inputs.
5. Tooling health and validation parse `pyproject.toml` structurally. They
   continue to require `science` in `[dependency-groups].dev`, accept a Git
   source, accept a path source that resolves within the same Git repository,
   and report an external path source as worktree-unsafe with a concrete fix.
6. `.env` and `SCIENCE_TOOL_PATH` are no longer required for normal Science
   invocation, and new scaffolds do not create the variable. During the
   downstream pass, remove only the vestigial `SCIENCE_TOOL_PATH` line. Preserve
   every other entry; delete `.env` only if no non-comment content remains.
7. The managed `validate.sh` shim remains:

   ```bash
   exec uv run science validate "$@"
   ```

   Correcting the dependency source makes this command work from both main and
   linked worktrees without a shim change.
8. The plugin manifest and Python package establish the shared `0.3.0`
   compatibility baseline. The root CLI exposes `science --version`, and tests
   keep the plugin, package, and preamble versions synchronized.

No migration guide is added. The repository has not yet been distributed to
external users, so maintaining a public migration surface would be premature.

## Downstream Conversion Pass

The live registry is `~/.config/science/config.yaml`. At design time it contains
22 persistent project entries:

- 20 external consumers with relative editable Science sources;
- `meta/`, which retains its deliberate in-repository editable source; and
- `science-commons`, which has no root `pyproject.toml` and is not an ordinary
  Science-managed consumer project.

After the toolkit change is committed, pushed, and confirmed reachable from
`origin/main`, perform a separate pass over the registry. For each of the 20
external consumers:

1. Replace the external path source with the canonical HTTPS Git source.
2. Regenerate and commit `uv.lock`.
3. Replace stale sibling-worktree guidance in `AGENTS.md` when present.
4. Remove the vestigial `SCIENCE_TOOL_PATH` assignment from `.env`, preserving
   all other content and deleting the file only if no non-comment content
   remains.
5. Run the project's normal sync and validation from its main checkout.

Record `meta/` and `science-commons` as explicit exclusions with the reasons
above. Do not silently skip registered entries. Keep each downstream repository
change separate from the toolkit commit, and do not write an unpublished local
SHA into consumer locks.

For each downstream `.env`, remove the vestigial `SCIENCE_TOOL_PATH` assignment.
Preserve files containing any other configuration, including placeholders and
secrets. Delete the file only when removing that assignment leaves no
non-comment content.

## Failure Behavior

- A missing `science` dev dependency remains a tooling-scaffold finding.
- A malformed `pyproject.toml` fails parsing and reports that error without a
  second misleading source finding.
- An external path source reports that nested worktrees are unsupported and
  points to the canonical Git-source configuration.
- A Git fetch failure remains visible as a uv error. There is no silent fallback
  to a local checkout or a different Science revision. A fresh no-egress
  environment therefore requires a pre-populated uv/Git cache.
- A plugin command whose required CLI floor exceeds the consumer's installed
  version stops in the shared preamble with the explicit Science upgrade
  command, rather than continuing to a bare Click `No such command` error.
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
4. An integration fixture that reproduces the real nested-source shape: a local
   Git repository contains the primary package in `science/` and that package
   declares an editable runtime path source in `science/model/`. A consumer
   locks the primary package from the Git repository's `science/` subdirectory.
   The test asserts that uv rewrites the nested model source to the same Git
   commit with `subdirectory=science/model`, rather than retaining a local
   editable path. It then creates a nested `.worktrees/<name>/` checkout and
   proves that frozen sync, CLI execution, tests, and validation work there.
   The fixture uses a local Git URL so it is deterministic and
   network-independent.
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
