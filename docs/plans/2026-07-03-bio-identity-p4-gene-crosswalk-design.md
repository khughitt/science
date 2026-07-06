# Bio Identity P4.2 Gene Crosswalk - Design

- **Status:** Draft for review
- **Date:** 2026-07-03
- **Scope:** P4.2 of the bio identity adoption umbrella: harden `dataset:gene-crosswalk-hgnc` as a pinned, offline HGNC gene crosswalk artifact and prove Science resolves gene namespaces against built-artifact bytes.
- **Umbrella:** `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`
- **Depends on:** P1-P3 identity resolver and P4.1 assembly-registry artifact pattern merged to `main`.

## Purpose

P4.2 makes human gene identity resolution a normal offline workflow step for MM30's symbol-space remaps. After this slice, `science dataset identity resolve` can mark `molecular_ids.gene` declarations resolved when `namespace: hgnc_id`, `hgnc_symbol`, `entrez`, or `ensembl` points at the pinned `science-commons` `dataset:gene-crosswalk-hgnc` artifact, and workflow contracts can cite that same artifact for `symbol_remap` / `namespace_map` provenance.

The invariant is unchanged from Pillar C: the canonical human gene identity key is the species-aware opaque key `9606|hgnc|HGNC:n`. HGNC symbols, previous symbols, alias symbols, Entrez ids, and Ensembl gene ids are accepted lookup namespaces; they are not identity. Ambiguous lookups remain ambiguous and never collapse to a guessed gene.

## Current State

Science already has the framework and resolver surface:

- `science_tool.commons.gene_crosswalk` reads `dataset:gene-crosswalk-hgnc` resource `crosswalk.csv`, verifies the datapackage hash through `commons.resolver.resolve`, and resolves `hgnc_id`, `hgnc_symbol`, `entrez`, and `ensembl` inputs to `ResolvedGeneMatch | AmbiguousGeneMatch | None`.
- `science_tool.commons.gene_crosswalk_build` has pure parsing helpers for HGNC complete-set and withdrawn release files.
- `science_tool.commons.identity_resolve` validates gene namespace declarations and registry/tier alignment, then marks the tier resolved only when explicit registry availability metadata says the gene crosswalk is available.
- Tests cover resolver semantics and builder parsing over small fixtures.

`~/d/science-commons/datasets/gene-crosswalk-hgnc/` already has real 2025-04-01 HGNC-derived bytes:

- `crosswalk.csv` has `49,359` data rows.
- `datapackage.yaml` resource `hash` and `bytes` match the current file.
- `entity.md` reports `gene_count: 49359`.
- `recipe/build.py` fetches pinned HGNC complete-set and withdrawn URLs and writes `crosswalk.csv`.

The gap is not model design or first-byte population. The gap is the P4.1-level adoption hardening: the recipe does not yet enforce the resolver contract end-to-end, update metadata deterministically, or produce a Science fixture proving runtime gene resolution against built-artifact shape rather than toy-only rows.

## Decision

Finish the existing `science-commons/datasets/gene-crosswalk-hgnc` dataset as the authoritative artifact home. Keep the current CSV contract for v1 and harden the build/read path around it.

The built artifact contract remains:

- `crosswalk.csv`: required for human gene identity resolution.
  Columns: `gene_key,symbol,entrez_id,ensembl_gene_id,alias_symbol,prev_symbol,status,replacement_gene_keys`.

No new manifest or side index is introduced in P4.2. The Science resolver contract is intentionally narrow: identity resolution consumes `crosswalk.csv` through the existing commons datapackage resolver, and namespace declarations become resolved only through the existing `identity_resolve` registry-availability gate.

## Identity And Lookup Semantics

The canonical key is always built by `make_gene_key(9606, "HGNC:n")` and treated as opaque outside that helper. The current v1 artifact is human-only; non-human taxon requests return no match rather than parsing taxon out of `gene_key`.

Supported lookup namespaces stay exactly:

- `hgnc_id`: exact HGNC CURIE, e.g. `HGNC:5`;
- `hgnc_symbol`: current symbol first, then previous symbol, then alias symbol;
- `entrez`: Entrez Gene id from HGNC complete-set data;
- `ensembl`: Ensembl gene id from HGNC complete-set data.

Resolver behavior stays explicit:

- a unique current/previous/alias symbol resolves with `match_type`;
- a shared symbol/alias returns `AmbiguousGeneMatch` with no `gene_key`;
- `merged` rows carry one `replacement_gene_key` but do not auto-follow it;
- `split` rows return ambiguity over forward targets;
- `withdrawn` rows remain resolvable as withdrawn lifecycle records when matched directly;
- unsupported namespaces fail early at the direct resolver boundary and become `declared_unresolved` with an error through identity authoring paths.

This preserves the core identity rule: mappings are provenance-bearing relationships, not synonym assertions.

### Tier-resolution semantics differ from the assembly tier

