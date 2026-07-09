# Typed claim-to-claim relations

**Status:** proposal / feedback
**Raised from:** `cancer/mechanisms/evolution`, `/science:explore-ideas` pass 2026-07-08
**Author:** assistant (Claude Opus 4.8), at user request
**Companion:** `2026-07-09-explore-ideas-third-run-frictions-design.md` — its
group E (`decision: merge` for `already-covered` candidates) is sequenced after
this proposal, because a merge must write a typed edge rather than an untyped
`related` entry.

## The gap

The substrate can express *evidence qualifying a claim*. It cannot express
*a claim qualifying another claim*.

Concretely, `SupportDirection` in
`science/src/science_tool/evidence_payload.py` already carries exactly the
right vocabulary:

```python
SupportDirection = Literal[
    "supports", "disputes", "qualifies",
    "methodological-input", "framework-proposal",
    "quality-record", "operation-record",
]
```

and it composes with `ValidationRole = "gate-update"` and
`PropagationPolicy = "propagate-blocking"`.

But that vocabulary is reachable only from an `evidence-line`, whose
`target` is a `proposition` (see
`science/model/src/science_model/templates/evidence-line.md`). Between two
epistemic entities the only available edge is:

```python
related: list[str] | None = None    # entities.py:163, :313
```

— an untyped list of id strings. `related` cannot distinguish "these two
hypotheses are about the same subject" from "if this hypothesis is true,
that hypothesis's operationalization is invalid."

## Why it matters — the case that surfaced it

`/science:explore-ideas` produced two hypotheses in the evolution project
that are not siblings of the entities they touch:

- `hypothesis:0017-ith-as-evolutionary-rate-marker` — claims the
  ITH→resistance association is confounded by evolutionary rate. If true,
  analyses regressing outcome on ITH *without a rate covariate* estimate a
  biased quantity. It does not compete with
  `question:0105-cna-ith-vs-plasticity-relapse-driver`; it constrains how
  q105 must be specified.
- `hypothesis:0016-plasticity-as-stochastic-epigenetic-noise` — a
  construct-validity challenge. `h002`/`h004`/`h005` all operationalize
  "plasticity"; if the construct conflates environment-triggered switching
  with environment-independent fluctuation, their existing evidence does not
  discriminate, regardless of how much of it accumulates.

Both are falsifiable claims that should accumulate their own evidence — so
filing them as `theme` guardrails is wrong (it forfeits belief tracking).
But filing them as plain hypotheses linked by untyped `related` is also
wrong: it loses the asymmetry, and nothing in the graph tells a later
`compare-hypotheses` or `interpret-results` pass that h017's truth-value
*gates* q105's estimand.

Today the constraint survives only as prose in the body plus a `science
tasks` entry — invisible to the graph, to attention ranking, and to
federation.

## Sketch of a fix

Promote the existing `SupportDirection` semantics to a typed entity→entity
edge. Minimal shape, reusing vocabulary already in the codebase:

```yaml
# in hypothesis:0017 frontmatter
constrains:
  - target: question:0105-cna-ith-vs-plasticity-relapse-driver
    relation: qualifies          # reuse SupportDirection
    role: gate-update            # reuse ValidationRole
    propagation: propagate-blocking
    note: >
      Any ITH→outcome estimand must include an evolutionary-rate covariate.
```

Properties worth preserving:

- **Asymmetric and directional.** `related` is symmetric in practice;
  `constrains` must not be.
- **Belief-inert on the target.** A `qualifies` edge should not move the
  target's belief scalar. It should mark the target's *operationalization*
  as conditionally invalid, which is a different axis — closer to the
  existing `edge_status`/`identification` split in
  `references/dag-two-axis-evidence-model.md` than to support/dispute.
- **Surfaceable.** `science project index` and the attention ranking should
  be able to answer "what claims currently gate this one?"

## Open questions for the maintainer

1. Is `qualifies`-between-entities better modelled as a first-class edge, or
   as a `proposition` on the constraining hypothesis whose `target` is the
   constrained entity? The latter reuses more machinery but overloads
   `proposition`, which currently means "a decomposable sub-claim of *this*
   entity."
2. Should a `gate-update` edge block `interpret-results` from updating the
   target's belief until the gating claim is resolved, or only warn? Blocking
   is epistemically cleaner and operationally annoying.
3. Does this subsume the `guardrail` concept that `commands/add-theme.md`
   references but no entity kind implements?

## Not doing yet

No code change proposed here. This is a substrate-gap report from a
downstream project, filed because the workaround (prose + task) silently
drops the strongest structural information the exploration pass produced.
