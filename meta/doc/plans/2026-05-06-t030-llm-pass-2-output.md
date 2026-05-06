# t030 — Blind LLM Extraction Pass 2 (raw output)

> **Pass identifier:** `llm-blind-2` (general-purpose subagent, fresh context, ~2 min wall-clock).
> **Sample:** main sample n=12, locked per `meta/doc/plans/2026-05-06-t030-full-sampling-plan-and-rubric.md`.
> **Prompt:** verbatim same as `llm-blind-1`.
> **Status:** Raw output preserved verbatim. Paired with `llm-blind-1` for D4 agreement scoring.

---

I have all 12 papers read. Now I'll produce the audit. (Noting the system reminders about MCP/skills — neither applies to this blind extraction-cost audit, which the user explicitly scoped to no other tools.)

# Extraction-Cost Audit

## 1. Klugkist2023

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper / synthesis-method | Paper introduces a method (BES); type isn't stated; INVENTED if no "methods-paper" enum exists |
| extensions | 1 | 2 | [bayesian-evidence-synthesis] | Inferred from method content; no extension list stated |
| input_artifact_refs | 2 | 2 | [simulation:BES-sim1, simulation:BES-sim2, BFpack@1.0.0, R@4.2.1] | Two simulations explicitly described |
| claim_source_ref | 2 | 1 | paper:Klugkist2023 | The paper itself |
| method_ref | 2 | 1 | method:BayesFactor / package:BFpack | Stated explicitly |
| proposition_refs | 0 | 4 | [prop:BES-aggregates-heterogeneous-replications, prop:BES-not-rescue-for-underpowered] | Multiple findings; cand: one synthetic prop vs multiple per-finding props; picked the latter |
| target_artifact_ref | ✗ | 0 | n/a | Not an evaluation/operation payload |
| comparison_target | 1 | 2 | hypothesis-set | BES compares informative hypotheses against complement/null/unconstrained; "model-set" also defensible |
| support_direction | 1 | 2 | supports | Findings support method's behavior; methodological-input also defensible |
| validation_role | 1 | 2 | strengthen-belief | Simulation-validated method; could also be "prioritize-attention" |
| validation_status | 2 | 1 | pending | Default for newly-authored payload |
| uncertainty_summary | 0 | 3 | "BES sim, 1000 iter/condition; PMP-based" | No single quantitative summary; cand: PMP statement vs sim-config string; picked latter |
| reason_codes | ✗ | 1 | [] | None stated; abstention_reason n/a |

## 2. VanLissa2024

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 1 | methods-paper / tutorial | Tutorial paper; type not stated |
| extensions | 1 | 1 | [product-bayes-factor] | Inferred |
| input_artifact_refs | 1 | 2 | [package:bain, simulation:PBF-benchmarks, dataset:meta-analytic-example, dataset:IPD-example] | Described abstractly, not enumerated specifically |
| claim_source_ref | 2 | 1 | paper:VanLissa2024 | Self |
| method_ref | 2 | 1 | method:ProductBayesFactor / package:bain | Stated |
| proposition_refs | 1 | 3 | [prop:PBF-good-for-incomparable-effect-sizes, prop:PBF-higher-sensitivity-lower-specificity] | Findings present but not crisply enumerated |
| target_artifact_ref | ✗ | 0 | n/a | Not evaluation/operation |
| comparison_target | 1 | 2 | model-set | PBF benchmarked against random-effects, IPD, vote counting; "hypothesis-set" also fits |
| support_direction | 1 | 2 | supports | Could also be methodological-input |
| validation_role | 1 | 2 | strengthen-belief | Simulation-validated; could be prioritize-attention |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 0 | 3 | "PBF sim: high sensitivity, lower specificity" | No quantitative numbers given; cand: qualitative string vs "n/a"; picked qualitative |
| reason_codes | ✗ | 1 | [] | None |

## 3. Yu2026

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 0 | 4 | benchmark / dataset-paper | Cand: dataset-contribution (taxonomy-ish, possibly out-of-scope) vs evaluation-paper. Picked benchmark. INVENTED enum |
| extensions | 1 | 2 | [llm-evaluation, scientific-context-benchmark] | Inferred |
| input_artifact_refs | 1 | 2 | [domain-corpora:bio,chem,phys,biomed,materials] | "Ten domain-specific sub-datasets" abstract |
| claim_source_ref | 2 | 1 | paper:Yu2026 | Self |
| method_ref | 1 | 2 | method:SciCUEval-benchmark | Method is the benchmark itself; not a canonical external method |
| proposition_refs | 0 | 4 | [prop:LLMs-have-context-understanding-gaps] | Cand: claim about benchmark utility vs claim about LLM limitations; both vague. Picked latter |
| target_artifact_ref | 0 | 3 | [various LLMs] | Cand: this is an evaluation-of-LLMs payload (would need target ref) vs benchmark contribution payload. Picked target |
| comparison_target | 0 | 3 | model-set | Cand: model-set (across LLMs) vs artifact-target. Picked model-set |
| support_direction | 0 | 3 | quality-record | Cand: quality-record vs supports (a methodological proposition). Picked quality-record |
| validation_role | 0 | 3 | quality-record-only | Cand: quality-record-only vs prioritize-attention. Picked former |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 0 | 3 | "benchmark: 4 competencies, 10 sub-datasets" | No metrics given in summary |
| reason_codes | ✗ | 1 | [] | None |

