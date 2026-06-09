# Substrate Phase 4a — `terms.yaml` coined-concept promotion

> Part of the structural-aggregate retirement line (§B5 of
> `2026-06-06-knowledge-meta-model-and-substrate-design.md`). Phases 3a–3c
> retired the `entities.yaml` `coined`/`cruft`/`shadow`/`decision-log` buckets
> (merged `ce3ea5f7` / `3a0d0335` / `409a76c7`). **Phase 4** finishes the job;
> decomposed into **4a (this doc — `terms.yaml` coined concepts) → 4b
> (external-reference resolver, §B2/B3a/D4) → 4c (ambiguous adjudication +
> `AggregateAdapter` deprecated-owner-mode removal, §C3)**.

## Goal

Extend the existing 3b/3c retirement executor to also retire the **coined
`concept` rows in `knowledge/sources/<profile>/terms.yaml`** — promoting each to
an id-preserving owner file under `entities/concepts/<slug>.md` (the built-in
`concept` path policy, `entities.py:59`) whose **body preserves the row's
`description`** as the definition. After 4a, the single largest remaining
aggregate bucket (≈108 coined concepts in MM30's `terms.yaml`) has a clean
promotion path. Everything else in `terms.yaml`
(the `ambiguous` rows) and all `external-ref` rows stay untouched, deferred to
4b/4c.

## Scope decisions (locked during brainstorming)

- **`terms.yaml` coined, concept in practice.** 4a admits `terms.yaml` into the
  executor's retirement scope but promotes **only** the `coined` bucket.
  `ambiguous` rows (e.g. `protein:`/`method:` vocabulary with external ids) are
  left in place — they are 4c's per-row judgment work. The planner already
  enforces this: bucket dispatch promotes only `COINED` under `--promote-coined`,
  leaving `AMBIGUOUS` a no-op. The `COINED` bucket is `concept`/`latent`
  (`_COINABLE_KINDS`), but the executor stays **kind-generic** — it does not
  special-case `concept`. Promotion is gated by `_promote_target`'s path-policy
  conformance: `concept` has a built-in `slug` policy (`entities/concepts/`), so
  concepts promote; `latent` is a project-local kind that **defaults to the
  `numeric` strategy** unless the project manifest declares otherwise, so a
  `latent:<slug>` id is **rejected/retained** by `_promote_target` (never
  renumbered) until MM30's manifest grants `latent` a conforming policy (project
  Task #30). 4a therefore promotes the ≈108 `terms.yaml` **concepts**; any
  `latent` rows surface as `rejected` rather than mis-promoted — no special code.
- **One flag, spans both files.** `--promote-coined` now promotes coined rows
  from **both** `entities.yaml` and `terms.yaml` in a single pass — consistent
  semantics, no new flag. Blast radius is contained by the unchanged v3 `--apply`
  gate (MM30 is v2 → cannot apply until project Task #30).
- **Single-type aggregates stay out of scope.** The `doc/<plural>/<plural>.{json,yaml}`
  topic/dataset aggregates are *not* admitted. 4a covers exactly the two
  multi-type files (`entities.yaml`, `terms.yaml`). Keeping this boundary tight
  prevents 4a from becoming a broader aggregate-system rewrite.
- **Identity from the compiled model (§C2).** The executor must **not**
  reimplement `id`→`canonical_id` or `kind` inference. Row identity comes from
  the compiled triage/meta; only authoring **content** fields (`title`,
  `description`, `profile`) are pulled from the raw aggregate row.
- **Tooling now, live migration later.** As in 3b/3c, `--apply` stays v3-gated;
  4a never mutates v2 MM30. The live MM30 promotion runs under project Task #30.

## Why this is small (and where it is not)

The 3a triage classifier has **no filename firewall** — it already classifies
`terms.yaml` rows (that is how the 3b inventory found ≈108 coined + ≈81
ambiguous there). The firewall lives only in the **executor**
(`aggregate_retire.py:124`, `name != "entities.yaml"`). So most of 4a is
"widen the firewall." Two non-trivial catches make it more than a one-line
change:

1. **Root key.** `terms.yaml`'s YAML root key is `terms:`, not `entities:`
   (per the adapter's `_MULTI_TYPE_FILES = {"entities.yaml": "entities",
   "terms.yaml": "terms"}`). The executor's `_read_entries`/`_rewrite_aggregate`
   hardcode `data["entities"]`; run as-is against `terms.yaml` they would read
   zero rows and rewrite the file with a wrong/empty root.

2. **Row schema differs across files.** `entities.yaml` rows carry explicit
   `canonical_id` + `kind` + `title`; `terms.yaml` rows carry `id` (no explicit
   `kind`) + `title` + `description`. The loader normalizes the `terms.yaml`
   shape (`AggregateAdapter` lines 125–136: `id`→`canonical_id`, `kind` from the
   `concept:` prefix), but the executor re-reads **raw** YAML and applies none of
   that — so today every `terms.yaml` row would fail the executor's
   `canonical_id`/`kind` required-field check. The §C2-aligned fix is to take
   identity from the compiled model, not the raw row.

## Architecture

`graph/aggregate_retire.py` stays the orchestration layer; the change is
localized there plus a small public-API promotion in the adapter. No new module.

```
storage_adapters/aggregate.py
  MULTI_TYPE_AGGREGATE_ROOT_KEYS = {"entities.yaml": "entities", "terms.yaml": "terms"}   (public)
  multi_type_root_key(filename) -> str | None                                             (helper)
        │ imported by
        ▼
graph/aggregate_retire.py
  firewall:        name in MULTI_TYPE_AGGREGATE_ROOT_KEYS      (was: == "entities.yaml")
  _read_entries:   root key = multi_type_root_key(basename)    (was: hardcoded "entities")
  _rewrite_aggregate: same
  promote branch:  identity ← pr.triage (compiled model); content ← raw entry
  _owner_text:     body = description (when str & non-empty) else _STUB_BODY
```

### Component 1 — public multi-type-file API (`storage_adapters/aggregate.py`)

Promote the private `_MULTI_TYPE_FILES` to a public constant
`MULTI_TYPE_AGGREGATE_ROOT_KEYS` (same `{filename: root_key}` mapping) and add a
helper:

```python
def multi_type_root_key(filename: str) -> str | None:
    """Root key for a multi-type aggregate file, or None if not one."""
    return MULTI_TYPE_AGGREGATE_ROOT_KEYS.get(filename)
```

Update the adapter's own internal references. This is the single source of truth
for *which* files are multi-type aggregates and *what* their root keys are; the
executor imports it rather than mirroring a constant (no drift).

### Component 2 — firewall + root-key-aware read/rewrite (`aggregate_retire.py`)

- Replace the `_ENTITIES_FILE` constant and the `name != _ENTITIES_FILE` firewall
  (`:124`) with membership: `if Path(meta.path).name not in
  MULTI_TYPE_AGGREGATE_ROOT_KEYS: continue`.
- `_read_entries(project_root, rel)`: `root_key = multi_type_root_key(Path(rel).name)`;
  read `data.get(root_key) or []`. (A non-multi-type `rel` never reaches here —
  the firewall already excluded it — but if `root_key` is None, return `[]`.)
- `_rewrite_aggregate(project_root, rel, drop)`: same `root_key` derivation;
  rewrite `data[root_key] = [row for i, row in enumerate(items) if i not in drop]`.
  Drop-by-index logic is otherwise unchanged.

### Component 3 — description-preserving, schema-agnostic owner renderer

Rewrite `_owner_text` to take explicit fields rather than a raw dict:

```python
def _owner_text(canonical_id, kind, title, description, profile, *, promoted_from) -> str:
    fm = {"id": canonical_id, "type": kind, "title": title}
    if profile:
        fm["profile"] = profile
    fm["promoted_from"] = promoted_from
    body = description.rstrip("\n") + "\n" if isinstance(description, str) and description else _STUB_BODY
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body
```

- **`description` becomes the body** (the §B5 "line of definition") when it is a
  **non-empty string**; a non-string/empty/absent `description` is treated as
  absent → the existing `_STUB_BODY`. Exact string content is preserved with a
  single trailing newline.
- Frontmatter is unchanged: `id`/`type`/`title`/`[profile]`/`promoted_from`.

In `apply_retirement`'s promote branch (the non-decision arm):

```python
entry = entries(pr.source_path)[pr.line]
title = entry.get("title")
if not title:
    rejected.append((pr.triage.canonical_id, "missing required field title"))
    continue
# identity from the compiled model (§C2); content from the raw row.
text = _owner_text(
    pr.triage.canonical_id, pr.triage.kind, title,
    entry.get("description"), entry.get("profile"),
    promoted_from=pr.source_path,
)
```

- `_REQUIRED_FIELDS` (`canonical_id`/`kind`/`title`) collapses to a **`title`-only**
  raw-row check — identity (`canonical_id`, `kind`) is guaranteed present on the
  triage. Behavior-preserving for `entities.yaml` (its raw `canonical_id`/`kind`
  already equal the triage values); makes `terms.yaml`'s `id`-only rows promote
  instead of being rejected.
- The decision arm (3c `render_owner_file`) is untouched.

### Component 4 — precise triage join (`aggregate_triage.py` + planner)

With two files in scope, the planner's id-keyed triage lookup is lossy: a
`canonical_id` present in both files (e.g. coined in one, ambiguous in the other)
could inherit the wrong bucket/action.

- Add `path: str | None` and `line: int | None` to `AggregateRowTriage`. The
  classifier already has them via `decl.source_ref` (`aggregate_triage.py:73`);
  populate at construction (`ref.path`/`ref.line`, both `None` when `source_ref`
  is `None`).
- `plan_retirement`: replace `triage_by_id = {t.canonical_id: t for t in rows}`
  with `triage_by_ref = {(t.path, t.line): t for t in rows}` and look up
  `triage_by_ref.get((meta.path, meta.line))`. `(path, line)` uniquely
  identifies an aggregate row, so cross-file id collisions can no longer
  mis-route. Behavior-identical for the existing single-file case (ids were
  unique within `entities.yaml`).

## Behavior preserved

- v3 `--apply` gate unchanged; `--promote-coined` is the only flag involved.
- Decision-kind interception (3c) and `--promote-decisions`/`--delete-cruft`/
  `--delete-shadow` paths unchanged.
- `entities.yaml`-only runs behave exactly as in 3b/3c.
- Single-type/topic aggregates excluded.

## Error handling

- Malformed row missing/empty `title` → `rejected` (fail-early), row retained.
- Non-conforming coined id (slug strategy) → `rejected`/retained via the
  existing `_promote_target` conformance belt; never renumbered.
- Non-string/absent `description` → owner gets the stub body, not a crash.
- A `rel` whose basename is not a multi-type file → `multi_type_root_key`
  returns `None`; `_read_entries` returns `[]` (defensive; firewall already
  prevents reaching here).

## Testing (TDD; 3b/3c fixture style — `profiles: {local: local}` + local `manifest.yaml`)

1. **terms coined promotes with description body.** A `terms.yaml`
   `concept:<slug>` with a `description` → promotes to `entities/concepts/<slug>.md`;
   owner body equals the description (single trailing newline); `promoted_from`
   marker present; row dropped from `terms.yaml`.
2. **Reload parity for `content_preview`.** Load the promoted owner → the loaded
   entity's body/`content` preserves the definition and `content_preview` is
   non-empty. (The promoted definition lives in the owner **body**, not a
   frontmatter `description`, so the operative fallback is
   `content`→`content_preview` at `sources.py:701`, not the
   `description`→`content_preview` arm.)
3. **terms ambiguous untouched.** A non-self-sourced `terms.yaml` row
   (`source_path: doc/something.md`, kind not coinable) → `AMBIGUOUS`; not
   promoted, not deleted, survives the rewrite. *(The fixture must set a
   non-self-source: a self-sourced `concept:x` would bucket `COINED`.)*
4. **`_rewrite_aggregate` preserves the `terms:` root.** After a promote+rewrite,
   `terms.yaml` still parses with a `terms:` top-level list (not `entities:`).
5. **Mixed run.** One `entities.yaml` coined + one `terms.yaml` coined promote in
   a single `--promote-coined` pass; each source file is rewritten exactly once.
6. **Duplicate id across files routes by `(path, line)`.** Same `canonical_id`
   appears as coined in `entities.yaml` and as a **non-self-sourced** ambiguous
   row in `terms.yaml` → only the coined row promotes; the ambiguous row is
   untouched.
7. **Non-conforming terms id → rejected/retained.** e.g. `concept:Bad_Slug` →
   `rejected`, row stays in `terms.yaml`.
8. **`_owner_text` description handling.** Unit: non-empty string → body; empty
   string / non-string / absent → `_STUB_BODY`; trailing-newline normalization.
9. **Public API.** `multi_type_root_key("terms.yaml") == "terms"`,
   `multi_type_root_key("entities.yaml") == "entities"`,
   `multi_type_root_key("topics.json") is None`.

## MM30 smoke (still v2)

`science entities triage-aggregate --promote-coined --apply` stays **refused,
exit 1** (v3 gate); the dry-run now additionally lists the ≈108 `terms.yaml`
coined concepts as promotable. No mutation; MM30 git-clean.

## Out of scope (later phases)

- `external-ref` rows (recognize-as-external + drop owner) → **4b** (§B2/B3a/D4).
- `ambiguous` adjudication (concept→file / external→ref / delete) → **4c**.
- `AggregateAdapter` deprecated-owner-mode removal → **4c** (blocked until all
  rows clear).
- Single-type/topic aggregate retirement → not in Phase 4.
