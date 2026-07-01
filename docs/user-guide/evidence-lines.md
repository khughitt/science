# Evidence Lines

An `evidence-line` is a durable, reviewable line of support or dispute. It links
a source, result, observation, or interpretation to the proposition it bears on.

## Core Fields

```yaml
stance: supports
target: proposition:p01-example
source: paper:Example2026
evidence_type: empirical_data_evidence
strength: moderate
independence: independent
independence_group: example-cohort-1
evidence_role: direct_test
```

| Field | Purpose |
|---|---|
| `stance` | Whether the line `supports` or `disputes` the target. |
| `target` | The proposition or epistemic target being evaluated. |
| `source` | Citation, source entity, dataset, workflow run, or other provenance. |
| `evidence_type` | Kind of evidence. |
| `strength` | How strong this line is when honestly interpreted. |
| `independence` | Whether this line is independent of other lines. |
| `independence_group` | Shared group for lines that should not be double-counted as independent. |
| `evidence_role` | How directly this line tests the target. |

## Evidence Types

Common evidence types:

| Evidence Type | Use |
|---|---|
| `literature_evidence` | Prior publications, reviews, or meta-analyses. |
| `empirical_data_evidence` | Observed or experimental data. |
| `simulation_evidence` | Computational, mechanistic, or generative simulations. |
| `benchmark_evidence` | Benchmark tasks, evaluation suites, or standardized comparisons. |
| `expert_judgment` | Structured expert assessment. |
| `negative_result` | Valid compatibility token for a null or negative result; model the stance and scope carefully. |

Benchmark evidence lines should come from actual benchmark evaluations or
standardized comparisons. The current `science benchmark tests` command projects
read-only candidate test rows; it does not author evidence lines or benchmark
outcome records.

`negative_result` is accepted for compatibility, but it is usually better
understood as a result pattern. The line's `stance`, role, and scope should say
what the null or negative result does to the target proposition.

The typed evidence vocabulary is owned by the model enum. The canonical stored
tokens are `empirical_data`, `benchmark`, `simulation`, `literature`,
`expert_judgment`, and `negative_result`. Authoring may still use the historical
`_evidence` suffix for compatibility, such as `empirical_data_evidence` or
`expert_judgment_evidence`; Science strips that suffix at the model boundary
and stores the canonical member.

Unknown evidence types fail when parsed as authored evidence-line entities. Some
graph readers still read arbitrary literals from materialized graphs; those
readers use the same suffix normalizer but degrade unknown tokens to rank 0
rather than raising. Rank tables are reconciled against the model vocabulary:
`negative_result` is a valid but unranked member, while diagnostic roles remain
valid but unranked evidence roles.

## Authored Assertions

`expert_judgment` is the evidence type for authored assertions. In the belief
engine, an authored assertion is recognized only by normalized `evidence_type:
expert_judgment`; dataset usage is not inspected for that purpose. By authoring
convention, empirical lines use `empirical_data_evidence` or `empirical_data`
and carry `dataset_usage`, while authored assertions are dataset-less structured
judgments.

Authored assertions enter belief through a confidence gate:

```yaml
evidence_type: expert_judgment
confidence: 0.9
```

`confidence` must be present, numeric, and in `[0, 1]`. The default belief
policy admits authored assertions when `confidence >= 0.5`. Confidence is a
gate, not a weight: a passing assertion contributes one support or dispute unit;
`0.9` does not count more than `0.6`. Missing, out-of-range, or below-threshold
confidence does not count in belief aggregation and is reported as excluded
authored confidence.

Authored assertions can corroborate empirical evidence, but authored-only
support is capped by policy. Under the default policy, support made only of
authored assertions cannot exceed `fragile`, and the result records
`authored_capped` when that ceiling lowers the computed magnitude. Authored
disputes follow the same discipline: they may make a proposition contested, but
they are not qualifying direct tests and cannot act as decisive refutations.

Validation treats authored assertions differently from empirical scored lines.
An authored assertion with valid confidence does not need ordinary
role/strength scoring to be considered belief-admissible; an authored assertion
with missing or invalid confidence is a warning because it cannot pass the
belief gate.

## Independence

Multiple lines from the same cohort, instrument, source, or analysis family are
not independent just because they are written as separate files. Use the same
`independence_group` when support should be discounted as shared.

Orthogonal modality is not independence by itself. If two modalities share
patients, labels, derived annotations, preprocessing, or ground truth, record
that dependence instead of counting the lines as independent only because their
assays differ.

