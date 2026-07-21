# Skills Corpus Reorganization + Rename (Phase 3) — Design

> Phase 3 of the skills-organization program. Phase 1 (archetype backfill) shipped at
> `1feb088c`; phase 2 (research/ + writing/ hub extraction) at `9878802c`. This phase is the
> **original complaint**: top-level `skills/` folders mix topics with disciplines, and
> `statistics/` is overloaded. It is a **structural reorganization + identifier rename** — files
> move into a coherent subject/domain tree and every leaf's `name:` is re-prefixed to its new
> subject. **No teaching content is extracted or split** (that is phase 4).

**Goal:** Reorganize the 46-file corpus into a subject/domain tree so every folder is one coherent
topic; split the overloaded `statistics/` into modeling-methods vs reasoning-disciplines; and
migrate every skill identifier off its old placement prefix onto its new subject — the rename that
doctrine (`skill-authoring.md:34`, `skill-taxonomy.md:109`) explicitly defers to *this* migration.

**Architecture:** `git mv` every leaf/router into the new tree; re-prefix each moved leaf's `name:`;
rewrite all cross-`.md` links, `INDEX.md`, and the affected routers; update every site that
hard-codes an old path **or an old skill name** (code, tests, commands, references, templates,
aspects, docs); drop the `research-methodology` Codex companion and rewrite its callers; regenerate
the `codex-skills/` mirror. The linter's discovery/archetype/router checks are already
path-agnostic, so the churn is paths + names + links, not linter logic.

**Scope (owner-ratified 2026-07-20):** reorg **and rename**; **no** hub extraction, no
principle-trimming, no `frictionless`/`mutational-signatures` content splits (all phase 4).

## Global Constraints

- No AI-attribution trailers/footers on commits (no `Co-Authored-By`, no "Generated with").
- No "legacy"/"compatibility" layers; no "Unified" prefix. Composition > inheritance; explicit >
  defensive; fail early / no silent fallbacks.
- All `uv run` from `science/` (no root `pyproject.toml`); test dirs are not type-checked.
- `codex-skills/` is a **generated** mirror — never hand-edit; regenerate via
  `scripts/generate_codex_skills.py` after any `skills/`/generator/source-doc change, or
  `test_committed_codex_skills_match_fresh_generation` fails.
- Use `git mv` (preserve history), never delete + re-add.
- Nothing pushed to origin unless the owner asks.

## Decisions (resolved during brainstorming + review)

| Fork | Decision |
|---|---|
| Organizing principle | **By subject/domain** — each top-level folder is one coherent topic. |
| Scope | **Reorg + rename**; extraction/splits deferred to phase 4. |
| Bio grouping | Biological assays **grouped under `bio/`** parent. |
| Statistics overload | Split into `statistics/` (modeling method-guides) + **`study-design/`** (reasoning disciplines). |
| `embeddings-manifold-qa` | New top-level **`ml/`**. |
| `annotation-curation-qa` | **`epistemics/`**. |
| `openalex`/`pubmed` | **`literature/sources/`**. |
| Rename prefix source | **Innermost subject** (`name = <subject>-<operation>`). `bio/` is a navigational parent (no `bio-` prefix); **`ml` is itself a subject** (its leaf is `ml-embeddings-manifold-qa`). |
| Codex `research-methodology` companion | **Dropped; all callers rewritten** to load `scientific-writing` + consult `skills/INDEX.md` for the relevant `literature/`/`epistemics/`/`research-package/` leaves. `research/` fully dissolves — **no portal router**. |

`data/` and `research/` **dissolve** entirely; `.claude-plugin/skills/` (causal-dag,
knowledge-graph) is a **separate** plugin tree, **out of scope**.

## Target tree

