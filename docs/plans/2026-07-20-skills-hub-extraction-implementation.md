# Skills Hub Extraction (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the router invariant for `skills/research/` and `skills/writing/` by extracting their embedded doctrine into four typed leaves, deduplicating the doctrine they share, and fixing the Codex generator so the resulting cross-directory links resolve correctly.

**Architecture:** Five sequential tasks. Task 1 is a pure toolkit fix that makes correct link rewriting possible (and closes six pre-existing danglers). Tasks 2 and 3 extract the two hubs — research first, because `writing/scientific-writing.md` links to a research leaf. Task 4 lands the cross-subject retargets and doctrine updates that need both hubs done. Task 5 is the acceptance sweep.

**Tech Stack:** Python 3.13, pytest, uv, ruff, pyright. Markdown skill corpus under `skills/`, generated mirror under `codex-skills/`.

**Design doc:** [`2026-07-20-skills-hub-extraction-design.md`](2026-07-20-skills-hub-extraction-design.md). Read it before Task 2 — it fixes every destination and the full outcome contract.

## Global Constraints

- Work in the worktree at `.claude/worktrees/skills-hub-extraction` on branch `skills-hub-extraction`. Verify with `git branch --show-current` before every commit.
- All Python commands run from `science/`. There is **no root `pyproject.toml`**.
- No AI-attribution trailers or footers on commits. No `Co-Authored-By`, no generated-with footer.
- No "legacy"/"compatibility" layers. No `Unified` prefix. Composition over inheritance; explicit over defensive; fail early rather than silent fallback.
- Use `~/d/` in docs and code paths, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **Any change under `skills/` requires regenerating `codex-skills/` in the same commit.** `codex-skills/` is a git-tracked generated mirror guarded by `test_committed_codex_skills_match_fresh_generation`. Regenerate with `uv run python ../scripts/generate_codex_skills.py` from `science/`.
- **Routers and `INDEX.md` must not declare `archetype:`.** Structural role stays derived from filename. Every leaf must declare exactly one of: `measurement-qa`, `method-guide`, `analysis-discipline`, `normative-reference`, `tool-guide`, `practice-guide`.
- **Pre-existing failures, not caused by this branch:** 4 ruff errors in `science/tests/test_numeric_binding.py`, 7 pyright errors in `prose_lint.py`, both reproducible at base `1feb088c`. The bar is **no new findings**, not a clean global run.
- Prose that **moves** is specified by exact source line range — copy it verbatim, do not paraphrase. Prose that must be **authored** (template slots with no source text) is pinned verbatim in this plan. Implementers invent neither.
- Never bare `git stash` / `git stash pop` — the stash stack is shared across worktrees.

---

### Task 1: Generator — classify links by emitted artifacts, rewrite copied resources

Pure toolkit change. No `skills/` edits. Closes six pre-existing dangling links in the committed mirror, then adds a guard so they cannot return. This is deliberately sweep-then-ratchet: fix first, ratchet second.

**Files:**
- Modify: `science/src/science_tool/codex_skills.py:160-212`
- Test: `science/tests/test_codex_skills.py`
- Regenerate: `codex-skills/` (contents change — six links get rewritten)

**Interfaces:**
- Produces: `_resource_paths(source_path: Path) -> list[Path]` — the single predicate for "which files become bundled resources", used by both the copy loop and the link rewriter.
- Produces: `_companion_link_targets(repo_root: Path) -> dict[Path, str]` — maps a repo-relative `skills/...` path to its emitted location fragment.
- Produces: `_rewrite_companion_body_links(body: str, repo_root: Path) -> str` — **signature change**, gains `repo_root`. Task 3 relies on this being data-driven from `COMPANION_SKILLS`.

- [ ] **Step 1: Write the failing tests**

Add to `science/tests/test_codex_skills.py`:

