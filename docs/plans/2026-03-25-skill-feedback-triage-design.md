# Skill Feedback Triage — Design Spec

**Date:** 2026-03-25
**Status:** Approved
**Scope:** Address all unresolved skill feedback from three science projects (3d-attention-bias, seq-feats, natural-systems) since the last triage on 2026-03-15.

## Context

Three projects maintain `doc/meta/skill-feedback.md` files that log friction, missing capture, and improvement suggestions after each skill invocation. All three were last triaged on 2026-03-15. This spec addresses ~30 unresolved items accumulated since then (plus a few deferred items from earlier), organized by the file they touch.

## Approach

Command-first: group all changes by the file they modify, work through each file once. This minimizes re-reads and ensures internal consistency within each command/template pair.

---

## 1. interpret-results (command + template) — 9 changes

### Command: `commands/interpret-results.md`

**1a. Add "descriptive" signal strength category (Step 1)**

Add `descriptive` to the signal classification list. Current list: strong, suggestive, null, ambiguous, methodological. The new category covers exploratory/visualization results where statistical testing isn't applicable (e.g., UMAP structure, k-mer landscape patterns). The distinction from "suggestive" is that "descriptive" doesn't imply weak evidence — it means the finding is structural/qualitative by nature.

*Source: seq-feats 3/16, natural-systems 3/10*

**1b. Expand Step 4 with specific "Data Quality Checks"**

Step 4 ("Check Evidence Quality") already mentions "data quality, sample counts, control integrity" as general bullets. Expand these with a specific prompted checklist. Do not create a separate step — augment the existing Step 4 bullets with concrete checks:
- Verify control uniqueness (no duplicate sequences, no shared samples across conditions)
- Confirm dimensionality matches expectations (embedding sizes, feature counts)
- Spot-check sample counts against experimental design
- Flag any data quality issues discovered as first-class findings with signal strength "methodological"

Replace the existing terse bullets ("data quality", "sample counts", "control integrity") with these more specific versions to avoid redundancy.

Two data bugs were discovered at interpretation time across projects (CGI T3 control issue, TMR T2/T3 identical sequences). This makes the check systematic.

*Source: seq-feats 3/12, 3/14*

**1c. Add "Suspiciously Good" check (also in Step 4, as a new paragraph after the quality checklist)**

Add guidance at the end of Step 4: when results substantially exceed pre-registered upper bounds (e.g., observed >> expected), prompt for a "Suspiciously Good" analysis before accepting:
- Enumerate plausible inflators (confounds, data leakage, overfitting)
- Reference the pre-registration document if one exists
- Compare observed vs. pre-registered expected range explicitly

*Source: seq-feats 3/14*

**1d. Adaptive terminology guidance (Writing section + template)**

Add a note in the Writing section (not Step 2) since this affects the output document headers, not the analysis workflow: "If the project uses open questions rather than formal hypotheses, adapt section headers accordingly (e.g., 'Question-Level Implications' instead of 'Hypothesis-Level Implications'). Evaluate against questions in `doc/questions/` rather than hypothesis files in `specs/hypotheses/`."

Also update the template's `## Hypothesis-Level Implications` comment to note: "Rename this section to 'Question-Level Implications' if the project uses open questions rather than formal hypotheses."

*Source: natural-systems, 13+ occurrences of relabeling "Hypothesis Evaluation" as "Question Evaluation"*

**1e. Prior Findings cross-reference (new subsection after Modes)**

Add a new `### Cross-Referencing Prior Interpretations` subsection after the Modes list. This guidance applies across modes but is most relevant in Update mode and combined multi-task interpretations:

"When interpreting multiple tasks jointly or building on a prior interpretation, list which earlier interpretation documents this one extends or supersedes using the `prior_interpretations` frontmatter field (see 1i). This creates a provenance chain across interpretation documents."

*Source: natural-systems 3/23*

**1f. Superseded interpretation guidance (same new subsection as 1e)**

Add within the same `### Cross-Referencing Prior Interpretations` subsection:

"When a combined multi-task interpretation supersedes a single-task one, note which prior interpretation is superseded in the `prior_interpretations` frontmatter field (see 1i). The prior document remains for provenance but the combined one is canonical for downstream reference."

*Source: natural-systems 3/23*

### Template: `templates/interpretation.md`

**1g. Add "Data Quality Checks" section**

Add between Evidence Quality and Claim-Level Updates:

```markdown
## Data Quality Checks

<!-- Any data quality concerns discovered during interpretation?
- Control uniqueness: are controls distinct from test samples?
- Sample counts: do they match the experimental design?
- Dimensionality: do embedding sizes / feature counts match expectations?
- Unexpected duplicates or anomalies?

If no issues found, note "No data quality concerns identified."
Flag any issues as findings with signal strength "methodological". -->
```

*Source: seq-feats 3/12, 3/14*

**1h. Add "User Questions" section**

Add after New Questions Raised:

```markdown
## User Questions

<!-- Questions the user raised during interpretation, with answers.
These are often the most insightful prompts — record them as part of the
interpretation rather than losing them to conversation history.
Omit if no user questions were raised. -->
```

*Source: seq-feats 3/15*

**1i. Add `prior_interpretations` frontmatter field**

Add to frontmatter (this is the mechanism referenced by items 1e and 1f above):

```yaml
prior_interpretations: []  # optional: interpretation IDs this document extends or supersedes
```

*Source: natural-systems 3/23*

### Items considered but not added

- **Methodological Artifacts section:** Belongs in Limitations & Residual Uncertainty (already exists). Adding a comment prompt to mention analysis-level artifacts there is sufficient.
- **Connections to Papers section:** Belongs contextually in Evidence Quality or Claim-Level Updates. Not frequent enough to warrant a dedicated section.
- **Signal Decomposition section:** Deferred as lower priority per seq-feats triage note. Better handled by random-init baseline workflow than by a mandatory template section.

---

## 2. plan-pipeline (command) — 5 changes

### Command: `commands/plan-pipeline.md`

**2a. "Tech Stack" → "New Dependencies"**

In Step 2 (identify computational requirements), replace guidance about listing the full tech stack with: "List new dependencies needed (libraries, tools, data sources not already in the project), not the full existing stack." This focuses the section on what's actionable.

*Source: seq-feats 3/15, 3/19 (2 occurrences)*

**2b. "Changes to Existing Code" section (Step 4, conditional)**

For Task mode / "extend existing workflow" plans, add a section to the plan document: "Which existing files are modified and why? What's the diff from the current working pipeline?" Conditional: include when the plan extends an existing pipeline rather than building from scratch.

*Source: seq-feats 3/19*

**2c. Top-level "Decision Criteria" section (Step 4, conditional)**

For research exploration plans, add: "What would change our mind about pursuing this? What result at what stage would make us stop or pivot?" Distinct from per-task validation criteria — this is the overall go/no-go for the whole plan. Conditional: include for exploratory/research plans, omit for straightforward implementation plans.

*Source: seq-feats 3/15*

**2d. Tool-specific section (opt-in)**

Soften the current rule from "MUST NOT embed tool-specific logic" to: "By default, keep the plan tool-agnostic and reference skills instead. However, when the user explicitly requests a specific orchestration tool (Snakemake, Nextflow, Make, etc.), include a tool-specific section with the workflow definition. The rest of the plan should remain tool-agnostic."

Update both locations where this rule appears: the Rules list bullet and the Important Notes section later in the file.

*Source: natural-systems 3/22*

**2e. "Reusable Infrastructure" flag (Step 4)**

Add guidance: "If any task produces infrastructure (tools, indices, data pipelines) that has value beyond this specific analysis, flag it with a `reusable: true` note and briefly describe the broader applicability." Lightweight — just a flag per task, not a whole section.

*Source: seq-feats 3/17*

---

## 3. research-paper (command + template) — 4 changes

### Command: `commands/research-paper.md`

**3a. Paywall fallback in Source Strategy**

Under the "If given a URL" section, add fallback guidance: "If the URL returns a paywall, 403, or redirect loop: fall back to DOI resolution, then PubMed/preprint search, then press coverage, then GitHub README/repo. Do not abandon the paper — most paywalled papers have accessible metadata through alternative channels."

*Source: seq-feats 3/20*

**3b. Cross-paper synthesis step**

Add a new section after "After Writing" for batch processing: "When processing multiple papers in a single session, after all individual summaries are written, produce a brief cross-paper synthesis document at `doc/papers/synthesis-YYYY-MM-DD-<theme>.md` that identifies: shared themes, tensions between papers, and combined implications for the project. This only applies when 2+ papers are processed together and share a thematic connection."

*Source: natural-systems 3/21*

### Template: `templates/paper-summary.md`

**3c. "Model / Tool Availability" section**

Add after Limitations:

```markdown
## Model / Tool Availability

<!-- If the paper describes a model, tool, or dataset intended for reuse:
- Available checkpoints / versions
- Hardware requirements
- License
- Quantization options (if applicable)
- Access restrictions

Omit for papers that don't release artifacts. -->
```

*Source: seq-feats 3/20*

**3d. "Project Framework Mapping" section**

Add after Relevance:

```markdown
## Project Framework Mapping

<!-- If the project has an existing ontology, schema, or classification framework,
map the paper's concepts to the project's vocabulary:

| Paper Concept | Project Concept | Notes |
|---|---|---|
| <their term> | <our term> | <correspondence notes> |

Omit if no structured framework exists to map against. -->
```

*Source: natural-systems 3/19*

---

## 4. next-steps (command) — 2 changes

### Command: `commands/next-steps.md`

**4a. "Status Transitions" (expand section 3b)**

Rename "Newly Unblocked" to "Status Transitions" and expand to cover three directions:
- **Newly unblocked:** tasks that were blocked but are now actionable (existing)
- **Newly blocked:** tasks that lost a dependency or had assumptions invalidated
- **Newly irrelevant:** tasks superseded by results or no longer decision-relevant

