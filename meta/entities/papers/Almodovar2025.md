---
kind: paper
title: 'DeCaFlow: A deconfounding causal generative model'
status: active
created: '2026-07-10'
updated: '2026-07-10'
id: paper:Almodovar2025
ontology_terms: []
dataset_usage: []
source_refs:
- cite:Almodovar2025
related:
- hypothesis:0004-causal-estimand-guardrails-reduce-false-causal-edge-strengthening
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- question:0003-causal-synthesis-guardrails
- question:0010-causal-graph-construction-pipeline
---

# DeCaFlow: A deconfounding causal generative model

- **Authors:** Alejandro Almodóvar, Adrián Javaloy, Juan Parras, Santiago Zazo, and Isabel Valera
- **Year:** 2025
- **Journal/Venue:** NeurIPS 2025 (39th Conference on Neural Information Processing Systems)
- **DOI/URL:** https://doi.org/10.48550/arxiv.2503.15114
- **BibTeX key:** Almodovar2025
- **Source:** PDF

## Key Contribution

DeCaFlow is a causal generative model (CGM) that correctly estimates interventional and counterfactual queries under hidden confounding, requiring only observational data and the known causal graph.
It extends causal normalizing flows (CNFs) with a variational autoencoder-style architecture — a conditional normalizing flow as generative decoder (conditioned on latent confounders) and a second normalizing flow as an inference network (encoder) that approximates the posterior of hidden confounders given observations.
The paper proves theoretically that DeCaFlow provides correct causal estimates for all queries identifiable by do-calculus and extends identifiability to hidden-confounded queries via proxy variables, including counterfactuals — a novel result showing a one-to-one correspondence between proxy-identifiable interventional and counterfactual queries.

## Methods

DeCaFlow has two components trained jointly by maximizing the ELBO:

1. **Generative network**: A conditional masked autoregressive normalizing flow (Tθ) that models the confounded SCM, mapping exogenous variables to observed variables conditioned on hidden confounders z. The causal graph G is used to mask the network so that pθ(x|z) factorizes causally.
2. **Deconfounding (inference) network**: A conditional normalizing flow (Tφ) that approximates the intractable posterior qφ(z|x), using only children of z and their parents (structurally masked by G).

Training uses KL balancing to prevent posterior collapse. The do-operator adapted from CNFs enables exact sampling from interventional and counterfactual distributions.

For causal queries involving direct children of hidden confounders, proxy variables (variables conditionally independent of treatment or outcome given z) are exploited via a proximal causal inference extension (building on Miao et al. and Wang & Blei), broadened to allow observed common ancestors of treatment and outcome.

**Identifiability results** (informal):
- Prop 3.1: DeCaFlow recovers the SCM for variables not in ch(z), up to exogenous distribution reparametrization.
- Prop 4.1: An interventional query p(y|do(t)) with y,t ∈ ch(z) is identifiable given proxy (w) and null-proxy (n) variables satisfying a completeness condition.
- Prop 4.4: If p(y|do(t)) is proxy-identifiable, so is its counterfactual p(y_cf|do(t_cf),x_f).

**Evaluation datasets**: synthetic SCMs, Sachs protein-signaling network (11 variables, bivariate hidden confounder PKC/PKA, semi-synthetic), Ecoli70 gene network (43 variables, 3 independent hidden confounders), and a real-world law school dataset for counterfactual fairness.

Baselines: CNF, ANM (additive noise models), DCM (diffusion causal models), Deconfounder.

## Key Findings

- DeCaFlow outperforms all baselines (CNF, ANM, DCM, Deconfounder) in average treatment effect (ATE) and counterfactual estimation error on the Sachs and Ecoli70 semi-synthetic datasets, matching oracle performance (a CNF that observes z directly).
- DeCaFlow scales to complex graphs (43 observed variables, 3 hidden confounders) with a single end-to-end training pass.
- More proxy variables consistently improve hidden-confounded query estimation; overspecifying the latent dimension Dz is robust, while underspecification increases error — practitioners should use a large latent space.
- In the law school counterfactual fairness application, DeCaFlow-based predictions substantially reduce inter-group distributional divergence (MMD ≈ 10⁻⁵ vs 0.147 for the unaware baseline) at a small cost to RMSE.
- The Deconfounder's apparent strong performance on Ecoli70 is an evaluation artifact: it only holds on queries meeting its more stringent assumptions.

## Relevance

DeCaFlow bears directly on the Science toolkit's causal-inference layer in several ways:

**Hidden confounder representation (H04, P4a)**: The paper makes explicit that the causal graph must distinguish children of hidden confounders from non-children to determine which identifiability tier applies. This maps to H04's graph-construction guardrail requirement: evidence from a CGM like DeCaFlow carries a "hidden-variable assumption" field (causal sufficiency relaxed with proxy structure) and an "identification status" field (proxy-identifiable vs. do-calculus identifiable vs. unidentifiable). The guardrail's `causal-sufficiency-assumption` and `identification-missing` warning codes are directly operationalized here.

**Evidence payload for proxy-identified claims (H02, Q0003)**: A proxy-identifiable causal effect requires recording which variables served as proxy/null-proxy, whether the completeness condition was checked, and the assumed confounder dimensionality (Dz). These constitute new fields for the causal-evidence payload schema that are absent from standard estimand metadata.

**Graph construction pipeline (Q0010)**: DeCaFlow assumes a fully specified causal graph including confounder–variable edge structure. In workflow terms this means the graph-construction pipeline must have a dedicated confounder node type with outgoing edges to its observed children — otherwise DeCaFlow cannot be applied (or the user must treat confounders as latent background assumptions rather than explicit graph nodes).

**Natural-systems connection**: The Ecoli70 and Sachs experiments are drawn from biological networks. DeCaFlow's approach to gene regulatory network inference with hidden confounders is directly applicable to natural-systems causal graph tasks. This paper should be cross-promoted to the commons once the full toolkit interface for hidden-confounder graph queries is stabilized.

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Hidden confounder z with ch(z) | Confounder node in causal graph + `hidden_confounder` metadata field | Graph must explicitly mark confounded nodes |
| Proxy variable, null-proxy | Evidence payload fields: `proxy_vars`, `null_proxy_vars` | Required for proxy-identified causal claims |
| Completeness condition on proxies | Identification check in evidence guardrail | Untestable in practice; count and diversity of proxies are proxies for this |
| Identifiability tier (do-calculus / proxy / unidentifiable) | `identification_status` on causal evidence artifact | Maps to existing H04 guardrail field |
| SCM with confounded causal equations | Confounded SCM source node | Source type needs `hidden_variable_assumption: proxy_adjustable` |
| ELBO training objective | Model-fitting metadata (`model_class: VAE-style CGM`) | Approximation status: variational |
| Single training pass per dataset | Dataset-scoped model artifact | One DeCaFlow per dataset node in provenance graph |
| Causal normalizing flow (CNF) as backbone | Causal generative model sub-type | Precursor paper to track: Javaloy et al. [27] |

## Limitations

- **Known graph required**: DeCaFlow requires the full causal graph G including which variables are children of hidden confounders. Misspecification of confounder children breaks the proxy-identifiability guarantees. This is a significant constraint for discovery workflows where G is uncertain.
- **Continuous variables only**: The model is restricted to continuous endogenous variables; the fairness experiment suggests CNF-based models handle discrete variables approximately in practice, but this is not formally guaranteed.
- **Completeness condition is untestable**: The completeness condition for proxy variables cannot be verified from observational data alone. The empirical ablation shows that more proxies help, but there is no stopping criterion.
- **No joint causal discovery**: The graph G must be given; DeCaFlow does not perform structure learning. It cannot be applied in purely observational discovery settings without a separate structure-learning phase.
- **Confounder dimensionality**: Overspecifying Dz is robust, but underspecifying leads to degraded performance. Practitioners must choose Dz without a principled data-driven criterion.
- **Scalability ceiling**: The VAE-style training may not scale to graphs much larger than Ecoli70 (43 variables) without architecture modifications; the paper does not benchmark beyond this size.

## Model / Tool Availability

- Implementation: [github.com/aalmodovares/DeCaFlow](https://github.com/aalmodovares/DeCaFlow)
- License: not stated in the paper [UNVERIFIED]
- Framework: PyTorch-based normalizing flows [UNVERIFIED]
- No pretrained checkpoints; users train per dataset.

## Follow-up

- **Read**: Javaloy et al. (CNFs, the backbone model) — already cited across the project as [27]; check if a summary exists under `entities/papers/`.
- **Read**: Miao et al. and Wang & Blei (proximal causal inference foundations) to understand the completeness condition fully.
- **Question raised**: Can the proxy-variable requirements (identity of proxy/null-proxy variables, completeness check) be encoded as mandatory fields in the Science evidence-payload schema for CGM-based causal estimates? → Candidate for `question:0003` extension or a new question.
- **Graph implication**: Add `hidden_confounder` as a node annotation type and `proxy_identifiable` as an `identification_status` value in the causal graph schema.
- **Natural-systems**: Flag this paper for commons promotion once the hidden-confounder pipeline interface is defined; Ecoli70 and Sachs benchmarks are replicable with publicly available data.
