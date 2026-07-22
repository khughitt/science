# Pipelines Router Extraction — Design (phase-4 slice 4)

**Date:** 2026-07-22
**Status:** Approved (design forks resolved with owner via AskUserQuestion)
**Program:** Skills archetype/taxonomy — phase 4 (hub extraction). See
`project_skills_archetype_taxonomy` memory and the three shipped precedents:
statistics (slice 1), transcriptomics (slice 2), data-management (slice 3).

## Motivation

`skills/pipelines/SKILL.md` is the **last route-and-teach hub** in the corpus.
It fuses a routing table ("When to use which") with five "Cross-cutting
principles" that teach substrate-agnostic pipeline-construction rigor. The
router invariant — *a `SKILL.md` routes, it does not teach; teaching lives in a
typed leaf* — holds for every other subtree. Extracting this hub is the final
step that makes the invariant hold **corpus-wide** (zero hubs remain), a
program milestone.

## Decision

Convert `pipelines/SKILL.md` into a **pure router** and extract its five
principles into **one** new leaf:

- `skills/pipelines/reproducibility.md` — archetype **practice-guide**,
  `name: pipeline-reproducibility`, `provenance: internal`.

The filename is **bare** (`reproducibility.md`), matching the existing pipeline
leaves (`snakemake.md`, `marimo.md`, `runpod.md`); the `pipeline-` prefix lives
only in `name:`, per the corpus naming rule.

### Why practice-guide (and not analysis-discipline)

The first framing mapped the principles' "certify / lock / acknowledge" verbs to
`analysis-discipline`. Reading the actual template refuted that: the
`analysis-discipline` archetype is an **interpretation-gate** — its slots are
*Triggering condition / Required precommitment / Decision rule / Outcomes
(pass/fail) / Permitted reporting language*, all framed around "what must hold
**before a result may be interpreted**." The five pipeline principles are
**construction rigor** ("pin versions, lock seeds, hash inputs"; "make
provenance-stamping a convention"), not interpretation gates. They map cleanly
onto the `practice-guide` template (*When to apply / Workflow steps / Judgment
rules / Quality criteria / Common pitfalls / Outputs*), and this matches the
slice-3 precedent where the parallel "how to do cross-cutting data work well"
content became `data-management-acquisition.md`, a practice-guide.

The alternative that these are a single-vs-two-leaf split (as data-management
was) was rejected: the teaching is ~40 lines / 5 principles; splitting a
provenance-stamp "contract" out as a separate normative-reference would be
over-engineering at that volume (YAGNI).

### Principle → practice-guide slot mapping

| Source principle (in `SKILL.md`) | practice-guide slot |
|---|---|
| 1. Tool-agnostic plans first | Workflow steps |
| 2. Side effects belong outside the workflow tree (marker-file pattern; `protected()` does not prevent rerun-cleanup) | Judgment rules |
| 3. Reproducibility = environment + seeds + inputs | Quality criteria |
| 4. Provenance is captured, not hand-stamped — fb-2026-07-11-026 | Quality criteria / Outputs |
| 5. Sandboxed network fetches hang, not fail (wall-clock watchdog; pre-stage inputs) — fb-2026-07-10-001/-002/-003 | Common pitfalls |

Inline `fb-…` attributions carry into the leaf verbatim (provenance-coverage
discipline — never drop attribution when relocating content).

**Principle 4 is re-expressed through the canonical run-fingerprint model, not
promoted verbatim.** The source hub text mandated ad-hoc per-output fields
`git_revision` / `created` / `sha256` — but `git_revision` appears nowhere else
in the toolkit, and the canonical mechanism is `science dataset register-run`,
which captures a `science-run-fingerprint/v1` record (`code_sha`, env/param/
input/output-manifest digests, `seed_policy`/`step_seeds`) on the `workflow-run`
entity and is explicitly *not* hand-authored (`templates/workflow-run.md`,
`science/model/src/science_model/run_fingerprint.py`). Promoting the ad-hoc
schema would mint a second, conflicting provenance contract. The leaf expresses
the principle's rationale (recoverable vs unrecoverable incident) and its
attribution through that canonical mechanism plus the per-output Frictionless
`datapackage.yaml`, introducing no new schema.

**Principle 2 and the fetch-concurrency guard are Snakemake realizations, not
universal mechanics.** `protected()`, `out_dir`, rules, `--retries`, and high
`-c` belong to `snakemake.md`. The shared leaf states the substrate-agnostic
principle (side effects outside the managed output tree; bound fetch concurrency)
and routes to `snakemake.md` for the mechanics — so the "applies to every
substrate" framing does not overclaim.

## Scope

**Files touched:**

- **Create** `skills/pipelines/reproducibility.md` (practice-guide leaf).
- **Modify** `skills/pipelines/SKILL.md` → pure router on the router template
  (Routing trigger / Scope boundary / Leaves [4 rows] / Decision-compose order /
  Parent & neighbors / Success test / Companion Skills). The "Cross-cutting
  principles" section is deleted; the "When to use which" table becomes the
  Leaves table; the marimo→snakemake→runpod compose note becomes
  Decision/compose order. The inherited "terminal rule should produce a research
  package" Companion line is corrected (see Content-guard/coupling below).
- **Modify** `skills/pipelines/snakemake.md`, `marimo.md`, `runpod.md` — retarget
  each leaf's Companion Skills reference that currently cites `SKILL.md` as the
  source of "shared pipeline conventions / artifact contracts": that role moves
  to `reproducibility.md`. A router link to `SKILL.md` is retained purely for
  navigation.
- **Modify** `skills/INDEX.md` — add the `pipeline-reproducibility` machine
  entry under `## Execution / Orchestration`.
- **Modify** `skills/meta/skill-authoring.md` and `skills/meta/skill-taxonomy.md`
  — reconcile the hub claim to **"0 hubs remain; the router invariant now holds
  corpus-wide,"** appending the pipelines extraction sentence (dated 2026-07-22,
  → `pipeline-reproducibility` practice-guide).
