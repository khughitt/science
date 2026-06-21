# User Guide Restructure Design

## Status

Proposed.

## Context

Science currently has overlapping user-facing model documentation:

- `README.md`
- `docs/user-guide.md`
- `docs/project-organization-profiles.md`
- `meta/entities/hypotheses/0007-working-model.md` (working-model entity) and its
  derived convention writeup `docs/conventions/project-working-model-h00.md`
- `docs/claim-and-evidence-model.md`
- `docs/proposition-and-evidence-model.md`

The single-file user guide mixes installation, workflow teaching, project layout,
the reasoning model, command tables, and cross-project notes. The proposition
and evidence model page is more detailed, but it is also a second canonical home
for the same ideas. The claim and evidence model page is already marked
superseded. The result is a guide surface that is harder to read, harder to keep
current, and easy for agents to cite inconsistently.

The goal is a cohesive user guide that reflects the current Science framework:
authored entity files, derived graph state, explicit epistemic uncertainty,
provenance, health checks, project/domain boundaries, and the patch/federation
working model.

## Decision

Make `docs/user-guide/index.md` the canonical user guide entry point and split
the guide into focused chapters under `docs/user-guide/`.

Remove these old canonical or superseded pages entirely:

- `docs/user-guide.md`
- `docs/project-organization-profiles.md`
- `docs/proposition-and-evidence-model.md`
- `docs/claim-and-evidence-model.md`

Update internal links, command docs, tests, and README references in the same
migration. Do not leave compatibility stubs for the deleted model docs.

Keep the working-model entity `meta/entities/hypotheses/0007-working-model.md`
as a design/research artifact. It is not a user-guide page and should not be
deleted. The new `science-model.md` chapter is its stable user-facing
derivative; the two are allowed to differ in detail and tone.

Resolve the third canonical surface explicitly:
`docs/conventions/project-working-model-h00.md` is a convention writeup derived
from the same working-model entity. Once `science-model.md` exists, this
conventions page is a duplicate canonical home for the model. Delete it as part
of this migration and re-point any references (it is currently cited by the
proposition/evidence model doc and by the working-model entity) at
`docs/user-guide/science-model.md`. The authored entity remains the source of
truth; the user guide becomes the single user-facing derivative.

## Guide Shape

Use this chapter structure:

```text
docs/user-guide/
  index.md
  introduction.md
  science-model.md
  project-layout.md
  entities.md
  epistemic-model.md
  evidence-lines.md
  graph-and-derived-state.md
  health-and-validation.md
  agent-workflows.md
  cross-project-work.md
```

The guide should be a user-facing manual, not a design archive. It can draw from
plans and hypotheses, but it should present the stable operational model in
plain language.

## Chapter Responsibilities

### `index.md`

The guide landing page. It should explain what the guide covers, link to each
chapter, and give a short reading path:

1. Start with introduction and science model.
2. Learn project layout and entities.
3. Learn the epistemic model and evidence lines.
4. Learn graph build, health, workflows, and cross-project work.

### `introduction.md`

The concise front door. Cover what Science helps users do, how Claude/Codex/CLI
fit together, and the "skeptical by default" stance. Keep the existing nonlinear
research-loop framing.

### `science-model.md`

The first conceptual chapter after the introduction. Translate the working-model
entity `meta/entities/hypotheses/0007-working-model.md` (and the steady-state
content of the now-retired `docs/conventions/project-working-model-h00.md`) into
user-facing documentation.

It should cover:

- Science projects as authored source files plus derived graph views.
- The difference between substrate, entities, relations, graphs, and reports.
- Epistemic neighborhoods or patches as local clusters around questions,
  hypotheses, propositions, evidence, inquiries, datasets, and computations.
- Project, domain, epistemic, operational, and reference surfaces.
- Provenance and uncertainty as first-class data, not after-the-fact notes.
- Federation as `patch subset project subset project collection` in ordinary
  prose, without copying the full `h00` research artifact.

The epistemic model should be introduced here, but detailed proposition and
evidence semantics belong in later chapters.

### `project-layout.md`

Replace the steady-state user-facing parts of
`docs/project-organization-profiles.md`. Explain the ordinary project
filesystem:

- `science.yaml`
- `AGENTS.md` / `CLAUDE.md`
- `pyproject.toml`
- `doc/`
- `specs/`
- `tasks/`
- `knowledge/`
- `papers/references.bib`
- `.ai/`

Describe source-authored files versus generated artifacts, and reinforce that
generated graph files should be rebuilt rather than hand-edited.

Resolve the `science.yaml` / `pyproject.toml` split explicitly:

