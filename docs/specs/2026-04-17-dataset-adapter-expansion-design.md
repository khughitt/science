# Dataset Adapter Expansion

**Status:** proposed
**Created:** 2026-04-17
**Source:** feedback fb-2026-04-17-001 (mm30)

## Problem

Current dataset adapters (GEO, Zenodo, Dryad, Semantic Scholar) miss the
portals that dominate biomedical practice. On a recent MM30 run, only 3 of 9
candidate datasets were verifiable via existing adapters; the other 6 relied
on LLM-only accession references, which is unsafe for pipeline inputs.

## Priority adapters

Listed in biomedical-impact order. Each can ship independently.

### 1. Open Targets Platform (highest priority)

- **Scope:** target–disease associations, drug–target, genetic evidence,
  disease-gene pairs across ~30 data sources. Primary bulk interface is
  versioned Parquet over FTP.
- **Entry points:**
  - Bulk: `https://platform.opentargets.org/downloads` (Parquet releases)
  - REST/GraphQL: `https://api.platform.opentargets.org/api/v4/graphql`
- **Search strategy:** GraphQL search endpoint for entity-level queries
  (targets, diseases, drugs); fall back to release-index for bulk datasets.
- **Effort:** M — GraphQL client + release-index parser.

### 2. DepMap

- **Scope:** CCLE cell-line genomics, gene-dependency screens, drug-response,
  Achilles/Chronos. Single portal covers many frequently-cited datasets.
- **Entry points:**
  - Catalog: `https://depmap.org/portal/download/api/downloads`
  - Direct file URLs are published per release
- **Search strategy:** JSON catalog endpoint; filter by release year / file
  type / context keyword.
- **Effort:** S — single JSON catalog, stable schema.

### 3. figshare (+)

- **Scope:** long tail of scRNA-seq, Perturb-seq mirrors, preprint data,
  institutional shares. High-recall supplement to Zenodo.
- **Entry points:**
  - Public API: `https://api.figshare.com/v2/articles/search`
  - Per-record: `/v2/articles/{id}` and `/v2/articles/{id}/files`
- **Search strategy:** POST search with `search_for` and `item_type=3`
  (dataset). API shape is very close to Zenodo; adapter can be a near-copy.
- **Effort:** S — mirrors Zenodo adapter structure.

### 4. PDC / CPTAC

- **Scope:** proteomics + multi-omics across CPTAC cohorts. Often referenced
  alongside TCGA but served separately.
- **Entry points:**
  - GraphQL: `https://pdc.cancer.gov/graphql`
  - File manifest downloads via `filesPerStudy` query
- **Search strategy:** GraphQL for study/project lookup; expand to files.
- **Effort:** M — GraphQL + study → files unroll.

### 5. clue.io / LINCS

- **Scope:** L1000 perturbation signatures, connectivity map, compound × cell
  × perturbation matrices.
- **Entry points:**
  - Bulk: `https://lincs-dcic.s3.amazonaws.com/` (signed/listed releases)
  - API: `https://api.clue.io/api` (requires key for some endpoints)
- **Search strategy:** tiered — public release index first; key-gated queries
  only if a token is configured.
- **Effort:** M — auth handling + versioned release parsing.

### 6. IHEC / BLUEPRINT

- **Scope:** epigenomic reference data (ChIP-seq, methylation, RNA-seq across
  hematopoietic and immune contexts).
- **Entry points:**
  - EpiRR API: `https://www.ebi.ac.uk/vg/epirr/view/all?format=json`
  - EGA accessions for access-controlled portions
- **Search strategy:** EpiRR index for discovery; mark access-controlled
  children with `access: controlled` so the template enum surfaces them.
- **Effort:** M — indexing is easy, access-tier handling is the work.

## Long-tail: generic HTTP-bulk adapter

For resources that will not get a bespoke adapter soon, expose a generic
adapter that accepts a user-supplied manifest:

```yaml
# manifest.yaml
name: "Replogle Perturb-seq K562 essentials"
entries:
  - url: "https://..."
    checksum: "sha256:..."
    format: "h5ad"
    size_bytes: 12345678
```

This lets the template/workflow stay uniform even when the portal does not
justify engineering time.

- **Effort:** S — one adapter that trusts the manifest and only fetches.

## Implementation plan

Ship adapters in the priority order above. Each PR should:

1. Add the adapter file under `science_tool/datasets/<name>.py` matching the
   existing `DatasetAdapter` protocol.
2. Register it in `science_tool/datasets/__init__.py`.
3. Add tests under `science-tool/tests/test_datasets.py` using the same
   mock-based pattern as the Zenodo tests.
4. Document the source in `science-tool/src/science_tool/datasets/sources.md`
   (create if needed) with entry-point URLs and query semantics.
5. Update `commands/find-datasets.md` only if the new adapter changes usage.

Skip implementing until at least one consumer in an active project would
benefit — do not expand adapter surface ahead of demand.

## Out of scope

- TCGA / GDC — already covered by ad-hoc tooling in most biomedical projects;
  revisit only if a consumer needs it.
- Controlled-access auth flows (dbGaP, EGA submission) — adapters should
  surface controlled records but not attempt the auth handshake.
- Per-adapter citation export — leave to the generic metadata path.

## Non-goals

- Replacing portal-native download tools. These adapters are for discovery
  and metadata extraction, not large downloads.
- Building a unified biomedical ontology mapping inside the adapters. Keep
  ontology normalization in `science-tool graph` consumers, not here.
