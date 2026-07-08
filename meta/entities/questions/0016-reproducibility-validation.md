---
id: question:0016-reproducibility-validation
kind: question
title: How should Science actively validate analysis reproducibility, and when should
  a reproduction verdict cap belief?
status: active
ontology_terms: []
datasets: []
source_refs: []
origins: []
related:
- question:0013-robustness-reproducibility-evaluation
- question:0004-source-and-pipeline-provenance
- hypothesis:0002-rich-evidence-payloads-improve-graph-calibration
- hypothesis:0007-working-model
- question:0017-benchmark-grounding-metrics
created: '2026-07-08'
updated: '2026-07-08'
---
# How should Science actively validate analysis reproducibility, and when should a reproduction verdict cap belief?

## Summary

Science enforces reproducibility of the knowledge *graph* (source content-hashing,
deterministic TriG, bundle integrity) but not of the *analyses* that produce
empirical evidence. This question asks how Science should **actively verify** that
a claimed-reproducible workflow really is reproducible — by re-executing it — and
when the resulting verdict should **cap belief**, mirroring the existing
dataset-QA ceiling.

This is distinct from `question:0013` / `task:t040`, which design how to
*represent* reproducibility claims as typed evaluation artifacts. Representation
without verification lets an unverified "reproducible" label carry the same weight
as a checked one.

## Why It Matters

- Decides whether the framing's creed ("believe nothing until we re-analyze the
  data ourselves") is backed by a mechanism, or is aspirational language over
  provenance bookkeeping.
- Decides whether a belief-eligible empirical evidence line must transitively
  resolve to a reproducible run record (code SHA, environment digest, input-data
  content hashes, parameters, seed policy, output hashes).
- Risk if unanswered: empirical belief rests on runs that nobody can re-execute;
  silent irreproducibility (e.g. an unseeded stochastic step) passes as strong
  support and inflates the graph.

## Current Evidence

- Enforced today: `SourceSnapshot` content-hashes source files; `graph_revision`
  carries a `semantic_hash`; `project_package` verifies per-file `sha256` and
  bundle `git_commit`. All concern the graph build, not analysis runs.
- Not enforced today: `EvidencePayloadCore.source_commit` is optional and not
  wired into `validate`; dataset `DerivationBlock.git_commit` is a bare string
  that accepts `""`, is caller-supplied not captured; no environment digest and no
  seed field exist anywhere in the evidence/run schemas.
- `workflow-run` entities pin `workflow` / `produces` / `inputs` / `manifest_path`
  and health check #9 enforces bidirectional referential integrity — but not
  code/env/data/seed pinning or any re-execution check.
- Precedent to reuse: the dataset-QA ceiling already turns a structural verdict
  over a resource into a belief cap; a reproduction verdict is the same pattern
  applied to a run.

## Thoughts

- Best current interpretation — two tiers plus a ceiling:
  - **Static lint (cheap, first):** over a pipeline plan, flag stochastic steps
    with no declared seed, unpinned environments, and uncaptured code SHA.
  - **Dynamic reproduction check:** rerun a workflow twice and compare outputs;
    for expensive workflows, use a **seeded subsample** as a reproduction smoke
    test.
  - **Verdict as ceiling:** track `unverified` / `self-consistent` /
    `independently-reproduced` / `failed` at the run/dataset/evidence level and
    cap belief accordingly, phased warn-only → eligibility gate so existing
    projects do not break on day one.
- A first-class analysis-run reproducibility contract is the durable owner of
  code SHA, environment digest, input-data hashes, parameters, seed policy, and
  output hashes; empirical belief-eligible evidence resolves to it directly or
  through its datasets.
- Major remaining uncertainty: how tolerant "same result" should be (bitwise vs
  within-tolerance numeric), how to bound subsample cost while preserving
  indicativeness, and whether the contract lives on the run entity, the evidence
  payload, or both.

## Connections to Project

- Related hypotheses: `hypothesis:0002-rich-evidence-payloads-improve-graph-calibration`,
  `hypothesis:0007-working-model`.
- Related questions: `question:0013-robustness-reproducibility-evaluation`
  (representation), `question:0004-source-and-pipeline-provenance` (run contract
  provenance), `question:0017-benchmark-grounding-metrics` (verdicts as belief
  inputs).
- Required analyses: run-reproducibility contract design; static repro lint;
  dynamic reproduction check with seeded subsample; reproduction verdict as belief
  ceiling. Tracked as the `reproducibility-validation` task group.
- Priority level: high — Phase-1 lead of the reproducibility/grounding roadmap.

## Related

- Roadmap: `doc/plans/2026-07-08-epistemic-reproducibility-and-grounding-roadmap.md`.
- Methods/Datasets: workflow re-execution, seeded subsampling, content hashing,
  reproducibility checklists.
