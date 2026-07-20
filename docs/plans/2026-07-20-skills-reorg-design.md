# Skills Corpus Reorganization (Phase 3) — Design

> Phase 3 of the skills-organization program. Phase 1 (archetype backfill) shipped at
> `1feb088c`; phase 2 (research/ + writing/ hub extraction) at `9878802c`. This phase is
> the **original complaint**: top-level `skills/` folders mix topics with disciplines, and
> `statistics/` is overloaded. It is a **pure structural reorganization** — files move into a
> coherent subject/domain tree; no teaching content is extracted or split.

**Goal:** Reorganize the 46-file skills corpus into a subject/domain top-level tree so every
folder is one coherent topic, and split the overloaded `statistics/` into modeling-methods vs
reasoning-disciplines — without changing the *content* of any leaf.

**Architecture:** `git mv` every leaf and router into the new tree; rewrite all cross-`.md`
links, `INDEX.md`, and the affected routers; update the handful of code/test/doctrine sites that
hard-code old paths; regenerate the `codex-skills/` mirror. The linter's discovery and
archetype/router checks are already path-agnostic, so the churn is paths + links, not logic.

**Scope (owner-ratified 2026-07-20):** *pure reorg only.* Explicitly **deferred to a later phase
(phase 4):** extracting the 3 surviving teaching hubs (`data-management`, `bio/transcriptomics`,
`pipelines`), trimming `statistics/SKILL.md`'s principles to pointers, and the `frictionless` /
`mutational-signatures` content splits.

## Global Constraints

- No AI-attribution trailers/footers on commits (no `Co-Authored-By`, no "Generated with").
- No "legacy"/"compatibility" layers; no "Unified" prefix. Composition > inheritance; explicit >
  defensive; fail early / no silent fallbacks.
- All `uv run` from `science/` (no root `pyproject.toml`); test dirs are not type-checked.
- `codex-skills/` is a git-tracked generated mirror — regenerate via
  `scripts/generate_codex_skills.py` after **any** `skills/` edit, or
  `test_committed_codex_skills_match_fresh_generation` fails.
- Use `git mv` (preserve history), never delete + re-add.
- Nothing pushed to origin unless the owner asks.

## Decisions (resolved during brainstorming)

| Fork | Decision |
|---|---|
| Organizing principle | **By subject/domain** — each top-level folder is one coherent topic. |
| Scope | **Pure reorg** — moves only; extraction/splits deferred to phase 4. |
| Bio grouping | Biological assays **grouped under `bio/`** parent. |
| Statistics overload | Split into `statistics/` (modeling method-guides) + **`study-design/`** (reasoning disciplines). |
| `embeddings-manifold-qa` | New top-level **`ml/`** (domain-agnostic manifold/clustering QA). |
| `annotation-curation-qa` | **`epistemics/`** (pairs with proposition schema/graph). |
| `openalex` / `pubmed` | **`literature/sources/`** (with literature-evaluation + citation-discipline). |
| Codex `research-methodology` companion | **Dropped** (research/ dissolves; reachable via `codex-skills/INDEX.md`). |

`data/` and `research/` **dissolve** entirely; `.claude-plugin/skills/` (causal-dag,
knowledge-graph) is a **separate** plugin tree, **out of scope**.

## Target tree