- **Regenerate** `codex-skills/` — doctrine feeds the `skill-development`
  companion mirror; this is the green gate.

**Corpus:** 42 → 43 leaves.

## Non-goals

- The `mutational-signatures` split (remaining phase-4 work — stays listed as
  remaining in the doctrine).
- The `bio/genomics/SKILL.md` "two leaves" → "three" prose fix (separate).
- Phase 5 (skills-as-KG-entities).

## Content-guard analysis (slice-3 lesson applied)

Slice 3 discovered that `science/tests/test_command_docs.py` and
`test_codex_skills.py` assert specific guidance lives in specific skill files by
substring, so relocating content breaks them. Grepping those files for this
slice's targets:

- **No test asserts any content inside `pipelines/SKILL.md`.** The five
  principles were never referenced by a content-guard.
- The one relevant guard (`test_data_skills_document_configured_data_root`)
  reads `skills/pipelines/snakemake.md` for the data-root policy — and
  `snakemake.md`'s data-root content is **not moved** by this slice (only its
  Companion-Skills reference is retargeted).

Risk is therefore low **for tests**. The **mandatory full-suite pytest green
gate remains non-negotiable** (that is what caught slice 3), and the plan
includes a pre-delete grep re-confirming no test asserts the principle phrases
before they are removed from `SKILL.md`.

**A retarget IS required** (unlike an earlier draft's claim): the three
substrate leaves each name `SKILL.md` as the source of "shared pipeline
conventions / artifact contracts." Once `SKILL.md` is navigation-only those
descriptions are false, so the conventions reference retargets to
`reproducibility.md` (Task 3) while a navigation link to the router is retained.

## Task decomposition (4 tasks, no RED window)

1. **Create the leaf + register it in INDEX.md** (same task → no missing-index
   RED window). The leaf's Companion Skills use **ordinary Markdown links** to
   `SKILL.md`, `snakemake.md`, `marimo.md`, `runpod.md`, `../INDEX.md` — all
   exist at Task 1, so the links resolve (no RED) *and* `check_relative_links`
   guards them against future drift. Green.
2. **Rewrite `SKILL.md` hub → router.** The Leaves-table markdown link to
   `./reproducibility.md` resolves because Task 1 created the file. Pre-delete
   grep confirms no test asserts the principle phrases. The inherited
   research-package Companion line is corrected to distinguish workflow-result
   packages (`results/<workflow>/<slug>/`, → `data-management/conventions.md`)
   from optional research packages. Green.
3. **Retarget the three substrate leaves' Companion Skills** — the "shared
   pipeline conventions / artifact contracts" reference moves from `SKILL.md` to
   `reproducibility.md`; a navigation link to the router is retained. Green.
4. **Reconcile both doctrine files + regenerate the codex mirror.** Green gate =
   `science skills lint` + full `pytest` + `test_committed_codex_skills_match_fresh_generation`.

## Verification

- `cd science && uv run --frozen science skills lint --root ../skills` → exit 0.
- `cd science && uv run --frozen pytest` → exit 0 (run the whole suite; do not
  stop at skills lint — the slice-3 lesson).
- `codex-skills/` regenerated and byte-identical to fresh generation.
- Ruff/pyright: this slice touches **no Python**; base-main carries pre-existing
  ruff/pyright failures in unrelated files (see slice-2 lesson) — prove the
  touched set is Python-free rather than &&-chaining the gate through them.

## Execution

Subagent-driven development (fresh implementer + spec/quality reviewer per task,
opus whole-branch review) in an isolated `.worktrees/pipelines-router-extraction`
branch off `main`. Model selection: sonnet implementers (router/leaf mapping and
doctrine reconciliation are judgment, not verbatim transcription), sonnet
reviewers, opus final review. Controller owns the Task-4 green-gate suite run
(subagents have repeatedly backgrounded long suites and returned without
committing — 4 confirmed occurrences).
