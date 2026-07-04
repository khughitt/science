# `/science:explore-ideas --apply` manual smoke check

## Why this is manual, not pytest

`/science:explore-ideas` ships exactly one deterministic Python surface — the
`parse_origin_spec` `+` extension (covered by unit tests beside the existing
`parse_origin_spec` tests). Everything else in Apply mode — parsing the
report's fenced `yaml` blocks, mapping each `keep` candidate to the matching
`science questions create` / `science hypotheses create` call, routing
literature anchors to `--origin "+literature:..."` vs. `--source-ref`, writing
`decision: applied` back into the report — is executed by the command/agent
in prose, the same way `wander` and `big-picture` orchestration is. There is
no orchestration function to call from pytest, and this toolkit repo is not
itself a Science project (no `entities/`, no `science.yaml`), so there is no
in-repo project to apply against even if there were.

This doc is the substitute: a fixture report a human (or an agent standing in
for one) can copy into a real scratch Science project and a step-by-step
procedure with expected results, exercising the create-call mapping,
provenance routing (origin vs. `source_refs`), report write-back, and
idempotence on re-run.

## The fixture report

Copy the block below verbatim to
`entities/meta/explorations/explore-2026-07-04.md` in a scratch project (or
the sibling `meta/` project, in a throwaway branch/worktree you don't intend
to keep). It is a hand-authored stand-in for what Generate mode would have
produced — three candidates, chosen to exercise all three apply branches:

- `cand-mechanism-vagal-cytokine-loop` — `decision: keep`, `proposed_kind:
  question`, reasoned-only, with one **resolved, non-predating** literature
  anchor (`ref: cite:chen2022`, `note` does *not* start with `predates:`).
  This exercises the "supports" routing: the paper becomes a `--source-ref`
  at apply time, not a literature origin.
