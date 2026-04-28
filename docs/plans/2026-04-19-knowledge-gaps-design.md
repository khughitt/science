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
- **Aspect filter is explicit at the call boundary.** `resolve_questions()` currently returns all questions plus resolved aspects; it does not itself filter out software-only questions. Knowledge-gap computation therefore accepts the caller's filtered question-ID set explicitly rather than assuming the input dict has already been trimmed.
- **Canonicalize path and prefix variants at load boundaries.** Topic discovery must tolerate both `doc/topics/` and `doc/background/topics/`; paper discovery must tolerate both `doc/papers/` and `doc/background/papers/`; external-literature IDs must tolerate both `paper:` and legacy `article:` during the transition window.

## Scope

### In scope (v1)

- New module `science_tool.big_picture.knowledge_gaps` with `compute_topic_gaps`, `TopicGap` dataclass.
- New `science-tool big-picture knowledge-gaps` CLI subcommand emitting JSON for inspection.
- Per-hypothesis bundle assembly gains a `topic_gaps` slice; hypothesis-synthesizer agent renders it in Research Fronts.
- Project rollup gains a Knowledge Gaps section; Opus orchestrator computes and renders it.
- Coverage metric: inclusive (union of entity-linked papers + bibtex `source_refs:` citekeys), deduplicated by bibkey where determinable.
- Gap criterion: `demand(T) > 0 AND coverage(T) < demand(T)`. Topics with `demand == 0` are excluded as research-irrelevant.
- Dual-path discovery for topics and papers: scan both current and legacy background directories, deduplicate by entity ID, and fail fast on duplicate IDs with conflicting files.
- Big-picture validator support for topic refs emitted by this feature.
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

Single-PR landing with the rename spec: both specs MAY land in one PR. In that case, knowledge-gaps tests work on three project states: (a) pre-migration projects via `article:` acceptance, (b) post-migration projects via canonical `paper:`, (c) mixed-state projects during partial migration. The migration-tool ship + dual-acceptance decouple the spec landings from any project's migration timing.

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

Dedup: the three sets are unioned with bibkey-based comparison where determinable. A `paper:<bibkey>` entity and a `cite:<bibkey>` citation referencing the same bibkey count as one paper. Bibkey extraction follows the canonical rule defined in the manuscript + paper rename spec (§Canonical bibkey extraction): the full substring after the first `:`, case-sensitive byte equality, no normalization. When a citekey cannot be extracted from an entity ID, dedup falls back to entity-ID string equality.

Note on `T.source_refs`: topics do not conventionally carry `source_refs:` in tracked projects today (the field lives mostly on question/interpretation entities). The `bibtex_refs(T)` union term exists to handle projects that do or will. If tracked projects never populate this field, the term is a no-op but harmless.

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

`hypotheses` is derived from the resolver output. Concrete rule: a hypothesis `h` is associated with a topic `T` iff any question bucketed under `h` by `resolve_questions` (whether via its `primary_hypothesis` field or any additional related-hypothesis field the resolver already honors) has `T.id ∈ q.frontmatter.related`. No new linkage logic — reuse whatever `resolve_questions` already returns under `h.question_ids`; the knowledge-gaps module does not re-implement hypothesis↔question bucketing.

`demanding_questions` and `hypotheses` are sorted alphabetically for stable JSON and markdown diffs.

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

Ordering: `gap_score` descending; ties broken alphabetically by topic ID. No cap on the number of topic lines — hypothesis-local lists are usually short. If zero gaps, the sub-bullet is omitted entirely.

Rendering rule for `demanding_questions` inline list: if the list exceeds 5 IDs, show the first 5 (alphabetical) followed by `… and N more`. The full list remains in `TopicGap.demanding_questions` and in the CLI JSON emission. Rationale: a heavily-investigated topic can drive 20+ questions; wall-of-text markdown obscures the signal this feature exists to surface.

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
    included_question_ids: set[str],
) -> list[TopicGap]:
    """Return all topics with demand > 0 and coverage < demand.

    Sorted by gap_score descending; ties broken by topic_id ascending.
    """
