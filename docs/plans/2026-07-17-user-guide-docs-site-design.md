# User Guide Docs Site + Figures — Design

**Date:** 2026-07-17
**Branch/worktree:** `docs/user-guide-site` in `.worktrees/user-guide-docs` (off `main`)
**Status:** Approved design; implementation plan to follow.

## Goal

Turn the existing `docs/user-guide/` Markdown (19 chapters, ~4,200 lines) into a
polished, published documentation site with a coherent set of illustrations that
share one visual vocabulary, and make it deploy to GitHub Pages automatically.

Three deliverables:

1. A MkDocs + Material static site built from the existing chapters, deployed to
   GitHub Pages via GitHub Actions on push to `main`.
2. A consistent figure system (color-by-class, shape-by-kind) applied across a
   prioritized set of diagrams that illustrate the key conceptual chapters.
3. A light prose-coherence pass: figure callouts, nav/cross-link parity, and a
   few tightened chapter intros — **no changes to technical claims**.

## Non-goals

- No deep chapter restructuring, merging, or rewriting (possible follow-up).
- No changes to belief semantics, entity classification, or any technical claim.
- No new root `pyproject.toml` (AGENTS.md forbids it).
- No exhaustive kind-registry reference figure (F0 is a compact reader's key).

## A. Site tooling & layout

- **`mkdocs.yml` at repo root**, with `docs_dir: docs/user-guide`. The site is
  *only* the user guide; the rest of `docs/` (audits, plans, conventions) stays
  internal and out of the site.
- **Dependencies** live in **`docs/requirements.txt`** (pinned `mkdocs-material`,
  `pymdown-extensions`). No root `pyproject.toml`. Local preview:
  `uv run --with-requirements docs/requirements.txt mkdocs serve`.
- **Theme:** `material` with:
  - Light/dark **palette toggle** (primary `indigo` to match the epistemic
    accent; toggle sets `[data-md-color-scheme]` on `<body>`).
  - Features: `navigation.sections`, `navigation.top`, `navigation.tracking`,
    `content.code.copy`, `toc.follow`, `search.suggest`, `search.highlight`.
  - `extra_css: [assets/palette.css]`.
- **Markdown extensions:** `admonition`, `pymdownx.superfences` (with a custom
  `mermaid` fence for Material's native diagram integration), `pymdownx.details`,
  `pymdownx.tabbed`, `attr_list`, `md_in_html` (required so hero SVGs can be
  inlined and themed by page CSS), `tables`, `toc` (permalinks).
- **Explicit `nav`** in reading-path order, including `codex.md` (currently
  missing from `index.md`'s reading path). Every chapter file appears exactly
  once.
- **Explicit `validation:` block** so strict CI is comprehensive, not just
  nav-shaped:
  ```yaml
  validation:
    nav:
      omitted_files: warn
      not_found: error
      absolute_links: warn
    links:
      not_found: error
      absolute_links: warn
      unrecognized_links: warn
      anchors: warn
  ```
- **Doc "test" = `mkdocs build --strict`**: any broken internal link, missing
  nav file, or bad anchor fails the build (and CI).
- **Assets** under `docs/user-guide/assets/`:
  - `palette.css` — the single source of truth for design tokens (CSS custom
    properties), styling both Material chrome and inlined SVGs, keyed on
    `[data-md-color-scheme="default"|"slate"]`.
  - `figures/*.svg` — bespoke hero figures (inlined into pages via `md_in_html`).

## B. Deploy

- **`.github/workflows/docs.yml`**:
  - Trigger: `push` to `main` touching `docs/**`, `mkdocs.yml`, or the workflow
    file; plus `workflow_dispatch`.
  - Steps: checkout → `actions/setup-python` → `pip install -r docs/requirements.txt`
    → `mkdocs build --strict` → publish with the **official GitHub Pages actions**
    (`actions/configure-pages`, `actions/upload-pages-artifact`,
    `actions/deploy-pages`). No `gh-pages` branch.
  - Permissions: `pages: write`, `id-token: write`, `contents: read`.
  - Concurrency group so overlapping deploys cancel cleanly.
- **One-time manual step (documented, not automatable here):** repo Settings →
  Pages → Source = "GitHub Actions."
- **Visibility:** `khughitt/science` is **public** (verified via `gh repo view`),
  so Pages is free — no paid-plan constraint.

## C. Visual design system

**Principle:** *color encodes entity **class**; shape encodes **kind**; relation
semantics and belief-state are separate, fixed accent systems that never collide
with class colors.* Authored entities and derived state look categorically
different.

Every hex below is defined once in `palette.css` and reused verbatim in mermaid
`classDef` blocks and SVG symbols. Each kind's class MUST be re-checked against
`science/model/src/science_model/profiles/core.py` before it is drawn — not
recalled from memory.

### Entity classes (authored)

| Class | Hue | Stroke | Light fill | Meaning |
|---|---|---|---|---|
| **Epistemic** | Indigo | `#4F46E5` | `#E0E7FF` | uncertain knowledge |
| **Operational** | Cyan | `#0891B2` | `#CFFAFE` | work products, sources, datasets, machinery |
| **Reference** | Warm stone | `#78716C` | `#E7E5E4` | concepts, variables, outcomes, referenced objects |

Dark-scheme fills are darker tints of the same hue (defined in `palette.css`);
strokes stay constant for recognizability.

### Fixed shape per kind

Only kinds that appear in the figures are listed; F0 shows exactly this subset.
Classes are authoritative from `core.py` (spot-checked: `report` is **epistemic**,
not operational).

| Kind | Class | Shape |
|---|---|---|
| question | epistemic | stadium / pill |
| hypothesis | epistemic | hexagon |
| **proposition** | epistemic | rounded rect, **heavier border** (the belief-bearing unit) |
| observation | epistemic | small circle |
| evidence-line | epistemic | parallelogram, tagged `+` / `−` |
| inquiry / patch-definition | epistemic | dashed rounded **container** (a neighborhood) |
| mechanism | epistemic | double-outline hexagon |
| report | epistemic | lined document |
| dataset | operational | cylinder |
| workflow / run | operational | chevron |
| source / paper | operational | dog-eared page |
| concept / variable / outcome | reference | notched tag |

### Derived state (NOT authored entities)

Rendered in a **ghosted/dashed "derived" style** — muted fill, dashed stroke, a
small "derived" marker — so they never read as authored source. Grouped in a
separate band of F0.

| Item | Rendering |
|---|---|
| belief | gauge ring (SVG) / diamond (mermaid), derived style |
| snapshot | stacked rectangle, derived style |
| knowledge graph / dashboards / health reports | ghosted panels |

### Relation accents (fixed, collision-free)

| Relation | Style |
|---|---|
| **supports** | solid green `#16A34A`, arrow |
| **disputes** | solid red `#DC2626`, arrow |
| plumbing / derived (contains, member, produces, bears_on) | slate `#94A3B8`, **dashed** |

`contested` is **not** a relation. Contestation, fragility, and uncertainty are
**belief-state axes**, rendered as overlays/annotations in the belief figures
(F4/F5) — never as edges. Belief *magnitude* uses an indigo-intensity ramp so it
stays in the epistemic family and never reads as support-green.

### Theming

- **Hero SVGs are inlined** into Markdown via `md_in_html` (raw `<svg>` blocks),
  so `palette.css` styles them and they follow Material's manual palette
  **toggle** (`[data-md-color-scheme="slate"] .figure-… { … }`), not merely OS
  `prefers-color-scheme`.
- **Mermaid** uses Material's native light/dark integration; per-diagram
  `classDef` blocks carry the same hexes.

## D. Figures (prioritized)

**Tier 1 — foundation**

- **F0 · Entity vocabulary reader's key** (inlined SVG) — the three authored
  classes, each kind's shape/color used in the figures, the derived-state band,
  and the relation accents. This is figure-zero and the design reference.
  Embedded near the top of `entities.md`; linked from a "how to read the figures"
  note in `big-picture.md`.
- **F1 · The belief spine** (mermaid) —
  `question → hypothesis → proposition → observation / evidence-line → belief → snapshot`,
  with belief/snapshot in derived style. → `big-picture.md`, `epistemic-model.md`.
- **F2 · Authored sources → derived views** (mermaid) — upgrade the existing
  `science-model.md` diagram with the palette; authored files (operational) →
  graph build → graph → {dashboards, snapshots, health}, derived items ghosted;
  emphasize "fix the source, rebuild." → `science-model.md`, `introduction.md`.

**Tier 2 — hero conceptual (bespoke inlined SVG)**

- **F3 · Patchwork of epistemic neighborhoods** — several dashed inquiry
  neighborhoods (focal hypothesis/question + member propositions/datasets), a
  **commons** of shared canonical owners, and peer projects synchronizing.
  → `big-picture.md`, `science-model.md`, `cross-project-work.md`.
- **F4 · Belief aggregation & ceilings** — evidence lines (support/dispute,
  independence groups) → proposition; reduction by independence & quality; the
  two ceilings (`expert_judgment` → `fragile`; dataset-QA-failed cap) and the
  refutation cap; the ordinal ladder speculative → fragile → supported →
  well_supported with contestation overlaid. → `epistemic-model.md`,
  `evidence-lines.md`.

**Tier 3 — supporting**

- **F5 · Belief vocabulary ladder** — the ordinal magnitude ladder with
  contestation/fragility/uncertainty as orthogonal overlays.
- **F6 · Inquiry as a neighborhood** — boundary-in/out, flow edges, minted
  assumption/transformation nodes, focal target. → `epistemic-model.md`.
- **F7 · Verdict-token legend** — `[+] [−] [~] [?] [⌀]` with meanings.
- **F8 · Entity anatomy** — `kind:id`, frontmatter = machine identity, body =
  human context. → `entities.md`.

Figures are implemented Tier 1 → Tier 3; the plan may checkpoint after each tier.

## E. Prose coherence pass (light — no claim changes)

- Add each figure with a one-line caption and a "how to read the figures"
  pointer to F0.
- Fix `index.md`: reading path and chapter table reach parity with the files
  (add `codex.md`); nav matches.
- Ensure every chapter is in nav and all internal cross-links resolve under
  `--strict`.
- Tighten a few chapter intros so each opens by orienting the reader. Wording of
  technical content is unchanged.

## F. File layout

```
mkdocs.yml                                  # new, repo root
docs/requirements.txt                       # new
.github/workflows/docs.yml                  # new
docs/user-guide/assets/palette.css          # new (design tokens, SoT)
docs/user-guide/assets/figures/*.svg        # new (hero figures)
docs/user-guide/*.md                         # edited: figure embeds, intros, links
docs/plans/2026-07-17-user-guide-docs-site-design.md   # this spec
```

## Risks / open items

- **Pages enablement** is a one-time manual repo setting; CI can build+`--strict`
  before it is enabled, so the workflow is safe to merge early.
- **SVG theming fidelity**: inlining + `md_in_html` is required; if a figure must
  be referenced as `<img>`, it can only follow OS `prefers-color-scheme`. Hero
  figures are therefore inlined.
- **Token duplication**: hexes live in `palette.css` but are copied into mermaid
  `classDef` blocks (mermaid can't read CSS vars). Accepted for v1; a small
  generator is possible later but is out of scope.