Note: this paper sits near the survey/benchmark boundary; flagging as borderline out-of-scope (no propositional claim about a target system).

## 4. Si2025

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper / evaluation-method | Reformulates bias detection; not stated |
| extensions | 1 | 2 | [bayesian-hypothesis-test, llm-bias-evaluation] | Inferred |
| input_artifact_refs | 2 | 2 | [dataset:BBQ, dataset:CrowS-Pairs, dataset:Winogender] | Named explicitly |
| claim_source_ref | 2 | 1 | paper:Si2025 | Self |
| method_ref | 2 | 1 | method:BayesFactor-binomial | Stated |
| proposition_refs | 2 | 2 | [prop:BF-distinguishes-no-evidence-from-evidence-of-no-bias, prop:CrowS-Pairs-bias-consistent-EN-FR] | Two clear claims |
| target_artifact_ref | 1 | 3 | [LLM-class] | If this is an evaluation payload of LLMs, target is LLMs but unspecified which |
| comparison_target | 2 | 2 | null-vs-alternative | H0: pi=0.5 explicit |
| support_direction | 1 | 2 | supports | Supports BF-method claim |
| validation_role | 1 | 2 | strengthen-belief | Could be prioritize-attention |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 1 | 2 | "BF binomial test, H0:pi=0.5" | No specific BF reported in summary |
| reason_codes | ✗ | 1 | [] | None |

## 5. Williams2018

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper / simulation-study | Not stated |
| extensions | 1 | 2 | [bayesian-meta-analysis, prior-sensitivity] | Inferred |
| input_artifact_refs | 2 | 2 | [simulation:varying-k-tau-n, dataset:towel-reuse, dataset:power-pose, package:brms, package:metaBMA, package:metafor] | Named |
| claim_source_ref | 2 | 1 | paper:Williams2018 | Self |
| method_ref | 2 | 1 | method:RandomEffectsMA-Bayesian / prior:half-Cauchy | Stated |
| proposition_refs | 2 | 3 | [prop:DL-REML-boundary-zero-frequent, prop:Bayesian-priors-reduce-boundary-issue, prop:half-t-can-underestimate-large-tau] | Multiple stated findings with numbers |
| target_artifact_ref | ✗ | 0 | n/a | Not eval/op |
| comparison_target | 1 | 2 | model-set | Compares classical vs Bayesian estimators; could also be hypothesis-set |
| support_direction | 2 | 1 | supports | Clear |
| validation_role | 1 | 2 | strengthen-belief | Default for sim-validated method evidence |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 2 | 1 | "DL: 31% zero-tau; REML: 25% zero-tau (mu=0,tau=0.15)" | Stated quantitatively |
| reason_codes | ✗ | 1 | [] | None |

## 6. Allen2017

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 0 | 4 | commentary / methods-agenda | Cand: methods-paper vs survey/commentary (out-of-scope?). Self-described as "methodological commentary"; picked commentary. Borderline survey |
| extensions | 1 | 2 | [multi-view-integration, mixed-graphical-models] | Inferred |
| input_artifact_refs | 1 | 2 | [dataset:TCGA-ovarian, package:TCGA2STAT] | TCGA mentioned; not exhaustive |
| claim_source_ref | 2 | 1 | paper:Allen2017 | Self |
| method_ref | 1 | 3 | method:mixed-chain-graphical-models | Multiple methods surveyed; not one canonical method |
| proposition_refs | 1 | 3 | [prop:multi-view-needs-typed-aggregation, prop:missing-views-as-graph-fact, prop:TCGA-ovarian-204-of-592-complete] | Some specific, some abstract |
| target_artifact_ref | ✗ | 0 | n/a | Not eval/op |
| comparison_target | 0 | 3 | n-a | Cand: n-a vs hypothesis-set. Commentary not testing hypotheses; picked n-a |
| support_direction | 0 | 3 | methodological-input | Cand: methodological-input vs supports. Picked methodological-input given commentary nature |
| validation_role | 0 | 3 | record-only | Cand: record-only vs prioritize-attention. No direct validation |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 0 | 3 | "commentary; no quantitative summary" | No method-specific uncertainty reported |
| reason_codes | ✗ | 1 | [] | None; possibly out-of-scope (survey-like). Flag |

