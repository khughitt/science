---
description: Interpret analysis results and feed findings back into the research framework. Use when the user has pipeline output or findings to evaluate against propositions/hypotheses and update project priorities.
---

# Interpret Results

Interpret the results specified by `$ARGUMENTS` and update the project in a proposition/evidence-centric way.

In this project, results do not automatically prove or refute a hypothesis. They shift support, dispute, and uncertainty for specific propositions.

If no argument is provided, ask the user to describe their findings or point to a results file.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `${CLAUDE_PLUGIN_ROOT}/docs/user-guide/epistemic-model.md`.
2. Read `${CLAUDE_PLUGIN_ROOT}/docs/user-guide/evidence-lines.md`.
3. Read `.ai/templates/interpretation.md` first; if not found, read `${CLAUDE_PLUGIN_ROOT}/templates/interpretation.md`.
4. Read active hypotheses in `entities/hypotheses/`.
5. Read open questions in `entities/questions/`.
6. Read relevant prior interpretations in `entities/interpretations/`.
7. If an inquiry slug is involved, load it:

```bash
uv run science inquiry show "<slug>" --format json
```

## Input

`$ARGUMENTS` may be:
- a path to a results file, notebook, or output directory
- a path to a `datapackage.json` in a result directory
- a prose description of findings
- an inquiry slug

If given a directory, scan for result files and summarize what is available.

- **Workflow-run manifest** — path to a `datapackage.json` in a result directory.
  The manifest provides entity cross-references, config snapshot, and resource
  listing. Load the manifest to identify which questions/hypotheses the run
  addresses, then interpret the results resources.

## Modes

- **Write mode:** no existing interpretation document yet
- **Update mode:** an interpretation already exists; update framework implications without rewriting the whole narrative
- **Dev mode:** the result is about tooling or workflow rather than substantive empirical evidence. Use the dedicated `templates/interpretation-dev.md` (see Writing below) — the empirical-mode sections are dead weight for infrastructure work.
- **Conceptual mode:** the input is a discussion document, synthesis, or free-form user observations — not empirical data, notebooks, or pipeline output. Auto-select this mode when:
  - the input is a `entities/discussions/*.md` file
  - the user describes observations or insights without pointing to data files
  - the input has no associated data quality characteristics (no sample counts, effect sizes, or controls)

Always note the mode at the top of the output when not in standard write mode.

### Cross-Referencing Prior Interpretations

When interpreting multiple tasks jointly or building on a prior interpretation,
list earlier interpretation documents in `prior_interpretations` as a narrative
breadcrumb. This field is not the machine-readable conclusion chain.

For needs-review resolution, use first-class graph relations:

- `sci:amends` when the new conclusion revises, narrows, qualifies, or extends
  an older conclusion without replacing it.
- `sci:supersedes` when the new conclusion replaces the older conclusion as the
  current canonical reading. In this case, also mark the old conclusion
  `status: superseded`.

Do not use `sci:supersedesClaim` for conclusion replacement. That predicate is
reserved for falsification records.

Example frontmatter on the new interpretation:

```yaml
relations:
  - predicate: "sci:amends"
    target: "interpretation:old"
```

or:

```yaml
relations:
  - predicate: "sci:supersedes"
    target: "interpretation:old"
```

### Needs-Review Resolution

When a result is being interpreted because an epistemic entity was flagged
`needs-review`, keep the review timestamp separate from the conclusion change:

1. Inspect the flagged entity, its `sci:triggeredBy` upstream sources, and nearby
   prior conclusions.
2. If standing is unchanged, run
   `science entity review <target-ref> --note "Reviewed against <source>; no standing change."`
3. If standing changes, author the new interpretation or finding, add
   `sci:amends` or `sci:supersedes`, and only then run
   `science entity review <target-ref> --note "Reconsidered; see interpretation:<new>."`

`<target-ref>` is the flagged entity, not the newly authored conclusion.
Freshness remains a review prompt; it does not mutate standing.

## Workflow

### 1. Summarize The Findings

