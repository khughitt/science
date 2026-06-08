# Substrate Phase 3b — `entities.yaml` retirement: `--apply` executor (design)

> **Status:** approved design, pre-implementation. Feeds the writing-plans step.
> **Series:** substrate redesign, Part B/C of
> `2026-06-06-knowledge-meta-model-and-substrate-design.md` (§B5, §C2, §C3).
> **Predecessors merged:** Phase 1 (compiler seam) · 2a/2b/2c (dataset
> reconciliation) · **3a** (`entities.yaml` retirement *visibility* —
> `2026-06-07-substrate-3a-entities-retirement-visibility-design.md`). Phase 3 is
> decomposed into **3a → 3b (this doc) → 3c**.

## 1. Why this exists (3a made the debt visible; 3b makes it actionable)

3a delivered a read-only triage of every aggregate (`entities.yaml`-family) owner
row into six buckets (`shadow`/`coined`/`decision-log`/`external-ref`/`cruft`/
`ambiguous`) plus a standing lone-stub WARN. 3b is the **destructive executor**
that retires the two fully-unblocked dispositions:

- `coined` → **promote** to an `entities/<kind>/<slug>.md` owner file (§B5's
  canonical "coined-here lightweight node → owned declaration").
- `cruft` and `shadow` → **delete** the aggregate entry (§B5's "stub shadowing an
  existing markdown owner → deleted"; `cruft` = `migration:*` audit-injected
  degenerate stubs the §B5 model never anticipated).

### 1.1 The real inventory (verified against MM30, the only live aggregate set)

The project's `knowledge/sources/local/` holds **two** aggregate files the
`AggregateAdapter` loads, and they already separate the concerns:

| File | Entries | Buckets | 3b disposition |
|---|---|---|---|
| `entities.yaml` | 176 | `coined` 134 (concept 130, latent 4) · `cruft` 26 (`migration:*`) · `decision-log` 16 (`decision` from `core/decisions.md`) | **the 3b target** (minus decision-log) |
| `terms.yaml` | 189 | `external-ref` 93 (article/paper + `.bib`) · `ambiguous` 96 (disease/drug/gene/protein/method/topic) | **untouched** — Phase 4 |

The `ambiguous` 96 are overwhelmingly **external-standard-vocabulary** kinds
(`disease:multiple-myeloma`, `protein:*`, `gene:*`, `drug:*`), not coined-or-not
judgment calls — they are Phase-4 external references the 3a heuristic could not
yet name. Because 3b acts **only** on `coined`/`cruft`/`shadow`, it never touches
`terms.yaml` and the misclassification blast radius is structurally contained.

### 1.2 Two scope-shaping facts (carried from 3a, re-confirmed)

