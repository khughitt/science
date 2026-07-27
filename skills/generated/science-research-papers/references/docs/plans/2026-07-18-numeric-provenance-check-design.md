# Numeric-Claim Provenance Check — Redesign Design

## Status

Proposed. Phased: **Part A** (precision overhaul of the existing `numeric-anchor`
lint) is the near-term implementation; **Part B** (structured, verifiable numeric
claims) is the declared end-state, specified here for forward-compatibility but
deferred to its own cycle.

**Revision 2 (2026-07-18, post-review).** Part A was tightened after review found
its first-draft clearance rules broader than its goals: kind-wide exemption hid
ungrounded thresholds; entity-wide body anchors recreated the motivating
false-negative at larger scope; candidates were accepted without existence checks.
This revision rests on three principles:

1. **Structural, stipulated, anchored, and unanchored are distinct outcomes** — a
   discriminated assessment type, not a boolean.
2. **Only explicit entity provenance is entity-scoped**; incidental body anchors
   are local evidence.
3. **"Resolvable source" belongs in Part A**; "this exact value came from that
   locator" belongs in Part B.

## Context

The `numeric-anchor` prose lint (`science_tool/prose_lint.py:detect_numeric_anchor`,
wired through `validate/checks/prose_lints.py`) flags a numeric claim in body prose
when no *anchor token* (`task:`, `pipeline/`, `[@`, `data/`, `scripts/`,
`[[wiki]]`) appears in the **same paragraph**. It is `info` severity by default
(promoted to `warn` under `--strict`) and already carries exclusion logic
(identifier masking, cell-line / biomedical short-forms, 4-digit years, bare
integers < 100, `Eq. 2` / `Fig 3` refs). Two ad-hoc exemption helpers also exist:
`_paper_note_has_source_context` (paper notes with `source_refs`/`doi`/`pmid`/
`url`/`bibkey`) and `_interpretation_has_artifact_context` (interpretations with a
nonempty `artifact` string — **no existence check**).

Its **goal is valid**: quantitative claims should be traceable, especially in an
AI-assisted corpus where a figure can be hallucinated, copied stale, or drift from
its origin. But the **mechanism is a weak proxy** — "is an anchor-token substring
present in this paragraph" — and fails in both directions:

- **False positives.** A number can be fully traceable (source declared in
  frontmatter `source_refs: task:tNNN`; the entity *is* that task's writeup) yet
  flag, because the token isn't repeated in-paragraph.
- **False negatives.** A paragraph can state a *fabricated* number next to a
  valid-looking `[@Paper]` — or an interpretation can carry an invented
  `artifact:` path — and pass, because nothing checks the source exists or
  produced the value. (This exact failure was caught in a 2026-07-18 pan-disease
  review.)

It also **conflates claim types** (stipulated `alpha = 0.05` vs empirical
`E = 7.94×`) and **scopes provenance to the paragraph** when it lives at the entity.

### Empirical grounding

A cross-project audit (`docs/audits/2026-07-18-numeric-anchor-audit/`) sampled and
classified **320 flagged numbers across 8 domain-diverse projects**:

- **~83% are false positives** — provenance exists at doc/frontmatter scope, not
  in the flagged paragraph (58% cited-elsewhere-in-doc, 25% frontmatter/title).
- **~33% are exempt-by-nature** — structural tokens (11%) + stipulated design
  params (22%) need no external source.
- **The genuine "ungrounded number" signal is ~10% and hand-wavy is 3%** — small,
  and clustered in narrative/manuscript entities that restate the project's own
  computed statistics without a task ref, plus a few uncited domain facts.

The corpus is disciplined; the check's *output* is dominated by noise its own
mechanism manufactures. The redesign shrinks the check to its real signal without
masking (no `exclude_paths` hacks — those hide genuine claims alongside noise).

## Goals

- Cut the false-positive mass legitimately — resolve provenance where it lives,
  recognize the anchor forms the corpus uses, and stop flagging exempt-by-nature
  numbers.
- Keep the genuine signal firing — ungrounded numbers, including ungrounded
  *stipulated thresholds*, which the project's methodology wants surfaced.
- Distinguish outcomes honestly (structural / stipulated / anchored / unanchored).
- Make the check *trustworthy*: when it fires, it means something.
- Verify that a cited source *exists* (Part A); pave toward verifying that a value
  *came from* it (Part B).
- Stay config-native; no project-local ledger dependency.

## Non-Goals

- **Which-source resolution and value verification are Part B.** A credits a claim
  when the entity/paragraph declares a source that *could* cover it and that source
  *resolves*; it does not determine *which* source produced *this* number, nor that
  the value is correct. (Verification is impossible without per-claim binding, and
  that binding *is* B's core.)
- **Not a per-number correctness checker.** A's promise is precisely: *this
  entity/paragraph's numbers lack declared, resolvable provenance at the
  appropriate scope.* An orphaned number inside an otherwise-sourced entity is a
  known, documented Part-A miss (Part B closes it) — see Success Criteria.
- Do not change the default severity (`info`).
- Do not build Part B's authoring surface or verifier in this cycle.

## Decision (phased — "C")

Ship **Part A** as an evolution of `numeric-anchor`; **specify Part B** as the
end-state so A's scope/vocabulary/output choices stay forward-compatible.

---

## Part A — Precision overhaul (near-term, this implementation)

### The assessment, as a discriminated outcome

Each numeric claim resolves to exactly one:

```
ClaimAssessment =
    NotClaim(reason)                     # structural / not a quantitative claim
  | Exempt(reason, scope)                # stipulated design parameter, marked
  | Anchored(candidates: [SourceCandidate])   # resolvable provenance covers it
  | Unanchored(kind_hint)               # the genuine signal; kind shapes messaging

SourceCandidate = { reference, origin ∈ {frontmatter, title, body},
                    field_or_line, resolution_status ∈ {resolved, unresolved} }
```

Only `Anchored` carries candidates. `kind_hint` on `Unanchored` lets a spec-class
entity phrase the finding as "stipulated parameter lacks grounding — mark or
ground it" rather than "numeric claim lacks source," without changing whether it
fires.

### Resolution order

**1 — NotClaim (structural).** Extend identifier masking, *narrowly*, to clearly
structural tokens: hardware IDs (`RTX 3070`, `NovaSeq 6000`), database accession
suffixes (`GCST\d+`), license/spec versions (`CC-BY-4.0`), entity-slug digits,
config line numbers. **Model dimensions and file sizes are context-gated, not
blanket-masked** — `516.9 MB download` is structural, but `the genome is 3.2 Gb`
is a factual claim; negative fixtures guard against over-masking. (≈11%.)

**2 — Exempt (stipulated, marker-based).** A number cleared here must sit within an
explicit **stipulated marker's** scope. Marker granularity, narrowest-first:

- **Section/block markers are the default** — one marker per parameter block (e.g.
  a "Decision thresholds" section). Section markers **fail closed**: scope ends at
  the next heading of equal-or-higher level unless explicitly repeated. A section
  that **mixes** empirical results with stipulated parameters must use a **block**
  marker around the parameters, not a section marker — the section marker's reach
  would otherwise silently clear the empirical numbers too.
- **Document-level frontmatter flag is reserved** for genuinely pure-spec
  documents (no empirical numbers anywhere in the body). It is a deliberate,
  narrow escape hatch — **not** a template default (see below).

Templates and scaffolds **must not** ship a document-wide stipulated marker on
every plan / pre-registration. Auto-marking the whole document would recreate
kind-wide exemption indirectly — the exact false-negative the review rejected.
Authors add markers where parameters actually live.

**Entity `kind` does *not* clear numbers.** Spec-class kinds (config
`spec_class_kinds`, default `[pre-registration, plan]`) only set the `Unanchored`
`kind_hint` (messaging). This is the review-driven change: kind-wide clearance
would hide ungrounded thresholds like the audit's `60%` assessability gate — a
stipulated-but-arbitrary cutoff the methodology explicitly wants surfaced. Marking
is the author's positive declaration "this is a chosen parameter" (the
`capability_scope` pattern); an *unmarked* ungrounded threshold correctly fires.
At `info` severity the modest authoring burden buys a durable, auditable
stipulated/empirical distinction. (Reclassifies ≈22%: cheaply marked where
genuinely stipulated, surfaced where not.)

**3 — Anchored (resolvable provenance), scope-aware.** A claim is anchored only by
a source that **resolves** (existence-checked — principle 3), at the correct scope:

- **Entity-scoped** — *explicit* entity provenance only: frontmatter provenance
  fields (config `provenance_fields`, default `[source_refs, task_links, input]`),
  the existing paper-note forms (`doi`/`pmid`/`url`/`bibkey`), interpretation
  `artifact`/`artifacts`, or an owning task named in the title. These deliberate,
  entity-level declarations cover the entity's non-exempt numbers. **`related` is
  excluded** (topical links, not sources).
- **Local (paragraph/section-scoped)** — a resolvable *body* reference
  (`cite:`/`[@`/`task:`/`dataset:`/`[[wiki]]`/an `artifact` path) anchors only its
  own paragraph (or section). One incidental body citation must **not** clear
  unrelated numbers elsewhere in the entity (the review's finding 2).
- **anchor_evidence (local suppression, not provenance)** — generic
  `anchor_patterns` regex matches (e.g. `config/`, `scripts/`) are weak *local*
  evidence: they suppress the paragraph's finding but produce no `SourceCandidate`
  and never clear entity-wide. (Tracked distinctly; see Result contract.)

**Existence checking (Part A, not B).** Deferring *which* source produced a value
is fine; deferring *whether the cited source exists* is not — the motivating
failure was a nonexistent path being accepted. Every candidate clears only if it
is syntactically valid **and** resolves through the existing reference/artifact
machinery: `task:t999` and invented `artifact:` paths do **not** anchor. Purity is
preserved by passing a **precomputed resolution index** (known entity/task/cite/
dataset ids + artifact-path existence) into the resolver. This unifies and
*replaces* the two ad-hoc helpers (`_paper_note_has_source_context`,
`_interpretation_has_artifact_context`), preserving their clears where the source
genuinely resolves and newly flagging where it does not.

**4 — Unanchored.** None of the above: a non-exempt claim with no resolvable
entity-scoped provenance and no resolvable local reference. The genuine signal.
Remediation stays the existing two-way choice — **mark as stipulated or provide
resolvable provenance** — modulated only by `kind_hint` messaging.

### Module boundaries

A `DocumentContext` (path, kind, frontmatter, title, body paragraphs) is built
**in the scanning layer** and shared by CLI, validation, direct detector calls,
and the annotation adapter — today the detector re-parses frontmatter while
`scan_root` owns traversal, so the four callers can diverge. The core is a pure
module `numeric_provenance.py`:

```
assess_numeric_claims(document_context, resolution_index, config)
    -> list[ClaimAssessment]

detect_numeric_anchor(...)   # thin: filters Unanchored assessments into LintIssues
```

`assess_numeric_claims` returning *all* assessments (not just failures — the
current detector drops cleared claims) is the reusable hook Part B builds on.

### Config surface (all under `prose_lint`)

| key | status | default | purpose |
|---|---|---|---|
| `additional_anchor_patterns` | **new** | `[]` | additive vocabulary (`cite:`, `paper:`, `dataset:`, `config/`, inline `t\d{3,}`) — see Rollout |
| `anchor_patterns` | exists | `DEFAULT_ANCHOR_PATTERNS` | full override escape hatch (replaces defaults) |
| `spec_class_kinds` | new | `[pre-registration, plan]` | sets `Unanchored` messaging only |
| `provenance_fields` | new | `[source_refs, task_links, input]` | entity-scoped frontmatter fields (excludes `related`) |
| stipulated marker | new | — | document/section marker producing `Exempt(stipulated)` |

Structural masking is hardcoded — mechanical, not a project knob.

---

## Part B — Structured numeric claims (end-state spec, deferred)

Specified for forward-compatibility; not built in A's cycle.

### The model

An **optional, per-claim** binding ties a value to a specific source **and a
locator** — where in the producing artifact the value lives — so it can be
**verified**:

```
value 7.94  <-  task:t064  @  results/2026-.../qap.json  · key `enrichment`
```

### Authoring shape (open — B's own cycle finalizes)

- *Inline token* — binding where the number appears (co-located, but clutters prose).
- *Sidecar claims block* — a frontmatter/adjacent `{value, source, locator}` table
  with a light inline reference id (clean prose, decoupled).

Leaning sidecar-with-inline-ref.

### Verifier + feasibility boundary

A new check resolves each **bound** claim's locator against its artifact and
confirms the value matches within tolerance — catching the fabricated/stale number
the token-check structurally cannot. **Feasibility boundary (B owns it):**
JSON/feather/CSV/parquet locators are resolvable; PNG/figure values are not — B
must declare those *unverifiable* rather than pretend.

### A → B contract

- **Unbound numbers keep A's behavior.** Binding is opt-in per claim — bind only
  high-stakes headline results, never all 45% of internal-results. Closes the
  documented Part-A miss (an orphan inside an otherwise-sourced entity) exactly
  where it's worth the effort.
- **A's `Anchored.candidates` is B's binding menu** — B refines "entity declares
  `task:t064`" into "this number ← t064 @ this locator, verified."
- **Progressive tightening** — a project can later flip specific kinds (e.g.
  `interpretation`, `evidence-line`) from "entity-scope OK" to "headline numbers
  must be bound," without touching A's engine.

## Rollout & severity

Severity stays **`info`** (strict → `warn`), now trustworthy.

**Not strictly monotonic — an intended tightening.** Existence-checking turns some
currently-cleared items into findings (fabricated `artifact:` paths, `task:t999`,
dangling refs). That is the point (it surfaces previously-hidden fabrications), but
it means a few *new* flags appear; projects should expect and welcome them rather
than a pure reduction.

**Vocabulary reaches configured projects.** Because `anchor_patterns` *replaces*
defaults, six downstream projects with explicit patterns (incl. pan-disease) would
not receive an expanded `DEFAULT_ANCHOR_PATTERNS`. The new vocabulary ships as an
**additive `additional_anchor_patterns`** (merged with whatever `anchor_patterns`
resolves to), so every project gets it; `anchor_patterns` remains a full-override
escape hatch.

**Rollout surface includes the annotation adapter.** `annotation/sources/lint.py`
calls `detect_numeric_anchor` directly and identifies findings by a detector
version; the signature change and a detector-version bump must land there too, or
historical annotations mis-key.

**Closes pan-disease t107:** its 587 collapse to the genuine residual once A ships;
its project-local `paper:` anchor and reverted `exclude_paths` fold into defaults /
`additional_anchor_patterns`.

## Testing

**Materialize a real regression oracle first.** The audit's `samples/*.jsonl`
holds findings and `results/*.json` holds *aggregates* — not row-level labels. The
plan must produce a stable labeled dataset:

```
finding_id · file · line · number · origin · traceability
           · expected_part_a_outcome ∈ {NotClaim, Exempt, Anchored, Unanchored}
           · expected_reason
```

seeded from the 320 sampled findings (re-labeled per-row) **plus adversarial
controls** — sampling current findings estimates precision but not recall after
broader/narrower rules:

- an empirical prior *inside* a pre-registration (must stay `Unanchored` unless it
  carries its own resolvable source);
- an unrelated citation elsewhere in a multi-source document (must **not** clear a
  distant unsourced number — finding 2);
- a nonexistent `task:t999` (must **not** anchor — finding 5);
- a nonexistent `artifact:`/`input:` path (must **not** anchor — finding 5);
- one genuinely orphaned number inside an otherwise-sourced entity (documented
  Part-A miss: expected `Anchored`, flagged as a B-only case);
- projects with custom `anchor_patterns` / `additional_anchor_patterns`;
- Layer-1 negative fixtures (`3.2 Gb genome` factual vs `516.9 MB download`
  structural) so masking does not overreach.

Then: **pure-unit tests** per outcome, and a **cross-project before/after** run
confirming numeric-anchor drops to ≈ the genuine-orphan rate with survivors
spot-checked as genuinely ungrounded.

## Success criteria

- Structural masking, marked-stipulated exemption, and entity-/local-scoped
  resolvable anchoring each behave as specified, verified against the labeled
  oracle **including** the adversarial controls.
- Residual ≈ genuine orphans + unmarked-ungrounded thresholds — target
  order-of-magnitude drop (e.g. pan-disease 587 → ~tens).
- No candidate clears without resolving; `task:t999`/fabricated paths flag.
- One incidental body anchor never clears distant unrelated numbers.
- **Honest recall boundary:** Part A does **not** guarantee catching an orphan
  number inside an otherwise-sourced entity — that is Part B. Success is measured
  against A's stated promise (declared-provenance presence at the right scope), not
  per-number correctness.

## Open questions

**Part A (resolve in the plan):**
- Stipulated-marker *syntax* (the concrete document-flag key + the section/block
  fence tokens). The *granularity policy* is settled: section/block default,
  section markers fail closed at the next equal-or-higher heading, block markers
  for mixed empirical/parameter sections, document flag reserved for pure-spec
  docs, no template auto-marking.
- Local anchor scope: paragraph vs section.
- Exact preservation set when unifying the two ad-hoc exemption helpers.

**Part B (deferred):**
- Authoring syntax (inline vs sidecar).
- Locator grammar per format (JSON path; feather/parquet column + stable row
  selector — not a positional index).
- **Reproducible-provenance requirements** a task-plus-mutable-path lacks: artifact
  **revision/content hash**, **units**, **rounding/normalization**, and
  **repeated-value ambiguity** (which occurrence a locator means).
- Numeric tolerance policy (exact vs relative epsilon).
- Whether/when to promote specific kinds to "headline numbers must bind."
