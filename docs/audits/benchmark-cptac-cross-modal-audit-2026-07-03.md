# CPTAC Cross-Modal Benchmark Audit - 2026-07-03

## Scope

This audit follows up on the fallback rollup decision for:

- `dataset:cptac-proteogenomics#protein-rna-cross-modal`

The question was whether the current commons record can become a staged
deposit/recipe, or whether it should stay reference-only.

Current commons metadata:

- Record: `~/d/science-commons/datasets/cptac-proteogenomics/entity.md`
- `dataset_class: reference`
- `source_class: reference`
- Access verification: `landing-confirmed`
- Task support: `candidate`, reason `requires-study-specific-staging`
- Task: predict mass-spectrometry protein abundance from transcriptomic and
  genomic features.

Commands sampled:

```bash
PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark list --commons --format json
PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark tests --commons --format json --benchmark dataset:cptac-proteogenomics --project-root ~/d/cancer/cancer-types/multiple-myeloma
PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --commons --format json --benchmark dataset:cptac-proteogenomics --project-root ~/d/cancer/cancer-types/multiple-myeloma
```

The multiple-myeloma triage view reported 298 CPTAC rows:

- `blocked-or-reference`: 1 opportunity-relative row
- `fallback-diagnostic`: 297 fallback rows
- `readiness_label`: all `metadata-only`
- `dataset_class`: all `reference`
- `task_support_state`: all `candidate`

## Concrete Package Candidate

Recommended concrete package to stage next:

- cBioPortal study id: `gbm_cptac_2021`
- Title: Glioblastoma (CPTAC, Cell 2021)
- Proposed commons slug: `cptac-gbm-2021-proteogenomics`
- Proposed relation to current record: child/specific deposit derived from the
  umbrella `dataset:cptac-proteogenomics` reference record.

Why this package:

- It is explicitly CPTAC-generated and public in cBioPortal.
- It has 99 samples, with 99 mRNA RNA-seq samples and 99 mass-spectrometry
  samples according to the cBioPortal public API.
- It has concrete profile ids for both:
  - `gbm_cptac_2021_mrna`
  - `gbm_cptac_2021_protein_quantification`
- Its DataHub README states that the transformed source table included mRNA,
  protein, phosphoproteome, acetylome, lipidome, metabolome, methylation,
  mutation, and copy-number data.

## Source And Access Findings

Primary source facts:

- NCI GDC describes CPTAC as a proteogenomics program and states that CPTAC
  genomic data is in GDC while proteomic data is in PDC.
- GDC lists gene-expression quantification as open, while aligned RNA-seq reads
  and several sequencing products are controlled.
- cBioPortal documents three user download routes: study zip files from the
  datasets page, DataHub, and API slices.
- cBioPortal DataHub documents that study folders are available through git LFS
  and gives the `git lfs pull -I public/<study>` workflow.
- The DataHub license for this study is ODbL. A staged derivative must preserve
  attribution, keep derived datasets open, and carry the same license.

Local probes:

- `https://www.cbioportal.org/api/studies/gbm_cptac_2021` returned a public
  study with 99 samples, 99 RNA-seq samples, and 99 mass-spectrometry samples.
- `https://www.cbioportal.org/api/studies/gbm_cptac_2021/molecular-profiles`
  returned mRNA and protein profiles, including
  `gbm_cptac_2021_mrna` and `gbm_cptac_2021_protein_quantification`.
- Raw GitHub DataHub URLs for the mRNA and protein data files returned git LFS
  pointer files:
  - `data_mrna_seq_fpkm.txt`: LFS object size `29693169`
  - `data_protein_quantification.txt`: LFS object size `6852651`
- The direct historical tarball URL
  `https://cbioportal-datahub.s3.amazonaws.com/gbm_cptac_2021.tar.gz`
  returned S3 `AccessDenied` during this audit.
- A scoped DataHub clone completed, but `git -c lfs.fetchexclude= lfs pull -I
  public/gbm_cptac_2021` did not complete within the audit window and was
  interrupted. The checked-out data files remained LFS pointers.

## Decision

Do not convert `dataset:cptac-proteogenomics` itself into a deposit.

Keep the umbrella CPTAC record as:

- `dataset_class: reference`
- `task_support.state: candidate`
- `task_support.reason: requires-study-specific-staging`

Reason: it describes a portal/program-level benchmark surface, not one concrete
stageable package. Converting it directly would collapse study selection,
access verification, and package layout into a misleading runnable claim.

