# Declaring protein identity (C3)

A dataset whose data are protein-keyed declares its protein id space via the
`bio.identity_context/1.0` extension's `molecular_ids.protein` tier:

```yaml
identity_context:
  taxon: 9606
  molecular_ids:
    protein:
      namespace: uniprot       # uniprot | uniprot_entry_name | ensembl_protein | refseq_protein
      canonical: true
      registry: dataset:protein-crosswalk-uniprot   # optional; this is the default
      resolution_status: resolved                    # or declared_unresolved (RCM-D2)
```

`science validate` (the protein check, declaration-level) verifies the namespace
is crosswalk-supported and that `registry` resolves to a `bio.protein_crosswalk/1.0`
collection (`member_key_column: protein_key`). A registry of the wrong type errors;
an unloadable one is reported INFO (cannot verify). The gene and protein checks
share one generalized core (`evaluate_tier_identity`).

Payload-level mapping (resolving the actual protein-id column of a dataset) is
**not** done by `science validate`; use the resolver:

```python
from science_tool.commons.protein_crosswalk import to_canonical
m = to_canonical(taxon=9606, namespace="uniprot", protein_id="P04217")
# -> ResolvedProteinMatch(protein_key="9606|uniprot|P04217", gene_key=("9606|hgnc|HGNC:5",), ...), or
#    AmbiguousProteinMatch(candidates=(...)) when an input maps to >1 protein, or None.
```

The canonical key is the opaque composite `"<taxon>|uniprot|<accession>"`. Each row
carries the C2 `gene_key` (protein→gene join). An isoform input (`P12345-2`) surfaces
the canonical protein with `match_type="isoform"` and the queried isoform preserved
(never collapsed). Merged secondary accessions resolve with `status="merged"` + a
`replacement_protein_key` forward pointer (never auto-followed). Shared RefSeq/Ensembl-
protein ids return `AmbiguousProteinMatch` (no single key — never guess). Multi-species
support is deferred but the API is taxon-explicit from the start.
