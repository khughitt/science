# Docs: Big Picture chapter + README / AGENTS refresh — Design

**Date:** 2026-07-03
**Status:** Approved (brainstorm) — ready for implementation plan

## Goal

Continue the docs cleanup that produced `docs/user-guide/`. Add a concise
conceptual on-ramp, stop the README from duplicating the manual, give the
toolkit repo a real agent guide, and fold the Codex doc into the user guide.

## Decisions (locked)

1. **Single source for concise/TL;DR material.** A new chapter,
   `docs/user-guide/big-picture.md`, holds *all* the concise treatment.
   No `tldr/` folder and no per-page TL;DR sections (those would duplicate and
   drift). Detailed chapters stay canonical for depth; each concise subsection
   links *down* to its detailed chapter.
2. **New root `./AGENTS.md`** — a lean dev guide for working on the toolkit
   repo itself. Refresh the project **template** too and document its update
   mechanism.
3. **Move `docs/README.codex.md` → `docs/user-guide/codex.md`** as a listed
   chapter.
4. **Data-model detail stays in `big-picture.md` (concise) + `entities.md`
   (depth).** No new data-model reference chapter — `entities.md` already
   covers entity shape and the dataset lifecycle/schema/QA.

## Deliverables

### A. `docs/user-guide/big-picture.md` (new)

Slot: **after Introduction, before Science Model** in the reading path.
Four sections, each concise, each ending with a `→ full detail: [chapter]`
pointer down into the existing detailed chapters.

1. **Stance** — the skeptical, data-driven creed:
   - open data ≫ closed data; open literature ≫ closed literature
   - we believe nothing until we have re-analyzed the data ourselves
   - support from multiple independent datasets ≫ single-dataset support
   - literature claims are *hints*, not facts — belief updates from our own
     analyses
   - uncertainty, contestation, and fragility stay visible (fail-early,
     explicit-over-defensive)
   → full detail: `introduction.md`, `epistemic-model.md`
2. **The substrate** — authored project files (especially Markdown/YAML entity
   files, but also bibliography, source records, sidecar annotations, terms,
   and manifests) are the source of truth; graph, summaries, snapshots, and
   health are *derived views*;
   **heterogeneous patchwork** of small epistemic neighborhoods; **commons**
   (shared datasets / reference graphs, peers & sync); fix-the-source-then-
   rebuild-the-graph (never patch generated TriG).
   → full detail: `science-model.md`, `cross-project-work.md`
3. **Epistemic model & key players** — the belief pipeline
   `question → hypothesis → proposition → observation / evidence-line →
   belief → snapshot`; role of each; evidence *supports / disputes*, never
   "proves"; one paragraph on belief aggregation (log-odds, independence,
   authored-confidence and dataset-QA ceilings).
   → full detail: `epistemic-model.md`, `evidence-lines.md`
4. **The data model** — `Entity` = typed `kind:id` record, markdown + YAML
   frontmatter, relations connect entities, kind descriptors are the per-kind
   SSOT, three classes (epistemic / operational / reference). **Dataset
   schema** = Frictionless Data Package: runtime **`datapackage.yaml`**
   (JSON `datapackage.json` also accepted), typed Data Resource schema, QA
   verdicts feed belief.
   → full detail: `entities.md`

**Naming guard:** distinguish this "Big Picture" chapter from the existing
`big-picture-synthesis.md` ("Big-Picture Synthesis" — the generated per-
project synthesis report). Index entries and prose must make the difference
obvious (Big Picture = conceptual map of Science; Big-Picture Synthesis =
a generated report *for* a project).

### B. `docs/user-guide/codex.md` (moved)

- `git mv docs/README.codex.md docs/user-guide/codex.md`.
- Add to `index.md` (reading path is optional; chapter table yes).
- Fix any drift; relink from `README.md` and the index.
- Grep for and update any inbound references to the old path.

### C. Root `./AGENTS.md` (new) + `./CLAUDE.md` pointer

