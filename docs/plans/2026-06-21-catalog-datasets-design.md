---
id: "plan:2026-06-21-catalog-datasets-design"
type: "plan"
title: "Catalog datasets — gap-driven discovery, accessibility verification, and reproducible prioritization"
status: "active"
created: "2026-06-21"
updated: "2026-06-21"
related:
  - "plan:2026-06-21-dataset-catalog-cli-design"
  - "plan:2026-04-19-dataset-entity-lifecycle-design"
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
singular/plural split that `plan:2026-04-19-dataset-entity-lifecycle-design` established: the singular
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

- **Chosen approach:** every row carries `gap-flags` ∈ {`no-edge`, `unverified`, `redundant`}, and the command summarizes them.
- **Rejected alternative:** emit only the ranked score.
- **Reason:** in a sparse graph the *ranking* is weak but the *gaps* are the real signal — "this dataset has no question edge yet" and "this dataset is unverified" are the actionable findings that make a future ranking meaningful. The command's near-term value is surfacing work, not ordering a near-empty set.

## The scorer: `science dataset prioritize`

**Inputs (read-only):** the project's dataset entities and, when present, the materialized graph
(`dataset_usage` → proposition → question/hypothesis edges; question `priority`/`status`;
`risk_score`/`contested`/`single_source`).

**Formula:**

```
score(d) = readiness_weight(d) × (1 + reach(d)) × leverage_tilt(d)
```

- **`readiness_weight(d)`** — derived from the computed `readiness()` state:

  | readiness state | weight |
  |---|---|
  | `available` (verified, obtainable) | 1.0 |
  | unverified, `level: public` | 0.7 |
  | unverified, `level: registration` | 0.5 |
  | unverified, `level: controlled`/`commercial` | 0.3 |
  | `acquiring` (exception: expanded-to-acquire) | 0.4 |
  | `consumable-via-scope-reduced`/`substituted` | 0.25 |
  | `embargoed` / `withdrawn` | 0.05 |
  | derived / `done` | 0.6 |

  (Concrete constants; tunable in one place. The ordering is the load-bearing part.)

- **`reach(d)`** — number of *distinct* questions/hypotheses `d` bears on:
  - if evidence-lines with `dataset_usage` exist: traverse `dataset_usage → cito:supports/disputes →
    proposition → discusses/addresses → hypothesis/question`.
  - else: count frontmatter `related`/`source_refs` edges to `question:`/`hypothesis:` entities.
  - redundancy discount (Key decision 4): edges in a shared `independence_group`/cohort contribute
    `1/k` each rather than 1.

- **`leverage_tilt(d)`** — `1.0` baseline, multiplied by a bounded factor (capped, e.g. ≤2.0) built
  from whichever question-side signals are present: higher when the touched Q/H are `contested`,
  `single_source`, `no_empirical_data`, or high-`priority`; `1.0` when none are populated.

**Output:** one row per dataset —
`rank · id · score · readiness · reach · top-reason · gap-flags` — sorted by score descending.
Flags: `--explain` (full per-row reason breakdown), `--format table|json`, plus the existing
`list`-style filters (`--origin/--status/--level/--tier`) so a project can prioritize a subset.

**Degradation check (must hold):**
- *Sparse graph (this project today):* `leverage_tilt ≈ 1` everywhere, `reach` from frontmatter refs,
  `readiness_weight` dominates → an accessibility-weighted ordering that foregrounds `unverified` and
  `no-edge` gaps.
- *Mature graph (`mm30`):* full `reach` via `dataset_usage`, real `leverage_tilt` from
  `risk_score`/`contested`. Same command, no flags changed.

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

## Open questions

- Exact `leverage_tilt` factor shape and cap — to be pinned in the implementation plan against real
  `mm30` numbers so it neither dominates nor vanishes.
- Whether `reach` should weight hypotheses above questions (a hypothesis edge may be worth more than a
  question edge). Default v1: equal weight; revisit with data.
- Whether the redundancy discount can reuse an existing `science_tool` shared-source derivation helper
  or needs the `origin`/cohort fallback (resolve by code inspection during planning).

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