```
skills/
  INDEX.md                              # rewritten (all paths + names change)
  bio/
    SKILL.md                            # NEW router (name: bio)
    functional-genomics-qa.md          # <- data/functional-genomics-qa.md
    genomics/
      SKILL.md                          # <- data/genomics/SKILL.md   (name: data-genomics -> genomics)
      somatic-mutation-qa.md  copy-number-sv-qa.md  mutational-signatures-and-selection.md
    transcriptomics/
      SKILL.md                          # <- data/expression/SKILL.md (name: data-expression -> transcriptomics; still a HUB — extraction is phase 4)
      bulk-rnaseq-qa.md  microarray-qa.md  scrna-qa.md
    proteomics/
      SKILL.md                          # NEW router (name: proteomics)
      proteomics-qa.md  protein-sequence-structure-qa.md
  ml/
    SKILL.md                            # NEW router (name: ml)
    embeddings-manifold-qa.md           # <- data/embeddings-manifold-qa.md
  data-management/
    SKILL.md                            # <- data/SKILL.md  (name: data-management unchanged; still a HUB — extraction is phase 4)
    frictionless.md
  statistics/
    SKILL.md                            # retarget routing to the 6 modeling leaves (name: statistics)
    bayesian-workflow.md  compositional-data.md  likelihood-model-comparison.md
    population-genetics-likelihood.md  survival-and-hierarchical-models.md  time-series-and-longitudinal-models.md
  study-design/
    SKILL.md                            # NEW router (name: study-design)
    bias-vs-variance-decomposition.md  causal-identification.md  estimator-certification.md
    power-floor-acknowledgement.md  prereg-amendment-vs-fresh.md  prereg-defensive-instrumentation.md
    replicate-count-justification.md  sensitivity-arbitration.md
  epistemics/
    SKILL.md                            # NEW router (name: epistemics)
    proposition-schema.md  proposition-graph-reasoning.md  annotation-curation-qa.md
  literature/
    SKILL.md                            # NEW router (name: literature)
    literature-evaluation.md  citation-discipline.md
    sources/
      openalex.md  pubmed.md
  research-package/
    SKILL.md                            # NEW router (name: research-package)
    research-package-spec.md  research-package-rendering.md   # names already conform — unchanged
  pipelines/                            # UNCHANGED (still a HUB — extraction is phase 4)
    SKILL.md  marimo.md  runpod.md  snakemake.md
  writing/                              # UNCHANGED (pure router post phase-2)
    SKILL.md  scientific-writing.md
  meta/                                 # UNCHANGED
    SKILL.md  skill-authoring.md  skill-taxonomy.md  templates/*
```

`skills/research/SKILL.md` is **deleted** (no portal). Leaf accounting (38): bio 9, ml 1,
data-management 1, statistics 6, study-design 8, epistemics 3, literature 4, research-package 2,
pipelines 3, writing 1. **28 move (26 also renamed), 10 stay.**

## Skill rename (name migration)

Rule: `name = <subject>-<operation>` where `<subject>` is the leaf's **innermost subject folder**
(`bio/` is navigational — `bio/genomics/` → subject `genomics`; **`ml` is itself a subject** →
`ml-embeddings-manifold-qa`). Leaves that
don't change subject keep their name. `research-package-{spec,rendering}` already match their new
folder and are **unchanged**.

### Renamed leaves (26)

