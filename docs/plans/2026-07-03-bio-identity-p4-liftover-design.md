# Bio Identity P4.3 Liftover Consumption - Design

- **Status:** Draft for review
- **Date:** 2026-07-03
- **Scope:** P4.3 of the bio identity adoption umbrella: make `transform: liftover` consume the pinned `dataset:assembly-liftover-grch37-grch38` artifact offline through Science resolver and validation surfaces.
- **Umbrella:** `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`
- **Depends on:** P1-P3 identity workflow/provenance layer, P4.1 assembly-registry digests, and the existing C4b liftover parser/remedy code.

## Purpose

P4.3 turns liftover from a declared remedy into a proven offline workflow step. After this slice, a derived coordinate-bearing dataset can declare an assembly transform that points at `dataset:assembly-liftover-grch37-grch38`, validation can prove that the referenced commons artifact contains the exact source-target seqcol compatibility relation, and a small runtime fixture can lift at least one interval using pinned chain bytes.

The invariant is unchanged from Pillar C: liftover relates distinct assembly-anchored identities. A lifted coordinate is not equal to the source coordinate; it is a new target-assembly coordinate with explicit chain provenance.

## Current State

Science already has the framework and low-level pieces:

- `science_tool.commons.liftover` parses UCSC chain text and lifts same-strand intervals inside a single chain block, returning explicit `LiftedInterval` or `LiftoverDefect`.
- `science_tool.commons.assembly_compatibility` reads `compatibility_relations.csv` from a commons datapackage resource and parses exact `liftover_possible` relations.
- `science_tool.validate.checks.identity_context` detects cross-dataset assembly mismatches and treats a `derivation.transformations[]` liftover entry as a remedy only when a loaded compatibility relation exactly matches `from_seqcol_digest -> to_seqcol_digest`.
- `dataset register-run` routes `identity_context.assembly.transform.dataset` into `derivation.transformations[]` instead of `derivation.inputs`, preserving the reference-artifact-vs-data-ancestor split.
- Unit tests cover chain parsing/lifting and synthetic compatibility relations.

`~/d/science-commons/datasets/assembly-liftover-grch37-grch38/` already exists and is hash-pinned:

- `datapackage.yaml` exposes resource `compatibility_relations` and resource `hg19ToHg38_chain`.
- `recipe/lockfile.yaml` pins UCSC `hg19ToHg38.over.chain.gz` with SHA-256 `sha256:5c0598e500ceb5a78c73086929e8ef993aec309bcafb595139b53d440b125a1d` and `227698` bytes.
- `recipe/build.py` validates explicit source/target seqcol digests, verifies the installed chain bytes against the lockfile, writes `compatibility_relations.csv`, and updates datapackage hashes.

The gap is consumption hardening. Science does not yet have a built-artifact fixture for this dataset, does not prove the compatibility loader reads the commons-style datapackage/hash path, and does not prove the chain resource named by the compatibility row can be opened and used offline.

## Decision

Finish P4.3 as a consumption and fixture slice over the existing `science-commons` dataset. Do not redesign the liftover model and do not add a broad interval-liftover CLI in this slice.

The built artifact contract remains:

- `compatibility_relations.csv`: required for validation of `transform: liftover` remedies.
  Columns: `source_seqcol_digest,target_seqcol_digest,relation,method,chain_resource,direction,source_label,target_label,source_url,chain_sha256`.
- `chains/hg19ToHg38.over.chain.gz`: required chain bytes named by `chain_resource`.

Science consumes this contract in two layers:

1. The validation layer loads `compatibility_relations.csv` through `commons.resolver.resolve` and checks exact source-target digest compatibility.
2. The runtime liftover layer resolves the named chain resource, verifies its hash via the datapackage resolver, decompresses/parses UCSC chain text, and uses `lift_interval` for same-strand single-block intervals.

## Liftover Provenance Shape

For v1, keep `from_seqcol_digest` and `to_seqcol_digest` explicit in `derivation.transformations[]`.

Example derived entity provenance:

```yaml
derivation:
  inputs:
    - dataset:gse87585-wu2017
  transformations:
    - kind: identity_transform
      target: assembly
      type: liftover
      method: ucsc_chain
      dataset: dataset:assembly-liftover-grch37-grch38
      from_seqcol_digest: XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA
      to_seqcol_digest: XemD97fxYMS4q-FBm_n5CHQgmzh1_67a
```

