# Skills Hub Extraction (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the router invariant for `skills/research/` and `skills/writing/` by extracting their embedded doctrine into four typed leaves, deduplicating the doctrine they share, and fixing the Codex generator so the resulting cross-directory links resolve correctly.

**Architecture:** Five sequential tasks. Task 1 is a pure toolkit fix that makes correct link rewriting possible (and closes nine pre-existing danglers). Tasks 2 and 3 extract the two hubs — research first, because `writing/scientific-writing.md` links to a research leaf. Task 4 lands the cross-subject retargets and doctrine updates that need both hubs done. Task 5 is the acceptance sweep.

**Tech Stack:** Python 3.13, pytest, uv, ruff, pyright. Markdown skill corpus under `skills/`, generated mirror under `codex-skills/`.

**Design doc:** [`2026-07-20-skills-hub-extraction-design.md`](2026-07-20-skills-hub-extraction-design.md). Read it before Task 2 — it fixes every destination and the full outcome contract.

## Global Constraints

- Work in the worktree at `.claude/worktrees/skills-hub-extraction` on branch `skills-hub-extraction`. Verify with `git branch --show-current` before every commit. **`$WT` below means the worktree root**; every command block declares its own starting directory and uses subshells, because repeated `cd science` in one pasted block fails after the first.
- All Python commands run from `$WT/science`. There is **no root `pyproject.toml`**.
- **`science skills lint` defaults to `--root skills`, which resolves to `science/skills` and does not exist.** Always pass `--root ../skills`. The wrong form exits **2**, and piping it through `tail` reports `0` — capture exit codes before any pipe.
- No AI-attribution trailers or footers on commits. No `Co-Authored-By`, no generated-with footer.
- No "legacy"/"compatibility" layers. No `Unified` prefix. Composition over inheritance; explicit over defensive; fail early rather than silent fallback.
- Use `~/d/` in docs and code paths, never `/home/keith/` or `/mnt/ssd/Dropbox/`.
- **Any change under `skills/` requires regenerating `codex-skills/` in the same commit.** `codex-skills/` is a git-tracked generated mirror guarded by `test_committed_codex_skills_match_fresh_generation`.
- **Routers and `INDEX.md` must not declare `archetype:`.** Every leaf declares exactly one of: `measurement-qa`, `method-guide`, `analysis-discipline`, `normative-reference`, `tool-guide`, `practice-guide`.
- **Pre-existing failures, not caused by this branch:** 4 ruff errors in `science/tests/test_numeric_binding.py`, 7 pyright errors in `prose_lint.py`, both reproducible at base `1feb088c`. The bar is **no new findings**.
- **Implementers invent no prose.** Text that *moves* is named by exact source range with a `git show` command to retrieve it — including text an earlier task has already deleted. Text that is *new* is pinned verbatim here.
- Never bare `git stash` / `git stash pop` — the stash stack is shared across worktrees.

**Declare `$WT` once per shell session before running any command block:**

```bash
export WT=~/d/science/.claude/worktrees/skills-hub-extraction
(cd "$WT" && git branch --show-current)   # must print: skills-hub-extraction
```

**Retrieving text deleted by an earlier task.** Tasks 3 and 4 need prose that Task 2 removes. Retrieve it from the pre-branch commit, never from the working tree — all ranges below are verified against `1feb088c`:

```bash
git show 1feb088c:skills/research/SKILL.md | sed -n '170,180p'   # Project Awareness
git show 1feb088c:skills/research/SKILL.md | sed -n '185,187p'   # Template Usage
git show 1feb088c:skills/writing/SKILL.md  | sed -n '24,40p'     # Voice/Tone + Hedging
```

---

### Task 1: Generator — classify links by emitted artifacts, rewrite copied resources

Pure toolkit change. No `skills/` edits. Closes nine pre-existing dangling links — six in copied companion resources, three in command bodies — then adds a guard so they cannot return. Sweep-then-ratchet: fix first, ratchet second.

**Files:**
- Modify: `science/src/science_tool/codex_skills.py` — the companion path (`160-212`) and `_build_skill_text` (the command-body path)
- Test: `science/tests/test_codex_skills.py`
- Regenerate: `codex-skills/`

**Interfaces:**
- Produces: `_resource_paths(source_path: Path) -> list[Path]` — the single predicate for the emitted resource set, used by both the copy loop and the rewriter.
- Produces: `_companion_link_targets(repo_root: Path) -> dict[Path, str]` — repo-relative `skills/...` path → emitted location fragment.
- Produces: `_rewrite_companion_body_links(body: str, repo_root: Path) -> str` — **signature change**, gains `repo_root`.
- Produces: `_rebase_command_body_links(body: str) -> str` — re-depths a command body's relative links; called from `_build_skill_text`, which is modified to invoke it.

- [ ] **Step 1: Write the failing tests**

Add `import re` to `science/tests/test_codex_skills.py` if absent, then append:

```python
def _generate(tmp_path: Path) -> Path:
    generated_root = tmp_path / "codex-skills"
    generate_codex_skills(ROOT, generated_root)
    return generated_root


def _resolve_generated_link(source: Path, target: str, generated_root: Path) -> Path:
    """Resolve a link as it would resolve in the committed layout.

    `codex-skills/` sits at the repo root, so any `../../...` fallback — into
    `skills/`, `docs/`, or elsewhere — points into the real repo. Under a
    tmp_path generated tree that fallback would escape into the temporary
    directory, so re-root every `../../` link at ROOT. Links that stay inside
    the generated tree (`../science-*/...`) resolve against the source's parent.
    """
    if target.startswith("../../"):
        return ROOT / target[len("../../") :]
    return source.parent / target


def _dangling_links(generated_root: Path) -> list[str]:
    dangling: list[str] = []
    for path in sorted(generated_root.rglob("*.md")):
        for raw in re.findall(r"]\((\.\.?/[^)]+)\)", path.read_text(encoding="utf-8")):
            target = raw.split("#", 1)[0]
            if not target:
                continue
            if not _resolve_generated_link(path, target, generated_root).exists():
                dangling.append(f"{path.relative_to(generated_root)} -> {raw}")
    return dangling


def test_rewrites_link_to_companion_source_leaf(tmp_path: Path) -> None:
    rendering = (_generate(tmp_path) / "science-research-methodology" / "research-package-rendering.md").read_text(
        encoding="utf-8"
    )
    assert "../science-scientific-writing/SKILL.md" in rendering
    assert "](../writing/SKILL.md)" not in rendering


def test_rewrites_link_to_non_companion_leaf(tmp_path: Path) -> None:
    curation = (_generate(tmp_path) / "science-research-methodology" / "annotation-curation-qa.md").read_text(
        encoding="utf-8"
    )
    assert "../../skills/statistics/sensitivity-arbitration.md" in curation
    assert "](../statistics/sensitivity-arbitration.md)" not in curation


def test_no_dangling_relative_links_in_generated_tree(tmp_path: Path) -> None:
    assert _dangling_links(_generate(tmp_path)) == []
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
(cd "$WT/science" && uv run --frozen pytest tests/test_codex_skills.py -k "rewrites_link or no_dangling" -v)
```

Expected: all three FAIL. `test_no_dangling_relative_links_in_generated_tree` lists exactly **nine** entries, verified against the committed mirror at `1feb088c`:

```
science-health/SKILL.md                                    -> ../docs/user-guide/evidence-lines.md
science-plan-analysis/SKILL.md                             -> ../skills/statistics/estimator-certification.md
science-pre-register/SKILL.md                              -> ../skills/statistics/estimator-certification.md
science-research-methodology/annotation-curation-qa.md     -> ../data/frictionless.md
science-research-methodology/annotation-curation-qa.md     -> ../statistics/sensitivity-arbitration.md
science-research-methodology/research-package-rendering.md -> ../writing/SKILL.md
science-research-methodology/research-package-rendering.md -> ../pipelines/snakemake.md
science-research-methodology/research-package-spec.md      -> ../data/frictionless.md
science-research-methodology/research-package-spec.md      -> ../pipelines/snakemake.md
```

The first three come from **command** bodies, not companions, and need the separate fix in Step 3b. If the count differs from nine, investigate the generator — do **not** relax the test to match. A guard that gets weakened to fit an unexpected count stops being a guard.

- [ ] **Step 3: Implement**

Replace the resource-copy loop at `codex_skills.py:173-176`:

```python
    for resource_path in _resource_paths(source_path):
        text = resource_path.read_text(encoding="utf-8")
        (skill_dir / resource_path.name).write_text(
            _rewrite_companion_body_links(text, repo_root), encoding="utf-8"
        )
```

Update the body-rewrite call at line 183 to `body = _rewrite_companion_body_links(body, repo_root)`.

Replace `_rewrite_companion_body_links` (lines 200-212) with:

```python
def _resource_paths(source_path: Path) -> list[Path]:
    """Markdown files bundled as resources beside a companion's SKILL.md.

    Excludes the directory's router (SKILL.md) and the companion's own source
    file, which is emitted as the companion's SKILL.md rather than as a
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

A path absent from `targets` is emitted nowhere and resolves to its canonical source. That covers a non-companion directory **and** a router excluded from its own companion's bundle — the case Task 3 creates, with no further edit.

- [ ] **Step 3b: Rebase relative links in command bodies**

Companion rewriting does not reach command skills. Command sources live in
`commands/` (one level below the repo root) and are emitted to
`codex-skills/science-<command>/SKILL.md` (two levels below), so every relative
link in a command body is short by exactly one `../`. All three such links in
the corpus point outside `skills/` or at a non-companion leaf, so a depth
rebase is both correct and sufficient — no companion mapping applies.

Add:

```python
def _rebase_command_body_links(body: str) -> str:
    """Re-depth relative links for a command body's generated location.

    Command sources sit at `commands/<name>.md` (depth 1) and are emitted to
    `codex-skills/science-<name>/SKILL.md` (depth 2), so each relative link
    needs one more `../` to reach the same target.
    """
    return re.sub(r"]\(\.\./", "](../../", body)
```

Call it in `_build_skill_text` alongside the existing rewrites, after
`_rewrite_claude_specific_text`:

```python
    rewritten_body = _rebase_command_body_links(rewritten_body)
```

The three command links are verified against the regenerated mirror in Step 4,
after `generate_codex_skills.py` runs — grepping `codex-skills/` here would read
the stale committed files, which still carry the pre-fix depth.

- [ ] **Step 4: Verify green, regenerate, verify suite**

```bash
(cd "$WT/science" && uv run --frozen pytest tests/test_codex_skills.py -v)
(cd "$WT/science" && uv run python ../scripts/generate_codex_skills.py)
(cd "$WT" && git diff --stat codex-skills/)
(cd "$WT" && grep -rn '](\.\./\.\./' codex-skills/science-health/SKILL.md \
  codex-skills/science-plan-analysis/SKILL.md codex-skills/science-pre-register/SKILL.md)
(cd "$WT/science" && uv run --frozen pytest -q >/dev/null 2>&1; echo "PYTEST_EXIT=$?")
(cd "$WT/science" && uv run ruff check; uv run pyright)
```

Expected: all codex tests PASS; six files change under `codex-skills/` — three under `science-research-methodology/` (companion resources) and `science-health/`, `science-plan-analysis/`, `science-pre-register/` (command bodies); the grep shows `../../docs/user-guide/evidence-lines.md` once and `../../skills/statistics/estimator-certification.md` twice, against the freshly regenerated mirror; `PYTEST_EXIT=0`; only the 4 known ruff and 7 known pyright errors.

- [ ] **Step 5: Commit**

```bash
(cd "$WT" && git add science/src/science_tool/codex_skills.py science/tests/test_codex_skills.py codex-skills/ \
  && git commit -m "fix(codex): rewrite links in copied resources and classify by emitted artifacts")
