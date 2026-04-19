# Knowledge Gaps in Project Synthesis

**Date:** 2026-04-19
**Status:** Draft

## Motivation

`/science:big-picture` currently surfaces where live investigation is happening — hypotheses, claims, evidence, orphan questions, cross-cutting threads. What it does not surface is where reading lags investigation: topics that questions refer to but that the project has not backed with sufficient literature.

This blind spot matters because research pressure and reading pressure are often decoupled in practice. A project accumulates questions around a domain (e.g., `ribosome-biogenesis`) while a single background paper sits behind the curtain; the question stack keeps growing without the reading catching up. The synthesis layer has everything it needs to detect this mismatch — it already knows which topics questions reference and which papers the project has — but nothing currently reports the imbalance.

The signal is forward-looking and action-oriented: *"you are asking more about this topic than you have read about it."* Surfacing it in the big-picture rollup and per-hypothesis files makes the gap visible where users already look for "where should I direct effort next?"

## Goal

Add a topic-coverage gap metric to `/science:big-picture` output, at two scales:

1. **Per-hypothesis**: a Knowledge Gaps sub-bullet inside each hypothesis's Research Fronts section, listing topics in that hypothesis's subgraph where coverage lags demand.
2. **Project-rollup**: a new Knowledge Gaps section in `synthesis.md` between Research Fronts and Emergent Threads, listing top-N thinnest topics project-wide with demanding hypotheses named.

## Design Principles

- **One gap definition, two output scales.** The per-hypothesis and rollup views consume the same `compute_topic_gaps` helper with different input scopes. No divergent logic.
- **Use existing linkage data; do not introduce new fields.** Projects already express topic–paper relationships through `related:` (both directions) and `source_refs:` (bibtex citekeys). The metric unions these; it does not demand a new uniform schema.
- **Signal over precision.** The feature's job is ranking, not accounting. A topic that appears twice because one entity links to it two ways and another links in the inverse direction is a ranking-order concern, not a correctness failure. Dedup where cheap; tolerate noise at the edges.
- **Aspect filter cascades from resolver.** Knowledge-gap computation consumes aspect-filtered resolver output. Software-only entities are already excluded upstream; this feature inherits that filter without implementing its own.

## Scope

### In scope (v1)

- New module `science_tool.big_picture.knowledge_gaps` with `compute_topic_gaps`, `TopicGap` dataclass.
- New `science-tool big-picture knowledge-gaps` CLI subcommand emitting JSON for inspection.
- Per-hypothesis bundle assembly gains a `topic_gaps` slice; hypothesis-synthesizer agent renders it in Research Fronts.
- Project rollup gains a Knowledge Gaps section; Opus orchestrator computes and renders it.
- Coverage metric: inclusive (union of entity-linked papers + bibtex `source_refs:` citekeys), deduplicated by bibkey where determinable.
- Gap criterion: `demand(T) > 0 AND coverage(T) < demand(T)`. Topics with `demand == 0` are excluded as research-irrelevant.
- Tests: unit tests for `compute_topic_gaps` against an extended minimal_project fixture; integration against the existing big-picture smoke path.
- `commands/big-picture.md` prose updated to include knowledge-gap computation in Phase 1 bundle assembly and Phase 3 rollup.

### Out of scope (v1)

- **(A) Per-question gap view** ("before answering q48 you need to read more on topic X"). Defer: topic-level signal is the minimum viable version; question-level ranking is a useful drill-down but requires a separate UI shape and is not load-bearing for the main synthesis.
- **(D) Orphan reading** (papers with no downstream question/interpretation/hypothesis reference). Defer: retrospective rather than forward-looking, different semantic purpose, different output placement.
- **Dataset coverage gaps.** Entirely separate feature; should not be folded in.
- **Per-topic paper recommendation.** Out of scope. V1 flags that a gap exists; it does not suggest specific papers to read. External literature search is a different system.
- **Aspect-aware topic filtering at the topic level.** Topics themselves do not gain an `aspects:` field. The filter cascades from the questions driving demand.

## Prerequisites

