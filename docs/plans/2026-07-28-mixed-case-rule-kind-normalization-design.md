# Mixed-case rule-kind normalization

**Date:** 2026-07-28

## Problem

`science health` builds a finding registry before running health checks. Projects
that enable the chemistry ontology include its legitimate mixed-case entity kind
`pH` in the active kind set. The status-vocabulary rule family currently maps an
active kind to a rule-ID segment by replacing underscores with hyphens only, so
registry construction attempts to declare `pH.status-vocabulary`.

`FindingRule` correctly rejects that value because stable rule IDs are lowercase
dotted kebab-case. The same incomplete mapping also affects the
`<kind>.unbacked-inverse` family.

## Decision

`rule_kind_segment(kind)` will be the canonical wire mapping from an entity-kind
name to a rule-ID segment:

1. lowercase the kind name;
2. replace underscores with hyphens.

Thus `pH` maps to `ph`, `workflow_run` maps to `workflow-run`, and existing
lowercase kebab-case names remain unchanged.

Only the rule-ID segment is normalized. The original kind name remains the input
to entity lookup, status-vocabulary lookup, titles, and `severity_for_kind`.

## Collision handling

Both dynamic rule families already fail before registry construction when two
active kinds map to the same rule segment. The collision check remains in force
after lowercase normalization, so a set containing both `pH` and `ph` fails
explicitly instead of choosing one by iteration order.

## Alternatives rejected

- Allow uppercase characters in `FindingRule.id`. This would weaken the stable
  lowercase wire contract for every producer to accommodate one incomplete
  mapping.
- Exclude ontology entity types from the dynamic families. This would alter
  validation coverage and the meaning of the active kind registry rather than
  correcting its rule-ID projection.

## Verification

Focused tests will establish that:

- `rule_kind_segment("pH") == "ph"`;
- status-vocabulary and supersession rules for `pH` have valid lowercase IDs;
- mixed-case kinds that normalize to the same segment fail early;
- existing underscore and kebab-case mappings remain unchanged.

After the focused tests pass, run the affected validation tests, lint and type
checks, then rerun `uv run science health` in
`~/d/cancer/cancer-types/multiple-myeloma` using the fixed toolkit.
