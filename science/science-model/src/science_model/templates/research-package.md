---
id: "research-package:<slug>"
type: "research-package"
title: "<Rendered analysis title>"
status: "active"

# What derived datasets this rendering bundle displays.
# MUST be symmetric with each dataset's consumed_by (state invariant #11).
displays: []                       # ["dataset:<slug>", ...]

location: ""                       # research/packages/<lens>/<section>/
manifest: ""                       # research/packages/<lens>/<section>/datapackage.yaml

# Narrative bundle (shape unchanged from legacy data-package; data resources removed).
cells: ""                          # path to cells.json
figures: []                        # [{name, path, caption}]
vegalite_specs: []                 # [{name, path, caption}]
code_excerpts: []                  # [{name, path, source, lines, github_permalink}]

related: []                        # ["workflow-run:<slug>", ...]
created: "<YYYY-MM-DD>"
updated: "<YYYY-MM-DD>"
---

# <Rendered analysis title>

## Summary

<What this rendering bundle illustrates and which derived datasets it draws from.>

## Related

- Workflow run: <workflow-run:slug>
- Datasets displayed: <dataset:slug>, ...
