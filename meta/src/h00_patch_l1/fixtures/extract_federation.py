# science:code
# status: tool
# task_ids: [t067]
# science:end
"""Extract the data-driven latent COMMON axis that federates patches (t067).

t066 subtracted the publication-attention axis per cell (PMI). t067 factorizes
the resulting PPMI matrix into a low-rank shared coordinate (RFC §2 GLUE): each
disease gets an embedding, and two disease-patches relate by their proximity in
that coordinate — *without* re-inheriting literature bias, and *without* needing
shared symbolic identifiers. "Symbolic glue where identities are known; latent
glue where they aren't."

This records, honestly (no cherry-picking — neighbors are the true top-ranked
over ALL 3831 diseases):
  * CMT and HSP embeddings + their top-15 latent neighbors (mesh id, name, MeSH
    tree number for independent class validation, cosine);
  * the CMT↔HSP cosine and mutual ranks under BOTH the corrected (PPMI-SVD) and
    the RAW (uncorrected count) profiles — so the correction's *marginal* effect
    on federation can be reported, not assumed;
  * 10 seeded-random control diseases (proximity is specific, not universal);
  * gene-coordinate embeddings for the slice's panel + universal genes.

Cross-project extraction; run from the pan-disease env / project root:

    cd ~/d/health/comparisons/pan-disease
    uv run --frozen python \
      ~/d/science/meta/src/h00_patch_l1/fixtures/extract_federation.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize

HERE = Path(__file__).resolve().parent
SLICE = HERE / "q14_slice.json"
OUT = HERE / "q14_federation.json"
BASE = Path("/data/packages/lit-explore/pubtator/disease-similarity/2026-03-17/")

CMT, HSP = "MESH:D002607", "MESH:D015419"
K = 30          # latent dimensions
N_NEIGHBORS = 15
N_CONTROLS = 10
SEED = 0


def _tree(trees: dict, mesh: str) -> str:
    t = trees.get(mesh)
    return str(list(t)[0]) if t is not None and len(t) else ""


def main() -> None:
    df = pd.read_feather(BASE / "gene_disease_comat_filtered.feather").set_index("entrez_id")
    dis = df.columns.values
    terms = pd.read_feather(BASE / "mesh_terms.feather").set_index("mesh_id")
    names = terms["disease"].to_dict()
    trees = terms["tree_numbers"].to_dict()

    M = df.values.astype(np.float64)
    N = M.sum()
    cg = M.sum(1, keepdims=True)
    cd = M.sum(0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        pmi = np.log((M * N) / (cg * cd))
        pmi[~np.isfinite(pmi)] = 0.0
    ppmi = np.maximum(pmi, 0.0).astype(np.float32)        # genes x diseases

    svd = TruncatedSVD(n_components=K, random_state=SEED)
    Dn = normalize(svd.fit_transform(ppmi.T))             # diseases x K  (corrected)
    Gn = normalize(svd.components_.T)                     # genes x K     (gene coordinate)
    Rn = normalize(M.T)                                   # diseases x genes (raw, uncorrected)
    idx = {m: i for i, m in enumerate(dis)}
    var_explained = float(svd.explained_variance_ratio_.sum())

    def neighbors(mesh: str, embed: np.ndarray, k: int) -> list[dict]:
        cos = embed @ embed[idx[mesh]]
        order = np.argsort(-cos)
        out = []
        for j in order[1 : k + 1]:
            m = dis[j]
            out.append({"mesh_id": m, "name": names.get(m, m),
                        "tree": _tree(trees, m), "cosine": round(float(cos[j]), 4)})
        return out

    def rank_of(target: str, src: str, embed: np.ndarray) -> int:
        cos = embed @ embed[idx[src]]
        order = np.argsort(-cos)
        return int(np.where(order == idx[target])[0][0])

    focal = {}
    keep_embed = {}
    for mesh, lbl in [(CMT, "CMT"), (HSP, "HSP")]:
        focal[mesh] = {
            "label": lbl,
            "name": names.get(mesh, mesh),
            "tree": _tree(trees, mesh),
            "neighbors_corrected": neighbors(mesh, Dn, N_NEIGHBORS),
        }
        keep_embed[mesh] = [round(float(x), 6) for x in Dn[idx[mesh]]]
        for nb in focal[mesh]["neighbors_corrected"]:
            keep_embed.setdefault(nb["mesh_id"],
                                  [round(float(x), 6) for x in Dn[idx[nb["mesh_id"]]]])

    # Seeded-random controls drawn from diseases that are NOT focal/neighbor.
    excluded = set(keep_embed)
    pool = [m for m in dis if m not in excluded]
    rng = np.random.default_rng(SEED)
    controls = []
    for m in rng.choice(pool, size=N_CONTROLS, replace=False):
        controls.append({"mesh_id": m, "name": names.get(m, m), "tree": _tree(trees, m),
                         "cosine_to_cmt": round(float(Dn[idx[m]] @ Dn[idx[CMT]]), 4)})
        keep_embed[m] = [round(float(x), 6) for x in Dn[idx[m]]]

    # Gene-coordinate embeddings for the slice genes (panel + universal).
    slice_fix = json.loads(SLICE.read_text())
    gene_rows = {int(e): i for i, e in enumerate(df.index.values)}
    gene_embed = {}
    for disease in slice_fix["diseases"].values():
        for g in disease["genes"]:
            ez = int(g["entrez"])
            if g["symbol"] not in gene_embed and ez in gene_rows:
                gene_embed[g["symbol"]] = {
                    "in_panel": g["in_panel"],
                    "embedding": [round(float(x), 6) for x in Gn[gene_rows[ez]]],
                }

    out = {
        "provenance": {
            "source_matrix": "pan-disease gene_disease_comat_filtered.feather",
            "pubtator_version": "2026-03-17",
            "method": "PPMI (t066 attention-corrected) -> TruncatedSVD",
            "k": K, "seed": SEED, "var_explained_k": round(var_explained, 4),
            "extracted": "2026-06-01",
            "note": ("Real extracted slice for the t067 patch-federation prototype "
                     "(meta h00). Disease embeddings are L2-normalized so cosine = dot. "
                     "Neighbors are the true global top-ranked (no cherry-picking)."),
        },
        "n_diseases": int(len(dis)),
        "focal": focal,
        "cmt_hsp": {
            "cosine_corrected": round(float(Dn[idx[CMT]] @ Dn[idx[HSP]]), 4),
            "cosine_raw": round(float(Rn[idx[CMT]] @ Rn[idx[HSP]]), 4),
            "hsp_rank_among_cmt_corrected": rank_of(HSP, CMT, Dn),
            "hsp_rank_among_cmt_raw": rank_of(HSP, CMT, Rn),
        },
        "controls": controls,
        "disease_embeddings": keep_embed,
        "gene_embeddings": gene_embed,
    }
    OUT.write_text(json.dumps(out, indent=2) + "\n")
    print(f"wrote {OUT} | k={K} var={var_explained:.3f} | "
          f"CMT-HSP cos={out['cmt_hsp']['cosine_corrected']} "
          f"(corrected rank {out['cmt_hsp']['hsp_rank_among_cmt_corrected']}, "
          f"raw rank {out['cmt_hsp']['hsp_rank_among_cmt_raw']}) | "
          f"{len(keep_embed)} disease + {len(gene_embed)} gene embeddings")


if __name__ == "__main__":
    main()