```python
def test_rewrites_link_to_companion_source_leaf(tmp_path: Path) -> None:
    generate_codex_skills(ROOT, tmp_path)
    rendering = (tmp_path / "science-research-methodology" / "research-package-rendering.md").read_text(
        encoding="utf-8"
    )
    assert "../science-scientific-writing/SKILL.md" in rendering
    assert "../writing/SKILL.md" not in rendering


def test_rewrites_link_to_non_companion_directory(tmp_path: Path) -> None:
    generate_codex_skills(ROOT, tmp_path)
    curation = (tmp_path / "science-research-methodology" / "annotation-curation-qa.md").read_text(
        encoding="utf-8"
    )
    assert "../../skills/statistics/sensitivity-arbitration.md" in curation
    assert "](../statistics/sensitivity-arbitration.md)" not in curation


def test_no_dangling_relative_links_in_generated_tree(tmp_path: Path) -> None:
    generate_codex_skills(ROOT, tmp_path)
    dangling: list[str] = []
    for path in sorted(tmp_path.rglob("*.md")):
        for target in re.findall(r"]\((\.\.?/[^)]+)\)", path.read_text(encoding="utf-8")):
            if not (path.parent / target).exists():
                dangling.append(f"{path.relative_to(tmp_path)} -> {target}")
    assert dangling == []
```

Add `import re` to the test file's imports if absent.

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd science && uv run --frozen pytest tests/test_codex_skills.py -k "rewrites_link or no_dangling" -v
```

Expected: all three FAIL. The two rewrite tests fail because copied resources are never rewritten. `test_no_dangling_relative_links_in_generated_tree` fails listing exactly six entries (`../data/frictionless.md` ×2, `../pipelines/snakemake.md` ×2, `../statistics/sensitivity-arbitration.md`, `../writing/SKILL.md`).

- [ ] **Step 3: Implement**

In `science/src/science_tool/codex_skills.py`, replace the resource-copy loop at lines 173-176 with:

```python
    for resource_path in _resource_paths(source_path):
        text = resource_path.read_text(encoding="utf-8")
        (skill_dir / resource_path.name).write_text(
            _rewrite_companion_body_links(text, repo_root), encoding="utf-8"
        )
```

Update the body-rewrite call at line 183:

```python
    body = _rewrite_companion_body_links(body, repo_root)
```

Replace `_rewrite_companion_body_links` (lines 200-212) with:

```python
def _resource_paths(source_path: Path) -> list[Path]:
    """Markdown files bundled as resources beside a companion's SKILL.md.

    Excludes both the directory's router (SKILL.md) and the companion's own
    source file, which is emitted as the companion's SKILL.md rather than as a
    resource. This is the single definition of the emitted resource set: the
    copy loop and the link rewriter must agree, or links resolve to files that
    were never copied.
    """
    return [
        path
        for path in sorted(source_path.parent.glob("*.md"))
        if path.name != "SKILL.md" and path != source_path
    ]


def _companion_link_targets(repo_root: Path) -> dict[Path, str]:
    """Map a repo-relative skills/ path to where generation actually emits it."""
    targets: dict[Path, str] = {}
    for companion in COMPANION_SKILLS:
        skill_name = companion_to_skill_name(companion.canonical_name)
        targets[companion.source_path] = f"../{skill_name}/SKILL.md"
        for resource_path in _resource_paths(repo_root / companion.source_path):
            relative = companion.source_path.parent / resource_path.name
            targets[relative] = f"../{skill_name}/{resource_path.name}"
    return targets


def _rewrite_companion_body_links(body: str, repo_root: Path) -> str:
    targets = _companion_link_targets(repo_root)

    def replace_link(match: re.Match[str]) -> str:
        directory, filename = match.group(1), match.group(2)
        emitted = targets.get(Path("skills") / directory / filename)
        if emitted is not None:
            return emitted
        return f"../../skills/{directory}/{filename}"

    return re.sub(r"\.\./([a-z0-9-]+)/([A-Za-z0-9._-]+\.md)", replace_link, body)
```

A path absent from `targets` is emitted nowhere and resolves to its canonical source. That covers a directory with no companion **and** a router excluded from its own companion's bundle — the case Task 3 creates.

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd science && uv run --frozen pytest tests/test_codex_skills.py -v
```

Expected: all PASS, including the pre-existing `test_generate_codex_skills_emits_companion_methodology_skills`.

- [ ] **Step 5: Regenerate the mirror**

```bash
cd science && uv run python ../scripts/generate_codex_skills.py && cd .. && git diff --stat codex-skills/
```

