# Skills Corpus Reorganization + Rename (Phase 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the 46-file `skills/` corpus into a subject/domain tree, split the overloaded
`statistics/` into `statistics/` (modeling) + `study-design/` (disciplines), and re-prefix every
moved leaf's `name:` onto its new subject — with no teaching-content extraction (phase 4).

**Architecture:** `git mv` files into the new tree + re-prefix `name:`; rewrite all cross-`.md`
links, `INDEX.md`, and routers; drop the `research-methodology` Codex companion and rewrite its
callers; update every path/name-coupled site in code, tests, commands, references, templates,
aspects, and doctrine; regenerate the `codex-skills/` mirror. The design is
`docs/plans/2026-07-20-skills-reorg-design.md` (read it once for rationale; this plan is
self-contained for execution).

**Tech Stack:** Python toolkit under `science/` (run `uv run --frozen …` from `science/`); Markdown
skill corpus under `skills/`; generated mirror under `codex-skills/` via
`scripts/generate_codex_skills.py`; linter `science skills lint`.

> **RED-by-construction.** Every file cross-links and cross-names, so **Tasks 1–4 commit RED** — the
> moment files move + rename, links and name references dangle until every consumer lands. The
> **single green gate is Task 5**. Reviewers of Tasks 1–4 verify correctness **by inspection against
> the maps in this plan**, not by a green suite. This mirrors phase 2 (hub extraction), where the
> owner ratified RED intermediates with the gate at the closing task.

## Global Constraints

- No AI-attribution trailers/footers on commits (no `Co-Authored-By`, no "Generated with").
- No "legacy"/"compatibility" layers; no "Unified" prefix. Composition > inheritance; explicit >
  defensive; fail early / no silent fallbacks.
- All `uv run` from `science/` (no root `pyproject.toml`); test dirs are not type-checked.
- `codex-skills/` is **generated** — never hand-edit; only `scripts/generate_codex_skills.py` writes it.
- Use `git mv` (preserve history), never delete + re-add. `git mv` auto-creates parent directories.
- Subject-prefix rule for names: `name = <subject>-<operation>`, subject = innermost subject folder
  (`bio/`, `ml/` are navigational parents, **not** name parts).
- Nothing pushed to origin unless the owner asks. Work stays on branch `skills-reorg`.

## Authoritative maps (used by multiple tasks)

### MAP-A — moved paths (old → new), all repo-relative under `skills/`

```
# --- to bio/genomics/ ---
data/genomics/somatic-mutation-qa.md                  -> bio/genomics/somatic-mutation-qa.md
data/genomics/copy-number-sv-qa.md                    -> bio/genomics/copy-number-sv-qa.md
data/genomics/mutational-signatures-and-selection.md  -> bio/genomics/mutational-signatures-and-selection.md
data/genomics/SKILL.md                                -> bio/genomics/SKILL.md
# --- to bio/transcriptomics/ ---
data/expression/bulk-rnaseq-qa.md                     -> bio/transcriptomics/bulk-rnaseq-qa.md
data/expression/microarray-qa.md                      -> bio/transcriptomics/microarray-qa.md
data/expression/scrna-qa.md                           -> bio/transcriptomics/scrna-qa.md
data/expression/SKILL.md                              -> bio/transcriptomics/SKILL.md
# --- to bio/proteomics/ ---
data/proteomics-qa.md                                 -> bio/proteomics/proteomics-qa.md
data/protein-sequence-structure-qa.md                 -> bio/proteomics/protein-sequence-structure-qa.md
# --- to bio/ (loose) ---
data/functional-genomics-qa.md                        -> bio/functional-genomics-qa.md
# --- to ml/ ---
data/embeddings-manifold-qa.md                        -> ml/embeddings-manifold-qa.md
# --- to data-management/ ---
data/frictionless.md                                  -> data-management/frictionless.md
data/SKILL.md                                         -> data-management/SKILL.md
# --- to literature/ ---
data/sources/openalex.md                              -> literature/sources/openalex.md
data/sources/pubmed.md                                -> literature/sources/pubmed.md
research/literature-evaluation.md                     -> literature/literature-evaluation.md
research/citation-discipline.md                       -> literature/citation-discipline.md
# --- to epistemics/ ---
research/proposition-schema.md                        -> epistemics/proposition-schema.md
research/proposition-graph-reasoning.md               -> epistemics/proposition-graph-reasoning.md
research/annotation-curation-qa.md                    -> epistemics/annotation-curation-qa.md
# --- to research-package/ ---
research/research-package-spec.md                     -> research-package/research-package-spec.md
research/research-package-rendering.md                -> research-package/research-package-rendering.md
# --- to study-design/ (from statistics/) ---
statistics/bias-vs-variance-decomposition.md          -> study-design/bias-vs-variance-decomposition.md
statistics/causal-identification.md                   -> study-design/causal-identification.md
statistics/estimator-certification.md                 -> study-design/estimator-certification.md
statistics/power-floor-acknowledgement.md             -> study-design/power-floor-acknowledgement.md
statistics/prereg-amendment-vs-fresh.md               -> study-design/prereg-amendment-vs-fresh.md
statistics/prereg-defensive-instrumentation.md        -> study-design/prereg-defensive-instrumentation.md
statistics/replicate-count-justification.md           -> study-design/replicate-count-justification.md
statistics/sensitivity-arbitration.md                 -> study-design/sensitivity-arbitration.md
# --- deleted (research/ dissolves) ---
research/SKILL.md                                     -> (git rm)
```

