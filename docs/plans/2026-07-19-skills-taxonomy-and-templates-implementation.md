# Skills Taxonomy & Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a durable skill-authoring doctrine (a `meta/` skill) plus one authoring template per leaf archetype, and make the frontmatter contract executable in the linter — without migrating the existing corpus.

**Architecture:** Add a shared skill-file iterator that excludes authoring scaffolds; extend the linter with an optional-but-validated `archetype:` field and rename `type:`→`depth:`; author `skills/meta/` (a pure router + two doctrine leaves) and `skills/meta/templates/` (six archetype templates + a router profile); wire the codex mirror to bundle the meta skill and its templates; validate failing-first with unit tests, per-archetype template-conformance tests, and documented behavioral scenarios whose baselines are captured **before** the doctrine exists.

**Tech Stack:** Python ≥3.11, `click`, `pyyaml`, `pytest`; the `science` toolkit under `science/` (no root pyproject).

**Design:** [`2026-07-19-skills-taxonomy-and-templates-design.md`](./2026-07-19-skills-taxonomy-and-templates-design.md) · **Corpus matrix:** [`2026-07-19-skills-taxonomy-corpus-matrix.md`](./2026-07-19-skills-taxonomy-corpus-matrix.md). Read both before starting.

## Global Constraints

- **All `uv` commands run from the `science/` subdirectory** (no root pyproject): `cd science && uv run --frozen pytest …` / `ruff check …` / `pyright`. Test directories are not type-checked. The harness LSP emits false `reportMissingImports` for `science_tool.skills_lint.*`; the authoritative check is `cd science && uv run pyright` (baseline 0/0/0).
- **Fixed skill names (public identifiers — do not invent alternatives):** router `meta/SKILL.md` → `name: skill-development` (Codex `science-skill-development`); `meta/skill-taxonomy.md` → `name: skill-taxonomy` (`archetype: normative-reference`); `meta/skill-authoring.md` → `name: skill-authoring` (`archetype: practice-guide`).
- **The six archetypes (exact spellings):** `measurement-qa`, `method-guide`, `analysis-discipline`, `normative-reference`, `tool-guide`, `practice-guide`.
- **`archetype:` is optional this phase** — leaves are NOT yet required to declare it; completeness enforcement + corpus backfill are deferred to migration. Routers and `INDEX.md` must NOT carry `archetype:`.
- **Scalar validation is presence-and-type explicit** — a present `depth:`/`archetype:` must be a recognized string; `null`/list/mapping values are `invalid-field`, never a crash, never silently "absent".
- **No compatibility alias for `type:`.** A present `type:` key is `invalid-field` immediately; `depth:` replaces it (`standard | deep-reference`, absent ⇒ `standard`).
- **Every skill Markdown file (router and leaf) must carry `provenance: internal` or valid `sources:`** — `missing-provenance` is ERROR — **and a `## Companion Skills` section** (`check_companion_skills` runs on every discovered file). The excluded `meta/templates/**` scaffolds carry neither.
- **Regenerate the codex mirror after ANY `skills/` change:** `cd science && uv run python ../scripts/generate_codex_skills.py`; `test_committed_codex_skills_match_fresh_generation` guards staleness.
- **Failing-first ordering is mandatory (design "Validation"):** behavioral **baselines are captured before the doctrine leaves exist in the worktree** (Task 4, before Task 6); template conformance tests are written and observed RED before the templates are authored (within Task 5).
- **No AI-attribution trailer/footer on commits.** Use `~/d/` in any docs/code paths.

## File Structure

**Create:**
- `science/src/science_tool/skills_lint/discovery.py` — `iter_skill_files(root)`.
- `skills/meta/SKILL.md`, `skills/meta/skill-taxonomy.md`, `skills/meta/skill-authoring.md`.
- `skills/meta/templates/{router,measurement-qa,method-guide,analysis-discipline,normative-reference,tool-guide,practice-guide}.md`.
- `science/tests/skills_lint/test_discovery.py`, `science/tests/skills_lint/test_templates.py`.
- `docs/plans/2026-07-19-skills-taxonomy-behavioral-scenarios.md`.

**Modify:**
- `science/src/science_tool/skills_lint/lint.py`, `cli.py`, `codex_skills.py`.
- `skills/INDEX.md` (add meta entries + broaden the intro), `skills/statistics/replicate-count-justification.md` (`type`→`depth`).
- `science/tests/skills_lint/test_lint.py`, `science/tests/test_codex_skills.py`.
- `science/tests/skills_lint/fixtures/good-deep-reference.md`, `science/tests/skills_lint/fixtures/INDEX.md`; rename `fixtures/bad-invalid-type.md` → `fixtures/bad-legacy-type-key.md`.
- `codex-skills/**` (regenerated).

**Getting started (before Task 1):** on the feature branch, commit the three untracked planning docs first:
```bash
git add docs/plans/2026-07-19-skills-taxonomy-and-templates-design.md \
        docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md \
        docs/plans/2026-07-19-skills-taxonomy-and-templates-implementation.md
git commit -m "docs(skills): taxonomy + templates design, corpus matrix, implementation plan"
```

---

### Task 1: Shared skill-file iterator

**Files:**
- Create: `science/src/science_tool/skills_lint/discovery.py`
- Modify: `science/src/science_tool/skills_lint/lint.py:141`, `:206`; `science/src/science_tool/skills_lint/cli.py:66`
- Test: `science/tests/skills_lint/test_discovery.py`

**Interfaces:**
- Produces: `iter_skill_files(root: Path) -> Iterator[Path]` — sorted `*.md` under `root`, excluding any path whose posix form starts with `meta/templates/`; `INDEX.md` is included.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/skills_lint/test_discovery.py
from pathlib import Path

from science_tool.skills_lint.discovery import iter_skill_files


def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("---\nname: x\ndescription: y\nprovenance: internal\n---\n", encoding="utf-8")


