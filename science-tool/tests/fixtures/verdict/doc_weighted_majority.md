---
id: "interpretation:fixture-weighted-majority"
verdict:
  composite: "[+]"
  rule: "weighted-majority"
  claims:
    - id: "n1"
      polarity: "[-]"
      weight: 1.0
    - id: "n2"
      polarity: "[-]"
      weight: 1.0
    - id: "n3"
      polarity: "[-]"
      weight: 1.0
    - id: "p1"
      polarity: "[+]"
      weight: 4.0
---

**Verdict:** [+] One load-bearing positive outweighs three weak negatives (4/7 strict majority under v1.2 tie rule).
