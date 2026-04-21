---
id: "interpretation:fixture-weighted-majority"
type: "interpretation"
title: "Fixture: weighted-majority rule with load-bearing minority"
status: "active"
created: "2026-04-21"
verdict:
  composite: "[+]"
  rule: "weighted-majority"
  claims:
    - id: "n1"
      polarity: "[-]"
      strength: "weak"
      weight: 1.0
      evidence_summary: "n1"
    - id: "n2"
      polarity: "[-]"
      strength: "weak"
      weight: 1.0
      evidence_summary: "n2"
    - id: "n3"
      polarity: "[-]"
      strength: "weak"
      weight: 1.0
      evidence_summary: "n3"
    - id: "p1"
      polarity: "[+]"
      strength: "strong"
      weight: 4.0
      evidence_summary: "load-bearing p1 — weight=4 yields 4/7≈0.571>0.5, a genuine strict majority"
---

## Verdict

**Verdict:** [+] One load-bearing positive outweighs three weak negatives (4/7 strict majority under v1.2 tie rule).
