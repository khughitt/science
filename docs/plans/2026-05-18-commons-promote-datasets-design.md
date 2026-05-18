# Phase G — `science commons promote dataset` (design)

Phase G of the multi-project commons rollout. Adds dataset migration to the
kind-pluggable promote framework introduced in Phase F. Inherits Phase E's
papers shape and Phase F's topic/theme generalization. Pilots end-to-end on
one carefully-chosen public dataset (`dataset:ccle-proteomics-nusinow-2020`
in `multiple-myeloma`).

Parent design: `~/d/science/docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md`
(§3.2 dataset mixin, §4 bulk data resolution, §8.4 data migration policy,
§9 Phase G).

---

## 1. Goal

Migrate one dataset end-to-end from project-local to commons-canonical with
a project overlay, exercising the full v1 surface: two-file canonical layout,
hash computation over real bytes, per-machine override write, and recipe
stubbing. Reuse the kind-pluggable framework from Phase F where it
generalizes; extend it to handle multi-file canonical entities without
adding discriminator branches throughout the apply pipeline.

The pilot target is `dataset:ccle-proteomics-nusinow-2020` in
`multiple-myeloma`: 2 Parquet resources totaling ~1.3 MB
(`mm-proteomics-long.parquet` 1.31 MB + `mm-cell-lines.parquet` 3 KB),
public source (Nusinow 2020 CCLE proteomics), with an entity descriptor at
`doc/datasets/data-ccle-proteomics.md` and a Frictionless sidecar at
`data/external/ccle_proteomics/2020-01/datapackage.json`. The 31 MB total
under `data/external/ccle_proteomics/2020-01/` is the directory size
including `raw/protein_quant_current_normalized.csv.gz`, which is **not** a
declared resource and is not hashed. The pilot entity is missing required
dataset-mixin fields (`origin`, `tier`, `access`) and needs a pre-migration
prep commit (see §3.5).

---

## 2. Motivation and non-goals

### Why this is hard

Datasets carry bytes, not just markdown. Three structural differences from
Phase F:

1. **Two-file canonical**: a shared dataset lives as
   `commons/datasets/<slug>/{entity.md, datapackage.yaml, recipe/}`, not as
   a single `<slug>.md`. The kind-pluggable framework currently writes a
   single file per canonical entity.
2. **Real-byte hashing**: the canonical `datapackage.yaml` must carry
   `hash: sha256:...` and `bytes: ...` per resource (§3.2 makes this
   required from v1). Hashes are computed in-place against the existing
   project on-disk data; no movement.
3. **Side-channel override**: `~/.config/science/data.yaml` is written
   outside both commons and project repos. This is the per-machine pointer
   that the data resolver (Phase C) uses to find bytes after the descriptor
   moves to commons.

### Real-world snag in the corpus

The pilot project's entity descriptors live at `doc/datasets/data-<slug>.md`
and the Frictionless sidecars live at `data/.../datapackage.json`. Neither
file points at the other, and slug forms can differ (entity slug
`ccle-proteomics-nusinow-2020` vs Frictionless `name`
`mm30-external-ccle-proteomics-2020-01`). The parent design §8.4 assumes
the two files are co-located under `data/processed/<slug>/`, which doesn't
match what's on disk. Phase G resolves this by **requiring an explicit
`datapackage:` field on the project entity descriptor as a pre-migration
prerequisite** (matches §3.2 canonical surface; surgical and explicit).

### Non-goals (v1)

- `--relocate` flag (move bulk data to `$SCIENCE_DATA_ROOT/<slug>/`). v1
  is override-only — the project's data dir stays put; the commons
  descriptor + the per-machine override point at it.
- Derived datasets with `derivedFrom: [{path: <relative>}]` references.
  These need upstream-first ordering. v1 covers `origin: external` only;
  derived comes in v1.1 once the entity-only pattern is proven.
- Cross-project dedup. v1 supports one project per dataset slug. If two
  projects have the same dataset slug, promote fails with a clear message.
- Recipe execution / verification. Phase H + later concern. v1 stubs
  `recipe/README.md` when no project recipe is found. **`tier:` is
  user-authored and reflects scientific readiness, not recipe maturity**
  — promote never overwrites it. The audit log flags
  `recipe_stubbed: true` so the back-fill task is traceable separately
  (see §9 open question 1).
- Bio mixin extensions (RNA-seq / scRNA-seq / CNA). Phase H.

---

## 3. Architecture

### 3.1 Reuse the kind-pluggable framework

Add `PROMOTE_KIND_DATASET` alongside the existing `PROMOTE_KIND_PAPER`,
`PROMOTE_KIND_TOPIC`, `PROMOTE_KIND_THEME` constants. Discovery,
plan-time validation, audit logging, rollback envelope, and CLI surface
all reuse Phase F's machinery.

The CLI entry point matches Phase E/F:

```
science commons promote dataset --from <project-id> [--slug <slug>] [--apply]
```

`--slug` is new; scopes promotion to one dataset within the project. For
v1, the pilot always passes `--slug`. Without it, all eligible datasets in
the project are planned (this stays implemented but isn't exercised by the
pilot).

### 3.2 Multi-file canonical via the artifact-list model

The current promote model is single-file: `PromoteDecision.canonical_path`
and `.canonical_content` are singular, and the apply / cleanliness-check /
rollback paths each handle one path per decision
(`science/src/science_tool/commons/promote.py:185`,
`promote.py:824`). A callback alone won't extend cleanly. Phase G replaces
the singular fields with a list of canonical artifacts and threads the
list through every site that today reads `canonical_path`.

**Data model.** `PromoteDecision` and `PromoteResult` gain:

```python
@dataclass(frozen=True)
class CanonicalArtifact:
    path: Path                            # relative to commons root, e.g. datasets/<slug>/entity.md
    content: str                          # rendered file content (UTF-8)
    validator: Literal[
        "entity-mixin",                   # frontmatter must pass base + mixin
        "frictionless-datapackage",       # parse + validate via Frictionless
        "plain",                          # no validation (e.g., recipe stub)
    ]

class PromoteDecision:
    canonical_artifacts: list[CanonicalArtifact]   # replaces canonical_path/content
    ...

class PromoteResult:
    canonical_paths: list[Path]                    # replaces canonical_path
    ...
```

Paths are stored relative to the commons root; the apply stage resolves
them against `commons_root` before writing. Display surfaces (dry-run
output, error messages) may render the absolute form
`<commons-root>/datasets/<slug>/entity.md`, but the in-memory `path` field
is always commons-relative.

Single-file kinds (paper / topic / theme) produce a one-element list:
`[CanonicalArtifact(path=<subdir>/<slug>.md, content=<body>,
validator="entity-mixin")]`. The dataset kind produces three artifacts:

| Artifact | Path (commons-relative) | Validator |
|---|---|---|
| Entity surface | `datasets/<slug>/entity.md` | `entity-mixin` (frontmatter via base + mixin-dataset/1.0) |
| Frictionless sidecar | `datasets/<slug>/datapackage.yaml` | `frictionless-datapackage` (parse + check resources[].path uniqueness + hash format) |
| Recipe stub | `datasets/<slug>/recipe/README.md` | `plain` (only emitted if no project recipe found) |

**Sites that thread the list (not exhaustive — see implementation plan)**:

- Discovery output: still keyed by candidate, no artifact list yet.
- Plan stage: renders the artifact list for each candidate (canonical
  content + datapackage hashes + recipe stub if applicable).
- Plan-time validation: iterates the artifact list and dispatches by
  `validator` field. `entity-mixin` calls existing `EntityValidator.validate`;
  `frictionless-datapackage` parses with `frictionless` package's
  `Package` (or a minimal in-repo parser to avoid the dep) and checks the
  required field set we own (`resources[].path` non-empty,
  `resources[].hash` matches `^sha256:[0-9a-f]{64}$`,
  `resources[].bytes` non-negative int); `plain` does nothing.
- Commons cleanliness check: extends the set of "dirty paths under
  `commons_subdir/`" to include any path that appears in the planned
  artifact list (currently checks only `<slug>.md`).
- Commons write: iterates the artifact list, creating parent dirs and
  writing each content. The commons commit message stays one-per-decision
  (`promote: <type> <slug> via op <op-id>`).
- Tag creation: unchanged. One tag per decision: `<type>/<slug>/<version>`.
- Rollback for partial commons writes: clean up any path in the artifact
  list, not just `<slug>.md`. Implementation: track which artifacts were
  written so far in apply, and on failure restore each path via
  `_restore_paths_to_head` (`promote.py:723`) — `git checkout HEAD -- <rel>`
  if the path existed at HEAD, else `Path.unlink(missing_ok=True)`. Once
  commons is committed, tag-/override-/overlay-failure rollback uses
  `_rollback_step5` (`promote.py:1745`): delete created tags, `git reset
  --soft HEAD~1`, then per-path restore. Path-limited throughout — see
  §4.4.
- Audit log: records `canonical_paths: [<path>, ...]` instead of singular
  `canonical_path`.

The Phase F regression suite (paper / topic / theme single-file behavior)
is exercised end-to-end after the refactor to confirm the list-of-one
codepath is equivalent to the prior singular fields.

### 3.3 Project overlay surface and field routing

Project file `doc/datasets/data-<slug>.md` is rewritten as a minimal
overlay constrained by `overlay-1.1.json` (which has
`additionalProperties: false`). The pilot file has fields that the
overlay schema rejects (`ontologies: [biology]`, `datasets: [...]`,
`source_refs: [...]`, etc.); v1 routes each project entity field into
one of four buckets:

