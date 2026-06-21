---
id: "plan:2026-06-21-dataset-catalog-cli-design"
type: "plan"
title: "Dataset catalog CLI — ergonomic authoring, listing, and candidate lifecycle"
status: "active"
created: "2026-06-21"
updated: "2026-06-21"
related:
  - "plan:2026-04-19-dataset-entity-lifecycle-design"
---

# Dataset catalog CLI — ergonomic authoring, listing, and candidate lifecycle

## Purpose

Make the singular `science dataset` group an ergonomic **catalog** surface: hand-author a
not-yet-acquired dataset, list/filter the catalog richly, and inspect a single entry. This completes
the read/inspect commands that `plan:2026-04-19-dataset-entity-lifecycle-design` already approved but
left unbuilt (`show`, `consumers`, rich `list` filters), and adds two genuinely new capabilities
motivated by recent cataloguing work in `health-post-acute-infection` (t013): a `dataset add`
authoring command and a first-class **candidate** (not-yet-acquired) lifecycle state.

**Guiding principle.** Acquisition-lifecycle (`status`) is orthogonal to priority (`tier`).
`status: candidate` means "catalogued but we don't have the data yet"; `tier`
(`use-now`/`evaluate-next`/`track`) means "how much we want it." The data-package pointer is required
**iff** the dataset is acquired.

## Scope decomposition

**In scope (v1):**
- `dataset add <slug>` — author a candidate external dataset entity.
- `dataset show <slug>` — full single-entity view.
- `dataset list` rework — rich table + `--status/--candidate`, `--tier`, `--unverified`, `--level`,
  `--commons`; plus the `type: dataset` filter bugfix.
- `dataset consumers <slug>` — reverse lookup via the entity's `consumed_by`.
- `validate/checks/dataset_acquisition.py` — enforce "acquired ⇒ datapackage required".
- Tests + this design doc + the companion implementation plan.

**Out of scope (deferred, with reason):**
- `dataset list --stale-review --months N` — needs date arithmetic and a freshness policy; follow-on
  once the table lands. (Was in the 2026-04-19 surface.)
- `dataset verify <slug>` — external-verification automation; already deferred upstream.
- Collapsing the singular `dataset` group into the plural `datasets` (discovery/download) group —
  considered and **rejected** this session (see Key decision 1).
- The strict JSON-schema mixin change — **rejected** in favour of a friendly validate check (Key
  decision 3).

**Adjacent, not in this plan:** `health-post-acute-infection` has ~8 catalog entities with
`license: restricted`/`commercial` (unrecognized → soft warnings). `dataset add` prevents new
occurrences by defaulting to the recognized sentinel `unknown`; fixing the existing ones is a separate
2-line cleanup in that project.

## Architecture

The singular `dataset` group (`~/d/science/science/src/science_tool/cli.py:5171`) keeps its current
three commands (`list`, `register-run`, `reconcile`) and gains three read commands + one author
command. The plural `datasets` group (discovery/download) is **untouched**. No caller of
`science dataset register-run|reconcile` (workflow templates, skills, tests) is affected.

```
science/src/science_tool/
  cli.py
    dataset_group  (@main.group "dataset")          MODIFY
      dataset list          ── rework: table + filters + type-filter   MODIFY
      dataset show          ── NEW
      dataset add           ── NEW
      dataset consumers     ── NEW
      dataset register-run  ── UNCHANGED
      dataset reconcile     ── UNCHANGED
  entities.py                                         REUSE (create helpers)
  datasets_catalog.py        ── NEW (add/show/list/consumers logic, thin CLI)
  validate/
    checks/dataset_acquisition.py  ── NEW
    checks/__init__.py             ── MODIFY (register the check)
science/model/src/science_model/templates/
  dataset.md                 ── MODIFY (default status: active → candidate)
science/tests/
  test_dataset_add_cli.py          ── NEW
  test_dataset_show_cli.py         ── NEW
  test_datasets_list_cli.py        ── MODIFY (filters + type-filter + --commons)
  test_dataset_consumers_cli.py    ── NEW
  test_dataset_acquisition_check.py  ── NEW
docs/plans/
  2026-06-21-dataset-catalog-cli-design.md   ── THIS
  2026-06-21-dataset-catalog-cli-plan.md     ── companion (writing-plans)
```

