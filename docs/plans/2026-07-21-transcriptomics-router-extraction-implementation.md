# Transcriptomics Hub Extraction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `skills/bio/transcriptomics/SKILL.md` from a route-and-teach hub into a pure navigation router, extracting its cross-cutting teaching into two typed leaves (`cohort-qa.md`, `data-integration.md`), retargeting the three modality leaves that cite it, and deriving the Halt-On lint requirement from archetype instead of a drift-prone path allowlist.

**Architecture:** The hub's universal QA content becomes a `measurement-qa` leaf (`transcriptomics-cohort-qa`); its cross-platform aggregation decision becomes an `analysis-discipline` leaf (`transcriptomics-data-integration`); the `SKILL.md` becomes a pure router mirroring the slice-1 `statistics/SKILL.md`. The modality leaves keep their platform-specific realizations and gain one-line cross-refs up to the integration leaf. A lint change makes the Halt-On requirement archetype-derived (closing two pre-existing gaps). Both doctrine files are reconciled to "two hubs remain" and the codex mirror is regenerated.

**Tech Stack:** Python `science_tool` CLI (skills linter, codex mirror generator), pytest / ruff / pyright, Markdown skill files, `scripts/generate_codex_skills.py`.

**Design doc:** [`2026-07-21-transcriptomics-router-extraction-design.md`](./2026-07-21-transcriptomics-router-extraction-design.md) — the authoritative source for content mapping, slot contracts, and the reference-retargeting inventory.

## Global Constraints

Every task's requirements implicitly include this section.

- **No AI-attribution trailers/footers** on commits (no `Co-Authored-By`, no "Generated with Claude Code").
- **Run all tooling from `science/`** (there is no root `pyproject.toml`): tests `uv run --frozen pytest`; lint `uv run ruff check`; types `uv run pyright`; **skills lint `uv run --frozen science skills lint --root ../skills`**. A task is not green until `skills lint` exits 0 over the whole `../skills` tree.
- **Leaf filenames carry NO subject prefix** — `cohort-qa.md`, `data-integration.md` (matching `bulk-rnaseq-qa.md`). The `transcriptomics-` prefix lives ONLY in the `name:` frontmatter value.
- **Every leaf declares exactly one recognized `archetype:`; routers and `INDEX.md` carry none** (the linter enforces both directions).
- **The two new leaves' `## Companion Skills` use backticked inline-code paths** (`` - `./SKILL.md` — … ``), the archetype-template style — NOT `[label](path)` markdown links. This is deliberate: the two leaves cross-reference each other, and backticked paths are not link-validated, so each leaf lints clean regardless of which is created first (avoids a mutual-forward-ref that would be RED by construction). The archetype templates (`skills/meta/templates/{measurement-qa,analysis-discipline}.md`) already show Companion Skills in this backticked form.
- **Slot fidelity:** Leaf A carries the `measurement-qa` sections **in template order and with the template's exact `##` headings**; Leaf B carries the `analysis-discipline` sections likewise. The router carries the `router.md` template's sections. No archetype's required section may be dropped or renamed.
- **Axis-safe QA metric (Leaf A):** the leaf must **detect matrix orientation first** (samples vs genes on which axis) and must not assume AnnData obs-as-rows. The sample-count metric compares `n_unique(sample_id)` to the length of the **detected sample/cell axis**. The universal operation is the **primary expression matrix** scale/content check; AnnData `.X`/`.raw`/`.layers` is one realization and the inspection code block is explicitly conditional on AnnData input (a tabular genes×samples deposit has no `.X`).
- **Integration content (Leaf B):** strategy 1 is **within-cohort** (run per dataset/cohort — cohorts sharing a platform still carry cohort-specific artifacts), never "within-platform". The **identifiability gate**: halt when the biological contrast is fully aliased with cohort/platform/batch (no adjustment recovers an unconfounded effect). The batch-adjustment methods (ComBat / RUV / SVA / mixed-effects / exclusion) are **not interchangeable** — each is stated with its assumption; the chosen strategy dictates which is admissible.
- **Modality-leaf bodies stay intact** except the single light rephrase of `bulk-rnaseq-qa.md`'s meta-analysis paragraph. The modality cross-platform *realizations* are NOT moved.
- **Do NOT retarget the router-pointing references** — `skills/bio/SKILL.md:26`, `proteomics/SKILL.md:34`, `genomics/SKILL.md:39`, `data-management/SKILL.md:15,151,185`, `INDEX.md:26`. They reference the transcriptomics area *as a navigational entry* and correctly stay on the router.
- **Doctrine agreement:** after this slice both `skill-authoring.md` and `skill-taxonomy.md` state **two hubs remain (`data-management/`, `pipelines/`)** and neither lists `statistics/` or `bio/transcriptomics/` as a current hub.
- **Never tune content or metadata to silence a check.** The archetype-derived Halt-On check must remain able to fail — Task 1 proves it does.
- Use `~/d/` (not `/home/keith/d/` or `/mnt/ssd/Dropbox/`) in any doc/code path text.

---

### Task 1: Archetype-derive the Halt-On lint check

Make `check_halt_on_conditions` require `## Halt-On Conditions` for every `measurement-qa` leaf, deriving the requirement from the parsed `archetype:` frontmatter instead of the hard-coded `HALT_ON_REQUIRED` path allowlist. The allowlist has already drifted (`copy-number-sv-qa.md`, `proteomics-qa.md` are `measurement-qa` with Halt-On but absent from it); deriving from archetype closes those gaps and can never drift again. This task is independent of the leaf/router edits — do it first so the enforcement gate exists before the new leaf lands.

**Files:**
- Modify: `science/src/science_tool/skills_lint/lint.py` (delete `HALT_ON_REQUIRED` at lines 71–81; rewrite `check_halt_on_conditions` at lines 135–143; update its call site at line 234)
- Modify: `science/tests/skills_lint/test_lint.py` (replace the two Halt-On tests at lines 70–85; add one)
- Modify: `science/tests/skills_lint/fixtures/good.md`, `good-with-companion.md`, `good-deep-reference.md` (add `## Halt-On Conditions` — see Step 1 rationale)

