# Scoped Validation Guidance Design

## Goal

Reduce avoidable validation time for agents working on the Science toolkit and
Science projects without weakening the full suites or changing what bare
`pytest` means.

The change is guidance-only. It updates the toolkit guide, the project scaffold,
and existing project guides. It does not change pytest configuration, add a
fast-suite marker, add CI workflows, or introduce template synchronization.

## Context

The optimized default CLI suite still takes roughly seven minutes on the
Dropbox-backed toolkit checkout. A localized change can therefore spend far
more time in repeated full-suite runs than in implementation. The current
toolkit guide names the full CLI and model suites as the primary validation
commands and reserves them for the top-level agent, which still encourages a
full run for routine handoff and again after integration.

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
the trigger criteria apply.

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

Rejected. The scaffold intentionally treats its static body as project-owned
after creation. Adding propagation machinery for one policy paragraph would
create a synchronization system that the migration does not need.

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
The audited inventory contains 21 project guides: 19 registered guides and the
two known adopters. `~/d/science-commons` is excluded because it has no
`AGENTS.md`; transient registry entries under `/tmp` are excluded.

Before editing each repository, recheck `AGENTS.md` for concurrent changes. An
unrelated dirty file does not block a guide-only commit, but a dirty target
guide must not be overwritten or silently skipped: stop and request direction.
Commit only the intended guide in each downstream repository. Do not create new
guides, migrate other documentation, or add a push-to-existing-projects
mechanism.

## Verification

For the toolkit repository:

- inspect the diff for the three toolkit-owned guidance files;
- run `git diff --check`;
- run the focused existing tests that read the root guide or project scaffold;
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
