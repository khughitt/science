# Substrate Phase 4b — bibliography external-reference resolver

> Part of the structural-aggregate retirement line (§B5 of
> `2026-06-06-knowledge-meta-model-and-substrate-design.md`), and the first real
> consumer of the **external-reference** participation mode (§B1/§B3/§C3) and the
> external-reference resolver named in §B2/§B3a/§D4. Phases 3a–3c retired the
> `entities.yaml` `coined`/`cruft`/`shadow`/`decision-log` buckets; **Phase 4a**
> (merged `3c7247be`) added `terms.yaml` coined-concept promotion. Phase 4 is
> decomposed **4a (coined concepts) → 4b (this doc — bibliographic external-refs)
> → 4c (ambiguous adjudication + `AggregateAdapter` deprecated-owner-mode
> removal)**.

## Goal

Make the project bibliography (`papers/references.bib`) the **identity authority**
for `paper:<citekey>`, so the aggregate manifest's **bibliographic deprecated-owner
rows** (the `external-ref` triage bucket — `paper`/`article` kinds, ≈93 rows in
MM30) can be **retired without losing graph connectivity**. After 4b a cited paper
is an *external reference* — a referenced graph node backed by the bib, with **no
authored entity file and no owner declaration** — and the redundant aggregate stub
rows are dropped.

This is also the activation of `ParticipationMode.EXTERNAL_REFERENCE`, which is
defined (`identity_table.py:24`) but, before 4b, **never emitted or consumed** by
any adapter or resolver.

## Scope decisions (locked during brainstorming)

- **`references.bib` is a project-local citation authority, not the bio identity
  pillar.** §D4 defers *ontology* authority-registry resolution (HGNC/MONDO/…)
  behind the bio identity pillar. The project bibliography is a different class:
  local citation infrastructure already used in practice (the `cite:` helpers in
  `bibliography.py`, the `external_prefixes` machinery). Building a local
  bibliography resolver now is **in scope and unblocked**. Ontology/vocabulary
  refs (the `protein:`/`gene:`/`disease:` rows in the *ambiguous* bucket) remain
  4c / bio-pillar work.
- **Lightweight reference nodes, not owned entities.** "External reference" means
  *not project-owned and not authored as an entity file* — **not** "absent from the
  RDF graph." If `paper:X` is cited by project claims/evidence, the graph keeps a
  real target node so citation/evidence edges stay inspectable. The node carries a
  **small metadata surface** (citekey, title, year/date, doi/url when present),
  typed by its kind-class **and `prov:Entity`** as a lightweight reference/provenance
  node, never as an owned markdown entity. (Chosen
  over resolution-only, which would retire substrate debt by deleting graph
  connectivity, and over id-only nodes, which throw away cheap, useful metadata the
  resolver already has in hand.)
- **`doc/papers/*.md` are NOT adopted as owners.** Those stay summaries / notes /
  derived views. Making them identity owners would turn external literature into
  project-owned entities and explode the substrate in exactly the way §B2 forbids.
- **Scope = `paper:` / `article:` only.** `article:<X>` already canonicalizes to
  `paper:<X>` at load (`literature_prefix.canonical_paper_id`, applied in
  `sources.py:_enrich_raw`), so both fold to the same citekey. The ≈37 `doi:` rows
  (kind `article`, whose id is a DOI, not a bib citekey) do **not** match a bib key
  and are **rejected/retained** with reason `"missing bibliography authority"` —
  surfaced for a later call (4c, or add bib entries), never silently dropped and
  never special-cased in 4b.
- **All bib keys are the authority; retirement touches only the 93.** The resolver
  loads every entry in `references.bib` (≈510 in MM30) as available external
  references; retirement deletes only the aggregate rows whose citekey the bib
  backs. The bib is the source of truth, not the aggregate.
- **`cite:<key>` is left unchanged.** It is already recognized as a bibliography
  reference everywhere (`is_bibliography_reference`, consumed in
  `materialize`/`migrate`/`health`). 4b does **not** force-migrate prose
  `paper:`→`cite:`; the converged convention (both `paper:` and `cite:` ultimately
  back to `references.bib`) is noted as future cleanup, not 4b work.
