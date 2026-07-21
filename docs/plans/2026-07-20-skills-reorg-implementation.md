# Skills Corpus Reorganization + Rename (Phase 3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganize the 46-file `skills/` corpus into a subject/domain tree, split the overloaded
`statistics/` into `statistics/` (modeling) + `study-design/` (disciplines), and re-prefix every
moved leaf's `name:` onto its new subject — no teaching-content extraction (that is phase 4).

**Architecture:** `git mv` files (after `mkdir -p`) + re-prefix `name:`; rewrite all cross-`.md`
links, `INDEX.md`, and routers; drop the `research-methodology` Codex companion and rewrite its
callers; update every path/name-coupled site in code, tests, commands, references, templates,
aspects, and doctrine; regenerate the `codex-skills/` mirror. Rationale is in
`docs/plans/2026-07-20-skills-reorg-design.md`; this plan is self-contained for execution.

**Tech Stack:** Python toolkit under `science/` (run `uv run --frozen …` **from `science/`**);
Markdown corpus under `skills/`; generated mirror under `codex-skills/` via
`scripts/generate_codex_skills.py`; linter `science skills lint`.

> **RED-by-construction.** Every file cross-links and cross-names, so **Tasks 1–4 commit RED**. The
> **single green gate is Task 5**. Reviewers of Tasks 1–4 verify correctness **by inspection against
> the maps below** plus each task's embedded structural checks, not by a green suite. This mirrors
> phase 2, where the owner ratified RED intermediates with the gate at the closing task.

## Global Constraints

- No AI-attribution trailers/footers on commits. No "legacy"/"compatibility" layers; no "Unified"
  prefix. Composition > inheritance; explicit > defensive; fail early / no silent fallbacks.
- All `uv run` **from `science/`** (no root `pyproject.toml`); test dirs are not type-checked.
- **Generated** `codex-skills/` outputs — `INDEX.md` and the `science-*/` skill dirs — are written
  only by `scripts/generate_codex_skills.py`; never hand-edit them. `codex-skills/INSTALL.codex.md`
  is **static** (not generated) and **is** hand-edited in this plan.
- The generator **regenerates in place** but does **not** prune orphaned `science-*/` dirs, so
  dropping the `research-methodology` companion would leave a stale `codex-skills/science-research-methodology/`
  that fails `test_committed_codex_skills_match_fresh_generation` (which generates into a *fresh temp
  dir* and byte-compares to the committed tree). Task 4 adds stale-dir pruning to the generator (the
  durable fix — every future command/companion removal needs it), not a one-off `git rm`.
- `git mv` does **not** create destination directories and does **not** remove emptied source
  directories — `mkdir -p` before, `rmdir` after. Use `git mv` (preserve history), never delete+add.
- Name rule: `name = <subject>-<operation>`; subject = innermost subject folder. **`bio/` is a
  navigational parent (no `bio-` prefix); `ml` is itself a subject (its leaf is `ml-…`).** MAP-B
  below is authoritative for every name.
- Work stays on branch `skills-reorg`. Nothing pushed unless the owner asks.

## MAP-A — moved paths (old → new), repo-relative under `skills/`

```
data/genomics/somatic-mutation-qa.md                  -> bio/genomics/somatic-mutation-qa.md
data/genomics/copy-number-sv-qa.md                    -> bio/genomics/copy-number-sv-qa.md
data/genomics/mutational-signatures-and-selection.md  -> bio/genomics/mutational-signatures-and-selection.md
data/genomics/SKILL.md                                -> bio/genomics/SKILL.md
data/expression/bulk-rnaseq-qa.md                     -> bio/transcriptomics/bulk-rnaseq-qa.md
data/expression/microarray-qa.md                      -> bio/transcriptomics/microarray-qa.md
data/expression/scrna-qa.md                           -> bio/transcriptomics/scrna-qa.md
data/expression/SKILL.md                              -> bio/transcriptomics/SKILL.md
data/proteomics-qa.md                                 -> bio/proteomics/proteomics-qa.md
data/protein-sequence-structure-qa.md                 -> bio/proteomics/protein-sequence-structure-qa.md
data/functional-genomics-qa.md                        -> bio/functional-genomics-qa.md
data/embeddings-manifold-qa.md                        -> ml/embeddings-manifold-qa.md
data/frictionless.md                                  -> data-management/frictionless.md
data/SKILL.md                                         -> data-management/SKILL.md
data/sources/openalex.md                              -> literature/sources/openalex.md
data/sources/pubmed.md                                -> literature/sources/pubmed.md
research/literature-evaluation.md                     -> literature/literature-evaluation.md
research/citation-discipline.md                       -> literature/citation-discipline.md
research/proposition-schema.md                        -> epistemics/proposition-schema.md
research/proposition-graph-reasoning.md               -> epistemics/proposition-graph-reasoning.md
research/annotation-curation-qa.md                    -> epistemics/annotation-curation-qa.md
research/research-package-spec.md                     -> research-package/research-package-spec.md
research/research-package-rendering.md                -> research-package/research-package-rendering.md
statistics/bias-vs-variance-decomposition.md          -> study-design/bias-vs-variance-decomposition.md
statistics/causal-identification.md                   -> study-design/causal-identification.md
statistics/estimator-certification.md                 -> study-design/estimator-certification.md
statistics/power-floor-acknowledgement.md             -> study-design/power-floor-acknowledgement.md
statistics/prereg-amendment-vs-fresh.md               -> study-design/prereg-amendment-vs-fresh.md
statistics/prereg-defensive-instrumentation.md        -> study-design/prereg-defensive-instrumentation.md
statistics/replicate-count-justification.md           -> study-design/replicate-count-justification.md
statistics/sensitivity-arbitration.md                 -> study-design/sensitivity-arbitration.md
research/SKILL.md                                     -> (git rm — research/ dissolves)
```

Emptied dirs to `rmdir` after moves: `skills/data/genomics`, `skills/data/expression`,
`skills/data/sources`, `skills/data`, `skills/research`.

## MAP-B — renamed `name:` identifiers (old → new)

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
research-proposition-schema                        -> epistemics-proposition-schema
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
**Unchanged names — do NOT rewrite:** `statistics-{bayesian-workflow, compositional-data,
likelihood-model-comparison, population-genetics-likelihood, survival-and-hierarchical-models,
time-series-and-longitudinal-models}`, `pipeline-{marimo, runpod, snakemake}`, `scientific-writing`,
`research-package-spec`, `research-package-rendering`, routers `data-management`, `statistics`,
`pipelines`, `writing`, index `science-skill-index`.

> **CAUTION (used by Tasks 4 & 5):** a blanket `s/statistics-/study-design-/` is WRONG — only the 8
> MAP-B rows move; the 6 modeling `statistics-*` stay. Always rewrite from MAP-B literally.

---

### Task 1: Move files + re-prefix names

**Files:** MAP-A moves (`git mv`) + `git rm skills/research/SKILL.md`; `name:` frontmatter of the 26
MAP-B leaves + 2 routers (`bio/genomics/SKILL.md`, `bio/transcriptomics/SKILL.md`).

**Interfaces:** Produces the new tree + new `name:` values every later task relies on.

- [ ] **Step 1: Pre-create destination directories.**

