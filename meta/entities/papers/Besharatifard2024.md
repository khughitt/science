---
id: paper:Besharatifard2024
kind: paper
title: A review on graph neural networks for predicting synergistic drug combinations
status: active
paper_kind: review
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Besharatifard2024
related:
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0005-sequential-evidence-improves-attention
- question:0035-benchmark-evaluation-discipline
- question:0039-heterogeneous-graph-edge-typing
created: '2026-07-10'
updated: '2026-07-10'
---
# A review on graph neural networks for predicting synergistic drug combinations

- **Authors:** Milad Besharatifard, Fatemeh Vafaee
- **Year:** 2024
- **Journal:** Artificial Intelligence Review, 57:49
- **DOI/URL:** https://doi.org/10.1007/s10462-023-10669-z
- **BibTeX key:** Besharatifard2024
- **Source:** PDF

## Key Contribution

Besharatifard and Vafaee provide the first comprehensive review specifically focused on GNN-based methods for predicting synergistic drug combinations, surveying 25 models published from 2020 to July 2023 [@Besharatifard2024].
The review covers GNN architecture taxonomies (GCN, GAT, GAE, GraphSAGE, graph regularization), heterogeneous graph construction strategies, synergy metric definitions, dataset landscape, and comparative performance evaluation across in vitro and clinical datasets.
The science/meta relevance is methodological: the review documents both the design vocabulary for graph-structured evidence models and the critical benchmark failures (inconsistent thresholding, non-overlapping datasets, absent controls) that systematically undermine cross-study comparisons.

## Methods

The review is a systematic literature survey covering PubMed, Google Scholar, and Web of Science up to July 2023 using keywords "graph", "drug combination", and "synergy".
The authors organized 25 GNN studies into four sections: (1) in vitro classification methods, (2) in vitro regression methods, (3) clinical-data classification methods, and (4) comparative evaluation.
For each model, the review tabulates: GNN architecture, input feature types (drug molecular graphs, fingerprints, PPI networks, gene expression, knowledge graphs), dataset(s) used, prediction task type (classification vs. regression), synergy metric (Loewe, Bliss, ZIP, HSA), train/test split strategy, performance metrics (AUC, AUPR, F1, RMSE), and code availability.

## Key Findings

**GNN architecture taxonomy.** The 25 models split into three major architecture families:
- GCN (graph convolutional network): most common; used for molecular graph feature extraction and biological network embedding.
- GAT (graph attention network): second most common; assigns learned attention weights to neighbor nodes, enabling selective aggregation; used in both drug-structure graphs and knowledge graphs.
- GAE (graph autoencoder): encodes drug-drug synergy networks into latent space and reconstructs the adjacency matrix to infer novel synergistic relationships.

**Feature landscape.** Two orthogonal axes structure how models represent drugs and cell lines: (a) representation type — molecular graph (2D/3D structure via SMILES) vs. fingerprint vs. knowledge graph node, and (b) entity scope — drug only vs. drug + cell line vs. drug + cell line + biological network (PPI, pathway, gene expression).
Models incorporating richer, multi-modal heterogeneous features consistently outperform single-feature baselines; e.g., the Hu et al. (2023) model's use of drug + protein + disease heterogeneous graph with pre-trained embeddings outperformed DeepDDS which used drug structure only (AUC 0.84 vs. 0.66 on AstraZeneca) [@Besharatifard2024].

