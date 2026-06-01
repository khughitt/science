---
id: "interpretation:h00-t066-latent-correction-2026-06-01"
type: "interpretation"
title: "Latent-construct correction: subtracting the publication-attention axis on the q14 slice"
hypothesis: "hypothesis:h00-working-model"
artifact: "meta/src/h00_patch_l1/latent.py"
related:
  - task:t066
  - task:t065
  - task:t067
  - task:t070
created: "2026-06-01"
updated: "2026-06-01"
---

# Latent-construct bias correction (t066)

RFC §8.1 / R3, executed. t065 *discounted* publication gravity — it collapsed
the shared-source double-count so one corpus-wide mechanism could not be counted
N times — but the [t065 interpretation](h00-l1-patch-prototype-2026-06-01.md)
was explicit that this is **not** correction: each surviving co-occurrence signal
was still biased by how much its gene is studied at all, and "true correction is
the §8.1 / `task:t066` latent-construct model." This is that model. Code:
`meta/src/h00_patch_l1/latent.py`; tests: `meta/tests/test_h00_latent.py` (9, all
green); demo View D: `PYTHONPATH=src uv run python -m h00_patch_l1`.

## The measurement model

Observed literature co-occurrence `C_gd` is treated as a **biased measurement**
of the latent biological association `A_gd`, the bias being publication
**attention** — how much gene `g` and disease `d` are studied at all:

```
log E[C_gd] = log N + α_g + β_d + A_gd
α_g = log(C_g. / N)    gene attention    (publication gravity, gene axis)
β_d = log(C_.d / N)    disease attention (publication gravity, disease axis)
```

The two-way independence null (`A_gd = 0`) is `E0 = C_g.·C_.d / N`. The corrected
association is the log-scale residual — exactly **pointwise mutual information**,
the attention axes subtracted off:

```
PMI(g,d) = log(C_gd / E0) = log(C_gd·N / (C_g.·C_.d)) = log(C_gd/N) − α_g − β_d
```

`PMI > 0`: co-occurs *more* than attention predicts → specific. `PMI ≈ 0`:
explained by attention. `PMI < 0`: co-occurs *less* than attention predicts (a
universal gene "diluted" across the whole corpus). The marginals (`C_g.`, `C_.d`,
`N`) were extracted from the same pan-disease matrix as the t065 cells
(`fixtures/extract_marginals.py`, additive — t065 tests unchanged).

This **reuses the shipped belief machinery** (D-005): the correction only decides
*whether a literature unit is specific support at all*; `aggregate_belief` /
`belief_scalar` / the opinion view then run unchanged on the survivors.

## Results — the correction subtracts what the discount only discounted

For **both** focal diseases, PMI cleanly separates the two ends of the attention
spectrum the slice was built to contrast:

| gene class | CMT PMI range | HSP PMI range | specific (PMI>0)? |
|---|---|---|---|
| 7 curated panel genes (specific biology) | +2.52 … +4.96 | +3.16 … +5.52 | **all 7 yes** |
| 10 universal publication-gravity genes | −1.89 … −0.66 | −1.06 … −0.41 | **all 10 no** |

**The headline t065 could not claim — a flipped ranking.** Raw co-occurrence
ranks pure-attention genes *above* true causal genes. In HSP, `TNF` has the
single highest raw count of **any** gene (253, above every panel gene) yet is the
least disease-specific; the panel gene `CYP7B1` has the lowest raw count (39).
Correction reverses them: `TNF` → PMI **−0.95** (dropped), `CYP7B1` → **+3.16**
(kept). The attention axis, once subtracted, sends every universal gene negative.

**The progression, on real numbers.** The patch-claim support fusion sharpens at
each step:

| | supports counted | what happens to universal genes |
|---|---|---|
| naive | 17 | counted individually (over-confident) |
| discounted (t065) | 8 | collapsed to **one** shared-source unit, but still counted |
| **corrected (t066)** | **7** | **PMI ≤ 0 → not specific support at all; dropped** |

Correction is strictly more aggressive than the discount: 10 attention-only genes
contribute *nothing* after the axis is removed, versus the single residual unit
the t065 reduction left behind.

## What this tells the RFC forks

- **§8.1 / R3 (latent construct): the correction is real, and it is the minimal
  faithful instance.** PMI is the closed-form, rank-1 (saturated-marginal)
  instance of the Poisson GLM `log E[C] = α_g + β_d + A`. It needs only the
  marginals, is fully interpretable, and *subtracts* the bias rather than flagging
  it. It composes with t034: the latent association `A_gd` is a
  `latent_variable_hypothesis`-role construct; the proxy `C_gd` is its biased
  measurement.
- **§2 (glue / latent common axis): the same object.** `α_g` (the per-gene
  attention vector) **is** the data-driven latent nuisance axis named in the patch
  schema's GLUE block. A low-rank factorization of the PPMI matrix is the shared
  latent *common coordinate* that connects patches — i.e. the bias-correction
  (R3) and the common-space glue (§2) are two reads of one decomposition. Building
  that factorization is the explicit successor (`task:t067`, patch-latent /
  federation), noted, not built here.

## Limitations (carry-forward, not defects)

- **Clean separation is partly a property of the slice.** The 7-vs-10 step is
  decisive *because the slice contrasts the two extremes* — curated specific genes
  vs the canonical publication-gravity set (TNF, IL6, …). Correct behavior at both
  ends is necessary but **not sufficient**: whether PMI cleanly separates the
  *ambiguous middle* is untested and needs the full 18,206×3,831 matrix. So
  **`PPMI > 0` is a correction, not a calibrated panel classifier** — do not read
  the perfect 7/7 ∧ 10/10 as a recall/precision claim. Full-matrix ranking and
  held-out-panel validation are `task:t070` (and overlap pan-disease's recall@K /
  cluster-mate-AUC machinery — the natural cross-project proving ground).
- **No sampling-variance guard.** Rare cells have high-variance PMI; the
  low-count panel gene `CYP7B1` (cooc 39) gets a high point estimate with a wide
  interval. The sign-based gate is robust to this, but any *fine* PMI ranking or a
  near-zero threshold is not — a shrinkage / Poisson-significance guard is part of
  `task:t070`.
- **The PMI=0 boundary is the assumption-light choice (PPMI), not a calibrated
  decision threshold.** Finer PMI→`strength` mapping is unexamined and ties into
  the t069 evidence-field-mapping sensitivity surface.
- **Two-way independence ignores higher-order structure** — gene-gene co-study,
  disease-ontology proximity, corpus temporal drift. The full Poisson-GLM /
  low-rank latent-factor MLE (§2 glue, t067) is the generalization.
- **`has_measurement_model` is kept `False`** for corrected units (conservative):
  whether the correction *earns* measurement-model status (and so lifts the gated-
  proxy penalty in belief) is a belief-semantics decision, deliberately not made
  here.
- **Still a real extracted slice, not federated live linkage** — same scope as
  t065; the cross-project reference primitive (`task:t068`) stays load-bearing.