Extract the main findings and classify each as:
- `strong`
- `suggestive`
- `null`
- `ambiguous`
- `methodological`
- `descriptive` — structural or qualitative findings from exploratory/visualization analyses where statistical testing is not applicable (e.g., UMAP cluster structure, k-mer landscape patterns). Distinct from `suggestive`: the finding is qualitative by nature, not merely weak.
- `conceptual` — (conceptual mode only) insights from discussion, synthesis, or reasoning that reframe understanding without new empirical evidence

Also identify the evidence type where possible:
- `literature_evidence`
- `empirical_data_evidence`
- `simulation_evidence`
- `benchmark_evidence`
- `expert_judgment`
- `negative_result`

Include effect sizes, uncertainty intervals, and sample counts where available.

**Conceptual mode adaptation:** Most findings will be `expert_judgment` or `literature_evidence`. Instead of effect sizes and sample counts, characterize each insight by:
- **Novelty:** does this reframe existing understanding, or confirm what was already believed?
- **Grounding:** is the insight anchored in specific prior evidence/literature, or is it speculative?
- **Actionability:** does it suggest concrete next steps or tests?

### 2. Map Findings To Propositions

For each relevant hypothesis or inquiry, ask:
- Which specific propositions are touched by these results?
- Does this result support, dispute, or leave each proposition unresolved?
- How much does it actually move belief?

When a result bundle mixes levels, split them explicitly:
- empirical regularity
- causal effect claim
- mechanistic narrative or structural interpretation

Prefer outputs like:
- “supports proposition P1 modestly”
- “disputes proposition P3”
- “leaves the hypothesis organizing idea intact but increases uncertainty in proposition P2”

Avoid outputs like:
- “the hypothesis is now proved”
- “this edge is validated”

### 3. Evaluate Against Open Questions

For each relevant open question:
- is it addressed, partially addressed, or unchanged?
- what constraints or new uncertainty does the result introduce?
- what sub-question becomes more important now?

### 4. Check Evidence Quality

**Conceptual mode:** Skip the empirical quality checks below. Instead, assess:
- **Reasoning quality:** Are the arguments logically sound? Are there hidden assumptions or circular reasoning?
- **Completeness:** Does the discussion consider alternative explanations or counterarguments?
- **Independence:** Is this a genuinely new perspective, or does it merely restate an existing proposition in different words?
- **Testability:** Does the insight suggest concrete predictions or experiments that could validate it?

Then proceed to Step 5.

**Empirical modes (write/update/dev):** Before updating beliefs, check:
- **Control uniqueness:** are controls distinct from test samples? No duplicate sequences, no shared samples across conditions
- **Dimensionality:** do embedding sizes, feature counts, and output shapes match expectations?
- **Sample counts:** do they match the experimental design? Spot-check against the data source
- **Data quality issues:** flag any anomalies discovered during interpretation as findings with signal strength `methodological`
- whether the result is confirmatory or exploratory
- whether the result is independent of prior supporting evidence or largely redundant
- whether it adds empirical support to a proposition that previously had only literature or simulation support

If the finding is fragile, say so explicitly.

Also ask:
- does this result rest on a proxy that needs `measurement_model` rather than prose-only caveats?
- is the evidence independent, or does it collapse into one `independence_group`?
- if the result adjudicates among alternatives, should it update a `rival_model_packet` and its `current_working_model`?

**Aggregator-circularity check.** If "external validation" comes from a literature-aggregating resource (Open Targets, ChEMBL, DrugBank, PharmGKB, DisGeNET, OMIM, etc.), treat the agreement as partly circular: the resource's evidence pool may already include the project's own findings or the same upstream studies. Mitigations:
- prefer per-datatype breakdowns (genetic, somatic, animal-model, drug, RNA) over combined overall scores
- check the resource's source-evidence list for direct citations of the analyses driving the project's finding
- when redundancy is unavoidable, downgrade the evidence weight and label it as `redundant-with-prior` rather than independent corroboration

**Suspiciously good results:** When results substantially exceed pre-registered upper bounds (observed >> expected), do not accept them uncritically. Before proceeding:
- Enumerate plausible inflators: confounds, data leakage, overfitting, control inadequacy
- Reference the pre-registration document (in `entities/pre-registrations/*.md`) and compare observed vs. expected range explicitly
- State whether the result survives scrutiny or needs additional verification
- For epistemic-target pre-regs, an out-of-range result is `disputes` evidence weighted by the pre-reg's commitment — it does not invalidate the hypothesis on its own.

