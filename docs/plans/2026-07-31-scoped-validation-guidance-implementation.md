# Scoped Validation Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Keep the
> downstream sweep serial because it mutates 20 Dropbox-backed repositories and
> maintains one recovery ledger.

**Goal:** Make scoped validation the default agent behavior in the Science
toolkit, new-project scaffold, and every existing Science project guide in the
approved migration inventory.

**Architecture:** Change documentation only. The toolkit guide gets detailed
CLI/model full-suite triggers; the scaffold and project guides get
project-neutral scoped-first guidance while retaining their local commands and
warnings. Existing guides are migrated with one local commit per downstream
repository and no pushes.

**Tech Stack:** Markdown, Git, pytest documentation guards, POSIX shell
inspection commands.

## Global Constraints

- Bare `pytest` continues to mean the full suite; do not change pytest
  configuration, markers, collection, or CI.
- Do not add template propagation or managed-block machinery.
- Preserve every project's commands, special validation requirements, and
  known-failure warnings.
- Use `~/d/` paths in documentation.
- Do not edit or create an `AGENTS.md` for `~/d/science-commons`.
- Exclude transient registry entries under `/tmp`.
- Require every downstream checkout to remain on `main` and at its recorded
  starting commit until its guide-only commit is created.
- Commit locally in each repository and push nothing.
- Never run two test or validation suites concurrently in one worktree.
- Do not run full CLI, model, or downstream application suites for this
  Markdown-only change.

## Migration Inventory

| Scope | Files | Git repositories / commit shape |
| --- | ---: | --- |
| Toolkit policy, scaffold, and registered meta guide: `AGENTS.md`, `templates/agents-md.md`, `meta/AGENTS.md` | 3 | One toolkit worktree and one toolkit implementation commit |
| Persistent registered downstream guides, excluding toolkit `meta` and guide-less `science-commons` | 18 | 18 repositories, one `AGENTS.md` commit in each |
| Known unregistered adopters: `~/d/cats/AGENTS.md`, `~/d/3d-attention-bias/AGENTS.md` | 2 | 2 repositories, one `AGENTS.md` commit in each |

This is 21 project guides plus the toolkit root guide and scaffold: 23 files in
21 Git repositories. The downstream sweep is 20 repositories.

All downstream repositories are physically Dropbox-backed. The two `~/d/`
adopter paths are symlinks into `/mnt/ssd/Dropbox/` as well. Branch and commit
rechecks therefore guard against concurrent checkout movement, not merely dirty
files.

## Policy Text

Use these exact shared blocks, adapting only the command-specific lead-in named
in the inventory below.

### Application-test block

```markdown
Use the narrowest test selection that covers the changed behavior while
iterating. Before handoff, run the affected tests plus adjacent integration or
contract guards. Run the full application suite only when changes affect shared
configuration, dependencies, schemas, or cross-cutting behavior; touch multiple
subsystems; produce unexpected broader effects; prepare a release; or when
explicitly requested. Do not take a full-suite baseline for a localized change,
and do not repeat a passing full run after a fast-forward integration when the
exact commit and its base are unchanged.
```

### Science-structure block

```markdown
Run Science structural validation once before handoff when Science-managed data,
configuration, references, workflows, or generated artifacts changed. Use the
narrowest project-specific check that covers the change while iterating. Also
run full project validation for shared schema or configuration changes,
cross-cutting changes, releases, unexpected broader effects, or an explicit
request. Do not repeat a passing validation after a fast-forward integration
when the exact commit and its base are unchanged.
```

### Structural-validation addendum

Use this shorter form only where a guide already has a separate application
testing section:

```markdown
Run Science structural validation once before handoff when Science-managed data,
configuration, references, workflows, or generated artifacts changed. Do not
repeat a passing structural validation after a fast-forward integration when
the exact commit and its base are unchanged.
```

### Workflow block

