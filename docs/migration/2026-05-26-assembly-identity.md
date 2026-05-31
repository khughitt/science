# Declaring assembly identity (C1)

A coordinate-bearing dataset (`bio.rnaseq` / `bio.scrna` / `bio.cna`) declares
its assembly via the `bio.identity_context/1.0` extension instead of the
free-text `reference_genome` field.

Add `+bio.identity_context/1.0` to the dataset's `schema_profile` and:

```yaml
identity_context:
  taxon: 9606
  molecular_ids:
    gene: {namespace: hgnc, canonical: true}   # gene resolution lands in C2
  assembly:
    seqcol_digest: <SQ-collection-digest>       # canonical key (C-D2)
    label: GRCh38                               # advisory alias
    registry: dataset:assembly-registry
    resolution_status: resolved                 # or declared_unresolved (RCM-D2)
```

`seqcol_digest` must resolve in `dataset:assembly-registry` (exact equality,
RCM-D6) or carry `resolution_status: declared_unresolved`. Free-text
`reference_genome` is deprecated: `science validate` warns
(`identity.assembly-undeclared`) until migrated. Cross-assembly joins are
detected (`identity.cross-dataset-assembly-mismatch`); the liftover remedy
is implemented in C4b and requires exact pinned liftover provenance.