The corresponding entity identity remains target-assembly identity:

```yaml
identity_context:
  taxon: 9606
  assembly:
    label: GRCh38
    seqcol_digest: XemD97fxYMS4q-FBm_n5CHQgmzh1_67a
    registry: dataset:assembly-registry
    resolution_status: resolved
    transform:
      type: liftover
      from: dataset:gse87585-wu2017
      method: ucsc_chain
      dataset: dataset:assembly-liftover-grch37-grch38
```

The explicit digests in `derivation.transformations[]` are not a second authority. They are run provenance emitted by `register-run` from the resolved source and target identities. Keeping them explicit lets the validator check a remedy without re-inferring which parent was lifted when a derived dataset has multiple inputs.

### The Umbrella Fork

The umbrella asked whether P4.3 should drop `from_seqcol_digest` / `to_seqcol_digest` and rely on the current transform block alone. The decision for P4.3 is **no**:

- the transform block records author intent and reference artifact;
- the derivation transformation records execution provenance for the specific source-target digest pair;
- validators can fail loud when the contract claims a liftover but the run provenance lacks the exact pair;
- multi-input derived datasets stay unambiguous without a new inference algorithm.

A future ergonomics improvement may let `register-run` synthesize these fields automatically from resolved inputs and output identity. P4.3 may add that emission if it is local and testable, but it should not remove the explicit fields from the provenance contract.

## Artifact Boundary

The recipe is operator-run and may use the network at fetch time. Runtime resolution, validation, and interval lifting remain fully offline.

Build-time inputs:

- pinned UCSC chain URL in `recipe/lockfile.yaml`;
- pinned chain SHA-256 and byte count;
- explicit GRCh37 and GRCh38 seqcol digests from the P4.1 assembly registry;
- installed chain bytes under the commons data root.

Build-time checks:

- reject mutable URLs such as `latest` or `current`;
- verify downloaded or installed chain bytes against the lockfile;
- fail if source and target seqcol digests are blank, malformed, or equal;
- write a deterministic single-row `compatibility_relations.csv`;
- update datapackage `hash` and `bytes` for both compatibility and chain resources.

Runtime checks:

- `commons.resolver.resolve` verifies datapackage resource hashes before reading compatibility rows or chain bytes;
- compatibility parsing fails on malformed rows, duplicate source-target relations, unsupported relation/method/direction, or bad chain SHA strings;
- a chain resource referenced by compatibility rows must exist as a datapackage resource with a matching hash;
- runtime code must not fetch network data.

## Alternatives Considered

### A. Prove consumption of the existing commons liftover dataset

Chosen. The dataset, lockfile, build recipe, compatibility reader, and chain parser already exist. The highest-value work is proving they line up end-to-end through real commons-style fixtures and validation.

### B. Rebuild the liftover artifact format

Rejected. The current two-resource contract is enough: a small CSV for compatibility checks and a gzipped UCSC chain file for actual interval lifting. A richer manifest would duplicate datapackage metadata without a current consumer.

### C. Treat a declared transform as sufficient without exact digest provenance

Rejected for v1. A prose or intent-only transform can hide a wrong source-target pair. The exact `from_seqcol_digest` / `to_seqcol_digest` fields make the validator's question concrete: does this chain dataset contain a relation for this parent assembly to this output assembly?

### D. Implement broad BED/VCF liftover CLI now

Rejected. P4.3's definition of done is `lift hg19 -> hg38` runs offline against pinned chains and validation consumes the pinned relation. Batch file liftover, reverse-strand allele reminting, multi-mapping policy, and VCF/BED output formats are larger C4/P5 concerns.

## Cross-Repo Ownership

`~/d/science-commons` owns the built bytes and recipe:

- `datasets/assembly-liftover-grch37-grch38/recipe/lockfile.yaml`
- `datasets/assembly-liftover-grch37-grch38/recipe/fetch.py`
- `datasets/assembly-liftover-grch37-grch38/recipe/build.py`
- `datasets/assembly-liftover-grch37-grch38/datapackage.yaml`
- `datasets/assembly-liftover-grch37-grch38/entity.md`
- data-root bytes for `compatibility_relations.csv` and `chains/hg19ToHg38.over.chain.gz`

