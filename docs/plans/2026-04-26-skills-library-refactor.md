# Skills Library Refactor — Structural Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the `skills/` library to a uniform structural baseline — frontmatter, naming, hubs, output conventions, cross-references, broken pointers — so it can support the planned `skills/INDEX.md` + `science-plan-analysis` workflow without further rework.

**Architecture:** Twelve sequential phases, each ending in a verifying lint pass and a commit. Phase 0 builds a small `science-tool skills lint` check that becomes the "test" for documentation work. Subsequent phases use that linter to verify each structural change. Phase 11 creates the minimal index-readiness contract required by the source spec; full `science-plan-analysis` command implementation remains out of scope. Content authoring of net-new skills (causal-DAG, sample-size, meta-analysis, model-evaluation, etc.) is **out of scope** for this plan — see the Follow-up Plans section.

**Tech Stack:** Markdown skills, Python >=3.11 / `uv` / `pyright` / `ruff` / `pytest` for the linter, `science-tool` CLI extension. No code in `skills/`; this is a documentation refactor with a verification harness.

**Source spec:** `docs/specs/2026-04-26-analysis-planning-and-skill-index-design.md` (the proposed `skills/INDEX.md` workflow that motivates this cleanup).

---

## File Structure

### Created

- `science-tool/src/science_tool/skills_lint/__init__.py` — module entry point
- `science-tool/src/science_tool/skills_lint/lint.py` — lint logic (frontmatter, cross-refs, naming, companion-skills)
- `science-tool/src/science_tool/skills_lint/cli.py` — Click-based CLI registration
- `science-tool/tests/skills_lint/test_cli.py` — CLI smoke tests
- `science-tool/tests/skills_lint/test_lint.py` — unit tests for each lint rule
- `science-tool/tests/skills_lint/fixtures/` — minimal valid + invalid skill markdown fixtures
- `skills/pipelines/SKILL.md` — new pipelines hub
- `skills/data/genomics/SKILL.md` — new genomics hub
- `skills/research/proposition-schema.md` — extracted Science-project schema (claim_layer, identification_strength, etc.)
- `skills/INDEX.md` — compact analysis-planning index required by the source spec

### Renamed

- `skills/research/lab-notebook.md` → `skills/research/research-package-rendering.md`
- `skills/research/provenance.md` → `skills/research/research-package-spec.md`

### Modified

- All 18 current skill leaf/reference files missing frontmatter (frontmatter added): `data/embeddings-manifold-qa.md`, `data/functional-genomics-qa.md`, `data/protein-sequence-structure-qa.md`, `data/expression/{bulk-rnaseq-qa,microarray-qa,scrna-qa}.md`, `data/genomics/{somatic-mutation-qa,mutational-signatures-and-selection}.md`, `statistics/{bias-vs-variance-decomposition,compositional-data,power-floor-acknowledgement,prereg-amendment-vs-fresh,replicate-count-justification,sensitivity-arbitration,survival-and-hierarchical-models}.md`, `research/{annotation-curation-qa,lab-notebook,provenance}.md`
- `skills/research/SKILL.md` (extract enums; add companion-skills footer; add leaf table)
- `skills/statistics/SKILL.md` (add leaf-summary table; companion-skills footer)
- `skills/writing/SKILL.md` (add companion-skills footer)
- `skills/data/SKILL.md` (document output-path split; add index pointer)
- `skills/data/expression/SKILL.md`, `skills/pipelines/snakemake.md`, `skills/pipelines/runpod.md`, `skills/pipelines/marimo.md` (companion-skills footers, cross-refs)
- All 9 QA/QA-like leaves: add or normalize `## Halt-On Conditions` section
- All commands referencing missing `knowledge-graph` and `causal-dag` skill pointers (Phase 2): resolve or explicitly route to follow-up
- `codex-skills/` regenerated via `scripts/generate_codex_skills.py` once at end of each phase that touches commands

### Deleted

None. Renames preserve git history via `git mv`.

---

## Conventions Decided Up Front

To prevent bikeshed during execution:

1. **Frontmatter `name:` field convention.** `<hub>-<leaf-slug>` (kebab-case). Examples:
   - `data/expression/bulk-rnaseq-qa.md` → `name: data-expression-bulk-rnaseq-qa`
   - `statistics/power-floor-acknowledgement.md` → `name: statistics-power-floor-acknowledgement`
   - `data/genomics/somatic-mutation-qa.md` → `name: data-genomics-somatic-mutation-qa`
   - Hubs keep their existing names (`data-management`, `statistics`, `research-methodology`, `scientific-writing`).
2. **Frontmatter `description:` field.** Single sentence, ≤ 200 chars, starts with "Use when..." for leaves. New or substantially rewritten hubs start with "Source of truth for..."; existing hub descriptions may be preserved unless the task explicitly changes them.
3. **Output-path convention** (documented in `data/SKILL.md`):
   - **Input QA artifacts** (per-cohort, per-dataset preprocessing): `data/processed/<cohort_id>/<qa_step>/`
   - **Analysis QA artifacts** (per-analysis, post-hoc verification): `results/<workflow>/aNNN-<slug>/<qa_step>/`
   - Every output directory carries a `datapackage.json` (cross-ref `frictionless.md`).
4. **Companion Skills footer.** Every leaf and hub ends with a `## Companion Skills` section listing 1–5 cross-references with relative paths and a one-line "use when" hook.
5. **Halt-On Conditions section.** Every QA leaf has a `## Halt-On Conditions` section listing 3–7 specific conditions that should stop downstream analysis (modeled on `data/genomics/somatic-mutation-qa.md`).
6. **Index coverage.** Every `skills/**/*.md` file must be either referenced from `skills/INDEX.md` or explicitly ignored by a short allowlist inside the linter. This is the handoff contract for the follow-up `science-plan-analysis` implementation.

These decisions are locked. If a task encounters a conflict, the task handler raises it; do not improvise.

## Execution Guardrails

- Run this plan from a clean dedicated branch or worktree. Before each phase, run `git status --short`; if unrelated edits are present, do not stage them.
- Prefer explicit `git add <path> ...` commands. Avoid `git add -A` except immediately after `git mv` when the command names only the renamed directory and known reference files.
- Regenerate `codex-skills/` only after changing `commands/` or command-derived skill content. Pure `skills/` reference edits do not require regeneration unless a command file embeds the changed reference.
- If a lint rule intentionally creates a temporary failing baseline, capture the expected failure in the phase notes before the fixing task starts.

---

## Phase 0: Build the lint harness

The linter is the "unit test" for every subsequent documentation change. Without it, refactor verification is manual and unreliable.

### Task 0.1: Add `science-tool skills lint` scaffolding

**Files:**
- Create: `science-tool/src/science_tool/skills_lint/__init__.py`
- Create: `science-tool/src/science_tool/skills_lint/cli.py`
- Modify: `science-tool/src/science_tool/cli.py` (register subcommand)
- Test: `science-tool/tests/skills_lint/test_cli.py`

- [ ] **Step 1: Locate the existing CLI entry point**

Run: `rg -n "^def\s+\w+_group|@click.group|click.Command" science-tool/src/science_tool/cli.py`
Expected: identifies the top-level `click.group` to register the new `skills` subcommand under.

- [ ] **Step 2: Write the failing CLI smoke test**

```python
# science-tool/tests/skills_lint/test_cli.py
from click.testing import CliRunner
from science_tool.cli import main

def test_skills_lint_help_exits_zero():
    result = CliRunner().invoke(main, ["skills", "lint", "--help"])
    assert result.exit_code == 0
    assert "lint" in result.output.lower()
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd science-tool && uv run --frozen pytest tests/skills_lint/test_cli.py -v`
Expected: FAIL with "No such command 'skills'".

- [ ] **Step 4: Implement minimal scaffold**

```python
# science-tool/src/science_tool/skills_lint/__init__.py
from .cli import skills_group

__all__ = ["skills_group"]
```

```python
# science-tool/src/science_tool/skills_lint/cli.py
import click

@click.group(name="skills")
def skills_group() -> None:
    """Skills library tooling."""

@skills_group.command(name="lint")
@click.option("--root", type=click.Path(exists=True, file_okay=False), default="skills")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def lint_cmd(root: str, fmt: str) -> None:
    """Lint the skills/ tree for structural conformance."""
    click.echo("skills lint: no rules registered yet")
```