Expected: three files change (`annotation-curation-qa.md`, `research-package-rendering.md`, `research-package-spec.md` under `science-research-methodology/`), six link rewrites total.

- [ ] **Step 6: Verify the full suite and linters**

```bash
cd science && uv run --frozen pytest -q; echo "PYTEST_EXIT=$?"
cd science && uv run ruff check; uv run pyright
```

Expected: `PYTEST_EXIT=0`. Ruff shows only the 4 known `test_numeric_binding.py` errors; pyright only the 7 known `prose_lint.py` errors. Capture the exit code **before** any pipe — `cmd | tail` reports `tail`'s status, not pytest's.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/codex_skills.py science/tests/test_codex_skills.py codex-skills/
git commit -m "fix(codex): rewrite links in copied resources and classify by emitted artifacts"
```

---

### Task 2: Extract `skills/research/` into three leaves

**Files:**
- Create: `skills/research/literature-evaluation.md`, `skills/research/citation-discipline.md`, `skills/research/proposition-graph-reasoning.md`
- Modify: `skills/research/SKILL.md` (reduce to router), `skills/research/proposition-schema.md` (extend + retarget), `skills/research/annotation-curation-qa.md:111` (retarget)
- Regenerate: `codex-skills/`

**Interfaces:**
- Produces: leaves named `research-literature-evaluation`, `research-citation-discipline`, `research-proposition-graph-reasoning`. Task 3 and Task 4 link to these exact filenames.

- [ ] **Step 1: Create `literature-evaluation.md`**

Frontmatter:

```markdown
---
name: research-literature-evaluation
description: Use when reviewing literature, assessing source quality, or synthesizing findings across papers, before writing durable claims.
archetype: practice-guide
provenance: internal
---
```

Body follows `skills/meta/templates/practice-guide.md` slot-for-slot. Move verbatim from `skills/research/SKILL.md`: Source Hierarchy (L30-46) → **Workflow steps**; Confidence Calibration (L48-56) and Evaluating Sources (L70-78) → **Judgment rules**; Cross-Checking Key Facts (L58-68) → **Workflow steps** (final step); Synthesis, Not Just Summarization (L80-88) → **Quality criteria**.

**When to apply** and **Outputs** are authored — pin verbatim:

```markdown
## When to apply

Before writing any durable output that rests on external sources: a paper
summary, a topic synthesis, a background section, or an evidence line citing
literature. Also when auditing claims someone else sourced.

## Outputs

A source set with each item's tier recorded (primary, preprint, secondary), the
claims each source backs, and explicit `[UNVERIFIED]` marks on anything that
could not be cross-checked.
```

**Common pitfalls** is authored — pin verbatim:

```markdown
## Common pitfalls

- Writing from model memory without searching → treat recall as orientation for search terms, never as a citable source.
- Citing a paper read only at the abstract level → mark conclusions abstract-level and make no durable evidence update.
- Reporting agreement across sources that share an origin → check whether the sources are independent before counting them as convergent.
- Summarizing each source in turn and stopping → synthesis requires naming the disagreements and the gaps, not just the contents.
```

- [ ] **Step 2: Create `citation-discipline.md`**

```markdown
---
name: research-citation-discipline
description: Use when authoring or validating citations, source pointers, and bibliography references in project documents.
archetype: normative-reference
provenance: internal
---
```

Follows `skills/meta/templates/normative-reference.md`. Merge verbatim: `research/SKILL.md` Citation Discipline (L161-168) and `writing/SKILL.md` Citation Format (L64-73). The two overlap on `[@AuthorYear]`, `references.bib`, and the `cite:` vs `paper:` distinction — state each rule **once**.

**Invariants**, **Examples**, and **Invalid cases** are authored — pin verbatim:

```markdown
## Invariants

- Every BibTeX key used in a document has a corresponding entry in `papers/references.bib`.
- `cite:AuthorYear` in `source_refs` backs a bibliography entry; `paper:AuthorYear` links a project paper note. They are not interchangeable.
- A factual claim carries either a citation or an annotation token. Never neither.

## Examples

