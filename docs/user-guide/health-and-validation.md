# Health And Validation

Validation and health checks protect explicit references, durable evidence,
non-silent uncertainty, and reproducible project structure.

Common commands:

```bash
science validate
science health
science entity needs-review
science belief snapshot
```

## Validation

`science validate` checks project structure and authored files. It catches
schema errors, broken references, invalid frontmatter, and convention problems.

## Health

`science health` aggregates diagnostics across graph migration, references,
aspects, evidence coverage, identity policy, and related hygiene.

Projects may mark a validation warning as reviewed in `science.yaml` when the
warning is an intentional, documented residual risk rather than an unresolved
defect. Accepted warnings are omitted from `health.total_issues` and reported in
`accepted_validation` so the audit trail remains visible.

```yaml
health:
  accepted_validation:
    - rule: belief.fragile-single-line
      severity: warning
      message_contains:
        - proposition/example-target
        - evidence-line/example-sensitive-line
      reason: Reviewed single-line sensitivity; the claim remains intentionally fragile pending independent replication.
```

Use narrow match criteria and a concrete reason. Do not accept a warning until
the project has decided that the residual state is honest and useful to track.

## Needs Review And Freshness

Freshness and `needs-review` are attention surfaces, not hard gates. They help
you decide which entities deserve another look after upstream evidence,
datasets, code, or propositions change.

## Honest Warning States

A warning is not automatically a failure. If evidence is weak, indirect,
contested, or incomplete, the correct outcome may be to leave the warning
visible and explain the residual uncertainty.
