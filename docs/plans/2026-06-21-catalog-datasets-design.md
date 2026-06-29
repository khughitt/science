---
id: "plan:2026-06-21-catalog-datasets-design"
type: "plan"
title: "Catalog datasets — gap-driven discovery, accessibility verification, and reproducible prioritization"
status: "active"
created: "2026-06-21"
updated: "2026-06-21"
related:
  - "plan:2026-06-21-dataset-catalog-cli-design"
  - "docs/user-guide/entities.md#dataset-lifecycle"
---

# Catalog datasets — gap-driven discovery, accessibility verification, and reproducible prioritization

## Purpose

Give the science framework a **reusable, systematic way to build a project's dataset catalog**: find
candidate datasets that connect to the project's open questions and hypotheses, verify whether they
are actually obtainable, wire them into the knowledge graph, and rank them by a reproducible estimate
of near-term usefulness — so the project knows *which dataset to operationalize next*.

This is the "front half" of the dataset arc. The "back half" — per-dataset download/QA/preprocessing
workflows — is already served by `/science:plan-pipeline` → `superpowers:executing-plans` applied per
dataset, and is explicitly out of scope here. The seam between the two halves mirrors the deliberate
singular/plural split documented in `docs/user-guide/entities.md#dataset-lifecycle`: the singular
`science dataset` group is the **catalog/lifecycle** surface; acquisition runs live elsewhere.

**Guiding principle.** Design only around signals that are *actually populated*, not signals the model
*could* track. An audit of three science-framework projects (this one, `natural-systems`, and the
mature `mm30`) showed that the rich epistemic vocabulary (`belief_state`, `risk_score`, per-line
`strength`, `independence_group`) is sparsely populated even in mature projects, while two facts hold
everywhere: (a) accessibility is under-recorded (`access.verified: true` on 0/14, 3/19, and 6/254
datasets respectively), and (b) the one dataset↔epistemic edge that scales is
`evidence-line.dataset_usage → proposition → question/hypothesis`. The scorer is built from what
exists and **degrades gracefully** as a project's graph matures.

## Background: the audit that shaped this design

| Signal | this project (today) | natural-systems | mm30 (mature) |
|---|---|---|---|
| Questions / Hypotheses | 18 / 7 | 127 / 11 | 163 / 15 |
| Propositions | few | 3 (bare stubs) | 326 |
| Evidence-lines with `stance` + `dataset_usage` | ~0 | 0 | 328 |
| Datasets | 14 | 19 | 254 |
| `access.verified: true` | 0/14 | 3/19 | 6/254 |
| Per-line `strength`/`confidence` | — | — | not a field |
| `independence_group` populated | — | — | ~15/326 (hand-curated core) |

Three invariants follow, and they constrain the whole design:

1. **The scaling edge is `dataset_usage`.** Dataset → question/hypothesis reach is dense and
   computable in `mm30` (328 evidence-lines, all carrying `dataset_usage`), but requires evidence-lines
   to exist. In young projects the only edge is frontmatter `related`/`source_refs`. The scorer must
   read both and prefer the richer one when present.
2. **Accessibility is under-recorded everywhere**, yet `DatasetEntity.readiness()` already computes a
   readiness state from the access block. "Verify accessibility" is therefore an *action this command
   drives*, not a field it can assume is filled.
3. **Fine-grained strength × independence × uncertainty are fantasy inputs** — they do not exist at
   scale even when a project is mature. Any formula that depends on them divides by zero in practice.

## Scope decomposition

**In scope (v1):**

- A new deterministic CLI subcommand `science dataset prioritize` (the reusable ranking primitive).
- A new command/skill `/science:catalog-datasets` orchestrating the front-half loop:
  gap-scan → discover → verify-accessibility → connect → prioritize → handoff.
- Reuse of existing surfaces: `/science:find-datasets`, the access schema and the `plan-pipeline`
  Dimension-3 data-access gate, `readiness()`, `independence_group` semantics, and the built
  `dataset add/list/show/consumers`.
- First-consumer validation on `health-post-acute-infection`.

**Out of scope (deferred):**

