# t034 Pilot Extraction (3 papers, v1.1)

> **Status:** Pilot extraction (2026-05-06). Empirical pressure-test of `[t034]` v1.1 (`meta/doc/plans/2026-05-06-t034-causal-graph-extension-design.md`). Three Batch-3 papers extracted to v1.1 payload shape: Faller2024 (graph-diagnostic), Zuber2025 (mr-graph-model + stage-(b) sketch), Dugourd2021 (mechanistic-hypothesis-bundle). Mirrors the `[t030]` rubric so findings are comparable.
>
> **Goal:** find the gaps between the v1.1 schema and what authors can actually produce from existing project content. Surfaces field-overload, field-drift, and authoring ambiguities the worked examples didn't.

**Sources:**
- `meta/doc/background/papers/Faller2024.md`
- `meta/doc/background/papers/Zuber2025.md`
- `meta/doc/background/papers/Dugourd2021.md`

**Method:** for each paper, author the payload(s) that the paper's content actually produces in this project. Use *only* the project's existing paper-summary as input (not the source PDF) — this models the realistic Science authoring workflow. Score each field per the t030 rubric: **2** stated explicitly; **1** clearly inferable from summary; **0** ambiguous (multiple plausible fillings); **✗** not present in summary AND not authoring-stage (would require PDF re-read or external lookup); **A** authoring field (mechanical, not paper-content).

---

## Pre-extraction surprise: most Batch-3 papers produce *methods-paper* claims, not t034 extension payloads

