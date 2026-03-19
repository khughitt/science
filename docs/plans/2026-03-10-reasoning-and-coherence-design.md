# Reasoning, Critical Thinking & Coherence Improvements

## Problem

The Science plugin is strong on structured output and evidence provenance but weak on **structured adversarial reasoning** — the deliberate effort to prove yourself wrong. Hypotheses are evaluated in isolation, not head-to-head. There is no mechanism to formalize expectations before analysis, no systematic bias detection, and no pipeline QA discipline to rule out "the data was wrong" before accepting "the theory was wrong."

Additionally, several commands overlap in scope, document metadata is inconsistent across types, and the inquiry status lifecycle has gaps.

## Goals

1. Add core reasoning capabilities that surface weaknesses, unknown unknowns, and alternative explanations
2. Integrate QA discipline into the computational pipeline workflow
3. Simplify and unify overlapping commands
4. Standardize document metadata for programmatic cross-referencing

## Non-Goals

- Forcing linear workflows — all status transitions remain advisory, not gating
- Adding new aspects — reasoning capabilities are foundational, not opt-in. Pipeline QA extensions are gated by the existing `computational-analysis` aspect, not a new one.
- Changing existing document _content_ formats — frontmatter is additive, not breaking

## Deliberate Breaking Changes

- `next-steps` changes from read-only/terminal-only to always saving output to `doc/meta/`. This is intentional — ephemeral analysis that disappears after the session is less useful than a versioned record. The merged command subsumes `research-gaps`, which already saved output.
- `research-gaps` output path changes from `doc/10-research-gaps.md` to `doc/meta/next-steps-<date>.md`. Projects with existing `doc/10-research-gaps.md` files keep them; they just won't be updated by the deprecated alias. No automated migration needed.

---

## Design

### Part 1: New Commands

#### 1.1 `/science:pre-register`

**Purpose:** Formalize expectations before analysis to prevent post-hoc rationalization.

**When to use:** After `add-hypothesis` or `plan-pipeline`, before running analysis. Also triggered by "what do I expect", "pre-register", "before I run this".

**Inputs:**
- Relevant hypotheses from `specs/hypotheses/`
- Relevant inquiries from `models/`
- Pipeline plan if one exists

**Output:** `doc/meta/pre-registration-<slug>.md`

**Document structure:**
- **Hypotheses under test** — which hypotheses does this analysis address?
- **Expected outcomes** — what do you expect to find, and why?
- **Decision criteria** — what evidence would support, weaken, or refute each hypothesis? Be specific (direction, magnitude, pattern).
- **Null result plan** — what does it mean if results are ambiguous or null? What would you do next?
- **Known limitations** — what can this analysis _not_ tell you, even if it works perfectly?
- **Exploratory vs. confirmatory** — which analyses are pre-registered (confirmatory) and which are explicitly exploratory?

**Discovery mechanism:** `interpret-results` finds the relevant pre-registration by matching on the `related` frontmatter field. The pre-registration document lists hypothesis IDs (e.g., `related: [hypothesis-h01-circadian-gating]`) and the interpretation document lists the same hypotheses. When both reference the same hypothesis, the cross-check activates. If multiple pre-registrations exist for a hypothesis, the most recent (by `created` date) is used.

**Process reflection:** Like all Science commands, appends a reflection block to `doc/meta/skill-feedback.md`.

**Key discipline:** The document is version-controlled. Enforcement is honor-system — nothing prevents editing post-hoc, but the git history preserves the original. `interpret-results` cross-checks against the current file content and flags if the pre-registration was modified after analysis began (by comparing `created` date against interpretation date).

#### 1.2 `/science:compare-hypotheses`

**Purpose:** Head-to-head evaluation of competing explanations, rather than evaluating hypotheses in isolation.

**When to use:** When 2+ hypotheses exist for the same phenomenon. Also triggered by "compare", "which explanation is better", "competing hypotheses", "alternative explanations".