| old name | new name | new path |
|---|---|---|
| data-genomics-somatic-mutation-qa | genomics-somatic-mutation-qa | bio/genomics/somatic-mutation-qa.md |
| data-genomics-copy-number-sv-qa | genomics-copy-number-sv-qa | bio/genomics/copy-number-sv-qa.md |
| data-genomics-mutational-signatures-and-selection | genomics-mutational-signatures-and-selection | bio/genomics/mutational-signatures-and-selection.md |
| data-expression-bulk-rnaseq-qa | transcriptomics-bulk-rnaseq-qa | bio/transcriptomics/bulk-rnaseq-qa.md |
| data-expression-microarray-qa | transcriptomics-microarray-qa | bio/transcriptomics/microarray-qa.md |
| data-expression-scrna-qa | transcriptomics-scrna-qa | bio/transcriptomics/scrna-qa.md |
| data-proteomics-qa | proteomics-qa | bio/proteomics/proteomics-qa.md |
| data-protein-sequence-structure-qa | proteomics-protein-sequence-structure-qa | bio/proteomics/protein-sequence-structure-qa.md |
| data-functional-genomics-qa | functional-genomics-qa | bio/functional-genomics-qa.md |
| data-embeddings-manifold-qa | ml-embeddings-manifold-qa | ml/embeddings-manifold-qa.md |
| data-frictionless | data-management-frictionless | data-management/frictionless.md |
| data-source-openalex | literature-source-openalex | literature/sources/openalex.md |
| data-source-pubmed | literature-source-pubmed | literature/sources/pubmed.md |
| research-literature-evaluation | literature-evaluation | literature/literature-evaluation.md |
| research-citation-discipline | literature-citation-discipline | literature/citation-discipline.md |
| research-proposition-schema | epistemics-proposition-schema | epistemics/proposition-schema.md |
| research-proposition-graph-reasoning | epistemics-proposition-graph-reasoning | epistemics/proposition-graph-reasoning.md |
| research-annotation-curation-qa | epistemics-annotation-curation-qa | epistemics/annotation-curation-qa.md |
| statistics-bias-vs-variance-decomposition | study-design-bias-vs-variance-decomposition | study-design/bias-vs-variance-decomposition.md |
| statistics-causal-identification | study-design-causal-identification | study-design/causal-identification.md |
| statistics-estimator-certification | study-design-estimator-certification | study-design/estimator-certification.md |
| statistics-power-floor-acknowledgement | study-design-power-floor-acknowledgement | study-design/power-floor-acknowledgement.md |
| statistics-prereg-amendment-vs-fresh | study-design-prereg-amendment-vs-fresh | study-design/prereg-amendment-vs-fresh.md |
| statistics-prereg-defensive-instrumentation | study-design-prereg-defensive-instrumentation | study-design/prereg-defensive-instrumentation.md |
| statistics-replicate-count-justification | study-design-replicate-count-justification | study-design/replicate-count-justification.md |
| statistics-sensitivity-arbitration | study-design-sensitivity-arbitration | study-design/sensitivity-arbitration.md |

### Moved but **not** renamed (2)

`research-package-spec`, `research-package-rendering` → `research-package/` (names already conform).

### Unchanged (10 leaves, in place)

`statistics-{bayesian-workflow, compositional-data, likelihood-model-comparison,
population-genetics-likelihood, survival-and-hierarchical-models, time-series-and-longitudinal-models}`;
`pipeline-{marimo, runpod, snakemake}`; `scientific-writing`.

### Routers

`data/genomics/SKILL.md` (`data-genomics`→`genomics`) and `data/expression/SKILL.md`
(`data-expression`→`transcriptomics`) move + rename; `data/SKILL.md` → `data-management/SKILL.md`
(`data-management`, name unchanged). New routers: `bio` (bio/), `proteomics` (bio/proteomics/), `ml`,
`study-design`, `epistemics`, `literature`, `research-package`. `statistics`/`pipelines`/`writing`
routers stay. `research/SKILL.md` (`research-methodology`) is **deleted**. Routers/`INDEX.md` carry
**no** `archetype:`; new routers are **pure routing tables** (no methodology).

## What the move touches

1. **File moves** — `git mv` all 28 relocating leaves + the 3 moved routers.
2. **`name:` re-prefix** — 26 renamed leaves + 2 renamed routers.
3. **Cross-link rewrites** — every relative `.md` link (leaf→leaf, router→leaf, INDEX→leaf,
   leaf→bundled-resource, generated command-body links) recomputed to new relative depth. *Bulk +
   error-prone;* depth changes where nesting changes (e.g. `data/proteomics-qa.md` depth-1 →
   `bio/proteomics/proteomics-qa.md` depth-2).
