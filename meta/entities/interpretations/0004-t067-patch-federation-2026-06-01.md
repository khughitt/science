---
kind: interpretation
title: 'Patch federation: the bias-corrected latent coordinate as data-driven glue'
status: active
created: '2026-06-01'
updated: '2026-06-01'
id: interpretation:0004-t067-patch-federation-2026-06-01
hypothesis: hypothesis:0007-working-model
artifact: science_tool.model.federation (machinery); pan-disease code/scripts/h00_patch_demo.py
  (application)
related:
- task:t067
- task:t066
- task:t068
- task:t070
---

# Patch federation via the dual common space (t067)

RFC §2 / R1, executed. t066 *subtracted* the publication-attention axis per cell
(PMI). t067 **factorizes the resulting PPMI matrix into a shared latent
coordinate** and uses proximity in that coordinate to *connect patches* — the
data-driven half of the §2 glue ("ontologies where identities are known;
bias-corrected latent axes where they aren't"). Code:
the glue primitives (cosine, `FederationLink`, glue-kind, TriG emission) are
`science_tool.model.federation` (framework; graduated per **D-007**), driven by
the pan-disease application `code/scripts/h00_patch_demo.py` (`disease_federation`,
which computes the symbolic Jaccard from the panels); demo:
`uv run python code/scripts/h00_patch_demo.py`. (Originally prototyped in the
now-retired `meta/src/h00_patch_l1/glue.py`.)

## The construction

A truncated SVD (`k=30`) of the PPMI matrix (18,206 genes × 3,831 diseases) gives
each disease an embedding and each gene an embedding in one shared coordinate.
Two disease-patches relate by **cosine** in the disease coordinate; the gene
coordinate is the other half (genes federate too). The embeddings are extracted
once from pan-disease (`fixtures/extract_federation.py`, seeded, neighbors
recorded as the true global top-ranked — no cherry-picking) and consumed here
with stdlib. `glue.py` exposes both glue measures per patch pair:

- **symbolic** — Jaccard of the curated panel gene sets (HGNC symbols);
- **latent** — cosine in the PPMI-SVD coordinate;

and a `glue_kind` ∈ {`symbolic+latent`, `latent-only`} recording which actually
connects them.

## Results

**Latent glue federates patches that curated-gene overlap calls disconnected.**
CMT and HSP have **disjoint** panel gene sets (symbolic Jaccard = 0 — no shared
curated causal gene), yet in the bias-corrected coordinate HSP is CMT's **#2
nearest disease out of all 3,831** (cosine 0.95). The link is `latent-only`: the
data-driven axis carries a relationship the gene panels cannot express.

**The coordinate is biologically coherent — independently validated.** Every one
of CMT's and HSP's top-15 neighbors *that has a MeSH tree number* sits in **C10
(Nervous System Diseases)**; CMT's nearest neighbor is literally its own parent
class (Hereditary Sensory and Motor Neuropathy), and the neighborhoods are
Spinocerebellar Ataxias, Cerebellar Diseases, Motor Neuron Disease, etc. The
embedding **never saw the MeSH hierarchy** — it rediscovers the neurodegenerative
class structure from attention-corrected co-occurrence alone. Proximity is
*specific*: CMT–HSP cosine (0.95) exceeds every seeded-random control disease.

**The gene-coordinate half is structured too.** Same-biology panel genes cluster
(PMP22~MPZ = 0.93, both CMT myelin); a panel gene is far from a universal gene
(PMP22~TNF = 0.17); and the universal publication-gravity genes form *their own*
cluster (TNF~IL6 = 0.92) — a generic-attention region distinct from
disease-specific genes. So the universal genes neither drive disease proximity
nor scatter; they collect in one corner of the coordinate.

**Serialized as a multi-scale graph.** The federation is emitted as its own
`aggregate`-scale named graph holding a reified `PatchFederationLink` between the
two patch IRIs, carrying `symbolicJaccard`, `latentCosine`, and `glueKind`
(`patch ⊂ project ⊂ collection`, one scale above the disease patches).

## What this tells the RFC forks

- **§2 (federation / dual common space): the data-driven half works, and its real
  value is *reach*.** Curated gene panels exist for only a handful of diseases
  (the q14 set); the latent axis is computed from literature co-occurrence for
  **all 3,831** diseases — including the ~3,700 with no panel at all, where
  gene-level symbolic glue is *impossible*. That is the precise sense of "latent
  glue where identities aren't known": not that CMT and HSP are unrelatable
  (they are siblings in MeSH), but that the latent coordinate federates the vast
  majority of diseases that have **no curated gene identity** to align on.
- **§8.1 → §2 (one decomposition): confirmed.** The attention axis `α_g` (t066)
  and this common coordinate are two reads of the same PPMI matrix — correction
  and glue are not separate machinery.

## Limitations (carry-forward, not defects)

- **The correction's marginal effect on federation is modest — a sharpening, not
  a rescue.** At the disease-*profile* scale the attention bias is largely washed
  out by L2-normalization over the full gene space: HSP is already CMT's #4
  neighbor under *raw* co-occurrence (#2 after correction; cosine 0.78 → 0.95).
  This contrasts sharply with t066, where the same bias *decisively* flipped
  per-edge rankings (TNF over MPZ). **The bias bites hard at the per-association
  level and softly at the aggregate-profile level** — a real, honest finding about
  *where* publication gravity matters. The coordinate is built on the corrected
  matrix on principle (so it *cannot* be driven by attention), but correction is
  not what enables this federation.
- **Symbolic glue here is narrow.** It is panel-gene Jaccard, not full ontology
  alignment. CMT and HSP *are* ontologically related (both MeSH C10.500.300.x);
  the `latent-only` result is specifically about disjoint **gene** identifiers,
  not disease-level relatedness. Wiring MeSH/MONDO disease-ontology distance as
  the symbolic axis (and comparing it to the latent axis) is unexplored.
- **A single coherent neighborhood, not a cross-class stress test.** Two rare
  hereditary neuropathies that *should* be close were close. Whether the latent
  axis correctly separates *distant* classes, and how it compares to pan-disease's
  existing gene-axis / symptom-axis disease-disease similarity, is the natural
  next validation — it folds into the pan-disease disease track and the `task:t070`
  scale work. (One random control reached cosine 0.88: in 30-d normalized space
  cosine compresses, so **rank is a more reliable proximity signal than absolute
  cosine**.)
- **`k=30` captures ~22 % of variance** — robust for nearest-neighbor structure,
  but the coordinate is lossy; no claim it is the optimal/complete latent space.
- **Still a real extracted slice, not federated live linkage.** The embeddings are
  a static artifact; gluing patches across the live meta↔pan-disease boundary
  still needs the cross-project reference primitive (`task:t068`, load-bearing).
