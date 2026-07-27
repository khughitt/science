# Finding Convergence — Design

> **Status:** design, revision 2. **Spec 1 of three** in the autonomous-audit program,
> and a prerequisite for the autonomy envelope's S5 harness slice. **Spec 1 ships no
> agent** and adds no autonomy: it converges the deterministic audit surface onto one
> emitted contract so that Spec 2 (unattended lens agents) consumes a type already
> exercised across the full deterministic variety, rather than becoming the experiment
> that discovers the type is incomplete.
>
> Spec 2 (unattended harness, Pi actor + supervisor, lens agents emitting findings at
> `report-only` tier) and Spec 3 (second-pass validation, confirmation counts,
> promotion to task) are out of scope here and consume this contract.
>
> **Revision 2** closed seven contract gaps found in review of revision 1: arrival-order
> dependence in `FindingRecord` (§4), an unserializable `rule` field and an unfrozen
> fingerprint (§1, §3), the missing producer enumeration (§9), an incomplete acceptance
> migration contract (§10), an unspecified output schema (§11), an overbroad
> producer-completeness claim (§Grounding, §6), and a lifecycle left open (§4, §8).
>
> **Revision 3** closes the consequences of making those contracts concrete: report
> provenance (§11), non-identity qualifiers on occurrences (§4), the transition graph and
> review record (§4), `--apply` abort semantics (§10), a transaction mechanism that
> matches its guarantee (§8), section ordering (§6, §11), the `dataset.anomaly.*`
> enumeration (§9), fingerprint type constraints and filename validation (§3), and two
> internal contradictions (§Out of scope, §Open questions).

## Motivation

At least a dozen spellings of "the audit found something" exist today, and none of them
are shared: eight check-specific `*Finding` TypedDicts, two entirely untyped `list[dict]`
streams, `data_audit`'s own `Violation` and `AuditNote`, and further row types that are
issue rows without the name (`UnresolvedRef`, `UnregisteredRefKind`,
`LingeringTagsRecord`). Each is drained into a different key of a 21-key heterogeneous
`HealthReport`, counted by bespoke logic in `count_issues`, and rendered by code that
hardcodes rule strings.

That debt is owed independent of any agent. But it becomes disqualifying the moment an
unattended agent is a producer: an agentic lens emitting one more dialect cannot be
deduplicated against a deterministic check that already found the same thing, cannot be
suppressed by the same mechanism, and cannot be compared against the checks at all —
which forecloses the one measurement that makes agentic auditing worth doing, *did the
agent find something a deterministic check should have caught*.

Prose is the other half of the problem. The existing curation sweep writes a narrative
ledger and re-reads the previous one to extract carry-overs, which is a prose-parsing
workaround for the absence of durable identity. Structured findings retire it.

## The rulings

> **R1 — Scope.** Spec 1 converges every deterministic issue emitter onto `Finding`. It
> does not converge every diagnostic value: measurements remain metrics, and inability
> to run remains instrument state.
>
> - Findings say: *the audit found something.*
> - Metrics say: *the audit measured something.*
> - `unwired` says: *the audit could not look.*

R1 is not new doctrine. `UnwiredCheck` already states the third partition in its own
docstring (`graph/health.py:57`):

> This is deliberately NOT folded into `total_issues`. An unwired check is not a
> finding about the project — it is a HOLE IN THE DIAGNOSTIC, and burying it in a
> count would re-hide exactly what it exists to expose.

Spec 1 generalizes that distinction to the whole surface rather than inventing one.

> **R2 — Ontology.** A curation finding is a typed project-state case about repository
> or corpus hygiene. It is neither knowledge nor work authorization. It never
> materializes into the knowledge graph, affects belief, enters attention, or authorizes
> a task. Untrusted producers may propose findings only through a gated report; trusted
> ingestion owns identity, deduplication, lifecycle, and promotion.

> **R3 — Counting.** A measurement never contributes to an issue count by virtue of its
> value. Where current behaviour derives an issue from a metric, the producer emits an
> explicit **policy-violation finding** alongside the retained measurement. Every
> resulting change to observable counts is enumerated in §9 and approved there, never
> absorbed silently.

R3 exists because R1 as stated in revision 1 contradicted the tree: `count_issues`
currently derives issues from coverage metrics and from archive lag (§Grounding).

## Grounding findings that shape the design

Verified against the tree at `8db7aad9`.

- **`InstrumentResult` is already generic.** `class InstrumentResult(BaseModel, Generic[RowT])`
  (`instruments.py:73`), so `InstrumentResult[Finding]` is well-formed and the uniform
  channel needs no new machinery.

- **A partial migration is already in flight, and its tolerance branch is why it
  stalled.** `_drain_instrument_results` (`graph/health.py:108`) unpacks
  `InstrumentResult`s and diverts unwired ones, but documents that *"Checks that do not
  (yet) return an `InstrumentResult` pass through untouched."* The drain accepting both
  shapes is precisely why the dialects coexist. Converging without removing that branch
  reproduces the same half-migration.

- **The public schema is one heterogeneous TypedDict.** `HealthReport`
  (`graph/health.py:89`) has twenty-one keys of five different shapes: typed finding
  lists, untyped `list[dict]`, nested report objects, a bare `dict[str, object]`, a
  count, and the unwired channel.

