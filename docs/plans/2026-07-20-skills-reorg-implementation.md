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
# run each MAP-A row as: git mv skills/<old> skills/<new>   (28 leaves + 3 routers)
git rm skills/research/SKILL.md
rmdir skills/data/genomics skills/data/expression skills/data/sources skills/data skills/research
```

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
[ "$fail" -eq 0 ] && echo "names ok" || { echo "FAIL leftover names"; exit 1; }
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
  `research-package/…`, `study-design/…` change depth. Any link into the deleted `research/SKILL.md`
  is retargeted to the specific new leaf/router or dropped (see Task 4 Step 5 for
  `data-management/SKILL.md`).

- [ ] **Step 3: Retarget the moved/surviving routers.**
  - `bio/genomics/SKILL.md`, `bio/transcriptomics/SKILL.md`: same-folder leaf references usually
    unchanged — verify each still resolves.
  - `data-management/SKILL.md`: repoint routing rows that pointed at the migrated data-QA leaves to
    `../bio/…`; leave its teaching body (extraction is phase 4). (Its `../research/SKILL.md` link is
    handled in Task 4 Step 5.)
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

**Files:** `science/src/science_tool/skills_lint/lint.py` (`HALT_ON_REQUIRED`); external
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
if grep -rqn "skills/statistics/estimator-certification\|statistics-estimator-certification" \
  commands/pre-register.md aspects/ templates/ science/model/src/science_model/templates/; then
  echo "FAIL leftover estimator link"; exit 1; fi
diff templates/pre-registration.md science/model/src/science_model/templates/pre-registration.md
diff templates/proposition.md science/model/src/science_model/templates/proposition.md
( cd science && uv run --frozen python -c "from science_tool.skills_lint.lint import HALT_ON_REQUIRED as H; assert len(H)==9 and 'epistemics/annotation-curation-qa.md' in H and not any(p.split('/')[0] in {'data','research','statistics'} for p in H); print('HALT ok')" )
```

- [ ] **Step 7: Commit.**

```bash
git add -A && git commit -m "refactor(skills): update linter, external links, templates, and doctrine (phase 3, task 3)"
```

---

### Task 4: Drop the Codex companion + rewrite plan-analysis + all callers

**Files:** `science/src/science_tool/codex_skills.py`; `references/command-preamble.md:10`;
`references/role-prompts/{research-assistant.md:17, discussant.md:18}`;
`commands/{review.md:25, plan-pipeline.md:9, review-pipeline.md:9}`; **all of**
`commands/plan-analysis.md`; `skills/data-management/SKILL.md` (the `../research/SKILL.md` link);
`docs/user-guide/codex.md:113`; `codex-skills/INSTALL.codex.md` (static); tests
`science/tests/test_codex_skills.py`, `science/tests/test_command_docs.py`.

**Interfaces:** Consumes the dissolved `research/` + new leaves. Produces a Codex surface and command
corpus with zero reference to the removed companion or any old name.

- [ ] **Step 1: Remove the companion.** In `codex_skills.py`, delete
  `CompanionSkill("research-methodology", Path("skills/research/SKILL.md"))` from `COMPANION_SKILLS`
  (keep `scientific-writing`, `skill-development`).

