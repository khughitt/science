# Schema-Closure Slice 3 — `search`: Field-Surface Inventory (Step 1)

Third slice of the per-kind schema-closure tranche, following `concept` (2026-07-28)
and `method` (2026-07-29). Procedure:
[`../conventions/schema-closure-slice-procedure.md`](../conventions/schema-closure-slice-procedure.md).

This document freezes the candidate universe and the disposition of every field before
any mixin is written. It is step 1 and nothing here is armed.

## What makes this slice different

| | `concept` | `method` | `search` |
|---|---|---|---|
| records | 329 | 51 | **36** |
| typed subclass | no | `MethodEntity` | **no** — `ProjectEntity` |
| packaged template | yes | yes | **none** |
| YAML source rows | yes | yes | **none — markdown only** |
| project extension scoped to it | no | no | **no** |
| `status` values in corpus | all `active` | 4 + `proposed` | **all `active`** |

Two consequences follow immediately:

- **Step 5 is the untyped variant.** With no `SearchEntity`, the surplus direction has
  nothing to explain; only the gap direction (admitted-but-undeclared) needs the UNHELD
  manifest.
- **There is no template surface to align in step 3.** The `method` slice's lesson about
  inventorying a template's `omit: true` fields has no analogue here — but that is a
  reason to look harder at the *other* surfaces, not a reason to relax. A kind with no
  template is a kind whose authored shape was never prescribed anywhere.

## Corpus measurement

36 markdown records, no YAML source rows, measured 2026-07-30 across all 7 projects:

| project | records |
|---|---|
| `~/d/cancer` (multiple-myeloma) | 19 |
| `~/d/health` | 10 |
| `~/d/natural-systems` | 7 |

Field occurrence over those 36:

| field | count | base 2.0? | note |
|---|---|---|---|
| `id`, `kind`, `title`, `status`, `created`, `updated` | 36 (all) | yes | the base-required set |
| `related` | 25 | no | **mixin must admit** |
| `source_refs` | 8 | no | **mixin must admit** |
| `task` | 5 | no | see the ruling below |
| `task_ref` | 2 | no | see the ruling below |
| `ontology_terms` | 1 | yes | base admits; no mixin entry needed |

`status` is `active` in **all 36**. Per the standing ruling, that uniformity is not
evidence — see "The `status` ruling" below.

## Candidate universe

The union of surfaces, not the observed corpus:

1. **Authored formats** — markdown frontmatter only. No `search` row exists in any
   project's `knowledge/sources/**.yaml`, so there is no source-migration burden here
   (unlike `finding`).
2. **Template output** — none. No `search.md` in the packaged templates or the repo-root
   `templates/`.
3. **Writer-emitted records** — none specific to `search`.
4. **Keyed consumer reads** — see the `task` finding below; the one function that looks
   task-shaped reads `related`, not a `task` key.
5. **Pydantic projection** — `ProjectEntity` (69 fields). No `SearchEntity`.
6. **Base 2.0** — admits `contributors`, `created`, `dataset_usage`, `description`, `id`,
   `kind`, `licenses`, `ontology_terms`, `same_as`, `schema_profile`, `sources`, `status`,
   `tags`, `title`, `updated`, `version`. Requires `id`, `kind`, `title`, `created`,
   `updated`.
7. **Loader-injected keys** — `graph/sources.py:1041` defaults `profile` into `raw` when
   the author omits it. `MarkdownAdapter.INJECTED_KEYS` is `{content, file_path,
   canonical_id}` and does **not** include `profile`.

### `profile` — admit, despite zero occurrences

No `search` record authors `profile`. It is admitted anyway, on two independent grounds:

- **The loader injects it.** `sources.py:1041` writes `raw["profile"]` whenever the author
  did not, so the key reaches the composed schema regardless of what any author does.
- **The shipped precedent is empirical, not assumed.** `mixin-concept-1.0`/`1.1` admits
  exactly `profile` and none of the other keys mutated into `raw` nearby (`type`,
  `content_preview`, `canonical_id`, `file_path`, `content`) — and `concept` is armed with
  329 records loading today. That fixes the effective validated key set for an armed
  markdown kind without my having to re-derive the injection order.

This is the `method` slice's zero-occurrence lesson applying to a different field:
**omitting `profile` would pass every corpus check and then refuse every record at load.**
Step 4 proves it rather than trusting this paragraph.

`promoted_from` is the mirror case and is **omitted**: no `search` record carries it, no
YAML source promotes into `search`, and `search` is not among the six unclosed kinds the
procedure lists as carrying it. Omission is the default refusal.

## The `status` ruling — no enum

The descriptor (`profiles/core.py:560-571`) declares
`["active", "complete", "retired", "archived"]`. The mixin will declare
`{"type": "string"}` with **no enum**, per the standing ruling: `search` is not in
`_CERTIFIED_KINDS` (`validate/kind_severity.py:24` is `frozenset({"hypothesis"})`), and a
schema enum refuses at load with no warning stage — harder than the validate ERROR the
doctrine already forbids for an uncertified kind.