- Inline: `[@Smith2020]`
- Multiple: `[@Smith2020; @Jones2021]`
- With page: `[@Smith2020, p. 42]`
- Narrative: `Smith et al. [@Smith2020] found that...`
- Frontmatter: `source_refs: ["cite:Smith2020"]`

## Invalid cases

1. `[@Smith2020]` with no matching entry in `papers/references.bib` — the key must resolve.
2. `paper:Smith2020` in `source_refs` where only a bibliography entry exists — use `cite:` unless a project paper note exists.
3. An unsourced factual claim with no `[UNVERIFIED]` or `[MISSING_CITATION]` token — silence is not a permitted state.
4. A citation to a source read only at abstract level, presented as backing a specific numerical result.
```

**Versioning / migration**: state that this leaf supersedes the citation rules formerly duplicated in `research/SKILL.md` and `writing/SKILL.md`, extracted 2026-07-20.

- [ ] **Step 3: Create `proposition-graph-reasoning.md`**

```markdown
---
name: research-proposition-graph-reasoning
description: Use when interpreting or updating the project's own proposition graph — assessing hypothesis support, reading dashboard signals, or deciding where to direct effort.
archetype: analysis-discipline
provenance: internal
---
```

Follows `skills/meta/templates/analysis-discipline.md`. Move verbatim from `research/SKILL.md`: Working with Hypotheses (L90-102) → **Required reasoning / check / precommitment**; Recognizing Unmigrated Projects (L130-143) → **Triggering condition** and the `migration-limited` row; Using Dashboard Summaries (L145-159) → **Decision rule** inputs.

**Outcomes** is the decided contract — pin verbatim from the design doc:

```markdown
## Outcomes

Outcomes are **non-exclusive flagged conditions**, not a ladder and not a
verdict. Any number may hold at once. Each licenses a prioritization action;
none licenses a claim about how well-supported a proposition is.

| Condition | Fires when | Licenses |
|---|---|---|
| `migration-limited` | hypothesis prose carries the reasoning; scalar `confidence` is doing the epistemic work; propositions are not decomposed; evidence is not attached as support/dispute | prefer creating or refining propositions over editing prose; state that interpretation quality is bounded by migration state |
| `contested` | support and dispute lines both bear on the proposition | read the disagreement before summarizing; do not report a direction of effect as settled |
| `single-source-fragile` | support traces to one source, or to lines sharing an `independence_group` | treat support as fragile; prioritize independent replication |
| `lacks-empirical-support` | support is present but no `empirical_data` line bears on it | name the evidence kind when reporting; prioritize empirical work |
| `high-uncertainty` | the proposition sits in a neighborhood the dashboard reports as high-uncertainty | prioritize reading, replication, or model cleanup here |

**No flagged condition is not certification.** The dashboard reports only over
what has been *recorded*; silence is equally consistent with adequate support
and with nothing having been entered. An instrument that cannot distinguish
those two states cannot certify either, so the absence of a signal licenses
proceeding — and nothing more. It must never be written up as adequate,
sufficient, or well-supported. There is deliberately no `adequate` outcome.

**Unevaluated is a distinct state.** Dashboard summaries are conditional on
`knowledge/graph.trig` existing. When it does not, the last four conditions
cannot be evaluated at all, and that must be recorded as unevaluated — never
collapsed into "no flagged condition." `migration-limited` remains assessable
from the entity files alone.
```

**Permitted reporting language** is authored — pin verbatim:

```markdown
## Permitted reporting language

- Permitted: "supports", "disputes", "leaves unresolved", "is consistent with", "single-source", "contested".
- Forbidden without a flagged-condition basis: "confirms", "proves", "validates", "establishes", "well-supported", "adequate".
- Forbidden always: reporting the absence of flagged conditions as positive evidence of support.
```

**Halt / escalation** — move from L141-143 verbatim: call out that the project still needs migration work when that affects interpretation quality.

**Required evidence & artifacts** is authored — pin verbatim:

```markdown
## Required evidence & artifacts

