# Entity Layout Migration Guide (v2 → v3)

This guide walks through migrating a Science project from the legacy
`doc/` + `specs/` entity layout (layout version 2) to the unified
`entities/` layout (layout version 3). The migration is performed by the
`science entities migrate` command.

## What Changes

| Item | Before (v2) | After (v3) |
|---|---|---|
| Markdown entities | Scattered across `doc/`, `specs/` | `entities/<kind>/NNNN-slug.md` |
| Paper summaries | `doc/papers/<citekey>.md` | `entities/papers/<citekey>.md` |
| Research question | `specs/research-question.md` or `doc/research-question.md` | `entities/research-question.md` |
| Claim registry | `specs/claim-registry.yaml` | `entities/claim-registry.yaml` |
| Layout marker | `layout_version: 2` in `science.yaml` | `layout_version: 3` in `science.yaml` |
| `specs/` directory | Exists | Retired (no longer scanned) |

Numeric entity kinds (questions, hypotheses, propositions, evidence-lines,
interpretations, reports, plans, searches, methods, pre-registrations) are
assigned a zero-padded four-digit sequence number `NNNN` derived from their
`created` date, oldest-first. Conformant legacy filenames (already in
`NNNN-slug` form) preserve their number unchanged. Paper entities keep their
citekey stem (e.g. `Smith2024.md` → `entities/papers/Smith2024.md`).

The `specs/` directory is retired. Singletons (`research-question.md`,
`claim-registry.yaml`) move to `entities/` at their canonical paths.

## Preconditions

1. **Clean working tree.** Run `git status` and commit or stash any changes
   before proceeding. The command issues `git mv` operations; uncommitted
   changes in the affected files will conflict.
2. **On a branch.** Do not run `--apply` directly on `main`. Migrate on a
   feature branch so the result is reviewable before merging.
3. **Plans 1 and 2 shipped.** The `science entities migrate` command requires
   the entity path policy layer (Plan 1) and the graph sources layer (Plan 2)
   to be present in the installed `science_tool` package.

## Step 1 — Dry Run

Run the migrator without `--apply` to inspect the planned changes:

```bash
science entities migrate --project-root /path/to/project
```

The `--project-root` flag defaults to `.` (the current directory), so inside
a project you can omit it:

```bash
science entities migrate
```

The command prints a JSON report to stdout. The report always contains these keys:

| Key | Description |
|---|---|
| `moves` | List of entity files to move (`old_rel_path`, `new_rel_path`, `old_id`, `new_id`, `kind`). |
| `singletons` | List of singleton files to move (`old_rel_path`, `new_rel_path`). |
| `id_map` | Mapping of old entity ids (and filename-stem aliases) to new canonical ids. |
| `collisions` | Blocking conflicts that must be resolved before `--apply` (see below). |
| `unresolved_references` | Per-file map of legacy-shaped tokens that could not be rewritten (see below). |
| `undated_entities` | Legacy entities with no derivable date — blocks `--apply` (see below). |
| `applied` | `false` in a dry run; `true` after a successful `--apply`. |

On a successful `--apply` the report also contains:

| Key | Description |
|---|---|
| `graph_validation` | `"passed"` — post-move graph audit succeeded and `layout_version` was bumped. |

Example dry-run output (abbreviated):

```json
{
  "moves": [
    {
      "old_rel_path": "specs/hypotheses/h01-aging-early.md",
      "new_rel_path": "entities/hypotheses/0001-aging-early.md",
      "old_id": "hypothesis:h01-aging-early",
      "new_id": "hypothesis:0001-aging-early",
      "kind": "hypothesis"
    }
  ],
  "singletons": [
    {
      "old_rel_path": "specs/research-question.md",
      "new_rel_path": "entities/research-question.md"
    }
  ],
  "id_map": {
    "hypothesis:h01-aging-early": "hypothesis:0001-aging-early",
    "hypothesis:h01-aging-early": "hypothesis:0001-aging-early"
  },
  "collisions": [],
  "unresolved_references": {},
  "undated_entities": [],
  "applied": false
}
```

Review all four blocking fields before proceeding:

- `collisions` must be empty.
- `unresolved_references` must be empty.
- `undated_entities` must be empty.

A non-empty value in any of these fields will cause `--apply` to raise a clean
error with no changes made to the working tree.

## Step 2 — Resolve Collisions

`collisions` lists blocking conflicts detected during planning. These must be
resolved by hand; `--apply` refuses to proceed while any collision exists.

Collision kinds:

| `kind` field | Meaning | Fix |
|---|---|---|
| `"path"` | Two legacy files would land at the same target path. | Rename or delete one of the sources. |
| `"id"` | Two legacy files produce the same new canonical id. | Rename or remove the duplicate. |
| `"number"` | Two conformant legacy files carry the same sequence number for their kind. | Rename one to a non-conflicting stem. |
| `"disk"` | The planned target path already exists on disk (partial-migration or re-run case). | Delete or move the pre-existing target file. |
| `"alias"` | Two files under different legacy roots map to the same filename-stem alias, making it ambiguous. | Rename one file so the stems are distinct. |

After editing, re-run the dry run and confirm `collisions` is empty.

## Step 3 — Resolve Undated Entities

`undated_entities` lists legacy entities from which no creation date could be
derived. The migrator needs a date to assign correct `NNNN` sequence numbers;
without one it cannot proceed.

Each entry has `old_rel_path` (the legacy file) and `new_rel_path` (the
planned destination, with a `9999-99-99` sort-last placeholder that is never
written to disk).