**This slice is the first to face that ruling with the trap fully visible.** All 36
records are `active`, exactly the uniform-corpus condition that let
`mixin-concept-1.0`'s premature enum survive its own certification. No probe over this
corpus can distinguish a correct vocabulary from an over-tight one, so the corpus is not
consulted for this field at all.

## RULING (decided): `task` vs `task_ref` — omit both, migrate the corpus

**Decision: option B.** Both keys are omitted from the mixin, and the 7 records that
carry them are migrated to `related: [task:tNNN]` first. This is the slice's substantive
finding.

**Measured facts:**

- 5 `~/d/cancer` records carry `task:`; 2 `~/d/natural-systems` records carry `task_ref:`.
  Two projects independently invented different key names for the same association.
- **Neither key is read by any production code.** `consolidation_candidates.py:92`
  `_task_refs()` is the only task-shaped reader, and it reads **`related`**, selecting
  items with a `task:` prefix — its local variable is named `task_ref`, which is what
  makes this easy to misread. The `task`/`task_ref` hits elsewhere are
  `finding.qualifiers` (validate) and a `Transition` audit-record field, neither of which
  is entity frontmatter.
- **The values disagree in shape, not just the key.** `natural-systems` writes
  `task_ref: task:t021` — a canonical ref under a non-canonical key. `cancer` writes
  `task: t01` (a bare task number, not a ref) and, in one record,
  `task: discussion:0008-sc-bulk-integration` — which is not a task at all.
- **Neither record duplicates the link into `related`.** Checked directly: the
  natural-systems record's `related` carries questions and a paper, no task. So the
  association exists *only* in the unread key, and dropping the key drops the fact.

**Options:**

| | Effect | Cost |
|---|---|---|
| **A. Admit both as strings** | 7 records keep loading unchanged | Enshrines two names for one concept in a versioned schema, and blesses `task: discussion:...` as a task |
| **B. Omit both, migrate first** | One supported spelling: `related: [task:tNNN]`, which the one real consumer already reads | Corpus migration in 2 external repos; `t01` → `task:t01` is a value transform, and the `discussion:` value migrates to a *different* target |
| **C. Admit `task_ref` only, migrate `task`** | Keeps the canonical-valued key | Still two spellings across the tranche; the survivor is still read by nothing |

**Chosen: B.** Omission is the procedure's default refusal, and the alternative puts a
field in a versioned schema that no code reads and whose values are already inconsistent.
It also makes slice 3 carry a small corpus migration — which the procedure currently says
only `finding` does; that sentence needs correcting.

A fact found during the migration that strengthens the ruling: `natural-systems`'
`entities/searches/0003-ontology-completeness` has carried `task:t072` in `related` all
along. The supported spelling was already in use **in the same directory** as the
divergent key, so this is a migration onto an existing project convention rather than a
new one imposed by the toolkit.

### Migration status

| project | records | state |
|---|---|---|
| `~/d/natural-systems` | 2 | **DONE** — commit `a644c026` on `main`. `science validate` result sets compared as SETS (not counts) before and after: identical, 40 warnings, 0 errors. |
| `~/d/cancer/cancer-types/multiple-myeloma` | 5 | **BLOCKED** — the repo is on branch `big-picture-regen-2026-07-30` with uncommitted work from another session. Editing there risks the change being swept into an unrelated commit. |

**The mm30 migration is a hard prerequisite for step 4.** Certification composes the
candidate profile over every project; with 5 records still carrying `task:`, the run must
fail. That is the mixin working, not a defect to route around — do not soften the mixin
to make certification pass.

The five records and their targets, all verified to resolve before any edit:

| record | current | migrates to |
|---|---|---|
| `0001-bulk-sc-integration-methods` | `task: discussion:0008-sc-bulk-integration` | append `discussion:0008-sc-bulk-integration` to existing `related` |
| `0002-existing-mm-meta-analyses` | `task: discussion:0007-research-gaps` | new `related: [discussion:0007-research-gaps]` |
| `0003-meta-analysis-methods` | `task: t01` | `related: [task:t01]` |
| `0004-mm-deconvolution` | `task: t02` | `related: [task:t02]` |
| `0005-mm-drug-response-expression` | `task: t03` | `related: [task:t03]` |

Two of the five do not migrate to a task at all — `task: discussion:...` names a
discussion. `t01`/`t02`/`t03` are declared in `tasks/archive.md` as "Historical task
alias", retained expressly so older references stay resolvable, so `task:t01` is a valid
ref rather than a dangling one.

## What this slice does not close

- The `task`-family association has no schema-level relation semantics either way;
  `related` remains a flat string list.
- F1 (the Markdown authored-vs-injected-key blind spot) still weakens step 4 here, exactly
  as it did for `concept` and `method`.
- `~/d/cancer`'s `task: discussion:...` record is a data-quality defect independent of
  this slice's outcome; option B surfaces it, option A hides it behind a passing schema.