Record, on the interpretation or synthesis entity that consumes the reasoning:
which conditions fired, which could not be evaluated and why (typically a
missing `knowledge/graph.trig`), and the dashboard command and its output if
one was run.
```

- [ ] **Step 4: Reduce `skills/research/SKILL.md` to a router**

Rewrite following `skills/meta/templates/router.md`. Keep `name: research-methodology`, keep `provenance: internal`, **do not add `archetype:`**. Keep the description verbatim (`codex_skills.py` copies it into the companion and a test asserts its text). Keep the framing paragraph at L11-19 (skeptical proposition-centric model + the INDEX pointer) — that is scope, not methodology.

The Leaves table gains four rows. "Annotation and Curation" (L121-128) becomes the `annotation-curation-qa.md` row's "Load when" text — a table row, not a retained prose section. Delete every extracted section. `Project Awareness` (L170-180) and `Template Usage` (L185-187) move to Task 3's writing leaf — delete them here and hand the text to Task 3.

- [ ] **Step 5: Extend and retarget `proposition-schema.md`**

Add an `## Evidence Types` section. Do **not** copy `research/SKILL.md` L106-119 verbatim — that list is written in the `_evidence` alias form. State the canonical tokens from `science/model/src/science_model/reasoning.py:134-139` — `empirical_data`, `benchmark`, `simulation`, `literature`, `expert_judgment`, `negative_result` — note that the `_evidence` suffix is an accepted authoring alias stripped at the model boundary (`docs/user-guide/evidence-lines.md:57-62`), and carry the `negative_result` caveat from `evidence-lines.md:53-55`: it is accepted for compatibility but usually better understood as a result pattern, with the line's stance, role, and scope carrying the meaning. Keep the hub's rule that these must not be collapsed into a generic "computational evidence" label.

Retarget L9-11: `SKILL.md` → `./literature-evaluation.md` (source hierarchy, evaluating sources) and `./citation-discipline.md` (citation discipline).

- [ ] **Step 6: Retarget `annotation-curation-qa.md:111`**

Replace the single line with two:

```markdown
- [`literature-evaluation.md`](literature-evaluation.md) - source hierarchy and source-quality assessment for literature-derived claims.
- [`citation-discipline.md`](citation-discipline.md) - citation and source-pointer conformance.
```

- [ ] **Step 7: Lint, regenerate, verify, commit**

```bash
cd science && uv run science skills lint; echo "LINT_EXIT=$?"
cd science && uv run python ../scripts/generate_codex_skills.py
cd science && uv run --frozen pytest -q; echo "PYTEST_EXIT=$?"
```

Expected: `LINT_EXIT=0`, `PYTEST_EXIT=0`.

```bash
git add skills/research/ codex-skills/
git commit -m "refactor(skills): extract research hub into literature-evaluation, citation-discipline, proposition-graph-reasoning"
```

---

### Task 3: Extract `skills/writing/` and transfer the `scientific-writing` identifier

The leaf creation, the router rename, and the `COMPANION_SKILLS` mapping change **must land in one commit**. Generation raises `ValueError` on a name mismatch (`codex_skills.py:163-165`), so any intermediate state fails.

**Files:**
- Create: `skills/writing/scientific-writing.md`
- Modify: `skills/writing/SKILL.md` (router + `name:` change), `science/src/science_tool/codex_skills.py:18`, `science/tests/test_codex_skills.py:82-99`
- Regenerate: `codex-skills/`

- [ ] **Step 1: Create `skills/writing/scientific-writing.md`**

```markdown
---
name: scientific-writing
description: Scientific writing conventions for research documents. This skill should be used whenever writing or editing research documents, background sections, paper summaries, hypothesis descriptions, overview documents, or any content in the doc/ directory. Also use when the user asks to write, draft, revise, or edit any scientific or technical prose, or when creating content that will be part of a research project's documentation.
archetype: practice-guide
provenance: internal
---
```

The description is transferred verbatim from the current router — it is the discovery surface for this behavior and must not be re-worded.

Follows `skills/meta/templates/practice-guide.md`. Move verbatim from the current `writing/SKILL.md`: Voice and Tone (L24-30) and Hedging Guide (L32-40) → **Judgment rules**; Document Structure (L42-49), Formatting Conventions (L89-95), Length Guidelines (L97-103) → **Quality criteria**; Connecting to the Project (L75-87) merged with `research/SKILL.md`'s Project Awareness (L170-180) → **Workflow steps** (first step: check the project before writing); `research/SKILL.md`'s Template Usage (L185-187) → **Workflow steps**.