- `science.yaml` is the Science project manifest: profile, aspects, ontologies,
  peers, and knowledge-profile configuration.
- `pyproject.toml` is the project-local Python/tooling manifest used by managed
  projects so `uv run science ...` and validation resolve consistently.

Do not carry forward old migration instructions. Science is not public yet and
the known projects have already been migrated, so the guide should teach the
steady-state model rather than historical migration procedure.

### `entities.md`

Explain what an entity looks like in Science:

- Markdown file with YAML frontmatter plus body prose.
- Stable `id` / typed reference such as `proposition:...`.
- `type`, `title`, status fields, relationships, source refs, and body context.
- Authored fields versus derived fields.
- Entity classes: epistemic, operational, and reference.

List the main entity kinds grouped by class. The implementation should derive
or verify this list from `CORE_PROFILE`
(`science/model/src/science_model/profiles/core.py`) and `EntityClass`
(`science_model.identity`) so the guide does not invent stale vocabulary. This
chapter is the single canonical home for the kind-by-class list;
`science-model.md` introduces the three classes conceptually and links here
rather than restating the enumeration, so the drift test has one target.

### `epistemic-model.md`

Replace the conceptual parts of `docs/proposition-and-evidence-model.md`.

Cover:

- Questions, hypotheses, propositions, observations, mechanisms, inquiries, and
  patch definitions as epistemic records.
- Propositions as the primary belief-bearing assertions.
- Hypotheses as organizing conjectures or bundles of propositions.
- Observations as concrete findings.
- Belief states, support, dispute, contestation, fragility, and uncertainty.
- Authored versus derived fields.
- Bundle belief rollups and weakest-link semantics at a user-facing level.
- Optional layered-claim metadata: `claim_layer`, `identification_strength`,
  `measurement_model`, `supports_scope`, and `rival_model_packet`.
- Evidence integrity: checks are instruments for reading the record, not targets
  to game.

### `evidence-lines.md`

Replace the field-level evidence authoring parts of
`docs/proposition-and-evidence-model.md`.

Cover:

- What an `evidence-line` is.
- `stance`, `target`, `source`, `evidence_type`, `strength`, `independence`,
  `independence_group`, `evidence_role`, and quantitative result fields.
- Evidence types and the `negative_result` compatibility note.
- Independence and why duplicate support should not be counted as independent.
- Source references and bibliography references.
- A short worked example that can be copied into a real entity file.

### `graph-and-derived-state.md`

Explain the derived layer:

- `science graph build`
- graph materialization
- dashboard summaries
- belief snapshots
- grounding/prose-derived reports where relevant
- why the graph is not the source of truth

### `health-and-validation.md`

Explain validation, health, needs-review, migration audits, freshness, and
attention surfaces. Make clear that yellow or warning states can be honest
outcomes when the evidence remains genuinely weak, indirect, or incomplete.

### `agent-workflows.md`

Map user intents to Claude slash commands, Codex skills, and core CLI commands.
This should preserve the useful command table from the current README and guide,
but keep it chapter-local rather than repeating it across many docs.

### `cross-project-work.md`

Explain peers, sync, federation, and cross-project references at the user level.
Link to `docs/federation.md` for the deeper model.

## Diagrams

Use Markdown-native diagrams only. Prefer Mermaid where it clarifies flow and
ASCII where it is simpler. Do not add generated image assets for this pass.

Recommended diagrams:

1. Authored source files -> graph build -> derived reports / summaries / health.
2. Project surfaces: domain, epistemic, operational, reference, and generated.
3. Question -> hypothesis -> proposition -> evidence-line -> belief result.
4. Patch subset project subset project collection.

## README Changes

Update `README.md` after the guide migration. README should become a concise
front door:

- What Science is.
- The core skeptical reasoning stance.
- A short model summary.
- Install/start pointers for Claude, Codex, and CLI.
- A small command map.
- Links into `docs/user-guide/index.md` and the most relevant guide chapters.

README should not continue pointing at deleted model docs.

## Command And Skill Read Targets

Several command docs do more than link to the old model docs: they instruct
agents to read them before acting, and `science/tests/test_command_docs.py`
asserts those strings. Replacing the old files therefore requires explicit
successor targets, not a generic link rewrite.

Use this mapping:

| Source instruction context | New target |
|---|---|
| Hypothesis authoring and comparison (`add-hypothesis`, `compare-hypotheses`, status model context) | `docs/user-guide/epistemic-model.md` |
| Interpretation and evidence authoring (`interpret-results`, health evidence notes, research-methodology companion skill) | `docs/user-guide/epistemic-model.md` and `docs/user-guide/evidence-lines.md` |
| Graph creation/update and model specification (`create-graph`, `update-graph`, `sketch-model`, `specify-model`, `critique-approach`, `plan-pipeline`, `review-pipeline`) | `docs/user-guide/science-model.md`, `docs/user-guide/entities.md`, and `docs/user-guide/graph-and-derived-state.md` |
| General user-guide references | `docs/user-guide/index.md` |

The implementation should update command docs and their tests in the same
change. Tests should assert the new read targets and assert that no command doc
still names the deleted model docs.

Codex skills under `codex-skills/` are generated mirrors, not hand-maintained
source. After editing `commands/` or canonical companion skills, regenerate them
with:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run --project science python scripts/generate_codex_skills.py
```

The canonical companion skills under `skills/` are source files and must be
edited directly when they cite the deleted docs; regenerated `codex-skills/`
should then mirror those changes.

## Link And Test Migration

The implementation must update all internal references to:

- `docs/user-guide.md`
- `docs/proposition-and-evidence-model.md`
- `docs/claim-and-evidence-model.md`

Command docs and tests are in scope. Existing tests that assert the old paths
should be updated to the new guide chapter paths. Historical plan files may keep
old paths when they describe past work, but current canonical-reference language
should be changed.

Two surfaces sit outside the obvious `docs commands skills codex-skills` sweep
and must be handled explicitly:

- `docs/conventions/` references the retired docs (`docs/conventions/README.md`
  cites `project-organization-profiles.md`, and the conventions writeup
  `project-working-model-h00.md` is itself retired). It is under `docs/`, so the
  scan covers it, but call it out so the reference flip is not missed.
- The `meta/` project is a real top-level project in this repo, and
  `meta/entities/hypotheses/0007-working-model.md` cites the retired model docs.
  Decide its scope: re-point the meta entity's references to the new guide paths
  as part of this migration (recommended, since meta is the working-model
  entity's home) rather than leaving a dangling canonical reference.

Add or update a guide drift test for the entity-kind list. The test should read
the kinds and `EntityClass` groupings documented in `docs/user-guide/entities.md`
and compare them with the current core profile / registered kind descriptors.
The exact parser can be simple, but the contract should be real enough that a
new core kind or reclassified kind fails until the guide is updated.

Reuse the existing descriptor-introspection helpers rather than re-deriving kind
enumeration. `science/qa/tests/test_descriptor_contract.py` and the model-side
`science/model/tests/test_kind_reconciliation.py` already walk `CORE_PROFILE`;
the guide-drift test should pull its expected set the same way so the two stay
consistent.

## Sequencing

Use a two-step implementation sequence inside one branch:

1. Add the new `docs/user-guide/` chapter tree and the entity-kind drift test.
   Keep old links temporarily while drafting content.
2. Flip README, command docs, canonical skills, generated Codex skills, and
   tests to the new guide paths; then delete the retired docs.

This keeps the content reviewable before the high-impact reference flip, while
still landing as one coherent migration.

After deletion, run the old-path scan over all live source surfaces, including
canonical and generated skills.

## Alternatives Considered

### Minimal split

Split only `docs/user-guide.md` and leave the model docs in place. This is lower
risk but preserves the duplicate canonical surfaces and stale search results.
Rejected.

### Full reference manual

Create a larger documentation system with separate tutorial, concepts,
reference, operations, and design sections. This may be a good eventual shape,
but it is too broad for this pass. Rejected for now.

### Compatibility stubs

Keep `docs/proposition-and-evidence-model.md` and
`docs/claim-and-evidence-model.md` as redirect pages. This would reduce link
breakage, but it preserves outdated entry points. Rejected in favor of a clean
canonical guide tree.

### Keep project organization as a separate page

Leave `docs/project-organization-profiles.md` as the canonical project-layout
reference and have `project-layout.md` link to it. This would avoid moving one
more doc, but it leaves duplicate project-layout guidance in place. Rejected:
the steady-state content should be absorbed into the guide and the historical
migration guidance should be omitted.

## Validation

At minimum, implementation should run:

```bash
rg "docs/user-guide.md|docs/project-organization-profiles.md|docs/proposition-and-evidence-model.md|docs/claim-and-evidence-model.md|project-working-model-h00" README.md docs commands skills codex-skills science/tests meta
UV_CACHE_DIR=/tmp/uv-cache uv run --project science python scripts/generate_codex_skills.py
uv run --frozen pytest science/tests/test_command_docs.py
```

If implementation touches generated Codex skills or command docs, run the
relevant command-doc tests and any formatter/linter checks normally used for
Markdown or generated skill files.
