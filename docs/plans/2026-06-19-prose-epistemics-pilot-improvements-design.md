# Prose epistemics pilot improvements design

**Status:** draft design, 2026-06-19.

**Parent:**
`~/d/science/docs/plans/2026-06-17-prose-epistemics-umbrella-design.md`

**Related framework designs:**
- P2 internal prose:
  `~/d/science/docs/plans/2026-06-18-prose-epistemics-p2-internal-prose-design.md`
- P3 domain grounding:
  `~/d/science/docs/plans/2026-06-18-prose-epistemics-p3-domain-grounding-design.md`
- P4 health coverage:
  `~/d/science/docs/plans/2026-06-18-prose-epistemics-p4-health-coverage-design.md`
- Natural-systems application:
  `~/d/science/docs/plans/2026-06-19-natural-systems-prose-epistemics-application-design.md`

**Scope of this document:** follow-up framework improvements learned from the first
natural-systems prose epistemics pilot. This is not P5 of the original framework arc and
not a second natural-systems application plan. It captures small, reusable seams in
`science` that make future prose campaigns less brittle while preserving the P2/P3/P4
contract.

---

## 1. Motivation

The first natural-systems pilot proved the core architecture:

```text
reviewed decomposition artifact
  -> P2 ingest/check/promote
  -> graph build
  -> P3 grounding
  -> P4 prose-health artifact
  -> downstream TS health reader
```

The framework behaved as intended. The pilot produced a truthful early coverage ramp:
three candidate units, three promoted units, zero grounded units, and three unbacked units.
That is the expected starting state for a content campaign with sparse domain evidence.

The friction was not architectural failure. It came from places where downstream code had
to mirror framework rules or paper over operational details:

- Markdown locator preflight had to reproduce P2 resolver semantics.
- Promotion was precise but one unit at a time.
- Source paths and generated graph metadata needed downstream normalization.
- Health output surfaced some operational annotation refs as generic graph warnings.
- The deterministic pilot validated plumbing, not offline-agent decomposition quality.

The right follow-up is to harden the reusable seams in `science`, not to move belief,
promotion, or locator logic into downstream TypeScript.

## 2. Design goals

- Keep Python as the epistemic source of truth.
- Make downstream campaigns call reusable framework helpers instead of mirroring private
  resolver and path rules.
- Preserve explicit, auditable operations. Batch ergonomics must not hide per-unit
  decisions.
- Keep P2/P3/P4 artifacts stable unless a concrete consumer break requires a schema
  revision.
- Add an offline-agent artifact pilot so the next validation tests decomposition quality,
  not only plumbing.

Non-goals:

- No live LLM orchestration in `science`.
- No TypeScript belief or promotion computation.
- No new locator regime beyond Markdown regenerable locators.
- No automatic evidence authoring.
- No pass/fail health gate for sparse early grounding.

## 3. Long-term shape

The ideal long-term system has three operator surfaces.

1. **Artifact validation surface.** A project can ask `science` whether an offline
   decomposition artifact will resolve against the current source before ingest. The check
   uses the same resolver code as P2, returns exact unit-level findings, and never requires
   downstream code to approximate heading/quote matching.
2. **Review and promotion surface.** A project can plan and apply reviewed promotions for
   many units while preserving the existing single-unit audit trail. Batch mode is a
   convenience wrapper over the same decision engine, not a different promotion path.
3. **Consumer health surface.** P4 remains the only downstream JSON contract. Project
   health readers consume `data/prose-health/prose-health.json`; `science health` and graph
   validation understand prose operational refs well enough to avoid duplicate or misleading
   warnings.

The offline agent remains outside the framework. Its output is a P2 JSON artifact that
`science` validates, ingests, checks, promotes, grounds, and rolls up.

## 4. Framework improvements

### 4.1 Reusable Markdown locator preflight

Problem: the pilot writer had to implement its own heading-path and quote-context checks.
That downstream check initially drifted from `InternalProseAdapter.resolve_markdown_locator`
because the framework resolver searches only inside the matched section body and requires a
single context match.

`check-prose-decomposition` already performs this resolver check, but it operates on the
already-ingested latest artifact and its P2 index. The missing seam is pre-ingest
validation of an arbitrary offline-agent artifact file before it mutates project state.

Design:

- Expose one shared resolver-reporting helper in the P2 module boundary.
- Make both `check-prose-decomposition` and the new pre-ingest validator call that helper,
  so persisted-artifact checks and raw-artifact checks cannot drift.
- Provide a small CLI surface for pre-ingest artifact validation:

```text
science annotate validate-prose-decomposition-artifact <artifact.json> --root .
```

The command should:

- parse the submitted artifact with the existing P2 parser
- read the declared Markdown source
- compute or verify the source hash with the same ingest rules
- resolve every unit locator with `InternalProseAdapter`
- report the same per-unit locator statuses and finding vocabulary as
  `check-prose-decomposition`, as JSON or table output
- make unknown skip reason codes and competing candidate quote homes hard failures

This is preflight, not a new persisted artifact. Ingest remains the state-changing command.

### 4.2 Batch promotion planning and apply

Problem: `promote-prose-decomposition` is intentionally one unit per invocation. That is
good for auditability, but awkward once a reviewed artifact has many accepted candidate
units.

Design:

- Add a batch planning command that lists promotion decisions for selected units without
  applying changes.
- Add a batch apply mode that applies a reviewed plan, one existing promotion operation at
  a time.

Suggested command family:

```text
science annotate plan-prose-promotions --source prose-source:<slug> --units reviewed.json
science annotate apply-prose-promotions --source prose-source:<slug> --plan plan.json
```

The plan format should be explicit:

```json
{
  "schema_version": 1,
  "source_ref": "prose-source:example",
  "decomposition_artifact_id": "decomp-...",
  "units": [
    {
      "unit_id": "u001",
      "fingerprint": "sha256:...",
      "decision": "mint",
      "target_ref": null
    }
  ]
}
```

Batch apply must fail early if:

- the source's latest decomposition artifact changed since planning
- a unit fingerprint no longer matches the planned fingerprint
- a unit is skip, stale, unresolvable, or already promoted differently
- a planned link target cannot be resolved

This keeps the existing single-unit promotion logic authoritative while reducing operator
friction. The plan is identity-only: it does not carry a copied candidate payload or claim
text. Apply re-reads the candidate from the latest P2 artifact and may print that claim in
the audit log for human confirmation.

### 4.3 Source-path canonicalization

Problem: downstream wrappers had to normalize paths to `~/d/...` and avoid leaking absolute
machine paths into committed prose-source metadata or graph revision fields.

This is not greenfield. `prose_source_entity._display_path()` currently stores in-project
paths with a hardcoded `~/d/science` prefix. That is unsuitable for downstream projects
whose project roots are not `~/d/science`, and it conflicts with the stronger durable-data
preference for project-relative paths.

Design:

- Centralize display-path normalization for prose-source metadata and prose health rows.
- Prefer project-relative paths in durable artifacts when the path is inside the project.
- Use `~/d/<project>/...` only in human-facing docs or reports that need a stable host
  shorthand.
- Never write host-specific absolute home or Dropbox paths into durable docs or framework
  artifacts.
- Derive any `~/d/<project>/...` shorthand from the project root; do not hardcode
  `~/d/science`.
- Apply the new policy to future ingest by default. Do not rewrite already-stored
  prose-source entities unless a concrete consumer break requires a migration.

The P2 prose-source resolver should own this policy for `source_path`. P4 should continue
using manifest paths as display-authoritative, but it should not have to repair absolute
paths emitted by earlier framework stages.

### 4.4 Graph revision metadata ignores

Problem: generated health/report files can appear in graph revision metadata when they sit
under a directory treated as graph input. The observed natural-systems pilot case was
`doc/reports/health-report.json`: `graph.io.build_input_manifest()` includes `doc/`
recursively, so a generated report under `doc/reports/` enters the graph revision manifest
even though it is not a semantic graph input. The pilot wrapper filtered that one file
after graph build.

This is general graph-input hygiene, not a prose-specific semantic rule. Any generated
file under an included graph-input directory can pollute revision metadata. The prose pilot
made the issue visible because `doc/reports/health-report.json` is a generated health
output under the recursively included `doc/` tree.

Design:

- Fix the actual inclusion path first: generated report outputs under graph input
  directories should be excluded from revision metadata or moved out of the input set.
- If exclusion is the right mechanism, teach graph build revision metadata to respect
  project ignore rules or an explicit science config ignore list.