Working through the three papers immediately surfaces a classification problem the design doc's worked examples papered over: a paper that *introduces* a method (Petersen2014, Faller2024, Ban2023, Wan2025, Zhang2021gCastle, the Faller2024 case here) produces a `methods-paper` paper-extracted-claim about the method's properties — that lives in `[t022]` core, not in any t034 extension. A t034 extension payload (e.g., `graph-diagnostic`) is only authored when *Science applies the method* to one of its own causal graphs. The PDF often *also* contains a worked application (Zuber's mental-health case, Dugourd's ccRCC case, Faller's synthetic-data experiment) — which is itself a t034-extension payload, but authored from the paper *as evidence about that application*, not as evidence about the method.

So each paper potentially produces *two* payloads in this project: (a) a methods-paper paper-extracted-claim, (b) an extension payload re-encoding the paper's own worked application. Below I extract (b) where the summary supports it.

---

## Extraction 1 — Faller2024 → graph-diagnostic + methods-paper

The summary describes self-compatibility's *method*; its applied content is a single sentence: "Experiments show the incompatibility score can correlate with structural Hamming distance and aid model selection in some settings." The summary names no specific dataset, no specific causal-discovery algorithm under audit, no specific threshold, no specific score value. So an applied `graph-diagnostic` payload faithful to the summary cannot be fully populated.

**(a) Methods-paper payload (core-only).** Trivial under v2.2: artifact_type `methods-paper`, source_direction `framework-proposal`, validation_role `record-only`, single-source-evidence reason code. No t034 extensions involved. Skipped here — this is the boring case.

**(b) Applied graph-diagnostic payload (the t034-relevant case).** Reconstructed from the one applied sentence:

```yaml
core:
  payload_id: ev-2026-faller-applied-self-compat        # A: authoring
  artifact_type: graph-diagnostic                        # 1: clear from summary's method description
  extensions: [graph-diagnostic]                         # 2: dispatched from artifact_type
  created_at: 2026-05-06T15:45:00Z                      # A
  source_commit: <commit>                                # A
  input_artifact_refs: []                                # ✗: which graph(s) were diagnosed in the paper? not in summary
  claim_source_ref: paper:Faller2024                     # 2: from frontmatter
  method_ref: paper:Faller2024                           # 2: same
  agent_ref: agent:human:khughitt                        # A
  pipeline_provenance_ref: ~                             # A: no pipeline run
  proposition_refs: []                                   # 2: graph-diagnostic never targets propositions
  comparison_target: artifact-target                     # 2: per design doc table
  support_direction: quality-record                      # 2: graph-diagnostic semantic
  validation_role: quality-record-only                   # 2: per extension rule
  validation_status: pending                             # A: default for new extraction
  uncertainty_summary: "self-compatibility correlates with SHD on simulated DAGs; threshold and score range unknown from summary"   # 0: prose-only summary content
  reason_codes: [single-source-evidence, simulated-data-only]   # 1: simulated-data-only inferable from "in some settings" + Limitations note about simulation reliance
  abstention_reason: ~                                   # A

extension/graph-diagnostic:
  audited_graph_payload_ref: ~                           # ✗: no specific graph cited in summary
  diagnostic_kind: self-compatibility                    # 2: explicit
  compatibility_notion: ~                                # ✗: paper defines BOTH graphical and interventional; summary doesn't say which was used in the experiment
  variable_subsets_tested: ~                             # ✗
  diagnostic_score: ~                                    # ✗: "correlates with SHD" given as relative claim, not absolute score
  pass_threshold: ~                                      # ✗
  result: inconclusive                                   # 1: closest fit; "aids model selection in some settings" is neither pass nor fail
```

**Per-field rubric for this payload (extraction fields only — 13 fields per `[t030]` rubric split):**

| Field | Score | Note |
|---|---|---|
| artifact_type | 1 | clear from summary's method description |
| extensions | 2 | dispatched |
| input_artifact_refs | ✗ | summary names no specific audited graph |
| claim_source_ref | 2 | frontmatter |
| method_ref | 2 | self-reference |
| proposition_refs | 2 | empty by extension type |
| comparison_target | 2 | per design table |
| support_direction | 2 | per extension semantic |
| validation_role | 2 | per extension rule |
| uncertainty_summary | 0 | prose-only content; forced canonicalization |
| reason_codes | 1 | inferable |
| abstention_reason | 2 | n/a |
| extension/graph-diagnostic.audited_graph_payload_ref | ✗ |
| extension/graph-diagnostic.diagnostic_kind | 2 |
| extension/graph-diagnostic.compatibility_notion | ✗ | paper-defined both; summary loses the disambiguation |
| extension/graph-diagnostic.variable_subsets_tested | ✗ |
| extension/graph-diagnostic.diagnostic_score | ✗ |
| extension/graph-diagnostic.pass_threshold | ✗ |
| extension/graph-diagnostic.result | 1 |

**Counts (extraction fields):** 2: 7 (37%); 1: 3 (16%); 0: 1 (5%); ✗: 7 (37%); n/a: 1 (5%).

**Friction notes for Faller2024:**

- **Cannot author `audited_graph_payload_ref` from the summary.** The extension *requires* it (it's not marked `[opt]`). Either the field becomes optional, or this payload type cannot be authored from a paper-summary that lacks the experimental detail — which collapses the entire applied-graph-diagnostic use case for paper-summaries-as-extraction-source.
- **`compatibility_notion` enum forces a binary the paper presents as a parallel pair.** Faller defines two compatibility notions and uses both. The summary loses this; the schema would force the author to pick one.
- **`result: inconclusive`** is the closest fit, but the design's `pass | fail | inconclusive` enum may need a fourth value (`partial` or `correlative-only`) for "demonstrably useful as a signal but not a hard verdict."

---

## Extraction 2 — Zuber2025 → mr-graph-model (stage a) + mr-analysis sketch (stage b)

The summary tells us: a Bayesian causal graphical model (MrDAG) over multiple exposures and outcomes; instruments are genetic; direction (exposures→outcomes) is assumed; reverse causation excluded; mental-health application involved education, smoking, schizophrenia liability, cognition. No instrument count, no exposure count, no outcome count, no posterior summary specifics, no pleiotropy model details.

**Stage (a) — mr-graph-model payload:**

```yaml
core:
  payload_id: ev-2026-zuber-mrdag-mental-health         # A
  artifact_type: mr-graph-model                          # 2
  extensions: [mr-graph-model, causal-graph, statistical-uncertainty]   # 2
  created_at: 2026-05-06T16:00:00Z                       # A
  source_commit: <commit>                                # A
  input_artifact_refs: []                                # ✗: which GWAS sumstats? not in summary
  claim_source_ref: paper:Zuber2025                      # 2
  method_ref: paper:Zuber2025                            # 2
  agent_ref: agent:human:khughitt                        # A
  pipeline_provenance_ref: ~                             # A
  proposition_refs: []                                   # 2: graph-posterior doesn't update propositions
  comparison_target: hypothesis-set                      # 1: paper compares to other MR/CGM methods
  support_direction: methodological-input                # 2: per Example T34-6
  validation_role: prioritize-attention                  # 2: per extension rule
  validation_status: pending                             # A
  uncertainty_summary: "MrDAG posterior over lifestyle/behavior exposures and mental-health outcomes; pleiotropy model unspecified in summary"   # 0: prose
  reason_codes: [single-source-evidence, instrument-assumption-risk, reverse-causation-assumed]   # 2

extension/mr-graph-model:
  exposure_set: [var:education, var:smoking, ...]        # 1: partial; "education and smoking" + "lifestyle/behavioral exposures" implies more, not enumerated
  outcome_set: [var:schizophrenia-liability, var:cognition, ...]   # 1: partial
  instrument_set: []                                     # ✗
  instrument_validity_assumptions: [relevance, exclusion]   # ✗: summary doesn't list assumptions; defaulting to standard MR pair
  pleiotropy_model: not-modelled                         # ✗: summary says nothing about pleiotropy treatment; "not-modelled" is a defensible fallback that triggers blocking pleiotropy-untested
  direction_constraint: exposures-to-outcomes-only        # 2: explicit
  graph_object_type: graph-posterior                     # 1: "Bayesian causal graphical model" + "graph uncertainty" implies posterior
  summary_statistic_provenance: ~                        # ✗

extension/causal-graph:
  graph_object_type: graph-posterior                     # 1
  causal_model_ref: ~                                    # ✗
  nodes: [...]                                           # ✗
  edges: []                                              # 1: posterior, edges abridged
  edges_total: ~                                         # ✗
  identified_edge_count: 0                               # 2: stage (a) has no identified edges
  hidden_variable_set: ~                                 # ✗
  graph_artifact_path: ~                                 # ✗

extension/statistical-uncertainty:
  posterior_form: full-posterior                         # 1
  ci_method: ~                                           # ✗
  approximation_diagnostics: ~                           # ✗
```

**Per-field rubric (extraction fields, abridged):**

| Field | Score |
|---|---|
| artifact_type | 2 |
| extensions | 2 |
| input_artifact_refs | ✗ |
| claim_source_ref | 2 |
| method_ref | 2 |
| proposition_refs | 2 |
| comparison_target | 1 |
| support_direction | 2 |
| validation_role | 2 |
| uncertainty_summary | 0 |
| reason_codes | 2 |
| abstention_reason | 2 |
| mr-graph-model.exposure_set | 1 (partial) |
| mr-graph-model.outcome_set | 1 (partial) |
| mr-graph-model.instrument_set | ✗ |
| mr-graph-model.instrument_validity_assumptions | ✗ |
| mr-graph-model.pleiotropy_model | ✗ |
| mr-graph-model.direction_constraint | 2 |
| mr-graph-model.graph_object_type | 1 |
| mr-graph-model.summary_statistic_provenance | ✗ |
| causal-graph.graph_object_type | 1 |
| causal-graph.causal_model_ref | ✗ |
| causal-graph.nodes | ✗ |
| causal-graph.edges_total | ✗ |
| causal-graph.identified_edge_count | 2 |
| statistical-uncertainty.posterior_form | 1 |
| statistical-uncertainty.ci_method | ✗ |

**Counts:** 2: 9 (33%); 1: 6 (22%); 0: 1 (4%); ✗: 11 (41%).

**Stage (b) — mr-analysis sketch (would be authored if Science were extracting a per-edge effect estimate from the paper's mental-health table; the summary names "education and smoking" as important intervention points, which implies stage-(b) per-edge claims).**

The summary doesn't give effect sizes, so a stage-(b) payload would carry exclusively `[UNVERIFIED]` markers in the effect_estimate field. Skipping the full draft. Friction signal: stage-(b) extractions from current paper-summaries are essentially un-authorable.

**Friction notes for Zuber2025:**

- **Massive ✗-rate (41%) on extraction fields.** The paper-summary as it stands is far too short to populate `mr-graph-model`'s required fields. Either (a) the schema's "required" status on `instrument_set`, `summary_statistic_provenance`, `instrument_validity_assumptions` is too strong for paper-extracted payloads, OR (b) the paper-summary template (`[t029]` workflow) needs to capture these specifics, OR (c) MrDAG-style extractions are expected to come from a pipeline run, not a paper-summary.
- **`pleiotropy_model: not-modelled` as fallback is dangerous.** Triggering the blocking `pleiotropy-untested` code becomes the default for paper-extracted MR payloads where the summary is silent — this means *every* paper-extracted MR payload will block strengthening at stage (b) until someone re-reads the PDF. May be the correct behavior (caution by default) but it converts authoring sparseness into hard-validation friction. Consider: a softer `pleiotropy_model: unspecified` value that triggers `pleiotropy-untested` *non*-blocking.
- **`exposure_set` / `outcome_set` cardinality mismatch.** The paper studied multiple exposures and outcomes jointly; the summary names two and gestures at others. The schema demands enumeration. A `[partial]` or `[summary-only]` annotation pattern might be needed for paper-extracted multi-element fields. Otherwise authors will list what's named and silently elide the rest, losing fidelity.
- **`reverse-causation-assumed` as default for direction-constrained MR.** Zuber's design is genetics-instrumented (germline IVs *do* biologically constrain direction). Declaring `reverse-causation-assumed` here is over-flagging — the assumption is well-grounded, not unjustified. v1.1 open-question (5) flagged this; pilot confirms it's a real authoring problem.

---

## Extraction 3 — Dugourd2021 → mechanistic-hypothesis-bundle

The summary names: COSMOS workflow; integrates transcriptomics, phosphoproteomics, metabolomics with a signed directed prior knowledge network; applied to clear cell renal cell carcinoma matched tumor/healthy tissue; recovered hypoxia, inflammatory, oncogenic patterns; output is "hypothesis-generating, not a definitive causal proof."

```yaml
core:
  payload_id: ev-2026-dugourd-cosmos-ccrcc              # A
  artifact_type: mechanistic-hypothesis-bundle           # 2
  extensions: [mechanistic-hypothesis-bundle, causal-graph]   # 2
  created_at: 2026-05-06T16:30:00Z                       # A
  source_commit: <commit>                                # A
  input_artifact_refs:                                   # 1: dataset implied by "matched tumor and healthy tissue"
    - dataset:dugourd-2021-ccrcc-multiomics
  claim_source_ref: paper:Dugourd2021                    # 2
  method_ref: paper:Dugourd2021                          # 2
  agent_ref: agent:human:khughitt                        # A
  pipeline_provenance_ref: ~                             # A
  proposition_refs: [prop:ccrcc-mechanism-hypoxia-inflammatory-oncogenic]   # 1: paper makes a mechanism claim; representing as one proposition is one of several plausible cardinalities
  comparison_target: hypothesis-set                      # 1
  support_direction: methodological-input                # 2
  validation_role: prioritize-attention                  # 2
  validation_status: pending                             # A
  uncertainty_summary: "mechanistic hypothesis: hypoxia + inflammatory + oncogenic patterns recovered; subnetwork size unspecified in summary"   # 0
  reason_codes: [mechanism-hypothesis-only, prior-network-dependent, single-source-evidence]   # 2

extension/mechanistic-hypothesis-bundle:
  prior_knowledge_network_ref: ~                         # ✗: paper says "signed directed prior knowledge network integrating signaling, transcriptional regulation, and metabolism"; no specific network ref (OmniPath? Reactome? custom?) named in summary
  prior_network_version: ~                               # ✗
  omics_layer_set: [transcriptomics, phosphoproteomics, metabolomics]   # 2: explicit
  activity_estimation_method: footprint-based            # 1: "footprint methods" in summary
  causal_reasoning_algorithm: COSMOS                     # 2
  coherent_subnetwork_size: ~                            # ✗
  mechanism_role: hypothesis-only                        # 2: explicit ("hypothesis-generating, not a definitive causal proof")

extension/causal-graph:
  graph_object_type: candidate-graph                     # 2: per design rule for mechanistic-hypothesis-bundle
  causal_model_ref: ~                                    # ✗
  nodes: [...]                                           # ✗: not enumerated
  edges: []                                              # ✗
  edges_total: ~                                         # ✗
  identified_edge_count: 0                               # 2
```

**Per-field rubric:**

| Field | Score |
|---|---|
| artifact_type | 2 |
| extensions | 2 |
| input_artifact_refs | 1 |
| claim_source_ref | 2 |
| method_ref | 2 |
| proposition_refs | 1 |
| comparison_target | 1 |
| support_direction | 2 |
| validation_role | 2 |
| uncertainty_summary | 0 |
| reason_codes | 2 |
| abstention_reason | 2 |
| mhb.prior_knowledge_network_ref | ✗ |
| mhb.prior_network_version | ✗ |
| mhb.omics_layer_set | 2 |
| mhb.activity_estimation_method | 1 |
| mhb.causal_reasoning_algorithm | 2 |
| mhb.coherent_subnetwork_size | ✗ |
| mhb.mechanism_role | 2 |
| causal-graph.graph_object_type | 2 |
| causal-graph.causal_model_ref | ✗ |
| causal-graph.nodes | ✗ |
| causal-graph.edges_total | ✗ |
| causal-graph.identified_edge_count | 2 |

**Counts:** 2: 13 (54%); 1: 4 (17%); 0: 1 (4%); ✗: 6 (25%).

**Friction notes for Dugourd2021:**

- **`prior_knowledge_network_ref` ambiguity is corrosive.** The paper builds a custom integrated prior network, not (just) OmniPath or Reactome. The schema's `prior_knowledge_network_ref` expects a single ref; the paper's reality is "an integration of multiple curated sources." Either the field becomes a list, or a synthesis-of-priors sub-bundle is allowed.
- **`coherent_subnetwork_size` unfindable from summary.** A blocker if required; fine if optional.
- **`proposition_refs` cardinality.** "Hypoxia + inflammatory + oncogenic patterns" is plausibly one mechanism cluster (one proposition) OR three separate mechanisms (three propositions). v2.2's authoring rule says "one entry per finding-cluster (don't synthesize a catch-all)" but doesn't help with the inverse — *under*-fragmenting *and* over-fragmenting are both authoring errors and the rule doesn't disambiguate.
- **Best ✗-rate of the three (25%).** Mechanistic-hypothesis-bundle's required fields land closer to what paper-summaries actually contain.

---

## Cross-cutting findings

### F-pilot-1 — Paper-summary content does not span t034 extension required fields, especially for MR

✗-rate by paper: Faller2024 37%, Zuber2025 41%, Dugourd2021 25%. The MR case is worst because instrument-set / summary-statistic-provenance / pleiotropy-model are mechanically detailed and rarely surface in the project's existing summary template. Two paths:

- **Loosen required-field set on t034 extensions for paper-extracted payloads.** Mark `instrument_set`, `summary_statistic_provenance`, `audited_graph_payload_ref`, `prior_knowledge_network_ref`, `coherent_subnetwork_size` as `[opt]`. Trade-off: payloads of these shapes lose machine-checkable completeness.
- **Tighten the paper-summary template (`[t029]` workflow).** Add an "Artifact Specifics" section that captures method-specific reproducible-detail. Trade-off: more author burden, more re-PDF-reading per paper.

Recommendation: do both, asymmetrically. Loosen the schema to accept paper-extracted payloads with sparse required fields *under the explicit reason code `extracted-from-summary-only`* (proposed new code). Keep all fields required for *pipeline-extracted* payloads. The schema then encodes the difference.

### F-pilot-2 — `uncertainty_summary` scored 0 in all three

Same finding as `[t030]`: paper-summary content is prose, and forcing it into a canonical `uncertainty_summary` either drops information or invents structure. v2.2 made the field optional, which helps. The pilot suggests an additional rule: when the summary is purely qualitative, leave `uncertainty_summary` empty rather than synthesizing prose. Authors who synthesize tend to over-claim precision. Add to `[t022]` authoring guidance.

### F-pilot-3 — Methods-paper / applied-payload split is real and undocumented

A paper that introduces a method (Faller2024, Petersen2014, Ban2023, Wan2025, Zhang2021gCastle) produces *two distinct payload candidates* in this project: (a) the methods-paper claim about the method, (b) zero-or-more applied payloads re-encoding the paper's worked applications. The current design doc shows only (b) in worked examples and doesn't note (a)'s existence at all.

Recommendation: add a brief subsection to the design doc (under "Pipeline → extension mapping" or as a new section "Method-paper vs applied-payload routing") clarifying that for any method-introducing paper:
- The method itself produces a `methods-paper` paper-extracted-claim in core, with `single-source-evidence` and possibly `simulated-data-only` reason codes. No t034 extension involved.
- The paper's worked applications produce t034-extension payloads, *one per application*, with `claim_source_ref: paper:X` for provenance.

This is a v1.2 documentation patch, not a structural change.

### F-pilot-4 — `reverse-causation-assumed` is over-flagging (open question 5 confirmed)

For genetics-instrumented MR (Zuber2025), `direction_constraint: exposures-to-outcomes-only` is biologically grounded and not a methodological caveat. Declaring `reverse-causation-assumed` always-when-direction-constrained collapses the distinction between justified and unjustified direction constraints.

Recommendation: refine the rule. `reverse-causation-assumed` is declared when `direction_constraint` is set AND the assumption is not biologically inherent (e.g., for non-genetic IVs, or when direction is asserted from domain knowledge). For germline genetic instruments, declaring is an authoring choice, not a default. Add a sub-field to `mr-graph-model.instrument_validity_assumptions` that distinguishes inherent-from-IV-class versus author-asserted constraints.

This is the pilot pressure-tested resolution to v1.1 open question 5.

### F-pilot-5 — `pleiotropy_model: not-modelled` as default is over-blocking

A paper-summary that's silent on pleiotropy treatment shouldn't force the extracted payload to declare blocking `pleiotropy-untested`. Pilot suggests adding a soft `pleiotropy_model: unspecified` value that triggers `pleiotropy-untested` *non*-blocking. The blocking version remains for explicit `pleiotropy_model: none-assumed` (the author actively chose to not model it).

### F-pilot-6 — Multi-element fields need partiality semantics

`exposure_set`, `outcome_set`, `nodes`, `omics_layer_set`, `mediator_set`, `instrument_set`: when the paper-summary names some elements and gestures at others, the schema currently forces full enumeration. Authors will silently elide. Two candidate fixes:

- **List-with-partial-marker:** allow `exposure_set: [var:education, var:smoking, "[partial — see PDF]"]`. Ugly; bypasses normal validation.
- **Boolean partial flag:** add `<field>_complete: bool` next to each list field, defaulting `true`; authors set `false` when listing is partial. Cleaner; lets the validator and downstream consumers distinguish "two exposures" from "two of N exposures."

Recommend the boolean-flag variant; bake into `[t022]` core authoring rules rather than t034 specifically.

### F-pilot-7 — `proposition_refs` cardinality rule is one-sided

v2.2 says "don't synthesize a catch-all." The Dugourd2021 case showed the inverse problem: when a paper presents three intertwined mechanism patterns, the rule doesn't tell the author whether to author one mechanism-cluster proposition or three separate ones. Add a complementary authoring rule: "when findings are *intertwined* (one mechanism story with multiple recovered patterns), one proposition; when findings are *independent* (multiple distinct claims), separate propositions."

### F-pilot-8 — Faller's `compatibility_notion` enum forces a pick where the paper presents a pair

The paper defines *both* graphical and interventional notions and presents them in parallel. The schema forces the author to pick one. Either the field becomes a list (`[graphical, interventional]`), or it becomes optional with a separate "pair declared" reason code. Recommend list shape — the field is genuinely multi-valued in some paper applications.

### F-pilot-9 — `result: pass | fail | inconclusive` in graph-diagnostic may need a fourth value

Faller's claim "incompatibility score correlates with SHD and aids model selection in some settings" doesn't fit any of the three. `inconclusive` is the closest but loses the "demonstrably useful as a signal but not a hard verdict" semantic. Candidate fourth value: `correlative` (the diagnostic produces a useful signal but not a binary verdict). Lightweight addition.

### F-pilot-10 — `extracted-from-summary-only` reason code

Net of F-pilot-1 and F-pilot-5: there's a real distinction between "extracted from a project paper-summary" (sparse, summary-only) and "extracted from PDF re-read or pipeline run" (rich). Adding `extracted-from-summary-only` as a non-blocking reason code lets the validator be lenient about ✗ rates on summary-extracted payloads while remaining strict on pipeline-extracted ones. Aligns with the natural-systems "asserted vs. verified" thread.

---

## Rubric-comparable summary table

| Paper | Required-field ✗ rate (extraction fields only) | Schema friction class |
|---|---|---|
| Faller2024 (graph-diagnostic) | 37% | high (audited-graph-ref unobtainable from method paper) |
| Zuber2025 (mr-graph-model) | 41% | very high (instrument/sumstat/pleiotropy detail not in summary) |
| Dugourd2021 (mechanistic-hypothesis-bundle) | 25% | medium (subnetwork-size and prior-network-ref are the gaps) |

For comparison, `[t030]` full audit of `[t022]` core had ✗ rates that drove `target_artifact_ref` (0.167) and `uncertainty_summary` (0.583 ambiguous) out of required-status. The pilot's ✗ rates argue for analogous loosenings on the t034 extensions, *gated by the new `extracted-from-summary-only` reason code* so pipeline-extracted payloads remain strict.

---

## Recommended v1.2 patches

Tractable mechanical changes from this pilot, sized like the v1.1 patch set:

- **P-pilot-1.** Add `extracted-from-summary-only` reason code (non-blocking). Loosen `instrument_set`, `summary_statistic_provenance`, `audited_graph_payload_ref`, `coherent_subnetwork_size`, `prior_knowledge_network_ref` to `[opt]` *when this code is present*. (Implementation: extension validators check the producing payload's `core.reason_codes`.)
- **P-pilot-2.** Add `pleiotropy_model: unspecified` enum value (triggers `pleiotropy-untested` non-blocking, vs `none-assumed` which triggers blocking).
- **P-pilot-3.** Add `compatibility_notion: [enum]` list shape (not single-valued).
- **P-pilot-4.** Add `result: correlative` to graph-diagnostic enum.
- **P-pilot-5.** Add complementary `proposition_refs` authoring rule for the intertwined-vs-independent disambiguation; mirror to v2.2 contract.
- **P-pilot-6.** Add boolean `_complete` flag pattern to `[t022]` core authoring rules for multi-element list fields. Mirror to t034's `exposure_set`, `outcome_set`, `omics_layer_set`, etc.
- **P-pilot-7.** Refine `reverse-causation-assumed` rule: declare only when direction constraint is not biologically inherent (subfield on `instrument_validity_assumptions`).
- **P-pilot-8.** Add to v1 design doc: brief "Method-paper vs applied-payload routing" section per F-pilot-3.
- **P-pilot-9.** Add to `[t022]` authoring guidance: leave `uncertainty_summary` empty for purely-qualitative summaries; do not synthesize prose.

P-pilot-1 is the highest-leverage change; it turns the ✗-rate finding from a schema problem into an authoring-source-tracked annotation. P-pilot-6 also propagates upward into `[t022]` and benefits `[t035]`/`[t037]`/`[t038]`/`[t040]` similarly.

---

## What the pilot did NOT pressure-test

- **The 10-extension carve-up.** No friction surfaced from the boundary choices themselves. (Could be because three papers happen to be one-extension cases.)
- **Multi-extension dispatch.** Zuber's stage-(b) sketch was skipped. No extraction here actually exercised `mediation-analysis` or `mr-analysis` co-loading.
- **Reason-code propagation across payloads.** All three were single-payload extractions; no upstream/downstream chain was authored.
- **Validation rules' enforceability.** The pilot is a *thought-extraction*, not a runner pass — F-pilot natural-systems-aligned commitment is still pending.

These remain on the t034 audit-prompts list for the next pass.

---

## Next steps

1. **Apply v1.2 patches** mechanically (the nine listed above). Roughly half are extension-spec edits, half are authoring-rule additions.
2. **Mirror three new codes to `[t025]`:** `extracted-from-summary-only`, plus the enum additions don't add codes per se.
3. **Pilot a multi-payload chain** — pick a paper that produces both a methods-paper claim AND an applied payload, author both, exercise reason-code propagation. Likely Zuber2025 with the stage-(b) effect estimate filled in (PDF-assisted, since the summary is silent).
4. **Pilot a real validator.** Per the natural-systems alignment commitment, write the actual validator function for one extension's rules and run it against these three payloads. Surfaces "is the rule even decidable from payload state" failures.

The structural decisions of v1.1 (10 extensions, validation-rule permission table, promotion-by-reference) all survived the pilot. The patches are calibration adjustments, not architectural changes.
