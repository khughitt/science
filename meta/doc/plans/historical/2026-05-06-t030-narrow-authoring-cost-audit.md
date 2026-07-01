# t030 — Narrow Authoring-Cost Audit (first pass)

> **Scope.** Pragmatic first pass on `[t030]`: 4 paper summaries (not the full 10–20), no LLM-vs-human agreement scoring, no rubric. Goal: surface contract problems in the v2 design draft (`meta/doc/plans/2026-05-06-evidence-payload-core-and-extension-contract.md`) cheaply, *before* the full `[t030]` deliverable commits to a sampling plan and rubric. **This audit does not satisfy the full `[t030]` deliverables specified at `meta/tasks/active.md:345`** — it informs them.
>
> **Method.** For each paper, classify what payload(s) it implies, attempt to author them under v2's core schema, and log every spot where I had to invent a field, leave one blank, or pick a value that didn't quite fit. Each paper picked to **not** overlap with the six worked examples already in v2 (Gronau, Zhao, Petersen, Mohammadi, Ding, Banzi).

---

## Sample

| Paper | Aspect | Paper kind |
|---|---|---|
| Heyard2025 | Statistical / evaluation | Scoping review (50 reproducibility metrics) |
| Faller2024 | Causal | Methodological — proposes self-compatibility diagnostic |
| Jin2025 | Agent-op / infrastructure | Survey on KG evolution & versioning |
| Freiesleben2023 | Conceptual / methodology | Philosophy-of-science theory paper |

---

## Per-paper attempts

### 1. Heyard2025 — scoping review

**Classification.** Two candidate payloads: (a) a *meta-claim* about reproducibility-metric pluralism; (b) a method-registry import for each of 50 metrics.

**Drafted payload (meta-claim).**

```yaml
core:
  payload_id: ev-2026-heyard-metric-plurality
  artifact_type: literature-review-claim                # ❓ not in v2's enum
  extensions: [literature-review-claim]                 # ❓ no extension defined for this
  created_at: 2026-05-06T15:00:00Z
  input_artifact_refs: []                               # ❓ no derivation inputs; the paper itself is the source of the claim
  claim_source_ref: paper:Heyard2025                    # ❓ proposed new core field — "extracted from this artifact"
  method_ref: ~                                         # scoping-review method? not paper-defined
  agent_ref: agent:human:khughitt
  pipeline_provenance_ref: ~
  proposition_refs: [prop:no-universal-reproducibility-metric]
  comparison_target: hypothesis-set                     # ❓ stretch
  support_direction: supports
  validation_role: prioritize-attention
  validation_status: pending                            # extraction has not been audited; peer-review of the source ≠ validation of this payload
  uncertainty_summary: "scoping review: 50 metrics across 49 projects + 97 methods papers"
  reason_codes: [single-source-evidence]                # ❓ not in t025 yet
```

**Note on first attempt.** I initially put `paper:Heyard2025` into `input_artifact_refs` and set `validation_status: validated` because the source paper is peer-reviewed. Both were wrong: in v2 (line 41), `input_artifact_refs` are *derivation inputs* (datasets, studies, prior payloads, audited artifacts), not the paper a claim was extracted from; and `validation_status` is the *payload's* state, not the source's. The right move is a separate `claim_source_ref` core field for extraction provenance.

**Method-registry side.** Cannot be expressed as a payload at all — registry imports are not "evidence about a proposition." Belongs to a different artifact class entirely.