### MAP-B — renamed `name:` identifiers (old → new)

Leaves (26):

```
data-genomics-somatic-mutation-qa                 -> genomics-somatic-mutation-qa
data-genomics-copy-number-sv-qa                   -> genomics-copy-number-sv-qa
data-genomics-mutational-signatures-and-selection -> genomics-mutational-signatures-and-selection
data-expression-bulk-rnaseq-qa                    -> transcriptomics-bulk-rnaseq-qa
data-expression-microarray-qa                     -> transcriptomics-microarray-qa
data-expression-scrna-qa                          -> transcriptomics-scrna-qa
data-proteomics-qa                                -> proteomics-qa
data-protein-sequence-structure-qa               -> proteomics-protein-sequence-structure-qa
data-functional-genomics-qa                       -> functional-genomics-qa
data-embeddings-manifold-qa                       -> ml-embeddings-manifold-qa
data-frictionless                                 -> data-management-frictionless
data-source-openalex                              -> literature-source-openalex
data-source-pubmed                                -> literature-source-pubmed
research-literature-evaluation                    -> literature-evaluation
research-citation-discipline                      -> literature-citation-discipline
research-proposition-schema                       -> epistemics-proposition-schema
research-proposition-graph-reasoning              -> epistemics-proposition-graph-reasoning
research-annotation-curation-qa                   -> epistemics-annotation-curation-qa
statistics-bias-vs-variance-decomposition         -> study-design-bias-vs-variance-decomposition
statistics-causal-identification                  -> study-design-causal-identification
statistics-estimator-certification                -> study-design-estimator-certification
statistics-power-floor-acknowledgement            -> study-design-power-floor-acknowledgement
statistics-prereg-amendment-vs-fresh              -> study-design-prereg-amendment-vs-fresh
statistics-prereg-defensive-instrumentation       -> study-design-prereg-defensive-instrumentation
statistics-replicate-count-justification          -> study-design-replicate-count-justification
statistics-sensitivity-arbitration                -> study-design-sensitivity-arbitration
```

Routers (2): `data-genomics -> genomics`, `data-expression -> transcriptomics`.
**Unchanged names** (do NOT touch): the 6 `statistics-*` modeling leaves, 3 `pipeline-*`,
`scientific-writing`, `research-package-spec`, `research-package-rendering`, and routers
`data-management`, `statistics`, `pipelines`, `writing`.

## File Structure

New folders (created implicitly by `git mv`): `skills/bio/{,genomics/,transcriptomics/,proteomics/}`,
`skills/ml/`, `skills/data-management/`, `skills/study-design/`, `skills/epistemics/`,
`skills/literature/{,sources/}`, `skills/research-package/`. Dissolved: `skills/data/`,
`skills/research/`. Unchanged: `skills/{statistics,pipelines,writing,meta}/`.