"Resolved" does not mean the same thing for genes as it does for assemblies, and the difference is deliberate. For the assembly tier (P4.1), `resolve_identity` reads the registry bytes and mints the concrete `seqcol_digest` into `identity_context` — resolution *produces a dataset-level identity value*. For the gene tier, there is no dataset-level gene key to mint (gene identity is per-row, not per-dataset), so `resolve_namespace` marks the tier `resolved` on the basis of namespace/tier/registry alignment plus registry **availability** — it does **not** perform a per-gene lookup and does not verify that any specific gene id exists in the crosswalk. Per-gene resolution is `to_canonical`'s job and is exercised separately.

Concretely, this means a gene-tier `resolve_identity` call resolves whenever the crosswalk registry is available and the declaration is well-formed, regardless of whether the artifact actually contains a matching gene. Callers that need per-gene verification must use `to_canonical`. The integration fixture reflects this split explicitly: the `to_canonical` assertions are the byte-level proof; the `resolve_identity` assertion proves only the availability/alignment path.

## Build Boundary

The recipe is operator-run and may use the network at build time. Runtime resolution and validation remain fully offline.

Build-time inputs:

- pinned, dated HGNC complete-set TSV URL;
- pinned, dated HGNC withdrawn TSV URL;
- release date or release label recorded in `recipe/sources.yaml`;
- optional source-file hashes if HGNC provides stable checksums or if the implementation records fetched-input hashes after retrieval.

Build-time checks:

- fetch only the pinned dated URLs, not `latest` or other moving aliases;
- parse complete-set and withdrawn files through `science_tool.commons.gene_crosswalk_build`;
- write stable CSVs with fixed columns and deterministic row order;
- parse the generated rows through `science_tool.commons.gene_crosswalk._parse_crosswalk_rows`;
- fail on blank or duplicate `gene_key`;
- fail on invalid lifecycle status;
- fail on `merged` rows without exactly one replacement and `split` rows without at least two replacements;
- fail if replacement keys point at missing rows, unless the source row is classified as `withdrawn` with no replacement;
- update datapackage resource `hash` and `bytes`;
- update `entity.md` `gene_count`, `updated:`, and `version:` when bytes change.

Runtime checks:

- `commons.resolver.resolve` verifies resource SHA-256 before any resolver reads bytes;
- `load_gene_crosswalk` fails on malformed rows;
- `to_canonical` returns explicit match objects or `None`; it does not fetch network data;
- `resolve_identity` preserves P1-P3 authoring behavior: unavailable or invalid registries degrade to `declared_unresolved` with messages unless a later publish/promote policy requires full resolution.

## Reconciling The Existing Artifact

Unlike P4.1 — where the artifact was a stub (`assembly_count: 0`) built greenfield — the gene crosswalk already ships real, hash-pinned bytes (49,359 rows from the 2025-04-01 HGNC release). P4.2 adds build-time contract validation *and* deterministic row ordering to a recipe whose output already exists, so hardening is not purely additive. Two conflicts must be resolved before P4.2 can claim a reproducible artifact, and neither may be left implicit:

1. **The shipped bytes may fail the new validator.** They predate these checks, so a `merged` row without exactly one replacement, a `split` without at least two, a replacement key pointing outside the row set, or a duplicate/blank `gene_key` would surface now as a *pre-existing data defect to fix*, not a clean pass. The implementation must run the hardened validator against the **current** `crosswalk.csv` as its first step and reconcile every failure explicitly (fix the source-parse, or record why the row is legitimate) before regenerating anything.

2. **Re-running may not reproduce the shipped bytes.** If the hardened recipe's deterministic sort differs from the current file's row order, the rebuild changes the resource hash. The plan must decide up front, not discover mid-run, which of these it is:
   - **Prove-identical:** if the current bytes already match the hardened output byte-for-byte, assert that (recompute hash, confirm no diff) and touch no data.
   - **Regenerate-and-accept:** if they differ, treat the regenerated bytes as the new pinned artifact — update `datapackage.yaml` hash/bytes, bump `entity.md` `gene_count`/`updated`/`version`, re-sync the Science fixture from the new bytes, and commit the data change deliberately (not as incidental churn).

The definition-of-done phrase "running the recipe produces deterministic `crosswalk.csv` content" means *stable across runs*, and — via one of the two paths above — reconciled with what is committed. It does not silently assume the current bytes are already conformant.

## Alternatives Considered

### A. Harden the existing HGNC artifact and fixture-test it

Chosen. This is the smallest slice that makes MM30's gene-tier identity useful offline. The artifact home, CSV resource, resolver, pure build helpers, and real built bytes already exist. P4.2 should bring them up to the P4.1 standard rather than redesign the crosswalk.

### B. Merge HGNC with NCBI and Ensembl source files now