- **`count_issues` is not a row count, and it derives issues from measurements.**
  Its own docstring (`graph/health_count.py:126`) says so: *"``managed_artifacts`` uses
  ``counts_as_issue``, coverage gaps are derived from metrics, and non-zero archive lag
  contributes one issue."* Concretely, `_count_layered_claim_issues` adds `issues += 1`
  for each of `proposition_claim_layer_coverage` and
  `causal_leaning_identification_coverage` whose `denominator > 0 and numerator <
  denominator`, and the total adds `(1 if lag_total else 0)`.

- **Two producers emit rows that count as zero, and it is an omission.**
  `legacy_task_type` and `invalid_entity_aspects` appear in `count_issues`'s
  `row_sections` — so their shape is strictly validated — but are **absent from the
  return expression**, alongside the two deliberate exclusions (`accepted_validation`,
  `unwired_checks`). Both producers return `InstrumentResult[…Finding]`
  (`legacy_task_type.py:18`, `invalid_entity_aspects.py:18`): they emit findings, not
  informational measurements. There is no third exclusion class; §9 counts them.

- **`unresolved_refs` already groups by target.** `collect_unresolved_refs`
  (`unresolved_refs.py:70`) builds `by_target` and emits one `UnresolvedRef` row per
  unresolved reference, carrying `mention_count` and a sorted `sources` list. Moving
  citing files to occurrence evidence is therefore a representation change with **no
  count effect**.

- **A declared code table has already drifted from what is emitted.**
  `dataset_anomalies.py` emits twelve distinct codes but `DATASET_ANOMALY_CODES` (`:13`)
  declares eleven — `dataset_access_invalid` (`:197`) is emitted, is asserted by
  `tests/test_health.py:1868`, and is undeclared. The guard at `test_health.py:1804` is
  `expected.issubset(set(DATASET_ANOMALY_CODES))`, a subset assertion that by
  construction cannot catch an emitted-but-undeclared code. This is registry failure
  condition #2 of §6 occurring in the tree today, and it is the concrete argument for
  deriving the registry from declarations that producers must construct findings *from*.

- **Four streams are genuinely mixed and must be split, not classified wholesale.**
  `layered_claims` carries two finding lists (`migration_issues`,
  `rival_model_packets_missing_discriminating_predictions`) *and* two coverage metrics;
  `prose_epistemics` and `cross_paper_evidence` each carry a `findings` sub-key beside
  measurements; `managed_artifacts` rows carry a per-row `counts_as_issue` flag.

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

- **Producer completeness is guarded for two namespaces, by two different tests, and not
  at all for the rest.** `tests/test_check_registry_is_complete.py` compares
  `validate/checks/*.py` against `CANONICAL_CHECK_MODULES`;
  `tests/test_health_checks_package.py:34,95` globs the health-check directory and
  asserts agreement with `HEALTH_CHECKS`. Neither covers `data_audit`, and neither
  covers the generic producer registry §6 introduces. `HEALTH_CHECKS` itself is
  explicitly hand-ordered — *"assembled by explicit import below — never by filesystem
  discovery, which would make check order implicit"* — so its order is observable and
  must be preserved as presentation metadata rather than as import order (§6, §11).

- **The guard's own docstring states the rule this design must obey.**
  `test_check_registry_is_complete.py`: *"a guard that enumerates its own scope has a
  hole by construction, which is the very hole it would be closing."*

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
  autonomous actor **today, with no gate change**.

- **Transient project-state records already have a staleness scar.**
  `DEFAULT_REVISION_MANIFEST_EXCLUDES` (`graph/io.py:428`) ships `doc/curations/*.md`
  because ledgers were hashed into the revision manifest, so *"editing one flipped the
  graph to stale… the natural workflow guaranteed a dirty graph every sweep"*
  (fb-2026-07-17-001). Findings have the identical property at higher volume.

- **Never act on stale derived state.** Plan D ruling #3 of the autonomy envelope:
  `finish` re-materializes before capturing because *"`graph.trig` is derived and
  actor-controlled; without this, a run that edited entities and never rebuilt would be
  judged against a stale graph and pass."* §7 inherits this rule rather than inventing
  it.

## Design

### 1. `Finding` — the shared emitted payload

An immutable payload emitted identically by deterministic checks, validation modules,
`data_audit`, and (in Spec 2) agentic lenses. It is what a producer *says* on one
observation; it is not what is stored.

| Field | Serialized as | Meaning |
|---|---|---|
| `rule_id` | `str` | The declared rule this instance realizes. **A string, not an object** — the payload crosses a JSON report boundary (§8) and must survive it. |
| `subject` | tagged object | Exactly one discriminated subject (§2). |
| `severity` | `str` | Must be a member of the rule's declared `severities`. |
| `qualifiers` | object | Typed, rule-specific, stable. Validated against the rule's `qualifier_schema`. |
| `message` | `str` | Human-readable. **Never** identity-bearing. |
| `evidence` | list | Supporting paths, excerpts, locations, prose. **Never** identity-bearing. |

Producer-side factories still take a `FindingRule` **object** and derive `rule_id` from
it, so a producer cannot emit an undeclared rule; only the wire form is a string.

`message` and `evidence` are excluded from identity so that rewording a diagnostic does
not fork a case — the defect that makes `message_contains` acceptance fragile today.

### 2. `FindingSubject` — one required, discriminated primary subject

```python
FindingSubject = EntitySubject | PathSubject | IdentifierSubject | ProjectSubject
```

- **`EntitySubject(type="entity", ref="dataset:gtex-v8")`** — a known canonical entity,
  including tasks. Resolution is validated.
- **`PathSubject(type="path", path=..., pointer=...)`** — files, missing expected files,
  and malformed entities that cannot supply a valid ref. Paths are normalized
  project-relative POSIX. A `pointer` may name a **stable semantic key** or logical
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
annotations qualify a sidecar subject; additional prose and paths are *evidence*.

