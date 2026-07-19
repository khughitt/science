---
numeric_claims:
  p1:
    artifact: per_disease.feather
    locator: {column: score, where: {disease: "MESH:D003924"}}
  orphan1:
    artifact: summary.feather
    locator: {column: score}
  dup1:
    artifact: summary.feather
    locator: {column: score}
---

# Oracle fixture: percent claims and binding-declaration errors

The share of cases meeting criteria was **13%**[^p1] of the enrolled cohort.

The claim declared under `orphan1` in the frontmatter is never pinned to a marker anywhere in this body, which is exactly the point.

A duplicated pin: first the value was **210**[^dup1] and later restated as **330**[^dup1] in the same document.