In `science-tool/src/science_tool/cli.py`, register: `main.add_command(skills_group)` (use the existing pattern in that file — match how other groups are registered).

- [ ] **Step 5: Run test to verify it passes**

Run: `cd science-tool && uv run --frozen pytest tests/skills_lint/test_cli.py -v`
Expected: PASS.

- [ ] **Step 6: Run typecheck and format**

Run: `cd science-tool && uv run --frozen pyright src/science_tool/skills_lint && uv run --frozen ruff check src/science_tool/skills_lint && uv run --frozen ruff format src/science_tool/skills_lint`
Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add science-tool/src/science_tool/skills_lint/ science-tool/src/science_tool/cli.py science-tool/tests/skills_lint/
git commit -m "feat(skills-lint): scaffold science-tool skills lint subcommand"
```

### Task 0.2: Implement the frontmatter rule

**Files:**
- Create: `science-tool/src/science_tool/skills_lint/lint.py`
- Modify: `science-tool/src/science_tool/skills_lint/cli.py`
- Test: `science-tool/tests/skills_lint/test_lint.py`
- Test fixtures: `science-tool/tests/skills_lint/fixtures/{good,bad-no-frontmatter,bad-missing-name,bad-missing-description}.md`

- [ ] **Step 1: Create test fixtures**

```markdown
<!-- fixtures/good.md -->
---
name: test-good
description: Use when verifying the linter accepts a well-formed skill.
---

# Good
```

```markdown
<!-- fixtures/bad-no-frontmatter.md -->
# No Frontmatter

This file has no YAML block.
```

```markdown
<!-- fixtures/bad-missing-name.md -->
---
description: Use when missing name field.
---

# Missing name
```

```markdown
<!-- fixtures/bad-missing-description.md -->
---
name: test-missing-description
---

# Missing description
```

- [ ] **Step 2: Write failing test for `check_frontmatter`**

```python
# science-tool/tests/skills_lint/test_lint.py
from pathlib import Path
from science_tool.skills_lint.lint import check_frontmatter, SkillIssue

FIXTURES = Path(__file__).parent / "fixtures"

def test_good_frontmatter_returns_no_issues():
    issues = check_frontmatter(FIXTURES / "good.md")
    assert issues == []

def test_no_frontmatter_returns_issue():
    issues = check_frontmatter(FIXTURES / "bad-no-frontmatter.md")
    assert len(issues) == 1
    assert issues[0].kind == "missing-frontmatter"

def test_missing_name_returns_issue():
    issues = check_frontmatter(FIXTURES / "bad-missing-name.md")
    assert len(issues) == 1
    assert issues[0].kind == "missing-field"
    assert issues[0].field == "name"

def test_missing_description_returns_issue():
    issues = check_frontmatter(FIXTURES / "bad-missing-description.md")
    assert len(issues) == 1
    assert issues[0].kind == "missing-field"
    assert issues[0].field == "description"
```

- [ ] **Step 3: Run tests to verify failure**

Run: `cd science-tool && uv run --frozen pytest tests/skills_lint/test_lint.py -v`
Expected: 4 errors (ImportError for `check_frontmatter`).

- [ ] **Step 4: Implement `check_frontmatter`**

```python
# science-tool/src/science_tool/skills_lint/lint.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

IssueKind = Literal[
    "missing-frontmatter",
    "invalid-yaml",
    "missing-field",
    "invalid-field",
    "missing-section",
    "broken-relative-link",
    "missing-index-entry",
]

@dataclass(frozen=True)
class SkillIssue:
    path: Path
    kind: IssueKind
    field: str | None = None
    detail: str = ""

REQUIRED_FIELDS = ("name", "description")

def check_frontmatter(path: Path) -> list[SkillIssue]:
    text = path.read_text()
    if not text.startswith("---\n"):
        return [SkillIssue(path, "missing-frontmatter")]
    end = text.find("\n---\n", 4)
    if end == -1:
        return [SkillIssue(path, "missing-frontmatter", detail="unterminated YAML block")]
    block = text[4:end]
    try:
        parsed = yaml.safe_load(block) or {}
    except yaml.YAMLError as exc:
        return [SkillIssue(path, "invalid-yaml", detail=str(exc))]
    if not isinstance(parsed, dict):
        return [SkillIssue(path, "invalid-yaml", detail="frontmatter is not a mapping")]
    issues: list[SkillIssue] = []
    for field in REQUIRED_FIELDS:
        if not parsed.get(field):
            issues.append(SkillIssue(path, "missing-field", field=field))
    return issues
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd science-tool && uv run --frozen pytest tests/skills_lint/test_lint.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Wire `check_frontmatter` into the `lint` CLI command**

In `cli.py`, replace the placeholder echo with: walk `Path(root).rglob("*.md")`, run `check_frontmatter` on each, format issues either as text (`<path>: <kind> <field> <detail>`) or as JSON (`{"issues": [...]}`). Convert `Path` values to POSIX strings before JSON serialization. Exit code = 1 if any issues.

- [ ] **Step 7: Add an end-to-end test that runs the CLI against the fixtures dir**

```python
def test_lint_cli_against_fixtures(tmp_path: Path):
    # Copy fixtures dir to tmp_path/skills, then invoke
    # CliRunner: result.exit_code == 1; output mentions all 3 bad files; "good.md" is not in output.
```

- [ ] **Step 8: Run typecheck, format, and full test**

Run: `cd science-tool && uv run --frozen pyright src/science_tool/skills_lint && uv run --frozen ruff check src/science_tool/skills_lint && uv run --frozen ruff format src/science_tool/skills_lint && uv run --frozen pytest tests/skills_lint/ -v`
Expected: all green.

- [ ] **Step 9: Commit**

```bash
git add science-tool/src/science_tool/skills_lint/ science-tool/tests/skills_lint/
git commit -m "feat(skills-lint): add frontmatter rule with name/description checks"
```

### Task 0.3: Capture baseline lint failures against `skills/`

**Files:**
- Create: `docs/plans/2026-04-26-skills-library-refactor-baseline.txt` (one-shot artifact)

- [ ] **Step 1: Run lint against the real skills tree**

Run: `cd science-tool && uv run --frozen science-tool skills lint --root ../skills --format text > ../docs/plans/2026-04-26-skills-library-refactor-baseline.txt; echo "exit=$?"`
Expected: exit=1, with 18 missing-frontmatter entries in the current tree.

- [ ] **Step 2: Verify the failure count matches the audit**

Run: `wc -l docs/plans/2026-04-26-skills-library-refactor-baseline.txt`
Expected: 18 lines (one per skill/reference file without frontmatter). If the count differs, investigate before continuing — do not adjust the baseline file to match.

- [ ] **Step 3: Commit baseline as a reference artifact**

```bash
git add docs/plans/2026-04-26-skills-library-refactor-baseline.txt
git commit -m "chore(skills): capture pre-refactor lint baseline"
```

---

## Phase 1: Frontmatter on every leaf

Goal: drive the baseline `missing-frontmatter` count to zero. The convention from "Conventions Decided Up Front" applies.

### Task 1.1: Add frontmatter to all 18 files missing it

**Files (all to modify):**
- `skills/data/embeddings-manifold-qa.md`
- `skills/data/functional-genomics-qa.md`
- `skills/data/protein-sequence-structure-qa.md`
- `skills/data/expression/bulk-rnaseq-qa.md`
- `skills/data/expression/microarray-qa.md`
- `skills/data/expression/scrna-qa.md`
- `skills/data/genomics/somatic-mutation-qa.md`
- `skills/data/genomics/mutational-signatures-and-selection.md`
- `skills/research/annotation-curation-qa.md`
- `skills/research/lab-notebook.md`
- `skills/research/provenance.md`
- `skills/statistics/bias-vs-variance-decomposition.md`
- `skills/statistics/compositional-data.md`
- `skills/statistics/power-floor-acknowledgement.md`
- `skills/statistics/prereg-amendment-vs-fresh.md`
- `skills/statistics/replicate-count-justification.md`
- `skills/statistics/sensitivity-arbitration.md`
- `skills/statistics/survival-and-hierarchical-models.md`

(The current tree has 18 missing-frontmatter files. The older audit count missed the two `data/genomics/` leaves, `annotation-curation-qa.md`, and the two research package reference files. Confirm against the baseline file from Task 0.3 — that file is the source of truth for which files need fixing.)

- [ ] **Step 1: Generate the frontmatter block for each file**

For each file, the block is:

```yaml
---
name: <hub>-<leaf-slug>
description: Use when <one-sentence trigger sentence based on the existing first paragraph>.
---
```

Concrete values (locked here to prevent drift):

| File | `name` | `description` (use exactly) |
|---|---|---|
| `data/embeddings-manifold-qa.md` | `data-embeddings-manifold-qa` | Use when analyzing high-dimensional embeddings, UMAP/t-SNE/PCA projections, HDBSCAN clusters, Mapper graphs, CKA, kNN purity, Moran's I, archetypes, or multi-lens comparisons. |
| `data/functional-genomics-qa.md` | `data-functional-genomics-qa` | Use when working with CRISPR/RNAi screens, DepMap dependency data, perturb-seq, LINCS/L1000 signatures, drug-response matrices, viability assays, or perturbation replication analyses. |
| `data/protein-sequence-structure-qa.md` | `data-protein-sequence-structure-qa` | Use when working with protein sequences, UniProt mappings, Pfam/InterPro/CATH labels, Foldseek/MMseqs clusters, PLM embeddings, DeepLoc/Meltome labels, or sequence/structure benchmark splits. |
| `data/expression/bulk-rnaseq-qa.md` | `data-expression-bulk-rnaseq-qa` | Use when ingesting or QA-reviewing bulk RNA-Seq cohorts (TCGA, GTEx, recount3, ARCHS4, GEO, MMRF), especially before meta-analysis. |
| `data/expression/microarray-qa.md` | `data-expression-microarray-qa` | Use when ingesting or QA-reviewing bulk microarray cohorts (Affymetrix, Agilent, Illumina BeadArray) for legacy meta-analysis. |
| `data/expression/scrna-qa.md` | `data-expression-scrna-qa` | Use when ingesting or QA-reviewing single-cell RNA-Seq cohorts, especially before pseudobulk meta-analysis or cell-type composition claims. |
| `data/genomics/somatic-mutation-qa.md` | `data-genomics-somatic-mutation-qa` | Use when ingesting or auditing tumor mutation calls from cBioPortal, AACR GENIE, TCGA/MC3, ICGC, MAF files, study supplements, or targeted-panel cohorts. |
| `data/genomics/mutational-signatures-and-selection.md` | `data-genomics-mutational-signatures-and-selection` | Use when analyzing SBS/DBS/ID mutational signatures, tumor mutational burden, replication-timing bias, driver-gene enrichment, dN/dS, dNdScv, or selection signals. |
| `research/annotation-curation-qa.md` | `research-annotation-curation-qa` | Use when creating or auditing curated labels, extracted claims, taxonomy/facet assignments, model annotations, literature-derived tables, or LLM-assisted annotation workflows. |
| `research/lab-notebook.md` | `research-lab-notebook` | Use when rendering research-package materials into notebook-like review views, summaries, or inspection pages. |
| `research/provenance.md` | `research-provenance` | Use when defining or reviewing research-package provenance, manifests, evidence tables, and reproducibility metadata. |
| `statistics/bias-vs-variance-decomposition.md` | `statistics-bias-vs-variance-decomposition` | Use when choosing estimators, replicate counts, correction terms, simulation designs, or sensitivity analyses where stochastic noise and systematic error could be confused. |
| `statistics/compositional-data.md` | `statistics-compositional-data` | Use when analyzing proportions, fractions, cell-type composition, microbiome relative abundance, clone fractions, topic mixtures, deconvolution outputs, or any features constrained to sum to one. |
| `statistics/power-floor-acknowledgement.md` | `statistics-power-floor-acknowledgement` | Use before interpreting null, weak, or boundary results from finite-sample analyses, especially pre-registrations, replication attempts, subgroup tests, and negative findings. |
| `statistics/prereg-amendment-vs-fresh.md` | `statistics-prereg-amendment-vs-fresh` | Use when a follow-up analysis changes data, operationalisation, model, thresholds, or scope after an earlier pre-registration exists. |
| `statistics/replicate-count-justification.md` | `statistics-replicate-count-justification` | Use when choosing the number of replicates for stochastic estimators (bootstrap, permutation, Monte Carlo, downsampling, MCMC) and you would otherwise pick a round-number default. |
| `statistics/sensitivity-arbitration.md` | `statistics-sensitivity-arbitration` | Use when an analysis includes multiple robustness checks, alternate operationalisations, filters, covariate sets, priors, models, or negative controls whose results could change interpretation. |
| `statistics/survival-and-hierarchical-models.md` | `statistics-survival-and-hierarchical-models` | Use when designing or reviewing Cox, Weibull, AFT, frailty, mixed-effects, Bayesian hierarchical, or multi-dataset causal models. |

- [ ] **Step 2: Apply the frontmatter to each file**

For each file, prepend the block exactly. Do not modify any existing content (including the first `# Heading`). Use the Edit tool with `old_string` = first heading line and `new_string` = `<frontmatter>\n\n<heading>`.

- [ ] **Step 3: Re-run the linter; verify the baseline count drops to zero**

Run: `cd science-tool && uv run --frozen science-tool skills lint --root ../skills --format text`
Expected: exit code 0, no output.

- [ ] **Step 4: Spot-check three files manually**

Run: `head -5 skills/data/expression/bulk-rnaseq-qa.md skills/statistics/power-floor-acknowledgement.md skills/data/genomics/somatic-mutation-qa.md`
Expected: each begins with the locked frontmatter block exactly.

- [ ] **Step 5: Commit**

```bash
git add skills/
git commit -m "chore(skills): add frontmatter to all leaves with hub-leaf naming"
```

---

## Phase 2: Resolve broken command skill pointers

The string `knowledge-graph` is a `> Prerequisites:` reference in command and codex-skill files but no `skills/knowledge-graph.md` exists. The string `causal-dag` is also referenced, while the planned causal DAG skill is listed as a follow-up under `skills/statistics/causal-dag-and-identification.md`. Resolve `knowledge-graph` now and make the `causal-dag` state explicit so the final tree has no accidental broken skill pointers.

### Task 2.1: Investigate the intended target

- [ ] **Step 1: Search the repo for any file that could be the `knowledge-graph` or `causal-dag` skill**

Run: `rg -l "^# Knowledge Graph|name: knowledge-graph|name: knowledge_graph|^# Causal DAG|name: causal-dag|name: causal_dag" /mnt/ssd/Dropbox/science --glob '!node_modules/**' --glob '!.git/**'`
Expected: either zero results (skill never existed) or a path outside `skills/` (skill lives elsewhere).

- [ ] **Step 2: Search for a likely alternative source**

Run: `rg -l "knowledge graph|sci:Concept|knowledge/graph.trig|causal DAG|identification" /mnt/ssd/Dropbox/science/references/ /mnt/ssd/Dropbox/science/docs/ 2>&1 | head -40`
Expected: identifies a candidate document (likely in `docs/specs/` or `references/`) that explains the knowledge-graph model.

- [ ] **Step 3: Document findings inline in the plan**

Append a comment to this task in the plan with the search results — do not dispatch another investigation. The next task picks the resolution path based on what was found.

### Task 2.2: Resolve based on findings

Three resolution paths for `knowledge-graph`. Pick exactly one based on Task 2.1. For `causal-dag`, either update references to the real follow-up name (`causal-dag-and-identification`) if the skill is created in this phase, or remove/soften prerequisite wording so commands say the causal-DAG skill is planned but not currently loadable.

- [ ] **Path A — Skill exists outside `skills/`:** update each referencing file to use the correct path. Example replacement:
  - `Load the knowledge-graph skill for ontology reference` →
  - `Load the knowledge-graph reference at <actual-path>` (or whatever phrasing matches the surrounding command-preamble idiom).

- [ ] **Path B — Skill should live in `skills/`:** create `skills/knowledge-graph.md` (or `skills/research/knowledge-graph.md` if scoped to research framing) with the locked frontmatter convention from Phase 1. The body summarizes the entity types, edge types, and `science-tool graph ...` invocations. Source material: `references/role-prompts/`, `docs/specs/2026-*-graph-*.md`, the existing references in `commands/{plan-pipeline,review-pipeline,specify-model,sketch-model,critique-approach,update-graph,create-graph,import-project}.md` and their codex-skills counterparts.

- [ ] **Path C — Reference is stale and should be removed:** strip the `Load the knowledge-graph skill` line from each referencing file. Justify in the commit message why the prerequisite is no longer needed.

- [ ] **Step: Find every referencing file**

