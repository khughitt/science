# Science Skills Corpus Classification Matrix

> **Post-reorg note:** the `path`/`name`/`subject` columns below are **pre-reorg** — this matrix was phase 3's input, not its output; rows are left unrewritten.

> Companion artifact to `2026-07-19-skills-taxonomy-and-templates-design.md`. This is
> the ratifying classification of the whole skills corpus against the taxonomy. It
> validates which archetypes earn a template (this phase) **and** it is the primary
> input to the downstream corpus-migration project (reorg + rename + `archetype`
> backfill + hub extraction). Classification is by each skill's **promised operation**,
> not its directory or name.

Corpus as of 2026-07-19: **46 files** — 1 index, 7 routers (4 hubs, 3 pure), 38 leaves.

## Matrix

| path | role | router-state | archetype | subject | depth | source-basis | expected-output | boundary? | likely-split? |
|---|---|---|---|---|---|---|---|---|---|
| INDEX.md | index | — | — | research-infra | standard | internal | which leaf(s) to load for the current task | — | — |
| data/SKILL.md | router | hub | — | data-management | standard | external-spec (edam) | data directory layout + dataset-entity workflow decision | — | y — Principles + Output-Path Convention + "When Adding a New Data Source" are doctrine, not routing |
| data/embeddings-manifold-qa.md | leaf | — | measurement-qa | embeddings | standard | external-tool (umap, hdbscan) | QA verdict on which embedding structure survives nuisance/seed/negative-control checks | — | — |
| data/expression/bulk-rnaseq-qa.md | leaf | — | measurement-qa | transcriptomics | standard | external-tool (deseq2, edger) | per-cohort QA package + counts-vs-TPM/DE-tool decision | — | — |
| data/expression/microarray-qa.md | leaf | — | measurement-qa | transcriptomics | standard | external-tool (limma) | per-cohort QA package + probe-to-gene collapse decision | — | — |
| data/expression/scrna-qa.md | leaf | — | measurement-qa | transcriptomics | standard | external-tool (scanpy; +cite tirosh-2016) | per-cohort QA package (doublets/ambient/batch) + pseudobulk decision | — | — |
| data/expression/SKILL.md | router | hub | — | transcriptomics | standard | internal | which expression-modality leaf to load + cross-cutting preflight answers | — | y — universal pre-flight checklist + 3 idioms + cross-platform-aggregation strategy are transferable doctrine |
| data/frictionless.md | leaf | — | normative-reference | data-management | standard | external-spec (frictionless-spec; +tool frictionless) | a validated datapackage.json descriptor for a data directory | tool-guide (CLI layered on the contract) | y — split contract vs. tooling at migration |
| data/functional-genomics-qa.md | leaf | — | measurement-qa | functional-genomics | standard | external-tool (depmap, mageck) | QA package separating perturbation effect from assay/growth confounds | — | — |
| data/genomics/copy-number-sv-qa.md | leaf | — | measurement-qa | genomics | standard | external-tool (ampliconarchitect) | CN/SV/amplicon QA package conditioned on ploidy/purity + AA/AC version | — | — |
| data/genomics/mutational-signatures-and-selection.md | leaf | — | measurement-qa | genomics | standard | external-tool (cosmic-signatures, dndscv) | signature/selection QA package + opportunity-model statement | method-guide (method selection) | y — possible signature-vs-selection split at migration |
| data/genomics/SKILL.md | router | pure-router | — | genomics | standard | internal | which genomics-QA leaf to load, and in what order | — | — |
| data/genomics/somatic-mutation-qa.md | leaf | — | measurement-qa | genomics | standard | internal | mutation-call QA tables with callable-territory-aware frequencies | — | — |
| data/protein-sequence-structure-qa.md | leaf | — | measurement-qa | protein-structure | standard | external-tool (uniprot, foldseek) | protein dataset QA package + homology-disjoint split plan | — | — |
| data/proteomics-qa.md | leaf | — | measurement-qa | proteomics | standard | internal | proteomics QA package (rollup/missingness/batch) + verdict caveats | — | — |
| data/sources/openalex.md | leaf | — | tool-guide | literature-sources | standard | external-tool (openalex) | ranked, provenance-tagged OpenAlex search-results file | — | — |
| data/sources/pubmed.md | leaf | — | tool-guide | literature-sources | standard | external-tool (ncbi-eutilities) | ranked, provenance-tagged PubMed search-results file | — | — |
| pipelines/marimo.md | leaf | — | tool-guide | pipelines | standard | external-tool (marimo) | a working marimo notebook + optional result manifest | — | — |
| pipelines/runpod.md | leaf | — | tool-guide | pipelines | standard | external-tool (runpod) | customized push/setup/run/pull scripts for a GPU pod job | — | — |
| pipelines/SKILL.md | router | hub | — | pipelines | standard | internal | which execution substrate to load | — | y — "cross-cutting principles" (reproducibility triad) is doctrine |
| pipelines/snakemake.md | leaf | — | tool-guide | pipelines | standard | external-tool (snakemake; +cite molder-snakemake) | a Snakefile/rule set + datapackage.json manifest | — | — |
| research/annotation-curation-qa.md | leaf | — | measurement-qa | curation | standard | internal | curated-label QA package with agreement metrics + adjudication log | analysis-discipline (halt gates), normative-reference (schema versioning) | — |
| research/citation-discipline.md | leaf | — | normative-reference | research-methodology | standard | internal | a citation/source-pointer that conforms to the project's citation contract (BibTeX key resolves; annotation token present when unsourced) | — | — |
| research/literature-evaluation.md | leaf | — | practice-guide | research-methodology | standard | internal | a source set with provenance/publication-status recorded per item, claims traced to sources, and `[UNVERIFIED]` marks on anything not cross-checked | — | — |
| research/proposition-graph-reasoning.md | leaf | — | analysis-discipline | research-methodology | standard | internal | an interpretation correctly flagged against the proposition-graph outcome conditions (migration-limited, contested, single-source-fragile, lacks-empirical-support, high-uncertainty) rather than a certified verdict | — | — |
| research/proposition-schema.md | leaf | — | normative-reference | epistemics | standard | internal | correctly enum-valued proposition/evidence frontmatter | — | — |
| research/research-package-rendering.md | leaf | — | practice-guide | research-infra | standard | internal | a working `/src` provenance route wired to a research package | resolved 2026-07-20 (acknowledged force-fit); NOT the basis for practice-guide eligibility; phase-3 relocation candidate — a web-app implementation guide living under research/ | y — revisit if a second build-a-component leaf appears |
| research/research-package-spec.md | leaf | — | normative-reference | research-infra | standard | internal | a valid research-package datapackage.json + cells.json bundle | — | — |
| research/SKILL.md | router | pure-router | — | research-methodology | standard | internal | source-hierarchy-compliant research approach + which research leaf to load | — | — (extracted 2026-07-20) |
| statistics/bayesian-workflow.md | leaf | — | method-guide | statistics | standard | external-methodology (baygent-skills; +cite gelman, vehtari-loo) | a fitted, convergence-gated, calibration-checked Bayesian model + reported interval | — | — |
| statistics/bias-vs-variance-decomposition.md | leaf | — | analysis-discipline | statistics | standard | internal | an error-term decomposition gating which fix (more replicates vs bias correction) is legitimate | method-guide (surface reads like estimator selection) | — |
| statistics/causal-identification.md | leaf | — | analysis-discipline | statistics | standard | external-methodology (baygent-skills; +cite hernan-robins, pearl, vanderweele-ding, rosenbaum) | a certified adjustment set or a fail-closed non-identification verdict | — | — |
| statistics/compositional-data.md | leaf | — | method-guide | statistics | standard | internal | a chosen transform/model family for proportion-valued data + QA checks | analysis-discipline | — |
| statistics/estimator-certification.md | leaf | — | analysis-discipline | statistics | standard | internal | reject / do-not-reject / INDETERMINATE verdict on a numeric fit, with the E ≤ ρ·σ_null budget | — | — |
| statistics/likelihood-model-comparison.md | leaf | — | method-guide | statistics | standard | external-methodology (baygent-skills; +cite vehtari-loo) | a well-posedness-checked AIC/BIC/LRT or LOO/ELPD selection with bootstrap stability | — | — |
| statistics/population-genetics-likelihood.md | leaf | — | method-guide | popgen | standard | internal | a constructed WF/Moran/segregation likelihood + neutral-vs-selection comparison | — | — |
| statistics/power-floor-acknowledgement.md | leaf | — | analysis-discipline | statistics | standard | internal | a stated minimum-detectable-effect floor gating how a null/weak result may be worded | — | — |
| statistics/prereg-amendment-vs-fresh.md | leaf | — | analysis-discipline | statistics | standard | internal | amendment-vs-fresh classification + inheritance table for a follow-up pre-reg | — | — |
| statistics/prereg-defensive-instrumentation.md | leaf | — | analysis-discipline | statistics | standard | internal | locked universe/candidate/tripwire/decision-table instrumentation attached to a pre-reg | — | — |
| statistics/replicate-count-justification.md | leaf | — | analysis-discipline | statistics | deep-reference | internal | a locked replicate count R (or B, or m) from a measured pilot rule | — | — |
| statistics/sensitivity-arbitration.md | leaf | — | analysis-discipline | statistics | standard | external-methodology (baygent-skills) | a mechanically-produced verdict from a pre-committed sensitivity/veto table | — | — |
| statistics/SKILL.md | router | hub | — | statistics | standard | internal | which statistics leaf(s) govern the analysis at hand | — | y — 14 numbered Principles restate each leaf (trim to pointers, don't extract) |
| statistics/survival-and-hierarchical-models.md | leaf | — | method-guide | statistics | standard | external-methodology (baygent-skills) | a fitted Cox/Weibull/hierarchical model with PH/shrinkage diagnostics | — | — |
| statistics/time-series-and-longitudinal-models.md | leaf | — | method-guide | statistics | standard | internal | a time-origin/cadence/lag-specified longitudinal model + pre-specified lag sensitivity grid | — | — |
| writing/scientific-writing.md | leaf | — | practice-guide | writing | standard | internal | a document conforming to its framework template, with every claim cited or annotated, hedging matched to evidence strength, and links to the hypotheses/questions/propositions it bears on | — | — |
| writing/SKILL.md | router | pure-router | — | writing | standard | internal | correctly hedged, cited, formatted project prose | — | — (extracted 2026-07-20) |

## Boundary cases (adjudicated)

- **`mutational-signatures-and-selection` → measurement-qa** (not method-guide): structurally identical to its sibling QA leaves and framed by its parent hub as the "analysis QA" layer paired with `somatic-mutation-qa`'s "input QA" layer. Its one method-selection sentence is a QA rule inside the leaf, not its organizing verb. Flagged for a possible signature-vs-selection split at migration.
- **`annotation-curation-qa` → measurement-qa** (subject=curation): "curation is measurement" — carries the full QA skeleton (pre-flight, agreement metrics, failure modes, halt-on, output package) generalized to curated labels. Proves the archetype spans past biological data. Real analysis-discipline (halt gates) and normative-reference (schema versioning) content exists but neither dominates the structure.
- **`frictionless` → normative-reference** (primary source kind=`spec`): core content is the datapackage.json contract; CLI commands are operating instructions layered on top. Split candidate at migration.
- **`bias-vs-variance-decomposition` → analysis-discipline**: verbs are name / decompose / decide-what-shrinks; ends in decision rules that gate reporting language.
- **`compositional-data` → method-guide**: organizing content is a transform-selection table (CLR/ALR/ILR/…), verb = select/construct; structural sibling of the other `*-models` leaves.
- **`research-package-rendering` → practice-guide** (resolved 2026-07-20, acknowledged force-fit): a software *implementation* guide — the corpus's only build-a-component leaf. Not `normative-reference` (that is its sibling `research-package-spec.md`, which it builds on as "layer 1"); not `tool-guide` (remark/rehype and vega-embed are named as interchangeable, so no single tool is operated — the other five tool-guides operate a tool, this one builds a component); not `method-guide` (estimand/fitting/diagnostics slots are analysis-shaped). Classified `practice-guide` because minting a seventh `implementation-guide` archetype would violate the two-target eligibility rule at a population of one, and the practice-guide slots do map (When to Use → when-to-apply; the five pattern sections → workflow steps; route-specificity, permalink fallback, and RFC 4180 handling → judgment rules; the natural-systems reference implementation → outputs). It remains **not** the basis for practice-guide eligibility — that still rests on the two hub extractions. Trip-wire recorded in `skills/meta/skill-authoring.md`; flagged as a phase-3 relocation candidate.
- **`data/genomics/SKILL.md` → pure-router**: its one substantive sentence is an ordering/routing instruction, not free-standing doctrine — unlike its hub siblings.

## Archetype tally (leaves)

| Archetype | Count | Members |
|---|---|---|
| measurement-qa | 11 | embeddings-manifold-qa, bulk-rnaseq-qa, microarray-qa, scrna-qa, functional-genomics-qa, copy-number-sv-qa, mutational-signatures-and-selection, somatic-mutation-qa, protein-sequence-structure-qa, proteomics-qa, annotation-curation-qa |
| analysis-discipline | 9 | bias-vs-variance, causal-identification, estimator-certification, power-floor, prereg-amendment-vs-fresh, prereg-defensive-instrumentation, replicate-count-justification, sensitivity-arbitration, proposition-graph-reasoning |
| method-guide | 6 | bayesian-workflow, compositional-data, likelihood-model-comparison, population-genetics-likelihood, survival-and-hierarchical-models, time-series-and-longitudinal-models |
| tool-guide | 5 | openalex, pubmed, marimo, runpod, snakemake |
| normative-reference | 4 | frictionless, proposition-schema, research-package-spec, citation-discipline |
| practice-guide | 3 | research-package-rendering (resolved 2026-07-20, acknowledged force-fit — see boundary cases), literature-evaluation (extracted 2026-07-20), scientific-writing (extracted 2026-07-20) |
| unresolved | 0 | — |

## Earns-a-template check (this phase)

Eligibility rule (recorded doctrine): **template eligibility considers both existing leaves and independently identifiable practices embedded in hubs, provided at least two concrete target extractions demonstrate the same content contract and success test.**

- **measurement-qa (11)** — PASSES. Slots: pre-flight checklist, QA metrics table, failure-modes list, halt-on conditions, fixed output-package tree. Success test: does the produced QA package contain the named files and state which halt-on conditions were evaluated?
- **analysis-discipline (8)** — PASSES. Slots: triggering condition, the required reasoning/check/precommitment, decision rule or reasoning criteria, outcomes (pass/fail/indeterminate or branch/threshold selected), override/halt conditions. Success test: was the required reasoning/precommitment carried out *before* interpretation, and does the conclusion follow from it — mechanically where a locked table applies, by the stated criteria otherwise?
- **method-guide (6)** — PASSES. Slots: applicability/non-applicability, estimand & assumptions, model/procedure choices, fitting, diagnostics, failure modes, reporting. Success test: are applicability and assumptions stated, is the model/procedure selection justified, and are model-specific diagnostics present with a verdict downgrade when they fail?
- **tool-guide (5)** — PASSES. Slots: setup/version pin, command/API surface, failure handling (+ rate limits), verification/smoke-test. Success test: does the skill complete and verify a *representative operation* end-to-end, including recovery from a common failure?
- **normative-reference (3)** — PASSES (thin but coherent). Slots: scope, vocabulary/schema/enums, invariants, conformance rules, examples, versioning/migration, invalid cases. Success test: is there an explicit conformance check against the vocabulary/invariants — mechanical (lint/validate) where available, an itemized checklist otherwise?
- **practice-guide (2 clean leaves, extracted 2026-07-20 — this count deliberately excludes the force-fitted `research-package-rendering`; see Boundary cases)** — PASSES **under the eligibility rule**: two concrete extraction targets share the contract — (1) scientific writing (`writing/SKILL.md`, 108 lines, zero leaves) and (2) literature evaluation (`research/SKILL.md`'s Source Hierarchy / Confidence Calibration / Evaluating Sources / Synthesis). Slots: when-to-apply, workflow steps, judgment rules, quality criteria, common pitfalls, outputs. Success test: did the agent carry out the cross-cutting practice according to its workflow, judgment rules, and quality criteria?

**Final catalog (6 templates):** measurement-qa · method-guide · analysis-discipline · normative-reference · tool-guide · practice-guide. Plus a minimal **router profile** template (structural, not a leaf archetype).

## Hub extraction candidates (migration-phase input, not this phase)

- **`data/SKILL.md`** → extract Principles + Output-Path Convention + "When Adding a New Data Source" into a `data-management-conventions` practice-guide; leave a pure routing table.
- **`data/expression/SKILL.md`** → extract the universal pre-flight checklist + 3 idioms + cross-platform aggregation into a shared `transcriptomics-preflight` measurement-qa (or practice-guide); leave routing + failure-mode summary.
- **`pipelines/SKILL.md`** → extract "cross-cutting principles" (reproducibility triad, side-effects-outside-tree) into a `pipeline-reproducibility` practice-guide; leave a pure decision table.
- **`research/SKILL.md`** (largest doctrine load) — **DONE 2026-07-20**: extracted into (1) Source Hierarchy + Confidence Calibration + Evaluating Sources + Synthesis → `literature-evaluation` **practice-guide**; (2) Working with Hypotheses + Evidence Classification → `proposition-graph-reasoning` **analysis-discipline**; (3) Citation Discipline + Template Usage → `citation-discipline` **normative-reference**.
- **`statistics/SKILL.md`** (borderline) → **tighten, don't extract**: trim each of the 14 Principles to a one-line pointer (match `data/genomics/SKILL.md`'s discipline).
- **`writing/SKILL.md`** (most acute — zero leaves) — **DONE 2026-07-20**: extracted into `scientific-writing` **practice-guide** (Hedging, Annotation Tokens, Citation Format, Document Structure, Length Guidelines).
