# User Guide Docs Site + Figures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `docs/user-guide/` as a polished MkDocs + Material site on GitHub Pages, with a coherent, theme-aware figure system illustrating the key conceptual chapters.

**Architecture:** `mkdocs.yml` at repo root with `docs_dir: docs/user-guide`. Figures are theme-aware: bespoke SVGs are imported into pages with `pymdownx.snippets` and colored by CSS custom properties in `assets/palette.css` (so they follow Material's light/dark toggle); reused Mermaid diagrams live in `.mmd` files and use Material's native diagram integration. A two-job GitHub Actions workflow builds on every PR (`mkdocs build --strict`) and deploys to Pages only from `main`.

**Tech Stack:** MkDocs, Material for MkDocs, PyMdown Extensions (both **exactly pinned** in `docs/requirements.txt`, resolved at implementation), GitHub Pages via GitHub Actions, SVG, Mermaid.

**Design source of truth:** `docs/plans/2026-07-17-user-guide-docs-site-design.md` (Approved).

## Global Constraints

- No root `pyproject.toml` (AGENTS.md). Docs deps live only in `docs/requirements.txt`.
- Python floor `>=3.11`; CI uses Python `3.12`.
- No AI-attribution trailers/footers on commits (user global rule). Conventional-commit subjects, prefix `docs(user-guide):` (or `ci:` for the workflow).
- In docs/code prose, write filesystem paths as `~/d/…`, never `/home/keith/…` or `/mnt/ssd/Dropbox/…`.
- Canonical palette hexes (defined once in `assets/palette.css`; copied verbatim into every Mermaid `classDef` and SVG): epistemic stroke `#4F46E5` / light fill `#E0E7FF`; operational stroke `#0891B2` / light fill `#CFFAFE`; reference stroke `#78716C` / light fill `#E7E5E4`; derived stroke `#64748B` / light fill `#F1F5F9`; support `#16A34A`; dispute `#DC2626`; plumbing `#94A3B8`.
- Each kind's entity **class** MUST be re-checked against `science/model/src/science_model/profiles/core.py` before drawing (spot-checked: `report` is **epistemic**). `belief` and `snapshot` are **derived**, not entity kinds.
- Support/dispute must be legible **without color**: every such arrow carries a text label (`+ supports` / `− disputes`); color only reinforces.
- Derived state uses **neutral slate + solid outline + a `derived` badge**, never ghosting or dashing (dashing is reserved for neighborhood boundaries and plumbing edges).
- Verdict tokens, if ever written, use canonical ASCII `[-]`, never Unicode `[−]`.
- All work happens in the `.worktrees/user-guide-docs` worktree on branch `docs/user-guide-site`. Run `git`/`mkdocs` from the worktree root.
- The doc "test" at every checkpoint is `uv run --with-requirements docs/requirements.txt mkdocs build --strict` from the worktree root; it must exit 0 (except where a step explicitly expects the pre-file failure).

---

## File Structure

| File | Responsibility |
|---|---|
| `mkdocs.yml` | Site config: theme, nav, markdown extensions (snippets/superfences/md_in_html), explicit `validation`, `edit_uri`. |
| `docs/requirements.txt` | Pinned docs toolchain. |
| `docs/user-guide/assets/palette.css` | Canonical palette CSS custom properties + SVG helper classes; light + `slate` overrides. |
| `docs/user-guide/assets/figures/f0-vocabulary.svg` | F0 reader's key (imported SVG). |
| `docs/user-guide/assets/figures/f1-belief-spine.mmd` | F1 Mermaid body (reused in 2 pages). |
| `docs/user-guide/assets/figures/f2-sources-derived.mmd` | F2 Mermaid body (reused in 2 pages). |
| `docs/user-guide/assets/figures/f3-patchwork.svg` | F3 patchwork + commons (imported SVG). |
| `docs/user-guide/assets/figures/f4-belief-ceilings.svg` | F4 belief aggregation & ceilings (imported SVG). |
| `docs/user-guide/assets/figures/f8-entity-anatomy.svg` | F8 entity anatomy (imported SVG). |
| `docs/user-guide/*.md` | Edited: figure embeds + captions, cross-`docs_dir` link rewrites, `index.md` parity, tightened intros. |
| `.github/workflows/docs.yml` | Two-job build (PR + push) / deploy (main only) to Pages. |

---

## Task 1: MkDocs scaffold (config + deps)

**Files:**
- Create: `mkdocs.yml`
- Create: `docs/requirements.txt`
- Modify: `.gitignore` (append `site/`)

**Interfaces:**
- Produces: a buildable site whose `docs_dir` is `docs/user-guide`, snippet `base_path` is `docs/user-guide/assets` with `check_paths: true`, a mermaid custom fence, `md_in_html`, an explicit `validation` block, and full `nav` including `codex.md`. Later figure tasks import files with `--8<-- "figures/<name>"`.

- [ ] **Step 1: Resolve and exactly pin `docs/requirements.txt`**

Resolve the current latest and write **exact** pins (not ranges) so the toolchain is reproducible:

```bash
uv pip compile --quiet - <<'EOF' -o docs/requirements.txt
mkdocs-material
pymdown-extensions
EOF
```

If `uv pip compile` is unavailable, instead run
`uv run --with mkdocs-material --with pymdown-extensions python -c "import importlib.metadata as m; print('mkdocs-material==' + m.version('mkdocs-material')); print('pymdown-extensions==' + m.version('pymdown-extensions'))"`
and write those two `==` lines to `docs/requirements.txt`. Result must contain exact `==` pins for at least `mkdocs-material` and `pymdown-extensions`.

- [ ] **Step 2: Ignore generated `site/`**

Append `site/` to `.gitignore` (the strict-build checkpoints in every later task write `docs`-site output to `site/`, which must never be committed):

```bash
printf 'site/\n' >> .gitignore
```

Verify: `rg -n '^site/$' .gitignore` prints a match.

- [ ] **Step 3: Create `mkdocs.yml`**

```yaml
site_name: Science User Guide
site_description: The canonical user-facing manual for Science.
site_url: https://khughitt.github.io/science/
repo_url: https://github.com/khughitt/science
repo_name: khughitt/science
edit_uri: edit/main/docs/user-guide/
docs_dir: docs/user-guide

theme:
  name: material
  palette:
    - media: "(prefers-color-scheme: light)"
      scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/weather-night
        name: Switch to dark mode
    - media: "(prefers-color-scheme: dark)"
      scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/weather-sunny
        name: Switch to light mode
  features:
    - navigation.sections
    - navigation.top
    - navigation.tracking
    - content.code.copy
    - toc.follow
    - search.suggest
    - search.highlight

extra_css:
  - assets/palette.css

markdown_extensions:
  - admonition
  - attr_list
  - md_in_html
  - tables
  - toc:
      permalink: true
  - pymdownx.details
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.superfences:
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - pymdownx.snippets:
      base_path:
        - docs/user-guide/assets
      check_paths: true

plugins:
  - search

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

nav:
  - Home: index.md
  - Introduction: introduction.md
  - Big Picture: big-picture.md
  - Science Model: science-model.md
  - Project Layout: project-layout.md
  - Entities: entities.md
  - Epistemic Model: epistemic-model.md
  - Evidence Lines: evidence-lines.md
  - Graph And Derived State: graph-and-derived-state.md
  - Big-Picture Synthesis: big-picture-synthesis.md
  - Health And Validation: health-and-validation.md
  - CLI And Workflows: cli-and-workflows.md
  - Agent Workflows: agent-workflows.md
  - Codex: codex.md
  - Feedback And Telemetry: feedback-and-telemetry.md
  - Benchmarking: benchmarking.md
  - Project Packaging: project-packaging.md
  - Cross-Project Work: cross-project-work.md
```

- [ ] **Step 4: Non-strict build succeeds**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build`
Expected: exits 0; writes `site/`. (Non-strict tolerates the not-yet-fixed cross-`docs_dir` links.)

- [ ] **Step 5: Strict build FAILS on the known cross-`docs_dir` links (diagnostic)**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: non-zero exit; warnings name the 8 `../…` links (in `project-packaging.md`, `cli-and-workflows.md`, `graph-and-derived-state.md`, `cross-project-work.md`, `entities.md`). This confirms `--strict` + `validation` are wired. Task 2 fixes these.

- [ ] **Step 6: Confirm `site/` is untracked**

Run: `git status --porcelain site/`
Expected: no output (ignored).

- [ ] **Step 7: Commit**

```bash
git add mkdocs.yml docs/requirements.txt .gitignore
git commit -m "docs(user-guide): scaffold MkDocs Material site"
```

---

## Task 2: Clean strict baseline (link policy + index parity)

**Files:**
- Modify: `docs/user-guide/project-packaging.md:45,71`
- Modify: `docs/user-guide/cli-and-workflows.md:151,156`
- Modify: `docs/user-guide/graph-and-derived-state.md:291`
- Modify: `docs/user-guide/cross-project-work.md:130`
- Modify: `docs/user-guide/entities.md:452,555`
- Modify: `docs/user-guide/index.md`

**Interfaces:**
- Consumes: the strict-build failure from Task 1.
- Produces: a `mkdocs build --strict` that exits 0 — the clean baseline every later task must preserve.

**Link rewrite rule:** replace each `../<path>` target with the absolute repo blob URL `https://github.com/khughitt/science/blob/main/docs/<path>`. Keep the visible link text unchanged. The 8 edits:

| File:line | Old target | New target |
|---|---|---|
| project-packaging.md:45 | `../conventions/data-boundary.md` | `https://github.com/khughitt/science/blob/main/docs/conventions/data-boundary.md` |
| project-packaging.md:71 | `../conventions/citations-and-references.md` | `https://github.com/khughitt/science/blob/main/docs/conventions/citations-and-references.md` |
| cli-and-workflows.md:151 | `../conventions/annotation-tokens.md` | `https://github.com/khughitt/science/blob/main/docs/conventions/annotation-tokens.md` |
| cli-and-workflows.md:156 | `../conventions/cli-behavior.md` | `https://github.com/khughitt/science/blob/main/docs/conventions/cli-behavior.md` |
| graph-and-derived-state.md:291 | `../audits/plans-cleanup/2026-06-17-prose-epistemics-checkpoint.md` | `https://github.com/khughitt/science/blob/main/docs/audits/plans-cleanup/2026-06-17-prose-epistemics-checkpoint.md` |
| cross-project-work.md:130 | `../federation.md` | `https://github.com/khughitt/science/blob/main/docs/federation.md` |
| entities.md:452 | `../process/adding-a-domain.md` | `https://github.com/khughitt/science/blob/main/docs/process/adding-a-domain.md` |
| entities.md:555 | `../conventions/citations-and-references.md` | `https://github.com/khughitt/science/blob/main/docs/conventions/citations-and-references.md` |

- [ ] **Step 1: Rewrite all 8 links** per the table (edit the target inside `](…)`, leave link text as-is).

- [ ] **Step 2: Verify no `../` links remain**

Run: `rg -n '\]\(\.\./' docs/user-guide/*.md`
Expected: no output.

- [ ] **Step 3: Fix `index.md` parity** — the chapter table already lists Codex, but the numbered "Reading Path" (item 5) omits it. Add Codex to the reading path so nav, table, and reading path agree. Edit `docs/user-guide/index.md` item 5 list to include `[Codex](codex.md)` in sequence after `[Agent Workflows](agent-workflows.md)`.

- [ ] **Step 4: Strict build PASSES**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0, no warnings.

- [ ] **Step 5: Commit**

```bash
git add docs/user-guide/
git commit -m "docs(user-guide): rewrite cross-docs links + index parity for strict build"
```

---

## Task 3: Canonical palette CSS

**Files:**
- Create: `docs/user-guide/assets/palette.css`

**Interfaces:**
- Produces: CSS custom properties and SVG helper classes consumed by every imported SVG (F0/F3/F4/F8). Class names later SVGs rely on: `.sci-figure`, `.sci-epistemic`, `.sci-proposition`, `.sci-operational`, `.sci-reference`, `.sci-derived`, `.sci-belief-1`…`.sci-belief-4` (F4 ladder), `.sci-edge-support`, `.sci-edge-dispute`, `.sci-edge-plumbing`, `.sci-badge`, `.sci-badge-text`.

- [ ] **Step 1: Create `docs/user-guide/assets/palette.css`**

```css
/* Canonical palette for Science user-guide figures.
   Mermaid classDef blocks and SVG symbols copy these hexes verbatim;
   this file is the canonical definition those copies must track. */

:root {
  /* Entity classes (authored) */
  --sci-epistemic-stroke: #4F46E5;
  --sci-epistemic-fill:   #E0E7FF;
  --sci-operational-stroke: #0891B2;
  --sci-operational-fill:   #CFFAFE;
  --sci-reference-stroke: #78716C;
  --sci-reference-fill:   #E7E5E4;
  /* Derived state */
  --sci-derived-stroke: #64748B;
  --sci-derived-fill:   #F1F5F9;
  /* Relation accents */
  --sci-support:  #16A34A;
  --sci-dispute:  #DC2626;
  --sci-plumbing: #94A3B8;
  /* Belief magnitude ramp (epistemic/indigo family; NOT support-green).
     1=speculative → 4=well_supported, increasing intensity. */
  --sci-belief-1: #EEF2FF;
  --sci-belief-2: #C7D2FE;
  --sci-belief-3: #818CF8;
  --sci-belief-4: #4F46E5;
  /* Figure surface */
  --sci-fig-text:  #1E293B;
  --sci-fig-muted: #475569;
}

[data-md-color-scheme="slate"] {
  /* Darker fills for dark scheme; strokes stay constant for recognizability. */
  --sci-epistemic-fill:  #312E81;
  --sci-operational-fill: #164E63;
  --sci-reference-fill:  #44403C;
  --sci-derived-fill:    #1E293B;
  /* Belief ramp for dark scheme: rising indigo intensity on a dark ground. */
  --sci-belief-1: #312E81;
  --sci-belief-2: #3730A3;
  --sci-belief-3: #4F46E5;
  --sci-belief-4: #6366F1;
  --sci-fig-text:  #E2E8F0;
  --sci-fig-muted: #94A3B8;
}

/* Imported SVGs inherit these because snippets injects the SVG into the DOM. */
.sci-figure { max-width: 100%; height: auto; display: block; margin: 1rem auto; }
.sci-figure text { fill: var(--sci-fig-text); font-family: var(--md-text-font-family, sans-serif); }
.sci-figure .muted { fill: var(--sci-fig-muted); }

.sci-epistemic   { fill: var(--sci-epistemic-fill);   stroke: var(--sci-epistemic-stroke);   stroke-width: 2; }
.sci-proposition { fill: var(--sci-epistemic-fill);   stroke: var(--sci-epistemic-stroke);   stroke-width: 3.5; }
.sci-operational { fill: var(--sci-operational-fill); stroke: var(--sci-operational-stroke); stroke-width: 2; }
.sci-reference   { fill: var(--sci-reference-fill);   stroke: var(--sci-reference-stroke);   stroke-width: 2; }
.sci-derived     { fill: var(--sci-derived-fill);     stroke: var(--sci-derived-stroke);     stroke-width: 2; }

/* Belief-ladder rungs (F4). Stroke stays epistemic-indigo; fill ramps. */
.sci-belief-1 { fill: var(--sci-belief-1); stroke: var(--sci-epistemic-stroke); stroke-width: 2; }
.sci-belief-2 { fill: var(--sci-belief-2); stroke: var(--sci-epistemic-stroke); stroke-width: 2; }
.sci-belief-3 { fill: var(--sci-belief-3); stroke: var(--sci-epistemic-stroke); stroke-width: 2; }
.sci-belief-4 { fill: var(--sci-belief-4); stroke: var(--sci-epistemic-stroke); stroke-width: 2; }

.sci-edge-support  { stroke: var(--sci-support);  stroke-width: 2.5; fill: none; }
.sci-edge-dispute  { stroke: var(--sci-dispute);  stroke-width: 2.5; fill: none; }
.sci-edge-plumbing { stroke: var(--sci-plumbing); stroke-width: 2; stroke-dasharray: 6 5; fill: none; }

.sci-badge { fill: var(--sci-derived-stroke); }
/* Higher specificity than `.sci-figure text` so badge text stays white. */
.sci-figure .sci-badge-text { fill: #FFFFFF; font-size: 10px; font-weight: 700; }
```

- [ ] **Step 2: Strict build still PASSES** (CSS is referenced by `extra_css`; unused so far but valid).

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0.

- [ ] **Step 3: Commit**

```bash
git add docs/user-guide/assets/palette.css
git commit -m "docs(user-guide): add canonical figure palette"
```

---

## Task 4: F0 — entity vocabulary reader's key (SVG) + "how to read figures" note

**Files:**
- Create: `docs/user-guide/assets/figures/f0-vocabulary.svg`
- Modify: `docs/user-guide/entities.md` (embed after the opening paragraph, before `## Entity Shape`)
- Modify: `docs/user-guide/big-picture.md` (add a "How to read the figures" admonition linking to the F0 anchor in `entities.md`)

**Interfaces:**
- Consumes: `palette.css` helper classes (Task 3).
- Produces: the canonical rendering of each kind's shape, which F1/F3/F4/F8 reuse. Anchor `entities.md#figure-key` (from the embed's heading) is linked by `big-picture.md`.

