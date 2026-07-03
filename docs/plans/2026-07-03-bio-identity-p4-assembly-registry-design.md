# Bio Identity P4.1 Assembly Registry - Design

- **Status:** Draft for review
- **Date:** 2026-07-03
- **Scope:** P4.1 of the bio identity adoption umbrella: finish the `dataset:assembly-registry` build artifact and prove Science resolves `hg38` / `hg19` against that artifact offline.
- **Umbrella:** `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`
- **Depends on:** P1-P3 identity resolver and datapackage resource resolver merged to `main`.

## Purpose

P4.1 turns assembly resolution from a fixture/mock behavior into a normal offline workflow step. After this slice, `science dataset identity resolve --assembly hg38` can resolve through the pinned `science-commons` `dataset:assembly-registry` artifact, not through a monkeypatch or an example-only fixture.

The invariant is unchanged from Pillar C: the assembly identity key is the GA4GH seqcol digest. Labels such as `hg38`, `GRCh38`, `hg19`, and `GRCh37` are authoring aliases only.

## Current State

Science already has most of the framework surface:

- `science_tool.commons.assembly` reads `dataset:assembly-registry` resource `assemblies.csv`, verifies the datapackage hash through `commons.resolver.resolve`, and resolves either exact `seqcol_digest` or unique `label`.
- `science_tool.commons.identity_resolve` calls that resolver and degrades to `declared_unresolved` when the registry is absent or invalid.
- `science_tool.commons.assembly_registry_build` has pure helpers for computing seqcol digests from level-2 records and writing assembly/contig rows.
- `science_tool.commons.assembly_report_build` has pure helpers for converting NCBI assembly reports into contig aliases.
- Tests cover the pure builder helpers and fixture-based resolver reads.

`~/d/science-commons` already has `datasets/assembly-registry/` with `entity.md`, `datapackage.yaml`, and `recipe/build.py`, but the recipe is not finished as a pinned artifact: `recipe/sources.yaml` still has placeholders, `datapackage.yaml` has zero hashes/bytes, and `entity.md` says `assembly_count: 0`.

## Decision

Use the existing `science-commons/datasets/assembly-registry` dataset as the authoritative artifact home. P4.1 finishes that recipe and adds a Science integration fixture that exercises the actual resolver path over the built artifact shape.

The built artifact contract is:

- `assemblies.csv`: required for assembly identity resolution.
  Columns: `seqcol_digest,label,accession,n_sequences,source_url`.
- `contigs.csv`: required for contig/variant support already built in C4a.
  Columns: `seqcol_digest,sequence_index,name,refget_digest,length`.
- `contig_aliases.csv`: required for accession/UCSC alias lookup already built in C4a.
  Columns: `seqcol_digest,refget_digest,alias,alias_kind,sequence_accession`.

The Science resolver contract remains intentionally narrow: assembly identity resolution consumes only `assemblies.csv`. Contig and variant helpers consume `contigs.csv` and `contig_aliases.csv` through their existing modules. P4.1 does not introduce a new registry format or a new aggregate manifest.

## Minimum Assembly Set

P4.1 must build the human assemblies MM30 needs first:

- GRCh38 / hg38.
- GRCh37 / hg19.

The recipe may include aliases in metadata or tests, but the CSV contract has only one canonical `label` column today. To avoid widening the resolver contract prematurely, P4.1 makes Science accept the two common labels MM30 authors will use through this explicit rule:

- keeping `assemblies.csv` one row per seqcol digest with canonical labels `GRCh38` and `GRCh37`;
- adding a small explicit authoring alias map in `science_tool.commons.assembly` so `hg38` resolves as `GRCh38` and `hg19` resolves as `GRCh37` before lookup.

This alias map is deliberately not a synonym table for identity. It is an authoring convenience over labels only; exact `seqcol_digest` equality remains the identity rule, and no alias may point at more than one digest.

## Build Boundary

The recipe is operator-run and may use the network at build time. Runtime resolution and validation must remain fully offline.

Build-time inputs:

- pinned seqcol collection digests in `recipe/sources.yaml`;
- pinned assembly report URLs for those same assemblies;
- the seqcol server level-2 records fetched by digest;
- NCBI assembly report text fetched from the pinned URLs.

Build-time checks:

- recompute the seqcol digest from level-2 `names` + `sequences`;
- fail if the recomputed digest differs from the pinned digest;
- fail on ragged level-2 records, duplicate contig names, blank fields, invalid lengths, or unmatched assembly-report rows;
- write stable CSVs with fixed columns and deterministic row order;
- update datapackage resource `hash` and `bytes`;
- update `entity.md` `assembly_count`.