```markdown
Use the narrowest lint, dry-run, or smoke-test selection that covers the changed
workflow while iterating. Before handoff, run the affected checks plus adjacent
workflow guards. Run the full workflow or application suite only when changes
affect shared configuration, dependencies, schemas, or cross-cutting behavior;
touch multiple subsystems; produce unexpected broader effects; prepare a
release; or when explicitly requested. Run Science structural validation once
before handoff when Science-managed data, configuration, references, workflows,
or generated artifacts changed. Do not repeat a passing full run after a
fast-forward integration when the exact commit and its base are unchanged.
```

### Combined scaffold block

```markdown
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
```

---

### Task 1: Capture the baseline and recovery ledger

**Files:**
- Create temporarily: `/tmp/scoped-validation-migration.tsv`
- Read: `~/.config/science/config.yaml`
- Read: the 20 downstream `AGENTS.md` files listed in Tasks 3 and 4

**Interfaces:**
- Produces: a tab-separated recovery ledger with repository, starting commit,
  migration commit, and status columns.
- Produces: a green 42-case toolkit documentation-guard baseline.

- [ ] **Step 1: Verify the toolkit worktree state**

Run from the toolkit worktree root:

```bash
git branch --show-current
git status --short
git log -3 --oneline
```

Expected: branch `docs/scoped-validation-guidance`; no uncommitted changes; the
two design commits and this implementation-plan commit are present.

- [ ] **Step 2: Run the documentation guards before editing**

Run from `science/` inside the toolkit worktree:

```bash
uv run --frozen pytest \
  tests/test_command_docs.py::test_active_tooling_docs_drop_relative_editable_workarounds \
  tests/test_agent_assets.py::test_agents_md_template_has_no_at_core_includes \
  tests/test_curate_agents_md.py \
  tests/test_acceptance_managed_artifacts.py \
  tests/test_no_raw_task_file_reads_in_docs.py
```

Expected: 42 tests pass. Stop and investigate any baseline failure before
editing; do not attribute an existing failure to the new prose.

- [ ] **Step 3: Audit all downstream branches, commits, and target files**

For each path below, run the three commands with `project_repo` set to that
repository:

```bash
git -C "$project_repo" branch --show-current
git -C "$project_repo" rev-parse HEAD
git -C "$project_repo" status --short -- AGENTS.md
```

Repositories:

```text
~/d/protein-landscape
~/d/natural-systems
~/d/cancer/cancer-types/multiple-myeloma
~/d/cancer/meta
~/d/cancer/mechanisms/evolution
~/d/cancer/conditions/pre-cancer
~/d/cancer/data-sources/cbioportal
~/d/seq-feats
~/d/health/meta
~/d/health/comparisons/pan-disease
~/d/health/processes/cycles
~/d/cancer/cancer-types/ovarian
~/d/cancer/cancer-types/head-and-neck
~/d/cancer/cancer-types/prostate
~/d/cancer/cancer-types/breast
~/d/health/processes/immunity
~/d/health/processes/post-acute-infection
~/d/cancer/therapeutics
~/d/cats
~/d/3d-attention-bias
```

Expected: every branch is `main` and every `AGENTS.md` is clean. Record the
20 starting commits. If a target guide is dirty or a checkout is not on `main`,
stop and request direction.

- [ ] **Step 4: Create the temporary recovery ledger**

Use `apply_patch` to create `/tmp/scoped-validation-migration.tsv` with this
header and one row per repository using the exact hashes from Step 3:

```text
repository	starting_commit	migration_commit	status
```

Set `migration_commit` empty and `status` to `pending`. After each downstream
commit, update that row with the new commit hash and `complete`. The starting
and migration hashes make an interrupted sweep auditable and are the rollback
handle: revert a completed guide with its recorded migration commit rather than
resetting a repository.

### Task 2: Update and verify toolkit-owned guidance

**Files:**
- Modify: `AGENTS.md`, section `Validation / tests`
- Modify: `templates/agents-md.md`, section `Validation`
- Modify: `meta/AGENTS.md`, section `Validation`

**Interfaces:**
- Produces: the canonical detailed toolkit policy.
- Produces: the generic policy inherited by newly created/imported projects.
- Produces: the migrated policy for the registered `meta` project without a
  separate downstream commit.

