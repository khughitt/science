# Numeric-Claim Provenance Check — Redesign Design

## Status

Proposed. Phased: **Part A** (precision overhaul of the existing `numeric-anchor`
lint) is the near-term implementation; **Part B** (structured, verifiable numeric
claims) is the declared end-state, specified here for forward-compatibility but
deferred to its own cycle.

## Context

The `numeric-anchor` prose lint (`science_tool/prose_lint.py:detect_numeric_anchor`,
wired through `validate/checks/prose_lints.py`) flags a numeric claim in body prose
when no *anchor token* (`task:`, `pipeline/`, `[@`, `data/`, `scripts/`,
`[[wiki]]`) appears in the **same paragraph**. It is `info` severity by default
(promoted to `warn` under `--strict`). It already carries non-trivial exclusion
logic — identifier masking, cell-line / biomedical short-form context, 4-digit
years, bare integers < 100, `Eq. 2` / `Fig 3` structural refs.

Its **goal is valid and valuable**: quantitative claims should be traceable to a
source, especially in an AI-assisted corpus where a figure can be hallucinated,
copied stale, or drift from its origin. But the **mechanism is a weak proxy** —
"is an anchor-token substring present in this paragraph" — and it fails in both
directions:

- **False positives.** A number can be fully traceable (its source declared in
  frontmatter `source_refs: task:tNNN`; the whole entity *is* the interpretation
  of that task) yet flag, because the token isn't repeated in-paragraph.
- **False negatives.** A paragraph can state a *fabricated* number next to a
  valid-looking `[@Paper]` and pass — the token is present, but nothing verifies
  the number actually comes from that source. (This exact failure — an invented
  path satisfying the sibling `artifact:` exemption with no existence check — was
  caught in a 2026-07-18 pan-disease review.)

It also **conflates claim types** (a stipulated `alpha = 0.05` and an empirical
`E = 7.94×` are treated identically) and **scopes provenance to the paragraph**
when provenance lives at the entity.

### Empirical grounding

A cross-project audit (`docs/audits/2026-07-18-numeric-anchor-audit/`) sampled and
classified **320 flagged numbers across 8 domain-diverse projects**:

- **~83% are false positives** — provenance exists at doc/frontmatter scope, not
  in the flagged paragraph (58% cited-elsewhere-in-doc, 25% frontmatter/title).
- **~33% are exempt-by-nature** — structural tokens (11%: model dims, hardware
  IDs, accessions, license/version, file sizes) + stipulated design params (22%:
  alphas, seeds, planned-N, thresholds) need no external source.
- **The genuine "ungrounded number" signal is ~10% and hand-wavy is 3%** — small,
  and clustered in narrative/manuscript entities that restate the project's own
  computed statistics without a task ref, plus a few uncited domain facts.

The corpus is disciplined; the check's *output* is dominated by noise its own
mechanism manufactures. The redesign shrinks the check to its real signal without
masking (no `exclude_paths` hacks — those hide genuine claims alongside noise).

## Goals

- Cut the false-positive mass legitimately — by resolving provenance where it
  actually lives (entity scope) and recognizing the anchor forms the corpus uses.
- Stop flagging numbers that are exempt by nature (structural, stipulated params).
- Keep the genuine ~10% signal firing — ungrounded numbers in entities that
  declare no source.
- Make the check *trustworthy*: when it fires, it means something.
- Pave toward verifiable per-claim provenance (Part B) without building it yet.
- Stay config-native and framework-native; no project-local ledger dependency.

## Non-Goals

- **Which-source resolution and value verification are Part B**, not A. A credits
  "the entity declares *a* source that could cover this number"; it does not check
  *which* source produced *this* number, nor that the value is correct. (Rationale:
  verification is impossible without per-claim binding, and that binding *is* B's
  core — doing it now collapses the phasing.)
- Do not change the check's default severity (`info`) or turn any project red.
- Do not auto-infer a stipulated-param marker from prose; the exemption is
  entity-class-based, not content-sniffed.
- Do not build Part B's authoring surface or verifier in this cycle.

## Decision (phased — "C")

Ship **Part A** as an evolution of `numeric-anchor`; **specify Part B** as the
end-state so A's scope/vocabulary/output choices stay forward-compatible.

---

## Part A — Precision overhaul (near-term, this implementation)

A numeric claim fires **only if it survives all three layers**.

### Layer 0 — "not a claim" (structural masking)

Extend the existing identifier masking to cover the structural leakage the audit
found:

- model dims / hyperparameters in model-name context (`768`, `4096`),
- hardware IDs (`RTX 3070`, `NovaSeq 6000`, `HiSeq 3000`),
- database accession suffixes (`GCST\d+`, etc.),
- license / spec versions (`CC-BY-4.0`),
- file sizes (`4.1 GB`, `516.9 Mb`),
- entity-slug digits and config line numbers.

Mechanical, no author involvement, not a project knob. (Removes ~11%.)

### Layer 1 — type exemption (entity-class)

If the entity's `kind` is **spec-class** (config `spec_class_kinds`, default
`[pre-registration, plan]`), its numbers are design parameters and are exempt from
the external-source requirement. Layer 0 masking still applies; cited priors
inside a pre-reg still resolve via Layer 2, so genuinely-empirical numbers there
are not hidden. (Removes ~22%.)

Mirrors the `capability_scope` precedent: entity-type-aware, positively scoped,
zero per-number authoring burden.

### Layer 2 — provenance resolution (entity scope)

A claim is anchored if the entity declares a source that *could* cover it:

1. **Frontmatter provenance fields** (config `provenance_fields`, default
   `[source_refs, task_links, input]`) containing any `task:` / `cite:` /
   `paper:` / `dataset:` id. **`related` is deliberately excluded** — those are
   topical links to hypotheses/questions, not sources.