- Per-dataset download/QA/preprocessing workflows — handled by `/science:plan-pipeline` → execute,
  invoked per dataset *after* prioritization. The handoff is the boundary.
- Commons promotion — deferred and gated on `access.verified: true` at minimum; promoting speculative
  candidates would pollute the commons.
- Graph-centrality metrics (degree/betweenness) — rejected for v1: the edge set is too sparse and
  partly circular (high-degree datasets are high-degree because already mined), so centrality is
  near-zero signal today. Revisit once `dataset_usage` density justifies it.
- Any change to the plural `datasets` discovery group, `register-run`, or `reconcile` — untouched.

## Architecture

```
~/d/science/
├── science/src/science_tool/
│   ├── dataset_prioritize.py        NEW     pure scoring core: score/reach/readiness_weight/leverage_tilt + row assembly
│   └── cli.py                       MODIFY  add `dataset prioritize` Click command (delegates to dataset_prioritize)
├── science/tests/
│   └── test_dataset_prioritize_cli.py   NEW  scorer + degradation + reasons/gap-flags
├── commands/
│   └── catalog-datasets.md          NEW     front-half orchestration command/skill
└── docs/plans/
    └── 2026-06-21-catalog-datasets-design.md   (this file)
```

`readiness()` and `independence_group` semantics are consumed from `science_model`
(`entities.py`) and the existing usage/independence derivation — **read, do not reimplement**. If a
ready-made shared-source derivation helper exists in `science_tool`, reuse it; otherwise the redundancy
discount falls back to an `origin`/cohort heuristic (see Key decision 4).

## Key decisions

### Key decision 1: a deterministic CLI primitive, not an agent-judged ranking

- **Chosen approach:** the ranking lives in `science dataset prioritize` — pure, reproducible, re-runnable, emitting per-row reasons.
- **Rejected alternative:** let the `/science:catalog-datasets` skill rank datasets by LLM judgment.
- **Reason:** the ranking must be inspectable and stable as the graph grows; a model re-ranking on each run is neither reproducible nor auditable.

### Key decision 2: multiplicative score with accessibility as the dominant term

- **Chosen approach:** `score = readiness_weight × (1 + reach) × leverage_tilt`.
- **Rejected alternative:** additive weighting of accessibility + reach + leverage.
- **Reason:** the chosen objective is near-term, accessibility-weighted ("what can I run next"). A multiplicative `readiness_weight` lets an inaccessible dataset be driven toward zero regardless of how many questions it touches — additive scoring would let a high-reach private cohort outrank an obtainable public one, which is exactly the "private → deferred" trap this project keeps hitting.

### Key decision 3: graceful degradation over richness

- **Chosen approach:** `leverage_tilt = 1.0` unless question-side signals are present; `reach` falls back from `dataset_usage` to frontmatter refs.
- **Rejected alternative:** require evidence-lines / `risk_score` and error or score 0 when absent.
- **Reason:** the same command must be useful on a 14-dataset sparse graph and a 254-dataset mature one. Inert terms collapse to neutral multipliers rather than failing.

### Key decision 4: redundancy discount via independence, not raw reach