- [ ] **Step 1: Generalize the toolkit validation section**

In `AGENTS.md`, keep the full CLI/model commands and marker explanation, then
replace the current subagent-only recommendation with:

```markdown
During development, run the smallest test node, module, or package selection
that exercises the changed behavior. Before handoff, run the affected modules
plus adjacent integration or contract guards, along with Ruff or pyright when
the changed code falls under those checks.

Run the full CLI or model suite only when shared pytest configuration or
fixtures changed; dependencies, packaging, or supported Python behavior
changed; schemas, serialization, source resolution, task or project graphs,
validation, or output contracts changed across subsystem boundaries; multiple
unrelated subsystems changed; scoped results reveal unexpected cross-boundary
effects; the work prepares a release; or the user explicitly requests it. The
model suite is relevant when model or schema code changes, or when CLI code
depends on changed model behavior.

Do not take a full-suite baseline for a localized change. Do not repeat a
passing full run after a fast-forward integration when the tested commit and its
base are unchanged.
```

Update the runtime paragraph from `~10 min` to `about seven minutes`, citing the
observed 6:42–7:24 range. Preserve these operational rules in the same section:

- a full run exceeds the default 120-second command timeout;
- when a full-suite trigger applies, the top-level agent owns it and passes an
  explicit long timeout;
- subagents run scoped selections because a yielded background run will not
  reliably resume; and
- two suites never run concurrently in one worktree.

- [ ] **Step 2: Update the scaffold**

Insert the combined scaffold block under `## Validation` in
`templates/agents-md.md`, immediately before the existing
`bash validate.sh --verbose` command. Do not edit the template header, worktree
section, task guidance, or managed load-bearing-constraints block.

- [ ] **Step 3: Update the registered meta guide**

Insert the combined scaffold block under `## Validation` in `meta/AGENTS.md`,
immediately before its existing `uv run --frozen science validate --verbose`
command. Keep the command and all meta-specific working-directory, convention,
and task guidance unchanged.

- [ ] **Step 4: Check the toolkit diff**

Run from the toolkit worktree root:

```bash
git diff --check
git diff -- AGENTS.md templates/agents-md.md meta/AGENTS.md
```

Confirm only validation guidance changed, all full-suite commands remain, and
the template contains no instruction to open raw task files.

- [ ] **Step 5: Run the post-edit documentation guards**

Run from `science/` inside the toolkit worktree:

```bash
uv run --frozen pytest \
  tests/test_command_docs.py::test_active_tooling_docs_drop_relative_editable_workarounds \
  tests/test_agent_assets.py::test_agents_md_template_has_no_at_core_includes \
  tests/test_curate_agents_md.py \
  tests/test_acceptance_managed_artifacts.py \
  tests/test_no_raw_task_file_reads_in_docs.py
```

Expected: 42 tests pass.

- [ ] **Step 6: Commit the toolkit guidance**

```bash
git add AGENTS.md templates/agents-md.md meta/AGENTS.md
git commit -m "docs: adopt scoped validation guidance"
```

### Task 3: Pilot the downstream migration

**Files:**
- Modify: `~/d/cats/AGENTS.md`
- Modify: `~/d/cancer/cancer-types/multiple-myeloma/AGENTS.md`
- Update temporarily: `/tmp/scoped-validation-migration.tsv`

**Interfaces:**
- Produces: one software-project example and one complex workflow-project
  example for reviewing the migration wording before the remaining sweep.

- [ ] **Step 1: Recheck both pilot repositories**

For each pilot, confirm `main`, confirm HEAD equals its ledger starting commit,
and confirm `AGENTS.md` remains clean. Stop if any check differs.

- [ ] **Step 2: Update `cats`**

Insert the application-test block at the start of `## Testing`. Under
`### Validation`, insert the structural-validation addendum before the existing
Science commands.

Preserve the pytest, Ruff, formatting, pyright, and Science command list.

- [ ] **Step 3: Verify and commit `cats`**

