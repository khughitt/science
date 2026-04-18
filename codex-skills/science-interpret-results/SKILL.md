---
name: science-interpret-results
description: "Interpret analysis results and feed findings back into the research framework. Use when the user has pipeline output, notebook results, statistical summaries, or preliminary findings to evaluate against propositions and hypotheses and update project priorities. Also use when the user explicitly asks for `science-interpret-results` or references `/science:interpret-results`."
---

# Interpret Results

Converted from Claude command `/science:interpret-results`.

## Science Codex Command Preamble

Before executing any research command:

1. **Resolve project profile:** Read `science.yaml` and identify the project's `profile`.
   Use the canonical layout for that profile:
   - `research` → `doc/`, `specs/`, `tasks/`, `knowledge/`, `papers/`, `models/`, `data/`, `code/`
   - `software` → `doc/`, `specs/`, `tasks/`, `knowledge/`, plus native implementation roots such as `src/` and `tests/`
2. Load role prompt: `.ai/prompts/<role>.md` if present, else `references/role-prompts/<role>.md`.
3. Load the `research-methodology` and `scientific-writing` skills.
4. Read `specs/research-question.md` for project context when it exists.
5. **Load project aspects:** Read `aspects` from `science.yaml` (default: empty list).
   For each declared aspect, resolve the aspect file in this order:
   1. `aspects/<name>/<name>.md` — canonical Science aspects
   2. `.ai/aspects/<name>.md` — project-local aspect override or addition

   If neither path exists (the project declares an aspect that isn't shipped with
   Science and has no project-local definition), do not block: log a single line
   like `aspect "<name>" declared in science.yaml but no definition found —
   proceeding without it` and continue. Suggest the user either (a) drop the
   aspect from `science.yaml`, (b) author it under `.ai/aspects/<name>.md`, or
   (c) align the name with one shipped under `aspects/`.

   When executing command steps, incorporate the additional sections, guidance,
   and signal categories from loaded aspects. Aspect-contributed sections are
   whole sections inserted at the placement indicated in each aspect file.
6. **Check for missing aspects:** Scan for structural signals that suggest aspects
   the project could benefit from but hasn't declared:

   | Signal | Suggests |
   |---|---|
   | Files in `specs/hypotheses/` | `hypothesis-testing` |
   | Files in `models/` (`.dot`, `.json` DAG files) | `causal-modeling` |
   | Workflow files, notebooks, or benchmark scripts in `code/` | `computational-analysis` |
   | Package manifests (`pyproject.toml`, `package.json`, `Cargo.toml`) at project root with project source code (not just tool dependencies) | `software-development` |

   If a signal is detected and the corresponding aspect is not in the `aspects` list,
   briefly note it to the user before proceeding:
   > "This project has [signal] but the `[aspect]` aspect isn't enabled.
   > This would add [brief description of what the aspect contributes].
   > Want me to add it to `science.yaml`?"

   If the user agrees, add the aspect to `science.yaml` and load the aspect file
   before continuing. If they decline, proceed without it.

   Only check once per command invocation — do not re-prompt for the same aspect
   if the user has previously declined it in this session.
7. **Resolve templates:** When a command says "Read `.ai/templates/<name>.md`",
   check the project's `.ai/templates/` directory first. If not found, read from
   `templates/<name>.md`. If neither exists, warn the
   user and proceed without a template — the command's Writing section provides
   sufficient structure.