4. **`INDEX.md`** — full rewrite: new `name`→`path` pairs (both columns change for every renamed
   leaf), new folder groupings, **remove** the `research-methodology` row.
5. **Routers** — author 7 new pure routers; retarget the 3 moved hubs' + `statistics/` routing links;
   delete `research/SKILL.md`.
6. **Drop the `research-methodology` Codex companion + rewrite every caller** (all `codex-skills/*`
   are generated and follow on regen — do not hand-edit them):
   - `science/src/science_tool/codex_skills.py`: remove the `COMPANION_SKILLS` research entry (`:18`);
     rework `_rewrite_companion_skill_references` (`:295-310`) so the new source instruction maps to
     its Codex form (`science-scientific-writing`; the research half reads `../../skills/INDEX.md`,
     **not** `codex-skills/INDEX.md`, which lists only commands + companions, not canonical leaves).
   - `references/command-preamble.md:10`; `references/role-prompts/{research-assistant.md:17,
     discussant.md:18}`.
   - `commands/{review.md:25, plan-pipeline.md:9, review-pipeline.md:9}`; `commands/plan-analysis.md`
     skill-list rows (`:79`, `:197`) — replace the `research-methodology` token with the specific
     leaves (e.g. `literature-evaluation`, `epistemics-annotation-curation-qa`).
   - `skills/INDEX.md:16` (drop row); `skills/data/SKILL.md:188` (internal link to `../research/SKILL.md`
     → retarget to `literature/` or drop).
   - `docs/user-guide/codex.md:113`; `codex-skills/INSTALL.codex.md` is **static** (hand-edited, not
     generated): drop `science-research-methodology`, keep `science-scientific-writing`.
   - Replacement instruction (canonical): keep "Load the `scientific-writing` skill"; replace the
     research half with "consult `skills/INDEX.md` and load the relevant `literature/`, `epistemics/`,
     and `research-package/` leaves (e.g. `literature-evaluation`, `literature-citation-discipline`,
     `epistemics-proposition-graph-reasoning`)."
7. **Rename/repath edits to `name`- or `path`-coupled sites:**
   - `skills_lint/lint.py` `HALT_ON_REQUIRED` — update all **9** paths: **7 under `bio/`, 1 under
     `ml/`, 1 under `epistemics/`** (`research/annotation-curation-qa.md` →
     `epistemics/annotation-curation-qa.md`).
   - `science/tests/test_command_docs.py` — every skills path/name assertion: `558-559`, `608-611`
     (source-tool paths), `632` & `657` (`_read` of `skills/data/SKILL.md`, `skills/data/frictionless.md`),
     `778-779` (`INDEX` `name`:`path` expectations — break on **both** rename and repath), `1010-1011`,
     `1035-1036`. (Sweep the whole file for `skills/data`, `skills/statistics`, `skills/research`, and
     old name tokens.)
   - `science/tests/test_codex_skills.py` — `86/89/96/127/129/138/836/844/857/862` (all
     `science-research-methodology` expectations, companion INDEX row, companion-body link targets).
   - **External live links** to moved leaves (all currently point at `statistics/estimator-certification.md`
     → `study-design/estimator-certification.md`, text `statistics-estimator-certification` →
     `study-design-estimator-certification`): `commands/plan-analysis.md:171`, `commands/pre-register.md:124`,
     `aspects/computational-analysis/computational-analysis.md:72`, `templates/pre-registration.md:170`,
     **and** `science/model/src/science_model/templates/pre-registration.md:170` (the packaged shadow
     the Renderer actually reads — must match the root template).
8. **Doctrine (`skills/meta/`):** `skill-authoring.md:34,43` and `skill-taxonomy.md:109` — flip
   framing from "reorg/rename deferred to phase 3" to "reorg + rename DONE; hub **extraction** is the
   deferred phase 4"; update hub paths (`data-management/`, `bio/transcriptomics/`, `pipelines/`,
   `statistics/`); state the new subject-prefix convention now in force. `templates/router.md` and
   the `<subject>-*` templates already describe the convention — verify no example cites an old path.
