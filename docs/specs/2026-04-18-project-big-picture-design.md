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
- Dated project-level rollup under `doc/reports/synthesis-YYYY-MM-DD.md`.
- An "emergent threads" file for cross-hypothesis and orphan material.
- Question→hypothesis resolver with fallback chain.
- Data-source precedence rule that tolerates both pre- and post-graph-claim-migration projects.
- Degraded-mode markers (orphan count, thin-arc flags, missing-claim-structure flags) surfaced as first-class output.
- Parallel Sonnet sub-agent dispatch with Opus synthesizer.

### Out of scope (v1)

- Writing back to `core/overview.md`. Overview stays human-curated; big-picture output is an input the user distills from manually. A future `/science:update-overview` command may automate distillation — deferred.
- Visual/graphical synthesis artifacts (per-hypothesis DAGs with narrative annotations). Future work.
- Cross-project synthesis. Single-project only.
- `.edges.yaml` → graph claim importer. Already on the roadmap per the 2026-04-15 layered-claims spec.
- Fixing the question→hypothesis frontmatter gap. Handled in a sibling spec (see Follow-on Work).

## Command Interface

```
/science:big-picture [--hypothesis <id>] [--dry-run] [--commit] [--since <date>]
```

- **Default behavior**: regenerate all per-hypothesis files, the emergent-threads file, and a fresh dated rollup. Files written, left unstaged.
- `--hypothesis <id>`: regenerate only one per-hypothesis file and skip the rollup. For iterative work on a single front.
- `--dry-run`: print what would be generated without writing files.
- `--commit`: auto-commit written files with a standard message (`doc(big-picture): regenerate synthesis YYYY-MM-DD`).
- `--since <date>`: bias the Arc section toward activity after this date. Omits older provenance from the narrative but still references it in the State section.

## Artifact Layout

```
doc/reports/synthesis/
├── <hypothesis-id>.md            # one per hypothesis, overwritten on regen
├── _emergent-threads.md          # cross-hypothesis + orphan material
doc/reports/
├── synthesis-YYYY-MM-DD.md       # dated project-level rollup, new file per run
```

Per-hypothesis files are overwritten; git provides versioning. The dated rollup is a new file each run (matching the existing `doc/meta/next-steps-*.md` pattern), so comparing successive rollups is trivially a `git diff` or file comparison.

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

This precedence is stable across the graph-claim migration. Pre-migration projects (mm30) lean on (2) and (3); post-migration projects will lean on (1); hybrid projects will combine. User experience is identical.

## Question → Hypothesis Resolver

Because question files do not yet carry an explicit `hypothesis:` field in YAML frontmatter (see sibling spec), the resolver applies fallbacks in order:

1. **Direct**: question frontmatter has `hypothesis: <id>` (or `hypothesis: [<id>, ...]`). Future state once the sibling spec lands.
2. **Inverse top-down**: hypothesis file's `related:` field lists the question. Primary path today.
3. **Transitive via interpretation**: any interpretation whose `related:` contains both the question and a hypothesis is evidence of association. Score by count and recency.
4. **Orphan**: no reachable hypothesis. Surfaced in emergent-threads.

The resolver's output for each question is `{hypothesis_id | null, confidence: "direct" | "inverse" | "transitive" | "orphan"}`. Displayed in per-hypothesis State sections when confidence is not `direct`, so readers can judge inference strength.

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
   - Write synthesis-YYYY-MM-DD.md (new file)
   - Leave unstaged unless --commit
```

## Degraded-Mode Behavior

Three quality signals surface in output, not as failures but as first-class observations:

- **`provenance_coverage`** (per-hypothesis frontmatter): `high` | `partial` | `thin`. Based on fraction of interpretations under this hypothesis that have `prior_interpretations` chains and on presence/absence of `.edges.yaml` or graph claims.
- **Thin-arc marker**: when `provenance_coverage: thin`, the Arc section is explicitly shortened and opens with a one-line note naming the limitation.
- **Orphan-question count** (project rollup TL;DR): total orphan questions, linked to the emergent-threads file.

The point: these are useful signals about where provenance investment would pay off, and they validate the structural gap findings we identified (questions without `hypothesis:` field, claims not yet in graph).

## Relationship to Existing Artifacts

| Existing artifact | Relationship to big-picture |
|---|---|
| `/science:status` | Unchanged. Remains the fast orientation layer. Big-picture is complementary, not a replacement. |
| `/science:health` | Unchanged. Big-picture consumes health output as context (e.g., proposition coverage) but does not duplicate it. |
| `/science:next-steps` | Unchanged. Big-picture's Research Fronts section is broader and hypothesis-organized; next-steps remains task-level and immediate. |
| `/science:compare-hypotheses` | Unchanged. That command does deep pairwise comparison; big-picture gives holistic rollup. Boundary: if compare-hypotheses output would fit inside big-picture's cross-hypothesis State section, big-picture summarizes and links to the comparison rather than duplicating. |
| `core/overview.md` | Unchanged in v1. Remains human-curated identity bedrock. Users read big-picture output and manually slim/update overview.md with it in front of them. Expected to shrink back toward the ~150-line template cap as big-picture absorbs accrued state/arc mass. |
| `doc/reports/` | Big-picture adds a `synthesis/` subdirectory and dated rollup files. Existing task-granular analyses are untouched. |
| `doc/meta/` | Big-picture does not write here. Status and next-steps snapshots remain ephemeral. |

## Follow-on Work

- **Sibling spec: question→hypothesis frontmatter**. Small, targeted: add optional `hypothesis:` field to `templates/question.md`, add `/science:create-question` command, add soft validator warning, optional back-fill migration. Independent of this spec; can be implemented in parallel. When it lands, the resolver's fallback chain naturally benefits but doesn't require changes here.
- **`.edges.yaml` → graph claim importer**. Already on the roadmap per the 2026-04-15 layered-claims spec and 2026-04-17 inquiry-edge-posterior spec. When it lands, this spec's data-source precedence rule auto-benefits — priority 1 (graph claims) starts returning content on projects that previously relied on priority 2 (`.edges.yaml`).
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
- **Rollup retention**: how many dated rollups to keep? Probably all (git-tracked, cheap, valuable for longitudinal change tracking). But worth revisiting if the directory becomes cluttered.
- **Software-profile projects**: natural-systems has hypotheses backed by code. V1 treats code as opaque — interpretations cite it but the synthesizer does not read code directly. Confirm adequacy during implementation.
- **Inquiry vs. hypothesis decomposition**: the graph exposes `inquiry-summary` as a more graph-native unit. V1 decomposes by hypothesis (matching `specs/hypotheses/*.md`). If inquiries prove more useful as the decomposition axis during implementation, switch — but hypothesis is the predictable, user-facing structure that should stay the default.