- At minimum, allow a project to exclude known generated paths such as:

```text
doc/reports/health-report.json
```

This should affect graph revision metadata only. It must not hide unresolved entity refs,
invalid source refs, or materialization errors.

### 4.5 Operational annotation refs in health

Problem: prose promotion and decomposition artifacts introduce operational provenance refs.
Some generic health output during the pilot appeared to overlap with the more precise P3/P4
`unbacked` signal.

The obvious `annotation:` source-ref path is already handled: `graph.migrate._audit_reference`
returns no finding for `source_refs` beginning with `annotation:`, and materialization maps
them to stable annotation URIs. Therefore this section must not add broad classification
machinery for a path that is already silent.

The leading hypothesis is narrower: the exemption is scoped to `field_name == "source_refs"`.
If a prose annotation ref appears in another audited field, such as `evidence_refs` or a
typed relation, it can still surface as an unresolved reference. The investigation should
confirm whether the pilot warning came from one of those non-`source_refs` fields before
changing health behavior.

Design:

- Before implementation, pin the exact warning string and emitting call site observed in
  the pilot.
- If the warning is a valid operational prose ref being treated as an evidence defect,
  classify that specific field/ref shape explicitly in graph health.
- Keep unresolved or malformed refs as hard findings.
- When a prose-promoted proposition has no eligible evidence, prefer the P3/P4 `unbacked`
  row as the actionable finding rather than adding a second generic warning.

The goal is not to suppress epistemic absence. The goal is to report absence once, at the
right layer.

## 5. Validation vehicle: offline-agent decomposition artifact pilot

Problem: the first pilot used deterministic reviewed fixtures. That was the right way to
validate the pipe, but it did not test whether an offline agent can produce useful
candidate/skip artifacts from real prose.

Design:

- Run a second, narrow pilot using one genuine offline-agent artifact for one existing
  natural-systems manifest source.
- Do not add live model execution to `science`.
- Commit the offline artifact as input, then run the normal P2/P3/P4 loop.
- Compare agent output against the reviewed deterministic fixture or a manually reviewed
  gold artifact.

Recommended source:

```text
prose-source:universality-classes-two-faces
```

Reason: it mixes domain claims, conceptual framing, and meta commentary, so it exercises
candidate/skip discrimination better than a purely mechanical page.

Pilot acceptance criteria:

- artifact parses under P2 schema version 1
- every unit uses the canonical P2 skip vocabulary or `StatementCandidate` payload
- candidate locators resolve with the exact P2 resolver
- every non-promoted span has a reason-coded skip or is deliberately outside the reviewed
  range
- reviewer can identify false candidates, missed domain claims, and wrong skip reasons
- P4 can report the resulting backlog without schema changes

Output should include a short review report with counts:

- candidate units
- skip units by reason code
- unresolved or ambiguous locators
- false-positive candidates
- missed domain claims
- promoted units
- unbacked promoted units

The purpose is to validate the prompt and artifact contract, not to maximize coverage.

## 6. Data and API contracts

### 6.1 Public validation result

Locator preflight should return a stable unit-level result shape:

```json
{
  "source_ref": "prose-source:example",
  "artifact_id": "decomp-...",
  "summary": {
    "units": 10,
    "resolved": 9,
    "unresolved": 1,
    "ambiguous": 0,
    "hard_failures": 0
  },
  "units": [
    {
      "unit_id": "u001",
      "fingerprint": "sha256:...",
      "disposition": "candidate",
      "status": "resolved",
      "heading_path": ["Section"],
      "message": ""
    }
  ]
}
```

This must reuse the existing check row vocabulary. The important contract is that
downstream artifact writers can depend on it instead of duplicating resolver logic.

### 6.2 Batch promotion plan

Batch promotion plans are generated artifacts, not hand-authored schemas. They should
record enough state to make apply deterministic and fail early if the source changed.

Required identity fields:

- `source_ref`
- `decomposition_artifact_id`
- `unit_id`
- `fingerprint`
- planned decision (`mint` or `link`)
- target ref for links

The plan must not carry a second candidate payload or copied claim text. The latest P2
artifact remains the source of candidate truth. Deliberately not promoting a candidate is
represented by omitting it from the plan, not by a record-only `skip` row. Artifact units
whose P2 disposition is `skip` remain invalid promotion-plan inputs.