def test_iter_skill_files_excludes_meta_templates_keeps_index(tmp_path: Path) -> None:
    for rel in (
        "INDEX.md", "data/SKILL.md", "meta/SKILL.md", "meta/skill-taxonomy.md",
        "meta/templates/router.md", "meta/templates/measurement-qa.md",
    ):
        _touch(tmp_path / rel)
    found = {p.relative_to(tmp_path).as_posix() for p in iter_skill_files(tmp_path)}
    assert "meta/templates/router.md" not in found
    assert "meta/templates/measurement-qa.md" not in found
    assert "INDEX.md" in found  # NOT excluded: the linter must inspect it
    assert {"data/SKILL.md", "meta/SKILL.md", "meta/skill-taxonomy.md"} <= found


def test_iter_skill_files_is_sorted(tmp_path: Path) -> None:
    for rel in ("b/SKILL.md", "a/SKILL.md", "INDEX.md"):
        _touch(tmp_path / rel)
    rels = [p.relative_to(tmp_path).as_posix() for p in iter_skill_files(tmp_path)]
    assert rels == sorted(rels)
```

- [ ] **Step 2: Run to verify failure** — `cd science && uv run --frozen pytest tests/skills_lint/test_discovery.py -q` → FAIL (`ModuleNotFoundError: …skills_lint.discovery`).

- [ ] **Step 3: Create the iterator**

```python
# science/src/science_tool/skills_lint/discovery.py
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

TEMPLATES_PREFIX = "meta/templates/"


def iter_skill_files(root: Path) -> Iterator[Path]:
    """Yield every skill-tree Markdown file, sorted, EXCLUDING authoring scaffolds
    under ``meta/templates/``. ``INDEX.md`` is intentionally included — the linter
    must inspect it (e.g. to reject ``archetype:`` on the index). Consumers apply
    their own structural-role filters after iterating."""
    for path in sorted(root.rglob("*.md")):
        if path.relative_to(root).as_posix().startswith(TEMPLATES_PREFIX):
            continue
        yield path
```

- [ ] **Step 4: Route the three scanners through it**

Add `from science_tool.skills_lint.discovery import iter_skill_files` to `lint.py` and `cli.py`. Replace the loop header `for path in sorted(root.rglob("*.md")):` with `for path in iter_skill_files(root):` at `lint.py:141` (in `check_index_coverage`), `lint.py:206` (in `check_skills`), and `cli.py:66` (in `build_dependency_views`).

- [ ] **Step 5: Run + lint** — `cd science && uv run --frozen pytest tests/skills_lint/test_discovery.py tests/skills_lint/test_lint.py tests/skills_lint/test_cli.py -q` → PASS; `uv run --frozen ruff check src/science_tool/skills_lint/discovery.py && uv run pyright` → clean.

- [ ] **Step 6: Commit** — `git add science/src/science_tool/skills_lint/discovery.py science/src/science_tool/skills_lint/lint.py science/src/science_tool/skills_lint/cli.py science/tests/skills_lint/test_discovery.py && git commit -m "feat(skills-lint): single skill-file iterator excluding meta/templates"`

---

### Task 2: Replace `type:` with `depth:` (crash-safe) + reconcile fixtures

**Files:**
- Modify: `science/src/science_tool/skills_lint/lint.py:60`, `:97-99`
- Modify: `skills/statistics/replicate-count-justification.md`
- Modify: `science/tests/skills_lint/fixtures/good-deep-reference.md`, `science/tests/skills_lint/fixtures/INDEX.md`; rename `fixtures/bad-invalid-type.md` → `fixtures/bad-legacy-type-key.md`
- Modify: `science/tests/skills_lint/test_lint.py` (existing tests at `:44`, `:49`, CLI test at `:126`) + new tests

**Interfaces:**
- Produces: `VALID_DEPTHS = {"standard", "deep-reference"}`; a present `type:` ⇒ `invalid-field`; a present `depth:` that is not a recognized string ⇒ `invalid-field`; absent `depth:` ⇒ OK.

- [ ] **Step 1: Reconcile the existing fixtures + tests + add the shared helper (these are the failing-first anchors)**

Edit `fixtures/good-deep-reference.md`: change `type: deep-reference` → `depth: deep-reference` (keep `provenance: internal`).
Rename `fixtures/bad-invalid-type.md` → `fixtures/bad-legacy-type-key.md` and change its frontmatter to `name: test-bad-legacy-type-key`, `description: Use when verifying the linter rejects the retired type key.`, and `type: deep-reference` (a formerly-valid value proving the **key** is now illegal). `git mv` it.
In `fixtures/INDEX.md`, replace `` `skills/bad-invalid-type.md` `` with `` `skills/bad-legacy-type-key.md` `` so the renamed fixture remains indexed and does not add an unrelated `missing-index-entry` finding.
Add the shared test helper once near the top of `test_lint.py` (below `FIXTURES`):
```python
def _write_leaf(tmp_path: Path, extra_fields: str) -> Path:
    path = tmp_path / "leaf.md"
    path.write_text(
        f"---\nname: x\ndescription: y\nprovenance: internal\n{extra_fields}---\n\n## Companion Skills\n",
        encoding="utf-8",
    )
    return path
```
In `test_lint.py`, update the two existing tests:
```python
def test_deep_reference_depth_is_valid() -> None:
    issues = check_frontmatter(FIXTURES / "good-deep-reference.md")
    assert issues == []


def test_legacy_type_key_is_rejected() -> None:
    issues = check_frontmatter(FIXTURES / "bad-legacy-type-key.md")
    assert len(issues) == 1
    assert issues[0].kind == "invalid-field"
    assert issues[0].field == "type"
```
In the CLI test around `:126`, change the referenced filename `bad-invalid-type.md` → `bad-legacy-type-key.md` (the `good-deep-reference.md` "not in output" assertion at `:132` stays — it is now clean via `depth:`).

- [ ] **Step 2: Add the crash-safe scalar tests**

```python
# append to test_lint.py — _write_leaf is the shared helper defined in Step 1
def test_depth_absent_defaults_standard(tmp_path: Path) -> None:
    assert [i for i in check_frontmatter(_write_leaf(tmp_path, "")) if i.field == "depth"] == []


def test_depth_deep_reference_is_valid(tmp_path: Path) -> None:
    assert [i for i in check_frontmatter(_write_leaf(tmp_path, "depth: deep-reference\n")) if i.field == "depth"] == []