Rejected for P4.2. It may eventually improve coverage and auditability for Entrez/Ensembl mappings, but it expands the slice into source-conflict policy: which source wins when HGNC, NCBI, and Ensembl disagree; how release dates align; and how to represent multiple mappings per gene. MM30's immediate need is reproducible HGNC-symbol remap over the already-populated human artifact.

### C. Treat the current commons bytes as complete and jump to liftover

Rejected. The bytes are real, but the build path is not yet hardened. Without recipe contract checks and a built-artifact Science fixture, the project would be relying on a one-off CSV rather than a reproducible reference dataset.

### D. Make symbols first-class identity for MM30 convenience

Rejected. Symbols are mutable, reused, previous/alias-qualified, and sometimes ambiguous. Treating symbols as identity would reproduce the silent harmonization problem this effort exists to remove.

## Cross-Repo Ownership

`~/d/science-commons` owns the built bytes and the recipe:

- `datasets/gene-crosswalk-hgnc/recipe/sources.yaml`
- `datasets/gene-crosswalk-hgnc/recipe/build.py`
- `datasets/gene-crosswalk-hgnc/crosswalk.csv`
- `datasets/gene-crosswalk-hgnc/datapackage.yaml`
- `datasets/gene-crosswalk-hgnc/entity.md`

`~/d/science` owns the reader contract, identity authoring behavior, and integration fixture:

- `science/src/science_tool/commons/gene_crosswalk.py`
- `science/src/science_tool/commons/gene_crosswalk_build.py`
- `science/src/science_tool/commons/identity_resolve.py`
- `science/tests/test_commons_gene_crosswalk.py`
- `science/tests/test_gene_crosswalk_build.py`
- `science/tests/test_identity_resolve.py`
- a focused fixture copied from the built commons artifact.

If implementation requires a `science-commons` worktree, create it under `~/d/science-commons/.worktrees/` and keep commits split by repo.

## Integration Fixture

P4.2 needs a resolver integration fixture parallel to P4.1:

1. Use a real commons-style entity + datapackage + data-root layout.
2. Copy a small, documented subset of rows from the built `crosswalk.csv`, not hand-authored toy rows.
3. Include rows that prove:
   - exact HGNC id resolution;
   - current symbol resolution;
   - previous-symbol or alias-symbol resolution;
   - an ambiguous symbol/alias that resolves to `AmbiguousGeneMatch` without collapsing (shared `alias_symbol`/`prev_symbol` collisions are ubiquitous in HGNC, so a compact example always exists — this is required, not conditional, to satisfy the non-collapsing acceptance criterion).
4. Verify `to_canonical(..., commons_root=..., data_root=...)` reads through the on-disk datapackage/hash path.
5. Verify `resolve_identity({"taxon": 9606, "molecular_ids": {"gene": ...}})` marks the tier resolved when `registries={dataset:gene-crosswalk-hgnc: {available: true, tier: gene}}`.
6. Monkeypatch sockets or reuse the existing no-network pattern to prove runtime gene resolution does not use the network.

The fixture should be small. It proves Science consumes the built contract; it does not duplicate the full 3.3 MB commons artifact.

## Error Handling

Builder errors should fail early with row number, source field, and gene key when available. Bad source URLs, malformed HGNC rows, duplicate member keys, invalid lifecycle pointers, stale datapackage hashes, and metadata mismatch are operator errors.

Resolver errors should preserve the P1-P3 behavior: unavailable or invalid commons artifacts produce messages and `declared_unresolved` during authoring, while promote/publish policies may later reject unresolved gene identity when resolution is required.

## Non-Goals

- No broad NCBI/Ensembl source merge beyond fields already present in HGNC's complete-set file.
- No live MyGene, Ensembl REST, BioMart, or NCBI runtime fallback.
- No non-human population beyond retaining the taxon-explicit API shape.
- No protein crosswalk expansion; that remains outside this MM30-critical P4.2 slice.
- No variant-label or dbSNP work.
- No MM30 retrofit work; P5 owns consumer migration after P4 artifact shapes are settled.

## Acceptance Criteria

- `~/d/science-commons/datasets/gene-crosswalk-hgnc/recipe/sources.yaml` records pinned dated HGNC inputs and release metadata.
- Running the recipe produces deterministic `crosswalk.csv` content with the declared columns.
- The recipe validates generated rows through the Science resolver parser or an equivalent shared contract check.
- Duplicate keys, invalid lifecycle status, bad merged/split replacement counts, and missing replacement targets fail the build.
- `datapackage.yaml` resource hash and byte count match the generated file.
- `entity.md` reports the correct `gene_count`, `updated:`, and `version:`.
- Science has an integration test proving gene identity resolution reads a commons-style artifact from disk and resolves HGNC id, current symbol, and previous/alias symbol through built-artifact rows.
- Science proves ambiguous symbol/alias behavior remains non-collapsing.
- Runtime gene resolution remains offline.
- The umbrella doc is updated when P4.2 lands to record the settled artifact shape and move `Next:` to P4.3.