8. **Resolve science-tool invocation:** When a command says to run `science-tool`,
   prefer the project-local install path: `uv run science-tool <command>`.
   This assumes the root `pyproject.toml` includes `science-tool` as a dev
   dependency installed via `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.
   If that fails (no root `pyproject.toml` or science-tool not in dependencies),
   fall back to:
   `uv run --with <science-plugin-root>/science-tool science-tool <command>`

Interpret the results specified by the user input and update the project in a proposition/evidence-centric way.

In this project, results do not automatically prove or refute a hypothesis. They shift support, dispute, and uncertainty for specific propositions.

If no argument is provided, ask the user to describe their findings or point to a results file.

## Setup

Follow the Science Codex Command Preamble before executing this skill. Use the `research-assistant` role prompt.

Additionally:
1. Read `docs/proposition-and-evidence-model.md`.
2. Read `.ai/templates/interpretation.md` first; if not found, read `templates/interpretation.md`.
3. Read active hypotheses in `specs/hypotheses/`.
4. Read open questions in `doc/questions/`.
5. Read relevant prior interpretations in `doc/interpretations/`.
6. If an inquiry slug is involved, load it:

```bash
uv run science-tool inquiry show "<slug>" --format json
```

## Input

the user input may be:
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
  - the input is a `doc/discussions/*.md` file
  - the user describes observations or insights without pointing to data files
  - the input has no associated data quality characteristics (no sample counts, effect sizes, or controls)

Always note the mode at the top of the output when not in standard write mode.

### Cross-Referencing Prior Interpretations

When interpreting multiple tasks jointly or building on a prior interpretation, list which earlier interpretation documents this one extends or supersedes using the `prior_interpretations` frontmatter field.

- **Combined interpretations:** When interpreting 2+ tasks as a single arc, list any prior single-task interpretations that this combined document supersedes. The prior documents remain for provenance; the combined one is canonical for downstream reference.
- **Update mode:** When updating an existing interpretation with new evidence, reference the prior version's ID.

This creates a provenance chain across interpretation documents.

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
- Reference the pre-registration document (in `doc/meta/pre-registration-*.md`) and compare observed vs. expected range explicitly
- State whether the result survives scrutiny or needs additional verification

### 5. Update Proposition Support / Dispute

When graph updates are warranted, frame them as proposition updates:
- add a project proposition describing the result
- attach it as `cito:supports` or `cito:disputes` to the affected proposition
- note residual uncertainty, especially when evidence is single-source, weak, or contested
- classify the new evidence explicitly using the canonical evidence types above

Do not use hypothesis status changes as the primary output.
Hypothesis-level summaries can be updated later as a secondary reflection of underlying proposition changes.

After drafting the interpretation, run:

```bash
science-tool health --project-root . --format json
```

Call out any remaining:
- unsupported mechanistic narratives
- proxy-mediated propositions lacking `measurement_model`
- rival-model packets lacking discriminating predictions

### Structured Output

After analyzing results, create structured entities in addition to the prose document:

1. For each concrete empirical fact:
   `science-tool graph add observation "<description>" --data-source <data-package-ref> --metric <what> --value <value>`

2. For each interpretive proposition:
   `science-tool graph add proposition "<text>" --source <data-package-ref> --confidence <0-1>`

3. For each observation that bears on a proposition:
   `science-tool graph add evidence <observation-ref> <proposition-ref> --stance supports|disputes --strength strong|moderate|weak`

4. Bundle into a finding:
   `science-tool graph add finding "<summary>" --confidence moderate --proposition <ref> --observation <ref> --source <data-package-ref>`

5. Create the interpretation:
   `science-tool graph add interpretation "<summary>" --finding <ref> --context "<what prompted this>"`

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
science-tool graph project-summary --format json
science-tool graph question-summary --format json  # full by default; add --top to narrow
science-tool graph inquiry-summary --format json
science-tool graph dashboard-summary --format json
science-tool graph neighborhood-summary --format json
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

- **Dev mode:** follow `.ai/templates/interpretation-dev.md` first, then `templates/interpretation-dev.md`. Skip the empirical sections (Evidence Quality, Data Quality Checks, Proposition-Level Updates, Evidence vs. Open Questions) entirely — the dev template omits them on purpose.
- **All other modes (write / update / conceptual):** follow `.ai/templates/interpretation.md` first, then `templates/interpretation.md`.

If the project uses open questions rather than formal hypotheses, adapt section headers in the output document accordingly — e.g., "Question-Level Implications" instead of "Hypothesis-Level Implications". Evaluate against questions in `doc/questions/` rather than hypothesis files in `specs/hypotheses/`.
Save to `doc/interpretations/YYYY-MM-DD-<slug>.md`.

Populate frontmatter:
- `id`
- `related`
- `source_refs`
- `input`
- `created`
- `updated`

## After Writing

1. Update relevant hypothesis documents with new support/dispute and uncertainty notes.
Do not mechanically flip them to `supported` or `refuted`.
2. Add new questions to `doc/questions/` when needed.
3. Update tasks via `science-tool tasks`.
Write durable result interpretations under `doc/interpretations/`, and when the findings change the project-level narrative or current state substantially, summarize that in `doc/reports/` as well.
4. If graph updates were proposed, point the user to the exact proposition or evidence updates to make.
5. If the project still lacks proposition-backed evidence summaries, say that it appears partially migrated and that interpretation quality is constrained by that gap.
6. Suggest next steps:
   - `science-compare-hypotheses`
   - `science-discuss`
   - `science-add-hypothesis`
   - `science-pre-register`

## Process Reflection

Reflect on the **template** and **workflow** used above.

If you have feedback (friction, gaps, suggestions, or things that worked well),
report each item via:

```bash
science-tool feedback add \
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