def test_depth_unknown_value_is_invalid(tmp_path: Path) -> None:
    assert any(i.kind == "invalid-field" and i.field == "depth" for i in check_frontmatter(_write_leaf(tmp_path, "depth: shallow\n")))


def test_depth_null_is_invalid_not_crash(tmp_path: Path) -> None:
    assert any(i.kind == "invalid-field" and i.field == "depth" for i in check_frontmatter(_write_leaf(tmp_path, "depth: null\n")))


def test_depth_list_is_invalid_not_crash(tmp_path: Path) -> None:
    assert any(i.kind == "invalid-field" and i.field == "depth" for i in check_frontmatter(_write_leaf(tmp_path, "depth: [standard]\n")))
```

- [ ] **Step 3: Run to verify failure** — `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -q` → FAIL. Expected failure mode: the current code checks `type:` (not `depth:`), so the legacy-key test fails because `type: deep-reference` is still *accepted*, and the three invalid-`depth` tests fail because the expected `invalid-field` issue is simply **absent** (current code never inspects `depth`, so `null`/`[standard]` produce no issue rather than a crash — the crash-safety is a property of the Step-4 implementation, verified by these tests staying green after it lands).

- [ ] **Step 4: Implement (crash-safe)**

In `lint.py` replace `VALID_SKILL_TYPES = {"skill", "deep-reference"}` (line 60) with `VALID_DEPTHS = {"standard", "deep-reference"}`. Replace lines 97–99 with:
```python
    if "type" in parsed:
        issues.append(SkillIssue(path, "invalid-field", field="type", detail="'type' was renamed to 'depth'"))
    if "depth" in parsed and (not isinstance(parsed["depth"], str) or parsed["depth"] not in VALID_DEPTHS):
        issues.append(SkillIssue(path, "invalid-field", field="depth", detail=str(parsed["depth"])))
```

- [ ] **Step 5: Migrate the one corpus declaration** — in `skills/statistics/replicate-count-justification.md`, `type: deep-reference` → `depth: deep-reference`.

- [ ] **Step 6: Run + repo lint** — `cd science && uv run --frozen pytest tests/skills_lint/ -q` → PASS; `uv run science skills lint --root ../skills` → exit 0.

- [ ] **Step 7: Commit** — `git add -A science/tests/skills_lint/fixtures science/src/science_tool/skills_lint/lint.py skills/statistics/replicate-count-justification.md science/tests/skills_lint/test_lint.py && git commit -m "feat(skills-lint): rename type->depth (crash-safe, no alias); reconcile fixtures"`

---

### Task 3: Optional-but-validated `archetype:` (crash-safe)

**Files:**
- Modify: `science/src/science_tool/skills_lint/lint.py` (constants + `check_frontmatter`)
- Test: `science/tests/skills_lint/test_lint.py`

**Interfaces:**
- Consumes: `check_frontmatter`, `_write_leaf` (Task 2).
- Produces: `VALID_ARCHETYPES` (the six), `STRUCTURAL_FILENAMES = {"SKILL.md", "INDEX.md"}`; present-and-invalid (unknown string / `null` / list) ⇒ `invalid-field`; present on router/index ⇒ `invalid-field`; absent ⇒ OK.

- [ ] **Step 1: Write the failing tests**

```python
# append to test_lint.py
def test_archetype_absent_is_ok(tmp_path: Path) -> None:
    assert [i for i in check_frontmatter(_write_leaf(tmp_path, "")) if i.field == "archetype"] == []


def test_archetype_valid_is_ok(tmp_path: Path) -> None:
    assert [i for i in check_frontmatter(_write_leaf(tmp_path, "archetype: measurement-qa\n")) if i.field == "archetype"] == []


def test_archetype_unknown_is_invalid(tmp_path: Path) -> None:
    assert any(i.kind == "invalid-field" and i.field == "archetype" for i in check_frontmatter(_write_leaf(tmp_path, "archetype: mega-qa\n")))


def test_archetype_null_is_invalid(tmp_path: Path) -> None:
    assert any(i.kind == "invalid-field" and i.field == "archetype" for i in check_frontmatter(_write_leaf(tmp_path, "archetype: null\n")))


def test_archetype_list_is_invalid_not_crash(tmp_path: Path) -> None:
    assert any(i.kind == "invalid-field" and i.field == "archetype" for i in check_frontmatter(_write_leaf(tmp_path, "archetype: [measurement-qa]\n")))


def _write_named(tmp_path: Path, filename: str, fields: str) -> Path:
    path = tmp_path / filename
    path.write_text(f"---\nname: x\ndescription: y\n{fields}---\n\n## Companion Skills\n", encoding="utf-8")
    return path


def test_archetype_on_router_is_invalid(tmp_path: Path) -> None:
    p = _write_named(tmp_path, "SKILL.md", "provenance: internal\narchetype: practice-guide\n")
    assert any(i.kind == "invalid-field" and i.field == "archetype" for i in check_frontmatter(p))


def test_archetype_on_index_is_invalid(tmp_path: Path) -> None:
    p = _write_named(tmp_path, "INDEX.md", "archetype: normative-reference\n")
    assert any(i.kind == "invalid-field" and i.field == "archetype" for i in check_frontmatter(p))
```

- [ ] **Step 2: Run to verify failure** — `cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -k archetype -q` → FAIL.

- [ ] **Step 3: Implement**

Add constants after `VALID_DEPTHS`:
```python
VALID_ARCHETYPES = {
    "measurement-qa", "method-guide", "analysis-discipline",
    "normative-reference", "tool-guide", "practice-guide",
}
STRUCTURAL_FILENAMES = {"SKILL.md", "INDEX.md"}
```
In `check_frontmatter`, after the depth block and before `return issues`:
```python
    if "archetype" in parsed:
        archetype = parsed["archetype"]
        if path.name in STRUCTURAL_FILENAMES:
            issues.append(SkillIssue(path, "invalid-field", field="archetype", detail="leaf-only field; routers and INDEX derive structural role"))
        elif not isinstance(archetype, str) or archetype not in VALID_ARCHETYPES:
            issues.append(SkillIssue(path, "invalid-field", field="archetype", detail=str(archetype)))