```

---

### Task 2: Extract `skills/research/` into three leaves

**Files:**
- Create: `skills/research/literature-evaluation.md`, `skills/research/citation-discipline.md`, `skills/research/proposition-graph-reasoning.md`
- Modify: `skills/research/SKILL.md`, `skills/research/proposition-schema.md`, `skills/research/annotation-curation-qa.md:111`
- Regenerate: `codex-skills/`

**Interfaces:**
- Produces: leaves named `research-literature-evaluation`, `research-citation-discipline`, `research-proposition-graph-reasoning`, at those exact filenames. Tasks 3 and 4 link to them.

- [ ] **Step 1: Create `skills/research/literature-evaluation.md`**

Frontmatter and the authored slots are pinned. Moved prose is named by range.

```markdown
---
name: research-literature-evaluation
description: Use when reviewing literature, assessing source quality, or synthesizing findings across papers, before writing durable claims.
archetype: practice-guide
provenance: internal
---

# Literature Evaluation

Answers: how do I evaluate and synthesize external sources well?

## When to apply

Before writing any durable output that rests on external sources: a paper
summary, a topic synthesis, a background section, or an evidence line citing
literature. Also when auditing claims someone else sourced.

## Workflow steps
```

Then, verbatim from `git show 1feb088c:skills/research/SKILL.md`:

- lines 32-46 (the four-item Source Hierarchy list) as steps 1-4
- lines 62-68 (the Cross-Checking Key Facts bullet list and the `[UNVERIFIED]` sentence) as the final step, introduced by the pinned line: `5. **Cross-check before committing.** Always cross-check these via web search:`

  The range starts at 62, not 60: source line 60 is "Always cross-check via web search before committing to a document:", which the pinned lead-in above already says. Copying both would state it twice.

Then continue with pinned content:

```markdown
## Judgment rules
```

Verbatim from lines 50-56 (Confidence Calibration, including the closing "worst outcome" sentence) and lines 72-78 (the five Evaluating Sources bullets).

```markdown
## Quality criteria
```

Verbatim from lines 82-88 (the five Synthesis bullets).

```markdown
## Common pitfalls

- Writing from model memory without searching → treat recall as orientation for search terms, never as a citable source.
- Citing a paper read only at the abstract level → mark conclusions abstract-level and make no durable evidence update.
- Reporting agreement across sources that share an origin → check whether the sources are independent before counting them as convergent.
- Summarizing each source in turn and stopping → synthesis requires naming the disagreements and the gaps, not just the contents.

## Outputs

A source set with two axes recorded separately for each item — **provenance**
(primary or secondary) and **publication status** (peer-reviewed, preprint, or
informal) — since a peer-reviewed review article is secondary and a preprint may
be primary. Plus the claims each source backs, and explicit `[UNVERIFIED]` marks
on anything that could not be cross-checked.

## Success test

Did the agent carry out the cross-cutting practice according to its workflow, judgment rules, and quality criteria?

## Companion Skills

- [`citation-discipline.md`](citation-discipline.md) - citation and source-pointer conformance for what this practice produces.
- [`proposition-graph-reasoning.md`](proposition-graph-reasoning.md) - reasoning over the project's own proposition graph, as opposed to external sources.
- [`../INDEX.md`](../INDEX.md) — the skill index.
```

- [ ] **Step 2: Create `skills/research/citation-discipline.md`**

Fully pinned. The only moved content is the format list, and it is reproduced here in merged form because the merge of `research/SKILL.md:163-168` with `writing/SKILL.md:66-73` is a judgment the plan makes, not the implementer.

```markdown
---
name: research-citation-discipline
description: Use when authoring or validating citations, source pointers, and bibliography references in project documents.
archetype: normative-reference
provenance: internal
---

# Citation Contract

Answers: what must a citation or source pointer mean and contain?

## Scope

Governs every citation, bibliography key, and source pointer in project prose
and entity frontmatter. It does not govern document structure or templates
(see [`../writing/scientific-writing.md`](../writing/scientific-writing.md)),
nor the annotation-token vocabulary, which is owned by
`docs/conventions/annotation-tokens.md`.

## Vocabulary / schema

| Form | Where | Means |
|---|---|---|
| `[@AuthorYear]` | prose | inline citation; the key must resolve in `papers/references.bib` |
| `[@Smith2020; @Jones2021]` | prose | multiple sources for one claim |
| `[@Smith2020, p. 42]` | prose | citation with locator |
| `Smith et al. [@Smith2020]` | prose | narrative citation |
| `cite:AuthorYear` | `source_refs` frontmatter | bibliography backing |
| `paper:AuthorYear` | `source_refs` frontmatter | link to a project paper note |

## Invariants

- Every BibTeX key used in a document has a corresponding entry in `papers/references.bib`. Creating a citation means adding the entry.
- `cite:AuthorYear` backs a bibliography entry; `paper:AuthorYear` links a project paper note. They are not interchangeable.
- Every factual claim carries either a citation or the annotation token that correctly describes its unsourced state, per [`../../docs/conventions/annotation-tokens.md`](../../docs/conventions/annotation-tokens.md). Unmarked and unsourced is not a permitted state. Which token is *appropriate* is decided by that document, not here — `[SPECULATION]`, for instance, marks author conjecture, which is not a factual claim awaiting a source at all.
- Primary sources are preferred over secondary summaries.
- Claims drawn from model knowledge are cross-checked via web search before they are committed.

## Conformance rules

Conformance is checked by `validate.sh` and `science refs check`, which resolve
every `[@Key]` against `papers/references.bib` and report unresolved keys.
`[UNVERIFIED]` and `[MISSING_CITATION]` are counted as warnings by default;
`[SPECULATION]` and `[INACCESSIBLE]` are reported as info unless `--strict`.

## Examples

- Inline: `[@Smith2020]`
- Multiple: `[@Smith2020; @Jones2021]`
- With page: `[@Smith2020, p. 42]`
- Narrative: `Smith et al. [@Smith2020] found that...`
- Frontmatter: `source_refs: ["cite:Smith2020"]`