9. **`2026-07-19-skills-taxonomy-corpus-matrix.md`** — annotate that `path`/`subject`/`name` columns
   are pre-reorg (it was this phase's *input*). Do **not** edit historical phase-1/2 plan docs.
10. **Regenerate `codex-skills/`** and commit.

## Invariants & verification (the green gate)

- `science skills lint` (from `science/`, `--root ../skills`) exits 0: no dangling links, every leaf
  keeps its `archetype:`, `INDEX.md` enumerates every leaf by its **new** name, the nine
  `HALT_ON_REQUIRED` leaves still carry a halt-on section, routers/`INDEX.md` carry no `archetype:`.
- `test_committed_codex_skills_match_fresh_generation` green (mirror byte-identical to fresh gen —
  the deleted `science-research-methodology` dir must be gone from the committed mirror).
- `test_no_dangling_relative_links_in_generated_tree` (phase-2 guard) green.
- Full `uv run --frozen pytest` green; `ruff`/`pyright` at pre-existing baseline.
- **No dangling skill-name reference:** grep the repo (excluding generated `codex-skills/` and
  historical `docs/plans/`) for every *old* name and for `research-methodology` — zero live hits.
- **Preserved-by-design:** the 4 remaining hubs (`data-management/`, `bio/transcriptomics/`,
  `pipelines/`, `statistics/`) still route + teach; the linter does not ERROR on hubs today, so the
  moves keep it green. Do **not** add a router-methodology ERROR check this phase.

## Sequencing note (for the implementation plan)

Everything cross-links and cross-names, so a per-task green gate is **unsatisfiable** (as in phase
2): the moment files move + rename, links and name references dangle until every consumer lands.
Expect **RED intermediate commits by construction**, single green gate at the closing task. Natural
task cut:

1. Create dirs; `git mv` all files; re-prefix each moved leaf's/router's `name:`. *(RED)*
2. Rewrite all cross-links, `INDEX.md`, retarget/author routers, delete `research/SKILL.md`. *(RED)*
3. Drop the companion + rewrite all `research-methodology` callers (generator, preamble, role
   prompts, commands, INDEX link, user guide). *(RED)*
4. Path/name edits to `lint.py`, tests, external links, both templates, aspect, doctrine. *(approaching green)*
5. Regenerate `codex-skills/`; full green gate + the no-dangling-name grep. *(GREEN)*

## Deferred (phase 4) & follow-ups

- **Phase 4 (extraction/tightening):** extract `data-management/SKILL.md`,
  `bio/transcriptomics/SKILL.md`, `pipelines/SKILL.md` teaching content into typed leaves; trim
  `statistics/SKILL.md`'s principles to pointers; split `frictionless` (contract + CLI tool-guide)
  and `mutational-signatures` (signature + selection).
- **`HALT_ON_REQUIRED` is a "list-its-scope" guard** (hole by construction). Updating its 9 paths is
  required now; *deriving* it from `archetype == measurement-qa` is a phase-4 candidate.
- **Phase 5+ (vision):** lift skills to science-KG entities/relations; data-driven gap-detection;
  `/curate-skills`. Captured separately; not this phase.

## Risks / gotchas

- **Link-depth + name arithmetic** is the main correctness risk — recompute per file; the linter,
  the dangling-link guard, and the no-dangling-name grep are the safety net.
- **Both pre-registration templates** must move in lock-step (root + packaged shadow); the Renderer
  reads the packaged one.
- **Codex mirror is generated** — change source + generator, then regenerate; never hand-edit
  `codex-skills/`. The committed-match test catches a stale mirror.
- **Dropbox main-checkout volatility** — we work in a worktree branched from local HEAD (`9878802c`,
  39 commits ahead of `origin/main`); at merge time re-verify branch + trial-merge before trusting
  the conflict count.
- **`git mv` history** — preserve it; a delete+add loses per-leaf provenance.
