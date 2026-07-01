# MMRF CoMMpass Staging Recipe Design

Date: 2026-07-01

## Goal

Define a conservative path for turning `dataset:mmrf-commpass` from a
metadata-only benchmark target into a runnable benchmark package without
overstating access or stageability.

The current commons record is correctly conservative:

- `dataset_class: pointer`
- task: `progression-risk`
- benchmark value: longitudinal multiple myeloma progression and response
  questions
- blocker: no concrete runtime artifact or task-specific manifest

This design does not promote the dataset to `deposit`. It defines the recipe,
manifest, package contract, and promotion gates required before that class
change is justified.

## Source Reality

MMRF CoMMpass is exposed through GDC and mirrored through the AWS Open Data
registry:

- AWS registry page: <https://registry.opendata.aws/mmrf-commpass/>
- GDC API: <https://api.gdc.cancer.gov/>

As of 2026-07-01, GDC status reported Data Release 45.0
(`2025-12-04`). A GDC files aggregation for project `MMRF-COMMPASS` reported:

- 995 cases
- 34,109 files
- 2,960 open-access files and 31,149 controlled-access files
- 859 open `Gene Expression Quantification` RNA-seq files
- RNA-seq, WXS, and WGS assay coverage, with raw/aligned sequencing data
  largely controlled

The AWS bucket is public-listable but organized by UUID-like file directories.
That makes it a transport mirror, not a sufficient semantic manifest. The GDC
metadata API should remain the source of truth for file selection, access
classification, case/sample linkage, and release provenance.

## Non-Goals

- Do not mark `dataset:mmrf-commpass` as `deposit` in this slice.
- Do not create a broad datapackage that points at the whole GDC/AWS project.
- Do not download or stage controlled-access files.
- Do not imply that longitudinal causal treatment effects are testable from
  this package alone.
- Do not add a new benchmark command. Existing `benchmark tests` and
  `benchmark test-triage` reports should consume the promoted dataset after the
  package exists.

## Recommended Slice

Build a recipe-first staging design for the existing `progression-risk` task.
The first runnable package should be compact and open-access only:

1. Open RNA-seq gene expression quantification.
2. Open clinical fields needed for progression, relapse, survival, censoring,
   or a clearly documented fallback outcome.
3. Open biospecimen/case/sample linkage needed to join expression rows to
   patient-level outcomes.
4. A held-out-patient split definition.

If the open clinical fields are insufficient to define progression or relapse
labels, the recipe must fail explicitly and keep the dataset as `pointer`.

## Recipe Inputs

The staging recipe should query GDC metadata rather than hand-maintaining file
UUIDs. The manifest-generation step should capture at least:

- `gdc_data_release`
- `project_id`
- `file_id`
- `file_name`
- `data_category`
- `data_type`
- `data_format`
- `experimental_strategy`
- `access`
- `case_id`
- `case_submitter_id`
- `sample_submitter_id`
- `sample_type`
- file size and checksum when available
- GDC download URL
- AWS S3 URI when derivable from the GDC/AWS mirror

The default file filter for the first package should be:

- `cases.project.project_id == "MMRF-COMMPASS"`
- `access == "open"`
- `data_type == "Gene Expression Quantification"`
- `experimental_strategy == "RNA-Seq"`
- `data_format == "TSV"`

Clinical and biospecimen records should be queried separately from the GDC
cases endpoint and joined by `case_id` / submitter identifiers. The recipe
should not assume every expression sample has a usable outcome.

## Package Contract

The staged package should be a compact analysis-ready directory, not a mirror of
the source project:

```text
mmrf-commpass-progression-risk/
  datapackage.yaml
  manifest/files.parquet
  manifest/query.json
  data/expression.parquet
  data/samples.parquet
  data/outcomes.parquet
  splits/heldout_patient_v1.parquet
  README.md
```

`expression.parquet`
: Expression values keyed by sample and gene. The recipe should choose one
  expression measure from the GDC augmented STAR output and document that choice.

`samples.parquet`
: Case/sample linkage, sample type, submitter ids, assay metadata, and any
  timepoint or disease-course fields available from open metadata.

`outcomes.parquet`
: Patient-level endpoint labels. Required fields are patient id, outcome value,
  censoring/status where applicable, and the source clinical fields used to
  derive the label.

`splits/heldout_patient_v1.parquet`
: Deterministic train/validation/test assignment by patient, with no sample from
  the same patient crossing split boundaries.

`datapackage.yaml`
: Runtime resources, schema hints, source URLs, GDC data release, recipe version,
  and validation summary.

## Validation Gates

The package is promotable only if all gates pass:

1. Manifest count for open RNA-seq gene expression files matches the GDC query
   total used by the recipe.
2. Every downloaded expression file is present and checksum-verified when a
   checksum is available.
3. Expression rows join to nonempty sample metadata.
4. A nonempty subset of expression-linked patients joins to usable outcome
   labels.
5. Held-out-patient splits are nonempty and have no patient leakage.
6. The package records the exact GDC data release and query filters.
7. The package can be loaded by a minimal smoke test that fits the task schema:
   feature table, target vector, held-out unit, metric, and baseline label.

If any gate fails, the recipe should emit a clear failure report and leave the
commons entity unchanged.

## Promotion Rule

Only after the staged package exists and passes the validation gates should the
commons record change:

- `dataset_class: pointer` -> `dataset_class: deposit`
- `tier: track` -> `tier: evaluate-next` or `use-now`, based on package quality
- add `datapackage: datapackage.yaml`
- update `access.verification_method` to a method that reflects verified runtime
  stageability, not just landing-page confirmation
- update limitations to distinguish open expression/clinical package limits from
  broader controlled-access CoMMpass limits

Before promotion, `science benchmark test-triage` should continue to report MMRF
rows as `metadata-only`. After promotion, the expected actionability change is
that MMRF rows move to `run-now` or `stage-next`, depending on whether the
package is committed as a local artifact or as a recipe-derived artifact.

## Error Handling

The recipe should fail early in these cases:

- GDC project query returns zero cases or zero open expression files.
- GDC data release cannot be recorded.
- clinical/outcome fields needed for `progression-risk` are unavailable in open
  metadata.
- expression samples cannot be linked to cases.
- requested files require controlled access.

Failures should be written as a durable report, but they should not mutate the
commons entity.

## Testing

Implementation should include:

- unit tests for GDC query filter construction;
- unit tests for manifest row normalization from representative GDC file/case
  payloads;
- validation tests for patient split leakage;
- a dry-run test that produces a manifest without downloading expression files;
- a smoke test over a tiny fixture package that exercises
  `progression-risk` task loading;
- a commons validation test proving `dataset:mmrf-commpass` remains `pointer`
  until a package exists.

## Implementation Defaults

The first implementation plan should use these defaults:

1. Place the reusable recipe and manifest contract in
   `science-commons/datasets/mmrf-commpass/`. Project-specific overlays can come
   later if multiple-myeloma needs narrower endpoint definitions.
2. Support two modes:
   - `--dry-run`: query GDC, write the manifest and validation report, but do
     not download expression files.
   - full mode: download and stage all open expression quantification files
     selected by the manifest.
3. Treat endpoint-field discovery as part of the dry run. The dry run should
   report the candidate clinical fields and fail promotion if no suitable
   progression, relapse, survival, or censoring fields are available.
4. Do not commit staged expression/outcome data by default. Commit the recipe,
   manifest schema, tiny test fixtures, and documentation. Stage full outputs
   outside git unless a future review explicitly decides the package is small
   enough to version.