**Interfaces:**
- Produces: `check_halt_on_conditions(path: Path) -> list[SkillIssue]` — **signature drops the `root` parameter** (no longer needed; the archetype comes from the file's own frontmatter). Every caller must pass only `path`.
- Consumes: `leaf_frontmatter` (already imported in `lint.py` from `.sources`) → `dict | None`.

- [ ] **Step 1: Add `## Halt-On Conditions` to the three "good" measurement-qa fixtures**

`good.md`, `good-with-companion.md`, and `good-deep-reference.md` all declare `archetype: measurement-qa` but have no Halt-On section. Today they lint clean only because they are absent from `HALT_ON_REQUIRED`. Under the archetype-derived rule they would newly trip `missing-section`, breaking `test_lint_cli_against_fixtures`'s `"good*.md" not in result.output` assertions. Add the section to each (append after the existing `## Companion Skills` block — heading order is not linted, only presence). Append to **each** of the three files:

```markdown

## Halt-On Conditions

- The measurement cannot be shown trustworthy for inference.
```

- [ ] **Step 2: Rewrite the failing test first (TDD)**

In `science/tests/skills_lint/test_lint.py`, replace the two existing Halt-On tests (lines 70–85, `test_required_halt_on_leaf_with_section_returns_no_issues` and `test_required_halt_on_leaf_without_section_returns_issue`) with these three. The import of `check_halt_on_conditions` at the top of the file stays.

```python
def test_measurement_qa_leaf_with_halt_on_returns_no_issues() -> None:
    # embeddings-manifold-qa.md is archetype: measurement-qa and carries the section.
    path = FIXTURES / "ml" / "embeddings-manifold-qa.md"
    assert check_halt_on_conditions(path) == []


def test_measurement_qa_leaf_without_halt_on_returns_issue(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf.md"
    leaf.write_text(
        "---\nname: x\ndescription: d\narchetype: measurement-qa\nprovenance: internal\n---\n"
        "# X\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    issues = check_halt_on_conditions(leaf)
    assert len(issues) == 1
    assert issues[0].kind == "missing-section"
    assert issues[0].detail == "Halt-On Conditions"


def test_non_measurement_qa_leaf_without_halt_on_is_exempt(tmp_path: Path) -> None:
    # The check must NOT over-fire: a non-measurement-qa leaf needs no Halt-On section.
    leaf = tmp_path / "leaf.md"
    leaf.write_text(
        "---\nname: x\ndescription: d\narchetype: analysis-discipline\nprovenance: internal\n---\n"
        "# X\n## Companion Skills\n- none\n",
        encoding="utf-8",
    )
    assert check_halt_on_conditions(leaf) == []
```

- [ ] **Step 3: Run the new tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -k halt -v`
Expected: FAIL — the current `check_halt_on_conditions(path, root)` signature rejects the single-argument calls (TypeError), and the current allowlist logic ignores archetype.

- [ ] **Step 4: Delete `HALT_ON_REQUIRED` and rewrite the check**

In `science/src/science_tool/skills_lint/lint.py`, delete the entire `HALT_ON_REQUIRED = { … }` block (lines 71–81). Replace `check_halt_on_conditions` (lines 135–143) with:

```python
def check_halt_on_conditions(path: Path) -> list[SkillIssue]:
    frontmatter = leaf_frontmatter(path)
    if frontmatter is None or frontmatter.get("archetype") != "measurement-qa":
        return []
    text = path.read_text(encoding="utf-8")
    if not re.search(r"^## Halt-On Conditions$", text, re.MULTILINE):
        return [SkillIssue(path, "missing-section", detail="Halt-On Conditions")]
    return []
```

Then update the call site in `check_skills` (line 234) from `check_halt_on_conditions(path, root)` to:

```python
        issues.extend(_relative_issues(check_halt_on_conditions(path), root))
```

- [ ] **Step 5: Run the Halt-On tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -k halt -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Run the full lint test module, ruff, pyright, and the whole-tree skills lint**

Run: `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -q && uv run ruff check && uv run pyright && uv run --frozen science skills lint --root ../skills`
Expected: all pass; `skills lint` exits 0. (`uv run ruff check` — no path — lints the whole configured `science` package, covering both the modified `lint.py` and `test_lint.py`. Confirmed precondition: every current `archetype: measurement-qa` leaf in `../skills` already carries `## Halt-On Conditions`, so no shipped leaf is newly flagged.)

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/skills_lint/lint.py science/tests/skills_lint/test_lint.py science/tests/skills_lint/fixtures/good.md science/tests/skills_lint/fixtures/good-with-companion.md science/tests/skills_lint/fixtures/good-deep-reference.md
git commit -m "feat(skills-lint): derive the Halt-On requirement from archetype==measurement-qa

Replace the hard-coded HALT_ON_REQUIRED path allowlist (which had drifted:
copy-number-sv-qa and proteomics-qa are measurement-qa with Halt-On but were
absent from it) with an archetype-derived check. Every measurement-qa leaf now
requires ## Halt-On Conditions; the check no longer needs the skills root and
never drifts again. Add Halt-On to the three good measurement-qa fixtures so
they stay clean under the new rule; the check-can-fail test proves a
measurement-qa leaf missing the section is flagged and a non-measurement-qa
leaf is exempt."
```

---

### Task 2: Leaf A — `transcriptomics-cohort-qa` (measurement-qa)

Create the single-cohort ingest/QA leaf from the hub's universal pre-flight checklist (items 1–4, 6, and the factual half of item 5) and its three preprocessing idioms, reshaped into the `measurement-qa` slot contract. Add its `INDEX.md` machine entry in the same task so index coverage stays green.

**Files:**
- Create: `skills/bio/transcriptomics/cohort-qa.md`
- Modify: `skills/INDEX.md` (add one machine entry, alphabetically after `transcriptomics-bulk-rnaseq-qa`)

**Interfaces:**
- Produces: file `cohort-qa.md`, `name: transcriptomics-cohort-qa`, `archetype: measurement-qa`. Referenced later by the router (Task 4, backticked), the modality leaves (Task 5, markdown links), and Leaf B (Task 3, backticked companion).
- Consumes: hub content from `skills/bio/transcriptomics/SKILL.md` (checklist items 1–4/5-factual/6 at lines 31–73; idioms at lines 75–129).

- [ ] **Step 1: Write the leaf (transcribe the complete file below verbatim)**

Create `skills/bio/transcriptomics/cohort-qa.md` with **exactly** this content — it is final, not a skeleton. Transcribe it as-is (the fenced block is the file body; do not include the outer ` ```markdown ` fence):