**Gaps surfaced.**
- **Gap A — `literature-review-claim` is not in v2's `artifact_type` enum.** The v2 `support_direction` includes `methodological-input` and `quality-record`; neither matches a survey claim.
- **Gap B — Method-registry imports have no home.** No payload type covers "this paper defines 50 methods we want to register." Either we add a `registry-import` artifact_type or we accept that registry imports are out-of-scope of t022 (and live in a different graph layer entirely).
- **Gap C — No core field for extraction provenance.** A paper-extracted claim has *no derivation inputs* (the paper isn't an input — the claim was *extracted from* it). v2's `input_artifact_refs` does not capture this; nor does `method_ref`. Candidate fix: a new core field `claim_source_ref` for "the artifact this payload's claim was lifted from." Distinct from `input_artifact_refs` (derivation inputs) and `method_ref` (canonical method definition).

**Authoring effort.** ~10 fields filled with confidence; 4 fields required workarounds; 1 field (`method_ref`) genuinely doesn't apply.

---

### 2. Faller2024 — methodological diagnostic paper

**Classification.** Three candidate payloads: (a) the empirical claim ("incompatibility score correlates with SHD on simulated benchmarks"); (b) the methodological-contribution claim (defines self-compatibility); (c) a method-registry import. Authoring (a) — closest to a "real" evidence payload.

**Drafted payload.**

```yaml
core:
  payload_id: ev-2026-faller-incompat-shd-correlation
  artifact_type: empirical-evaluation-claim             # ❓ not in v2's enum
  extensions: [empirical-evaluation-claim, statistical-uncertainty]   # ❓ first extension undefined
  created_at: 2026-05-06T15:15:00Z
  input_artifact_refs: []                               # paper does not name a public dataset; sims are internal
  claim_source_ref: paper:Faller2024                    # extraction provenance (proposed new field, see Gap C)
  method_ref: ~                                         # ❓ the paper *is* the method definition; see Gap D
  agent_ref: agent:human:khughitt
  pipeline_provenance_ref: ~
  proposition_refs: [prop:self-compat-detects-causal-discovery-failure]
  comparison_target: hypothesis-set
  support_direction: supports
  validation_role: prioritize-attention                 # single paper, simulated; not strengthen
  validation_status: pending                            # peer-review of the source ≠ validation of this extracted payload
  uncertainty_summary: "incompat ~ SHD in sims (some settings); 1 paper, simulated benchmarks"
  reason_codes: [single-source-evidence, simulated-data-only]      # ❓ neither in t025 yet
```

**Gaps surfaced.**
- **Gap A — repeats:** `empirical-evaluation-claim` artifact_type missing.
- **Gap C — repeats:** `claim_source_ref` again needed; `input_artifact_refs` empty for paper-extracted claims that don't name external derivation inputs.
- **Gap D — Method-paper-as-claim-source means `method_ref` is unset, not duplicated.** With `claim_source_ref` carrying the paper, `method_ref` doesn't *need* to point at the paper — the method definition lives where the claim was extracted from. So Finding 2's source/method split is preserved by adding `claim_source_ref`, not by relaxing `method_ref`. (Earlier draft of this audit recommended allowing `method_ref` to duplicate `input_artifact_refs` — wrong; retracted.)
- **Gap E — Reason codes for "sample of N=1 paper" / "simulated only" do not exist.** Strong candidates for t025 additions: `single-source-evidence`, `simulated-data-only`, `internal-validity-only`. These are generic, not extension-specific.
- **Gap F (revised) — Method-paper self-validation as a propagation hint.** When `claim_source_ref` and (a future downstream) `method_ref` resolve to the same paper, the validator should attach a `self-validated-method` reason code — purely as a hint to consumers, not as a structural exception to the source/method split.

**Authoring effort.** ~10 fields confident; 3 invented reason codes; 2 fields required workarounds.

---

### 3. Jin2025 — survey on KG evolution

**Classification.** No domain-claim payload. The paper is taxonomy + literature pointer. Natural project-side artifact: a topic note or method-registry pointer. Attempting to author it as a payload exposes the *boundary* of t022's scope.

**Attempt.**

```yaml
core:
  payload_id: ev-2026-jin-kg-evolution-taxonomy
  artifact_type: ???                                    # truly nothing fits
  extensions: [???]
  ...
  proposition_refs: []                                  # no proposition
  target_artifact_ref: ~                                # not auditing anything
  comparison_target: n-a
  support_direction: ???                                # not supporting/disputing/methodological-input/quality-record/operation-record
  validation_role: record-only
  validation_status: validated
  uncertainty_summary: "survey: KG evolution = proliferation + dynamic-embedding + versioning"
```

**Conclusion: no payload, no enum pressure.** Survey/conceptual papers do not fit t022's payload schema and should not be forced to. They belong to a separate `topic` / `vocabulary` / `method-registry` artifact class outside t022's scope. This is consistent with v2's Finding 1 ("Papers are not payloads"); the audit's contribution is to make that explicit and to *not* count taxonomy-import failure as evidence that t022's enums are undersized. (Earlier draft of this audit suggested `vocabulary-contribution` / `taxonomy-import` enum additions — retracted; those would re-import the survey class through the back door.)

**v2.1 should add an explicit "What does NOT live in t022" section** listing surveys, taxonomies, conceptual theory papers, and method-registry imports.

**Authoring effort.** Failed cleanly. No payload draftable.

---

### 4. Freiesleben2023 — conceptual theory of robustness

**Classification.** Same as Jin2025: vocabulary + conceptual machinery, no propositional claim. Same outcome — fails to fit t022.

But there is a *secondary* artifact: when later evidence is authored (e.g., the OSIRIS audit in v2 example 6), the `robustness_modifier` / `target_tolerance` fields *come from* this paper. So Freiesleben2023 is method-registry source for downstream extensions but contributes no payload itself.

**Authoring effort.** Failed cleanly, like Jin2025.

---

## Findings

### F1 — `artifact_type` enum is too narrow.

Three of four papers needed an `artifact_type` not yet in v2 (`literature-review-claim`, `empirical-evaluation-claim`, taxonomy-import). v2's enum was implicitly enumerated from the worked examples; as soon as we leave that set, paper summaries don't fit. **v2.1 must publish the full enum** and either (a) extend it to cover paper-summary-extracted claims, or (b) explicitly out-of-scope them and route them through a sibling artifact class.

### F2 — Paper-extracted-claim payloads need a `claim_source_ref` core field.

v2's `input_artifact_refs` is for *derivation inputs* (datasets, studies, prior payloads, audited artifacts) and `method_ref` is for the canonical method/tool definition. Neither is "the artifact this payload's claim was lifted from." Without a dedicated extraction-provenance field, paper-extracted claims either misuse `input_artifact_refs` (which silently widens its semantics) or have nowhere to record their source. **Add `claim_source_ref: ref [opt]` to core.** This is more precise than the earlier "allow `method_ref` to duplicate input_artifact_refs" suggestion, which would have collapsed Finding 2's source/method split.

### F3 — Survey / taxonomy / vocabulary papers don't generate payloads.

Half the sample (Jin2025, Freiesleben2023) has *no natural payload*. v2's contract is silent on this; v2.1 should add an explicit "What does NOT live in t022" section listing surveys, conceptual theory, taxonomy/vocabulary contributions, and method-registry imports, and route them through a sibling artifact class (likely owned by `[t038]` graph-evolution or a future topic-import task). This is a *boundary clarification*, not an enum extension.

### F4 — Reason codes for paper-summary-level evidence are missing from t025.

`single-source-evidence`, `simulated-data-only`, `peer-reviewed-only`, `self-validated-method` are all generic-not-extension-specific codes that arise as soon as we author paper-derived payloads. They should be added to t025 as a "general evidence-quality" code group, not deferred to specific extensions.

### F5 — `validation_status` is the *payload's* state, not the source paper's.

A common authoring error (which I committed twice on first draft) is to set `validation_status: validated` because the source paper is peer-reviewed. v2 line 54 says `validation_status` is the *payload* state, not the source's. v2.1 should add an explicit note next to the field: peer-review of `claim_source_ref` does not validate the extracted payload; default `pending`. A `peer-reviewed-only` reason code can carry the source-quality signal separately.

### F6 — Authoring cost is uneven.

Empirical-claim payloads (Faller2024) authored in ~5 minutes once the gaps were noted. Survey/taxonomy papers (Jin, Freiesleben) couldn't be authored at all (correctly — they don't belong in t022). The takeaway: **v2's contract handles synthesis-derived and method-applied payloads well; it needs `claim_source_ref` plus an explicit out-of-scope statement to handle the dominant flow of paper summaries entering the project**, which will be survey / methodological / theory papers, not freshly-generated synthesis runs.