## 7. Zhang2017CancerGenomics

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper | Not stated |
| extensions | 1 | 2 | [mixed-graphical-models, joint-graph-estimation] | Inferred |
| input_artifact_refs | 1 | 2 | [simulation:joint-MGM, dataset:cancer-genomics] | Abstract |
| claim_source_ref | 2 | 1 | paper:Zhang2017CancerGenomics | Self |
| method_ref | 2 | 1 | method:joint-mixed-graphical-model | Stated |
| proposition_refs | 1 | 3 | [prop:joint-MGM-balances-pooling-vs-separate] | One core claim, abstract |
| target_artifact_ref | ✗ | 0 | n/a | Not eval/op |
| comparison_target | 1 | 2 | model-set | Comparing pooled vs separate vs joint estimation |
| support_direction | 2 | 1 | supports | Clear |
| validation_role | 1 | 2 | strengthen-belief | Default |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 0 | 3 | "sim + cancer genomics application; no metrics given" | No quantitative summary |
| reason_codes | ✗ | 1 | [] | None |

## 8. Mulder2026

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper / review-with-method-guidance | Not stated; somewhat survey-like but with five concrete models |
| extensions | 1 | 2 | [bayes-factor-meta-analysis, e-value-link] | Inferred |
| input_artifact_refs | 2 | 2 | [package:BFpack, application:language-impairment, application:seroma-postop-exercise] | Named |
| claim_source_ref | 2 | 1 | paper:Mulder2026 | Self |
| method_ref | 2 | 1 | method:BayesFactorMA / package:BFpack | Stated |
| proposition_refs | 1 | 3 | [prop:BF-distinguishes-absence-from-evidence-of-absence, prop:prior-sensitivity-is-load-bearing] | Multiple but not enumerated as findings |
| target_artifact_ref | ✗ | 0 | n/a | Not eval/op |
| comparison_target | 1 | 2 | model-set | Five models compared; could be hypothesis-set |
| support_direction | 1 | 2 | supports | Could be methodological-input given review nature |
| validation_role | 1 | 2 | strengthen-belief | Default |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 0 | 3 | "5 BF-MA models; e-value-linked" | No specific metrics |
| reason_codes | ✗ | 1 | [] | None |

## 9. Berenfeld2026

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper | Stated as proposing causal aggregation; type not literal |
| extensions | 1 | 2 | [causal-meta-analysis] | Inferred |
| input_artifact_refs | 2 | 2 | [package:CaMeA, sim:causal-vs-classical, dataset:Cochrane-meta-analyses] | Named |
| claim_source_ref | 2 | 1 | paper:Berenfeld2026 | Self |
| method_ref | 2 | 1 | method:arm-based-causal-aggregation / package:CaMeA | Stated |
| proposition_refs | 2 | 2 | [prop:RD-classical-can-be-causal, prop:RR-OR-classical-not-causally-valid, prop:classical-vs-causal-can-reverse-conclusions] | Multiple clear claims |
| target_artifact_ref | ✗ | 0 | n/a | Not eval/op |
| comparison_target | 1 | 2 | model-set | Classical vs causal estimators; could be hypothesis-set |
| support_direction | 2 | 1 | supports | Clear |
| validation_role | 1 | 2 | strengthen-belief | Sim + Cochrane-validated |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 1 | 2 | "Causal vs classical sim+Cochrane; can reverse conclusions" | Qualitative but specific |
| reason_codes | ✗ | 1 | [] | None |

## 10. Liu2024HiddenWorld

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper / framework-paper | Stated as framework, not as schema enum |
| extensions | 1 | 2 | [llm-causal-discovery, variable-proposal] | Inferred |
| input_artifact_refs | 1 | 2 | [framework:COAT, benchmark:reviews, benchmark:medical-diagnosis] | Some named, some abstract |
| claim_source_ref | 2 | 1 | paper:Liu2024HiddenWorld | Self |
| method_ref | 2 | 1 | method:COAT | Stated |
| proposition_refs | 1 | 3 | [prop:LLM+CD-mutually-beneficial, prop:CD-feedback-improves-variable-proposal] | Stated but somewhat abstract |
| target_artifact_ref | ✗ | 0 | n/a | Not eval/op |
| comparison_target | 0 | 3 | n-a | Cand: n-a vs model-set. No clear baseline structure described. Picked n-a |
| support_direction | 1 | 2 | supports | Default |
| validation_role | 1 | 2 | strengthen-belief | Benchmarks support |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 0 | 3 | "COAT: synthetic + real benchmarks; no metrics" | No numbers given |
| reason_codes | ✗ | 1 | [] | None |

