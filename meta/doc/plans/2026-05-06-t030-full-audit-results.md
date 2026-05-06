# t030 — Full Authoring-Cost Audit: Results (D2, D3, D4)

> **Status.** Combined results document for the three remaining `[t030]` deliverables, computed from two independent blind LLM passes (`meta/doc/plans/2026-05-06-t030-llm-pass-1-output.md`, `meta/doc/plans/2026-05-06-t030-llm-pass-2-output.md`) over the locked 12-paper main sample. Field-pruning rules and aggregation methodology are specified in the sampling plan.

## Summary

The two blind passes converged strongly: both flagged the same schema gaps and the same out-of-scope candidates. Of v2.1's 13 extraction fields:

- **5 fields are reliably extractable** (`claim_source_ref`, `validation_status`, `method_ref`, `support_direction`, `input_artifact_refs`) — keep in core.
- **2 fields are inference-only but stable** (`extensions`, `validation_role`) — keep in core; mark in the schema as authoring-defaulted.
- **3 fields need rubric/enum revision** (`artifact_type`, `comparison_target`, `uncertainty_summary`) — keep in core but revise.
- **1 field needs a rubric clarification** (`reason_codes`) — passes split on what `✗` means; not a schema bug but a docs bug.
- **1 field is a typed-extension candidate** (`target_artifact_ref`) — applicability ≤ 0.17 in payload-bearing papers.
- **1 field needs cardinality treatment** (`proposition_refs`) — papers carry 2–4 distinct claims; the rubric gave no guidance on whether to author one synthetic proposition or multiple, and the passes split.

Four of the 12 main-sample papers (Allen2017, Yu2026, Mulder2026, Jiang2024) were independently flagged by both blind passes as borderline-out-of-scope. This validates the narrow audit's "title alone is unreliable" finding and means roughly **~33% of the corpus needs a closer payload-vs-out-of-scope routing review** before extension drafting.

---

## D2 — Per-field extractability table

Aggregated over 24 cells per field (12 papers × 2 blind passes). Where one pass scored a cell `✗` and the other scored a number, the cell counts toward applicability disagreement (column "appl. disagreement"). All other cells contribute to the rate computation.

| Field | Applicability | Stated rate | Inferred rate | Ambiguous rate | Appl. disagree | Verdict |
|---|---|---|---|---|---|---|
| `claim_source_ref` | 1.000 | **1.000** | 0 | 0 | 0 | KEEP CORE — fully extractable |
| `validation_status` | 1.000 | **1.000** | 0 | 0 | 0 | KEEP CORE — mechanical default |
| `method_ref` | 1.000 | **0.833** | 0.125 | 0.042 | 0 | KEEP CORE — strong signal |
| `support_direction` | 1.000 | 0.625 | 0.208 | 0.167 | 0 | KEEP CORE — stated+inferred=0.833 |
| `input_artifact_refs` | 1.000 | 0.417 | 0.583 | 0 | 0 | KEEP CORE — stated+inferred=1.000 |
| `extensions` | 1.000 | 0 | **0.917** | 0.083 | 0 | KEEP CORE — never stated; always inferred |
| `validation_role` | 1.000 | 0 | **0.875** | 0.125 | 0 | KEEP CORE — never stated; mostly defaulted |
| `proposition_refs` | 1.000 | 0.167 | 0.625 | 0.208 | 0 | REVISE — cardinality unclear |
| `comparison_target` | 1.000 | 0.250 | 0.500 | 0.250 | 0 | REVISE — enum gap on method-vs-method |
| `artifact_type` | 1.000 | 0 | 0.792 | 0.208 | 0 | REVISE — enum gap on methods/framework/benchmark |
| `uncertainty_summary` | 1.000 | 0.167 | 0.250 | **0.583** | 0 | REVISE — definition unclear for prose summaries |
| `target_artifact_ref` | 0.167 | 0 | 0.750* | 0.250* | 0 | MOVE TO EXTENSION — applicability < 0.5 |
| `reason_codes` | 0.500 | 0 | 0.917* | 0.083* | **12** | RUBRIC FIX — passes split on ✗ vs empty-list |