**Inputs:**
- 2+ hypotheses from `specs/hypotheses/` (user selects, or command proposes candidates that share `related` entities in frontmatter, reference the same papers/topics, or make predictions about the same observable)
- All project evidence (topics, papers, interpretations, discussions)

**Comparison mode:** Always pairwise. When 3+ hypotheses are relevant, the command recommends the highest-value pair to compare first (based on evidence overlap and discriminability) and notes remaining pairs for follow-up.

**Output:** `doc/discussions/comparison-<slug>.md`

**Document structure:**
- **Hypotheses compared** — summary of each with key claims
- **Evidence inventory** — for each hypothesis: what supports it, what weakens it, what is silent
- **Discriminating predictions** — where do these hypotheses make _different_ predictions? These are the high-value observations.
- **Crucial experiments** — what single observation or analysis would most decisively distinguish between them?
- **Current verdict** — which is better supported, how confident, and what would change the verdict?
- **Synthesis** — are these truly competing, or could they be complementary/operating at different scales?

**Key discipline:** Forces the researcher to consider that their preferred hypothesis might be wrong, and to identify what evidence would prove it.

**Process reflection:** Like all Science commands, appends a reflection block to `doc/meta/skill-feedback.md`.

#### 1.3 `/science:bias-audit`

**Purpose:** Systematic check of cognitive and methodological biases against current project state.

**When to use:** At any point, but especially valuable before `interpret-results` or when a project has been running long enough to accumulate blind spots. Also triggered by "check my biases", "what am I missing", "audit", "threats to validity".

**Inputs:**
- Project state scoped to a focus area (specific hypothesis, inquiry, or pipeline). If no focus is specified, the command audits the most active area of the project (most recently modified documents). Full-project audit is available but optional — large projects should scope to avoid context limits.
- Pre-registration documents if they exist
- Causal DAGs if `causal-modeling` is active

**Output:** `doc/meta/bias-audit-<slug>.md`

**Bias checklist (rated: not detected / possible / likely, with evidence):**

_Cognitive biases:_
- **Confirmation bias** — Are you seeking/citing evidence that supports your preferred hypothesis disproportionately? Are disconfirming papers absent from your searches?
- **Anchoring** — Are early conclusions or first-read papers over-weighted? Has the framing shifted since the project started?
- **Availability bias** — Are you over-relying on familiar methods, datasets, or frameworks?
- **Sunk cost** — Are you pursuing a hypothesis or approach because of effort invested rather than evidence?

_Methodological biases:_
- **Selection bias** — In literature selection, data inclusion/exclusion, or method choice
- **Survivorship bias** — Are you only seeing studies/datasets/methods that "worked"?
- **HARKing** — Do current hypotheses match pre-registration? If no pre-registration exists, flag this.
- **Multiple comparisons / p-hacking risk** — How many analyses are planned? Is there correction?
- **Confounding** — Cross-references causal DAG if available; otherwise checks for uncontrolled variables
- **Publication bias** — Is the literature search biased toward positive results?

**Summary:** Overall threat level (low / moderate / elevated / high), top 3 mitigations, and recommended next actions.

**Process reflection:** Like all Science commands, appends a reflection block to `doc/meta/skill-feedback.md`.

---

### Part 2: Extensions to Existing Commands

#### 2.1 `critique-approach` + Sensitivity Analysis

**Applies to:** All projects (not aspect-gated). The sensitivity section adapts to the model type — causal DAGs get confounder-focused analysis; conceptual models get assumption-focused analysis.

**New section: "Sensitivity Analysis"**

For each key assumption or edge in the model:
- **What if this assumption is violated?** — How do conclusions change?
- **What if this relationship doesn't hold / is reversed?** — Impact on the model structure
- **Unmeasured variables** — For each critical path, what unmeasured variable could explain the relationship? (For causal DAGs: unmeasured confounders specifically. For conceptual models: hidden mediators or moderators.)
- **Robustness** — What's the minimum effect size / relationship strength that would survive this threat?
- **Boundary conditions** — Under what conditions does the model break down entirely?