New router files (7): `bio/SKILL.md` (`bio`), `bio/proteomics/SKILL.md` (`proteomics`), `ml/SKILL.md`
(`ml`), `study-design/SKILL.md` (`study-design`), `epistemics/SKILL.md` (`epistemics`),
`literature/SKILL.md` (`literature`), `research-package/SKILL.md` (`research-package`). Each is a
**pure router** — follow `skills/meta/templates/router.md`; frontmatter `name` + `description` only
(no `archetype:`), a one-paragraph scope line, and a routing table `| leaf | load when |`.

---

### Task 1: Move files + re-prefix names

**Files:**
- Move/rename: all rows in MAP-A (`git mv`) + `git rm skills/research/SKILL.md`.
- Modify `name:` frontmatter: the 26 leaves in MAP-B + 2 routers (`bio/genomics/SKILL.md`,
  `bio/transcriptomics/SKILL.md`).

**Interfaces:**
- Produces: the new file tree and new `name:` values that every later task and MAP-A/MAP-B rely on.
  Consumes: nothing.

- [ ] **Step 1: Apply MAP-A moves.** From repo root, run each `git mv` in MAP-A verbatim, then
  `git rm skills/research/SKILL.md`. (`git mv` creates the destination directories.)

- [ ] **Step 2: Verify the tree.** Run:

```bash
# every OLD path is gone; every NEW path exists
git -C . status --porcelain | grep -E '^R' | wc -l   # expect 31 renames (28 leaves + 3 routers)
test ! -e skills/data && test ! -e skills/research/SKILL.md && echo "data/ + research/SKILL.md gone"
find skills -name '*.md' ! -name 'SKILL.md' ! -name 'INDEX.md' | grep -v meta/templates | wc -l  # expect 38
```
Expected: 31 renames, both gone, 38 leaves.

- [ ] **Step 3: Re-prefix `name:` fields.** For each MAP-B row, edit the target file's `name:` line
  (line 2) from old to new. Also set `bio/genomics/SKILL.md` → `name: genomics` and
  `bio/transcriptomics/SKILL.md` → `name: transcriptomics`. Change **only** the `name:` line; touch
  no body content.

- [ ] **Step 4: Verify names.** Run:

```bash
# no old renamed name survives anywhere under skills/
for old in data-genomics-somatic-mutation-qa data-expression-scrna-qa data-proteomics-qa \
  data-protein-sequence-structure-qa data-functional-genomics-qa data-embeddings-manifold-qa \
  data-frictionless data-source-openalex data-source-pubmed research-literature-evaluation \
  research-citation-discipline research-proposition-schema research-proposition-graph-reasoning \
  research-annotation-curation-qa statistics-sensitivity-arbitration statistics-estimator-certification \
  data-genomics data-expression; do
    grep -rn "name: $old\b" skills/ && echo "LEFTOVER: $old";
  done; echo "name check done"
grep -c '^name: study-design-' skills/study-design/*.md | grep -v ':1' ; echo "study-design names ok"
```
Expected: no `LEFTOVER` lines. (Full suite/lint are RED here — that is expected; do NOT run them as a gate.)

- [ ] **Step 5: Commit.**

```bash
git add -A
git commit -m "refactor(skills): move corpus into subject/domain tree + re-prefix names (phase 3, task 1)"
```

---

### Task 2: Rewrite cross-links, INDEX.md, and routers

**Files:**
- Modify (link rewrites): every skill file that contains a relative `.md` link to a moved target —
  discover with the grep in Step 1.
- Rewrite: `skills/INDEX.md`.
- Retarget routers: `skills/bio/genomics/SKILL.md`, `skills/bio/transcriptomics/SKILL.md`,
  `skills/data-management/SKILL.md`, `skills/statistics/SKILL.md`.
- Create routers (7): `bio/SKILL.md`, `bio/proteomics/SKILL.md`, `ml/SKILL.md`,
  `study-design/SKILL.md`, `epistemics/SKILL.md`, `literature/SKILL.md`, `research-package/SKILL.md`.

**Interfaces:**
- Consumes: MAP-A (target paths) and the new tree from Task 1.
- Produces: a fully self-consistent `skills/` link graph + INDEX (validated by `skills lint` in Task 5).