```

Pure function with only file-reading side effects. Loads:

- Every topic file from `doc/topics/` and `doc/background/topics/` if present — frontmatter + `related:` + `source_refs:`.
- Every paper file from `doc/papers/` and `doc/background/papers/` if present — frontmatter + `related:`. Accepts both `paper:<bibkey>` and `article:<bibkey>` entity prefixes during the transition window.
- Every question file from `doc/questions/` — frontmatter + `related:` — for demand computation.

Loader rules:

- If the same entity ID appears in two topic files or two paper files across the scanned directories, raise a clear error naming both paths. Silent "first one wins" behavior is not acceptable here because it would make the coverage metric non-deterministic.
- Normalize external-paper IDs to canonical `paper:<bibkey>` before dedup/counting.
- A question's `related:` entry of the form `topic:<id>` that does not match any loaded topic file is NOT counted toward demand. Emit one warning per unknown ID via `logging.getLogger(__name__).warning(...)`; do not raise. Dangling-reference enforcement is the big-picture validator's domain (`science_tool.big_picture.validator.validate_synthesis_file`); knowledge-gaps does not duplicate it.
- `source_refs:` entries that do not match the `cite:<key>` shape are logged at warning level (one warning per malformed entry) and excluded from coverage. This is a deliberate narrow exception to the fail-early principle: citation entries are user-authored free-text and occasional malformedness should not block knowledge-gap reporting across an entire project.

No dependency on the resolver module beyond its `ResolverOutput` type — the function does not call `resolve_questions` itself. The caller computes resolver output once, derives `included_question_ids` using the same aspect filter as the rest of big-picture synthesis, then passes both in.

### Bundle-assembly integration

`commands/big-picture.md` Phase 1 gains a new bundle slice. The **Opus orchestrator** (running Phase 1 and Phase 3) is the sole caller of `compute_topic_gaps`; per-hypothesis bundles do not re-invoke it.

```
included_question_ids: the exact set of question IDs already computed
                       upstream in Phase 1 by the big-picture aspect filter
                       — reuse that variable, do NOT reimplement the filter.

topic_gaps: compute_topic_gaps(project_root, resolved_questions, included_question_ids),
            filtered per hypothesis to topics in that hypothesis's subgraph.
            A topic is in the subgraph iff any question bucketed under the
            hypothesis (see TopicGap.hypotheses rule) references the topic.
