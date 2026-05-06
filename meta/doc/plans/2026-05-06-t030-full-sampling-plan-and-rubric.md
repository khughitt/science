# t030 — Full Authoring-Cost Audit: Sampling Plan and Rubric

> **Scope.** Full `[t030]` deliverables per `meta/tasks/active.md:345`. The narrow first pass (`meta/doc/plans/2026-05-06-t030-narrow-authoring-cost-audit.md`) drove four v2.1 patches; this plan operationalizes the wider sample, the rubric, the manual + LLM extraction passes, and the two feedback notes.

---

## Goals

The full audit decides whether v2.1's core schema and reason-code registry are right-sized. It produces:

- D1 — **sampling plan + rubric** (this document).
- D2 — **per-field extractability table** (manual pass).
- D3 — **field-pruning recommendation note** to t022 (core / typed-extension / drop / new).
- D4 — **two-blind-LLM agreement note** (per-field agreement; rubric ambiguity signal). Originally specified as manual-vs-blind-LLM and reframed mid-execution; see methodology section. The full-context-manual signal originally meant for `[t033]` is deferred to a future audit.

Enum-sizing decisions for `artifact_type`, `support_direction`, and `validation_status` are gated on D2/D3.

---

## Sampling plan

**Pool.** 57 paper-summary files under `meta/doc/background/papers/` (excluding 6 batch-synthesis files, which are project-internal artifacts, not paper summaries). Excluded from sampling:

- The six papers used as v2 worked examples (Gronau2021, Zhao2012, Petersen2014, Mohammadi2025, Ding2025, Banzi2026) — biased.
- The four papers used in the narrow-pass audit (Heyard2025, Faller2024, Jin2025, Freiesleben2023) — already scored; the narrow-audit findings serve as **qualitative interpretive context** for D2/D3 but are *not* aggregated into per-field metrics, since the narrow pass did not apply this rubric.

**Eligible pool: 47 papers.**

**The audit splits into two sample sets, per the reviewer's open question:**

### Main sample — payload-bearing papers (per-field rubric, n=12)

This is the sample on which D2's per-field extractability metrics are computed. Eligibility: the paper, on inspection, produces at least one t022-eligible payload (empirical claim, methodological claim with empirical demonstration, method application, causal-discovery output, agent operation, or evaluation artifact). Out-of-scope papers (surveys, conceptual theory, taxonomy/vocabulary contributions per v2.1's "What does NOT live in t022") are not eligible for this sample.

**Stratification.** 12 slots over 6 strata defined by *what payload-shape the paper produces*, not by paper-internal genre:

| Stratum | Slots | Rationale |
|---|---|---|
| Paper-extracted empirical claim | 3 | Schema-weak region (per narrow audit F6); over-sample |
| Paper-extracted methodological claim | 3 | Schema-weak region; over-sample |
| Method-application / synthesis-style payload | 2 | Where v2 is already strong; confirm |
| Causal-discovery / graph-construction payload | 2 | Active aspect (`[t034]`) |
| Agent-operation / tool-use payload | 1 | Active aspect (`[t037]`) |
| Robustness / reproducibility evaluation payload | 1 | Active aspect (`[t040]`) |

The 3/3/2/2/1/1 allocation gives strong per-stratum signal in the over-sampled paper-extracted-claim strata (n=6 combined) and adequate spot-check coverage in the others. The 1-slot strata produce per-stratum signal only in conjunction with cross-aspect patterns; per-field rates from a single paper are noted but not over-interpreted.

**Locked main sample (12 papers, post-spot-check).** Adjustable if a closer reading during the manual pass reveals a wrong-stratum classification:

| # | Paper | Stratum |
|---|---|---|
| 1 | Klugkist2023 | methodological claim (BES intro w/ informative-hypothesis examples) |
| 2 | VanLissa2024 | methodological claim (PBF tutorial w/ simulation validation) |
| 3 | Yu2026 | empirical claim (SciCUEval benchmark results) |
| 4 | Si2025 | methodological claim (Bayes-factor LLM bias) |
| 5 | Williams2018 | methodological claim (Bayesian MA w/ weakly informative priors) |
| 6 | Allen2017 | methodological claim (mixed multi-view data-integration agenda) |
| 7 | Zhang2017CancerGenomics | method-application (cancer multi-omics joint graphical) |
| 8 | Mulder2026 | method-application (BF testing in meta-analysis w/ BFpack) |
| 9 | Berenfeld2026 | causal-discovery |
| 10 | Liu2024HiddenWorld | causal-discovery (LLM-assisted) |
| 11 | Jiang2024 | agent-operation / KG-operation (DiffKG diffusion filtering) |
| 12 | Maier2022 | robustness/evaluation (RoBMA publication-bias detection) |