Fix each undated entity by adding one of:

- A `**Date:** YYYY-MM-DD` prose header anywhere in the file body, or
- A `created: YYYY-MM-DD` field in the YAML frontmatter.

Example fix (prose header):

```markdown
## My Hypothesis

**Date:** 2024-03-15
**Status:** active

Body text here.
```

Re-run the dry run after fixing each file. When `undated_entities` is empty,
continue to the next step.

## Step 4 — Resolve Unresolved References

`unresolved_references` is a per-file map: each key is a relative file path
and each value is a list of legacy-shaped tokens in that file that could not
be automatically rewritten to a canonical id.

The reference rewriter scans **all project markdown** — not just the moved
entities — including `doc/` prose, `research/packages/`, and `tasks/`. Any
token that looks like a legacy reference but has no mapping in `id_map` is
reported here rather than left as a silent dead link. The dry-run report is
complete: if a token does not appear in `unresolved_references`, the rewriter
will handle it.

Two token shapes are reported:

- `<kind>:<local>` — a kind-qualified token whose local part is not conformant
  for that kind and has no entry in `id_map` (renamed target, deleted entity,
  or a slug the rewriter could not match). Example: `question:q5-aging`.
- `[[<local>]]` — a bare wiki-link with no kind prefix
  (e.g. `[[q01-foo]]`). These cannot be disambiguated to a kind, so they are
  always reported.

Fix each unresolved token by hand:

- If the target still exists under a different id, update the token to its
  current canonical id (e.g. `question:0005-aging-early`).
- If the target was deleted or renamed and there is no replacement, remove the
  reference or replace it with prose.
- For bare wiki-links, convert to a kind-qualified id or remove the link.

Re-run the dry run after each round of edits. When `unresolved_references` is
an empty object (`{}`), all references are either canonical already or will be
rewritten automatically by `--apply`.

## Step 5 — Apply

Once all three blocking fields are empty, apply the migration:

```bash
science entities migrate --apply --project-root /path/to/project
```

The command:

1. Issues `git mv` for every planned move (entities and singletons).
2. Writes the rewritten file content to each destination (frontmatter
   synthesized, id fields updated, references rewritten).
3. Rewrites references in-place in all non-moved project markdown.
4. Runs a post-move graph audit.
5. On a clean audit only: bumps `science.yaml` `layout_version` to `3`.

The final report (printed to stdout) includes `"graph_validation": "passed"`
and `"applied": true` on success.

## Step 6 — Verify

After a successful apply:

```bash
science validate
```

Expect a green pass. Then spot-check a few entity short-forms still resolve:

```bash
science entity show q5
science entity show h1
```

Short-form references (kind-initial + sequence number) are resolved by the
entity layer regardless of whether the underlying file stem uses the old
letter-prefix form or the new `NNNN` form, so existing scripts and agent
prompts that use short-forms continue to work.

## Rollback

**Dry run (no `--apply`):** The command makes no changes to the working tree.
Re-run as many times as needed; the only side-effect is console output.

**After `--apply` — clean audit:** `git restore .` and `git restore --staged .`
undo the in-place reference rewrites; `git mv` operations are staged, so also
run `git restore --staged .` before the plain restore, or simply reset the
branch:

```bash
git restore --staged .
git restore .
```

**After `--apply` — audit failure mid-way:** If the post-move graph audit
fails, the working tree is already modified (files have been `git mv`'d and
rewritten) but `layout_version` has **not** been bumped — the version bump
only happens on a clean audit. The command prints explicit rollback
instructions. To recover:

```bash
git restore --staged .
git restore .
```

Or reset the entire branch to its pre-migration state:

```bash
git reset --hard <pre-migration-commit>
```

Investigate the audit error (the printed cause will identify which references
or bindings failed to resolve), fix the underlying issue, and re-run from the
dry-run step.

## Edge Cases

### Hypotheses With `.lock.yaml` Sidecars

Hypotheses that are locked (pre-registered) have a `.lock.yaml` sidecar. The
migrator moves only the `.md` file; the `.lock.yaml` is not touched. After
`--apply`, reconcile the sidecar manually: move or rename it to sit alongside
the new `entities/hypotheses/NNNN-slug.lock.yaml` path, and update any path
references inside the sidecar that pointed to the old location.

### Prose-Header (Frontmatterless) Files

Legacy entities without YAML frontmatter rely on prose headers
(`**Date:**`, `**Status:**`, H1 heading) for metadata. The migrator
synthesizes frontmatter from these headers before writing the destination
file.

Review the synthesized output in the dry-run `moves` entries, particularly:

- `title` — taken from the first `# H1` heading; falls back to
  `"Untitled <kind>"` when no H1 is present. If the fallback fires, add an H1
  before running `--apply`.
- `status` — the prose `**Status:**` value is accepted only if it is in the
  kind's controlled vocabulary; otherwise the per-kind default is used. The
  original prose line is preserved in the body.
- `created` — taken from `**Date:**` in the body. If absent, the entity
  appears in `undated_entities` and blocks `--apply` (see Step 3).

### Paper Summary Consolidation

If the project has paper summaries in both `doc/papers/` and
`doc/background/papers/`, the migrator discovers and moves both. Check the
`moves` list for duplicates: two summaries for the same citekey would produce
a `"path"` or `"id"` collision (reported in `collisions`). Merge the content
into one file and remove the duplicate before re-running.