- **Local bib outranks a commons paper owner (for materialization).** The commons
  referenced-entity loader treats any id present in the load's `identity_table` as
  "locally present" and does not re-materialize a commons twin
  (`commons_sources.py:90`). Because a bib `paper:X` is in that table, a commons-owned
  `paper:X` of the same id is **not** re-materialized — the **project-local bib node
  wins**, while the commons owner row is still recorded for resolution/ambiguity
(recorded whenever the id is *referenced* by the project — the commons owner row
rides `collect_referenced_commons_ids`; an unreferenced commons twin that the bib
also lists records no commons owner row, but nothing cites it, so there is no
ambiguity to surface)
  (§B3a). This is the intended precedence (a project's own bibliography is its
  citation authority) and matches existing behavior; 4b states and tests it rather
  than re-plumbing the commons seam in a bibliography phase. Making commons-owned
  papers win is deferred (no MM30 commons papers today).
- **Tooling now, live migration later.** As in 3b/3c/4a, the retirement `--apply`
  stays **v3-gated**; 4b never mutates v2 MM30's manifest. But the **BibAdapter is
  live in v2 immediately** — MM30 gets bib-backed paper nodes and resolution as
  soon as 4b lands; only the aggregate-row deletion waits for project Task #30.

## The insight that keeps this small

A referenced id becomes an RDF node **only if it is in `sources.entities`**
(`materialize.py:_build_dataset_from_sources` builds `entity_index` from
`sources.entities`; a ref that resolves to an id absent from that index produces no
node and no edge). So instead of building a *parallel* external-reference
resolution path (a second index the `ReferenceResolver` must consult), 4b
**synthesizes lightweight `paper:<citekey>` `Entity` objects in memory from the
bib** and tags them `external-reference`. That single move gives all three
properties at once:

1. **Citations resolve for free** — the synthesized entities enter the normal
   alias/slug index, so `paper:X` (and canonicalized `article:X`) resolve like any
   loaded entity. No new branch in `ReferenceResolver`.
2. **The graph keeps a node per cited paper** — `materialize` emits a node for
   every `sources.entities` member.
3. **The migrator/conformance ignore them** — their identity rows are
   `participation_mode = external-reference`, not `owner`, so `IdentityTable.owners()`
   skips them: never renumbered, never a collision, no owner-file expectation. This
   is exactly §B1's external-reference mode ("a referenced node, no local
   declaration, never renumbered").

The entities are **synthesized at load, never written to disk** — that is the line
between this and "promote papers to owned files" (which §B2 forbids and the user
rejected).

## Why this is more than a constant change (where the work is)

Unlike 4a (mostly "widen a firewall"), 4b lights up a dormant arm:

1. **The load loop hardcodes `participation_mode = OWNER`.** Every adapter in the
   main loop (`sources.py:310–461`) emits an owner `IdentityDeclaration`; the only
   non-owner rows today (commons overlays → `borrower`) are emitted in a *separate*
   flow (`sources.py:569–577`), not via the loop. To make `BibAdapter` emit
   `external-reference`, the loop must honor a **per-adapter participation mode**.
2. **`classify_owner_scope` keys on adapter name.** It returns `(owner_scope,
   deprecated)` from `adapter.name`; it needs a `bib` case (`owner_scope = "bib"`,
   `deprecated = False`).
3. **`bibliography.py` parses keys + author surnames, not full entries — and its
   key reader (`load_bib_keys`) is regex-only, so it returns a key even from an
   unbalanced entry.** 4b needs a `load_bib_entries` that (a) admits only
   `_entry_span`-balanced entries (so its key set ⟺ node-producing entries — the
   retirement gate) and (b) extracts `title`/`year`/`doi`/`url` with a brace-depth
   field scanner so nested-brace titles (`{The {DNA} story}`) don't truncate.
4. **The retirement executor has no external-ref action.** The 3a classifier
   already buckets these rows `external-ref` (no firewall there); the executor
   (`aggregate_retire.py`) only knows `coined`/`cruft`/`shadow`/`decision`. It needs
   an `external-ref` bucket action: **bib-backed → drop the aggregate row;
   un-backed → reject/retain**.

## Architecture