```markdown
---
name: transcriptomics-cohort-qa
description: Use when ingesting or QA-reviewing a single transcriptomic cohort (bulk RNA-seq, microarray, or scRNA-seq; GEO, ArrayExpress, MMRF, HCA, recount, ARCHS4) before it enters analysis.
archetype: measurement-qa
provenance: internal
---

# Transcriptomic Cohort QA

Answers: is this single expression cohort trustworthy for downstream inference before it enters analysis?

## Sources & ingestion/construction

Public deposits — GEO, ArrayExpress, MMRF CoMMpass, HCA, recount3, ARCHS4 —
each carry idiosyncrasies: undocumented normalisation, mislabelled samples,
silent-failure modes that look plausible until they invalidate inference. The
primary expression matrix arrives either as an AnnData object (inspect `.X`,
and check `.raw` and `.layers["counts"]`) or as a tabular genes×samples deposit
(CSV/TSV, which has no `.X`). Every deposit's README describes what *should* be
there; this leaf is about verifying what *is* there before the cohort enters
analysis.

## Pre-flight checklist

Answer all of these in writing before running any downstream analysis:

- [ ] **Primary expression matrix — what is it actually?** Raw counts,
      log-normalised, batch-corrected, z-scored, or residualised? **Detect
      matrix orientation first** (which axis is samples vs genes — `obs` rows
      vs `var` rows for AnnData); a surprising fraction of deposits silently
      change the matrix contents between revisions. For AnnData input, inspect
      the matrix directly (a tabular genes×samples deposit has no `.X` — inspect
      the loaded array instead):
      ```python
      # AnnData only.
      sub = a[:200].X.toarray() if sparse.issparse(a.X) else a.X[:200]
      print(f"min={sub.min():.3f}, max={sub.max():.3f}, integer-like={(sub == sub.astype(int)).all()}")
      ```
      Integer + max in thousands → raw counts; float + max ≤ ~15 →
      log-normalised; float symmetric around 0 → z-scored/residualised; float +
      max in thousands → linear normalised (TPM-like). Many AnnData deposits
      keep transformed values in `.X` and raw counts in `.layers["counts"]` or
      `.raw` — check both.
- [ ] **Gene-identifier axis.** Symbols (HGNC for human), Ensembl IDs, RefSeq,
      probe IDs, or "gene names" Excel has corrupted (`SEPT1` → `1-Sep`)?
      Resolve to a canonical ID layer at ingest. Symbol churn is real —
      `MARCH1` is now `MARCHF1`.
- [ ] **Sample identifier.** Patient, cell, library, technical replicate, or
      run? Collapse or exclude duplicates. GEO `geo_accession` is
      unique-per-sample; `Sample_title` is not. MMRF samples can have multiple
      time points per patient.
- [ ] **Cohort definition.** Diseased vs healthy, treated vs untreated, primary
      vs metastasis? Confirm the stage / treatment / disease columns are
      populated for every sample you intend to use.
- [ ] **Normalization state recorded.** Record and verify what normalisation the
      depositor applied. Whether that normalisation is *compatible* with a
      particular meta-analysis is a cross-cohort decision — see
      `./data-integration.md`.
- [ ] **Single-cohort batch PCA.** Quick PCA coloured by batch, run, and
      biological group. If batch separates more strongly than biology, you have
      a confound; the cross-experiment remedy is a `./data-integration.md`
      decision, not a single-cohort one.

## QA metrics

Detect matrix orientation before computing any per-axis metric — never assume
`.X.shape[0]` is samples.

| Metric | Passing range | Meaning of failure |
|---|---|---|
| `n_unique(sample_id)` vs length of the detected sample/cell axis | equal | non-unique sample IDs → hidden replicates/duplicates that bias per-sample statistics |
| Integer-like fraction of the primary expression matrix (200-row sample) | ≈1.0 for claimed raw counts; ≈0 for claimed transformed | matrix scale contradicts the README → wrong transformation assumed downstream |
| Per-group fraction of samples dropped by a QC filter | comparable across stratification groups | a group over-represented in the dropped fraction → filter is confounded with the question |

## Common failure modes

- **README says vs matrix is.** Documentation describes "what should be there,"
  not "what is there." Treat it as a hypothesis: if the README says counts are
  integer, sample 200 rows and check; if it says samples are unique, check
  `n_unique` against the detected sample axis; if it says cells are QC-filtered,
  check the per-cell metric distributions yourself.
- **Unlogged preprocessing decisions.** Filter thresholds, transformation
  choices, batch handling, and sample exclusions left without a provenance
  sidecar cannot be reconstructed or audited later.
- **Filters that don't commute with the question.** Detection-rate-per-gene
  filters drop genes low in some groups but high in others (removing biology,
  e.g. immune markers in a non-immune-enriched cohort); `mean ± 3 SD` sample QC
  drops more samples from groups whose mean is shifted (treatment-confounded
  filtering); doublet calling on aggregated batches masks batch-specific rates.
  When in doubt, filter once on the full cohort, log the mask, and check that no
  group is over-represented in the dropped fraction.

## Halt-On Conditions

- The contents of the primary expression matrix (or the applicable AnnData
  layer) cannot be determined from the data plus metadata.
- Sample identifiers are non-unique and no collapse/exclusion rule is defined.
- A QC filter drops a stratification group asymmetrically and no filter mask was
  logged.

## Minimum output package

    cohort-qa/
      summary.md          # what was checked, which Halt-On Conditions were evaluated, verdict
      cohort_audit.json   # raw + after-each-filter sample/cell/patient counts; patients
                          # dropped with reasons; gene-universe size at QC pass;
                          # normalisation status; batch-metadata schema

## Success test

Does the produced QA package contain the named files, and does the summary state which Halt-On Conditions were evaluated?

## Companion Skills

- `./SKILL.md` — the transcriptomics router.
- `./data-integration.md` — the multi-cohort integration decision that consumes this QA.
- `./bulk-rnaseq-qa.md`, `./microarray-qa.md`, `./scrna-qa.md` — platform-specific QA.
- `../../data-management/frictionless.md` — Data-Package substrate for the cohort_audit sidecar.
```