```bash
mkdir -p skills/bio/genomics skills/bio/transcriptomics skills/bio/proteomics \
  skills/ml skills/data-management skills/study-design skills/epistemics \
  skills/literature/sources skills/research-package
```

- [ ] **Step 2: Apply MAP-A moves**, then remove the dissolved router and emptied dirs:

```bash
set -e
git mv skills/data/genomics/somatic-mutation-qa.md                 skills/bio/genomics/somatic-mutation-qa.md
git mv skills/data/genomics/copy-number-sv-qa.md                   skills/bio/genomics/copy-number-sv-qa.md
git mv skills/data/genomics/mutational-signatures-and-selection.md skills/bio/genomics/mutational-signatures-and-selection.md
git mv skills/data/genomics/SKILL.md                               skills/bio/genomics/SKILL.md
git mv skills/data/expression/bulk-rnaseq-qa.md                    skills/bio/transcriptomics/bulk-rnaseq-qa.md
git mv skills/data/expression/microarray-qa.md                     skills/bio/transcriptomics/microarray-qa.md
git mv skills/data/expression/scrna-qa.md                          skills/bio/transcriptomics/scrna-qa.md
git mv skills/data/expression/SKILL.md                             skills/bio/transcriptomics/SKILL.md
git mv skills/data/proteomics-qa.md                                skills/bio/proteomics/proteomics-qa.md
git mv skills/data/protein-sequence-structure-qa.md               skills/bio/proteomics/protein-sequence-structure-qa.md
git mv skills/data/functional-genomics-qa.md                       skills/bio/functional-genomics-qa.md
git mv skills/data/embeddings-manifold-qa.md                       skills/ml/embeddings-manifold-qa.md
git mv skills/data/frictionless.md                                 skills/data-management/frictionless.md
git mv skills/data/SKILL.md                                        skills/data-management/SKILL.md
git mv skills/data/sources/openalex.md                             skills/literature/sources/openalex.md
git mv skills/data/sources/pubmed.md                               skills/literature/sources/pubmed.md
git mv skills/research/literature-evaluation.md                    skills/literature/literature-evaluation.md
git mv skills/research/citation-discipline.md                      skills/literature/citation-discipline.md
git mv skills/research/proposition-schema.md                       skills/epistemics/proposition-schema.md
git mv skills/research/proposition-graph-reasoning.md              skills/epistemics/proposition-graph-reasoning.md
git mv skills/research/annotation-curation-qa.md                   skills/epistemics/annotation-curation-qa.md
git mv skills/research/research-package-spec.md                    skills/research-package/research-package-spec.md
git mv skills/research/research-package-rendering.md               skills/research-package/research-package-rendering.md
git mv skills/statistics/bias-vs-variance-decomposition.md         skills/study-design/bias-vs-variance-decomposition.md
git mv skills/statistics/causal-identification.md                  skills/study-design/causal-identification.md
git mv skills/statistics/estimator-certification.md                skills/study-design/estimator-certification.md
git mv skills/statistics/power-floor-acknowledgement.md            skills/study-design/power-floor-acknowledgement.md
git mv skills/statistics/prereg-amendment-vs-fresh.md              skills/study-design/prereg-amendment-vs-fresh.md
git mv skills/statistics/prereg-defensive-instrumentation.md       skills/study-design/prereg-defensive-instrumentation.md
git mv skills/statistics/replicate-count-justification.md          skills/study-design/replicate-count-justification.md
git mv skills/statistics/sensitivity-arbitration.md                skills/study-design/sensitivity-arbitration.md
git rm skills/research/SKILL.md
rmdir skills/data/genomics skills/data/expression skills/data/sources skills/data skills/research
```
(31 `git mv` + 1 `git rm`. `set -e` aborts on the first failure — e.g. a missing `mkdir -p` dest.)

- [ ] **Step 3: Verify the tree (fail-hard).**

```bash
set -e
renamed=$(git status --porcelain | grep -c '^R') ; [ "$renamed" -eq 31 ] || { echo "FAIL renames=$renamed (want 31)"; exit 1; }
[ ! -e skills/data ] && [ ! -e skills/research ] || { echo "FAIL data/ or research/ still on disk"; exit 1; }
leaves=$(find skills -name '*.md' ! -name 'SKILL.md' ! -name 'INDEX.md' -not -path 'skills/meta/*' | wc -l)
[ "$leaves" -eq 38 ] || { echo "FAIL leaves=$leaves (want 38, excluding skills/meta/)"; exit 1; }
echo "tree ok: 31 renames, 38 leaves, data/ + research/ gone"
```

- [ ] **Step 4: Re-prefix `name:` fields.** For each MAP-B leaf, edit its `name:` line (line 2) old→new.
  Set `skills/bio/genomics/SKILL.md` → `name: genomics` and `skills/bio/transcriptomics/SKILL.md` →
  `name: transcriptomics`. Change only the `name:` line.

- [ ] **Step 5: Verify names (fail-hard, full MAP-B).**

```bash
# no OLD name (leaf or router) survives anywhere under skills/
fail=0
for old in data-genomics-somatic-mutation-qa data-genomics-copy-number-sv-qa \
  data-genomics-mutational-signatures-and-selection data-expression-bulk-rnaseq-qa \
  data-expression-microarray-qa data-expression-scrna-qa data-proteomics-qa \
  data-protein-sequence-structure-qa data-functional-genomics-qa data-embeddings-manifold-qa \
  data-frictionless data-source-openalex data-source-pubmed research-literature-evaluation \
  research-citation-discipline research-proposition-schema research-proposition-graph-reasoning \
  research-annotation-curation-qa statistics-bias-vs-variance-decomposition \
  statistics-causal-identification statistics-estimator-certification \
  statistics-power-floor-acknowledgement statistics-prereg-amendment-vs-fresh \
  statistics-prereg-defensive-instrumentation statistics-replicate-count-justification \
  statistics-sensitivity-arbitration data-genomics data-expression; do
    if grep -rqn "^name: $old\$" skills/; then echo "LEFTOVER name: $old"; fail=1; fi
  done
[ "$fail" -eq 0 ] && echo "no leftover old names" || { echo "FAIL leftover names"; exit 1; }
# positive: each NEW name (MAP-B) is present at exactly the expected new path (name lands, not just old gone)
while IFS='|' read -r newname newpath; do
    got=$(grep -l "^name: $newname\$" "skills/$newpath" 2>/dev/null) || true
    [ -n "$got" ] || { echo "MISSING name: $newname at skills/$newpath"; fail=1; }
  done <<'MAPB'
genomics-somatic-mutation-qa|bio/genomics/somatic-mutation-qa.md
genomics-copy-number-sv-qa|bio/genomics/copy-number-sv-qa.md
genomics-mutational-signatures-and-selection|bio/genomics/mutational-signatures-and-selection.md
transcriptomics-bulk-rnaseq-qa|bio/transcriptomics/bulk-rnaseq-qa.md
transcriptomics-microarray-qa|bio/transcriptomics/microarray-qa.md
transcriptomics-scrna-qa|bio/transcriptomics/scrna-qa.md
proteomics-qa|bio/proteomics/proteomics-qa.md
proteomics-protein-sequence-structure-qa|bio/proteomics/protein-sequence-structure-qa.md
functional-genomics-qa|bio/functional-genomics-qa.md
ml-embeddings-manifold-qa|ml/embeddings-manifold-qa.md
data-management-frictionless|data-management/frictionless.md
literature-source-openalex|literature/sources/openalex.md
literature-source-pubmed|literature/sources/pubmed.md
literature-evaluation|literature/literature-evaluation.md
literature-citation-discipline|literature/citation-discipline.md
epistemics-proposition-schema|epistemics/proposition-schema.md
epistemics-proposition-graph-reasoning|epistemics/proposition-graph-reasoning.md
epistemics-annotation-curation-qa|epistemics/annotation-curation-qa.md
study-design-bias-vs-variance-decomposition|study-design/bias-vs-variance-decomposition.md
study-design-causal-identification|study-design/causal-identification.md
study-design-estimator-certification|study-design/estimator-certification.md
study-design-power-floor-acknowledgement|study-design/power-floor-acknowledgement.md
study-design-prereg-amendment-vs-fresh|study-design/prereg-amendment-vs-fresh.md
study-design-prereg-defensive-instrumentation|study-design/prereg-defensive-instrumentation.md
study-design-replicate-count-justification|study-design/replicate-count-justification.md
study-design-sensitivity-arbitration|study-design/sensitivity-arbitration.md
genomics|bio/genomics/SKILL.md
transcriptomics|bio/transcriptomics/SKILL.md
MAPB
[ "$fail" -eq 0 ] && echo "names ok (old gone, new present)" || { echo "FAIL names"; exit 1; }
```
(Full suite/lint are RED here by construction — do NOT run them as a gate.)