Run: `rg -l "knowledge-graph|causal-dag" commands/ codex-skills/ skills/`
Expected: all command/codex-skill paths with missing skill pointers.

- [ ] **Step: Apply the chosen path consistently across all referencing files**

Use the Edit tool with `replace_all=true` per file. Verify with `rg "knowledge-graph|causal-dag" commands/ codex-skills/ skills/` returning either zero results for removed stale pointers or only valid pointers to existing skills/follow-up text.

- [ ] **Step: If commands changed, regenerate codex-skills**

Run: `uv run python scripts/generate_codex_skills.py`
Expected: codex-skills regenerated; `git diff codex-skills/` shows the same edits propagated.

- [ ] **Step: Verify lint still passes**

Run: `cd science-tool && uv run --frozen science-tool skills lint --root ../skills --format text`
Expected: exit 0.

- [ ] **Step: Commit**

```bash
git add skills/ commands/ codex-skills/
git commit -m "fix(skills): resolve broken command skill pointers"
```

---

## Phase 3: Renames

### Task 3.1: Rename `lab-notebook.md` → `research-package-rendering.md`

**Files:**
- Rename: `skills/research/lab-notebook.md` → `skills/research/research-package-rendering.md`
- Modify: every file that references `research/lab-notebook` (verified in Phase 0 to be only `skills/pipelines/snakemake.md` plus design docs in `docs/specs/`)

- [ ] **Step 1: Find all references**

Run: `rg -l "research/lab-notebook|lab-notebook\.md" --glob '!node_modules/**' --glob '!.git/**'`
Expected: 1–3 paths.

- [ ] **Step 2: `git mv` the file**

Run: `git mv skills/research/lab-notebook.md skills/research/research-package-rendering.md`

- [ ] **Step 3: Update frontmatter, H1 heading, and internal self-references**

Read the renamed file; change frontmatter `name: research-lab-notebook` to `name: research-package-rendering`, change `# Lab Notebook Views` to `# Research Package Rendering`, and update any "lab notebook" prose that refers to the file's purpose to "research package rendering."

- [ ] **Step 4: Update referencing files**

For each path from Step 1 (other than the renamed file itself), replace `research/lab-notebook` with `research/research-package-rendering` (and similar variants). Use `Edit` with `replace_all=true`.

- [ ] **Step 5: Verify zero stale references**

Run: `rg "research/lab-notebook|lab-notebook\.md" --glob '!node_modules/**' --glob '!.git/**'`
Expected: empty.

- [ ] **Step 6: Lint + commit**

```bash
cd science-tool && uv run --frozen science-tool skills lint --root ../skills && cd ..
git add skills/research/research-package-rendering.md skills/research/lab-notebook.md skills/pipelines/snakemake.md docs/specs/2026-04-26-analysis-planning-and-skill-index-design.md
git commit -m "refactor(skills): rename research/lab-notebook to research-package-rendering"
```

### Task 3.2: Rename `provenance.md` → `research-package-spec.md`

Same shape as 3.1.

- [ ] **Step 1: Find all references**

Run: `rg -l "research/provenance|skills/research/provenance" --glob '!node_modules/**' --glob '!.git/**'`
Expected: 2–4 paths.

- [ ] **Step 2: `git mv`**

Run: `git mv skills/research/provenance.md skills/research/research-package-spec.md`

- [ ] **Step 3: Update frontmatter and H1**

Change frontmatter `name: research-provenance` to `name: research-package-spec`. Update H1 from `# Research Provenance` to `# Research Package Specification`. The body of the file is about the `science-research-package` data-package profile. Update prose accordingly so the file's name and content agree.

- [ ] **Step 4: Update all referencing files**

Same pattern as 3.1 step 4. The reference in `skills/pipelines/snakemake.md` line ~325 (`see the skills/research/provenance.md skill`) needs updating.

- [ ] **Step 5: Verify zero stale references**

Run: `rg "skills/research/provenance|research/provenance\.md" --glob '!node_modules/**' --glob '!.git/**'`
Expected: empty.

- [ ] **Step 6: Lint + commit**

```bash
cd science-tool && uv run --frozen science-tool skills lint --root ../skills && cd ..
git add skills/research/research-package-spec.md skills/research/provenance.md skills/pipelines/snakemake.md docs/specs/2026-04-26-analysis-planning-and-skill-index-design.md
git commit -m "refactor(skills): rename research/provenance to research-package-spec"
```

---

## Phase 4: New hubs

### Task 4.1: Create `skills/pipelines/SKILL.md`

**Files:**
- Create: `skills/pipelines/SKILL.md`

- [ ] **Step 1: Author the hub**

Content:

```markdown
---
name: pipelines
description: Source of truth for choosing and combining computational-execution skills (Snakemake, marimo, RunPod). Load when planning the orchestration shape of an analysis after methodology is decided.
---

# Pipelines

Decision aid for execution shape. Load **only after** methodology is decided
(see `skills/INDEX.md` and `science-plan-analysis`). Picking an execution
substrate before the analysis question is specified usually produces ceremony
without rigor.

## When to use which

| Skill | Load when | Avoid when |
|---|---|---|
| [`snakemake.md`](./snakemake.md) | Multi-step pipeline with file dependencies; intermediates worth caching; reproducible re-runs matter | One-off exploration; no DAG of dependencies |
| [`marimo.md`](./marimo.md) | Interactive exploration; parameter sweeps; presentation with widgets; pre-pipeline prototyping | Production batch; long jobs; CI |
| [`runpod.md`](./runpod.md) | Short-lived rented GPU; uv-based project; workload too large/slow for workstation | Long-lived managed cluster; CPU-only work |

These three are not mutually exclusive: `marimo` for prototyping → `snakemake`
for the pipeline → `runpod` for the GPU rule. The hub records the decision
order; the leaves cover the mechanics.

## Cross-cutting principles

1. **Tool-agnostic plans first.** `science-plan-pipeline` produces tool-agnostic
   task lists. Only commit to a specific orchestration substrate after the task
   list stabilizes.
2. **Side effects belong outside the workflow tree.** Snakemake's
   `protected()` does not save you from cleanup-before-rerun (see
   `snakemake.md` "protected() does NOT prevent rerun-cleanup"). Apply the
   marker-file pattern to any rule whose outputs live outside `out_dir`.
3. **Reproducibility = environment + seeds + inputs.** Pin tool versions, lock
   random seeds, hash inputs (`datapackage.json`). Without all three the
   pipeline is decorative.

## Companion Skills

- [`../data/SKILL.md`](../data/SKILL.md) — input-data conventions; pipelines should read from `data/raw/` and write to `data/processed/` or `results/`.
- [`../research/research-package-spec.md`](../research/research-package-spec.md) — terminal rule should produce a research package.
- [`../statistics/SKILL.md`](../statistics/SKILL.md) — statistical decisions that should be made before pipeline construction.
```

- [ ] **Step 2: Lint + commit**

Run: `cd science-tool && uv run --frozen science-tool skills lint --root ../skills && cd ..`
Expected: exit 0.

```bash
git add skills/pipelines/SKILL.md
git commit -m "feat(skills): add pipelines/SKILL.md hub"
```

### Task 4.2: Create `skills/data/genomics/SKILL.md`

**Files:**
- Create: `skills/data/genomics/SKILL.md`

- [ ] **Step 1: Author the hub**

Content:

```markdown
---
name: data-genomics
description: Source of truth for genomic-mutation data ingestion and QA. Use when working with somatic mutation calls, mutational signatures, dN/dS, or driver-selection analyses.
---

# Genomics — Data Ingestion & QA

Practical guidance for ingesting and quality-assessing genomic-mutation data.
Public mutation deposits combine biological signal with assay-specific failure
modes (panel coverage, calling pipeline drift, reference-build mismatches,
cohort composition) that look plausible until they invalidate downstream
inference.

## Two layers, two QA mindsets

| Layer | Leaf | Dominant failure modes |
|---|---|---|
| Mutation calls (input QA) | [`somatic-mutation-qa.md`](./somatic-mutation-qa.md) | callable territory, panel/exome mixing, NaN-vs-zero collapse, hypermutator dominance, sample-ID drift |
| Signatures and selection (analysis QA) | [`mutational-signatures-and-selection.md`](./mutational-signatures-and-selection.md) | opportunity-model omission, COSMIC version drift, length-confounded driver ranks, circular validation |

Always complete `somatic-mutation-qa.md` before treating signature or selection
results as verdict-bearing.

## Anticipated growth

Future leaves likely under this hub: copy-number QA, structural-variant QA,
fusion-transcript QA, methylation/EPIC-array QA. When adding a new leaf,
follow the frontmatter and companion-skills conventions established for
the existing two leaves.

## Companion Skills

- [`../SKILL.md`](../SKILL.md) — generic data-management conventions.
- [`../expression/SKILL.md`](../expression/SKILL.md) — expression cohorts often paired with mutation cohorts.
- [`../../statistics/power-floor-acknowledgement.md`](../../statistics/power-floor-acknowledgement.md) — mutation-frequency contrasts are typically low-power for rare genes.
- [`../../statistics/sensitivity-arbitration.md`](../../statistics/sensitivity-arbitration.md) — hypermutator-included vs -excluded analyses are the canonical sensitivity pair.
```