- [ ] **Step 1: Find every intra-skills link to rewrite.**

```bash
grep -rnoE '\]\(([.][.]?/)+[A-Za-z0-9./_-]+\.md\)' skills/ | sort   # all relative .md links
grep -rnoE '`[a-z0-9./_-]+\.md`' skills/ | grep -vE 'templates/' | sort  # inline-code path mentions
```

- [ ] **Step 2: Rewrite each link to its target's NEW relative path.** For every link found, resolve
  the target against MAP-A and recompute the relative path from the **source file's new location**.
  Rules: `bio/genomics/` and `bio/transcriptomics/` sit at the same depth as `data/genomics/` and
  `data/expression/` (depth 2), but `data/proteomics-qa.md` (depth 1) → `bio/proteomics/…` (depth 2),
  and `data/*` (depth 1) → `data-management/`, `ml/`, `literature/`, `epistemics/`, `study-design/`,
  `research-package/` (depth 1) — recompute `../` counts accordingly. Any link into the dissolved
  `research/SKILL.md` must instead point at the relevant `literature/`/`epistemics/`/`research-package/`
  leaf (or be dropped if it was a router pointer with no leaf equivalent).

- [ ] **Step 3: Retarget the 4 surviving/moved routers.**
  - `bio/genomics/SKILL.md`, `bio/transcriptomics/SKILL.md`: fix their internal routing links (same
    filenames, now siblings — usually unchanged, but verify).
  - `data-management/SKILL.md`: its routing table pointed at the data-QA leaves that left for `bio/`;
    repoint those rows to `../bio/…` (leave its teaching body intact — extraction is phase 4). Fix
    its `../research/SKILL.md` link per Task 4 (or drop; see Task 4 Step 4).
  - `statistics/SKILL.md`: **remove** routing rows for the 8 leaves that moved to `study-design/`;
    keep the 6 modeling leaves. Do not trim the Principles prose (phase 4).

- [ ] **Step 4: Author the 7 new routers.** Follow `skills/meta/templates/router.md`. Frontmatter:
  `name:` (per File Structure), a one-line `description:`, **no `archetype:`**. Body: a one-sentence
  scope line + a routing table listing that folder's leaves with a "load when" phrase. Routing
  targets:
  - `bio/SKILL.md` → `genomics/SKILL.md`, `transcriptomics/SKILL.md`, `proteomics/SKILL.md`,
    `functional-genomics-qa.md` (and a pointer to sibling `../ml/` for embedding QA).
  - `bio/proteomics/SKILL.md` → `proteomics-qa.md`, `protein-sequence-structure-qa.md`.
  - `ml/SKILL.md` → `embeddings-manifold-qa.md`.
  - `study-design/SKILL.md` → the 8 discipline leaves.
  - `epistemics/SKILL.md` → `proposition-schema.md`, `proposition-graph-reasoning.md`,
    `annotation-curation-qa.md`.
  - `literature/SKILL.md` → `literature-evaluation.md`, `citation-discipline.md`,
    `sources/openalex.md`, `sources/pubmed.md`.
  - `research-package/SKILL.md` → `research-package-spec.md`, `research-package-rendering.md`.

- [ ] **Step 5: Rewrite `skills/INDEX.md`.** Reproduce every leaf as a `` `new-name`: `skills/new/path.md` ``
  entry (both columns from MAP-A/MAP-B), grouped by the new folders, and **remove** the
  `research-methodology` router row. Match the existing INDEX format exactly (see the pre-move file
  in `git show HEAD~1:skills/INDEX.md`).

- [ ] **Step 6: Verify no dangling intra-skills link (structural, pre-lint).**

```bash
uv run --frozen python - <<'PY'
import pathlib, re
root = pathlib.Path("skills")
bad = []
for md in root.rglob("*.md"):
    for m in re.finditer(r'\]\((\.\.?/[^)]+\.md)\)', md.read_text()):
        tgt = (md.parent / m.group(1)).resolve()
        if not tgt.exists():
            bad.append(f"{md}: {m.group(1)}")
print("DANGLING:", *bad, sep="\n") if bad else print("no dangling intra-skills links")
PY
```
Expected: "no dangling intra-skills links". (Run from `science/`? No — run from repo root; adjust `skills` path if needed.) Full pytest/lint remain RED (external consumers not yet updated).

