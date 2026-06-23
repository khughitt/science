---
id: "report:{{NNNN}}-bias-audit-{{slug}}"
type: "report"
title: "Bias Audit: {{Short Title}}"
status: "proposed"
source_refs: []
related: []
created: "{{YYYY-MM-DD}}"
updated: "{{YYYY-MM-DD}}"
---

# Bias Audit: {{Short Title}}

## Scope

<!-- What area of the project is this audit focused on?
A specific hypothesis, inquiry, pipeline, or the most recently active area. -->

## Cognitive Biases

### Confirmation Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are you seeking/citing evidence that supports your preferred hypothesis disproportionately? Are disconfirming papers absent from your searches? -->

### Anchoring

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are early conclusions or first-read papers over-weighted? Has the framing shifted since the project started? -->

### Availability Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are you over-relying on familiar methods, datasets, or frameworks? -->

### Sunk Cost

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are you pursuing a hypothesis or approach because of effort invested rather than evidence? -->

### Process Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Assess the research process itself:
  - Pace of iteration: rapid single-analyst iteration creates momentum bias
  - Perspective diversity: has anyone else reviewed the findings?
  - Cooling-off period: how much time elapsed between analysis and interpretation?
  - Pattern: many commits in a short period without external review? -->

## Methodological Biases

### Selection Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- In literature selection, data inclusion/exclusion, or method choice. -->

### Survivorship Bias

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Are you only seeing studies/datasets/methods that "worked"? -->

### HARKing

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Do current hypotheses match pre-registration? If no pre-registration exists, flag this. -->

### Multiple Comparisons / p-hacking Risk

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- How many analyses are planned? Is there correction? -->

### Confounding

- **Rating:** not detected / possible / likely
- **Evidence:** <!-- Cross-reference causal DAG if available; otherwise check for uncontrolled variables. -->

#### Confound Severity Matrix

<!-- For each identified confound, rate severity and fixability.
HIGH severity + EASY fix → address before running experiments.
MED severity + INFEASIBLE → acknowledge as limitation.

| Confound | Severity | Fixability | Mitigation |
|---|---|---|---|
| _confound_ | HIGH/MED/LOW | EASY/HARD/INFEASIBLE | _action_ |
-->

### Publication Bias

- **Rating:** not detected / possible / likely / not applicable
- **Evidence:** <!-- Is the literature search biased toward positive results?
  For in-progress experimental projects (not systematic literature review),
  assess whether literature searches for context/methods are biased toward
  positive results. Mark "not applicable" if the project doesn't involve
  literature review. -->

### Corpus Independence (Closure Check)

- **Rating:** not detected / possible / likely / not applicable
- **Artifacts under audit:** <!-- list the artifacts being audited together -->
- **Shared corpus:** <!-- the papers / datasets / prior runs that all of the above depend on -->
- **Independent evidence sources:** <!-- benchmarks, datasets, or literature outside the shared corpus that could disconfirm any artifact -->
- **Verdict:** <!-- Mark HIGH-severity if no independent evidence source exists: the audit can ratify but not falsify by construction. Mitigations: introduce an out-of-corpus benchmark, split into single-artifact passes, or downgrade the audit verdict from "validated" to "internally consistent". -->

## Summary

- **Overall threat level:** low / moderate / elevated / high
- **Top mitigations:**
  1. <!-- Highest priority mitigation -->
  2. <!-- Second priority -->
  3. <!-- Third priority -->
- **Recommended next actions:** <!-- What to do about the identified threats -->