Create a separate concrete deposit candidate for `gbm_cptac_2021` if we decide
to implement staging. That deposit should be explicit that it is a cBioPortal
DataHub-derived CPTAC GBM package, not the whole CPTAC proteogenomics corpus.

Recommended implementation status for `gbm_cptac_2021`:

- Candidate can become a staged deposit/recipe.
- Do not mark it runnable until a recipe successfully fetches the LFS payload or
  API slices and materializes aligned mRNA/protein matrices.
- Use ODbL in the commons metadata, with attribution and share-alike notes.

## Proposed Deposit Shape

Suggested commons record:

- `id: dataset:cptac-gbm-2021-proteogenomics`
- `title: "CPTAC GBM proteogenomics (cBioPortal, Cell 2021)"`
- `dataset_class: deposit`
- `source_class: derived`
- `license: ODbL-1.0`
- `access.level: public`
- `access.availability: available`
- `access.verification_method: metadata-confirmed` until the recipe fetches and
  validates payload files; then promote to a stronger method.
- `benchmark.source_datasets: ["dataset:cptac-proteogenomics"]`
- `benchmark.modalities`: `proteomics`, `bulk-rna-seq`, `genomics`,
  `multimodal`
- `benchmark.signal_types`: `cross-sectional`, `multi-omic`
- Task id can remain `protein-rna-cross-modal`, but the parent dataset id should
  make the cancer/study context explicit.

Minimum recipe contract:

1. Fetch `gbm_cptac_2021` metadata and data through cBioPortal DataHub git LFS,
   or through cBioPortal API slices if full LFS download remains unreliable.
2. Verify that `data_mrna_seq_fpkm.txt` and `data_protein_quantification.txt`
   are real payloads, not LFS pointers.
3. Load sample ids from both matrices and require a nonempty sample
   intersection.
4. Emit normalized resources:
   - `expression/mrna_fpkm_uq.parquet`
   - `proteomics/protein_abundance_log2.parquet`
   - `metadata/samples.parquet`
   - `reports/build-summary.json`
5. Record the exact DataHub commit or cBioPortal API import date used.
6. Fail early if the download path returns pointers, access-denied responses, or
   empty sample intersections.

## Consequences For Benchmark Reports

Expected behavior before staging:

- `dataset:cptac-proteogenomics#protein-rna-cross-modal` remains
  `metadata-only` and candidate-supported.
- The broad fallback rows remain diagnostic only.

Expected behavior after a successful `gbm_cptac_2021` deposit is added:

- `dataset:cptac-gbm-2021-proteogenomics#protein-rna-cross-modal` can become
  `stage-needed` if a recipe exists but no local payload is staged.
- It can become `runnable` only after local datapackage resources exist.
- The umbrella `dataset:cptac-proteogenomics` should remain reference-class as a
  catalog entry for other future CPTAC studies.

## Sources Checked

- NCI GDC CPTAC overview:
  `https://gdc.cancer.gov/about-gdc/contributed-genomic-data-cancer-research/clinical-proteomic-tumor-analysis-consortium-cptac`
- cBioPortal downloads documentation:
  `https://docs.cbioportal.org/downloads/`
- cBioPortal DataHub repository:
  `https://github.com/cBioPortal/datahub`
- cBioPortal DataHub `gbm_cptac_2021` README:
  `https://github.com/cBioPortal/datahub/blob/master/public/gbm_cptac_2021/README.md`
- cBioPortal API study endpoint:
  `https://www.cbioportal.org/api/studies/gbm_cptac_2021`
- cBioPortal API molecular profiles endpoint:
  `https://www.cbioportal.org/api/studies/gbm_cptac_2021/molecular-profiles`
- AWS Open Data CPTAC-3 registry:
  `https://registry.opendata.aws/cptac-3/`

## Recommendation

Next implementation slice:

1. Add a new commons dataset record for
   `dataset:cptac-gbm-2021-proteogenomics` as a deposit candidate.
2. Write a recipe that first tries the documented DataHub git-LFS path and
   validates that downloaded files are real payloads.
3. If LFS transfer remains unreliable, fall back to cBioPortal API extraction
   for the mRNA and protein profiles.
4. Keep `dataset:cptac-proteogenomics` as the program-level reference record and
   link the concrete GBM deposit through `benchmark.source_datasets`.
