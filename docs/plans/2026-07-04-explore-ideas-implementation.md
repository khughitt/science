# `/science:explore-ideas` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship `/science:explore-ideas` — a generative pass that proposes the research questions/hypotheses a Science project is *missing*, blind to its existing framing, and applies kept ones as entities with source-faithful origins.

**Architecture:** A slash command (`commands/explore-ideas.md`) orchestrates a blind, parallel per-lens generation phase (a new `agents/idea-lens-researcher.md` with web-only tools), then a full-visibility classify/report phase, then an opt-in `--apply` that shells out to the existing `science questions/hypotheses create --origin/--added-by/--source-ref` seam. The one new Python surface is a backward-compatible `parse_origin_spec` extension (leading `+` → `independent: true`).

**Tech Stack:** Python 3.13 / Click / Pydantic v2 (`science_tool`, `science_model`); Claude slash commands + subagents; OpenAlex/PubMed REST via `WebFetch`.

**Design spec:** `docs/plans/2026-07-04-explore-ideas-design.md` (read it — section refs below point into it).

## Global Constraints

- Command file is `commands/explore-ideas.md` — hyphenated, plural. Agent file is `agents/idea-lens-researcher.md` — unprefixed name (surfaced as `science:idea-lens-researcher`).
- **Blindness invariant (non-negotiable):** `idea-lens-researcher` declares `tools: WebSearch, WebFetch` and NOTHING else — no `Read`, no `Bash`, no `Glob`/`Grep`. Its only project view is the domain brief passed inline. A reviewer must reject any tool that can touch the filesystem.
- Generation phase reads **only** `science.yaml`, `specs/research-question.md`, `specs/scope-boundaries.md`, `entities/topics/`. It must **exclude** `entities/hypotheses/`, `entities/questions/`, `entities/papers/`.
- Lens set (exact names): `mechanism`, `methodology`, `population`, `contrarian`, `analogy`, `temporal`.
- Report home: `entities/meta/explorations/explore-<YYYY-MM-DD>.md`, frontmatter `type: meta`. Same-day collision → suffix `-<HHMM>`.
- Candidate = one fenced ` ```yaml ` block containing a `candidate_id` key. `--apply` parses every such block and nothing else.
- `decision` enum: `keep | drop | defer | applied`. Human sets the first three (default `defer`); `--apply` writes `applied`.
- `--apply` **requires** `--from` (hard error otherwise). v1 apply routes `question`/`hypothesis` only; `topic`/`theme` kept candidates are reported "apply manually", never silently dropped.
- Apply is idempotent via **report write-back** (`decision: applied` + `applied_as:` + `applied_at:`), NOT slug/destination matching (auto-incremented ids would mint duplicates).
- Apply provenance: reasoned → `--origin assistant:explore-ideas-<lens>`; resolved non-predating literature → `--source-ref paper:<slug>` or `--source-ref cite:<key>`; convergent/predating literature → add `--origin +literature:cite:<key>` (independent). `--added-by` = `explore-ideas:<model-id>:<candidate_id>`.
- All origin dates are full `YYYY-MM-DD` (the `OriginRecord` validator rejects year-only, e.g. `2019` fails; `2019-01-01` passes).
- Package layout: **no root `pyproject.toml`**. Run CLI tests from `science/`: `cd science && uv run --frozen pytest`. Lint/types from `science/`: `uv run ruff check`, `uv run pyright` (pyright gates `src/` only, not tests).
- No AI-attribution trailers on commits (no `Co-Authored-By`, no "Generated with Claude Code").
- Editing `commands/` requires regenerating `codex-skills/` (`python scripts/generate_codex_skills.py`); `science/tests/test_codex_skills.py` enforces the mirror. Agents are NOT mirrored to `codex-skills/`.

---

## File Structure

- **Modify** `science/src/science_tool/entities.py` — extend `parse_origin_spec` (Task 1). Single function, ~6 new lines.
- **Modify** `science/tests/test_origin_cli.py` — add `+`-prefix unit tests + one CLI integration test (Task 1).
- **Create** `agents/idea-lens-researcher.md` — the blind per-lens generator (Task 2). Full content in this plan.
- **Create** `commands/explore-ideas.md` — the orchestration command (Task 3). Full spec + copy-exact snippets in this plan.
- **Regenerate** `codex-skills/science-explore-ideas/**` — generated artifact (Task 3).
- **Create** `docs/plans/2026-07-04-explore-ideas-manual-check.md` — fixture report + apply smoke-check procedure (Task 4).

Tasks are ordered so apply's grammar dependency (Task 1) and the dispatched agent (Task 2) exist before the command that uses them (Task 3).

---

## Task 1: `parse_origin_spec` `+`-prefix → `independent`

**Files:**
- Modify: `science/src/science_tool/entities.py:768-793` (the `parse_origin_spec` function)
- Test: `science/tests/test_origin_cli.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `parse_origin_spec(spec: str) -> dict[str, object]` — now recognizes a single leading `+` on the whole spec and adds `"independent": True` to the returned dict. Absent `+` → no `independent` key (unchanged behavior). Flows unchanged through `_build_origin_frontmatter` (cli.py:~1288) into both `hypotheses create` and `questions create`.

**Context:** The current grammar is `TYPE[:REF][@DATE]`. `OriginRecord` (in `science_model/entities.py`) has an `independent: bool = False` field the CLI cannot currently set. Apply needs it for convergent candidates. `+` is unambiguous because `TYPE` is the closed enum `user|assistant|literature`, none of which starts with `+`.

- [ ] **Step 1: Write the failing unit tests**

Append to `science/tests/test_origin_cli.py` (after the existing `parse_origin_spec` tests, before the CLI tests):

```python
def test_parse_independent_prefix_literature() -> None:
    assert parse_origin_spec("+literature:cite:K@2019-01-01") == {
        "type": "literature",
        "ref": "cite:K",
        "date": "2019-01-01",
        "independent": True,
    }


def test_parse_no_prefix_has_no_independent_key() -> None:
    # A plain spec must NOT carry an independent key (defaults False downstream).
    assert parse_origin_spec("literature:cite:K") == {"type": "literature", "ref": "cite:K"}


def test_parse_independent_prefix_on_user() -> None:
    assert parse_origin_spec("+user") == {"type": "user", "independent": True}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_origin_cli.py -k "independent or no_prefix" -v`
Expected: FAIL — `test_parse_independent_prefix_literature` and `test_parse_independent_prefix_on_user` fail because the current parser leaves the `+` in `type_` (`ValidationError`, unknown enum) or drops it; `test_parse_no_prefix_has_no_independent_key` passes already.

- [ ] **Step 3: Implement the extension**

In `science/src/science_tool/entities.py`, replace the body of `parse_origin_spec` so a leading `+` is stripped first and recorded. The full updated function:

```python
def parse_origin_spec(spec: str) -> dict[str, object]:
    """Parse a compact ``[+]TYPE[:REF][@DATE]`` origin spec into a validated dict.

    A single leading ``+`` marks the origin ``independent`` (converged
    independently of the entity's other origins). The remainder is parsed as
    before: a trailing ``@DATE`` is split off first, then ``TYPE:REF`` splits on
    the first ``:`` (so ``literature:paper:smith2019`` yields ref
    ``paper:smith2019``). A bare literature ref (no ``paper:``/``cite:`` prefix)
    is normalized to ``cite:<ref>``. Raises via ``OriginRecord.model_validate``
    if the resulting record is invalid (e.g. a literature origin with no ref, or
    a non ``YYYY-MM-DD`` date).
    """
    independent = False
    if spec.startswith("+"):
        independent = True
        spec = spec[1:]
    date: str | None = None
    if "@" in spec:
        spec, date = spec.rsplit("@", 1)
    if ":" in spec:
        type_, ref = spec.split(":", 1)
    else:
        type_, ref = spec, None
    if type_ == "literature" and ref and not ref.startswith(("paper:", "cite:")):
        ref = f"cite:{ref}"
    record: dict[str, object] = {"type": type_}
    if ref:
        record["ref"] = ref
    if date:
        record["date"] = date
    if independent:
        record["independent"] = True
    OriginRecord.model_validate(record)  # validate/normalize; raises on bad input
    return record
```

- [ ] **Step 4: Run the unit tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_origin_cli.py -k "independent or no_prefix" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Write the CLI integration test**

Append to `science/tests/test_origin_cli.py`:

```python
def test_question_create_writes_independent_origin() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        root = Path.cwd()
        seed_project(root)

        result = runner.invoke(
            main,
            [
                "questions",
                "create",
                "Convergent Q",
                "--origin",
                "assistant:explore-ideas-mechanism",
                "--origin",
                "+literature:cite:Smith2019",
                "--added-by",
                "explore-ideas:test:cand-mechanism-x",
            ],
        )

        assert result.exit_code == 0, result.output
        created = next((root / "entities" / "questions").glob("*.md"))
        text = created.read_text(encoding="utf-8")
        assert "ref: cite:Smith2019" in text
        assert "independent: true" in text
        assert "added_by: explore-ideas:test:cand-mechanism-x" in text
```

- [ ] **Step 6: Run the integration test**

Run: `cd science && uv run --frozen pytest tests/test_origin_cli.py::test_question_create_writes_independent_origin -v`
Expected: PASS. (Confirms the `+` grammar flows through `_build_origin_frontmatter` into the written frontmatter and serializes as `independent: true`.)

- [ ] **Step 7: Lint, then run the full origin test file**

Run: `cd science && uv run ruff check src/science_tool/entities.py tests/test_origin_cli.py && uv run --frozen pytest tests/test_origin_cli.py -q`
Expected: ruff clean; all tests pass.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/entities.py science/tests/test_origin_cli.py
git commit -m "feat(origins): parse_origin_spec accepts +PREFIX for independent origins"
```

---

## Task 2: `idea-lens-researcher` agent

**Files:**
- Create: `agents/idea-lens-researcher.md`

**Interfaces:**
- Consumes: nothing (dispatched by Task 3 with an inline domain brief + lens).
- Produces: a subagent that, given an inline domain brief + one lens + `n` + optional focus, returns a JSON array of candidate objects (`candidate_id`, `proposed_kind`, `title`, `question_or_claim`, `lens`, `rationale`, `literature_anchors[]`, `origin_plan`). Consumed by Task 3's Phase 2/3.

**Context:** Model the frontmatter on `agents/topic-researcher.md` (`name`, `description`, `model`, `tools`). The critical difference: `tools` is web-only. Sibling researcher agents use `model: claude-sonnet-4-6` — match that.

- [ ] **Step 1: Create the agent file**

Write `agents/idea-lens-researcher.md` with exactly this content:

````markdown
---
name: idea-lens-researcher
description: Generate candidate research questions (and testable hypotheses) a project may be MISSING, from ONE analytical lens, blind to the project's existing hypotheses/questions/papers. Given an inline domain brief plus one lens, returns a JSON array of candidate entities grounded in independent literature search. Dispatch one per lens in parallel during /science:explore-ideas generation.
model: claude-sonnet-4-6
tools: WebSearch, WebFetch
---

# Idea Lens Researcher

You are a dispatched subagent in the **generation** phase of
`/science:explore-ideas`. Your job: propose the research questions a project may
be **missing**, seen through **one** analytical lens, and return them as
structured JSON.

You are deliberately **blind** to the project's existing epistemic entities. You
have no filesystem tools — only web search. Everything you know about the project
is the brief in your dispatch prompt. Do not ask for more; do not try to inspect
the repository.

## Inputs (all provided inline in your dispatch prompt)

- **Domain brief** — what the project studies, its scope boundaries, background topics.
- **Lens** — the single frame you generate from, with its meaning.
- **n** — how many candidates to aim for (default 5).
- **Focus** (optional) — a topic to center on within the domain.

## Hard constraints

- **Blindness.** Generate from the brief and your lens ONLY. Novelty and overlap
  are judged later by the orchestrator, which CAN see the existing entities.
  Propose freely — duplicates are filtered downstream, so never self-censor to
  avoid overlap.
- **Stay in your lens.** Every candidate must genuinely arise from your assigned
  frame. Do not drift into other lenses.
- **Ground in literature.** For each candidate, run a focused search and attach
  the real papers that motivate or bear on it, via `WebFetch` on public REST:
  - OpenAlex: `https://api.openalex.org/works?search=<terms>&per-page=5`
  - PubMed esearch → esummary:
    `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<terms>&retmode=json`
  Use `WebSearch` for discovery. Capture **raw** citation metadata only — DOI,
  OpenAlex work id, title, first author, year. NEVER emit `paper:` or `cite:`
  refs; you cannot resolve them (you can't see the project's library).
- **Questions by default.** `proposed_kind` is `question` unless the candidate
  already states a falsifiable claim, in which case `hypothesis`.

## Output contract

Return ONLY a JSON array as your entire final message — no prose around it. Each
element:

```json
{
  "candidate_id": "cand-<lens>-<short-kebab-slug>",
  "proposed_kind": "question",
  "title": "<short title>",
  "question_or_claim": "<the question text, or the falsifiable claim>",
  "lens": "<your lens>",
  "rationale": "<why this is worth asking, from your lens>",
  "literature_anchors": [
    {"doi": "10.xxxx/xxxx", "openalex_id": "Wxxxxxxxxx", "title": "...", "first_author": "Smith", "year": 2021, "note": "how it bears on the candidate"}
  ],
  "origin_plan": {"origins": [{"type": "assistant", "ref": "explore-ideas-<lens>"}], "added_by": "explore-ideas"}
}
```

- `candidate_id`: `cand-` + your lens + a short kebab slug of the title; unique within your output.
- `literature_anchors`: `[]` is allowed if you genuinely found nothing, but try.
- If a found paper **already poses** this same question/claim (predates the idea,
  not merely relevant), set that anchor's `note` to begin with `predates:`. The
  orchestrator uses that signal to add an independent literature origin. Do not
  build literature origins yourself — you cannot resolve them.
````

- [ ] **Step 2: Verify the frontmatter parses and tools are web-only**

Run: `cd "$(git rev-parse --show-toplevel)" && python -c "import yaml,sys; d=yaml.safe_load(open('agents/idea-lens-researcher.md').read().split('---')[1]); assert d['name']=='idea-lens-researcher'; assert [t.strip() for t in d['tools'].split(',')]==['WebSearch','WebFetch'], d['tools']; print('ok')"`
Expected: prints `ok`. (Guards the blindness invariant: exactly `WebSearch, WebFetch`.)

- [ ] **Step 3: Confirm no full-test regression**

Run: `cd science && uv run --frozen pytest tests/test_codex_skills.py -q`
Expected: PASS (agents are not mirrored, so adding this file must not break the codex mirror test).

- [ ] **Step 4: Commit**

```bash
git add agents/idea-lens-researcher.md
git commit -m "feat(agents): add idea-lens-researcher (blind per-lens idea generation)"
```

---

## Task 3: `commands/explore-ideas.md` slash command + codex mirror

**Files:**
- Create: `commands/explore-ideas.md`
- Regenerate: `codex-skills/science-explore-ideas/**` (via the generator script)
- Reference (read first, do not modify): `commands/wander.md`, `commands/big-picture.md`, `commands/next-steps.md`, `references/command-preamble.md`

**Interfaces:**
- Consumes: `agents/idea-lens-researcher.md` (Task 2); `parse_origin_spec` `+` grammar (Task 1) via `science questions/hypotheses create`.
- Produces: the `/science:explore-ideas` command surface. No Python.

**Context:** This is a prose orchestration command like `wander`/`big-picture`. Match their structure: `description:` frontmatter, `$ARGUMENTS` flag parsing, numbered phases, `uv run science …` invocations, subagent dispatch. The command runs inside a *target* Science project (e.g. PAIS), not this toolkit repo.

- [ ] **Step 1: Read the reference commands**

Read `commands/wander.md` (phase/report structure + `--apply` gating precedent), `commands/big-picture.md` (parallel per-hypothesis subagent dispatch precedent), and `references/command-preamble.md` (Setup/role resolution). Write the new command in that idiom.

- [ ] **Step 2: Author `commands/explore-ideas.md`**

Create the file with this frontmatter verbatim:

```markdown
---
description: Generate the candidate research questions (and testable hypotheses) a project is MISSING — a blind, multi-lens idea-expansion pass de-anchored from the existing hypotheses. Report-first; --apply promotes kept candidates to entities with source-faithful origins. Use when the user asks "what questions/hypotheses are we missing?".
---
```

Immediately after the frontmatter, add a top-level heading line `# Explore Ideas` — this is **required**: `generate_codex_skills` (codex_skills.py:85) raises `Command file is missing a top-level heading` without one. Then author the body with these sections and **exact** contracts. (Write real prose in the wander/big-picture idiom — this list is the required content, not the literal text.)

**## Flags** — parse `$ARGUMENTS`:
- Generate mode (default, read-only): `--center <topic-id>`, `--topic <name>`, `--lens <name>` (repeatable; default = all six lenses), `--n <k>` (default 5), `--commit`.
- Apply mode: `--apply`, `--from <report-path-or-id>` (**required** with `--apply` — if `--apply` is present without `--from`, STOP with a clear error), `--commit`.
- `--center`/`--topic` accept **topics only** in v1; if given a hypothesis/question id, refuse and say hypothesis-centering is deferred.

**## Setup** — follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` (role: `research-assistant`), same as `next-steps`/`search-literature`.

**## Mode detection** — `--apply` present → Apply mode (skip generation). Else Generate mode.

**### Generate — Phase 1: Frame.** Read **only** `science.yaml`, `specs/research-question.md`, `specs/scope-boundaries.md`, `entities/topics/` (skip absent). State explicitly that `entities/hypotheses/`, `entities/questions/`, `entities/papers/` are **excluded** and must not be read here. If `--center`/`--topic`, fold that topic's subject terms into the brief. Produce a compact prose **domain brief**.

**### Generate — Phase 2: Generate (parallel, blind).** For each selected lens, dispatch an `idea-lens-researcher` subagent **in parallel** (dispatch by the agent's frontmatter `name`, bare — same as `commands/research-papers.md` uses `subagent_type: paper-researcher`), passing **inline**: the domain brief, the lens name + its meaning (from the table below), `n`, and any focus. Collect each agent's JSON array. Lens table (exact names + frames):

| Lens | Frame |
|------|-------|
| `mechanism` | causal/biological mechanism and pathway |
| `methodology` | measurement, assay, study-design, analysis method |
| `population` | population, context, subgroup, setting, boundary conditions |
| `contrarian` | what if the dominant assumption is wrong; null/negative framing |
| `analogy` | cross-disciplinary analogy — how an adjacent field would frame it |
| `temporal` | temporal/longitudinal/dynamics dimension |

**### Generate — Phase 3: Classify (full visibility).** Now load the existing surface: `uv run science project index --format json` (hypotheses + questions) plus `entities/topics/`. Then:
1. **Slug pre-pass:** slugify each candidate title; exact/near-exact collision with an existing id/title → mark `already-covered` (or `sharpens-existing`) without agent judgment.
2. **Agent-judged buckets:** for the rest, compare against the index; **read the referenced source files** when title-level info is insufficient for likely overlaps/refinements; assign exactly one `novelty_bucket` ∈ {`novel`, `sharpens-existing`, `already-covered`, `out-of-scope`}. Set `related_existing` for the middle two.
3. **Anchor resolution:** for each `literature_anchors[]` entry, add a resolved `ref`: `paper:<slug>` if the DOI/title matches an entity in `entities/papers/`; `cite:<key>` if the DOI/key is in `papers/references.bib`; else leave `ref` null (stays raw → no literature origin). Finalize `origin_plan` accordingly (see Phase-4 origin rules).

**### Generate — Phase 4: Report.** Write `entities/meta/explorations/explore-<YYYY-MM-DD>.md` (`type: meta`; same-day collision → `-<HHMM>` suffix). Present candidates **neutrally** — never rank/group so as to privilege a source or lens. `novel` + `sharpens-existing` shown prominently; `already-covered` collapsed; `out-of-scope` listed separately. Each candidate is one fenced ` ```yaml ` block carrying every schema field. Canonical block (copy this shape exactly):

```yaml
candidate_id: cand-mechanism-vagal-cytokine-feedback
proposed_kind: question
title: Vagal tone as a cytokine feedback regulator
question_or_claim: Does reduced vagal tone sustain systemic inflammation in post-acute infection syndromes?
lens: mechanism
rationale: >
  The cholinergic anti-inflammatory pathway is established in acute sepsis but
  under-explored as a chronic feedback failure in post-acute syndromes.
literature_anchors:
  - doi: 10.1000/example
    openalex_id: W1234567890
    title: Cholinergic control of inflammation
    first_author: Smith
    year: 2021
    note: relevant mechanism review
    ref: null
novelty_bucket: novel
related_existing: []
decision: defer
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
  added_by: explore-ideas
```

Origin-plan finalization rules (write these into the block during Phase 3→4):
- Purely reasoned → `origins: [{type: assistant, ref: explore-ideas-<lens>}]`.
- A resolvable anchor whose `note` began with `predates:` → ALSO add `{type: literature, ref: <paper:slug|cite:key>, independent: true}` (convergent).
- A resolvable anchor that merely supports (no `predates:`) → the paper belongs in the entity's `source_refs`, NOT as an origin. Keep the origin `assistant` only.
- If `--commit`: commit the report with `doc(explore-ideas): report YYYY-MM-DD`.

**### Apply mode.** Require `--from`; resolve id → `entities/meta/explorations/explore-<id>.md` (or use the literal path). Parse **every** fenced `yaml` block containing a `candidate_id`. For each block:
- `decision: keep` and `proposed_kind` ∈ {`question`,`hypothesis`} → build and run the create command (templates below), capture the created entity id, then **write back** into that block: `decision: applied`, `applied_as: <entity-id>`, `applied_at: <YYYY-MM-DD>`.
- `decision: applied` → skip (idempotent).
- `decision: keep` but `proposed_kind` ∈ {`topic`,`theme`} → do NOT create; list under "apply manually (CLI seam pending)".
- `decision: drop`/`defer` → skip.
Report created vs skipped counts. If `--commit`: commit created entities + the updated report with `feat(explore-ideas): apply kept candidates YYYY-MM-DD`.

Create command templates (copy-exact; `<model-id>` = the model running this command). No `--slug` — the create path auto-derives the id from the title, and idempotence comes from report write-back (§9), not slug matching. Forward traceability is the `candidate_id` in `--added-by`.

```bash
# reasoned-only question
uv run science questions create "<title>" \
  --origin "assistant:explore-ideas-<lens>" \
  --added-by "explore-ideas:<model-id>:<candidate_id>"

# convergent hypothesis (reasoned + predated in literature), plus a supporting (non-predating) paper
uv run science hypotheses create "<title>" \
  --origin "assistant:explore-ideas-<lens>" \
  --origin "+literature:cite:<predating-key>" \
  --source-ref "paper:<supporting-slug>" \
  --added-by "explore-ideas:<model-id>:<candidate_id>"
```

Literature anchor routing: a resolved anchor whose `note` began with `predates:` becomes an independent `--origin "+literature:<paper:slug|cite:key>"`; a resolved anchor that merely **supports** becomes `--source-ref "<paper:slug|cite:key>"` (provenance kept, but not an origin — origin stays `assistant`); an **unresolved** raw anchor is dropped from the create call (no origin, no source-ref) until the paper is imported.

- [ ] **Step 3: Regenerate the codex-skills mirror**

Run: `cd "$(git rev-parse --show-toplevel)" && python scripts/generate_codex_skills.py`
Expected: prints `Generated Codex skills in …/codex-skills`; creates `codex-skills/science-explore-ideas/`.

- [ ] **Step 4: Verify the codex sync test passes**

Run: `cd science && uv run --frozen pytest tests/test_codex_skills.py -q`
Expected: PASS (the mirror now matches `commands/explore-ideas.md`).

- [ ] **Step 5: Commit**

```bash
git add commands/explore-ideas.md codex-skills/
git commit -m "feat(commands): add /science:explore-ideas idea-expansion command"
```

---

## Task 4: Apply smoke-check fixture + procedure

**Files:**
- Create: `docs/plans/2026-07-04-explore-ideas-manual-check.md`

**Interfaces:**
- Consumes: the Task 3 command + Task 1 grammar.
- Produces: a committed fixture report and a documented manual procedure proving the apply round-trip (create-call mapping, write-back, idempotence). Per design §13 this is a smoke/manual check, not pytest (apply is agent-executed prose, and the toolkit repo is not itself a Science project).

**Context:** The check is run by a human against a throwaway Science project (or the sibling `meta/` project), because `--apply` needs a real project with `entities/`. The fixture must include mixed `decision` values and one convergent candidate so all origin branches are exercised.

- [ ] **Step 1: Write the manual-check doc**

Create `docs/plans/2026-07-04-explore-ideas-manual-check.md` containing:

1. A short intro: what this verifies and why it's manual (not pytest).
2. A complete fixture report body — a `type: meta` frontmatter plus **three** candidate `yaml` blocks:
   - one `decision: keep`, `proposed_kind: question`, reasoned-only with one resolved non-predating literature anchor (so apply must pass `--source-ref` and the created entity must carry `source_refs`);
   - one `decision: keep`, `proposed_kind: hypothesis`, **convergent** (origin_plan has an `assistant` origin AND a `{type: literature, ref: cite:<key>, independent: true}` origin);
   - one `decision: drop` (must NOT be created).
3. The procedure, with expected results:
   - Copy the fixture to `entities/meta/explorations/explore-<date>.md` in a scratch project.
   - Run `/science:explore-ideas --apply --from explore-<date>` (or the CLI-equivalent create commands shown in the command doc).
   - Expected: exactly 2 entities created (the two `keep`s), none for the `drop`; the reasoned-only question's frontmatter includes the resolved supporting paper under `source_refs` and does **not** add it as a literature origin; the convergent one's frontmatter shows two `origins` with `independent: true` on the literature one; both created blocks flip to `decision: applied` with `applied_as`/`applied_at`.
   - Re-run the same apply → expected: 0 created, 2 skipped (idempotent).
   - Confirm `science validate` on the scratch project shows no new ERRORs from the created entities (a raw/unresolved `cite:` key is an expected WARN only).

- [ ] **Step 2: Sanity-check the fixture parses as YAML**

Run: `cd "$(git rev-parse --show-toplevel)" && python -c "import yaml,re; t=open('docs/plans/2026-07-04-explore-ideas-manual-check.md').read(); blocks=re.findall(r'\`\`\`yaml\n(.*?)\`\`\`', t, re.S); cands=[yaml.safe_load(b) for b in blocks if 'candidate_id' in b]; assert len(cands)==3, len(cands); assert sum(c['decision']=='keep' for c in cands)==2; assert any(any(o.get('independent') for o in c['origin_plan']['origins']) for c in cands); assert any(any(a.get('ref') for a in c.get('literature_anchors', []) if not str(a.get('note', '')).startswith('predates:')) for c in cands); print('ok', len(cands))"`
Expected: prints `ok 3`. (Confirms the fixture has 3 candidate blocks, 2 `keep`, a convergent independent origin, and at least one resolved non-predating anchor for the `--source-ref` branch — the shape the procedure relies on.)

- [ ] **Step 3: Commit**

```bash
git add docs/plans/2026-07-04-explore-ideas-manual-check.md
git commit -m "docs(explore-ideas): apply smoke-check fixture and procedure"
```

---

## Final verification (after all tasks)

- [ ] `cd science && uv run --frozen pytest -q` — full tool suite green (Task 1 tests + codex mirror).
- [ ] `cd science/model && uv run --frozen pytest -q` — model suite green (unaffected, but confirm).
- [ ] `cd science && uv run ruff check && uv run pyright` — lint + types clean.
- [ ] `git status` — only the intended files changed (entities.py, test_origin_cli.py, the two new markdown surfaces, regenerated codex-skills, the manual-check doc).

## Self-Review (author checklist — completed)

**Spec coverage:** §2 blindness → Task 2 tools invariant + Step-2 guard; §4 flags → Task 3 Flags; §5 phases → Task 3 Generate Phases 1-4; §6 lenses → Task 3 lens table (exact names); §7 dedup → Phase 3 pre-pass + buckets; §8 grounding/anchor split → Task 2 constraints + Task 3 Phase 3 resolution; §9 report format + write-back → Task 3 Phase 4 + Apply; §10 origins + `+` grammar → Task 1 + Task 3 templates; §11 agent → Task 2; §12 footprint → Tasks 1-3; §13 tests → Task 1 (deterministic) + Task 4 (smoke). No gaps.

**Placeholder scan:** none — every code/markdown step carries full content or an exact contract + copy-exact snippet.

**Type consistency:** `parse_origin_spec` return dict shape, `candidate_id`/`decision`/`origin_plan` field names, lens names, and the `+literature:` / `assistant:explore-ideas-<lens>` origin spellings are identical across Task 1, Task 2's output contract, Task 3's templates, and Task 4's fixture.
