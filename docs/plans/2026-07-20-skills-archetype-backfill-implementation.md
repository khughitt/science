# Skills Archetype Backfill + Required-Archetype Ratchet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Classify every corpus skill leaf with `archetype:` per the ratified corpus matrix, and make the field required-on-leaves at ERROR severity, so the taxonomy contract becomes enforced rather than documented.

**Architecture:** Three tasks in failing-first order. First resolve the one `unresolved` classification (`research-package-rendering` → `practice-guide`) and record why, since the backfill cannot mechanically complete without it. Then ratchet the linter so a leaf missing `archetype:` is an ERROR — observed failing against the real corpus (34 findings), which is the evidence the check can fail. Then backfill all 34 leaves until the linter returns to exit 0.

**Tech Stack:** Python ≥3.11, `uv`, pytest, the `skills_lint` package (`science/src/science_tool/skills_lint/`), the generated `codex-skills/` mirror.

## Global Constraints

- **No AI-attribution trailers or footers** on commits, PRs, or comments — no `Co-Authored-By`, no "Generated with Claude Code".
- **No "legacy"/"compatibility" layers.** `archetype:` is required from the start; there is no WARN phase and no grandfathering escape hatch.
- Composition over inheritance; **explicit over defensive; fail early over silent fallback**.
- No `Unified` prefix on component names.
- All Python tooling runs **from `science/`** — there is no root `pyproject.toml`. Commands: `cd science && uv run --frozen pytest`, `uv run ruff check`, `uv run pyright`. Test directories are not type-checked.
- **`codex-skills/` is a git-tracked generated mirror.** Any edit under `skills/` requires rerunning `scripts/generate_codex_skills.py` and committing the regenerated tree, or `test_committed_codex_skills_match_fresh_generation` fails.
- Use `~/d/` in docs and code paths, never `/home/keith/d/` or `/mnt/ssd/Dropbox/`.
- **Never tune content or metadata to silence a check.** If a classification does not fit, escalate — do not edit the skill's prose to make an archetype apply.
- The **six archetypes are closed** for this phase: `measurement-qa`, `method-guide`, `analysis-discipline`, `normative-reference`, `tool-guide`, `practice-guide`. Do not add a seventh.

## Certified preconditions (verified on this branch at `ff6e140d`)