```

- [ ] **Step 4: Run + lint** — `cd science && uv run --frozen pytest tests/skills_lint/ -q && uv run --frozen ruff check src/science_tool/skills_lint/lint.py && uv run pyright` → PASS/clean.

- [ ] **Step 5: Commit** — `git add science/src/science_tool/skills_lint/lint.py science/tests/skills_lint/test_lint.py && git commit -m "feat(skills-lint): optional-but-validated leaf archetype field"`

---

### Task 4: Behavioral scenarios — define + run no-doctrine baselines

Runs **before** any loadable doctrine leaf or template exists. The committed design and implementation plan already contain the intended doctrine, so filesystem absence alone does not protect the baseline: evaluation isolation is enforced by the dispatch contract below. Executed by the controller via fresh-context subagents; not pytest.

**Files:**
- Create: `docs/plans/2026-07-19-skills-taxonomy-behavioral-scenarios.md`

- [ ] **Step 1: Author the scenario definitions**

Write the three scenario families, each with an exact prompt and an acceptance criterion. Do **not** predict baseline behavior — it is measured.
- **S1 Classification:** paste the body of `skills/statistics/bias-vs-variance-decomposition.md` (no name/archetype) and ask "Which of these six archetypes is this — measurement-qa, method-guide, analysis-discipline, normative-reference, tool-guide, practice-guide — and why?" Acceptance: with-doctrine returns `analysis-discipline` via the verb test.
- **S2 Authoring:** "We need guidance for QA-ing a new assay modality. Draft the skill's section skeleton." Acceptance: with-doctrine produces the `measurement-qa` slot set.
- **S3 Create/extend/split:** (a) "add guidance on choosing the DE tool for bulk RNA-seq"; (b) "the frictionless skill also needs to teach the `frictionless validate` CLI end-to-end". Acceptance: with-doctrine applies the create/extend/split criteria so Request A separates DE-tool selection into a distinct `method-guide` by SPLIT/extraction or CREATE and never EXTENDs the `measurement-qa` leaf; Request B SPLITs the datapackage contract from the CLI tooling.

- [ ] **Step 2: Run isolated baselines (≥3 fresh-context repetitions per scenario arm)**

Dispatch each evaluator with `fork_turns="none"`. Its message contains only: (1) the scenario request, (2) the six archetype names for S1, and (3) the raw task-local artifact needed to answer. Paste the stripped `bias-vs-variance-decomposition.md` body for S1; S2 needs no repository artifact; paste the relevant existing skill bodies from `bulk-rnaseq-qa.md` and `frictionless.md` for S3. Do not include the design, implementation plan, doctrine, acceptance criterion, expected verdict, or prior evaluator outputs.

Tell every evaluator to answer solely from the supplied prompt, without inspecting the filesystem/repository or using tools. If an evaluator reads repository files or cites the design/plan, discard that run as contaminated and repeat it. Dispatch ≥3 independent evaluators per scenario, record each uncontaminated run's verbatim verdict, and note the spread (agreement/variance). Record **actual** behavior — do not write "wavers"; write what the runs did.

- [ ] **Step 3: Commit the baseline record** — `git add docs/plans/2026-07-19-skills-taxonomy-behavioral-scenarios.md && git commit -m "docs(skills): behavioral scenarios + no-doctrine baselines"`

---

### Task 5: Templates — conformance tests (failing-first) + exact template files

**Files:**
- Create: `skills/meta/templates/{router,measurement-qa,method-guide,analysis-discipline,normative-reference,tool-guide,practice-guide}.md`
- Create: `science/tests/skills_lint/test_templates.py`

**Interfaces:**
- Consumes: `iter_skill_files` (Task 1) so the scaffolds are not linted in the real tree; `check_skills` for the instantiation check.
- Produces: seven scaffolds; a non-tautological conformance test whose heading lists are encoded independently.

- [ ] **Step 1: Write the conformance tests (independently-encoded heading lists)**

```python
# science/tests/skills_lint/test_templates.py
from pathlib import Path

import pytest

from science_tool.skills_lint.lint import check_skills

REPO = Path(__file__).resolve().parents[3]
TEMPLATES = REPO / "skills" / "meta" / "templates"

# Approved heading lists — the CONTRACT, encoded here, NOT derived from the files.
EXPECTED_HEADINGS = {
    "measurement-qa": ["Sources & ingestion/construction", "Pre-flight checklist", "QA metrics",
                       "Common failure modes", "Halt-On Conditions", "Minimum output package",
                       "Success test", "Companion Skills"],
    "method-guide": ["Applicability / non-applicability", "Estimand & assumptions", "Model/procedure choices",
                     "Fitting / execution", "Diagnostics", "Failure modes", "Outputs & reporting",
                     "Success test", "Companion Skills"],
    "analysis-discipline": ["Triggering condition", "Required reasoning / check / precommitment",
                            "Decision rule or reasoning criteria",
                            "Outcomes (pass / fail / indeterminate, or branch/threshold)",
                            "Halt / escalation", "Required evidence & artifacts", "Permitted reporting language",
                            "Success test", "Companion Skills"],
    "normative-reference": ["Scope", "Vocabulary / schema / enums", "Invariants", "Conformance rules",
                            "Examples", "Versioning / migration", "Invalid cases",
                            "Success test", "Companion Skills"],
    "tool-guide": ["Setup & version assumptions", "Command / API surface", "Failure handling",
                   "Rate limits (where relevant)", "Verification / smoke-test",
                   "Success test", "Companion Skills"],
    "practice-guide": ["When to apply", "Workflow steps", "Judgment rules", "Quality criteria",
                       "Common pitfalls", "Outputs", "Success test", "Companion Skills"],
}
ROUTER_HEADINGS = ["Routing trigger", "Scope boundary", "Leaves", "Decision / compose order",
                   "Parent & neighbors", "Success test", "Companion Skills"]


def _headings(text: str) -> list[str]:
    return [ln[3:].strip() for ln in text.splitlines() if ln.startswith("## ")]


