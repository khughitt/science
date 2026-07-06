# Terms Authoring Ergonomics Design

**Date:** 2026-07-02

**Status:** Draft for review

## Goal

Make lightweight local semantic terms authorable through a small, predictable
CLI surface instead of requiring hand-edited `terms.yaml` rows.

This is the behavior-changing follow-up to
`concept-source-ownership-design.md` and `source-authored-concepts-design.md`.
Those designs clarified the concept ownership contract and enabled full
Markdown concept owners. This design covers the middle tier: a project-local
term that needs a stable resolvable id, title, and short metadata, but does not
yet need a full entity markdown file.

## Problem

`terms.yaml` is already a real source surface:

- `knowledge/sources/<local-profile>/terms.yaml` rows load through the
  aggregate source adapter.
- A row such as `id: concept:treatment-response` infers `kind: concept` from
  the CURIE prefix when no explicit kind is supplied.
- The row's `description` becomes the lightweight content preview.
- `content` and `body` fields are intentionally ignored by the loader.
- Cross-reference validation reads ids from `terms.yaml`.
- Graph materialization resolves lightweight terms.
- Promotion machinery can retire a coined term row into a full markdown owner
  such as `entities/concepts/<slug>.md`.

But there is no focused `science terms ...` authoring command. The current
routine path is manual YAML editing, which is easy to get subtly wrong:

- a user can add `content` or `body` and believe it will materialize;
- a user can create a same-id row when a markdown owner already exists;
- a user can pick a malformed id or unsupported prefix;
- agents have to remember the local-profile path and YAML shape;
- guidance has to describe a source surface that the CLI cannot create.

Now that full source-authored concepts are supported, the missing piece is not
another full entity writer. It is a thin helper for lightweight local terms.

## Current Contract

| Layer | Current behavior |
|---|---|
| Storage path | `knowledge/sources/<local-profile>/terms.yaml`, where `<local-profile>` is the configured `knowledge_profiles.local` value, defaulting to `local`. The aggregate loader does not glob every `knowledge/sources/*/terms.yaml`. |
| YAML shape | Root object with `terms:` list. Rows may use `id` or `canonical_id`. |
| Kind inference | If the row id is a CURIE and `kind` is absent, the prefix before `:` becomes `kind`. |
| Supported body | `description` is lightweight prose. `content` and `body` are ignored. |
| Source loading | Terms rows load as aggregate-owned source records. |
| Resolution | Cross-reference checks and graph materialization can resolve term ids. |
| Promotion | Existing aggregate-retirement machinery can promote coined concept rows into markdown owners. |
| Collision behavior | Markdown adapters load before aggregate adapters. Under strict identity, a same-id markdown owner and terms row raise an identity collision. In non-strict load, the markdown owner wins deterministically and validation/health reports the duplicate owner condition. |

The new command should expose this contract directly. It should not invent a
second meaning for `terms.yaml`.

## Alternatives Considered

### 1. Add `science terms add`

Add a focused command group for lightweight semantic term rows:

```bash
science terms add concept:treatment-response --title "Treatment response" --description "Clinical response after treatment."
```

This makes the authoring intent explicit and keeps the full entity writer
separate from the lightweight term writer. It is the recommended path.

### 2. Extend `science entity create` with a lightweight flag

For example:

```bash
science entity create concept "Treatment response" --lightweight
```

This keeps top-level command count smaller, but it blurs two different owner
contracts. `entity create` writes markdown owners with bodies and lifecycle.
`terms.yaml` rows are aggregate lightweight records whose `body`/`content`
fields are ignored. Hiding that distinction behind one command would make the
wrong thing easy.

### 3. Leave authoring manual and improve docs only

This is the lowest implementation cost, but it leaves the sharp edge in place.
The framework now recommends lightweight terms in multiple command docs, so the
source surface should have a small safe writer.

## Decision

Add a focused `science terms add` command for creating lightweight local term
rows in the configured local profile's `terms.yaml`.

The command should be narrow in the first slice:

- create only new rows;
- write only the existing `terms.yaml` schema;
- avoid update/delete/promote behavior;
- reject content fields that the loader ignores;
- fail early on malformed ids, unsupported kinds, duplicate rows, and existing
  markdown owners with the same canonical id;
- do not accept a free-form profile selector in the first slice, because rows
  written outside the configured local profile would not be loaded or resolve.

