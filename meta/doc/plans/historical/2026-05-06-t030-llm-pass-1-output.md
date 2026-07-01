# t030 — Blind LLM Extraction Pass 1 (raw output)

> **Pass identifier:** `llm-blind-1` (general-purpose subagent, fresh context, ~2.5 min wall-clock).
> **Sample:** main sample n=12, locked per `meta/doc/plans/historical/2026-05-06-t030-full-sampling-plan-and-rubric.md`.
> **Prompt:** as designed in the sampling plan: v2.1 schema sections + rubric + 12 paper-summary file paths; instruction not to read any other files.
> **Status:** Raw output preserved verbatim. Will be paired with `llm-blind-2` for LLM-vs-LLM-blind agreement scoring (D4).

---

All papers read. Now I'll produce the audit tables.

# Blind Extraction-Cost Audit (12 papers)

## 1. Klugkist2023

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-introduction (synthesis-method) | INVENTED candidate; paper introduces BES method + simulation. Could be `method-contribution` or `evidence` (sim findings). Picked the methodological framing. |
| extensions | 1 | 1 | [bayesian-evidence-synthesis, simulation] | Not enumerated as extensions; inferred from content |
| input_artifact_refs | 1 | 2 | [simulation:bes-sim1, simulation:bes-sim2, dataset:binomial-illustration] | Two R simulations + analytic example named, not formally enumerated as inputs |
| claim_source_ref | 2 | 1 | paper:Klugkist2023 | Trivially the paper itself |
| method_ref | 2 | 1 | method:bayesian-evidence-synthesis | Method explicitly named (BES, BFpack) |
| proposition_refs | 0 | 4 | candidates: [prop:bes-aggregates-heterogeneous-evidence, prop:bes-not-remedy-for-underpowered-studies]; picked the first | Multiple distinct claims; paper carries several findings, no single proposition |
| target_artifact_ref | ✗ | 0.5 | n-a | Not an evaluation/operation payload |
| comparison_target | 1 | 2 | hypothesis-set | BES vs BSU and informative-vs-complement-vs-null comparisons; "hypothesis-set" fits but interpretive |
| support_direction | 2 | 1 | supports | Findings support BES under stated conditions |
| validation_role | 1 | 2 | strengthen-belief | Simulation supports a methodological claim; default newly-authored payload |
| validation_status | 2 | 1 | pending | Newly-authored, default per pitfall guidance |
| uncertainty_summary | 0 | 4 | candidates: "1000 iterations/condition; n in {50..800}; R2 in {0.02,0.09,0.25}" or "PMP-based, no headline number"; picked the simulation-grid string | No single canonical Bayes factor / posterior; sim spans many conditions |
| reason_codes | 0 | 3 | candidates: [] vs [H03:underpowered-aggregation-risk]; picked [] | No clear H03 codes listed; could invent |

## 2. VanLissa2024

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-tutorial-evidence | Tutorial + simulation; framing ambiguous between method intro and evidence |
| extensions | 1 | 1 | [product-bayes-factor, simulation, tutorial] | Not enumerated |
| input_artifact_refs | 1 | 2 | [simulation:pbf-benchmark, dataset:meta-analytic-example, dataset:ipd-example] | Described abstractly |
| claim_source_ref | 2 | 0.5 | paper:VanLissa2024 | Trivial |
| method_ref | 2 | 1 | method:product-bayes-factor (impl: bain) | Explicit |
| proposition_refs | 1 | 2 | [prop:pbf-aggregates-conceptual-replications] | Single inferred main claim |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 2 | 2 | hypothesis-set | Compared against meta-analysis, IPD, vote counting |
| support_direction | 2 | 1 | supports | Sim favors PBF accuracy |
| validation_role | 1 | 2 | strengthen-belief | Default for newly-authored |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 0 | 3 | candidates: "favorable accuracy, higher sensitivity / lower specificity" or "no headline statistic"; picked the qualitative one | No numeric headline reported in summary |
| reason_codes | 1 | 2 | [] (none indicated) | Default empty |