- [ ] **Step 6: Commit.**

```bash
git add -A && git commit -m "refactor(skills): move corpus into subject/domain tree + re-prefix names (phase 3, task 1)"
```

---

### Task 2: Rewrite cross-links, INDEX.md, and routers

**Files:** every `skills/**` file with a relative `.md` link to a moved target; rewrite
`skills/INDEX.md`; retarget `bio/genomics/SKILL.md`, `bio/transcriptomics/SKILL.md`,
`data-management/SKILL.md`, `statistics/SKILL.md`; **create** 7 routers (bodies below).

**Interfaces:** Consumes MAP-A + the Task-1 tree. Produces a self-consistent link graph + INDEX
(validated by `skills lint` in Task 5). Every skill file — leaf **and router** — must keep/gain a
`## Companion Skills` section, `provenance: internal` (routers) or its existing `provenance:`/`sources:`
(leaves), and no `archetype:` (routers). Every router **and** leaf must appear in `INDEX.md`.

- [ ] **Step 1: Find every intra-skills link + inline path mention.**

```bash
grep -rnoE '\]\((\.\.?/[^)]+\.md)\)' skills/ | sort         # markdown links (lint-checked)
grep -rnoE '`(\.\.?/)?[a-z0-9./_-]+\.md`' skills/ | grep -v 'skills/meta/templates/' | sort  # inline code
```

- [ ] **Step 2: Rewrite each markdown link** to its target's NEW path (resolve via MAP-A; recompute
  `../` from the source file's new location). Depth reminders: `data/genomics/`→`bio/genomics/` and
  `data/expression/`→`bio/transcriptomics/` keep depth-2; `data/*.md` (depth-1) →
  `bio/proteomics/…`, `ml/…`, `data-management/…`, `literature/…`, `epistemics/…`,
  `research-package/…`, `study-design/…` change depth.