| Bucket | Examples | Disposition |
|---|---|---|
| **Canonical-only** | `id`, `type`, `title`, `description`, `datapackage`, `origin`, `tier`, `accessions`, `access`, `derivation`, `parent_dataset`, `siblings`, `consumed_by` | Move to canonical `entity.md` frontmatter. Stripped from overlay. |
| **Overlay-only** | `pin_version`, `relevance`, `hypothesis_links`, `task_links`, `project_tags`, `project_notes`, `source` | Keep in overlay frontmatter. Stripped from canonical. |
| **Both layers — append at read time** (`science:merge: append` on base) | `tags`, `ontology_terms`, `same_as` | Copied into canonical. Also kept on overlay if the project's value adds entries not present canonically (deduped per schema). Resolver concatenates at read time. |
| **Both layers — same value v1** (independent `replace` on base + overlay-1.1) | `created`, `updated`, `status`, `related`, `source_refs` | Copied into canonical (source date / status). Also copied into overlay with the same value at promote time. Overlay's `replace` wins at read; v1 keeps them identical so the merge result is unchanged. v2 may diverge them (overlay = project tracking history; canonical = source authorship). Documented in audit log. |
| **Dropped with audit** | `ontologies` (not in any schema), `datasets` (self-referential on a dataset entity — redundant with `id`), other project-local fields not in any schema | Dropped from both canonical and overlay. Each dropped `(field, value, source_path)` recorded in the audit log under `dropped_fields:`. Plan-stage output also shows them so the user can review before apply. |
| **Project-only body sections** | Free-text markdown sections | Preserved in the overlay body. |