```bash
git -C ~/d/cats diff --check
git -C ~/d/cats diff -- AGENTS.md
git -C ~/d/cats add AGENTS.md
git -C ~/d/cats commit -m "docs: adopt scoped validation guidance"
```

Record the new HEAD and `complete` in the `cats` ledger row.

- [ ] **Step 4: Update `multiple-myeloma`**

At the start of `## Validation`, insert:

```markdown
Use the narrowest check that covers the changed behavior while iterating.
Before handoff, run the affected tests and validation commands plus adjacent
guards. Run the full pytest suite only when changes affect shared configuration,
dependencies, schemas, or cross-cutting behavior; touch multiple subsystems;
produce unexpected broader effects; prepare a release; or when explicitly
requested. Do not take a full-suite baseline for a localized change, and do not
repeat a passing full test or validation run after a fast-forward integration
when the exact commit and its base are unchanged.

Run Science structural validation once before handoff when Science-managed data,
configuration, references, workflows, or generated artifacts changed.
```

Preserve the project-wide Ruff/pre-commit requirements, Snakemake lint,
boundary checks, 20-minute runtime warning, and six known pytest failures.

- [ ] **Step 5: Verify and commit `multiple-myeloma`**

```bash
git -C ~/d/cancer/cancer-types/multiple-myeloma diff --check
git -C ~/d/cancer/cancer-types/multiple-myeloma diff -- AGENTS.md
git -C ~/d/cancer/cancer-types/multiple-myeloma add AGENTS.md
git -C ~/d/cancer/cancer-types/multiple-myeloma commit -m "docs: adopt scoped validation guidance"
```

Record the new HEAD and `complete` in the pilot's ledger row. Review both pilot
diffs together before proceeding; no application or Science full-suite run is
required for these Markdown-only edits.

### Task 4: Migrate the remaining 18 downstream guides

**Files:**
- Modify: the 18 `AGENTS.md` files in the table below
- Update temporarily: `/tmp/scoped-validation-migration.tsv`

**Interfaces:**
- Consumes: the approved pilot wording and recovery ledger.
- Produces: one local guide-only commit per remaining repository.

| Guide | Policy block | Insertion point / local content to preserve |
| --- | --- | --- |
| `~/d/protein-landscape/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the separate expensive-artifact command and warning |
| `~/d/natural-systems/AGENTS.md` | Application-test plus structural-validation addendum | Start of `## Testing Guidelines`; put the addendum at start of `### Validation`; preserve Vitest, build, workflow, and graph commands |
| `~/d/cancer/meta/AGENTS.md` | Science-structure | Start of `## Validation Before Commit`; preserve validate, graph-build, peers-check, and graph-validate commands |
| `~/d/cancer/mechanisms/evolution/AGENTS.md` | Science-structure | Start of `## Graph Refresh Order`; preserve the toolkit-owned guardrail statement and child-then-meta graph order |
| `~/d/cancer/conditions/pre-cancer/AGENTS.md` | Science-structure | Start of `## Validation Before Commit`; preserve validate and graph commands |
| `~/d/cancer/data-sources/cbioportal/AGENTS.md` | Workflow | Start of `## Validation`; preserve Science, Snakemake lint, Ruff, and format commands plus the mtime idempotency contract |
| `~/d/seq-feats/AGENTS.md` | Combined scaffold | Start of `## Validation`; preserve both existing structural-validation commands |
| `~/d/health/meta/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the toolkit guardrail explanation |
| `~/d/health/comparisons/pan-disease/AGENTS.md` | Workflow | Start of `## Validation`; preserve Science validation, pytest smoke tests, Snakemake dry-run, and cwd warning |
| `~/d/health/processes/cycles/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the existing command |
| `~/d/cancer/cancer-types/ovarian/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the existing command |
| `~/d/cancer/cancer-types/head-and-neck/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the existing command |
| `~/d/cancer/cancer-types/prostate/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the existing command |
| `~/d/cancer/cancer-types/breast/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the existing command |
| `~/d/health/processes/immunity/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the existing command |
| `~/d/health/processes/post-acute-infection/AGENTS.md` | Science-structure | Start of `## Validation`; preserve the existing command and other project-specific guidance |
| `~/d/cancer/therapeutics/AGENTS.md` | Science-structure | Start of `## Validation Before Commit`; preserve validate and graph-build commands |
| `~/d/3d-attention-bias/AGENTS.md` | Combined scaffold | Start of `## Validation`; preserve both existing structural-validation commands and GPU sequencing rules |