```
bibliography.py
  load_bib_keys(root) -> set[str]                    (exists)
  load_bib_entries(root) -> dict[citekey, BibEntry]  (NEW: title/year/doi/url)
        │ used by
        ▼
graph/storage_adapters/bib.py            (NEW)
  class BibAdapter(StorageAdapter)
    name = "bib"
    participation_mode = EXTERNAL_REFERENCE
    discover()  -> one SourceRef per bib entry (path=papers/references.bib, line=i)
    load_raw()  -> {kind: "paper", id: "paper:<citekey>", title, year?, doi?, url?}
        │ registered in
        ▼
graph/sources.py
  adapters list:           + BibAdapter()
  load loop (310–461):     emit IdentityDeclaration(participation_mode =
                             adapter.participation_mode)  [was: hardcoded OWNER]
                           + BibAdapter defer guard (mirrors §B4 datapackage:124)
        │ feeds (external-reference rows are skipped by owners(); entities enter the index)
        ▼
graph/identity_table.py
  classify_owner_scope:    + "bib" -> ("bib", deprecated=False)   [defined here, :97]
  (owners()/collisions()/owner_scopes_by_id() unchanged — external-reference
   already excluded from all three)
graph/reference_resolution.py  (unchanged — resolves via synthesized entity presence)
        │
        ▼
graph/materialize.py
  minimal reference-node branch for kind=="paper" entities (adds to the shared
  node, which already has its kind-class rdf:type + skos:prefLabel=title):
    +rdf:type prov:Entity; year->dcterms:date, doi->sci:doi, url->dcat:downloadURL
        │
        ▼
graph/aggregate_retire.py
  new external-ref bucket action (flag: --retire-external-refs):
    citekey ∈ set(load_bib_entries)  -> drop aggregate row   (node-producing authority)
    citekey ∉ set(load_bib_entries)  -> rejected "missing bibliography authority", retained
  --apply stays v3-gated; planner join already (path,line)-keyed (4a)
cli.py
  entities triage-aggregate --retire-external-refs   (parallels --promote-coined)
```

### Component 1 — bib entry reader (`bibliography.py`)

Add a frozen `BibEntry` dataclass (`key`, `title`, `year`, `doi`, `url`; all but
`key` optional) and `load_bib_entries(project_root) -> dict[str, BibEntry]`.

- **Balanced-entry gate (fixes the regex-key trap).** The existing `load_bib_keys`
  is **regex-only** (`_BIBTEX_ENTRY_RE = @\w+\s*\{\s*([^,\s]+)\s*,`): it returns a
  key from the header even when the entry's body braces never balance. So a
  truncated/unbalanced entry yields a key. `load_bib_entries` instead admits an
  entry **only when `_entry_span` balances** (the same whole-entry brace matcher
  `add_bib_entry` uses), so its key set is exactly the set of entries that produce a
  real `BibEntry`. This makes "**backed**" mean "**a replacement external-reference
  node exists**" — the invariant retirement relies on (see Component 5). A
  key whose block is unbalanced is **excluded** from `load_bib_entries`, so any
  aggregate row for it stays **un-backed/retained**, never dropped.
- **Schema-loadability (the other half of "backed ⟺ node").** Brace-balance is
  necessary but not sufficient: the synthesized `PaperEntity` must also pass
  validation or `load_project_sources` skips it (`sources.py:355`) and no node is
  produced. The only constrained field is `year` (`PaperEntity.year` is
  `ge=1800, le=2200`). So `load_bib_entries` **clamps `year` to `None` unless it is a
  4-digit integer in `[1800, 2200]`** — parsed metadata can never make the entity
  fail validation, so a returned key always yields a node. (The entry is still
  admitted; only the out-of-range year is dropped. All other parsed fields are
  unconstrained strings.) Retirement therefore keys off `set(load_bib_entries(root))`
  and "backed" is exactly "node-producing".
- **Balanced field-value extraction (fixes nested-brace truncation).** Field values
  themselves can nest braces — `title = {The {DNA} story}`. A naive
  `field\s*=\s*\{([^}]*)\}` regex truncates at the inner `}`. So field extraction
  uses a **small brace-depth scanner** (the same depth-counting loop as `_entry_span`,
  applied within the entry span): locate `field = {`, then consume to the
  **matching** close brace by depth. Quoted form (`field = "…"`) and bare numeric
  form (`year = 2024`) are handled too. A missing field → `None` (lenient).