### 4d. Pre-registration evaluation

For each pre-registration relevant to the current analysis, classify its target class and frame the comparison accordingly. Pre-registered evidence flows into the graph as a `bears_on` edge derived from the pre-reg's commitment targets to the relevant epistemic entities; this step structures the proposition updates that § 5 will emit.

Locate any pre-reg with the current analysis or its hypothesis/question in its `related` set:

```bash
science entity list --kind pre-registration --related <ref>
```

`science entity list --related <ref>` filters source-authored entities whose `related:` refs point to the current analysis, hypothesis, question, or other focus entity, resolving aliases where possible.

For each found pre-reg, read its `committed:` clause and classify each commitment target by the registered `EntityClass` of its kind (or by `commits_to:` when populated):

- **Operational pre-regs.** Did the analysis run as committed? If not, flag the deviation and confirm an `amendments:` entry exists. Operational pre-regs remain gating; this is unchanged from prior practice.
- **Epistemic pre-regs.** Compare the observed result to the pre-registered prediction and frame the comparison as a *weighted update*, not a verdict. Example framing:

  > "Pre-reg `pre-registration:h07-beta-arbitration` predicted effect > 0.3 for support of H07. Observed: 0.18. This is a `disputes` evidence edge into H07, weighted strong (per pre-reg commitment level)."

  Avoid framings like "Pre-reg predicted >0.3, observed 0.18 — H07 is rejected per the pre-registered criterion." That is the kill-switch framing the recast deliberately drops for epistemic targets.

- **Pre-canonical pre-regs (hypothesis-in-body-only).** Some older pre-regs reference hypotheses inline in their body prose (e.g., "H1 (primary, confirmatory)") but do not carry the corresponding `hypothesis:` ref in `related:`. The auto-derivation rule produces no `bears_on` edge for body-only hypotheses. When interpreting:

  1. Read the pre-reg's body for inline hypothesis labels and identify the corresponding `hypothesis:` entity if it exists.
  2. If the entity exists, author a durable proposition and evidence line, then rebuild:

     ```bash
     science propositions create "<observed result proposition>" \
       --source-ref <dataset-or-workflow-run-ref> \
       --related pre-registration:<slug> \
       --id proposition:<slug>

     science evidence-lines create "<short evidence title>" \
       --target proposition:<slug> \
       --stance supports \
       --source <dataset-or-workflow-run-ref> \
       --evidence-type empirical_data \
       --strength strong \
       --related hypothesis:<target-id> \
       --related pre-registration:<slug>

     science graph build
     ```

     Use `--stance disputes` when the result contradicts the target. If the
     project needs an explicit `sci:preRegisteredIn` triple rather than a
     navigational `related:` link, author that relation in
     `knowledge/sources/local/relations.yaml` and rebuild.

  3. If no formal `hypothesis:` entity exists yet, flag this in the interpretation document and recommend the project promote it to a formal entity. Project-side cleanup is the resolution path; the recast cannot fully derive `bears_on` for body-only hypotheses.

### 5. Update Proposition Support / Dispute

When graph updates are warranted, frame them as proposition updates:
- add a project proposition describing the result
- attach it as `cito:supports` or `cito:disputes` to the affected proposition
- note residual uncertainty, especially when evidence is single-source, weak, or contested
- classify the new evidence explicitly using the canonical evidence types above
- **group by cohort, not by workflow.** When a follow-up analysis (different workflow) reuses the
  *same cohort / rows* as an existing evidence line, the new `shared-source` line must reuse the
  **same `independence_group`** as that cohort's existing lines — independence groups are
  cohort-level, not workflow-level. Minting a per-workflow group name (e.g. `swan` alongside an
  existing `swan-stage-age`) makes the aggregator count two same-cohort lines as independent and
  **over-promotes** the proposition. Setting `--independence shared-source` alone does **not** prevent
  the over-count; the grouping is what does.
- when the proposition is grounded in a pre-registered analysis, record the
  pre-registration in source metadata (`related:` / `source_refs:` on the
  proposition or evidence line). If downstream graph consumers require
  `sci:preRegisteredIn`, author that relation in
  `knowledge/sources/local/relations.yaml` and rebuild with
  `science graph build`.