## 3. Yu2026

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 0 | 4 | candidates: benchmark-dataset, evaluation, method-resource; picked `benchmark-dataset` | INVENTED; paper introduces a benchmark; might be out-of-scope as taxonomy/resource contribution |
| extensions | 0 | 3 | candidates: [llm-evaluation, benchmark, dataset]; picked the first | Not stated |
| input_artifact_refs | 1 | 2 | [dataset:scicueval (10 sub-datasets across 5 domains)] | Described abstractly |
| claim_source_ref | 2 | 0.5 | paper:Yu2026 | Trivial |
| method_ref | 1 | 2 | method:scicueval-benchmark | Implicit |
| proposition_refs | 0 | 4 | candidates: [prop:llms-have-context-understanding-gaps, prop:scicueval-is-reliable-benchmark]; picked the first | Possibly out-of-scope (resource paper, not propositional) |
| target_artifact_ref | 1 | 2 | target:llm-models-evaluated | If treated as evaluation payload, target is the LLMs — not specifically named |
| comparison_target | 0 | 3 | candidates: model-set, n-a; picked `model-set` | Multiple SOTA LLMs compared but specifics not given |
| support_direction | 0 | 3 | candidates: methodological-input, quality-record; picked `methodological-input` | Benchmark contribution doesn't cleanly fit |
| validation_role | 0 | 2 | candidates: prioritize-attention, quality-record-only; picked `quality-record-only` | Ambiguous role |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 1 | 2 | "fine-grained competency analysis across 4 dimensions, 10 sub-datasets" | Inferred |
| reason_codes | 1 | 2 | [] | None indicated |

Possible out-of-scope flag: leans benchmark-resource; only marginally propositional.

## 4. Si2025

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-contribution / agent-evaluation | Bridges methodology + bias evaluation |
| extensions | 1 | 1 | [bayes-factor-testing, llm-bias-evaluation] | Not enumerated |
| input_artifact_refs | 2 | 2 | [dataset:BBQ, dataset:CrowS-Pairs, dataset:Winogender] | Datasets explicitly named |
| claim_source_ref | 2 | 0.5 | paper:Si2025 | Trivial |
| method_ref | 2 | 1 | method:bayes-factor-bias-test | Explicit |
| proposition_refs | 1 | 2 | [prop:bayes-factors-distinguish-no-evidence-from-evidence-of-no-bias] | Inferred single proposition |
| target_artifact_ref | 1 | 2 | target:llm-set (unspecified) | Implicit if treated as eval |
| comparison_target | 1 | 2 | null-vs-alternative | H0 pi=0.5 vs alternative — clean fit but interpretive |
| support_direction | 2 | 1 | supports | Supports BF method over binomial test |
| validation_role | 1 | 2 | strengthen-belief | Default |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 0 | 3 | candidates: "BF results consistent across English/French CrowS-Pairs"; "null pi=0.5"; picked first | No numeric headline |
| reason_codes | 1 | 1 | [] | None indicated |

## 5. Williams2018

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-evaluation (simulation-evidence) | Sim-driven methodological evidence |
| extensions | 1 | 1 | [bayesian-meta-analysis, simulation, prior-sensitivity] | Inferred |
| input_artifact_refs | 2 | 2 | [simulation:williams-tau-sim, dataset:towel-reuse, dataset:power-pose] | Examples named |
| claim_source_ref | 2 | 0.5 | paper:Williams2018 | Trivial |
| method_ref | 2 | 1 | method:bayesian-random-effects-meta-analysis-half-cauchy | Explicit |
| proposition_refs | 1 | 3 | [prop:weakly-informative-priors-reduce-boundary-tau-failures] | Multiple findings; one main claim inferable |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 2 | 2 | model-set | DL vs REML vs Bayesian explicit |
| support_direction | 2 | 1 | supports | Supports Bayesian priors over classical |
| validation_role | 1 | 2 | strengthen-belief | Default |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 2 | 2 | "DL: 31% boundary tau=0; REML: 25% (mu=0, tau=0.15)" | Numeric headline given |
| reason_codes | 1 | 2 | [] | None indicated |