- [ ] **Step 2: Lint + commit**

```bash
cd science-tool && uv run --frozen science-tool skills lint --root ../skills && cd ..
git add skills/data/genomics/SKILL.md
git commit -m "feat(skills): add data/genomics/SKILL.md hub"
```

---

## Phase 5: Output-path convention

### Task 5.1: Document the convention split in `data/SKILL.md`

**Files:**
- Modify: `skills/data/SKILL.md`

- [ ] **Step 1: Locate the existing "Data Directory Convention" section**

Read: `skills/data/SKILL.md` lines ~30–60 (already shows `data/raw/`, `data/processed/`, `results/`).

- [ ] **Step 2: Insert a new subsection after `## Result Packages`**

```markdown
## Output-Path Convention for QA Artifacts

QA artifacts split by lifecycle:

- **Input QA** — per-cohort/per-dataset preprocessing checks that travel with the
  dataset: `data/processed/<cohort_id>/<qa_step>/`. Examples: `cohort_audit.json`,
  per-sample QC tables, probe-to-gene mappings, callable-territory tables.
- **Analysis QA** — per-analysis post-hoc checks tied to a specific result:
  `results/<workflow>/aNNN-<slug>/<qa_step>/`. Examples: bias audits,
  reconstruction-error reports, sensitivity panels, model diagnostics.

Every QA output directory must carry a `datapackage.json` (see
[`frictionless.md`](./frictionless.md)). Leaves should reference this
convention rather than redefining it.

The two locations are mirrors of each other: input QA lives next to the data
it audits; analysis QA lives next to the result it diagnoses. A QA step that
genuinely applies to both (e.g., row-alignment assertions) lives wherever it
runs; document the convention chosen in the leaf.
```

- [ ] **Step 3: Re-lint and commit**

```bash
cd science-tool && uv run --frozen science-tool skills lint --root ../skills && cd ..
git add skills/data/SKILL.md
git commit -m "docs(skills): document output-path convention split for QA artifacts"
```

### Task 5.2: Reconcile each leaf with the documented convention

Per the audit, output paths drift across leaves. Reconcile.

- [ ] **Step 1: Inventory the current state**

Run: `rg -n "results/<analysis>|data/processed/<cohort_id>" skills/`
Expected: ~20 hits across the 11 QA leaves.

- [ ] **Step 2: For each leaf, classify as input-QA or analysis-QA**

Locked classification (do not relitigate during execution):

| Leaf | Class | Path |
|---|---|---|
| `data/expression/bulk-rnaseq-qa.md` | input | `data/processed/<cohort_id>/` |
| `data/expression/microarray-qa.md` | input | `data/processed/<cohort_id>/` |
| `data/expression/scrna-qa.md` | input | `data/processed/<cohort_id>/` |
| `data/genomics/somatic-mutation-qa.md` | input | `data/processed/<cohort_id>/somatic_mutation_qa/` |
| `data/protein-sequence-structure-qa.md` | input | `data/processed/<protein_dataset>/` |
| `research/annotation-curation-qa.md` | input | `data/processed/<curation_task>/` |
| `data/embeddings-manifold-qa.md` | analysis | `results/<analysis>/embedding_qa/` |
| `data/functional-genomics-qa.md` | analysis | `results/<analysis>/functional_genomics_qa/` |
| `data/genomics/mutational-signatures-and-selection.md` | analysis | `results/<analysis>/signature_selection_qa/` |
| `statistics/compositional-data.md` | analysis | `results/<analysis>/compositional_qa/` |
| `statistics/survival-and-hierarchical-models.md` | analysis | `results/<analysis>/model_qa/` |

These already match the convention. If a leaf does not, update its `## Output Package` (or `## Minimum Artifacts`) section to match.

- [ ] **Step 3: For each leaf, add a one-line cross-ref to `frictionless.md` immediately above the output-tree code block**

Insert this sentence, adjusting the relative path:

```markdown
Generate a `datapackage.json` for this directory; see [`../frictionless.md`](../frictionless.md).
```

- [ ] **Step 4: Re-lint and commit**

```bash
cd science-tool && uv run --frozen science-tool skills lint --root ../skills && cd ..
git add skills/
git commit -m "docs(skills): align leaf output paths with documented convention; reference frictionless.md"
```

---

## Phase 6: Cross-references via Companion Skills sections

### Task 6.0: Add companion-skills and relative-link lint rules

**Files:**
- Modify: `science-tool/src/science_tool/skills_lint/lint.py`
- Modify: `science-tool/tests/skills_lint/test_lint.py`
- Test fixtures: add `bad-no-companion-skills.md`, `good-with-companion.md`, `bad-broken-relative-link.md`

- [ ] **Step 1: Add a fixture**

```markdown
<!-- bad-no-companion-skills.md -->
---
name: test-no-companion
description: Use when testing the linter rejects a leaf without companion skills.
---

# No Companion

Body without the required section.
```

- [ ] **Step 2: Write failing test**

```python
def test_missing_companion_skills_section_returns_issue():
    issues = check_companion_skills(FIXTURES / "bad-no-companion-skills.md")
    assert any(i.kind == "missing-section" and i.detail == "Companion Skills" for i in issues)
```

- [ ] **Step 3: Run test → fails (no `check_companion_skills`)**
- [ ] **Step 4: Implement companion-section check**

Search for exact `^## Companion Skills$` with `re.MULTILINE`; emit `SkillIssue(kind="missing-section", detail="Companion Skills")` if absent. Existing lowercase `## Companion skills` headings should fail so Phase 6.1 normalizes casing.

- [ ] **Step 4b: Implement markdown relative-link resolution**

Parse markdown links with a conservative regex for `](...)`. For each non-URL, non-anchor link ending in `.md`, resolve relative to `path.parent` and emit `SkillIssue(kind="broken-relative-link", detail=<target>)` if the target file does not exist. Include a fixture where `good-with-companion.md` links to an existing sibling and `bad-broken-relative-link.md` links to `missing.md`.

- [ ] **Step 5: Wire into the CLI; re-run lint against `skills/` (expect many failures — this is intentional, the next task fixes them)**
- [ ] **Step 6: Commit just the linter change with the failing baseline noted in the commit message**

```bash
git add science-tool/
git commit -m "feat(skills-lint): require Companion Skills sections and valid relative links"
```

### Task 6.1: Add Companion Skills sections per the audit's cross-reference matrix

**Files (modify):** every leaf and hub missing the section. Run the linter to enumerate.

- [ ] **Step 1: Run lint to enumerate offenders**

Run: `cd science-tool && uv run --frozen science-tool skills lint --root ../skills --format text | rg "Companion Skills"`
Expected: a list of paths.

- [ ] **Step 2: For each offender, append a `## Companion Skills` section using these locked cross-references** (from the audit, §C):