- **Chosen approach:** edges sharing an `independence_group` (or, absent that, the same `origin`/cohort) count fractionally toward `reach`.
- **Rejected alternative:** `reach` = raw count of distinct Q/H edges.
- **Reason:** two meta-analyses that share primary studies are one evidence line, not two (observed directly in this project's `interpretation:0002`, where Hertanti2025 ⊕ Conde2026 are a shared-source pair). Raw reach over-ranks redundant datasets.

### Key decision 5: gap-flags are first-class output, not a side effect

- **Chosen approach:** every row carries `gap-flags` ∈ {`no-edge`, `unverified`, `redundant`, `readiness-unresolved`} (the canonical set; `readiness-unresolved` is emitted by the `readiness_weight` flagged default), and the command summarizes them.
- **Rejected alternative:** emit only the ranked score.
- **Reason:** in a sparse graph the *ranking* is weak but the *gaps* are the real signal — "this dataset has no question edge yet" and "this dataset is unverified" are the actionable findings that make a future ranking meaningful. The command's near-term value is surfacing work, not ordering a near-empty set.

### Key decision 6: degrade-with-warning on a stale graph, never auto-materialize

- **Chosen approach:** at startup, check `graph_is_stale(project_root, graph_path)` (`science_tool/entities.py:925`, an mtime comparison). If the graph is missing or stale, emit a warning to stderr (`graph may be stale; reach/leverage computed from the last build — run \`science graph build\``) and **continue**, computing what it can. The frontmatter `related` reach is computed by scanning **raw entity frontmatter directly** (not graph triples), so it works even with no graph at all; the graph `skos:related` path is used only when a graph is loaded (the two must agree when both are available — see the `reach` term). Usage-reach and `leverage_tilt` degrade to their neutral values when the graph is absent.
- **Rejected alternatives:** (a) hard-require a fresh graph and error out; (b) silently auto-run `materialize_graph()` inside a read-only command.
- **Reason:** this matches the one existing precedent in the codebase — `entity neighbors` (`cli.py:796`) warns on `graph_is_stale` but does not rebuild — and keeps a read-only ranking command free of write side effects. Auto-materializing would surprise the user with a graph rewrite; hard-failing would make the command useless precisely on the young graphs where it is most needed.

## The scorer: `science dataset prioritize`

**Inputs (read-only):** the project's dataset entities and, when present, the materialized graph
(`dataset_usage` → proposition → question/hypothesis edges; question `priority`/`status`;
`risk_score`/`contested`/`single_source`).

**Formula:**

```
score(d) = readiness_weight(d) × (1 + reach(d)) × leverage_tilt(d)
```

- **`readiness_weight(d)`** — keyed on the **structured fields** behind `DatasetEntity.readiness()`,
  not on label-matching its prose. `readiness()` returns a `Readiness(ready: bool, state: str,
  detail: str)` (`science_model/entities.py:395,735`), and `state` is a small closed set of exact
  strings — match those verbatim, never a conceptual paraphrase. The weight is a function of
  `readiness.ready` plus the structured discriminators (`origin`, `access.level`,
  `access.exception.mode`, `access.availability`):

  | `readiness.state` (exact) | condition | weight |
  |---|---|---|
  | `available` | external, verified, obtainable | 1.0 |
  | `derived-via-code` / `derived-via-member-of` / `derived-via-workflow-recipe` | derived, resolvable | 0.6 |
  | `consumable-via-scope-reduced` / `consumable-via-substituted` | usable via exception | 0.55 |
  | `"<level>, unverified"` where level = `public` | external, unverified | 0.7 |
  | `"<level>, unverified"` where level = `registration` / `mixed` | external, unverified | 0.5 |
  | `"<level>, unverified"` where level = `controlled` / `commercial` | external, unverified | 0.3 |
  | `acquiring` | exception: expanded-to-acquire | 0.4 |
  | `embargoed` / `withdrawn` | not obtainable now | 0.05 |
  | `unknown` / `missing-access-block` / `missing-provenance` / `exception:<mode>` | unresolved | 0.1 **and emit a `readiness-unresolved` gap-flag** |

  The last row is the anti-footgun: an unrecognized state must **flag**, never silently fall into a
  default bucket. (Constants tunable in one place; the ordering and the explicit flagged-default are
  the load-bearing parts. `"<level>, unverified"` is parsed by splitting on `", unverified"` and
  reading `access.level` from the structured field, not by string-matching the whole label.)

- **`reach(d)`** — number of *distinct* questions/hypotheses `d` bears on, computed **per-dataset as a
  merged union** of two sources (never a global either/or — a graph that has *some* `dataset_usage`
  must not make a dataset that is only frontmatter-connected look like `no-edge`):

  1. **Usage path** (preferred per edge, when present): find consumers of `d` via the reified usage
     node — `?consumer sci:hasDatasetUsage ?u . ?u sci:dataset <d>` (provenance graph,
     `graph/dataset_usage.py:201`). For each consumer evidence-line, expand to epistemic targets:
     `evidence-line —cito:supports|cito:disputes→ proposition` (frontmatter `target:`,
     `materialize.py:873`), then `proposition —cito:discusses→ hypothesis` (`io.py:73`) and
     `question —sci:addresses→ proposition` traversed **backwards** (the edge is question→proposition;
     `store/summary.py:362`, `cross_impact.py:200`). Reuse the existing `sci:bearsOn` derivers/closure
     (`graph/freshness.py:70,182,231`) for the proposition→Q/H expansion rather than re-implementing
     it.
  2. **Frontmatter path** (always also counted, both directions): the bidirectional `related` linkage
     between `d` and any `question:`/`hypothesis:` entity — **including the back-edge** where a
     question/hypothesis lists `dataset:d` in *its own* `related`. This path has **two read modes** that
     must produce the same edge set: when a graph is loaded, read the `skos:related` triples in both
     directions (`(d, skos:related, Q/H)` and `(Q/H, skos:related, d)`, materialized at
     `materialize.py:646`); when no graph is available (Key decision 6), scan **raw entity frontmatter
     directly** — `d.related` for outgoing refs and every question/hypothesis entity's `related` list
     for the incoming back-edge. Either mode must catch the back-edge that a dataset-only outgoing scan
     would miss. Do **not** count `source_refs`: those materialize as `prov:wasDerivedFrom` provenance,
     not semantic relatedness (`materialize.py:720`), and already participate via the usage/`bearsOn`
     path where they form a real chain.

  The two sources are unioned and de-duplicated by target Q/H id. Redundancy discount
  (Key decision 4): targets reached only through a shared `independence_group`/cohort contribute `1/k`
  each rather than 1.

- **`leverage_tilt(d)`** — `1.0` baseline, multiplied by a bounded factor (capped ≤ 2.0) over the
  propositions `d` reaches. It **reuses the existing computed claim signals** rather than introducing a
  second interpretation of them: `risk_score`, `contested`, `single_source`, and `no_empirical_data`
  are computed by `_claim_summary_data(knowledge, provenance, uri)` (`graph/store/summary.py:67`),
  which returns the signal record **for a single proposition URI**. `leverage_tilt` calls that
  **per reached-proposition URI** and aggregates (plus question `priority` where a reached proposition
  is addressed by a question). It must **not** read `query_dashboard_summary(graph_path, top)`
  (`summary.py:226`): that surface returns formatted, **top-N-truncated** rows and would silently drop
  a reached proposition that falls outside `top`. If a per-URI helper is not already public, expose
  `_claim_summary_data` (or the untruncated `_claim_summaries()` at `summary.py:217`) rather than
  scoring off the dashboard surface. When no propositions are reached (sparse graph), the factor is
  exactly `1.0`.

**Output:** one row per dataset —
`rank · id · score · readiness · reach · top-reason · gap-flags` — sorted by score descending.
Flags: `--explain` (full per-row reason breakdown), `--format table|json`, plus the existing
`list`-style filters (`--origin/--status/--level/--tier`) so a project can prioritize a subset.
**Gated datasets** (`access.level` in `{registration, controlled, commercial}`) are excluded by
default on both `list` and `prioritize`, so suggestions stay actionable; surface them with
`--include-gated`, or by naming the level explicitly via `--level`. Derived rows (no access block)
and `public`/`mixed` are never gated.

**Degradation check (must hold):**
- *Sparse graph (this project today):* `leverage_tilt = 1` everywhere (no propositions reached),
  `reach` from the frontmatter `skos:related` path only, `readiness_weight` dominates → an
  accessibility-weighted ordering that foregrounds `unverified` and `no-edge` gaps.
- *Mixed graph:* a project with *some* `dataset_usage` must still credit `reach` to datasets connected
  only by frontmatter — the union (not either/or) is what guarantees this.
- *Mature graph (`mm30`):* merged usage + frontmatter `reach`, real `leverage_tilt` from the reused
  `_claim_summary_data` signals. Same command, no flags changed.

## The loop: `/science:catalog-datasets`

A command/skill that orchestrates the front half. Each step reuses an existing surface where one
exists.

1. **Gap scan.** Identify questions/hypotheses with **no accessible dataset** (no edge, or only edges
   to unverified/inaccessible datasets). This is the driver — in a sparse graph it is the most
   informative output.
2. **Discover.** For gap Q/H, invoke `/science:find-datasets` to author new **public** candidate
   datasets (`status: candidate`) via `science dataset add`. Bias toward obtainable omics
   (GEO/SRA/Zenodo) for under-covered triggers.
3. **Verify accessibility.** For each candidate, confirm obtainability and record it: flip
   `access.verified`/`verification_method`/`last_reviewed`, or populate `access.exception` per the
   Branch-A/B logic already specified in the `plan-pipeline` Dimension-3 data-access gate. Append a
   dated verification-log line. **No new findings store** — this is exactly the existing schema.
4. **Connect.** Author dataset→Q/H edges; where evidence-lines exist, author `dataset_usage` blocks so
   the dataset participates in the materialized graph (and thus in `reach`).
5. **Prioritize.** Run `science dataset prioritize`; present the ranked table and the gap summary.
6. **Handoff.** Route the top obtainable datasets to `/science:plan-pipeline` → execute for the
   per-dataset download/QA work. This is the front/back boundary; the loop ends here.

## First consumer: health-post-acute-infection

The command is validated on a real sparse graph:

- Gap-scan exposes that only **3 of 14** catalogued datasets are `level: public` (the dengue
  sex-OR meta and Sylvester2022, both literature-only and already mined; GSE130353, already being
  operationalized via `plan:0002`/t035). The near-term public frontier is nearly exhausted.
- Therefore the high-value move is **discovery**: new public omics for under-covered triggers
  (post-dengue, Q-fever fatigue syndrome, PTLDS, ME/CFS) → verify → connect → prioritize → hand the
  top candidates to `plan-pipeline`.
- This exercises every step against a graph at the sparse end of the maturity spectrum, confirming the
  degradation behavior before the command is relied on elsewhere.

## Resolved by review (2026-06-21)

- **`leverage_tilt` reuses computed signals, not a second interpretation.** `risk_score`/`contested`/
  `single_source`/`no_empirical_data` are computed claim/neighborhood signals
  (`graph/store/summary.py:_claim_summary_data`, the untruncated per-URI helper — **not** the top-N
  `query_dashboard_summary` surface), not authored question fields. `leverage_tilt` calls it per
  reached-proposition URI and aggregates — see the term definition above.
- **Stale-graph policy = degrade-with-warning** (Key decision 6).
- **`reach` is a per-dataset merged union**, frontmatter path checks both directions, `source_refs` is
  provenance not relatedness — see the `reach` term above.
- **`readiness_weight` keys on exact `readiness.state` strings + structured fields**, with a flagged
  default for unresolved states — see the table above.

## Open questions

- Exact `leverage_tilt` factor shape and cap — to be pinned in the implementation plan against real
  `mm30` numbers so it neither dominates nor vanishes.
- Whether `reach` should weight hypotheses above questions (a hypothesis edge may be worth more than a
  question edge). Default v1: equal weight; revisit with data.
- Whether the redundancy discount can reuse an existing `science_tool` shared-source derivation helper
  or needs the `origin`/cohort fallback (resolve by code inspection during planning).
- **Multi-hop usage reach via the `sci:bearsOn` closure — SCOPED FOR IMPLEMENTATION (2026-06-22).**
  The v1 implementation walks the usage path's proposition→Q/H expansion with the two DIRECT edges only
  (`cito:discusses`, `sci:addresses`), not the transitive `sci:bearsOn` closure this design recommended
  (`graph/freshness.py:70,182,231`). Consequence: a proposition reachable only through a multi-hop
  chain (e.g. `P ⊳supports P2 ⊳supports H`, giving `P bearsOn H` at depth 2) is undercounted in
  `reach`. **Resolution (2026-06-22):** `_qh_for_proposition` (in `dataset_prioritize.py`) gains a
  third source — the materialized transitive `sci:bearsOn` closure targets typed Question/Hypothesis —
  **unioned** with the existing two direct edges (NOT a replacement: `cito:discusses`/`sci:addresses`
  are not in the `bearsOn` deriver rule set, so the closure alone would drop them). Purely additive:
  cannot regress any existing acceptance criterion. `usage_reach` inherits the upgrade; the leverage
  path (`reached_proposition_uris`) is untouched. Validated by a synthetic multi-hop test — there is no
  live consumer (PAIS has 0 `dataset_usage` edges; lights up end-to-end only on an `mm30`-scale graph).
  Flagged by the final whole-branch review (2026-06-21); accepted as a scoped reduction, then promoted
  to implementation by the project owner (2026-06-22).

- **Candidate-aware leverage — DEFERRED with an explicit un-defer trigger (2026-06-22).** Idea: let a
  *candidate* dataset's `leverage_tilt` borrow from the claim-signals (`contested`/`single_source`/
  `no_empirical_data`/`risk_score`) of the propositions in the bearsOn neighborhood of its
  frontmatter-linked Q/H, so leverage is meaningful *before* the dataset is analyzed — as a
  **subordinate tilt** (bounded so it never lets a lower-readiness dataset overtake a higher-readiness
  one; preserves Key decision 2). **Why deferred:** an audit of PAIS (2026-06-22) found the required
  signal is unpopulated — only 7 proposition nodes exist and **zero** bear on any question/hypothesis,
  so the traversal returns the neutral `1.0` for every dataset; the only populated proxy (bearsOn
  in-degree to a question) is the circular centrality signal this design already rejects as a Non-goal.
  Building it now would violate the Guiding Principle ("design only around signals that are actually
  populated"). **Un-defer trigger:** a consumer graph has propositions wired to its candidate-targeted
  questions — i.e. proposition→Q/H `bearsOn` edges are non-zero on datasets' frontmatter-linked Q/H.
  Revisit then, tuning the subordinate cap against that consumer's real numbers.

## Non-goals

- Re-ranking by graph centrality (deferred).
- Operationalization, QA, or download of any dataset (handled downstream by `plan-pipeline`).
- Commons promotion (later; gated on `access.verified`).
- Any change to `datasets` (plural) discovery, `register-run`, or `reconcile`.

## Acceptance criteria

- [ ] `science dataset prioritize` runs on a project with **zero** evidence-lines and produces a
      sensible accessibility-weighted ordering with correct `no-edge`/`unverified` gap-flags.
- [ ] The same command on a graph **with** `dataset_usage` edges incorporates `reach` and a non-trivial
      `leverage_tilt`, with no flag or config change.
- [ ] **Mixed-graph (regression for the High finding):** in a graph where *some* datasets have
      `dataset_usage` and another is connected to a question only by frontmatter `skos:related`, the
      frontmatter-only dataset shows `reach ≥ 1` and is **not** flagged `no-edge`.
- [ ] **Back-edge reach:** a dataset is credited with `reach` when a *question* lists `dataset:d` in its
      own `related` (incoming edge), not only when the dataset lists the question.
- [ ] **`source_refs` is not relatedness:** a dataset cited only via an interpretation's `source_refs`
      is not double-counted as a direct `skos:related` reach edge.
- [ ] **Flagged default:** a dataset whose `readiness.state` is unrecognized/`unknown` gets the
      `readiness-unresolved` gap-flag rather than silently landing in a default weight bucket.
- [ ] **Stale/missing graph:** the command warns (does not error, does not auto-materialize) and still
      produces a frontmatter-based ranking.
- [ ] The redundancy discount collapses a known shared-source pair (e.g. the dengue meta) to a single
      effective reach contribution.
- [ ] `--explain` shows, per row, why it ranked where it did (readiness state, reach edges,
      leverage signals).
- [ ] `/science:catalog-datasets` drives gap-scan → discover (via `find-datasets`) → verify (via the
      access schema) → connect → prioritize → handoff, with each step reusing the named existing
      surface rather than a new store.
- [ ] Validated end-to-end on `health-post-acute-infection`: at least one new public candidate
      discovered, verified, connected, and surfaced at the top of the ranking.
- [ ] No change to `datasets` (plural), `register-run`, `reconcile`, or the existing
      `add/list/show/consumers` behavior (regression check).
