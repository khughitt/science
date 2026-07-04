# `/science:explore-ideas` — Design

> **Status:** design accepted (brainstorming). Implementation plan to follow via
> `writing-plans`.
> **Date:** 2026-07-04
> **Depends on:** the entity origin-provenance feature (`origins` / `added_by`,
> merged to main `f33e331e`; impossible-date fix `ed87ab4c`). This design
> consumes that model as its apply-time provenance seam.

## 1. Motivation & niche

The PAIS project (`~/d/health/processes/post-acute-infection`) is organized
around 9 hypotheses. The motivating question — *"what interesting questions
(and hypotheses) are we **missing**?"* — is not answerable by any existing
command, because every existing command **reviews what already exists**:

- `wander` — serendipitous review of *existing* entities for gaps/connections.
- `next-steps` — coverage-gap analysis → prioritized *actions* (not new entities).
- `search-literature` — literature search → a *reading queue* of papers.
- `bias-audit` / `critique-approach` / `compare-hypotheses` — audit/critique
  what is already framed.

`/science:explore-ideas` is the only **generative** pass: it produces the
candidate epistemic entities the project **does not yet have**, deliberately
de-anchored from the current framing, and records kept ones with source-faithful
provenance so they are judged on evidence — not on who proposed them.

## 2. Core principle: blindness by input boundary, not by prompt vibes

The distinctive claim of this design is that anti-anchoring is **structural**.
During generation, the lens agents are never given the project's existing
hypotheses, questions, or papers. They cannot cluster near the current framing
because they cannot see it. Novelty is judged only *afterward*, in a separate
step that has full visibility. Blindness is enforced by **what the orchestrator
hands each agent** (a domain brief that excludes those inputs) plus an explicit
prohibition in the agent contract — not by asking a single prompt to "be
unbiased."

## 3. Non-goals (v1)

- No embedding/vector similarity engine. Dedup is agent-judged with a cheap
  deterministic slug-collision pre-pass (§7).
- No new Python subsystem. v1 is a slash command + a dedicated agent,
  orchestrating existing CLIs. A durable `science explore-ideas` CLI is a
  deferred follow-up, added only if the slash command becomes too procedural.
- No auto-promotion. Applying candidates is an explicit, human-gated second pass.
- v1 apply auto-creates **questions and hypotheses only** (the kinds whose
  `create` CLI already carries the `--origin`/`--added-by` seam). `topic`/
  `theme` candidates may be *proposed* in the report but are applied manually
  until those create commands gain the same seam (§10, §12).

## 4. Run model & flags

Invocation: `/science:explore-ideas [flags]`. Command file:
`commands/explore-ideas.md` (hyphenated, plural, consistent with existing
slash-command naming).

Two modes, selected by the presence of `--apply`:

**Generate mode (default, read-only):**

- Project-wide by default.
- `--center <id>` — narrow generation around one hypothesis/topic. Only a
  **focus area** derived from the center (its subject/topic terms) is added to
  the brief; the center's own claim text and all sibling hypotheses/questions
  remain excluded (blindness holds — centering steers *where* to look, it does
  not reveal *what is already claimed*).
- `--topic <name>` — narrow around a named topic instead of the whole project.
- `--lens <name>` (repeatable) — restrict to specific lenses; default = all (§6).
- `--n <k>` — target candidates per lens (default 5).
- `--commit` — auto-commit the written report.

**Apply mode (`--apply`, side-effecting):**

- `--apply` — promote candidates marked `decision: keep`.
- `--from <report-path-or-id>` — **required** with `--apply`. Applies a specific
  report; never guesses "the latest." The id is the report's date-slug
  (e.g. `explore-2026-07-04`) or an explicit path.
- `--commit` — auto-commit the created entities.

Refusing `--apply` without `--from` is a hard error (fail early).

## 5. Pipeline

### Phase 1 — Frame (assemble the blind domain brief)

Read **only** these, in this order, skipping any that are absent:

1. `science.yaml` (project domain, aspects, scope signals)
2. `specs/research-question.md`
3. `specs/scope-boundaries.md`
4. `entities/topics/`

Deliberately **exclude** `entities/hypotheses/`, `entities/questions/`, and
`entities/papers/`. The lens agents discover literature independently (§8); they
must not be seeded with the project's existing paper set or epistemic framing.