### 3. Identity — fingerprint v1, frozen

The fingerprint is an API. It is persisted in filenames and in external acceptance
metadata inside consumers' `science.yaml`, so its observable bytes are frozen here.

**Inputs, and only these:** `rule_id`, `subject`, and the subset of `qualifiers` the rule
declares identity-bearing. Explicitly excluded: date, model, lens, run id, producer,
prose, `message`, `severity`, `evidence`, line numbers, and list positions.

**Normalization**, applied before encoding:

- strings: Unicode NFC, no case folding except where a field's own vocabulary is
  lowercase (`namespace`, `type`)
- paths: project-relative, POSIX separators, no `.`/`..` segments, no trailing slash
- entity refs: canonical `<prefix>:<slug>` form
- qualifiers: only rule-declared identity keys, others dropped
- absent optional fields are omitted, never encoded as null

**Identity-qualifier value types are constrained** to `str`, `bool`, `int`, and arrays
of those. Floats, nulls, and nested objects are rejected at rule declaration, so no
identity ever depends on float formatting or on a nested key order. Arrays are encoded in
**declaration order, not sorted** — order is meaningful where a rule declares a sequence —
and integers are encoded as bare decimal digits with no sign for zero and no leading
zeros.

**Canonical encoding:** UTF-8 JSON, object keys sorted lexicographically by code point,
no insignificant whitespace, no non-ASCII escaping.

**Digest:** `SHA-256` over the byte string
`science.finding.v1\n` + canonical JSON, rendered as 64 lowercase hex characters.

The `science.finding.v1` domain prefix means a future v2 normalization produces disjoint
identities by construction rather than silently colliding with v1 records. The version is
stored on every record; ingestion refuses a record whose fingerprint version it does not
implement.

**Filename mapping:** `doc/audits/cases/<rule-slug>--<digest>.md`, carrying the **full**
digest. No truncation, and therefore no collision handling to design.

`<rule-slug>` is a frozen transformation of `rule_id`: lowercase, `.` and `_` replaced by
`-`, any character outside `[a-z0-9-]` replaced by `-`, runs of `-` collapsed, leading and
trailing `-` stripped, truncated to 60 characters. The slug exists purely so the directory
is browsable; it is derived from a digest input, so it can never carry information the
record does not.

**Loaders validate the filename against the contents.** A case whose filename slug does
not equal `slug(record.rule_id)`, or whose filename digest does not equal
`record.finding_id`, or whose `finding_id` does not equal the fingerprint recomputed from
its own immutable fields, is a **load error** — never a silent repair or rename. A renamed
or hand-edited case file must fail loudly rather than acquire a new identity.

### 4. `FindingRecord` — the canonical stored case

`FindingRecord` carries immutable identity fields plus append-only history. **It does not
store a canonical payload.** Revision 1 stored "the `Finding` as first emitted", which
made the record arrival-order dependent: the first producer to arrive — later, possibly
an agent — would own the message and evidence forever, subsequent observations would be
discarded, and a severity change would have no defined effect.

| Field | Mutability | Meaning |
|---|---|---|
| `finding_id` | immutable | The v1 fingerprint (§3). |
| `fingerprint_version` | immutable | `1`. |
| `rule_id` | immutable | Identity input. |
| `subject` | immutable | Identity input. |
| `identity_qualifiers` | immutable | The rule-declared identity subset. |
| `occurrences` | append-only | One complete observation each (below). |
| `reviews` | append-only | Distinct eligible reviews, each retaining its note. |
| `transitions` | append-only | Lifecycle transition log (below). |
| `status` | derived | `proposed` \| `confirmed` \| `dismissed` \| `promoted`. |
| `promoted_task` | derived | Task ref. **Present iff `status == "promoted"`.** |

**Occurrence** — the complete observation, so nothing is discarded:

| Field | Meaning |
|---|---|
| `idempotency_key` | `sha256("science.occurrence.v1\n" + producer_id + "\0" + ingestion_ref + "\0" + finding_id)`. Re-ingesting the same report appends nothing. |
| `producer_id` | Registered producer that observed it. |
| `ingestion_ref` | Run ref for an unattended run; the ingestion id for an interactive one. Never absent. |
| `observed_at` | Timestamp. |
| `severity` | Severity **as observed**. Severity is not identity, so it varies per occurrence legitimately. |
| `message` | As emitted. |
| `qualifiers` | The **complete** observed qualifier object, not only the identity subset. Non-identity qualifiers are recorded here or they are not recorded at all. |
| `evidence` | As emitted, including locations and line numbers. |

Current severity for display and for acceptance scoping is the **maximum severity over
occurrences from the most recent ingestion of each producer** — a defined function of the
log, not a field anyone writes.

**Transitions** — append-only, one per lifecycle act:

| Field | Meaning |
|---|---|
| `from_status` | The prior status. `None` **only** on the genesis transition. |
| `to_status` | The new status. |
| `actor` | Human identity, or a trusted producer id. |
| `at` | Timestamp. |
| `reason` | Required free text. |
| `task_ref` | Required on a transition to `promoted`, forbidden otherwise. |

**Every record opens with a genesis transition `None → proposed`**, written by ingestion
when the record is created. The log is therefore never empty and `status` needs no
special case for "no transitions yet".

**The transition graph is closed.** Any pair not in this table is rejected:

| From | Permitted to |
|---|---|
| *(genesis)* | `proposed` |
| `proposed` | `confirmed`, `dismissed` |
| `confirmed` | `dismissed`, `promoted` |
| `dismissed` | `proposed` *(reopen)* |
| `promoted` | `dismissed` |

**Lifecycle rulings:**

- Dismissed cases are **retained indefinitely** in Spec 1. Nothing is deleted.
- **Re-detection appends an occurrence and never changes status.** A dismissed case that
  reappears stays dismissed, with a new occurrence recording that it reappeared. Reopening
  is an explicit `dismissed → proposed` transition by an actor, never a side effect of
  detection.
- `status` is **derived from the last transition** and validated against the stored value;
  disagreement is a load error, not a repair.
- `promoted_task` is present **if and only if** `status == "promoted"`, enforced by a
  model validator.

**Review** — the record Spec 3's confirmation counts are derived from. A note alone cannot
support a count, so the shape is fixed here rather than in Spec 3:

| Field | Meaning |
|---|---|
| `review_id` | Stable id, `sha256("science.review.v1\n" + reviewer_ref + "\0" + run_ref + "\0" + finding_id)`. |
| `reviewer_kind` | `human` \| `agent` \| `deterministic`. |
| `reviewer_ref` | Human identity, or the agent role. Never a bare model name. |
| `lens` | The analytical lens, where the reviewer had one. Required when `reviewer_kind == "agent"`. |
| `model` | Model provenance, where applicable. Recorded, never an eligibility input on its own. |
| `run_ref` | The run this review was produced in. |
| `at` | Timestamp. |
| `outcome` | `confirms` \| `refutes` \| `abstains`. |
| `note` | Required concise reasoning. |

Confirmation counts are derived from **distinct eligible reviews** and retain their notes.
**They are never a confidence, never aggregated, never a belief input.** What makes a
review *eligible* — and the promotion threshold — is Spec 3's subject; Spec 1 fixes the
storage shape so Spec 3 cannot reopen the schema. `lens` and `reviewer_ref` are required
fields precisely so Spec 3 can define eligibility over lens diversity rather than raw
count.

A standing caution for Spec 3, recorded here because it constrains that threshold: *N
reviewers drawn from the same model family are strongly correlated.* Lens diversity buys
far more independence than sample count; the `explore-ideas` blind per-lens dispatch is
the precedent to copy.

### 5. Storage and placement

Canonical cases are typed project-state documents under `doc/audits/cases/`, with
frontmatter carrying `doc_kind: finding-record` and `finding_id: …`, and **never** an
entity `kind:` or `id:`. Prose in the body is supporting context only.

Three placement constraints, each with a verified cause:

1. **Not `entities/`, not an EntityKind.** `finding` is taken by a live epistemic kind.
   Cases are project-state, not knowledge.
2. **Not any directory named `findings/`.** `_infer_kind_from_path` keys on
   `path.parent.name` with no root anchoring, so `doc/audits/findings/` would infer the
   epistemic kind. `cases/` is not in `_DIR_TO_KIND`.
3. **`doc/audits/cases/*.md` is added to `DEFAULT_REVISION_MANIFEST_EXCLUDES`**
   (`graph/io.py:428`), not to per-project config. Without it every ingestion flips the
   graph to stale — the fb-2026-07-17-001 failure at higher volume.

Cases never materialize into `graph/knowledge`, never become belief bearers, freshness
subjects, or attention candidates — the same placement ruling, for the same reason, that
run records were given (`graph/attention.py`).

### 6. Rules — declared beside the producer, registry derived

Rules are declared next to the code that emits them, and **one frozen registry is derived
from those declarations**. There is no hand-maintained central list, and therefore no
repeated ID string to drift — while ingestion still gets exactly one immutable lookup
authority.

```python
FindingRule(
    id="dataset.cached-field-drift",
    severities={"warning"},
    subject_types={"entity"},
    identifier_namespaces=set(),
    qualifier_schema=DatasetFieldQualifier,
    identity_qualifiers=("field",),
    remediation="producer",
    # presentation metadata — so renderers stop hardcoding sections and order
    title="Cached dataset field drifted from source",
    section="datasets",
    display_order=340,
    default_visibility="visible",
)
```

Sections are themselves declared, with an explicit order — sorting by section *name* would
alphabetize and destroy the order `HEALTH_CHECKS` encodes today:

```python
FindingSection(id="datasets", title="Datasets", section_order=300)
```

**Producer registration carries a metrics schema.** A producer that emits metrics declares
their type at registration, and the derived registry validates each producer's metrics
object against it. Without this, §11's `ProducerMetrics` would be an untyped escape hatch —
which is the same defect as `dataset_anomalies: list[dict]`, reintroduced one layer up.

- **`severities` is a permitted set, not a single default.** Existing rules legitimately
  vary by context.
- **`identity_qualifiers`** names the identity-bearing subset consumed by §3. Qualifiers
  outside it are recorded but do not fork a case.
- **Presentation metadata is part of the declaration.** `HEALTH_CHECKS`'s hand-ordered
  tuple currently encodes display order as import order, which the §11 rewrite would
  otherwise destroy; `display_order` carries it explicitly, and `default_visibility`
  replaces `validate/cli.py:25`'s hardcoded `_VISIBLE_INFO_RULES`.
- **Dynamic rule strings are retired.** `prose_lints.<check>` becomes a declared
  `prose-lints.hit` rule with `check` as a typed identity qualifier. A wildcard family
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
3. A finding whose severity, subject type, identifier namespace, or qualifiers violate
   its rule.