- `load_bib_keys` stays for its existing callers (the cheap lint path); it is **not**
  the retirement gate — retirement uses `set(load_bib_entries(root))` so backed
  ⟺ node-producing.

### Component 2 — `BibAdapter` (`graph/storage_adapters/bib.py`)

A `StorageAdapter` subclass: `name = "bib"`; class attribute
`participation_mode = ParticipationMode.EXTERNAL_REFERENCE`. `discover` returns one
`SourceRef(adapter_name="bib", path="papers/references.bib", line=i)` per entry
(stable order = bib file order). `load_raw` returns
`{"kind": "paper", "id": f"paper:{key}", "title": entry.title or key, ...optional
metadata}`. No `dump` (read-only authority). Absent bib → `discover` returns `[]`
(no-op; lenient on absence, the established framework pattern).

### Component 3 — participation mode in the load loop (`graph/sources.py`)

- Add a default `participation_mode: ParticipationMode = ParticipationMode.OWNER`
  to the `StorageAdapter` base (`base.py`), overridden by `BibAdapter`.
- In the loop's `IdentityDeclaration(...)` emit, replace the hardcoded
  `ParticipationMode.OWNER` with `adapter.participation_mode`. Behavior-preserving
  for every existing adapter (all default `OWNER`).
- `classify_owner_scope` (**defined in `identity_table.py:97`**, called from the
  `sources.py` loop): add the `"bib" -> ("bib", False)` case. External-reference
  rows carry an `owner_scope` naming the authority (`"bib"`), matching §B3 ("where
  the owner declaration lives" — here, the external authority).
- Register `BibAdapter()` in the `adapters` list, **after `AggregateAdapter`**.
- **Defer guard (load-bearing — mirrors the §B4 datapackage defer at
  `sources.py:414`).** The loop's id-dedup raises `EntityIdentityCollisionError`
  under **strict** load on *any* second declaration of a canonical id — it keys on
  the loop-local `identity_table` dict (id → ref), **before** any participation-mode
  grading. So a transitional `paper:X` (aggregate deprecated-owner) **plus** a bib
  `paper:X` would crash strict load. The fix is the same defer the datapackage uses:
  ```python
  if isinstance(adapter, BibAdapter) and entity.canonical_id in identity_table:
      continue  # already declared this load (real owner OR aggregate stub) — bib defers
  ```
  Consequences, all intended:
  - While an aggregate stub for `paper:X` still exists, the **bib defers** — no
    second row, no duplicate entity, no collision. `paper:X` stays a
    deprecated-owner (the aggregate), and the existing stub node carries citations.
  - When 4b's retirement **drops that aggregate row**, the *next load* finds
    `paper:X` undeclared when the bib adapter runs, so the bib emits the
    `external-reference` row + the metadata-bearing entity. **The participation mode
    flips owner→external-reference automatically at retirement** — exactly the §B5
    transition, no extra step.
  - A bib paper with **no** aggregate row and **no** markdown owner (the common
    cited-but-unstubbed case, and the ≈510−93 uncited keys) is undeclared when the
    bib runs → emitted directly as an external reference.
- **Synthesize for all bib keys** (the authority must know every key so retirement's
  backed/un-backed test and any citation resolve). Uncited keys become isolated
  reference nodes — acceptable for a bibliography; gating materialization on
  citation is noted as a future optimization, not 4b work.

### Component 4 — minimal reference node (`graph/materialize.py`)

`_add_entity` (`materialize.py:236`) receives only the `Entity`, **not** its
participation mode, and owned/commons paper entities are *also* `kind == "paper"`.
Rather than thread an `external_reference_ids`/adapter map into the materializer,
the metadata branch keys on **`kind == "paper"`** and applies to **all** paper
entities. The shared `_add_entity` path already emits the node's `rdf:type`
(its kind-class) and `skos:prefLabel = title`; the branch **adds**, only when
present on the entity:

- `year` → `dcterms:date`
- `doi`  → `sci:doi`
- `url`  → `dcat:downloadURL`

plus `rdf:type prov:Entity` (marking it a reference/provenance node, per the
brainstorm's "external/reference/provenance entities"). It is additive (adds
triples, removes none), so it is harmless on the rare owned/commons paper entity
(which simply may lack year/doi/url) and is the whole metadata surface for a
bib-synthesized one. The node therefore carries both its kind-class type and
`prov:Entity`. Deliberately a thin surface — not
full bibliographic modeling — sufficient for citation/evidence edges to land on an
inspectable, metadata-bearing node. Citation edges (`source_refs`/`evidence_refs →
paper:X`) already materialize when the target is in `entity_index`; synthesizing the
bib entities puts them there.

### Component 5 — external-ref retirement action (`graph/aggregate_retire.py`)

Mirror the 3b/4a bucket-dispatch shape. Under a new flag (plan: `--retire-external-refs`):

- For each `EXTERNAL_REF`-bucket triage row: compute its citekey from the canonical
  id (`paper:<citekey>` after the load-time `article:`→`paper:` canonicalization),
  test membership in **`set(load_bib_entries(project_root))`** — the **parseable**
  (balanced) entry set, **not** `load_bib_keys` (which would count a truncated entry
  the BibAdapter actually skipped, dropping a row with no replacement node).
- **Backed (citekey ∈ parseable bib entries):** a replacement external-reference
  node provably exists, so the aggregate row is a redundant deprecated-owner stub —
  **drop it** (the index-set rewrite path 3b/4a already use; reason `"external-ref
  backed by bibliography"`). No owner file written.
- **Un-backed (citekey ∉ parseable bib entries):** **reject + retain**, reason
  `"missing bibliography authority"`. Captures the `doi:` rows, any orphaned
  `paper:`/`article:` ids, **and** ids whose bib block is unbalanced/truncated —
  surfaced in the report for a human call, never silently removed.
- The `--apply` v3 gate, the dry-run default, and the `(path, line)` triage join
  (4a) are all unchanged. `--retire-external-refs` composes with
  `--promote-coined`/`--delete-cruft`/etc. in a single pass.

### Component 6 — CLI (`cli.py`)

Add `--retire-external-refs` to `entities triage-aggregate`, parallel to the
existing bucket flags, gated identically. Bare command behavior (3a report)
unchanged.

## Behavior preserved

- Every existing adapter still emits `owner` rows (default participation mode).
- `IdentityTable` (owners/collisions/scopes) is untouched — external-reference was
  already excluded from all three.
- `ReferenceResolver` is untouched — resolution rides on synthesized entity
  presence, not a new index.
- The v3 `--apply` gate, decision interception (3c), coined promotion (3b/4a),
  and the `(path, line)` join are unchanged.
- `cite:<key>` handling and the `_EXTERNAL_PREFIXES` ontology set are unchanged.

## Error handling

- **Absent `references.bib`** → `BibAdapter.discover` returns `[]`; no external
  references, no nodes, retirement leaves all external-ref rows un-backed
  (rejected/retained). Lenient on absence (framework convention).
- **Malformed bib entry** (unbalanced braces → `_entry_span` yields `None`) → that
  entry is skipped at parse; a key with no parseable block contributes no external
  reference (so any aggregate row for it stays un-backed/retained). Fail-early on a
  *declared-but-truncated* entry is the existing `add_bib_entry` contract; the
  reader is lenient (skip) since it only needs the well-formed subset.
- **`doi:` and other non-citekey ids** → un-backed → rejected/retained with a clear
  reason; never mis-promoted, never deleted.
- **Transitional id coexistence** (aggregate stub + bib entry for the same id) →
  the bib adapter **defers** (no second declaration, no duplicate entity), so strict
  load raises nothing; the stub remains the owner until 4b retires it, at which
  point the next load promotes the id to an external reference.

## Testing (TDD; 3b/3c/4a fixture style — `profiles: {local: local}` + local `manifest.yaml`)

1. **`load_bib_entries` parses fields + gates on balance.** A `references.bib` with
   title/year/doi → `BibEntry` carries them; an entry missing a field → that field
   `None`; a title with nested braces (`{The {DNA} story}`) is **not** truncated; an
   entry with **unbalanced** braces is **excluded** from the returned dict (so its
   key is absent — it cannot be "backed"), while well-formed sibling entries still
   load.
2. **`BibAdapter` discovers + loads.** N entries → N `SourceRef`s with stable
   line order; `load_raw` yields `kind="paper"`, `id="paper:<key>"`, title.
   Absent bib → `[]`.
3. **External-reference identity row + defer.** With no competing declaration,
   `paper:<key>` gets an identity row with `participation_mode == external-reference`,
   `owner_scope == "bib"`, **absent** from `IdentityTable.owners()`. With a same-id
   aggregate deprecated-owner stub also present, the bib **defers**: strict load
   raises no collision, and the id is owned by the (single) aggregate row — no second
   declaration is emitted.
4. **Citation resolves; node + edge materialize.** A fixture interpretation with
   `source_refs: [paper:<key>]` → the ref resolves; the graph has a `paper:<key>`
   node typed `prov:Entity` and carrying `skos:prefLabel` (title) + `dcterms:date`/`sci:doi`, plus the citation edge.
5. **Participation-mode default preserved.** Every non-bib adapter still emits
   `owner` rows (regression: an existing markdown/aggregate fixture is unchanged).
6. **Retire backed row.** An aggregate `paper:<key>` (or `article:<key>`) row whose
   key is in the bib → dropped from the aggregate manifest under
   `--retire-external-refs`; no owner file written; the citation still resolves
   (via the bib entity).
7. **Retain un-backed row.** An aggregate `paper:<key>`/`doi:<x>` row whose key is
   **not** in `load_bib_entries` → `rejected` with `"missing bibliography
   authority"`, row survives the rewrite. Includes the **unbalanced-entry** case: a
   `paper:<key>` whose bib block is truncated is un-backed (no replacement node), so
   its aggregate row is **retained**, never dropped.
8. **`article:` folds to the citekey.** An `article:<key>` aggregate row with
   `<key>` in the bib retires (canonicalization makes it `paper:<key>`).
9. **Flag composition + v3 gate.** `--retire-external-refs` composes with
   `--promote-coined` in one pass; `--apply` on a v2 fixture is refused (exit 1);
   the bare command still emits the unchanged 3a report.

## MM30 smoke (still v2)

- **Live in v2 — only *undeclared* bib keys synthesize immediately.** Because the
  BibAdapter **defers** to any prior declaration this load, the ≈93 paper/article
  ids that still have an aggregate stub **stay aggregate-owned** (the stub node and
  its citation edges are unchanged) until the v3-gated retirement removes the stub.
  The bib keys with **no** prior declaration (no aggregate stub, no markdown owner)
  synthesize as external references right away — so any **previously-unresolved**
  bib-backed citation (a `paper:X` cited in prose but never stubbed) **now resolves**
  on v2. That newly-resolving set is the immediate v2 win, not a 510-node flip.
- **Retirement dry-run** lists the bib-backed `external-ref` stub rows as droppable
  and the `doi:`/unbalanced/un-backed ones as `rejected "missing bibliography
  authority"`.
- **`--apply` refused, exit 1** (v3 gate names `layout_version 2`); MM30 git-clean.
  (On the eventual v3 `--apply`, each dropped stub becomes an external reference on
  the *next* load, completing the owner→external-reference flip.)

## Out of scope (later phases / future cleanup)

- **Ambiguous-bucket adjudication** (`protein:`/`gene:`/`disease:`/`topic:`/… —
  96 rows) and **`AggregateAdapter` deprecated-owner-mode removal** → **4c**
  (removal stays blocked until external-ref *and* ambiguous rows clear).
- **Ontology authority-registry resolution** (HGNC/MONDO/…) → bio identity pillar
  (§D4); 4b's local-bibliography authority is explicitly *not* that.
- **`paper:` ⇄ `cite:` convention convergence** (force-migrating prose refs to a
  single bibliographic form) → future cleanup, not 4b.
- **Rich bibliographic modeling** (authors as nodes, venue, full CSL) → not needed
  for citation connectivity; the node metadata surface stays minimal.
- **`doi:` row resolution** (minting bib entries from DOIs, or a DOI authority) →
  deferred; 4b only rejects/retains them visibly.