## Versioning / migration

This leaf supersedes the citation rules formerly duplicated in
`research/SKILL.md` ("Citation Discipline") and `writing/SKILL.md` ("Citation
Format"), extracted and merged 2026-07-20. Neither router states citation rules
any longer; both link here.

## Invalid cases

1. `[@Smith2020]` with no matching entry in `papers/references.bib` — the key must resolve.
2. `paper:Smith2020` in `source_refs` where only a bibliography entry exists — use `cite:` unless a project paper note exists.
3. An unsourced factual claim carrying **no annotation token at all** — silence is not a permitted state. See [`../../docs/conventions/annotation-tokens.md`](../../docs/conventions/annotation-tokens.md) for which token applies.
4. A factual claim marked `[SPECULATION]` — that token designates author conjecture, so using it on a claim that is awaiting a source misreports what the claim is. Use the token the canonical convention assigns to that state.
5. A citation to a source read only at abstract level, presented as backing a specific numerical result.

## Success test

Is there an explicit conformance check against the vocabulary/invariants — mechanical (lint/validate) where available, an itemized checklist otherwise?

## Companion Skills

- [`literature-evaluation.md`](literature-evaluation.md) - how sources are selected and assessed before they are cited.
- [`../writing/scientific-writing.md`](../writing/scientific-writing.md) - document structure, hedging, and annotation-token usage in prose.
- [`../INDEX.md`](../INDEX.md) — the skill index.
```

The invariant and invalid cases 3-4 are deliberately consistent: the requirement is the *appropriate* token, not any token. `[SPECULATION]` marks author conjecture rather than a claim awaiting support, so treating the four as interchangeable would weaken the canonical semantics. This leaf points at `docs/conventions/annotation-tokens.md` and does not restate the definitions — restating them would recreate exactly the duplication this extraction removes.

- [ ] **Step 3: Create `skills/research/proposition-graph-reasoning.md`**

```markdown
---
name: research-proposition-graph-reasoning
description: Use when interpreting or updating the project's own proposition graph — assessing hypothesis support, reading dashboard signals, or deciding where to direct effort.
archetype: analysis-discipline
provenance: internal
---

# Proposition Graph Reasoning

Answers: before interpreting the project's own evidence, what must be checked
about how that evidence is recorded?

## Triggering condition

Fires whenever a conclusion is drawn from the project's own proposition graph
rather than from external literature: writing an interpretation, updating
hypothesis support, summarizing where the project stands, or choosing what to
work on next.

Science uses a skeptical, proposition-centric model:
```

Then verbatim from `git show 1feb088c:skills/research/SKILL.md` lines 12-16 (the five model bullets). These are the epistemic policy the router must **not** retain — propositions as belief units, sparse support as fragile, contested neighborhoods as prioritization signals.

```markdown
## Required reasoning / check / precommitment
```

Verbatim from lines 94-99 (the six Working with Hypotheses bullets) and lines 101-102 (the pointer to `proposition-schema.md`).

```markdown
## Decision rule or reasoning criteria

Assess each condition below against the entity files. When
`knowledge/graph.trig` exists, the last four are additionally checked against
the store summaries:

- `science graph dashboard-summary --format json`
- `science graph neighborhood-summary --format json`

These summaries are a prioritization instrument. They report where recorded
evidence is thin or contested; they do not measure whether a proposition is
true.
```

**Outcomes** is the decided contract — pinned verbatim:

```markdown
## Outcomes (flagged conditions)

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

## Halt / escalation
```

Verbatim from lines 139-143 — the "In those cases:" lead-in and its three bullets, the last of which already reads "call out that the project still needs migration work when that affects interpretation quality." Do **not** append that instruction again; the moved range supplies it.

```markdown
## Required evidence & artifacts

**Every** condition that fired is recorded, along with every condition that
could not be evaluated and why. Nothing is dropped for being unsurprising.

- **On an interpretation** (`templates/interpretation.md`): the full fired set and the unevaluated set under `## Evidence Quality`; what those flags license under `## Updated Priorities`.
- **On a synthesis** (`templates/synthesis.md`): the full fired set and the unevaluated set under `## Knowledge Gaps` — including `migration-limited`, `contested`, and `single-source-fragile`, not only the gap-shaped ones; the prioritization they license under `## Research fronts`.
- The dashboard command run and its output, when one was run; when `knowledge/graph.trig` was absent, record that instead.

## Permitted reporting language

- Permitted: "supports", "disputes", "leaves unresolved", "is consistent with", "single-source", "contested", "unevaluated".
- **Not licensed by this discipline, ever:** "confirms", "proves", "validates", "establishes", "well-supported", "sufficient". No flagged condition licenses any of them — the conditions report where recorded evidence is thin or contested, and none of them measures whether a proposition is true. A positive support judgment requires a separate warrant this discipline does not supply.
- Forbidden always: reporting the absence of flagged conditions as positive evidence of support.

## Success test

Was the required reasoning/precommitment carried out before interpretation, and does the conclusion follow from it — mechanically where a locked table applies, by the stated criteria otherwise?

## Companion Skills

- [`proposition-schema.md`](proposition-schema.md) - the strict enums and field semantics this reasoning writes against.
- [`literature-evaluation.md`](literature-evaluation.md) - evaluating external sources, as opposed to the project's own graph.
- [`../INDEX.md`](../INDEX.md) — the skill index.
```

- [ ] **Step 4: Rewrite `skills/research/SKILL.md` as a router**

Replace the whole file with this, verbatim. The `description:` is unchanged from the current file — `codex_skills.py` copies it into the companion and a test asserts its text.

```markdown
---
name: research-methodology
description: Core research methodology for scientific investigation. This skill should be used whenever conducting literature review, evaluating scientific sources, synthesizing findings across papers, assessing evidence quality, identifying gaps in knowledge, or working with hypotheses. Also use when the user mentions research, papers, citations, evidence, or scientific literature — even if they don't explicitly ask for "research methodology."
provenance: internal
---

# Research Methodology Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when any research activity is in scope — literature review,
paper summarization, hypothesis development, evidence evaluation, curation, or
topic exploration — before loading any leaf.

For analysis-readiness planning, start at [`../INDEX.md`](../INDEX.md) or run
`science-plan-analysis`.

## Scope boundary

Covers how the project evaluates external sources and reasons over its own
proposition graph. Excludes prose conventions (see
[`../writing/SKILL.md`](../writing/SKILL.md)) and statistical interpretation
(see [`../statistics/SKILL.md`](../statistics/SKILL.md)).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| [`literature-evaluation.md`](literature-evaluation.md) | Reviewing literature, assessing source quality, or synthesizing across papers | Reasoning about the project's own recorded evidence |
| [`citation-discipline.md`](citation-discipline.md) | Authoring or validating citations, bibliography keys, or `source_refs` | Deciding which sources to trust |
| [`proposition-graph-reasoning.md`](proposition-graph-reasoning.md) | Interpreting or updating the project's proposition graph, or deciding where to direct effort | Evaluating an external source |
| [`proposition-schema.md`](proposition-schema.md) | Authoring proposition entities, evidence metadata, or layered-claim fields | Reasoning about support adequacy rather than field values |
| [`annotation-curation-qa.md`](annotation-curation-qa.md) | Designing or reviewing claim extraction, labels, adjudication, or LLM-assisted curation | Curating nothing — reading only |
| [`research-package-spec.md`](research-package-spec.md) | Defining research-package manifests, cells, provenance, or workflow integration | Rendering an existing package |
| [`research-package-rendering.md`](research-package-rendering.md) | Rendering research packages and source routes in web experiences | Defining the package schema itself |

## Decision / compose order

Leaves are independent except where noted:

1. `literature-evaluation.md` before `citation-discipline.md` — select and assess sources, then record them correctly.
2. `proposition-schema.md` before `proposition-graph-reasoning.md` — know the field semantics before reasoning over their values.
3. `research-package-spec.md` before `research-package-rendering.md` — the rendering leaf builds on the spec as layer 1.

## Parent & neighbors

- Parent index: [`../INDEX.md`](../INDEX.md)
- Neighboring routers: [`../writing/SKILL.md`](../writing/SKILL.md), [`../statistics/SKILL.md`](../statistics/SKILL.md), [`../data/SKILL.md`](../data/SKILL.md)

## Success test

Representative in-scope tasks route to the correct leaf (or the correct compose order when leaves combine) without any methodology being read from this router.

## Companion Skills

- [`../INDEX.md`](../INDEX.md) — the skill index.
```

Note what this removes and where it went: the proposition-centric model bullets (old L11-16) are epistemic policy and moved to `proposition-graph-reasoning.md` in Step 3 — the router keeps only the INDEX pointer and a one-sentence scope boundary. "Annotation and Curation" (old L121-128) is now the `annotation-curation-qa.md` table row. "Project Awareness" (old L170-180) and "Template Usage" (old L185-187) move to Task 3's writing leaf; retrieve them with the `git show` commands in Global Constraints.

- [ ] **Step 5: Extend and retarget `proposition-schema.md`**

Two methodology-owning links here point at the router. Retarget **both**.

First, lines 9-11 — replace the sentence pointing at `SKILL.md` with:

```markdown
For the generic methodology layer, see
[`literature-evaluation.md`](literature-evaluation.md) (source hierarchy,
evaluating sources) and [`citation-discipline.md`](citation-discipline.md)
(citation discipline). For the prose explanation of the model, see
`docs/user-guide/epistemic-model.md` and `docs/user-guide/evidence-lines.md`.
```

Second, the **Companion Skills** entry at line 89. Its description — "generic
research methodology that this schema overlays" — becomes false once the router
teaches nothing, and it preserves the same indirection removed everywhere else.
Replace that single line with:

```markdown
- [`literature-evaluation.md`](./literature-evaluation.md) - evaluating the external sources that populate proposition entities.
- [`citation-discipline.md`](./citation-discipline.md) - citation and source-pointer conformance for `source_refs`.
- [`proposition-graph-reasoning.md`](./proposition-graph-reasoning.md) - reasoning over the graph these field values build.
```

Then add an `## Evidence Types` section — pinned, because the canonical form differs from the hub's alias form:

```markdown
## Evidence Types

The typed evidence vocabulary is owned by the model enum
(`science_model.reasoning.EvidenceType`). The canonical stored tokens carry
**no** `_evidence` suffix:

- `empirical_data` — project-run analyses over observed data
- `benchmark` — benchmark tasks, evaluation suites, standardized comparisons
- `simulation` — results that primarily come from a model world
- `literature` — prior publications, reviews, meta-analyses
- `expert_judgment` — structured expert assessment
- `negative_result` — accepted for compatibility, but usually better understood as a result pattern; the line's `stance`, role, and scope should carry what the null or negative result does to the target proposition

Authoring may still use the historical `_evidence` suffix — `literature_evidence`,
`empirical_data_evidence` — which Science strips at the model boundary and
stores as the canonical member. Unknown evidence types fail when parsed.

Do not collapse these into a generic "computational evidence" label.
```

- [ ] **Step 6: Retarget `annotation-curation-qa.md:111`**

Replace the single line with two:

```markdown
- [`literature-evaluation.md`](literature-evaluation.md) - source hierarchy and source-quality assessment for literature-derived claims.
- [`citation-discipline.md`](citation-discipline.md) - citation and source-pointer conformance.
```

- [ ] **Step 7: Lint, regenerate, verify, commit**

```bash
(cd "$WT/science" && uv run --frozen science skills lint --root ../skills; echo "LINT_EXIT=$?")
(cd "$WT/science" && uv run python ../scripts/generate_codex_skills.py)
(cd "$WT/science" && uv run --frozen pytest -q >/dev/null 2>&1; echo "PYTEST_EXIT=$?")
(cd "$WT" && git add skills/research/ codex-skills/ \
  && git commit -m "refactor(skills): extract research hub into literature-evaluation, citation-discipline, proposition-graph-reasoning")
```

Expected: `LINT_EXIT=0`, `PYTEST_EXIT=0`.

---

### Task 3: Extract `skills/writing/` and transfer the `scientific-writing` identifier

Leaf creation, router rename, and the `COMPANION_SKILLS` change **must land in one commit** — generation raises `ValueError` on name mismatch (`codex_skills.py:163-165`), so any intermediate state fails.

**Files:**
- Create: `skills/writing/scientific-writing.md`
- Modify: `skills/writing/SKILL.md`, `science/src/science_tool/codex_skills.py:18`, `science/tests/test_codex_skills.py`
- Regenerate: `codex-skills/`

- [ ] **Step 1: Write the failing tests first**

Update the existing assertions in `test_generate_codex_skills_emits_companion_methodology_skills`:

- line 93: `` `skills/writing/SKILL.md` `` → `` `skills/writing/scientific-writing.md` ``
- line 95: `"../science-research-methodology/SKILL.md"` → `"../science-research-methodology/citation-discipline.md"`

Line 95 is the **bundled-resource** case: the writing leaf's companion link points at a research *leaf*, which is emitted as a resource of the research companion. Then append:

```python
def test_rewrites_link_to_bundled_resource(tmp_path: Path) -> None:
    writing_skill = (_generate(tmp_path) / "science-scientific-writing" / "SKILL.md").read_text(encoding="utf-8")
    assert "../science-research-methodology/citation-discipline.md" in writing_skill
    assert "](../research/citation-discipline.md)" not in writing_skill


def test_rewrites_excluded_router_to_canonical_source(tmp_path: Path) -> None:
    research_skill = (_generate(tmp_path) / "science-research-methodology" / "SKILL.md").read_text(encoding="utf-8")
    assert "../../skills/writing/SKILL.md" in research_skill
    assert "../science-scientific-writing/SKILL.md" not in research_skill


def test_companion_source_leaf_is_not_also_a_resource(tmp_path: Path) -> None:
    assert not (_generate(tmp_path) / "science-scientific-writing" / "scientific-writing.md").exists()
```

Together with Task 1's two tests, the five destination classes are each covered once: source → companion root, bundled resource → companion resource, excluded router → canonical source, non-companion leaf → canonical source, and rewriting *within* a copied resource (Task 1's `test_rewrites_link_to_companion_source_leaf`, which reads a copied resource).

