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

- `knowledge/sources/<profile>/terms.yaml` rows load through the aggregate
  source adapter.
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
| Storage path | `knowledge/sources/<profile>/terms.yaml` under a source profile directory. |
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
rows in `knowledge/sources/<profile>/terms.yaml`.

The command should be narrow in the first slice:

- create only new rows;
- write only the existing `terms.yaml` schema;
- avoid update/delete/promote behavior;
- reject content fields that the loader ignores;
- fail early on malformed ids, unsupported kinds, duplicate rows, and existing
  markdown owners with the same canonical id.

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
| `<id>` | Required canonical CURIE-style id whose prefix is a registered source kind, such as `concept:treatment-response` or `method:bayesian-model-check`. External ontology CURIEs belong in `--ontology-term`, not as the local term id. |
| `--title` | Required display title. |
| `--description` | Optional short prose. This maps to the lightweight content preview. |
| `--alias` | Repeatable alias string. |
| `--same-as` | Repeatable external equivalent id or URI. |
| `--ontology-term` | Repeatable ontology CURIE. |
| `--profile` | Optional source profile directory name. Defaults to the project local profile when the project config exposes one, otherwise `local`. |
| `--project-root` | Standard project root selector following the CLI behavior contract. |

Do not accept `--body`, `--content`, or markdown-template flags in this command.
Those belong to full entity owners and would be silently ignored by the current
terms loader.

### Written Row

The command writes rows like:

```yaml
terms:
  - id: concept:treatment-response
    title: Treatment response
    description: Clinical response after treatment.
    aliases: []
    same_as: []
    ontology_terms: []
```

The implementation may omit empty optional arrays if that better matches the
surrounding file style, but it should be deterministic for new files.

### File Handling

- Target path: `knowledge/sources/<profile>/terms.yaml`.
- Create `knowledge/sources/<profile>/` when missing.
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
| Unsupported kind prefix | Error unless the prefix resolves to a registered source kind. |
| Existing row with same `id` or `canonical_id` in target `terms.yaml` | Error. |
| Existing source owner with the same canonical id anywhere in the project | Error by default. |
| Existing markdown owner with the same id | Error with guidance to edit the markdown owner instead. |
| Existing aggregate row in another profile with the same id | Error by default, because two lightweight owners create non-obvious precedence. |
| Existing malformed `terms.yaml` | Error without rewriting the file. |
| User supplies ignored body/content fields | Click rejects unknown options. |

The same-id check should use the project source-loading/identity machinery where
possible, not a filename-only check. The prior concept work proved that
markdown-vs-terms collisions are deterministic, but the authoring command
should avoid creating the collision in the first place.

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
6. An existing markdown owner with the same canonical id blocks term creation.
7. An existing terms row in another profile with the same canonical id blocks
   term creation.
8. An existing malformed `terms.yaml` is rejected without rewrite.
9. The created row reloads through `load_project_sources()`.
10. Command docs and generated Codex mirrors use `science terms add` instead of
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
| Profile defaulting is ambiguous. | Use the project local profile when available; otherwise use `local`; document the rule. |
| The first slice grows into a terms-management subsystem. | Limit to `add` and defer update/delete/promote/list to later designs. |

## Acceptance Criteria

- `science terms add concept:treatment-response --title "Treatment response"`
  creates a valid lightweight terms row under
  `knowledge/sources/local/terms.yaml` or the configured local profile.
- Created rows reload through `load_project_sources()` and resolve as
  canonical ids.
- Duplicate ids are rejected before writing, including ids owned by markdown
  entity files and ids in other `terms.yaml` profiles.
- The command does not accept body/content options that the loader ignores.
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