Replace Annotation Tokens (L51-62) with a pointer — pin verbatim:

```markdown
When a claim cannot carry an in-line citation, mark it with one of the four
annotation tokens defined in `docs/conventions/annotation-tokens.md`:
`[UNVERIFIED]`, `[MISSING_CITATION]`, `[SPECULATION]`, `[INACCESSIBLE]`. That
document is the normative owner of the vocabulary and the validator behavior;
do not restate the definitions here.
```

Delete Citation Format (L64-73) — it lives in `research/citation-discipline.md` now. Link it under **Companion Skills** as `../research/citation-discipline.md`.

**Common pitfalls** and **Outputs** are authored — pin verbatim:

```markdown
## Common pitfalls

- Hedging language that outruns the evidence → match the hedge to the tier in the table, not to how confident the sentence sounds.
- Writing a document with no connection to a hypothesis or question → check the project before drafting, not after.
- Restating the annotation-token definitions locally → point at `docs/conventions/annotation-tokens.md`; a second copy drifts.
- Passive throat-clearing openings → lead with the point in the first paragraph.

## Outputs

A document conforming to its framework template, with every substantive claim
either cited or annotated, hedging matched to evidence strength, and explicit
links to the hypotheses, questions, or propositions it bears on.
```

- [ ] **Step 2: Reduce `skills/writing/SKILL.md` to a router**

Follow `skills/meta/templates/router.md`. Change `name: scientific-writing` → `name: writing`. Author a new router description (the old one transferred to the leaf) — pin verbatim:

```markdown
description: Use when scientific prose for a research project is in scope. Routes to the writing leaves below.
```

Do **not** add `archetype:`. Leaves table: one row for `scientific-writing.md`. Under **Parent & neighbors**, link `../research/SKILL.md`. Under **Companion Skills**, link `../research/citation-discipline.md`. Delete the "No leaves currently" note and every doctrine section.

- [ ] **Step 3: Update the companion mapping**

In `science/src/science_tool/codex_skills.py:18`:

```python
    CompanionSkill("scientific-writing", Path("skills/writing/scientific-writing.md")),
```

No other generator change is needed — Task 1's `_companion_link_targets` derives everything from `COMPANION_SKILLS`, so `skills/writing/SKILL.md` now falls through to `../../skills/writing/SKILL.md` automatically.

- [ ] **Step 4: Update the codex tests**

In `science/tests/test_codex_skills.py`, update the assertion at line 91 to the new source path and **add** the destination assertion that item 7 of acceptance requires:

```python
    assert "Adapted from canonical Science skill `skills/writing/scientific-writing.md`." in writing_skill


def test_research_router_neighbor_link_points_at_writing_router(tmp_path: Path) -> None:
    generate_codex_skills(ROOT, tmp_path)
    research_skill = (tmp_path / "science-research-methodology" / "SKILL.md").read_text(encoding="utf-8")
    assert "../../skills/writing/SKILL.md" in research_skill
    assert "../science-scientific-writing/SKILL.md" not in research_skill


def test_companion_source_leaf_is_not_also_a_resource(tmp_path: Path) -> None:
    generate_codex_skills(ROOT, tmp_path)
    assert not (tmp_path / "science-scientific-writing" / "scientific-writing.md").exists()
```

`test_research_router_neighbor_link_points_at_writing_router` is the case a link-existence check passes while being wrong: under a parent-directory model the link resolves to the scientific-writing leaf. Assert the destination, not resolvability.

- [ ] **Step 5: Run tests to verify the new ones fail**

```bash
cd science && uv run --frozen pytest tests/test_codex_skills.py -k "neighbor_link or not_also_a_resource" -v
```

Expected: FAIL before Steps 1-3 are applied. If Steps 1-3 are already applied, they PASS — in that case verify by reverting `codex_skills.py:18` alone and confirming generation raises `ValueError: Companion skill name mismatch`.

- [ ] **Step 6: Lint, regenerate, verify, commit**