- [ ] **Step 2: Add the INDEX machine entry**

In `skills/INDEX.md`, insert this line immediately after the `transcriptomics-bulk-rnaseq-qa` entry (line 27), keeping the `transcriptomics-*` block alphabetical:

```markdown
- `transcriptomics-cohort-qa`: `skills/bio/transcriptomics/cohort-qa.md`
```

- [ ] **Step 3: Verify the leaf lints clean and the slot contract is complete**

Run: `cd science && uv run --frozen science skills lint --root ../skills`
Expected: exit 0 (no `missing-section`, `missing-archetype`, `missing-provenance`, `broken-relative-link`, or `missing-index-entry` for `cohort-qa.md`).

Then run these **fail-closed** guards (each `exit 1`s on violation) — confirm all eight `measurement-qa` headings are present and no angle-bracket placeholder survived transcription:

```bash
n=$(rg -c '^## (Sources & ingestion/construction|Pre-flight checklist|QA metrics|Common failure modes|Halt-On Conditions|Minimum output package|Success test|Companion Skills)$' skills/bio/transcriptomics/cohort-qa.md)
[ "$n" = "8" ] || { echo "EXPECTED 8 measurement-qa headings, got ${n:-0}"; exit 1; }
if rg -n '<[^>]+>' skills/bio/transcriptomics/cohort-qa.md; then echo "ANGLE-BRACKET PLACEHOLDER LEFT"; exit 1; fi
echo "slots complete, no placeholders"
```
Expected: `slots complete, no placeholders` (and a zero exit). The `<[^>]+>` pattern catches any `<…>` regardless of first character; the guard `exit 1`s if one is found. (`rg -c` prints the count of matching lines; the authored body contains no `<…>` sequences, so the placeholder guard finds nothing.)

- [ ] **Step 4: Commit**

```bash
git add skills/bio/transcriptomics/cohort-qa.md skills/INDEX.md
git commit -m "feat(skills): add transcriptomics-cohort-qa measurement-qa leaf

Extract the hub's universal pre-flight checklist (items 1-4, 6, and the factual
half of item 5) and its three preprocessing idioms into a measurement-qa leaf,
reshaped into the archetype slot contract with an axis-safe sample-count metric
and primary-expression-matrix phrasing. Index it."
```

---

### Task 3: Leaf B — `transcriptomics-data-integration` (analysis-discipline)

Create the multi-cohort integration-decision leaf from the hub's "Cross-platform aggregation: the fundamental tension" section plus the aggregation-dependent half of item 5, reshaped into the `analysis-discipline` slot contract with an explicit identifiability gate. Add its `INDEX.md` entry in the same task.

**Files:**
- Create: `skills/bio/transcriptomics/data-integration.md`
- Modify: `skills/INDEX.md` (add one machine entry, alphabetically before `transcriptomics-microarray-qa`)

**Interfaces:**
- Produces: file `data-integration.md`, `name: transcriptomics-data-integration`, `archetype: analysis-discipline`. Referenced by the router (Task 4), Leaf A (Task 2, backticked), and the modality leaves (Task 5).
- Consumes: hub content at `skills/bio/transcriptomics/SKILL.md` lines 131–151 (3 strategies) and item 5 at lines 65–69 / boundary note in the design.

- [ ] **Step 1: Write the leaf (transcribe the complete file below verbatim)**

