---
name: research-annotation-curation-qa
description: Use when creating or auditing curated labels, extracted claims, taxonomy/facet assignments, model annotations, literature-derived tables, or LLM-assisted annotation workflows.
---

# Annotation and Curation QA

Use when creating or auditing curated labels, extracted claims, taxonomy/facet
assignments, model annotations, literature-derived tables, or LLM-assisted
annotation workflows.

Curation is measurement. The QA goal is to make the measurement model explicit:
what counts as a label, who or what assigned it, how disagreements are handled,
and which downstream claims are sensitive to annotation error.

## Pre-Flight Checklist

1. **Define the label schema.** Every label needs allowed values, inclusion
   criteria, exclusion criteria, and examples near decision boundaries.
2. **Separate source text from interpretation.** Store exact source spans or
   references separately from the normalized label.
3. **Record annotator identity.** Human, script, model name, prompt version, and
   date are provenance, not metadata clutter.
4. **Plan adjudication.** Decide before annotation which disagreements are
   resolved by consensus, senior review, majority vote, or retained uncertainty.
5. **Keep uncertainty.** Use explicit `uncertain`, `ambiguous`, or confidence
   fields instead of forcing labels that downstream analyses treat as truth.
6. **Version the schema.** A changed label definition creates a new measurement
   instrument. Record migrations.

## Agreement and Reliability

Use agreement metrics when two or more annotators label overlapping items:

| Situation | Useful metric |
|---|---|
| Two annotators, nominal labels | Cohen's kappa plus raw agreement |
| More than two annotators | Fleiss' kappa or Krippendorff's alpha |
| Imbalanced labels | Precision/recall by class plus prevalence |
| Hierarchical labels | Agreement at each hierarchy level |
| Continuous scores | ICC or rank correlation, depending on scale |

Kappa is prevalence-sensitive. Low kappa with high raw agreement can happen
when one class dominates; report both and inspect the confusion matrix.

## LLM-Assisted Annotation

- Freeze the prompt, model, decoding settings, and schema before batch runs.
- Run a calibration set with known or adjudicated labels.
- Require source-span extraction for claims, not just normalized labels.
- Audit hallucinated citations, unsupported spans, and overconfident labels.
- Re-run a small stability panel across seeds or model versions if the labels
  drive a verdict.
- Do not use the same LLM output as both label generator and independent
  evaluator.

## Common Failure Modes

- **Schema drift.** Early and late labels use different implicit definitions.
- **Boundary-case collapse.** Ambiguous cases are forced into common labels,
  inflating apparent certainty.
- **Adjudication leakage.** Reviewers see downstream results before resolving
  labels.
- **Prevalence trap.** A classifier gets high accuracy by predicting the common
  class.
- **Citation laundering.** A derived claim is treated as sourced because a
  nearby paper was cited, even though the paper does not support the label.
- **Circular validation.** Labels extracted from project prose are used to prove
  the project prose is correct.

## Minimum Artifacts

Generate a `datapackage.json` for this directory; see [`../data/frictionless.md`](../data/frictionless.md).

```
data/processed/<curation_task>/
|-- schema.json
|-- source_items.parquet
|-- annotations_raw.parquet
|-- adjudication_log.parquet
|-- labels_final.parquet
|-- agreement_report.md
`-- provenance.json
```

For claim extraction, include source document, section, source span, normalized
claim, evidence type, polarity, confidence, and adjudication status.

## Reporting

Report:

- schema version and label definitions,
- annotator/model provenance,
- calibration-set performance,
- agreement metrics and confusion matrix,
- adjudication rule,
- fraction uncertain or excluded,
- downstream analyses that depend on fragile labels.