### 6.3 Offline-agent review report

The offline-agent pilot should produce a small Markdown report in the downstream project,
not a new framework artifact. A good location for natural-systems is:

```text
doc/reports/prose-epistemics-agent-artifact-pilot.md
```

The report should link the input artifact, P2 check output, P4 health artifact, and any
manual review notes.

## 7. Error handling

- Validation commands fail early for schema errors, unknown skip codes, invalid source
  refs, and source hash mismatches.
- Locator resolution returns per-unit findings for unresolved or ambiguous locators when
  the artifact is otherwise parseable.
- Batch apply refuses to proceed on stale plans rather than silently re-planning.
- Path normalization should be deterministic. Manifest-backed durable prose-source paths
  should be project-relative. Any out-of-project path handling applies only to
  non-manifest display fields; if such a path would enter durable artifact data, fail with
  a clear message.
- Health changes must not hide missing evidence; they should route it to P3/P4 `unbacked`
  rows.

## 8. Testing

Framework tests should cover:

- pre-ingest validation uses the same resolver behavior as `check-prose-decomposition`,
  including section-body boundaries and exact context uniqueness
- pre-ingest validation and `check-prose-decomposition` produce identical per-unit findings
  for the same artifact once that artifact is ingested
- duplicate heading paths produce ambiguous locator findings
- unknown skip reason codes hard-fail
- source hash mismatch behavior matches ingest
- batch planning produces the same mint/link/skip decisions as single-unit dry runs
- batch apply appends the same source refs and promotion state as repeated single-unit
  applies
- stale batch plans fail when the latest decomposition artifact changes
- prose-source paths are stored project-relative for in-project Markdown
- graph revision metadata excludes configured generated paths without hiding materialize
  failures
- valid prose annotation refs do not produce generic evidence-line warnings

Downstream pilot tests should cover:

- one real offline-agent artifact can pass framework validation after review
- P2/P3/P4 artifacts build without TypeScript recomputing epistemic logic
- the review report distinguishes pipe failures from decomposition-quality failures

## 9. Sequencing

Recommended order:

1. Add the reusable locator preflight API and CLI.
2. Run the offline-agent artifact pilot using that preflight surface.
3. Add path canonicalization in prose-source resolution.
4. Add graph revision metadata ignores.
5. Investigate the pinned operational-ref warning; classify only if a genuine defect
   remains.
6. Add batch promotion planning/apply once the second pilot confirms promotion volume is
   the main operator bottleneck.

The offline-agent pilot should happen before batch promotion work. If decomposition quality
is poor, better batch ergonomics only make it easier to promote bad units.

## 10. Alternatives considered

### Keep all fixes downstream

Rejected. The pilot already showed downstream code had to mirror private framework
semantics. That is brittle and will drift as soon as P2 locator behavior changes.

### Add a full prose pipeline orchestrator now

Rejected for now. A single `science annotate run-prose-pipeline` command may be useful
later, but the immediate friction is at narrower seams: validation, path normalization,
health classification, and promotion ergonomics. Keeping operations separate preserves
auditability while the artifact contract is still young.

### Add live agent generation to science

Rejected. The framework contract is offline-agent artifact ingest. The next pilot should
test a real agent artifact, but generation orchestration belongs outside `science` until a
clear multi-project need appears.

## 11. Open decisions for the implementation plan

- Exact CLI names for preflight and batch promotion commands.
- Whether generated reports under graph input directories should move, be excluded through
  `science.yaml`, follow `.gitignore`, or use an explicit graph-build flag.
- Whether a later migration is needed for already-stored prose-source paths after the
  future-ingest policy has shipped.
- The exact offline-agent prompt and reviewed range for the one-source artifact pilot.
- Whether batch promotion should support a reviewed unit-selection file before planning, or
  require operators to plan all current unpromoted candidates and then apply only accepted
  identity rows from that generated plan.

## 12. Success criteria

This follow-up is successful when:

- downstream projects no longer implement their own Markdown locator resolver checks
- a real offline-agent artifact can be reviewed through framework preflight before ingest
- project-root paths in prose-source metadata and health artifacts are stable and portable
- graph health does not duplicate P4's `unbacked` signal with generic annotation-ref noise
- promotion of reviewed multi-unit artifacts is ergonomic without losing per-unit audit
  state
