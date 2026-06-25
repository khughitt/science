---
id: "plan:2026-06-24-dataset-reach-authoring-surfaces-design"
type: "plan"
title: "Dataset reach should follow all natural dataset↔inquiry authoring surfaces (paper-mediated usage reach + the datasets: field)"
status: "proposed"
created: "2026-06-24"
updated: "2026-06-24"
related:
  - "plan:2026-06-21-catalog-datasets-design"
  - "plan:2026-06-22-bears-on-multihop-reach"
  - "plan:2026-06-24-dataset-reach-authoring-surfaces-implementation-plan"
---

# Dataset reach should follow all natural dataset↔inquiry authoring surfaces

## Purpose

`science dataset prioritize` ranks a project's datasets by `score = readiness × (1 + reach) × leverage`.
`reach` is the count of questions/hypotheses a dataset connects to. This note proposes **two additive
extensions to the `reach` computation** so it credits dataset↔inquiry links that authors *already
record* but the scorer currently ignores:

1. **Paper-mediated usage reach** — `dataset_usage` recorded on a **paper** (the dominant place it
   actually lives) should propagate to the questions/hypotheses that paper is `related:` to.
2. **The `datasets:` field on questions** — currently authored but dead; `reach` reads only `related:`.

Both are instances of one principle: **reach should follow every natural authoring surface for a
dataset↔inquiry link, not only `dataset.related`.** Both are purely additive — they can raise reach,
never lower it — and neither requires new author behavior; they make existing data load-bearing.

Motivating evidence: on `health-meta` (174 questions/hypotheses, 113 datasets), the catalog began at
**1/174 covered** despite 32 papers carrying rich `dataset_usage` provenance. Closing the gap required
hand-authoring **266 `related:` edges** that the tool already had the data to derive. Extension #1
would have derived that coverage automatically; extension #2 gives authors a direct surface for the
rest.

## Background: where reach comes from today

`reach` is the union of two paths (`science/src/science_tool/dataset_prioritize.py`, `merged_reach`):

- **Frontmatter path** — `frontmatter_reach` (`dataset_prioritize.py:116`). Reads **only** the
  `related:` field, in two directions: a dataset's `related: question:…/hypothesis:…`, and the
  back-edge where a Q/H lists `dataset:…` in *its* `related:`. No graph needed.
- **Usage path** — `usage_reach` (`dataset_prioritize.py:215`). Walks the materialized graph:

  ```
  dataset ──sci:dataset──▶ usage_node ──hasDatasetUsage──▶ consumer
      consumer ──cito:supports / cito:disputes──▶ proposition
          proposition ──{cito:discusses, sci:addresses⁻¹, sci:bearsOn closure}──▶ Q/H
  ```

  (last hop is `_qh_for_proposition`, recently widened to the `sci:bearsOn` closure per
  `plan:2026-06-22-bears-on-multihop-reach`.)

The usage path's first inference — `consumer ──cito:supports──▶ proposition` — is the load-bearing
assumption this note targets. It holds **only when the entity carrying `dataset_usage` is an
evidence-line** (evidence-lines support/dispute propositions). The `2026-06-21-catalog-datasets-design`
audit already names this: *"the one dataset↔epistemic edge that scales is
`evidence-line.dataset_usage → proposition → question/hypothesis`."*

## Gap #1: `dataset_usage` on papers reaches nothing

In practice, young and mid-maturity projects attach `dataset_usage` to **papers**, not evidence-lines —
because the paper is where the dataset's use is first recorded during ingestion, long before anyone
authors an evidence-line + proposition. Concretely on `health-meta`, `entities/papers/Wen2025ProtBAG.md`:

```yaml
id: paper:Wen2025ProtBAG
related:
  - hypothesis:0005-health-is-individualized-dynamic-homeostasis   # ── paper → Q/H
dataset_usage:
  - ref: dataset:ukb-ppp        # ── paper → dataset
  - ref: dataset:finngen
  - ref: dataset:pgc
```

The graph **does** materialize `paper hasDatasetUsage usage_node` and `usage_node sci:dataset
dataset:ukb-ppp` (`graph/dataset_usage.py:add_usage_record_to_graph`), and **does** materialize
`paper:Wen2025ProtBAG skos:related hypothesis:0005` (`graph/materialize.py:671`, `related:` → `skos:related`
for non-task entities). So both legs of a `dataset → paper → Q/H` path exist in the graph. But:

- `usage_reach` finds the paper as a `consumer`, then asks for `consumer cito:supports proposition` —
  a paper has none, so the walk dead-ends. **Zero reach.**