Do not use hypothesis status changes as the primary output.
Hypothesis-level summaries can be updated later as a secondary reflection of underlying proposition changes.

After drafting the interpretation, run:

```bash
science health --project-root . --format json
```

Call out any remaining:
- unsupported mechanistic narratives
- proxy-mediated propositions lacking `measurement_model`
- rival-model packets lacking discriminating predictions

Then verify the update did not silently over-promote: confirm `belief.fragile-single-line` did **not
newly fire** for the proposition you just touched. If it did, the most likely cause is a same-cohort
line placed in its own `independence_group` (see the cohort-grouping rule above) — fix the grouping
rather than the threshold.

Clarify the single-line case before changing the source:
- **Authoring a new single-line proposition:** if the result genuinely has only one weak,
  same-cohort, or otherwise non-independent support line, keep the proposition fragile and do not
  suppress `belief.fragile-single-line`. The warning is the correct representation of current
  support, not a tooling failure.
- **Touching an existing proposition:** `belief.fragile-single-line` should newly fire only when this
  run made an existing proposition newly single-line, for example by replacing multiple independent
  lines with one line or by splitting lines into the same `independence_group`. If the warning
  already existed before this interpretation and remains true, report it as residual risk rather
  than treating this run as the cause.

### Structured Output

After analyzing results, create structured entities in addition to the prose document.