- [ ] **Step 2: Run them to verify they fail**

```bash
(cd "$WT/science" && uv run --frozen pytest tests/test_codex_skills.py -k "bundled_resource or excluded_router or companion_methodology" -v)
```

Expected: `test_rewrites_link_to_bundled_resource`, `test_rewrites_excluded_router_to_canonical_source`, and the updated `test_generate_codex_skills_emits_companion_methodology_skills` all FAIL — the writing companion is still generated from the router, so it carries no citation link and the research router link still rewrites to the companion.

`test_companion_source_leaf_is_not_also_a_resource` **passes vacuously** at this point, because `scientific-writing.md` does not exist yet. That is expected and is not evidence of anything; it only becomes meaningful after Step 3. Do not revert implementation code to manufacture a failure for it.

- [ ] **Step 3: Create `skills/writing/scientific-writing.md`**

```markdown
---
name: scientific-writing
description: Scientific writing conventions for research documents. This skill should be used whenever writing or editing research documents, background sections, paper summaries, hypothesis descriptions, overview documents, or any content in the doc/ directory. Also use when the user asks to write, draft, revise, or edit any scientific or technical prose, or when creating content that will be part of a research project's documentation.
archetype: practice-guide
provenance: internal
---

# Scientific Writing

Answers: how do I write project prose that is correctly hedged, sourced, and
connected to the research framework?

## When to apply

Before writing or editing any document in `doc/` or `specs/`, any entity
description, or any prose that will become part of the project's durable
record.

The default epistemic posture is skeptical:
- write hypotheses as organizing conjectures
- write propositions as uncertain unless the evidence base is unusually strong
- describe evidence as supporting, disputing, or leaving a proposition unresolved

## Workflow steps

1. **Check the project first.** Before writing any document, check:
```

