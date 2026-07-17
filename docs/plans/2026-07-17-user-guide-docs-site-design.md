# User Guide Docs Site + Figures — Design

**Date:** 2026-07-17
**Branch/worktree:** `docs/user-guide-site` in `.worktrees/user-guide-docs` (off `main`)
**Status:** Proposed.

## Goal

Turn the existing `docs/user-guide/` Markdown (19 chapters, ~4,200 lines) into a
polished, published documentation site with a coherent set of illustrations that
share one visual vocabulary, and make it deploy to GitHub Pages automatically.

Three deliverables:

1. A MkDocs + Material static site built from the existing chapters, deployed to
   GitHub Pages via GitHub Actions.
2. A consistent figure system (color-by-class, shape-reinforces-kind-family)
   applied across a prioritized set of diagrams that illustrate the key
   conceptual chapters.
3. A light prose-coherence pass: figure callouts, nav/cross-link parity, and a
   few tightened chapter intros — **no changes to technical claims**.

## Non-goals

- No deep chapter restructuring, merging, or rewriting (possible follow-up).
- No changes to belief semantics, entity classification, or any technical claim.
- No new root `pyproject.toml` (AGENTS.md forbids it).
- No exhaustive kind-registry reference figure (F0 is a compact reader's key).

## A. Site tooling & layout

- **`mkdocs.yml` at repo root**, with `docs_dir: docs/user-guide`. The site is
  *only* the user guide; the rest of `docs/` stays internal and out of the site.
- **`site_url`** set to the published Pages URL
  (`https://khughitt.github.io/science/`); **`repo_url`** set to the GitHub repo
  so link-rewriting and "edit this page" work.
- **Dependencies** live in **`docs/requirements.txt`** (pinned `mkdocs-material`,
  `pymdown-extensions`). No root `pyproject.toml`. Local preview:
  `uv run --with-requirements docs/requirements.txt mkdocs serve`.
- **Theme:** `material` with:
  - Light/dark **palette toggle** (primary `indigo`; toggle sets
    `[data-md-color-scheme]` on `<body>`).
  - Features: `navigation.sections`, `navigation.top`, `navigation.tracking`,
    `content.code.copy`, `toc.follow`, `search.suggest`, `search.highlight`.
  - `extra_css: [assets/palette.css]`.
- **Markdown extensions:**
  - `admonition`, `pymdownx.details`, `pymdownx.tabbed`, `attr_list`, `tables`,
    `toc` (permalinks).
  - `pymdownx.superfences` with a custom `mermaid` fence (Material's native
    diagram integration).
  - `md_in_html` — permits Markdown parsing inside block HTML wrappers around
    inlined figures. (It does **not** import external files — see snippets.)
  - `pymdownx.snippets` — the mechanism that **imports figure source** into
    pages, with a constrained `base_path` (`docs/user-guide/assets`) and
    `check_paths: true` so a missing snippet fails the build. Hero SVGs are
    included as snippets; reused Mermaid diagrams are stored as `.mmd` files and
    included into a `mermaid` fence so each diagram has exactly one source.
- **Explicit `nav`** in reading-path order, including `codex.md` (currently
  missing from `index.md`'s reading path). Every chapter file appears once.
- **Explicit `validation:` block** (MkDocs accepts only `warn` | `info` |
  `ignore`; `--strict` promotes every `warn` to a build failure):
  ```yaml
  validation:
    nav:
      omitted_files: warn
      not_found: warn
      absolute_links: warn
    links:
      not_found: warn
      absolute_links: warn
      unrecognized_links: warn
      anchors: warn
  ```
- **Doc "test" = `mkdocs build --strict`**: any broken internal link, missing
  nav file, or bad anchor fails the build (and CI).
- **Cross-`docs_dir` link policy.** Seven user-guide links currently point into
  internal `docs/` content outside `docs_dir` (`../conventions/…`, `../process/…`,
  `../audits/…` in `cli-and-workflows.md`, `entities.md`,
  `graph-and-derived-state.md`, `project-packaging.md`). Strict builds reject
  these. Policy: **rewrite each as an absolute repository blob URL** (based on
  `repo_url`), since the targets are internal repo docs not published to the
  site. This policy is stated here and applied in §E. No internal doc is moved.
- **Assets** under `docs/user-guide/assets/`:
  - `palette.css` — the **canonical palette** (CSS custom properties), styling
    both Material chrome and inlined SVGs, keyed on
    `[data-md-color-scheme="default"|"slate"]`. Mermaid `classDef` blocks
    duplicate these hexes (mermaid cannot read CSS vars); `palette.css` is the
    canonical definition those copies must track, not a literal build-time SoT.
  - `figures/*.svg` — bespoke hero figures (imported via snippets).
  - `figures/*.mmd` — reused Mermaid diagram bodies.

## B. Deploy

**`.github/workflows/docs.yml`** — follows GitHub's recommended custom-workflow
contract with separated build and deploy jobs:

- **Triggers:** `push` to `main` and **`pull_request`** (both touching `docs/**`,
  `mkdocs.yml`, or the workflow), plus `workflow_dispatch`.
- **`build` job (all triggers):** checkout → `actions/setup-python` →
  `pip install -r docs/requirements.txt` → `mkdocs build --strict` →
  `actions/upload-pages-artifact` with **`path: site/`** (MkDocs outputs to
  `site/`; the action defaults to `_site/`, so the path is explicit). This job
  validates every PR.
- **`deploy` job:** `needs: build`, gated `if: github.ref == 'refs/heads/main'`
  (deploy only from `main`; PRs build but never deploy). Uses
  `actions/deploy-pages`, declares the **`github-pages` environment** with its
  deployment `url`.
- **Permissions:** `pages: write`, `id-token: write`, `contents: read`.
  **Concurrency:** a `pages` group so overlapping deploys cancel cleanly.
- **Pages enablement is a prerequisite for the deploy job, not optional.** Repo
  Settings → Pages → Source = "GitHub Actions" must be set **before** work merges
  to `main`, or the deploy job fails. The build job (on PRs) needs no Pages
  setting, so validation works before enablement — but do not merge to `main`
  until Pages is enabled.
- **Visibility:** `khughitt/science` is **public** (verified via `gh repo view`),
  so Pages is free.

## C. Visual design system

**Principle:** *color encodes entity **class**; **shape reinforces kind family**
and labels identify the exact kind; relation semantics and belief-state are
separate, fixed accent systems that never collide with class colors.* Authored
entities and derived state look categorically different. Shapes are shared within
a family (e.g. inquiry/patch-definition, workflow/run, concept/variable/outcome),
so the text label is always what pins the exact kind — the encoding is
family-level, not one-to-one.

Every hex below is defined in `palette.css` and copied verbatim into mermaid
`classDef` blocks and SVG symbols. Each kind's class MUST be re-checked against
`science/model/src/science_model/profiles/core.py` before it is drawn.

### Entity classes (authored)

| Class | Hue | Stroke | Light fill | Meaning |
|---|---|---|---|---|
| **Epistemic** | Indigo | `#4F46E5` | `#E0E7FF` | uncertain knowledge |
| **Operational** | Cyan | `#0891B2` | `#CFFAFE` | work products, sources, datasets, machinery |
| **Reference** | Warm stone | `#78716C` | `#E7E5E4` | concepts, variables, outcomes, referenced objects |

Dark-scheme fills are darker tints of the same hue (in `palette.css`); strokes
stay constant for recognizability.

### Shape per kind family

Only kinds that appear in the shipped figures are listed; F0 shows exactly this
subset. Classes are authoritative from `core.py` (spot-checked: `report` is
**epistemic**). Shared shapes are disambiguated by label.

| Kind | Class | Shape family |
|---|---|---|
| question | epistemic | stadium / pill |
| hypothesis | epistemic | hexagon |
| **proposition** | epistemic | rounded rect, **heavier border** (the belief-bearing unit) |
| observation | epistemic | small circle |
| evidence-line | epistemic | parallelogram, tagged `+` / `−` |
| inquiry / patch-definition | epistemic | dashed rounded **container** (a neighborhood) |
| report | epistemic | lined document |
| dataset | operational | cylinder |
| workflow / run | operational | chevron |
| source / paper | operational | dog-eared page |
| concept / variable / outcome | reference | notched tag |

### Derived state (NOT authored entities)

Rendered in a **neutral slate treatment with a solid outline and an explicit
`derived` badge** — visually distinct from authored source, but *not* ghosted or
dashed. (Ghosting reads as disabled/unimportant; dashed already means
neighborhood boundaries and plumbing.) Grouped in a separate band of F0.

| Item | Rendering |
|---|---|
| belief | gauge ring (SVG) / diamond (mermaid), slate + `derived` badge |
| snapshot | stacked rectangle, slate + `derived` badge |
| knowledge graph / dashboards / health reports | slate panels + `derived` badge |

### Relation accents (fixed, color-independent)

Arrows are legible without color: every support/dispute arrow carries a text
label, with color only reinforcing it.

| Relation | Style |
|---|---|
| **supports** | `+ supports`, solid green `#16A34A` arrow |
| **disputes** | `− disputes`, solid red `#DC2626` arrow |
| plumbing / derived (contains, member, produces, bears_on) | slate `#94A3B8`, **dashed** |

`contested` is **not** a relation and **not** a magnitude rung — it is a single
**boolean overlay** on a proposition where credible support and credible dispute
coexist, rendered as an annotation in F4. `fragile` is a magnitude rung on the
ordinal ladder, not an overlay. There are no separate "fragility"/"uncertainty"
output axes to draw. Belief *magnitude* uses an indigo-intensity ramp so it stays
in the epistemic family and never reads as support-green.

### Theming & accessibility

- **Hero SVGs are imported via `pymdownx.snippets`** into Markdown, so
  `palette.css` styles them and they follow Material's manual palette **toggle**
  (`[data-md-color-scheme="slate"] .figure-… { … }`), not merely OS
  `prefers-color-scheme`.
- **Mermaid** uses Material's native light/dark integration; per-diagram
  `classDef` blocks carry the same hexes.
- **Acceptance checks (every figure):** legible in **both** light and dark
  schemes; support/dispute distinguishable **without color** (labels); SVGs have
  a `<title>`/alt text; text contrast meets WCAG AA; figures are **responsive**
  (scale within the content column on narrow viewports).

## D. Figures (shipped set: F0–F4 + F8)

**Tier 1 — foundation**

- **F0 · Entity vocabulary reader's key** (imported SVG) — the three authored
  classes, each kind's shape/color used in the figures, the derived-state band
  (slate + `derived` badge), and the labeled relation accents. Figure-zero and
  the design reference. Embedded near the top of `entities.md`; linked from a
  "how to read the figures" note in `big-picture.md`.
- **F1 · The belief spine** (mermaid) — **not** a forward pipeline. A question
  *frames*; a hypothesis *organizes* the central proposition; observations and
  evidence-lines **bear on** the proposition (arrows converge **into** it, not
  through it); belief is **derived from** the proposition; a snapshot **persists**
  the belief. Derived items in slate + `derived` badge. → `big-picture.md`,
  `epistemic-model.md`.
- **F2 · Authored sources → derived views** (mermaid) — upgrade the existing
  `science-model.md` diagram with the palette. **Authored records span all three
  classes** (epistemic, operational, reference) — not "operational files." They
  feed graph build → graph → {dashboards, snapshots, health}, with derived items
  in slate + `derived` badge; emphasize "fix the source, rebuild." →
  `science-model.md`, `introduction.md`.

**Tier 2 — hero conceptual (bespoke imported SVG)**

- **F3 · Patchwork of epistemic neighborhoods + commons** — several dashed
  inquiry neighborhoods (focal hypothesis/question + member propositions/
  datasets). Beyond one project, show three *distinct* cross-project relations,
  not a generic "sync": **(a) peer graph composition** (a peer's graph composed
  in), **(b) registry indexing** (projects discovered/indexed via the registry),
  and **(c) borrowing commons owners** (a project referencing a shared canonical
  owner in the commons). → `big-picture.md`, `science-model.md`,
  `cross-project-work.md`.
- **F4 · Belief aggregation & ceilings** — evidence lines (labeled
  support/dispute, grouped by independence) **bear on** a proposition; reduction
  by independence & quality; the two ceilings — the **authored-only support
  ceiling** (a proposition whose support is authored-only cannot exceed
  `fragile`) and the **dataset-QA-failed cap** — and the **refutation cap** (a
  decisive, independent, whole-claim **direct** test can cap stronger support to
  `fragile`). Includes the ordinal ladder speculative → fragile → supported →
  well_supported, with **contestation as a boolean overlay**. → `epistemic-model.md`,
  `evidence-lines.md`.

**Tier 3 — supporting**

- **F8 · Entity anatomy** (imported SVG) — `kind:id`; frontmatter = machine
  identity, body = human context. Simple and high-value for onboarding. →
  `entities.md`.

**Cut / deferred:**

- **F5 (belief ladder)** — **cut**; F4 already contains the ladder.
- **F6 (inquiry as a neighborhood)** — **deferred** until the foundation is
  proven; it also needs assumption/transformation shapes absent from F0.
- **F7 (verdict-token figure)** — **cut as a figure**; the existing verdict-token
  **table** in `epistemic-model.md` is clearer and more accessible. If a callout
  is ever added, it must use canonical ASCII `[-]`, never Unicode `[−]`.

## E. Prose coherence pass (light — no claim changes)

- Add each shipped figure with a one-line caption and a "how to read the figures"
  pointer to F0.
- Fix `index.md`: reading path and chapter table reach parity with the files
  (add `codex.md`); nav matches.
- **Apply the cross-`docs_dir` link policy (§A):** rewrite the seven `../`
  links into internal `docs/` content as absolute repository blob URLs so the
  strict build passes. No internal doc is moved.
- Ensure every chapter is in nav and all internal cross-links resolve under
  `--strict`.
- Tighten a few chapter intros so each opens by orienting the reader. Wording of
  technical content is unchanged.

## F. File layout

```
mkdocs.yml                                  # new, repo root
docs/requirements.txt                       # new
.github/workflows/docs.yml                  # new
docs/user-guide/assets/palette.css          # new (canonical palette)
docs/user-guide/assets/figures/*.svg        # new (F0, F3, F4, F8)
docs/user-guide/assets/figures/*.mmd        # new (F1, F2 mermaid bodies)
docs/user-guide/*.md                         # edited: figure embeds, intros, links
docs/plans/2026-07-17-user-guide-docs-site-design.md   # this spec
```

## Risks / open items

- **Pages enablement** must precede any merge to `main` (deploy job fails
  otherwise). PR builds validate without it.
- **SVG theming fidelity**: snippets-import + page CSS is required to follow the
  manual toggle; an `<img>`-referenced SVG could only follow OS
  `prefers-color-scheme`. Hero figures are therefore imported, not linked.
- **Palette duplication**: hexes live in `palette.css` (canonical) but are copied
  into mermaid `classDef` blocks. Accepted for v1; a small generator is possible
  later but is out of scope.