- Leaf roster: **34 leaves** on disk (`skills/**/*.md` excluding `INDEX.md`, `SKILL.md`, `skills/meta/**`), matching the matrix's 34 rows **exactly** (diff clean).
- **0 of 34** corpus leaves currently carry `archetype:`.
- 7 non-meta routers (`SKILL.md`) + `skills/INDEX.md` are structural and must **not** carry `archetype:` (already enforced as `invalid-field`).
- All 34 leaves have a `provenance:` or `sources:` line inside their frontmatter block (100% anchor coverage), and **no** leaf has a wrapped/multi-line `description:`. This makes the backfill insertion point deterministic.
- Baseline: `science skills lint --root ../skills` exits **0**; `pytest tests/skills_lint/ tests/test_codex_skills.py` is **green (179 passed)**.

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md` | Ratifying classification; records the `research-package-rendering` ruling | 1 |
| `skills/meta/skill-authoring.md` | Authoring doctrine; gains the archetype-eligibility trip-wire | 1 |
| `science/src/science_tool/skills_lint/lint.py` | Adds `missing-archetype` at ERROR for non-structural files | 2 |
| `science/tests/skills_lint/test_lint.py` | Ratchet tests (leaf required, structural exempt, no cascade) | 2 |
| `skills/**/*.md` (34 leaves) | Gain `archetype:` per the matrix | 3 |
| `codex-skills/**` | Regenerated mirror | 1, 3 |

---

### Task 1: Resolve `research-package-rendering` + record the ruling

**Files:**
- Modify: `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md` (the leaf's row, its boundary-case bullet, the archetype tally)
- Modify: `skills/meta/skill-authoring.md` (template-eligibility section — add trip-wire)
- Modify: `codex-skills/**` (regenerated)

**Interfaces:**
- Produces: `research/research-package-rendering.md` is classified **`practice-guide`**. Task 3 consumes this as row 34 of its backfill table.

**The ruling (do not re-derive — apply it):** `research-package-rendering` is a software *implementation* guide (routing pattern, manifest prebuild, loader, component patterns, plus a TS/React reference implementation). It is not `normative-reference` — that contract belongs to its sibling `research-package-spec.md`, which it explicitly builds on as "layer 1". It is not `tool-guide` — it names remark/rehype and vega-embed as interchangeable ("or similar"), so no single tool is being operated; the other five tool-guides teach *operating a tool*, this teaches *building a component*. It is not `method-guide` — those slots are estimand/fitting/diagnostics, which is analysis-shaped.

It is classified `practice-guide` because (a) minting a seventh `implementation-guide` archetype would violate the eligibility rule shipped in `skill-authoring.md`, which requires **at least two** concrete targets sharing a content contract and success test — population here is one; and (b) the practice-guide slots do map: "When to Use" → when-to-apply; the five pattern sections → workflow steps; the `/src` route-specificity rule, the graceful permalink fallback, and RFC 4180 handling → judgment rules; the natural-systems reference implementation → outputs.

This is an acknowledged force-fit, recorded as such.

- [ ] **Step 1: Update the matrix row**

In `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md`, replace the `research-package-rendering` table row:
```
| research/research-package-rendering.md | leaf | — | unresolved | research-infra | standard | internal | a working `/src` provenance route wired to a research package | migration-candidate; provisional practice-guide vs tool-guide (reference TS/React impl) vs normative-reference (cell-type→component contract) | y — resolve dominant contract at migration; NOT the basis for practice-guide |
```
with:
```
| research/research-package-rendering.md | leaf | — | practice-guide | research-infra | standard | internal | a working `/src` provenance route wired to a research package | resolved 2026-07-20 (acknowledged force-fit); NOT the basis for practice-guide eligibility; phase-3 relocation candidate — a web-app implementation guide living under research/ | y — revisit if a second build-a-component leaf appears |
```

- [ ] **Step 2: Replace the boundary-case bullet**

Replace the `research-package-rendering` bullet in the "Boundary cases (adjudicated)" section:
```
- **`research-package-rendering` → migration-candidate**: contract is genuinely ambiguous (internal engineering recipe vs tool-guide vs normative-reference). Downgraded so it is **not** the justification for the practice-guide archetype. Resolve dominant contract at migration.
```
with:
```
- **`research-package-rendering` → practice-guide** (resolved 2026-07-20, acknowledged force-fit): a software *implementation* guide — the corpus's only build-a-component leaf. Not `normative-reference` (that is its sibling `research-package-spec.md`, which it builds on as "layer 1"); not `tool-guide` (remark/rehype and vega-embed are named as interchangeable, so no single tool is operated — the other five tool-guides operate a tool, this one builds a component); not `method-guide` (estimand/fitting/diagnostics slots are analysis-shaped). Classified `practice-guide` because minting a seventh `implementation-guide` archetype would violate the two-target eligibility rule at a population of one, and the practice-guide slots do map (When to Use → when-to-apply; the five pattern sections → workflow steps; route-specificity, permalink fallback, and RFC 4180 handling → judgment rules; the natural-systems reference implementation → outputs). It remains **not** the basis for practice-guide eligibility — that still rests on the two hub extractions. Trip-wire recorded in `skills/meta/skill-authoring.md`; flagged as a phase-3 relocation candidate.
```

- [ ] **Step 3: Update the tally table**

In the "Archetype tally (leaves)" table, change the `practice-guide` and `unresolved` rows:
```
| practice-guide | 0 clean leaves today | (population is trapped in hubs — see extraction candidates) |
| unresolved | 1 | research-package-rendering (migration-candidate — see boundary column) |
```
to:
```
| practice-guide | 1 | research-package-rendering (resolved 2026-07-20, acknowledged force-fit — see boundary cases; further population is trapped in hubs, see extraction candidates) |
| unresolved | 0 | — |
```

**Do NOT modify the "Earns-a-template check" section.** The practice-guide eligibility argument must continue to rest on the two hub-extraction targets (`writing/SKILL.md` and `research/SKILL.md`), not on this leaf. Changing it would make the archetype self-justifying.

- [ ] **Step 4: Add the trip-wire to `skills/meta/skill-authoring.md`**

In the **Template-eligibility rule** section, append this paragraph verbatim after the existing rule text:
```markdown
**Open trip-wire (recorded 2026-07-20).** `research/research-package-rendering.md` is classified `practice-guide` as an acknowledged force-fit: it is a software *implementation* guide (build-a-component), which none of the six archetypes model well, and its population of one is below the two-target threshold above. If a second build-a-component leaf appears, the pair becomes eligible and a seventh `implementation-guide` archetype must be reconsidered rather than force-fitted again.
```

- [ ] **Step 5: Regenerate the Codex mirror** — `skills/meta/` is mirrored, so the edit in Step 4 stales `codex-skills/`:

```bash
cd science && uv run python ../scripts/generate_codex_skills.py
```

- [ ] **Step 6: Verify** — nothing structural changed, so the linter must still be clean and the mirror test green:

```bash
cd science && uv run science skills lint --root ../skills          # expect exit 0
cd science && uv run --frozen pytest tests/test_codex_skills.py -q  # expect PASS
```

- [ ] **Step 7: Commit**

```bash
git add docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md skills/meta/skill-authoring.md codex-skills/
git commit -m "docs(skills): resolve research-package-rendering as practice-guide + eligibility trip-wire"
```

---

### Task 2: Ratchet — `archetype:` required on leaves at ERROR

**Files:**
- Modify: `science/src/science_tool/skills_lint/lint.py` (`IssueKind` literal ~line 21, severity constant near `MISSING_PROVENANCE_SEVERITY` line 35, `check_frontmatter` archetype block lines 108–112)
- Modify: `science/tests/skills_lint/test_lint.py` (new tests; `_write_leaf` helper already exists)

**Interfaces:**
- Consumes: `VALID_ARCHETYPES`, `STRUCTURAL_FILENAMES`, `MISSING_PROVENANCE_SEVERITY` (as the pattern to mirror), `_write_leaf(tmp_path, extra_fields)` — all already present.
- Produces: `MISSING_ARCHETYPE_SEVERITY: Severity = "error"`; a new `IssueKind` member `"missing-archetype"`. A non-structural file with no `archetype:` key yields exactly one `missing-archetype` issue at ERROR. `SKILL.md` and `INDEX.md` yield none.

**Note on the intentional red window:** after this task, `science skills lint --root ../skills` exits 1 with 34 findings. That is the point — it is the evidence the check can fail on the real corpus. Task 3 closes it. Do not backfill any corpus file in this task.

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/skills_lint/test_lint.py` (the `_write_leaf` helper is already defined near `FIXTURES`):

```python
def test_leaf_without_archetype_is_error(tmp_path: Path) -> None:
    issues = [i for i in check_frontmatter(_write_leaf(tmp_path, "")) if i.kind == "missing-archetype"]
    assert len(issues) == 1
    assert issues[0].severity == "error"
    assert issues[0].field == "archetype"


def test_leaf_with_archetype_has_no_missing_archetype(tmp_path: Path) -> None:
    path = _write_leaf(tmp_path, "archetype: measurement-qa\n")
    assert [i for i in check_frontmatter(path) if i.kind == "missing-archetype"] == []


def test_router_without_archetype_is_exempt(tmp_path: Path) -> None:
    path = tmp_path / "SKILL.md"
    path.write_text(
        "---\nname: x\ndescription: y\nprovenance: internal\n---\n\n## Companion Skills\n",
        encoding="utf-8",
    )
    assert [i for i in check_frontmatter(path) if i.kind == "missing-archetype"] == []


def test_index_without_archetype_is_exempt(tmp_path: Path) -> None:
    path = tmp_path / "INDEX.md"
    path.write_text(
        "---\nname: x\ndescription: y\n---\n\n## Companion Skills\n",
        encoding="utf-8",
    )
    assert [i for i in check_frontmatter(path) if i.kind == "missing-archetype"] == []


def test_broken_yaml_does_not_cascade_to_missing_archetype(tmp_path: Path) -> None:
    path = tmp_path / "leaf.md"
    path.write_text("---\nname: [unclosed\n---\n\n## Companion Skills\n", encoding="utf-8")
    kinds = {i.kind for i in check_frontmatter(path)}
    assert kinds == {"invalid-yaml"}
```

- [ ] **Step 2: Run to verify failure**

```bash
cd science && uv run --frozen pytest tests/skills_lint/test_lint.py -q
```
Expected: FAIL. `test_leaf_without_archetype_is_error` fails because no `missing-archetype` issue is produced (the field is currently optional); the three exemption tests and the cascade test pass vacuously today but must stay green after Step 3.

- [ ] **Step 3: Implement**

In `lint.py`, add `"missing-archetype",` to the `IssueKind` `Literal` (alongside `"missing-provenance"`).

Add the severity constant immediately below `MISSING_PROVENANCE_SEVERITY: Severity = "error"` (line 35):
```python
MISSING_ARCHETYPE_SEVERITY: Severity = "error"
```

In `check_frontmatter`, replace the archetype block (lines 108–112):
```python
    if "archetype" in parsed:
        archetype = parsed["archetype"]
        if path.name in STRUCTURAL_FILENAMES:
            issues.append(SkillIssue(path, "invalid-field", field="archetype", detail="leaf-only field; routers and INDEX derive structural role"))
        elif not isinstance(archetype, str) or archetype not in VALID_ARCHETYPES:
            issues.append(SkillIssue(path, "invalid-field", field="archetype", detail=str(archetype)))
```
with:
```python
    if "archetype" in parsed:
        archetype = parsed["archetype"]
        if path.name in STRUCTURAL_FILENAMES:
            issues.append(SkillIssue(path, "invalid-field", field="archetype", detail="leaf-only field; routers and INDEX derive structural role"))
        elif not isinstance(archetype, str) or archetype not in VALID_ARCHETYPES:
            issues.append(SkillIssue(path, "invalid-field", field="archetype", detail=str(archetype)))
    elif path.name not in STRUCTURAL_FILENAMES:
        issues.append(
            SkillIssue(
                path,
                "missing-archetype",
                field="archetype",
                detail="every leaf must declare exactly one recognized archetype",
                severity=MISSING_ARCHETYPE_SEVERITY,
            )
        )
```
The `elif` placement matters: it hangs off `if "archetype" in parsed`, so a file that declares the field is never also reported missing. The early returns above it mean a file with broken frontmatter reports only `invalid-yaml`/`missing-frontmatter` — no cascade.

- [ ] **Step 4: Run to verify pass**

```bash
cd science && uv run --frozen pytest tests/skills_lint/ -q            # expect PASS
cd science && uv run --frozen ruff check src/science_tool/skills_lint/lint.py && uv run pyright   # expect clean
```

- [ ] **Step 5: Observe the check failing on the real corpus (the evidence step)**

```bash
cd science && uv run science skills lint --root ../skills --format json > /tmp/ratchet-red.json; echo "exit=$?"
python3 -c "import json;d=json.load(open('/tmp/ratchet-red.json'));m=[i for i in d if i['kind']=='missing-archetype'];print('missing-archetype findings:',len(m))"
```
Expected: `exit=1` and **exactly 34** `missing-archetype` findings — one per corpus leaf, zero on routers or INDEX. If the count is not 34, stop and report: either the roster drifted or the structural exemption is wrong. Record the observed count in the commit message.

(`--format` accepts `text|json`; verified on this branch.)

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/skills_lint/lint.py science/tests/skills_lint/test_lint.py
git commit -m "feat(skills-lint): require archetype on every leaf at ERROR severity"
```

---

### Task 3: Backfill `archetype:` on all 34 corpus leaves

**Files:**
- Modify: the 34 leaf files listed in the mapping table below
- Modify: `codex-skills/**` (regenerated)

**Interfaces:**
- Consumes: the Task 1 ruling (`research-package-rendering` → `practice-guide`) and the Task 2 ratchet.
- Produces: `science skills lint --root ../skills` returns to exit 0.

**Insertion rule (deterministic — verified against all 34 files):** insert a single line `archetype: <value>` immediately **before** the first line inside the frontmatter block that begins with `provenance:` or `sources:`. Every leaf has exactly one such anchor, and no leaf has a wrapped `description:`, so this reproduces the template's field order (`name`, `description`, `archetype`, `provenance`/`sources`). Change nothing else in any file — no reformatting, no reordering, no prose edits.

**Mapping table — the classification is the matrix's, transcribe it exactly. Do not re-derive, and do not adjust a skill's content to fit its archetype.**

| # | path (under `skills/`) | archetype |
|---|---|---|
| 1 | `data/embeddings-manifold-qa.md` | `measurement-qa` |
| 2 | `data/expression/bulk-rnaseq-qa.md` | `measurement-qa` |
| 3 | `data/expression/microarray-qa.md` | `measurement-qa` |
| 4 | `data/expression/scrna-qa.md` | `measurement-qa` |
| 5 | `data/functional-genomics-qa.md` | `measurement-qa` |
| 6 | `data/genomics/copy-number-sv-qa.md` | `measurement-qa` |
| 7 | `data/genomics/mutational-signatures-and-selection.md` | `measurement-qa` |
| 8 | `data/genomics/somatic-mutation-qa.md` | `measurement-qa` |
| 9 | `data/protein-sequence-structure-qa.md` | `measurement-qa` |
| 10 | `data/proteomics-qa.md` | `measurement-qa` |
| 11 | `research/annotation-curation-qa.md` | `measurement-qa` |
| 12 | `statistics/bias-vs-variance-decomposition.md` | `analysis-discipline` |
| 13 | `statistics/causal-identification.md` | `analysis-discipline` |
| 14 | `statistics/estimator-certification.md` | `analysis-discipline` |
| 15 | `statistics/power-floor-acknowledgement.md` | `analysis-discipline` |
| 16 | `statistics/prereg-amendment-vs-fresh.md` | `analysis-discipline` |
| 17 | `statistics/prereg-defensive-instrumentation.md` | `analysis-discipline` |
| 18 | `statistics/replicate-count-justification.md` | `analysis-discipline` |
| 19 | `statistics/sensitivity-arbitration.md` | `analysis-discipline` |
| 20 | `statistics/bayesian-workflow.md` | `method-guide` |
| 21 | `statistics/compositional-data.md` | `method-guide` |
| 22 | `statistics/likelihood-model-comparison.md` | `method-guide` |
| 23 | `statistics/population-genetics-likelihood.md` | `method-guide` |
| 24 | `statistics/survival-and-hierarchical-models.md` | `method-guide` |
| 25 | `statistics/time-series-and-longitudinal-models.md` | `method-guide` |
| 26 | `data/sources/openalex.md` | `tool-guide` |
| 27 | `data/sources/pubmed.md` | `tool-guide` |
| 28 | `pipelines/marimo.md` | `tool-guide` |
| 29 | `pipelines/runpod.md` | `tool-guide` |
| 30 | `pipelines/snakemake.md` | `tool-guide` |
| 31 | `data/frictionless.md` | `normative-reference` |
| 32 | `research/proposition-schema.md` | `normative-reference` |
| 33 | `research/research-package-spec.md` | `normative-reference` |
| 34 | `research/research-package-rendering.md` | `practice-guide` |

Counts: measurement-qa 11 · analysis-discipline 8 · method-guide 6 · tool-guide 5 · normative-reference 3 · practice-guide 1 = **34**.

- [ ] **Step 1: Apply the backfill**

Edit each of the 34 files per the insertion rule. Note that `statistics/replicate-count-justification.md` (row 18) also carries `depth: deep-reference` — leave that line untouched; `archetype:` still goes immediately before the `provenance:`/`sources:` anchor.

- [ ] **Step 2: Verify every file got the right value**

```bash
cd "$(git rev-parse --show-toplevel)/skills" && for f in $(find . -name '*.md' ! -name 'INDEX.md' ! -name 'SKILL.md' ! -path './meta/*' | sed 's|^\./||' | sort); do
  printf '%s -> %s\n' "$f" "$(grep -m1 '^archetype:' "$f" | sed 's/^archetype: //')"
done
```
Expected: 34 lines, each matching the mapping table exactly, with no blanks. Cross-check the per-archetype counts (11/8/6/5/3/1).

- [ ] **Step 3: Verify the linter is green again**

```bash
cd science && uv run science skills lint --root ../skills; echo "exit=$?"
```
Expected: `exit=0`. A nonzero exit means a value is misspelled or an insertion landed outside the frontmatter block — fix the file, never the check.

- [ ] **Step 3b: Remove the red-window scaffolding (REQUIRED — the window is now closed)**

Task 2 left two temporary constructs in `science/tests/skills_lint/test_provenance_coverage_repo.py`. Both must go, or the repo permanently loses ERROR-detection for `missing-archetype` in its only automated gate.

1. Delete the `@pytest.mark.xfail(strict=True, reason="Task 2->3 red window: ...")` decorator on `test_corpus_has_no_error_severity_findings`. Leave the function body untouched — it is already the original unfiltered assertion. Because the marker is `strict`, leaving it in place after the backfill makes the suite FAIL with XPASS, so this step is mechanically forced rather than trusted to memory.
2. Delete `test_corpus_missing_archetype_count_is_known` in full (it asserts `len(missing) == 34`, which is now 0).
3. Drop the `import pytest` if nothing else in the file uses it.

Verify:
```bash
cd science && uv run --frozen pytest tests/skills_lint/test_provenance_coverage_repo.py -v
```
Expected: **2 passed, 0 xfailed, 0 xpassed**. Seeing `xpassed` means the marker is still there; seeing `xfailed` means the backfill did not actually close the corpus.

- [ ] **Step 4: Regenerate the Codex mirror**

The `research-methodology` companion bundle copies its sibling `research/*.md` files, so backfilling those leaves stales the mirror:
```bash
cd science && uv run python ../scripts/generate_codex_skills.py
```

- [ ] **Step 5: Full verification**

```bash
cd science && uv run --frozen pytest -q                              # full suite green
cd science && uv run --frozen ruff check . && uv run pyright         # clean
cd science && uv run science skills lint --root ../skills            # exit 0
cd science && uv run python ../scripts/generate_codex_skills.py && git status --porcelain ../codex-skills/   # no diff
```

- [ ] **Step 6: Commit**

```bash
git add skills/ codex-skills/
git commit -m "feat(skills): classify all 34 corpus leaves with archetype"
```

---

## Final verification (after all tasks)

```bash
cd science && uv run --frozen pytest -q                              # full suite green
cd science && uv run --frozen ruff check . && uv run pyright         # clean, 0/0/0
cd science && uv run science skills lint --root ../skills; echo $?   # exit 0
cd science && uv run python ../scripts/generate_codex_skills.py && git status --porcelain ../codex-skills/   # no diff
```

Then confirm the ratchet still bites — a deliberately broken leaf must fail:
```bash
ROOT="$(git rev-parse --show-toplevel)"
cp "$ROOT/skills/data/proteomics-qa.md" /tmp/pq.bak
sed -i '/^archetype:/d' "$ROOT/skills/data/proteomics-qa.md"
cd "$ROOT/science" && uv run science skills lint --root ../skills; echo "exit=$? (expect 1)"
cp /tmp/pq.bak "$ROOT/skills/data/proteomics-qa.md" && rm /tmp/pq.bak
cd "$ROOT/science" && uv run science skills lint --root ../skills; echo "exit=$? (expect 0)"
```
This is the acceptance evidence that the contract is enforced, not merely declared. Confirm `git status --porcelain skills/` is empty afterward.

## Self-Review (author checklist — completed)

- **Spec coverage:** the ruling + both recorded notes (T1) · required-archetype ERROR ratchet with structural exemption and no-cascade (T2) · all 34 leaves classified (T3) · mirror regenerated in both tasks that touch `skills/`. The user's two decisions — `require` from the start, and resolving `research-package-rendering` — each map to a task.
- **Failing-first:** T2's tests are observed RED before the implementation, and the ratchet is then observed failing on the *real corpus* (34 findings, exit 1) before T3 closes it. The final verification re-breaks a leaf to prove the check still bites.
- **No placeholders:** every edit is given as exact old→new text or exact code; the backfill carries all 34 rows explicitly rather than "classify per the matrix".
- **Scope discipline:** hub extraction, reorganization, and renaming are explicitly *not* in this plan — they are phases 2 and 3.
- **Type/name consistency:** `missing-archetype`, `MISSING_ARCHETYPE_SEVERITY`, `VALID_ARCHETYPES`, `STRUCTURAL_FILENAMES`, `_write_leaf`, and the six archetype spellings are used identically wherever referenced, and match the names already in `lint.py`.
- **Known trap avoided:** T1 Step 3 explicitly forbids editing the "Earns-a-template check" section, so practice-guide eligibility does not become self-justifying via the leaf it was told not to rest on.