This gives agents and humans one durable command for "I need this local term to
resolve, but I do not need a full markdown entity yet."

## Command Contract

### Command

```bash
science terms add <id> --title "<title>" [options]
```

Example:

```bash
science terms add concept:treatment-response --title "Treatment response" --description "Clinical response after treatment."
```

### Inputs

| Input | Contract |
|---|---|
| `<id>` | Required canonical CURIE-style id whose prefix is a registered entity kind, such as `concept:treatment-response` or `method:bayesian-model-check`. External ontology CURIEs such as `HP:0001250` belong in `--ontology-term`, not as the local term id. |
| `--title` | Required display title. |
| `--description` | Optional short prose. This maps to the lightweight content preview. |
| `--alias` | Repeatable alias string. |
| `--same-as` | Repeatable external equivalent id or URI. |
| `--ontology-term` | Repeatable ontology CURIE. |
| `--project-root` | Standard project root selector following the CLI behavior contract. |

Do not accept `--body`, `--content`, `--name`, `--profile`, or
markdown-template flags in this command. Body/content fields belong to full
entity owners and would be ignored by the current terms loader. `--title` is
the authored display field; `name` is not mapped by the loader.

### Written Row

The command writes rows like:

```yaml
terms:
  - id: concept:treatment-response
    title: Treatment response
    description: Clinical response after treatment.
```

Rows deliberately omit redundant `kind:` and rely on the existing prefix
inference. The writer should emit only keys that carry values; loader defaults
cover empty optional fields. This keeps new rows minimal and avoids churn in
curated source files.

### File Handling

- Target path: `knowledge/sources/<local-profile>/terms.yaml`, where
  `<local-profile>` comes from `knowledge_profiles.local`, falling back to
  `local`.
- Create `knowledge/sources/<local-profile>/` when missing.
- Create a new YAML file with root key `terms` when missing.
- Preserve existing row order and append the new row at the end.
- Preserve unrelated top-level keys if an existing file already has them.
- Fail if the existing file does not parse to a mapping with a list-valued
  `terms` key.

Appending instead of sorting avoids surprising churn in curated source files.
Ordering can become a separate formatting command later if needed.

## Validation And Errors

Validation belongs at the command boundary. The writer should fail before
touching the file when input is invalid.

| Case | Behavior |
|---|---|
| Missing colon in id | Error: id must be a canonical CURIE-style term id. |
| Empty prefix or local id | Error. |
| Unsupported kind prefix | Error unless the prefix resolves to a registered entity kind through the entity registry. Do not treat external ontology prefixes as valid local ids; tell users to pass those through `--ontology-term`. |
| Existing row with same `id` or `canonical_id` in target `terms.yaml` | Error. |
| Existing source owner with the same canonical id in the loaded source set (core, commons, or the local profile) | Error by default. |
| Existing markdown owner with the same id | Error with guidance to edit the markdown owner instead. |
| Existing malformed `terms.yaml` | Error without rewriting the file. |
| User supplies body/content/name/profile flags | Click rejects unknown options. |

The same-id check should use the project source-loading/identity machinery where
possible, not a broad filesystem scan. The prior concept work proved that
markdown-vs-terms collisions are deterministic, but the authoring command should
avoid creating collisions within the loaded source set in the first place.

Two contract details follow from routing the check through the loader:

- **Load strictness.** Run the pre-write check with `strict_identity=False` so the
  command can inspect the identity table rather than aborting on the first
  pre-existing collision. Loading in strict mode would let an unrelated,
  already-present collision raise before the new id is ever evaluated, turning a
  pre-existing project problem into a confusing `terms add` failure. The command
  distinguishes the two conditions in its error message: "the new id already
  resolves to an existing owner" versus "the project already contains an
  identity collision unrelated to this term; resolve it first."
- **Check scope.** Load with `include_commons=True` (the default) so the same-id
  check also rejects ids owned by core or commons sources. A local term must not
  shadow a core/commons id. The "anywhere in the project" cases above are the
  project-visible subset of this loaded set; the check itself spans core,
  commons, and the local profile.

## Boundaries

`science terms add` is a lightweight identity writer. It is not:

- a replacement for `science entity create concept ...`;
- an ontology lookup or normalization service;
- a term promotion command;
- a bulk import command;
- an update/delete surface;
- a graph mutation command.