`~/d/science` owns the reader contract, validation behavior, and integration fixture:

- `science/src/science_tool/commons/assembly_compatibility.py`
- `science/src/science_tool/commons/liftover.py`
- `science/src/science_tool/validate/checks/identity_context.py`
- `science/src/science_tool/datasets_register.py`
- `science/tests/test_commons_assembly_compatibility.py`
- `science/tests/test_commons_liftover.py`
- `science/tests/validate/test_checks_identity_context.py`
- a focused commons-style fixture copied from the built liftover artifact.

If implementation requires a `science-commons` worktree, create it under `~/d/science-commons/.worktrees/` and keep commits split by repo.

## Integration Fixture

P4.3 needs a reduced fixture parallel to P4.1 and P4.2:

1. Use a real commons-style entity + datapackage + data-root layout for `dataset:assembly-liftover-grch37-grch38`.
2. Include a small `compatibility_relations.csv` row copied from the built artifact, using the real P4.1 GRCh37 and GRCh38 seqcol digests.
3. Include a tiny gzipped UCSC chain resource under `chains/` whose SHA-256 and byte count are recorded in the fixture datapackage.
4. Verify `load_compatibility_relations(..., commons_root=..., data_root=...)` reads through the datapackage/hash path and returns the real source-target relation.
5. Verify validation suppresses the cross-dataset assembly mismatch only when the transformation names the same liftover dataset, method, `from_seqcol_digest`, and `to_seqcol_digest`.
6. Verify a chain-loader path resolves the chain resource offline, parses it, and lifts one interval.
7. Monkeypatch sockets or use the existing no-network pattern to prove runtime compatibility loading and interval lifting do not use the network.

The fixture should not commit the full UCSC chain. A tiny synthetic chain is acceptable for Science tests as long as the compatibility row and datapackage shape mirror the built artifact contract. The full chain remains in the commons data root and is verified by the commons recipe.

## Error Handling

Direct reader APIs should fail early:

- malformed compatibility CSV rows raise `AssemblyCompatibilityError`;
- missing or ambiguous compatibility relations return no remedy or raise at the direct parser boundary;
- malformed chain text raises `ChainFormatError`;
- unliftable, multi-mapping, or unsupported reverse-strand intervals return `LiftoverDefect` rather than silently dropping rows.

Authoring and validation surfaces preserve existing behavior:

- if the liftover dataset cannot be resolved, cross-dataset assembly validation keeps the mismatch warning instead of crashing;
- provenance validation errors when `transform.dataset` is not a real dataset entity or is not routed through `derivation.transformations[]`;
- reference artifacts are not placed in `derivation.inputs` and do not create data-dependence edges.

## Non-Goals

- No new assembly identity model and no equality assertion across GRCh37/GRCh38.
- No broad batch liftover command for BED/VCF/table files.
- No reverse-strand allele projection or VRS reminting expansion.
- No cytoband proxy dataset; that is P4.4.
- No MM30 entity/workflow retrofit; that is P5.
- No runtime network fallback to UCSC or any external liftover service.

## Acceptance Criteria

- Science has a commons-style `assembly-liftover-grch37-grch38` fixture with compatibility and chain resources resolved through datapackage hashes.
- `load_compatibility_relations` is integration-tested against that fixture using the real GRCh37 and GRCh38 P4.1 seqcol digests.
- Runtime chain loading and `lift_interval` are tested offline through a datapackage-resolved gzipped chain resource.
- Cross-dataset assembly validation passes only for exact declared `from_seqcol_digest -> to_seqcol_digest` relations present in the pinned liftover dataset.
- Wrong method, wrong target digest, missing relation, missing dataset, or reference-artifact misrouting still warn/error as appropriate.
- If `register-run` emits liftover transformations from an output contract, it includes `from_seqcol_digest` and `to_seqcol_digest` when source and target identities are resolved; unresolved sources remain explicit and do not fabricate digests.
- The `science-commons` liftover recipe remains deterministic and verifies the pinned chain lockfile; datapackage hashes match generated resources.
- Runtime liftover resolution remains offline.
- The umbrella doc is updated when P4.3 lands to record the settled explicit-digest provenance decision and move `Next:` to P4.4.