1. **MM30 is still `layout_version: 2`.** There is no `entities/` owner root;
   markdown owners live in `doc/papers/`, `specs/hypotheses/`, etc. §B5 presumes
   the markdown kinds already migrated to `entities/<kind>/`. **3b is therefore
   v3-gated, fixture-validated tooling** — like 1.3/1.4 were — and cannot run
   against MM30 until the separate v2→v3 markdown migration (project Task #30)
   lands. `--apply` refuses on a v2 project.
2. **`shadow` is 0 on MM30 today** (no markdown owners exist yet to be shadowed),
   but becomes non-empty the moment a project reaches v3 with real owner files.
   3b implements `shadow` deletion as first-class tooling and fixture-tests it
   even though MM30 currently exhibits none.

### 1.3 End-state staging

```
entities.yaml: 176 ──(promote 134 coined → entities/<kind>/*.md)──▶ ──(delete 26 cruft)──▶ 16 left
                                                                                            └─ decision-log → 3c
terms.yaml:    189 ──────────────────────────────────────────────────────────── untouched ──▶ Phase 4
```

After 3b, only the 16 `decision-log` rows remain in `entities.yaml`. **3c** retires
those (promote + make `core/decisions.md` a generated view over
`entities/decision/*.md`) and, once no aggregate rows remain anywhere, removes the
`AggregateAdapter` deprecated-owner mode (§C3). **Phase 4** retires `terms.yaml`
via the external-reference authority resolver.

## 2. Scope

### In scope (3b)

0. A **foundation prerequisite — the `slug` filename strategy** (§3.0). The v3
   entity-path policy substrate (`entities.py`) currently admits only `numeric`
   and `citekey` local-part strategies; coined kinds (`concept`, `latent`) carry
   kebab-mnemonic ids (`concept:1q-gain`) that conform to neither. §B5's
   "coined-here lightweight node → a small file" presumes the id **is** the slug,
   so 3b first adds a `slug` strategy and gives `concept` a core policy, enabling
   **id-preserving** promotion (no renumber, no ref rewrite).
1. A pure **disposition planner** that turns the 3a classifier output + per-bucket
   opt-in flags into a `RetirementPlan` (`promote` / `delete` / `rejected`),
   **scoped to `entities.yaml` declarations only** (§3.1).
2. An **executor** that writes `coined` owner files and rewrites the affected
   aggregate file(s), removing promoted + deleted entries, **crash-recoverable
   via a promotion provenance marker** (§3.5).
3. CLI: `--apply` + `--promote-coined` / `--delete-cruft` / `--delete-shadow`
   flags on the existing `science entities triage-aggregate` command, plus a
   `--format json` report. Dry-run by default.
4. A **`layout_version >= 3` gate** on `--apply` (§3.7).

### Out of scope (deferred)

| Deferred item | Phase |
|---|---|
| `decision-log` promotion **+** `core/decisions.md` as a generated view | 3c |
| Remove the `AggregateAdapter` deprecated-owner mode (gated on zero aggregate rows) | 3c |
| External-reference resolution for `external-ref` / `ambiguous` (`terms.yaml`) | Phase 4 |
| Running any retirement against MM30 content | after MM30 reaches v3 (Task #30) |
| `--undo` / transactional rollback (git is the safety net; see §6) | not planned |

## 3. Architecture

### 3.0 Foundation prerequisite: the `slug` filename strategy

The v3 path-policy substrate lives in `entities.py`. Verified facts that force
this prerequisite:

- `EntityFilenameStrategy = Literal["numeric", "citekey", "singleton"]`;
  `_VALID_STRATEGIES = {"numeric", "citekey"}` (the set a *local* kind may
  declare; `singleton` is excluded for local kinds).
- `_CORE_POLICIES` maps each core kind to an `EntityPathPolicy(root, strategy)`.
  It has **no `concept`, `latent`, or `decision`** — `concept` is core-*loadable*
  (`entity_registry`) but has **no path policy**; `latent`/`decision` are local
  kinds that default to `numeric` (`ek.strategy or "numeric"`).
- `numeric` requires `NNNN-slug` local parts; `citekey` requires `Author2025`.
  A coined id like `concept:1q-gain` conforms to neither.
- Slug machinery **already exists** for title-derivation: `_SLUG_RE`,
  `validate_slug`, `normalize_to_slug`, `derive_slug`. There is simply no `slug`
  *strategy* that routes a kind's filename/id through it.

**The addition (bounded, additive):**

1. `EntityFilenameStrategy`: add `"slug"`.
2. `_VALID_STRATEGIES`: add `"slug"` so a local kind may declare it.
3. `local_part_conforms`: `strategy == "slug"` → `bool(_SLUG_RE.fullmatch(local_part))`.
4. `validate_entity_id`: a `slug` branch validating the local part with `_SLUG_RE`
   (parallel to the existing `citekey` branch).
5. `generate_entity_id` (the real generated-id helper; **not** a `derive_local_part`
   — that name does not exist): add a `slug` branch. An explicit `entity_id`
   already routes through `validate_entity_id` (now slug-aware). For a *generated*
   id, return `f"{kind}:{validate_slug(slug) if slug is not None else derive_slug(title)}"`
   — i.e. use the title-slug **directly, skipping `_next_numeric_local_part`**
   (which is the numeric-only path). `path_for_entity` needs **no** change: it is
   `resolve_path_policy(kind).root / f"{local_part}.md"` and becomes correct for
   slug once `validate_entity_id` accepts a slug id.
6. **`entity_layout_migration.py` — an explicit `slug` planning branch (REQUIRED,
   not optional).** Adding `concept` to `_CORE_POLICIES` registers `entities/concepts`
   as a known destination, so a `slug`-kind entity can enter the migrator's
   per-kind loop. That loop has `singleton`/`citekey`/`numeric` branches and falls
   through to `numeric`; there, `local_part_conforms("concept", "1q-gain")` is now
   **true** (it is a valid slug), so the numeric branch executes
   `int(stem.split("-", 1)[0])` → `int("1q")` → **ValueError crash**
   (`entity_layout_migration.py:458-459`). Add a `slug` branch **parallel to
   `citekey`** (the block at `:435`): preserve `Path(entity.rel_path).stem` as the
   local part, move to `policy.root/<stem>.md`, id `f"{kind}:{stem}"`, **never
   numbered**. This guards a partly-migrated tree even though §D3 keeps structural
   aggregate kinds out of scope and 3b owns their retirement.
7. `_BUILTIN_MARKDOWN_POLICIES` (the real name; the design earlier called it
   `_CORE_POLICIES`): add `"concept": EntityPathPolicy(Path("entities/concepts"), "slug")`
   — `concept` is a core kind, so its policy belongs in the core table. **Also**
   register its status vocabulary (`_DEFAULT_STATUS["concept"] = "active"`,
   `_STATUS_VALUES["concept"] = {"active", "deprecated"}`): once `concept` is a
   recognized kind, the migrator's `synthesize_frontmatter` →
   `default_status`/`valid_statuses` raises `KeyError` for it without one.
8. A v3 project that retires its aggregate registers its other coined kinds
   (`latent`, and later `decision`) with `strategy: slug` in
   `knowledge/sources/<profile>/manifest.yaml`. (The MM30 manifest update is part
   of MM30's eventual v3 cutover, Task #30, not this framework change; the 3b
   fixtures register a slug local kind directly.)

The implementer must grep every `strategy ==` / `strategy in` switch
(`validate_entity_id`, `generate_entity_id`, `singleton_path`,
`_next_numeric_local_part`, **the migrator's per-kind planning loop**, the
conformance checks) and handle `"slug"` explicitly — the migrator branch above is
load-bearing (it crashes without it), not a "safe ignore." The net effect of this
section, for existing kinds: **no** behavior change for any `numeric`/`citekey`/
`singleton` kind; for a `slug` kind the owner lives at `<root>/<id-local-part>.md`
and its id is accepted as conforming and is never renumbered.

### 3.1 The §C2 law: model decides *which*, file provides *content*; scope to `entities.yaml`

3b honors the architectural law (§C2: every consumer reads the compiled model,
not raw disk) at the level that matters — **identity decisions**. Which rows are
acted on, and what bucket each is in, comes entirely from
`classify_aggregate_rows(sources)` (the 3a classifier over the `IdentityTable` +
`ProjectSources.aggregate_rows`). The executor never re-derives identity by
grepping YAML.

The executor *does* perform file I/O — it must, to write owner files and rewrite
the aggregate file — and for a promoted row it reads that row's full entry
content (e.g. `title`, `profile`) from the YAML it is already rewriting. This is
the same split 2a's `datapackage_promote.py` used: the compiled model drives the
**decision**; the source file provides the **content** to copy. The two never
disagree for acted buckets, because:

- `coined`/`cruft`/`shadow` ids are **not** subject to the `article:`→`paper:`
  canonicalization (only `article` ids are rewritten, and those are `external-ref`,
  never acted). So a coined row's compiled `canonical_id` equals its file
  `canonical_id`.
- The join from a triage row back to its file entry uses the declaration's
  `source_ref.(path, line)` — `line` is the entry index `AggregateAdapter` always
  sets — so the executor drops/reads entries **by index**, robust even if an id
  ever were canonicalized.

**`entities.yaml`-only firewall (Finding #1).** `AggregateAdapter` loads **both**
`entities.yaml` and `terms.yaml` as aggregate sources (`_MULTI_TYPE_FILES =
{"entities.yaml": "entities", "terms.yaml": "terms"}`), plus single-type
`doc/<plural>/<plural>.{json,yaml}` lists. So `classify_aggregate_rows` returns
rows from all of them, and a future `cruft`/`shadow` row in `terms.yaml` would
otherwise be deleted. The planner therefore considers **only** declarations whose
`Path(source_ref.path).name == "entities.yaml"`; every other aggregate row
(terms, single-type) is excluded from the plan up front. This is structural, not
incidental: `terms.yaml` is the Phase-4 external-vocabulary surface (it is even
row-normalized by `_normalize_term_row` on load) and 3b must never rewrite it. A
test asserts a coined/cruft/shadow row sourced from `terms.yaml` is absent from
the plan.

### 3.2 Module layout

| File | Role |
|---|---|
| `entities.py` (extend) | the `slug` filename strategy (`EntityFilenameStrategy`, `_VALID_STRATEGIES`, `local_part_conforms`, `validate_entity_id`, `generate_entity_id`) + `concept` core policy (§3.0) |
| `entity_layout_migration.py` (extend) | a `slug` planning branch parallel to `citekey` — REQUIRED to avoid a numeric-branch crash (§3.0 item 6) |
| `graph/aggregate_retire.py` (NEW) | planner + executor; keeps 3a's `aggregate_triage.py` strictly read-only |
| `cli.py` (extend `entities_triage_aggregate_command`) | flags, dry-run/apply dispatch, `_read_layout_version`, report rendering |

Keeping the destructive executor in its own module (rather than growing
`aggregate_triage.py`) preserves the single responsibility of the 3a classifier
(read-only triage) and isolates all mutation in one auditable place.

### 3.3 Data types

```python
class RetireAction(StrEnum):
    PROMOTE = "promote"   # coined → owner file
    DELETE  = "delete"    # cruft / shadow → drop entry

@dataclass(frozen=True, slots=True)
class PlannedRow:
    triage: AggregateRowTriage     # the 3a classification (carries canonical_id, kind, bucket, …)
    action: RetireAction
    source_path: str               # the aggregate FILE path (declaration source_ref.path)
    line: int                      # entry index within that file
    target_path: str | None        # policy.root/<local_part>.md for PROMOTE; None for DELETE

@dataclass(frozen=True, slots=True)
class RetirementPlan:
    promote: tuple[PlannedRow, ...]
    delete: tuple[PlannedRow, ...]
    rejected: tuple[tuple[AggregateRowTriage, str], ...]   # (row, reason)

@dataclass(frozen=True, slots=True)
class RetirementReport:
    promoted: tuple[str, ...]      # canonical_ids written to owner files
    deleted: tuple[str, ...]       # canonical_ids removed from aggregate files
    rejected: tuple[tuple[str, str], ...]
    skipped: tuple[tuple[str, str], ...]   # e.g. target already exists
    files_rewritten: tuple[str, ...]
    dry_run: bool
```

### 3.4 Planner (pure)

```python
def plan_retirement(
    project_root: Path,                 # for resolve_path_policy(kind, project_root=...)
    sources: ProjectSources,
    rows: list[AggregateRowTriage],
    *,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
) -> RetirementPlan
```

Pure over the classification: `project_root` is used only to resolve the static
path-policy table (`resolve_path_policy` / `entity_policies`), not to read entity
content — so the planner remains unit-testable against a fixture root that
declares the kinds without any aggregate state on disk.

- Considers **only** `entities.yaml` declarations (§3.1 firewall); every other
  aggregate row is dropped before bucket mapping.
- Maps each enabled bucket to its action: `coined`→`PROMOTE` (if
  `promote_coined`), `cruft`→`DELETE` (if `delete_cruft`), `shadow`→`DELETE` (if
  `delete_shadow`). `decision-log`/`external-ref`/`ambiguous` are **never** acted.
- For each acted row, recovers `(source_path, line)` by joining the triage row
  back to its aggregate `IdentityDeclaration` / `aggregate_rows` entry (via
  `canonical_id` → declaration; `line` from `source_ref`).
- For a `PROMOTE`, the target is computed **from the path policy** (§3.0), not a
  raw `entities/<kind>` guess: `policy = resolve_path_policy(kind,
  project_root=...)`, `target_path = policy.root / f"{local_part}.md"`. Rejects
  (does not promote) when:
  - `resolve_path_policy(kind)` raises (kind has no policy — e.g. a coined kind
    the project never registered with a `slug` strategy) — reason
    `"no path policy for kind <k>"`;
  - the id's `local_part` does not satisfy `local_part_conforms(kind, local_part)`
    — reason `"id <id> does not conform to <strategy> strategy"`. This check
    runs **for every strategy, including `slug`**: a slug-strategy id must still be
    a valid slug (`_SLUG_RE` rejects `bad_slug`, `Trailing-`, etc.). 3b promotes
    **id-preserving**; it never renumbers, so a non-conforming id is rejected.
  - the local part fails the **2a `_is_safe_slug` firewall**
    (`^[a-z0-9][a-z0-9._-]*$`, reject `..`) — reason `"unsafe slug"`. (A
    path-safety belt after conformance; redundant for slug kinds, whose `_SLUG_RE`
    already excludes `.`/`..`, but kept so a future non-slug promote stays safe.)
- Crash-recovery of a *prior* promotion is an impure executor concern (§3.5),
  deliberately kept out of the planner.

### 3.5 Executor

```python
def apply_retirement(
    project_root: Path,
    plan: RetirementPlan,
    *,
    dry_run: bool,
) -> RetirementReport
```

**File I/O contract (Finding #4).** `entities.yaml` is a **mapping with a root
key** (`{entities: [ ... ]}`), not a top-level list; `source_ref.path` is
**project-root-relative** (the loader resolves relative refs via chdir). So every
file touch:
- resolves the absolute path as `project_root / ref.path`;
- `data = yaml.safe_load(text)`; the entry list is `data["entities"]` (the root
  key from `_MULTI_TYPE_FILES`, which 3b only ever sees as `"entities"` given the
  §3.1 firewall);
- indexes/drops within that list by `ref.line`; re-dumps as
  `{"entities": survivors}` with `yaml.safe_dump(sort_keys=False)` (files carry no
  comments, so no round-trip fidelity concern).

**Promotion provenance marker.** Every promoted owner file carries a frontmatter
field `promoted_from: <entities.yaml rel path>`. It records provenance **and** is
the key to crash-safe recovery (below): it lets a rerun distinguish "an owner file
*I* wrote in a prior, interrupted run" from "a real, hand-authored owner."

Order of operations (write-before-rewrite, so a crash mid-run never strands an id
with neither an owner file nor an aggregate entry):

1. **Promote / reconcile.** For each `PlannedRow` in `plan.promote`, read its full
   entry dict from `data["entities"][line]`; build owner-file frontmatter — `id` =
   `canonical_id`, `type` = `kind`, `title`, `profile` (copied), `promoted_from`,
   **excluding** `source_path` and aggregate-only bookkeeping; body = a one-line
   stub (`<!-- promoted from entities.yaml by substrate-3b; add definition -->`).
   For each row, resolve the target by existence + marker:
   - **target absent** → write it, then mark its aggregate entry for deletion.
   - **target exists *with* our `promoted_from == <this aggregate>` marker** → a
     prior interrupted run already wrote it; **skip the write but still mark the
     entry for deletion** (completes the half-done promote — the recovery path,
     Finding #3). Reported under `promoted` (idempotent).
   - **target exists *without* our marker** (a foreign/hand-authored owner) →
     `skipped` (reason `"target exists (foreign owner)"`); entry **retained**; do
     not clobber. Surfaced in the report as a conflict.
   - Required fields `id`/`kind`/`title` absent → `rejected` (reason `"missing
     required field <f>"`); entry **retained**.
   - `dry_run`: classify the outcome and record the intended write, touch nothing.
2. **Crash-recovery sweep (only when `--promote-coined`).** Because a completed
   write flips the row's bucket from `coined` to `shadow` on the next load, a
   stranded entry (owner written, entry not yet deleted) is no longer in
   `plan.promote`. So, additionally, scan `shadow` rows whose owning markdown file
   carries `promoted_from == <this aggregate>` and mark their aggregate entries for
   deletion. This reconciles **only** our own prior promotions (marker-keyed);
   foreign-owned shadows are untouched (that is `--delete-shadow`'s job). This
   makes `--promote-coined` alone idempotent and crash-safe.
3. **Rewrite aggregate files.** Collect the `(source_path, line)` of every entry
   marked for deletion in steps 1–2 (successful/reconciled promotes) plus every
   `plan.delete` row. Group by `source_path`. For each file: load, drop those
   indices from `data["entities"]` in one filtering pass (collect all indices
   first — never remove one-at-a-time, which shifts indices), write survivors back.
   Rejected/skipped rows are **not** dropped, so the file stays consistent.
   - `dry_run`: record `files_rewritten` that *would* change, write nothing.
4. Return the `RetirementReport`.

### 3.6 CLI surface (extends the 3a command)

```
science entities triage-aggregate
    [--project-root PATH] [--format text|json]
    [--promote-coined] [--delete-cruft] [--delete-shadow]
    [--apply]
```

| Invocation | Behavior | Exit |
|---|---|---|
| no bucket flags, no `--apply` | **unchanged 3a triage report** (full six-bucket inventory) | 0 |
| ≥1 bucket flag, no `--apply` | `apply_retirement(dry_run=True)` → print the `RetirementReport` (`dry_run: true`); a plan and a result share one shape (text or json) | 0 |
| ≥1 bucket flag, `--apply` | `apply_retirement(dry_run=False)` → print the `RetirementReport` | 0 |
| `--apply`, no bucket flag | usage error: explicit opt-in required | 2 |
| `--apply` on `layout_version < 3` | refuse: "promotion needs an `entities/` owner root; this project is layout_version N — complete the v2→v3 migration (Task #30) first" | 1 |

Backward compatibility: the bare command and `--format json` with no bucket flags
behave exactly as in 3a (a regression test pins this).

### 3.7 The `layout_version` gate (Finding #5)

`layout_version` must be read **directly from `science.yaml`** —
`yaml.safe_load((project_root / "science.yaml").read_text()).get("layout_version")`
— **not** via `_read_project_config()`, which drops the field. Apply the same
convention the validate checks use (`validate/checks/manifest.py:30`,
`directory_structure.py:22`): treat it as v3 iff `isinstance(v, int) and v >= 3`.
A tiny local helper (e.g. `_read_layout_version(project_root) -> int | None`) in
the CLI module keeps this in one place. The gate applies **only** to `--apply`
(which writes owner files into `entities/<kind>/`); dry-run planning is read-only
and works on a v2 project as a useful preview. Refusal is a clean non-zero exit
with an actionable message, never a stack trace.

## 4. Error handling (Explicit > Defensive, fail-early)

| Condition | Handling |
|---|---|
| Kind has no path policy / coined kind not registered `slug` | row → `rejected` (`"no path policy for kind"`); entry retained |
| Id non-conforming to its kind's strategy (3b never renumbers) | row → `rejected` (`"id … does not conform"`); entry retained |
| Unsafe slug local part | row → `rejected` (`"unsafe slug"`); entry retained |
| Missing `id`/`kind`/`title` in a promote entry | row → `rejected` (`"missing required field"`); entry retained |
| Promote target exists **with** our `promoted_from` marker | recovery: skip write, **delete** the stranded entry (idempotent) |
| Promote target exists **without** our marker (foreign owner) | row → `skipped` (`"target exists (foreign owner)"`); entry retained; reported as conflict |
| Row sourced from `terms.yaml` / a single-type aggregate | excluded from the plan entirely (§3.1 firewall) |
| `--apply` without a bucket flag | click usage error (exit 2) |
| `--apply` on `layout_version < 3` | refuse (exit 1), actionable message |
| Malformed aggregate YAML (unparseable file) | the load already failed upstream; the executor never reaches a file the loader could not parse |

No partial-entry mutation: an entry is removed **only** if its disposition fully
succeeded (promoted/reconciled and written, or a clean delete).

## 5. Idempotency

After a successful `--apply`:

- A **promoted** id now has a markdown owner under `entities/<kind>/` **and** no
  aggregate entry → it is the sole owner → absent from `classify_aggregate_rows`
  on the next load → nothing to re-promote.
- A **deleted** id is simply gone.

So a second `--apply` with the same flags is a **no-op** (empty `promoted`/
`deleted`). A round-trip test asserts this: load → apply → reload → assert the
promoted ids resolve to markdown owners, the aggregate file shrank by exactly the
acted count, and the 3a lone-stub WARNs for the acted ids are gone.

**Crash recovery (Finding #3).** If the process dies *after* writing an owner file
but *before* deleting its aggregate entry, the entry survives and the id now has a
real owner — so the next load classifies it `shadow`, not `coined`. A naive
"target exists → skip" would then strand the entry forever under `--promote-coined`
alone. The `promoted_from` marker closes this: on rerun, step 1 treats a
marker-matched existing target as a completed promote (delete the entry), and
step 2's sweep reconciles any `shadow` whose owner bears our marker. A dedicated
test simulates the crash (pre-write the marked owner file, leave the entry) and
asserts a single `--promote-coined` rerun deletes the stranded entry and reports
it under `promoted`, while a same-id *foreign* owner (no marker) is left intact.

## 6. Safety & reversibility

3b performs irreversible deletes, but does **not** implement `--undo` or a
transactional journal. The safety model is:

1. **Dry-run by default** — destructive action requires both an explicit bucket
   flag *and* `--apply`.
2. **Git is the rollback** — real projects are version-controlled; the executor
   makes ordinary file edits a `git checkout`/`git restore` reverts. (MM30 raw
   data sensitivity is irrelevant here: `entities.yaml` is committed metadata,
   not raw MMRF/GEO data.)
3. **Write-before-rewrite ordering** — owner files are written before their
   entries are removed, so an interrupted run never strands an id with neither an
   owner file nor an aggregate entry.
4. **Per-row failure isolation** — a rejected/skipped row leaves its aggregate
   entry intact; one bad row never aborts the batch or corrupts the file.

## 7. Testing

`cd ~/d/science/science && uv run --frozen pytest`; lint
`uv run --frozen ruff check . && uv run --frozen ruff format --check .` (120-char).

- **`slug`-strategy unit tests** (`tests/test_entities.py` or peer): a `slug` kind
  accepts a kebab id (`local_part_conforms`, `validate_entity_id`);
  `generate_entity_id` with no explicit id returns `kind:<derive_slug(title)>`
  (no `NNNN-` prefix); `path_for_entity` lands it at `policy.root/<slug>.md`;
  `resolve_path_policy("concept").root == entities/concepts` with strategy `slug`;
  existing `numeric`/`citekey`/`singleton` behavior unchanged (regression).
- **Migrator slug-branch test** (`tests/test_entity_layout_migration.py` or peer):
  a legacy/partly-migrated `slug`-kind file with a kebab stem (`1q-gain.md`) plans
  a move to `policy.root/1q-gain.md` with id `concept:1q-gain` and is **never
  numbered** — and critically does **not** raise `ValueError` from the numeric
  branch. (Pins the §3.0 item-6 crash guard.)
- **Planner unit tests** (`tests/graph/test_aggregate_retire.py`): pure matrix —
  each bucket × each flag yields the right action or skip;
  `decision-log`/`external-ref`/`ambiguous` never acted; a `terms.yaml`-sourced
  coined/cruft/shadow row is **excluded from the plan** (§3.1 firewall); kind with
  no policy → rejected; a non-conforming id under a non-`slug` strategy → rejected
  (never renumbered); unsafe slug → rejected; `(source_path, line)` join recovered.
- **Executor tests** (v3 fixtures — `layout_version: 3`, an `entities/` root, a
  local `slug` kind registered, and an `entities.yaml` stub file):
  - promote writes `entities/concepts/<slug>.md` with `id`/`type`/`title`/`profile`/
    `promoted_from` frontmatter and a stub body, **id preserved**; the source entry
    is removed; survivors (and an untouched second file, e.g. `terms.yaml`) are
    byte-stable except for the dropped entry.
  - delete removes a `cruft` entry; a `shadow` entry (id with a real markdown
    owner) is removed and the markdown owner survives.
  - **file-shape:** the rewrite preserves the `{entities: [...]}` mapping shape and
    resolves the project-root-relative `source_ref.path` correctly.
  - **crash recovery:** pre-write a marked owner file + leave its entry → one
    `--promote-coined` rerun deletes the stranded entry, reports it `promoted`; a
    same-id foreign owner (no marker) → entry retained, reported conflict.
  - missing-`title` promote → rejected, entry retained.
  - `dry_run=True` writes nothing but reports the intended plan.
  - **idempotency:** apply twice → second run reports empty.
  - **v2 refusal:** `--apply` against a `layout_version: 2` fixture refuses (exit 1).
- **CLI tests** (`tests/test_cli_entities_triage_aggregate.py`, extending 3a's):
  bare command = 3a report (regression); a bucket flag alone = dry-run plan;
  `--apply` executes and the report JSON has the documented shape; `--apply`
  without a flag is a usage error (exit 2); v3 gate message on a v2 fixture.
- **Round-trip integration:** `load_project_sources → plan → apply → reload`,
  asserting owner resolution, file shrinkage, and lone-stub WARN clearance.

**Fixture note (carried from 3a):** `AggregateAdapter` scans
`knowledge/sources/<value>/` where `<value>` is the profile-map value; use
`knowledge_profiles: {local: local}`. The v3 executor fixtures additionally set
`layout_version: 3` and create the `entities/` owner root so promoted files are
rediscovered on reload. `decision`/`latent` are local (not core) kinds — exercise
their rules through the pure planner; drive the load→apply integration with core
kinds (`concept` for coined; a `dataset`+markdown owner for shadow).

## 8. Risks & mitigations

- **Destructive action on a misclassified row.** Mitigated by acting only on the
  three lowest-ambiguity buckets (`coined`/`cruft`/`shadow`), explicit per-bucket
  opt-in, dry-run default, per-row rejection, and git as rollback. The
  high-judgment buckets (`ambiguous`, `decision-log`) are never acted in 3b.
- **Touching `terms.yaml` / external vocabulary.** Doubly prevented: the §3.1
  firewall excludes every non-`entities.yaml` declaration from the plan, **and**
  3b only promotes `coined` (which never includes the `external-ref`/`ambiguous`
  vocab that lives in `terms.yaml`). A test asserts a `terms.yaml` row is never
  planned.
- **Owner file landing where the loader won't find it / id non-conformance.**
  Mitigated by computing the target from `resolve_path_policy(kind)` (the policy
  the loader/conformance machinery itself uses) and the new `slug` strategy, plus
  the round-trip test that reloads and asserts owner resolution. 3b **never
  renumbers** — a non-conforming id is rejected, never silently relocated.
- **The `slug`-strategy foundation change regressing existing kinds — or crashing
  the migrator.** The sharp edge is `entity_layout_migration.py`: registering
  `concept` makes `entities/concepts` a known destination, so a slug stem can reach
  the numeric branch and `int("1q")`-crash. Mitigated by the **required** explicit
  slug planning branch (§3.0 item 6, pinned by a migrator test), an otherwise
  additive design (no change to `numeric`/`citekey`/`singleton` branches), a grep
  of every `strategy ==`/`strategy in` switch, and a regression assertion that
  existing kinds are unchanged.
- **Crash between owner-write and entry-delete.** Mitigated by the `promoted_from`
  marker + step-2 recovery sweep (§3.5), making `--promote-coined` idempotent and
  crash-safe; covered by the crash-simulation test.
- **Index drift during rewrite.** Mitigated by collecting all drop-indices per
  file up front and filtering the survivor list in one pass, rather than removing
  entries one at a time.

## 9. Success criteria

- A `slug` filename strategy exists; `concept` has a core slug policy; existing
  `numeric`/`citekey`/`singleton` kinds are unchanged (regression-pinned).
- `science entities triage-aggregate` with bucket flags prints a correct dry-run
  retirement plan; with `--apply` it promotes `coined` rows to **id-preserving**
  owner files (never renumbering; non-conforming ids rejected) and deletes
  `cruft`/`shadow` entries, idempotently and crash-recoverably (`promoted_from`).
- `--apply` refuses on `layout_version < 3` with an actionable message.
- The bare 3a report and JSON output are unchanged (regression-pinned).
- No `terms.yaml` entry and no `decision-log` row is ever touched by a 3b path.
- Full suite green; ruff clean on changed files.