### Routing-test sample — out-of-scope papers (n=5)

A separate, smaller test set verifying that v2.1's "What does NOT live in t022" rule correctly classifies surveys, conceptual theory, and registry-import papers as out-of-scope. **These papers are not field-scored** — they are routed only.

**Locked routing-test set (5 papers, all spot-checked):**

| # | Paper | Out-of-scope reason |
|---|---|---|
| R1 | Linkov2017 | methodological commentary on Bayesian weight-of-evidence; explicitly self-described as "not an empirical validation study" |
| R2 | Aitken2024 | methodological review of Bayes-factor properties; survey, no empirical claim |
| R3 | Vahabi2022 | review of unsupervised multi-omics integration; offers a taxonomy across methods |
| R4 | Zhang2025ScientificMethod | perspective/review of LLMs across the scientific method; survey |
| R5 | Hackenberger2020 | practitioner perspective + survey of Bayesian meta-analysis software |

A routing-test paper passes if v2.1's rule classifies it as out-of-scope without forcing it into a payload. Failure modes: (a) the paper has a hidden empirical claim that should make it payload-bearing; (b) v2.1's wording leaves the routing rule ambiguous on this paper class. Both feed back into v2.2.

### Spot-check log

The following papers were considered for the routing-test set and rejected (they turned out to be payload-bearing methodological papers, not surveys):

- **Liu2020** — proposes fast variational inference with theoretical sufficient conditions and reduces computation while preserving solutions. Methodological-claim payload.
- **Maier2022** — was relocated to the main sample (slot 12) once its simulation studies + RMSE comparisons were confirmed.

This pattern (initial-classification-from-title-fails) confirms the audit's spot-check requirement and is itself a finding for v2.2: a paper's genre classification cannot reliably be inferred from its title.

A routing-test paper passes if v2.1's rule classifies it as out-of-scope without forcing it into a payload. Failure modes: (a) the paper has a hidden empirical claim that should make it payload-bearing; (b) v2.1's wording leaves the routing rule ambiguous on this paper class. Both feed back into v2.2.

---

## Rubric

For each (paper, core-schema-field) pair, the rubric assigns a per-field score:

| Score | Label | Meaning |
|---|---|---|
| 2 | **stated** | The field's value is explicitly stated in the summary; minimal interpretation needed |
| 1 | **inferred** | A defensible value can be inferred from the summary, but the summary doesn't directly say it |
| 0 | **ambiguous** | Multiple defensible values; cannot pick one without arbitrary choice |
| ✗ | **not-applicable** | The paper class does not produce a payload of this type, so the field has no meaningful value |
| — | **out-of-scope** | The paper itself is out of t022 scope (per v2.1 "What does NOT live in t022") — no payload at all |

Each cell also records:

- **Effort (mins):** rough authoring time for that field, including time spent reading/searching the summary.
- **Notes:** if a field had to be invented, left blank, or required a workaround, a one-line note.

**Field partition.** v2.1's 18 core fields split into two classes for the rubric:

**Authoring fields (5)** — supplied at authoring time from environment / project state, not extractable from a paper summary. **Excluded from rubric scoring.** They are noted here so it is clear why they don't appear in D2:

- `payload_id` — generated mechanically per project naming convention.
- `created_at` — system clock.
- `source_commit` — project git state, not a paper field.
- `agent_ref` — the agent doing the authoring.
- `pipeline_provenance_ref` — set if the payload comes from a pipeline run; null for paper-extracted claims.

(Caveat: for *agent-operation* payloads, `agent_ref` and `pipeline_provenance_ref` *are* paper-extractable when the paper describes its own agent system — e.g., Ding2025. For agent-operation papers, score these two fields per the rubric below; otherwise treat as authoring fields.)

**Extraction fields (13)** — the rubric scores these:

- Identity: `artifact_type`, `extensions`
- Provenance: `input_artifact_refs`, `claim_source_ref`, `method_ref`
- Attachment: `proposition_refs`, `target_artifact_ref`, `comparison_target`
- Epistemic semantics: `support_direction`, `validation_role`, `validation_status`, `uncertainty_summary`
- Quality flags: `reason_codes`, `abstention_reason`

(That is 14 lines but `abstention_reason` is grouped with `reason_codes` in scoring — if the payload is a "we can't say" abstention, score it; otherwise mark not-applicable.)

**Rubric for arrays (e.g., `input_artifact_refs`, `proposition_refs`):**

