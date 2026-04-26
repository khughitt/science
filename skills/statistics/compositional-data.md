# Compositional Data

Use when analyzing proportions, fractions, cell-type composition, microbiome
relative abundance, clone fractions, topic mixtures, deconvolution outputs, or
any features constrained to sum to one.

Compositional data are relative. Increasing one component forces at least one
other component to decrease, so ordinary correlations and regressions can create
artifacts even when absolute abundances are unchanged.

## First Questions

1. **What is the denominator?** Cells, reads, molecules, patients, tissue area,
   or inferred mixture mass. Changing the denominator changes the estimand.
2. **Is total abundance meaningful?** If totals carry biology, analyze totals
   separately from composition.
3. **Are zeros structural or sampling zeros?** A truly absent component differs
   from one missed because depth was low.
4. **What is the independent unit?** Cells inside a donor, genes inside a cell,
   and clones inside a patient are usually repeated measurements.
5. **Is composition a confounder or outcome?** Cell-type composition can explain
   a bulk-expression association without being the primary biological effect.

## Transform Choices

| Method | Use when | Caveat |
|---|---|---|
| CLR | Components are all positive after pseudocount; symmetric interpretation | Singular covariance; depends on pseudocount |
| ALR | A stable reference component exists | Results depend on reference choice |
| ILR | Need orthonormal coordinates | Harder to explain biologically |
| Multinomial / Dirichlet-multinomial | Counts and total depth are observed | Multinomial underfits overdispersion; Dirichlet-multinomial has limited covariance structure |
| Logistic-normal multinomial | Counts with correlated components or overdispersion | Needs more data and diagnostics |

Never apply log ratios without documenting the pseudocount or zero-handling
rule.

## QA Checks

- Plot total count/depth against each composition component.
- Check whether group differences persist under a model that handles total
  depth explicitly, such as binomial/multinomial likelihoods, offsets,
  precision weights, or depth-stratified sensitivity analyses.
- Repeat key contrasts with at least one alternative log-ratio basis.
- For deconvolution, validate against marker genes or known mixture controls.
- For scRNA-seq cell fractions, bootstrap or model at the donor/sample level,
  not the cell level.
- For bulk expression, test whether the signal is lost after adjusting for
  inferred cell composition or purity.

## Common Failure Modes

- **Closure-induced correlation.** Component A and B appear anticorrelated only
  because all components sum to one.
- **Rare-component instability.** Small denominators turn tiny count changes into
  large fraction swings.
- **Pseudocount sensitivity.** Results depend on the arbitrary zero replacement.
- **Composition/expression conflation.** A bulk gene signature tracks cell-type
  abundance, not per-cell expression.
- **Double use of proportions.** A fraction appears as both predictor and part
  of an outcome or adjustment set.

## Pseudobulk and Cell Fractions

For scRNA-seq:

- Aggregate expression to donor x cell type before bulk-style testing.
- Analyze cell-type fractions at donor/sample level.
- Include donor-level covariates and batch/channel where available.
- Report per-donor cell counts; low-cell donors should not carry the same
  precision as high-cell donors unless the model accounts for it.

For deconvolution:

- Treat inferred fractions as estimates with error, not ground truth.
- Keep method, reference panel, marker set, and scaling choices in provenance.
- Use negative controls: signatures for absent cell types should not dominate.

## Reporting

State:

- denominator and independent unit,
- zero-handling and pseudocount,
- transform/model family,
- total-depth handling,
- sensitivity to basis or pseudocount,
- whether the claim is about composition, absolute abundance, or per-unit
  expression.

## Minimum Artifacts

```
results/<analysis>/compositional_qa/
|-- input_manifest.json
|-- denominator_table.parquet
|-- zero_handling.json
|-- transformed_features.parquet
|-- total_depth_diagnostics.parquet
|-- basis_or_pseudocount_sensitivity.parquet
|-- model_config.yaml
`-- qa_summary.md
```

The summary should state which checks passed, which failed, and whether any
verdict was downgraded because composition, depth, or zero handling remained
ambiguous.
