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

When a project uses prose epistemics, `science health` also reads
`data/prose-health/prose-health.json`. It reports prose-health findings but does
not rebuild the artifact implicitly. Regenerate that derived state with:

```bash
science annotate build-prose-health --write
```

Derived cross-paper literature evidence can be inspected without writing files:

```bash
science annotate cross-paper-evidence
science annotate cross-paper-evidence --source proposition:<slug> --format json
```

The project-wide form reports every proposition that gains derived literature
support or dispute, plus all derivation faults. The `--source` form reports the
derived units for one proposition and computes the literature-only belief
summary through the same belief reducer used for evidence summaries.

Projects may mark a validation warning as reviewed in `science.yaml` when the
warning is an intentional, documented residual risk rather than an unresolved
defect. Accepted warnings are omitted from `science validate` output/counts and
from `totals.findings_total`; `science health` reports them in `accepted` so the
audit trail remains visible.

```yaml
health:
  accepted_validation:
    - finding_id: "<64-lowercase-hex>"
      fingerprint_version: 1
      severity_scope: ["warn"]
      reason: Reviewed residual risk; the project is intentionally retaining it.
```

Use the finding fingerprint from health output and a concrete reason. `warn` and
`error` are the canonical severity spellings. Only validation findings are
eligible for these entries, and `science validate` remains warn-only: even an
entry whose scope includes `error` does not hide validation errors from that
command.

Migrate older prose-keyed entries with:

```bash
science findings migrate-acceptances
science findings migrate-acceptances --apply
```

The command is a dry run by default. `--apply` is all-or-nothing: any invalid,
stale, ambiguous, duplicate, or indeterminate entry prevents the write.
Migrated entries omit `accepted_on` because their historical acceptance date is
unknown. Rerunning the command reports valid replacement entries as
`already-current`; when every entry is current, `--apply` exits successfully
without rewriting `science.yaml`.

Migration reports syntax or model failures as `invalid` and includes the
classifier error. `stale` is reserved for a valid legacy matcher that found no
current finding. Legacy and invalid entries suppress nothing. After emitting
its complete table or JSON output (and any `--output` notice), `science health`
exits 2 when either kind is configured because it could not apply the requested
acceptance counts. Ordinary ERROR findings do not change the health exit code.

Do not accept a warning until the project has decided that the residual state
is honest and useful to track.

Health JSON uses the shared audit-report schema. Its channels remain distinct:

- `findings` contains current validated issues; `totals.findings_total` is
  exactly their row count.
- `accepted` contains reviewed validation warnings without counting them as
  current findings.
- `metrics` contains numeric coverage and inventory observations. Metrics are
  never reconstructed into findings.
- `caveats` records diagnostics that ran with a disclosed limitation.
- `unwired` records diagnostics that could not run. An unwired report is never
  described as clean, even when it contains no findings.

## Needs Review And Freshness

Freshness and `needs-review` are attention surfaces, not hard gates. They help
you decide which entities deserve another look after upstream evidence,
datasets, code, or propositions change.

`science graph attention-rank` provides a deterministic review queue over the
materialized graph. It uses the same attention scoring substrate as
`attention-sample`, but sorts candidates by derived weight instead of sampling
them. The open-question-debt component raises attention for epistemic entities
connected to active, partially answered, or deferred questions through
`skos:related` links or shared theme membership. This deliberately does not use
`bears_on`, because unanswered scoping questions often sit outside the stronger
dependency layer.

```bash
science graph attention-rank
science graph attention-rank --kind proposition --limit 20
```

`science entity rotation` is the coverage *floor* that complements
`attention-rank`'s weighted queue. It ranks the reviewable corpus — the same
domain `entity review` resolves — least-recently-reviewed first and prints an
adaptive per-sweep budget, so the least-recently-touched entities are read first.
It is stateless and read-only, advisory like the other attention surfaces: it
selects but never reviews, so a selected row only leaves the least-recently-
reviewed prefix once you stamp it with `science entity review <ref> --note ...`.
It reaches full coverage in a bounded number of sweeps only when each sweep both
completes its budget and stamps reviews with a date strictly later than the
corpus's current maximum `last_reviewed`; the two tools are complementary —
attention biases toward what changed, rotation drives floor coverage.

```bash
science entity rotation
science entity rotation --all --format json
```

`science entity review` requires a review artifact through `--note`. A review
should record what was inspected and what changed, not merely bump a timestamp.
Programmatic callers can still use the lower-level review function without the
CLI artifact guard when they are preserving existing metadata.

## Honest Warning States

A warning is not automatically a failure. If evidence is weak, indirect,
contested, or incomplete, the correct outcome may be to leave the warning
visible and explain the residual uncertainty.