Command logic lives in a new `datasets_catalog.py` module (keeping `cli.py` thin, matching how
`register-run` delegates to `datasets_register.py`).

### `dataset add <slug>`

Authors a **candidate external** dataset entity at `doc/datasets/<slug>.md`. The `dataset` kind has a
registry entry but **no path policy**, so `generate_entity_id` would raise
(`resolve_path_policy("dataset").strategy`); `add` instead **synthesizes `dataset:<slug>` directly** —
it validates the slug with `validate_slug(slug)` (pattern + length only; no path policy) and constructs
`f"dataset:{slug}"`. (`validate_entity_id` is also unusable: it likewise calls
`resolve_path_policy("dataset").strategy`.) This is the direct-construction approach `register-run`
uses. It still reuses the prospective-write validation (`_validate_prospective_write`) and the atomic
temp-file replace, and populates the dataset-specific frontmatter the generic `create_entity` does not
know about.

Options: `--title` (required), `--origin external|derived` (default `external`), `--tier` (default
`track`), `--level` (default `controlled`), `--source-url`, `--ontology-term` (repeatable),
`--related` (repeatable), `--project-root`. `--origin` is defined explicitly so the derived-rejection
guard below emits a friendly error rather than Click's "No such option".

Emitted frontmatter (the candidate shape proven out in the t013 catalog):

```yaml
id: dataset:<slug>
type: dataset
title: "<title>"
status: candidate
created/updated: <today>
origin: external
source_class: observational      # default; --source-class to override
tier: <tier>
license: unknown                 # recognized sentinel → no warning
access:
  level: <level>
  availability: available
  verified: false
  source_url: "<url>"
accessions: []
ontology_terms: [...]
related: [...]
```

Body: a short candidate template (What it is / Why it fits / Coverage table / Access caveats).

Guard rails (fail-early): `--origin derived` is **rejected** with a pointer to `register-run`
(derived datasets are machine-authored, never hand-written). Destination-exists → error (mirrors
`create_entity`). Runs prospective validation and prints any warnings.

### Ref forms and scope resolution (`show`, `consumers`)

`dataset list` prints canonical ids (`dataset:foo`) and `--commons` rows are not under local
`doc/datasets/`, so `show`/`consumers` must not be naive `doc/datasets/<arg>.md` lookups. A shared
resolver:

1. **Accepts either form** — `foo` or `dataset:foo` — normalizing by stripping a leading `dataset:`.
2. **Resolves local first:** `doc/datasets/<slug>.md`.
3. **Falls back to commons** via `CommonsQuery(commons_root).show("dataset:<slug>")` when not found
   locally (so a `--commons` row the user just saw resolves).
4. **Clear miss:** if absent in both, exit 2 with a message naming both scopes searched.

Reuse `resolve_entity_ref` for the local side and `CommonsQuery` for the commons side rather than
re-globbing.

### `dataset show <slug|dataset:slug>`

Resolves the ref (above), prints a formatted view: key frontmatter (id, title, status, tier,
origin, access level/verified, license, accessions, source_url), the resolved `related` and
`consumed_by` lists, and the body.

### `dataset list` (rework)

Replaces the bare `f"{id}  {title}"` loop with a `rich` table (the table primitive already used by
`science tasks list`). Columns: id, title, status, tier, origin, level, verified.

- **Bugfix:** only include entries whose frontmatter `type == "dataset"` (today's loop prints any
  parseable `.md`, which is why the legacy combined note `2026-06-20-public-cross-trigger-geo-sets.md`
  renders titleless).
- **Filters** (all on raw frontmatter fields): existing `--origin`; new `--status <s>` and
  `--candidate` (shorthand for `--status candidate`), `--tier <t>`, `--unverified`
  (`access.verified == false`), `--level <l>`.
- **`--commons`:** also enumerate commons dataset entities via
  `CommonsQuery(commons_root).find("dataset")` — the registry-backed catalog query.
  (`load_project_sources(include_commons=True)` only pulls *referenced* commons ids + overlays, **not**
  the full catalog, so it is wrong here.) Each `CommonsEntityRecord` carries
  `canonical_id`/`title`/`frontmatter_json`/`datapackage_path` for the table; tag rows as commons so
  local vs commons is visible.

