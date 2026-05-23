---
name: data-genomics-copy-number-sv-qa
description: Use when ingesting or auditing copy-number segments, structural-variant/breakpoint calls, or AmpliconArchitect/AmpliconClassifier focal-amplicon and ecDNA outputs, from bulk WGS/WES or per-cell scWGS (e.g. DLP+).
---

# Copy-Number, Structural-Variant, and Amplicon QA

Use when ingesting or auditing copy-number (CN) segments, structural-variant
(SV) / breakpoint calls, or AmpliconArchitect (AA) / AmpliconClassifier (AC)
focal-amplicon and ecDNA outputs — from bulk WGS/WES or per-cell single-cell
WGS (e.g. DLP+).

CN, SV, and amplicon calls share one root QA problem: every call is conditional
on a ploidy/purity model, a calling-pipeline version, and an assay fragmentation
profile, any of which can turn an artifact into apparent biology. AA/AC outputs
add a second problem: they are *derived* from the same CN+SV calls, so they are
not independent confirmation of them.

## Acquisition Checklist

1. **Lock the coordinate system.** Genome build, chromosome naming, and whether
   segment coordinates are 0- or 1-based. Never join GRCh37 and GRCh38
   breakpoints or segments without liftover plus post-liftover validation.
2. **Name the unit of analysis.** Bulk sample, per-cell, clone, or patient. Cells
   from one tumor are not independent; bulk calls are mixtures over an unknown
   clone composition. State the unit the endpoint is computed over.
3. **Record the ploidy/purity model.** Every absolute-CN value is conditional on
   an estimated tumor purity and ploidy. Store the caller, its version, and the
   purity/ploidy estimate per sample. CN 8 at ploidy 2 and at ploidy 4 are
   different biological claims.
4. **Record per-cell binning / segmentation parameters.** For scWGS, the bin size
   and segmentation method set the floor on detectable focal events and the
   discreteness of per-cell CN. Bins must be identical across cells being
   compared.
5. **Record SV breakpoint support and filters.** Split-read / discordant-pair
   support, mapping-quality filters, and blacklist/centromere masking. A
   breakpoint with single-end support near a repeat is not a confirmed SV.
6. **Pin the AA/AC version and reference.** AmpliconArchitect and
   AmpliconClassifier change amplicon-type logic across versions. Store both
   versions, the reference build, the CN/seed threshold used to define amplified
   intervals, and the AC amplicon-type confidence.

## Minimum QA Tables

| Artifact | Required fields |
|---|---|
| `cn_segments` | sample_or_cell_id, chrom, start, end, copy_number, caller, purity, ploidy |
| `sv_breakpoints` | sample_id, chrom1, pos1, chrom2, pos2, sv_type, support, pass_filter |
| `amplicon_calls` | sample_id, amplicon_id, amplicon_type, intervals, aa_version, ac_version, ac_confidence |
| `ploidy_purity_audit` | sample_id, purity, ploidy, method, low_confidence_flag |
| `percell_binning_audit` | cell_id, bin_size, n_bins, segmentation, qc_status |

## Common Failure Modes

- **AA/AC version + ploidy-correction drift.** Amplicon type (ecDNA, BFB,
  complex, linear) and CN thresholds shift across AA/AC releases and across the
  purity/ploidy estimate used. Re-running with a different version or ploidy can
  reclassify ecDNA as linear and vice versa.
- **FFPE fragmentation.** FFPE damage shortens fragments and inflates artifactual
  breakpoints while suppressing true long-range amplicon reconstruction. FFPE and
  fresh-frozen amplicon calls are not comparable without an explicit
  fragmentation/quality covariate.
- **Per-cell CN-binning choices.** Coarse bins miss focal amplicons; fine bins
  inflate per-cell CN variance. A "convergent amplification" signal can be a
  binning artifact when bins differ across compared cells.
- **Classifier-confidence handling.** AC assigns amplicon types with a
  confidence; ecDNA-vs-HSR-vs-BFB-vs-linear calls near the threshold should carry
  the confidence forward, not be hardened to a categorical label.
- **AA/AC pipeline non-independence.** AC consumes AA output, which consumes the
  CN+SV calls. Agreement among AA, AC, and the CN caller is expected by
  construction and is not independent corroboration of an amplicon.
- **GC / mappability waviness.** Uncorrected GC and mappability bias produces wavy
  CN profiles read as low-amplitude gains/losses.

## Analysis Rules

- Never report an absolute CN without the purity/ploidy it is conditional on.
- Never treat AA and AC (or AA/AC and the CN caller) as independent confirmation
  of an amplicon; they share inputs by construction.
- Never compare amplicon detection across FFPE and fresh-frozen samples without a
  fragmentation/quality adjustment or restriction.
- Keep per-cell bin size and segmentation fixed across all cells in a contrast.
- Carry AC amplicon-type confidence into downstream verdicts; do not harden
  near-threshold ecDNA/HSR/BFB calls.

## Halt-On Conditions

- Tumor purity/ploidy is unavailable or low-confidence for samples whose absolute
  CN drives the endpoint.
- AA/AC versions are unpinned or mismatched across the cohort.
- FFPE and fresh-frozen samples are mixed in an amplicon contrast without
  adjustment.
- Per-cell bins are incomparable across cells being contrasted.

## Output Package

Generate a `datapackage.json` for this directory; see [`../frictionless.md`](../frictionless.md).

```
data/processed/<cohort_id>/cn_sv_amplicon_qa/
|-- cn_segments.parquet
|-- sv_breakpoints.parquet
|-- amplicon_calls.parquet
|-- ploidy_purity_audit.parquet
|-- percell_binning_audit.parquet
`-- cohort_audit.json
```

The audit should state the purity/ploidy model behind every absolute CN, the
AA/AC versions, and which amplicon calls share inputs (and are therefore not
independent).

## Companion Skills

- [`SKILL.md`](./SKILL.md) — genomics data-ingestion hub.
- [`somatic-mutation-qa.md`](./somatic-mutation-qa.md) — callable-territory and missing-vs-zero rules that also govern CN/SV denominators.
- [`../../statistics/population-genetics-likelihood.md`](../../statistics/population-genetics-likelihood.md) — downstream selection/segregation modelling that consumes per-cell CN.
- [`../../statistics/power-floor-acknowledgement.md`](../../statistics/power-floor-acknowledgement.md) — focal-event and per-cell contrasts are typically low-power.
- [`../../statistics/sensitivity-arbitration.md`](../../statistics/sensitivity-arbitration.md) — ploidy-model and AA/AC-version variants are the canonical sensitivity pair.