Use `science entity create concept ...` when the concept needs body prose,
lifecycle status, source refs, relationships, or independent review. Use the
most specific registered kind when one exists. Use `science terms add` only for
short local semantic identities that need to resolve now.

## Documentation Updates

Update source docs first, then regenerate generated mirrors:

- `docs/user-guide/entities.md`: replace manual-only lightweight term guidance
  with the new command and keep the promotion distinction.
- `docs/user-guide/epistemic-model.md`: point lightweight inquiry refs at
  `science terms add` when no richer source owner is needed.
- `docs/user-guide/cli-and-workflows.md`: classify `terms` as a source-write
  command family once the command exists.
- `commands/sketch-model.md` and `commands/specify-model.md`: use
  `science terms add` for lightweight local refs, while preserving the domain
  kind first and full concept owner guidance.
- `commands/create-graph.md` and `commands/health.md`: align triage language so
  "add a lightweight term row" has an executable command.
- `codex-skills/science-*`: regenerate from source command docs; do not edit
  generated mirrors by hand.

## Tests

The implementation plan should start with failing tests for:

1. `science terms add concept:treatment-response --title "Treatment response"`
   creates `knowledge/sources/local/terms.yaml`.
2. Re-running the same command fails without modifying the file.
3. `--description`, repeated `--alias`, repeated `--same-as`, and repeated
   `--ontology-term` serialize to the expected row fields.
4. A malformed id fails before writing.
5. An unsupported prefix fails before writing.
6. An external ontology prefix such as `HP:0001250` fails as the row id and the
   error points to `--ontology-term`.
7. An existing markdown owner with the same canonical id blocks term creation.
8. An existing malformed `terms.yaml` is rejected without rewrite.
9. The created row reloads through `load_project_sources()` with the expected
   title.
10. The command rejects `--body`, `--content`, `--name`, and `--profile`.
11. An id owned by a core or commons source is rejected (the check loads with
    commons included; a local term cannot shadow a core/commons id).
12. A project that already contains an unrelated identity collision produces a
    distinct pre-existing-collision error, not a crash and not a false "your id
    already exists" message.
13. Command docs and generated Codex mirrors use `science terms add` instead of
    hand-authoring YAML for routine lightweight term creation.

## Non-Goals

This slice should not:

- add `science terms update`, `delete`, `list`, `show`, or `promote`;
- migrate existing term rows into markdown owners;
- change aggregate loading semantics;
- change graph materialization semantics;
- change identity-collision severity;
- add ontology lookup or autocomplete;
- introduce compatibility aliases for hand-written older shapes;
- refactor broader entity source loading.

## Risks And Checks

| Risk | Check |
|---|---|
| The command creates a second owner for an id that already resolves. | Source-load before writing and fail on any existing canonical id. |
| The command suggests terms are a full entity replacement. | Docs keep the lightweight term vs markdown owner boundary explicit. |
| YAML rewriting causes unnecessary churn. | Preserve existing row order and unrelated top-level keys; append only. |
| Free-form profile selection writes dead rows. | Do not expose `--profile` in the first slice; always write to the configured local profile. |
| The first slice grows into a terms-management subsystem. | Limit to `add` and defer update/delete/promote/list to later designs. |

## Acceptance Criteria

- `science terms add concept:treatment-response --title "Treatment response"`
  creates a valid lightweight terms row under
  `knowledge/sources/local/terms.yaml` or the configured local profile.
- Created rows reload through `load_project_sources()` and resolve as
  canonical ids with the supplied title.
- Duplicate ids are rejected before writing, including ids owned by markdown
  entity files.
- The command does not accept body/content/name/profile options that the loader
  ignores or cannot load.
- Existing row order is preserved and the new row is appended.
- User-guide, command docs, and generated Codex mirrors describe
  `science terms add` as the routine lightweight authoring path.
- Full concept entities remain the documented path for concepts that need body
  prose, lifecycle, source refs, or relationships.

## Follow-Ups

Useful later slices:

1. `science terms list/show` for inspection.
2. `science terms promote <id>` as a first-class wrapper around existing
   aggregate-retirement promotion behavior.
3. A formatting/check command for `terms.yaml` files if hand-edited source files
   remain common.
4. CLI help text and runtime warnings for `science graph add concept` so direct
   graph mutation is visibly exploratory.