```bash
cd science && uv run science skills lint; echo "LINT_EXIT=$?"
cd science && uv run python ../scripts/generate_codex_skills.py
cd science && uv run --frozen pytest -q; echo "PYTEST_EXIT=$?"
```

Expected: both exit 0. `codex-skills/science-scientific-writing/SKILL.md` now carries the leaf's content, and `codex-skills/science-scientific-writing/scientific-writing.md` does **not** exist.

```bash
git add skills/writing/ science/src/science_tool/codex_skills.py science/tests/test_codex_skills.py codex-skills/
git commit -m "refactor(skills): extract writing hub and transfer scientific-writing identifier to the leaf"
```

---

### Task 4: Cross-subject retargets, index, and doctrine

Everything that needed both hubs extracted.

**Files:**
- Modify: `skills/data/sources/openalex.md:145`, `skills/data/sources/pubmed.md:126`, `skills/research/research-package-rendering.md:82`, `skills/INDEX.md`, `skills/meta/skill-taxonomy.md`, `skills/meta/skill-authoring.md:41`, `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md`
- Regenerate: `codex-skills/`

- [ ] **Step 1: Split the three cross-subject references**

Each names two methodologies now in different leaves. Replace one line with two.

`skills/data/sources/openalex.md:145` and `skills/data/sources/pubmed.md:126` — note the depth is `../../`:

```markdown
- [`../../research/citation-discipline.md`](../../research/citation-discipline.md) - citation and source-pointer conformance.
- [`../../writing/scientific-writing.md`](../../writing/scientific-writing.md) - project-awareness checks before writing.
```

`skills/research/research-package-rendering.md:82`:

```markdown
- [`../writing/scientific-writing.md`](../writing/scientific-writing.md) - narrative conventions for rendered prose.
- [`citation-discipline.md`](citation-discipline.md) - citation conventions for rendered prose.
```

- [ ] **Step 2: Update `skills/INDEX.md`** — four operations:

1. Under **Core Analysis Checks**, remap `scientific-writing` from `skills/writing/SKILL.md` to `skills/writing/scientific-writing.md`.
2. Under **Core Analysis Checks**, add `- \`writing\`: \`skills/writing/SKILL.md\`` for the router.
3. Under **Curation and Evidence** (which already holds `research-annotation-curation-qa`), add:

```markdown
- `research-literature-evaluation`: `skills/research/literature-evaluation.md`
- `research-citation-discipline`: `skills/research/citation-discipline.md`
- `research-proposition-graph-reasoning`: `skills/research/proposition-graph-reasoning.md`
```

4. Leave the Companion Skills block at the foot pointing at routers — those references are correct as routers and must not be churned.

- [ ] **Step 3: Update `skills/meta/skill-authoring.md:41`**

Live doctrine, false after this phase. Replace the router-invariant paragraph — pin verbatim:

```markdown
This is stated as a **target invariant** that the corpus is converging on: 4 of 7 current `SKILL.md` files are still **hubs** (route + teach). `research/SKILL.md` and `writing/SKILL.md` were extracted on 2026-07-20 and are now true routers; `data/genomics/SKILL.md` was already one. Every remaining hub is a migration extraction candidate (see the matrix). A document that routes *and* teaches is a hub; its teaching content is extracted into typed leaves before it is a true router.
```

Leave the `Placement (pre-migration)` guidance at L36-40 unchanged — this phase adds no directory.

- [ ] **Step 4: Update `skills/meta/skill-taxonomy.md`**

In Versioning/migration, record that the router invariant now holds for `research/` and `writing/`, that four hubs remain, and that reorganization stays deferred to phase 3.

- [ ] **Step 5: Update the corpus matrix**

In `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md`: set `router-state` to `pure-router` for `research/SKILL.md` and `writing/SKILL.md`; add the four new leaf rows; update the archetype tally (`practice-guide` 1 → 3, `normative-reference` 3 → 4, `analysis-discipline` 8 → 9, total 34 → 38); strike the two completed entries from "Hub extraction candidates" and note the date.

In the **Earns-a-template check**, `practice-guide` now has two clean corpus instances. Update the count, but **do not** rewrite the eligibility argument to rest on `research-package-rendering` — that force-fit is explicitly excluded from the practice-guide population, and its trip-wire stands.

