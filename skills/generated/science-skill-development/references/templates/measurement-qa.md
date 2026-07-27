---
name: <subject>-<operation>-qa
description: Use when ingesting or QA-reviewing <this data product>.
archetype: measurement-qa
provenance: internal
---

# <Data Product> QA

Answers: is this observed or derived measurement trustworthy for inference?

## Sources & ingestion/construction

<Where the data comes from and how it is ingested or constructed.>

## Pre-flight checklist

- [ ] <check 1>
- [ ] <check 2>

## QA metrics

| Metric | Passing range | Meaning of failure |
|---|---|---|
| <metric> | <range> | <what a failure invalidates> |

## Common failure modes

- <failure mode → symptom → what it invalidates>

## Halt-On Conditions

- <condition under which analysis must stop until resolved>

## Minimum output package

    <qa-output-dir>/
      summary.md
      metrics.tsv

## Success test

Does the produced QA package contain the named files, and does the summary state which Halt-On Conditions were evaluated?

## Companion Skills

- `../INDEX.md` — the skill index.
