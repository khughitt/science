# `/science:explore-ideas` — Design

> **Status:** design accepted (brainstorming). Implementation plan to follow via
> `writing-plans`.
> **Date:** 2026-07-04
> **Depends on:** the entity origin-provenance feature (`origins` / `added_by`,
> merged to main `f33e331e`; impossible-date fix `ed87ab4c`). This design
> consumes that model as its apply-time provenance seam.
>
> **Revision (2026-07-04, review round 1):** resolved five contract gaps —
> structural blindness by tool restriction (§2, §11); `independent` via a small
> `--origin` grammar extension (§10, §12); explicit fenced-YAML report format
> (§9); `--center` limited to topics in v1 (§4); idempotence via report
> write-back rather than slug matching (§9, §10).

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
hypotheses, questions, or papers, and — crucially — **cannot read them**. The
`idea-lens-researcher` agent is declared with web tools **only** (`WebSearch`,
`WebFetch`); it has no `Read` and no `Bash`, so it physically cannot open the
repository. The orchestrator passes the domain brief **inline in the dispatch
prompt**; the agent's entire view of the project is that text. Novelty is judged
only *afterward*, in a separate step run by the orchestrator (which is not
blind) with full visibility.

This is stronger than the usual "instruction-level" blindness: agent tool
declarations in this repo are broad capability names (`Read`, `Bash`), which
cannot be directory-scoped, so a prohibition alone would be unenforceable. By
withholding filesystem tools entirely, blindness becomes a property of the
agent's capability set, not of its prompt. Literature grounding therefore runs
over public REST endpoints via `WebFetch` (§8), not the Bash-based source
skills.

## 3. Non-goals (v1)

- No embedding/vector similarity engine. Dedup is agent-judged with a cheap
  deterministic slug-collision pre-pass (§7).
- No new Python subsystem. v1 is a slash command + a dedicated agent,
  orchestrating existing CLIs. The one bounded Python change is a small
  backward-compatible extension to `parse_origin_spec` so a leading `+` marks an
  origin `independent` (§10) — required because apply is create-only and the
  current grammar cannot express it. A durable `science explore-ideas` CLI is a
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
- `--center <topic-id>` — narrow generation around one **topic** (v1 accepts
  topic ids only; hypothesis/question centering is deferred, see below). The
  topic's subject terms are folded into the brief; since topics are already an
  allowed brief input, no blindness question arises. Centering on a *hypothesis*
  is deferred precisely because deriving focus terms from a claim would require
  the orchestrator to read that claim and risk anchoring — out of scope for v1.
- `--topic <name>` — narrow around a named topic instead of the whole project
  (equivalent to `--center` by name rather than id).
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
receives — **inline in the dispatch prompt** — the domain brief, its single lens
spec, `--n`, and any `--center`/`--topic` narrowing. Because the agent has only
web tools (no `Read`/`Bash`), the inline brief is its entire project view; it
cannot read existing hypotheses, questions, or papers even if it tried. Each
returns a list of **candidate entities** conforming to the candidate schema
(§9), minus the fields Phase 3 fills (`novelty_bucket`, `related_existing`).

### Phase 3 — Classify (full visibility)

Now, and only now, load the existing epistemic surface. Start with
`science project index --format json` (all hypotheses + questions with titles and
statuses) plus `entities/topics/` for scope. The index is the compact routing
surface, not the whole novelty basis: for candidates that look like likely
overlaps or refinements by title/id, the orchestrator reads the referenced source
files before assigning a final novelty bucket.

1. **Deterministic pre-pass (cheap):** slugify each candidate title and compare
   against slugified existing entity ids/titles. Exact or near-exact collisions
   are marked immediately (`already-covered` or `sharpens-existing`) without
   spending agent judgment.
