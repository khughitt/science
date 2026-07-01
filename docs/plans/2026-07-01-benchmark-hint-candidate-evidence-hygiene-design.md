# Benchmark Hint Candidate Evidence Hygiene Design

## Goal

Improve `science benchmark hint-candidates` actionability by keeping obvious report/prose boilerplate visible, but no longer presenting it as `domain-candidate` material for benchmark hint lexicon expansion.

## Context

After the classification cleanup, fresh active-project reports no longer put project shorthand such as `mm30` and `pais` in `domain-candidate`. The remaining top rows still include non-actionable prose/report terms such as `related`, `details`, `banner`, `demonstrates`, `promoted`, `any`, `over`, and `current`.

These terms are useful as evidence that project text contains generic report or writing patterns, but they are not useful benchmark facet candidates. Treating them as domain candidates makes the report noisier and encourages weak lexicon additions.

## Design

Use the existing category system and keep JSON shape stable.

- Add the report/prose terms to the existing non-domain classification path.
- Route them to `workflow-or-modeling`, not to `domain-candidate`.
- Do not suppress them through `_UNMAPPED_TERM_EXCLUSIONS`; users should still be able to see that these terms are present.
- Preserve existing precedence: `project-local` first, then workflow/modeling/report terms, then domain-candidate.
- Do not add new `FACET_HINT_TERMS` mappings in this slice.

Initial term set:

```text
any
banner
current
demonstrates
details
over
promoted
related
```

## Non-Goals

- No new benchmark facet mappings.
- No semantic/fuzzy term grouping.
- No changes to `hint-candidates` JSON schema.
- No generated project review artifacts.

## Testing

Add one focused report-level test showing the report/prose terms are emitted as `workflow-or-modeling` and do not appear as `domain-candidate`.

Keep active-project smoke checks as verification rather than brittle fixtures:

- multiple myeloma should no longer show `related`, `details`, `banner`, `demonstrates`, or `promoted` as top domain candidates.
- natural-systems should no longer show `current` or `over` as top domain candidates.
- cbioportal should no longer show `any` as a top domain candidate.

## Success Criteria

- Focused hint-candidate tests pass.
- Ruff passes on touched files.
- Fresh active-project reports have fewer obvious boilerplate terms in `domain-candidate`.
- No review files are written during smoke checks.
