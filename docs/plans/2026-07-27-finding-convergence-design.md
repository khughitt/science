# Finding Convergence — Design

> **Status:** design. **Spec 1 of three** in the autonomous-audit program, and a
> prerequisite for the autonomy envelope's S5 harness slice. **Spec 1 ships no agent**
> and adds no autonomy: it converges the deterministic audit surface onto one emitted
> contract so that Spec 2 (unattended lens agents) consumes a type already exercised
> across the full deterministic variety, rather than becoming the experiment that
> discovers the type is incomplete.
>
> Spec 2 (unattended harness, Pi actor + supervisor, lens agents emitting findings at
> `report-only` tier) and Spec 3 (second-pass validation, confirmation counts,
> promotion to task) are out of scope here and consume this contract.

## Motivation

A dozen spellings of "the audit found something" exist today, and none of them are
shared: eight check-specific `*Finding` TypedDicts, two entirely untyped `list[dict]`
streams, `data_audit`'s own `Violation` and `AuditNote`, and several row types that are
issue rows without the name (`UnresolvedRef`, `UnregisteredRefKind`,
`LingeringTagsRecord`). Each is drained into a different key of a 20-key heterogeneous
`HealthReport`, counted by bespoke logic, and rendered by code that hardcodes rule
strings.

That debt is owed independent of any agent. But it becomes disqualifying the moment an
unattended agent is a producer: an agentic lens emitting an eleventh dialect cannot be
deduplicated against a deterministic check that already found the same thing, cannot be
suppressed by the same mechanism, and cannot be compared against the checks at all —
which forecloses the one measurement that makes agentic auditing worth doing, *did the
agent find something a deterministic check should have caught*.

Prose is the other half of the problem. The existing curation sweep writes a narrative
ledger and re-reads the previous one to extract carry-overs, which is a prose-parsing
workaround for the absence of durable identity. Structured findings retire it.

## The ruling

> **Spec 1 converges every deterministic issue emitter onto `Finding`. It does not
> converge every diagnostic value: measurements remain metrics, and inability to run
> remains instrument state.**
>
> - Findings say: *the audit found something.*
> - Metrics say: *the audit measured something.*
> - `unwired` says: *the audit could not look.*

This is not new doctrine. `UnwiredCheck` already states the third partition in its own
docstring (`graph/health.py:57`):

> This is deliberately NOT folded into `total_issues`. An unwired check is not a
> finding about the project — it is a HOLE IN THE DIAGNOSTIC, and burying it in a
> count would re-hide exactly what it exists to expose.

Spec 1 generalizes that distinction to the whole surface, rather than inventing one.

And the complementary ruling on ontology:

> A curation finding is a typed project-state case about repository or corpus hygiene.
> It is neither knowledge nor work authorization. It never materializes into the
> knowledge graph, affects belief, enters attention, or authorizes a task. Untrusted
> producers may propose findings only through a gated report; trusted ingestion owns
> identity, deduplication, lifecycle, and promotion.

## Grounding findings that shape the design

Verified against the tree at `8db7aad9`.

- **`InstrumentResult` is already generic.** `class InstrumentResult(BaseModel, Generic[RowT])`
  (`instruments.py:73`), so `InstrumentResult[Finding]` is well-formed and the uniform
  channel needs no new machinery.

- **A partial migration is already in flight, and its tolerance branch is why it
  stalled.** `_drain_instrument_results` (`graph/health.py:108`) unpacks
  `InstrumentResult`s and diverts unwired ones, but documents that *"Checks that do not
  (yet) return an `InstrumentResult` pass through untouched."* The drain accepting both
  shapes is precisely why ten dialects coexist. Converging without removing that branch
  reproduces the same half-migration.

- **The public schema is one heterogeneous TypedDict.** `HealthReport`
  (`graph/health.py:89`) has twenty keys of five different shapes: typed finding lists,
  untyped `list[dict]`, nested report objects, a bare `dict[str, object]`, a count, and
  the unwired channel.

- **The two hardest producers are untyped.** `dataset_anomalies: list[dict]` and
  `managed_artifacts: list[dict]` carry no schema at all. They exert more design
  pressure on the payload than the eight TypedDicts do.

