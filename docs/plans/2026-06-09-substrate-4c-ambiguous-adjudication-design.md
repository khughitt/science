# Substrate Phase 4c — Ambiguous-Row Adjudication & Curie External-Reference Authority

**Status:** approved design (2026-06-09)
**Branch:** `substrate-4c-ambiguous-adjudication`
**Predecessors:** Phase 4a (terms.yaml coined-concept promotion, `3c7247be`), Phase 4b
(bibliography external-reference resolver, `37a7859f`)
**Master design:** `docs/plans/2026-06-06-knowledge-meta-model-and-substrate-design.md`
(§B5 retirement, §B2 external references, §C3 adapters, §D5 concept-vs-tag judgment)

---

## 1. Problem

The 3a triage classifier buckets every aggregate (`entities.yaml` / `terms.yaml`)
owner row into one of six buckets. Phases 3b/3c/4a/4b drained five of them
(coined concepts/latents/decisions → owner files; decision-log → `core/decisions.md`
view; cruft/shadow → delete; external-ref/bibliography → bib-backed retirement).
What remains is the catch-all **`AMBIGUOUS`** bucket: in MM30, **96 rows** (81 in
`terms.yaml`, 15 in `entities.yaml`) that no rule could name.

That bucket is not actually homogeneous. It is two distinct populations plus a
small residual:

| Population | MM30 kinds & counts | Distinguishing evidence |
|---|---|---|
| **Curie-bearing biomedical refs** | protein (21 UniProt), disease (5 MONDO), drug (8 ChEMBL/ChEBI), gene (1 HGNC) = **35** | row carries a `primary_external_id` (a full `ExternalId`: `source`, `id`, `curie`, `provenance`) |
| **Bare coined vocabulary** | method (16), topic (36) = **52** | bare `id + title + description`, no external id |
| **Epistemic question stubs** | question (7) | bare `id + title`, but `question` is an epistemic kind |
| **True residual** | no-curie disease (1), no-curie drug (1), any unknown kind = **2** | biomedical kind, but no `primary_external_id` |

Each population needs a different disposition, and the curie population needs a
**backing authority** so retiring its aggregate row does not destroy the
`canonical_id → curie` mapping (which today lives only in the row itself).

The invariant 4b established and 4c must preserve:

> A `canonical_id` resolves because a **named authority source backs it**, not
> because a deprecated aggregate row happens to still exist.

## 2. Scope (approved)

**In scope** — adjudication capability + an executable end-state gate:

1. Split `AMBIGUOUS` into named buckets: `CURIE_EXTERNAL_REF`, widened `COINED`
   (method/topic), `QUESTION_DEFERRED`, and a tightened residual `AMBIGUOUS`.
2. A dedicated **curie external-reference authority** — new
   `knowledge/sources/local/external_refs.yaml` + a new `CurieRefAdapter`
   (`participation_mode = EXTERNAL_REFERENCE`).
3. A retirement action `--migrate-curie-refs` that **creates** the authority row
   and **drops** the aggregate row (backed-only, idempotent).
4. Widen `--promote-coined` to method/topic by making those builtin kinds
   **slug identity kinds**.
5. A `layout_version >= 3` **conformance gate**: ERROR if any multi-type
   aggregate owner rows remain.

**Out of scope** (deferred, by design):

- **Deleting the `AggregateAdapter` class / deprecated-owner mode.** The v3 gate
  *asserts* the end-state; the code deletion is a trivial post-migration
  follow-up, and is provably blocked while any project still loads aggregate
  rows. MM30's live retirement is v3-gated (Task #30).
- **Promoting or renumbering `question:`.** Epistemic questions have richer
  expected body structure, a reservation flow, and big-picture / open-question
  graph behavior; a one-line stub is not enough to mint an owner. Routed to a
  retained, *visible* bucket and left for a focused epistemic-question migration.
- **Authoring curies for no-curie disease/drug.** Do not invent authority.
- **Coordinating with the bio/commons ownership program.** A curie external-ref
  yields automatically to a future `owner_scope=commons` owner (the 4b precedence
  rule), so no lock-step is required.