| File | Companion entries |
|---|---|
| `data/SKILL.md` | `expression/SKILL.md`, `frictionless.md`, `../statistics/SKILL.md`, `../research/SKILL.md` |
| `data/expression/SKILL.md` | normalize existing `## Companion skills` heading to `## Companion Skills`; keep existing links and add `../genomics/SKILL.md` if mutation/expression paired-cohort language is present |
| `data/frictionless.md` | `SKILL.md`, `../pipelines/snakemake.md`, `../research/research-package-spec.md` |
| `data/sources/openalex.md` | `pubmed.md`, `../../research/annotation-curation-qa.md`, `../../research/SKILL.md` |
| `data/sources/pubmed.md` | `openalex.md`, `../../research/annotation-curation-qa.md`, `../../research/SKILL.md` |
| `statistics/compositional-data.md` | `../data/expression/scrna-qa.md` (pseudobulk), `survival-and-hierarchical-models.md`, `bias-vs-variance-decomposition.md` |
| `statistics/survival-and-hierarchical-models.md` | `sensitivity-arbitration.md`, `power-floor-acknowledgement.md`, `compositional-data.md` |
| `statistics/bias-vs-variance-decomposition.md` | `replicate-count-justification.md`, `sensitivity-arbitration.md`, `power-floor-acknowledgement.md` |
| `statistics/power-floor-acknowledgement.md` | `sensitivity-arbitration.md`, `bias-vs-variance-decomposition.md`, `replicate-count-justification.md` |
| `statistics/replicate-count-justification.md` | `bias-vs-variance-decomposition.md`, `power-floor-acknowledgement.md`, `survival-and-hierarchical-models.md` |
| `statistics/sensitivity-arbitration.md` | `power-floor-acknowledgement.md`, `survival-and-hierarchical-models.md`, `compositional-data.md` |
| `statistics/prereg-amendment-vs-fresh.md` | `sensitivity-arbitration.md`, `power-floor-acknowledgement.md` |
| `data/functional-genomics-qa.md` | `data/embeddings-manifold-qa.md` (L1000 connectivity), `data/expression/scrna-qa.md` (perturb-seq), `statistics/sensitivity-arbitration.md` |
| `data/embeddings-manifold-qa.md` | `data/protein-sequence-structure-qa.md` (already present — keep), `statistics/bias-vs-variance-decomposition.md` |
| `data/protein-sequence-structure-qa.md` | `data/embeddings-manifold-qa.md` (already present), `data/SKILL.md` |
| `data/expression/bulk-rnaseq-qa.md` | `SKILL.md`, `../../../statistics/power-floor-acknowledgement.md`, `../../../statistics/bias-vs-variance-decomposition.md` |
| `data/expression/microarray-qa.md` | `SKILL.md`, `bulk-rnaseq-qa.md`, `../../../statistics/bias-vs-variance-decomposition.md` |
| `data/expression/scrna-qa.md` | `SKILL.md`, `../../../statistics/compositional-data.md`, `../../../statistics/power-floor-acknowledgement.md` |
| `data/genomics/SKILL.md` | `../SKILL.md`, `somatic-mutation-qa.md`, `mutational-signatures-and-selection.md`, `../../statistics/sensitivity-arbitration.md` |
| `data/genomics/somatic-mutation-qa.md` | keep existing section; ensure heading casing and links pass lint |
| `data/genomics/mutational-signatures-and-selection.md` | `somatic-mutation-qa.md`, `../../statistics/power-floor-acknowledgement.md`, `../../statistics/sensitivity-arbitration.md` |
| `research/annotation-curation-qa.md` | `research/SKILL.md`, `statistics/sensitivity-arbitration.md` |
| `research/research-package-rendering.md` | `research-package-spec.md`, `../writing/SKILL.md`, `../pipelines/snakemake.md` |
| `research/research-package-spec.md` | `../data/frictionless.md`, `../pipelines/snakemake.md`, `proposition-schema.md` |
| `research/SKILL.md` | `annotation-curation-qa.md`, `research-package-rendering.md`, `research-package-spec.md`, `proposition-schema.md` (will exist after Phase 7) |
| `statistics/SKILL.md` | `data/SKILL.md`, `research/SKILL.md`, `writing/SKILL.md` |
| `writing/SKILL.md` | `research/SKILL.md`, `statistics/SKILL.md` |
| `pipelines/SKILL.md` | already authored in Phase 4; verify links pass lint |
| `pipelines/snakemake.md` | `pipelines/SKILL.md`, `data/frictionless.md`, `research/research-package-spec.md` |
| `pipelines/marimo.md` | `pipelines/SKILL.md`, `pipelines/snakemake.md` |
| `pipelines/runpod.md` | `pipelines/SKILL.md`, `pipelines/snakemake.md` |

Format for the section (copy literally, adjust relative paths and the trigger sentence):

```markdown
## Companion Skills

- [`<relative/path.md>`](<relative/path.md>) — load when <one-line trigger>.
- [`<relative/path.md>`](<relative/path.md>) — load when <one-line trigger>.
```

- [ ] **Step 3: Re-run linter**

Run: `cd science-tool && uv run --frozen science-tool skills lint --root ../skills --format text`
Expected: exit 0.

- [ ] **Step 4: Confirm relative-link rule covers all Companion Skills links**

Run: `cd science-tool && uv run --frozen science-tool skills lint --root ../skills --format text`
Expected: no `broken-relative-link` issues. Do not defer this to a follow-up; broken links make the future index unreliable.

- [ ] **Step 5: Commit**

```bash
git add skills/
git commit -m "docs(skills): add Companion Skills sections with cross-references per audit"
```

---

## Phase 7: Extract project schema from `research/SKILL.md`

### Task 7.1: Move enums to `research/proposition-schema.md`

**Files:**
- Create: `skills/research/proposition-schema.md`
- Modify: `skills/research/SKILL.md`

- [ ] **Step 1: Identify the enum block in `research/SKILL.md`**