4. A rule declaring producer remediation without a registered trusted handler.
5. A registered producer returning anything except the uniform result channel.
6. Project configuration attempting to add or override a toolkit rule.
7. Two rules claiming the same `display_order` within a `section`, or two sections
   claiming the same `section_order`.

**Completeness guards, one per producer namespace.** The existing guards cover two
namespaces by two different tests (`test_check_registry_is_complete.py` for
`validate/checks/*.py`; `test_health_checks_package.py` for `health_checks/`). Spec 1
requires an equivalent filesystem-derived guard for **every** namespace contributing to
the derived registry, including `data_audit` and the generic producer registry. Each
guard must be derived from the filesystem, never from a list — per the rule
`test_check_registry_is_complete.py` states about itself.

### 7. Remediation — capability, not instruction

> `Finding` carries no executable fix command and no authoritative proposed mutation.
> The rule registry may declare a trusted remediator. Acting on a finding re-runs that
> producer against current state and recomputes the plan.

`data_audit` therefore keeps `Violation.proposed_target` **internally**, while a stored
case never authorizes a stale move. Agent-authored repair suggestions are notes only.
Spec 3 queries the rule's capability without reopening the finding schema.

This inherits Plan D ruling #3 of the autonomy envelope: both rules prohibit acting on
stale derived state.

### 8. Trusted ingestion — the write boundary

```
producer (check | validation | data_audit | Spec 2 lens)
    ↓ emits shared Finding
one gated report path                     ← the only surface an untrusted actor writes
    ↓ science findings ingest <report>    ← trusted; validates, fingerprints, upserts
canonical FindingRecord under doc/audits/cases/
    ↓ explicit promotion (Spec 3 or human)
task
```

The actor never writes canonical cases. It writes its one supervisor-supplied report
path — the surface `report-only` already allows. `entity_kind_for_path` already returns
`None` for `doc/audits/cases/…` and the gate already reads `None` as denied, so *"Layer 1
works unchanged"* is literal: nothing in `autonomy/policy.py` is edited and no allowlist
widens.

**`science findings ingest <report>` is a separate explicit command.** `science health`
stays purely read-only and gains no persist flag; a diagnostic run never writes cases as
a side effect.

Because this is a trust boundary crossed by untrusted output, ingestion enforces:

- **Schema and version validation.** The report declares `schema_version` and
  `fingerprint_version`; unknown or unimplemented values are refused outright, never
  coerced.
- **Size limits.** A maximum report byte size and a maximum finding count, both
  configured in the toolkit, not by the project.
- **Path safety.** Every path in a subject or evidence entry must be relative,
  normalized, free of `..`, and resolve inside the project root. Absolute paths are
  refused.
- **Symlink refusal.** Any path resolving through a symlink is refused, including the
  report path itself.
- **Serialized application under a project-scoped lock.** Ingestion takes an exclusive
  lock on the project's case directory for its duration; concurrent ingestions queue
  rather than interleave.
- **Full prevalidation, then atomic per-record writes.** The whole report is validated
  before anything is written; on a *validation* failure nothing is written. Each case file
  is then written atomically (temp file plus rename).

  **This is not a multi-file transaction, and the spec does not claim one.** A crash after
  three renames leaves three committed cases. That is acceptable **only because recovery
  is idempotent**: re-running the same ingestion re-applies the whole report, and every
  already-written record is a no-op by occurrence idempotency key. Partial I/O failure is
  therefore recoverable by retry, and retry is the documented procedure. A journal or
  directory-level commit protocol is deliberately not built; it would buy atomicity this
  design does not need.
- **Idempotency, and idempotency conflicts.** Re-ingesting an identical report is a no-op,
  enforced by occurrence idempotency keys (§4), never by inspecting timestamps. An
  incoming occurrence whose idempotency key already exists **with different observation
  content is an error**, not a silent retry — identical keys must mean identical
  observations, or the key means nothing.

### 9. Migration ledger

R3 requires every count change to be enumerated and approved rather than absorbed. This
is that enumeration; it is part of the contract, not an appendix.

Column key: **Count today** is the contribution to `count_issues`; **Change** marks an
intentional observable difference.