## Derived Literature Evidence

Some literature evidence is derived during graph materialization rather than
authored as files under `entities/evidence-lines/`. When active statement
annotations from papers have been promoted to the same `proposition:<slug>`,
Science derives virtual `sci:EvidenceLine` nodes from the promoted annotation
provenance. These nodes are URI-only, deterministic, and rebuildable from the
paper sidecars; do not create matching authored evidence-line files for them.

Only active `proposition` annotations with `promoted_to: proposition:<slug>`
participate. `question` and `hypothesis` promotions are valid but are not
literature evidence for a proposition. `fixed`, `dismissed`, and `superseded`
annotations are retained as history but do not contribute belief.

The stance mapping is:

| Statement stance | Derived edge | Evidence role | Strength |
|---|---|---|---|
| `asserted` | `cito:supports` | `proxy_support` | `moderate` |
| `negated` | `cito:disputes` | `proxy_support` | `moderate` |
| `hypothesized` | `cito:supports` | `background_constraint` | `weak` |
| `open` | skipped | - | - |

Derived literature evidence uses `evidence_type: literature` and
`independence: independent`. The `independence_group` is keyed by paper, so
multiple same-paper statements with the same proposition and stance collapse to
one unit. If the same paper both supports and disputes a proposition, both units
are retained in the same group, and belief aggregation records that group as
contested instead of silently choosing a winner.

Literature corroboration can move a proposition from speculative or fragile to
supported, but it cannot by itself make a proposition `well_supported`. That
state requires qualifying direct-test evidence, not only repeated statements in
papers.

This derived layer does not reconcile separately minted propositions that may
be paraphrases of the same claim, does not infer citation-graph independence
between papers, does not persist generated evidence-line files, and does not
grade strength from article section names. Those remain separate curation or
modeling problems.

## Dataset Usage

Empirical evidence lines should name the datasets they use with
`dataset_usage`. Belief-eligible empirical lines without `dataset_usage` are
validation errors. Use `belief_eligible: false` only as a staging marker for an
empirical line that exists but should not emit `cito:supports`/`cito:disputes`
or enter belief aggregation until dataset grounding is complete.

```yaml
dataset_usage:
  - ref: dataset:gtex-v8
    role: analyzed
    overlap: full
```

`ref` must be a `dataset:<slug>` reference. Roles are:

| Role | Interpretation |
|---|---|
| `analyzed` | The evidence depends directly on analysis of the dataset. |
| `set_definition_source` | The dataset supplied a set or collection definition. |
| `training` | The dataset trained or fit the model being evaluated. |
| `upstream` | The dataset is an upstream input to a derived artifact. |
| `validation_source` | The dataset was used for validation, not as the main dependence. |
| `cited` | The dataset is cited context rather than a dependence. |

`overlap` is `full`, `partial`, or `unknown`. Dependence roles
(`analyzed`, `set_definition_source`, `training`, and `upstream`) contribute to
dataset-derived independence. Full-overlap dependence on the same dataset, or
on ancestor/descendant datasets in a sub-cohort lineage, can become a
`shared-source` commitment. Partial or unknown overlap, validation-only,
citation-only, sibling sub-cohorts, virtual rows, and indirect bears-on paths
remain candidate warnings for review.

## Quantitative Results

An evidence line may carry a structured `quantitative_result` when a fitted
model or analysis produced effect-size or posterior information:

```yaml
quantitative_result:
  beta: 0.41
  hdi: [0.2, 0.6]
  prob_sign: 0.98
  fit_task: task:fit-example-model
  model: logistic_regression
```

This is evidence substance, not an authored belief state. Eligible quantitative
results can inform scalar belief projections, while the ordinary stance,
strength, independence, role, and dataset grounding fields still determine
whether the line is admissible.

## Worked Example

```markdown
---
id: evidence-line:sleep-extension-reaction-time-pilot
type: evidence-line
title: "Pilot trial reports faster reaction time after sleep extension"
status: active
stance: supports
target: proposition:p01-sleep-extension-reaction-time
source: paper:Example2026
evidence_type: empirical_data_evidence
strength: moderate
independence: independent
independence_group: sleep-extension-reaction-time-pilot
evidence_role: direct_test
---

# Pilot trial reports faster reaction time after sleep extension

The study reports faster next-day reaction time in the sleep-extension arm.
The line is a direct test of the proposition, but it remains only moderate
because the sample is small and replication is not yet available.
```