Runtime checks:

- `commons.resolver.resolve` verifies resource SHA-256 before any resolver reads bytes;
- `load_assembly_registry` fails on missing/blank/duplicate `seqcol_digest`;
- `resolve_identity` catches registry unavailability and degrades to `declared_unresolved` with a warning;
- no runtime resolver path may fetch from the network.

## Alternatives Considered

### A. Finish the existing commons dataset and keep Science's read contract

Chosen. This is the least disruptive path: the artifact home already exists, Science already reads the expected resource names, and C4a contig support already expects the same dataset to carry contig resources.

### B. Create a new generated registry artifact outside `science-commons`

Rejected. A side artifact would bypass the commons dataset lifecycle, duplicate checksum/provenance machinery, and leave downstream workflows with two places to look for the same identity authority.

### C. Add a richer JSON manifest as the resolver source

Rejected for P4.1. The current CSV resources already match the resolver and contig helper contracts. A JSON manifest would only be useful if P4.2/P4.3 reveal a cross-artifact registry need; adding it now would expand the public surface without a consumer.

## Cross-Repo Ownership

`~/d/science-commons` owns the built bytes and the recipe:

- `datasets/assembly-registry/recipe/sources.yaml`
- `datasets/assembly-registry/recipe/build.py`
- `datasets/assembly-registry/assemblies.csv`
- `datasets/assembly-registry/contigs.csv`
- `datasets/assembly-registry/contig_aliases.csv`
- `datasets/assembly-registry/datapackage.yaml`
- `datasets/assembly-registry/entity.md`

`~/d/science` owns the reader contract, CLI behavior, and integration fixture:

- `science/src/science_tool/commons/assembly.py`
- `science/src/science_tool/commons/identity_resolve.py`
- `science/tests/test_commons_assembly.py`
- `science/tests/test_identity_resolve.py`
- any focused fixture needed to exercise the built commons artifact without committing large generated data into Science.

If the implementation requires a `science-commons` worktree, create it under `~/d/science-commons/.worktrees/` and keep commits split by repo.

## Integration Fixture

P4.1 needs one resolver integration test that is stronger than the current monkeypatch tests:

1. Use a real commons-style entity + datapackage + data-root layout.
2. Include `assemblies.csv` with the real GRCh38 and GRCh37 seqcol digests from the built artifact contract.
3. Verify `resolve_assembly_label("hg38" or "GRCh38", dataset:assembly-registry)` returns the GRCh38 seqcol digest.
4. Verify `resolve_identity({"taxon": 9606, "assembly": {"label": "hg38", "registry": "dataset:assembly-registry"}})` produces `resolution_status: resolved`.
5. Monkeypatch sockets or use the existing no-network test pattern to prove runtime resolution does not use the network.

The fixture should be small. It proves the resolver consumes the on-disk contract; it does not need to duplicate the full real contig tables in Science.

## Error Handling

Builder errors should fail early with the source label or digest in the message. Bad pins, digest mismatches, bad level-2 structure, broken assembly reports, and stale datapackage hashes are operator errors.

Resolver errors should preserve the P1-P3 behavior: unavailable or invalid commons artifacts produce warnings and `declared_unresolved` during authoring, but validation/publish policies may later reject unresolved identity when resolution is required.

## Non-Goals

- No gene crosswalk work; that is P4.2.
- No liftover-chain integration; that is P4.3.
- No cytoband proxy dataset decision; that is P4.4.
- No new identity model, no synonym table that treats labels as identity, and no live runtime refget fallback.
- No broad population of non-human assemblies unless it is nearly free and does not delay GRCh38/GRCh37.

## Acceptance Criteria

- `~/d/science-commons/datasets/assembly-registry/recipe/sources.yaml` has real pinned GRCh38 and GRCh37 inputs, not placeholders.
- Running the recipe produces `assemblies.csv`, `contigs.csv`, and `contig_aliases.csv` with deterministic content.
- `datapackage.yaml` resource hashes and byte counts match the generated files.
- `entity.md` reports the correct `assembly_count`.
- Science has an integration test proving assembly identity resolution reads the commons-style artifact from disk and resolves GRCh38/hg38 and GRCh37/hg19 as intended.
- Runtime identity resolution remains offline and continues to degrade to `declared_unresolved` when the artifact is missing.
- The umbrella doc is updated when P4.1 lands to record the settled artifact shape.
