# Scoped Validation Guidance Design

## Goal

Reduce avoidable validation time for agents working on the Science toolkit and
Science projects without weakening the full suites or changing what bare
`pytest` means.

The change is guidance-only. It updates the toolkit guide, the project scaffold,
and existing project guides. It does not change pytest configuration, add a
fast-suite marker, add CI workflows, or introduce template synchronization.

## Context

Post-optimization measurements put the default CLI suite between 6:42 and 7:24
on the Dropbox-backed toolkit checkout. The toolkit guide's current “~10 min”
estimate is stale, but its warning that a full run exceeds the normal 120-second
command timeout remains valid. A localized change can therefore spend far more
time in repeated full-suite runs than in implementation.

The current guide already tells subagents to run affected modules plus guards,
but reserves the full run for the top-level agent. The new policy generalizes
scoped-first validation to every agent, including the top-level agent. When a
full-suite trigger does apply, the top-level agent still owns that run and must
use an explicit long timeout; the subagent backgrounding warning remains because
a subagent that yields while waiting will not reliably resume.

Science project guides are heterogeneous. Most expose Science structural
validation through `bash validate.sh --verbose`; some also have application
tests, pipelines, or known failing checks. Their existing commands and warnings
are authoritative and must be preserved.

The project scaffold is write-once outside its managed load-bearing-constraints
block. Updating `templates/agents-md.md` affects new projects only, so existing
project guides require an explicit migration.

## Decision

Adopt a scoped-first validation ladder in agent guidance.

### Toolkit policy

During development, run the smallest test node, module, or package selection
that exercises the changed behavior. Before handoff, run the affected modules
plus adjacent integration or contract guards, along with Ruff or pyright when
the changed code falls under those checks.

Run the full CLI or model suite only when at least one of these conditions
applies:

- shared pytest configuration or fixtures changed;
- dependencies, packaging, or supported Python behavior changed;
- schemas, serialization, source resolution, task or project graphs,
  validation, or output contracts changed across subsystem boundaries;
- multiple unrelated subsystems changed;
- scoped results reveal unexpected cross-boundary effects;
- the work prepares a release; or
- the user explicitly requests the full suite.

The model suite is relevant when model or schema code changes, or when CLI code
depends on changed model behavior. A localized change does not require a full
baseline. A passing full run is not repeated after a fast-forward integration
when the tested commit and its base are unchanged.

Bare `pytest` remains the full default suite. The guide continues to document
the explicit commands and opt-in marker groups so a full run remains easy when
the trigger criteria apply. The guide's runtime estimate is updated from
“~10 min” to “about seven minutes” while preserving the 120-second timeout and
subagent-backgrounding warning that the duration supports.

### Project-template policy

The scaffold uses project-neutral wording because not every Science project
uses pytest or contains application code:

- use the narrowest project-specific check while iterating;
- test touched application code with the project's existing focused commands;
- run `bash validate.sh --verbose` once before handoff when Science-managed
  data, configuration, references, workflows, or generated artifacts changed;
- reserve a full application suite for shared configuration, dependencies,
  schemas, cross-cutting behavior, multiple subsystems, releases, unexpected
  broader effects, or an explicit request; and
- do not repeat validation after a fast-forward integration when the exact
  commit already passed and its base is unchanged.

This policy distinguishes Science structural validation from an application's
full code suite. Project-specific commands, stricter local rules, and known
failure warnings remain authoritative.

## Alternatives considered

### Make a critical subset the default pytest selection

Rejected for this tranche. A static allowlist is not necessarily relevant to a
given change, would require ongoing classification, and would make an
unqualified “pytest passed” ambiguous. Bare `pytest` should continue to mean the
full suite.

### Add a managed validation block to every project guide

Rejected. The header of `templates/agents-md.md` explicitly says that its static
body applies only at create or import time and that “There is no
push-to-existing-projects mechanism.” The only managed block is a digest of each
project's own `core/decisions.md`, not a toolkit-to-project propagation channel.
There is therefore no existing synchronization mechanism to extend, and adding
one for this policy paragraph would be unnecessary machinery.

### Apply identical text mechanically to every guide

Rejected. Existing guides use different toolchains and include local commands
and warnings. A shared policy with individually adapted wording is smaller and
safer than normalizing their validation sections.

## Migration scope

Update these toolkit-owned files together:

- `AGENTS.md`
- `templates/agents-md.md`
- `meta/AGENTS.md`

Then update every existing `AGENTS.md` in the persistent Science registry plus
the known unregistered adopters `~/d/cats` and `~/d/3d-attention-bias`.
The audited project-guide inventory contains 21 files: 19 registered guides and
the two known adopters. The 19 registered guides include `meta/AGENTS.md`, whose
edit belongs to the toolkit commit listed above. The project-guide migration is
therefore 21 files, with the separate downstream sweep visiting 20 repositories
and editing one guide in each. The toolkit root guide and scaffold template are
two additional toolkit-owned files.
`~/d/science-commons` is excluded because it has no `AGENTS.md`; transient
registry entries under `/tmp` are excluded.

Before editing each repository, record its branch and starting commit and
recheck `AGENTS.md` for concurrent changes. The audit found all 20 downstream
checkouts on `main`; require that branch at execution time and stop for
direction if any checkout has moved. An unrelated dirty file does not
block a guide-only commit, but a dirty target guide must not be overwritten or
silently skipped.
Immediately before committing, confirm the branch is unchanged and HEAD still
matches the recorded starting commit. Commit only the intended guide in each
downstream repository. Push nothing: the migration ends with local commits,
including for repositories that have no remote. Do not create new guides,
migrate other documentation, or add a push-to-existing-projects mechanism.

## Verification

For the toolkit repository:

- inspect the diff for the three toolkit-owned guidance files;
- run `git diff --check`;
- from `science/`, run these existing focused guards:

  ```bash
  uv run --frozen pytest \
    tests/test_command_docs.py::test_active_tooling_docs_drop_relative_editable_workarounds \
    tests/test_agent_assets.py::test_agents_md_template_has_no_at_core_includes \
    tests/test_curate_agents_md.py \
    tests/test_acceptance_managed_artifacts.py \
    tests/test_no_raw_task_file_reads_in_docs.py
  ```

  The last module is load-bearing for the new template wording: it rejects
  guidance that tells agents to bypass `science tasks` and read raw task files;
  and
- confirm the full-suite commands and marker documentation remain present.

For the downstream migration:

- inspect every guide diff and confirm its existing commands, local rules, and
  known-failure warnings remain intact;
- confirm every target states the scoped-first rule and explicit full-validation
  triggers appropriate to that project; and
- run `git diff --check` in each repository.

The full CLI, model, and downstream application suites are not required for
this Markdown-only change. Running them would not exercise the policy text and
would contradict the scoped-validation decision being introduced.