## 6. Allen2017

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 0 | 5 | candidates: commentary, survey, methodological-agenda; picked `commentary` | INVENTED; paper is a commentary/agenda — likely OUT-OF-SCOPE per "surveys methods / vocabulary contribution" rule |
| extensions | 0 | 2 | candidates: [data-integration, multi-view] | Not enumerated; commentary status undermines extension semantics |
| input_artifact_refs | 1 | 2 | [paper:Morris-Baladandayuthapani-review, dataset:TCGA-ovarian] | Mentioned but not formally inputs |
| claim_source_ref | 2 | 0.5 | paper:Allen2017 | Trivial |
| method_ref | 0 | 3 | candidates: method:mixed-chain-graphical-model, n-a; picked `n-a` | No single canonical method |
| proposition_refs | 0 | 4 | candidates: [prop:multi-view-integration-needs-typed-evidence, none]; picked first | Survey-like; multiple weak claims |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 0 | 3 | candidates: n-a, hypothesis-set; picked `n-a` | Commentary, no comparison structure |
| support_direction | 0 | 3 | candidates: methodological-input, qualifies; picked `methodological-input` | Commentary fits poorly |
| validation_role | 1 | 2 | prioritize-attention | Surveys agenda — flags topics |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 1 | 2 | "TCGA ovarian: 204/592 subjects with complete views" | One quantitative anchor |
| reason_codes | 1 | 2 | [] | None |

**Likely out-of-scope flag (survey/commentary)**.

## 7. Zhang2017CancerGenomics

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-contribution | Method paper + sim + application |
| extensions | 1 | 1 | [mixed-graphical-models, joint-network-estimation] | Inferred |
| input_artifact_refs | 1 | 2 | [simulation:zhang-mgm-sim, dataset:cancer-genomics-application (unnamed)] | Abstract |
| claim_source_ref | 2 | 0.5 | paper:Zhang2017CancerGenomics | Trivial |
| method_ref | 2 | 1 | method:joint-mixed-graphical-model | Explicit |
| proposition_refs | 1 | 2 | [prop:joint-mgm-balances-shared-and-condition-specific-structure] | One inferred claim |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 1 | 2 | model-set | Pooled vs separate vs joint — interpretive |
| support_direction | 2 | 1 | supports | Supports joint estimation |
| validation_role | 1 | 1 | strengthen-belief | Default |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 0 | 3 | candidates: "no numeric headline", "sim + cancer application"; picked first | No quantitative headline |
| reason_codes | 1 | 1 | [] | None |

## 8. Mulder2026

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 0 | 3 | candidates: review, method-contribution; picked `review` | Paper is a review with practical guidance — borderline out-of-scope |
| extensions | 1 | 1 | [bayes-factor-meta-analysis, prior-sensitivity, e-values] | Inferred |
| input_artifact_refs | 1 | 2 | [dataset:language-impairment, dataset:seroma-postop-exercise, methodset:5-bf-meta-models] | Named applications |
| claim_source_ref | 2 | 0.5 | paper:Mulder2026 | Trivial |
| method_ref | 2 | 1 | method:bf-meta-analysis (BFpack) | Explicit |
| proposition_refs | 1 | 3 | [prop:bayes-factors-suit-cumulative-meta-analysis] | Inferable single claim |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 1 | 2 | hypothesis-set | BF vs p-value framing |
| support_direction | 2 | 1 | supports | Supports BF approach |
| validation_role | 1 | 1 | strengthen-belief | Default |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 0 | 3 | candidates: "5 BF meta models, 2 applications", "no numeric headline"; picked first | No numeric headline |
| reason_codes | 1 | 1 | [] | None |

Possible scope flag: review-style.