## 3. The bucket split

`graph/aggregate_triage.py` gains buckets and `_bucket`'s terminal fan-out is
rewritten. Precedence is unchanged for the already-handled buckets (shadow →
cruft → decision-log → external-ref → coined); the new logic replaces only the
final `return AMBIGUOUS` line.

New `AggregateBucket` members:

- `CURIE_EXTERNAL_REF = "curie-external-ref"`
- `QUESTION_DEFERRED = "question-deferred"`

New terminal logic (after the existing coined check):

```
# row carries a validated external authority id -> curie external ref
if has_primary_external_id:                       # entity.primary_external_id is not None
    return CURIE_EXTERNAL_REF, f"{kind} carries primary_external_id {curie} -> curie external ref"
# bare epistemic question stub: visible but never auto-promoted in 4c
if self_sourced and kind == "question":
    return QUESTION_DEFERRED, "bare question stub -> requires epistemic authoring (deferred)"
# bare project vocabulary: method/topic promote as slug owners
if self_sourced and kind in _COINABLE_VOCAB_KINDS:   # {"method", "topic"}
    return COINED, f"self-sourced vocabulary kind={kind} -> coined"
# biomedical / unknown kind with no authority -> human decision
return AMBIGUOUS, f"{kind} without primary_external_id -> requires human identity decision"
```

`has_primary_external_id` requires the triage to see the row's
`primary_external_id`, which the current classifier does not carry. The 3a loader
already captures per-row `AggregateRowMeta`; 4c extends that capture to record the
row's `primary_external_id` — taken from the **validated entity**
(`entity.primary_external_id`, a typed `ExternalId`) at the same emit point. The
classifier reads it from the joined meta.

Note the contract: `primary_external_id` is a real schema field of type
`ExternalId`, which requires **all** of `source`, `id`, `curie`, `provenance`, and
`schema.model_validate(raw)` runs **before** the aggregate-meta capture. So a
malformed `primary_external_id` never reaches the classifier at all — it fails
`ExternalId` validation and the whole row is **skipped**
(`entity_schema_validation_failed`), not routed to `AMBIGUOUS`. The classifier
therefore sees only two states: a full validated `ExternalId` (→
`CURIE_EXTERNAL_REF`) or `None` (→ routed by kind). A half-filled mapping cannot
masquerade as backed because it cannot load.

Bucket dispositions:

| Bucket | Disposition | Retirement action |
|---|---|---|
| `CURIE_EXTERNAL_REF` | migrate to `external_refs.yaml`, drop aggregate row | `--migrate-curie-refs` |
| `COINED` (method/topic) | promote id-preserving slug owner | `--promote-coined` (widened) |
| `QUESTION_DEFERRED` | retained + visible, never written | none (visible only) |
| `AMBIGUOUS` (residual) | retained/rejected, flagged | none (human decision) |

## 4. Curie external-reference authority (the 4b mirror)

### 4.1 The authority file

`knowledge/sources/local/external_refs.yaml`, root key `references:`:

```yaml
references:
  - id: protein:BCMA
    type: protein
    title: BCMA
    primary_external_id:
      source: UniProtKB
      id: Q02223
      curie: UniProtKB:Q02223
      provenance: manual
    description: B-cell maturation antigen (TNFRSF17), the principal MM surface target...
```

This file is the project's durable assertion of `canonical_id → curie`. It is
**not** throwaway: like `references.bib` records the project's bibliography, this
records the project's intended ontology cross-references. A future commons owner
for `protein:BCMA` supersedes it via normal external-ref precedence.

### 4.2 `CurieRefAdapter`

New `graph/storage_adapters/curie_ref.py`, modeled on `bib.py`:

- `name = "curie-ref"`, `participation_mode = ParticipationMode.EXTERNAL_REFERENCE`.
- **Constructor takes `local_profile`** (like `AggregateAdapter`, *unlike*
  `BibAdapter` whose `papers/references.bib` is profile-independent). The path is
  built from the resolved profile, **not hardcoded to `local`**:
  `project_root / "knowledge" / "sources" / self._local_profile / "external_refs.yaml"`
  — exactly mirroring `AggregateAdapter`. **Do not import
  `local_profile_sources_dir` from `science_tool.graph.sources` into this adapter:**
  `sources.py` registers `CurieRefAdapter`, so importing back from sources would
  create a circular import at module load. (The `--migrate-curie-refs` *writer* in
  `aggregate_retire.py` — §4.5 — is not imported by `sources.py`, so it may use the
  helper freely.) `sources.py` registers `CurieRefAdapter(local_profile=local_profile)`,
  passing the same resolved `local_profile` it gives `AggregateAdapter`.
  `knowledge/sources/local/external_refs.yaml` is only the *common* MM30/example
  path, not a constant.
- `discover()` → one `SourceRef(adapter_name="curie-ref", path=<resolved rel path>, line=i)`
  per row. **Both integrity failures raise loudly** — never a silent skip:
  - **Intra-file duplicate id** → raise (a second row for the same `id` is a
    conflict; see §4.3).
  - **Malformed `primary_external_id`** (missing any of `source`, `id`, `curie`,
    `provenance` — the full `ExternalId` shape) → raise. A malformed *aggregate*
    row is skipped at schema-validation time (`entity_schema_validation_failed`)
    and surfaced as a `SkippedEntity`, which is acceptable for transitional debt;
    but `external_refs.yaml` is the **durable backing authority** once aggregate
    rows retire, so the adapter validates the shape *itself* at discover time and
    fails loud rather than deferring to a later skip — a silently-dropped authority
    row would leave citations unresolved or lose the curie mapping with no clear
    failure.
- `load_raw()` → `{kind: <type>, id: <id>, title: <title|id>, primary_external_id: {...}, same_as: [<curie>], file_path: <resolved rel path>, description?: ...}`.
  - **`file_path`** is the resolved relative path of `external_refs.yaml`
    (matching `BibAdapter`, which sets `file_path=_BIB_REL`). `_enrich_raw`
    defaults a missing `file_path` to `""` → weak `prov:wasDerivedFrom`
    provenance for the authority node, so set it explicitly.
  - **`same_as`** is a **list** `[curie]`, *not* a `frozenset`: `_enrich_raw`
    normalizes `same_as` only when `isinstance(vals, list)` (`sources.py:740`); a
    non-list value is silently dropped and the curie edge would never materialize.
- Synthesizes a lightweight in-memory `Entity` per row whose `same_as` carries the
  curie. This drives correct materialization (§4.4) — the existing same-as path
  turns it into a `skos:exactMatch` to a URIRef external-term node. **Never**
  writes owner files, **never** participates in owner collisions.
- Explicit `RuntimeError` guard if `load_raw()` precedes `discover()` (no silent
  re-read), matching `BibAdapter`.
- Source-specific parsing/backing logic lives **inside the adapter** (and the
  retirement action), never in the generic loader branch.

`classify_owner_scope("curie-ref") → ("curie-ref", False)` in
`graph/identity_table.py` (a non-deprecated authority scope, exactly like
`bib`).

### 4.3 Generic external-reference defer guard

4b's loader defer was `isinstance(adapter, BibAdapter)`. Generalize it (§B3a) to:

```python
# An external-reference adapter contributes refs, not owners. If a prior
# declaration for this id already exists (an owner, or an aggregate stub still
# in transition), defer to it — do not collide under strict load.
if adapter.participation_mode == ParticipationMode.EXTERNAL_REFERENCE \
        and entity.canonical_id in identity_table:
    continue
```

The branch says **only** "this adapter contributes external references and a
prior declaration exists → defer." No adapter-specific knowledge. This covers
bib *and* curie in one rule. Registration order: `CurieRefAdapter` after
`AggregateAdapter` (so a lingering aggregate stub precedes the curie row and the
defer fires); the existing `# AggregateAdapter must precede …` comment at the
registration site is updated to name the curie adapter too. Owner →
external-reference flip is automatic on the next load once the aggregate row
drops.

**Conflict safety (review fix).** The loop-local dedup table records prior
declarations *without* participation mode, so a generalized "defer to any prior
declaration" would silently skip a *second* `external_refs.yaml` row for the same
id rather than flag it. Two layers close this:

1. **Adapter-level integrity (primary):** `CurieRefAdapter.discover()` rejects
   intra-file duplicate ids loudly (§4.2). The `--migrate-curie-refs` writer
   enforces the same at authoring time (§4.5: same curie → reconcile, different
   curie → loud reject). So `external_refs.yaml` cannot present two conflicting
   rows for one id in the first place.
2. **Defer semantics:** with (1) guaranteeing at most one external-ref row per id,
   the generic defer is only ever deferring a curie row to a *prior owner or
   transitional aggregate stub* — its intended use. A curie id colliding with a
   prior external-ref authority row of a *different* adapter (e.g. a `bib`
   `paper:` row) is structurally implausible (curie kinds are
   protein/disease/drug/gene, bib is `paper`), and (1) would catch any same-file
   recurrence regardless.

### 4.4 Materialization

Two distinct concerns, each routed to the **correct existing contract** — not a
new literal predicate and not a kind/curie-presence heuristic.

**(a) The curie cross-reference — reuse the existing `same_as` path.**
Materialization already turns an entity's `same_as` targets into
`skos:exactMatch` edges to a **URIRef external-term node**, via
`_link_same_as_external` → `_external_uri(curie)` + `_register_external_term`
(`graph/materialize.py:410`, with the exact precedent example
`topic:PHF19 ↔ UniProtKB:Q5T6S3`). Because `CurieRefAdapter` populates the
synthesized entity's `same_as` with the curie (§4.2), the curie node gets a
**correct** `skos:exactMatch` *to a URIRef* (not a literal) that connects to the
registered external-term node — **with no new materialization code**. The
earlier draft's `skos:exactMatch → Literal(curie)` was inconsistent RDF and is
rejected.

**(b) The lightweight `prov:Entity` marking — gate on declared participation,
not kind/curie.** `_add_entity` receives only an `Entity`
(`graph/materialize.py:236`), so it cannot see participation mode on its own.
Inferring "external reference" from `primary_external_id` presence would be
**wrong**: a future commons-*owned* `protein:BCMA` legitimately carries a curie
and must keep full owner treatment. Therefore:

- Build `external_reference_ids: set[str]` once in `_build_dataset_from_sources`
  from `sources.identity_declarations` (ids whose
  `participation_mode == ParticipationMode.EXTERNAL_REFERENCE`).
- Thread it into `_add_entity` and emit `(uri, RDF.type, PROV.Entity)` **iff**
  `entity.canonical_id in external_reference_ids`. An owned entity carrying a
  curie is *not* in the set → no external-ref marking, and its curie still
  materializes via (a).

This subsumes 4b's `kind == "paper"` prov:Entity marking: the implementer
**converges** that branch onto the same `external_reference_ids` gate (papers are
declared EXTERNAL_REFERENCE, so they remain marked), removing the kind-keyed
special case. The paper-specific metadata (`dcterms:date` / `sci:doi` /
`dcat:downloadURL`) stays keyed on the paper fields and is unchanged.

### 4.5 `--migrate-curie-refs` (distinct from `--retire-external-refs`)

A **separate** flag from 4b's `--retire-external-refs`, because the mutation
semantics differ:

- `--retire-external-refs` (4b): *delete* an aggregate bibliography row **when
  backed by an existing authority** (`references.bib`).
- `--migrate-curie-refs` (4c): *create* a new authority row in
  `external_refs.yaml`, **then** delete the aggregate row.

Keeping the primitives explicit is clearer and safer; an umbrella flag can come
later. Per `CURIE_EXTERNAL_REF` row, in one apply:

1. **Append** `{id, type, title, primary_external_id, description}` to
   `external_refs.yaml` (create the file with root key `references:` if absent).
   The writer resolves the target path through the project config —
   `local_profile_sources_dir(project_root, local_profile=resolve_local_profile_name(project_root)) / "external_refs.yaml"`
   — **never** a hardcoded `knowledge/sources/local/...` string (the same fixture
   gotcha earlier substrate plans corrected for `AggregateAdapter`).