This captures pruning opportunities alongside forward momentum.

Also update the writing template example later in the same file (the `## Newly Unblocked` line in the output format section) to `## Status Transitions` to match.

*Source: 3d-attention-bias 3/19*

**4b. "Design Constraints" note (section 4)**

Add guidance in Suggested Next Steps: "If the user has provided actionable design feedback during the session that doesn't fit the task/question/hypothesis taxonomy (e.g., page density preferences, API constraints, performance requirements), capture it in a 'Design Constraints' bullet under Recommended Next Actions with a note to record it in project memory or a design doc."

*Source: natural-systems 3/18*

---

## 5. pre-register (command) — 2 changes

### Command: `commands/pre-register.md`

**5a. Pilot-specific prompt (section 4)**

Add to "Plan for Null Results": "If this is a pilot experiment (1-2 seeds, small N, exploratory scope): explicitly state what this pilot CAN and CANNOT establish. A pilot can suggest directions and calibrate effect sizes but cannot confirm or refute a hypothesis. Frame decision criteria accordingly — a pilot's null result means 'insufficient signal to justify scaling up', not 'hypothesis is wrong'."

*Source: 3d-attention-bias 3/16*

**5b. "Sampling Strategy Rationale" (section 5)**

After the confirmatory/exploratory split, add an optional sub-section: "If the experimental design involves non-obvious sampling decisions (stratified sampling, subsampling from a larger population, context selection), document the rationale and trade-offs. What was chosen, what was the alternative, and why?" Conditional — omit when sampling is straightforward.

*Source: seq-feats 3/17*

---

## 6. discuss (command + template) — 2 changes

### Command: `commands/discuss.md`

**6a. "Actionable Recommendations" guidance (After Discussion section)**

Add: "If the discussion produces a concrete, low-cost design change or implementation recommendation (something testable in under an hour), flag it in the Prioritized Follow-Ups table with an `[actionable now]` tag. Offer to implement it immediately rather than creating a task for later."

*Source: natural-systems 3/22, 3/23*

### Template: `templates/discussion.md`

**6b. Add `[actionable now]` example row**

Update the Prioritized Follow-Ups table example:

```markdown
| Priority | Action | Why now | Dependencies |
|---|---|---|---|
| P1 | <action> | <rationale> | <deps> |
| P1 [actionable now] | <low-cost change> | <can verify immediately> | none |
```

*Source: natural-systems 3/22, 3/23*

---

## 7. bias-audit (command) — 1 change

### Command: `commands/bias-audit.md`

**7a. Confound Severity Matrix**

In the confounding assessment section, add: "For each identified confound, assess severity (HIGH/MED/LOW) and tractability (EASY/HARD/INFEASIBLE). Present as a table:

```markdown
| Confound | Severity | Tractability | Recommended Action |
|---|---|---|---|
| <confound> | HIGH/MED/LOW | EASY/HARD/INFEASIBLE | <action or 'acknowledge as limitation'> |
```

HIGH severity + EASY should be addressed before running experiments. MED severity + INFEASIBLE becomes a stated limitation."

*Source: seq-feats 3/12*

---

## 8. review-pipeline (command) — 1 change

### Command: `commands/review-pipeline.md`

**8a. Conditional rubric dimensions**

Add guidance: "When reviewing a sub-plan or extension of an already-reviewed pipeline, dimensions 1 (Evidence Coverage) and 7 (Scope Check) may be marked 'N/A — inherited from parent plan' if the parent plan has already passed review on these dimensions. Reference the parent plan's review document. Focus review effort on dimensions specific to the sub-plan: validation criteria, assumption audit, integration boundaries."

*Source: seq-feats 3/17*

---

## Implementation Order

1. `commands/interpret-results.md` + `templates/interpretation.md` (9 changes)
2. `commands/plan-pipeline.md` (5 changes)
3. `commands/research-paper.md` + `templates/paper-summary.md` (4 changes)
4. `commands/next-steps.md` (2 changes)
5. `commands/pre-register.md` (2 changes)
6. `commands/discuss.md` + `templates/discussion.md` (2 changes)
7. `commands/bias-audit.md` (1 change)
8. `commands/review-pipeline.md` (1 change)

After all changes: update the `Last reviewed` date in all three `skill-feedback.md` files to 2026-03-25.

## Files Modified

| File | Action |
|---|---|
| `commands/interpret-results.md` | Edit (6 changes) |
| `templates/interpretation.md` | Edit (3 changes) |
| `commands/plan-pipeline.md` | Edit (5 changes) |
| `commands/research-paper.md` | Edit (2 changes) |
| `templates/paper-summary.md` | Edit (2 changes) |
| `commands/next-steps.md` | Edit (2 changes) |
| `commands/pre-register.md` | Edit (2 changes) |
| `commands/discuss.md` | Edit (1 change) |
| `templates/discussion.md` | Edit (1 change) |
| `commands/bias-audit.md` | Edit (1 change) |
| `commands/review-pipeline.md` | Edit (1 change) |
