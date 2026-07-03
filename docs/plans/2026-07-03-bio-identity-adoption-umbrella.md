# Bio Identity Adoption - Umbrella

- **Status:** Active umbrella tracker
- **Date:** 2026-07-03
- **Scope:** Phase-level orientation for the bio identity adoption effort across `~/d/science`, `~/d/science-commons`, and MM30.
- **Detailed design:** `docs/plans/2026-07-02-bio-identity-adoption-layer-design.md`
- **Framework implementation plan:** `docs/plans/2026-07-02-bio-identity-adoption-layer-implementation-plan.md`

## End-to-end goal

MM30 can declare, resolve, propagate, stamp, validate, and use biological identity context end-to-end, with t665's TAD and A-B compartment axes unblocked by a machine-visible cross-build/proxy declaration instead of prose.

Concretely:

- every identity-bearing dataset (coordinate/gene/protein/variant profile; see the design's profile-to-tier table) has an entity-authoritative `identity_context`;
- every coordinate- or feature-emitting workflow output has an `outputs[].identity` contract;
- datapackages carry only a derived `science.identity_context` stamp;
- `science validate` catches missing declarations, entity/stamp disagreement, unmarked cross-build joins, missing transform/proxy provenance, and unsafe inheritance;
- `science dataset identity resolve` resolves labels where pinned commons artifacts exist and degrades honestly to `declared_unresolved` where they do not;
- MM30 stops hardcoding species/build metadata and becomes the first fully-resolved consumer.

## Current phase map

### P1-P3 - Framework adoption layer

**Status:** Merged to `main` on 2026-07-03 (`9f52b81d Merge branch 'bio-identity-adoption-layer'`).

Delivered:

- `bio.identity_context` schema/model support for `proxy`, tier-general `transform`, unresolved assemblies, and workflow output identity contracts;
- profile-scoped mandatory declaration gate;
- derived datapackage stamp helpers and agreement validation;
- `science dataset identity resolve|show|suggest`;
- `dataset add`, `commons dataset init`, and `dataset register-run` identity authoring/propagation integration;
- strict `inherit`, structured proxy handling, transform/proxy provenance checks, and reference dataset usage role;
- planning/user docs for identity-bearing datasets and workflow outputs.

P1-P3 make identity declaration strict and ergonomic. They do not make resolution fully useful until P4 artifacts exist.

### P4 - MM30-critical pinned commons artifacts

**Status:** P4.1-P4.3 landed; P4.4 next.

Purpose: make the resolver's offline path real for the artifacts MM30 needs first.

Work packages:

- **P4.1 assembly-registry build entrypoint.** Landed. `science-commons` now has a pinned `dataset:assembly-registry` artifact with row-bound assembly labels/aliases, deterministic `assemblies.csv` / `contigs.csv` / `contig_aliases.csv`, and updated datapackage hashes. Science resolver tests exercise the on-disk artifact offline using a reduced fixture copied from the built artifact.
- **P4.2 gene-crosswalk-hgnc build entrypoint.** Landed. `science-commons` now has a hardened pinned HGNC crosswalk artifact with validated `gene_key` lifecycle semantics, deterministic `crosswalk.csv`, and updated datapackage metadata. Science resolver tests exercise built-artifact rows offline through a reduced fixture.
- **P4.3 liftover-chain consumption.** Landed. Science now fixture-tests `dataset:assembly-liftover-grch37-grch38` through commons-style compatibility rows and gzipped chain bytes, validates cross-dataset liftover remedies against exact `from_seqcol_digest -> to_seqcol_digest` relations, and emits exact liftover seqcol provenance from `register-run` when source and target assemblies are resolved.
- **P4.4 cytoband-hg19 proxy reference.** Decide and implement the home for `cytoband-hg19`, preferably a commons reference dataset usable as `proxy.via` (this is the tracked work package for the open fork below).

P4 is not a broad reference-data program. It is the minimum artifact substrate needed for MM30 to move from declaration-level identity to resolved identity where it matters.

### P5 - MM30 first fully-resolved consumer

**Status:** Re-plan after P4.1-P4.4 shape is known.

Purpose: prove the framework and commons artifacts on a real consumer.

Work packages:

- remove MM30's hardcoded human species/taxon constants from datapackage emission;
- backfill declaration-level `identity_context` across existing MM30 dataset entities;
- resolve coordinate/gene datasets where P4 artifacts exist;
- add `outputs[].identity` contracts to coordinate- and feature-emitting workflows;
- replace t665's prose cross-build caveat with structured `proxy` identity and unblock TAD / A-B compartment axes.

P5 is the definition-of-done for the larger effort. P1-P4 are enabling layers; the end-to-end claim is only real when MM30 uses them successfully.

## Invariants to preserve

- **Entity source of truth.** Dataset entity `identity_context` is authoritative. Datapackage `science.identity_context` is derived and read-only.
- **Profile-scoped mandatory declarations.** Coordinate assays require assembly; gene/protein/variant datasets require the relevant molecular tier; all identity-bearing datasets require `taxon`; non-bio datasets are exempt.
- **Two-level strictness.** Declaration is strict at authoring time. Full resolution is required at promote/publish time or by explicit project policy.
- **Migration window discipline.** New/touched identity-bearing entities should be strict immediately, but the untouched backlog moves through a timed warn-then-error window surfaced by batch reporting. Missing derived datapackage stamps remain non-fatal during adoption; present stamps that disagree with the entity always error.
- **Offline reproducibility.** Resolution uses pinned commons artifacts only. No live MyGene, Ensembl REST, refgenie, UniProt, or other network fallbacks in reproducible paths.
- **Structured unresolved state.** `declared_unresolved` is legal only when explicit. Cross-build/proxy outputs keep assembly honest and carry a structured `proxy`.
- **Tier-general transforms.** `liftover`, `symbol_remap`, and `namespace_map` can apply to assembly or molecular tiers.
- **Reference artifacts are not data ancestors.** `transform.dataset` and `proxy.via` are provenance/reference machinery, not `derivation.inputs`; `proxy.sources[].dataset` are data ancestors.
- **Strict inheritance.** Bare `inherit` requires all selected inputs to agree. `inherit: {from: dataset:X}` must name a real source.

## Open forks

### Closed P1-P3 forks

- **Multi-input `transform.from: input`: closed.** Bare `from: input` is legal only for a single input; `dataset register-run` rejects it when multiple run inputs exist. Covered by `science/tests/test_dataset_register_run.py::test_register_run_rejects_transform_from_input_with_multiple_inputs`.
- **Migration-window strictness: partially closed.** P1-P3 implement the non-fatal missing-stamp adoption rule and strict present-stamp disagreement rule. P5 still owns the timed warn-then-error policy and batch reporting for the untouched MM30 backlog.

### `cytoband-hg19` home

Closed in P4.4: UCSC hg19 cytoBand is promoted as `dataset:cytoband-hg19` in `science-commons`. MM30/t665 should use this shared reference artifact as `identity_context.assembly.proxy.via` rather than creating an MM30-local cytoband reference.

### Exact P4 artifact shapes

P4.1 settled the assembly-registry on-disk/API contract the resolver consumes: row-bound assembly labels/aliases, RefSeq-accession named hosted seqcol rows for GRCh37/GRCh38, and assembly-report alias joins declared with `assembly_report_match_column: RefSeq-Accn`. P4.2 should do the same for gene crosswalks. The umbrella rule is simple: resolver contracts must be fixture-tested against built artifacts, not mocked-only.

### Liftover digest details

The framework has provenance hooks for liftover remedies. P4.3 should confirm whether resolved liftover outputs need `from_seqcol_digest` / `to_seqcol_digest` emitted into `derivation.transformations[]` for older validators, or whether the current transform block is sufficient.

## Progress ledger

- 2026-07-02: Bio identity adoption layer design and implementation plan written.
- 2026-07-03: P1-P3 framework adoption layer merged to `main` (`9f52b81d`). The merged state includes late planning/contract-validation fixes from `57fb4b96`, `815ba885`, and `aa362aec`; it is not just the original plan text.
- 2026-07-03: P1-P3 completion verification included `science/model` pytest, `science` pytest, `science/model` Ruff, targeted Ruff over changed Science files, and `git diff --check HEAD`.
- 2026-07-03: P4.1 assembly-registry landed. `science-commons` now has a pinned `dataset:assembly-registry` artifact with GRCh38 `XemD97fxYMS4q-FBm_n5CHQgmzh1_67a` and GRCh37 `XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA`, row-bound assembly labels/aliases, deterministic `assemblies.csv` / `contigs.csv` / `contig_aliases.csv`, and updated datapackage hashes; Science resolver tests exercise the on-disk artifact offline through a reduced built-artifact fixture.
- 2026-07-03: P4.2 gene-crosswalk-hgnc landed. `science-commons` has a pinned HGNC 2025-04-01 crosswalk artifact with validated opaque `gene_key` rows, hash-verified datapackage metadata, and Science offline resolver coverage for HGNC id/current symbol/previous symbol/alias ambiguity using built-artifact fixture rows.
- 2026-07-03: P4.3 liftover-chain consumption landed. The explicit `from_seqcol_digest` / `to_seqcol_digest` provenance decision is closed for v1; the transform block records intent, while `derivation.transformations[]` records the exact lifted source-target pair. Science proves offline compatibility loading and a tiny gzipped-chain interval lift through a reduced built-artifact fixture.
- 2026-07-03: P4.4 cytoband proxy reference landed. `science-commons` now has pinned `dataset:cytoband-hg19` bytes from UCSC hg19 `cytoBand.txt.gz`; Science has an offline hash-verified `science_tool.commons.cytoband` reader with parse + interval-overlap lookup, and proxy provenance tests use the real `dataset:cytoband-hg19` reference slug.
- Next: P5 MM30/t665 re-planning.

## How to use this doc

Use this as the orientation page at phase boundaries. Do not turn it into the detailed implementation plan for each work package. For each P4/P5 slice:

1. confirm the slice's role against the end-to-end goal;
2. write or update the focused plan in the appropriate repo;
3. implement in an isolated worktree;
4. update this umbrella only when a phase lands or an open fork closes.