## 11. Jiang2024

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper / model-paper | Not literal |
| extensions | 1 | 2 | [kg-diffusion, recommendation-system] | Inferred |
| input_artifact_refs | 1 | 2 | [3-public-datasets, repo:HKUDS/DiffKG] | "Three public datasets" abstract |
| claim_source_ref | 2 | 1 | paper:Jiang2024 | Self |
| method_ref | 2 | 1 | method:DiffKG | Stated |
| proposition_refs | 1 | 3 | [prop:DiffKG-improves-recommendation, prop:KG-filtering-helps-noise-sparsity] | Stated but not crisply formalized |
| target_artifact_ref | ✗ | 0 | n/a | Not eval/op |
| comparison_target | 1 | 2 | model-set | Beats baselines; standard ML benchmark structure |
| support_direction | 2 | 1 | supports | Clear |
| validation_role | 1 | 2 | strengthen-belief | Standard benchmark claim |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 0 | 3 | "improvements over baselines; no metrics given" | No numbers in summary |
| reason_codes | ✗ | 1 | [] | None. Possibly tangential to project's scientific-belief domain |

## 12. Maier2022

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | methods-paper | Not literal |
| extensions | 1 | 2 | [robust-bayesian-meta-analysis, model-averaging, publication-bias] | Inferred |
| input_artifact_refs | 2 | 2 | [package:RoBMA, package:JAGS, dataset:violent-video-games-Anderson, dataset:ManyLabs2-28-effects, sim:varying-mu-tau-k-bias, JASP] | Named |
| claim_source_ref | 2 | 1 | paper:Maier2022 | Self |
| method_ref | 2 | 1 | method:RoBMA | Stated |
| proposition_refs | 2 | 3 | [prop:RoBMA-distinguishes-absence-of-bias, prop:RoBMA-best-RMSE-65pct, prop:RoBMA-overestimates-under-p-hacking] | Multiple specific claims |
| target_artifact_ref | ✗ | 0 | n/a | Not eval/op |
| comparison_target | 2 | 2 | model-set | 12-model ensemble; explicit |
| support_direction | 2 | 1 | supports | Clear |
| validation_role | 1 | 2 | strengthen-belief | Sim+example-validated |
| validation_status | 2 | 1 | pending | Default |
| uncertainty_summary | 2 | 1 | "RoBMA r=0.151 [0.094, 0.207]; RMSE-best in 65% / bias-best in 36% sim conditions; 1/28 ML2 false positive" | Quantitative |
| reason_codes | ✗ | 1 | [] | None |

---

## Findings

**Systematically ambiguous fields:**
- `artifact_type`: Almost no summary literally states a type. The schema enum is not pasted, but every paper here is a methods/framework paper, and that label seems missing. Most scored 1 (inferred); Yu2026 and Allen2017 scored 0.
- `uncertainty_summary`: Most summaries lack a single canonical short-form metric. The schema example ("BF10=0.115") is hard to fill from prose-style summaries. Williams2018 and Maier2022 (which include concrete numbers) were the only clean 2s.
- `comparison_target`: The enum (null-vs-alternative / hypothesis-set / model-set / artifact-target / n-a) maps awkwardly onto methods-paper findings, where multiple comparison structures coexist. Frequently scored 1.
- `proposition_refs`: Papers often present 2–4 distinct findings. Whether to author one synthetic proposition or multiple is itself a design choice; many scored 1.
- `support_direction`/`validation_role` for review/commentary papers (Allen2017, Mulder2026): the "methodological-input" vs "supports" distinction is unclear when the paper both reviews and advocates.

**Schema enums that need extending:**
- `artifact_type` needs a value like `methods-paper`, `framework-paper`, or `tutorial-paper`. Without it, almost every paper's primary type is forced.
- `artifact_type` likely also needs `benchmark`/`dataset-paper` (Yu2026).
- `support_direction` could use a `descriptive-finding` or `framework-proposal` value distinct from `supports`/`methodological-input` for papers that propose a new approach without a comparator hypothesis.

**Possible out-of-scope flags:**
- Yu2026 (SciCUEval): benchmark contribution; the propositional claim is thin (essentially "SciCUEval is useful and LLMs have gaps"). Borderline payload-bearing.
- Allen2017: self-described "methodological commentary" surveying integration challenges. Has a programmatic agenda but limited propositional content. Borderline survey/scoping.
- Jiang2024 (DiffKG): a recommender-system paper; payload-relevant for project's KG-provenance theme but the scientific claim is narrow ML-benchmark.

**Total time:** ~70 min (≈5–6 min per paper across 13 fields, plus ~5 min reading each summary, plus aggregation).

Most reliable fields to extract: `claim_source_ref`, `method_ref`, `validation_status` (always defaults to `pending`), and (for papers with concrete benchmarks/sims) `input_artifact_refs`. Least reliable: `artifact_type`, `uncertainty_summary`, and `comparison_target`.
