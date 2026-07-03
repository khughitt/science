# Docs: Big Picture chapter + README / AGENTS refresh — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a concise "Big Picture" user-guide chapter (single source for the conceptual TL;DR), fold the Codex doc into the guide, give the toolkit repo a root `AGENTS.md`, refresh the project AGENTS template + its update-mechanism docs, and trim the README so it stops duplicating the manual.

**Architecture:** Docs-only change. The design doc `docs/plans/2026-07-03-docs-big-picture-and-readme-refresh-design.md` is the content spec — each task below implements one of its deliverables (A–F) and references the matching design section for prose content rather than re-deriving it. Deliverables are largely independent and committed in chunks.

**Tech Stack:** Markdown. No code. Verification is by shell greps (link resolution, CLI-command drift, naming guard) — there is no markdown test runner, and `science prose lint` targets project research prose (`--root`), not these standalone guide files, so it is deliberately not used here.

## Global Constraints

- **Worktree:** All work happens in `.worktrees/docs-big-picture-readme-refresh/` on branch `docs-big-picture-readme-refresh`. Every command below runs from that worktree root. Verify with `git branch --show-current` → `docs-big-picture-readme-refresh` before committing.
- **No AI-attribution trailers** on commits (no `Co-Authored-By`, no "Generated with" footer). — per global rules.
- **Filepaths in prose:** use `~/d/...` (never `/home/keith/...` or `/mnt/ssd/Dropbox/...`) when an absolute path is unavoidable; prefer repo-relative paths.
- **Naming guard (verbatim):** the new chapter is **"Big Picture"** (`big-picture.md`); the existing generated-report chapter is **"Big-Picture Synthesis"** (`big-picture-synthesis.md`). Index and prose must make the distinction explicit.
- **CLI names are load-bearing** — every `science <cmd>` shown in the README must resolve to a real group/command in `science/src/science_tool/cli.py`. Use first-class wrappers (e.g. `science evidence-lines create`, not `science entity create evidence-line`).
- **datasets phrasing (verbatim):** runtime surface is `datapackage.yaml`; `datapackage.json` is also accepted. Never say only "JSON".
- **Content source of truth:** the design doc sections A–F. Do not invent content that contradicts them.

**Reusable verification snippets** (run from worktree root):

```bash
# LINK-CHECK: every relative .md link in FILE resolves (links are relative to FILE's dir)
check_links() {
  local f="$1"; local d; d="$(dirname "$f")"
  grep -oE '\]\(([^)]+)\)' "$f" | sed -E 's/^\]\(([^)#]+).*/\1/' \
    | grep -E '\.md$' | while read -r l; do
        case "$l" in /*|http*) continue;; esac
        [ -f "$d/$l" ] || echo "MISSING from $f -> $l"
      done
}
# CMD-DRIFT: every `science <word>` in FILE is a real top-level CLI group/command
check_cmds() {
  local f="$1"
  comm -23 \
    <(grep -oE 'science [a-z][a-z-]+' "$f" | awk '{print $2}' | sort -u) \
    <(grep -oE '@main\.(group|command)\("?[a-z-]+' science/src/science_tool/cli.py \
        | sed -E 's/.*"([a-z-]+).*/\1/' | sort -u) \
  | grep -v -E '^(bib|validate|health|graph|tasks|sync|peers)$' || true   # allowlist known multi-word/aliased
}
```

> Note on `check_cmds`: it prints command tokens present in the doc but not found as a literal `@main.group/command` name. A non-empty result is a prompt to hand-verify (some real commands are subcommands or use `name=`/aliases), not an automatic failure. The allowlist covers tokens known-good from the current README.

---

### Task 1: Big Picture chapter (`big-picture.md`) + index wiring

Implements design **A** and the Big-Picture half of **F**.

**Files:**
- Create: `docs/user-guide/big-picture.md`
- Modify: `docs/user-guide/index.md` (reading path step 1; chapter table row; naming distinction)

**Interfaces:**
- Produces: chapter file `docs/user-guide/big-picture.md` with H1 `# Big Picture` and four H2 sections in this order: `## Stance`, `## The Substrate`, `## Epistemic Model & Key Players`, `## The Data Model`. Later tasks (README) link to this file.