**First, route structured output through source-authored files.** `science graph
build` rematerializes `knowledge/graph.trig` deterministically from markdown
sources; it never reads the existing `graph.trig` back. The old graph writer
surfaces for observation/proposition/evidence/finding/interpretation are
retired. For anything that must survive a rebuild, author it in a source the
build reads:

  - **Proposition** → `science propositions create "<title>"` (durable source-authored entity).
    For a **proxy-mediated** proposition, set these in the frontmatter so it validates on the
    first `science graph build` (otherwise `science health` fails *after* build with "Proxy-mediated
    proposition lacks measurement metadata"):
    - `proxy_directness:` — enum `direct | indirect | derived` (**not** `proxy`).
    - `measurement_model:` — a mapping with `observed_entity` (required) plus optional
      `latent_construct`, `measurement_relation`, `rationale`, `known_failure_modes` (list),
      and `substitutable_with` (list).
  - **Observation** → author `entities/observations/<slug>.md` with
    `science entity create observation "<title>"` when a standalone empirical
    datum needs an owner; otherwise anchor it inside a proposition, finding, or
    interpretation source file.
  - **Evidence with stance / strength / independence** → author an **evidence-line** entity under
    `entities/evidence-lines/*.md` (kind `evidence-line`), which the build reads and materializes; or
    express the relation inside the proposition/finding/interpretation source file.
  - **Interpretation / finding** → `science interpretations create` (step 5 below) produces a durable
    source document. Use `science entity create finding "<title>"` or edit
    `entities/findings/<slug>.md` for durable finding owners.

Use the source-authoring recipes below, then run `science graph build`.

1. For each concrete empirical fact:
   `science entity create observation "<description>" --id observation:<slug>`

2. For each interpretive proposition:
   `science propositions create "<text>" --source-ref <dataset-or-workflow-run-ref>`

3. For each observation that bears on a proposition:
   `science evidence-lines create "<short evidence title>" --target <proposition-ref> --stance supports|disputes --source <dataset-or-workflow-run-ref> --evidence-type empirical_data --strength strong|moderate|weak`

4. Bundle into a finding:
   `science entity create finding "<summary>" --related <proposition-ref> --source-ref <dataset-or-workflow-run-ref>`

5. Create the interpretation as a source-authored entity:
   `science interpretations create "<summary>" --input <dataset-or-workflow-run-ref> --related <finding-or-proposition-ref>`

   This places the file under `entities/interpretations/<today>-<slug>.md` with canonical frontmatter and runs prospective validation.

### 6. Surface New Questions

Identify new questions raised by the results.

For each:
- priority
- type: empirical / methodological / theoretical
- what evidence would most efficiently reduce uncertainty

### 7. Update Priorities

Propose changes to the task queue:
- new tasks to add
- propositions needing more empirical evidence
- contested areas needing direct comparison or replication
- weakly supported regions of the graph worth prioritizing
- high-uncertainty neighborhoods that look likely to pay off with targeted follow-up

When `knowledge/graph.trig` exists, prefer using:

```bash
science graph project-summary --format json
science graph question-summary --format json  # full by default; add --top to narrow
science graph inquiry-summary --format json
science graph dashboard-summary --format json
science graph neighborhood-summary --format json
```

to anchor the prioritization section, especially for:
- the overall research-project rollup
- high-priority questions
- high-priority inquiries
- propositions lacking empirical support
- single-source propositions
- contested local clusters

For `software` projects, skip `project-summary` for now and start at `question-summary` / `inquiry-summary`.

Use them in this order:
1. `project-summary` to see the current research-level rollup, when the project is `research`
2. `question-summary` for the full question rollup, with `--top` as optional narrowing
3. `inquiry-summary` to find which threads deserve attention
4. `dashboard-summary` and `neighborhood-summary` to identify the exact propositions and clusters driving that priority

## Writing

Pick the template that matches the mode:

- **Dev mode:** follow `.ai/templates/interpretation-dev.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/interpretation-dev.md`. Skip the empirical sections (Evidence Quality, Data Quality Checks, Proposition-Level Updates, Evidence vs. Open Questions) entirely — the dev template omits them on purpose.
- **All other modes (write / update / conceptual):** follow `.ai/templates/interpretation.md` first, then `${CLAUDE_PLUGIN_ROOT}/templates/interpretation.md`.

If the project uses open questions rather than formal hypotheses, adapt section headers in the output document accordingly — e.g., "Question-Level Implications" instead of "Hypothesis-Level Implications". Evaluate against questions in `entities/questions/` rather than hypothesis files in `entities/hypotheses/`.

Create the interpretation file with `science interpretations create`:

```bash
uv run science interpretations create "<short title>" \
  --input <dataset-or-workflow-run-ref> \
  --related <hypothesis:hNN-...|question:qNN-...>
```

The tool builds the canonical `interpretation:<today>-<slug>` ID, places the file under `entities/interpretations/`, writes canonical frontmatter (`id`, `kind`, `title`, `status`, `related`, `source_refs`, `created`, `updated`), and runs prospective validation. `--input` maps to `source_refs`; `--related` is repeatable. After creation, open the file and fill the body using the template — preserve the frontmatter the tool produced. Add custom fields (e.g. `input` if the project schema requires it) by editing the frontmatter directly.

## After Writing

1. Update relevant hypothesis documents with new support/dispute and uncertainty notes. For metadata changes use `science entity edit <ref> --status ...`; for body changes edit the file in place. Do not mechanically flip statuses to `supported` or `rejected`.
2. **New questions surfaced:** create them with `science questions create "<text>" [--related <ref>] [--source-ref <ref>]`. To attach the new question to the interpretation, run `science entity edit <interpretation-ref> --related <question-ref>`.
3. Update tasks via `science tasks`.
Write durable result interpretations under `entities/interpretations/`, and when the findings change the project-level narrative or current state substantially, summarize that in `entities/reports/` as well.
4. If graph updates were proposed, point the user to the exact proposition or evidence updates to make.
5. If the project still lacks proposition-backed evidence summaries, say that it appears partially migrated and that interpretation quality is constrained by that gap.
6. Suggest next steps:
   - `/science:compare-hypotheses`
   - `/science:discuss`
   - `/science:add-hypothesis`
   - `/science:pre-register`

## When results surprise you

If a result contradicted a pre-registered expectation, a run failed, or an
assumption turned out to be violated, consider `/science:post-mortem` to capture
a generalized methodology lesson — what would have surfaced the issue sooner —
as feedback.

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science feedback add \
  --target "command:interpret-results" \
  --category <friction|gap|guidance|suggestion|positive> \
  --summary "<one-line summary>" \
  --detail "<optional prose>"
```

Guidelines:
- One entry per distinct issue (not one big dump)
- If the same issue has occurred before, the tool will detect it and
  increment recurrence automatically
- Skip if everything worked smoothly — no feedback is valid feedback
- For template-specific issues, use `--target "template:<name>"` instead