Plan-time validation catches misrouted fields: if a canonical field is
unexpectedly absent (e.g., the dataset-mixin's required `origin`), the
plan halts with `PromoteValidationError` and the user is pointed at
pre-migration prep (§3.5). v1 deliberately does NOT extend `overlay-1.1`
to admit new fields; the routing policy keeps the overlay schema stable.

The minimal overlay shape after rewrite:

```yaml
---
id: "dataset:<slug>"
overlay_of: "dataset:<slug>"
pin_version: "1.0.0"
relevance: ""               # if present in original
hypothesis_links: []        # if present
task_links: []              # if present
project_tags: []            # if present
status: ""                  # if present (overlay-1.1 allows)
created: "..."
updated: "..."
---

<original project-only body sections, preserved verbatim>
```

The project's `data/.../datapackage.json` is **left untouched** in v1. The
per-machine override (§3.4) points at its parent directory. v2 / `--relocate`
will remove it.

### 3.4 Per-machine override

After commons write + commit + tag (and before project overlay rewrite —
§4.3 step 5), promote upserts one entry into `~/.config/science/data.yaml`:

```yaml
ccle-proteomics-nusinow-2020: /home/keith/d/cancer/cancer-types/multiple-myeloma/data/external/ccle_proteomics/2020-01
```

The value is the absolute path to the directory containing the project
datapackage.json (and its resources). The data resolver (Phase C, §4.1
step 2) uses this entry as the second lookup step.

Atomic write: load existing yaml (or empty), upsert, atomic temp-file +
rename. Backup written to `.bak.<op-id>` immediately before the upsert so
the failure-path can restore.

### 3.5 Pre-migration contract

Per dataset, before the apply step runs, the project entity descriptor
must declare the full set of dataset-mixin required fields plus the
`datapackage:` pointer. The mixin (`mixin-dataset-1.0.json`) requires:

- `id`, `type` (already present)
- `datapackage:` (project-relative path to the Frictionless sidecar)
- `origin: "external" | "derived"`
- `tier: "use-now" | "evaluate-next" | "track"`

Plus conditionals on `origin`:

- `origin: external` → requires `access` block with at minimum `level`
  and `verified`.
- `origin: derived` → requires `derivation` block with `workflow_recipe`
  and `inputs` (list of `dataset:<slug>` ids).

Promote fails-fast at discovery on datasets that are missing any of these
fields (recorded as a `FailedCandidate` per missing-field reason, with
the path to the project entity file). v1 deliberately does NOT synthesize
these from the Frictionless `mm30.external_source` or licenses — the
inputs are too project-specific and synthesis would mask real metadata
gaps. The pre-migration prep is an explicit user commit per dataset.

**Pilot example.** Before running Phase G promote on
`data-ccle-proteomics.md`, the user commits a frontmatter prep that adds:

```yaml
datapackage: data/external/ccle_proteomics/2020-01/datapackage.json
origin: external
tier: evaluate-next
access:
  level: public
  verified: true
  source_url: "https://gygi.hms.harvard.edu/publications/ccle.html"
```

(Specific values are user-chosen. The example reflects what is already
known about CCLE proteomics from the Frictionless sidecar prose; the user
authors the canonical statement.)

### 3.6 New error classes

- `PromoteResourceMissingError(slug, resource_name, resource_path)` —
  raised during discovery / hash-compute when a `resources[].path` doesn't
  resolve to a readable file. Recorded as a `FailedCandidate` on the
  enclosing dataset; doesn't abort the whole run.
- `PromoteOverrideConflictError(slug, existing_path, planned_path)` —
  raised during plan-time validation when `~/.config/science/data.yaml`
  already maps the slug to a different absolute path. Halts plan-time
  validation (fail-fast, before any writes).
- Existing `PromoteWriteError(stage="override_write", ...)` covers the
  apply-stage failure where the side-channel write fails.

---

## 4. Data flow

### 4.1 Discovery (read-only)

```
Inputs: --from <project-id> [--slug <slug>]

For each doc/datasets/data-*.md (or just doc/datasets/data-<slug>.md if
--slug given):
  1. Parse frontmatter via _parse_frontmatter_only.
  2. Classify: skip if id prefix != "dataset:" or kind/type != "dataset".
     Record FailedCandidate if explicit id has wrong prefix.
  3. Validate slug matches filename stem; slug regex
     ^[a-z0-9][a-z0-9-]{1,63}$ (dataset mixin slug rule).
  4. NEW: require frontmatter has `datapackage:` field. Record
     FailedCandidate if missing.
  5. NEW: resolve datapackage path relative to project root; verify the
     file exists. FailedCandidate if not.
  6. NEW: parse the project datapackage.json. For each resources[].path,
     resolve relative to the datapackage parent dir; verify each file
     exists. FailedCandidate if any resource is unreachable
     (PromoteResourceMissingError).
  7. Produce DatasetPromoteCandidate with: slug, project_slug,
     entity_source_path, datapackage_source_path, project_data_dir
     (parent of the project datapackage.json), canonical/project-only
     field splits, canonical_body, project_only_body, resource_paths.
```

Single-instance only in v1. If two projects produce the same slug, plan
halts with a clear error pointing at both files; no dedup is offered.

### 4.2 Plan (read-only)

```
For each candidate:
  1. Compute SHA-256 + byte count for each resource (streaming, 1 MiB
     chunks; per-resource progress so dry-run can report elapsed time +
     speed for the largest resources).
  2. Build canonical datapackage.yaml content:
     - Take project datapackage.json fields.
     - Inject computed hash: "sha256:<hex>" and bytes: <int> into each
       resources[] entry.
     - Strip project-only fields (mm30.*, conformsTo, derivedFrom in path
       form). Reset id and name to <slug>.
  3. Build canonical entity.md content:
     - Take base + dataset-mixin fields from the project entity
       descriptor.
     - Add datapackage: "datapackage.yaml" pointer (sibling, conventional
       name).
     - tier: is taken verbatim from the project descriptor (user-authored;
       promote never overwrites). The recipe stub flag is recorded in
       the audit log instead.
  4. Build recipe stub content if no project-side recipe was detected:
     recipe/README.md content =
       "# Recipe back-fill needed\n\n
        Acquisition: <source from entity.source or accessions>.\n
        Promote stubbed this README because no project recipe was
        detected. Replace with the acquisition or preprocessing
        workflow.\n"
     (`tier:` is left untouched on the canonical entity; recipe
     maturity is tracked via the audit log's recipe_stubbed flag.)
     Recipe detection in v1: always 'no recipe found'. (Recipe back-fill
     is left as future work — see open questions.)
  5. Build overlay content for the project file: id, overlay_of,
     pin_version, project-only fields kept, project body preserved.
  6. Build per-machine override delta: { <slug>: <abs path to
     project_data_dir> }. If user's existing data.yaml already maps this
     slug to a different absolute path → PromoteOverrideConflictError.
  7. Validate canonical entity surface against
     science-entity-base/1.0+mixin-dataset/1.0 and the overlay against
     overlay-1.1.json. Plan-time validation halts at first failure
     (Phase F rule).
```

### 4.3 Apply (writes, in order)

Phase G keeps Phase E/F's atomic-transaction shape: any failure after the
plan-time validation passes triggers an unconditional rollback to the
pre-apply state. The user is expected to fix the failure cause and
re-run from scratch — there is no resume-from-partial path. This matches
Phase F precedent (tag-existence preflight at `promote.py:808` already
rejects re-runs over partially-applied state, so resume would require
new content/tag-match semantics; deferred).

The order **commons → override → overlay** matters: after overlay rewrite
the project starts depending on the commons descriptor, and override
must already point at bytes when that flip happens. Writing override
before overlay keeps the resolver chain coherent.

```
1. Pre-flight (extends Phase F):
   - Commons clean (working tree empty, no untracked under any artifact
     path in the plan, or under .migrations).
   - Project pilot paths clean (doc/datasets/<file> in working tree).
   - ~/.config/science/data.yaml readable and parseable.
   - Existing override entry for this slug (if any) matches plan.
   - Tag dataset/<slug>/<version> does not already exist
     (Phase F preflight rule).

2. Write commons canonical artifacts (iterate canonical_artifacts list):
   commons/datasets/<slug>/entity.md
   commons/datasets/<slug>/datapackage.yaml
   commons/datasets/<slug>/recipe/README.md      (only if stubbed)

3. Commit in commons: "promote: dataset <slug> via op <op-id>"

4. Tag in commons: dataset/<slug>/<version>

5. Write per-machine override side-channel:
   - Read ~/.config/science/data.yaml (initialize empty if missing).
   - Write ~/.config/science/data.yaml.bak.<op-id> (backup of current).
   - Upsert <slug>: <abs path>.
   - Atomic write via temp-file + rename.

6. Write project overlay rewrite to working tree:
   <project>/doc/datasets/data-<slug>.md  (rewritten in place)

   The project's data/.../datapackage.json is LEFT UNTOUCHED in v1.

7. Write success audit log:
   commons/.migrations/<ts>-<op-id>.yaml
   Records: commons_commit, commons_tags, canonical_paths (list, not
   singular), project files touched, override file path + backup file
   path + line before/after, per-resource hashes, recipe_stubbed flag,
   dropped_fields list per §3.3.

8. Commit audit log in commons: "audit: op <op-id>"
```

### 4.4 Failure handling

Atomic-transaction semantics through step 6 (project overlay rewrite):
each failure from step 2 through step 6 unwinds all prior side effects of
the op before exiting, so the user sees either pre-apply or post-overlay
state — never partial. Steps 7-8 (audit log) are explicitly carved out
(see last bullet); a successful migration is not rolled back over an
audit-log failure.

All rollback is **path-limited**, matching Phase F precedent
(`_restore_paths_to_head` at `promote.py:723`, `_rollback_step5` at
`promote.py:1745`). Promote never runs `git reset --hard`, `git clean -fd`,
or `git checkout -- .` on the commons repo — only `git reset --soft
HEAD~1` (to undo a commit while leaving working-tree paths under our
control), per-path `git checkout HEAD -- <rel>`, and `Path.unlink` for
paths that didn't exist at HEAD. This preserves any unrelated user state
in the commons working tree.

State accumulated through the apply sequence is tracked in a per-op
context (`commons_artifacts_written: list[Path]`,
`commons_commit_sha: str | None`, `tags_created: list[str]`,
`override_backup_path: Path | None`, `overlay_rewritten: list[Path]`).
The rollback handler reads this and reverses each side effect that has
landed, in reverse order.

- **Before any writes** (discovery, plan, hash-compute, plan validation,
  preflight) → exit non-zero with `PromoteCandidateError` /
  `PromoteValidationError` / `PromoteResourceMissingError` /
  `PromoteOverrideConflictError`. No state touched anywhere.
- **Commons artifact write fails** (step 2) → call
  `_restore_paths_to_head(commons_root, commons_artifacts_written)` —
  for each artifact, `git checkout HEAD -- <rel>` if it existed at HEAD,
  else `Path.unlink(missing_ok=True)`. No commit yet. Failure audit log
  written best-effort.
- **Commons commit fails** (step 3) → call `_restore_paths_to_head` on
  the staged artifacts (same as step-2 failure). The Phase F commit
  failure path at `promote.py:849` is identical; reuse it. No override
  or overlay changes attempted.
- **Tag creation fails** (step 4, commit already succeeded) → mirror
  Phase F's `_rollback_step5` at `promote.py:862`/`promote.py:1745`:
  delete every tag in `tags_created`, `git reset --soft HEAD~1` to undo
  the commit, then per-path restore each artifact (`git checkout HEAD --
  <rel>` if it existed at HEAD, else `Path.unlink`). No override or
  overlay changes attempted.
- **Override write fails** (step 5) → restore override from
  `data.yaml.bak.<op-id>` (atomic rename back). Then unwind commons via
  the same `_rollback_step5` path (delete tag + `reset --soft HEAD~1` +
  per-path restore). No overlay changes attempted.
- **Project overlay rewrite fails** (step 6) → restore each path in
  `overlay_rewritten` via `git checkout HEAD -- <overlay-path>` in the
  project repo (Phase F pattern at `promote.py:896-905`). Then restore
  override from `data.yaml.bak.<op-id>`. Then unwind commons via
  `_rollback_step5`.
- **Audit log write or commit fails** (steps 7-8) — **excluded from
  atomic-transaction semantics.** The Phase F bugfix to `.gitignore`
  makes write+commit safe under normal conditions. If a disk-full or
  permission failure surfaces here anyway, leave all prior state in
  place: rolling back a successful migration over a log-write failure
  is worse than the alternative. Emit a clear stderr message including
  the rendered `failure_audit_yaml` payload (the same content the
  success path would have written) so the user can hand-place it into
  `<commons_root>/.migrations/<ts>-<op-id>.yaml` and commit it manually
  once the underlying issue is fixed. No new CLI command is added in v1.

Backup files (`data.yaml.bak.<op-id>`) are retained on success too — the
audit log records their location, so a later manual rollback can find
them.

The rollback handler is exercised by fault-injection tests at each
transition through step 6 (see §6.1). The audit-log failure path is
covered by a separate test that asserts the migration remains landed and
the failure exception carries a parseable `failure_audit_yaml` payload.

---

## 5. Schema additions

| Schema file | Change |
|---|---|
| `mixin-dataset-1.0.json` | Verify the field set matches what Phase G actually emits. Additive minor tweaks only (`parent_dataset`, `siblings`, `consumed_by` if missing). No `2.0` bump. |
| `overlay-1.1.json` | No change. Existing `pin_version` / `pin_effective_version` / `relevance` / `hypothesis_links` / `task_links` / `project_tags` etc. cover the dataset overlay surface. |
| `science-entity-base-1.0.json` | No change. `same_as` added during Phase F pilot generalizes to dataset entities. |
| Frictionless `datapackage.yaml` | No `science:*` extensions. Pure Frictionless Data Package v2. Resource `hash:` field carries `sha256:<hex>` prefix per design §4.2. |

---

## 6. Testing

Phase F's test file shape carries forward: one file per stage, plus an
integration test that drives `apply_promote` end-to-end with a synthetic
project under `tmp_path`.

### 6.1 Unit tests

| File | Scope |
|---|---|
| `tests/test_commons_promote_discovery.py` (append) | Dataset discovery: id-prefix rejection, missing `datapackage:` field, datapackage path doesn't resolve, resource path doesn't resolve (raises `PromoteResourceMissingError`), slug-stem mismatch. |
| `tests/test_commons_promote_dataset_plan.py` (new) | Hash-compute determinism (golden 12-byte fixture `hello world\n` → sha256 `a948904f...a447`); multi-resource plan; override-conflict detection (`PromoteOverrideConflictError`); canonical `entity.md` rendering; canonical `datapackage.yaml` rendering (project fields stripped, hashes injected, name reset to `<slug>`); recipe stub content when no project recipe; user-authored `tier:` preserved verbatim on the canonical (NOT overwritten when recipe stubbed); `recipe_stubbed: true` flag in the planned audit log. |
| `tests/test_commons_promote_dataset_apply.py` (new) | Multi-artifact canonical write (3 files, parent dir created); commons commit + tag; per-machine override upsert (new file path; existing file with other entries; conflict path); project overlay rewrite; dropped_fields recorded in audit log; rollback paths (atomic-transaction through step 6; path-limited only — never `reset --hard`, `checkout -- .`, or `clean -fd`): (a) artifact-write failure → `_restore_paths_to_head` over written artifacts; (b) commit failure → `_restore_paths_to_head` over staged artifacts; (c) tag-creation failure → `_rollback_step5` (delete tag + `reset --soft HEAD~1` + per-path restore); (d) override-write failure → restore `.bak.<op-id>` then `_rollback_step5`; (e) overlay-rewrite failure → `git checkout HEAD -- <overlay-path>` per project file + restore override + `_rollback_step5`. All five end with commons HEAD SHA + tags + per-artifact working-tree paths byte-identical to pre-apply, `~/.config/science/data.yaml` byte-identical to pre-apply, and unrelated commons working-tree state untouched. Separate test for audit-log failure (step 7-8): assert migration remains landed and the raised `PromoteWriteError` carries a non-empty `failure_audit_yaml` payload that re-renders identically to a manually-placed audit file. |
| `tests/test_commons_promote_kind_pluggable.py` (touch) | Cover the new `canonical_artifacts` list model: paper / topic / theme kinds produce a one-element list (regression that single-file rendering is preserved); dataset kind produces three CanonicalArtifact entries with the expected validators. |

### 6.2 Integration test

One end-to-end test:

- Set up synthetic project under `tmp_path`:
  - `doc/datasets/data-fixture-ds.md` with frontmatter passing the full
    mixin-required set:
    ```yaml
    id: dataset:fixture-ds
    type: dataset
    title: "Fixture dataset"
    datapackage: data/fixture-ds/datapackage.json
    origin: external
    tier: evaluate-next
    access:
      level: public
      verified: true
    created: "2026-05-18"
    updated: "2026-05-18"
    ```
  - `data/fixture-ds/datapackage.json` (Frictionless, 2 resources).
  - `data/fixture-ds/r1.txt` (12 bytes, content `"hello world\n"`) and
    `data/fixture-ds/r2.txt` (37 bytes).
- Configure commons under `tmp_path`; set `XDG_CONFIG_HOME=<tmp_path>/.config`
  via `monkeypatch.setenv` so the override write
  (`get_science_config_dir() / "data.yaml"`) is sandboxed.
- Call `apply_promote` with `kind=PROMOTE_KIND_DATASET`,
  `project_id="fixture-proj"`, `slug="fixture-ds"`.
- Assert:
  - `commons/datasets/fixture-ds/entity.md` exists and validates.
  - `commons/datasets/fixture-ds/datapackage.yaml` exists, has 2 resources
    each with `hash: sha256:...` and `bytes: <int>`.
  - `commons/datasets/fixture-ds/recipe/README.md` exists with stub
    content.
  - 1 commons commit + 1 audit commit + 1 dataset tag.
  - Project overlay file rewritten with `overlay_of: dataset:fixture-ds`,
    `pin_version: 1.0.0`.
  - `<sandbox>/.config/science/data.yaml` has
    `fixture-ds: <abs path>` line.
  - Backup `data.yaml.bak.<op-id>` exists alongside `data.yaml`.

### 6.3 Hash determinism fixture

Golden fixture under `tests/fixtures/promote_dataset/`:

```
hello.txt        12 bytes "hello world\n"
                 sha256 = a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447
```

Pinned in `test_commons_promote_dataset_plan.py` to detect any drift in
the hashing implementation.

---

## 7. Pilot rollout

Companion runbook: `docs/plans/2026-05-18-commons-promote-datasets-pilot.md`.

### Preconditions

1. Commons store initialized and clean. `.gitignore` no longer ignores
   `.migrations/` (Phase F bugfix committed at `7c7fff0`).
2. `multiple-myeloma` registered in `~/.config/science/config.yaml` with
   stable `id: multiple-myeloma`.
3. Pilot project working tree clean in `doc/datasets/data-ccle-proteomics.md`
   and `data/external/ccle_proteomics/2020-01/`.
4. **Pre-migration step** (manual, not part of promote): user adds the
   full required dataset-mixin set to `doc/datasets/data-ccle-proteomics.md`
   frontmatter, committed separately:

   ```yaml
   datapackage: data/external/ccle_proteomics/2020-01/datapackage.json
   origin: external
   tier: evaluate-next            # user-chosen; reflects scientific readiness
   access:
     level: public
     verified: true
     source_url: "https://gygi.hms.harvard.edu/publications/ccle.html"
   ```

   These are exactly the fields the discovery preflight will check
   (§3.5). Skipping any of them causes a `FailedCandidate` per missing
   field.
5. `~/.config/science/data.yaml` either doesn't exist or doesn't already
   map `ccle-proteomics-nusinow-2020` to a conflicting path.

### Dry-run

```
science commons promote dataset \
  --from multiple-myeloma \
  --slug ccle-proteomics-nusinow-2020
```

Expected output:
- 1 candidate planned, 0 failed.
- Canonical artifact list (3 paths under
  `commons/datasets/ccle-proteomics-nusinow-2020/`): `entity.md`,
  `datapackage.yaml`, `recipe/README.md`.
- Per-resource hash + bytes (2 hashes; ~1.3 MB total; dry-run completes
  in well under a second).
- Per-machine override line to be written.
- Project overlay rewrite stat (one file modified).
- Dropped fields list (per §3.3): expect `ontologies`, `datasets` (the
  redundant slug-on-self field), and possibly others depending on
  what the pre-migration prep commit added or left.

### Apply

```
science commons promote dataset \
  --from multiple-myeloma \
  --slug ccle-proteomics-nusinow-2020 \
  --apply
```

Expected: 1 commons commit + 1 audit commit + 1 `dataset/ccle-proteomics-nusinow-2020/1.0.0`
tag, 1 project overlay rewritten (uncommitted), 1 line upserted to
`~/.config/science/data.yaml` (with `.bak.<op-id>` backup retained).

User then commits the project overlay manually (matches Phase E/F pattern):

```
cd ~/d/cancer/cancer-types/multiple-myeloma
git diff doc/datasets/data-ccle-proteomics.md
git add doc/datasets/data-ccle-proteomics.md
git commit -m "docs(datasets): promote ccle-proteomics to commons (Phase G pilot)"
```

### Verify

```
science commons inventory | rg '"id": "dataset:ccle-proteomics-nusinow-2020"'
# expect: 1 hit

science commons show dataset:ccle-proteomics-nusinow-2020 --project multiple-myeloma
# expect: merged entity reads correctly

science commons data resolve dataset:ccle-proteomics-nusinow-2020 mm-cell-lines.parquet
# expect: returns the original project absolute path (via the override) and
# verifies the parquet bytes against the canonical hash
```

If `inventory`, `show --project`, and `data resolve` all succeed, the
pilot has exercised the full Phase G path.

### Rollback hints

The audit log records every touched file. Path-limited rollback only.
- Commons: `git revert <commons-commit>` (success-path) or
  `git reset --hard <prior>` (rare; pilot only). Delete the dataset tag
  only — never wildcard.
- Project: `git checkout HEAD -- doc/datasets/data-ccle-proteomics.md`.
- Override: copy back from `data.yaml.bak.<op-id>` (path in audit log).

Do not hard-reset any user repository. Rollback is path-limited so
unrelated work is preserved.

---

## 8. Implementation phases

| Phase | Scope |
|---|---|
| **G.1 Canonical artifact model** | Replace `PromoteDecision.canonical_path` / `.canonical_content` with `canonical_artifacts: list[CanonicalArtifact]` (path, content, validator). Replace `PromoteResult.canonical_path` with `canonical_paths: list[Path]`. Thread the list through plan-time validation (dispatch by `validator` field), commons cleanliness check, commons write, partial-write rollback, audit log. Single-element list for paper/topic/theme kinds preserves Phase F behavior; regression test confirms equivalence. |
| **G.2 Discovery (datasets)** | Dataset-specific discovery: `datapackage:` field check; required mixin fields (`origin`, `tier`, conditional `access`/`derivation`) check; project datapackage parses; resource files exist (`PromoteResourceMissingError`); field-routing policy (canonical / overlay / dropped buckets) returned with the candidate so plan-stage can render the dropped-fields list. |
| **G.3 Hash + plan** | Streaming sha256 + byte count per resource; canonical `datapackage.yaml` rendering (project datapackage fields stripped, hashes injected); canonical `entity.md` rendering; recipe stub content; plan-time validation per artifact (`entity-mixin` / `frictionless-datapackage` / `plain`). |
| **G.4 Override side-channel** | Read/write `~/.config/science/data.yaml` via `get_science_config_dir() / "data.yaml"`; backup-before-upsert (`data.yaml.bak.<op-id>`); `PromoteOverrideConflictError`; sandbox-friendly via `XDG_CONFIG_HOME` for tests. |
| **G.5 Apply (with new ordering)** | Multi-artifact commons write; commit + tag; **then** override side-channel; **then** project overlay rewrite. Audit log records `canonical_paths`, `override_file`, `override_backup`, `dropped_fields`. Failure-path restores match §4.4. |
| **G.6 Integration test** | End-to-end synthetic-project test under `tmp_path` (§6.2) plus fault-injection tests for each failure transition. |
| **G.7 Pilot runbook** | Author the companion `2026-05-18-commons-promote-datasets-pilot.md`. |

---

## 9. Open questions

Resolvable at implementation time without changing load-bearing design
decisions.

1. **Recipe back-fill**: if a `Snakefile` exists somewhere in the project
   (e.g., `pipeline/<task-id>/Snakefile`), should promote copy it into
   `commons/datasets/<slug>/recipe/`? v1 pilot: always stub. The discovery
   heuristic is brittle and copying executable code without review is
   risky. Defer auto-copy to v1.1.
2. **Override file YAML preservation**: `~/.config/science/data.yaml` may
   carry user comments. `yaml.safe_dump` loses them. v1 pilot: load,
   upsert, dump (loses comments); add a one-line
   `# managed by science commons promote` header. v2: switch to
   `ruamel.yaml` round-trip if comments matter.
3. **Hash algorithm**: sha256 only in v1. `hash:` carries `sha256:` prefix
   for future migration (design §4.2).
4. **Derived datasets**: out of v1 scope. v1.1 needs an ordering pass that
   promotes upstream-first. Until then, derived datasets with
   `derivedFrom: [{path: <relative>}]` fail at discovery with a clear
   message pointing to v1.1.

---

## 10. Acceptance criteria

The Phase G implementation is done when:

1. All unit + integration tests pass.
2. `science commons promote dataset --from multiple-myeloma --slug ccle-proteomics-nusinow-2020`
   (dry-run) completes with the expected plan summary.
3. The same command with `--apply` produces:
   - 1 commons commit + 1 audit commit
   - 1 `dataset/ccle-proteomics-nusinow-2020/1.0.0` tag
   - 1 project overlay rewritten (uncommitted, manually committed by user)
   - 1 line added to `~/.config/science/data.yaml`
4. `science commons inventory`, `science commons show ... --project ...`,
   and `science commons data resolve <dataset-id> <logical-path>` all
   succeed against the migrated dataset.
5. Rollback from a fault-injected failure at every transition **through
   step 6** (commons artifact write, commit, tag, override, overlay)
   leaves the commons repo (HEAD SHA, tags, per-artifact working-tree
   paths) and `~/.config/science/data.yaml` byte-identical to their
   pre-apply state, with unrelated commons working-tree state untouched.
   Audit-log failure (steps 7-8) is explicitly excluded — the migration
   remains landed and the user is given the rendered audit yaml to
   hand-place.
