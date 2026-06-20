---
type: paper
title: 'MetaBayesDTA: codeless Bayesian meta-analysis of test accuracy, with or without
  a gold standard'
status: active
created: '2026-05-05'
updated: '2026-05-05'
id: paper:Cerullo2023
ontology_terms: []
source_refs:
- cite:Cerullo2023
related: []
---

# MetaBayesDTA: codeless Bayesian meta-analysis of test accuracy, with or without a gold standard

- **Authors:** Enzo Cerullo, Alex J. Sutton, Hayley E. Jones, Olivia Wu, Terry J. Quinn, Nicola J. Cooper
- **Year:** 2023
- **Journal:** BMC Medical Research Methodology
- **DOI/URL:** https://doi.org/10.1186/s12874-023-01910-y
- **BibTeX key:** Cerullo2023
- **Source:** PDF

## Key Contribution

Cerullo et al. present MetaBayesDTA, a web-based R Shiny and Stan application for Bayesian meta-analysis of diagnostic test accuracy studies [@Cerullo2023].
The main contribution is lowering the implementation barrier for advanced diagnostic accuracy synthesis, including bivariate models, subgroup analysis, meta-regression, comparative test accuracy, and latent class models that do not assume a perfect reference standard [@Cerullo2023].
For Science, the paper is a practical example of turning probabilistic evidence aggregation into an interactive tool while preserving priors, posterior intervals, model diagnostics, and sensitivity checks as visible workflow objects [@Cerullo2023].

## Methods

The application implements Bayesian versions of the bivariate diagnostic test accuracy model for analyses that assume a perfect gold standard [@Cerullo2023].
For the bivariate model, the tool supports standard meta-analysis, categorical or continuous univariate meta-regression, subgroup analysis, and comparative test accuracy using categorical meta-regression [@Cerullo2023].
The application also implements Bayesian latent class models for analyses that relax the perfect-reference-test assumption and estimate index-test accuracy, reference-test accuracy, and disease prevalence jointly [@Cerullo2023].
The latent class workflow lets users choose fixed or random effects for index and reference test sensitivities and specificities, model multiple reference tests, and compare conditional-independence versus conditional-dependence assumptions [@Cerullo2023].
The default priors for pooled logit sensitivity and specificity are weakly informative normal distributions, with truncated normal priors for between-study standard deviations and an LKJ prior for between-study correlation in the bivariate model [@Cerullo2023].
The paper demonstrates the application on a 13-study Cochrane IQCODE dementia-screening dataset and compares results under perfect and imperfect reference-standard assumptions [@Cerullo2023].
Model diagnostics include Stan sampler checks, split R-hat, trace and density plots, residual plots for latent class models, deviance summaries, and interactive visualizations such as sROC plots and forest plots [@Cerullo2023].

## Key Findings

The Bayesian bivariate analysis of the IQCODE example reproduced the earlier frequentist summary estimates closely, with sensitivity 0.91 and specificity 0.66 under the perfect gold-standard model [@Cerullo2023].
Categorical meta-regression by IQCODE version found broadly similar sensitivity and specificity for the 16-item and 26-item versions, while the 32-item group was based on only one study and therefore highly uncertain [@Cerullo2023].
Subgroup analysis produced similar 16-item and 26-item estimates but differed from categorical meta-regression by allowing subgroup-specific random-effect variances rather than assuming common variances across groups [@Cerullo2023].
In the latent class analysis assuming conditional independence, IQCODE sensitivity and specificity were estimated at 0.94 and 0.77, suggesting that the perfect-reference analysis underestimated both quantities in that model [@Cerullo2023].
In the latent class analysis allowing conditional dependence, IQCODE sensitivity and specificity were estimated at 0.89 and 0.71, and this model fit better by residual diagnostics and deviance than the conditional-independence model [@Cerullo2023].
The paper emphasizes that relaxing the perfect reference-test assumption can materially change diagnostic accuracy conclusions, which may affect which tests are favored in clinical practice [@Cerullo2023].
The authors argue that easy-to-use Bayesian tools can increase uptake of appropriate methods, but also warn that easier access may lead to invalid analyses when users lack diagnostic-checking expertise [@Cerullo2023].

