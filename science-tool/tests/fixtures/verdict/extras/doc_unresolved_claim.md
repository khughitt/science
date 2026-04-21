---
id: "interpretation:fixture-unresolved"
type: "interpretation"
title: "Fixture: claim ID missing from registry (advisory warning case)"
status: "active"
created: "2026-04-21"
verdict:
  composite: "[+]"
  rule: "and"
  claims:
    - id: "hunknown#not-in-registry"
      polarity: "[+]"
      strength: "strong"
      evidence_summary: "this id is intentionally absent from the fixture registry"
---

## Verdict

**Verdict:** [+] Body agrees; parser should warn that the claim ID doesn't resolve.
