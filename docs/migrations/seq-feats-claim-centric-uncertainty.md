# Seq-Feats Claim-Centric Uncertainty Migration Guide

Project: `/home/keith/d/seq-feats`

## Why This Project Needs Migration

`seq-feats` already has a rich `science` graph, but much of the epistemic state still lives in:

- long hypothesis documents under `specs/hypotheses/`
- interpretation writeups under `doc/interpretations/`
- authored `confidence` values in `knowledge/sources/project_specific/entities.yaml`

That makes the project readable, but it still compresses too much reasoning into hypothesis-level prose and scalar confidence. The claim-centric model is a good fit here because the project already has many distinct lines of support, dispute, and retraction-like updates that should not be flattened into one hypothesis verdict.

## Current Shape

Relevant files:

- `/home/keith/d/seq-feats/specs/hypotheses/h01-raw-feature-embedding-informativeness.md`
- `/home/keith/d/seq-feats/specs/hypotheses/h02-phenotype-predictive-feature-discovery.md`
- `/home/keith/d/seq-feats/specs/hypotheses/h03-periodic-structure-in-embedding-space.md`
- `/home/keith/d/seq-feats/specs/hypotheses/h04-cross-dataset-robustness.md`
- `/home/keith/d/seq-feats/doc/interpretations/`
- `/home/keith/d/seq-feats/doc/questions/`
- `/home/keith/d/seq-feats/knowledge/sources/project_specific/entities.yaml`
- `/home/keith/d/seq-feats/knowledge/sources/project_specific/relations.yaml`

Observed migration pressure:

- hypotheses contain many separate assertions with different evidential status
- interpretations already contain concrete experimental results that can become evidence items
- `entities.yaml` still uses authored confidence directly on hypotheses/questions
- `relations.yaml` is currently empty, so most project reasoning is still prose-first

## Migration Goal

Keep `H01`-`H04` as organizing hypotheses, but decompose them into explicit `claim` / `relation_claim` units and attach typed evidence from existing experimental writeups.

The target outcome is:

- hypotheses become claim bundles
- interpretation docs become evidence sources
- benchmark runs and residualization analyses become `empirical_data_evidence`
- literature summaries remain `literature_evidence`
- known invalidations/retractions become explicit disputing evidence, not just revised prose

## Recommended First Migration Targets

Start in this order:

1. `H01` in `/home/keith/d/seq-feats/specs/hypotheses/h01-raw-feature-embedding-informativeness.md`
2. the strongest interpretation docs under `/home/keith/d/seq-feats/doc/interpretations/`
3. the controls/confound questions under `/home/keith/d/seq-feats/doc/questions/`
4. only then `H02`-`H04`

Reason:

- `H01` already contains explicit predictions, falsifiability clauses, and mixed support/dispute evidence
- several interpretation docs already describe concrete benchmark outcomes and invalidations
- the project’s major uncertainty is not whether evidence exists, but how to separate biological signal from composition, architecture, and tokenization confounds

## Suggested Claim Decomposition

Do not migrate `H01` as one monolithic belief object. Split it into narrower claims such as:

- certain feature classes show embedding signal beyond composition-matched controls
- protein evidence survives token-frequency baselines
- DNA evidence survives token-frequency baselines
- random-init comparisons can distinguish architecture from pretraining
- feature identity signal is stronger than function-specific signal

These should become separate relation claims or explicit claims, because the current project history already shows different outcomes for each.

## Evidence Migration Rules

Use these mappings:

- benchmark and analysis results from `/home/keith/d/seq-feats/doc/interpretations/` -> `empirical_data_evidence`
- negative residualization / confound findings -> `negative_result` or disputing `empirical_data_evidence`
- methodological concerns from `/home/keith/d/seq-feats/doc/questions/` -> usually not evidence themselves; use them to motivate missing-evidence or uncertainty notes
- prior papers cited in hypotheses/background -> `literature_evidence`

Important:

- do not convert every paragraph into a claim
- convert only assertions that you expect to compare, support, dispute, or prioritize
- when one interpretation invalidates an earlier reading, record that as disputing evidence instead of silently rewriting the hypothesis story

## Concrete Migration Steps

1. Remove reliance on authored confidence in `/home/keith/d/seq-feats/knowledge/sources/project_specific/entities.yaml` for `H01`-`H04`.
2. Create first-pass `relation_claim` records for the highest-value `H01` assertions.
3. Link the strongest interpretation docs as evidence-bearing sources.
4. Classify each evidence line as `literature_evidence`, `empirical_data_evidence`, or `negative_result`.
5. Mark unresolved areas explicitly as weakly supported or single-source rather than “low confidence”.
6. Use questions like `Q37`, `Q42`, `Q47`, and `Q48` to drive missing-evidence panels rather than to stand in for evidence.

## Success Criteria

The migration is successful when:

- `H01` can be summarized as a bundle of narrower claims with mixed evidential states
- invalidating interpretations appear as disputing evidence instead of only prose revisions
- the dashboard can distinguish:
  - protein-supported areas
  - DNA-contested areas
  - claims with no empirical support
  - claims that are still single-source

## Recommended Validation Commands

Run in `/home/keith/d/seq-feats`:

```bash
uv run --frozen science-tool graph audit --project-root . --format json
uv run --frozen science-tool graph build --project-root .
uv run --frozen science-tool graph validate --format json --path knowledge/graph.trig
uv run --frozen science-tool graph dashboard-summary --path knowledge/graph.trig --format json
```

## Main Risk

The biggest migration mistake here would be over-aggregating. `seq-feats` has already produced genuine support, genuine invalidation, and ambiguous methodological lessons. If those all collapse back into one hypothesis confidence score, the migration will fail semantically even if the files validate.
