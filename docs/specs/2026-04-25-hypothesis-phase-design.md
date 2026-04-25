# Hypothesis Developmental Phase

**Date:** 2026-04-25
**Status:** Draft
**Author:** keith.hughitt@gmail.com

## Motivation

The existing `status:` field on a hypothesis tracks **evidence state** —
where the hypothesis sits on the falsifiability continuum (proposed,
conjecture, under-investigation, supported, refuted). It does not track
**developmental commitment** — how seriously the project is treating the
hypothesis as an organizing frame.

These are independent properties. A hypothesis can have no evidence yet
and still be a committed frame the project plans to investigate; another
can have no evidence yet and be a tentative framing the project is
trialing and may walk back. Today there is no way to express that
distinction, which creates two failure modes:

1. **Promotion paralysis.** A user with an emerging research direction
   that lacks substantial evidence faces a binary choice — draft a full
   hypothesis (overcommit; the spec implies investigation discipline that
   hasn't been earned) or leave it as scattered orphan questions and
   discussions (undercommit; orphans don't organize work). There is no
   lightweight middle.
2. **Status drift.** Hypotheses authored as `status: proposed` long ago
   drift in evidence state without anyone tracking developmental
   commitment. A reader cannot distinguish "we drafted this once and
   walked away" from "we are actively investigating but haven't
   accumulated evidence yet."

A concrete example surfaced in the natural-systems-guide project on
2026-04-25 during a `/science:big-picture` follow-up: a coherent cluster
of orphan questions and 5 data-fitting pilot interpretations pointed at
a candidate "empirical fidelity" hypothesis (provisional H07). The
methodology pilot worked; the structural-prediction claim was
under-evidenced. There was no clean way to promote the framing without
implying the full epistemic standing of the existing H01–H06.

## Goal

Introduce a separate `phase:` field on hypotheses that tracks
developmental commitment, orthogonal to `status:`. Add the minimum
tooling support needed for downstream commands to render candidates
distinguishably from active hypotheses.

This is a v0 proposal. It deliberately defers a number of natural
extensions (archived/superseded phases, lifecycle automation, citation-
rule changes, skill heuristics) to a v1 that responds to actual usage
rather than anticipated needs.

## Scope (v0)

### In scope

- New optional `phase:` frontmatter field on hypotheses with two
  enumerated values: `candidate | active`.
- Default value when absent: `active` (preserves existing-project
  semantics on read).
- Updated hypothesis template (`templates/hypothesis.md`) with `phase:
  active` in frontmatter and a documentation-only "Promotion criteria"
  body section convention for `phase: candidate`.
- Validator support: `phase`, when present, must be one of the two
  enumerated values. No further requirements.
- `/science:big-picture` rendering: candidates appear in a separate
  "Candidate frames" section of the project rollup. Same citation,
  grounding, and length rules as active hypotheses. Visual / structural
  distinction only.

### Out of scope (v0)

Everything below is deferred to v1, where it can be designed against
real usage patterns.

- Additional phase values (`archived`, `superseded`).
- Validator-required `promotion_criteria:` field.
- `/science:add-hypothesis` skill heuristics for choosing phase.
- `/science:next-steps` actions for promoting / retiring candidates.
- Citation-rule changes for candidate synthesis sections (its own
  separate design).
- Knowledge-graph emission of phase.
- Migration tooling that rewrites existing hypotheses.
- Per-claim phase.
- Cross-project phase visibility through `/science:sync`.

## Design

### Phase enumeration and semantics

| Phase | Meaning | Treated as authoritative? |
|---|---|---|
| `candidate` | Promoted to organize orphan work; framing is being trialed; may be walked back without ceremony | Renders in candidate-frames section; same evidence rules |
| `active` | Committed frame. Default. | Yes; renders in main hypothesis arc |

`status:` and `phase:` evolve independently. Common combinations:

- `phase: candidate, status: proposed` — newly-promoted candidate, no
  evidence yet. Most common starting state.
- `phase: candidate, status: under-investigation` — candidate
  accumulating evidence; promotion to active becomes a near-term
  decision.
- `phase: active, status: conjecture` — committed frame with claims
  formed but not yet decisively tested. Current default for many
  in-flight hypotheses.
- `phase: active, status: supported` / `refuted` — committed frame with
  claims empirically backed or rejected.

### Frontmatter

```yaml
phase: "candidate"  # candidate | active (default: active)
```

That is the entire schema addition for v0.

### Template changes

`templates/hypothesis.md`:

- Add `phase: "active"` to the frontmatter block, with a comment
  explaining the candidate alternative.
- Add a new optional body section **"Promotion criteria"** between
  "Falsifiability" and "Supporting Evidence". Its body comment
  explains: required prose for `phase: candidate`; absent for `phase:
  active`. This is a documentation convention, not a validator-enforced
  rule in v0.

### Validator behavior

The frontmatter validator gains exactly one new rule:

- If `phase:` is present, its value must be `candidate` or `active`.

No requirement that `phase: candidate` declare promotion criteria. No
other field interactions. Existing hypotheses without `phase:` continue
to validate unchanged.

### `/science:big-picture` rendering

The rollup file (`doc/reports/synthesis.md`) gains one new section,
placed after "Research fronts" and before "Knowledge Gaps":

```markdown
## Candidate frames

<!-- One paragraph per candidate hypothesis. Same citation rules as
     the per-hypothesis files. May be empty if no candidates exist. -->
```

Per-candidate synthesis files continue to live at
`doc/reports/synthesis/<id>.md` with the **same** length, citation,
grounding, and provenance-coverage rules as active hypotheses.
Candidates are simply listed under their own rollup heading instead of
being mixed into the main hypothesis arc.

The rollup frontmatter's `synthesized_from:` list includes both active
and candidate hypothesis files; they are distinguished by reading each
file's `phase:` field.

If no candidate hypotheses exist in a project, the "Candidate frames"
section emits a one-line "No candidate hypotheses." marker rather than
being suppressed entirely. This makes the absence visible and reminds
users that candidate phase exists.

## Migration

Existing hypotheses without `phase:` are read as `phase: active`. No
file edits required. Projects opt into candidate phase by adding
`phase: candidate` to a new (or existing) hypothesis when they want
the rendering distinction.

The natural-systems-guide project will be the first concrete adopter:
H07 (empirical-fidelity alignment) is already drafted with `phase:
candidate` and will render correctly under v0 once the big-picture
change lands.

## Risks

### Risk: candidates become a permanent epistemic dodge

Without lifecycle pressure, `phase: candidate` could become a way to
hold framings indefinitely without testing them.

**v0 mitigation:** none beyond the visual/structural distinction in
big-picture output, which makes candidate accumulation visible to
the reader. v1 will add validator and `/science:next-steps`
mechanisms for surfacing stale candidates, designed against the
actual accumulation patterns observed under v0.

### Risk: confusion with `status: proposed`

Two fields that both convey something like "tentative" is genuinely
confusing on first encounter.

**v0 mitigation:** the template comment and big-picture rollup
explicitly explain the distinction. If real users persistently
conflate the two, v1 can rename `phase: candidate` (cheap with a
two-value enum) or revisit the design.

### Risk: tooling fragmentation

Other commands (`/science:status`, `/science:next-steps`,
`/science:add-hypothesis`) may eventually want phase-aware behavior.

**v0 mitigation:** the schema is forward-compatible. Other commands
read the `phase:` field as needed; they default to ignoring it in v0.

## Naming, alternatives, decisions

### Why a new field, not an extended `status:`?

Extending `status:` to include `candidate` and `active` would mix two
axes. A hypothesis would have to pick `under-investigation` *or*
`candidate` when both are true. The existing `status:` enum is itself
a continuum (proposed → conjecture → under-investigation →
supported/refuted) and adding developmental phase loses the natural
ordering.

### Why not just leave `status: proposed` as the implicit candidate marker?

Today `status: proposed` means "freshly drafted, no evidence yet" —
but actively-investigated hypotheses pass through this state on the
way to `under-investigation`. If "proposed" also meant "we might walk
this back," tooling that wanted to render candidates differently
would treat every newly-drafted hypothesis as a candidate, which is
wrong.

### Why `candidate` rather than `provisional` / `tentative` / `trial`?

`candidate` is the term that's most clearly oriented at *promotion* —
the expectation is that a candidate either becomes active or is
retired. The alternatives all carry permanence connotations that
`candidate` specifically rejects. With a two-value v0 enum, renaming
later is cheap if real users find it confusing.

## Follow-on work (v1 candidates)

These are deliberately deferred until v0 sees real use. Each is a
plausible v1 feature; landing v0 first lets the design respond to
observed behavior rather than anticipated needs.

- **Additional phase values.** `archived` for retired-but-retained
  hypotheses (today these are mixed into `status: refuted`);
  `superseded` for hypotheses replaced by a successor. `superseded`
  may be better expressed as a separate `superseded_by:` field
  independent of phase, since it is a relation rather than a
  lifecycle stage.
- **Required `promotion_criteria:` for candidates.** A frontmatter
  field listing the conditions that would convert a candidate to
  active. Validator-enforced. Justified once we have evidence
  candidates are accumulating without conversion.
- **`/science:next-steps` lifecycle actions.** "Promote candidate"
  and "Retire candidate" actions surfaced when criteria are met or
  staleness is detected. Requires `promotion_criteria:` to land first.
- **`/science:add-hypothesis` skill heuristics.** Default the phase
  based on evidence density at authoring time. Requires usage data
  to calibrate the heuristic thresholds.
- **Citation-rule relaxation for candidate synthesis sections.** A
  separate design with its own tradeoffs (does relaxation make
  candidates a place to hide weak claims?). Should not piggyback on
  the schema change.
- **Knowledge-graph emission.** Add a `<hypothesis> sci:phase
  "<value>"` triple so graph queries can filter. Wait until the export
  pipeline stabilizes.
- **`/science:promote-candidate` skill.** Automates the promotion
  checklist and updates phase atomically. Natural extension once
  promotion_criteria exist.
- **Per-claim phase.** Currently claims carry only `status:`.
  Reconsider once the proposition-and-evidence model surfaces a
  concrete need.
- **Cross-project phase visibility.** When `/science:sync` shares
  hypotheses, candidates should propagate as candidates.