**F0 construction spec.** A single `<svg class="sci-figure" role="img" viewBox="0 0 960 520">` with `<title>` and `<desc>`. Three labelled columns (authored classes) + a bottom band (derived state) + a relations key. Every shape carries a visible text label (shapes are family-level; the label pins the kind). Shapes:

- question → stadium (`<rect rx="18">` full-pill), class `sci-epistemic`.
- hypothesis → hexagon (`<polygon>`), class `sci-epistemic`.
- proposition → rounded rect with heavy border, class `sci-proposition`, label "proposition (belief-bearing)".
- observation → circle, class `sci-epistemic`.
- evidence-line → parallelogram (`<polygon>` skewed), class `sci-epistemic`, label "evidence-line + / −".
- inquiry / patch-definition → dashed rounded container (`<rect rx="12" stroke-dasharray="6 5">`), class `sci-epistemic` with dashed stroke, label "inquiry / patch (neighborhood)".
- report → lined document, class `sci-epistemic`.
- dataset → cylinder (ellipse + rect), class `sci-operational`.
- workflow / run → chevron (`<polygon>`), class `sci-operational`.
- source / paper → dog-eared page, class `sci-operational`.
- concept / variable / outcome → notched tag (`<polygon>`), class `sci-reference`.
- derived band: belief (gauge ring), snapshot (stacked rect), graph/dashboards/health (panel) — all class `sci-derived` with a small `derived` badge (a `<rect class="sci-badge">` + `<text class="sci-badge-text">derived</text>`).
- relations key: three sample arrows — `+ supports` (class `sci-edge-support`, with `marker-end` arrow), `− disputes` (`sci-edge-dispute`), and `plumbing / derived` (`sci-edge-plumbing`). Include a `<defs>` with two arrowhead markers (support-green, dispute-red) and one slate marker.

