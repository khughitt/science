# `science datasets infer-schema` — Schema-Authoring Scaffold — Design (Spec 3)

**Status:** approved design (2026-06-14). Third of the schema-driven-QA arc. Spec 1
(typed Data Resource schema, Pydantic SSOT) shipped 2026-06-13 (local `main` `5a4b6168`);
Spec 2 (schema→checks compiler + generic `tabular` program) shipped 2026-06-14 (local
`main` `fc3ffe0c`).

**Goal:** Give authors a low-friction, *safe* way to start populating the typed Data
Resource schema that Specs 1–2 consume — by inferring a resource's *observed shape*
(field names + coarse types) from its produced table, while leaving every build-fatal
*invariant* (constraints, keys, foreign keys, `qa:`) to deliberate human authorship.

**Tech stack:** Python, Pydantic v2 (Spec 1 models, already in `science_tool`),
pandas/pyarrow (already in `science_tool`), Click (existing `datasets` CLI group).

---

## 1. Why this is Spec 3 (the original premise is withdrawn)

The 3-spec decomposition originally framed Spec 3 as *"dedupe `datasets validate` ↔
`science_qa`, backfill schemas, retire the legacy qa-config columns."* A direct survey of
both repos (2026-06-14) invalidated two-thirds of that premise:

- **Nothing to retire.** There are **zero** committed qa-config artifacts anywhere
  (`science` or `~/d`). The hand-written per-column QA config Spec 2's compiler was meant
  to replace was never authored in production. Spec 2 removed a burden nobody had taken on.
- **Backfill is authoring, not code.** Of **182** `datapackage.json` under `~/d` (plus
  ~64 more in `datapackage.yaml`/`.yml` across the repos), ~161 carry **no schema at all**,
  ~20 carry only header/type `fields[]`, and exactly **1** (`~/d/r/p3/package`) reaches
  `foreignKeys` — and even it has no `constraints`, `primaryKey`, or `qa:`. **None exercise
  the full Spec 1 vocabulary.** Hand-authoring
  invariant schemas across ~180 packages is a curated, project-by-project human effort,
  and auto-committing inferred bounds/keys/`qa:` as build-fatal invariants would be
  actively harmful.
- **The "duplication" is forced, not removable.** `datasets validate` reads the descriptor
  through the Pydantic SSOT (`ResourceDescriptor.model_validate`); `science_qa/compile.py`
  re-reads it via plain dict access. The ~95% overlap **cannot be deduplicated by sharing
  code** — the SSOT lives in `science_tool`, and `science_qa` is deliberately pydantic-free
  and forbidden to import `science_tool`. The two readers are a deliberate architectural
  cost, not a bug.

The real bottleneck is that Specs 1–2 created a contract and a compiler with **near-zero
adopters**: the compiler has almost nothing to compile. So Spec 3 is re-scoped to attack
adoption directly. The arc re-decomposes as:

- **Spec 3 (this doc):** schema-authoring scaffold — infer *observed shape* safely.
- **Spec 4 (deferred):** `science datasets qa` reachability, once real schemas exist.
- **Ongoing (not an implementation plan):** curated schema-adoption campaign, per project.

In place of a removable dedup, this spec carries a small **consistency contract** (§7) so
the two forced descriptor readers can never silently diverge.

## 2. Core principle: machine writes shape, humans author meaning

The whole design rests on one separation rule:

> **If a wrong inference could make a future QA run build-fatal, it must never enter the
> schema by default — it appears only in the human-facing review report.**

Concretely, the *machine* may emit only `schema.fields[].name` and `schema.fields[].type`
— nothing else (not even the descriptor `format` field; see §4). Everything that maps to a structural QA check —
`constraints` (`required`/`unique`/`minimum`/`maximum`/`enum`/…), `primaryKey`,
`uniqueKeys`, `foreignKeys`, `missingValues`, and the `qa:` extension — is *meaning* a
human must author. Inference may *recommend* these in a report, never *emit* them into the
descriptor.

## 3. Command surface & UX

A new subcommand in the existing `datasets` Click group, beside `validate`:

```
science datasets infer-schema DP --resource R            # read-only: diff + review report (default)
science datasets infer-schema DP --resource R --write    # apply ONLY safe names+types in place
science datasets infer-schema DP --resource R --emit-suggestions sugg.yaml   # save report; never mutates contract
```

- `DP` — path to a datapackage descriptor (`datapackage.json`, `.yaml`, or `.yml`) or the
  directory containing one. Format is detected by extension; the descriptor is read
  generically (`json.load` / `yaml.safe_load`), independent of the commons
  canonical-datapackage machinery (`commons/datapackage.py`). The estate is mixed — ~183
  JSON and ~64 YAML descriptors across the repos — so JSON-only would strand ~26% of it.
- `--resource R` — **required** (no bulk `--all` in this spec; see §9). `R` matches
  `resources[].name` **primarily**; only if no name matches does it fall back to
  `resources[].path`. An `R` that matches more than one resource — or matches one
  resource's name and a *different* resource's path — is an **ambiguity error** (abort),
  never a silent pick.
- `--sample N` — row cap for value-derived statistics (default cap; types from parquet
  metadata need no scan, see §4).
- `--format table|json` — default human-readable diff + report; `json` emits a structured
  `{patch, report}` object for tooling, mirroring the other `datasets` commands'
  `OUTPUT_FORMATS`.
- `--write` — apply the safe patch in place (§6).
- `--emit-suggestions FILE` — write the review report to `FILE` as YAML; **never** mutates
  the datapackage.

Default (no `--write`) is **read-only**: it prints (a) the proposed descriptor patch as a
diff against the resource's current schema and (b) the review report. Nothing on disk
changes.

## 4. Inference engine (the machine-safe half)

`infer_schema.py` reads the resource's `path` table relative to the datapackage directory:

- **Parquet:** field names + types from the Arrow schema directly — no row scan needed for
  typing.
- **CSV:** names from the header; types sniffed from the first `--sample N` rows.
- **Coarse Frictionless type map** (conservative — matches `science_qa`'s
  numeric-vs-non-numeric granularity, and never guesses a build-relevant fine type):

  | observed dtype | Frictionless `type` |
  |---|---|
  | integer | `integer` |
  | float | `number` |
  | boolean | `boolean` |
  | `datetime64` | `datetime` |
  | `object` / string / **mixed** | `string` (+ warning if mixed/object) |

  `date`, `year`, `yearmonth`, `duration`, `geopoint`, `geojson` are **not** inferred —
  they need human eyes and a wrong fine-type can mis-drive a future check. Mixed-dtype
  `object` columns map to `string` and raise a report warning, never a silent guess.

