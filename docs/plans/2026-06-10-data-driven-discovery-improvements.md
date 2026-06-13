# Data-Driven Discovery Improvements — Umbrella Roadmap

> **This is a roadmap/catalog, not an implementation plan.** It frames an opportunity
> space and lists candidate workstreams tiered by readiness. It deliberately uses *no*
> `- [ ]` task checkboxes — each workstream below is expected to spin out into its own
> `brainstorm → design spec → writing-plans → implementation` cycle. Pick one, then go
> deep on it separately.

**Provenance.** The observations motivating this roadmap come from the MIA seminar
*"Evaluating AI agents in biological discovery"* (Shreya Johri, with a primer by Maha
Shady; `talk:Johri2026`, `cite:Johri2026`, hosted in the `science-meta` project at
`meta/doc/background/talks/Johri2026.md`). Theme A additionally draws on the **Platonic
Representation Hypothesis** (different modalities converging on a shared latent → stronger
joint evidence). The talk is an *unrefereed* source on ongoing work: its specific results
are hints to verify, but its framing maps cleanly onto Science's existing machinery.

**Baseline (assumed *after* these facets land — not all are in the repo yet).** This roadmap
builds *on top of* two framework facets and does not re-propose what they deliver. Their
status differs, and the gating is load-bearing for any spin-out:
- `2026-06-08-dataset-evidence-flow-plan.md` — `dataset_usage` / `overlap`, dataset-entity
  origin invariants, and the A1/A2/B1/B2 dataset-**independence** machinery (same-vs-distinct
  dataset collapse). This independence machinery is **already merged** — **evidence
  *independence* is built**, so the new Theme A work is *strength tiering* and *cross-modality
  reward*, not independence.
- `2026-06-08-epistemic-edges-plan.md` — relational propositions, the evidence-line
  `quantitative_result`, and the `belief_eligible` staging marker. **Not yet in the repo**
  (verified 2026-06-10: zero `belief_eligible` / `quantitative_result` occurrences under
  `science/`); this facet is still HELD on the v3-substrate gate and *defines* that work
  rather than providing it. **Theme A (A1/A2) is gated on these fields landing** — a spin-out
  must not start from fields/behavior that do not exist yet.

**How to read each entry.** `talk observation → gap in Science today → sketch of the change
→ readiness tier → dependencies`.

---

## Theme A — Evidence strength tiering & multi-modal corroboration

*Talk grounding:* robustness was established by finding a signal in scRNA and **re-confirming
it in an independent modality/dataset** (TCGA bulk) against independent ground truth (IHC
ER-status, survival); concordance was highly variable, so a single-source signal is weak.

- **A1 — Evidence-tier ladder.** *Gap:* belief aggregation treats a literature "hint", a
  single analyzed dataset, and corroboration across many as differing mostly by count, not by
  *kind* of support. *Sketch:* make source-tier an explicit, belief-weighting-relevant
  attribute — `paper-hint < single-dataset < multi-dataset < multi-modal` — layered on the
  `dataset_usage` / `belief_eligible` fields. The user's long-standing stance ("papers we
  haven't analyzed are hints; data we analyzed is better; multiple experiments better still")
  becomes a first-class, queryable axis. *Tier:* **Gated** (extends the epistemic-edges
  evidence model). *Deps:* **`belief_eligible` / `quantitative_result` must land first**
  (epistemic-edges); then dataset-evidence-flow.
- **A2 — Reward cross-modality corroboration.** *Gap:* nothing currently *rewards* the same
  conclusion arriving from orthogonal modalities; the independence engine collapses
  *same-source* duplicates but doesn't *up-weight* genuinely orthogonal agreement. *Sketch:*
  reward cross-modality agreement **only after dataset/sample/ground-truth dependence is
  accounted for** — modality alone is **not** independence: bulk and scRNA can share patients,
  preprocessing, labels, or derived annotations. Orthogonal *modality* is one input to an
  independence judgement, not a substitute for it, so this **composes with** the existing
  `overlap` / dependence-role accounting (B2) rather than adding a parallel "modality =
  independent" axis. The motivating case earned its weight from an independent dataset **and**
  independent ground truth (IHC, survival), not modality alone (cf. Platonic Representation
  Hypothesis). *Tier:* **Gated** (follows A1). *Deps:* A1, dataset-independence (B2).

## Theme B — Process quality over cookbook execution

*Talk grounding (the headline finding):* agents iterated only on cell-type *annotations*,
never on QC / clustering resolution / parameters; they followed the canned scanpy recipe
verbatim, while every real paper deviates for dataset-specific reasons. "No computational
biologist one-shots the analysis."