- [ ] **Step 1: Write `docs/user-guide/big-picture.md`**

Content per design section A. Requirements the file MUST satisfy (verified below):
- H1 `# Big Picture`; opening 1–2 sentences framing it as the concise conceptual map of Science, with a one-line pointer that this is distinct from "Big-Picture Synthesis" (the generated per-project report, `big-picture-synthesis.md`).
- `## Stance` — the five creed bullets (open data ≫ closed; open lit ≫ closed; believe nothing until we re-analyze the data ourselves; multi-dataset ≫ single-dataset; literature claims are *hints*, belief updates from our analyses; uncertainty/contestation/fragility stay visible). Ends with: `→ full detail: [Introduction](introduction.md), [Epistemic Model](epistemic-model.md)`.
- `## The Substrate` — authored project files (especially Markdown/YAML entity files, but also bibliography, source records, sidecar annotations, terms, manifests) are the source of truth; graph/summaries/snapshots/health are *derived views*; heterogeneous **patchwork** of small epistemic neighborhoods; **commons** (shared datasets / reference graphs, peers & sync); fix-the-source-then-rebuild (never patch generated TriG). Ends with: `→ full detail: [Science Model](science-model.md), [Cross-Project Work](cross-project-work.md)`.
- `## Epistemic Model & Key Players` — the pipeline `question → hypothesis → proposition → observation / evidence-line → belief → snapshot`, the role of each player, "evidence *supports / disputes*, never *proves*", and one paragraph on belief aggregation (log-odds, independence, authored-confidence and dataset-QA ceilings). Ends with: `→ full detail: [Epistemic Model](epistemic-model.md), [Evidence Lines](evidence-lines.md)`.
- `## The Data Model` — `Entity` = typed `kind:id` record, Markdown + YAML frontmatter, relations connect entities, kind descriptors are the per-kind SSOT, three classes (epistemic / operational / reference); dataset schema = Frictionless Data Package with runtime `datapackage.yaml` (`datapackage.json` also accepted), typed Data Resource schema, QA verdicts feed belief. Ends with: `→ full detail: [Entities](entities.md)`.

- [ ] **Step 2: Wire into `index.md`**

- Reading Path: insert Big Picture as the new step right after Introduction, e.g. change step 1 to `1. Start with [Introduction](introduction.md), then the [Big Picture](big-picture.md).` and keep [Science Model] in the subsequent step.
- Chapter table: add a row immediately below Introduction:
  `| [Big Picture](big-picture.md) | Concise conceptual map: stance, substrate, epistemic model, and data model, each linking down to its detailed chapter. |`
- Ensure the existing `[Big-Picture Synthesis](big-picture-synthesis.md)` row keeps its distinct wording ("Generated synthesis reports …"). If ambiguous, tighten its Purpose cell to start with "Generated per-project synthesis …".

- [ ] **Step 3: Verify links + naming guard**

```bash
cd .worktrees/docs-big-picture-readme-refresh
source /dev/stdin <<'EOF'
<paste the check_links function from Global Constraints>
EOF
check_links docs/user-guide/big-picture.md      # expect: no output
check_links docs/user-guide/index.md            # expect: no output
grep -c 'big-picture-synthesis.md' docs/user-guide/index.md   # expect: >=1 (row preserved)
grep -E 'Big Picture|Big-Picture Synthesis' docs/user-guide/index.md   # eyeball: both present, distinct
```
Expected: no `MISSING` lines; both chapters present and distinguishable.

- [ ] **Step 4: Commit**

```bash
git add docs/user-guide/big-picture.md docs/user-guide/index.md
git commit -m "docs: add Big Picture user-guide chapter"
```

---

### Task 2: Move Codex doc into the guide

Implements design **B** and the Codex half of **F**.

**Files:**
- Rename: `docs/README.codex.md` → `docs/user-guide/codex.md`
- Modify: `docs/user-guide/index.md` (add Codex chapter row)
- Modify: any file referencing the old path (fixed in Step 2)

