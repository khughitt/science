---
id: "convention:project-working-model-h00"
type: "convention"
title: "Project working model (h00)"
status: "active"
created: "2026-05-31"
updated: "2026-05-31"
---

# Project working model (h00)

Reserve the hypothesis id **`h00`** in every project for an explicit description
of the project's **overarching working model** — the model that the project's
ordinary hypotheses (`h01`, `h02`, …) are *facets, components, or predictions of*.

## Why

Today the overarching model of a project is **implicit**: a reader must
reverse-engineer it by piecing together the individual hypotheses. `h00` makes
it **first-class and discoverable** — one canonical place that says "here is the
model we are working within," with the individual hypotheses hanging off it.

The science framework itself is no different: `science-meta` uses `h00` to make
the framework's *own* working model (how knowledge/evidence/belief is
represented) explicit — see `hypothesis:h00-working-model` in `meta/`.

## The convention

- **Optional.** Create `h00` only *if/when* the project has an articulable
  working model. A project with only loosely-related hypotheses need not have one.
- **Location.** `specs/hypotheses/h00-<slug>.md` (alongside the other
  hypotheses), or the project's hypothesis directory.
- **Not a testable hypothesis.** `h00` is the umbrella *model*, not a truth-apt
  conjecture under support/dispute. It does not carry the belief lifecycle the
  way `h01+` do. For tooling compatibility it may use `type: hypothesis` with a
  `role: working-model` marker (or a project-local `type: model`); the defining
  features are the reserved `h00` id + working-model content. **Note (until the
  deferred validator exemption lands):** a `type: hypothesis` `h00` still
  satisfies the validator's required `## Falsifiability` section — frame it
  honestly as *"revised, not refuted; the facet hypotheses (`h01+`) carry the
  falsifiable content and are the model's revision triggers."* See `meta`'s
  `hypothesis:h00-working-model` for reference wording.
- **Prefer explicit structure over prose.** Authors choose the formality, but a
  working model should be expressed **graphically / structurally** where
  possible — a diagram, a typed entity-and-relation schema, a causal/Bayesian
  DAG, or a patchwork of such — not prose alone. Prose-only `h00` is allowed but
  discouraged; the point is an inspectable model.
- **Cross-link the facets.** `h00` should reference the `h01+` hypotheses (and
  key questions) it subsumes via `related:`, and those entities may point back.
- **Depth is the author's call.** `h00` can be a one-paragraph sketch + diagram,
  or a rich structural model with a companion design doc (`doc/plans/…`) holding
  the full detail. Start light; deepen as the model firms up.

## Relationship to existing concepts

- Complements the per-proposition `current_working_model` / `rival_model_packet`
  fields (`docs/proposition-and-evidence-model.md`): those are *local* model
  commitments on a single proposition; `h00` is the *project-level* umbrella.
- A formal `h00` is the natural home for a project's
  patchwork-of-epistemic-neighborhoods model (see
  `meta/doc/plans/2026-05-31-epistemic-causal-probabilistic-graph-model-design.md`).

## Possible follow-ups (not yet adopted)

- Validator/template support: recognize the reserved `h00` slot, optionally warn
  when `h00` is prose-only, and offer an `h00` scaffold in `science hypothesis`.
- These are deferred; this convention is documentation-first until enforcement is
  explicitly requested.