For the row marked “Application-test plus structural-validation addendum,” use
the exact addendum defined under `Policy Text`.

- [ ] **Step 1: Edit and commit each guide serially**

For each table row:

1. Confirm branch is `main`.
2. Confirm HEAD equals the row's ledger starting commit.
3. Confirm `AGENTS.md` is clean.
4. Apply only the mapped policy block at the mapped insertion point.
5. Run `git diff --check` and inspect `git diff -- AGENTS.md`.
6. Confirm the branch and starting HEAD again immediately before committing.
7. Commit only `AGENTS.md` with message
   `docs: adopt scoped validation guidance`.
8. Record the migration commit and `complete` in the ledger before moving to
   the next repository.

Do not batch `git add`, `git commit`, or branch checks across repositories.

- [ ] **Step 2: Audit the completed downstream ledger**

Confirm all 20 rows are `complete`, every starting commit remains recorded, and
every migration commit resolves in its named repository. If the sweep stopped
partway, leave pending repositories untouched and use the ledger to report the
exact completed boundary. Roll back only with `git revert` of the recorded
migration commits; never reset a repository to the starting hash.

### Task 5: Final verification and handoff

**Files:**
- Verify: `AGENTS.md`, `templates/agents-md.md`, `meta/AGENTS.md`
- Verify: all 20 downstream `AGENTS.md` files
- Read temporarily: `/tmp/scoped-validation-migration.tsv`

**Interfaces:**
- Produces: evidence that all 23 guidance files carry the intended policy and
  that each downstream repository has one recoverable local commit.

- [ ] **Step 1: Re-run the toolkit guard block**

Run from `science/` inside the toolkit worktree:

```bash
uv run --frozen pytest \
  tests/test_command_docs.py::test_active_tooling_docs_drop_relative_editable_workarounds \
  tests/test_agent_assets.py::test_agents_md_template_has_no_at_core_includes \
  tests/test_curate_agents_md.py \
  tests/test_acceptance_managed_artifacts.py \
  tests/test_no_raw_task_file_reads_in_docs.py
```

Expected: 42 tests pass.

- [ ] **Step 2: Verify the toolkit implementation commit**

```bash
git show --stat --oneline HEAD
git status --short
```

Expected: the implementation commit changes exactly `AGENTS.md`,
`templates/agents-md.md`, and `meta/AGENTS.md`; the worktree is clean.

- [ ] **Step 3: Verify every downstream migration commit**

For each ledger row, run:

```bash
git -C "$project_repo" show --stat --oneline "$migration_commit"
git -C "$project_repo" status --short -- AGENTS.md
```

Expected: each migration commit changes only `AGENTS.md`, and every target guide
is clean afterward. Unrelated pre-existing dirty files may remain untouched.

- [ ] **Step 4: Verify policy coverage and preserved exceptions**

Inspect all 23 changed guidance files and confirm:

- scoped checks are the iteration default;
- full suites have explicit triggers;
- Science structural validation is run once before handoff when managed
  artifacts change;
- unchanged fast-forward integrations are not revalidated;
- the toolkit still documents both full suites, opt-in markers, the long
  timeout, top-level ownership of triggered full runs, subagent backgrounding,
  and no concurrent suites;
- `multiple-myeloma` still documents its six pre-existing failures and
  20-minute runtime; and
- no local command, known warning, or managed constraints block was removed.

- [ ] **Step 5: Report without pushing**

Report the toolkit commit, the 20 downstream migration commits, the 42-test
baseline and post-edit results, and any unrelated dirty files observed. State
explicitly that no repository was pushed and that no full suite was run.