(*) computed only over applicable cells.

**Interpretive notes:**
- `extensions` and `validation_role` have applicability=1.0 but stated=0; both are *inferred-only* fields. Acceptable for core because they're effectively authoring-defaulted (every payload declares some extensions list and some validation_role from a small enum).
- `target_artifact_ref` was applicable for only 4 of 24 cells (the Si2025 and Yu2026 cells across both passes). With 96% of payload-bearing cells scoring `✗`, this is a clear typed-extension candidate — it belongs to evaluation/audit/operation extensions, not core.
- `reason_codes` had a clean methodological split: pass 1 scored every cell as 0 or 1 (treating empty-list as a value to score); pass 2 scored every cell as `✗` (treating "no codes apply" as not-applicable). This is a rubric clarification, not a real ambiguity in the papers.

---

## D3 — Field-pruning recommendations to t022 (v2.1 → v2.2)

Applying the field-pruning rules from `meta/doc/plans/2026-05-06-t030-full-sampling-plan-and-rubric.md`:

### Action 1 — Move `target_artifact_ref` to typed extensions (P1)

Applicability is 0.167, well under the 0.5 threshold. It belongs to evaluation, audit, and operation extensions only (where every payload sets it), not in core. v2.2 should remove it from core and require any extension declaring an evaluation/audit/operation type to provide it.

### Action 2 — Extend `artifact_type` enum (P1)

Both blind passes scored 0/12 cells as "stated" and ~80% as inferred, with 21% ambiguous. Both passes independently invented overlapping new values:

- Pass 1 invented: `method-contribution`, `method-tutorial`, `commentary`, `benchmark-resource`.
- Pass 2 invented: `methods-paper`, `framework-paper`, `tutorial-paper`, `benchmark`, `dataset-paper`.

**Recommended additions to v2.2 enum:**

- `methods-paper` (or `method-contribution`) — papers that propose a method and demonstrate it; covers ~8 of 12 main-sample papers.
- `framework-paper` — papers that propose an analytic framework without a single canonical method (e.g., Allen2017, Liu2024HiddenWorld).
- `benchmark-or-dataset-paper` — papers whose primary contribution is a benchmark or dataset (Yu2026).

Existing types (`bayesian-meta-analysis`, `truth-discovery-result`, `causal-discovery-run`, `graph-posterior-synthesis`, `agent-tool-operation`, `reproducibility-checklist-audit`) remain valid for synthesis-derived and operation-record payloads. The new types apply to paper-extracted-claim payloads.

### Action 3 — Extend `comparison_target` enum (P1)

Stated rate 0.250, ambiguous rate 0.250, with both passes flagging the gap. The current enum (`null-vs-alternative` / `hypothesis-set` / `model-set` / `artifact-target` / `n-a`) doesn't distinguish *method-vs-method* comparisons (where two methods are evaluated against each other on a benchmark, not models against a hypothesis-set). Pass 1 explicitly proposed `method-set`.