```
skills/
  INDEX.md                              # rewritten (all paths change)
  bio/
    SKILL.md                            # NEW thin router
    functional-genomics-qa.md          # <- data/functional-genomics-qa.md
    genomics/
      SKILL.md                          # <- data/genomics/SKILL.md
      somatic-mutation-qa.md
      copy-number-sv-qa.md
      mutational-signatures-and-selection.md
    transcriptomics/
      SKILL.md                          # <- data/expression/SKILL.md  (still a hub — extraction is phase 4)
      bulk-rnaseq-qa.md
      microarray-qa.md
      scrna-qa.md
    proteomics/
      SKILL.md                          # NEW thin router
      proteomics-qa.md
      protein-sequence-structure-qa.md
  ml/
    SKILL.md                            # NEW thin router
    embeddings-manifold-qa.md           # <- data/embeddings-manifold-qa.md
  data-management/
    SKILL.md                            # <- data/SKILL.md  (retarget links; still a hub — extraction is phase 4)
    frictionless.md
  statistics/
    SKILL.md                            # retarget routing to the 6 modeling leaves (drop the 8 that moved)
    bayesian-workflow.md
    compositional-data.md
    likelihood-model-comparison.md
    population-genetics-likelihood.md
    survival-and-hierarchical-models.md
    time-series-and-longitudinal-models.md
  study-design/
    SKILL.md                            # NEW router (8 discipline leaves)
    bias-vs-variance-decomposition.md
    causal-identification.md
    estimator-certification.md
    power-floor-acknowledgement.md
    prereg-amendment-vs-fresh.md
    prereg-defensive-instrumentation.md
    replicate-count-justification.md
    sensitivity-arbitration.md
  epistemics/
    SKILL.md                            # NEW router
    proposition-schema.md
    proposition-graph-reasoning.md
    annotation-curation-qa.md
  literature/
    SKILL.md                            # NEW router
    literature-evaluation.md
    citation-discipline.md
    sources/
      openalex.md
      pubmed.md
  research-package/
    SKILL.md                            # NEW router
    research-package-spec.md
    research-package-rendering.md
  pipelines/                            # UNCHANGED (still a hub — extraction is phase 4)
    SKILL.md  marimo.md  runpod.md  snakemake.md
  writing/                              # UNCHANGED (pure router post phase-2)
    SKILL.md  scientific-writing.md
  meta/                                 # UNCHANGED
    SKILL.md  skill-authoring.md  skill-taxonomy.md  templates/*
```

Leaf accounting (38): bio 9 (genomics 3, transcriptomics 3, proteomics 2, functional-genomics 1),
ml 1, data-management 1, statistics 6, study-design 8, epistemics 3, literature 4,
research-package 2, pipelines 3, writing 1. **28 move, 10 stay.**

## Router strategy

- **One `SKILL.md` router per top-level subject folder** (established convention — every current
  top-level folder has one). New routers: `bio/`, `bio/proteomics/`, `ml/`, `study-design/`,
  `epistemics/`, `literature/`, `research-package/` (7). New routers are **pure routing tables —
  no methodology** (respects the router invariant; new content is routing only, not teaching
  extraction).
- **Sub-folders only where ≥2 related leaves** (matches today: `data/genomics/` has a router,
  `data/proteomics-qa` sat loose). So `functional-genomics-qa` sits loose under `bio/`;
  `literature/sources/` (2 tool-guides) has no router of its own (routed by `literature/SKILL.md`).
- **Moved routers:** `data/genomics/SKILL.md` → `bio/genomics/SKILL.md`; `data/expression/SKILL.md`
  → `bio/transcriptomics/SKILL.md`; `data/SKILL.md` → `data-management/SKILL.md`. These three
  remain **hubs** (route + teach) — retarget only their routing links; their teaching content is
  left intact for the phase-4 extraction.
- **Retargeted in place:** `statistics/SKILL.md` — drop routing rows for the 8 leaves that left for
  `study-design/`, keep the 6 modeling leaves. (Its 14 numbered Principles are trimmed in phase 4,
  not now.)
- **Deleted:** `research/SKILL.md` (research/ dissolves; its routing role redistributes into the new
  `literature/`, `epistemics/`, `research-package/` routers).

## What the move touches

1. **File moves** — `git mv` all 28 relocating leaves + the 3 moved routers into the new tree.
2. **Cross-link rewrites** — every relative `.md` link (leaf→leaf, router→leaf, INDEX→leaf,
   leaf→bundled-resource, command-body links in the codex mirror) recomputed to new relative depth.
   *This is the bulk and the error-prone part:* depth changes where a leaf's nesting level changes
   (e.g. `data/proteomics-qa.md` depth-1 → `bio/proteomics/proteomics-qa.md` depth-2).
3. **`INDEX.md`** — full rewrite (every path changed; new folder groupings).
4. **7 new routers** authored (pure routing tables); 3 moved hubs' + `statistics/` routing retargeted.
5. **Code edits (`science/src`, `science/tests`):**
   - `skills_lint/lint.py` `HALT_ON_REQUIRED` — update all **9** paths (8 under `bio/*`, 1 under
     `ml/`, incl. `research/annotation-curation-qa.md` → `epistemics/annotation-curation-qa.md`).
   - `codex_skills.py` `COMPANION_SKILLS` — **remove** the `research-methodology` /
     `skills/research/SKILL.md` entry (keep `scientific-writing` and `skill-development`, both
     unmoved).
   - `tests/test_command_docs.py:558-559` — update literal assertions
     `skills/data/SKILL.md` → `skills/data-management/SKILL.md`,
     `skills/data/frictionless.md` → `skills/data-management/frictionless.md`.
   - `tests/test_codex_skills.py` — update any hard-coded companion/skill paths (research refs).
   - Command doc(s) under `commands/` carrying those literal `skills/data/...` paths — sweep +
     update (exact files enumerated in the plan).
   - `skills_lint/fixtures/INDEX.md` — verify (likely self-contained test paths; change only if it
     mirrors corpus paths).
