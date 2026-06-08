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

1. A pure **disposition planner** that turns the 3a classifier output + per-bucket
   opt-in flags into a `RetirementPlan` (`promote` / `delete` / `rejected`).
2. An **executor** that writes `coined` owner files and rewrites the affected
   aggregate file(s), removing promoted + deleted entries.
3. CLI: `--apply` + `--promote-coined` / `--delete-cruft` / `--delete-shadow`
   flags on the existing `science entities triage-aggregate` command, plus a
   `--format json` report. Dry-run by default.
4. A **`layout_version >= 3` gate** on `--apply`.

### Out of scope (deferred)

| Deferred item | Phase |
|---|---|
| `decision-log` promotion **+** `core/decisions.md` as a generated view | 3c |
| Remove the `AggregateAdapter` deprecated-owner mode (gated on zero aggregate rows) | 3c |
| External-reference resolution for `external-ref` / `ambiguous` (`terms.yaml`) | Phase 4 |
| Running any retirement against MM30 content | after MM30 reaches v3 (Task #30) |
| `--undo` / transactional rollback (git is the safety net; see §6) | not planned |

## 3. Architecture

### 3.1 The §C2 law: model decides *which*, file provides *content*

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

### 3.2 Module layout

| File | Role |
|---|---|
| `graph/aggregate_retire.py` (NEW) | planner + executor; keeps 3a's `aggregate_triage.py` strictly read-only |
| `cli.py` (extend `entities_triage_aggregate_command`) | flags, dry-run/apply dispatch, report rendering |

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
    target_path: str | None        # entities/<kind>/<slug>.md for PROMOTE; None for DELETE

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
    sources: ProjectSources,
    rows: list[AggregateRowTriage],
    *,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
    owner_root_for: Callable[[str], str | None],   # kind -> owner dir, framework mapping
) -> RetirementPlan
```

- Maps each enabled bucket to its action: `coined`→`PROMOTE` (if
  `promote_coined`), `cruft`→`DELETE` (if `delete_cruft`), `shadow`→`DELETE` (if
  `delete_shadow`). `decision-log`/`external-ref`/`ambiguous` are **never** acted.
- For each acted row, recovers `(source_path, line)` by joining the triage row
  back to its aggregate `IdentityDeclaration` / `aggregate_rows` entry (via
  `canonical_id` → declaration; `line` from `source_ref`).
- For a `PROMOTE`, computes `target_path = <owner_root_for(kind)>/<slug>.md` where
  `slug` is the id's local part. Rejects (does not promote) when:
  - `owner_root_for(kind)` is `None` (kind has no owner root) — reason
    `"no owner root for kind"`;
  - the slug fails the **2a `_is_safe_slug` firewall** (`^[a-z0-9][a-z0-9._-]*$`,
    reject `..`) — reason `"unsafe slug"`.
- Pure: no I/O, fully unit-testable on synthetic `AggregateRowTriage` lists.

### 3.5 Executor

```python
def apply_retirement(
    project_root: Path,
    plan: RetirementPlan,
    *,
    dry_run: bool,
) -> RetirementReport
```

Order of operations (write-before-rewrite, so a crash mid-run never deletes an
entry whose owner file was not written):

1. **Promote.** For each `PlannedRow` in `plan.promote`, read its full entry dict
   from `source_path[line]`; build owner-file frontmatter — `id` = `canonical_id`,
   `type` = `kind`, `title`, `profile` (copied), **excluding** `source_path` and
   any aggregate-only bookkeeping; body = a one-line stub
   (`<!-- promoted from entities.yaml by substrate-3b; add definition -->`).
   - Required fields `id`/`kind`/`title` absent → move the row to `rejected`
     (reason `"missing required field <f>"`); its entry is **not** deleted from
     the aggregate file. (Explicit > Defensive — fail the row, not the run.)
   - `target_path` already exists → `skipped` (reason `"target exists"`); entry
     **not** deleted (a real owner or a prior promotion already holds it).
   - `dry_run`: record the intended write, touch nothing.
2. **Rewrite aggregate files.** Collect the `(source_path, line)` of every row
   that was *successfully* promoted **or** is a delete. Group by `source_path`.
   For each file: `yaml.safe_load`, drop the entries at those indices, write the
   survivors back (`yaml.safe_dump`, stable key order; the files carry no comments
   so no round-trip fidelity concern). Rejected/skipped promotes are **not**
   dropped, so the file stays internally consistent.
   - `dry_run`: record `files_rewritten` that *would* change, write nothing.
3. Return the `RetirementReport`.

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

### 3.7 The `layout_version` gate

Read `layout_version` from the project manifest (the same field the migrator and
`orphan_datapackage_owner` check consult). The gate applies **only** to `--apply`
(which writes owner files into `entities/<kind>/`); dry-run planning is read-only
and works on a v2 project as a useful preview. Refusal is a clean non-zero exit
with an actionable message, never a stack trace.

## 4. Error handling (Explicit > Defensive, fail-early)

| Condition | Handling |
|---|---|
| Unsafe slug | row → `rejected`, not written; entry retained |
| Missing `id`/`kind`/`title` in a promote entry | row → `rejected`; entry retained |
| Kind has no owner root | row → `rejected`; entry retained |
| Promote target file already exists | row → `skipped`; entry retained |
| `--apply` without a bucket flag | click usage error (exit 2) |
| `--apply` on layout_version < 3 | refuse (exit 1), actionable message |
| Malformed aggregate YAML (unparseable file) | the load already failed upstream; the executor never reaches a file the loader could not parse |

No partial-entry mutation: an entry is removed **only** if its disposition fully
succeeded (promoted and written, or a clean delete).

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

- **Planner unit tests** (`tests/graph/test_aggregate_retire.py`): pure matrix —
  each bucket × each flag combination yields the right action or skip;
  `decision-log`/`external-ref`/`ambiguous` never acted; unsafe slug → rejected;
  kind with no owner root → rejected; `(source_path, line)` join is recovered
  correctly.
- **Executor tests** (v3 fixtures — a project with `layout_version: 3`, an
  `entities/` root, and an aggregate stub file):
  - promote writes `entities/<kind>/<slug>.md` with `id`/`type`/`title`/`profile`
    frontmatter and a stub body; the source entry is removed; survivors (and a
    second untouched file) are byte-stable except for the dropped entry.
  - delete removes a `cruft` entry; a `shadow` entry (id with a real markdown
    owner) is removed and the markdown owner survives.
  - missing-`title` promote → rejected, entry retained.
  - pre-existing target → skipped, entry retained.
  - `dry_run=True` writes nothing but reports the intended plan.
  - **idempotency:** apply twice → second run reports empty.
  - **v2 refusal:** `--apply` against a `layout_version: 2` fixture refuses.
- **CLI tests** (`tests/test_cli_entities_triage_aggregate.py`, extending 3a's):
  bare command = 3a report (regression); a bucket flag alone = dry-run plan;
  `--apply` executes and the report JSON has the documented shape; `--apply`
  without a flag is a usage error; v3 gate message on a v2 fixture.
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
- **Promoting an externally-owned vocabulary term.** Structurally impossible:
  external vocab lives in `terms.yaml` as `external-ref`/`ambiguous`, never
  `coined`; 3b only promotes `coined`.
- **Owner file landing where the loader won't find it.** Mitigated by deriving
  `<kind>/` from the framework's own owner-root mapping (the same one
  `MarkdownAdapter` discovers owners through), and by the round-trip test that
  reloads and asserts owner resolution.
- **Index drift during rewrite.** Mitigated by collecting all drop-indices per
  file up front and filtering the survivor list in one pass, rather than removing
  entries one at a time.

## 9. Success criteria

- `science entities triage-aggregate` with bucket flags prints a correct dry-run
  retirement plan; with `--apply` it promotes `coined` rows to owner files and
  deletes `cruft`/`shadow` entries, idempotently.
- `--apply` refuses on `layout_version < 3` with an actionable message.
- The bare 3a report and JSON output are unchanged (regression-pinned).
- No `terms.yaml` entry and no `decision-log` row is ever touched by a 3b path.
- Full suite green; ruff clean on changed files.