Product: a **domain brief** — a compact prose description of what the project is
about, its scope boundaries, and its background topics. This is the only project
context the lens agents receive.

### Phase 2 — Generate (parallel, blind)

Dispatch one `idea-lens-researcher` subagent **per lens**, in parallel. Each
receives: the domain brief, its single lens spec, `--n`, and any `--center`/
`--topic` narrowing. Each returns a list of **candidate entities** conforming to
the candidate schema (§9), minus the fields Phase 3 fills
(`novelty_bucket`, `related_existing`). No lens agent is given — or may read —
existing hypotheses, questions, or papers.

### Phase 3 — Classify (full visibility)

Now, and only now, load the existing epistemic surface via
`science project index --format json` (all hypotheses + questions with titles and
statuses) plus `entities/topics/` for scope.

1. **Deterministic pre-pass (cheap):** slugify each candidate title and compare
   against slugified existing entity ids/titles. Exact or near-exact collisions
   are marked immediately (`already-covered` or `sharpens-existing`) without
   spending agent judgment.
2. **Agent-judged classification:** the orchestrator (or a classifier step)
   assigns every remaining candidate exactly one `novelty_bucket`:
   - `novel` — no existing entity covers it.
   - `sharpens-existing` — a sharper/edge variant of an existing entity;
     `related_existing` names it.
   - `already-covered` — an existing entity already asks this; `related_existing`
     names it. Collapsed in the report (evidence the pass isn't blind-spotting).
   - `out-of-scope` — falls outside `scope-boundaries.md`. Surfaced but not
     promoted by default.

### Phase 4 — Report

Write the report artifact (§9). Candidates are presented **neutrally** — never
ranked or grouped by source/lens in a way that privileges one origin over
another. `novel` and `sharpens-existing` are shown prominently; `already-covered`
is collapsed; `out-of-scope` is listed separately.

## 6. Lens set

Fixed, domain-neutral default set; `--lens` restricts or overrides. Each lens is
orthogonal so coverage is *forced* across angles rather than clustering:

| Lens | Frame |
|------|-------|
| `mechanism` | causal/biological mechanism and pathway |
| `methodology` | measurement, assay, study-design, analysis method |
| `population` | population, context, subgroup, setting, boundary conditions |
| `contrarian` | what if the dominant assumption is wrong; null/negative framing |
| `analogy` | cross-disciplinary analogy — how an adjacent field would frame it |
| `temporal` | temporal/longitudinal/dynamics dimension |

## 7. Dedup / novelty (v1 contract)

- Deterministic slug-collision pre-pass first (cheap, catches obvious dups).
- Agent-judged buckets for the rest: `novel`, `sharpens-existing`,
  `already-covered`, `out-of-scope`.
- No embedding similarity in v1.
- Classification compares against **questions + hypotheses** (via
  `science project index`); topics inform `out-of-scope` scope judgments.

## 8. Literature grounding

Each lens agent does a focused, lens-specific search using the existing
OpenAlex/PubMed source skills (the same ones `search-literature` uses). Grounding
rules:

- If a supporting paper is **already in** `entities/papers/`, the anchor resolves
  to `paper:<slug>`.
- If the key is **already in** `papers/references.bib`, the anchor may be
  `cite:<key>`.
- Otherwise the anchor is recorded as a **raw citation** in the report; it does
  **not** become a `cite:`/`paper:` origin until the paper is imported. Until
  then the candidate's origin stays `assistant` (§10). This respects the
  `origins` validate check (unresolved `cite:`/`paper:` → WARN).

## 9. Report artifact

**Home:** follows the `wander` precedent —
`entities/meta/explorations/explore-<YYYY-MM-DD>.md`, `type: meta`. (The
validator requires `type: meta` entities under `entities/meta/`.) If a same-day
report exists, suffix with `-<HHMM>` rather than overwrite.

**Per-candidate schema** (the stable contract `--apply` consumes):

| Field | Meaning |
|-------|---------|
| `candidate_id` | stable slug, `cand-<lens>-<short-slug>` — apply's key |
| `proposed_kind` | `question` (default) \| `hypothesis` \| `topic` \| `theme` |
| `title` | short title |
| `question_or_claim` | the actual question text, or the falsifiable claim |
| `lens` | producing lens |
| `rationale` | why this is worth asking (the reasoning) |
| `literature_anchors` | list of `{ref, note}`; `ref` = `paper:<slug>` \| `cite:<key>` \| raw citation |
| `novelty_bucket` | `novel` \| `sharpens-existing` \| `already-covered` \| `out-of-scope` |
| `related_existing` | existing entity ids this overlaps/refines |
| `decision` | `keep` \| `drop` \| `defer` (default `defer`) — human-edited |
| `origin_plan` | structured `origins` + `added_by` apply will stamp (§10) |

`proposed_kind` is `hypothesis` only when `question_or_claim` already states a
falsifiable claim; otherwise `question`.

## 10. `--apply` & origins (reuse of the provenance seam)

Apply reads the `--from` report and, for every candidate with `decision: keep`,
**shells out to the existing create path** — no new write path:

```
uv run science questions create   … --origin <spec> [--origin <spec>] --added-by explore-ideas:<model>
uv run science hypotheses create  … --origin <spec> [--origin <spec>] --added-by explore-ideas:<model>
```

`origin_plan` → concrete `--origin`/`--added-by` args:

- **Purely reasoned** candidate → `--origin assistant:explore-ideas-<lens>`.
- **Literature-traced** candidate whose anchor is a resolvable `paper:<slug>` /
  `cite:<key>` → `--origin literature:paper:<slug>` (or `cite:<key>`).
- **Convergent** (independently reasoned *and* found in the literature) → two
  `--origin`s, with `independent` set on the literature one (the
  "we predicted it AND it's predated in the lit" case the model was built for).
- `--added-by` is always `explore-ideas:<model-id>`.
- Unresolved raw citations do **not** produce a literature origin; the candidate
  stays `assistant`-origin until the paper is imported.

Apply behavior:

- Idempotent: skip candidates whose target entity already exists; report
  created vs skipped counts.
- v1 routes `question`/`hypothesis` only. `topic`/`theme` kept candidates are
  reported as "apply manually (CLI seam pending)" rather than silently dropped.

## 11. The `idea-lens-researcher` agent

New agent file: `agents/idea-lens-researcher.md` (unprefixed filename, per repo
convention; surfaced as `science:idea-lens-researcher`).

- **Purpose:** given a domain brief + one lens, generate `--n` candidate entities
  in that frame, each grounded by an independent literature search.
- **Tools:** Read (scoped), WebSearch/WebFetch, Bash (for the OpenAlex/PubMed
  source skills). *No* access to — and an explicit prohibition against reading —
  `entities/hypotheses/`, `entities/questions/`, `entities/papers/`.
- **Output contract:** a JSON list of candidates matching §9 minus
  `novelty_bucket` / `related_existing` (filled in Phase 3) and minus `decision`
  (defaults `defer`). Includes a provisional `origin_plan`.
- **Blindness clause:** the single most important instruction — the agent
  proposes from its lens and the brief only, and must not attempt to look up or
  reconcile against the project's existing epistemic entities.

## 12. New-code footprint & deferred work

**v1 builds:**
- `commands/explore-ideas.md` (+ regenerated `codex-skills/` mirror).
- `agents/idea-lens-researcher.md`.

**v1 reuses (no new code):** `science project index` (dedup input),
`science questions/hypotheses create --origin/--added-by` (apply), the
OpenAlex/PubMed source skills (grounding).

**Deferred:**
- `--origin`/`--added-by` on `topics`/`themes` create commands, to let apply
  route those kinds.
- A durable `science explore-ideas classify|apply` CLI, if/when the slash
  command's classify/apply logic outgrows prose orchestration.
- Embedding-based dedup.

## 13. Testing considerations

- The command and agent are prose surfaces; the enforceable contracts are:
  (a) the frame-input boundary (generation must not read the excluded dirs),
  (b) the candidate schema, (c) the apply → `create --origin` mapping.
- Apply's origin-spec construction is the piece most worth a deterministic test:
  given an `origin_plan`, assert the exact `--origin`/`--added-by` args, reusing
  the `parse_origin_spec` guarantees already tested in the provenance feature.
- `codex-skills/` sync test must pass after adding the command
  (`scripts/generate_codex_skills.py`).
