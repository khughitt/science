---
numeric_claims:
  v1:
    artifact: summary.feather
    locator: {column: score}
  m1:
    artifact: per_disease.feather
    locator: {column: score, where: {disease: "MESH:D009101"}}
  o1:
    artifact: results.json
    locator: {opaque: "read off the appendix figure"}
  e1:
    artifact: missing-artifact.json
    locator: {pointer: /x}
  o2:
    artifact: missing-opaque.dat
    locator: {opaque: "see supplementary figure"}
  a1:
    artifact: per_disease.feather
    locator: {column: score, where: {disease: "DUP"}}
---

# Oracle fixture: bound claims and a control unbound number

Accuracy on the holdout set was **0.978**[^v1] overall, matching the summary table.

The reported association score for multiple myeloma was **0.50**[^m1] in the per-disease table, though the displayed figure differs from the underlying value.

As described in the appendix, the panel reading was **512**[^o1] units, transcribed by hand from a plot.

A separate figure claims **744**[^e1] from an artifact that does not exist on disk.

Another opaque figure shows **351**[^o2] pointing at a file that was never committed.

The duplicated-key row reports **0.60**[^a1] in the per-disease table, though the key is ambiguous.

Separately, and unrelated to any of the above bindings, the cohort included 482 patients across the enrollment sites.