2. **A task id named in the title** (`… (t064)`).
3. **Inline / section / doc-body anchor tokens**, with the vocabulary widened to
   what the audit showed missing. `anchor_patterns` defaults gain: `cite:`,
   `paper:`, `dataset:`, `config/`, and inline `\bt\d{3,}\b`.

Scope is the **entity**: if it declares provenance, its non-exempt numbers are
presumed traceable to it. Deliberately coarse — which-source/value is Part B.
(Clears the ~83% cited/frontmatter mass.)

### What still fires (the residual)

A **non-exempt** numeric claim in a **non-spec entity that declares no source and
has no inline anchor**. This is the genuine ~10%. It survives correctly: the
concerning cases (a manuscript restating its own AUCs with no task ref; an uncited
domain fact) are precisely the entities that lack declared provenance, so they
still flag — while interpretation/evidence-line entities carrying
`source_refs: task:tNNN` clear.

Severity stays **`info`** (strict → `warn`), now trustworthy.

### Module boundaries

Extract the resolution into a small **pure module** — `numeric_provenance.py`:

```
resolve(claim, entity_kind, frontmatter, doc_body, config)
    -> Resolution{cleared: bool, layer: 0|1|2|None, source_candidates: list[str]}
```

`detect_numeric_anchor` stays thin and calls it. The `validate/checks/prose_lints.py`
wrapper feeds in the entity `kind` / frontmatter / title it already has (a
signature change: the detector must receive entity context, not just prose). Each
layer is independently unit-testable; `source_candidates` is a first-class return
value (Part B's hook), not a side effect.

### Config surface (all under `prose_lint`)

| key | status | default | purpose |
|---|---|---|---|
| `anchor_patterns` | exists | extended | add `cite:`, `paper:`, `dataset:`, `config/`, inline `t\d{3,}` |
| `spec_class_kinds` | new | `[pre-registration, plan]` | Layer-1 exemption list |
| `provenance_fields` | new | `[source_refs, task_links, input]` | Layer-2 frontmatter fields (excludes `related`) |

Structural masking (Layer 0) is hardcoded — mechanical, not a project knob.

### Forward-compat hook

For each cleared claim the resolver emits `source_candidates` — the declared
source(s) that cleared it. This candidate set is exactly what Part B refines into
a verified per-claim binding.

---

## Part B — Structured numeric claims (end-state spec, deferred)

Specified for forward-compatibility; not built in A's cycle.

### The model

An **optional, per-claim** binding ties a specific value to a specific source
**and a locator** — where in the producing artifact the value lives — so it can be
**verified**, not merely anchored:

```
value 7.94  <-  task:t064  @  results/2026-.../qap.json  · key `enrichment`
```

### Authoring shape (open — B's own cycle finalizes)

Two candidates; only the *contract* is committed now:

- **Inline token** — binding where the number appears (co-located, readable, but
  clutters prose).
- **Sidecar claims block** — a frontmatter/adjacent `{value, source, locator}`
  table with a light inline reference id (clean prose, decoupled).

Leaning sidecar-with-inline-ref.

### Verifier + feasibility boundary

A new check resolves each **bound** claim's locator against its artifact and
confirms the value matches within tolerance — catching the fabricated/stale
number the token-check structurally cannot. **Feasibility boundary (B owns it):**
JSON / feather / CSV / parquet locators are resolvable; PNG / figure values are
not — B must declare those *unverifiable* rather than pretend.

### A → B contract

- **Unbound numbers keep A's behavior** (coarse entity-scope). Binding is opt-in
  per claim — bind only high-stakes headline results, never all 45% of
  internal-results.
- **A's `source_candidates` is B's binding menu** — B refines "entity declares
  `task:t064`" into "this number ← t064 @ this locator, verified."
- **Progressive tightening** — a project can later flip specific kinds (e.g.
  `interpretation`, `evidence-line`) from "entity-scope OK" to "headline numbers
  must be bound," without touching A's engine.

Net: A makes the check *trustworthy*; B makes it *verifying* where it's worth the
effort.

---

## Rollout & severity

The improved check is a strict reduction in false positives, so it ships
**default-on for all projects** with no flag-day — nothing goes red (it only
clears flags). Clean projects (MM30, cbioportal) are unaffected.

**Closes pan-disease t107 for free:** its 587 findings collapse to the genuine
residual once A ships, and its project-local `paper:` anchor pattern / reverted
`exclude_paths` become unnecessary (folded into defaults).

## Testing (audit as regression oracle)

- **Pure-unit tests** per layer (masking, exemption, resolution) with fixture
  entities covering each path.
- **Labeled regression oracle** — the 320 classified findings in
  `docs/audits/2026-07-18-numeric-anchor-audit/`: assert the new check clears
  every `frontmatter-source-covers` / `cited-elsewhere-in-doc` / structural /
  stipulated-param case and still flags every `truly-orphaned` one. Precision /
  recall measured against real data.
- **Cross-project before/after** — re-run across the same 8 projects; confirm
  numeric-anchor drops to ≈ the genuine-orphan rate and spot-check that survivors
  are genuinely ungrounded (guard against new false negatives).

## Success criteria

- Structural + spec-param + entity-scope-covered claims all clear.
- Residual ≈ genuine orphans — target order-of-magnitude drop (e.g. pan-disease
  587 → ~tens).
- Every survivor, on inspection, is a genuinely unsourced number.
- `source_candidates` present on cleared claims (B-readiness).

## Open questions (deferred to B)

- Final authoring syntax for bound claims (inline vs sidecar).
- Locator grammar per artifact format (JSON path, feather column+row selector).
- Numeric tolerance policy for verification (exact vs relative epsilon).
- Whether/when to promote specific entity-kinds to "headline numbers must bind."