> **Extend the existing QA substrate, don't rediscover it.** This repo already ships
> `docs/conventions/pipeline-qa-checkpoints.md` (QA checkpoint conventions) and
> `docs/process/pipeline-audit-and-refactor.md` (the three-axis pipeline audit/refactor
> playbook). B1–B3 build *on* those — their gap is missing reusable libraries / metrics
> *behind* the conventions, not a missing convention.

- **B1 — QA-check toolkit. ✅ SHIPPED (2026-06-11).** *Gap:* QA conventions exist as checkpoint
  guidance, but there is no reusable *library* of data-type-specific checks operationalizing them.
  *Sketch:* a growing toolkit of helper checks per data type (scRNA, bulk RNA, genomics CN/SV,
  amplicon, …) that implements the checkpoint conventions, rather than rediscovering their shape.
  *Tier:* **Mid.** *Deps:* `docs/conventions/pipeline-qa-checkpoints.md`. *Delivered:* light
  standalone **`science-qa`** distribution at `science/qa/` (config-runner over the `qa:` schema +
  scRNA pack + deterministic `qa_report.{json,md}` + analyst-owned `qa_dispositions.yaml`). See
  `docs/plans/2026-06-11-qa-toolkit-and-iteration-audit-design.md`.
- **B2 — Quantify QA breadth/depth. ✅ SHIPPED (2026-06-13).** *Gap:* a project can record one
  shallow check and look as "QA'd" as one with broad coverage. *Sketch:* a score/metric over QA
  coverage (against the checkpoint conventions' expected checks) that flags shallow or narrow
  checking. *Tier:* **Mid.** *Deps:* B1, `docs/conventions/pipeline-qa-checkpoints.md`.
  *Delivered:* composable **check-library** — checks composed as **aspects** (`general`, `tabular`,
  `numeric-column`, `gene-expression-qc-table`, `scrna-qc-table`, `project-local`) into a named
  **program** (`qa.program`), providing a *baseline library* of type-appropriate checks;
  project-local extensions added via `qa.project_local`. Breadth is a program-derived coverage
  readout: `qa_report.json` now carries a `coverage` block (executable denominator +
  `ran`/`empty`/`blocked`/`not-applicable` per invocation + declared-but-unconfigured families);
  `science qa-audit` surfaces a `breadth` column (`ran/denominator`). See
  `docs/plans/2026-06-13-qa-check-library-design.md` and
  `docs/plans/2026-06-13-qa-check-library-plan.md`.
- **B3 — Flag no-iteration workflows. ✅ SHIPPED (2026-06-11).** *Gap:* a build→run-once→record→"truth"
  workflow is indistinguishable from a properly iterated one. *Sketch:* detect and flag analyses
  with zero recorded iterations / re-entries, surfacing them through the audit playbook. *Tier:*
  **Mid.** *Deps:* `docs/process/pipeline-audit-and-refactor.md`. *Delivered:* **`science qa-audit`**
  advisory CLI (`science_tool/qa_audit/`) reporting two orthogonal verdicts (iteration:
  QA-RESPONSIVE/RE-RAN-UNRELATED/SINGLE-RUN; engagement: NO-QA/NO-FLAGS/RESPONDED/IGNORED/PARTIAL).
- **B4 — Adaptive (not rigid) pre-registration.** *Gap:* the pre-reg + gating framing imports
  a clinical-trial stance that can discourage the exploratory, data-driven iteration that
  discovery meta-analysis *needs*. *Sketch:* reframe `pre-register` as sharpening thinking +
  capturing blindspots/confounders **while explicitly planning to iterate and let data drive**
  — distinct from confirmatory gating. *Tier:* **Near-term** (skill/doc change). *Deps:* none.

## Theme C — Robustness via perturbation & model comparison

*Talk grounding:* agents go down one reasoning track and over-rank familiar programs (e.g.
EMT) regardless of task; brittle, overfit conclusions survive unexamined.

- **C1 — Seeded `noise` parameter.** *Gap:* no systematic guard against overfitting/brittleness
  of a conclusion to exact parameter/input choices. *Sketch:* a (seeded) `noise` config knob
  that perturbs some/all workflow parameters or inputs, surfacing sensitivity; ties to the
  `statistics` skill's sensitivity/perturbation methods. *Tier:* **Mid.**
- **C2 — Bayesian model-selection support.** *Gap:* model/structure choices are rarely
  compared quantitatively. *Sketch:* first-class support for Bayesian model comparison/
  selection as a robustness + anti-overfit tool. *Tier:* **Exploratory.** *Deps:* C1, statistics.

## Theme D — Reproducibility verification

*Talk grounding (indirect):* the speaker re-ran agents over 5 parallel runs to account for
stochasticity; reproducibility is a precondition for trusting any of this. *(Also surfaced by
the user: we assert "reproducible workflows" but don't verify it.)*

- **D1 — Seed in version-controlled config; stochastic steps consume it.** *Gap:* stochastic
  steps (t-SNE, UMAP, clustering, sampling) may not consume a recorded seed. *Sketch:* require
  a seed in each workflow's committed config and ensure stochastic steps read it. *Tier:*
  **Near-term** (convention + check).
- **D2 — Re-run-and-diff.** *Gap:* "reproducible" is asserted, never checked. *Sketch:* re-run
  the pipeline with the same seed and assert identical outputs (a reproducibility gate). *Tier:*
  **Mid.** *Deps:* D1. *Note:* the noise/overfitting link (Theme C) is why this lives in the
  umbrella rather than as standalone infra.

## Theme E — Decision & provenance richness

*Talk grounding:* M3A logs, *before* each tool executes, *why* the tool was chosen, what
alternatives were considered, and **what output is expected** — and the cited Anthropic result
that reasoning traces are *not faithful*.

- **E1 — Step-level decision telemetry.** *Gap:* provenance records *what* ran, not *why it was
  chosen* or *what was expected*. *Sketch:* capture choice-rationale + expected-outcome **before
  execution**, turning each step into a falsifiable micro-prediction and making
  result-contradicts-expectation detectable (the only reliable reflection trigger). *Tier:*
  **Exploratory** (deeper provenance). *Deps:* provenance graph.
- **E2 — Artifact-over-narrative faithfulness.** *Gap:* `interpret-results` / `review` can be
  swayed by a clean-sounding rationale. *Sketch:* weight verifiable artifacts (code, numbers,
  plots) above prose rationale; treat a tidy narrative as ~zero evidence of a sound process.
  *Tier:* **Mid** (skill change).

## Theme F — Memory & bias

*Talk grounding:* the cognitive-science memory taxonomy (episodic / semantic / procedural), and
the failure modes — overconfidence, no external grounding, opt-out on hard questions, gene-set
credulity ("EMT shows up therefore EMT"), tail-hiding metrics.

- **F1 — Episodic failure memory.** *Gap:* Science captures landed interpretations but not
  systematically "what we tried that failed and why" — the **episodic** gap. *Sketch:* a
  failed-attempt record feeding `next-steps` / `bias-audit`. *Tier:* **Exploratory.**
- **F2 — `bias-audit` additions.** *Gap:* current audit doesn't target these specific traps.
  *Sketch:* new checks for overconfidence / no-external-grounding / opt-out-on-hard-questions /
  off-the-shelf-gene-set credulity / tail-hiding (averaged) metrics. *Tier:* **Near-term**
  (skill change).

---

## Readiness tiers (the prioritized menu)

| Tier | Workstreams | Why now / what blocks it |
|---|---|---|
| **✅ Shipped** | B1, B3, B2 | B1+B3 merged to local `main` 2026-06-11 (`science-qa` toolkit + `science qa-audit`); B2 merged 2026-06-13 (composable check-library, aspects/programs, breadth coverage) |
| **Near-term (unblocked)** | B4, D1, F2 | Skill / doc / convention changes; no substrate dependency |
| **Mid** | C1, D2, E2 | New mechanisms, scoped |
| **Gated** | A1, A2 | Need `belief_eligible` / `quantitative_result` from epistemic-edges (not in repo yet) |
| **Exploratory** | C2, E1, F1 | Deeper provenance/methodology; design-heavy |

## Recommended first spin-out

- **B3 + B1 (no-iteration flagging + QA-check toolkit), then B2** — ✅ **B3 + B1 + B2 SHIPPED**
  (B1+B3 merged to local `main` 2026-06-11; `science-qa` toolkit + `science qa-audit`; see
  `docs/plans/2026-06-11-qa-toolkit-and-iteration-audit-design.md` / `…-plan.md`).
  B2 merged 2026-06-13 as a composable check-library (aspects/programs) with breadth as a
  program-derived coverage readout; see `docs/plans/2026-06-13-qa-check-library-design.md` and
  `docs/plans/2026-06-13-qa-check-library-plan.md`.
- **Theme A (evidence tiering + cross-modality)** — strongest grounding and highest epistemic
  payoff (the user's long-emphasized hint/single/multi/multi-modal ladder, finally systematic),
  **but gated**: it cannot start until `belief_eligible` / `quantitative_result` land via
  epistemic-edges. Best second, or queue it behind that facet.

## Cross-cutting principle

The talk's spirit, which should color every workstream: **explore and iterate before
committing; let the data drive; evaluate the process, not just the result.** Pre-registration
still earns its place as a thinking-sharpener and blindspot-catcher (B4), but discovery-driven
meta-analysis is adaptive by nature — the roadmap should make iteration and multi-source,
multi-modal corroboration the path of least resistance, not the exception.