- `frontmatter_reach` only reads `related:` on datasets and Q/H entities; it never inspects a paper's
  `related:` or `dataset_usage`. **Zero reach.**

Result: 32 papers' worth of provenance contributed nothing to prioritization, and the catalog read as
1/174 covered. This is the gap that forced the 266 hand-authored edges.

### Proposal #1

Add a **paper-mediated (more precisely: non-proposition-consumer) usage path** — a second consumer→Q/H
edge alongside the existing proposition expansion:

```
dataset ──sci:dataset──▶ usage_node ──hasDatasetUsage──▶ consumer
    consumer ──skos:related (typed Question/Hypothesis)──▶ Q/H
```

This is **unconditional and additive**, never a replacement: for **every** consumer of a dataset's
usage node, collect *both* the proposition-derived Q/H (`cito:supports/disputes → proposition →
_qh_for_proposition`) **and** the consumer's direct typed `skos:related` Q/H, then union. An
evidence-line that both supports a proposition and is `related:` to a question contributes both; a paper
that only has `related:` edges contributes those — neither is gated on the other being absent. Two
implementation options:

- **Option A — graph path (recommended).** Extend `usage_reach` in `dataset_prioritize.py`: for each
  `consumer` of a dataset's usage node, unconditionally run *both* the existing `cito:supports/disputes
  → proposition` expansion *and* a new `consumer skos:related ?qh` collection, where `?qh` is typed
  `sci:Question`/`sci:Hypothesis` (the same typing guard `_qh_for_proposition` already uses). The two
  result sets union (dedup by Q/H id). Symmetric, additive, reuses the existing graph traversal style.
  Generalizes beyond papers to any entity that carries `dataset_usage` and is `related:` to inquiry
  (interpretations, notes).
- **Option B — frontmatter path.** Extend `frontmatter_reach` to bridge `dataset → paper (via the
  paper's `dataset_usage`) → Q/H (via the paper's `related:`)` with no graph. Cheaper to make *always*
  run (the frontmatter path runs even when the graph is stale/absent — see Caveat below), but
  re-implements provenance traversal in frontmatter space and is paper-specific.

**Recommendation: Option A**, for symmetry with the existing usage path and generality. **Caveat that
may force B (or both)** — the prioritize CLI's graph handling has two distinct degraded modes
(`cli.py:5468-5478`), and a graph-only fix has different failure modes in each:

- **Missing graph** (`knowledge/graph.trig` absent): `usage_reach` never runs at all — prioritize emits
  *"no materialized graph; reach from frontmatter only"* and reach comes purely from `frontmatter_reach`.
  A graph-only fix for Gap #1 contributes **nothing** here.
- **Stale graph** (`graph.trig` exists but older than its sources): prioritize **loads the last build**
  and warns *"graph may be stale; reach/leverage from last build — run `science graph build`"*. So
  `usage_reach` does run, but against the previous build: a graph-only code change can expose
  paper-mediated edges that were already in that build, while any `dataset_usage`/`related:` edges
  authored since the last `graph build` are **invisible until rebuild**. This is exactly the footgun
  that bit this session: edit edges, re-run prioritize, see no change.

If paper-mediated reach is meant to work out-of-the-box, either also cover Gap #1 in the always-on
frontmatter path (Option B), or (cleaner) have prioritize build/refresh the graph when the usage path
is requested. Resolve during planning.

**Resolved in the implementation plan:** do both Option A and the frontmatter bridge. The graph path
keeps materialized usage reach symmetric with existing proposition reach; the frontmatter bridge makes
source-authored paper/consumer `dataset_usage` + `related:` links visible when the graph is missing or
stale.

## Gap #2: the `datasets:` field on questions is dead

Question entities ship a purpose-built `datasets:` frontmatter field. On `health-meta` it is present on
**168/174** questions — and **every one is `datasets: []`**, because nothing rewards filling it:
`frontmatter_reach` reads `related:`, never `datasets:`. The author's most intuitive move — "list the
datasets this question needs in the question's `datasets:` field" — is inert. During this session the
only way to register a dataset→question link from the question side was to put `dataset:…` in the
question's `related:` block, which is non-obvious and overloads `related:`.

### Proposal #2

Pick one (recommend 2a):

- **2a — make `datasets:` load-bearing (recommended).** In `frontmatter_reach`, when scanning a Q/H,
  also read its `datasets:` field and add a `dataset → Q/H` edge for each entry, exactly as the
  `related:` back-edge does today (`dataset_prioritize.py:126-129`). Additive; gives authors the
  obvious surface; symmetric with `dataset.related` from the other side. Update the question template
  and the `catalog-datasets` Step 4 docs to point authors at `datasets:`.
- **2b — deprecate the field.** If `related:` is meant to be the sole surface, remove `datasets:` from
  the question template and lint authored-but-ignored occurrences, so the field stops misleading.

Either is acceptable; the status quo (a prominent field that does nothing) is the worst option. 2a is
preferred because "which datasets does this question need" is a real, frequently-known authoring fact
that deserves a first-class home, and because it makes the catalog populatable without touching the
graph at all.

## Why both, and why additive

Unified principle: **`reach` should follow all the natural authoring surfaces for a dataset↔inquiry
link** — `dataset.related` (have it), Q/H `related:` back-edge (have it), the evidence-line/proposition
usage path (have it), **paper/consumer `dataset_usage` + `related:` (Gap #1)**, and **Q/H `datasets:`
(Gap #2)**. Each is a place a human already records the same underlying fact; the scorer should not
privilege one and silently drop the others.

Both extensions are strictly additive to a union — they match the safety property established for the
`sci:bearsOn` closure work (`plan:2026-06-22-bears-on-multihop-reach`): they can only *add* Q/H to a
dataset's reach, so no existing prioritize acceptance criterion can regress.

## Interaction with existing work

- Complementary to `plan:2026-06-22-bears-on-multihop-reach`: that note widened the **last** hop
  (proposition → Q/H, via the `bearsOn` closure). This note adds **earlier** hops (a new consumer→Q/H
  inference, and a new frontmatter surface). They compose — a paper-mediated consumer still benefits
  from the widened proposition expansion if it *also* reaches a proposition.
- Does **not** touch `leverage_tilt` / `reached_proposition_uris` (still proposition-only, correctly —
  leverage borrows claim-signals that only propositions carry). Paper-mediated reach raises `reach`
  but leaves `leverage` neutral (`1.0`) for a dataset with no proposition path, which is the right
  default.

## Open questions

- **Stale-graph reach (resolved in implementation plan).** Gap #1 will be covered in the always-on
  frontmatter path as well as the graph path, so source-authored paper/consumer links work without a
  current graph while proposition-derived reach still comes from the materialized graph.
- **Role filtering.** `dataset_usage` carries a `role` (`analyzed`/`validation_source`/`cited`/
  `upstream`/`training`/`set_definition_source`). Should a `cited`-only usage count toward reach the
  same as `analyzed`? v1 proposal: count all roles equally (matches the proposition path, which does
  not filter by role); revisit if `cited` proves too weak a signal.
- **Double-counting.** When a paper is `related:` to a Q/H *and* an evidence-line for the same dataset
  supports a proposition that bears on the same Q/H, the union dedups by Q/H id (sets), so reach is not
  inflated. Confirm with a test.

## Non-goals

- No new findings store or schema field — both extensions read existing fields (`dataset_usage`,
  `related:`, `datasets:`).
- No change to readiness, leverage, the gated-level policy, or the CLI surface.
- Not addressing reference-class datasets, commons promotion, or access-verification ergonomics —
  those are tracked separately as feedback (fb-2026-06-24-012…018).

## Validation sketch

- Synthetic project test for Gap #1: a `dataset:d` used by `paper:p` (`dataset_usage`), `paper:p
  related: hypothesis:h` (no evidence-line, no proposition). Assert `usage_reach(...)["dataset:d"] ==
  {"hypothesis:h"}` (pre-change: `set()`).
- Synthetic project test for Gap #2: `question:q` with `datasets: ["dataset:d"]` and no `related:`.
  Assert `frontmatter_reach(root)["dataset:d"] == {"question:q"}` (pre-change: absent).
- **CLI-level test for the chosen graph behavior** (required if Gap #1 is fixed via the graph path).
  The two unit tests above exercise `usage_reach`/`frontmatter_reach` in isolation — an implementation
  can pass both while still failing "works out-of-the-box," because the CLI only feeds `usage_reach` a
  graph when one exists; if that graph is stale, it reflects the last build rather than current
  frontmatter. Add a `dataset prioritize` CLI test that asserts the chosen out-of-the-box semantics:
  e.g. paper-mediated coverage with **no** `graph.trig` present (forces the frontmatter path to carry
  Gap #1 if that is the decision), and the stale-graph case (asserts the warning fires and documents
  whether recent source edits are covered by the frontmatter bridge or remain absent until rebuild).
  Without this, the stale/missing degraded modes above are untested.
- Regression: the full `tests/test_dataset_prioritize*` suite must pass unchanged (additive property).
