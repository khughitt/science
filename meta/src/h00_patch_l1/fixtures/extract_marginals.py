# science:code
# status: tool
# task_ids: [t066]
# science:end
"""Enrich the q14 slice fixture with the marginals a bias-CORRECTION needs (t066).

t065 only needed per-cell co-occurrence (`cooc`) and `ubiquity`. The t066
latent-construct correction (PMI / two-way independence residual) additionally
needs the *marginals* of the contingency table:

  * per-gene total  C_g.  = sum of the gene's row over all diseases  (gene attention)
  * per-disease total C_.d = sum of the disease's column over all genes (disease attention)
  * grand total      N     = sum of the whole matrix

These are the publication-attention nuisance axes the correction subtracts.

This is a CROSS-PROJECT extraction: it reads pan-disease's co-occurrence matrix
(pandas + the 60 MB feather live there) and writes the meta fixture. Run it from
the pan-disease env, from the pan-disease project root:

    cd ~/d/health/comparisons/pan-disease
    uv run --frozen python \
      ~/d/science/meta/src/h00_patch_l1/fixtures/extract_marginals.py

The edit is ADDITIVE — it only adds `gene_marginal`, `disease_marginal`, and
`grand_total`; every field t065 reads is preserved, so t065 tests still pass.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

FIXTURE = Path(__file__).resolve().parent / "q14_slice.json"
MATRIX = Path(
    "/data/packages/lit-explore/pubtator/disease-similarity/2026-03-17/"
    "gene_disease_comat_filtered.feather"
)


def main() -> None:
    fixture = json.loads(FIXTURE.read_text())
    df = pd.read_feather(MATRIX).set_index("entrez_id")
    gene_total = df.sum(axis=1)          # C_g.  (indexed by entrez_id, int)
    disease_total = df.sum(axis=0)       # C_.d  (indexed by MESH col)
    grand_total = int(df.values.sum())   # N

    fixture["grand_total"] = grand_total
    for mesh_id, disease in fixture["diseases"].items():
        disease["disease_marginal"] = int(disease_total[mesh_id])
        for gene in disease["genes"]:
            ez = int(gene["entrez"])
            gene["gene_marginal"] = int(gene_total.loc[ez])
            # sanity: the stored cell count must match the live matrix
            cell = int(df.loc[ez, mesh_id])
            if cell != gene["cooc"]:
                raise SystemExit(
                    f"cell mismatch {gene['symbol']}/{mesh_id}: "
                    f"fixture {gene['cooc']} != matrix {cell}"
                )

    prov = fixture["provenance"]
    prov["marginals_added"] = "2026-06-01 for t066 latent-construct correction"
    prov["grand_total_def"] = "N = sum of the full filtered co-occurrence matrix"
    prov["gene_marginal_def"] = "C_g. = row sum over all diseases (gene attention)"
    prov["disease_marginal_def"] = "C_.d = column sum over all genes (disease attention)"

    FIXTURE.write_text(json.dumps(fixture, indent=2) + "\n")
    print(f"enriched {FIXTURE} | N={grand_total:,} | "
          f"{sum(len(d['genes']) for d in fixture['diseases'].values())} genes")


if __name__ == "__main__":
    main()