Range: lines ~96–117 (the `### Allowed enum values` subsection plus the surrounding `Working with Hypotheses` schema discussion that's project-specific). Read carefully to find the exact boundaries — the section starts with the layered-claim metadata bullets and ends before `## Evidence Classification`.

- [ ] **Step 2: Author the new leaf**

```markdown
---
name: research-proposition-schema
description: Use when authoring or updating proposition entities, hypothesis frontmatter, or knowledge-graph claim metadata. Defines the strict enums and field semantics for the Science project model.
---

# Proposition and Evidence Schema

Project-specific schema for the Science proposition/evidence model. For the
generic methodology layer (source hierarchy, evaluating sources, citation
discipline), see [`SKILL.md`](./SKILL.md). For the prose explanation of the
model, see `docs/proposition-and-evidence-model.md`.

When the project uses layered-claim metadata:

- use `claim_layer` only when the authored proposition really needs that distinction
- treat `identification_strength` as an evidence-design label, not as confidence
- keep `measurement_model` separate from the concrete `observation`
- do not promote mechanistic prose into `mechanistic_narrative` unless the supporting lower-layer structure is explicit
- if rival models are genuinely in play, prefer a bounded `rival_model_packet` over free-form prose comparison
- treat `current_working_model` as optional; do not invent one just to satisfy a schema

## Allowed enum values

These fields are strict enums. **Do not invent values** — if no listed value
fits, drop the field and explain in `measurement_model.rationale` or
`known_failure_modes` instead.

- **`claim_layer`** — what kind of claim is this?
  - `empirical_regularity` — observed pattern in data (a correlation, a frequency, a trend)
  - `causal_effect` — claim about a causal effect of one variable on another
  - `mechanistic_narrative` — proposed mechanism story; requires linked lower-layer support
  - `structural_claim` — claim about graph topology, model structure, or definitional scaffolding
- **`identification_strength`** — how much causal leverage does this evidence carry *in the target system*?
  - `none` — no causal handle (descriptive only)
  - `structural` — derived from network/model structure or theory, not data
  - `observational` — observational study, association adjusted for confounders
  - `longitudinal` — within-subject change over time
  - `interventional` — perturbation in the target system
  - `analogical` — interventional in a *model* system, extrapolated to target by analogy
- **`proxy_directness`** — `direct` | `indirect` | `derived`
- **`supports_scope`** — `local_proposition` | `hypothesis_bundle` | `cross_hypothesis` | `project_wide`

Methodological scaffolding (analysis methods, definitional/framework material,
historical context) usually does **not** belong as a `proposition`. Use
`method:`, `topic:`, or `discussion:` entity types instead — those don't
require enum classification.

## Companion Skills

- [`SKILL.md`](./SKILL.md) — generic research methodology that this schema overlays.
- [`annotation-curation-qa.md`](./annotation-curation-qa.md) — when extracting curated claims that will populate proposition entities.
```

- [ ] **Step 3: Replace the moved block in `SKILL.md` with a one-line pointer**

```markdown
For the strict enum values, layered-claim metadata semantics, and proposition
entity types, see [`proposition-schema.md`](./proposition-schema.md).
```

- [ ] **Step 4: Lint + commit**

```bash
cd science-tool && uv run --frozen science-tool skills lint --root ../skills && cd ..
git add skills/research/
git commit -m "refactor(skills): extract proposition schema from research/SKILL.md"
```

---

## Phase 8: `## Halt-On Conditions` sections

### Task 8.0: Add a lint rule

Mirror Task 6.0. Rule: every required QA/QA-like leaf in the explicit set below must contain a `## Halt-On Conditions` section. Hubs are exempt. Do not key only on `*-qa`; `mutational-signatures-and-selection.md` is analysis-QA but does not use the suffix.

- [ ] **Step 1:** Add a constant in `lint.py`:

```python
HALT_ON_REQUIRED = {
    "data/embeddings-manifold-qa.md",
    "data/functional-genomics-qa.md",
    "data/protein-sequence-structure-qa.md",
    "data/expression/bulk-rnaseq-qa.md",
    "data/expression/microarray-qa.md",
    "data/expression/scrna-qa.md",
    "data/genomics/somatic-mutation-qa.md",
    "data/genomics/mutational-signatures-and-selection.md",
    "research/annotation-curation-qa.md",
}
```

- [ ] **Step 2–6:** same TDD shape as Task 6.0, with one positive fixture and one missing-section fixture.

### Task 8.1: Author Halt-On sections per leaf

For each `*-qa.md` leaf, add a `## Halt-On Conditions` section following the pattern in `data/genomics/somatic-mutation-qa.md` (`## Red Flags Worth Halting On`).

**Affected leaves:** `data/embeddings-manifold-qa.md`, `data/functional-genomics-qa.md`, `data/protein-sequence-structure-qa.md`, `data/expression/{bulk-rnaseq,microarray,scrna}-qa.md`, `data/genomics/{somatic-mutation-qa,mutational-signatures-and-selection}.md`, `research/annotation-curation-qa.md` (9 files; `somatic-mutation-qa.md` already has `## Red Flags Worth Halting On` but should be renamed `## Halt-On Conditions` for consistency).

Locked content (one entry per file — these are the conditions to include; word them in the leaf's existing voice):

| Leaf | Halt conditions |
|---|---|
| `bulk-rnaseq-qa.md` | matrix scale unverified (could be TPM masquerading as counts); gene-model version unknown across cohorts; >10% samples with `% rRNA > 20`; PCA shows batch dominating biology and no batch metadata available; suspected pseudobulk-as-bulk per-sample read count anomaly |
| `microarray-qa.md` | platform variant unknown; no probe annotation available; quantile-normalization assumption violated (cohort heterogeneous); two-colour data treated as single-channel |
| `scrna-qa.md` | depositor's filter is cell-type-subset and not reversible; doublet calls absent and tool/threshold unknown; ambient-correction status unknown for low-expression marker biology; per-batch median UMI differs by >2x with no batch covariate available |
| `embeddings-manifold-qa.md` | row-universe alignment cannot be asserted across lenses; PC1 tracks length/depth/batch and no residualized mode is feasible; no homology-disjoint splits available for benchmarks |
| `functional-genomics-qa.md` | guide annotation absent; no non-targeting controls; copy-number not available for CRISPR amplicon-toxicity check; cell-line identity unverified |
| `protein-sequence-structure-qa.md` | identifier mapping ambiguous (gene-symbol joins for paralog families); train/test homology overlap above pre-set threshold; label hierarchy inconsistent |
| `somatic-mutation-qa.md` | callable territory unavailable or incomparable across cohorts; panel/exome cohorts mixed without restriction to common territory; missing-vs-zero mutation calls cannot be distinguished; hypermutators dominate gene-level contrasts |
| `mutational-signatures-and-selection.md` | opportunity model unknown for panel data; COSMIC version not pinned; driver ranks correlate with coding length and no length-aware model is run |
| `annotation-curation-qa.md` | schema version not recorded; <2 annotators on items used for verdict-bearing analysis; calibration set missing for LLM-assisted runs |

- [ ] **Step 1: For each leaf, draft and append the section**
- [ ] **Step 2: Re-lint (rule from 8.0)**
- [ ] **Step 3: Commit**

```bash
git add skills/
git commit -m "docs(skills): add Halt-On Conditions to every QA leaf"
```

---

## Phase 9: Classify `replicate-count-justification.md`

### Task 9.1: Mark as deep-reference and add TL;DR

**Files:**
- Modify: `skills/statistics/replicate-count-justification.md`

- [ ] **Step 1: Extend frontmatter with `type: deep-reference`**

Update the frontmatter block authored in Phase 1:

```yaml
---
name: statistics-replicate-count-justification
description: Use when choosing the number of replicates for stochastic estimators (bootstrap, permutation, Monte Carlo, downsampling, MCMC) and you would otherwise pick a round-number default.
type: deep-reference
---
```

- [ ] **Step 2: Add an optional `type` field to the linter**

Update `lint.py` so `type` is allowed but optional, and `type` ∈ `{"skill", "deep-reference"}` with default `"skill"`.

- [ ] **Step 3: Add a TL;DR section directly under the H1**

```markdown
## TL;DR

Lock replicate count R from a measured pilot, not a tutorial default.

- **Point estimators:** smallest R such that `SE_replicates(R) / SD_signal ≤ θ` (default θ = 0.20).
- **Permutation/MC p-values:** smallest B such that minimum-attainable p < target alpha and `p_hat ± 2·MCSE` cannot cross the decision boundary.
- **MCMC:** R-hat / ESS, not the ratio rule. `R-hat ≈ 1.00`, ESS adequate for tail probabilities used in the verdict.
- **Multiple imputation:** Rubin's `T = V_within + (1+1/m)·V_between`.

The rest of this file is the long-form derivation, worked examples, and
gotchas. Skim the TL;DR; read the body when designing the pilot.
```

- [ ] **Step 4: Lint + test the new optional `type` field**

Add a unit test that `type: deep-reference` is accepted. Add a unit test that `type: bogus` fails.

- [ ] **Step 5: Commit**

```bash
git add skills/statistics/replicate-count-justification.md science-tool/
git commit -m "docs(skills): add TL;DR and deep-reference type to replicate-count-justification"
```

---

## Phase 10: Hub-side leaf tables

### Task 10.1: Add leaf-summary table to `statistics/SKILL.md`

**Files:**
- Modify: `skills/statistics/SKILL.md`

- [ ] **Step 1: Insert a table immediately under the existing intro paragraph (before `## Principles`)**

```markdown
## Leaves

| Leaf | Use when |
|---|---|
| [`replicate-count-justification.md`](./replicate-count-justification.md) | Choosing R for bootstrap, permutation, Monte Carlo, downsampling, or MCMC |
| [`bias-vs-variance-decomposition.md`](./bias-vs-variance-decomposition.md) | Naming which error term shrinks with more data vs more replicates vs better estimator |
| [`power-floor-acknowledgement.md`](./power-floor-acknowledgement.md) | Before interpreting a null, weak, or boundary result |
| [`sensitivity-arbitration.md`](./sensitivity-arbitration.md) | Pre-committing the rule for resolving disagreement among robustness checks |
| [`prereg-amendment-vs-fresh.md`](./prereg-amendment-vs-fresh.md) | Deciding whether a follow-up needs a fresh pre-reg or an amendment |
| [`survival-and-hierarchical-models.md`](./survival-and-hierarchical-models.md) | Cox / Weibull / mixed-effects / Bayesian hierarchical models |
| [`compositional-data.md`](./compositional-data.md) | Proportions, fractions, deconvolution outputs, microbiome relative abundance |
```

- [ ] **Step 2: Lint + commit**

```bash
git add skills/statistics/SKILL.md
git commit -m "docs(skills): add leaf-summary table to statistics/SKILL.md"
```

### Task 10.2: Same shape for `research/SKILL.md` and `writing/SKILL.md`

- [ ] **`research/SKILL.md` table:** entries for `annotation-curation-qa.md`, `proposition-schema.md`, `research-package-rendering.md`, `research-package-spec.md`.

- [ ] **`writing/SKILL.md` table:** state "No leaves currently; planned future areas: pre-registration prose, results-interpretation, paper-summary." (See Follow-up Plans.) Do not create stub leaf files.

- [ ] **Lint + commit per file**

```bash
git add skills/research/SKILL.md skills/writing/SKILL.md
git commit -m "docs(skills): add leaf-summary tables to research and writing hubs"
```

---

## Phase 11: Minimal `skills/INDEX.md` readiness contract

This plan does not implement `science-plan-analysis`, but the source spec requires a compact skill index and an index-coverage lint check. Add the index now so the structural refactor finishes with a usable discovery map rather than another cleanup dependency.

### Task 11.1: Create `skills/INDEX.md`

**Files:**
- Create: `skills/INDEX.md`
- Modify: `skills/data/SKILL.md`
- Modify: `skills/statistics/SKILL.md`
- Modify: `skills/research/SKILL.md`
- Modify: `skills/writing/SKILL.md`
- Modify: `skills/pipelines/SKILL.md`

- [ ] **Step 1: Author the compact index**

Use the Proposed Index Shape from `docs/specs/2026-04-26-analysis-planning-and-skill-index-design.md`, but make it lintable like every other markdown file under `skills/`: include frontmatter and a short `## Companion Skills` section.

Required frontmatter:

```yaml
---
name: science-skill-index
description: Source of truth for finding Science methodology skills during analysis-readiness planning.
---
```

Then update renamed paths:

- `research-package-spec`: `skills/research/research-package-spec.md`
- `research-package-rendering`: `skills/research/research-package-rendering.md`
- `research-proposition-schema`: `skills/research/proposition-schema.md`
- `pipelines`: `skills/pipelines/SKILL.md`
- `data-genomics`: `skills/data/genomics/SKILL.md`

Keep the file under about 150 lines. Use frontmatter `name` values as IDs when present; do not invent IDs that differ from frontmatter.

End with:

```markdown
## Companion Skills

- [`data/SKILL.md`](data/SKILL.md) — load when data acquisition, preprocessing, or QA is in scope.
- [`statistics/SKILL.md`](statistics/SKILL.md) — load when finite-sample quantitative interpretation is in scope.
- [`research/SKILL.md`](research/SKILL.md) — load when evidence evaluation, curation, or proposition schema is in scope.
- [`pipelines/SKILL.md`](pipelines/SKILL.md) — load only after methodology is clear and execution planning is needed.
```

- [ ] **Step 2: Add the source-spec pointer to each hub**

At the top of each hub body, immediately after the H1 and intro paragraph if present, add:

```markdown
For analysis-readiness planning, start at [`../INDEX.md`](../INDEX.md) or run
`science-plan-analysis`.
```

Adjust the relative path per hub:

| Hub | Index link |
|---|---|
| `skills/data/SKILL.md` | `../INDEX.md` |
| `skills/data/expression/SKILL.md` | `../../INDEX.md` |
| `skills/data/genomics/SKILL.md` | `../../INDEX.md` |
| `skills/statistics/SKILL.md` | `../INDEX.md` |
| `skills/research/SKILL.md` | `../INDEX.md` |
| `skills/writing/SKILL.md` | `../INDEX.md` |
| `skills/pipelines/SKILL.md` | `../INDEX.md` |

- [ ] **Step 3: Lint + commit**

```bash
cd science-tool && uv run --frozen science-tool skills lint --root ../skills && cd ..
git add skills/INDEX.md skills/data/SKILL.md skills/data/expression/SKILL.md skills/data/genomics/SKILL.md skills/statistics/SKILL.md skills/research/SKILL.md skills/writing/SKILL.md skills/pipelines/SKILL.md
git commit -m "docs(skills): add compact analysis-planning index"
```

### Task 11.2: Add index-coverage lint rule

**Files:**
- Modify: `science-tool/src/science_tool/skills_lint/lint.py`
- Modify: `science-tool/tests/skills_lint/test_lint.py`
- Test fixtures: add `index/` fixture tree with one indexed skill and one unindexed skill

- [ ] **Step 1: Write failing tests**

Test that every markdown file under the lint root is referenced from `INDEX.md` by relative path. The index file itself is exempt. Use POSIX-style relative paths.

- [ ] **Step 2: Implement `check_index_coverage(root: Path)`**

Read `root / "INDEX.md"`, collect all markdown links and inline code paths that begin with `skills/` or are relative to the repo root, normalize them to paths relative to `root`, and compare against `root.rglob("*.md")`. Emit `SkillIssue(kind="missing-index-entry", detail=<relative-path>)` for each uncovered file. Keep an internal allowlist empty for now; do not silently skip utility skills.

- [ ] **Step 3: Wire into CLI and verify**

Run: `cd science-tool && uv run --frozen pytest tests/skills_lint/ -v && uv run --frozen science-tool skills lint --root ../skills --format text`
Expected: tests pass and real-tree lint exits 0.

- [ ] **Step 4: Commit**

```bash
git add science-tool/src/science_tool/skills_lint/lint.py science-tool/tests/skills_lint/test_lint.py science-tool/tests/skills_lint/fixtures/
git commit -m "feat(skills-lint): require skills index coverage"
```

---

## Phase 12: Final regeneration and verification

### Task 12.1: Regenerate codex-skills

- [ ] **Step 1**

Run: `uv run python scripts/generate_codex_skills.py`
Expected: codex-skills regenerated.

- [ ] **Step 2: Inspect diff**

Run: `git diff codex-skills/ | head -200`
Verify: changes match the command edits made during Phase 2 (knowledge-graph fix). No unexpected changes.

- [ ] **Step 3: Commit**

```bash
git add codex-skills/
git commit -m "chore(codex-skills): regenerate after skills refactor"
```

### Task 12.2: Final lint + cross-reference resolution sweep

- [ ] **Step 1: Full lint**

Run: `cd science-tool && uv run --frozen science-tool skills lint --root ../skills`
Expected: exit 0.

- [ ] **Step 2: Find any dangling internal links across the skills tree**

Run: `find skills -name '*.md' -exec rg -o '\]\([^)#][^)]*\)' {} + | sort -u | head -100`
Manually spot-check ~10 sampled paths exist relative to their containing file.

- [ ] **Step 3: Final commit if anything was tweaked; otherwise skip**

---

## Out-of-Scope / Follow-up Plans

The following items from the audit are **not** addressed by this plan. Each merits its own plan because each requires substantive subject-matter authoring rather than mechanical refactor.

| Follow-up plan | Audit reference | Notes |
|---|---|---|
| `skills/statistics/causal-dag-and-identification.md` | §G.2 | Anchors `science:sketch-model` / `specify-model` / `critique-approach` |
| `skills/statistics/sample-size-and-design.md` | §G.3 | Prospective complement to power-floor |
| `skills/statistics/meta-analysis.md` | §G.4 | Extracts the meta-analysis prose currently embedded in expression leaves |
| `skills/statistics/model-evaluation.md` | §G.5 | Generic ML eval (calibration, threshold selection, CV) |
| `skills/data/multi-omics-integration.md` | §G.6 | Cross-modality joining, batch handling, MOFA/totalVI patterns |
| `skills/pipelines/reproducibility.md` | §G.7 | Determinism, lockfiles, container freezing |
| `skills/research/lab-notebook.md` (the genuine one) | §G.8 | After the rename frees the namespace |
| `skills/writing/visualization.md` | §G.9 | Project conventions for altair/seaborn |
| `skills/data/spatial-transcriptomics-qa.md` | §G.10 | If/when project priorities cover Visium/Xenium/MERFISH |
| `skills/statistics/time-series.md` | §G.11 | Longitudinal beyond what survival covers |
| `skills/data/controlled-access.md` | §G.12 | dbGaP/EGA credential discipline |
| `skills/writing/pre-registration-prose.md` | §G.13 | Structure complement to `prereg-amendment-vs-fresh` |
| `science-plan-analysis` command implementation | source spec implementation scope | This plan creates `skills/INDEX.md` and index coverage; command/docs/codex-skill wiring should be a separate implementation plan. |

The structural refactor in this plan deliberately leaves future-skill slots out of the current implementation. The writing hub may state "No leaves currently" and name planned future areas, but it must not create stub files or empty placeholder sections.

---

## Self-Review Checklist (run before execution)

- **Spec coverage:** every structural audit recommendation §A–§J has at least one task; source-spec index coverage is handled in Phase 11; full `science-plan-analysis` command implementation is explicitly out of scope. ✓
- **Placeholder scan:** searched for "TBD", "TODO", "fill in", "appropriate", and "placeholder". The convention tables in Phase 1 and Phase 6 give concrete values or require linter-enumerated offenders before edits. ✓
- **Type/name consistency:** the locked frontmatter `name:` values in Phase 1 match the relative-path references used in the Companion Skills tables in Phase 6 and the leaf-summary tables in Phase 10. ✓
- **Out-of-scope clarity:** every audit gap not addressed is listed in the Follow-up section. ✓
