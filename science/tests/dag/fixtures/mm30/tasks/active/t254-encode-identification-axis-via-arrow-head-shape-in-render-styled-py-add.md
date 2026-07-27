---
id: t254
project: ''
title: Encode identification axis via arrow-head shape in _render_styled.py; add persistent
  footer legend strip to auto-PNG
type: ''
aspects:
- software-development
priority: P2
status: proposed
blocked_by: []
related:
- discussion:2026-04-19-dag-iteration-and-refinement
parent: ''
group: dag-refresh
artifacts: []
findings: []
created: '2026-04-20'
completed: null
---

Per discussion:2026-04-19-dag-iteration-and-refinement Q3. Currently _render_styled.py encodes identification via double-line color (interventional) and vee arrow (longitudinal); the [I]/[L] markers inside labels remain easy to miss. Proposal: use arrow-head shape alone (normal / diamond / odot) for the identification axis so that color (edge_status) and shape (identification) are independently legible. Add a persistent footer legend to the PNG so readers don't need README.md to decode.
