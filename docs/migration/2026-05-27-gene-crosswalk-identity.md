# Declaring gene identity (C2)

A dataset whose data are gene-keyed declares its gene id space via the
`bio.identity_context/1.0` extension's `molecular_ids.gene` tier:

```yaml
identity_context:
  taxon: 9606
  molecular_ids:
    gene:
      namespace: hgnc_id        # hgnc_id | hgnc_symbol | entrez | ensembl
      canonical: true
      registry: dataset:gene-crosswalk-hgnc   # optional; this is the default
      resolution_status: resolved              # or declared_unresolved (RCM-D2)
```

`science validate` (check 2, declaration-level) verifies the namespace is
crosswalk-supported and that `registry` resolves to a `bio.gene_crosswalk/1.0`
collection (`member_key_column: gene_key`). A registry of the wrong type errors;
an unloadable one is reported INFO (cannot verify). This supersedes C1's
"gene resolution lands in C2" — `molecular_ids.gene` is now resolvable.

Payload-level mapping (resolving the actual gene-id column of a dataset) is **not**
done by `science validate`; use the resolver:

```python
from science_tool.commons.gene_crosswalk import to_canonical
m = to_canonical(taxon=9606, namespace="hgnc_symbol", gene_id="TP53")
# -> ResolvedGeneMatch(gene_key="9606|hgnc|HGNC:11998", ...), or
#    AmbiguousGeneMatch(candidates=(...)) when an input maps to >1 gene, or None.
```

The canonical key is the opaque composite `"<taxon>|hgnc|<hgnc_id>"`. Deprecated /
merged / withdrawn ids resolve with `status` + a `replacement_gene_key` forward
pointer (never auto-followed); split entries and shared symbols return
`AmbiguousGeneMatch` (no single key — never guess). Multi-species support is
deferred but the API is taxon-explicit from the start.