### `dataset consumers <slug|dataset:slug>`

Resolves the ref (above), reads the entity's `consumed_by` list, and prints each consumer (plans,
workflow-runs). Exit 2 if the entity is missing; prints "no recorded consumers" when empty.

### `validate/checks/dataset_acquisition.py`

Mirrors `dataset_taxonomy.py` (read raw frontmatter via the `dataset_frontmatters` helper, re-enforce
a schema-critical rule with a friendly message). The acquired-data signal is the presence of a data
pointer — **`datapackage` OR `local_path`** — not `status` alone; `local_path` is the template's
single-file escape hatch ("mutually exclusive with datapackage") and `register-run` writes derived
entities as `status: active` **with** a `datapackage`, so both must satisfy the check.

Rule `dataset.acquired-without-pointer`:

- `status != "candidate"` **and** neither `datapackage` nor `local_path` is populated →
  `Severity.ERROR` (fails the run). Message names the slug and the fix: "set `status: candidate` if
  not yet acquired, or add a `datapackage`/`local_path` pointer."
- `status == "candidate"` → pass regardless of pointers (the supported not-yet-acquired state).
- any non-candidate **with** a pointer → pass.

Registered in `validate/checks/__init__.py`.

### `dataset.md` template default

Change the hand-author template's `status: "active"` → `status: "candidate"`. The template currently
ships `active` with empty `datapackage`/`local_path`, which the new check would (correctly) reject;
hand-authoring starts from the not-yet-acquired state, so `candidate` is the right default. This does
**not** affect `register-run`, which writes derived-entity frontmatter directly (`status: active` +
real `datapackage`), not via this template.

## Key decisions

### Key decision 1: complete the catalog in the singular group, do not collapse
- **Chosen:** keep `dataset` (catalog/lifecycle) and `datasets` (external discovery/download) as
  separate groups; build the catalog ergonomics inside `dataset`.
- **Rejected:** collapsing both into one `datasets` group (the original instinct).
- **Reason:** the split is a deliberate 2026-04-19 architecture and `register-run`/`reconcile` are
  load-bearing in workflow templates, skills, and tests; collapsing is breaking across `~/d/health/`
  for no functional gain, and the no-legacy-alias rule would force a hard cutover.

### Key decision 2: model "candidate" as acquisition-lifecycle on `status`, orthogonal to `tier`
- **Chosen:** `status: candidate` = not-yet-acquired; `tier` keeps meaning priority.
- **Rejected:** adding a new priority-like status enum parallel to `tier`.
- **Reason:** `tier` already encodes discovery priority; a parallel system would duplicate it. "Do we
  have the data yet?" is a genuinely different axis and belongs on the (already free-string) `status`.

### Key decision 3: enforce the acquisition invariant with a validate check, not a schema change
- **Chosen:** a friendly `dataset_acquisition` check in the validate layer.
- **Rejected:** making `datapackage` conditionally required in `mixin-dataset-1.0.json` + the strict
  `EntityValidator` + its ~15 schema tests.
- **Reason:** `science validate` already bypasses the strict JSON schema for authored frontmatter and
  re-enforces schema-critical rules in `checks/*.py` (see `dataset_taxonomy.py`, `identity_context.py`).
  The check turns today's *accidental, unchecked* leniency into an *explicit, checked* invariant
  (fail-early) with a far smaller blast radius and no risk to the cross-project closed-Entity path.

### Key decision 4: `dataset add` is bespoke; reuses the safe-write helpers but synthesizes the id directly
- **Chosen:** a dedicated writer that populates dataset frontmatter, synthesizes `dataset:<slug>`
  directly (validating the pattern), and reuses prospective validation + atomic write.
- **Rejected:** routing through the generic `create_entity(kind="dataset")` / `generate_entity_id`.
- **Reason:** `create_entity` only accepts `status`/`related`/`source_refs` and cannot express
  `origin`/`tier`/`access`; and `generate_entity_id` *and* `validate_entity_id` both call
  `resolve_path_policy("dataset").strategy`, but `dataset` has no path policy, so they raise before
  writing. Direct synthesis via `validate_slug(slug)` + `f"dataset:{slug}"` (the approach `register-run`
  already uses) sidesteps all of them while keeping the prospective-validation + atomic-write safety
  guarantees.

## Work packages

