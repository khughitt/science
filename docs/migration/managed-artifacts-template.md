# Managed-Artifacts Migration Template

> One-time migration of a Science project's `validate.sh` (and any future managed artifacts) onto the managed-artifact system per `docs/superpowers/specs/2026-04-26-managed-artifacts-long-term-design.md`.

This template guides converting a project's standalone `validate.sh` into a managed install that tracks the upstream canonical (currently v2026.04.26.2). Per-project specs adapt this template to each project's specific drift profile.

**Intended placement of per-project specs:** `<project>/doc/plans/2026-04-27-managed-artifacts-migration.md` (or your project's plan-doc convention).

---

## Prerequisites

Before starting:

- [ ] **Framework checkout up to date.** Your science framework checkout (typically at `~/d/science`) is at `main` HEAD with the managed-artifacts implementation merged (commit `a7439e3` or later) and the hook-points version bump landed (commit `90cd0e3` or later, putting the canonical at v2026.04.26.2).
- [ ] **`science-tool` is invocable.** From the project directory: `science-tool --help` succeeds. (If not, `cd <framework>/science-tool && uv sync` and ensure `science-tool` is on PATH, or use `uv run --project <framework>/science-tool science-tool ...`.)
- [ ] **Project working tree is clean.** `git status --short` is empty, OR you've decided to use `--allow-dirty` and have read its semantics. (Recommended: clean tree. If non-clean, the migration commits will entangle with your in-progress work.)
- [ ] **Drift survey done.** You've run `science-tool project artifacts check validate.sh --project-root . --json` and captured the output. Initial classification will be `untracked`.
- [ ] **Customization analysis done.** You've diffed your project's `validate.sh` against the canonical and bucketed each customization into one of:
  - **drop** — already in canonical (e.g., `.env` sourcing post Plan #7 Fix 2)
  - **config** — settable via `science.yaml` (e.g., `knowledge_profiles.local`)
  - **hook** — needs to live in `validate.local.sh` keyed to one of `pre_validation` / `extra_checks` / `post_validation`
  - **n/a** — pure lag (no real customization; just stale upstream)

If you have customizations in the **hook** bucket, you also need `validate.sh` at v2026.04.26.2 or later in the canonical (since hook dispatch points landed there). Pre-.2 migrations can only handle drop/config/n/a customizations.

---

## Pre-migration commands

Run these first; capture the output in your per-project spec under "Current state."

```bash
cd <project-root>

# Current hash
sha256sum validate.sh

# Drift status
science-tool project artifacts check validate.sh --project-root . --json

# Diff against canonical
diff -u validate.sh \
    ~/d/science/science-tool/src/science_tool/project_artifacts/data/validate.sh \
    | head -200

# Quick triage: what's in your file but not in the canonical
diff validate.sh \
    ~/d/science/science-tool/src/science_tool/project_artifacts/data/validate.sh \
    | grep '^<' | head -40
```

---

## Migration paths

Pick the path that matches your customization analysis. Most projects fit exactly one.

### Path 1 — Pure lag (no customizations)

Use when the customization analysis bucketed everything into **drop** or **n/a**.

```bash
cd <project-root>

# 1. Verify clean working tree (or accept --allow-dirty caveats).
git status --short

# 2. Remove the existing standalone validate.sh.
git rm validate.sh

# 3. Install the canonical.
science-tool project artifacts install validate.sh --project-root .

# 4. Verify status is now `current`.
science-tool project artifacts check validate.sh --project-root .
# expected: current  (validate.sh @ 2026.04.26.2)

# 5. Smoke-run the new validate.sh.
bash validate.sh
# Expect possibly more warnings/errors than before — the canonical does
# more checks (Plan #7 fixes + section 17 id-prefix). Address per project.

# 6. Commit.
git add validate.sh
git commit -m "chore(framework): migrate validate.sh to managed artifact v2026.04.26.2

Replaces standalone validate.sh body with the canonical from the
science-tool managed-artifact registry. No project-specific behavior
to preserve — pure-lag migration. New checks may surface findings;
addressing those is follow-up work, not part of this migration."
```

That's the entire path. Skip to **Post-migration verification.**

### Path 2 — Light customization (drop + config + maybe one hook)

Use when 1–3 customizations need to be preserved.

For each customization in the **drop** bucket: nothing to do (the canonical already does it).

For each customization in the **config** bucket: edit `science.yaml` to set the relevant field. Example: if your project's `LOCAL_PROFILE` was `project_specific`, set `knowledge_profiles.local: project_specific` in `science.yaml`.

For each customization in the **hook** bucket: add a function to a new `validate.local.sh` and `register_validation_hook` it.

```bash
cd <project-root>

# 1. (If config-bucket customizations) Edit science.yaml.
$EDITOR science.yaml

# 2. (If hook-bucket customizations) Create validate.local.sh.
cat > validate.local.sh <<'SH'
# Project-specific validation hooks. Sourced by the canonical validate.sh
# before validation runs.

my_extra_check() {
    # Example: project-specific check that calls back into canonical helpers.
    if [ ! -f some-required-file.txt ]; then
        warn "some-required-file.txt is missing"
    fi
}

register_validation_hook extra_checks my_extra_check
SH
chmod 0644 validate.local.sh

# 3. Remove old validate.sh and install the canonical.
git rm validate.sh
science-tool project artifacts install validate.sh --project-root .

# 4. Verify status.
science-tool project artifacts check validate.sh --project-root .
# expected: current

# 5. Smoke-run.
bash validate.sh
# Confirm your hook(s) fired by adding `info "my_extra_check ran"` to
# the function temporarily, or check echo'd warnings in output.

# 6. Commit.
git add validate.sh validate.local.sh science.yaml
git commit -m "chore(framework): migrate validate.sh to managed artifact v2026.04.26.2

Replaces standalone validate.sh body with the canonical and moves
project-specific behavior to validate.local.sh + science.yaml config.

Customizations preserved:
  - <list>: as a hook on <hook_point>
  - <list>: as science.yaml.<field>
Customizations dropped (now in canonical):
  - <list>"
```

### Path 3 — Heavy customization (multiple hooks, helpers, project-specific logic)

Use when the project has substantial logic that needs to migrate into the sidecar.

The structure is the same as Path 2; the difference is that `validate.local.sh` carries multiple helper functions and multiple registered hooks. Treat the sidecar as a normal bash module: helpers near the top, registrations at the bottom.

```bash
# validate.local.sh structure for heavy customization
# 1. Project-specific helpers (use your project's existing logic here).
extract_json_payload() {
    python3 -c '...'
}

# 2. Hook handlers — small, focused. Each calls helpers as needed.
my_pre_setup() {
    # something needed before any check runs
    ...
}

my_extra_structural_check() {
    # uses extract_json_payload internally
    ...
}

my_post_cleanup() {
    # tear-down (rare)
    ...
}

# 3. Registrations.
register_validation_hook pre_validation  my_pre_setup
register_validation_hook extra_checks    my_extra_structural_check
register_validation_hook post_validation my_post_cleanup
```

Then proceed with `git rm validate.sh` and `science-tool project artifacts install validate.sh --project-root .` as in Path 2.

### Path 4 — You're not ready / you need to defer

Pin the artifact to its currently-installed (untracked) state so the framework's loud-signal surfaces (`science-tool health`, `/status`, `/sync`) stop nagging:

```bash
science-tool project artifacts pin validate.sh \
    --project-root . \
    --rationale "Migration scheduled for <YYYY-MM-DD>; project is in active <experiment>." \
    --revisit-by <YYYY-MM-DD>
```

This is a documented, time-boxed defer — NOT an indefinite waiver. Set `--revisit-by` to a date within ~6 weeks.

---

## Post-migration verification

Run all of these. Each must pass.

```bash
cd <project-root>

# 1. check shows current.
science-tool project artifacts check validate.sh --project-root .
# expected: current  (validate.sh @ 2026.04.26.2)

# 2. JSON form for scripting.
science-tool project artifacts check validate.sh --project-root . --json
# expected: {"name": "validate.sh", "version": "2026.04.26.2", "status": "current", ...}

# 3. The canonical runs and returns sensibly.
bash validate.sh
echo "exit: $?"
# expected: 0 if your project is clean; non-zero indicates real findings
# (which canonical now surfaces; address as separate work).

# 4. (If you wrote validate.local.sh) Hooks fire.
# Add a temporary `info "<your hook> ran"` line in each hook function;
# bash validate.sh; observe the info lines; remove the temporary lines.

# 5. health.py picks it up.
science-tool health 2>&1 | grep -i validate.sh
# expected: a row showing `current`, no warnings.

# 6. Confirm shim parity (sanity).
diff <(bash validate.sh 2>&1 | head -3) \
     <(bash ~/d/science/science-tool/src/science_tool/project_artifacts/data/validate.sh 2>&1 | head -3)
# expected: identical output (modulo project-specific hook contributions).
```

---

## Rollback procedure

If any post-migration step fails or surfaces unexpected behavior:

```bash
cd <project-root>

# Option A: backup file is right there.
cp validate.sh.pre-install.bak validate.sh

# Option B: git revert.
git checkout HEAD -- validate.sh

# Verify rollback.
science-tool project artifacts check validate.sh --project-root .
# expected: untracked (back to pre-migration state).
```

If you wrote `validate.local.sh` and it caused the failure, just delete it (`rm validate.local.sh`) — the canonical works without a sidecar.

---

## Per-project spec template

Copy this section into `<project>/doc/plans/2026-04-27-managed-artifacts-migration.md` and fill in.

```markdown
# Managed-artifacts migration: <project>

**Status:** Draft / Ready / In-progress / Done
**Target version:** validate.sh @ 2026.04.26.2
**Migration path:** Path 1 / 2 / 3 (per docs/migration/managed-artifacts-template.md)

## Current state

- `validate.sh` SHA-256: `<hash>`
- Line count: `<N>`
- Last manual update: `<commit>` on `<date>`
- check verb output: `untracked` (no managed header)

## Customization analysis

| Diff hunk | Lines | Bucket | Action |
|---|---|---|---|
| `<one-line description>` | `<line range in your validate.sh>` | drop | (canonical does this; no action) |
| `<one-line description>` | `<line range>` | config | Set `science.yaml.<field>: <value>` |
| `<one-line description>` | `<line range>` | hook | Move to `validate.local.sh` as `<fn_name>` on `<hook_point>` |

## Migration plan

(Specific commands per the relevant Path in the template.)

## Verification

(The 6 post-migration verification commands. Mark ✅ as each is run.)

## Rollback ready?

(Yes/No — note the location of `.pre-install.bak`, the pre-migration commit SHA, etc.)

## Decision log

- `<date>`: `<decision>` — `<rationale>`
```

---

## Reference: what each hook point sees

Per `docs/superpowers/specs/2026-04-27-validate-hook-points.md`:

| Hook | Fires | Globals available | Typical use |
|---|---|---|---|
| `pre_validation` | After helpers/banner, before section 1. | `PROFILE`, `LOCAL_PROFILE`, `DOC_DIR`, `SPECS_DIR`, all canonical helpers (`error`, `warn`, `info`, color fns), `ERRORS=0`, `WARNINGS=0`. | Setup; declare project-specific env consumed by later hooks. |
| `extra_checks` | After all sections, before summary. | All of the above plus running `ERRORS` / `WARNINGS` counters mid-run. | Project-specific structural checks. Mutate counters to contribute to pass/fail. |
| `post_validation` | At process exit (trap EXIT). | All globals at their final state including `ERRORS` / `WARNINGS`. | Cleanup, custom reporting. |

Hook functions can call canonical helpers. To register a hook: `register_validation_hook <point> <fn_name>`. To see all registered hooks at runtime, the canonical's `dispatch_hook` walks `${SCIENCE_VALIDATE_HOOKS[<point>]}` (a space-separated list of fn names).

---

## Reference: the four motivating projects

The four projects that drove this migration's design (in increasing complexity):

| Project | Path | Customizations summary |
|---|---|---|
| mm30 | `~/d/r/mm30` | Pure lag (Path 1) |
| cbioportal | `~/d/r/cbioportal` | Light: `.env` sourcing (already in canonical → drop) (Path 2) |
| natural-systems | `~/d/natural-systems` | Light: `LOCAL_PROFILE=project_specific` (config) (Path 2) |
| protein-landscape | `~/d/protein-landscape` | Heavy: `extract_json_payload` Python helper + custom checks (Path 3) |

Each project's per-project spec lives in `<project>/doc/plans/2026-04-27-managed-artifacts-migration.md`. Drafts under review live alongside this template at `docs/migration/projects/<project>.md`.

---

## When this template gets retired

Once all in-flight projects have completed migration and the framework's onboarding docs (`commands/create-project.md`, `commands/import-project.md`) install the canonical from day one, this migration template is one-time-use scaffolding. Move it to `docs/conventions/historical/` or delete it. Until then, it's the authoritative source for downstream migrators.