Then verbatim from `git show 1feb088c:skills/research/SKILL.md | sed -n '174,180p'` (the five-item Project Awareness list and its closing sentence).

```markdown
2. **Read the template.**
```

Then verbatim from `git show 1feb088c:skills/research/SKILL.md | sed -n '187p'` (the Template Usage paragraph).

```markdown
3. **Draft, hedging to the evidence.** Apply the judgment rules below.
4. **Mark what you could not source.** When a claim cannot carry an in-line citation, mark it with one of the four annotation tokens defined in `docs/conventions/annotation-tokens.md`: `[UNVERIFIED]`, `[MISSING_CITATION]`, `[SPECULATION]`, `[INACCESSIBLE]`. That document is the normative owner of the vocabulary and the validator behavior; do not restate the definitions here.
5. **Connect the document to the framework.**
```

Then verbatim from `git show 1feb088c:skills/writing/SKILL.md | sed -n '79,85p'` (the five Connecting-to-the-Project bullets and the "Avoid writing as if" sentence). The range stops at 85 deliberately: line 87 is the `epistemic-model.md` pointer, which this leaf places once at the foot instead.

```markdown
## Judgment rules
```

Verbatim from `git show 1feb088c:skills/writing/SKILL.md | sed -n '26,40p'` (Voice and Tone bullets, then the Hedging Guide table).

```markdown
## Quality criteria
```

Verbatim from `sed -n '44,49p'` (Document Structure), `sed -n '91,95p'` (Formatting Conventions), and `sed -n '99,103p'` (Length Guidelines) of the same file.

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

## Success test

Did the agent carry out the cross-cutting practice according to its workflow, judgment rules, and quality criteria?

## Companion Skills