@pytest.mark.parametrize("archetype", sorted(EXPECTED_HEADINGS))
def test_template_headings_match_contract(archetype: str) -> None:
    text = (TEMPLATES / f"{archetype}.md").read_text(encoding="utf-8")
    assert _headings(text) == EXPECTED_HEADINGS[archetype]


def test_router_template_headings_match_contract() -> None:
    text = (TEMPLATES / "router.md").read_text(encoding="utf-8")
    assert _headings(text) == ROUTER_HEADINGS


def _body_of(template_text: str) -> str:
    """Return everything after the template's own frontmatter block."""
    end = template_text.find("\n---\n", 3)
    assert end != -1, "template has no closing frontmatter delimiter"
    return template_text[end + len("\n---\n"):]


@pytest.mark.parametrize("archetype", sorted(EXPECTED_HEADINGS))
def test_instance_from_template_passes_full_linter(archetype: str, tmp_path: Path) -> None:
    """Instantiate a leaf from the ACTUAL template file: keep its real body,
    swap only the placeholder frontmatter for a valid block, and prove FULL
    check_skills conformance (not a hand-picked subset of checks)."""
    body = _body_of((TEMPLATES / f"{archetype}.md").read_text(encoding="utf-8"))
    leaf_rel = f"{archetype}-example.md"
    (tmp_path / leaf_rel).write_text(
        f"---\nname: example-{archetype}\ndescription: Use when testing {archetype}.\n"
        f"archetype: {archetype}\nprovenance: internal\n---\n{body}",
        encoding="utf-8",
    )
    (tmp_path / "INDEX.md").write_text(
        "---\nname: idx\ndescription: index\n---\n\n"
        f"# Index\n\n- [`{leaf_rel}`]({leaf_rel})\n\n## Companion Skills\n\n- none\n",
        encoding="utf-8",
    )
    issues = [i for i in check_skills(tmp_path) if i.path.as_posix() == leaf_rel]
    assert issues == [], [i.to_json() for i in issues]
```

Note: the templates deliberately use **inline-code** references (`` `../INDEX.md` ``, `` `<leaf-a>.md` ``) rather than markdown links, so a body retained verbatim carries no live relative links for `check_relative_links` to resolve against the temp tree. If a future template introduces a real `[text](target)` link, this test will surface it as a genuine finding — that is the point of running full `check_skills`.

- [ ] **Step 2: Run to verify failure** — `cd science && uv run --frozen pytest tests/skills_lint/test_templates.py -q` → FAIL (`FileNotFoundError` — templates absent). This is the failing-first observation.

- [ ] **Step 3: Author the seven templates (exact contents below)**

Write each file **verbatim** (frontmatter placeholders model the real contract; the `##` headings must exactly match the contract encoded in Step 1).

`skills/meta/templates/router.md`:
```markdown
---
name: <subject>
description: Use when <the analysis phase this subtree governs> is in scope. Routes to the leaves below.
provenance: internal
---

# <Subject> Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when <the task class> is in scope, before loading any leaf.

## Scope boundary

<One sentence naming exactly what this subtree covers and what it excludes.>

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| `<leaf-a>.md` | <specific trigger> | <when it does not apply> |
| `<leaf-b>.md` | <specific trigger> | <when it does not apply> |

## Decision / compose order

<If leaves combine, the order to apply them; otherwise: "Leaves are independent.">

## Parent & neighbors

- Parent index: `../INDEX.md`
- Neighboring routers: `<../other/SKILL.md>`

## Success test

Representative in-scope tasks route to the correct leaf (or the correct compose order when leaves combine) without any methodology being read from this router.

## Companion Skills

- `../INDEX.md` — the skill index.
```

`skills/meta/templates/measurement-qa.md`:
```markdown
---
name: <subject>-<operation>-qa
description: Use when ingesting or QA-reviewing <this data product>.
archetype: measurement-qa
provenance: internal
---

# <Data Product> QA

Answers: is this observed or derived measurement trustworthy for inference?

## Sources & ingestion/construction

<Where the data comes from and how it is ingested or constructed.>

## Pre-flight checklist

- [ ] <check 1>
- [ ] <check 2>

## QA metrics

| Metric | Passing range | Meaning of failure |
|---|---|---|
| <metric> | <range> | <what a failure invalidates> |

## Common failure modes

- <failure mode → symptom → what it invalidates>

## Halt-On Conditions

- <condition under which analysis must stop until resolved>

## Minimum output package

    <qa-output-dir>/
      summary.md
      metrics.tsv

## Success test

Does the produced QA package contain the named files, and does the summary state which Halt-On Conditions were evaluated?

## Companion Skills

- `../INDEX.md` — the skill index.
```

`skills/meta/templates/method-guide.md`:
```markdown
---
name: <subject>-<models>
description: Use when selecting or fitting <this model family>.
archetype: method-guide
provenance: internal
---

# <Model Family>

Answers: which model/procedure applies here, and how do I fit and diagnose it?

## Applicability / non-applicability

Use when <...>. Do not use when <...>.

## Estimand & assumptions

<What is being estimated; the assumptions required.>

## Model/procedure choices

| Option | Use when |
|---|---|
| <model> | <situation> |

## Fitting / execution

<How to fit; solver/estimator notes.>

## Diagnostics

<Model-specific diagnostics and what a failure means.>

## Failure modes

- <failure → consequence>

## Outputs & reporting

<What to report, including uncertainty.>

## Success test

Are applicability and assumptions stated, is the model/procedure selection justified, and are model-specific diagnostics present with a verdict downgrade when they fail?

## Companion Skills

- `../INDEX.md` — the skill index.
```