**Interfaces:**
- Produces: `docs/user-guide/codex.md` (canonical Codex chapter). README (Task 6) links here.

- [ ] **Step 1: Move the file (preserve history)**

```bash
cd .worktrees/docs-big-picture-readme-refresh
git mv docs/README.codex.md docs/user-guide/codex.md
```

- [ ] **Step 2: Find and update inbound references to the old path**

```bash
rg -n --hidden -g '!.git' -l 'README\.codex\.md' .
```
Expected files include at least `README.md` and `docs/user-guide/index.md`'s canonical-references-style links if present. For each hit, replace `docs/README.codex.md` → `docs/user-guide/codex.md` (adjust relative prefix per the referencing file's location; e.g. from inside `docs/user-guide/` the link is `codex.md`). Also check `README.md`'s "For Codex, see …" line and its Canonical References list.

- [ ] **Step 3: Fix drift inside `codex.md`**

- Verify the title/heading still reads sensibly as a guide chapter ("Science for Codex" is fine).
- Verify any self-referential or repo-root-relative links still resolve from the new location; fix relative prefixes (`../` depth changed by one level).

- [ ] **Step 4: Add to index chapter table**

Add near the Agent Workflows row:
`| [Codex](codex.md) | Using Science with OpenAI Codex via native skill discovery: install and skill generation. |`

- [ ] **Step 5: Verify no dangling old path + links resolve**

```bash
rg -n 'README\.codex\.md' . -g '!.git'          # expect: no output
check_links docs/user-guide/codex.md             # expect: no output
check_links docs/user-guide/index.md             # expect: no output
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: move Science-for-Codex doc into user guide"
```

---

### Task 3: Root `AGENTS.md` + `CLAUDE.md` pointer

Implements design **C**.

**Files:**
- Create: `AGENTS.md` (repo root)
- Create: `CLAUDE.md` (repo root) — single-line pointer

**Interfaces:**
- Produces: root `AGENTS.md` dev guide; `CLAUDE.md` containing exactly `@AGENTS.md`.

- [ ] **Step 1: Write root `AGENTS.md`**

A lean dev guide for working ON the toolkit (distinct from `meta/AGENTS.md`). Required sections/content:
- `# science — Agent Guide` (or similar H1) and a "What this is" paragraph: the toolkit repo — `science/` (the `science` CLI package, `src/science_tool/`), `science/model/` (the `science-model` shared Pydantic package), plus `skills/`, `commands/`, `templates/`, `agents/`. Note that `meta/` is a *separate* Science research project (see `meta/AGENTS.md`) — do not confuse the two.
- **Layout / packages** section stating verbatim: there is **no root `pyproject.toml`**; CLI / package work runs from `science/`, model work from `science/model/` (uv source `model`, editable). There is also `science/qa` (`science-qa`).
- **Validation / tests** with concrete commands:
  - CLI package: `cd science && uv run --frozen pytest`
  - Model package: `cd science/model && uv run --frozen pytest`
  - Default pytest excludes `snapshot` and `real_projects` markers; opt in with `-m snapshot` / `-m real_projects`.
  - Lint / types (under `science/`): `uv run ruff check`, `uv run pyright`.
- **Conventions** — reference (do NOT duplicate) the global rules: composition > inheritance; explicit > defensive; fail-early / no silent fallbacks; no "legacy"/"compatibility" layers unless asked; no `Unified` prefix on component names; no AI-attribution trailers on commits/PRs/comments.
- **Docs** — user guide lives in `docs/user-guide/` (start at `index.md` → `big-picture.md`); conventions in `docs/conventions/`; plans/designs in `docs/plans/`.
- **Pointers** — `docs/user-guide/index.md`, `docs/user-guide/big-picture.md`, `templates/agents-md.md` (the project scaffold), `meta/AGENTS.md` (the meta project).

- [ ] **Step 2: Write root `CLAUDE.md`**

Exactly one line:
```text
@AGENTS.md
```

- [ ] **Step 3: Verify**