This spec depends on **manuscript + paper terminology normalization** landing first as a sibling spec. Without it, the `paper:<bibkey>` prefix is ambiguous (the existing `paper.md` template uses it for the user's own manuscript-in-progress). The knowledge-gaps feature uses `paper:<bibkey>` exclusively for external literature.

Transition handling: for the window between this spec landing and every project completing the terminology migration, `compute_topic_gaps` accepts both `paper:<bibkey>` and `article:<bibkey>` as external-literature entity prefixes. Both count the same toward coverage. The fallback is removed once the migration is complete on tracked projects.

## Data Model

### Coverage

For a topic `T` in project `P`:

```
coverage(T) = | related_papers(T) ∪ inverse_papers(T) ∪ bibtex_refs(T) |

where:
  related_papers(T) = { id ∈ T.related : id matches "paper:*" or "article:*" }
  inverse_papers(T) = { id(paper) : paper.related contains T.id,
                                   for paper in project P }
  bibtex_refs(T)    = { cite:<key> ∈ T.source_refs }
```

Dedup: the three sets are unioned with bibkey-based comparison where determinable. A `paper:<bibkey>` entity and a `cite:<bibkey>` citation referencing the same bibkey count as one paper. When a citekey cannot be extracted from an entity ID, dedup falls back to entity-ID string equality.

### Demand

For a topic `T` in project `P`, given aspect-filtered resolver output `R`:

```
demand(T) = |{ q ∈ R : T.id ∈ q.frontmatter.related }|
```

Direct linkage only — a question counts toward a topic's demand only if its own `related:` field lists the topic ID. Transitive inference (e.g., "an interpretation mentions both the question and the topic") is not expanded. Transitive expansion risks inflating demand well beyond the researcher's declared intent; direct linkage matches what users have explicitly asserted.

`R` is the aspect-filtered resolver output: software-only questions are excluded from demand automatically because they do not appear in `R`. This is the sole aspect-coupling point.

### Gap

```
gap_score(T) = max(0, demand(T) - coverage(T))
is_gap(T)    = demand(T) > 0 AND coverage(T) < demand(T)
```

Topics with `demand == 0` are excluded entirely from output. A topic no question references is not a gap; it is a topic the project is not currently asking about.

### `TopicGap` dataclass

```python
@dataclass(frozen=True)
class TopicGap:
    topic_id: str
    coverage: int
    demand: int
    gap_score: int
    demanding_questions: list[str]  # question IDs driving the demand
    hypotheses: list[str]            # hypothesis IDs whose subgraph includes this topic
```

`hypotheses` is derived from the resolver output: a hypothesis is associated with a topic if any question under that hypothesis (by `primary_hypothesis` or any resolver-hypothesis match) references the topic.

## Output

### Per-hypothesis (inside Research Fronts)

Each per-hypothesis synthesis file's existing Research Fronts section gains a Knowledge Gaps sub-bullet when the hypothesis's question subgraph contains any gap-flagged topics:

```markdown
### Research fronts

- [existing content on live questions, open tasks, uncertainty]
- **Knowledge gaps**: Topics where reading lags investigation for this hypothesis:
  - `topic:ribosome-biogenesis` — 1 paper vs 4 questions referencing it (question:q01, question:q12, question:q18, question:q22)
  - `topic:epigenetic-memory` — 0 papers vs 2 questions referencing it (question:q04, question:q09)
```

Ordering: `gap_score` descending; ties broken alphabetically by topic ID. No cap — hypothesis-local lists are usually short. If zero gaps, the sub-bullet is omitted entirely.

### Project rollup (new section)

`synthesis.md` gains a new `## Knowledge Gaps` section placed between Research Fronts and Emergent Threads:

```markdown
## Knowledge Gaps

Topics where the project's reading lags investigation. Ordered by gap score (questions referencing minus papers covering). Topics with zero questions referencing them are excluded.

| Topic | Coverage | Demand | Gap | Hypotheses |
|---|---|---|---|---|
| `topic:ribosome-biogenesis` | 1 | 4 | 3 | h1, h2 |
| `topic:epigenetic-memory` | 0 | 2 | 2 | h1 |
```

Top 10 topics by `gap_score`. If fewer than 10 topics have gaps, show only those. If zero, emit a one-line "No knowledge gaps detected this run." and skip the table.

Question detail is available in per-hypothesis files; the rollup table stays compact (topic, counts, hypotheses only) to fit the rollup's multi-section scope.

## Implementation Architecture

### Module layout

New module `science-tool/src/science_tool/big_picture/knowledge_gaps.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from science_tool.big_picture.resolver import ResolverOutput


@dataclass(frozen=True)
class TopicGap:
    topic_id: str
    coverage: int
    demand: int
    gap_score: int
    demanding_questions: list[str]
    hypotheses: list[str]


def compute_topic_gaps(
    project_root: Path,
    resolved_questions: dict[str, ResolverOutput],
) -> list[TopicGap]:
    """Return all topics with demand > 0 and coverage < demand.

    Sorted by gap_score descending; ties broken by topic_id ascending.
    """
```

Pure function with only file-reading side effects. Loads:

- Every topic file from `doc/background/topics/` — frontmatter + `related:` + `source_refs:`.
- Every paper file from `doc/papers/` and `doc/background/papers/` — frontmatter + `related:`. Accepts both `paper:<bibkey>` and `article:<bibkey>` entity prefixes during the transition window.
- Every question file from `doc/questions/` — frontmatter + `related:` — for demand computation. (Passed-in `resolved_questions` identifies which questions survived aspect filtering; the function re-reads question frontmatter to get `related:` for topic linkage.)

No dependency on the resolver module beyond its `ResolverOutput` type — the function does not call `resolve_questions` itself. The caller (big-picture command orchestrator) computes resolver output once, passes it in.

### Bundle-assembly integration

`commands/big-picture.md` Phase 1 gains a new bundle slice:

```
topic_gaps: filter compute_topic_gaps(project_root, resolved_questions)
            to the topics in this hypothesis's subgraph. A topic is in the
            subgraph iff it is referenced by any question the resolver
            associated with this hypothesis.
```

The hypothesis-synthesizer agent prompt gains one new instruction: "If the bundle includes `topic_gaps`, render them as a Knowledge Gaps sub-bullet inside Research Fronts, following the format in the spec."

### Rollup-phase integration

`commands/big-picture.md` Phase 3 (Opus orchestrator) gains:

- Call `compute_topic_gaps(project_root, resolved_questions)` once to get the full project list.
- Render the top 10 into a new Knowledge Gaps section inserted between Research Fronts and Emergent Threads.
- If zero gaps, emit the "No knowledge gaps detected this run." one-liner and skip the table.

### CLI surface

New subcommand in the existing `big-picture` click group:

```
science-tool big-picture knowledge-gaps [--project-root <path>]
```

Emits JSON of all `TopicGap` entries, sorted by `gap_score` descending. Useful for validation, debugging, and for users who want the numbers without running a full big-picture regeneration. Parallel in shape to the existing `resolve-questions` subcommand.

## Aspect Integration

Knowledge-gap computation sits downstream of the aspect-filter cascade established by the entity-aspects spec:

- The caller (`commands/big-picture.md` Phase 1) passes the aspect-filtered `resolved_questions` dict to `compute_topic_gaps`. Software-only questions are already excluded from this dict by earlier bundle assembly.
- `demand(T)` therefore counts only questions that passed the research-aspect filter.
- A topic referenced only by software-only questions will have `demand == 0` in the filtered view and will be excluded from output.
- Papers are not aspect-filtered — all papers contribute to `coverage(T)` regardless. (A "software paper" covering a research topic still counts as coverage.)

Topics themselves do not gain an `aspects:` field in this spec. If a need emerges (e.g., software-specific topics flooding research synthesis), it extends the entity-aspects spec, not this one.

## Testing

### Fixture extension

Extend `science-tool/tests/fixtures/big_picture/minimal_project/`:

- Add `doc/background/topics/t01-covered.md` — `aspects:` inherited, `related: [paper:p01-example]`.
- Add `doc/background/topics/t02-thin.md` — `related: []`, `source_refs: []`. No coverage.
- Add `doc/background/topics/t03-bibtex-covered.md` — `related: []`, `source_refs: [cite:Smith2024]`. Coverage via bibtex only.
- Add `doc/papers/p01-example.md` — `id: paper:p01-example`, `related: [topic:t01-covered]`.
- Update `doc/questions/q01-direct-to-h1.md` and `q02-inverse-via-h1.md` to include topic references in `related:`. Exact seeding chosen so `t01-covered` has demand=1 coverage=1 (no gap), `t02-thin` has demand=2 coverage=0 (gap_score=2), `t03-bibtex-covered` has demand=1 coverage=1 (no gap).

### Unit tests (`science-tool/tests/test_knowledge_gaps.py`)

- `test_topic_with_zero_demand_excluded` — topic referenced by no question, any coverage, not in output.
- `test_topic_with_coverage_equal_demand_no_gap` — demand=2, coverage=2, not flagged.
- `test_topic_with_coverage_exceeding_demand_no_gap` — demand=1, coverage=3, not flagged.
- `test_topic_with_zero_coverage_and_nonzero_demand_is_gap` — demand=2, coverage=0, gap_score=2.
- `test_topic_coverage_dedup_bibkey_across_entity_and_source_refs` — same bibkey appears in `topic.source_refs: [cite:Smith2024]` and as a `paper:Smith2024` entity → counts once.
- `test_topic_coverage_counts_inverse_linkage` — paper's `related:` contains topic, topic's `related:` does not list the paper → still counted.
- `test_demand_direct_linkage_only_not_transitive` — an interpretation mentions both a question and a topic; the question's own `related:` does not list the topic; topic demand is not incremented by that interpretation.
- `test_software_aspect_question_does_not_count_toward_demand` — question tagged `aspects: [software-development]` references topic T; because caller passes aspect-filtered `resolved_questions`, T's demand excludes the software question.
- `test_article_prefix_accepted_during_transition` — paper entity with `id: article:Smith2024` counts toward coverage alongside `paper:Smith2024`.
- `test_sort_order_gap_score_desc_tiebreak_topic_id_asc` — two topics with equal gap_score ordered alphabetically.

### Integration tests

- `test_knowledge_gaps_cli_emits_json` — `science-tool big-picture knowledge-gaps --project-root <fixture>` returns valid JSON with expected fields.
- `test_knowledge_gaps_empty_project` — project with no topics emits an empty list and exits 0.

### Manual smoke tests

Per the `big-picture` pattern, a mm30 + natural-systems smoke run after the sibling manuscript migration lands:

- `science-tool big-picture knowledge-gaps --project-root .` on mm30 — expect topics with heavy bibtex coverage to show as non-gaps, topics with many questions and thin source_refs to surface.
- Same on natural-systems — expect per-paper-entity coverage to dominate the metric since natural-systems has per-paper files and sparse bibtex.

## Relationship to Existing Specs

- **Entity-aspects (2026-04-19-entity-aspects-design.md)**: this spec relies on the aspect filter cascading through `resolved_questions`. No new coupling beyond what aspects already established.
- **Project big-picture (2026-04-18-project-big-picture-design.md)**: this spec adds one new section to the rollup (Knowledge Gaps, between Research Fronts and Emergent Threads) and one new sub-bullet to per-hypothesis Research Fronts. No change to State, Arc, TL;DR, or Emergent Threads sections.
- **Manuscript + paper terminology rename (sibling spec, not yet written)**: prerequisite. This spec uses `paper:<bibkey>` as the external-literature prefix and assumes the rename has landed; a dual-prefix acceptance (both `paper:` and `article:`) handles the transition window.

## Out of Scope / Follow-on Work

- **Question-relative gap view (A)**: surface gaps at the question level — "question q48 lacks background coverage in topic X." Would require a new ranking view inside per-hypothesis files or a standalone report. Build when the topic-level signal proves insufficient.
- **Orphan reading (D)**: papers whose `related:` field points at no question, interpretation, or topic used by any active hypothesis. Retrospective counterpart to knowledge gaps. Warrants a separate spec when patterns of "dormant reading" become visible in practice.
- **Topic-level aspect tagging**: an optional `aspects:` field on topic entities, if software-specific topics start polluting research synthesis. Extends the entity-aspects spec, not this one.
- **Configurable gap threshold**: move from the hardcoded `coverage < demand` rule to a tunable `knowledge_gaps: min_coverage_ratio: 0.5` or similar in `science.yaml`. Only if demand-weighted ranking proves too noisy or too narrow in practice.
- **Per-topic paper recommendation**: integration with external literature search to suggest specific papers for thin-coverage topics. Separate system; requires web-search or citation-database access. Do not bolt on to this feature.

## Open Decisions (to resolve during implementation)

- **Exact paper-directory discovery**: v1 scans `doc/papers/` and `doc/background/papers/`. If projects introduce other paper directories (e.g., `papers/`), discovery either hard-codes additional paths or adopts a lookup from `science.yaml` — defer until a real project requires it.
- **Bibtex parsing strictness**: `topic.source_refs: [cite:Smith2024]` is counted as one paper; malformed or non-`cite:` entries are ignored silently. If bibkey validation becomes worthwhile (e.g., typo-detection against an actual `.bib` file), add in a follow-up — do not couple this spec to a bibtex parser.
- **Ordering of "demanding_questions" list**: alphabetical by question ID for stable diffs, or reverse-chronological by question creation date (most-recent demand first)? v1 uses alphabetical; reconsider if users want "what's been asked recently" as the primary signal.