### WP1 — `dataset add` + template default
- **Depends on:** none.
- **Entry point:** `datasets_catalog.py::add_dataset`, wired as `@dataset_group.command("add")`; plus
  the `dataset.md` template `status` default flip (active → candidate).
- **Definition of done:** `science dataset add foo --title "Foo"` writes a valid candidate entity
  (id synthesized as `dataset:foo`, status candidate, license `unknown`) that passes `science validate`;
  `--origin derived` is rejected with a `register-run` pointer; destination-exists errors; unit tests
  green.

### WP2 — `dataset acquisition` validate check
- **Depends on:** WP1's template default flip (so the canonical template passes the new check).
- **Entry point:** `validate/checks/dataset_acquisition.py` + `__init__.py` registration.
- **Definition of done:** a non-candidate entity with neither `datapackage` nor `local_path` →
  `Severity.ERROR`; candidates pass; non-candidate **with** a pointer passes; the t013 catalog (15
  candidates) still validates clean; check unit test green.

### WP3 — `dataset list` rework
- **Depends on:** none (independent of WP1/2).
- **Entry point:** rewrite `dataset_list` to delegate to `datasets_catalog.py::list_datasets`.
- **Definition of done:** rich table; `--status/--candidate`, `--tier`, `--unverified`, `--level`
  filter correctly over local entries; `--commons` adds `CommonsQuery.find("dataset")` rows tagged as
  commons; non-`type:dataset` notes are excluded; existing `test_datasets_list_cli.py` updated and green.

### WP4 — `dataset show` + `dataset consumers`
- **Depends on:** none.
- **Entry point:** `datasets_catalog.py::show_dataset`, `::list_consumers`.
- **Definition of done:** `show` renders frontmatter + body + resolved refs; `consumers` lists
  `consumed_by`; both exit 2 on missing entity; unit tests green.

### WP5 — docs + smoke
- **Definition of done:** companion implementation plan written; `uv run --frozen science validate`
  and the dataset CLI pytest suite pass; a short note added wherever the dataset commands are
  user-documented (locate during planning).

## Open questions

*(Resolved during spec review — kept as a record.)*

1. ~~Is `dataset` body-templated?~~ **Resolved:** yes, `dataset.md` exists; WP1 *modifies* its `status`
   default rather than creating a template. `add` writes its own frontmatter and reuses the body
   sections.
2. ~~Does `_validate_status` constrain dataset status?~~ **Moot:** `add` synthesizes the id and
   frontmatter directly and does not go through `create_entity`/`_validate_status`. The base schema
   leaves `status` free-string, so `candidate` is valid.
4. ~~Which `Severity` fails the run?~~ **Resolved:** enum is `ERROR/WARN/INFO`; the check emits
   `Severity.ERROR`.

**Still open (resolve in-WP):**

3. **Resolving the commons root for `CommonsQuery`** — confirm how to locate the commons store root
   the way the `science commons` CLI does, and that `CommonsEntityRecord.frontmatter_json` exposes the
   table fields (status/tier/origin/access.level). `CommonsQuery` requires the registry to exist and
   warns on staleness — decide whether `--commons` rebuilds or just warns. Resolve in WP3.

## Non-goals

- No change to the plural `datasets` discovery/download group.
- No change to `register-run`/`reconcile` behaviour or their callers.
- No JSON-schema/`EntityValidator` change.
- No automated external verification (`dataset verify`).
- No backfill/migration of existing entities beyond what the new check surfaces.

## Acceptance criteria

- [ ] `science dataset add` authors a valid candidate entity; rejects `--origin derived`.
- [ ] `science dataset list` shows a filterable table, excludes non-dataset notes, supports `--commons`.
- [ ] `science dataset show` and `dataset consumers` accept `foo` and `dataset:foo`, resolve local
      then commons, and exit 2 (naming both scopes) on a true miss.
- [ ] `dataset_acquisition` check emits `Severity.ERROR` for a non-candidate with no
      `datapackage`/`local_path`, passes candidates and pointer-bearing entities; the t013 catalog and
      the updated `dataset.md` template both validate clean.
- [ ] `register-run`/`reconcile` and the plural `datasets` group are untouched; their tests still pass.
- [ ] New + updated unit tests green; `uv run --frozen science validate` passes.
