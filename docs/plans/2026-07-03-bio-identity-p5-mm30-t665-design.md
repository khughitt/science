# Bio Identity P5 - MM30/t665 Adoption Design

- **Status:** Draft
- **Date:** 2026-07-03
- **Scope:** P5 replanning for MM30 as the first fully-resolved consumer of the bio identity adoption layer.
- **Depends on:** P1-P3 framework adoption layer, P4.1-P4.4 pinned commons artifacts, and the umbrella tracker at `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`.
- **Execution repos:** `~/d/science` for coordination docs and validation behavior; the MM30 repository for entity/workflow/runtime adoption.

## Purpose

P5 proves that the bio identity adoption layer works on the real downstream project that motivated it. The end-to-end claim is:

> MM30 can declare, resolve, propagate, stamp, validate, and use biological identity context, with t665's mixed hg38/hg19 cytoband-proxy join represented as machine-checkable structure rather than prose.

P5 is not a broad reference-data program and not a full biological ontology cleanup. P1-P4 made the framework and reference artifacts usable; P5 must make a real workflow use them without breaking the rest of the MM30 backlog.

## Current State

The framework side is ready enough for a consumer:

- P1-P3 landed profile-scoped identity declaration, datapackage stamps, `science dataset identity resolve|show|suggest`, `register-run` propagation, strict `inherit`, tier-general transforms, and structured `proxy`.
- P4.1-P4.4 landed the MM30-critical commons artifacts: `dataset:assembly-registry`, `dataset:gene-crosswalk-hgnc`, `dataset:assembly-liftover-grch37-grch38`, and `dataset:cytoband-hg19`.
- The current `dataset:assembly-registry` rows are exact NCBI-named `GRCh37` and `GRCh38` collections. They are not blanket aliases for UCSC `hg19`/`hg38`; P5 must preflight whether each MM30 source is actually resolvable to those rows or needs an explicit unresolved declaration / registry expansion.
- The resolver needs both commons metadata and commons data bytes. P5 commands must set `SCIENCE_COMMONS_ROOT=~/d/science-commons` and `SCIENCE_COMMONS_DATA_ROOT` to the local built-byte root; otherwise missing data silently degrades assembly declarations to `declared_unresolved`, which is indistinguishable from a genuine registry miss unless a positive control is run.
- `dataset:cytoband-hg19` is now the shared proxy reference for t665. MM30 should not keep using its staged `cytoBand.hg19.txt.gz` as the identity authority, though the staging rule may keep downloading it as an input integrity check until the implementation removes or replaces that local path.

MM30 is still at pre-adoption state:

- The shared datapackage helper hardcodes `mm30.species: Homo sapiens` and `mm30.taxonomy_id: 9606`; identity does not derive from dataset entities.
- Approximately 259 dataset entities exist, but only a few have explicit `schema_profile`, and `identity_context` is effectively absent.
- `entities/datasets/gse131651-shah2019-nsd2.md` records the hg38 source context in prose and workflow configuration.
- `entities/datasets/gse87585-wu2017.md` records hg19 CN/SV and cytoband-proxy caveats in prose.
- `entities/workflows/gse131651-3d-locus-ledger.md` already has `outputs[]`, but no `outputs[].identity` contract.
- `workflows/stages/three_d_genome.smk` runs `three_d_genome_gse131651_locus_ledger`, consuming GSE131651, GSE87585, MM30 meta scores, and cytogenetics outputs.
- `scripts/analyses/t665_gse131651_3d_locus_ledger.py` contains local build checks and a hand-rolled cytoband-proxy join. That script should keep fail-loud data checks, but the identity claim must move into entity/workflow metadata.

## Key Decisions

### Decision 1: P5 starts with the t665 vertical slice, not a repo-wide retrofit

**Chosen:** first land a narrow, executable t665 path that proves declaration, resolution, workflow contract, register-run propagation, datapackage stamp, and validation on the real mixed-build proxy case.

**Rejected:** starting with a full backfill of every MM30 dataset entity. That would create a large metadata-change surface before proving the workflow seam, and it would make validation failures harder to interpret.

**Also rejected:** doing only t665 with no migration scaffold. That would prove the happy path while leaving the strictness/backlog policy unresolved.

### Decision 2: P5 is two lanes under one plan

**Chosen:** split P5 into:

- **P5a - t665 vertical slice:** concrete end-to-end adoption for the motivating workflow.
- **P5b - MM30 migration scaffold:** inventory, batch report, migration-window policy, and first identity backfill mechanics for the wider entity backlog.
- **P5c - broader MM30 rollout:** subsequent batches after P5a/P5b prove the contracts.

P5a and P5b are coupled: P5a prevents design theater, while P5b prevents a one-off demo that cannot scale to the project.

### Decision 3: Entity identity remains authoritative in MM30