6. **Doctrine (`skills/meta/`):**
   - `skill-authoring.md:43` and `skill-taxonomy.md:112` — update hub paths to the new tree and flip
     the framing from "reorg deferred to phase 3" to "reorg done; **extraction is the deferred phase
     4**". Remaining hubs become `data-management/`, `bio/transcriptomics/`, `pipelines/`,
     `statistics/`.
   - `2026-07-19-skills-taxonomy-corpus-matrix.md` — annotate that its `path` column is pre-reorg
     (or refresh it); it was the *input* to this phase.
7. **Regenerate `codex-skills/`** — run `scripts/generate_codex_skills.py`; commit the mirror
   (the dropped `research-methodology` companion dir disappears from the mirror here).

## Invariants & verification (the green gate)

- `science skills lint` (from `science/`, `--root ../skills`) exits 0: no dangling links, every leaf
  keeps its `archetype:`, `INDEX.md` enumerates every leaf, the 9 measurement-qa leaves still carry
  a halt-on section, routers/`INDEX.md` carry no `archetype:`.
- `test_committed_codex_skills_match_fresh_generation` green (mirror byte-identical to fresh gen).
- `test_no_dangling_relative_links_in_generated_tree` (phase-2 guard) green.
- Full `uv run --frozen pytest` green; `ruff`/`pyright` at pre-existing baseline.
- **Preserved-by-design:** the 4 remaining hubs (`data-management/`, `bio/transcriptomics/`,
  `pipelines/`, `statistics/`) still route + teach. The linter does **not** ERROR on hubs today, so
  moving them keeps it green. Do not add a router-methodology ERROR check in this phase.

## Sequencing note (for the implementation plan)

Everything cross-links, so — like phase 2 — a per-task green gate is **unsatisfiable**: the moment
files move, links dangle until every link + `INDEX.md` + the new routers land, and the code/test
path edits must land together with the moves. Expect **RED intermediate commits by construction**,
with a **single green gate at the closing task**. Natural task cut:

1. Create new dirs; `git mv` all files (leaves + moved routers). *(RED)*
2. Rewrite all cross-links, `INDEX.md`, retarget moved/`statistics` routers, author the 7 new
   routers, delete `research/SKILL.md`. *(RED — code/tests still reference old paths)*
3. Code + test + command-doc + doctrine path edits. *(approaching green)*
4. Regenerate `codex-skills/`; run the full green gate. *(GREEN)*

## Deferred (phase 4) & follow-ups

- **Phase 4 (extraction/tightening):** extract `data-management/SKILL.md`,
  `bio/transcriptomics/SKILL.md`, `pipelines/SKILL.md` teaching content into typed leaves; trim
  `statistics/SKILL.md`'s 14 principles to pointers; split `frictionless` (contract + CLI tool-guide)
  and `mutational-signatures` (signature + selection).
- **`HALT_ON_REQUIRED` is a "list-its-scope" guard** (hole by construction — cf. the toolkit
  convergence lesson). Updating its 9 paths is required now; *deriving* it from
  `archetype == measurement-qa` is a phase-4 candidate, not this phase.
- **Phase 5+ (vision):** lift skills from path-strings to science-KG entities/relations;
  data-driven gap-detection seeds skills; `/curate-skills` + periodic curation. Captured separately;
  not this phase.

## Risks / gotchas

- **Link-depth arithmetic** is the main correctness risk — recompute per file, don't pattern-replace
  blindly. The linter + dangling-link guard are the safety net; run them before the final gate.
- **Codex mirror regeneration** is mandatory after the moves (easy to forget; the committed-match
  test catches it).
- **Dropbox main-checkout volatility** — we work in a worktree branched from local HEAD (`9878802c`,
  39 commits ahead of `origin/main`); at merge time re-verify the branch and trial-merge before
  trusting the conflict count.
- **`git mv` history** — preserve it; a delete+add loses per-leaf provenance the corpus relies on.
