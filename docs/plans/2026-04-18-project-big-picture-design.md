# Project Big-Picture Synthesis

**Date:** 2026-04-18
**Status:** Draft

## Motivation

As a research project grows, the number of questions, interpretations, tasks, and claims accumulates into a thicket. Each step was individually justified, but the cumulative story — "what did we investigate, what did we learn, where are we now?" — gets buried. Users confronted with the full accumulation see trees, not the forest.

The current surface addresses this partially but incompletely:

- `/science:status` is an ephemeral dashboard, capped at ~100 lines. Orientation-in-the-moment, not a story.
- `core/overview.md` is durable bedrock, template-scaffolded and agent-assisted-human-curated. Intended for identity-level claims ("what this project is / why it exists"), capped at ~150 lines. In practice it has been overgrown by state/arc material (mm30's is 24.5KB) because no better home existed for that content.
- `doc/reports/` holds ad-hoc analyses, typically task-granular. Not hypothesis-indexed, not regenerable.
- `/science:health`, `/science:next-steps`, `/science:compare-hypotheses` serve adjacent but distinct needs.

The missing layer is a **generated, multi-scale, hypothesis-organized narrative synthesis** — the forest-from-trees artifact.

## Goal

Introduce `/science:big-picture`, a command that generates a distilled project synthesis decomposed by hypothesis, with a project-level rollup. Intended both for the user's own orientation and as an artifact shareable with collaborators.

## Scope

### In scope (v1)

- New command `/science:big-picture`.
- Per-hypothesis synthesis files under `doc/reports/synthesis/`.
- Project-level rollup under `doc/reports/synthesis.md` (overwritten on regen) with optional timestamped snapshots under `doc/reports/synthesis-history/`.
- An "emergent threads" file for cross-hypothesis and orphan material.
- Question→hypothesis resolver with fallback chain, supporting many-to-many question↔hypothesis associations.
- Data-source precedence rule that tolerates both pre- and post-graph-claim-migration projects.
- Degraded-mode markers (orphan count, thin-arc flags, missing-claim-structure flags) surfaced as first-class output.
- Parallel Sonnet sub-agent dispatch with Opus synthesizer.
- Verification rules (citation requirement, hedging discipline, no-fabrication-under-thin-provenance) enforced through sub-agent prompt constraints and fixture tests.

### Out of scope (v1)

- Writing back to `core/overview.md`. Overview stays human-curated; big-picture output is an input the user distills from manually. A future `/science:update-overview` command may automate distillation — deferred.
- Visual/graphical synthesis artifacts (per-hypothesis DAGs with narrative annotations). Future work.
- Cross-project synthesis. Single-project only.
- `.edges.yaml` → graph claim importer. Already on the roadmap per the 2026-04-15 layered-claims spec.
- Fixing the question→hypothesis frontmatter gap. Handled in a sibling spec (see Follow-on Work).

## Command Interface

```
/science:big-picture [--hypothesis <id>] [--dry-run] [--commit] [--snapshot]
                     [--since <date> --output <path>]
```

- **Default behavior**: regenerate all per-hypothesis files, the emergent-threads file, and `doc/reports/synthesis.md`. Files written, left unstaged.
- `--hypothesis <id>`: regenerate only one per-hypothesis file. Skips the rollup. After a partial regen, the rollup's `synthesized_from` frontmatter will no longer match the per-hypothesis file's SHA; subsequent invocations must print a staleness warning naming the mismatched hypothesis file(s) until a full regen is run.
- `--dry-run`: print what would be generated without writing files.
- `--commit`: auto-commit written files with a standard message (`doc(big-picture): regenerate synthesis YYYY-MM-DD`).
- `--snapshot`: after regeneration, copy the project-level rollup to `doc/reports/synthesis-history/<YYYY-MM-DDTHHMMSSZ>.md` for longitudinal comparison. Without this flag, no history file is written — `git log -p doc/reports/synthesis.md` is the primary evolution record.
- `--since <date>`: produce a scoped Arc bounded to activity after this date. **Requires `--output <path>` and never overwrites canonical artifacts.** This prevents a partial-window narrative from later being mistaken for the authoritative synthesis. The scoped output records `since:` in frontmatter.

## Artifact Layout

```
doc/reports/synthesis/
├── <hypothesis-id>.md            # one per hypothesis, overwritten on regen
├── _emergent-threads.md          # cross-hypothesis + orphan material
doc/reports/
├── synthesis.md                  # project-level rollup, overwritten on regen
└── synthesis-history/
    └── <YYYY-MM-DDTHHMMSSZ>.md  # optional snapshots on --snapshot
```

All canonical artifacts (`synthesis/<hyp>.md`, `_emergent-threads.md`, `synthesis.md`) are overwritten on regen. Evolution is tracked by git: `git log -p doc/reports/synthesis.md` gives the full narrative history without fragmenting across dated filenames. Snapshots under `synthesis-history/` are opt-in via `--snapshot` for users who want a human-readable timeline independent of git.

## Section Structure

### Per-hypothesis file (~400–600 words)

Frontmatter:
```yaml
---
id: "synthesis:<hyp-id>"
type: "synthesis"
hypothesis: "hypothesis:<hyp-id>"
generated_at: "<ISO-8601>"
source_commit: "<SHA>"
provenance_coverage: "high" | "partial" | "thin"
---
```

Body sections:

1. **State** — current claim status and key questions. Drawn from `.edges.yaml` (if present) or graph claims (when migrated); falls back to hypothesis file's `related:` field and question-level status. Names the strongest supporting evidence and any contested or retracted claims.
2. **Arc** — narrative of how the investigation evolved. Reconstructed by traversing `prior_interpretations` chains and task creation dates. Not a retelling of every step — a story: initial framing → main investigative moves → what each move resolved → current epistemic position. If provenance is thin, the section is shorter and explicitly says so ("Arc reconstruction is limited because N interpretations lack prior_interpretations chains").
3. **Research fronts** — live questions under this hypothesis, open tasks, gap/uncertainty areas. Draws from the graph's `uncertainty` and `gaps` surfaces filtered to this hypothesis's subgraph, plus unresolved questions in its `related:` field.

### Emergent-threads file (~200–400 words)

- Orphan questions (unresolvable to any hypothesis by the resolver's fallback chain).
- Orphan interpretations (interpretations whose `related:` field doesn't intersect any hypothesis subgraph).
- Cross-hypothesis evidence clusters: interpretations or tasks that reference two or more hypotheses.
- Candidate hypotheses: recurring topics in discussions or orphan questions that might warrant a new hypothesis.

### Project-level rollup (~1000–1500 words)

Frontmatter:
```yaml
---
type: "synthesis-rollup"
generated_at: "<ISO-8601>"
source_commit: "<SHA>"
synthesized_from:
  - { hypothesis: "<hyp-id>", file: "doc/reports/synthesis/<hyp-id>.md", sha: "<SHA>" }
  # one entry per hypothesis — used to detect rollup staleness after partial regen
emergent_threads_sha: "<SHA>"
orphan_question_count: <int>
---
```

Body sections:

- **TL;DR** — 5–7 bullets. Most salient facts across the project. Written by the Opus synthesizer, lifted from the per-hypothesis summaries.
- **State** — cross-hypothesis consolidation. What the project collectively believes, where the strongest evidence sits, which areas are contested.
- **Arc** — project-wide narrative. One paragraph per hypothesis, plus a brief framing of how the hypotheses relate.
- **Research fronts** — ranked list of where effort would most likely pay off. Combines uncertainty density, recent activity, and explicit task priority signals.
- **Emergent threads** — pointer to `_emergent-threads.md` with a 2–3 sentence summary of what's there.

## Data-Source Precedence

For claim/evidence structure (used by State and Arc sections):

1. **Graph claims** — when `science-tool graph claims` surfaces proposition/claim nodes for the hypothesis. (Future state after the `.edges.yaml` import lands.)
2. **`.edges.yaml`** — hand-curated DAG edge files in `doc/figures/dags/*.edges.yaml`. Read directly as structured claim data (edge_status, identification, data_support, lit_support).
3. **YAML frontmatter chains** — follow `hypothesis.related[]`, `interpretation.related[]`, `interpretation.prior_interpretations[]`, `task.related[]`.
4. **Graph summary surfaces** — `question-summary`, `dashboard-summary`, `uncertainty`, `gaps` as complementary context.

**Semantics in v1: "highest-priority source with content wins, no merging."** If (1) returns any proposition/claim nodes for a hypothesis, they are used *instead of* (2) and (3) for claim structure — not merged field-by-field. Summary-surface data from (4) is complementary and always included.

**Deferred: hybrid-source merge semantics.** Today, no project is hybrid (mm30 has only `.edges.yaml`; natural-systems has neither graph claims nor `.edges.yaml`). Hybrid state only becomes possible once the `.edges.yaml` → graph importer lands. At that point, a follow-on design will define identity keys, dedup rules, and conflict handling for propositions present in both sources. v1 does not attempt this — treating a source that "wins" as fully authoritative is sufficient while every project is non-hybrid.

## Question → Hypothesis Resolver

Questions can legitimately serve multiple hypotheses (e.g., in mm30, a question about 1q-gain effects on CTA expression plausibly informs both `h1-epigenetic-commitment` and `h2-cytogenetic-distinct-entities`). The resolver is many-to-many.

For each question, collect associations from these sources:

1. **Direct**: question frontmatter has `hypothesis: <id>` or `hypothesis: [<id>, ...]`. Future state once the sibling spec lands. Confidence: `direct`.
2. **Inverse top-down**: hypothesis file's `related:` field lists the question. Primary path today. Confidence: `inverse`.
3. **Transitive via interpretation**: interpretations whose `related:` contains both the question and a hypothesis. Score by count and recency. Confidence: `transitive`.

Resolver output per question:

```
{
  "hypotheses": [
    { "id": "<hyp-id>", "confidence": "direct" | "inverse" | "transitive", "score": <float> }
  ],
  "primary_hypothesis": "<hyp-id>" | null
}
```

- `primary_hypothesis` is the highest-confidence association (ties broken by score, then recency). Null if the question is orphan.
- A question with ≥1 matching hypothesis appears in the **State** and **Research fronts** sections of every matching per-hypothesis file, with its association confidence shown when not `direct`.
- A question with ≥2 matching hypotheses at confidence `inverse`-or-better *also* appears in `_emergent-threads.md` under "Cross-hypothesis questions."
- A question with zero matches (orphan) appears **only** in `_emergent-threads.md`.

This avoids both under-coverage (multi-hypothesis questions dropped from relevant files) and false-signal cross-cutting (weak transitive-only matches flooding emergent-threads).

## Generation Flow

```
1. Precompute (main agent):
   - Load science.yaml, specs/research-question.md, specs/hypotheses/*.md
   - Run graph surfaces: project-summary, question-summary, inquiry-summary,
     dashboard-summary, uncertainty, gaps, neighborhood-summary
   - Run question→hypothesis resolver across all questions
   - For each hypothesis, assemble a bundle:
     * hypothesis file
     * resolved questions + their status
     * related tasks (via task.related[])
     * related interpretations (via interpretation.related[] intersection)
     * matching .edges.yaml files
     * filtered uncertainty/gaps output for this subgraph

2. Dispatch (parallel):
   - N Sonnet sub-agents, one per hypothesis, each receives:
     * hypothesis bundle
     * section template + length budget
     * degraded-mode detection rules
   - 1 Sonnet sub-agent for emergent-threads analysis (orphans + cross-cutters)

3. Synthesize:
   - Opus 4.7 synthesizer consumes all sub-outputs + project-level graph surfaces
   - Emits project-level rollup with TL;DR
   - Opus is the only agent with visibility across all hypotheses — the
     cross-hypothesis State/Arc/Fronts rolling happens here

4. Write:
   - Write per-hypothesis files (overwrite)
   - Write _emergent-threads.md (overwrite)
   - Write synthesis.md (overwrite)
   - If --snapshot: copy synthesis.md to synthesis-history/<timestamp>.md
   - Leave unstaged unless --commit
   - If invoked with --hypothesis <id>: skip steps 3 and the non-targeted
     file writes; on the next invocation, compare per-hypothesis SHAs
     against synthesis.md's synthesized_from frontmatter and print a
     staleness warning if any mismatch
```

## Degraded-Mode Behavior

Three quality signals surface in output, not as failures but as first-class observations:

- **`provenance_coverage`** (per-hypothesis frontmatter): `high` | `partial` | `thin`. Based on fraction of interpretations under this hypothesis that have `prior_interpretations` chains and on presence/absence of `.edges.yaml` or graph claims.
- **Thin-arc marker**: when `provenance_coverage: thin`, the Arc section is explicitly shortened and opens with a one-line note naming the limitation.
- **Orphan-question count** (project rollup TL;DR): total orphan questions, linked to the emergent-threads file.

**No-fabrication rule under thin provenance**: when `provenance_coverage: thin`, the Arc section MUST be shortened rather than filled with speculative narrative. Sub-agent prompts carry an explicit negative instruction: *if you cannot cite a specific interpretation or task for a claim, omit the claim and note the gap; do not invent plausible-sounding connective tissue.*

The point: these are useful signals about where provenance investment would pay off, and they validate the structural gap findings we identified (questions without `hypothesis:` field, claims not yet in graph).

## Verification & Acceptance Criteria

Because the failure mode of a generative synthesis is persuasive-but-weakly-grounded narrative, the primary defense is prompt-level constraints on the sub-agents, reinforced by fixture tests:

### Content rules (enforced via sub-agent prompts)

1. **Citation requirement**: every factual claim in the **State** section must name its source inline — an `.edges.yaml` edge ID, interpretation file, task ID, graph claim IRI, or question ID. Claims without a nameable source are not written.
2. **Arc grounding**: every sentence in the **Arc** section must reference at least one interpretation or task from the provenance bundle for that hypothesis. Narrative that cannot be grounded in a specific artifact is cut.
3. **Hedging discipline**: claims about unreplicated, contested, or transitively-inferred findings must use hedged language (e.g., "suggestive", "one-source", "not yet replicated", "inferred via interpretation X"). Confident prose is reserved for claims with direct graph or `.edges.yaml` status of `supported`.
4. **No-fabrication-under-thin-provenance**: restated from Degraded-Mode above — omit, do not invent.

### Fixture tests

Two regression fixtures exercise the two data-source regimes:

- **mm30** (`.edges.yaml` + frontmatter, no graph claims): exercises priorities (2) and (3). Validates that `.edges.yaml` edge structure is correctly read, that `prior_interpretations` chains produce credible Arc reconstruction, and that the h1+h2 cross-cutting questions appear in both files and in emergent-threads.
- **natural-systems** (frontmatter only, no `.edges.yaml` or graph claims): exercises priority (3) in isolation. Validates that State sections gracefully omit claim-structure content (`missing-claim-structure` marker visible) without synthesizing fictional claim status.

Each fixture asserts:

- Expected set of per-hypothesis files is produced with non-empty sections.
- Orphan-question count matches a hand-audited ground truth (±1).
- No Arc sentence references an interpretation ID that does not exist in the project.
- `provenance_coverage` markers match expected values per hypothesis.

Fixtures are executed against a pinned git SHA of each project to keep expectations stable; updates to fixture expectations are deliberate spec changes.

### Pre-release check

Before merging this command for general use, a manual review of the generated `synthesis.md` for both fixture projects must confirm:

- No hallucinated interpretation/task/edge references.
- Thin-arc sections are recognizable as such (not padded with speculation).
- The TL;DR is actually a distillation, not a re-summary of each hypothesis.

## Relationship to Existing Artifacts

| Existing artifact | Relationship to big-picture |
|---|---|
| `/science:status` | Unchanged. Remains the fast orientation layer. Big-picture is complementary, not a replacement. |
| `/science:health` | Unchanged. Big-picture consumes health output as context (e.g., proposition coverage) but does not duplicate it. |
| `/science:next-steps` | Unchanged. Big-picture's Research Fronts section is broader and hypothesis-organized; next-steps remains task-level and immediate. |
| `/science:compare-hypotheses` | Unchanged. That command does deep pairwise comparison; big-picture gives holistic rollup. Boundary: if compare-hypotheses output would fit inside big-picture's cross-hypothesis State section, big-picture summarizes and links to the comparison rather than duplicating. |
| `core/overview.md` | Unchanged in v1. Remains human-curated identity bedrock. Users read big-picture output and manually slim/update overview.md with it in front of them. Expected to shrink back toward the ~150-line template cap as big-picture absorbs accrued state/arc mass. |
| `doc/reports/` | Big-picture adds a `synthesis/` subdirectory, a top-level `synthesis.md`, and an optional `synthesis-history/` directory. Existing task-granular analyses are untouched. |
| `doc/meta/` | Big-picture does not write here. Status and next-steps snapshots remain ephemeral. |

## Follow-on Work

- **Sibling spec: question→hypothesis frontmatter**. Small, targeted: add optional `hypothesis:` field to `templates/question.md`, add `/science:create-question` command, add soft validator warning, optional back-fill migration. Independent of this spec; can be implemented in parallel. When it lands, the resolver's fallback chain naturally benefits but doesn't require changes here.
- **`.edges.yaml` → graph claim importer**. Already on the roadmap per the 2026-04-15 layered-claims spec and 2026-04-17 inquiry-edge-posterior spec. When it lands, this spec's data-source precedence rule auto-benefits — priority 1 (graph claims) starts returning content on projects that previously relied on priority 2 (`.edges.yaml`).
- **Hybrid-source merge semantics**. Co-designed with the importer above. Once hybrid projects become possible, a short follow-on spec defines proposition identity keys, dedup rules, and conflict handling (likely: prefer graph claims, mark conflict in output, surface discrepancy count). Not needed in v1 because no hybrid project exists yet.
- **`/science:update-overview`**. Defer. Once we have big-picture output in hand for a few projects, we'll know whether overview distillation is better done as a separate command or just left as the user's manual task.
- **Visual synthesis**. Per-hypothesis DAG-with-narrative rendering. Building on mm30's DAG precedent. Out of scope for v1.

## Implementation Notes

- The command lives at `commands/big-picture.md` following the existing pattern.
- Sub-agents dispatched via the framework's existing sub-agent pattern (see `agents/paper-researcher.md`, `agents/topic-researcher.md` for precedent).
- Bundle assembly in the main command is synchronous file reading + graph queries — no new science-tool CLI is required in v1.
- Section-template prompts for the Sonnet sub-agents should live in `agents/` (proposed: `agents/hypothesis-synthesizer.md`, `agents/emergent-threads-synthesizer.md`).
- The Opus synthesizer prompt lives inline in `commands/big-picture.md` since it's main-agent-facing.

## Open Questions (to resolve during implementation)

- **Length budgets**: per-hypothesis 400–600 words, rollup 1000–1500 words are starting points. May adjust after seeing output on mm30 and natural-systems.
- **Snapshot retention**: with `--snapshot`, how many `synthesis-history/` files to keep? v1 keeps all (git-tracked, cheap). Revisit if the directory becomes cluttered or if users want automatic pruning (e.g., keep one per month).
- **Software-profile projects**: natural-systems has hypotheses backed by code. V1 treats code as opaque — interpretations cite it but the synthesizer does not read code directly. Confirm adequacy during implementation.
- **Inquiry vs. hypothesis decomposition**: the graph exposes `inquiry-summary` as a more graph-native unit. V1 decomposes by hypothesis (matching `specs/hypotheses/*.md`). If inquiries prove more useful as the decomposition axis during implementation, switch — but hypothesis is the predictable, user-facing structure that should stay the default.