- [ ] **Step 2b: Retarget every link to the deleted `research/SKILL.md` (pinned destinations).** The
  router is gone, so each of these must point at a concrete successor; the Task-1 tree makes them all
  dangling until fixed. Apply exactly (paths are the leaves' NEW locations; recompute `../` from each
  source's new location):

  | Source (new location) | Old link | New target |
  |---|---|---|
  | `writing/SKILL.md:23` (prose "see …") | `../research/SKILL.md` | `../literature/SKILL.md` |
  | `writing/SKILL.md:40` (neighboring routers) | `../research/SKILL.md` | `../literature/SKILL.md`, `../epistemics/SKILL.md` |
  | `statistics/SKILL.md:155` (neighbor "high-level research methodology") | `../research/SKILL.md` | `../literature/SKILL.md`, `../epistemics/SKILL.md` |
  | `bio/transcriptomics/SKILL.md` (was `data/expression/SKILL.md:171`, "literature" context) | `../../research/SKILL.md` | `../../literature/SKILL.md` |
  | `data-management/SKILL.md` (was `data/SKILL.md:188`) | `../research/SKILL.md` | **split into two** direct leaf links: `../literature/literature-evaluation.md` (source-choice evaluation) + `../literature/citation-discipline.md` (citation conformance) |
  | `meta/SKILL.md:33` (neighboring subject routers list, also has `../data/SKILL.md`) | `../data/SKILL.md`, `../research/SKILL.md` | replace the whole list with the new top-level routers: `../bio/SKILL.md`, `../ml/SKILL.md`, `../data-management/SKILL.md`, `../statistics/SKILL.md`, `../study-design/SKILL.md`, `../epistemics/SKILL.md`, `../literature/SKILL.md`, `../research-package/SKILL.md`, `../pipelines/SKILL.md`, `../writing/SKILL.md` |
  | `literature/citation-discipline.md:57` (was `research/citation-discipline.md`, prose inline-code mention) | `` `research/SKILL.md` `` | `` `literature/SKILL.md` `` (prose; not a markdown link but must not name a deleted file) |

  `skills/INDEX.md` rows `:16`/`:88` are handled by the wholesale INDEX rewrite (Step 5).

- [ ] **Step 3: Retarget the moved/surviving routers.**
  - `bio/genomics/SKILL.md`, `bio/transcriptomics/SKILL.md`: same-folder leaf references usually
    unchanged — verify each still resolves.
  - `data-management/SKILL.md`: repoint routing rows that pointed at the migrated data-QA leaves to
    `../bio/…`; leave its teaching body (extraction is phase 4). (Its `../research/SKILL.md` link is
    split in Step 2b above.)
  - `statistics/SKILL.md`: **remove** routing rows for the 8 leaves now in `study-design/`; keep the
    6 modeling leaves. Do not trim the Principles prose (phase 4).

- [ ] **Step 4: Create the 7 routers.** Each follows `skills/meta/templates/router.md`: frontmatter
  `name` + `description` + `provenance: internal` (NO `archetype:`); sections `## Routing trigger`,
  `## Scope boundary`, `## Leaves`, `## Decision / compose order`, `## Parent & neighbors`,
  `## Success test`, `## Companion Skills`. Write these bodies verbatim:

**`skills/bio/SKILL.md`**
```markdown
---
name: bio
description: Use when a biological-assay dataset (genomics, transcriptomics, proteomics, functional-genomics) needs measurement QA. Routes to the assay subtree.
provenance: internal
---

# Biological Data Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when the data under analysis is a biological assay, before loading any leaf.

## Scope boundary

Covers assay-level measurement QA for genomics, transcriptomics, proteomics, and functional-genomics
data. Excludes general dimensionality-reduction QA (see `../ml/SKILL.md`) and dataset-directory
conventions (see `../data-management/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `genomics/SKILL.md` | somatic mutation, CN/SV, or signature/selection data | expression or protein data |
| `transcriptomics/SKILL.md` | bulk RNA-seq, microarray, or scRNA data | non-expression assays |
| `proteomics/SKILL.md` | mass-spec proteomics or protein sequence/structure data | nucleic-acid assays |
| `functional-genomics-qa.md` | CRISPR/RNAi screens, DepMap, perturbation data | descriptive (non-perturbation) assays |

## Decision / compose order

Route to exactly one assay sub-area; QA leaves within a sub-area may compose per that sub-router.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../ml/SKILL.md`, `../data-management/SKILL.md`, `../statistics/SKILL.md`

## Success test

A representative assay dataset routes to its correct sub-area (or loose leaf) with no methodology read
from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
```

**`skills/bio/proteomics/SKILL.md`**
```markdown
---
name: proteomics
description: Use when a proteomics or protein sequence/structure dataset needs measurement QA. Routes to the proteomics leaves.
provenance: internal
---

# Proteomics Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when the data is protein-level (abundance or sequence/structure), before any leaf.

## Scope boundary

Covers mass-spec proteomics QA and protein sequence/structure dataset QA. Excludes nucleic-acid
assays and embedding QA.

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `proteomics-qa.md` | MS intensity/abundance matrices, TMT/LFQ, phosphoproteomics | sequence/structure-only tasks |
| `protein-sequence-structure-qa.md` | UniProt/Pfam/CATH/Foldseek/PLM sequence or structure sets | abundance quantification |

## Decision / compose order

Leaves are independent; load whichever matches the data modality.

## Parent & neighbors

- Parent index: `../../INDEX.md`
- Neighboring routers: `../genomics/SKILL.md`, `../transcriptomics/SKILL.md`

## Success test

A proteomics dataset routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../../INDEX.md` — the skill index.
```

**`skills/ml/SKILL.md`**
```markdown
---
name: ml
description: Use when embedding, manifold, or unsupervised-structure output needs QA. Routes to the ML QA leaves.
provenance: internal
---

# Machine-Learning QA Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when the object under scrutiny is a learned embedding or unsupervised structure,
before any leaf.

## Scope boundary

Covers QA of embeddings/manifolds/clusterings regardless of source domain. Excludes assay-level
measurement QA (see `../bio/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `embeddings-manifold-qa.md` | UMAP/HDBSCAN/Mapper/CKA structure claims, cluster stability | raw-assay QA |

## Decision / compose order

Single leaf; load it directly.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../bio/SKILL.md`, `../statistics/SKILL.md`

## Success test

An embedding/clustering claim routes to the leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
```

**`skills/study-design/SKILL.md`**
```markdown
---
name: study-design
description: Use when analysis rigor must be pre-committed or a numeric verdict certified/arbitrated. Routes to the discipline leaves.
provenance: internal
---

# Study-Design & Inference-Discipline Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when a design commitment, certification, or arbitration governs how a result may be
claimed — before interpretation.

## Scope boundary

Covers pre-registration, replicate/power justification, estimator certification, sensitivity
arbitration, causal identification, and bias/variance reasoning. Excludes model fitting (see
`../statistics/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `prereg-amendment-vs-fresh.md` | deciding amendment vs fresh pre-reg for a follow-up | no prior pre-reg exists |
| `prereg-defensive-instrumentation.md` | locking universe/candidate/tripwire/decision tables | exploratory-only work |
| `replicate-count-justification.md` | choosing R/B/m from a pilot rule | count already externally fixed |
| `power-floor-acknowledgement.md` | wording a null/weak result under a detectability floor | strong positive effect |
| `estimator-certification.md` | certifying a numeric fit against the E ≤ ρ·σ_null budget | no numeric verdict at stake |
| `sensitivity-arbitration.md` | applying a pre-committed sensitivity/veto table | no pre-committed table |
| `causal-identification.md` | certifying an adjustment set / identification | purely descriptive analysis |
| `bias-vs-variance-decomposition.md` | deciding whether more replicates vs bias correction is legitimate | no error-source ambiguity |

## Decision / compose order

Leaves are independent; several may apply to one analysis. Apply design/pre-commitment leaves before
data are seen, certification/arbitration leaves at verdict time.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../statistics/SKILL.md`

## Success test

A rigor commitment or verdict routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
```

**`skills/epistemics/SKILL.md`**
```markdown
---
name: epistemics
description: Use when propositions, evidence, or curated annotations must be schema-valid, graph-reasoned, or agreement-checked. Routes to the epistemics leaves.
provenance: internal
---

# Epistemics Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when the object is a proposition/annotation and its schema, graph outcome, or
label agreement is in question — before interpretation.

## Scope boundary

Covers proposition/evidence schema conformance, proposition-graph outcome reasoning, and curated-label
QA. Excludes source selection/citation (see `../literature/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `proposition-schema.md` | writing/validating proposition or evidence frontmatter | non-proposition data |
| `proposition-graph-reasoning.md` | flagging an interpretation against graph outcome conditions | schema-only concerns |
| `annotation-curation-qa.md` | QA of manual/LLM annotation or taxonomy-label agreement | non-curated measurement |

## Decision / compose order

Leaves are independent; schema conformance typically precedes graph reasoning.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../literature/SKILL.md`

## Success test

A proposition/annotation concern routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
```

**`skills/literature/SKILL.md`**
```markdown
---
name: literature
description: Use when finding, evaluating, or citing scientific literature. Routes to the literature leaves.
provenance: internal
---

# Literature Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when sourcing, appraising, or citing literature is in scope — before drafting claims
that depend on sources.

## Scope boundary

Covers literature search tools, source evaluation, and citation conformance. Excludes proposition
schema/graph reasoning (see `../epistemics/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `literature-evaluation.md` | assessing/recording source provenance and publication status | no external sources |
| `citation-discipline.md` | conforming a citation/source-pointer to the project contract | no citations at stake |
| `sources/openalex.md` | querying OpenAlex for ranked, provenance-tagged results | non-OpenAlex sourcing |
| `sources/pubmed.md` | querying PubMed/NCBI E-utilities for ranked results | non-PubMed sourcing |

## Decision / compose order

Search leaves feed evaluation; citation-discipline applies whenever a claim cites a source.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../epistemics/SKILL.md`, `../research-package/SKILL.md`

## Success test

A sourcing/citation task routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
```

**`skills/research-package/SKILL.md`**
```markdown
---
name: research-package
description: Use when building or validating a research-package bundle (datapackage + cells) and its provenance route. Routes to the research-package leaves.
provenance: internal
---

# Research-Package Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when producing or validating a research-package artifact, before any leaf.

## Scope boundary

Covers the research-package descriptor contract and the component that renders its provenance route.
Excludes general dataset-directory conventions (see `../data-management/SKILL.md`).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `research-package-spec.md` | validating the datapackage.json + cells.json bundle | rendering/UI concerns only |
| `research-package-rendering.md` | wiring a `/src` provenance route to a package | contract validation only |

## Decision / compose order

`research-package-spec` (layer 1) is the contract `research-package-rendering` builds on.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../literature/SKILL.md`, `../data-management/SKILL.md`

## Success test

A research-package task routes to the correct leaf with no methodology read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
```

- [ ] **Step 5: Rewrite `skills/INDEX.md`.** It must list **every leaf AND every router** (the linter
  iterates all non-template `.md`). Reproduce the existing INDEX format (see
  `git show HEAD~2:skills/INDEX.md`) as `` - `<name>`: `skills/<new-path>` `` entries grouped by the
  new folders; include all 38 leaves and all routers `bio`, `bio/genomics`, `bio/transcriptomics`,
  `bio/proteomics`, `ml`, `data-management`, `statistics`, `study-design`, `epistemics`, `literature`,
  `research-package`, `pipelines`, `writing`, `meta`; **remove** the `research-methodology` row. Use
  MAP-B names.

- [ ] **Step 6: Verify no dangling intra-skills markdown link (structural, pre-lint).**

```bash
( cd science && uv run --frozen python - <<'PY'
import pathlib, re
root = pathlib.Path("../skills")
bad = [f"{md}: {m.group(1)}" for md in root.rglob("*.md")
       for m in re.finditer(r'\]\((\.\.?/[^)#]+\.md)', md.read_text())
       if not (md.parent / m.group(1)).exists()]
raise SystemExit("DANGLING:\n" + "\n".join(bad) if bad else 0)
PY
) && echo "no dangling intra-skills links"
```
(Full pytest/lint remain RED — external consumers not yet updated.)

- [ ] **Step 7: Commit.**

```bash
git add -A && git commit -m "refactor(skills): rewrite links, INDEX, and routers for the new tree (phase 3, task 2)"
```

---

### Task 3: Non-Codex path/name-coupled consumers

**Files:** `science/src/science_tool/skills_lint/lint.py` (`HALT_ON_REQUIRED`); HALT test fixtures
`science/tests/skills_lint/fixtures/data/{embeddings-manifold-qa,functional-genomics-qa}.md` +
`fixtures/INDEX.md` and `science/tests/skills_lint/test_lint.py`; external
`estimator-certification` links in `commands/pre-register.md:124`,
`aspects/computational-analysis/computational-analysis.md:72`, `templates/pre-registration.md:170`,
`science/model/src/science_model/templates/pre-registration.md:170`; `research-proposition-schema`
refs in `templates/proposition.md:12` **and** `science/model/src/science_model/templates/proposition.md:12`;
doctrine `skills/meta/skill-authoring.md` + `skills/meta/skill-taxonomy.md`; annotate
`docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md`. (`commands/plan-analysis.md` is Task 4 — do
not touch it here.)

**Interfaces:** Consumes MAP-A/MAP-B. Produces linter + non-Codex docs consistent with the new tree.

- [ ] **Step 1: Update `HALT_ON_REQUIRED`** in `lint.py` to the 9 new paths (7 bio, 1 ml, 1 epistemics):

```python
HALT_ON_REQUIRED = {
    "bio/genomics/somatic-mutation-qa.md",
    "bio/genomics/mutational-signatures-and-selection.md",
    "bio/transcriptomics/bulk-rnaseq-qa.md",
    "bio/transcriptomics/microarray-qa.md",
    "bio/transcriptomics/scrna-qa.md",
    "bio/proteomics/protein-sequence-structure-qa.md",
    "bio/functional-genomics-qa.md",
    "ml/embeddings-manifold-qa.md",
    "epistemics/annotation-curation-qa.md",
}
```

- [ ] **Step 1b: Relocate the HALT test fixtures to match the new constant.** `check_halt_on_conditions`
  keys on a fixture's path being in `HALT_ON_REQUIRED`; the two fixtures currently sit at
  `fixtures/data/…`, which just left the set, so `test_required_halt_on_leaf_without_section_returns_issue`
  and `test_lint_cli_against_fixtures` would break. Move both fixtures to two of the NEW required paths
  (preserving each fixture's identity and body — the embeddings fixture keeps its `## Halt-On Conditions`
  section, the functional-genomics fixture keeps *no* section):

  ```bash
  set -e
  mkdir -p science/tests/skills_lint/fixtures/ml science/tests/skills_lint/fixtures/bio
  git mv science/tests/skills_lint/fixtures/data/embeddings-manifold-qa.md   science/tests/skills_lint/fixtures/ml/embeddings-manifold-qa.md
  git mv science/tests/skills_lint/fixtures/data/functional-genomics-qa.md   science/tests/skills_lint/fixtures/bio/functional-genomics-qa.md
  rmdir science/tests/skills_lint/fixtures/data
  ```

  Then update the references that name the old fixture paths:
  - `test_lint.py:71` `FIXTURES / "data" / "embeddings-manifold-qa.md"` → `FIXTURES / "ml" / "embeddings-manifold-qa.md"`
  - `test_lint.py:79` `FIXTURES / "data" / "functional-genomics-qa.md"` → `FIXTURES / "bio" / "functional-genomics-qa.md"`
  - `test_lint.py:138` `assert "data/functional-genomics-qa.md" in result.output` → `assert "bio/functional-genomics-qa.md" in result.output`
  - `test_lint.py:142` `assert "data/embeddings-manifold-qa.md" not in result.output` → `assert "ml/embeddings-manifold-qa.md" not in result.output`
  - `fixtures/INDEX.md:14,15` `skills/data/embeddings-manifold-qa.md` → `skills/ml/embeddings-manifold-qa.md`,
    `skills/data/functional-genomics-qa.md` → `skills/bio/functional-genomics-qa.md`

  (Both new fixture paths are members of the Step-1 `HALT_ON_REQUIRED`, so the positive/negative
  assertions keep testing a genuinely required path. These fixtures are test doubles — do **not** add
  their paths to the production constant to keep tests green.)

- [ ] **Step 2: Retarget the 4 external `estimator-certification` links.** In `pre-register.md`,
  `computational-analysis.md`, and BOTH pre-reg templates: path
  `skills/statistics/estimator-certification.md` → `skills/study-design/estimator-certification.md`
  (fix `../` depth per file) and any `statistics-estimator-certification` text →
  `study-design-estimator-certification`. The root and packaged `pre-registration.md` must end
  **byte-identical** (`diff templates/pre-registration.md science/model/src/science_model/templates/pre-registration.md`).

- [ ] **Step 3: Fix both proposition templates.** In `templates/proposition.md:12` and
  `science/model/src/science_model/templates/proposition.md:12`, change `research-proposition-schema`
  → `epistemics-proposition-schema`. Keep the two files byte-identical.

- [ ] **Step 4: Update doctrine.** In `skill-authoring.md` and `skill-taxonomy.md`: flip "reorg/rename
  deferred to phase 3" → "reorg + rename completed in phase 3; hub **extraction** + principle-trimming
  + `frictionless`/`mutational-signatures` splits remain (phase 4)"; update the remaining-hub list to
  `data-management/`, `bio/transcriptomics/`, `pipelines/`, `statistics/`; in the subject-prefix
  bullet (`skill-authoring.md:34`) replace the pre-migration prefix list with the new subjects
  (`genomics-`, `transcriptomics-`, `proteomics-`, `functional-genomics-`, `ml-`,
  `data-management-`, `study-design-`, `epistemics-`, `literature-`, `literature-source-`; unchanged
  `statistics-`, `pipeline-`).

- [ ] **Step 5: Annotate the corpus matrix.** Add one line at the top of
  `2026-07-19-skills-taxonomy-corpus-matrix.md`: its `path`/`name`/`subject` columns are **pre-reorg**
  (it was this phase's input); do not rewrite rows. Touch no other `docs/plans/` file.

- [ ] **Step 6: Verify (fail-hard).**

```bash
set -e
if grep -rqn "skills/statistics/estimator-certification\|statistics-estimator-certification" \
  commands/pre-register.md aspects/ templates/ science/model/src/science_model/templates/; then
  echo "FAIL leftover estimator link"; exit 1; fi
diff templates/pre-registration.md science/model/src/science_model/templates/pre-registration.md || { echo "FAIL pre-registration templates diverge"; exit 1; }
diff templates/proposition.md science/model/src/science_model/templates/proposition.md || { echo "FAIL proposition templates diverge"; exit 1; }
[ ! -e science/tests/skills_lint/fixtures/data ] || { echo "FAIL fixtures/data still present"; exit 1; }
( cd science && uv run --frozen python -c "from science_tool.skills_lint.lint import HALT_ON_REQUIRED as H; assert len(H)==9 and 'epistemics/annotation-curation-qa.md' in H and 'ml/embeddings-manifold-qa.md' in H and 'bio/functional-genomics-qa.md' in H and not any(p.split('/')[0] in {'data','research','statistics'} for p in H); print('HALT ok')" )
echo "task 3 verify ok"
```

- [ ] **Step 7: Commit.**

```bash
git add -A && git commit -m "refactor(skills): update linter, external links, templates, and doctrine (phase 3, task 3)"
```

---

### Task 4: Drop the Codex companion + rewrite plan-analysis + all callers

**Files:** `science/src/science_tool/codex_skills.py` (drop companion, add stale-dir **pruning**,
rework rewrite); `references/command-preamble.md:10`;
`references/role-prompts/{research-assistant.md:17, discussant.md:18}`;
`commands/{review.md:25, plan-pipeline.md:9, review-pipeline.md:9}`; **all of**
`commands/plan-analysis.md`; the **path-only** consumer commands that reference moved skill files —
`commands/catalog-benchmarks.md:28`, `commands/catalog-datasets.md:17`, `commands/find-datasets.md:16-17`,
`commands/search-literature.md:16-17`; `docs/user-guide/codex.md:113`;
`codex-skills/INSTALL.codex.md` (static); tests `science/tests/test_codex_skills.py`,
`science/tests/test_command_docs.py`. (The `data-management/SKILL.md` `../research/SKILL.md` split is
done in **Task 2 Step 2b**, not here.)

**Interfaces:** Consumes the dissolved `research/` + new leaves. Produces a Codex surface and command
corpus with zero reference to the removed companion or any old name/path.

- [ ] **Step 1: Remove the companion.** In `codex_skills.py`, delete
  `CompanionSkill("research-methodology", Path("skills/research/SKILL.md"))` from `COMPANION_SKILLS`
  (keep `scientific-writing`, `skill-development`).

- [ ] **Step 1b: Prune orphaned `science-*` dirs in the generator.** Without this the in-place regen
  (Task 5) leaves a stale `codex-skills/science-research-methodology/` that fails the committed-mirror
  test. At the end of `generate_codex_skills`, after `_write_index(...)`, before `return generated`:

  ```python
      generated_dirs = {output_root / name for name in generated}
      for child in output_root.iterdir():
          if child.is_dir() and child.name.startswith("science-") and child not in generated_dirs:
              shutil.rmtree(child)

      return generated
  ```

  This only removes stale `science-*` **directories**; `INDEX.md` (regenerated) and the static
  `INSTALL.codex.md` are files and are skipped. Add a test in `test_codex_skills.py`:

  ```python
  def test_generate_prunes_orphaned_skill_dirs(tmp_path: Path) -> None:
      stale = tmp_path / "science-obsolete"
      stale.mkdir(parents=True)
      (stale / "SKILL.md").write_text("stale", encoding="utf-8")
      keep = tmp_path / "INSTALL.codex.md"
      keep.write_text("static", encoding="utf-8")

      generate_codex_skills(ROOT, tmp_path)

      assert not stale.exists()               # orphaned science-* dir removed
      assert keep.read_text(encoding="utf-8") == "static"  # static file untouched
  ```

- [ ] **Step 2: Author the canonical native instruction.** The `research-methodology` skill is gone,
  so callers load `scientific-writing` and consult the canonical index for methodology leaves. Write
  these **native** (source) strings verbatim:
  - **Full form** — `command-preamble.md:10` and `commands/review.md:25`:

    > Load the `scientific-writing` skill. For research methodology, read
    > `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md` and load the leaves relevant to the task (e.g.
    > `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).

  - **Short form** — `commands/plan-pipeline.md:9`, `commands/review-pipeline.md:9` (blockquote list
    items — replace the `research-methodology` line, no companion name):

    > For research methodology, read `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md` and load the relevant
    > `literature/`/`epistemics/` leaves.

  Do **not** direct Codex to `codex-skills/INDEX.md` for these leaves — it lists only commands +
  companions, not canonical leaves. The canonical index `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md` is
  correct for the native surface; the generator rewrites the depth (Step 3).

- [ ] **Step 3: Rework the generator's rewrite so the native strings map to their generated forms.**
  This is ordering-sensitive: `_load_command_preamble` and `_build_skill_text` call
  `_rewrite_claude_specific_text` (which itself ends by calling `_rewrite_companion_skill_references`),
  and its generic `("${CLAUDE_PLUGIN_ROOT}/", "")` rule strips the plugin-root prefix. If the INDEX
  depth-fix waited for `_rewrite_companion_skill_references`, the string would already read
  `skills/INDEX.md` and any replacement written against `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md` would
  never match. So split the two concerns:

  1. In `_rewrite_claude_specific_text`, **prepend** a specific INDEX rule to the `replacements`
     tuple, *before* the generic `("${CLAUDE_PLUGIN_ROOT}/", "")` strip (generated command/companion
     surfaces all emit at depth 2, so `../../skills/` is the correct depth):

     ```python
         ("${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md", "../../skills/INDEX.md"),
     ```

  2. In `_rewrite_companion_skill_references`, **delete all three** `research-methodology` replacement
     pairs and replace them with the single companion-name pair (this is the only companion still
     mirrored that appears by name in these instructions):

     ```python
     def _rewrite_companion_skill_references(text: str) -> str:
         return text.replace(
             "Load the `scientific-writing` skill.",
             "Load the `science-scientific-writing` Codex skill.",
         )
     ```

  The two transforms compose to the **generated** result (verify in Step 8's tests, full **and**
  short form):

    > **Full:** Load the `science-scientific-writing` Codex skill. For research methodology, read
    > `../../skills/INDEX.md` and load the leaves relevant to the task (e.g. `literature-evaluation`,
    > `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).
    >
    > **Short:** For research methodology, read `../../skills/INDEX.md` and load the relevant
    > `literature/`/`epistemics/` leaves.

- [ ] **Step 4: Fix role prompts.** In `research-assistant.md:17` and `discussant.md:18`, change
  `Skills: research-methodology, scientific-writing` → `Skills: scientific-writing` and append
  "; for research methodology, read `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md` and load the relevant
  `literature/`/`epistemics/` leaves".

- [ ] **Step 5: Rewrite the path-only consumer commands (moved skill files).** These reference moved
  skill **paths** (not the companion) via `${CLAUDE_PLUGIN_ROOT}/skills/…`; they flow into the mirror,
  so they must be fixed before Task 5 regen. Apply MAP-A:

  | File:line | Old path | New path |
  |---|---|---|
  | `commands/catalog-benchmarks.md:28` | `skills/data/SKILL.md` | `skills/data-management/SKILL.md` |
  | `commands/catalog-datasets.md:17` | `skills/data/SKILL.md` | `skills/data-management/SKILL.md` |
  | `commands/find-datasets.md:16` | `skills/data/SKILL.md` | `skills/data-management/SKILL.md` |
  | `commands/find-datasets.md:17` | `skills/data/frictionless.md` | `skills/data-management/frictionless.md` |
  | `commands/search-literature.md:16` | `skills/data/sources/openalex.md` | `skills/literature/sources/openalex.md` |
  | `commands/search-literature.md:17` | `skills/data/sources/pubmed.md` | `skills/literature/sources/pubmed.md` |

  (Line numbers are the pre-edit anchors; the Task-5 fail-hard path grep is the net if any site drifts.)

- [ ] **Step 6: Full MAP-B rewrite of `commands/plan-analysis.md`.** Rewrite every skill identifier
  on lines 34, 63–80, 130, 171, 195–202 using MAP-B **literally** (leave the 6 modeling `statistics-*`
  untouched); update the `estimator-certification` link on line 171 to
  `../skills/study-design/estimator-certification.md`; replace the `research-methodology` tokens on
  lines 79 & 197 with `literature-evaluation`/`literature-citation-discipline`; and
  `research-annotation-curation-qa` → `epistemics-annotation-curation-qa`; router mentions
  `data-expression` → `transcriptomics`.

- [ ] **Step 7: INSTALL + user guide.** Edit `codex-skills/INSTALL.codex.md:44` to drop
  `science-research-methodology` (keep `science-scientific-writing`). Edit `docs/user-guide/codex.md:113`
  to remove `science-research-methodology` from the companion list.

- [ ] **Step 8: Update `test_codex_skills.py`.** (The Task-5 fail-hard grep scans `science/tests/`,
  so any missed old name/path is caught at the gate — but fix them here.) Concretely:
  - **`:36`** (`test_generate_codex_skills_rewrites_link_to_datapackage_skill` or sibling reading
    `ROOT / "skills/data/frictionless.md"`): → `ROOT / "skills/data-management/frictionless.md"`.
  - **`test_generate_codex_skills_emits_companion_methodology_skills` (`:83-99`)**: delete the
    `research_skill` read + its 4 asserts (`:86,89-92`). Change `:96`
    `"../science-research-methodology/citation-discipline.md" in writing_skill` →
    `"../../skills/literature/citation-discipline.md" in writing_skill`; drop `:97`
    (`"../research/SKILL.md" not in writing_skill`) or keep as harmless; keep `:98`
    `"../../skills/statistics/SKILL.md" in writing_skill` and `:99`. Rename the test to drop
    "companion_methodology" (e.g. `_emits_scientific_writing_companion`).
  - **`test_generated_command_preamble_references_codex_companion_skills` (`:123-129`)**: replace `:127`
    with the Step-3 **generated full form**; **delete** `:128` (the `codex-skills/INDEX.md` fallback
    text no longer exists); keep `:129` old-native-absent (`Load the \`research-methodology\` and
    \`scientific-writing\` skills.` — still true). Add a second assert against a **short-form** command
    (e.g. `generated["science-plan-pipeline"]`) for the Step-3 generated short form.
  - **`test_generate_codex_skills_writes_index` (`:132-145`)**: delete the `research-methodology`
    companion-row assert (`:137-140`); keep the `scientific-writing` row (`:141-144`) and status row.
  - **plan-analysis expectation strings (`:167-370` cluster)**: every assert reading
    `generated["science-plan-analysis"]` (`:182,186,198,327,337,351,367` etc.) carries MAP-B old
    names — e.g. `:186` `` `data-proteomics-qa`, `statistics-bias-vs-variance-decomposition`,
    `statistics-sensitivity-arbitration` `` → `` `proteomics-qa`,
    `study-design-bias-vs-variance-decomposition`, `study-design-sensitivity-arbitration` ``. Rewrite
    each with MAP-B **literally** (the 6 modeling `statistics-*` stay); replace `research-methodology`
    tokens with `literature-evaluation`/`literature-citation-discipline` and
    `research-annotation-curation-qa` → `epistemics-annotation-curation-qa`, matching the Step-6
    plan-analysis.md edits verbatim.
  - **resource-block tests (`:835-870`)**: `test_rewrites_link_to_companion_source_leaf` (`:835`,
    reads `science-research-methodology/research-package-rendering.md`) and
    `test_rewrites_link_to_non_companion_leaf` (`:844`, reads
    `science-research-methodology/annotation-curation-qa.md`) and
    `test_rewrites_excluded_router_to_canonical_source` (`:862`, reads
    `science-research-methodology/SKILL.md`) all read the dropped companion — **delete** all three.
    `test_rewrites_link_to_bundled_resource` (`:855-859`, reads `science-scientific-writing/SKILL.md`):
    change `:857` `"../science-research-methodology/citation-discipline.md"` →
    `"../../skills/literature/citation-discipline.md"`; the negative `:858`
    `"](../research/citation-discipline.md)"` → `"](../literature/citation-discipline.md)"`. Keep
    `test_companion_source_leaf_is_not_also_a_resource` (writing companion is kept) and
    `test_no_dangling_relative_links_in_generated_tree`.
  - Leave `test_generate_codex_skills_emits_all_commands` (`:75-80`) — it uses `len(COMPANION_SKILLS)`
    and self-adjusts. Keep the new `test_generate_prunes_orphaned_skill_dirs` from Step 1b.

- [ ] **Step 9: Update `test_command_docs.py`.** Rewrite every skills path/name assertion to the new
  tree/names (558-559, 608-611, 632, 657, 778-779, 1010-1011, 1035-1036) and sweep the whole file for
  `skills/data`, `skills/statistics`, `skills/research`, `skills/data/expression`, and any MAP-B old
  name; apply MAP-A/MAP-B. (`skills/data/SKILL.md` → `skills/data-management/SKILL.md`,
  `skills/data/frictionless.md` → `skills/data-management/frictionless.md`,
  `data-proteomics-qa`→`proteomics-qa`, etc.)

- [ ] **Step 10: Commit** (still RED — mirror regenerated in Task 5).

```bash
git add -A && git commit -m "refactor(skills): drop research-methodology Codex companion + rewrite plan-analysis and callers (phase 3, task 4)"
```

---

### Task 5: Regenerate the mirror + green gate

**Files:** `codex-skills/**` (generated), plus any source fix a gate surfaces.

- [ ] **Step 1: Regenerate the mirror.**

```bash
( cd science && uv run --frozen python ../scripts/generate_codex_skills.py )
```

- [ ] **Step 2: Skills lint.**

```bash
( cd science && uv run --frozen science skills lint --root ../skills )
```
Expected: exit 0, no findings.

- [ ] **Step 3: No-dangling-name / -path grep (fail-hard; excludes generated + historical).**

```bash
EXCL='\.venv|/codex-skills/|/docs/plans/|\.claude/worktrees'
fail=0
# capture-then-test avoids pipeline-exit masking; `|| true` swallows grep's no-match (exit 1),
# so a genuine hit is the ONLY thing that sets `hits`.
check() {  # $1 = pattern, $2 = label
    hits=$(grep -rnE "$1" . --include="*.md" --include="*.py" 2>/dev/null | grep -vE "$EXCL" || true)
    if [ -n "$hits" ]; then echo "LEFTOVER $2:"; echo "$hits"; fail=1; fi
}
# OLD MAP-B leaf/router names (word-anchored) — zero LIVE hits
for tok in data-genomics-somatic-mutation-qa data-genomics-copy-number-sv-qa \
  data-genomics-mutational-signatures-and-selection data-expression-bulk-rnaseq-qa \
  data-expression-microarray-qa data-expression-scrna-qa data-proteomics-qa \
  data-protein-sequence-structure-qa data-functional-genomics-qa data-embeddings-manifold-qa \
  data-frictionless data-source-openalex data-source-pubmed research-literature-evaluation \
  research-citation-discipline research-proposition-schema research-proposition-graph-reasoning \
  research-annotation-curation-qa statistics-bias-vs-variance-decomposition \
  statistics-causal-identification statistics-estimator-certification \
  statistics-power-floor-acknowledgement statistics-prereg-amendment-vs-fresh \
  statistics-prereg-defensive-instrumentation statistics-replicate-count-justification \
  statistics-sensitivity-arbitration data-genomics data-expression; do
    check "(^|[^a-z-])$tok([^a-z-]|\$)" "name: $tok"
  done
# research-methodology: ANCHOR to skill-reference forms only — bare token appears as prose
# ("research-methodology entities" in meta/entities/questions/0038) and must NOT be flagged.
check '`research-methodology`' "skill-ref: \`research-methodology\`"
check 'skills/research/' "path: skills/research/"
# old PATH forms (lint misses inline-code path mentions). The 6 modeling statistics leaves STAY, so
# grep the 8 MOVED statistics leaf paths EXACTLY, never bare skills/statistics/.
for p in "skills/data/" "skills/data/expression" "skills/data/genomics" "skills/data/sources" \
  "skills/statistics/bias-vs-variance-decomposition.md" "skills/statistics/causal-identification.md" \
  "skills/statistics/estimator-certification.md" "skills/statistics/power-floor-acknowledgement.md" \
  "skills/statistics/prereg-amendment-vs-fresh.md" "skills/statistics/prereg-defensive-instrumentation.md" \
  "skills/statistics/replicate-count-justification.md" "skills/statistics/sensitivity-arbitration.md"; do
    check "$(printf '%s' "$p" | sed 's/[.]/[.]/g')" "path: $p"
  done
[ "$fail" -eq 0 ] && echo "no leftovers" || exit 1
```

- [ ] **Step 4: Full suite + committed-mirror + baselines** (each in its own subshell):

`pytest` and the committed-mirror test are **hard gates** (must exit 0). `ruff`/`pyright` have a
**known nonzero baseline** in this repo, so they are NOT `set -e` gates — run them and compare the
finding set to `main`, failing only on *new* findings this branch introduces:

```bash
# HARD GATE: pytest (includes the committed-mirror test) must be fully green.
( cd science && uv run --frozen pytest -q ) || { echo "FAIL pytest"; exit 1; }
# Spotlight the committed-mirror test explicitly (redundant with the full run, but unambiguous).
( cd science && uv run --frozen pytest -q tests/test_codex_skills.py::test_committed_codex_skills_match_fresh_generation ) \
  || { echo "FAIL committed-mirror"; exit 1; }
```

```bash
# BASELINE COMPARE: ruff/pyright — capture this branch, diff against the same commands on the merge
# base. Zero NEW findings is the pass condition; the pre-existing baseline is expected nonzero.
( cd science && uv run --frozen ruff check . )   ; echo "ruff exit=$?  (compare finding set to baseline on main)"
( cd science && uv run --frozen pyright )        ; echo "pyright exit=$? (compare finding set to baseline on main)"
```
Expected: pytest green; committed-mirror green; ruff/pyright show **only** the pre-existing baseline
findings (no new ones attributable to this branch). Do not suppress or edit a baseline finding to
silence it.

- [ ] **Step 5: Commit the regenerated mirror + any gate fixes.**

```bash
git add -A && git commit -m "refactor(skills): regenerate codex mirror; phase-3 reorg + rename complete (phase 3, task 5)"
```

---

## Self-Review

**Spec coverage:** subject/domain tree + statistics split → T1/T2; name rename (MAP-B) → T1S4 (+
positive-presence check T1S5); links + INDEX (leaves **and routers**) + 7 full routers → T2; **every
deleted-`research/SKILL.md` link pinned + data-management split** → T2S2b; `HALT_ON_REQUIRED` (7/1/1) →
T3S1 **+ HALT fixture relocation + `test_lint.py` edits → T3S1b**; external estimator links incl. both
pre-reg templates → T3S2; both proposition templates → T3S3; doctrine + matrix → T3S4-5; drop companion
→ T4S1; **generator stale-dir pruning + test → T4S1b**; native instruction (full/short) → T4S2;
**ordering-correct rewrite (INDEX depth rule + single scientific-writing pair) → T4S3**; role prompts →
T4S4; **path-only consumer commands (catalog-benchmarks/-datasets/find-datasets/search-literature) →
T4S5**; full `plan-analysis.md` MAP-B sweep → T4S6; INSTALL(static) + user guide → T4S7; both
codex/command test files incl. plan-analysis expectation cluster + resource-block deletions → T4S8-9;
regen + green gate + anchored/complete fail-hard grep → T5.

**No placeholders:** all 7 router bodies + all 31 `git mv` lines written verbatim; every branch
resolved (INSTALL static; companion drop uses generator pruning, not `git rm`). Every verification is
fail-hard: T1/T3 use `set -e`; T2 dangling-link + T5 grep capture-then-test (no pipeline masking); T5
pytest/committed-mirror are hard `|| exit 1` gates; ruff/pyright are baseline-compare (known nonzero),
never silenced.

**Type/name consistency:** MAP-A/MAP-B are the single source across T1–T4; T5's grep derives its token
list from MAP-B's old values + word-anchored, with `research-methodology` anchored to skill-ref forms
(bare-token prose in `meta/entities/` is not flagged) and the 8 **moved** statistics leaf paths listed
exactly (the 6 modeling `statistics-*` stay). `HALT_ON_REQUIRED` paths equal MAP-A destinations and the
two HALT fixtures move onto two of them. `git mv` preceded by `mkdir -p`, followed by `rmdir`. All
`uv run` in `science/` subshells. Leaf count excludes `skills/meta/` (38). **`ml` is a subject
(`ml-…`); `bio/` is navigational (no `bio-`).**

**Green gate:** Task 5 only; Tasks 1–4 RED-by-construction, verified by inspection + embedded
structural checks.