2. **Drop** the aggregate row (index-set rewrite, same machinery as promote/delete).

**Backed-only:** only `CURIE_EXTERNAL_REF` rows reach this action, and a row
reaches that bucket only when it carries a validated full `ExternalId`. A
*malformed* `primary_external_id` is skipped at load (never triaged); an *absent*
one buckets by kind (never `CURIE_EXTERNAL_REF`). So the migration target always
carries a well-formed `{source, id, curie, provenance}` — the exact parallel to
4b's bib-backed check.

**Idempotency (refinement):**

- If `external_refs.yaml` already contains the same `id` with the **same**
  `primary_external_id` → treat as already backed: skip the append, reconcile by
  dropping the aggregate row. (Safe re-run / crash recovery.)
- If the same `id` exists with a **different** curie → **reject loudly** (do not
  append a conflicting second mapping, do not drop the aggregate row); surface in
  the report's `rejected` with the conflicting curies.

`external_refs.yaml` rows are read by `CurieRefAdapter` (EXTERNAL_REFERENCE), so
they never re-enter the aggregate triage — no risk of a migrated row being
re-classified.

## 5. Coined vocabulary promotion (method / topic)

Set the builtin path policy `strategy` for `method` and `topic` from `numeric`
to `slug` in `entities.py` `_BUILTIN_MARKDOWN_POLICIES`:

```python
"method": EntityPathPolicy(Path("entities/methods"), "slug"),   # was "numeric"
"topic":  EntityPathPolicy(Path("entities/topics"),  "slug"),   # was "numeric"
```

These become **slug identity kinds going forward.** Precise statement of the
consequence (refinement):

- A slug local part like `bayesian-inference` now conforms and promotes
  id-preserving to `entities/methods/bayesian-inference.md`.
- An old numeric-shaped local part like `0001-foo` **also** satisfies the slug
  regex, so existing numeric-id method/topic files in any project remain valid —
  this *broadens* acceptance, it does not invalidate.
- **But** id *generation* for these kinds becomes slug-derived going forward
  (new method/topic ids are slugs, not `NNNN-`). That is appropriate for
  vocabulary kinds; the spec states it explicitly so it is not a surprise.

`question` stays `numeric` — untouched.

Promotion itself reuses the existing `--promote-coined` action (which already
writes slug owners since 4a) — no new flag. With method/topic now slug-policy,
their bare aggregate rows bucket `COINED` and flow through the same promoter.
The `{**local, **builtin}` precedence rule is **not** changed (avoids reopening
the core-kind shadowing bug class).

## 6. Question deferral

Bare `question:` stubs route to `QUESTION_DEFERRED`. No retirement action ever
writes or deletes them in 4c. They remain **visible** debt (counted in the
triage report and held in the aggregate file), preserving the open-question
signal until a focused epistemic-question migration authors real owners or does a
deliberate ref-rewrite/renumber. Because these rows keep `entities.yaml`
non-empty, they hold the v3 conformance gate (§7) red for MM30 — the intended
block.

## 7. End-state conformance gate

Extend the aggregate-stub conformance surface (`validate/checks/aggregate_stub.py`
or a sibling check): at `layout_version >= 3`, **ERROR** if any multi-type
aggregate owner rows remain (i.e. `entities.yaml` / `terms.yaml` are not fully
retired). At `layout_version < 3`, behavior is unchanged (the existing lone-stub
WARN visibility). The gate is scoped strictly to multi-type aggregates: the
`AggregateAdapter` also discovers and deprecates *single-type* aggregates
(`doc/<plural>/<plural>.{json,yaml}`), but 4c provides no retirement path for
those, so the check filters them out (`path.name in MULTI_TYPE_AGGREGATE_ROOT_KEYS`)
rather than asserting an end-state it cannot deliver.

This makes the target state **executable and asserted** without deleting any
adapter code. The `AggregateAdapter` class keeps loading aggregate rows (v2
projects depend on it; the migrator/promoter must read them). Deletion is a
post-migration follow-up gated on *all* projects crossing the v3 gate — out of
scope here.

