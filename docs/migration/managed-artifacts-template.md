# Managed-Artifacts Migration Template

> One-time migration of a Science project's standalone `validate.sh` onto the
> managed-artifact system.

This template guides converting a project's standalone `validate.sh` into the
managed shim that delegates to `science validate`. Per-project specifications
adapt it to each project's drift profile.

**Intended placement of per-project specs:**
`<project>/doc/plans/2026-04-27-managed-artifacts-migration.md` (or your
project's plan-doc convention).

## Prerequisites

Before starting:

- [ ] `science --help` succeeds from the project environment.
- [ ] The project working tree is clean, or the migration deliberately uses
  `--allow-dirty` after recording the existing changes.
- [ ] You ran `science project artifacts check validate.sh --project-root .
  --json` and captured the result in the project specification.
- [ ] You compared the existing `validate.sh` with the canonical artifact and
  classified each difference as either canonical behavior, configuration, or
  a project-specific check.

Project-specific checks are not extensions of `science validate`. Reusable
policy checks belong in the toolkit and require a design conversation;
genuinely project-specific checks belong in a separate project-owned command
that the project runs itself.

## Pre-migration commands

Run these first and record their output in the project specification.

```bash
cd <project-root>
sha256sum validate.sh
science project artifacts check validate.sh --project-root . --json
diff -u validate.sh \
    ~/d/science/science/src/science_tool/project_artifacts/data/validate.sh \
    | head -200
```

## Migration paths

### Path 1 — Canonical behavior or configuration only

Use when the differences are already supplied by the canonical validator or
can be represented in `science.yaml`.

```bash
cd <project-root>

# Configure any supported project settings before installing the shim.
$EDITOR science.yaml

git rm validate.sh
science project artifacts install validate.sh --project-root .
science project artifacts check validate.sh --project-root .
bash validate.sh

git add validate.sh science.yaml
git commit -m "chore(framework): migrate validate.sh to managed artifact"
```

### Path 2 — Project-specific checks

Use when a check is genuinely specific to this project. First move it into a
project-owned command, script, or workflow target with a clear name and usage
documentation. That command has no connection to `science validate`; the
project's own workflow decides when to invoke it.

Then install the managed shim:

```bash
cd <project-root>
git rm validate.sh
science project artifacts install validate.sh --project-root .
science project artifacts check validate.sh --project-root .
bash validate.sh
```

Record the new command and its invocation point in the project specification.
If the check is intended to be reusable policy instead, stop and open a toolkit
design conversation rather than retaining it as project-local behavior.

### Path 3 — Defer

If the migration cannot be completed now, pin the current artifact with a
time-boxed rationale:

```bash
science project artifacts pin validate.sh \
    --project-root . \
    --rationale "Migration scheduled for <YYYY-MM-DD>; project is in active <experiment>." \
    --revisit-by <YYYY-MM-DD>
```

## Post-migration verification

Run and record each command:

```bash
cd <project-root>
science project artifacts check validate.sh --project-root .
science project artifacts check validate.sh --project-root . --json
bash validate.sh
echo "exit: $?"
science health 2>&1 | grep -i validate.sh
diff <(bash validate.sh 2>&1 | head -3) \
     <(bash ~/d/science/science/src/science_tool/project_artifacts/data/validate.sh 2>&1 | head -3)
```

## Rollback procedure

Restore the backup created by installation or revert the migration commit, then
run `science project artifacts check validate.sh --project-root .` to confirm
the recorded pre-migration state.

## Per-project spec template

```markdown
# Managed-artifacts migration: <project>

**Status:** Draft / Ready / In-progress / Done

## Current state

- `validate.sh` SHA-256: `<hash>`
- Artifact check output: `<output>`

## Customization analysis

| Difference | Classification | Action |
|---|---|---|
| `<description>` | canonical / config / project-specific | `<action>` |

## Project-specific commands

(For each genuinely project-specific check: command name, owner, and when the
project runs it. For reusable policy, link the toolkit design conversation.)

## Verification

(Record the post-migration commands and results.)
```