#### 2.2 `plan-pipeline` + QA Checkpoints

**Applies to:** Projects with `computational-analysis` aspect.

**New section: "QA Checkpoints"**

For each pipeline stage:
- **Input assertions** — Expected row counts, value ranges, distributions, missingness rates, schema conformance
- **Inter-stage invariants** — No silent row drops, referential integrity, value conservation, cardinality checks
- **Sanity checks** — Known-answer tests (run on synthetic/known data), spot checks, summary statistics before/after
- **Failure mode** — What happens when an assertion fails? Hard stop vs. logged warning. Default: hard stop.

Added to the pipeline plan as first-class steps, not afterthoughts.

#### 2.3 `review-pipeline` + QA Coverage Audit

**Applies to:** Projects with `computational-analysis` aspect.

**New section: "QA Coverage"**

- Does every stage have input/output assertions?
- Are there intermediate checkpoints, or is it black-box end-to-end?
- What happens when an assertion fails?
- Is there a "dry run on small data" step before full execution?
- Are edge cases covered (empty inputs, missing values, extreme values)?

#### 2.4 `interpret-results` + Pre-registration Cross-check

**Applies to:** All projects, when a pre-registration document exists for the relevant hypothesis or inquiry.

**New section: "Pre-registration Cross-check"**

- **Match?** — Does the result match pre-registered expectations?
- **Divergence characterization** — If not: divergence in direction, magnitude, or kind?
- **QA verification** — Before updating beliefs: have pipeline QA checks passed? (links to QA output if available)
- **Confirmatory vs. exploratory** — Explicitly label which conclusions were pre-registered and which are post-hoc discoveries
- **Goalpost check** — Has the interpretation drifted from pre-registered decision criteria?

---

### Part 3: Coherence Cleanup

#### 3.1 Merge `research-gaps` into `next-steps`

**Current state:** Two commands that both analyze project state and recommend actions. `research-gaps` focuses on coverage gaps and saves a document. `next-steps` synthesizes progress and is terminal-only. Their boundaries are unclear.

**Change:** Merge into a single `next-steps` command that:
- Analyzes coverage gaps (concepts, evidence quality, contradictions, testability, data feasibility)
- Synthesizes recent progress and current state
- Recommends prioritized next actions
- Always saves output to `doc/meta/next-steps-<date>.md`

`research-gaps` becomes a deprecated alias for `next-steps`.

#### 3.2 Merge `build-dag` into `sketch-model`

**Current state:** Two commands for capturing structure — `sketch-model` (generic) and `build-dag` (causal-specialized). Unclear when to use which.

**Change:** `sketch-model` auto-detects causal intent from:
- `causal-modeling` aspect being active
- User language: "causal", "DAG", "confounders", "treatment effect"
- Existing causal inquiries in the project

When causal mode is active, `sketch-model` loads the `causal-dag` skill and follows the causal DAG workflow (identifying treatment, outcome, confounders, etc.). Otherwise, it follows the generic model-sketching workflow.

`build-dag` becomes a deprecated alias for `sketch-model`.

#### 3.3 Standardize Document Frontmatter

**Current state:** Hypotheses use sequential IDs (`h01`), searches use dates, questions use bare slugs. Cross-references are prose-only — no structured linking.

**Change:** All documents created or updated by Science commands include minimal YAML frontmatter:

```yaml
---
id: <type>-<slug>
type: topic | paper | hypothesis | question | method | dataset | search | discussion | interpretation | comparison | pre-registration | bias-audit
created: YYYY-MM-DD
updated: YYYY-MM-DD
related: [<id>, <id>, ...]
---
```