**Benchmark fragmentation.** No shared benchmark exists.
Studies differ in: dataset (Merck/O'Neil, DrugComb, AstraZeneca, ALMANAC, CLOUD, FORCINA), synergy metric (Loewe, Bliss, ZIP, HSA), thresholding strategy (arbitrary fixed cutoffs, quartile splits, averaging of multiple metrics), and cross-validation scheme (3-, 5-, or 10-fold; hold-out; leave-one-drug-out; leave-one-cell-line-out).
The authors conclude that direct performance comparison across models is unreliable, and call for a benchmarking study with controlled confounders [@Besharatifard2024].

**Class imbalance and metric choice.** Synergistic combinations are rare relative to non-synergistic ones; AUC-ROC is insensitive to this imbalance.
AUPR (area under the precision-recall curve) is the recommended metric for drug synergy classification tasks.

**GNN limitations.** Four recurring failure modes: (1) high computational cost + data hunger given a sparse experimental landscape; (2) overfitting risk under limited labeled pairs; (3) interpretability gaps — predictions cannot be mechanistically explained; (4) expressivity limits of standard GCNs on heterophilic graphs (nodes of different types connected by diverse edge semantics).

## Relevance

This review is a domain-specific methods survey whose primary value for science/meta is the **design vocabulary and benchmark critique** it contributes, not the drug-biology claims.

**hypothesis:0002-rich-evidence-payloads-improve-graph-calibration** — the comparative evidence across 25 models directly demonstrates that incorporating richer and more diverse feature types (drug molecular graphs + PPI networks + gene expression + disease associations) reliably improves predictive performance; this supports the hypothesis that richer evidence payloads improve graph calibration.

**hypothesis:0005-sequential-evidence-improves-attention** — the GAT literature reviewed here clarifies that graph attention weights are learned relevance signals, not independent evidence weights; they prioritize neighbor contributions during aggregation rather than encoding sequential evidence strength.
Science should maintain a clear semantic distinction between attention-as-aggregation-weight and evidence-as-epistemic-support (see also Dai2024GraphAttention).

**Benchmark fragmentation** is directly relevant to Science's evaluation methodology.
The review documents that varying thresholds, metrics, and data splits render model comparisons uninformative — a failure mode Science's benchmark tooling must prevent by enforcing fixed splits, logged preprocessing parameters, and evaluation-metric provenance.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Heterogeneous graph (drug + protein + disease nodes) | Knowledge graph with typed nodes | Multi-type entity graphs require typed edge semantics in the Science graph model |
| GNN message passing / aggregation | Evidence propagation / belief update | Analogous computational metaphor; semantics differ: GNN aggregation is a representation step, not a belief update |
| Graph attention weight | Attention / prioritization signal | Not evidential support; consistent with Dai2024GraphAttention's distinction |
| GAE latent embedding + adjacency reconstruction | Latent knowledge representation | GAE reconstructs missing edges — analogous to predicting unobserved relationships |
| Synergy metric (Loewe, Bliss, ZIP, HSA) | Outcome measure / label provenance | The lack of a standard synergy metric parallels the challenge of defining a canonical belief score in Science |
| Thresholding strategy | Belief boundary / discretization | Arbitrary thresholding is a validity threat; Science should prefer continuous beliefs (D-003) |
| Benchmark fragmentation | Evaluation discipline | Science's benchmark module should enforce experimental controls to avoid analogous fragmentation |
| Leave-one-drug-out vs. leave-one-cell-line-out | Generalization target | Distinction between generalizing to new entities vs. new contexts maps to Science's entity-vs-context generalization |

## Limitations

The review does not compare GNNs against the strongest non-GNN baselines (e.g., MatchMaker, DeepSynergy, DTF) in a controlled head-to-head study; this gap is acknowledged but deferred to future work.
Performance comparisons across the reviewed models are confounded by dataset selection, synergy metric, and threshold choices — the authors acknowledge this but do not resolve it.
The review ends at July 2023; methods published after (including transformer-heavy and large language model-augmented approaches) are not covered.
For science/meta purposes, the drug biology claims (which cell-line features matter, which synergy metric is most predictive) are domain-specific and should not be imported into toolkit design reasoning without a domain-transfer justification.

## Model / Tool Availability

This is a review paper; it does not release a model or dataset artifact.
Code links for all 25 reviewed models are tabulated in Table 2 of the paper; most are publicly available on GitHub.
The DrugComb database (https://drugcomb.fimm.fi) is the most-used dataset and is publicly accessible.

## Follow-up

- Dai2024GraphAttention — complementary study on causal inference + graph attention; already in the collection; provides the attention-as-aggregation-weight semantic distinction needed above.
- The benchmark fragmentation critique invites a question: does Science's evaluation tooling currently enforce the controls that would prevent this failure mode? (see question reserved below).
- The heterogeneous-graph literature raises a design question for Science's knowledge graph: how are multi-type node/edge relationships typed, and does the current model support typed propagation rules analogous to heterogeneous GNNs?