The **proposed patch** carries only `name` + `type` per field — nothing else. `format` is
**not** emitted: it can acquire parser/validator semantics downstream (CSV dialect,
date/number string formats), which violates the observed-shape-only rule, so it is never
inferred. (Distinct from the `--format table|json` *output* option in §3, which controls
the command's own rendering, not the descriptor.) The patch **preserves** any
already-authored descriptor content: field-level `constraints`/`qa`/extras, and
table-level `primaryKey`/`uniqueKeys`/`foreignKeys`/`missingValues`/`qa`/extras. It never
emits any of those itself.

The patch is presented as a **diff against the existing schema** (§3 default mode):

```
+ add    field is_hit        type=boolean
~ change field dose_uM  string -> number      (type-only change; see §6 conflict rules)
= same   field drug_id        type=string
- remove field legacy_col   (in schema, not in file)
```

For a schemaless resource every field is `+ add`; for a type-only resource it reconciles;
`- remove` rows are **reported, never auto-applied** (a column absent from the current file
may be a transient artifact — removal is a human decision).

## 5. The review report (the human-only half)

Everything build-fatal is *recommended* here, each line explicitly labelled
*"recommendation — not emitted as invariant"*:

- **identifier** candidates — unique + non-null in sample → consider `primaryKey`.
- **enum** candidates — low cardinality → consider `constraints.enum`.
- **required** candidates — no nulls observed → consider `constraints.required`.
- **unique / composite-key** candidates.
- **missing-sentinel** candidates — recurring out-of-band values (e.g. `-999`, `"NA"`).
- **bound** candidates — sample `min`/`max` for numeric/date columns → possible
  `minimum`/`maximum` (sample-derived, explicitly *not* a constraint).
- **warnings** — mixed-type columns, nullable columns, `object`/`list` columns,
  high-cardinality strings.

Recommendations may include suggested snippets, but those live **outside** the machine
patch. `--emit-suggestions FILE` serialises the report to YAML; it never touches
`datapackage.json`. Because every recommendation is sample-derived, the report states the
sample size and that statistics are observations, not guarantees.

## 6. `--write` semantics & guards

`--write` applies **only** the names+types patch, under strict guards. Any guard violation
**aborts with a clear error and writes nothing** — the tool never silently "fixes".

**Format-agnostic core path (one mutation path for JSON and YAML).** After parse, both
formats share a single in-memory flow: *load the descriptor mapping → mutate the selected
`resources[]` entry → validate the whole package (§6.3) → serialize back in the input
format*. Format only determines the parse and serialize ends; the mutation and validation
in the middle are identical. The descriptor is handled as a plain mapping throughout
(`json.load`/`yaml.safe_load`), never routed through the commons canonical-datapackage
parser — that profile imposes hash/bytes metadata general datapackages lack, so it would
make the scaffold unusable on valid non-commons packages.

1. **Preserve-only.** Authored content is never overwritten or dropped: field-level
   `constraints`/`qa`/extras **and** table-level `primaryKey`/`uniqueKeys`/`foreignKeys`/
   `missingValues`/`qa`/extras all survive **value-preserved** (semantically identical;
   exact bytes and formatting are not, since the descriptor is canonically re-rendered —
   §6.4).

2. **Conflict = type disagreement only.** The sole conflict is **an existing authored
   `type` that differs from the inferred type** for a field whose name is unchanged →
   abort (the author committed a type the data contradicts; that is theirs to resolve, not
   the machine's). It is **not** a conflict for an existing field to carry
   `constraints`/`qa`/extras: when the field's name and type are unchanged and its metadata
   is preserved, the field is left exactly as authored (a `= same` row), no error. New
   fields are added; fields absent from the file are *reported* (`- remove`) but never
   removed.

3. **Focused, whole-package post-validation** (deliberately *not* the global
   `datasets validate`, which carries broader project assumptions that could reject
   unrelated legacy state): apply the patch to the selected resource **in-memory**, then
   parse **every** resource in the package through Spec 1's
   `ResourceDescriptor.model_validate` and run `package_consistency_issues(all_descriptors)`
   over the full list. The whole-package step is required because cross-resource foreignKey
   resolution needs every descriptor (`datasets/schema.py:200`): validating the mutated
   resource alone would both false-fail valid *external* FKs and miss other resources whose
   FKs point *at* the mutated one. Also verify the referenced table file still matches the
   written field set. Save only if all pass.

4. **Atomic, canonical write — in the input's own format.** Write to a temp file in the
   same directory, then `os.replace` over the original descriptor file. The descriptor is
   re-rendered canonically in the format it was read in: JSON input → canonical JSON, YAML
   input → canonical YAML (`yaml.safe_dump`, stable key order). YAML writes preserve the
   descriptor's **mapping semantics only** — comments, anchors, quoting style, and any
   ordering beyond the deterministic canonical output are **not** preserved (and JSON cannot
   carry comments at all). Documented in the command help and the report so it is never a
   surprise.

## 7. Consistency contract (the in-spec guardrail)

In place of a removable dedup, a shared **descriptor-fixture corpus** keeps the two forced
readers honest. The fixtures are the shared *artifact*; no code crosses the boundary.

- **Home:** `science/fixtures/descriptor_contract/*.json` — a neutral directory sibling to
  `tests/` and `qa/`, owned by **neither** test suite (so neither package's tests depend on
  the other's test tree). Both suites load the files by `Path(__file__)`-anchored path.
- **science_tool side** (`science/tests/.../test_descriptor_contract.py`): every fixture
  passes `ResourceDescriptor.model_validate` + `package_consistency_issues`; and the patch
  `infer-schema` emits over known fixture tables round-trips as a *valid* Spec 1 descriptor
  (the same focused validation `--write` performs).
- **science_qa side** (`science/qa/tests/test_descriptor_contract.py`): every fixture
  either compiles via `schema_to_config` **or** raises `CompileError` for a *documented
  compiler-only reason* — a pinned allow-list (composite foreignKey; malformed bound
  value). Any other failure, or an unexpected divergence between the two sides, fails the
  test.

This guarantees the property the original "dedup" wanted without pretending the code is
shareable: **a descriptor accepted by Spec 1 is either QA-compilable or fails only for a
reason we have written down.**

## 8. File structure

| File | Change | Responsibility |
|---|---|---|
| `science/src/science_tool/datasets/infer_schema.py` | **create** | descriptor read/write (JSON+YAML by extension), table read, coarse type inference, resource resolution (name→path), diff-vs-existing, review report, guarded whole-package-validated atomic write |
| `science/src/science_tool/cli.py` | modify | `datasets infer-schema` command (beside `validate`) |
| `science/src/science_tool/datasets/schema.py` | reuse | Spec 1 models to construct/validate the proposed descriptor + focused post-write validation |
| `science/fixtures/descriptor_contract/*.json` | **create** | shared consistency-contract corpus (neutral home) |
| `science/tests/.../test_infer_schema.py` | **create** | inference, diff, report, guarded-write, atomic/canonical write |
| `science/tests/.../test_descriptor_contract.py` | **create** | science_tool side of the consistency contract |
| `science/qa/tests/test_descriptor_contract.py` | **create** | science_qa side of the consistency contract |

`science_qa` source is **untouched**; only a new test reads the shared corpus. The
non-importing boundary is preserved.

## 9. Scope boundaries (deferred)

- `--all` bulk mode (per-resource only here).
- `science datasets qa` reachability (Spec 4).
- Any inference of `constraints` / `primaryKey` / `uniqueKeys` / `foreignKeys` / `qa:` /
  missing sentinels / bounds **into** the schema — these are report-only, forever
  human-authored.
- Fine temporal/geo typing (`date`/`year`/`duration`/`geopoint`/…).
- Emitting the descriptor `format` field (report-only reasoning, never inferred — §4).
- Formatting/comment-preserving writes (canonical re-render, in the input's own format, is
  intentional — §6.4).
- `science_qa` and `science_tool` remain non-importing.

## 10. Testing strategy

- **Inference:** parquet (Arrow-schema typing) and CSV (sampled typing); each coarse type;
  mixed/`object` → `string` + warning; `format` is never emitted.
- **Descriptor formats:** JSON in → canonical JSON out; YAML in → canonical YAML out;
  extension-based detection; a directory argument resolves the contained descriptor.
- **Resource resolution:** `R` matches by `name`; falls back to `path` when no name
  matches; an `R` matching two resources (or a name-vs-other-path collision) → ambiguity
  error.
- **Diff:** against an absent schema (all `+ add`), a type-only schema (reconcile), and a
  schema with an authored type that disagrees (`~ change` flagged as a conflict per §6.2).
- **Review report:** each recommendation category fires on a crafted fixture; every line is
  labelled non-invariant; `--emit-suggestions` writes YAML and leaves the descriptor file
  byte-identical (no descriptor write occurs in that mode).
- **`--write`:** happy path (adds fields, preserves authored field-level *and* table-level
  metadata); refusal on a type-disagreement conflict (writes nothing); a field carrying
  `constraints`/`qa` with an unchanged name/type is a no-op (`= same`, not a conflict);
  atomic temp-file + `os.replace`; canonical re-render is deterministic in both JSON and
  YAML; whole-package post-validation passes a valid *external* foreignKey, and rejects a
  descriptor that would parse invalid.
- **Consistency contract:** both sides over the shared corpus (§7), including the pinned
  compiler-only-failure allow-list.