- `cand-methodology-retest-drift-threshold` — `decision: keep`,
  `proposed_kind: hypothesis`, **convergent**: `origin_plan.origins` carries
  both an `assistant` origin and a `{type: literature, ref: cite:okafor2015,
  independent: true}` origin (the anchor's `note` starts with `predates:`).
- `cand-contrarian-null-effect-explanation` — `decision: drop`. Must **not**
  be created by apply.

````markdown
---
type: meta
id: explore-2026-07-04
title: Exploration report — 2026-07-04
created: 2026-07-04
lenses: [mechanism, methodology, contrarian]
---

# Exploration report — 2026-07-04

## Novel / sharpens existing

```yaml
candidate_id: cand-mechanism-vagal-cytokine-loop
proposed_kind: question
title: Vagal tone as a cytokine feedback regulator
question_or_claim: Does reduced vagal tone sustain systemic inflammation in post-acute infection syndromes?
lens: mechanism
rationale: >
  The cholinergic anti-inflammatory pathway is established in acute sepsis but
  under-explored as a chronic feedback failure in post-acute syndromes.
literature_anchors:
  - doi: 10.1000/chen2022-vagal
    openalex_id: W3001112223
    title: Vagal afferents and cytokine feedback in chronic inflammation
    first_author: Chen
    year: 2022
    note: supports the feedback-loop framing with in-vivo measurements
    ref: cite:chen2022
novelty_bucket: novel
related_existing: []
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-mechanism
  added_by: explore-ideas
```

```yaml
candidate_id: cand-methodology-retest-drift-threshold
proposed_kind: hypothesis
title: Retest interval drives apparent measurement drift
question_or_claim: A fixed retest interval below the true autocorrelation timescale of the assay will manifest as spurious longitudinal drift.
lens: methodology
rationale: >
  Several longitudinal analyses in the field report "drift" using retest
  intervals shorter than the assay's known autocorrelation timescale; this was
  reasoned independently before locating prior work making the same point.
literature_anchors:
  - doi: 10.1000/okafor2015-retest
    openalex_id: W2004445556
    title: Autocorrelation timescales and apparent drift in repeated-measures assays
    first_author: Okafor
    year: 2015
    note: "predates: independently reasoned convergence, found after drafting the hypothesis"
    ref: cite:okafor2015
novelty_bucket: novel
related_existing: []
decision: keep
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-methodology
    - type: literature
      ref: cite:okafor2015
      independent: true
  added_by: explore-ideas
```

## Out of scope / dropped

```yaml
candidate_id: cand-contrarian-null-effect-explanation
proposed_kind: question
title: Is the observed effect fully explained by selection bias in enrollment?
question_or_claim: Would the primary effect disappear entirely under a design that removes the enrollment selection step?
lens: contrarian
rationale: >
  A contrarian null-framing candidate, included to exercise the drop path —
  judged out of scope for this project's enrollment design during review.
literature_anchors: []
novelty_bucket: out-of-scope
related_existing: []
decision: drop
origin_plan:
  origins:
    - type: assistant
      ref: explore-ideas-contrarian
  added_by: explore-ideas
```
````

## Procedure

Run these steps by hand (or via an agent turn standing in for a human) in a
scratch Science project with a real `entities/` tree — **not** in this
toolkit repo, which has none.

1. **Place the fixture.** Copy the fixture body above (frontmatter through
   the final ` ```yaml ` block) to
   `entities/meta/explorations/explore-2026-07-04.md` in the scratch project.

2. **Run apply.**

   ```
   /science:explore-ideas --apply --from explore-2026-07-04
   ```

   or, equivalently, the CLI create calls the command doc
   (`commands/explore-ideas.md`) specifies for each `keep` block:

   ```bash
   uv run science questions create "Vagal tone as a cytokine feedback regulator" \
     --origin "assistant:explore-ideas-mechanism" \
     --source-ref "cite:chen2022" \
     --added-by "explore-ideas:<model-id>:cand-mechanism-vagal-cytokine-loop"

   uv run science hypotheses create "Retest interval drives apparent measurement drift" \
     --origin "assistant:explore-ideas-methodology" \
     --origin "+literature:cite:okafor2015" \
     --added-by "explore-ideas:<model-id>:cand-methodology-retest-drift-threshold"
   ```

   **Expected:**
   - Exactly **2** entities created — one question, one hypothesis. Nothing
     is created for `cand-contrarian-null-effect-explanation`.
   - The created question's frontmatter carries `cite:chen2022` under
     `source_refs`, and its `origins` list contains only the `assistant`
     origin — the resolved-but-supporting anchor never became a literature
     origin.
   - The created hypothesis's frontmatter carries **two** entries under
     `origins`: the `assistant` one and a `literature` one with
     `ref: cite:okafor2015` and `independent: true`.
   - Both created blocks in the report flip from `decision: keep` to
     `decision: applied`, gaining `applied_as: <entity-id>` and
     `applied_at: 2026-07-04`. The `drop` block is untouched.
   - The command reports "2 created, 0 skipped" (or equivalent counts) to
     the user, plus nothing to apply manually (no `topic`/`theme` candidates
     in this fixture).

3. **Re-run the same apply (idempotence check).**

   ```
   /science:explore-ideas --apply --from explore-2026-07-04
   ```

   **Expected:** **0** entities created, **2** skipped (both blocks already
   `decision: applied`), and the drop block still skipped. No duplicate
   entities appear in `entities/questions/` or `entities/hypotheses/`.

4. **Validate the scratch project.**

   ```bash
   uv run science validate
   ```

   **Expected:** no new ERRORs attributable to the two created entities. A
   WARN on the raw, unresolved `cite:chen2022` / `cite:okafor2015` keys (if
   `papers/references.bib` in the scratch project doesn't actually define
   them) is expected and acceptable — the fixture's anchors are illustrative
   stand-ins, not real bibliography entries. If the scratch project does
   define those keys, no WARN should appear.

## Yaml sanity check (structural, not behavioral)

This only confirms the fixture in this doc parses and has the right shape —
it does not exercise the command itself. Run from the repo root:

```bash
cd "$(git rev-parse --show-toplevel)" && python -c "import yaml,re; t=open('docs/plans/2026-07-04-explore-ideas-manual-check.md').read(); blocks=re.findall(r'\`\`\`yaml\n(.*?)\`\`\`', t, re.S); cands=[yaml.safe_load(b) for b in blocks if 'candidate_id' in b]; assert len(cands)==3, len(cands); assert sum(c['decision']=='keep' for c in cands)==2; assert any(any(o.get('independent') for o in c['origin_plan']['origins']) for c in cands); assert any(any(a.get('ref') for a in c.get('literature_anchors', []) if not str(a.get('note', '')).startswith('predates:')) for c in cands); print('ok', len(cands))"
```

Expected output: `ok 3`.