- [ ] **Step 1 (red): add the embed before the file exists → strict build FAILS**

In `docs/user-guide/entities.md`, after the opening context paragraph and before `## Entity Shape`, insert:

```markdown
## Figure Key

The figures in this guide share one visual vocabulary. Color marks an entity's
**class**; shape reinforces its **kind family** and the label names the exact
kind. Derived state (belief, snapshots, the graph) is drawn in slate with a
`derived` badge — never as authored source.

<figure markdown="span">
--8<-- "figures/f0-vocabulary.svg"
<figcaption>Entity vocabulary reader's key.</figcaption>
</figure>
```

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: FAIL — snippets `check_paths` reports `figures/f0-vocabulary.svg` not found.

- [ ] **Step 2 (green): create `docs/user-guide/assets/figures/f0-vocabulary.svg`** implementing the F0 construction spec above. Requirements the file MUST satisfy:
  - Root `<svg class="sci-figure" role="img" viewBox="0 0 960 520" xmlns="http://www.w3.org/2000/svg">` with a `<title>Entity vocabulary reader's key</title>` and a `<desc>` summarizing the key.
  - No inline `fill`/`stroke` **colors** on class-bearing shapes — colors come only from `palette.css` classes (so light/dark toggle works). Geometry attributes (`d`, `points`, `rx`, `cx`) are inline.
  - Each authored shape uses exactly one of `sci-epistemic` / `sci-proposition` / `sci-operational` / `sci-reference`; each derived shape uses `sci-derived` + a badge.
  - Support/dispute sample arrows carry the literal text labels `+ supports` and `− disputes`.
  - `<defs>` arrowhead markers: `marker` fills reference the accent hexes directly (markers don't inherit the CSS var reliably across renderers) — use `#16A34A`, `#DC2626`, `#94A3B8` verbatim, matching the canonical palette.

- [ ] **Step 3: Link the key from `big-picture.md`** — after the opening two paragraphs, add the cross-page anchor link (this is why the strict build must come *after* this edit — `validation.links.anchors` checks `#figure-key` resolves):

```markdown
!!! info "How to read the figures"
    Diagrams in this guide share one visual vocabulary — see the
    [figure key](entities.md#figure-key). Color marks entity class, shape marks
    kind family, and derived state is drawn in slate with a `derived` badge.
```

- [ ] **Step 4 (green): strict build PASSES (validates snippet import AND the `#figure-key` anchor)**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0.

- [ ] **Step 5: Visual acceptance** — `uv run --with-requirements docs/requirements.txt mkdocs serve`, open `/entities/`. Confirm, and record pass/fail for each:
  - Legible in **light** and **dark** (toggle the palette); strokes stable, fills readable.
  - Support vs dispute distinguishable with color **off** (labels present).
  - Figure **scales** within the column when the window is narrowed (no horizontal overflow).
  - Screen-reader `<title>` present.

- [ ] **Step 6: Commit**

```bash
git add docs/user-guide/assets/figures/f0-vocabulary.svg docs/user-guide/entities.md docs/user-guide/big-picture.md
git commit -m "docs(user-guide): add F0 entity vocabulary figure + figure key"
```

---

## Task 5: F1 — the belief spine (Mermaid)

**Files:**
- Create: `docs/user-guide/assets/figures/f1-belief-spine.mmd`
- Modify: `docs/user-guide/big-picture.md` (replace the fenced ASCII spine under "Epistemic Model & Key Players")
- Modify: `docs/user-guide/epistemic-model.md` (embed near the top of "Core Types")

**Interfaces:**
- Consumes: canonical hexes (Global Constraints).
- Produces: one `.mmd` source imported into both pages via a snippet inside a `mermaid` fence.

**Semantics (must not be a forward pipeline):** question *frames* hypothesis; hypothesis *organizes* the central proposition; observation and evidence-line arrows **converge into** the proposition as neutral `bears on` edges (the spine overview does not adjudicate support-vs-dispute per line — the evidence-line node itself carries the `+ / −` stance); belief is **derived from** the proposition; snapshot **persists** belief.

**Mermaid vocabulary conventions (documented equivalents of the SVG system, applied to F1 and F2):**
- The SVG `derived` **badge** has no Mermaid primitive; its documented equivalent is a **parenthetical `(derived)` label + the slate `derived` classDef**. Stated here so it is a deliberate convention, not an omission.
- `bears on` and derivation/plumbing edges are **dashed slate** via explicit `linkStyle` (matching `.sci-edge-plumbing`), so no relation renders as a default solid link.

- [ ] **Step 1: Create `docs/user-guide/assets/figures/f1-belief-spine.mmd`**

```
flowchart TD
    Q(["question"]):::epistemic
    H{{"hypothesis"}}:::epistemic
    P["proposition"]:::prop
    O(("observation")):::epistemic
    E[/"evidence-line + / −"/]:::epistemic
    B{"belief (derived)"}:::derived
    S["snapshot (derived)"]:::derived

    Q -->|frames| H
    H -->|organizes| P
    O -->|bears on| P
    E -->|bears on| P
    P -->|derives| B
    B -->|persists| S

    classDef epistemic fill:#E0E7FF,stroke:#4F46E5,stroke-width:2px,color:#1E293B;
    classDef prop fill:#E0E7FF,stroke:#4F46E5,stroke-width:3.5px,color:#1E293B;
    classDef derived fill:#F1F5F9,stroke:#64748B,stroke-width:2px,color:#1E293B;

    %% edges: 0=frames 1=organizes 2,3=bears on 4=derives 5=persists
    %% bears-on = plumbing slate dashed; derivation = derived slate dashed
    linkStyle 2,3 stroke:#94A3B8,stroke-width:2px,stroke-dasharray:6 5;
    linkStyle 4,5 stroke:#64748B,stroke-width:2px,stroke-dasharray:6 5;
```

- [ ] **Step 2: Embed in `epistemic-model.md`** — immediately under the `## Core Types` heading, before the table:

```markdown
```mermaid
--8<-- "figures/f1-belief-spine.mmd"
```

*The belief spine: evidence and observations bear on a proposition; belief is
derived, then persisted as a snapshot. This is a teaching order, not a required
one.*
```

- [ ] **Step 3: Replace the ASCII spine in `big-picture.md`** — under "Epistemic Model & Key Players", replace the existing ```text question → … → snapshot``` fenced block with the figure **and a caption** (so the replacement is not left caption-less):

```markdown
```mermaid
--8<-- "figures/f1-belief-spine.mmd"
```

*The belief spine — a teaching order, not a required one: evidence and
observations bear on a proposition, whose belief is derived and then snapshotted.*
```

Leave the surrounding bullet list of player definitions unchanged.

- [ ] **Step 4: Strict build PASSES**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0.

- [ ] **Step 5: Visual acceptance** (`mkdocs serve`, open `/epistemic-model/` and `/big-picture/`): arrows **converge on** the proposition (not a straight chain); belief/snapshot read as derived; nodes legible in light and dark; no horizontal overflow on narrow width.

- [ ] **Step 6: Commit**

```bash
git add docs/user-guide/assets/figures/f1-belief-spine.mmd docs/user-guide/epistemic-model.md docs/user-guide/big-picture.md
git commit -m "docs(user-guide): add F1 belief-spine figure"
```

---

## Task 6: F2 — authored sources → derived views (Mermaid)

**Files:**
- Create: `docs/user-guide/assets/figures/f2-sources-derived.mmd`
- Modify: `docs/user-guide/science-model.md:9-15` (replace the existing mermaid block)
- Modify: `docs/user-guide/introduction.md` (embed under "Durable Sources First")

**Interfaces:**
- Produces: one `.mmd` imported into both pages. Corrects the current diagram's single "Authored project files" node into the three authored classes.

**Semantics:** authored records span **all three** classes (epistemic, operational, reference) and feed graph build → knowledge graph → {dashboards, snapshots, health}; derived nodes are labelled `(derived)` and use the derived classDef.

- [ ] **Step 1: Create `docs/user-guide/assets/figures/f2-sources-derived.mmd`**

```
flowchart LR
    subgraph A["Authored project files"]
      AE["epistemic sources"]:::epistemic
      AO["operational sources"]:::operational
      AR["reference sources"]:::reference
    end
    GB["graph build"]:::operational
    G["knowledge graph (derived)"]:::derived
    D["dashboard summaries (derived)"]:::derived
    SN["belief snapshots (derived)"]:::derived
    HV["health & validation (derived)"]:::derived

    AE --> GB
    AO --> GB
    AR --> GB
    GB --> G
    G --> D
    G --> SN
    G --> HV

    classDef epistemic fill:#E0E7FF,stroke:#4F46E5,stroke-width:2px,color:#1E293B;
    classDef operational fill:#CFFAFE,stroke:#0891B2,stroke-width:2px,color:#1E293B;
    classDef reference fill:#E7E5E4,stroke:#78716C,stroke-width:2px,color:#1E293B;
    classDef derived fill:#F1F5F9,stroke:#64748B,stroke-width:2px,color:#1E293B;

    %% edges: 0,1,2=authored→build (solid) 3=build→graph 4,5,6=graph→derived
    %% derivation edges are slate dashed (per the F1/F2 Mermaid conventions)
    linkStyle 3,4,5,6 stroke:#64748B,stroke-width:2px,stroke-dasharray:6 5;
```

Derived nodes carry the parenthetical `(derived)` label + slate `derived` classDef — the documented Mermaid equivalent of the SVG `derived` badge (see Task 5).

- [ ] **Step 2: Replace the diagram in `science-model.md`** — replace the existing 7-line ```mermaid block (lines 9–15, the `A[Authored project files] --> B[Graph build] …` flowchart) with:

```markdown
```mermaid
--8<-- "figures/f2-sources-derived.mmd"
```
```

- [ ] **Step 3: Embed in `introduction.md`** — at the end of the "Durable Sources First" section, add:

```markdown
```mermaid
--8<-- "figures/f2-sources-derived.mmd"
```

*Authored sources of every class feed graph build; the graph, dashboards,
snapshots, and health reports are derived. Fix the source and rebuild — never
hand-patch generated TriG.*
```

- [ ] **Step 4: Strict build PASSES**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0.

- [ ] **Step 5: Visual acceptance**: three distinct authored-class colors visible; derived nodes clearly derived; legible light/dark; no overflow.

- [ ] **Step 6: Commit**

```bash
git add docs/user-guide/assets/figures/f2-sources-derived.mmd docs/user-guide/science-model.md docs/user-guide/introduction.md
git commit -m "docs(user-guide): add F2 sources-to-derived figure"
```

---

## Task 7: F3 — patchwork of epistemic neighborhoods + commons (SVG)

**Files:**
- Create: `docs/user-guide/assets/figures/f3-patchwork.svg`
- Modify: `docs/user-guide/big-picture.md` (embed under "The Substrate")
- Modify: `docs/user-guide/science-model.md` (embed where the substrate/patchwork is described)
- Modify: `docs/user-guide/cross-project-work.md` (embed near the top)

**Interfaces:**
- Consumes: `palette.css` classes; F0 shape conventions.
- Produces: the patchwork figure reused by **three** chapters (design §D requires big-picture, science-model, cross-project-work).

**F3 construction spec.** `<svg class="sci-figure" role="img" viewBox="0 0 1000 660">` with `<title>`/`<desc>`. Contents:
- **Two project cards** (rounded rects, muted outline), each containing:
  - **2 dashed inquiry neighborhoods** (`sci-epistemic` dashed containers). Inside each: a focal hypothesis (hexagon) or question (stadium) plus 2–3 member propositions (heavy-border rounded rects) and one dataset (cylinder, `sci-operational`), wired with slate **plumbing** edges (`sci-edge-plumbing`, membership/containment). These are the **authored** neighborhoods.
  - **one derived graph panel** — a `sci-derived` panel with a `derived` badge, labelled e.g. "Project A graph (derived)". This is the peer's queryable graph; composition operates on it, not on authored neighborhoods.
- **A commons band** at the bottom: a labelled panel holding shared canonical owners — a `dataset` cylinder and a `reference-graph` tag (`sci-reference`).
- **Three distinct cross-project relations, each labelled** (do not draw a generic "sync"):
  1. **peer graph composition** — a solid slate arrow `composes` running **from Project B's derived graph panel into Project A's derived graph panel** (graph → graph, not neighborhood → project).
  2. **registry indexing** — a small `registry` node with `indexes` arrows to both project cards.
  3. **borrowing commons owners** — a `borrows` arrow from a project's dataset placeholder down to the commons canonical dataset.
- Every relation arrow carries a text label; none rely on color alone. Reuse the F0 arrowhead markers (`<defs>` with slate marker; add a labelled style rather than color-coding these structural edges).

- [ ] **Step 1 (red): add the three embeds → strict build FAILS** (file missing).

In `big-picture.md` under "The Substrate" (after the "patchwork" paragraph):

```markdown
<figure markdown="span">
--8<-- "figures/f3-patchwork.svg"
<figcaption>A patchwork of epistemic neighborhoods across projects, over a shared commons.</figcaption>
</figure>
```

In `science-model.md`, where the substrate/patchwork of neighborhoods is described, add the same `<figure>…--8<-- "figures/f3-patchwork.svg"…</figure>` block with caption "Neighborhoods within a project; derived graphs compose across peers; canonical owners live in the commons."

In `cross-project-work.md` near the top (after the first paragraph), add the same `<figure>…--8<-- "figures/f3-patchwork.svg"…</figure>` block with caption "Peer graphs compose, a registry indexes, and projects borrow canonical owners from the commons."

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: FAIL — `figures/f3-patchwork.svg` not found.

- [ ] **Step 2 (green): create `docs/user-guide/assets/figures/f3-patchwork.svg`** per the construction spec. MUST: use only `palette.css` classes for entity colors (no inline color on class shapes); render a per-project **derived graph panel** (`sci-derived` + badge) and draw `composes` as **graph-panel → graph-panel**; label all three cross-project relations with the exact words `composes`, `indexes`, `borrows`; include `<title>`/`<desc>`; keep neighborhoods as dashed `sci-epistemic` containers (dashed = boundary, per Global Constraints).

- [ ] **Step 3 (green): strict build PASSES**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0.

- [ ] **Step 4: Visual acceptance** (`/big-picture/`, `/science-model/`, `/cross-project-work/`): `composes` clearly runs graph-panel → graph-panel (not neighborhood → project); three cross-project relations are visually and textually distinct; neighborhoods are dashed containers; per-project derived graph panels carry the `derived` badge; commons band clearly separate; light/dark legible; responsive, no overflow.

- [ ] **Step 5: Commit**

```bash
git add docs/user-guide/assets/figures/f3-patchwork.svg docs/user-guide/big-picture.md docs/user-guide/science-model.md docs/user-guide/cross-project-work.md
git commit -m "docs(user-guide): add F3 patchwork + commons figure"
```

---

## Task 8: F4 — belief aggregation & ceilings (SVG)

**Files:**
- Create: `docs/user-guide/assets/figures/f4-belief-ceilings.svg`
- Modify: `docs/user-guide/epistemic-model.md` (embed under "Belief Policy")
- Modify: `docs/user-guide/evidence-lines.md` (embed near the top)

**Interfaces:**
- Consumes: `palette.css` classes; F0 conventions.
- Produces: the belief figure reused by two chapters.

**F4 construction spec.** `<svg class="sci-figure" role="img" viewBox="0 0 980 640">` with `<title>`/`<desc>`. Contents:
- **Left:** several **evidence-lines** (parallelograms) grouped into 2 **independence groups** (labelled boxes), each arrow labelled `+ supports` (green, `sci-edge-support`) or `− disputes` (red, `sci-edge-dispute`), converging (`bears on`) into a central **proposition** (heavy-border rounded rect).
- **Middle:** a "reduce by independence & quality" annotation between groups and proposition.
- **Right:** the **ordinal ladder** as four stacked rungs bottom→top: `speculative` (`sci-belief-1`), `fragile` (`sci-belief-2`), `supported` (`sci-belief-3`), `well_supported` (`sci-belief-4`) — the theme-aware indigo ramp from `palette.css` (all epistemic family — NOT green; no inline rung colors). Mark the achieved magnitude with a pointer.
- **Ceilings & caps, each a labelled horizontal line/annotation on the ladder:**
  1. **authored-only support ceiling** — a cap at `fragile`, labelled "authored-only support ≤ fragile" (NOT "expert_judgment").
  2. **dataset-QA-failed cap** — labelled precisely: "caps only when the achieved magnitude depends on QA-failed support and QA-clean support can't reach it alone."
  3. **refutation cap** — labelled "decisive, independent, whole-claim direct refutation → caps to fragile".
- **contestation** — a single **boolean overlay** badge on the proposition ("contested"), shown as an annotation, explicitly not a ladder rung.

- [ ] **Step 1 (red): add the two embeds → strict build FAILS** (file missing).

In `epistemic-model.md` under "## Belief Policy" (after the first paragraph):

```markdown
<figure markdown="span">
--8<-- "figures/f4-belief-ceilings.svg"
<figcaption>Evidence lines reduce into a proposition's belief; ceilings and a refutation cap bound it.</figcaption>
</figure>
```

In `evidence-lines.md` near the top (after the first paragraph), add the same `<figure>…--8<-- "figures/f4-belief-ceilings.svg"…</figure>` with caption "Support and dispute, grouped by independence, bear on a proposition; magnitude is bounded by two ceilings and a refutation cap."

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: FAIL — `figures/f4-belief-ceilings.svg` not found.

- [ ] **Step 2 (green): create `docs/user-guide/assets/figures/f4-belief-ceilings.svg`** per the spec. MUST: label support/dispute arrows in text; draw the four ladder rungs with classes `sci-belief-1`…`sci-belief-4` (no inline rung fills, no support-green); word the three caps exactly as specified (authored-only ceiling, dependency-qualified QA cap, decisive-independent-whole-claim-direct refutation); render contestation as a single boolean overlay, not a rung; `<title>`/`<desc>` present; entity colors only from `palette.css` classes.

- [ ] **Step 3 (green): strict build PASSES**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0.

- [ ] **Step 4: Cross-check wording against source truth** — reread `epistemic-model.md` "Belief Policy" and the design §D F4. Confirm the figure text matches the authored-only ceiling and the QA-cap dependency condition (no "expert_judgment → fragile" phrasing; no "any QA-failed dataset caps"). Fix the SVG text if drift exists.

- [ ] **Step 5: Visual acceptance**: support/dispute legible without color; ladder is indigo (not green); the three caps are individually labelled at the right rungs; contestation reads as an overlay; light/dark legible; responsive.

- [ ] **Step 6: Commit**

```bash
git add docs/user-guide/assets/figures/f4-belief-ceilings.svg docs/user-guide/epistemic-model.md docs/user-guide/evidence-lines.md
git commit -m "docs(user-guide): add F4 belief aggregation + ceilings figure"
```

---

## Task 9: F8 — entity anatomy (SVG)

**Files:**
- Create: `docs/user-guide/assets/figures/f8-entity-anatomy.svg`
- Modify: `docs/user-guide/entities.md` (embed inside/near "## Entity Shape")

**Interfaces:**
- Consumes: `palette.css` classes.
- Produces: a standalone onboarding figure (no reuse elsewhere).

**F8 construction spec.** `<svg class="sci-figure" role="img" viewBox="0 0 820 420">` with `<title>`/`<desc>`. A single entity file drawn as a rounded card (`sci-proposition` outline to signal an epistemic example) split into two labelled zones:
- **top — `kind:id`** header strip (e.g. `proposition:example`).
- **frontmatter = machine identity** (a small YAML block callout: `id`, `kind`, `title`, `status`, relations) annotated "machine-readable identity & relationships".
- **body = human context** (prose lines) annotated "human-readable context".
A slate plumbing arrow from the file to a small `derived` graph node (badge) captioned "→ graph build" to connect anatomy to derivation.

- [ ] **Step 1 (red): add the embed → strict build FAILS** (file missing).

In `entities.md`, at the end of the "## Entity Shape" section, add:

```markdown
<figure markdown="span">
--8<-- "figures/f8-entity-anatomy.svg"
<figcaption>An entity file: <code>kind:id</code>, machine-readable frontmatter, human-readable body.</figcaption>
</figure>
```

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: FAIL — `figures/f8-entity-anatomy.svg` not found.

- [ ] **Step 2 (green): create `docs/user-guide/assets/figures/f8-entity-anatomy.svg`** per the spec (colors only via classes; `<title>`/`<desc>`; the `derived` graph node carries a badge).

- [ ] **Step 3 (green): strict build PASSES**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0.

- [ ] **Step 4: Visual acceptance**: two zones clearly labelled (identity vs context); legible light/dark; responsive.

- [ ] **Step 5: Commit**

```bash
git add docs/user-guide/assets/figures/f8-entity-anatomy.svg docs/user-guide/entities.md
git commit -m "docs(user-guide): add F8 entity-anatomy figure"
```

---

## Task 10: Coherence audit (audit-only; no speculative rewrites)

This task is deliberately **audit-only**. Every figure caption is authored at the
point each figure is introduced (Tasks 4–9), so no chapter-opener rewriting is
prescribed here — that avoids an open-ended "improve the prose" step that could
drift into changing technical claims. The task verifies coherence and fixes only
concrete, enumerated defects if the audit finds them.

**Files:**
- Modify (only if an audit check below fails): the specific file named by that check.

**Interfaces:**
- Consumes: all figures embedded (Tasks 4–9).
- Produces: a verified-coherent site; no prose claims changed.

- [ ] **Step 1: Caption presence audit** — confirm each embedded figure has a caption/italic gloss at every placement:
  - F0 → `entities.md` (figcaption). 
  - F1 → `epistemic-model.md` (gloss) **and** `big-picture.md` (gloss added in Task 5 Step 3).
  - F2 → `science-model.md` (existing diagram context) **and** `introduction.md` (gloss).
  - F3 → `big-picture.md`, `science-model.md`, `cross-project-work.md` (figcaptions).
  - F4 → `epistemic-model.md`, `evidence-lines.md` (figcaptions).
  - F8 → `entities.md` (figcaption).
  If any is missing, add a one-line italic gloss/figcaption for that placement only. Do not edit surrounding prose.

- [ ] **Step 2: Reading-path/nav parity audit** — confirm `index.md` reading path, `index.md` chapter table, and `mkdocs.yml` `nav` list the same 18 chapters (incl. `codex.md`). Fix a mismatch if found; otherwise no change.

- [ ] **Step 3: Full strict build + link sweep**

Run: `uv run --with-requirements docs/requirements.txt mkdocs build --strict`
Expected: exits 0, zero warnings.
Run: `rg -n '\]\(\.\./' docs/user-guide/*.md`
Expected: no output (no cross-`docs_dir` links reintroduced).

- [ ] **Step 4: Whole-site visual pass** (`mkdocs serve`): click through nav top-to-bottom; every figure renders in light and dark; search works; no broken images.

- [ ] **Step 5: Commit (only if the audit changed anything)**

```bash
git add docs/user-guide/
git commit -m "docs(user-guide): coherence audit fixes"
```
If Steps 1–2 found nothing to fix, there is nothing to commit; note that and proceed.

---

## Task 11: GitHub Pages workflow

**Files:**
- Create: `.github/workflows/docs.yml`

**Interfaces:**
- Consumes: `docs/requirements.txt`, `mkdocs.yml` (strict-clean site from Tasks 1–10).
- Produces: PR validation on every docs change; Pages deploy from `main`.

- [ ] **Step 1: Create `.github/workflows/docs.yml`**

**Design note on the PR/main split.** `actions/configure-pages` and `actions/upload-pages-artifact` require Pages to be enabled (its auto-enable input defaults off and needs a stronger token), so running them on a PR before the user enables Pages would fail the PR. Therefore **PRs only run the strict build** (pure validation), and the `configure-pages`/`upload`/`deploy` chain is gated to `main`. Concurrency lives on the **deploy** job (not workflow-level) with `cancel-in-progress: false`, so unrelated PRs never cancel each other and an in-flight `main` deployment is never cancelled.

```yaml
name: docs

on:
  push:
    branches: [main]
    paths: ['docs/**', 'mkdocs.yml', '.github/workflows/docs.yml']
  pull_request:
    paths: ['docs/**', 'mkdocs.yml', '.github/workflows/docs.yml']
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r docs/requirements.txt
      - run: mkdocs build --strict
      # Pages packaging only on main (Pages must be enabled first; PRs just validate).
      - if: github.ref == 'refs/heads/main'
        uses: actions/configure-pages@v5
      - if: github.ref == 'refs/heads/main'
        uses: actions/upload-pages-artifact@v3
        with:
          path: site/

  deploy:
    needs: build
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    concurrency:
      group: pages
      cancel-in-progress: false
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Refresh action major versions** — before committing, check each action's latest major and bump if needed: `actions/checkout`, `actions/setup-python`, `actions/configure-pages`, `actions/upload-pages-artifact`, `actions/deploy-pages` (e.g. `gh api repos/actions/deploy-pages/releases/latest --jq .tag_name`). Update the `@vN` pins to match.

- [ ] **Step 3: Validate the workflow (hermetic; prefer `actionlint`)**

If `actionlint` is installed: `actionlint .github/workflows/docs.yml` (expected: no output).
Otherwise use the docs env, which has PyYAML (MkDocs depends on it) so the check is hermetic:
`uv run --with-requirements docs/requirements.txt python -c "import yaml; yaml.safe_load(open('.github/workflows/docs.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Confirm the build command matches local**

Verify `mkdocs build --strict` is the exact gate used in Tasks 1–10 and that `path: site/` matches MkDocs' output dir (`site/`). No code change expected.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/docs.yml
git commit -m "ci: build docs on PRs, deploy to Pages from main"
```

- [ ] **Step 6: Record the manual enablement prerequisite** — Pages must be enabled before merge to `main`, or the `main` deploy chain fails. This is a repo setting the user performs; note it in the handoff (Settings → Pages → Source = "GitHub Actions"). PRs are unaffected (they only run the strict build). Do not merge to `main` until Pages is enabled.

---

## Post-plan handoff notes

- **Manual step (user):** enable GitHub Pages (Settings → Pages → Source = "GitHub Actions") before this branch merges to `main`.
- **Deferred figures:** F5 (cut — ladder lives in F4), F6 (deferred — inquiry neighborhood; needs assumption/transformation shapes not in F0), F7 (cut — verdict-token table is clearer).
- **Follow-up candidates:** a small script to generate Mermaid `classDef` hexes from `palette.css` (removes the accepted v1 duplication); deeper chapter restructuring.

## Self-Review

- **Spec coverage:** §A → Tasks 1–3, 11 (incl. `.gitignore site/`, exact pins, `edit_uri`); §B → Task 11 (PR-build-only / main-deploy split, deploy-scoped concurrency); §C palette/classes incl. belief ramp → Task 3, applied Tasks 4–9; §D figures F0–F4+F8 → Tasks 4–9, F3 in all three chapters (big-picture, science-model, cross-project-work), F5/F6/F7 dispositions recorded; §E prose/links/index → Task 2 (links + index) and Task 10 (audit-only); §F layout → File Structure table. No uncovered spec section.
- **Placeholder scan:** no TBD/TODO; every config/CSS/Mermaid/workflow file is given in full. SVG hero figures (F0/F3/F4/F8) are specified by exact construction spec + hard MUST-constraints + red/green build gate + visual acceptance, because a pixel-final SVG is a visually-iterated deliverable, not blind-authorable; this is intentional, not a placeholder. Task 10 is scoped audit-only (with enumerated checks) rather than an open-ended prose rewrite.
- **Type/name consistency:** CSS class names (`sci-epistemic`, `sci-proposition`, `sci-operational`, `sci-reference`, `sci-derived`, `sci-belief-1`…`sci-belief-4`, `sci-edge-support`, `sci-edge-dispute`, `sci-edge-plumbing`, `sci-badge`, `sci-badge-text`, `sci-figure`) defined in Task 3 are the exact names referenced in Tasks 4/7/8/9. `.sci-figure .sci-badge-text` out-specifies `.sci-figure text` (badge text stays white). Snippet include paths (`figures/<name>`) match `base_path: docs/user-guide/assets`. Mermaid `classDef`/`linkStyle` hexes match the Global Constraints palette; derivation/plumbing edges are dashed slate in F1 and F2. Output dir `site/` consistent between local gate, workflow `path:`, and `.gitignore`.