```

Invocation discipline: exactly one call to `compute_topic_gaps` per big-picture run. The orchestrator invokes it once, slices the result per hypothesis for Phase 1 bundles, and reuses the full list for the Phase 3 rollup table. This guarantees per-hypothesis and rollup views stay consistent.

The hypothesis-synthesizer agent prompt gains one new instruction: "If the bundle includes `topic_gaps`, render them as a Knowledge Gaps sub-bullet inside Research Fronts, following the format in the spec."

### Rollup-phase integration

`commands/big-picture.md` Phase 3 (Opus orchestrator) gains:

- Call `compute_topic_gaps(project_root, resolved_questions, included_question_ids)` once to get the full project list.
- Render the top 10 into a new Knowledge Gaps section inserted between Research Fronts and Emergent Threads.
- If zero gaps, emit the "No knowledge gaps detected this run." one-liner and skip the table.

### CLI surface

New subcommand in the existing `big-picture` click group:

```
science-tool big-picture knowledge-gaps [--project-root <path>] [--limit N]
```

Emits JSON of all `TopicGap` entries, sorted by `gap_score` descending. `--limit N` caps the JSON list to the top N entries (useful when a project has many topics and the caller just wants the worst offenders). Default is no limit — emits all gap-flagged topics. The rollup markdown render in Phase 3 applies its own fixed cap of 10 regardless of the CLI flag, keeping the synthesis table compact.

By default the subcommand applies the same research-only aspect filtering used by big-picture synthesis before computing demand. Useful for validation, debugging, and for users who want the numbers without running a full big-picture regeneration. Parallel in shape to the existing `resolve-questions` subcommand.

## Validator Integration

Because this feature emits `topic:<id>` references in generated synthesis markdown, `science_tool.big_picture.validator` must be extended in the same PR:

- `REFERENCE_PATTERN` includes `topic` in addition to the currently supported reference kinds.
- `_collect_project_ids` scans topic directories (`doc/topics/`, `doc/background/topics/`) so validator lookups can succeed.

This spec does not require validator support for `paper:` references because the generated knowledge-gap sections do not directly emit paper entity IDs.

## Aspect Integration

Knowledge-gap computation sits downstream of the aspect-filter cascade established by the entity-aspects spec:

- The caller passes the full `resolved_questions` map plus an explicit `included_question_ids` set derived from the same research-aspect filter used elsewhere in big-picture synthesis.
- `demand(T)` therefore counts only questions in `included_question_ids`.
- A topic referenced only by software-only questions will have `demand == 0` in the filtered view and will be excluded from output.
- Papers are not aspect-filtered — all papers contribute to `coverage(T)` regardless. (A "software paper" covering a research topic still counts as coverage.)

Topics themselves do not gain an `aspects:` field in this spec. If a need emerges (e.g., software-specific topics flooding research synthesis), it extends the entity-aspects spec, not this one.

## Testing

### Fixture extension

Extend `science-tool/tests/fixtures/big_picture/minimal_project/`:

- Add `doc/background/topics/t01-covered.md` — `aspects:` inherited, `related: [paper:p01-example]`.
- Add `doc/background/topics/t02-thin.md` — `related: []`, `source_refs: []`. No coverage.
- Add `doc/background/topics/t03-bibtex-covered.md` — `related: []`, `source_refs: [cite:Smith2024]`. Coverage via bibtex only.
- Add `doc/background/topics/t04-legacy-covered.md` — `related: []`, `source_refs: []`. Coverage arrives via a legacy-prefixed paper file.
- Add `doc/papers/p01-example.md` — `id: paper:p01-example`, `related: [topic:t01-covered]`.
- Add `doc/papers/p02-legacy-article.md` — `id: article:p02-legacy-article`, `related: [topic:t04-legacy-covered]`. Exercises the transition-window `article:` prefix acceptance path (`test_article_prefix_accepted_during_transition`). Keep this file as long as the dual-prefix acceptance does.
- Update `doc/questions/q01-direct-to-h1.md` and `q02-inverse-via-h1.md` to include topic references in `related:`. Exact seeding:
  - `t01-covered`: demand=1, coverage=1 (no gap)
  - `t02-thin`: demand=2, coverage=0 (gap_score=2)
  - `t03-bibtex-covered`: demand=1, coverage=1 (no gap)
  - `t04-legacy-covered`: demand=1, coverage=1 via `article:p02-legacy-article` (no gap; transition-window alias counts)

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
- `test_duplicate_topic_ids_across_topic_directories_raise` — same `topic:<id>` appears in `doc/topics/` and `doc/background/topics/`; computation fails loudly rather than picking one arbitrarily.
- `test_duplicate_paper_ids_across_paper_directories_raise` — same `paper:<id>` appears in both paper roots; computation fails loudly.

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

- **Bibtex parsing strictness**: `topic.source_refs: [cite:Smith2024]` is counted as one paper; malformed or non-`cite:` entries are ignored silently. If bibkey validation becomes worthwhile (e.g., typo-detection against an actual `.bib` file), add in a follow-up — do not couple this spec to a bibtex parser.
- **Ordering of "demanding_questions" list**: alphabetical by question ID for stable diffs, or reverse-chronological by question creation date (most-recent demand first)? v1 uses alphabetical; reconsider if users want "what's been asked recently" as the primary signal.