(Note on enum sizing: this audit deliberately does **not** recommend extending `support_direction` or `artifact_type` enums on the basis of this 4-paper sample. The full `[t030]` with a wider sample should make the enum-sizing call.)

---

## Recommendations (v2 → v2.1 patch + a focused full-`[t030]`)

The narrow pass justifies a small set of v2.1 patches that are clearly load-bearing now, plus a focused full-`[t030]` to make the enum-sizing decisions on a wider sample:

**v2.1 patches (do now):**

1. **Add `claim_source_ref: ref [opt]` to core.** "The artifact this payload's claim was extracted from." Distinct from `input_artifact_refs` (derivation inputs) and `method_ref` (canonical method definition). Field count moves from 17 to 18.

2. **Add an explicit "What does NOT live in t022" section** to v2.1, listing surveys, conceptual theory, taxonomy/vocabulary, and method-registry imports. Route them to a sibling artifact class.

3. **Add a "validation_status pitfall" note** to the core schema description: `validation_status` is the payload's state. Peer-review of `claim_source_ref` does not validate the extracted payload; default to `pending`.

4. **Add a generic-evidence-quality reason-code group to t025**, with at minimum: `single-source-evidence`, `simulated-data-only`, `peer-reviewed-only`, `self-validated-method`. Mark `peer-reviewed-only` non-blocking; the others non-blocking by default but available for extension override.