- Score 2 if the summary names the inputs/propositions explicitly (even if the *count* is approximate).
- Score 1 if the summary describes the inputs/propositions abstractly (e.g., "applied to several psychology datasets") but does not enumerate them.
- Score 0 if the summary leaves it genuinely unclear.

**Rubric for enums (`comparison_target`, `support_direction`, `validation_role`, `validation_status`):**

- Score 2 if exactly one v2.1 enum value cleanly fits and the summary supports it directly.
- Score 1 if one value fits but requires interpretive judgment.
- Score 0 if no value cleanly fits, or two values both seem defensible.

When score = 0, the cell **must** record candidate enum values and which the extractor picked.

---

## Per-field aggregations to compute (D2)

The main sample is structurally all-payload-bearing (n=12 by construction), so payload-scope rate is reported separately for the routing test, not on the main sample. Per-field metrics are computed on the main sample only.

For each extraction field, define:

- **applicable papers for this field**: papers in the main sample where the field has a meaningful value for the payload they produce. (E.g., `target_artifact_ref` is applicable for evaluation/audit papers and not for empirical-claim papers; `proposition_refs` is applicable for empirical-claim and synthesis-style papers and not for agent-operation papers.)

For each field across the main sample:

- **stated rate** = (# papers scoring 2) / (# applicable papers for this field)
- **inferred rate** = (# papers scoring 1) / (# applicable papers for this field)
- **ambiguous rate** = (# papers scoring 0) / (# applicable papers for this field)
- **applicability rate** = (# applicable papers for this field) / 12  — interpreted within the payload-bearing main sample. A low rate signals the field is artifact-family-specific (extension candidate), **not** that the field doesn't belong because surveys don't use it.
- **mean effort** in minutes (over applicable papers only)
- **invented-value count** = # of papers where a workaround / new enum value / new field was needed

For the routing-test set (n≈4), report only:

- **routing accuracy**: fraction correctly classified as out-of-scope.
- Notes on any paper that proved ambiguous to route — these surface holes in v2.1's "What does NOT live in t022" wording.

**Field-pruning rule (driving D3).** Computed on the main sample, where every paper is payload-bearing:

- If `stated + inferred ≥ 0.8` AND `applicability rate ≥ 0.8`: **keep in core.**
- If `applicability rate < 0.5`: **move to a typed extension** (the field is artifact-family-specific within payload-bearing papers).
- If `ambiguous rate ≥ 0.4`: **revise the field** (definition unclear or enum needs widening).
- If `invented-value count > 1`: **flag the missing enum/value** for v2.2 enum-sizing review.
- If a candidate new field is invented in ≥ 2 papers: **propose adding to v2.2 core** with audit evidence.

---

## Two extraction passes (D4)

### Methodology: LLM-vs-LLM-blind comparison

**Update (2026-05-06).** The original plan was a full-context manual pass (run by the in-conversation assistant) vs. a blind LLM pass (run by a fresh subagent). After the first blind subagent returned, the manual extractor had already seen its output, which would have biased a subsequent manual pass. The methodology was revised to a cleaner alternative: **two independent blind LLM passes** instead of manual-vs-LLM.

Both passes use:
- Identical packets (verbatim same prompt).
- Fresh general-purpose subagents (no shared context, no shared conversation history).
- The same 12 main-sample papers.
- The same 13 extraction fields and rubric.

This eliminates two confounds the reviewer flagged:
1. Full-context-vs-blind asymmetry (M5): both passes are blind, so any disagreement reflects rubric-induced extraction variance, not context-access advantage.
2. Manual-after-seeing-LLM contamination: irrelevant when the manual pass is replaced by a second blind LLM pass.

**Tradeoff acknowledged:** D4 no longer informs `[t033]` directly about *full-context* extraction reliability. To recover that signal, a future audit can run a follow-up full-context manual pass (executed before the audit's LLM passes are visible) and score it independently. That is out of scope here.

### Blind-LLM packet contents (identical for both passes)

The blind LLM extractor sees only:

- The v2.1 core-schema description (the **Proposed core schema**, **What does NOT live in t022**, and **Pitfall** sections, pasted into the prompt).
- The rubric (rubric definitions + per-field score table; not the metrics, not the field-pruning rules).
- The 12 paper-summary file paths, with an instruction to read those files and only those files.

The extractor does not see:
- Other paper summaries (no cross-paper priors).
- The narrow-audit findings (would bias toward known gaps).
- This sampling plan beyond what's pasted.
- The rest of the v2.1 contract (worked examples, migration notes, open questions).
- The first pass's output (when running pass 2).

### Blind-LLM packet contents

The blind LLM extractor sees only:

- The v2.1 core-schema description (the **Proposed core schema**, **What does NOT live in t022**, and **Pitfall** sections of `meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`).
- The rubric above (rubric definitions + per-field score table; not the metrics, not the field-pruning rules, not the locked sample list beyond the paper assigned).
- The paper summary file at `meta/doc/background/papers/<key>.md`.

The extractor does not see:
- Other paper summaries (no cross-paper priors).
- The narrow-audit findings (would bias toward known gaps).
- This sampling plan's metric definitions or pruning rules.
- The rest of the v2.1 contract (worked examples, migration notes, open questions).

The extractor outputs a per-field row per paper with score + effort + notes + (if invented) the value chosen.

### Agreement metrics (LLM-vs-LLM-blind)

- **Per-field exact agreement rate** = (# main-sample papers where pass 1 and pass 2 scored identically on this field) / (# applicable papers for that field)
- **Per-field within-1 agreement rate** = (# papers where scores differ by ≤ 1) / (# applicable for that field)
- **Disagreement direction:** when scores differ, which pass scored higher? (No prior expectation — both passes are blind.)
- **Effort delta:** mean per-field effort difference. (Variance reflects rubric-induced extraction variance, not context access.)

D4 lists fields where exact agreement is `< 0.6` as candidates for **rubric ambiguity** (the rubric isn't precise enough that two independent extractors converge), distinct from **paper ambiguity** (the source genuinely doesn't pin the value). Rubric ambiguities feed into v2.2 documentation revisions. Paper ambiguities feed into the field-pruning rule. Because both passes are blind, disagreement is now a stronger signal of rubric ambiguity than under the original manual-vs-blind design.

---

## Effort budget (revised)

- **D1 (sampling plan + rubric)** — this document, ~90 min.
- **Two blind-LLM passes via subagents** — wall-clock ~3 min each, run in parallel; subagent compute cost paid by background tasks.
- **D2 tabulation** — ~45 min from the union/intersection of the two passes.
- **D3 + D4 notes** — ~60 min combined.

Total: roughly half a day's effort across the orchestrator's turns. Reasonable to split across sessions; D1 is shippable on its own.

---

## Decision points / forks

1. **Should the blind-LLM passes be run?** Yes — both passes have been run as of 2026-05-06. Pass 1 output preserved at `meta/doc/plans/2026-05-06-t030-llm-pass-1-output.md`; pass 2 launched after pass 1 returned and was visible to the orchestrator (which is why the methodology shifted to two-blind-LLM rather than manual-vs-blind).

2. **Should `[t033]` be deferred until after D4?** Yes, but the basis is weaker than originally planned: D4 now tells `[t033]` about rubric-induced extraction variance between two blind LLM extractors, not about full-context-manual extraction. `[t033]` should call out the deferred full-context measurement as future work.

3. **Should aspect extensions wait for D3?** Per the v2.1 audit's softened gate: no, they can begin against v2.1 with the understanding that enums are not-yet-locked. D3 may move 1–2 fields between core and extensions; aspect extensions should expect that.

4. **What if D3 surfaces a core field count > 22?** Re-prune. v2 picked 17 (now 18 with `claim_source_ref`) precisely so the core stays small. If the audit pushes beyond ~22, that signals over-fitting to paper-extracted claims and warrants pruning back.

5. **What if a main-sample paper turns out, on inspection, not to be payload-bearing?** Replace it from the eligible pool, document the swap in D2's notes, and (separately) inspect whether the misclassification reveals a routing-rule ambiguity in v2.1.

---

## Out of this audit's scope

- Authoring cost of *extension* fields. The aspect-extension tasks (`[t034]`/`[t035]`/`[t037]`/`[t038]`/`[t040]`) own their own per-field rubric for their respective fields.
- Cost of authoring `pipeline_provenance_ref` records — those live in a separate registry layer and are not paper-extracted.
- Authoring cost on *propositions* that the payloads reference. Proposition design is in scope of `[t023]`, not `[t030]`.
- Migration cost from legacy support/dispute edges. That's the v2.1 migration spec's own piloting step.

---

## Next steps

1. Lock the 12-paper sample list (after a quick PDF/summary spot-check on the candidates above).
2. Manual pass: produce per-paper per-field rows, and an aggregate table → D2.
3. Spawn LLM subagent for the same 12 papers → D4 agreement metrics.
4. Write D3 (field-pruning recommendations) and D4 (manual-vs-LLM note).
5. Decide on enum-sizing patches to v2.1 → v2.2.