```bash
cd .worktrees/docs-big-picture-readme-refresh
test "$(cat CLAUDE.md)" = "@AGENTS.md" && echo OK-pointer
grep -q 'no root `pyproject.toml`' AGENTS.md && echo OK-nested-note
grep -q 'cd science && uv run --frozen pytest' AGENTS.md && echo OK-test-cmd
check_links AGENTS.md    # expect: no MISSING (meta/AGENTS.md, templates/agents-md.md, docs/... must exist)
```
Expected: `OK-pointer`, `OK-nested-note`, `OK-test-cmd`, no `MISSING`.

- [ ] **Step 4: Commit**

```bash
git add AGENTS.md CLAUDE.md
git commit -m "docs: add root AGENTS.md dev guide and CLAUDE.md pointer"
```

---

### Task 4: Refresh project AGENTS template + document its update mechanism

Implements design **D**.

**Files:**
- Modify: `templates/agents-md.md`
- Modify: `commands/create-project.md`

**Interfaces:**
- Consumes: nothing from prior tasks.
- Produces: updated scaffold + honest update-mechanism documentation.

- [ ] **Step 1: Read current state**

```bash
cd .worktrees/docs-big-picture-readme-refresh
sed -n '1,90p' templates/agents-md.md
rg -n -i 'agents\.md|curate|decisions' commands/create-project.md
```

- [ ] **Step 2: Refresh `templates/agents-md.md`**

- Keep it short and keep the `BEGIN/END: load-bearing-constraints` managed block intact (that block is managed by `/science:curate`).
- Ensure the Validation and Task-execution sections still reflect current commands.
- If the template references the user guide, point at `docs/user-guide/index.md` / `big-picture.md` conventions where appropriate (do not inline).

- [ ] **Step 3: Document the update mechanism (honesty note) in BOTH surfaces**

Add a short, explicit note — same substance in both places:
- In `templates/agents-md.md` top comment (or a `<!-- -->` note): `/science:curate` refreshes the load-bearing-constraints digest from `core/decisions.md`, but the **static body of this template only applies at create/import time** — there is no push-to-existing-projects mechanism for the boilerplate; edit your project's `AGENTS.md` directly for body changes.
- In `commands/create-project.md`, in the AGENTS.md scaffold guidance, state the same: the scaffold is written once at project creation; ongoing changes to the template do not propagate to existing projects; `/science:curate` only manages the constraints digest.

- [ ] **Step 4: Verify**

```bash
grep -q 'BEGIN: load-bearing-constraints' templates/agents-md.md && echo OK-managed-block
grep -qi 'create/import time\|does not propagate\|only applies at create' templates/agents-md.md && echo OK-tmpl-note
grep -qi 'curate\|does not propagate\|written once' commands/create-project.md && echo OK-cmd-note
```
Expected: all three `OK-*`.

- [ ] **Step 5: Commit**

```bash
git add templates/agents-md.md commands/create-project.md
git commit -m "docs: document AGENTS.md template update mechanism and refresh scaffold"
```

---

### Task 5: Rewrite `README.md`

Implements design **E**. Do this near-last so links to `big-picture.md` and `docs/user-guide/codex.md` already exist.

**Files:**
- Modify: `README.md` (repo root)

**Interfaces:**
- Consumes: `docs/user-guide/big-picture.md` (Task 1), `docs/user-guide/codex.md` (Task 2).

- [ ] **Step 1: Rewrite to the trimmed structure (~80 lines)**

Sections in order, per design E:
1. `# Science` + `![Science](extra/Science.webp)` (keep image path exactly).
2. Overview — 2–3 sentences.
3. `## Philosophy` — the five-bullet creed (mirror `big-picture.md#stance`, condensed) → link `See [Big Picture](docs/user-guide/big-picture.md) for the full stance.`
4. `## Substrate & Epistemic Model` — a few lines naming the key players (authored files → derived views; patchwork; commons; question→hypothesis→proposition→evidence→belief) → link to `docs/user-guide/big-picture.md` and the detailed chapters.
5. `## Data Model` — one paragraph: `Entity` (typed `kind:id`, Markdown + YAML frontmatter, relations) and datasets as Frictionless Data Packages (`datapackage.yaml`, `datapackage.json` accepted) → link `docs/user-guide/entities.md`.
6. `## Commands` — a shortlist of ~6 key commands (e.g. `/science:create-project`, `/science:status`, `/science:next-steps`, `science graph build`, `science evidence-lines create`, `science validate`) + "Full command map in the [user guide](docs/user-guide/agent-workflows.md)." Drop the large command-map table.
7. `## Skills` — one or two sentences + link to the guide.
8. `## Start Here` — condensed install (plugin + `claude --plugin-dir`; Codex → `docs/user-guide/codex.md`).
9. `## Development` — keep the two-package table (condensed) + Python ≥ 3.11 note.
10. `## License` — MIT.