- [ ] **Step 7: Commit.**

```bash
git add -A
git commit -m "refactor(skills): rewrite links, INDEX, and routers for the new tree (phase 3, task 2)"
```

---

### Task 3: Update non-Codex path/name-coupled sites

**Files:**
- `science/src/science_tool/skills_lint/lint.py` (`HALT_ON_REQUIRED`).
- External live links: `commands/plan-analysis.md:171`, `commands/pre-register.md:124`,
  `aspects/computational-analysis/computational-analysis.md:72`, `templates/pre-registration.md:170`,
  `science/model/src/science_model/templates/pre-registration.md:170`.
- Doctrine: `skills/meta/skill-authoring.md` (lines ~34, ~43), `skills/meta/skill-taxonomy.md`
  (line ~109), and `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md` (annotation only).

**Interfaces:**
- Consumes: MAP-A, MAP-B. Produces: linter + external docs consistent with the new tree.

- [ ] **Step 1: Update `HALT_ON_REQUIRED`.** Replace the set in `lint.py` with the 9 new paths:

```python
HALT_ON_REQUIRED = {
    "ml/embeddings-manifold-qa.md",
    "bio/functional-genomics-qa.md",
    "bio/proteomics/protein-sequence-structure-qa.md",
    "bio/transcriptomics/bulk-rnaseq-qa.md",
    "bio/transcriptomics/microarray-qa.md",
    "bio/transcriptomics/scrna-qa.md",
    "bio/genomics/somatic-mutation-qa.md",
    "bio/genomics/mutational-signatures-and-selection.md",
    "epistemics/annotation-curation-qa.md",
}
```

- [ ] **Step 2: Retarget the 5 external `estimator-certification` links.** In each of the 5 files,
  update the path `skills/statistics/estimator-certification.md` →
  `skills/study-design/estimator-certification.md` (fix `../` depth per file) **and** the link/inline
  text `statistics-estimator-certification` → `study-design-estimator-certification`. Both
  pre-registration templates (root + packaged `science/model/.../templates/`) must end **identical**.

- [ ] **Step 3: Update doctrine.** In `skill-authoring.md` and `skill-taxonomy.md`: change the
  "reorg/rename deferred to phase 3" statements to "reorg + rename completed in phase 3; hub
  **extraction** + principle-trimming + `frictionless`/`mutational-signatures` splits remain (phase
  4)"; update the remaining-hub list to `data-management/`, `bio/transcriptomics/`, `pipelines/`,
  `statistics/`; and state that subject prefixes now reflect the new placement. In the
  subject-prefix bullet (`skill-authoring.md:34`), replace the pre-migration prefix list with the
  new subjects (`genomics-`, `transcriptomics-`, `proteomics-`, `ml-`, `data-management-`,
  `study-design-`, `epistemics-`, `literature-`, `literature-source-`, unchanged `statistics-`,
  `pipeline-`).