| Producer / report key | Count today | Findings after | Metrics retained | Change |
|---|---|---|---|---|
| `unresolved_refs` | `len(rows)` | `refs.unresolved`, subject = the unresolved ref as `IdentifierSubject(namespace="reference")` | — | net unchanged; the producer already groups by target (`unresolved_refs.py:70`), so citing files simply become evidence locations |
| `unregistered_ref_kinds` | `len(rows)` | `refs.unregistered-kind`, `IdentifierSubject(namespace="reference-kind")` | — | — |
| `lingering_tags_lines` | `len(rows)` | `tags.lingering`, `PathSubject` + semantic pointer | — | line numbers move to occurrence metadata |
| `agent_context` | `len(rows)` | `agent-context.*` | — | — |
| `identity_policy` | `len(rows)` | `identity.policy-violation` | — | — |
| `entity_identity` | `len(rows)` | `identity.entity` | — | — |
| `legacy_task_type` | **0** (validated, never summed) | `task.legacy-type`, `EntitySubject` | — | **counts change: rows now count.** Approved — the current zero is undocumented and inconsistent with every sibling row section |
| `invalid_entity_aspects` | **0** (validated, never summed) | `entity.invalid-aspects`, `EntitySubject` | — | **counts change: rows now count.** Same approval |
| `dataset_anomalies` | `len(rows)` | twelve declared rules, enumerated below | — | untyped `list[dict]` gains a schema; the undeclared twelfth code is regularized |
| `schema_invalid` | `len(rows)` | `entity.schema-invalid`, `PathSubject` (a malformed entity cannot supply a valid ref) | — | — |
| `managed_artifacts` | rows where `counts_as_issue` | `managed-artifact.*` for flagged rows only, `IdentifierSubject(namespace="managed-artifact")` | inventory of unflagged rows | split: the flag becomes the finding/metric boundary |
| `tooling_scaffold` | `len(rows)` | `tooling.scaffold` | — | — |
| `validation` | `len(rows)` | one rule per canonical validation rule id | — | `prose_lints.<check>` collapses to `prose-lints.hit` + `check` qualifier |
| `accepted_validation` | excluded | same rules, reported in the `accepted` channel (§11) | — | remains excluded from the finding total |
| `archive_lag` | `1 if total else 0` | `tasks.archive-lag`, `ProjectSubject`, emitted **iff** total > 0 | `done_in_active`, `retired_in_active`, `missing_completed` retained as metrics | net count unchanged (1 ↔ 1); the measurement is no longer the issue |
| `layered_claims.migration_issues` | `len()` | `layered-claim.migration` | — | — |
| `layered_claims.rival_model_packets_…` | `len()` | `layered-claim.rival-model-gap` | — | — |
| `layered_claims.*_coverage` (×2) | `+1` each when incomplete | `layered-claim.coverage-incomplete`, `ProjectSubject`, qualifier = which coverage | both coverage metrics retained | net count unchanged; the metric stops being the issue |
| `prose_epistemics.findings` | issue-flagged subset | `prose-epistemics.*` | remaining prose measurements | split, not wholesale classification |
| `cross_paper_evidence.findings` | `len(findings)` | `cross-paper.*` | cross-paper summaries | split, not wholesale classification |
| `unwired_checks` | excluded | **never a finding** | — | unchanged; own channel |
| `data_audit` `Violation` | not in health | `data.violation.*`, subject per violation quadrant | — | `proposed_target` stays producer-internal (§7) |
| `data_audit` warning `AuditNote` | not in health | `data.audit-note` | non-warning notes stay notes | only warning-bearing notes convert |

**Dataset anomaly rules.** `DATASET_ANOMALY_CODES` declares eleven codes while the
producer emits twelve; `dataset_access_invalid` is emitted at `dataset_anomalies.py:197`
and declared nowhere. All twelve become declared rules, and the drift is closed by
construction because producers must build findings from declaration objects (§6).

| Rule id | Subject | Identity qualifiers |
|---|---|---|
| `dataset.consumed-but-unverified` | `EntitySubject` (dataset) | — |
| `dataset.stale-review` | `EntitySubject` | — |
| `dataset.missing-source-url` | `EntitySubject` | — |
| `dataset.cached-field-drift` | `EntitySubject` | `field` |
| `dataset.invariant-violation` | `EntitySubject` | `invariant` |
| `dataset.derived-missing-workflow-run` | `EntitySubject` | — |
| `dataset.derived-asymmetric-edge` | `EntitySubject` | `counterpart` |
| `dataset.derived-input-chain-broken` | `EntitySubject` | `counterpart` |
| `dataset.origin-block-mismatch` | `EntitySubject` | `field` |
| `dataset.verified-but-unstageable` | `EntitySubject` | — |
| `dataset.research-package-asymmetric` | `EntitySubject` | `counterpart` |
| `dataset.access-invalid` | `EntitySubject` | — |

Rules taking a `counterpart` or `field` identity qualifier are those the producer can emit
more than once per dataset; without the qualifier those emissions would collapse into one
case. The mapping from each emission site to its qualifier value is a plan-writing detail;
the rule set and its identity keys are fixed here.

**Net count effect.** Two entries are net-new count increases (`legacy_task_type`,
`invalid_entity_aspects`), both approved above as omissions rather than a third exclusion
class. Two are net-neutral reclassifications (`archive_lag`, layered-claim coverage).
**No entry reduces counts.** Everything else preserves observable counts exactly.

### 10. Acceptance migration

Acceptance is re-keyed from `message_contains` prose onto fingerprints. Spec 1 ships
`science findings migrate-acceptances`, **dry-run by default**, with `--apply`.

**Correctness conditions:**

- **Match against the raw, unsuppressed finding stream.** Matching against a
  already-filtered stream cannot find what current acceptances suppress.
- **Preserve severity scope.** Severity is excluded from identity, so a fingerprint alone
  would let an acceptance written for a warning silently suppress a later error at the
  same rule and subject. The rewritten entry carries an explicit severity scope.
- **The correspondence evidence signature becomes a declared identity qualifier**, or
  that acceptance loses the automatic invalidation it has today.
- **Refuse to migrate unless every relevant producer ran.** "No finding matches" while
  the owning producer was skipped or `unwired` is **indeterminate, not stale** — this is
  the fourth outcome, and it aborts rather than rewriting.
- **`--apply` is all-or-nothing across entries, not merely atomic on the file.** Atomic
  rewriting says how `science.yaml` is written; it does not say what happens when some
  entries are stale or ambiguous. **Any non-unique outcome aborts the whole migration
  with no mutation.** The operator resolves the reported entries and reruns. A partial
  migration that drops unresolved entries would delete acceptance decisions as a side
  effect of a rewrite, which is exactly the silent-suppression direction §10 exists to
  prevent.
- **Duplicate `(finding_id, severity_scope)` entries are rejected** after rewriting —
  two prose acceptances can legitimately collapse onto one fingerprint, and a silently
  deduplicated pair hides that one of them was never doing anything.