**Chosen:** external dataset entities own identity. Runtime datapackages get derived `science.identity_context` stamps. For derived outputs, `outputs[].identity` in the workflow entity is the contract that `register-run` propagates into derived dataset entities and datapackages.

**Rejected:** adding authoritative build/species fields to MM30 datapackage emitters. That repeats the old hardcoded-species failure and splits the source of truth.

### Decision 4: The t665 output is a structured unresolved proxy

**Chosen:** the t665 ledger output declares:

- `taxon: 9606`
- `assembly.resolution_status: declared_unresolved`
- `assembly.seqcol_digest: UNKNOWN`
- `assembly.proxy.type: cytoband_proxy`
- `assembly.proxy.via: dataset:cytoband-hg19`
- `assembly.proxy.sources[]` naming the real data ancestors, at minimum `dataset:gse131651-shah2019-nsd2` and `dataset:gse87585-wu2017`.

This keeps assembly honest: the ledger is not GRCh38, not hg19, and not silently joinable as coordinate-precise.

**Rejected:** resolving the output to either input assembly, or leaving the proxy caveat in prose.

### Decision 5: Reference artifacts stay out of data ancestry

**Chosen:** `dataset:cytoband-hg19`, `dataset:assembly-registry`, `dataset:gene-crosswalk-hgnc`, and liftover chain datasets are reference machinery. They belong in transformations/reference usage, not `derivation.inputs`.

**Rejected:** placing cytoband, crosswalk, or chain artifacts into data ancestry. That would incorrectly imply shared biological evidence and confuse independence/reproducibility gates.

### Decision 6: Strictness is phased by touched surface

**Chosen:** new or touched t665 identity-bearing surfaces are strict immediately. The untouched MM30 backlog enters a migration window: validation reports missing identity as a batchable warning/advisory first, then later becomes an error by explicit project policy.

Present but disagreeing datapackage stamps always error. Missing stamps remain non-fatal during adoption.

**Rejected:** erroring immediately on the whole untouched backlog, which would block unrelated MM30 work; and indefinitely warning, which would preserve the current silent-drift risk.

## Target t665 Identity Shape

### Source Dataset: GSE131651

`dataset:gse131651-shah2019-nsd2` should become an identity-bearing coordinate/gene dataset with a human taxon and an explicit hg38/GRCh38 assembly stance.

The implementation plan must verify the exact label/digest pairing against the current `dataset:assembly-registry`. If the consumed intervals are UCSC-style `chr*` hg38, they must not be silently resolved to the NCBI-named `GRCh38` row. They may resolve only if the implementation proves the row is the intended collection under the registry's exact label/alias contract; otherwise the entity must declare `hg38` as unresolved and the implementation plan must record whether P5 needs a small assembly-registry expansion before claiming full coordinate resolution.

Conservative expected shape before that preflight:

```yaml
identity_context:
  taxon: 9606
  assembly:
    label: hg38
    registry: dataset:assembly-registry
    resolution_status: declared_unresolved
    seqcol_digest: UNKNOWN
  molecular_ids:
    gene:
      namespace: hgnc_symbol
      registry: dataset:gene-crosswalk-hgnc
      resolution_status: resolved
```

If the assembly registry can resolve the intended collection exactly, `science dataset identity resolve` replaces the declaration with the row-bound digest. If it cannot, the declaration remains honest and P5a can still prove proxy structure, but the broader "fully resolved consumer" claim remains blocked on adding the missing exact assembly row.

### Source Dataset: GSE87585

`dataset:gse87585-wu2017` should declare human taxon and hg19 identity for the CN/SV coordinate supplements. Its local staged `cytoBand.hg19.txt.gz` remains input-file provenance unless implementation removes it; the proxy reference identity should point to shared `dataset:cytoband-hg19`.

Conservative expected shape:

```yaml
identity_context:
  taxon: 9606
  assembly:
    label: hg19
    registry: dataset:assembly-registry
    resolution_status: declared_unresolved
    seqcol_digest: UNKNOWN
```

The current registry does not contain an exact `hg19` row. Do not alias hg19 to the NCBI `GRCh37` digest just to make the field resolved. P5a may proceed with an explicit unresolved source plus structured output proxy; the end-to-end resolution claim requires either an exact hg19 registry row or a documented decision that this t665 axis is intentionally proxy-only.

### MM30 Meta Scores and Cytogenetics Inputs

The t665 ledger consumes MM30 meta-score and cytogenetics outputs. These are not direct coordinate tracks, but they are feature-bearing and gene/symbol-space-bearing enough to need an explicit identity stance.

P5a should not attempt to remodel the entire meta/cytogenetics pipeline. It should declare the minimal identity needed for t665's consumed inputs:

- `taxon: 9606`
- gene tier `namespace: hgnc_symbol`
- `registry: dataset:gene-crosswalk-hgnc`
- `resolution_status: resolved` when the resolver can verify that the declared namespace is supported by an available gene registry for the gene tier, otherwise `declared_unresolved` with the namespace still explicit.

Current framework semantics do not make `molecular_ids.gene.resolution_status: resolved` a per-symbol membership claim. It says the namespace/tier/registry declaration is supported and available. If P5 needs to prove every symbol in a t665 artifact appears in `crosswalk.csv`, that must be a separate content check in the implementation plan, not implied by the identity metadata alone.

If those inputs do not yet have dataset entities, the implementation must either create narrow derived/input entities for the consumed artifacts or keep them as workflow-run inputs with explicit contract coverage. The design preference is to use dataset entities when the artifacts are reused outside one run.

### Workflow Output Contract

`entities/workflows/gse131651-3d-locus-ledger.md` should declare output identity next to `resource_names`:

```yaml
outputs:
- slug: gse131651-3d-locus-ledger
  title: GSE131651 3D architecture evidence ledger
  resource_names:
  - gse131651_locus_ledger
  - gse131651_track_inventory
  - gse131651_question_crosswalk
  identity:
    taxon: 9606
    assembly:
      label: mixed-build-cytoband-proxy
      registry: dataset:assembly-registry
      resolution_status: declared_unresolved
      seqcol_digest: UNKNOWN
      proxy:
        type: cytoband_proxy
        via: dataset:cytoband-hg19
        sources:
        - dataset: dataset:gse131651-shah2019-nsd2
          assembly: inherit
        - dataset: dataset:gse87585-wu2017
          assembly: inherit
    molecular_ids:
      gene:
        namespace: hgnc_symbol
        registry: dataset:gene-crosswalk-hgnc
        resolution_status: resolved
        transform:
          type: symbol_remap
          from: input
          dataset: dataset:gene-crosswalk-hgnc
```

The implementation plan must reconcile `transform.from: input` with the actual selected inputs. If multiple inputs participate in the gene transform, `from` must name the source dataset explicitly rather than using bare `input`.

## P5 Work Packages

### P5a - t665 Vertical Slice

Goal: prove the full identity path on the motivating workflow.

Work:

- add identity declarations to `dataset:gse131651-shah2019-nsd2` and `dataset:gse87585-wu2017`;
- preflight those declarations with `science dataset identity resolve` against `dataset:assembly-registry`, setting both `SCIENCE_COMMONS_ROOT` and `SCIENCE_COMMONS_DATA_ROOT`, and recording exact resolutions plus honest unresolved blockers;
- run a positive-control resolution for a known registry label such as `GRCh38` before trusting any unresolved result from hg19/hg38 preflight;
- add or identify the minimal t665 meta/cytogenetics input identities needed for the gene tier;
- add `outputs[].identity` to `workflow:gse131651-3d-locus-ledger`;
- run or register the t665 workflow output so the derived dataset receives `identity_context` and datapackage stamp;
- validate that `dataset:cytoband-hg19` is recorded as reference/proxy machinery, while GSE131651 and GSE87585 are data ancestors;
- keep script-level build checks fail-loud, but remove identity authority from bespoke local fields where possible.

Definition of done:

- `science validate --project-root $MM30_WORKTREE` passes or reports only explicitly accepted pre-existing warnings outside the touched t665 surface;
- the t665 derived output has entity `identity_context` and a matching datapackage `science.identity_context` stamp;
- a missing or wrong `proxy.via` causes validation failure;
- the TAD/A-B compartment unblock can point to a machine-visible `cytoband_proxy` contract, not prose.
- any exact-assembly gap for hg19/hg38 is explicit in the P5a result, not hidden behind GRCh37/GRCh38 aliasing.
- the resolver preflight proves it actually read `dataset:assembly-registry` by resolving a known-control label before interpreting hg19/hg38 as genuinely unresolved.

### P5b - MM30 Migration Scaffold

Goal: make the rest of MM30 adoptable without a destabilizing all-at-once edit.

Work:

- inventory all dataset entities and classify them as coordinate-bearing, gene-bearing, protein-bearing, variant-bearing, taxon-only, or non-bio/exempt;
- produce a batch report that identifies missing `schema_profile`, missing identity, declaration-only identity, resolved identity, and blocker reason;
- define the migration-window policy in MM30 project config or validation docs: touched identity-bearing entities are strict now; untouched backlog warns until a named cutoff;
- add a repeatable command path for batch identity declaration/resolution using `science dataset identity resolve`, without live network lookup;
- backfill declaration-level `taxon: 9606` for the human identity-bearing backlog where the entity evidence supports it, while leaving murine and non-human datasets explicitly non-human rather than inheriting MM30's old hardcoded human default.

Definition of done:

- MM30 has a reproducible identity adoption report;
- touched/t665 entities are strict;
- untouched backlog is visible and bounded by policy;
- the shared datapackage helper no longer hardcodes human identity as authority.

