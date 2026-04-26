---
name: research-lab-notebook
description: Use when rendering research-package materials into notebook-like review views, summaries, or inspection pages.
---

# Lab Notebook Views

Render research packages as notebook-like web pages within a project's web application. Builds on the research provenance skill (layer 1).

## When to Use

- When a web app should show "how we got here" for research-driven pages
- When implementing "view source" functionality for analysis-backed content

## Cell Rendering

Map each cell type to a web component:

| Cell Type | Rendering |
|-----------|-----------|
| narrative | Fetch markdown file, render with remark/rehype or similar pipeline |
| data-table | Parse CSV, render sortable/filterable table with column headers |
| figure | `<img>` with caption below |
| vegalite | Load .vl.json spec, render with `vega-embed` library |
| code-reference | Collapsible code block; "View on GitHub" link (graceful fallback when permalink is empty) |
| provenance | Metadata summary: workflow, config, commit, run date, scripts, inputs |

## Routing Pattern

Add sub-routes at `{path}/src` for any page backed by a data package:
- `/guide/theme/chaos` → guide content
- `/guide/theme/chaos/src` → research provenance view

The `/src` route should be more specific than the parent route in the router config.

## Manifest Pattern

A prebuild script:
1. Validates packages via `science-tool research-package validate`
2. Copies valid packages to the public/static assets directory
3. Generates a `manifest.json` mapping route keys to package metadata
4. The manifest is loaded once at app startup to determine which routes have research sources

## ViewSourceButton Pattern

A button component that:
1. Checks the manifest for the current route's lens/section
2. Renders nothing if no package exists
3. Shows a small icon button (e.g., science/flask icon) that navigates to the `/src` route

## DataPackageLoader Pattern

A runtime loader that:
1. Fetches `datapackage.json` and `cells.json` from the public directory
2. Validates the descriptor against the schema
3. Pre-loads CSV resources for data-table cells
4. Passes loaded data to the cell renderer

CSV parsing should handle RFC 4180 (quoted fields with commas).

## Data-Package Entity

Register a `web_route` data-package in the knowledge graph:
- `type`: `"web_route"`
- `target`: the rendered route path (e.g., `/guide/theme/chaos/src`)
- `grounded_by`: the source data-package canonical ID

## Reference Implementation

The natural-systems project (`src/research/`) provides a working TypeScript/React implementation with:
- `ResearchSourcePage.tsx` — route component
- `CellRenderer.tsx` — cell dispatch
- `DataPackageLoader.ts` — fetch + validate
- `ViewSourceButton.tsx` — conditional rendering
- Cell components in `cells/` — one per cell type
