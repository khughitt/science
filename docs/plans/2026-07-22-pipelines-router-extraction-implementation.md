# Pipelines Router Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `skills/pipelines/SKILL.md` from a route-and-teach hub into a pure navigation router, extracting its five "Cross-cutting principles" into one new `reproducibility.md` practice-guide leaf; retarget the three substrate leaves' conventions references; reconcile doctrine to "zero hubs remain" and regenerate the codex mirror.

**Architecture:** Four tasks. Task 1 creates the leaf and registers it in `skills/INDEX.md` (same task → no missing-index RED window). Task 2 rewrites the hub into a router (its Leaves-table link resolves because Task 1 created the leaf) and corrects the inherited research-package Companion line. Task 3 retargets the three substrate leaves whose Companion Skills currently name `SKILL.md` as the source of "shared pipeline conventions / artifact contracts" — a claim that goes false once the hub is navigation-only. Task 4 reconciles the two doctrine files and regenerates `codex-skills/` — the green gate.

**Tech Stack:** Markdown skills corpus; `science skills lint`; pytest content-guards; `scripts/generate_codex_skills.py` (codex mirror).

## Global Constraints

- No AI-attribution trailers/footers on commits (no "Co-Authored-By", no "Generated with Claude Code").
- No "legacy"/"compatibility" layers; no "Unified" prefix. Composition > inheritance; explicit > defensive; fail early.
- Use `~/d/` in any doc/code path text (never `/home/keith/d/` or `/mnt/ssd/Dropbox/`).
- All `uv run` commands run from the `science/` package dir (there is no root `pyproject.toml`).
- **All verification commands are relative to the active worktree root (the implementer's cwd). Never `cd` to an absolute repo path — an isolated-worktree run must inspect its own checkout, not the main one.**
- Skills lint: `uv run --frozen science skills lint --root ../skills` (run from `science/`).
- `codex-skills/` is **generated** — never hand-edit; regenerate via `uv run --frozen python ../scripts/generate_codex_skills.py` (no arguments; run from `science/`) after any `skills/` edit, including `skills/meta/` doc-only edits.
- Leaf filenames in a subject subtree carry **no** subject prefix in the filename; the `pipeline-` prefix appears only in `name:`. The new file is `reproducibility.md` with `name: pipeline-reproducibility` (matches `snakemake.md` → `name: pipeline-snakemake`).
- Preserve inline `fb-…` provenance attributions verbatim when relocating content.
- **Do not introduce a hand-authored provenance schema.** The canonical run-reproducibility record is captured by `science dataset register-run` (`science-run-fingerprint/v1`: `code_sha`, env/param/input/output digests, `seed_policy`/`step_seeds`) and is explicitly *not* hand-authored; per-output packages carry a Frictionless `datapackage.yaml`. `git_revision` is not a toolkit field — do not use it.
- **Keep workflow-result packages distinct from research packages.** Ordinary pipeline outputs are workflow-result packages under `results/<workflow>/<slug>/`; a research package under `research/packages/{name}/` is an *optional* narrative deliverable, not a universal terminal rule.
- The mandatory green gate is the **full** pytest suite, not just skills lint (slice-3 lesson).
- This slice touches **no Python**; base `main` carries pre-existing ruff/pyright failures in unrelated files — do not &&-chain the gate through them.
- Corpus after this slice: 42 → 43 leaves.

---

### Task 1: Create `reproducibility.md` leaf + register in INDEX.md

**Files:**
- Create: `skills/pipelines/reproducibility.md`
- Modify: `skills/INDEX.md` (add machine entry under `## Execution / Orchestration`)

**Interfaces:**
- Produces: a practice-guide leaf `name: pipeline-reproducibility` at `skills/pipelines/reproducibility.md`, referenced by Task 2's router Leaves table via `./reproducibility.md` and by Task 3's retargeted Companion links via `reproducibility.md`.

- [ ] **Step 1: Create the leaf file** with exactly this content:

```markdown
---
name: pipeline-reproducibility
description: Use when constructing a computational pipeline that must be reproducible — after methodology is decided, before and while committing to an orchestration substrate.
archetype: practice-guide
provenance: internal
---

# Pipeline Reproducibility

Answers: how do I construct any computational pipeline — regardless of substrate
(Snakemake, marimo, RunPod) — so that it is reproducible, provenance-captured,
and robust in constrained environments?

## When to apply

Load this after methodology is decided and you are planning or building the
execution shape of an analysis, before and while committing to a specific
orchestration substrate. The principles are substrate-agnostic; their mechanics
differ by substrate, and each substrate's realization lives in its tool-guide
leaf (`snakemake.md`, `marimo.md`, `runpod.md`). This practice covers what must
hold across all of them.

## Workflow steps

1. **Produce a tool-agnostic task list first.** `science-plan-pipeline` produces
   tool-agnostic task lists. Only commit to a specific orchestration substrate
   after the task list stabilizes — picking an execution substrate before the
   analysis question is specified usually produces ceremony without rigor.
2. **Pin the environment and seeds, and pre-stage inputs.** Pin tool versions and
   lock random seeds; declare each step's `seed_bindings` so the run's seed policy
   can be captured rather than guessed. Fetch inputs to `data/raw/` in a separate,
   network-allowed step so the run itself reads local files and never depends on
   egress.
3. **Execute on the chosen substrate.** Run the pipeline; the workflow executor
   writes (or updates) the tracked run-aggregate `datapackage.yaml` at
   `results/<workflow>/<run>/`.
4. **Commit the run records, verify a clean worktree, then register — after
   execution.** Execution itself writes tracked files, so a worktree that was
   clean *before* the run is dirty after it: commit the lightweight run manifest
   and `config.yaml` snapshot and confirm `git status` is clean immediately before
   capture, or the fingerprint records `code_dirty` and cannot reconstruct the
   source. Then capture with `science dataset register-run workflow-run:<slug>`. It
   reads the aggregate `datapackage.yaml`, records the `code_sha`, the
   environment/parameter/input/output-manifest digests, and the
   `seed_policy`/`step_seeds` derived from the workflow's steps, and writes the
   per-output `datapackage.yaml` views beneath the run package (with derived
   dataset entities under `entities/datasets/`). The fingerprint is an
   observation, never hand-authored; `science validate` re-checks it against
   `execution:` and tells you to re-register if they drift.

## Judgment rules

- **Side effects outside the managed output tree must be handled idempotently or
  transactionally** so a rerun cannot observe partial state. The general rule is
  substrate-independent; its realization differs — in Snakemake, use the
  marker-file pattern for any rule writing outside `out_dir` (`protected()` does
  *not* prevent rerun-cleanup; see `snakemake.md`), whereas a reactive notebook
  re-derives state on each run.
- **Bound fetch concurrency rather than leaning on retries.** When a substrate's
  own retry mechanism can deadlock under high fetch concurrency, reduce
  concurrency instead of adding retry loops. (In Snakemake, `--retries` under
  high `-c`; see `snakemake.md`.)

## Quality criteria

- **Reproducibility = environment + seeds + inputs.** Pin tool versions, lock
  random seeds, and identify inputs by their dataset references and the upstream
  datapackage resource hashes. Without all three the pipeline is decorative.
- **Provenance is captured, not hand-stamped.** A reproducible run is registered
  from a **clean worktree** with `science dataset register-run`, producing a
  `science-run-fingerprint/v1` record on the `workflow-run` entity (`code_sha`,
  env/param/input/output-manifest digests, `seed_policy`/`step_seeds`). A dirty
  tree is flagged (`code_dirty`) but not reconstructable — treat it as
  non-reproducible. Inputs are identified through the run's declared dataset
  references plus the upstream datapackage resource hashes, not through
  hand-authored per-output fields. Making this a convention rather than a
  per-script habit is the difference between a recoverable incident and an
  unrecoverable one: an unrelated pipeline's fingerprint saving your run is luck;
  your own is design. (fb-2026-07-11-026.)

## Common pitfalls

- **In constrained/sandboxed environments, network fetches can hang, not fail.**
  A sandbox that denies egress may *stall* an in-rule download indefinitely
  rather than return an error, wedging the whole run. Give every fetch a **total
  wall-clock watchdog**, not just a per-read timeout — a per-read `timeout=` does
  nothing against a slow-trickle or half-open socket, so a partial download can
  sit for hours. (fb-2026-07-10-001, -002, -003.)
- **Registering before the run completes, or from a dirty tree.** `register-run`
  reads the run-aggregate `datapackage.yaml` the executor writes at
  `results/<workflow>/<run>/`; run it *after* execution and from a committed tree,
  or the fingerprint records `code_dirty` and cannot reconstruct the source.
- **Relying on `protected()` for side-effect safety.** It does not prevent
  rerun-cleanup; use the marker-file pattern (see Judgment rules and
  `snakemake.md`).

## Outputs

A registered workflow run: the run owns one workflow-result package at
`results/<workflow>/<run>/` (its aggregate `datapackage.yaml`), and `science
dataset register-run` writes the per-output `datapackage.yaml` views beneath it —
and the derived dataset entities under `entities/datasets/` — while capturing the
run's `science-run-fingerprint/v1` fingerprint (`code_sha`, environment/input/
output digests, `seed_policy`/`step_seeds`). From a clean-tree registration, that
record identifies the tree
state and — via the input dataset references and their upstream resource hashes —
the inputs that produced the results, without any hand-authored metadata.

## Success test

Given a pipeline run registered from a clean worktree, can an independent agent
reproduce its outputs from the pinned environment, captured seeds, and the input
dataset references (with their upstream datapackage resource hashes), and tie any
output to the tree state via the run's captured `science-run-fingerprint/v1`
fingerprint — without relying on egress at run time and without hand-authored
provenance fields?

## Companion Skills

- [`../INDEX.md`](../INDEX.md) — the skill index.
- [`SKILL.md`](SKILL.md) — the pipelines router (choose the execution substrate).
- [`snakemake.md`](snakemake.md), [`marimo.md`](marimo.md), [`runpod.md`](runpod.md) — the substrate tool-guides whose mechanics this practice constrains.
```

- [ ] **Step 2: Register the leaf in `skills/INDEX.md`.** Under `## Execution / Orchestration`, insert the new machine entry immediately after the `pipelines` router line and before `pipeline-snakemake`:

Before:
```
- `pipelines`: `skills/pipelines/SKILL.md`
- `pipeline-snakemake`: `skills/pipelines/snakemake.md`
```
After:
```
- `pipelines`: `skills/pipelines/SKILL.md`
- `pipeline-reproducibility`: `skills/pipelines/reproducibility.md`
- `pipeline-snakemake`: `skills/pipelines/snakemake.md`
```

- [ ] **Step 3: Run skills lint — expect PASS.**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exit 0. (`pipeline-reproducibility` is a leaf with `archetype: practice-guide`, registered in INDEX.md; its Companion Skills are ordinary Markdown links to existing siblings/parent — all resolve.)

- [ ] **Step 4: Confirm the corpus leaf count rose by one.**

Run (from the worktree root): `rg -l '^archetype:' skills/ | rg -v '/meta/' | wc -l`
Expected: `43` (was 42).

- [ ] **Step 5: Commit.**

```bash
git add skills/pipelines/reproducibility.md skills/INDEX.md
git commit -m "feat(skills): add pipeline-reproducibility practice-guide leaf + register in INDEX"
```

---

### Task 2: Rewrite `pipelines/SKILL.md` hub → pure router

**Files:**
- Modify: `skills/pipelines/SKILL.md` (full rewrite to the router template)

**Interfaces:**
- Consumes: `./reproducibility.md` (created in Task 1) — referenced in the Leaves table as a resolving markdown link.
- Produces: a pure router `name: pipelines` with no methodology content, and Companion links that distinguish workflow-result packages from research packages.

- [ ] **Step 1: Pre-delete safety grep — confirm no test asserts the five principles' phrases.** Before removing the "Cross-cutting principles" section, verify nothing in the test suite depends on those phrases living in `SKILL.md`:

Run (from the worktree root):
```bash
rg --no-config -n 'Cross-cutting principles|stamps its own provenance|marker-file pattern|wall-clock watchdog|pipeline is decorative|Tool-agnostic plans first' science/tests/
```
Expected: no matches (empty output). If any match appears, STOP and escalate — a content-guard depends on the phrase and it must be re-homed (slice-3 re-home-preserve-strength procedure), not silently deleted.

(Probe scope note: the distinctive token is the heading `Cross-cutting principles`, not the bare word `Cross-cutting`, which collides with unrelated fixtures — a big-picture question fixture and an explore-ideas "Cross-cutting theme" title. Verified separately that no test references `pipelines/SKILL.md` and that none of the specific principle phrases appear in `science/tests/`.)

- [ ] **Step 2: Replace the entire contents of `skills/pipelines/SKILL.md`** with exactly this router:

```markdown
---
name: pipelines
description: Source of truth for choosing and combining computational-execution skills (Snakemake, marimo, RunPod). Load when planning the orchestration shape of an analysis after methodology is decided. Routes to the leaves below.
provenance: internal
---

# Pipelines Router

A router carries no methodology; teaching content belongs in a typed leaf. For
the cross-cutting rigor every pipeline must satisfy regardless of substrate, load
`reproducibility.md`.

## Routing trigger

Load this router when the execution shape of an analysis is in scope — **only
after** methodology is decided (see `skills/INDEX.md` and `science-plan-analysis`)
— before loading any leaf. Picking an execution substrate before the analysis
question is specified usually produces ceremony without rigor.

## Scope boundary

Covers the choice and combination of computational-execution substrates and the
substrate-agnostic reproducibility practice. Excludes the analysis methodology
itself (statistics, study design) and data acquisition/QA (data-management).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| [`reproducibility.md`](./reproducibility.md) | Constructing any pipeline that must be reproducible, provenance-captured, or robust to sandboxed fetches | You are only comparing substrates and no pipeline is being constructed |
| [`snakemake.md`](./snakemake.md) | Multi-step pipeline with file dependencies; intermediates worth caching; reproducible re-runs matter | One-off exploration; no DAG of dependencies |
| [`marimo.md`](./marimo.md) | Interactive exploration; parameter sweeps; presentation with widgets; pre-pipeline prototyping | Production batch; long jobs; CI |
| [`runpod.md`](./runpod.md) | Short-lived rented GPU; uv-based project; workload too large/slow for workstation | Long-lived managed cluster; CPU-only work |

## Decision / compose order

The substrate leaves are not mutually exclusive: `marimo` for prototyping ->
`snakemake` for the pipeline -> `runpod` for the GPU rule. `reproducibility`
applies across all of them — load it alongside whichever substrate you choose,
not instead of it.

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `../statistics/SKILL.md`, `../data-management/SKILL.md`, `../research-package/SKILL.md`

## Success test

Representative in-scope tasks route to the correct substrate leaf (or the correct
compose order when leaves combine), and construction-rigor questions route to
`reproducibility.md`, without any methodology being read from this router.

## Companion Skills

- [`../data-management/conventions.md`](../data-management/conventions.md) — data/result layout: read from `data/raw/`, write processed outputs and workflow-result packages under `results/<workflow>/<slug>/`.
- [`../research-package/research-package-spec.md`](../research-package/research-package-spec.md) — **only when** the pipeline's deliverable is a narrative research package under `research/packages/{name}/`; ordinary workflow results do not need one.
- [`../statistics/SKILL.md`](../statistics/SKILL.md) — statistical decisions that should be made before pipeline construction.
```

- [ ] **Step 3: Run skills lint — expect PASS.**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exit 0. (Router carries no `archetype:`; the Leaves and Companion links all resolve.)

- [ ] **Step 4: Confirm the router teaches nothing — the principles are gone.**

Run (from the worktree root): `rg --no-config -n 'Cross-cutting|stamps its own provenance|register-run|decorative' skills/pipelines/SKILL.md`
Expected: no matches.

- [ ] **Step 5: Commit.**

```bash
git add skills/pipelines/SKILL.md
git commit -m "refactor(skills): convert pipelines hub to a pure router"
```

---

### Task 3: Retarget the three substrate leaves' Companion Skills

**Files:**
- Modify: `skills/pipelines/snakemake.md`
- Modify: `skills/pipelines/marimo.md`
- Modify: `skills/pipelines/runpod.md`

**Interfaces:**
- Consumes: `reproducibility.md` (Task 1) and the router `SKILL.md` (Task 2), both existing links.

Each leaf currently names `SKILL.md` as the source of "shared pipeline conventions / artifact contracts" — false once the hub is navigation-only. Split that into a substantive link to `reproducibility.md` plus a navigation link to the router.

- [ ] **Step 1: `snakemake.md` — replace the first Companion bullet.**

Before:
```
- [`SKILL.md`](SKILL.md) - shared pipeline conventions and workflow artifact expectations.
```
After:
```
- [`reproducibility.md`](reproducibility.md) - shared, substrate-agnostic reproducibility practice (tool-agnostic planning, provenance capture, sandbox-fetch guards).
- [`SKILL.md`](SKILL.md) - pipelines router: choosing and combining execution substrates.
```

- [ ] **Step 2: `marimo.md` — replace the first Companion bullet.**

Before:
```
- [`SKILL.md`](SKILL.md) - shared pipeline conventions and workflow artifact expectations.
```
After:
```
- [`reproducibility.md`](reproducibility.md) - shared, substrate-agnostic reproducibility practice (tool-agnostic planning, provenance capture, sandbox-fetch guards).
- [`SKILL.md`](SKILL.md) - pipelines router: choosing and combining execution substrates.
```

- [ ] **Step 3: `runpod.md` — replace the first Companion bullet.**

Before:
```
- [`SKILL.md`](SKILL.md) - shared pipeline conventions and artifact contracts.
```
After:
```
- [`reproducibility.md`](reproducibility.md) - shared, substrate-agnostic reproducibility practice (tool-agnostic planning, provenance capture, sandbox-fetch guards).
- [`SKILL.md`](SKILL.md) - pipelines router: choosing and combining execution substrates.
```

- [ ] **Step 4: Run skills lint — expect PASS (new links resolve).**

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exit 0.

- [ ] **Step 5: Commit.**

```bash
git add skills/pipelines/snakemake.md skills/pipelines/marimo.md skills/pipelines/runpod.md
git commit -m "docs(skills): retarget pipeline substrate leaves to the reproducibility practice"
```

---

### Task 4: Reconcile doctrine to zero hubs + regenerate codex mirror (green gate)

**Files:**
- Modify: `skills/meta/skill-authoring.md`
- Modify: `skills/meta/skill-taxonomy.md`
- Regenerate: `codex-skills/` (generated; do not hand-edit)

**Interfaces:**
- Consumes: the completed router (Task 2), leaf (Task 1), and retargets (Task 3).

- [ ] **Step 1: Update `skills/meta/skill-authoring.md` "Placement" bullet** — hub extraction is complete, so drop it from the pending phase-4 list.

Before:
```
- Do **not** begin phase-4 corpus work (hub extraction, principle-trimming, or the `mutational-signatures` split) while authoring a single skill — that is migration work driven by the matrix, not per-skill work.
```
After:
```
- Do **not** begin phase-4 corpus work (principle-trimming or the `mutational-signatures` split) while authoring a single skill — that is migration work driven by the matrix, not per-skill work.
```

- [ ] **Step 2: Update `skills/meta/skill-authoring.md` "Router invariant" paragraph.**

Change the opening of the paragraph from:
```
This is stated as a **target invariant** the corpus is converging on: 1 of 14 current `SKILL.md` files is still a **hub** (route + teach) — `pipelines/SKILL.md`. `data-management/SKILL.md` was extracted
```
to:
```
This invariant **now holds corpus-wide**: 0 of 14 current `SKILL.md` files are hubs (route + teach). `pipelines/SKILL.md` was extracted to a router on 2026-07-22, its five cross-cutting principles moving into `pipeline-reproducibility` (practice-guide). `data-management/SKILL.md` was extracted
```

And change the clause near the end of the same paragraph from:
```
Every remaining hub is a migration extraction candidate (see the matrix). A document that routes *and* teaches is a hub; its teaching content is extracted into typed leaves before it is a true router.
```
to:
```
No hubs remain; any future `SKILL.md` that routes *and* teaches must be extracted before it is accepted. A document that routes *and* teaches is a hub; its teaching content is extracted into typed leaves before it is a true router.
```

- [ ] **Step 3: Update `skills/meta/skill-taxonomy.md` "archetype required" bullet.**

Before:
```
- Declaring `archetype:` is required on every leaf, and the corpus was backfilled in full on 2026-07-20. Reorg + rename completed in phase 3; hub **extraction** + principle-trimming + the `mutational-signatures` split remain (phase 4).
```
After:
```
- Declaring `archetype:` is required on every leaf, and the corpus was backfilled in full on 2026-07-20. Reorg + rename completed in phase 3; hub **extraction** completed in phase 4; principle-trimming + the `mutational-signatures` split remain.
```

- [ ] **Step 4: Update `skills/meta/skill-taxonomy.md` "router invariant now holds" bullet.**

Before:
```
One hub remains (`pipelines/`), pending phase-4 extraction; `statistics/` was reconciled to a router on 2026-07-21 (slice 1) and `bio/transcriptomics/` was extracted the same day into `transcriptomics-cohort-qa` and `transcriptomics-data-integration` (slice 2); `data-management/` was extracted on 2026-07-22 into `data-management-conventions` and `data-management-acquisition` (slice 3).
```
After:
```
No hubs remain: `pipelines/` was extracted on 2026-07-22 into `pipeline-reproducibility` (practice-guide, slice 4), completing the invariant corpus-wide; `statistics/` was reconciled to a router on 2026-07-21 (slice 1) and `bio/transcriptomics/` was extracted the same day into `transcriptomics-cohort-qa` and `transcriptomics-data-integration` (slice 2); `data-management/` was extracted on 2026-07-22 into `data-management-conventions` and `data-management-acquisition` (slice 3).
```

- [ ] **Step 5: Regenerate the codex mirror.**

Run (from `science/`): `uv run --frozen python ../scripts/generate_codex_skills.py`
(The script takes no arguments — it derives the repo root from its own path and writes `codex-skills/`. The `skill-development` companion mirrors `skills/meta/`, so the doctrine edits must propagate. Expected stdout: `Generated Codex skills in …/codex-skills`.)

- [ ] **Step 6: Green gate — skills lint, full pytest, codex match.** Run each separately (do not &&-chain through pre-existing ruff/pyright failures).

Run (from `science/`): `uv run --frozen science skills lint --root ../skills`
Expected: exit 0.

Run (from `science/`): `uv run --frozen pytest`
Expected: exit 0 — in particular `test_committed_codex_skills_match_fresh_generation` and `test_data_skills_document_configured_data_root` pass. Run the WHOLE suite (slice-3 lesson); do not stop at skills lint.

- [ ] **Step 7: Commit.**

```bash
git add skills/meta/skill-authoring.md skills/meta/skill-taxonomy.md codex-skills/
git commit -m "docs(skills): reconcile doctrine to zero hubs; regenerate codex mirror"
```

- [ ] **Step 8: Fail-closed Python-free check (after the final commit).** Confirm the whole branch touched no Python, so no new ruff/pyright is possible.

Run (from the worktree root) — each git step is guarded so a failure cannot masquerade as a clean result:
```bash
base=$(git merge-base main HEAD) || { echo "FAIL: merge-base errored"; exit 1; }
[ -n "$base" ] || { echo "FAIL: empty merge-base"; exit 1; }
files=$(git diff --name-only "$base"..HEAD -- '*.py') || { echo "FAIL: git diff errored"; exit 1; }
if [ -n "$files" ]; then echo "FAIL: python touched:"; echo "$files"; exit 1; fi
untracked=$(git status --porcelain --untracked-files=all -- '*.py') || { echo "FAIL: git status errored"; exit 1; }
if [ -n "$untracked" ]; then echo "FAIL: untracked/modified python present:"; echo "$untracked"; exit 1; fi
echo "OK: no python touched by this branch"
```
Expected: `OK: no python touched by this branch` (exit 0). Any git failure, any committed `*.py` in the branch range, or any untracked/modified `*.py` in the worktree exits 1 and must be investigated before merge.

---

## Final whole-branch review

After Task 4, dispatch the opus whole-branch review (superpowers:requesting-code-review) over the full branch diff (`git merge-base main HEAD`..HEAD). Focus areas: (a) practice-guide slot fidelity — do the five principles land in the right slots without dropped nuance (the reproducibility triad's "all three or decorative"; the watchdog's "per-read timeout does nothing")?; (b) provenance principle expressed through `science dataset register-run`/`science-run-fingerprint/v1` with **no** reintroduced `git_revision`/hand-authored schema, attribution preserved; (c) the router carries zero methodology and its research-package Companion line is conditional, not universal; (d) Snakemake-specific mechanics (`protected()`, `out_dir`, `--retries`, `-c`) are phrased as realizations routing to `snakemake.md`, not as universal rules; (e) the three substrate leaves' Companion retargets are consistent; (f) doctrine reconciliation internally consistent — no lingering "one hub remains"/"pipelines still a hub" anywhere in `skills/` or `codex-skills/`; (g) INDEX registration correct. Then superpowers:finishing-a-development-branch.

## Self-review (author)

- **Spec coverage:** leaf creation (Task 1), INDEX registration (Task 1 Step 2), router conversion + research-package correction (Task 2), substrate-leaf retarget (Task 3), doctrine reconciliation both files (Task 4), codex regen (Task 4) — all covered.
- **Placeholders:** none — full leaf and router content inlined; doctrine and Companion edits given as exact before→after.
- **Type/name consistency:** file `reproducibility.md`; `name: pipeline-reproducibility`; INDEX entry `pipeline-reproducibility` → `skills/pipelines/reproducibility.md`; router Leaves link `./reproducibility.md`; substrate-leaf links `reproducibility.md`; doctrine mentions `pipeline-reproducibility` — all consistent.
- **Provenance model:** the leaf uses only the canonical `science dataset register-run`/`science-run-fingerprint/v1` mechanism + Frictionless `datapackage.yaml`; no `git_revision` and no hand-authored schema.
- **RED-window check:** Task 1 registers the leaf in INDEX in the same commit it is created (no missing-index RED); the leaf's Companion Skills are ordinary Markdown links to targets that all exist at Task 1 (so they resolve *and* are drift-checked); Task 2's router link resolves because Task 1 landed first; Task 3's links resolve against Task-1/Task-2 files. Each task is independently green.
- **Worktree hygiene:** every verification command is relative to the worktree root or run from `science/`; none `cd` to an absolute path; the Python-free check is fail-closed against `git merge-base main HEAD`.