## Relevance

MetaBayesDTA directly supports Decision D-003 because diagnostic accuracy is represented as posterior probability distributions and credible intervals rather than as accepted or rejected binary claims [@Cerullo2023].
The paper is relevant to H01 because down-weighted or less favored diagnostic claims can change when reference-test assumptions, prior information, conditional dependence, or model-fit diagnostics are revisited [@Cerullo2023].
For Science graph workflows, the paper suggests that evidence aggregation nodes should retain model assumptions, priors, posterior summaries, diagnostics, and sensitivity-analysis outcomes as inspectable graph state [@Cerullo2023].
For research-agent behavior, the paper provides an example of when agents should revisit conclusions: when a model is nonidentifiable, posterior distributions are bimodal, diagnostics fail, or alternative reference-standard assumptions alter posterior accuracy estimates [@Cerullo2023].

## Project Framework Mapping

| Paper Concept | Project Concept | Notes |
|---|---|---|
| Diagnostic test sensitivity and specificity | Continuous claim belief | Accuracy estimates are probabilities with posterior uncertainty, aligning with D-003. |
| Bivariate meta-analysis | Evidence aggregation model | Aggregates study-level sensitivity and specificity while modeling cross-study correlation. |
| Latent class model | Hidden-state evidence model | Infers an unobserved disease class when no perfect reference standard is available. |
| Imperfect reference standard | Noisy evidence source | Treats labels or validators as uncertain measurements rather than ground truth. |
| Prior distribution | Operational prior belief | Encodes domain knowledge and stabilizes weakly identified models. |
| Conditional dependence between tests | Evidence correlation structure | Prevents double-counting when evidence sources are correlated within latent states. |
| Model diagnostics | Agent verification checkpoint | Divergences, R-hat, trace plots, residual plots, and deviance can trigger reanalysis. |
| Sensitivity analysis by excluding studies | Revisit trigger | Study influence can identify claims whose posterior belief should remain actively monitored. |

## Limitations

The application is described as a beta version, so the authors expect possible bugs and request user feedback [@Cerullo2023].
The latent class model cannot impose restrictions on the conditional-dependence correlation structure, such as forcing correlations to be positive or shared across disease classes [@Cerullo2023].
The latent class model can model different reference tests only through categorical meta-regression and therefore assumes the same between-study variances across reference tests [@Cerullo2023].
The application does not support subgroup analysis or general meta-regression for latent class models beyond modeling different reference tests [@Cerullo2023].
The bivariate subgroup and categorical meta-regression features do not yet let users assign different priors to each group [@Cerullo2023].
The tool still requires users or review teams to understand Bayesian model diagnostics, and the authors recommend including a statistician with this expertise [@Cerullo2023].
Because codeless tools reduce friction, the paper notes a risk of over-applying complex models when assumptions are inappropriate [@Cerullo2023].

## Model / Tool Availability

MetaBayesDTA is available as a web application at `https://crsu.shinyapps.io/MetaBayesDTA/` [@Cerullo2023].
The data, R code, and Stan code for the web application are available at `https://github.com/CRSU-Apps/MetaBayesDTA` [@Cerullo2023].
The application is platform independent and requires a web browser [@Cerullo2023].
The paper lists the programming languages as R and Stan [@Cerullo2023].
The paper lists the license as not applicable and reports no restrictions for non-academic use [@Cerullo2023].

## Follow-up

Use imperfect-reference-standard models as a template for Science evidence nodes whose labels or validators are themselves uncertain rather than authoritative.
Add graph fields for model diagnostics and identifiability warnings so agents can schedule stochastic revisits under H01.
Compare Science aggregation behavior under perfect-label, imperfect-label, and correlated-evidence assumptions to measure how often operational beliefs shift enough to change downstream decisions.