Remove: the full Command Map table and the Canonical References wall (both now live in the guide).

- [ ] **Step 2: Verify command drift + links + datapackage phrasing**

```bash
cd .worktrees/docs-big-picture-readme-refresh
check_cmds README.md         # inspect any output; hand-verify each token is a real command/subcommand
check_links README.md        # expect: no MISSING
grep -q 'datapackage.yaml' README.md && echo OK-yaml
! grep -qE '\| Intent \| Claude \| Codex \| CLI \|' README.md && echo OK-table-removed
grep -q 'evidence-lines create' README.md && echo OK-first-class-wrapper
```
Expected: `check_cmds` output empty or all-hand-verified; no `MISSING`; `OK-yaml`, `OK-table-removed`, `OK-first-class-wrapper`.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: trim README to essentials, add philosophy and data-model sections"
```

---

### Task 6: Final cross-doc consistency pass

Catches drift introduced across tasks (index completeness, dangling links repo-wide).

**Files:**
- Modify (only if issues found): `docs/user-guide/index.md`, any file with a broken link.

- [ ] **Step 1: Repo-wide link + reference audit**

```bash
cd .worktrees/docs-big-picture-readme-refresh
for f in README.md AGENTS.md docs/user-guide/*.md; do check_links "$f"; done   # expect: no MISSING
rg -n 'README\.codex\.md' . -g '!.git'          # expect: no output
# every user-guide .md (except index) appears in the index chapter table:
for f in docs/user-guide/*.md; do b="$(basename "$f")"; [ "$b" = index.md ] && continue; \
  grep -q "($b)" docs/user-guide/index.md || echo "NOT IN INDEX: $b"; done
```
Expected: no `MISSING`, no old-path hits, no `NOT IN INDEX` lines.

- [ ] **Step 2: Naming guard final check**

```bash
grep -E 'Big Picture|Big-Picture Synthesis' docs/user-guide/index.md README.md
```
Eyeball: "Big Picture" (conceptual map) and "Big-Picture Synthesis" (generated report) are clearly different in every occurrence.

- [ ] **Step 3: Fix any findings, then commit**

```bash
git add -A
git commit -m "docs: cross-doc consistency pass for guide restructure"   # skip if nothing changed
```

---

## Self-Review

**Spec coverage (design A–F):**
- A (Big Picture chapter) → Task 1. ✓
- B (Codex move) → Task 2. ✓
- C (root AGENTS.md + CLAUDE.md) → Task 3. ✓
- D (template refresh + mechanism docs) → Task 4. ✓
- E (README rewrite) → Task 5. ✓
- F (index update: Big Picture + Codex, naming guard) → split into Task 1 Step 2 (Big Picture row) and Task 2 Step 4 (Codex row), with Task 6 auditing completeness. ✓

**Placeholder scan:** No "TBD"/"handle edge cases"/"similar to". Prose content is specified as concrete required-content bullets + verifiable assertions, deferring full paragraphs to the design doc (the content SSOT) by explicit section reference — not a placeholder. ✓

**Consistency:** File paths, the `check_links`/`check_cmds` helpers, the `datapackage.yaml` phrasing, the `science evidence-lines create` wrapper, and the "Big Picture" vs "Big-Picture Synthesis" names are used identically across tasks. ✓

**Note:** Verification is grep-based (no markdown test runner exists); each task's verify step asserts the concrete facts that must appear, which is the doc-work analogue of a passing test.