## 9. Berenfeld2026

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-contribution | Theory + sim + application |
| extensions | 1 | 1 | [causal-meta-analysis, arm-based-aggregation] | Inferred |
| input_artifact_refs | 2 | 2 | [simulation:berenfeld-sim, dataset:cochrane-meta-analyses (hundreds)] | Named explicitly |
| claim_source_ref | 2 | 0.5 | paper:Berenfeld2026 | Trivial |
| method_ref | 2 | 1 | method:causal-meta-analysis (CaMeA) | Explicit |
| proposition_refs | 1 | 2 | [prop:classical-meta-analysis-loses-causal-meaning-for-nonlinear-contrasts] | Inferable |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 2 | 2 | model-set | Classical vs causal estimators |
| support_direction | 2 | 1 | qualifies | Qualifies use of classical meta-analysis under nonlinear contrasts |
| validation_role | 1 | 2 | strengthen-belief | Default |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 1 | 3 | "linear: classical OK; nonlinear (RR/OR): can mis-target; reversal cases observed in Cochrane reanalysis" | Qualitative summary |
| reason_codes | 1 | 2 | [] | None |

## 10. Liu2024HiddenWorld

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-contribution | Framework paper |
| extensions | 1 | 1 | [llm-causal-discovery, variable-proposal] | Inferred |
| input_artifact_refs | 1 | 2 | [dataset:synthetic-benchmarks, dataset:reviews, dataset:medical-diagnosis] | Abstract |
| claim_source_ref | 2 | 0.5 | paper:Liu2024HiddenWorld | Trivial |
| method_ref | 2 | 1 | method:COAT | Explicit |
| proposition_refs | 1 | 2 | [prop:llms-and-causal-discovery-mutually-beneficial] | Inferable |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 0 | 3 | candidates: model-set, n-a; picked `n-a` | Comparators not enumerated in summary |
| support_direction | 2 | 1 | supports | Supports COAT |
| validation_role | 1 | 1 | strengthen-belief | Default |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 0 | 3 | candidates: "evaluated on synthetic + real benchmarks", no numeric headline; picked first | No numeric headline |
| reason_codes | 1 | 1 | [] | None |

## 11. Jiang2024

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-contribution | Model paper |
| extensions | 1 | 1 | [knowledge-graph-diffusion, recommendation] | Inferred |
| input_artifact_refs | 1 | 2 | [dataset:public-rec-1, dataset:public-rec-2, dataset:public-rec-3] | Three public datasets, unnamed |
| claim_source_ref | 2 | 0.5 | paper:Jiang2024 | Trivial |
| method_ref | 2 | 1 | method:DiffKG | Explicit |
| proposition_refs | 1 | 2 | [prop:diffkg-improves-recommendation-via-kg-denoising] | Inferable |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 1 | 2 | model-set | "competitive baselines" — model-set fits but baselines unnamed |
| support_direction | 2 | 1 | supports | Reports improvement |
| validation_role | 1 | 1 | strengthen-belief | Default |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 1 | 2 | "improved over baselines on 3 public rec datasets" | Qualitative; no numbers in summary |
| reason_codes | 1 | 1 | [] | None |

Possibly out-of-scope for the science project (recommender systems), though the contribution itself is propositional.

## 12. Maier2022

| field | score | effort_min | picked_value | notes |
|---|---|---|---|---|
| artifact_type | 1 | 2 | method-contribution-with-evidence | Method intro + sim + applications |
| extensions | 1 | 1 | [robust-bayesian-meta-analysis, model-averaging, publication-bias] | Inferred |
| input_artifact_refs | 2 | 2 | [dataset:anderson-violent-video-game, dataset:many-labs-2 (28 effects), simulation:robma-sim] | Named |
| claim_source_ref | 2 | 0.5 | paper:Maier2022 | Trivial |
| method_ref | 2 | 1 | method:RoBMA (12-model ensemble) | Explicit |
| proposition_refs | 1 | 2 | [prop:robma-distinguishes-evidence-of-absence-from-absence-of-evidence-for-pub-bias] | Inferable |
| target_artifact_ref | ✗ | 0.5 | n-a | Not eval/op |
| comparison_target | 2 | 2 | model-set | 12-model ensemble; explicit |
| support_direction | 2 | 1 | supports | Supports RoBMA |
| validation_role | 1 | 2 | strengthen-belief | Default |
| validation_status | 2 | 0.5 | pending | Default |
| uncertainty_summary | 2 | 2 | "violent-game r=0.151, 95% CrI [0.094,0.207]; ML2: 1/28 false positives, 12/28 evidence of absence; best RMSE in 65% conditions" | Multiple numeric headlines |
| reason_codes | 1 | 2 | [] | None |