`skills/meta/templates/analysis-discipline.md`:
```markdown
---
name: <subject>-<discipline>
description: Use when <the triggering situation>, before interpreting a result.
archetype: analysis-discipline
provenance: internal
---

# <Discipline>

Answers: regardless of the method, what reasoning/check/precommitment must hold before the result may be interpreted?

## Triggering condition

<When this discipline fires.>

## Required reasoning / check / precommitment

<The commitment or check to carry out before interpretation.>

## Decision rule or reasoning criteria

<The rule or criteria that determine the outcome.>

## Outcomes (pass / fail / indeterminate, or branch/threshold)

<The possible outcomes; if locking is conditional on an analyst-chosen threshold/branch, state it.>

## Halt / escalation

<When to stop or escalate.>

## Required evidence & artifacts

<What must be recorded.>

## Permitted reporting language

<How results may and may not be worded.>

## Success test

Was the required reasoning/precommitment carried out before interpretation, and does the conclusion follow from it — mechanically where a locked table applies, by the stated criteria otherwise?

## Companion Skills

- `../INDEX.md` — the skill index.
```

`skills/meta/templates/normative-reference.md`:
```markdown
---
name: <subject>-<artifact>-schema
description: Use when authoring or validating <this artifact type>.
archetype: normative-reference
provenance: internal
---

# <Artifact> Contract

Answers: what must this artifact mean or contain?

## Scope

<Which artifact type this governs.>

## Vocabulary / schema / enums

<Fields, enums, required/optional.>

## Invariants

<Rules that must always hold.>

## Conformance rules

<How conformance is determined.>

## Examples

<A conformant example.>

## Versioning / migration

<How the contract is versioned and migrated.>

## Invalid cases

<Examples that must be rejected and why.>

## Success test

Is there an explicit conformance check against the vocabulary/invariants — mechanical (lint/validate) where available, an itemized checklist otherwise?

## Companion Skills

- `../INDEX.md` — the skill index.
```

`skills/meta/templates/tool-guide.md`:
```markdown
---
name: <subject>-<operation>
description: Use when operating <this tool/service> for <purpose>.
archetype: tool-guide
provenance: internal
---

# <Subject> <Operation>

Answers: how do I operate this specific product, library, service, or CLI?
Name the skill for the operation-on-subject it teaches, not for the tool
(e.g. `variant-calling`, not `gatk`) — doctrine forbids tool-based names.

## Setup & version assumptions

<Install, version pin, environment. If externally sourced, replace provenance with: sources: [<registered-id>].>

## Command / API surface

<The commands/API calls that matter.>

## Failure handling

<Common failures and their fixes.>

## Rate limits (where relevant)

<Throughput limits, backoff; "none" if not applicable.>

## Verification / smoke-test

<A representative operation to run, and how to confirm it worked.>

## Success test

Does the skill complete and verify a representative operation end-to-end, including recovery from a common failure?

## Companion Skills

- `../INDEX.md` — the skill index.
```

`skills/meta/templates/practice-guide.md`:
```markdown
---
name: <subject>-<practice>
description: Use when <carrying out this cross-cutting activity>.
archetype: practice-guide
provenance: internal
---

# <Practice>

Answers: how do I carry out this cross-cutting activity well?

## When to apply

<The situations that call for this practice.>

## Workflow steps

1. <step>
2. <step>

## Judgment rules

<The judgment calls and how to make them.>

## Quality criteria

<What good output looks like.>

## Common pitfalls

- <pitfall → correction>

## Outputs

<What the practice produces.>

## Success test

Did the agent carry out the cross-cutting practice according to its workflow, judgment rules, and quality criteria?

## Companion Skills

- `../INDEX.md` — the skill index.
```

- [ ] **Step 4: Run to verify GREEN + confirm the exclusion holds**

`cd science && uv run --frozen pytest tests/skills_lint/test_templates.py -q` → PASS (headings match; each instance passes full `check_skills`).
`cd science && uv run science skills lint --root ../skills` → exit 0 (the `meta/templates/**` scaffolds are excluded, so their placeholder frontmatter raises nothing).

- [ ] **Step 5: Commit** — `git add skills/meta/templates/ science/tests/skills_lint/test_templates.py && git commit -m "feat(skills): six archetype templates + router profile (conformance-tested)"`

---

### Task 6: The `meta/` skill — router + two doctrine leaves + INDEX

**Files:**
- Create: `skills/meta/SKILL.md`, `skills/meta/skill-taxonomy.md`, `skills/meta/skill-authoring.md`
- Modify: `skills/INDEX.md`

