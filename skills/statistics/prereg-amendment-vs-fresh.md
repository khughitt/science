# Pre-Registration Amendment vs Fresh Pre-Registration

Use when a follow-up analysis changes data, operationalisation, model,
thresholds, or scope after an earlier pre-registration exists.

The question is whether the new document tests the same proposition with a
changed implementation, or asks a genuinely new question. Amendments preserve
continuity and make deviations auditable; fresh pre-registrations prevent old
commitments from being stretched beyond their scope.

## Choose Amendment When

- The hypothesis/proposition and contrast are the same.
- The cohort is narrowed or expanded for a documented QA reason.
- The metric changes to fix a known measurement problem.
- A sensitivity becomes primary because the original operationalisation failed.
- The new run inherits most sections from the parent.
- The purpose is to arbitrate whether an earlier null/support result was
  operationalisation-driven.

## Choose Fresh Pre-Registration When

- The hypothesis or causal estimand changes.
- The outcome, exposure, or independent unit changes enough that the old power
  and assumptions no longer apply.
- The analysis asks a new biological question.
- The model family changes because the estimand changed, not just because the
  old model was inadequate.
- The result will stand independently rather than as a rerun or extension.

## Amendment Structure

Start with an inheritance table:

| Parent section | Status | Notes |
|---|---|---|
| Scope/rationale | inherited/revised/dropped/added | why |
| Cohort | inherited/revised/dropped/added | why |
| Metric | inherited/revised/dropped/added | why |
| Model | inherited/revised/dropped/added | why |
| Sensitivity panel | inherited/revised/dropped/added | why |
| Verdict rule | inherited/revised/dropped/added | why |
| Output artifacts | inherited/revised/dropped/added | why |

Then include only revised or new sections in full. Do not restate unchanged
parent text unless needed for clarity.

## Required Amendment Fields

- Parent pre-registration ID and date.
- Exact sections inherited unchanged.
- Exact sections revised and why.
- Whether parent results are known before the amendment.
- Which decisions are still locked before the new verdict-bearing run.
- Whether the amendment can override, narrow, or only contextualize the parent.
- New power floor if n, contrast, or estimator changed.
- New sensitivity-arbitration rule if any sensitivity changed status.

## Common Failure Modes

- **Fresh document laundering.** A rerun is written as a new pre-reg to hide that
  it responds to a failed result.
- **Amendment overreach.** A document claims inheritance while changing the
  estimand.
- **Selective inheritance.** Favorable parent choices are inherited; unfavorable
  constraints disappear.
- **Known-result ambiguity.** The reader cannot tell which choices were made
  before or after seeing parent outcomes.
- **Power drift.** Cohort narrowing is treated as procedural even though it
  changes the detectable effect.

## Reporting

Use explicit labels:

- `fresh_pre_registration`
- `amendment_before_results`
- `amendment_after_parent_results`
- `post_hoc_exploratory_followup`

If parent results are already known, say so in the first paragraph. An amendment
can still be useful, but it cannot pretend to be a fully fresh prospective
commitment.
