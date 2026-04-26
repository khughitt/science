---
name: data-functional-genomics-qa
description: Use when working with CRISPR/RNAi screens, DepMap dependency data, perturb-seq, LINCS/L1000 signatures, drug-response matrices, viability assays, or perturbation replication analyses.
---

# Functional Genomics QA

Use when working with CRISPR/RNAi screens, DepMap dependency data, perturb-seq,
LINCS/L1000 signatures, drug-response matrices, viability assays, or
perturbation replication analyses.

Functional-genomics datasets mix biology with assay sensitivity, cell-line
context, guide quality, dose, time, batch, and viability artifacts. QA should
separate perturbation effect from measurement and growth confounding before
ranking genes or drugs.

## Pre-Flight Checklist

1. **Define the perturbation unit.** Guide, shRNA, gene, compound, dose, time,
   cell line, donor, or perturbation signature.
2. **Record assay and normalization.** MAGeCK, CERES, Chronos, DEMETER2,
   z-score, robust z-score, MODZ, AUC, IC50, EC50, GR metric, or raw viability.
3. **Check replicate structure.** Technical replicate, biological replicate,
   independent screen, batch, plate, and cell-line lineage are different units.
4. **Preserve perturbation metadata.** Guide sequence, target gene, on-target
   score, copy-number segment, compound identity, dose, exposure time, vehicle,
   and batch.
5. **Audit cell-line identity.** STR, disease lineage, subtype, mutation status,
   expression state, growth rate, and culture conditions can dominate results.
6. **Separate discovery and validation.** A screen hit, public dependency score,
   and independent perturbation experiment are different evidence layers.

## CRISPR / RNAi Screen QA

| Check | Failure mode |
|---|---|
| Guide count per gene | single-guide hits are fragile |
| Non-targeting / safe-target controls | normalization or toxicity failure |
| Essential-gene controls | weak dynamic range or low infection/editing |
| Copy-number correlation | false dependencies from Cas9 cutting amplified loci |
| Guide concordance | off-target or guide-specific artifact |
| Batch / plate effects | positional or processing artifacts |
| Lineage-stratified effects | pan-essential vs lineage-specific dependency |

For gene-level calls, keep guide-level evidence available. Do not hide
discordant guides behind a gene-level score.

## LINCS / L1000 and Signature QA

- Record perturbagen, cell line, dose, time, build, and signature-generation
  method.
- Treat inferred genes separately from measured landmark genes.
- Compare signatures within matched cell line, dose, and time where possible.
- Use replicate-collapsed signatures only when replicate quality metrics pass.
- Check whether connectivity is driven by generic stress, cell cycle, or
  viability rather than the intended pathway.
- Avoid interpreting a single high-connectivity cell-line result as a general
  mechanism without replication.

## Drug-Response QA

- Prefer GR metrics when growth-rate differences are a likely confound.
- Keep dose-response curve fit diagnostics, not only AUC/IC50 summaries.
- Flag curves with poor fit, incomplete response, or activity outside tested
  dose range.
- Stratify by lineage and baseline expression/mutation context before making
  pan-cancer claims.
- Separate cytostatic viability effects from pathway-specific mechanism.

## Common Failure Modes

- **Dependency equals expression.** A gene is highly expressed in a lineage and
  appears essential because lineage is confounded with the phenotype.
- **Copy-number false positive.** CRISPR cutting toxicity inflates dependency in
  amplified regions.
- **Generic toxicity signature.** Perturbation produces stress/cell-cycle
  effects that mimic pathway reversal.
- **Dose mismatch.** Replication fails because dose/time do not match the
  original biology.
- **Batch-as-biology.** Screen batch or plate position tracks treatment group.
- **Hit-list circularity.** A validation panel is chosen from the same data used
  to define success.

## Minimum Artifacts

Generate a `datapackage.json` for this directory; see [`frictionless.md`](./frictionless.md).

```
results/<analysis>/functional_genomics_qa/
|-- input_manifest.json
|-- perturbation_metadata.parquet
|-- replicate_qc.parquet
|-- normalization_manifest.json
|-- guide_or_probe_level_results.parquet
|-- gene_or_signature_level_results.parquet
|-- batch_and_control_diagnostics.parquet
|-- sensitivity_results.parquet
`-- qa_summary.md
```

## Reporting

State:

- perturbation unit and independent unit,
- normalization method and version,
- control performance,
- batch/plate handling,
- guide/probe concordance,
- lineage/cell-line context,
- dose/time comparability,
- verdict downgrades caused by toxicity, growth, copy number, or weak controls.