- **`accepted-validation.stale` and `accepted-validation.ambiguous` are declared
  unsuppressible** — an acceptance-hygiene rule that could itself be accepted is a
  silencer for the silencer.

**Outcomes:**

| Outcome | Action | Mutates? |
|---|---|---|
| **Every** entry matches exactly one finding, all producers ran | Rewrite all entries to `{finding_id, severity_scope}`. | yes, wholly |
| Any entry matches no finding, all producers ran | Emit `accepted-validation.stale` for it; **abort**. | no |
| Any entry matches more than one | Emit `accepted-validation.ambiguous` for it; **abort**. | no |
| Any relevant producer skipped or `unwired` | **Indeterminate** — abort before matching. | no |

Under dry-run every entry is classified and reported, so one pass shows the operator the
complete set of problems rather than the first one.

**No failure case suppresses anything.** An acceptance matching nothing becomes a finding
in its own right, never a silent no-op — the fail-loud direction required by the standing
rule that evidence and metadata are never tuned to silence a check.

The replacement YAML schema is:

```yaml
health:
  accepted_validation:
    - finding_id: "<64-hex>"
      fingerprint_version: 1
      severity_scope: ["warning"]
      reason: "<required>"
      accepted_on: "<ISO-8601 date>"
```

`rule` and `message_contains` are removed, not retained alongside.

An acceptance entry's own subject, when it becomes a hygiene finding, is
`IdentifierSubject(namespace="accepted-validation", value=<acceptance key>)` — never a
`PathSubject` pointer into `health.accepted_validation`, which is a bare positional list
(`validate/acceptance.py:26`) whose indices move when any earlier entry is deleted.

**The acceptance key is frozen** as
`sha256("science.acceptance.v1\n" + canonical_json(entry))[:32]`, over the entry's own
content under the §3 canonical encoding — for a pre-migration entry that is
`{rule, severity, message_contains}`, for a migrated one `{finding_id, severity_scope}`.
Content-derived, so it survives reordering and deletion of siblings; truncated to 32 hex
characters because it names a config entry rather than identifying a stored record, and
nothing resolves by scanning it.

### 11. The output contract

The public schema changes **once**; no compatibility adapter preserves the heterogeneous
report.

```python
class ReportedFinding(TypedDict):
    producer_id: str                 # which producer observed it
    finding: Finding

class AcceptedFinding(TypedDict):
    producer_id: str
    finding: Finding
    acceptance_key: str              # §10 — the accepting entry's frozen key
    reason: str                      # the acceptance's own recorded reason

class AuditReport(TypedDict):
    schema_version: int              # 2
    fingerprint_version: int         # 1
    ingestion_ref: str               # trusted, report-level; run ref or ingestion id
    generated_at: str                # ISO-8601, report-level
    findings: list[ReportedFinding]  # unsuppressed, ordered (below)
    accepted: list[AcceptedFinding]
    metrics: dict[str, ProducerMetrics]   # keyed by producer_id, validated per §6
    unwired: list[UnwiredProducer]   # {producer_id, code, reason}
    totals: ReportTotals
    meta: ReportMeta                 # timings, duration, producers_run
```

- **Findings are enveloped with their producer.** A bare `Finding` cannot populate an
  occurrence's required `producer_id`, and rule ownership cannot supply it either, because
  multiple producers must be able to emit the same rule — that is the premise of
  cross-producer dedup. `ingestion_ref` and `generated_at` are **report-level and
  trusted**: supplied by the supervisor or the ingesting command, never by the finding.
  Accepted findings carry the same provenance, plus the key of the entry that accepted
  them.
- **`ProducerMetrics` is validated, not free-form** — against the metrics schema the
  producer declared at registration (§6).
- **`totals`** carries `findings_by_severity`, `findings_total`, `accepted_total`, and
  `unwired_total`. `accepted` and `unwired` are **not** in `findings_total`, preserving
  today's exclusions. `total_issues` is replaced by `totals.findings_total`; §9
  enumerates every case where that number differs from today's.
- **Ordering is deterministic and derived from the registry**, never from import order and
  never from a section's name:
  `(section_order, display_order, severity rank, subject canonical form, finding_id)`.
  Sorting on the section *identifier* would alphabetize, discarding the order
  `HEALTH_CHECKS`'s hand-ordered tuple encodes today; `section_order` (§6) carries it.
- **Visibility comes from `default_visibility`**, retiring
  `validate/cli.py:25`'s hardcoded rule set.
- **The unwired invariant survives the rewrite**: a non-empty `unwired` forbids any
  "clean" rendering, asserted directly on rendered output (§Testing 5).

## Testing

1. **Uniform-channel ratchet** — a registered producer returning anything but the uniform
   result channel fails. The `_drain_instrument_results` non-`InstrumentResult`
   passthrough is removed, not deprecated.
2. **Rule-completeness ratchet** — undeclared rule id, duplicate rule id, producer
   remediation without a registered handler, and colliding `display_order` within a
   section each fail.
3. **Constraint validation** — a finding whose severity, subject type, identifier
   namespace, or qualifiers violate its rule fails.
4. **Project config cannot add or override a toolkit rule.**
5. **Renderer clean-refusal** — a non-empty unwired channel forbids "Project is clean",
   asserted on rendered output, not on a boolean. The invariant lives in the layer being
   rewritten, and this is the guard-in-one-reader failure shape.
6. **Fingerprint v1 is frozen** — a golden-vector test pinning canonical encoding,
   normalization, and digest for each subject variant. Changing normalization must break
   this test. A rule declaring a float, null, or nested-object identity qualifier fails at
   declaration.