- [ ] **Step 2: Define the canonical instruction (native ↔ generated).**
  - **Native (source)** — used in `command-preamble.md:10`, `commands/review.md:25`:

    > Load the `scientific-writing` skill. For research methodology, read
    > `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md` and load the leaves relevant to the task (e.g.
    > `literature-evaluation`, `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).

  - **Native short form** — used in `commands/plan-pipeline.md:9`, `commands/review-pipeline.md:9`
    (drop "for evidence standards" tail or keep it after "methodology,"):

    > For research methodology, read `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md` and load the relevant
    > `literature/`/`epistemics/` leaves.

  - **Generated (Codex)** — produced by `_rewrite_companion_skill_references`; `${CLAUDE_PLUGIN_ROOT}/skills/INDEX.md`
    becomes `../../skills/INDEX.md`, and `scientific-writing` → `science-scientific-writing`:

    > Load the `science-scientific-writing` Codex skill. For research methodology, read
    > `../../skills/INDEX.md` and load the leaves relevant to the task (e.g. `literature-evaluation`,
    > `literature-citation-discipline`, `epistemics-proposition-graph-reasoning`).

  Do **not** direct Codex to `codex-skills/INDEX.md` for these leaves — it lists only commands +
  companions, not canonical leaves.

- [ ] **Step 3: Rework `_rewrite_companion_skill_references`** so its replacement pairs map the new
  native strings (Step 2) to their generated forms; delete the three old `research-methodology`
  pairs. Keep the `scientific-writing` companion mapping.

- [ ] **Step 4: Fix role prompts.** In both, change `Skills: research-methodology, scientific-writing`
  → `Skills: scientific-writing` (add "; see `skills/INDEX.md` for research-methodology leaves").

- [ ] **Step 5: Fix `data-management/SKILL.md` link (split into two).** Replace the single
  `[`../research/SKILL.md`](../research/SKILL.md)` bullet with two direct links:
  `../literature/literature-evaluation.md` (source-choice evaluation) and
  `../literature/citation-discipline.md` (citation conformance).

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

- [ ] **Step 8: Update `test_codex_skills.py`.**
  - `test_generate_codex_skills_emits_companion_methodology_skills`: delete the `research_skill`
    lines (read + 4 asserts). Change the writing-skill link assert to
    `assert "../../skills/literature/citation-discipline.md" in writing_skill`; keep
    `assert "../science-research-methodology/" not in writing_skill`; keep the `../../skills/statistics/SKILL.md`
    assert. Rename the test to drop "companion_methodology".
  - `test_generated_command_preamble_references_codex_companion_skills`: replace the line-127 assert
    with the Step-2 generated text; keep the "old text absent" assert (line 129) updated to the old
    native string.
  - `test_generate_codex_skills_writes_index`: delete the `research-methodology` companion-row assert;
    keep the `scientific-writing` row.
  - The resource block (~830–865) reading `science-research-methodology/{research-package-rendering,
    annotation-curation-qa,SKILL}.md`: delete those reads/asserts (that companion + its bundled
    resources are no longer generated); if a test's remaining purpose is the writing-skill link,
    repoint it to `../../skills/literature/citation-discipline.md`.
  - Leave `test_generate_codex_skills_emits_expected_number_of_skills` (line 80) — it uses
    `len(COMPANION_SKILLS)` and self-adjusts.

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
# every OLD MAP-B name + research-methodology must have zero LIVE hits
for tok in research-methodology data-genomics-somatic-mutation-qa data-genomics-copy-number-sv-qa \
  data-genomics-mutational-signatures-and-selection data-expression-bulk-rnaseq-qa \
  data-expression-microarray-qa data-expression-scrna-qa data-proteomics-qa \
  data-protein-sequence-structure-qa data-functional-genomics-qa data-embeddings-manifold-qa \
  data-frictionless data-source-openalex data-source-pubmed research-literature-evaluation \
  research-citation-discipline research-proposition-schema research-proposition-graph-reasoning \
  research-annotation-curation-qa statistics-bias-vs-variance-decomposition \
  statistics-causal-identification statistics-estimator-certification \
  statistics-power-floor-acknowledgement statistics-prereg-amendment-vs-fresh \
  statistics-prereg-defensive-instrumentation statistics-replicate-count-justification \
  statistics-sensitivity-arbitration; do
    if grep -rn "$tok" . --include="*.md" --include="*.py" | grep -vE "$EXCL" >/dev/null; then
      echo "LEFTOVER name: $tok"; fail=1; fi
  done
# old PATH forms (lint misses inline-code path mentions)
for p in "skills/data/" "skills/research/" "skills/data/expression" "skills/data/genomics" "skills/data/sources"; do
    if grep -rn "$p" . --include="*.md" --include="*.py" | grep -vE "$EXCL" >/dev/null; then
      echo "LEFTOVER path: $p"; fail=1; fi
  done
[ "$fail" -eq 0 ] && echo "no leftovers" || exit 1
```

- [ ] **Step 4: Full suite + committed-mirror + baselines** (each in its own subshell):

```bash
( cd science && uv run --frozen pytest -q )
( cd science && uv run --frozen pytest -q tests/test_codex_skills.py::test_committed_codex_skills_match_fresh_generation )
( cd science && uv run --frozen ruff check . )
( cd science && uv run --frozen pyright )
```
Expected: pytest green; committed-mirror green; ruff/pyright at pre-existing baseline.

- [ ] **Step 5: Commit the regenerated mirror + any gate fixes.**

```bash
git add -A && git commit -m "refactor(skills): regenerate codex mirror; phase-3 reorg + rename complete (phase 3, task 5)"
```

---

## Self-Review

**Spec coverage:** subject/domain tree + statistics split → T1/T2; name rename (MAP-B) → T1S4;
links + INDEX (leaves **and routers**) + 7 full routers → T2; `HALT_ON_REQUIRED` (7/1/1) → T3S1;
external estimator links incl. both pre-reg templates → T3S2; both proposition templates → T3S3;
doctrine + matrix → T3S4-5; drop companion + generator + native/generated instruction + role prompts
+ commands + INSTALL(static) + user guide → T4; full `plan-analysis.md` MAP-B sweep → T4S6;
`data-management` link split → T4S5; both codex/command test files → T4S8-9; regen + green gate +
fail-hard leftover grep → T5.

**No placeholders:** all 7 router bodies written verbatim; the one branch (INSTALL static) is
resolved (it is static — edit it). Every verification is fail-hard (`exit 1`), never print-only.

**Type/name consistency:** MAP-A/MAP-B are the single source across T1–T4; T5's grep derives its
token list from MAP-B's old values + old path forms. `HALT_ON_REQUIRED` paths equal MAP-A
destinations. `git mv` preceded by `mkdir -p` and followed by `rmdir`. All `uv run` in `science/`
subshells. Leaf count excludes `skills/meta/` (38, not 40). `ml` is a subject (`ml-…`), `bio/` is
navigational.

**Green gate:** Task 5 only; Tasks 1–4 RED-by-construction, verified by inspection + embedded
structural checks.