**Interfaces:**
- Consumes: `archetype:`/`depth:`/provenance validation (Tasks 2–3); the templates (Task 5); the design doc as the exact prose source.
- Produces: three linted, indexed skills. `meta/SKILL.md` `name: skill-development` (exact — Task 7's codex check asserts it).

- [ ] **Step 1: Author `skills/meta/SKILL.md` from the router contract**

Use the fixed `name: skill-development`, `provenance: internal`, and a description whose activation surface explicitly covers creating, **extending**, classifying, naming, organizing, and reviewing a Science skill. Keep the router navigation-only and include these `##` sections in order:

1. `Routing trigger` — explicitly includes extending as well as create/classify/name/organize/split/review.
2. `Scope boundary`.
3. `Leaves` — routes classification/frontmatter work to `skill-taxonomy.md` and create/**extend**/name/place/split work to `skill-authoring.md`.
4. `Decision / compose order` — taxonomy first, then authoring when both apply; otherwise load only the matching leaf.
5. `Parent & neighbors` — links the parent index and neighboring subject routers.
6. `Templates` — optional extra navigation to the seven scaffolds.
7. `Success test`.
8. `Companion Skills`.

This outline is the canonical router-profile contract from the approved design. Do not add substantive methodology to the router.

- [ ] **Step 2: Author `skills/meta/skill-taxonomy.md`**

Frontmatter verbatim:
```yaml
---
name: skill-taxonomy
description: Use when classifying a skill, choosing its archetype, or applying the skill frontmatter contract. Defines the axes, the six leaf archetypes, and the metadata contract.
archetype: normative-reference
provenance: internal
---
```
Body: `# Skill Taxonomy`, then the complete `normative-reference` contract in this `##` order:

1. `Scope`.
2. `Vocabulary / schema / enums` — preserve the five-axis table and all six archetype definitions, including their answers, classification tests, slots, and success tests.
3. `Invariants` — preserve the exactly-one-primary-archetype rule, orthogonal-axis model, and navigation-only router profile.
4. `Conformance rules` — preserve the executable frontmatter contract and the mechanical/itemized checking boundary.
5. `Examples` — use only examples already ratified by the design and current doctrine.
6. `Versioning / migration` — preserve stable-name, `type:`→`depth:`, optional-archetype, and deferred-migration doctrine.
7. `Invalid cases` — include unknown, `null`, list, **and mapping** values for scalar `archetype:`/`depth:` fields.
8. `Success test`.
9. `Companion Skills` — link the authoring leaf and parent index.

The design and existing doctrine remain the prose source. Organize them under the declared archetype slots; do not invent taxonomy policy.

- [ ] **Step 3: Author `skills/meta/skill-authoring.md`**

Frontmatter verbatim:
```yaml
---
name: skill-authoring
description: Use when creating, naming, placing, splitting, or extending a Science skill. The decision procedure, naming and placement rules, and template-eligibility doctrine.
archetype: practice-guide
provenance: internal
---
```
Body: `# Skill Authoring`, then the complete `practice-guide` contract in this `##` order:

1. `When to apply`.
2. `Workflow steps` — classify, choose CREATE/EXTEND/SPLIT, name, place, and author from the matching template; extract methodology when making a router.
3. `Judgment rules` — preserve naming, placement, CREATE/EXTEND/SPLIT, router/hub, and template-eligibility doctrine under subsections.
4. `Quality criteria` — express the approved doctrine as observable artifact criteria.
5. `Common pitfalls` — preserve the existing three pitfalls.
6. `Outputs` — record the decision and produce the typed leaf or navigation-only router, stable name, and placement outcome.
7. `Success test`.
8. `Companion Skills` — link the taxonomy leaf and parent index.

Derive workflow, quality, output, and success-test wording only from the approved design and preserved doctrine; do not add new authoring policy.

- [ ] **Step 4: Update `skills/INDEX.md` — add entries AND broaden the intro**

Make exactly these two verbatim replacements so the index is no longer described as only analysis-readiness.

Replace the frontmatter description line:
```
description: Source of truth for finding Science methodology skills during analysis-readiness planning.
```
with:
```
description: Source of truth for finding Science methodology skills and the skill-authoring doctrine.
```

Replace the opening paragraph:
```
Use this index before planning or running a data analysis. Load only the leaves
that match the current task. Do not load every leaf "just in case"; that defeats
progressive disclosure.
```
with:
```
Use this index before planning or running a data analysis, and when creating,
naming, or organizing a skill. Load only the leaves that match the current task.
Do not load every leaf "just in case"; that defeats progressive disclosure.
```

Then add, after "Core Analysis Checks":
```markdown
## Meta / Skill Authoring

- `skill-development`: `skills/meta/SKILL.md`
- `skill-taxonomy`: `skills/meta/skill-taxonomy.md`
- `skill-authoring`: `skills/meta/skill-authoring.md`
```

- [ ] **Step 5: Lint** — `cd science && uv run science skills lint --root ../skills` → exit 0 (provenance + `## Companion Skills` present on all three; archetypes valid; INDEX covers them; relative links resolve).

- [ ] **Step 6: Commit** — `git add skills/meta/SKILL.md skills/meta/skill-taxonomy.md skills/meta/skill-authoring.md skills/INDEX.md && git commit -m "feat(skills): meta skill-development router + taxonomy/authoring doctrine leaves"`

---

### Task 7: Codex mirror — meta companion + templates copy

**Files:**
- Modify: `science/src/science_tool/codex_skills.py:17` (COMPANION_SKILLS), `:159-192` (`_generate_companion_skill`)
- Modify: `codex-skills/**` (regenerated)
- Test: `science/tests/test_codex_skills.py` (new test + fix the two hard-coded two-companion assumptions)

**Interfaces:**
- Consumes: `skills/meta/SKILL.md` (name `skill-development`), the sibling doctrine leaves, and `meta/templates/**` (Tasks 5–6).
- Produces: a generated `science-skill-development` skill bundling the two leaves + a `templates/` subdir; an INDEX row for it.

- [ ] **Step 1: Write/adjust tests (failing-first)**

Add a new test and de-hard-code the two-companion assumptions:
```python
# in test_codex_skills.py — add imports:
from science_tool.codex_skills import COMPANION_SKILLS, companion_to_skill_name

def test_meta_skill_is_mirrored_with_templates(tmp_path: Path) -> None:
    generated = generate_codex_skills(ROOT, tmp_path)
    assert "science-skill-development" in generated
    skill_dir = generated["science-skill-development"].parent
    assert (skill_dir / "skill-taxonomy.md").is_file()
    assert (skill_dir / "skill-authoring.md").is_file()
    assert (skill_dir / "templates" / "router.md").is_file()
    assert (skill_dir / "templates" / "measurement-qa.md").is_file()
    assert (skill_dir / "templates" / "practice-guide.md").is_file()

def test_meta_skill_row_in_index(tmp_path: Path) -> None:
    generate_codex_skills(ROOT, tmp_path)
    text = (tmp_path / "INDEX.md").read_text(encoding="utf-8")
    assert "| `skill-development` | `science-skill-development` | `science-skill-development/SKILL.md` | `skills/meta/SKILL.md` |" in text
```
In `test_generate_codex_skills_emits_all_commands`, replace both `command_count + 2` (lines 73–74) with `command_count + len(COMPANION_SKILLS)`.
In `test_generated_command_skills_embed_cli_compatibility_gate`, replace the hard-coded skip set (line 749) with a derived one:
```python
    companion_names = {companion_to_skill_name(c.canonical_name) for c in COMPANION_SKILLS}
    for name, path in generated.items():
        if name in companion_names:
            continue
        ...
```

- [ ] **Step 2: Run to verify failure** — `cd science && uv run --frozen pytest tests/test_codex_skills.py -q` → FAIL because the new meta-skill and meta-index-row assertions fail. The de-hard-coded count and companion-skip assertions remain green with the current two-entry `COMPANION_SKILLS`.

- [ ] **Step 3: Register the companion**

```python
COMPANION_SKILLS: tuple[CompanionSkill, ...] = (
    CompanionSkill("research-methodology", Path("skills/research/SKILL.md")),
    CompanionSkill("scientific-writing", Path("skills/writing/SKILL.md")),
    CompanionSkill("skill-development", Path("skills/meta/SKILL.md")),
)
```

- [ ] **Step 4: Copy the templates subdir**

In `_generate_companion_skill`, after the sibling-`*.md` copy loop (after line 175) and before building `skill_text`:
```python
    templates_dir = source_path.parent / "templates"
    if templates_dir.is_dir():
        shutil.copytree(templates_dir, skill_dir / "templates")
```
(The skill dir was just `rmtree` + recreated, so the target does not pre-exist.)

- [ ] **Step 5: Regenerate the committed mirror** — `cd science && uv run python ../scripts/generate_codex_skills.py`; stage the regenerated tree.

- [ ] **Step 6: Run + lint** — `cd science && uv run --frozen pytest tests/test_codex_skills.py -q` → PASS incl. `test_committed_codex_skills_match_fresh_generation`; `uv run --frozen ruff check src/science_tool/codex_skills.py && uv run pyright` → clean.

- [ ] **Step 7: Commit** — `git add science/src/science_tool/codex_skills.py science/tests/test_codex_skills.py codex-skills/ && git commit -m "feat(codex): mirror meta skill-development with bundled templates"`

---

### Task 8: Behavioral scenarios — with-doctrine runs + verdicts

The doctrine now exists (Task 6). Run the with-doctrine arms and compare to the Task-4 baselines. Executed by the controller via subagents.

**Files:**
- Modify: `docs/plans/2026-07-19-skills-taxonomy-behavioral-scenarios.md`
- Modify (only if a repair is needed): `skills/meta/skill-taxonomy.md` and/or `skills/meta/skill-authoring.md`, and the regenerated `codex-skills/` tree

- [ ] **Step 1: Run with-doctrine arms (≥3 repetitions per scenario)**

For each scenario S1–S3, dispatch ≥3 evaluators with `fork_turns="none"`. Give them the same task-local prompt/artifact used by the corresponding baseline plus the complete `skill-taxonomy.md` and `skill-authoring.md` contents. Do not include the design, implementation plan, acceptance criterion, expected verdict, prior outputs, or any baseline result. Tell evaluators to answer solely from supplied context without inspecting the filesystem/repository or using tools; discard and repeat any contaminated run. Record the uncontaminated verdicts verbatim.

- [ ] **Step 2: Record outcomes + acceptance verdict**

Append a results table per scenario (baseline vs with-doctrine) and a verdict. **Acceptance:** with-doctrine reaches the designed outcome on all three scenarios: S1 → 3/3 `analysis-discipline`, with consistent doctrine-specific reasoning that applies the audit/justify verb boundary, method-independent pre-interpretation gate, and contract slots; S2 → 3/3 complete `measurement-qa` slot sets, including an explicit disposition for each halt condition and a fixed minimum output-package tree; S3 Request A → separate DE-tool selection into a distinct `method-guide` by SPLIT/extracting the existing method content or creating a distinct leaf, never extending the `measurement-qa` leaf; S3 Request B → SPLIT. The required baseline differences are S1's doctrine-specific reasoning consistency and S2's structural convergence.

If a scenario fails acceptance, the doctrine leaf is under-specified. Do NOT weaken the acceptance criterion. Repair via this exact loop, because a doctrine leaf under `skills/meta/` is mirrored into `codex-skills/` and editing the leaf alone staled the mirror (this exact class of miss shipped once before):
1. Edit the leaf (`skill-taxonomy.md` and/or `skill-authoring.md`).
2. `cd science && uv run science skills lint --root ../skills` → exit 0.
3. `cd science && uv run python ../scripts/generate_codex_skills.py` to regenerate the mirror.
4. `cd science && uv run --frozen pytest tests/test_codex_skills.py -q` → PASS (incl. `test_committed_codex_skills_match_fresh_generation`).
5. Re-run the failing scenario's with-doctrine arm (≥3 repetitions) from fresh context.
Only once the scenario passes: stage and commit the leaf, the regenerated `codex-skills/`, and the updated results together (Step 3).

- [ ] **Step 3: Commit** — stage the results doc (plus, if Step 2 repaired a leaf, the leaf files and the regenerated `codex-skills/`): `git add docs/plans/2026-07-19-skills-taxonomy-behavioral-scenarios.md skills/meta/ codex-skills/ && git commit -m "docs(skills): with-doctrine behavioral results + acceptance verdict"`

---

## Final verification (after all tasks)

```bash
cd science && uv run --frozen pytest -q                                 # full suite green
cd science && uv run --frozen ruff check . && uv run pyright            # clean, 0/0/0
cd science && uv run science skills lint --root ../skills               # exit 0
cd science && uv run python ../scripts/generate_codex_skills.py && git status --porcelain codex-skills/   # no diff
```

## Self-Review (author checklist — completed)

- **Spec coverage:** iterator (T1) · depth+fixtures (T2) · archetype (T3) · baselines-before-doctrine (T4) · templates + conformance/full-linter tests (T5) · meta router+leaves+INDEX-broaden (T6) · codex meta+templates+de-hard-coded counts (T7) · with-doctrine + acceptance (T8). Every design success-criterion and every reviewer finding maps to a step.
- **Failing-first:** T4 baselines precede all doctrine; T5 conformance tests are observed RED before the templates exist; T7 codex tests observed RED before wiring; T2/T3 unit tests RED before impl.
- **No placeholders:** all linter/codex/test steps carry exact code; the seven templates are given verbatim; the two doctrine leaves are specified by complete archetype-contract outlines grounded in the committed design prose.
- **Crash-safety:** `depth`/`archetype` validation is presence-and-`isinstance(str)` explicit; `null`/list/mapping tests cover scalar-field rejection.
- **Type/name consistency:** `iter_skill_files`, `VALID_DEPTHS`, `VALID_ARCHETYPES`, `STRUCTURAL_FILENAMES`, `COMPANION_SKILLS`/`companion_to_skill_name`, the six archetype spellings, and the three fixed names are used identically wherever referenced.
