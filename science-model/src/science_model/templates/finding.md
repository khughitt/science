---
id: "finding:{{finding_id}}"
type: "finding"
title: "{{title}}"
confidence: "{{confidence}}"  # high | moderate | low | speculative
propositions:
  - "proposition:{{prop_id}}"
observations:
  - "observation:{{obs_id}}"
source: "data-package:{{source_id}}"
related: []
source_refs: []
---

## Summary

{{Brief description of what was found.}}

## Observations

<!-- List the concrete empirical facts this finding is based on. -->

- observation:{{obs_id}} -- {{description of observation}}

## Propositions

<!-- List the interpretive claims this finding makes. -->

- proposition:{{prop_id}} -- {{claim text}}

## Evidence

<!-- How do the observations bear on the propositions? -->

- observation:{{obs_id}} **supports** proposition:{{prop_id}} (strength: {{moderate}})
  - Caveats: {{any limitations}}

## Source

Data from: data-package:{{source_id}}
Analysis: workflow-run:{{run_id}} (if applicable)
