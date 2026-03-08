# Science UX Improvements

> **Status: COMPLETE** — All five improvements implemented 2026-03-07.

Five improvements to make the science tool more intuitive and effective.
Each section sketches the problem, proposed solution, and key design decisions.

### Dependencies between improvements

These five changes are not fully independent:

- **#4 (streamline preambles) and #2 (consolidate docs)** are coupled — preambles reference file paths that change with consolidation. Do #2 first, then #4 (or together).
- **#1 (status)** should reflect the final file structure from #2.
- **#5 (refs check)** validates paths from #2's new layout.
- **#3 (interpret-results)** is additive and can proceed independently.

---

## 1. Project Status Command (`/science:status`) — DONE

### Problem

Every session starts cold.
An agent or returning human has to manually read `RESEARCH_PLAN.md`, `doc/08-open-questions.md`, `specs/hypotheses/`, graph stats, and recent git history to figure out where things stand.
There's no single entry point that synthesizes project state.

### Proposed solution

A `/science:status` command that produces a curated orientation covering:

1. **Project identity** — name, research question, scope (from `science.yaml` and `specs/research-question.md`)
2. **Key ideas** — active hypotheses with status, grouped by theme
3. **Open questions & gaps** — top 3-5 highest-priority items from `doc/08-open-questions.md`
4. **Recent activity** — last 5-10 git commits summarized by type (research, hypothesis, discussion, pipeline)
5. **Staleness warnings** — files not updated in >14 days, graph out of sync with docs
6. **Next steps** — current priorities from `RESEARCH_PLAN.md`, with blockers noted
7. **Broken references** — summary from `refs check` (#5), if available
8. **Knowledge graph core** — a small visual map of the ~5-10 most central entities and their relations

### Knowledge graph core visualization

When `knowledge/graph.trig` exists:

- Extract entities by semantic centrality: those connected to the research question, treatment/outcome nodes, and hypothesis-linked entities — not just highest degree (which would surface generic nodes like `rdf:type`)
- Include edges between them, prioritizing causal (`scic:causes`) and evidence (`cito:supports`, `cito:disputes`) edges over metadata
- Render as a Mermaid diagram in the output (renders well in markdown viewers and IDEs)
- For terminal-only contexts, fall back to a compact text list: `A --causes--> B`, `C --supports--> D`
- This serves as a "visual table of contents" — the researcher can see the core conceptual structure at a glance

When no graph exists, skip this section with a note suggesting `/science:create-graph`.

### Output

- Print to terminal (not saved to file — this is ephemeral orientation, not a document)
- Optionally save a snapshot to `doc/meta/status-snapshot-YYYY-MM-DD.md` if `--save` flag is passed
- Keep total output under ~100 lines — this is a summary, not an audit
- Data sources: file system inventory for document counts, graph for entity stats and core viz, git log for recent activity

---

## 2. Consolidate Notes and Summaries — DONE

### Problem

`research-paper` creates two artifacts for the same paper:
- `papers/summaries/AuthorYear-short-title.md` (detailed, ~300-800 words)
- `notes/articles/<citekey>.md` (compact, structured metadata + short summary)

Similarly, `research-topic` creates:
- `doc/background/NN-topic-name.md` (detailed background document)
- `notes/topics/<topic-slug>.md` (compact note)

The relationship between the two layers is implicit.
Both capture summary, relevance, and follow-up — at different granularities.
Commands create both, meaning double maintenance and ambiguity about which to consult.

Additionally, monolithic files like `doc/07-hypotheses.md` and `doc/08-open-questions.md` duplicate content that lives in `specs/hypotheses/` and `doc/questions/`.
These index files become stale when the source-of-truth files are updated directly.

### Proposed solution

Merge into a single document per entity, living under `doc/`:

#### Papers

- **Single location:** `doc/papers/<citekey>.md`
- **Structure:** Keep the detailed paper-summary template as the canonical format
- Add the structured YAML frontmatter from the article-note template (tags, ontology_terms, datasets, source_refs, related)
- The frontmatter serves the role that the compact note previously filled — machine-readable metadata for cross-referencing and indexing

#### Topics

- **Single location:** `doc/topics/<topic-slug>.md`
- **Structure:** Keep the detailed background-topic template as the canonical format
- Add structured YAML frontmatter from the topic-note template
- Note: "topics" is more neutral than "background" — a topic doc can cover foundational literature, emerging methods, or domain context

#### Questions, Methods, Datasets

- These currently only exist as notes, so no merge needed
- Move to `doc/questions/`, `doc/methods/`, `doc/datasets/` for consistency

#### Hypotheses

- `specs/hypotheses/hNN-*.md` remains the source of truth (these are specs, not docs)
- `doc/07-hypotheses.md` becomes a generated index, not manually maintained — or is replaced by `doc/index.md`

#### Monolithic index files

- `doc/07-hypotheses.md` and `doc/08-open-questions.md` become generated views, not hand-edited files
- A `science-tool docs index` subcommand (or part of `status`) could regenerate them from frontmatter
- Alternatively, drop them in favor of a single `doc/index.md` that lists all entities by type

#### What this replaces

| Before | After |
|---|---|
| `papers/summaries/AuthorYear.md` | `doc/papers/<citekey>.md` |
| `notes/articles/<citekey>.md` | (merged into above) |
| `doc/background/NN-topic.md` | `doc/topics/<topic-slug>.md` |
| `notes/topics/<slug>.md` | (merged into above) |
| `notes/questions/<slug>.md` | `doc/questions/<slug>.md` |
| `notes/methods/<slug>.md` | `doc/methods/<slug>.md` |
| `notes/datasets/<slug>.md` | `doc/datasets/<slug>.md` |
| `doc/07-hypotheses.md` | generated index or `doc/index.md` |
| `doc/08-open-questions.md` | `doc/questions/` + generated index |

#### Index

- `doc/index.md` replaces both `notes/index.md` and the numbered doc files
- Generated from frontmatter by `science-tool docs index` or maintained manually
- Grouped by type: topics, papers, hypotheses, questions, methods, datasets

### Compatibility aliases

`/science:summarize-topic` and `/science:summarize-paper` currently exist as aliases.
With the consolidation, deprecate them — their existence adds "which one do I use?" confusion.
Keep the command files for one release cycle with a deprecation notice pointing to the canonical commands.

### Migration path

- New projects get the new structure from `create-project`
- Existing projects: provide a migration script (`science-tool docs migrate`) that:
  1. Moves files to new locations
  2. Merges note frontmatter into summary docs
  3. Generates `doc/index.md`
  4. Reports what was moved and any conflicts
- Commands that reference old paths need updating: `research-topic`, `research-paper`, `search-literature`, `add-hypothesis`, `research-gaps`

### Design decisions to resolve

- Drop sequential numbering for topics (`NN-topic-name.md` → `<topic-slug>.md`)?
  Recommendation: yes. Slugs are more stable and meaningful. Ordering can come from frontmatter or the index.
- Keep `papers/references.bib` where it is, or move to `doc/papers/references.bib`?
  Recommendation: keep at `papers/references.bib` — BibTeX tools expect it there.
- What happens to `papers/` directory?
  Recommendation: `papers/references.bib` stays. `papers/pdfs/` stays (if used). `papers/summaries/` is replaced by `doc/papers/`. `papers/searches/` moves to `doc/searches/`.
- What happens to `doc/01-overview.md` through `doc/10-research-gaps.md`?
  Recommendation: keep `doc/01-overview.md` and `doc/04-approach.md` as standalone project-level docs (they aren't entity-per-file). Replace the numbered index files (07, 08, 10) with generated views.

---

## 3. Interpret Results Command (`/science:interpret-results`) — DONE

### Problem

The research cycle currently goes:
research-topic → add-hypothesis → build-dag → specify-model → plan-pipeline → review-pipeline → (run pipeline) → ???

After running a pipeline and getting results, there's no structured command for feeding findings back into the research framework.
The agent would need to manually update hypothesis status, revise the causal model, surface new questions, and update priorities.
This is the most intellectually important step — and it's unguided.

### Proposed solution

A `/science:interpret-results` command that takes results and systematically updates the research framework.

#### Input

`$ARGUMENTS` specifies what to interpret. Could be:
- A path to a results file, notebook, or output directory
- A prose description of findings
- An inquiry slug (to find associated outputs)

If no argument, prompt the user to describe what they found.

#### Workflow

1. **Load context** — research question, active hypotheses, the relevant inquiry/DAG, current open questions
2. **Summarize findings** — what did the analysis produce? Key numbers, effect sizes, confidence intervals, unexpected patterns. Distinguish between:
   - Strong signal (clear, replicated, large effect)
   - Suggestive signal (directional but uncertain)
   - Null result (no effect detected — important to record, not discard)
   - Ambiguous result (multiple interpretations possible)
3. **Evaluate hypotheses** — for each relevant hypothesis:
   - Does this evidence support, refute, or leave it unchanged?
   - Propose status update if warranted (proposed → supported/refuted/revised)
   - If revising, draft the revision
   - **Ask user to confirm** before writing any status change
4. **Assess causal model** — do results suggest:
   - Missing variables or edges?
   - Edges that should be removed or reversed?
   - Effect sizes that inform parameter estimates?
   - Propose graph updates via `science-tool` commands (don't edit graph directly)
5. **Surface new questions** — what new questions do these results raise?
6. **Update priorities** — given what we now know, what should change in RESEARCH_PLAN.md?
7. **Update knowledge graph** — add interpretation claims with provenance to the graph (confidence scores, evidence links)

#### Output

- Write interpretation to `doc/interpretations/YYYY-MM-DD-<slug>.md`
- Update hypothesis files in `specs/hypotheses/` (after user confirmation)
- Add new questions to `doc/questions/`
- Update `RESEARCH_PLAN.md` with revised priorities
- Suggest next commands: `discuss` (to debate findings), `research-gaps` (to reassess coverage), `add-hypothesis` (if new conjectures emerged)

#### Template sections

```markdown
## Findings Summary
<Key results with effect sizes and confidence. Classify signal strength.>

## Hypothesis Evaluation
| Hypothesis | Prior status | Evidence summary | Proposed status | Confidence |
<For each relevant hypothesis. Include null results.>

## Causal Model Implications
<Edges to add/remove/reverse. Missing variables suggested by results.>

## New Questions Raised
<Questions that didn't exist before these results.>

## Limitations & Caveats
<What these results do NOT tell us. Threats to validity.>

## Updated Priorities
<What changes in the research plan given these findings.>
```

### Design decisions to resolve

- Should this command also handle exploratory/descriptive results (not tied to a specific hypothesis)?
  Recommendation: yes. Not all results test hypotheses — some are discovery-oriented. The "Findings Summary" section handles this; "Hypothesis Evaluation" can be marked N/A.
- Should it include statistical assessment guidance?
  Recommendation: yes, but framework-agnostic. Prompt for practical significance ("is this effect large enough to matter?") rather than prescribing p-value thresholds.

---

## 4. Streamline Command Preambles — DONE

### Problem

Nearly every command starts with 8-10 "Before Writing" steps that overlap heavily:

```
1. Read role prompt (with fallback)
2. Read research-methodology skill
3. Read scientific-writing skill
4. Read template
5. Read specs/research-question.md
6. Check existing docs
...
```

This creates:
- **Redundant context burn** — an agent running two commands back-to-back re-reads identical files
- **Verbose commands** — half the command is boilerplate preamble
- **Maintenance burden** — changing a shared pattern means editing 10+ commands

### Proposed solution

#### A. Shared preamble reference

Create `references/command-preamble.md` with the common setup:

```markdown
# Command Preamble

Before executing any research command:

1. Load role prompt: `prompts/roles/<role>.md` if present,
   else `${CLAUDE_PLUGIN_ROOT}/references/role-prompts/<role>.md`.
2. Load the `research-methodology` and `scientific-writing` skills.
3. Read `specs/research-question.md` for project context.
```

Commands then reference it with only their command-specific additions:

```markdown
## Setup

Follow `references/command-preamble.md` (role: `research-assistant`).

Additionally:
1. Read `templates/background-topic.md`.
2. Check `doc/topics/` for existing coverage; ask before overwriting.
```

This cuts each command's preamble from ~10 lines to ~3-4.

#### B. Tighten wording throughout

General principles for the editing pass:
- Remove parenthetical explanations that restate the obvious
- Collapse multi-sentence instructions into single lines
- Remove "first-use compatibility" scaffolding (the new doc structure from #2 eliminates the need)
- Replace hedging ("if found, ask whether to update or create a new version") with direct instructions ("ask before overwriting")

#### C. Skill loading strategy

Skills listed in command preambles (`research-methodology`, `scientific-writing`) are also in the Claude Code skill system, which auto-loads them based on trigger descriptions.

Two concerns:
1. Auto-loading depends on the skill's `description` field matching the task context — not guaranteed for every invocation
2. Explicit loading is deterministic — the agent always reads the skill

Recommendation: keep explicit skill loading in the shared preamble (deterministic > clever).
This costs ~2 lines per command but guarantees the guidance is loaded.
Remove per-command repetition of the same instruction.

### Interaction with #2 (consolidation)

This improvement should be done **after** #2, since file paths in every command will change.
Doing both simultaneously avoids editing commands twice.

### Commands affected

All 18 commands need review. The ones with the heaviest preambles:
`research-topic`, `research-paper`, `summarize-topic`, `summarize-paper`, `search-literature`, `research-gaps`, `discuss`, `add-hypothesis`, `critique-approach`

Lighter commands (`create-project`, `review-tasks`, `sketch-model`) have shorter preambles but should still reference the shared file for consistency.

---

## 5. Systematic Cross-Reference Validation — DONE

### Problem

Commands instruct the agent to "reference hypothesis IDs," "link to open questions," and "use BibTeX keys."
But nothing verifies these references are valid.
A revised or deleted hypothesis leaves stale `H03` references scattered across documents.
A mistyped BibTeX key silently breaks citation chains.

Additionally, the `research-methodology` skill introduces `[UNVERIFIED]` and `[NEEDS CITATION]` markers — these are intentional gaps, but nothing tracks whether they get resolved.

### Proposed solution

#### A. `science-tool refs check` CLI command

A new subcommand that scans project documents for internal references and validates them.

**Reference types to check:**

| Pattern | Match strategy | Validates against |
|---|---|---|
| `H01`, `H02`, ... | `/\bH\d{2,}\b/` in prose (not headings/frontmatter) | Files in `specs/hypotheses/h01-*.md` |
| `[@AuthorYear]` | Standard pandoc citation syntax | Entries in `papers/references.bib` |
| Markdown links to `doc/`, `specs/` | `[text](path)` link targets | File existence |
| Inquiry slugs in commands/prose | Explicit mentions | `knowledge/graph.trig` inquiry nodes |
| `[UNVERIFIED]` markers | Literal string | Report count and locations (not an error — a tracking metric) |
| `[NEEDS CITATION]` markers | Literal string | Report count and locations |

Note on hypothesis ID matching: `H01` appears in many contexts (headings, frontmatter IDs, prose references).
Only flag references in prose body text that don't correspond to an existing hypothesis file.
Occurrences in headings or the hypothesis's own file are not cross-references.

**Output:**

```
refs check: 3 broken, 2 unresolved markers

  doc/topics/protein-folding.md:14
    H03 — no matching file in specs/hypotheses/

  doc/papers/Smith2020-attention.md:8
    @Smith2020 — not in papers/references.bib

  doc/interpretations/2026-03-01-pilot.md:22
    Link doc/background/03-rna-structure.md — file not found
    Suggestion: doc/topics/rna-structure.md (fuzzy match)

  Unresolved markers:
    2x [UNVERIFIED] (doc/topics/gene-regulation.md:18, doc/papers/Jones2024.md:31)
    0x [NEEDS CITATION]
```

#### B. Integration points

- Run as part of `/science:status` (summary line: "3 broken refs, 2 unresolved markers")
- Available standalone: `science-tool refs check`
- Optionally run by commands that create cross-references (`add-hypothesis`, `research-topic`, `interpret-results`) as a post-step

#### C. Auto-fix suggestions

For common cases, suggest the most likely fix:

- Hypothesis renumbered: "H03 not found. Did you mean H04 (`h04-rna-binding.md`)?"
- BibTeX key typo: "Did you mean `@Smith2021`?" (Levenshtein distance)
- File moved: check git log for renames of the missing path

Auto-fix is suggestion-only — never modify files without user confirmation.

### Implementation approach

1. **Phase 1:** Regex-based scan of markdown files + file system validation + BibTeX parser. Cover hypothesis IDs, citations, and markdown links. Ship as `science-tool refs check`.
2. **Phase 2:** Add `[UNVERIFIED]`/`[NEEDS CITATION]` tracking.
3. **Phase 3:** Integrate with knowledge graph — validate that entities referenced in prose exist as graph nodes.

### Scan scope

- Scan: `doc/`, `specs/`, `RESEARCH_PLAN.md`
- Skip: `templates/` (contain placeholders), `.venv/`, `data/`
- Broken refs are warnings by default, errors with `--strict` (useful for CI or pre-commit hooks)

---

## Priority and Sequencing

| # | Improvement | Impact | Effort | Status |
|---|---|---|---|---|
| 3 | `/science:interpret-results` | High — completes the research cycle | Medium | **DONE** (Phase A) |
| 2 | Consolidate notes/summaries | High — eliminates confusion | Medium-High | **DONE** (Phase B) |
| 4 | Streamline preambles | High — less context burn | Low-Medium | **DONE** (Phase B) |
| 1 | `/science:status` | High — pays off every session | Medium | **DONE** (Phase C) |
| 5 | Cross-reference validation | Medium — catches rot early | Medium | **DONE** (Phase C) |

### Execution history

- **Phase A:** `interpret-results` command + template created
- **Phase B:** Consolidated doc structure, merged templates, shared preamble, updated all 18 commands + 3 skills + 4 references, deleted `notes/` layer and `notes-organization.md`
- **Phase C:** `status` command created, `science-tool refs check` implemented with 13 tests (hypothesis IDs, citations, markdown links, markers)
