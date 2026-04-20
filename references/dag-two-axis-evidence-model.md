# Two-Axis DAG Evidence Model

How to annotate causal-DAG edges with honest, comparable evidence labels.
Consumed by the `dag` subcommand group (`science-tool dag render / audit /
staleness`) and by the `/science:dag-audit` skill.

## Motivation

An edge in a project's causal DAG is a claim. Two independent questions
always apply to that claim:

1. **How well-replicated is it?** — Is the effect seen in one dataset, five,
   or is it consistent with a literature baseline but not independently
   observed?
2. **How causally identified is it?** — Does the evidence come from a
   perturbation (an intervention on the cause, observing the effect), or
   from a temporal within-subject ordering, or from a cross-sectional
   correlation whose direction is **assumed**?

These are orthogonal. "Strong replication + no intervention" (e.g., a
correlation confirmed in five independent cohorts) is legitimate and
common. "One intervention + no replication" (a single knockout
experiment) is also legitimate but different. Collapsing the two into
one "is this a good edge?" label hides the asymmetry.

The two-axis model represents them separately:

- **`edge_status`** — replication / epistemic strength. 5 values.
- **`identification`** — causal-identification strength. 5 values.

## `edge_status` — replication strength

| Value | Meaning | Typical evidence |
|---|---|---|
| `supported` | Two or more independent evidence sources OR one decisive experiment | Five-dataset Bayesian meta-analysis; one high-quality perturbation with a rescue control |
| `tentative` | Plausible but single-source / indirect / not yet replicated | One dataset, one paper, one correlation |
| `structural` | Near-definitional (proxy, identity, measurement) | `burden → ISS`; `PHF19 → PRC2` (biochemistry) |
| `unknown` | Explicitly hypothetical; dashed in the DAG | Candidate non-1q driver (awaiting identification) |
| `eliminated` | Retracted / ruled out by subsequent evidence; retained for provenance | t204-closed composition channel; 80/20 architecture claim post-t125 null |

**Default** for newly-scaffolded edges: `unknown`.

## `identification` — causal-identification strength

| Value | Meaning | Typical evidence |
|---|---|---|
| `interventional` | Perturbation / knockdown / overexpression identifies the edge | shRNA, CRISPR KO, small-molecule inhibitor, PROTAC degrader |
| `longitudinal` | Within-subject temporal ordering supports directionality | Paired baseline/relapse samples; time-course RNA-seq |
| `observational` | Cross-sectional regression or replicated correlation; arrow is **assumed**, data is **consistent with** it | Bayesian hierarchical fits across datasets |
| `structural` | Proxy / definitional / measurement relation | Scale/unit conversion; biochemistry |
| `none` | No evidence of any identification type (valid for `unknown` edges) | Dashed / hypothetical edges |

**Default** for newly-scaffolded edges: `none`. **Do NOT default to
`observational`** — that converts missing curation into a positive
evidentiary claim. An un-curated edge has no claimed identification,
not an implicit observational one.

## The axes are orthogonal

Every `edge_status` can combine with every `identification`:

|  | `interventional` | `longitudinal` | `observational` | `structural` | `none` |
|---|:---:|:---:|:---:|:---:|:---:|
| `supported` | strongest | strong | strong | definitional | — |
| `tentative` | weak-decisive | suggestive | suggestive | — | — |
| `structural` | — | — | — | canonical | — |
| `unknown` | — | — | — | — | canonical |
| `eliminated` | — | — | — | — | — |

Some cells are meaningful (e.g., `supported-observational` = most
replicated correlations) and some are rare (`eliminated-interventional`
= an intervention specifically overturned the claim). The point is that
both axes should be readable independently — if 28 of 85 edges are
`supported` but only 6 are `interventional`, that asymmetry should be
visible to the reader, not averaged into a generic "good edge" quality.

## When to use `eliminated` vs `unknown`

They look superficially similar (both downweight the edge) but encode
different histories:

- **`unknown`** — "We haven't tested this." A candidate relationship,
  not yet challenged. Removing it loses nothing scientifically.
- **`eliminated`** — "We tested this. It didn't hold up." A retracted
  mechanism. Removing it loses provenance: a future reader will
  rediscover the same dead end.

Use `eliminated` with a mandatory `eliminated_by` field citing the task
/ interpretation / discussion that closed it. The render layer shows
eliminated edges in dotted grey with a `[✗]` prefix; the staleness
audit leaves them frozen (they never drift, by definition).

## Caveats as a separate field

When an edge is supported overall but carries an important qualifier,
use `caveats: [...]` — a list of short, structured annotations:

```yaml
- id: 6
  source: prc2
  target: ccis
  edge_status: supported
  identification: interventional
  caveats:
    - "Perturbation-mechanism-dependent: PRC2-complex loss required;
       catalytic-only EZH2 inhibition insufficient (t197 / t205 adjudicated)"
```

Caveats do not change the status, but they surface context a single
label can't carry. The render layer can optionally display them as
edge-label footnotes.

## How posteriors fit

When an edge has been fit as a Bayesian edge (β, HDI, P(sign)), the
posterior lives in a separate `posterior:` block (see
`docs/specs/2026-04-17-inquiry-edge-posterior-annotations-design.md`).
Posteriors are complementary to the two-axis labels:

- `edge_status` says "how replicated is this conclusion."
- `identification` says "what kind of evidence backs this direction."
- `posterior` says "what is the fitted magnitude and uncertainty."

The render layer uses `posterior.beta` to scale edge line thickness and
`posterior.hdi` crossing zero to force a dashed style — but only for
non-eliminated edges. The precedence rules live in the render spec.

## Cross-references

- **`docs/specs/2026-04-19-dag-rendering-and-audit-pipeline-design.md`** —
  introduces `eliminated` and `identification`; defines the render
  precedence matrix and the tagged-ref schema.
- **`docs/specs/2026-04-17-edge-status-dashboard-design.md`** —
  original `edge_status` enum spec; amended 2026-04-19 to include
  `eliminated`.
- **`docs/specs/2026-04-17-inquiry-edge-posterior-annotations-design.md`** —
  the posterior block schema.
- **`docs/specs/2026-03-07-phase4b-causal-dag-design.md`** — the
  underlying inquiry / graph/causal layer that these annotations
  compose with.

## Quick vocabulary check

Before committing an edge-status change, ask:

- "Would a skeptical reader agree this is `supported`, not `tentative`?"
  (≥ 2 independent sources, or one decisive experiment — not "I believe
  it strongly.")
- "Is this edge claiming `interventional` identification because we
  have a specific perturbation, or because I'm casually labeling
  correlations?"
- "If I retract this later, will I regret not making it `eliminated`
  rather than deleting?"

The honest answer is usually the conservative one. The two-axis model
exists because the underlying asymmetry is real; label edges in
a way a future reader can trust.