- [`../research/citation-discipline.md`](../research/citation-discipline.md) - citation format, bibliography keys, and source-pointer conformance.
- [`../research/literature-evaluation.md`](../research/literature-evaluation.md) - selecting and assessing the sources this prose cites.
- [`../statistics/SKILL.md`](../statistics/SKILL.md) - statistical reporting language for pre-registrations, analyses, and verdicts.
- [`../INDEX.md`](../INDEX.md) — the skill index.

For the project's reasoning model, see `docs/user-guide/epistemic-model.md`.
```

The Citation Format section (old L64-73) is **deleted**, not moved — it merged into `citation-discipline.md` in Task 2.

- [ ] **Step 4: Rewrite `skills/writing/SKILL.md` as a router**

Replace the whole file with this, verbatim:

```markdown
---
name: writing
description: Use when scientific prose for a research project is in scope. Routes to the writing leaves below.
provenance: internal
---

# Writing Router

A router carries no methodology; teaching content belongs in a typed leaf.

## Routing trigger

Load this router when writing or editing project prose is in scope, before
loading any leaf.

For analysis-readiness planning, start at [`../INDEX.md`](../INDEX.md) or run
`science-plan-analysis`.

## Scope boundary

Covers prose conventions for project documents — voice, hedging, structure,
and framework connection. Excludes citation conformance and source evaluation
(see [`../research/SKILL.md`](../research/SKILL.md)).

## Leaves

| Leaf | Load when | Do not load when |
|---|---|---|
| [`scientific-writing.md`](scientific-writing.md) | Writing or editing any research document, entity description, or project prose | Only validating citation keys — load `../research/citation-discipline.md` |

## Decision / compose order

Leaves are independent. Compose with
[`../research/citation-discipline.md`](../research/citation-discipline.md)
whenever the prose carries citations.

## Parent & neighbors

- Parent index: [`../INDEX.md`](../INDEX.md)
- Neighboring routers: [`../research/SKILL.md`](../research/SKILL.md), [`../statistics/SKILL.md`](../statistics/SKILL.md)

## Success test

Representative in-scope tasks route to the correct leaf (or the correct compose order when leaves combine) without any methodology being read from this router.

## Companion Skills

- [`../INDEX.md`](../INDEX.md) — the skill index.
```

Planned future leaves (pre-registration prose, results-interpretation, paper-summary) are deliberately **not** listed — a router advertises what exists.

- [ ] **Step 5: Update the companion mapping**

`science/src/science_tool/codex_skills.py:18`:

```python
    CompanionSkill("scientific-writing", Path("skills/writing/scientific-writing.md")),
```

No other generator change — Task 1's `_companion_link_targets` derives everything from `COMPANION_SKILLS`.

- [ ] **Step 6: Verify green, lint, regenerate, commit**

```bash
(cd "$WT/science" && uv run --frozen pytest tests/test_codex_skills.py -v)
(cd "$WT/science" && uv run --frozen science skills lint --root ../skills; echo "LINT_EXIT=$?")
(cd "$WT/science" && uv run python ../scripts/generate_codex_skills.py)
(cd "$WT/science" && uv run --frozen pytest -q >/dev/null 2>&1; echo "PYTEST_EXIT=$?")
(cd "$WT" && git add skills/writing/ science/src/science_tool/codex_skills.py science/tests/test_codex_skills.py codex-skills/ \
  && git commit -m "refactor(skills): extract writing hub and transfer scientific-writing identifier to the leaf")
```

Expected: all codex tests PASS; `LINT_EXIT=0`; `PYTEST_EXIT=0`; `codex-skills/science-scientific-writing/scientific-writing.md` does **not** exist.

---

### Task 4: Cross-subject retargets, index, and doctrine

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

1. Under **Core Analysis Checks**, change the `scientific-writing` line to:
   `- \`scientific-writing\`: \`skills/writing/scientific-writing.md\``
2. Directly below it, add the router:
   `- \`writing\`: \`skills/writing/SKILL.md\``
3. Under **Curation and Evidence**, add:

```markdown
- `research-literature-evaluation`: `skills/research/literature-evaluation.md`
- `research-citation-discipline`: `skills/research/citation-discipline.md`
- `research-proposition-graph-reasoning`: `skills/research/proposition-graph-reasoning.md`
```

4. Leave the Companion Skills block at the foot unchanged — those reference routers *as routers* and are correct.

- [ ] **Step 3: Update `skills/meta/skill-authoring.md:41`**

Replace the router-invariant paragraph with this, verbatim:

```markdown
This is stated as a **target invariant** the corpus is converging on: 4 of 7 current `SKILL.md` files are still **hubs** (route + teach). `research/SKILL.md` and `writing/SKILL.md` were extracted on 2026-07-20 and are now true routers; `data/genomics/SKILL.md` was already one. Every remaining hub is a migration extraction candidate (see the matrix). A document that routes *and* teaches is a hub; its teaching content is extracted into typed leaves before it is a true router.
```

Leave `Placement (pre-migration)` at L36-40 unchanged — this phase adds no directory.

- [ ] **Step 4: Update `skills/meta/skill-taxonomy.md`**

In the Versioning/migration list, append this bullet verbatim:

```markdown
- The router invariant now holds for `research/` and `writing/`, extracted 2026-07-20 into `literature-evaluation`, `citation-discipline`, `proposition-graph-reasoning`, and `scientific-writing`. Four hubs remain (`data/`, `data/expression/`, `pipelines/`, `statistics/`). Reorganizing and renaming the corpus stays deferred to phase 3, because subject is derived from path.
```

- [ ] **Step 5: Update the corpus matrix**

In `docs/plans/2026-07-19-skills-taxonomy-corpus-matrix.md`:

1. Header line 10: `**42 files** — 1 index, 7 routers (6 hubs, 1 pure), 34 leaves` → `**46 files** — 1 index, 7 routers (4 hubs, 3 pure), 38 leaves`.
2. `research/SKILL.md` and `writing/SKILL.md` rows: `router-state` `hub` → `pure-router`; clear the `likely-split?` cell to `— (extracted 2026-07-20)`.
3. Add four leaf rows with archetype, subject `research-methodology` / `writing`, depth `standard`, source-basis `internal`.
4. Tally: `practice-guide` 1 → 3, `normative-reference` 3 → 4, `analysis-discipline` 8 → 9; total 34 → 38.
5. Under "Hub extraction candidates", mark the `research/SKILL.md` and `writing/SKILL.md` entries `DONE 2026-07-20` and leave the other four.
6. In the **Earns-a-template check**, update `practice-guide (0 clean leaves, 2+ trapped)` to `practice-guide (2 clean leaves, extracted 2026-07-20)`.

**Do not** rewrite the eligibility argument to rest on `research-package-rendering`. That force-fit is explicitly excluded from the practice-guide population and its trip-wire stands.

- [ ] **Step 6: Lint, regenerate, verify, commit**

```bash
(cd "$WT/science" && uv run --frozen science skills lint --root ../skills; echo "LINT_EXIT=$?")
(cd "$WT/science" && uv run python ../scripts/generate_codex_skills.py)
(cd "$WT/science" && uv run --frozen pytest -q >/dev/null 2>&1; echo "PYTEST_EXIT=$?")
(cd "$WT" && git add skills/ docs/plans/ codex-skills/ \
  && git commit -m "docs(skills): retarget cross-subject references, index, and router-invariant doctrine")
```

---

### Task 5: Acceptance sweep

No new code. Verify every acceptance item from the design doc and report the command and output for each.

- [ ] **Step 1: Lint and router metadata**

```bash
(cd "$WT/science" && uv run --frozen science skills lint --root ../skills; echo "LINT_EXIT=$?")
(cd "$WT" && git grep -n '^archetype:' skills/research/SKILL.md skills/writing/SKILL.md; echo "ROUTER_ARCHETYPE_HITS=$?")
(cd "$WT" && git grep -c '^archetype:' skills/research/ skills/writing/; echo "GREP_EXIT=$?")
```

Expected: `LINT_EXIT=0`. `ROUTER_ARCHETYPE_HITS=1` (git grep exits 1 on no match) — routers must not declare `archetype:`. The third command reports **eight** archetyped leaves across the two directories: seven under `skills/research/` and one under `skills/writing/`.

- [ ] **Step 2: Router-profile conformance**

Open both routers beside `skills/meta/templates/router.md`. Confirm each carries `## Routing trigger`, `## Scope boundary`, `## Leaves`, `## Decision / compose order`, `## Parent & neighbors`, and `## Success test`, and that no section teaches. Confirm the research router's Leaves table has **seven** rows and retains no proposition-centric model bullets — those belong to `proposition-graph-reasoning.md`.

- [ ] **Step 3: Leaf-template conformance, itemwise**

For each of the four new leaves, open `skills/meta/templates/<archetype>.md` beside it and confirm every slot is present **and filled with content of the kind the slot names**. Lint cannot check this; a prose move can pass lint while failing the typed-leaf goal.

Confirm specifically for `proposition-graph-reasoning.md`: the five-condition table; the no-flag-is-not-certification paragraph; the unevaluated state; the artifact rule naming `## Evidence Quality` / `## Updated Priorities` / `## Knowledge Gaps` / `## Research fronts`; and that the prohibited-language list is **unconditional** — it must read "not licensed by this discipline, ever", with no "without a flagged-condition basis" qualifier that would imply a flag could license a support judgment.

Check `adequate` by reading, not by counting. It legitimately appears three times in the pinned prose — in the no-`adequate`-outcome sentence, in the "equally consistent with adequate support" contrast, and in the "never be written up as adequate" prohibition. What must **not** appear is `adequate` as a *flagged condition* in the outcomes table.

Both practice-guides carry a real `Common pitfalls` and `Outputs`. `citation-discipline.md` carries `Scope`, `Vocabulary / schema`, `Invariants`, `Conformance rules`, `Examples`, `Versioning / migration`, and `Invalid cases` — and does **not** restate the four annotation-token definitions, which stay owned by `docs/conventions/annotation-tokens.md`.

- [ ] **Step 4: Full suite and linters**

```bash
(cd "$WT/science" && uv run --frozen pytest -q >/dev/null 2>&1; echo "PYTEST_EXIT=$?")
(cd "$WT/science" && uv run ruff check; uv run pyright)
```

Expected: `PYTEST_EXIT=0`; only the 4 known ruff and 7 known pyright pre-existing errors. Report any new finding as a failure. The dangling-link sweep and all five destination-class assertions are automated here.

- [ ] **Step 5: Mirror freshness**

```bash
(cd "$WT/science" && uv run python ../scripts/generate_codex_skills.py)
(cd "$WT" && git status --porcelain codex-skills/)
```

Expected: empty output — the committed mirror is byte-identical to fresh generation.

- [ ] **Step 6: Corpus count**

```bash
(cd "$WT" && python3 -c "
import pathlib,re
from collections import Counter
leaves=[p for p in pathlib.Path('skills').rglob('*.md')
        if p.name not in {'SKILL.md','INDEX.md'} and p.parts[1] != 'meta']
c=Counter(re.search(r'^archetype:\s*(\S+)',p.read_text(),re.M).group(1) for p in leaves)
print(len(leaves), dict(sorted(c.items())))")
```

Expected: `38 {'analysis-discipline': 9, 'measurement-qa': 11, 'method-guide': 6, 'normative-reference': 4, 'practice-guide': 3, 'tool-guide': 5}`.

This runs from `$WT`, not `science/` — it is a corpus count over `skills/`, not a package command, so the "Python from `science/`" rule does not apply. `skills/meta/` is excluded **entirely**, not just its `templates/`: it holds two archetyped leaves outside the corpus matrix, and counting them yields 36 at baseline instead of 34. Baseline verified at `1feb088c`: 34 leaves, `practice-guide` 1.

- [ ] **Step 7: Report**

Report each acceptance item with the command run and its output. Never report green from a piped command — capture the exit code before the pipe.