### P5c - Broader Rollout

Goal: apply the proven pattern beyond t665 in controlled batches.

Work:

- migrate coordinate- and feature-emitting workflows in priority order;
- resolve coordinate and gene tiers where P4 artifacts support them;
- leave honest `declared_unresolved` declarations for unsupported taxa/namespaces/artifacts;
- turn the migration window from warning to error after backlog coverage reaches the agreed threshold.

Definition of done:

- every identity-bearing MM30 dataset has at least declaration-level identity;
- coordinate/gene datasets supported by P4 artifacts are resolved;
- routine datapackage builds stamp identity from entities rather than MM30 constants;
- validation catches unmarked cross-build joins in normal MM30 work.

## Validation Strategy

P5 validation should be layered:

1. **Focused t665 metadata tests**: assert the two source entities and workflow output parse with the intended identity blocks.
2. **Register-run test**: prove the t665 workflow contract propagates to a derived entity/datapackage and routes `dataset:cytoband-hg19` to transformations/reference usage, not data inputs.
3. **Resolver smoke test**: run `science dataset identity resolve` over the touched entities with both `SCIENCE_COMMONS_ROOT=~/d/science-commons` and `SCIENCE_COMMONS_DATA_ROOT=$SCIENCE_COMMONS_DATA_ROOT` set to the built commons data root.
4. **Project validation**: run `science validate --project-root $MM30_WORKTREE` and capture the warning/error split.
5. **Regression test for strictness**: temporarily remove the proxy or make source assemblies disagree without a proxy and confirm validation fails.
6. **Alias-conflation guard**: confirm hg19 is not resolved to the current NCBI `GRCh37` row, and hg38 is not resolved to the NCBI `GRCh38` row unless the registry row's exact label/alias contract supports that source.
7. **Positive-control guard**: before accepting any unresolved assembly result, resolve a known-supported label such as `GRCh38` and verify it returns the registry digest. If the control fails, the data root is misconfigured and the preflight result is invalid.

The implementation plan should prefer focused tests and command verification over broad runtime regeneration unless the runtime output is needed to prove the datapackage stamp.

## Non-goals

- Do not backfill all MM30 entities before proving t665.
- Do not add a second identity authority to MM30 datapackage metadata.
- Do not use live MyGene, Ensembl REST, UCSC, or other network lookup in reproducible identity resolution.
- Do not pretend `hg19` and `GRCh37` are interchangeable if the assembly registry cannot resolve the exact intended collection.
- Do not remodel t665's biological interpretation; this plan only makes the identity/proxy contract machine-visible and unblockable.
- Do not require all non-bio MM30 entities to carry assembly or molecular tiers.

## Open Questions For Implementation Planning

- Which exact MM30 output/entity represents the t665 derived ledger after `register-run`: an existing entity to update, or a new derived dataset entity minted from the workflow run?
- Does P5 first add exact UCSC hg19/hg38 assembly-registry rows, or does P5a intentionally land with those source assemblies `declared_unresolved` while proving the proxy contract?
- Does t665 need a separate content-level gene-symbol verification against `dataset:gene-crosswalk-hgnc`, or is namespace/tier/registry resolution sufficient for P5a?
- Do the MM30 meta-score and cytogenetics artifacts consumed by t665 already have dataset entities, or should P5a create narrow entities for only the consumed artifacts?
- Should the t665 script stop staging `cytoBand.hg19.txt.gz` once `dataset:cytoband-hg19` exists, or keep it temporarily as a source-file sentinel while identity points to the commons reference?
- What cutoff or policy name should MM30 use for the warn-then-error migration window?
- Which murine/non-human entities should be used as sentinel tests to ensure removal of the hardcoded human default is real?

## Acceptance Criteria

- [ ] The design separates t665 proof from broader MM30 migration, while keeping both in P5 scope.
- [ ] `dataset:gse131651-shah2019-nsd2` and `dataset:gse87585-wu2017` have entity-authoritative identity declarations.
- [ ] The plan does not conflate hg19 with GRCh37 or hg38 with GRCh38 unless the assembly registry contains exact row-bound support for that label.
- [ ] The resolver preflight sets both commons roots and includes a positive-control label resolution.
- [ ] The t665 workflow output declares a structured `cytoband_proxy` via `dataset:cytoband-hg19`.
- [ ] `register-run` propagates the t665 output identity into a derived dataset entity and datapackage stamp.
- [ ] `dataset:cytoband-hg19` is treated as reference/proxy machinery, not a data ancestor.
- [ ] MM30's hardcoded species/taxon metadata is no longer authoritative for datapackage identity.
- [ ] The untouched MM30 backlog is handled by an explicit migration-window report/policy.
- [ ] Validation fails for unmarked mixed-build t665 output identity.
