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
  dataset.md                 ── NEW IF not already templated (see Open question 1)
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

Authors a **candidate external** dataset entity at `doc/datasets/<slug>.md`. Reuses the entity-creation
safety helpers from `entities.py` — `generate_entity_id`, the prospective-write validation
(`_validate_prospective_write`), and the atomic temp-file replace — but populates dataset-specific
frontmatter that the generic `create_entity` does not know about.

Options: `--title` (required), `--tier` (default `track`), `--level` (default `controlled`),
`--source-url`, `--ontology-term` (repeatable), `--related` (repeatable), `--project-root`.

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

### `dataset show <slug>`

Reads `doc/datasets/<slug>.md`, prints a formatted view: key frontmatter (id, title, status, tier,
origin, access level/verified, license, accessions, source_url), the resolved `related` and
`consumed_by` lists, and the body. Exit 2 if not found.

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
  `load_project_sources(project_root, include_commons=True)`, tagging each row's origin-project so
  local vs commons is visible.

### `dataset consumers <slug>`

Reads the entity's `consumed_by` list and prints each consumer (plans, workflow-runs). Exit 2 if the
entity is missing; prints "no recorded consumers" when empty.

### `validate/checks/dataset_acquisition.py`

Mirrors `dataset_taxonomy.py` (read raw frontmatter via the `dataset_frontmatters` helper, re-enforce
a schema-critical rule with a friendly message). Rule `dataset.acquired-without-datapackage`:

- `status != "candidate"` (acquired) **and** `datapackage` empty/absent → **Severity that fails the
  run** (FAIL), message naming the slug and the fix ("set `status: candidate` if not yet acquired, or
  add the `datapackage:` pointer").
- `status == "candidate"` with no `datapackage` → pass (the supported state).

Registered in `validate/checks/__init__.py`.

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

### Key decision 4: `dataset add` is bespoke but reuses the creation helpers
- **Chosen:** a dedicated writer that populates dataset frontmatter, reusing `generate_entity_id`,
  prospective validation, and atomic write.
- **Rejected:** routing through the generic `create_entity(kind="dataset")`.
- **Reason:** `create_entity` only accepts `status`/`related`/`source_refs` and depends on a per-kind
  template + `_validate_status`; it cannot express `origin`/`tier`/`access`. Reusing the *helpers*
  keeps the safety guarantees without contorting the generic path.

## Work packages

### WP1 — `dataset add` + candidate template
- **Depends on:** Open question 1 (template registration).
- **Entry point:** `datasets_catalog.py::add_dataset`, wired as `@dataset_group.command("add")`.
- **Definition of done:** `science dataset add foo --title "Foo"` writes a valid candidate entity that
  passes `science validate`; `--origin derived` is rejected; destination-exists errors; unit tests green.

### WP2 — `dataset acquisition` validate check
- **Depends on:** none.
- **Entry point:** `validate/checks/dataset_acquisition.py` + `__init__.py` registration.
- **Definition of done:** acquired-without-datapackage FAILs with a friendly message; candidate passes;
  the t013 catalog (15 candidates) still passes; check unit test green.

### WP3 — `dataset list` rework
- **Depends on:** none (independent of WP1/2).
- **Entry point:** rewrite `dataset_list` to delegate to `datasets_catalog.py::list_datasets`.
- **Definition of done:** rich table; `--status/--candidate`, `--tier`, `--unverified`, `--level`,
  `--commons` all filter correctly; non-`type:dataset` notes are excluded; existing
  `test_datasets_list_cli.py` updated and green.

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

1. **Is `dataset` registered as a templated/`MIGRATED_KINDS` entity with a body template?** If yes,
   `add` can lean on it for the body; if no, WP1 adds a `dataset.md` template following the existing
   template format. Verify at the top of WP1.
2. **Does `_validate_status` (in `entities.py`) constrain dataset status values?** If it has a
   per-kind allow-list, confirm `candidate`/`active` are permitted (extend if needed). The base schema
   leaves `status` free-string, but the create path may be stricter.
3. **Exact `load_project_sources` return shape for `--commons`** — confirm it yields dataset
   frontmatter (or entities) with an origin-project tag usable in the table. Resolve in WP3.
4. **Which `Severity` value fails the run** in the validate framework (so the acquisition check FAILs
   rather than warns). Confirm against an existing FAIL-producing check in WP2.

## Non-goals

- No change to the plural `datasets` discovery/download group.
- No change to `register-run`/`reconcile` behaviour or their callers.
- No JSON-schema/`EntityValidator` change.
- No automated external verification (`dataset verify`).
- No backfill/migration of existing entities beyond what the new check surfaces.

## Acceptance criteria

- [ ] `science dataset add` authors a valid candidate entity; rejects `--origin derived`.
- [ ] `science dataset list` shows a filterable table, excludes non-dataset notes, supports `--commons`.
- [ ] `science dataset show` and `dataset consumers` work and exit 2 on missing entities.
- [ ] `dataset_acquisition` check FAILs acquired-without-datapackage, passes candidates; the t013
      catalog still validates clean.
- [ ] `register-run`/`reconcile` and the plural `datasets` group are untouched; their tests still pass.
- [ ] New + updated unit tests green; `uv run --frozen science validate` passes.