Rules:
- `id` is stable and unique within the project
- `related` contains IDs of documents this one references
- `validate.sh` can check for broken references (related ID that doesn't exist)
- Existing documents without frontmatter continue to work — commands add frontmatter when they create or update files
- Frontmatter is additive; it doesn't replace any existing document content

#### 3.4 Inquiry Status Lifecycle

**Current state:** `sketch-model` sets `sketch`, `specify-model` sets `specified`, `build-dag` doesn't set a status, `plan-pipeline` requires `specified`.

**Change:** Formalize statuses as descriptive breadcrumbs:

`sketch` → `specified` → `critiqued` → `planned` → `reviewed`

- `sketch-model` → sets `sketch`
- `specify-model` → sets `specified`
- `critique-approach` → sets `critiqued`
- `plan-pipeline` → sets `planned`
- `review-pipeline` → sets `reviewed`

**Non-linear:** Any transition is allowed. You can go back to `sketch` after `critiqued`. Commands warn if you skip a step (e.g., planning without validation) but don't block. The status records where the inquiry has _been_, not where it must _go_.

---

## Updated Command Table

After these changes, the full command set:

| Command | Category | Description |
|---|---|---|
| `status` | Orientation | Project overview — hypotheses, questions, activity, next steps |
| `create-project` | Setup | Scaffold a new research project |
| `import-project` | Setup | Add Science framework to an existing project |
| `research-topic` | Knowledge | Research and synthesize a topic |
| `research-paper` | Knowledge | Research and synthesize a paper |
| `search-literature` | Knowledge | Search OpenAlex/PubMed with relevance ranking |
| `find-datasets` | Knowledge | Discover and document candidate datasets |
| `add-hypothesis` | Reasoning | Develop and refine a hypothesis |
| `pre-register` | Reasoning | Formalize expectations before analysis |
| `compare-hypotheses` | Reasoning | Head-to-head evaluation of competing explanations |
| `bias-audit` | Reasoning | Systematic bias and threat-to-validity check |
| `discuss` | Reasoning | Structured critical discussion |
| `sketch-model` | Modeling | Sketch a model (auto-detects causal mode) |
| `specify-model` | Modeling | Formalize a model with evidence provenance |
| `critique-approach` | Modeling | Review model for problems + sensitivity analysis |
| `plan-pipeline` | Pipeline | Generate implementation plan (+ QA checkpoints) |
| `review-pipeline` | Pipeline | Audit plan against evidence rubric (+ QA coverage) |
| `interpret-results` | Synthesis | Interpret results (+ pre-registration cross-check) |
| `next-steps` | Synthesis | Gap analysis + progress synthesis + recommendations |
| `create-graph` | Knowledge Graph | Build knowledge graph from project documents |
| `update-graph` | Knowledge Graph | Incrementally update the graph |
| `tasks` | Management | Manage research and development tasks |

**Deprecated aliases:** `summarize-topic`, `summarize-paper`, `research-gaps`, `build-dag`

---

## Workflow Integration

The reasoning commands slot into the existing workflow:

```
1. create-project
2. add-hypothesis → pre-register
3. research-topic → search-literature → research-paper
4. compare-hypotheses (when 2+ hypotheses exist)
5. next-steps (replaces research-gaps + next-steps)
6. discuss
7. bias-audit
8. sketch-model → specify-model → critique-approach (now with sensitivity)
9. find-datasets
10. plan-pipeline (now with QA checkpoints)
11. review-pipeline (now with QA coverage)
12. [run analysis]
13. interpret-results (now with pre-registration cross-check)
14. create-graph / update-graph
15. iterate
```

Steps can be reordered, repeated, or skipped. The workflow is a guide, not a gate.

**Cross-cutting commands** (usable at any stage, not tied to a specific step):
- `tasks` — manage the task queue throughout
- `discuss` — stress-test any idea, hypothesis, or approach at any point
- `bias-audit` — check for blind spots whenever the project feels "too settled"
- `update-graph` — refresh the knowledge graph after any research round

#### Frontmatter ID mapping for existing documents

Existing hypothesis files use sequential IDs in filenames (e.g., `h01-circadian-gating.md`). When a command adds frontmatter to such a file, the `id` field preserves the existing convention: `id: hypothesis-h01-circadian-gating`. The filename remains the canonical identifier; the frontmatter `id` is derived from it. This avoids creating a parallel ID scheme.