7. **Filename binds to contents** — a case whose filename slug, filename digest, or
   stored `finding_id` disagrees with the fingerprint recomputed from its immutable fields
   fails to load, with no repair and no rename.
8. **Identity stability** — rewording a `message`, adding an occurrence, adding evidence,
   changing a line number, changing observed severity, or deleting an earlier
   `accepted_validation` entry changes no fingerprint.
9. **Occurrence idempotency, and conflict** — re-ingesting an identical report appends
   nothing; an occurrence reusing an existing idempotency key with different observation
   content is an error, not a retry.
10. **Partial-failure recovery** — an ingestion interrupted after some records are written
    is fully repaired by rerunning the same report, with no duplicate occurrences.
11. **No arrival-order dependence** — ingesting producer A then B, and B then A, yields
    byte-identical records modulo occurrence order.
12. **Non-identity qualifiers survive** — a qualifier outside `identity_qualifiers` is
    present on the occurrence and absent from the fingerprint.
13. **Cross-producer dedup** — two producers reporting the same rule + subject + identity
    qualifiers upsert **one** record with two occurrences, each carrying its own
    `producer_id` from the report envelope.
14. **Report provenance is required** — a report whose finding lacks a `producer_id`, or
    which omits `ingestion_ref` or `generated_at`, is refused; a `producer_id` naming an
    unregistered producer is refused.
15. **Producer metrics are validated** — a metrics object violating the schema the
    producer declared at registration fails.
16. **Subject discrimination is total and strict** — an invalid entity ref fails rather
    than degrading to a path subject.
17. **Lifecycle** — every record opens with a `None → proposed` genesis transition; a
    transition pair outside the §4 graph is rejected; re-detection of a dismissed case
    appends an occurrence and leaves status `dismissed`; `promoted_task` present without
    `promoted` status fails, and vice versa; a `status` disagreeing with the transition
    log fails to load.
18. **Review record** — a review missing `lens` when `reviewer_kind == "agent"` fails;
    two reviews from the same `(reviewer_ref, run_ref)` on one finding collapse to one
    `review_id`.
19. **Ingestion hardening** — absolute path, `..` traversal, symlinked path, unknown
    `schema_version`, unimplemented `fingerprint_version`, oversize report, and excess
    finding count are each refused, and a *validation* failure writes nothing.
20. **Layer 1 unchanged** — a write to `doc/audits/cases/…` in an autonomous commit range
    is denied by the existing path gate, with no edit to `autonomy/policy.py`.
21. **Graph isolation** — no finding triple appears in any named graph; cases are absent
    from attention candidates; ingesting cases does not stale the revision manifest.
22. **Acceptance migration** — all four outcomes; the severity-scope invariant (an
    accepted warning does not suppress a later error at the same fingerprint); the
    unsuppressibility of the two hygiene rules; **one stale entry among many valid ones
    aborts the entire `--apply` with `science.yaml` unmodified**; duplicate
    `(finding_id, severity_scope)` after rewriting is rejected; dry-run reports every
    problem entry rather than the first.
23. **Count ledger** — a test asserting the §9 table: for a fixture project, each
    producer's contribution to `totals.findings_total` matches the enumerated
    expectation. This is what makes the count changes approved rather than absorbed.
24. **Presentation order is preserved** — rendering order matches the current
    `HEALTH_CHECKS` order for the sections that exist today, and is unaffected by renaming
    a section identifier.
25. **Metrics are not findings** — coverage, counts, and nested summaries survive as
    metrics and are absent from the finding stream.
26. **Producer-namespace completeness** — every namespace contributing to the derived
    registry has a filesystem-derived guard.
27. **All twelve dataset rules are declared and reachable** — the emitted-code set equals
    the declared-rule set, asserted as equality rather than as a subset, which is the
    assertion shape that let `dataset_access_invalid` drift.

## Out of scope

- Any agent, lens, harness, or unattended execution (Spec 2).
- Review eligibility rules, the confirmation threshold, and promotion authority
  (Spec 3). Spec 1 fixes only the storage shape these use.
- **Converting measurements themselves into findings.** A coverage fraction, a lag count,
  or a corpus tally stays a metric; making the shared type carry measurements would make
  it broad enough to mean nothing. This does **not** exclude the enumerated
  policy-violation findings of R3 — `layered-claim.coverage-incomplete` and
  `tasks.archive-lag` are findings *about* a measurement crossing a policy threshold, and
  the measurement is retained alongside. §9 is the exhaustive list; no producer may add
  another without a ledger row.
- Retiring `doc/curations/` ledgers. The curation sweep's narrative output is a Spec 2
  question; Spec 1 only removes the reason it needs prose carry-over parsing.

## Open questions

- Whether `dismissed` cases are archived on a cadence once volume is known. Spec 1
  retains them indefinitely; this is a volume question to revisit with data, not a
  contract gap.
- Which emission site inside `dataset_anomalies.py` supplies each `counterpart` /
  `field` identity-qualifier value. The rule set and its identity keys are fixed in §9;
  only the per-site mapping is plan-writing work.
- **Acceptance migration scope, surveyed.** Four locally available projects carry 50
  `accepted_validation` entries: post-acute-infection (21), multiple-myeloma (24),
  `meta/` (2), natural-systems (3). Repositories outside the local checkout set remain
  unsurveyed, so `migrate-acceptances` must be safe to run against an unknown corpus —
  which the four-outcome contract (§10) already requires.