- [ ] **Step 4: Annotate the corpus matrix.** Add a one-line note at the top of
  `2026-07-19-skills-taxonomy-corpus-matrix.md` that its `path`/`name`/`subject` columns are
  **pre-reorg** (it was this phase's input). Do not rewrite its rows. Do **not** edit any other
  `docs/plans/` (historical).

- [ ] **Step 5: Verify (targeted).**

```bash
grep -rn "statistics/estimator-certification\|statistics-estimator-certification" \
  commands/ aspects/ templates/ science/model/src/science_model/templates/ && echo "LEFTOVER" || echo "external links updated"
cd science && uv run --frozen python -c "from science_tool.skills_lint.lint import HALT_ON_REQUIRED as H; assert 'epistemics/annotation-curation-qa.md' in H and not any(p.startswith(('data/','research/','statistics/')) for p in H); print('HALT_ON_REQUIRED ok', len(H))"
```
Expected: "external links updated", "HALT_ON_REQUIRED ok 9".

- [ ] **Step 6: Commit.**

```bash
git add -A
git commit -m "refactor(skills): update linter, external links, and doctrine for the new tree (phase 3, task 3)"
```

---

### Task 4: Drop the `research-methodology` Codex companion + rewrite callers

**Files:**
- `science/src/science_tool/codex_skills.py` (`COMPANION_SKILLS` line 18;
  `_rewrite_companion_skill_references` lines ~295–310).
- `references/command-preamble.md:10`; `references/role-prompts/research-assistant.md:17`;
  `references/role-prompts/discussant.md:18`.
- `commands/review.md:25`; `commands/plan-pipeline.md:9`; `commands/review-pipeline.md:9`;
  `commands/plan-analysis.md:79,197`.
- `skills/data-management/SKILL.md` (the `../research/SKILL.md` link — moved from `data/SKILL.md:188`).
- `docs/user-guide/codex.md:113`; `codex-skills/INSTALL.codex.md` (verify generated vs static — Step 6).
- Tests: `science/tests/test_codex_skills.py`, `science/tests/test_command_docs.py`.

**Interfaces:**
- Consumes: the dissolved `research/` (Task 1) + new `literature/`/`epistemics/` leaves. Produces:
  a Codex surface with no reference to the removed companion.

- [ ] **Step 1: Remove the companion + rework the rewrite rules.** In `codex_skills.py`: delete the
  `CompanionSkill("research-methodology", Path("skills/research/SKILL.md"))` entry. In
  `_rewrite_companion_skill_references`, drop the three `research-methodology` replacement pairs and
  replace the source preamble string mapping so the **new** source instruction (Step 2) maps to its
  Codex form — keep `science-scientific-writing`, and append the "consult `codex-skills/INDEX.md`"
  clause for research methodology. Keep the `scientific-writing` companion untouched.

- [ ] **Step 2: Rewrite the source instruction, one canonical form.** Replace every
  "Load the `research-methodology` and `scientific-writing` skills." (and the two shorter
  `research-methodology`-only variants in `commands/{plan-pipeline,review-pipeline}.md`) with:

> Load the `scientific-writing` skill. For research methodology, consult `skills/INDEX.md` and load
> the relevant `literature/`, `epistemics/`, and `research-package/` leaves (e.g.
> `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).

  Apply the shorter matching form where a caller only referenced `research-methodology`.

- [ ] **Step 3: Fix role prompts.** In both role prompts, change the `Skills:` line from
  `research-methodology, scientific-writing` to `scientific-writing` (+ "see `skills/INDEX.md` for
  research-methodology leaves").

- [ ] **Step 4: Fix `plan-analysis.md` skill-list rows + the moved data link.** In
  `commands/plan-analysis.md` rows 79 & 197, replace the `research-methodology` token with the
  specific leaves now carrying that content (`literature-evaluation`, `literature-citation-discipline`;
  the `research-annotation-curation-qa` token there also becomes `epistemics-annotation-curation-qa`).
  In `skills/data-management/SKILL.md`, retarget the old `../research/SKILL.md` link to
  `../literature/SKILL.md` (research-methodology context now lives under `literature/`), or drop the
  bullet if no longer apt.

- [ ] **Step 5: Update the two test files.** In `test_codex_skills.py`, remove/replace every
  `science-research-methodology` expectation (lines ~86/89/96/127/129/138/836/844/857/862): the
  companion INDEX row assertion, the `name: science-research-methodology` assertion, the
  bundled-resource link targets (`../science-research-methodology/citation-discipline.md` →
  `../science-scientific-writing/…`? no — those resources now live under the generated
  literature/epistemics **command**/companion dirs; assert against the regenerated tree from Step 6),
  and the "Load the …" preamble-rewrite assertions (align to the Step-2 text). In
  `test_command_docs.py`, update every skills path/name assertion (558-559, 608-611, 632, 657,
  778-779, 1010-1011, 1035-1036) to the new paths/names; sweep the whole file for `skills/data`,
  `skills/statistics`, `skills/research`, and old name tokens.

- [ ] **Step 6: Check INSTALL.codex.md + user guide.** Determine whether
  `codex-skills/INSTALL.codex.md` is emitted by the generator (`grep -n "INSTALL" scripts/generate_codex_skills.py science/src/science_tool/codex_skills.py`). If **generated**, leave it (Task 5 regen fixes it); if **static**, edit line 44 to drop `science-research-methodology`. Edit
  `docs/user-guide/codex.md:113` to remove `science-research-methodology` from the companion list.

- [ ] **Step 7: Commit** (still RED — mirror not yet regenerated).

```bash
git add -A
git commit -m "refactor(skills): drop research-methodology Codex companion + rewrite callers (phase 3, task 4)"
```

---

### Task 5: Regenerate the mirror + green gate

**Files:** `codex-skills/**` (generated), no source edits except fixes surfaced by the gate.

**Interfaces:** Consumes all prior tasks. Produces the committed, green end-state.

- [ ] **Step 1: Regenerate the mirror.**

```bash
cd science && uv run --frozen python ../scripts/generate_codex_skills.py
```

- [ ] **Step 2: Skills lint.**

```bash
cd science && uv run --frozen science skills lint --root ../skills
```
Expected: exit 0, no findings.

- [ ] **Step 3: No-dangling-name grep (repo-wide, excluding generated + historical).**

```bash
grep -rn "research-methodology" . --include="*.md" --include="*.py" \
  | grep -vE "\.venv|/codex-skills/|/docs/plans/|\.claude/worktrees"    # expect: no live hits
for old in data-expression- data-genomics- data-source- data-frictionless data-proteomics-qa \
  data-protein-sequence data-functional-genomics data-embeddings statistics-sensitivity-arbitration \
  statistics-estimator-certification statistics-bias-vs statistics-causal statistics-power-floor \
  statistics-prereg statistics-replicate; do
    grep -rn "$old" . --include="*.md" --include="*.py" \
      | grep -vE "\.venv|/codex-skills/|/docs/plans/|\.claude/worktrees" && echo "LEFTOVER $old";
  done; echo "name-grep done"
```
Expected: no output before "name-grep done" (no `LEFTOVER`).

- [ ] **Step 4: Full suite + committed-mirror + baselines.**

```bash
cd science && uv run --frozen pytest -q
cd science && uv run --frozen pytest -q tests/test_codex_skills.py::test_committed_codex_skills_match_fresh_generation
cd science && uv run --frozen ruff check . && uv run --frozen pyright
```
Expected: pytest green; committed-mirror test green; ruff/pyright at pre-existing baseline.

- [ ] **Step 5: Commit the regenerated mirror + any gate fixes.**

```bash
git add -A
git commit -m "refactor(skills): regenerate codex mirror; phase-3 reorg + rename complete (phase 3, task 5)"
```

---

## Self-Review

**Spec coverage** (design → task):
- Subject/domain tree + statistics split → Task 1 (moves) + Task 2 (routers/INDEX). ✓
- Name rename (MAP-B) → Task 1 Step 3. ✓
- Cross-links + INDEX + 7 new routers → Task 2. ✓
- `HALT_ON_REQUIRED` (7 bio + 1 ml + 1 epistemics) → Task 3 Step 1. ✓
- External links incl. both pre-reg templates → Task 3 Step 2. ✓
- Doctrine + corpus-matrix → Task 3 Steps 3–4. ✓
- Drop companion + rewrite all callers (generator, preamble, role prompts, commands, INDEX link,
  user guide, INSTALL) → Task 4. ✓
- test_command_docs + test_codex_skills → Task 4 Step 5. ✓
- Codex regen + full green gate + no-dangling-name grep → Task 5. ✓

**Placeholder scan:** every step names exact files/commands/values; router bodies point at the
committed `meta/templates/router.md` + explicit routing targets (prose is authored, not templated).
No "TBD"/"handle appropriately". The only deliberate branch is Task 4 Step 6 (INSTALL.codex.md
generated-vs-static), with the check that decides it.

**Type/name consistency:** MAP-A/MAP-B are the single source used across Tasks 1–4; the Task-5
name-grep is derived from MAP-B's old tokens. `HALT_ON_REQUIRED` paths match MAP-A destinations.
Green gate asserts "the nine `HALT_ON_REQUIRED` leaves" (not "measurement-qa", of which there are 11).

**Green gate:** at Task 5 only; Tasks 1–4 RED-by-construction, verified by inspection + the
structural checks embedded in each task.