2. **Agent-judged classification:** the orchestrator (or a classifier step)
   compares each remaining candidate against the index, reading source files for
   likely overlaps/refinements when title-level information is insufficient, and
   assigns exactly one `novelty_bucket`:
   - `novel` — no existing entity covers it.
   - `sharpens-existing` — a sharper/edge variant of an existing entity;
     `related_existing` names it.
   - `already-covered` — an existing entity already asks this; `related_existing`
     names it. Collapsed in the report (evidence the pass isn't blind-spotting).
   - `out-of-scope` — falls outside `scope-boundaries.md`. Surfaced but not
     promoted by default.
3. **Anchor resolution:** resolve each candidate's raw literature anchors to
   `paper:<slug>` / `cite:<key>` where they match `entities/papers/` or
   `papers/references.bib` (§8); unresolved anchors stay raw. This is where the
   `origin_plan`'s literature refs are finalized — only the orchestrator, not the
   blind lens, can do it.

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

Each lens agent does a focused, lens-specific search. Because the agent has no
`Bash` (blindness, §2), it queries the public REST endpoints directly via
`WebFetch` — OpenAlex (`https://api.openalex.org/works?search=…`) and PubMed
E-utilities (`https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?…`) —
plus `WebSearch` for discovery. These are the same sources `search-literature`
uses, reached over HTTP rather than through the Bash-based source skills.

**Division of labor (the lens phase is blind, so it cannot resolve anchors).**
A lens agent has no way to know what is already in `entities/papers/` or
`papers/references.bib` — it can't read them. So:

- **Lens agent (blind, generation):** attaches to each candidate the **raw
  citation metadata** it found — DOI, OpenAlex work id, title, first author,
  year. It never emits a `paper:`/`cite:` ref.
- **Orchestrator (full visibility, Phase 3):** resolves each raw anchor —
  → `paper:<slug>` when the DOI/title matches an entity in `entities/papers/`;
  → `cite:<key>` when the DOI/key is in `papers/references.bib`;
  → otherwise it stays a **raw citation**, yields **no** literature origin, and
  the candidate's origin remains `assistant` (§10) until the paper is imported.
  This respects the `origins` validate check (unresolved `cite:`/`paper:` → WARN).

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
| `literature_anchors` | list of `{doi, openalex_id, title, first_author, year, date?, note}` as emitted by the blind lens (`date` is the full `YYYY-MM-DD` when the source gives one); the orchestrator adds a resolved `ref` (`paper:<slug>` \| `cite:<key>`) in Phase 3 where it matches, else leaves it raw |
| `novelty_bucket` | `novel` \| `sharpens-existing` \| `already-covered` \| `out-of-scope` |
| `related_existing` | existing entity ids this overlaps/refines |
| `decision` | `keep` \| `drop` \| `defer` (human-edited, default `defer`) \| `applied` (terminal state written by `--apply`, never set by hand) |
| `origin_plan` | structured `origins` only (§10); `added_by` is not stored here — apply stamps it fresh as `explore-ideas:<model-id>:<candidate_id>` |

`proposed_kind` is `hypothesis` only when `question_or_claim` already states a
falsifiable claim; otherwise `question`.

**Concrete format (the parse contract).** The report is a single markdown file.
Each candidate is a fenced ` ```yaml ` block whose mapping carries every schema
field above; the surrounding markdown (headings, the collapsed `already-covered`
list, prose summary) is for humans and is ignored by the parser. `--apply`
parses **every fenced `yaml` block that contains a `candidate_id` key** — nothing
else. The human triages by editing `decision:` inside these blocks. A single
self-contained, human-editable, machine-parseable artifact (chosen over a JSON
sidecar so the thing the human edits and the thing apply reads are the same
file, never skewed).

**Apply write-back (idempotence key).** Auto-incremented numeric ids mean a
deterministic `--slug` does **not** prevent duplicates on re-apply (§10). So the
report is the durable ledger: after apply successfully creates an entity for a
candidate, it **rewrites that candidate's block** in place — `decision: applied`,
plus `applied_as: <created-entity-id>` and `applied_at: <YYYY-MM-DD>`. Re-running
`--apply --from <same-report>` skips any candidate already marked `applied`.
This makes apply idempotent without an external ledger and records the
candidate → entity mapping where a reader will find it.

## 10. `--apply` & origins (reuse of the provenance seam)

Apply reads the `--from` report and, for every candidate with `decision: keep`,
**shells out to the existing create path** — no new write path:

```
uv run science questions create   … --origin <spec> [--origin <spec>] --added-by explore-ideas:<model>
uv run science hypotheses create  … --origin <spec> [--origin <spec>] --added-by explore-ideas:<model>
```

`origin_plan` plus resolved anchors → concrete create args:

- **Purely reasoned** candidate → `--origin assistant:explore-ideas-<lens>`.
- **Resolved supporting literature** whose anchor does **not** claim priority →
  `--source-ref paper:<slug>` or `--source-ref cite:<key>`. Supporting literature
  is provenance for the entity, but not an originator.
- **Convergent** (independently reasoned *and* found in the literature) → two
  `--origin`s, with the literature one marked independent. This is reserved for
  anchors whose note begins with `predates:` (the paper already posed the same
  question/claim, not merely supported it):
  `--origin '+literature:cite:<key>'` (the "we predicted it AND it's predated in
  the lit" case the model was built for).
- `--added-by` is `explore-ideas:<model-id>:<candidate_id>` — the trailing
  `candidate_id` gives forward traceability from the created entity back to the
  report block.
- Unresolved raw citations do **not** produce a literature origin; the candidate
  stays `assistant`-origin until the paper is imported.

**`--origin` grammar extension (the one bounded Python change).**
`parse_origin_spec` currently accepts `TYPE[:REF][@DATE]` and has no way to set
`independent`. Extend it backward-compatibly: a leading `+` on the spec sets
`independent: true` (e.g. `+literature:cite:Smith2019@2019-01-01`, or with the
`@DATE` omitted). Unambiguous because
`TYPE` is a closed enum (`user|assistant|literature`) that never starts with `+`.
This keeps apply fully automated (no manual post-create frontmatter edit, which
the provenance work deliberately moved away from).

Apply behavior:

- **Idempotent via report write-back** (§9), *not* via slug/destination
  matching — auto-incremented ids would otherwise mint duplicates. Candidates
  already marked `decision: applied` are skipped; the run reports created vs
  skipped counts.
- v1 routes `question`/`hypothesis` only. `topic`/`theme` kept candidates are
  reported as "apply manually (CLI seam pending)" rather than silently dropped.

## 11. The `idea-lens-researcher` agent

New agent file: `agents/idea-lens-researcher.md` (unprefixed filename, per repo
convention; surfaced as `science:idea-lens-researcher`).

- **Purpose:** given a domain brief + one lens, generate `--n` candidate entities
  in that frame, each grounded by an independent literature search.
- **Tools:** `WebSearch` and `WebFetch` **only** — deliberately *no* `Read` and
  *no* `Bash`. The agent therefore cannot open the repository at all; blindness
  is a property of its capability set, not its prompt (§2). Its whole project
  view is the brief passed inline in the dispatch.
- **Output contract:** a JSON list of candidates matching §9 minus
  `novelty_bucket` / `related_existing` (filled in Phase 3) and minus `decision`
  (defaults `defer`). `literature_anchors` carry **raw** citation metadata (DOI,
  OpenAlex id, title, author, year) — never `paper:`/`cite:` refs, which the
  agent cannot resolve. `origin_plan` is provisional (`assistant` origin plus
  any raw anchors); the orchestrator finalizes literature refs in Phase 3.
- **Blindness clause:** the agent proposes from its lens and the inline brief
  only. (It could not reconcile against existing entities even if instructed to,
  since it has no filesystem tools — the clause documents intent; the tool set
  enforces it.)

## 12. New-code footprint & deferred work

**v1 builds:**
- `commands/explore-ideas.md` (+ regenerated `codex-skills/` mirror).
- `agents/idea-lens-researcher.md`.
- A bounded extension to `parse_origin_spec`: leading `+` → `independent: true`
  (§10), with a unit test.

**v1 reuses (no new code):** `science project index` (dedup input),
`science questions/hypotheses create --origin/--added-by/--source-ref` (apply), the
OpenAlex/PubMed REST endpoints (grounding via `WebFetch`).

**Deferred:**
- `--origin`/`--added-by` on `topics`/`themes` create commands, to let apply
  route those kinds.
- A durable `science explore-ideas classify` CLI (classify stays agent judgment
  in the command for now). The `apply` half **shipped** - see
  `2026-07-04-explore-ideas-apply-cli-design.md`; apply mechanics are now the
  tested `science explore-ideas apply` CLI, not command prose.
- Embedding-based dedup.

## 13. Testing considerations

v1 ships exactly one new Python surface (the `parse_origin_spec` `+` extension),
so it gets the one deterministic test. Everything else — report parsing,
write-back, the create-call mapping — is executed by the command/agent in prose
(like every other slash command in this repo; `wander`/`big-picture`
orchestration is not unit-tested), so those are smoke/manual checks, not pytest.
If apply logic later graduates into a `science explore-ideas apply` helper
(deferred, §12), it comes with deterministic tests then.

- **Deterministic — `parse_origin_spec` `+` extension:** `+literature:cite:K@
  2019-01-01` → `{type: literature, ref: cite:K, date: 2019-01-01, independent:
  True}`; a plain `literature:cite:K` stays `independent: False`; `+` on `user`/
  `assistant` also sets the flag. (Dates must be full `YYYY-MM-DD` — the
  `OriginRecord` validator rejects year-only.) Lives beside the existing
  `parse_origin_spec` tests from the provenance feature.
- **Apply round-trip (now deterministic):** apply mechanics moved into
  `science explore-ideas apply` and are covered by
  `science/tests/test_explore_ideas_apply.py` (routing, write-back, idempotence,
  and an end-to-end create against a seeded project). The former manual smoke-check
  doc (`2026-07-04-explore-ideas-manual-check.md`) is retired; its fixture lives in
  that test.
- `codex-skills/` sync test must pass after adding the command
  (`scripts/generate_codex_skills.py`).