- **Rule strings are built dynamically and duplicated in the renderer.**
  `validate/checks/prose_lints.py:197,226` construct `f"prose_lints.{check}"`, and
  `validate/cli.py:25` hardcodes `_VISIBLE_INFO_RULES = frozenset({"prose_lints.config"})`.
  A wildcard rule family cannot be ratcheted, and a literal rule string in a renderer is
  a second place the vocabulary drifts.

- **`prose_lints.numeric-verification.coverage` (`prose_lints.py:181`) is a metric, not
  a finding** — a clean instance of the partition this design draws.

- **Acceptance is keyed on prose, positionally stored.** `accepted_validation_entries`
  (`validate/acceptance.py:26`) returns `list[dict[str, Any]]` from `science.yaml`, and
  matching is `rule` + `severity` + `message_contains` substring. Rewording a message
  silently changes what is suppressed, and no entry has a stable key.

- **`finding` is a live core EntityKind.** `EntityKind.FINDING` (`entities.py:116`) is in
  `CORE_PROFILE` with `home="entities/findings"` and `canonical_prefix="finding"`
  (`profiles/core.py:149-157`), and participates in edge definitions
  (`source_kinds=["finding"]`, "a finding is grounded by a data package or workflow
  run"). Reusing the name for audit cases would be a semantic collision with an
  epistemic kind.

- **Any directory named `findings/` infers that kind, anywhere in the tree.**
  `_DIR_TO_KIND["findings"] = "finding"` (`frontmatter.py:370`) is consumed by
  `_infer_kind_from_path` (`:377`), which keys on `path.parent.name` with **no root
  anchoring**, at `:496` — reached exactly when a file has no `kind:` and no inferable
  `id:`, which is this design's frontmatter by construction. `doc/findings/` and
  `doc/audits/findings/` are both unusable.

- **The path gate already denies unclassified paths.** `entity_kind_for_path`
  (`autonomy/changes.py:71`) matches `candidate.parent == root` against exact
  `_CORE_HOMES`; its docstring says `None` means *"unclassified, which the gate reads as
  denied."* Canonical cases under `doc/audits/cases/` are therefore denied to an
  autonomous actor **today, with no gate change** — which is what makes trusted
  ingestion the correct shape rather than a workaround.

- **Transient project-state records already have a staleness scar.**
  `DEFAULT_REVISION_MANIFEST_EXCLUDES` (`graph/io.py:428`) ships `doc/curations/*.md`
  because ledgers were hashed into the revision manifest, so *"editing one flipped the
  graph to stale… the natural workflow guaranteed a dirty graph every sweep"*
  (fb-2026-07-17-001). Findings have the identical property at higher volume.

- **Producer completeness is already guarded.** `tests/test_check_registry_is_complete.py`
  establishes the filesystem-versus-registration invariant. Spec 1 adds *result* and
  *rule* completeness on top of it; it does not reinvent producer completeness.

- **Never act on stale derived state.** Plan D ruling #3 of the autonomy envelope:
  `finish` re-materializes before capturing because *"`graph.trig` is derived and
  actor-controlled; without this, a run that edited entities and never rebuilt would be
  judged against a stale graph and pass."* §7 below inherits this rule rather than
  inventing it.

## Design

### 1. `Finding` — the shared emitted payload

An immutable payload emitted identically by deterministic checks, validation modules,
`data_audit`, and (in Spec 2) agentic lenses. It is what a producer *says*; it is not
what is stored.

| Field | Meaning |
|---|---|
| `rule` | The `FindingRule` this instance realizes. Never a free string. |
| `subject` | Exactly one discriminated subject (§2). |
| `severity` | Must be a member of the rule's declared `severities`. |
| `qualifiers` | Typed, rule-specific, stable. Validated against the rule's `qualifier_schema`. |
| `message` | Human-readable. **Never** identity-bearing. |
| `evidence` | Supporting paths, excerpts, and prose. Never identity-bearing. |

`message` and `evidence` are deliberately excluded from identity so that rewording a
diagnostic does not fork a case — the defect that makes `message_contains` acceptance
fragile today.

### 2. `FindingSubject` — one required, discriminated primary subject

```python
FindingSubject = EntitySubject | PathSubject | IdentifierSubject | ProjectSubject
```

- **`EntitySubject(type="entity", ref="dataset:gtex-v8")`** — a known canonical entity,
  including tasks. Resolution is validated.
- **`PathSubject(type="path", path=..., pointer=...)`** — files, missing expected files,
  and malformed entities that cannot supply a valid ref. Paths are normalized
  project-relative POSIX. A `pointer` may name a stable semantic key or logical
  location; **positional segments and line numbers are forbidden in identity** and are
  occurrence metadata only.
- **`IdentifierSubject(type="identifier", namespace=..., value=...)`** — non-entity named
  objects: managed artifacts, dangling references, unregistered reference kinds,
  acceptance entries. Namespaces are registered vocabulary (§6), never
  producer-invented.
- **`ProjectSubject(type="project")`** — genuinely project-wide conditions, such as an
  unusable validation context. The rule and qualifiers distinguish multiple
  project-level findings.

**There is no entity-then-path fallback.** Producers choose a variant explicitly; an
invalid entity subject *fails* rather than silently degrading to a path, which would
change the case's identity without anyone noticing.

**One primary subject is sufficient.** Everything else has a home that does not perturb
identity: source files mentioning one unresolved reference are *occurrence locations*;
the counterpart in a broken dataset relation is a *stable qualifier*; cross-paper
annotations qualify a sidecar subject; additional prose and paths are *evidence*. This
is what prevents a case's identity from changing merely because another occurrence or
supporting location was later discovered.

### 3. Identity — a deterministic fingerprint

The fingerprint is computed over **rule id, subject, and the rule's declared stable
qualifiers** — and nothing else. Explicitly excluded: date, model, lens, run id, prose,
message, severity, evidence, line numbers, and list positions.

Two consequences that motivate the whole design:

- A deterministic check and an agentic lens that find the same thing produce the **same
  fingerprint**, and therefore the same record. Cross-producer dedup is the point.
- Re-detection appends an occurrence to an existing record rather than creating a new
  one. **Dedup is enforced by the loader/writer, not by convention.**

### 4. `FindingRecord` — the canonical stored case

`FindingRecord` wraps an immutable `Finding` payload with the mutable history the
payload must not carry:

| Field | Meaning |
|---|---|
| `finding_id` | The deterministic fingerprint (§3). |
| `payload` | The `Finding` as first emitted. |
| `occurrences` | Append-only provenance: producer, run ref, timestamp, locations, severity observed. |
| `reviews` | Distinct eligible reviews, each retaining its note. |
| `status` | `proposed` \| `confirmed` \| `dismissed` \| `promoted`. |
| `promoted_task` | Optional task reference. Set only by explicit promotion. |

**Confirmation counts are derived from distinct eligible reviews and retain their
notes. They are never a confidence, never aggregated, never a belief input.** Review
eligibility and the promotion gate are Spec 3's subject; Spec 1 defines only the
storage shape so Spec 3 does not reopen the schema.

A standing caution for Spec 3, recorded here because it constrains the schema: *N
reviewers drawn from the same model family are strongly correlated.* Lens diversity
buys far more independence than sample count, and the `explore-ideas` blind per-lens
dispatch is the precedent to copy.

### 5. Storage and placement

Canonical cases are typed project-state documents at:

```
doc/audits/cases/<fingerprint-prefix>-<rule-slug>.md
```

with frontmatter carrying `doc_kind: finding-record` and `finding_id: …`, and **never**
an entity `kind:` or `id:`. Prose in the body is supporting context only.

Three placement constraints, each with a verified cause:

1. **Not `entities/`, not an EntityKind.** `finding` is taken by a live epistemic kind
   (§Grounding). Cases are project-state, not knowledge.
2. **Not any directory named `findings/`.** `_infer_kind_from_path` keys on
   `path.parent.name` with no root anchoring, so `doc/audits/findings/` would infer the
   epistemic kind. `cases/` is not in `_DIR_TO_KIND`.
3. **`doc/audits/cases/*.md` is added to `DEFAULT_REVISION_MANIFEST_EXCLUDES`**
   (`graph/io.py:428`), not to per-project config. Without it, every ingestion flips the
   graph to stale — the exact fb-2026-07-17-001 failure, at higher volume. The existing
   comment there warns the split is deliberately not directory-aligned; this entry is an
   explicit glob for the same reason.

Cases never materialize into `graph/knowledge`, never become belief bearers, freshness
subjects, or attention candidates. That placement is load-bearing for the same reason it
was for run records: at sweep cadence they would otherwise become one of the largest
node populations in the graph and skew the very attention rankings curation depends on
(`graph/attention.py`).

### 6. Rules — declared beside the producer, registry derived

Rules are declared next to the code that emits them, and **one frozen registry is
derived from those declarations**. There is no hand-maintained central list, and
therefore no repeated ID string to drift — while ingestion still gets exactly one
immutable lookup authority.

```python
FindingRule(
    id="dataset.cached-field-drift",
    severities={"warning"},
    subject_types={"entity"},
    identifier_namespaces=set(),
    qualifier_schema=DatasetFieldQualifier,
    remediation="producer",
)
```

- **`severities` is a permitted set, not a single default.** Existing rules legitimately
  vary by context.
- **Dynamic rule strings are retired.** `prose_lints.<check>` becomes a declared
  `prose-lints.hit` rule with `check` as a typed stable qualifier. A wildcard family
  cannot be ratcheted, and defeats the registry.
- Producers export their declarations and construct findings from those objects. A
  **generic producer registration** — not `HealthCheck` specifically — contributes them
  to the frozen registry, so health checks, validation modules, `data_audit`, and later
  Pi lenses all participate without making health the ontology owner.
- `HealthCheck` may reference its declared rules for enforcement but does not own their
  definitions. The `validate` health check aggregates declarations from the canonical
  validation producers it wraps.

The derived registry **fails early** on:

1. Duplicate rule IDs.
2. An emitted finding naming an undeclared rule.
3. A finding whose severity, subject type, namespace, or qualifiers violate its rule.
4. A rule declaring producer remediation without a registered trusted handler.
5. A registered producer returning anything except the uniform result channel.
6. Project configuration attempting to add or override a toolkit rule.

The existing filesystem-versus-registration guard
(`tests/test_check_registry_is_complete.py`) establishes *producer* completeness; this
runtime ratchet establishes *result and rule* completeness. Between them, no list of
migrated modules and no tolerance branch remains.

### 7. Remediation — capability, not instruction

> `Finding` carries no executable fix command and no authoritative proposed mutation.
> The rule registry may declare a trusted remediator. Acting on a finding re-runs that
> producer against current state and recomputes the plan.

`data_audit` therefore keeps `Violation.proposed_target` **internally**, while a stored
case never authorizes a stale move. Agent-authored repair suggestions are notes only.
Spec 3 queries the rule's capability without reopening the finding schema.

This inherits Plan D ruling #3 of the autonomy envelope rather than inventing a rule:
both prohibit acting on stale derived state.

### 8. Trusted ingestion — why Layer 1 is unchanged

```
producer (check | validation | data_audit | Spec 2 lens)
    ↓ emits shared Finding
one gated report path                     ← the only surface an untrusted actor writes
    ↓ trusted ingestion (validate, fingerprint, upsert)
canonical FindingRecord under doc/audits/cases/
    ↓ explicit promotion (Spec 3 or human)
task
```

The actor never writes canonical cases. It writes its one supervisor-supplied report
path — the surface `report-only` already allows. After the run passes the gate, trusted
ingestion validates the payloads and upserts records.

This is what makes *"Layer 1 works unchanged"* literally true rather than aspirational:
`entity_kind_for_path` already returns `None` for `doc/audits/cases/…`, and the gate
already reads `None` as denied. Nothing in `autonomy/policy.py` is edited, and no
allowlist widens.

`science health` stays **read-only by default**. Convergence does not persist every
diagnostic run; trusted ingestion writes cases only when explicitly requested.

### 9. Converging the deterministic emitters

In scope — every deterministic *issue* emitter:

- Retire the eight check-specific `*Finding` TypedDicts.
- Type and convert the two untyped streams, `dataset_anomalies` and `managed_artifacts`.
- Convert synthesized findings such as `schema_invalid`.
- Convert `Violation` and warning-bearing `AuditNote` at the **data-audit output
  boundary**. Domain objects the fixer needs remain internal; they no longer define the
  emitted contract.
- Registered producers return a typed result with a uniform
  `findings: InstrumentResult[Finding]` channel plus optional producer-specific metrics.

Out of scope — measurements stay metrics:

- cross-paper summaries, prose coverage, layered-claim coverage, archive-lag counts,
  and `prose_lints.numeric-verification.coverage`.

Never converted:

- `UnwiredCheck`. Inability to run is instrument state, not a finding.

### 10. Acceptance migration

Acceptance is re-keyed from `message_contains` prose onto fingerprints. `Spec 1` ships
`science findings migrate-acceptances`, **dry-run by default** with `--apply`. It runs
current producers and:

| Outcome | Action |
|---|---|
| Exactly one current finding matches | Rewrite the acceptance to that fingerprint. |
| No finding matches | Emit `accepted-validation.stale`. |
| More than one matches | Emit `accepted-validation.ambiguous`. |

**Neither failure case suppresses anything.** An acceptance that matches nothing becomes
a finding in its own right rather than a silent no-op — the fail-loud direction required
by the standing rule that evidence and metadata are never tuned to silence a check.

Because unambiguous entries are rewritten mechanically, downstream projects do not flood
on upgrade; only genuinely unresolvable entries surface for human resolution.

An acceptance entry's subject is
`IdentifierSubject(namespace="accepted-validation", value=<content-derived-key>)` — not a
`PathSubject` pointer into `health.accepted_validation`, which is a bare positional YAML
list (`validate/acceptance.py:26`) whose indices move when any earlier entry is deleted.

### 11. Public output transition

Counting, severity filtering, projection, rendering, and JSON output are rewritten
around the uniform finding stream. **The public schema changes once**; no compatibility
adapter preserves the heterogeneous report. Rule strings move out of renderers
(`validate/cli.py:25`) and are read from the derived registry.

`total_issues` is re-derived from the finding stream, and the unwired channel remains
outside it.

## Testing

1. **Uniform-channel ratchet** — a registered producer returning anything but the
   uniform result channel fails. The `_drain_instrument_results` non-`InstrumentResult`
   passthrough is removed, not merely deprecated.
2. **Rule-completeness ratchet** — an emitted finding naming an undeclared rule fails;
   a duplicate rule id fails; a rule declaring producer remediation with no registered
   handler fails.
3. **Constraint validation** — a finding whose severity, subject type, identifier
   namespace, or qualifiers violate its rule fails.
4. **Project config cannot add or override a toolkit rule.**
5. **Renderer clean-refusal** — a direct renderer test proving a non-empty unwired
   channel forbids "Project is clean". Asserted on rendered output, not on a boolean;
   the invariant lives in the layer being rewritten, and this is the guard-in-one-reader
   failure shape.
6. **Identity stability** — rewording a `message`, adding an occurrence, adding
   evidence, or changing a line number does not change a fingerprint. Deleting an
   earlier `accepted_validation` entry does not change any fingerprint.
7. **Cross-producer dedup** — a deterministic check and a synthetic second producer
   reporting the same rule + subject + qualifiers upsert **one** record with two
   occurrences.
8. **Subject discrimination is total and strict** — an invalid entity ref fails rather
   than degrading to a path subject.
9. **Layer 1 unchanged** — a write to `doc/audits/cases/…` in an autonomous commit range
   is denied by the existing path gate, with no edit to `autonomy/policy.py`.
10. **Graph isolation** — no finding triple appears in any named graph; cases are absent
    from attention candidates; ingesting cases does not stale the graph revision
    manifest.
11. **Acceptance migration** — the three outcomes, and the invariant that neither
    failure case suppresses anything.
12. **Metrics are not findings** — coverage, counts, and nested summaries survive the
    transition as metrics and are absent from the finding stream.

## Out of scope

- Any agent, lens, harness, or unattended execution (Spec 2).
- Review eligibility rules, the confirmation threshold, and promotion authority
  (Spec 3). Spec 1 defines only the storage shape these will use.
- Converting metrics or coverage holes into findings. Doing so would make the shared
  type broad enough to mean nothing.
- Retiring `doc/curations/` ledgers. The curation sweep's narrative output is a Spec 2
  question; Spec 1 only removes the reason it needs prose carry-over parsing.

## Open questions

- Whether `science health` gains a persist flag or ingestion is always a separate
  command. Spec 1 requires only that the default stays read-only.
- Whether `dismissed` cases are retained indefinitely or archived on a cadence, and
  whether a dismissed fingerprint re-detected later reopens or stays dismissed with a
  new occurrence.
- Whether external projects need a migration beyond `migrate-acceptances`. How many
  repositories carry `accepted_validation` entries has not been surveyed; `meta/` does,
  and the count elsewhere should be established before the plan is written.