Create `skills/bio/transcriptomics/data-integration.md` with **exactly** this content — it is final, not a skeleton. Transcribe it as-is (do not include the outer ` ```markdown ` fence):

```markdown
---
name: transcriptomics-data-integration
description: Use when integrating or aggregating multiple heterogeneous transcriptomic cohorts for meta-analysis, before designing per-cohort preprocessing — committing to a cross-cohort strategy and handling experiment-level technical variation.
archetype: analysis-discipline
provenance: internal
---

# Transcriptomic Data Integration

Answers: regardless of the pooling method, what strategy and identifiability check must be committed before multiple transcriptomic cohorts may be integrated and interpreted?

## Triggering condition

Before designing per-cohort preprocessing for any analysis that pools ≥2
cohorts or platforms — microarray + RNA-seq, multiple GEO series, or bulk +
single-cell. The strategy choice cascades into preprocessing, so it must be
committed first, not reverse-engineered afterward.

## Required reasoning / check / precommitment

Before any per-cohort preprocessing, commit in writing:

- **(a) the aggregation strategy** — one of the three in the decision rule below.
- **(b) the identifiability check** — is the biological contrast fully aliased
  with cohort, platform, or batch? For the contrast of interest, list which
  cohorts/platforms contribute each level.
- **(c) the technical-artifact adjustment and its assumptions** — which of
  ComBat / RUV / SVA / mixed-effects / exclusion, and whether the data actually
  satisfy that method's prerequisites.

## Decision rule or reasoning criteria

**Aggregation strategies (not interchangeable):**

1. **Within-cohort association testing → aggregate test statistics.** Run
   DESeq2 / limma / logistic / Cox **per dataset/cohort** — cohorts sharing a
   platform still carry cohort-specific technical artifacts, so pool at the
   statistic level, not the sample level. Aggregate p-values (Stouffer's,
   Fisher's) or z-scored effects (random-effects metafor). Z-score per-cohort
   effects before pooling when scales differ.
2. **Common-reference normalisation** (gene-set rank, percentile, z-score)
   before pooling. Enables direct pooling but loses platform-specific magnitude.
3. **Hierarchical models with platform random effects.** The most principled;
   compute- and assumption-heavy. Often worth it for high-stakes confirmatory
   inference.

**Batch-adjustment branches (each with its prerequisite — the chosen strategy
dictates which is admissible):**

- **ComBat** — needs known batch labels; assumes batch is not confounded with
  biology.
- **RUV** — needs suitable negative-control genes or replicate samples.
- **SVA** — estimates latent factors; assumes they are separable from the
  biological contrast.
- **Mixed-effects** — platform/cohort as a random effect.
- **Exclusion** — drop the confounded cohort when no adjustment is admissible.

## Outcomes (pass / fail / indeterminate, or branch/threshold)

- **Strategy committed** → proceed to per-cohort preprocessing under it.
- **Non-identifiable** → halt (see below); no adjustment recovers an
  unconfounded effect.
- **Admissible but assumption-fragile** → proceed, reporting the limitation
  explicitly.

## Halt / escalation

- **Halt** when cohort/platform/batch is completely aliased with the biological
  contrast — the design is non-identifiable, and no ComBat/RUV/SVA adjustment
  can recover an unconfounded effect (adjustment removes the confound *and* the
  signal together).
- **Escalate** when the only admissible strategy rests on assumptions the data
  cannot support — no valid negative-control genes for RUV, no replicates, or
  latent factors not separable from the contrast.

## Required evidence & artifacts

- The committed aggregation strategy, recorded in the pre-registration before
  preprocessing.
- The identifiability assessment (which cohorts/platforms contribute each
  contrast level).
- The chosen adjustment method and its explicit assumption check.

## Permitted reporting language

- An effect pooled under a fragile-assumption or non-recoverable-confound path
  must be reported **with that limitation**, not as a clean cross-cohort effect.
- "Harmonised" describes a normalisation step; it is **not** a synonym for
  "confound-free." Do not imply the confound was removed unless the
  identifiability check supports it.

## Success test

Was the required reasoning/precommitment carried out before interpretation, and does the conclusion follow from it — mechanically where the identifiability gate applies, by the stated criteria otherwise?

## Companion Skills

- `./SKILL.md` — the transcriptomics router.
- `./cohort-qa.md` — the per-cohort QA this decision consumes.
- `./bulk-rnaseq-qa.md`, `./microarray-qa.md`, `./scrna-qa.md` — modality realizations of the chosen strategy.
- `../../statistics/SKILL.md` — the actual aggregation / hierarchical modeling.
- `../../study-design/SKILL.md` — pre-registering the committed strategy.
```

- [ ] **Step 2: Add the INDEX machine entry**

In `skills/INDEX.md`, insert immediately after the `transcriptomics-cohort-qa` entry (added in Task 2) and before `transcriptomics-microarray-qa`:

```markdown
- `transcriptomics-data-integration`: `skills/bio/transcriptomics/data-integration.md`
```

- [ ] **Step 3: Verify the leaf lints clean and the slot contract is complete**

Run: `cd science && uv run --frozen science skills lint --root ../skills`
Expected: exit 0. `data-integration.md` is `analysis-discipline`, so the archetype-derived Halt-On check correctly does **not** require a `## Halt-On Conditions` heading (its `## Halt / escalation` slot is a template convention, not a lint-enforced heading).

Then run these **fail-closed** guards (each `exit 1`s on violation) — confirm the nine `analysis-discipline` headings, the within-cohort phrasing, and no surviving placeholder:

```bash
n=$(rg -c '^## (Triggering condition|Required reasoning / check / precommitment|Decision rule or reasoning criteria|Outcomes \(pass / fail / indeterminate, or branch/threshold\)|Halt / escalation|Required evidence & artifacts|Permitted reporting language|Success test|Companion Skills)$' skills/bio/transcriptomics/data-integration.md)
[ "$n" = "9" ] || { echo "EXPECTED 9 analysis-discipline headings, got ${n:-0}"; exit 1; }
if rg -n 'within-platform' skills/bio/transcriptomics/data-integration.md; then echo "WRONG: within-platform (strategy 1 must be within-cohort)"; exit 1; fi
if rg -n '<[^>]+>' skills/bio/transcriptomics/data-integration.md; then echo "ANGLE-BRACKET PLACEHOLDER LEFT"; exit 1; fi
echo "slots complete, within-cohort, no placeholders"
```
Expected: `slots complete, within-cohort, no placeholders` (zero exit).

- [ ] **Step 4: Commit**

```bash
git add skills/bio/transcriptomics/data-integration.md skills/INDEX.md
git commit -m "feat(skills): add transcriptomics-data-integration analysis-discipline leaf

Extract the hub's cross-platform aggregation taxonomy and the aggregation-
dependent half of pre-flight item 5 into an analysis-discipline leaf: within-
cohort strategy taxonomy, an explicit identifiability gate (halt when the
contrast is fully aliased with cohort/platform/batch), and non-interchangeable
batch-adjustment branches (ComBat/RUV/SVA/mixed/exclusion), each with its
assumption. Index it."
```

---

### Task 4: Rewrite `transcriptomics/SKILL.md` as a pure router

Replace the hub body with a pure navigation router mirroring the slice-1 `statistics/SKILL.md`: routing trigger, scope boundary, a 5-row Leaves table, explicit compose order, parent/neighbors, success test, companions. No methodology.

**Files:**
- Modify: `skills/bio/transcriptomics/SKILL.md` (full-body replacement)

**Interfaces:**
- Consumes: the two leaves from Tasks 2–3 and the three existing modality leaves (referenced as backticked paths — not link-validated).
- Produces: a router with no `archetype:`, a `## Companion Skills` section (lint-required), and no teaching sections.

- [ ] **Step 1: Replace the file contents**

Overwrite `skills/bio/transcriptomics/SKILL.md` with exactly:

```markdown
---
name: transcriptomics
description: Use when ingesting, QA-reviewing, or integrating transcriptomic datasets — bulk RNA-seq, microarray, or scRNA-seq cohorts (GEO, ArrayExpress, MMRF, HCA, recount, ARCHS4), especially before meta-analysis. Routes to the leaves below.
provenance: internal
---

# Transcriptomics — Expression-Data Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when a transcriptomic dataset is being ingested, QA'd, or
integrated for meta-analysis — before loading any leaf.

## Scope boundary

Covers expression-cohort ingest QA and multi-cohort integration across bulk
RNA-seq, microarray, and scRNA-seq. Excludes the statistical modeling itself
(→ `../../statistics/SKILL.md`) and generic data conventions
(→ `../../data-management/SKILL.md`).

## Leaves

| Leaf | Load when |
|---|---|
| `cohort-qa.md` | QA'ing any newly-acquired transcriptomic cohort (cross-modality checklist + inspection idioms) |
| `data-integration.md` | integrating/aggregating multiple cohorts for meta-analysis (strategy choice + batch adjustment) |
| `bulk-rnaseq-qa.md` | bulk RNA-seq cohort specifics |
| `microarray-qa.md` | microarray cohort specifics |
| `scrna-qa.md` | single-cell RNA-seq cohort specifics |

## Decision / compose order

- **Single-cohort work** → load `cohort-qa.md` **plus** the applicable modality
  leaf (`bulk-rnaseq-qa.md` / `microarray-qa.md` / `scrna-qa.md`).
- **Multi-cohort / meta-analysis work** → **additionally** load
  `data-integration.md`, and consult it **before** per-cohort preprocessing
  decisions are made — its strategy choice cascades into preprocessing.

## Parent & neighbors

- Parent index: `../../INDEX.md`
- Parent router: `../SKILL.md`
- Neighboring routers: `../genomics/SKILL.md`, `../proteomics/SKILL.md`

## Success test

A representative transcriptomic task routes to the correct leaf (or the correct
compose order when leaves combine) with no methodology read from this router.

## Companion Skills

- `../../statistics/SKILL.md` — statistical modeling that consumes QA'd cohorts.
- `../../data-management/SKILL.md` — generic data conventions.
- `../../data-management/frictionless.md` — Data-Package substrate for the cohort_audit sidecar.
- `../genomics/SKILL.md` — mutation cohorts often paired with expression cohorts.
- `../../literature/SKILL.md` — field-consensus context for QA thresholds.
```

- [ ] **Step 2: Verify the router carries no methodology and lints clean**

```bash
rg -n '^## (Universal pre-flight|Idiom:|Cross-platform aggregation|Three modalities|When to invoke)' skills/bio/transcriptomics/SKILL.md && echo "METHODOLOGY LEFT" || echo "router is clean"
rg -n '^archetype:' skills/bio/transcriptomics/SKILL.md && echo "ROUTER HAS ARCHETYPE" || echo "no archetype OK"
cd science && uv run --frozen science skills lint --root ../skills
```
Expected: "router is clean"; "no archetype OK"; `skills lint` exit 0.

- [ ] **Step 3: Commit**

```bash
git add skills/bio/transcriptomics/SKILL.md
git commit -m "refactor(skills): make transcriptomics/SKILL.md a pure router

Replace the route-and-teach hub with a pure navigation router mirroring the
slice-1 statistics router: routing trigger, scope boundary, 5-row Leaves table,
explicit single-cohort vs multi-cohort compose order, parent/neighbors. All
teaching content now lives in the cohort-qa and data-integration leaves."
```

---

### Task 5: Retarget the three modality leaves

Point the modality leaves' moved-content references at the new leaves, and add a one-line cross-ref from each modality's cross-platform section up to `data-integration.md`. Only these three files change; do NOT touch the router-pointing references listed in Global Constraints, and do NOT move the modality realizations.

**Files:**
- Modify: `skills/bio/transcriptomics/bulk-rnaseq-qa.md` (lines 11–12, 97–98, 106+, 165)
- Modify: `skills/bio/transcriptomics/microarray-qa.md` (line 15, section at 91, Companion at 175)
- Modify: `skills/bio/transcriptomics/scrna-qa.md` (lines 11–12, section at 183, Companion at 255)

**Interfaces:**
- Consumes: `cohort-qa.md` and `data-integration.md` (created in Tasks 2–3) — these markdown-link targets now exist, so links resolve.

- [ ] **Step 1: Retarget `bulk-rnaseq-qa.md`**

Edit 1 (intro, ~line 11–12): replace
`For platform-general conventions see\n[`SKILL.md`](./SKILL.md).`
→ `For platform-general conventions see\n[`cohort-qa.md`](./cohort-qa.md).`

Edit 2 (idiom citation, ~line 97–98): replace
`in cohorts with mixed cell-type composition (see SKILL.md "filter\nsteps must commute with the question").`
→ `in cohorts with mixed cell-type composition (see\n[`cohort-qa.md`](./cohort-qa.md), "filter steps must commute with the question").`

Edit 3 (meta-analysis paragraph, ~line 106 — the single permitted body rephrase): replace the lead-in line
`For meta-analysis across cohorts:`
→ `For meta-analysis across cohorts, the integration-strategy decision (and its identifiability gate) lives in [`data-integration.md`](./data-integration.md); the bulk-specific realizations of those strategies are:`
(Keep the two bullets that follow unchanged.)

Edit 4 (Companion, line 165): replace
`- [`SKILL.md`](SKILL.md) - expression-data hub conventions for cross-platform cohort QA.`
→
```markdown
- [`cohort-qa.md`](cohort-qa.md) - platform-general cohort QA (checklist + inspection idioms).
- [`data-integration.md`](data-integration.md) - cross-cohort aggregation strategy and batch adjustment.
```

- [ ] **Step 2: Retarget `microarray-qa.md`**

Edit 1 (line 15): replace `For platform-general conventions see [`SKILL.md`](./SKILL.md).`
→ `For platform-general conventions see [`cohort-qa.md`](./cohort-qa.md).`

Edit 2 (cross-platform section at line 91): immediately after the heading
`## Cross-platform meta-analysis (the hard problem)`
insert a new paragraph:
```markdown

The cross-cohort strategy decision (and its identifiability gate) lives in
[`data-integration.md`](./data-integration.md); this section is the
microarray-specific realization.
```

Edit 3 (Companion, line 175): replace
`- [`SKILL.md`](SKILL.md) - expression-data hub conventions for cross-platform cohort QA.`
→
```markdown
- [`cohort-qa.md`](cohort-qa.md) - platform-general cohort QA (checklist + inspection idioms).
- [`data-integration.md`](data-integration.md) - cross-cohort aggregation strategy and batch adjustment.
```
(Leave the existing `bulk-rnaseq-qa.md` companion line beneath it intact.)

- [ ] **Step 3: Retarget `scrna-qa.md`**

Edit 1 (line 11–12): replace `For platform-general QA conventions see\n[`SKILL.md`](./SKILL.md).`
→ `For platform-general QA conventions see\n[`cohort-qa.md`](./cohort-qa.md).`

Edit 2 (cross-platform section at line 183): immediately after the heading
`## Pseudobulk for cross-platform aggregation`
insert a new paragraph:
```markdown

The cross-cohort strategy decision (and its identifiability gate) lives in
[`data-integration.md`](./data-integration.md); pseudobulk here is the
single-cell realization of that strategy.
```

Edit 3 (Companion, line 255): replace
`- [`SKILL.md`](SKILL.md) - expression-data hub conventions for cross-platform cohort QA.`
→
```markdown
- [`cohort-qa.md`](cohort-qa.md) - platform-general cohort QA (checklist + inspection idioms).
- [`data-integration.md`](data-integration.md) - cross-cohort aggregation strategy and batch adjustment.
```

- [ ] **Step 4: Verify no stale `SKILL.md` teaching links remain and links resolve**

```bash
rg -n '\]\(\.?/?SKILL\.md\)' skills/bio/transcriptomics/bulk-rnaseq-qa.md skills/bio/transcriptomics/microarray-qa.md skills/bio/transcriptomics/scrna-qa.md && echo "STALE SKILL.md LINK" || echo "no stale SKILL.md links"
rg -n 'see SKILL.md' skills/bio/transcriptomics/*.md && echo "STALE PROSE REF" || echo "no stale prose refs"
cd science && uv run --frozen science skills lint --root ../skills
```
Expected: "no stale SKILL.md links"; "no stale prose refs"; `skills lint` exit 0 (the new `[](cohort-qa.md)` / `[](data-integration.md)` links resolve because Tasks 2–3 created those files).

- [ ] **Step 5: Commit**

```bash
git add skills/bio/transcriptomics/bulk-rnaseq-qa.md skills/bio/transcriptomics/microarray-qa.md skills/bio/transcriptomics/scrna-qa.md
git commit -m "docs(skills): retarget modality-leaf references to the new transcriptomics leaves

Point the moved-content references (platform-general conventions, the
filter-must-commute idiom, the cross-platform-QA companion lines) at cohort-qa.md,
and add a one-line cross-ref from each modality's cross-platform section up to
data-integration.md as the strategy it realizes. Lightly rephrase bulk's
meta-analysis paragraph to defer strategy authority to data-integration.md.
The modality realizations themselves are unchanged."
```

---

### Task 6: Reconcile both doctrine files and regenerate the codex mirror

Update the two doctrine files to "two hubs remain" (fixing the slice-1 miss in `skill-taxonomy.md` and recording this slice), then regenerate the codex mirror because both files are resources of the `skill-development` companion.

**Files:**
- Modify: `skills/meta/skill-authoring.md` (the hub-count sentence at line 44)
- Modify: `skills/meta/skill-taxonomy.md` (the stale four-hub sentence at line 112)
- Regenerate: `codex-skills/science-skill-development/skill-authoring.md`, `codex-skills/science-skill-development/skill-taxonomy.md` (via the generator; do not hand-edit)

**Interfaces:**
- Consumes: `scripts/generate_codex_skills.py`; the committed-mirror test `science/tests/test_codex_skills.py::test_committed_codex_skills_match_fresh_generation`.

- [ ] **Step 1: Edit `skill-authoring.md`**

In the "Router invariant and the hub anti-pattern" paragraph (line 44): change `3 of 14 current \`SKILL.md\` files are still **hubs** (route + teach) — \`data-management/SKILL.md\`, \`bio/transcriptomics/SKILL.md\`, and \`pipelines/SKILL.md\`.` to `2 of 14 current \`SKILL.md\` files are still **hubs** (route + teach) — \`data-management/SKILL.md\` and \`pipelines/SKILL.md\`.`

Then, immediately after the existing sentence `\`statistics/SKILL.md\` was reconciled to a router on 2026-07-21 (…their theses already living in those leaves).`, insert:

```
 `bio/transcriptomics/SKILL.md` was extracted to a router on 2026-07-21, its cross-cutting teaching moving into `transcriptomics-cohort-qa` (measurement-qa) and `transcriptomics-data-integration` (analysis-discipline).
```

- [ ] **Step 2: Edit `skill-taxonomy.md`**

Replace the stale sentence at line 112:
`Four hubs remain (\`data-management/\`, \`bio/transcriptomics/\`, \`pipelines/\`, \`statistics/\`), pending phase-4 extraction.`
→
`Two hubs remain (\`data-management/\`, \`pipelines/\`), pending phase-4 extraction; \`statistics/\` was reconciled to a router on 2026-07-21 (slice 1) and \`bio/transcriptomics/\` was extracted the same day into \`transcriptomics-cohort-qa\` and \`transcriptomics-data-integration\` (slice 2).`

- [ ] **Step 3: Confirm the mirror is now stale (the check can see the change)**

Run: `cd science && uv run --frozen pytest tests/test_codex_skills.py::test_committed_codex_skills_match_fresh_generation -q`
Expected: FAIL — the committed `codex-skills/science-skill-development/{skill-authoring.md,skill-taxonomy.md}` no longer match fresh generation.

- [ ] **Step 4: Regenerate the mirror**

Run: `cd science && uv run --frozen python ../scripts/generate_codex_skills.py`

Then assert (**fail-closed**) that the changed-file set under `codex-skills/` is **exactly** the two doctrine resources — no more, no fewer. This is what proves no additional mirrored leaf was created (a mirrored `bio/transcriptomics/*.md` would show up here as an extra path; a content-grep for the leaf *names* cannot prove this, because Task 6 deliberately writes those names into the two doctrine resources). Run from the worktree root (you are already in it — no absolute path):

```bash
changed=$(git status --porcelain codex-skills/ | sed 's/^...//' | sort)
expected=$(printf '%s\n' \
  codex-skills/science-skill-development/skill-authoring.md \
  codex-skills/science-skill-development/skill-taxonomy.md | sort)
[ "$changed" = "$expected" ] || { echo "UNEXPECTED codex-skills change set:"; echo "$changed"; exit 1; }
echo "exactly the two doctrine mirror files changed — no extra mirrored leaf"
```
Expected: `exactly the two doctrine mirror files changed — no extra mirrored leaf` (zero exit). If the set differs (e.g. a `bio/` leaf was unexpectedly mirrored, or only one doctrine file regenerated), the guard `exit 1`s.

- [ ] **Step 5: Verify the whole tree is green**

Run: `cd science && uv run --frozen pytest -q && uv run ruff check && uv run pyright && uv run --frozen science skills lint --root ../skills`
Expected: full pytest passes (including `test_committed_codex_skills_match_fresh_generation`); ruff and pyright clean (Task 1 changed Python, so the final gate re-runs them); `skills lint` exit 0.

- [ ] **Step 6: Commit**

```bash
git add skills/meta/skill-authoring.md skills/meta/skill-taxonomy.md codex-skills/science-skill-development/skill-authoring.md codex-skills/science-skill-development/skill-taxonomy.md
git commit -m "docs(skills-doctrine): record transcriptomics extraction; reconcile hub count to two

skill-authoring.md and skill-taxonomy.md now agree that two hubs remain
(data-management, pipelines): statistics was reconciled to a router in slice 1
(this also fixes taxonomy's stale four-hub line that still listed statistics and
transcriptomics) and bio/transcriptomics was extracted in slice 2 into
transcriptomics-cohort-qa and transcriptomics-data-integration. Regenerate the
two skill-development codex mirror files."
```

---

## Self-Review

**Spec coverage** (design doc → task):
- Two new leaves (measurement-qa + analysis-discipline), no filename prefix → Tasks 2, 3. ✅
- Content mapping table (checklist items, idioms, aggregation taxonomy, item-5 split) → Tasks 2 (Leaf A), 3 (Leaf B). ✅
- Router rewrite (5-row table, compose order, no methodology) → Task 4. ✅
- Reference-retargeting inventory (3 modality leaves retargeted; router-pointing refs untouched; one bulk body rephrase) → Task 5 + Global Constraints. ✅
- Linter enforcement edit (archetype-derived Halt-On, delete allowlist, test update) → Task 1. ✅
- INDEX edits (two machine entries) → folded into Tasks 2, 3 (keeps index coverage green per task). ✅
- Doctrine edits (both files, two hubs) → Task 6. ✅
- Codex mirror (exactly two files, bio/ not mirrored, green gate) → Task 6. ✅
- Safety invariants (no dropped knowledge, no stale labels, router carries no methodology, archetype-slot completeness, archetype-derived Halt-On live, green gate) → verification steps in Tasks 1–6. ✅

**Placeholder scan:** The two leaf tasks now ship **complete final Markdown** to transcribe verbatim — no `<…>` skeletons, no design invention deferred to implementation time. Each leaf task additionally carries a fail-closed guard (`rg '<[^>]+>'` → `exit 1`) that catches any angle-bracket placeholder regardless of first character, as a transcription-drift net. No plan-level TODO/TBD remain.

**Type/name consistency:** `check_halt_on_conditions(path)` single-arg signature is defined in Task 1 and every caller (call site + tests) is updated in the same task. Leaf `name:` values (`transcriptomics-cohort-qa`, `transcriptomics-data-integration`) and file paths are used identically across INDEX entries (Tasks 2–3), router table (Task 4), retargeting links (Task 5), and doctrine text (Task 6).

**Ordering note:** Task 1 is independent (do first). Tasks 2–3 create the leaves + their INDEX entries so the tree stays green; the two leaves cross-reference via **backticked** companion paths (not link-validated), so neither task is RED-by-construction on the other's absence. Task 4 (router) and Task 5 (modality retargeting) both depend on the leaves existing. Task 6 is last (only it touches the codex mirror).
