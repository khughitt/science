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

`negative_result` is accepted for compatibility, but it is usually better
understood as a result pattern. The line's `stance`, role, and scope should say
what the null or negative result does to the target proposition.

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