**Full `[t030]` (do next, deliverables per `meta/tasks/active.md:345`):**

5. **Sampling plan and rubric.** 10–20 papers, biased toward paper-extracted-claim payloads (the schema-weak region), with explicit per-field success / ambiguity / inferred-vs-stated columns.

6. **LLM-vs-human extraction agreement.** Run the manual pass and an LLM pass against the same rubric and score agreement; that informs `[t033]` agent-source modeling.

7. **Use the wider sample to make enum-sizing decisions** for `artifact_type` and `support_direction`. Do **not** extend these enums in v2.1.

The recommended sequence is: ship the four v2.1 patches (1–4), then run the full `[t030]` (5–7). Aspect extensions (`[t034]`/`[t035]`/`[t037]`/`[t038]`/`[t040]`) can begin against v2.1 in parallel with `[t030]` running, so long as their drafts treat enum sets as not-yet-locked. This is a softer gate than the earlier draft of this audit suggested.

---

## What this audit does *not* claim

- It does not claim the contract is broken. All six v2 worked examples remain valid.
- It does not claim the gaps require a structural rewrite. F1–F6 are addressable in v2.1 without re-doing core/extension separation, multi-extension dispatch, or reason-code inheritance — the load-bearing parts.
- **It does not replace the full `[t030]` deliverable.** The deliverables specified at `meta/tasks/active.md:345` (sampling plan, per-field extractability table, field-pruning recommendation, LLM-vs-manual agreement note) are not produced here and are still required.

---

## Closing recommendation

Patch v2 with the four v2.1 edits above (`claim_source_ref`, the out-of-scope section, the validation_status note, the generic reason-code group), then run the full `[t030]` with a sample biased toward paper-extracted-claim payloads. Aspect extensions can be drafted in parallel with the full `[t030]` running, so long as they treat enum sets as not-yet-locked. The full `[t030]` makes the enum-sizing call.