## 8. MM30 disposition under 4c (read-only smoke, still v2)

After 4a (`--promote-coined`) + 4c on a hypothetical v3 MM30:

- **35 curie rows** (terms.yaml) → `external_refs.yaml`; terms.yaml curie rows dropped.
- **52 method/topic rows** → `entities/methods/*.md`, `entities/topics/*.md`.
- **108 concept rows** (terms.yaml) → owner files (4a).
- terms.yaml → **empty → retires.**
- **7 question rows** (entities.yaml) → `QUESTION_DEFERRED`, retained.
- **2 no-curie disease/drug** → residual `AMBIGUOUS`, retained.
- entities.yaml → **non-empty** (questions + residual) → v3 gate **ERRORs** →
  AggregateAdapter retirement stays blocked until questions are resolved. This is
  the intended, correct block.

All of this is **v3-gated**: on v2 MM30 every `--apply` refuses (exit 1, names
`layout_version`), git stays clean. 4c is a capability phase; the live migration
is Task #30.

## 9. Testing

TDD, subagent-driven (fresh implementer + two-stage spec/quality review per task
+ final holistic). Per-task coverage:

- **Bucket matrix** — unit tests on pure `_bucket`: curie-bearing → `CURIE_EXTERNAL_REF`;
  no-`primary_external_id` biomedical kind → residual `AMBIGUOUS`; bare method/topic →
  `COINED`; bare question → `QUESTION_DEFERRED`; no-curie disease/drug → residual.
- **Row-meta capture** — loader carries the validated `primary_external_id` into
  `AggregateRowMeta`; a malformed `primary_external_id` fails `ExternalId` validation
  upstream, so its row is skipped (a `SkippedEntity`) and never captured.
- **`CurieRefAdapter`** — discover → one ref per well-formed row; **intra-file
  duplicate id raises**; **malformed `primary_external_id` row raises** (durable
  authority fails loud, not silent skip); synthesized entity carries the curie in
  a **list** `same_as` and sets `file_path`; `RuntimeError` if load_raw precedes
  discover; scope `("curie-ref", False)`; **path resolved via
  `local_profile_sources_dir`** (test with a non-`local` profile name to catch a
  hardcoded path).
- **Generic defer** — an EXTERNAL_REFERENCE adapter defers to a prior declaration;
  bib + curie both covered by the single branch; no strict-load collision with a
  transitional aggregate stub of the same id.
- **Materialize (a) curie edge** — synthesized curie node emits
  `skos:exactMatch` to a **URIRef** external-term node (assert object is a
  URIRef, not a Literal) and the external term is registered.
- **Materialize (b) participation gate** — an id declared EXTERNAL_REFERENCE gets
  `prov:Entity`; an *owned* entity carrying the same-shaped `primary_external_id`
  does **not** get the external-ref marking yet still emits its curie via
  `same_as`; paper nodes still `prov:Entity` through the converged gate.
- **`--migrate-curie-refs`** — round-trip: aggregate row → `external_refs.yaml`
  row + dropped aggregate row; citation to the id still resolves after reload;
  idempotent re-run (same curie → no-op append + reconcile); conflicting curie →
  loud reject, no mutation; writer honors a non-`local` profile dir. v2 `--apply`
  refused.
- **method/topic slug** — load → `--promote-coined` → reload finds owner as
  `adapter="markdown"`; numeric-shaped legacy id still conforms.
- **method/topic creation path** — `create_entity(project_root, "method", ...)`
  (and/or `science entities create --kind method`) generates a **slug** id/path
  under `entities/methods/` and the rendered frontmatter id agrees — guards
  against drift now that these are slug identity kinds going forward.
- **v3 gate** — ERROR when residual multi-type aggregate rows remain at
  `layout_version >= 3`; silent/WARN below.
- Full suite green; lint clean on touched files.

## 10. Non-goals recap

- No `AggregateAdapter` class deletion.
- No `question` promotion/renumber.
- No invented curies for no-curie biomedical rows.
- No `{**local, **builtin}` precedence change.
- No live MM30 mutation (v3-gated).
- No bio/commons program coupling.