**Recommended addition:** `method-set` — for papers comparing method A vs method B (e.g., Williams2018 comparing DL/REML/Bayesian estimators; Berenfeld2026 comparing classical vs causal aggregation; Maier2022's 12-model RoBMA ensemble). v2.1 currently shoehorns these into `model-set`.

### Action 4 — Extend `support_direction` enum (P2)

Stated rate 0.625, inferred 0.208, ambiguous 0.167 — already adequate for a core field. But a recurring pattern: papers proposing a new method often have findings that "support the method" in a way the existing `supports`/`methodological-input` distinction doesn't quite capture. Pass 1 proposed `proposes-method`/`methodological-input-with-evidence`; pass 2 proposed `descriptive-finding`/`framework-proposal`.

**Recommended addition:** `framework-proposal` — for papers contributing a new framework or method whose findings primarily support the framework's behavior under stated conditions, without comparing it against an alternative hypothesis. This is the dominant case in this corpus and would resolve most of the within-1 disagreements between `supports` (P1) and `supports`/`methodological-input` (P2).

This is P2 (not P1) because the existing enum already covers the common cases adequately — the addition mainly tightens the rubric.

### Action 5 — Define `proposition_refs` cardinality rule (P1)

Stated rate 0.167, inferred 0.625, ambiguous 0.208. The two passes disagreed on whether to author one synthetic proposition per paper or multiple per-finding propositions. Both interpretations are defensible; the rubric needs to pick one.

**Recommended rule:** *one canonical proposition per finding-cluster; if a paper carries multiple distinct findings, author multiple `proposition_refs` and let the synthesis layer (`[t023]`) re-aggregate.* This avoids forcing the extractor to invent a synthetic catch-all proposition. It also keeps `proposition_refs` array semantics aligned with v2.1's "may be empty for evaluation/operation artifacts."

This belongs in v2.2 documentation, not the schema itself — it's an authoring-rule clarification.

### Action 6 — Define `uncertainty_summary` canonical-form rule (P1)

Ambiguous rate 0.583 — the highest of any field. v2.1 carries this as open-question 2. The empirical signal: most paper summaries in the corpus are prose, not numeric; only papers with concrete benchmark results (Williams2018, Maier2022) afforded a clean canonical-form summary. Forcing an `"BF10=0.115"`-style short string was the source of ambiguity.

**Recommended rule:** when the paper's primary findings are prose-described, `uncertainty_summary` may carry a short qualitative form ("CPDAG, 12 edges; vaccination→severe-illness present-but-undirected") and the field is not required to be a single numeric statistic. Detailed numeric uncertainty lives in extensions. Mark `uncertainty_summary` `[opt]` in v2.2 (currently required).

### Action 7 — Clarify `reason_codes` not-applicable semantics (P1)

The pass 1 / pass 2 split on `reason_codes` was a clean methodology disagreement: pass 1 treated empty-list as a scoreable value (giving score 0/1 depending on confidence); pass 2 treated "no codes apply" as `✗`. Neither is wrong — but the rubric should pick one.

**Recommended rule:** when no reason codes apply, score the field `2` (stated empty) rather than `✗`. The empty list is a real value with a clear semantic ("the author affirmatively declares no reason-coded concerns").

This is a rubric clarification for D4 and beyond; in v2.1 itself, the schema and field semantics are correct.

### Summary of v2.2 patches

| Patch | Action | Priority |
|---|---|---|
| 1 | Remove `target_artifact_ref` from core; require it in evaluation/audit/operation extensions | P1 |
| 2 | Extend `artifact_type` enum: `methods-paper`, `framework-paper`, `benchmark-or-dataset-paper` | P1 |
| 3 | Extend `comparison_target` enum: `method-set` | P1 |
| 4 | Extend `support_direction` enum: `framework-proposal` | P2 |
| 5 | Add `proposition_refs` cardinality authoring rule (one per finding-cluster) | P1 (docs) |
| 6 | Loosen `uncertainty_summary` canonical-form requirement; mark `[opt]` | P1 |
| 7 | Clarify `reason_codes` empty-list scoring rule | P1 (rubric) |

After applying patches 1–4 and 6, **core field count moves from 18 → 17 (12 required, 5 optional)**: `target_artifact_ref` removed; `uncertainty_summary` moves required → optional. Patches 5 and 7 are documentation/rubric, not schema.

---

## D4 — LLM-vs-LLM-blind agreement note (informs `[t033]`)

### What this measures

Two independent blind LLM extractors with verbatim-identical packets (v2.1 schema sections + rubric + 12 paper-summary file paths) and no shared context produced extraction tables on the same 13 fields. Agreement reflects **rubric-induced extraction variance** — the degree to which the rubric is precise enough that two extractors converge — not full-context-vs-blind context-access advantage. (The original full-context manual signal was not collected; see methodology section of the sampling plan for why.)

### Per-field agreement table

| Field | Exact-agreement rate | Within-1 rate | Notes |
|---|---|---|---|
| `claim_source_ref` | 1.000 | 1.000 | Trivial — both passes pick the paper itself, score 2 |
| `validation_status` | 1.000 | 1.000 | Trivial — both passes default to `pending` |
| `target_artifact_ref` | 0.917 | 1.000 | One within-1 split (Yu2026: P1=1, P2=0) |
| `artifact_type` | 0.917 | 1.000 | One within-1 split (Mulder2026: P1=0, P2=1) |
| `method_ref` | 0.917 | 1.000 | One within-1 split (Allen2017: P1=0, P2=1) |
| `validation_role` | 0.917 | 1.000 | One within-1 split (Allen2017: P1=1, P2=0) |
| `extensions` | 0.833 | 1.000 | Two within-1 splits (Yu2026, Allen2017) |
| `input_artifact_refs` | 0.833 | 1.000 | Two within-1 splits (Klugkist2023, Mulder2026) |
| `comparison_target` | 0.667 | 1.000 | Four within-1 splits — enum-gap signal |
| `uncertainty_summary` | 0.667 | 1.000 | Four within-1 splits — definition signal |
| `proposition_refs` | 0.583 | 1.000 | Five within-1 splits — cardinality signal |
| `support_direction` | 0.583 | 1.000 | Five within-1 splits — pass 1 systematically scored higher than pass 2 |
| `reason_codes` | 0.000 | n/a | All 12 cells split on applicability (P1=0/1, P2=✗) — clean rubric ambiguity |

### Disagreement direction

Within-1 disagreements skewed: pass 1 scored higher than pass 2 in **17 of 25** cells (68%). This is a measurable extractor calibration difference between two fresh-context Claude Opus subagents on the same prompt. It is small in magnitude (always within-1) but consistent in direction.

For `[t033]`: this is empirical evidence that **extractor calibration varies between sessions even when context is fully blind and the prompt is verbatim-identical**. Agent-source modeling should not assume idempotent extraction; ensemble-of-N or repeated-extraction-with-disagreement-flagging may be needed for high-stakes fields.

### Rubric ambiguity flag (exact-agreement < 0.6)

Two fields cross the rubric-ambiguity threshold:

- **`reason_codes`** — 0.000 exact agreement. Cause: rubric did not specify whether empty-list maps to a score or to `✗`. Fix in v2.2 (D3 patch 7).
- **`support_direction`** — 0.583 exact agreement. Cause: pass 1 systematically scored higher (`supports` = 2) where pass 2 scored within-1 (`supports` = 1, "could also be methodological-input"). Same value picked, different confidence. Fix: a clearer rubric rule for what counts as "stated" support_direction.

A third field (`proposition_refs`) is on the boundary at 0.583 exact agreement. Its fix is the cardinality rule (D3 patch 5), not a rubric-precision tweak.

### What this audit cannot say

- It cannot estimate **full-context manual** extraction reliability against blind LLM extraction. That signal is deferred to a future audit running a manual pass *before* any LLM pass is visible.
- It cannot estimate **extractor variance across model families** — both blind passes used the same model. A separate audit with two different LLM families would test whether the systematic pass-1-higher-than-pass-2 calibration drift is model-internal or model-family-internal.
- It does not validate `[t025]` reason-code coverage. The reason-code rubric ambiguity above is structural (what does ✗ mean?) and will resolve before any code-coverage check.

### Carry-forward to `[t033]`

`[t033]` (LLM-agents-as-fallible-sources) should treat this audit's findings as inputs:

1. Even verbatim-identical blind extractions disagree on within-1 calibration roughly 25–40% of the time on rubric-ambiguous fields. Agent-source modeling needs a per-call agent identity and a per-extraction confidence/score.
2. Systematic calibration drift between fresh sessions is real and small. Ensemble-of-N may be needed for high-stakes extractions.
3. Two of the 13 fields (`reason_codes`, `support_direction`) have rubric-induced ambiguity that should be resolved in v2.2 before any agent-driven extraction at scale.

---

## Routing-test results (n=5)

The five out-of-scope papers (Linkov2017, Aitken2024, Vahabi2022, Zhang2025ScientificMethod, Hackenberger2020) were not field-scored — only routed. The blind passes did not see them, so this section reports the orchestrator's classification against v2.1's "What does NOT live in t022" rule.

All 5 classify cleanly as out-of-scope per v2.1's rule:

| Paper | Out-of-scope category | v2.1 rule applies? |
|---|---|---|
| Linkov2017 | "methodological commentary, not an empirical validation study" | yes — survey/conceptual |
| Aitken2024 | "methodological review" | yes — survey/conceptual |
| Vahabi2022 | "review of unsupervised multi-omics integration methods" | yes — survey + taxonomy |
| Zhang2025ScientificMethod | "perspective/review" | yes — survey/conceptual |
| Hackenberger2020 | "compact survey of available Bayesian meta-analysis software" | yes — survey/method-registry |

**Routing accuracy: 5/5.** No additions or wording changes to the v2.1 out-of-scope rule are needed from this sample.

A subtler observation surfaced during the audit: Allen2017 (in the main sample) was independently flagged as borderline-out-of-scope by both blind passes ("self-described methodological commentary surveying integration challenges"). Mulder2026, Yu2026, and Jiang2024 were also flagged as borderline. This suggests that **the boundary between in-scope methodological-claim papers and out-of-scope methodological-commentary papers is rubric-ambiguous in a way the routing rule does not yet handle.** v2.2 should add an explicit boundary criterion (e.g., "if the paper presents at least one falsifiable propositional claim with a comparison or evidence basis, it is in-scope; pure commentary or agenda-setting is out-of-scope").

This is a P2 routing-rule refinement, not a P1 fix.

---

## Aggregate cost

- Pass 1 wall-clock: ~2.5 min, ~95 min self-reported effort.
- Pass 2 wall-clock: ~2 min, ~70 min self-reported effort.
- Orchestrator-side aggregation (D2/D3/D4 in this document): ~50 min.

Total D2+D3+D4 produced from ~5 min of subagent wall-clock time and ~50 min of orchestrator effort. The narrow-audit estimate ("3–5 min per paper for the LLM pass; agent-vs-manual scoring takes longer than the LLM pass itself") was approximately correct, with the simplification that both passes are LLM-blind rather than one being manual.

---

## Carry-forward to v2.2

**v2.2 patches (P1, do now):**

1. Remove `target_artifact_ref` from core; require it in evaluation/audit/operation extensions.
2. Extend `artifact_type` enum: `methods-paper`, `framework-paper`, `benchmark-or-dataset-paper`.
3. Extend `comparison_target` enum: `method-set`.
4. Loosen `uncertainty_summary` canonical-form requirement; mark `[opt]`.
5. Add `proposition_refs` cardinality authoring rule.
6. Clarify `reason_codes` empty-list scoring rule.

**v2.2 patches (P2, do soon):**

7. Extend `support_direction` enum: `framework-proposal`.
8. Refine the routing rule: add an explicit "falsifiable propositional claim with comparison or evidence basis" criterion for in-scope vs out-of-scope.

**Deferred work:**

- A future audit with a true full-context manual pass executed before any LLM pass is visible. This is required to recover the original `[t033]` signal.
- A multi-LLM-family audit to separate model-family extractor calibration from rubric-induced variance.

After v2.2, aspect extensions (`[t034]`/`[t035]`/`[t037]`/`[t038]`/`[t040]`) can begin against a stable contract. Per the v2.1 audit's softened gate, they may have begun in parallel with `[t030]` running; if so, they need to refresh against v2.2 patches 1–3 (which change core).