Lean dev guide for agents/contributors working **on the toolkit code**
(distinct from `meta/AGENTS.md`, which is the science-*meta* research
project's guide). Contents:

- **What this is** — the toolkit: `science/` (CLI package), `science/model/`
  (shared Pydantic models), plus `skills/`, `commands/`, `templates/`,
  `agents/`.
- **Nested packages, no root `pyproject.toml`.** CLI / package work runs from
  `science/`; model work from `science/model/`. State this explicitly — it is
  the most common orientation mistake.
- **Validation / tests** — concrete command patterns (there is no root
  `pyproject.toml`, so tests run from each package dir):
  - CLI package: `cd science && uv run --frozen pytest`
  - Model package: `cd science/model && uv run --frozen pytest`
  - Default pytest excludes the `snapshot` and `real_projects` markers; name
    the opt-in forms (`-m snapshot`, `-m real_projects`).
  - Lint / types under `science/`: `uv run ruff check` and `uv run pyright`.
- **Conventions** — reference (do not duplicate) the global rules:
  composition > inheritance, explicit > defensive, fail-early / no silent
  fallbacks, no "legacy"/"compat" layers unless asked, no `Unified` prefix,
  no AI-attribution trailers on commits/PRs/comments.
- **Task system** note.
- **Key gotchas** not derivable from the code.

Companion `./CLAUDE.md` = single-line `@AGENTS.md` pointer, matching the
template pattern.

### D. Template refresh + update-mechanism honesty

- Refresh `templates/agents-md.md` for consistency with the above.
- **Document the update mechanism in both surfaces if both are touched:**
  `templates/agents-md.md` (the scaffold) and the create/import guidance in
  `commands/create-project.md`. State plainly: `/science:curate` refreshes the
  *load-bearing-constraints digest* in adopted projects from
  `core/decisions.md`, but the **static template body only applies at
  create/import time** — there is no push-to-existing-projects mechanism for
  the boilerplate. This sets an honest drift expectation.

### E. `README.md` rewrite (trim ~145 → ~80 lines)

Keep, in order:
- `Science.webp` image
- tight overview (2–3 sentences)
- **Philosophy** — the 5-bullet creed → link to Big Picture
- **Substrate / epistemic model** — key players in a few lines → link to Big
  Picture + guide
- **Data model** — one paragraph (`Entity` + `datapackage.yaml`) → link to
  `entities.md`
- **Commands** — shortlist of ~6 key commands + "full map in the user guide"
  (drop the giant command-map table). Use first-class CLI wrappers, e.g.
  `science evidence-lines create` (not `science entity create evidence-line`).
- **Skills** — brief mention + link
- condensed install / Start Here
- condensed Development (two-packages note) + License

Drop: the full command-map table and the canonical-references wall (both live
in the guide). While editing, **verify CLI command drift** against the actual
CLI (e.g. `science bib add`, proposition / evidence-line commands).

### F. `docs/user-guide/index.md` update

- Add **Big Picture** to the reading path (step 1, right after Introduction)
  and the chapter table.
- Add **Codex** to the chapter table.
- Keep the "Big Picture" vs "Big-Picture Synthesis" distinction crisp.

## Out of scope / rejected

- Separate `tldr/` folder — rejected (Markdown can't transclude; becomes copy
  or link-hub).
- Per-page TL;DR sections — rejected (duplication / drift with Big Picture).
- A dedicated data-model reference chapter — rejected (`entities.md` covers it).
- A glossary chapter — skipped (Big Picture's key-players section carries the
  vocabulary). Revisit only if requested.

## Notes for implementation

- Verified facts (2026-07-03): `science evidence-lines` is a real CLI group
  (`science/src/science_tool/cli.py:1143`); no root `pyproject.toml`
  (`science/pyproject.toml` + `science/model/pyproject.toml`);
  `datapackage.yaml` is the runtime surface (`templates/dataset.md:35`);
  `commands/create-project.md` exists; `/science:curate` digest logic lives in
  `science/src/science_tool/curate/agents_md.py`.
- Deliverables are largely independent and can be committed in logical chunks
  (Big Picture; Codex move; AGENTS + template; README; index).