- [ ] **Step 6: Regenerate, verify, commit**

```bash
cd science && uv run science skills lint; echo "LINT_EXIT=$?"
cd science && uv run python ../scripts/generate_codex_skills.py
cd science && uv run --frozen pytest -q; echo "PYTEST_EXIT=$?"
```

```bash
git add skills/ docs/plans/ codex-skills/
git commit -m "docs(skills): retarget cross-subject references, index, and router-invariant doctrine"
```

---

### Task 5: Acceptance sweep

No new code. Verify every acceptance item from the design doc and report evidence.

- [ ] **Step 1: Lint and typed-leaf metadata**

```bash
cd science && uv run science skills lint; echo "LINT_EXIT=$?"
cd .. && git grep -c '^archetype:' skills/research/ skills/writing/
git grep -n '^archetype:' skills/research/SKILL.md skills/writing/SKILL.md
```

Expected: `LINT_EXIT=0`. The second grep returns **nothing** — routers must not declare `archetype:`.

- [ ] **Step 2: Router-profile conformance**

Open `skills/research/SKILL.md` and `skills/writing/SKILL.md` beside
`skills/meta/templates/router.md`. Confirm each carries `## Routing trigger`,
`## Scope boundary`, `## Leaves`, `## Decision / compose order`,
`## Parent & neighbors`, and `## Success test` — and that **no** section
teaches. A router that retains a prose section re-acquires the hub smell even
when the prose only routes; "Annotation and Curation" must be a table row, not
a section.

- [ ] **Step 3: Leaf-template conformance, itemwise**

For each of the four new leaves, open `skills/meta/templates/<archetype>.md` beside it and confirm every slot is present **and filled with content of the kind the slot names**. Lint cannot check this; a prose move can pass lint while failing the typed-leaf goal.

Confirm specifically: `proposition-graph-reasoning.md` carries the five-condition table, the no-flag-is-not-certification paragraph, the unevaluated state, and permitted-vs-forbidden wording; no `adequate` outcome exists anywhere in it. Both practice-guides carry a real `Common pitfalls` and `Outputs`. `citation-discipline.md` carries `Invariants`, `Examples`, and `Invalid cases`.

- [ ] **Step 4: Full suite and linters**

```bash
cd science && uv run --frozen pytest -q; echo "PYTEST_EXIT=$?"
cd science && uv run ruff check; uv run pyright
```

Expected: `PYTEST_EXIT=0`; only the 4 known ruff and 7 known pyright pre-existing errors. Report any new finding as a failure.

- [ ] **Step 5: Mirror freshness and dangling-link sweep**

```bash
cd science && uv run python ../scripts/generate_codex_skills.py && cd .. && git status --porcelain codex-skills/
```

Expected: empty — the committed mirror is byte-identical to fresh generation.

The dangling sweep and the router-destination assertion are automated by `test_no_dangling_relative_links_in_generated_tree` and `test_research_router_neighbor_link_points_at_writing_router`, both green in Step 3.

- [ ] **Step 6: Corpus count**

```bash
cd .. && python3 -c "
import pathlib,re
from collections import Counter
leaves=[p for p in pathlib.Path('skills').rglob('*.md')
        if p.name not in {'SKILL.md','INDEX.md'} and p.parts[1] != 'meta']
c=Counter(re.search(r'^archetype:\s*(\S+)',p.read_text(),re.M).group(1) for p in leaves)
print(len(leaves), dict(c))"
```

Expected: `38 {'measurement-qa': 11, 'method-guide': 6, 'analysis-discipline': 9, 'normative-reference': 4, 'tool-guide': 5, 'practice-guide': 3}`.

`skills/meta/` is excluded entirely, not just its `templates/`. It holds two archetyped leaves (`skill-authoring.md`, `skill-taxonomy.md`) that sit outside the corpus matrix; counting them yields 36 at baseline instead of the matrix's 34 and produces a false failure. Baseline verified at `1feb088c`: 34 leaves, `practice-guide` 1.

- [ ] **Step 7: Report**

Report each acceptance item with the command run and its output. Do not report green from a piped command without capturing the exit code separately.