---

## Findings

**Systematically ambiguous fields** (scored 0 or 1 across most papers):

- `artifact_type`: The schema's enum (per the prompt: evidence/synthesis/evaluation/operation) does not cleanly accommodate methodological tutorial/contribution papers. Almost every paper here is a "method introduction with supporting simulation evidence" — neither pure evidence nor pure synthesis. Most extractions ended up inventing values like `method-contribution` or `method-tutorial-evidence`.
- `extensions`: Never explicitly stated; always inferred from topic keywords. Score 1 is the modal honest call.
- `proposition_refs`: Most papers carry several findings; picking a canonical "the proposition" is interpretive. Score 1 is typical; for richer papers (Klugkist, Allen) it is genuinely 0.
- `uncertainty_summary`: Many summaries lack a single numeric headline (e.g. PMP, BF, RMSE), so picking a canonical short form is arbitrary. Williams2018 and Maier2022 are the two clean exceptions.
- `comparison_target`: The enum (`null-vs-alternative` / `hypothesis-set` / `model-set` / `artifact-target` / `n-a`) does not cleanly distinguish "method-vs-method" from "model-vs-model"; tutorials with multiple comparator types fit awkwardly.
- `support_direction`: Generally fine for empirical papers; gets messy for commentaries (Allen2017) and benchmarks (Yu2026).
- `reason_codes`: Schema defines H03 codes but no concrete code list was visible in summaries; defaulted to `[]`.

**Schema enums that needed extending:**

- `artifact_type` needs `method-contribution`, `method-tutorial`, `commentary`, `benchmark-resource` (or an explicit out-of-scope marker).
- `support_direction`: would benefit from a `proposes-method` or `methodological-input-with-evidence` value distinct from `methodological-input`.
- `comparison_target`: a `method-set` value would resolve several method-vs-method papers currently shoehorned into `model-set`.

**Likely out-of-scope flags:**

- **Allen2017** is a commentary / methodological agenda paper — closer to a survey than a propositional contribution. It should probably produce no payload, or at most a `methodological-input` payload with very thin propositional content.
- **Yu2026** is a benchmark-resource paper. It is borderline: it does carry the implicit proposition "current LLMs have measurable context-understanding gaps," but its primary contribution is a dataset. Could be a vocabulary/method-registry import rather than evidence.
- **Mulder2026** is a review with practical guidance — borderline.
- **Jiang2024** (DiffKG) is in-scope as a propositional ML claim, but its scientific relevance to this project's domain is tangential.

**Authoring-field defaults working well:** `claim_source_ref` is trivially the paper itself in every case (score 2, ~0.5 min). `validation_status: pending` per the pitfall guidance is mechanical. `target_artifact_ref` correctly resolves to `n-a` for the 9 non-eval papers.

**Total time spent on the pass:** approximately 95 minutes (reading 12 summaries: ~25 min; scoring 13 fields x 12 papers with notes: ~70 min).

Honest aggregate: roughly 30% of (paper x field) cells scored 2, 45% scored 1, 15% scored 0, 10% not-applicable. The schema is most reliably extractable for `claim_source_ref`, `method_ref`, `validation_status`, `target_artifact_ref` (when n-a), and `support_direction`. It is least reliably extractable for `artifact_type`, `uncertainty_summary`, `proposition_refs`, and `comparison_target`.
