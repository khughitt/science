# CPTAC GBM Fetchability Spike - 2026-07-03

## Scope

This spike follows the CPTAC cross-modal benchmark audit and tests whether the
specific cBioPortal/DataHub package `gbm_cptac_2021` is fetchable enough to
support a concrete deposit recipe for:

- Proposed dataset: `dataset:cptac-gbm-2021-proteogenomics`
- Task: `protein-rna-cross-modal`
- Parent/reference dataset: `dataset:cptac-proteogenomics`

The goal was not to add commons metadata or stage durable data yet. The goal was
to prove one reliable extraction path and identify the recipe contract.

## Live Source Surface

The cBioPortal study endpoint reports:

- Study id: `gbm_cptac_2021`
- Name: `Glioblastoma (CPTAC, Cell 2021)`
- Public study: `true`
- Import date: `2026-01-07 13:14:46`
- All samples: 99
- RNA-seq samples: 99
- Mass-spectrometry samples: 99
- Citation: Wang et al. Cell 2021
- PMID: `33577785`

The molecular profile endpoint exposes the required profile ids:

- mRNA: `gbm_cptac_2021_mrna`
- Protein: `gbm_cptac_2021_protein_quantification`

The sample-list endpoint exposes matching lists:

- mRNA list: `gbm_cptac_2021_rna_seq_mrna`
- Protein list: `gbm_cptac_2021_protein_quantification`

## Fetch Paths Tested

### cBioPortal API

Small gene slices work for both mRNA and protein through:

```bash
curl -L --fail --silent --show-error \
  -X POST "https://www.cbioportal.org/api/molecular-profiles/gbm_cptac_2021_mrna/molecular-data/fetch?projection=DETAILED" \
  -H "Content-Type: application/json" \
  -d '{"entrezGeneIds":[1956,7157],"sampleListId":"gbm_cptac_2021_rna_seq_mrna"}'

curl -L --fail --silent --show-error \
  -X POST "https://www.cbioportal.org/api/molecular-profiles/gbm_cptac_2021_protein_quantification/molecular-data/fetch?projection=DETAILED" \
  -H "Content-Type: application/json" \
  -d '{"entrezGeneIds":[1956,7157],"sampleListId":"gbm_cptac_2021_protein_quantification"}'
```

Both returned numeric values for `EGFR` and `TP53` across the expected samples.

Full-profile API requests using only `sampleListId` began returning substantial
payloads but did not complete within a 45-second cap:

- mRNA request timed out after receiving 18,726,912 bytes.
- Protein request timed out after receiving 17,022,976 bytes.

Conclusion: cBioPortal API is useful for metadata and smoke-slice validation,
but a full matrix recipe should not rely on one all-profile API request as its
primary transport.

### DataHub Git LFS Objects

Raw GitHub DataHub URLs expose git-LFS pointer files:

```text
version https://git-lfs.github.com/spec/v1
oid sha256:235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722
size 29693169
```

for `data_mrna_seq_fpkm.txt`, and:

```text
version https://git-lfs.github.com/spec/v1
oid sha256:b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e
size 6852651
```

for `data_protein_quantification.txt`.

The GitHub LFS batch API returned signed download URLs for both objects:

```bash
curl -L --fail --silent --show-error \
  -X POST https://github.com/cBioPortal/datahub.git/info/lfs/objects/batch \
  -H "Accept: application/vnd.git-lfs+json" \
  -H "Content-Type: application/vnd.git-lfs+json" \
  -d '{"operation":"download","transfers":["basic"],"objects":[{"oid":"235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722","size":29693169},{"oid":"b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e","size":6852651}]}'
```

Direct object downloads completed and matched the expected object hashes:

| File | Bytes | SHA-256 | Rows | Columns | Pointer |
| --- | ---: | --- | ---: | ---: | --- |
| `data_mrna_seq_fpkm.txt` | 29,693,169 | `235cef753fc34d0168e97c145616bcfb3fe1c2f726038bef891639dfbec05722` | 44,963 | 100 | no |
| `data_protein_quantification.txt` | 6,852,651 | `b5512312c26b68b1f137fa493448ecce0e9a8b44a5bd35b8cc9dfb67f68a6a0e` | 10,997 | 100 | no |

The row counts exclude the header row. The column counts include the feature id
column plus 99 sample columns.

## Sample Alignment

The mRNA and protein files have identical sample headers:

- mRNA sample count: 99
- Protein sample count: 99
- Intersection: 99
- mRNA-only samples: 0
- protein-only samples: 0
- Same sample order: `true`

This is strong enough to support a deterministic aligned-matrix recipe without
sample-id reconciliation heuristics.

## Decision

`gbm_cptac_2021` is fetchable enough to become a concrete deposit recipe.

Recommended primary fetch route:

1. Read DataHub LFS pointers from the public GitHub raw URLs.
2. Parse and verify `oid sha256` and `size`.
3. Use the GitHub LFS batch API to obtain signed direct download URLs.
4. Download the two objects.
5. Verify byte count and SHA-256 exactly match the pointer metadata.
6. Fail early if a downloaded file is still an LFS pointer.
7. Parse both matrices and require exact nonempty sample intersection.

Recommended secondary validation route:

- Query cBioPortal study/profile/sample-list endpoints to confirm the current
  public metadata still advertises the expected study, profiles, sample counts,
  and import date.
- Fetch a small cBioPortal molecular-data slice for a few sentinel genes as a
  source sanity check, not as the full matrix transport.

## Recipe Contract

The next implementation slice should create:

- `~/d/science-commons/datasets/cptac-gbm-2021-proteogenomics/entity.md`
- A recipe under the same commons dataset directory.
- Generated data under `~/d/science-commons-data/cptac-gbm-2021-proteogenomics/`,
  never under git-tracked commons metadata.

Minimum recipe behavior:

1. Require an explicit output directory or `SCIENCE_COMMONS_DATA_ROOT`.
2. Fetch cBioPortal metadata and record `importDate`.
3. Fetch DataHub LFS pointer metadata for mRNA and protein files.
4. Download LFS payloads through the batch API.
5. Verify byte count, SHA-256, and non-pointer payload status.
6. Parse mRNA and protein matrices.
7. Require 99 aligned sample ids for the current package, or fail with a
   clear mismatch report if cBioPortal/DataHub changes.
8. Emit normalized resources:
   - `expression/mrna_fpkm_uq.parquet`
   - `proteomics/protein_abundance_log2.parquet`
   - `metadata/samples.parquet`
   - `reports/build-summary.json`
9. Preserve source ids and unmodified raw payload copies under a non-git data
   directory.

## Sources Checked

- cBioPortal study endpoint:
  `https://www.cbioportal.org/api/studies/gbm_cptac_2021`
- cBioPortal molecular profiles endpoint:
  `https://www.cbioportal.org/api/studies/gbm_cptac_2021/molecular-profiles`
- cBioPortal sample lists endpoint:
  `https://www.cbioportal.org/api/studies/gbm_cptac_2021/sample-lists`
- cBioPortal molecular data endpoint:
  `https://www.cbioportal.org/api/molecular-profiles/<profile-id>/molecular-data/fetch`
- DataHub mRNA raw pointer:
  `https://raw.githubusercontent.com/cBioPortal/datahub/master/public/gbm_cptac_2021/data_mrna_seq_fpkm.txt`
- DataHub protein raw pointer:
  `https://raw.githubusercontent.com/cBioPortal/datahub/master/public/gbm_cptac_2021/data_protein_quantification.txt`
- GitHub LFS batch endpoint:
  `https://github.com/cBioPortal/datahub.git/info/lfs/objects/batch`
