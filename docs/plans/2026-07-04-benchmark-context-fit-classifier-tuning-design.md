# Benchmark Context-Fit Classifier Tuning Design

## Context

The first durable context-fit calibration pass
(`docs/reports/benchmark-context-fit-calibration-pass-1-2026-07-04.md`)
recommended **classifier tuning**. The sharp signal was not fallback volume by
itself; it was that `23` `direct-fit` / `adjacent-fit` gap candidates carried
cross-context warnings, all in the `cbioportal` project and all involving
`dataset:cptac-gbm-2021-proteogenomics` with
`cross-disease:gbm-vs-breast`.

The current classifier assigns `direct-fit` when both predicates are true:

- `strong_context`
- `task_signal`

It computes warning cues separately (`cross-disease`, `cell-line-vs-primary`,
`simulated-vs-observed`), but the direct-fit branch runs before warnings can
constrain the label. That lets a benchmark with useful modality/task evidence
and some shared context remain `direct-fit` even when a specific disease cue
says the benchmark and project/entity contexts are mismatched.

## Goals

- Reduce misleading `direct-fit` rows when specific cross-context warnings are
  present.
- Preserve legitimate direct-fit rows where the project/entity explicitly
  matches the benchmark disease, source dataset, or study context.
- Keep raw matching, candidate scoring, fallback selection, and benchmark
  metadata unchanged.
- Keep `context_fit_warnings` visible. This slice changes classification
  behavior, not warning generation.
- Add focused regression coverage around the observed `cbioportal` /
  CPTAC-GBM failure mode.

## Non-Goals

- Do not add embeddings, ontology lookup, network calls, or semantic matching.
- Do not alter `candidate_score`, `relative_score`, or fallback candidate
  selection.
- Do not rewrite commons benchmark metadata.
- Do not make `cross-disease` smarter with disease ontology equivalence.
- Do not hide warned rows from JSON or tables; they should remain visible under
  their corrected context-fit label.

## Recommended Approach

Add a direct-fit safety gate inside `_context_fit_for_row(...)`.

The classifier should continue computing:

- `shared_specific` from project/entity context tokens intersected with
  benchmark context tokens;
- `task_reasons`;
- `predicates.warning_cues`.

Then, before returning `direct-fit`, classify rows with specific cross-context
warnings as **not direct** unless they have an explicit direct-context override.

### Cross-Context Warning Set

For v1, direct-fit-constraining warnings are:

- `cross-disease:*`
- `cell-line-vs-primary`
- `simulated-vs-observed`

Treat this as a small helper, not a new public vocabulary:

```python
def _direct_fit_blocking_warnings(warnings: Sequence[str]) -> list[str]:
    ...
```

The helper should use explicit prefixes / values and fail closed when the list is
empty: no warning means no direct-fit demotion.

### Direct-Context Override

A row with blocking warnings can still be `direct-fit` when the entity/project
has explicit same-context evidence for the benchmark. V1 should keep this
deterministic and token-based.

Allow direct-fit despite blocking warnings when at least one of these is true:

1. The shared specific context includes the benchmark-side warning token.
   Example: warning `cross-disease:gbm-vs-breast`, and `shared_specific`
   contains `gbm`.
2. The entity tokens explicitly include the benchmark disease/source token.
   Example: a cBioPortal question specifically about GBM or CPTAC-GBM.
3. The shared specific context includes a source-dataset/study token that is not
   merely a broad project token.
   Example: `cptac-gbm`, `gbm`, or another concrete study/source token, not just
   `cancer`, `omics`, `dataset`, or `cbioportal`.

Do **not** use task support, task readiness, or modality overlap as an override.
Those are task/actionability signals, not proof that the context mismatch is
resolved.

### Classification Rule

Replace the effective direct-fit rule:

```text
strong_context and task_signal -> direct-fit
```

with:

```text
strong_context and task_signal and no blocking warning -> direct-fit
strong_context and task_signal and blocking warning and direct-context override -> direct-fit
strong_context and task_signal and blocking warning and no override -> adjacent-fit
```

The demoted row should retain:

- all existing `context_fit_reasons`;
- all existing `context_fit_warnings`;
- an added reason such as `context-warning:demoted-direct-fit` or
  `cross-context:demoted-direct-fit`.

Use one reason string consistently and document it in tests. The recommended
string is `context-warning:demoted-direct-fit`.

## Expected Behavior

### Observed Calibration Cluster

For the `cbioportal` rows in the calibration report:

- `dataset:cptac-gbm-2021-proteogenomics`
- warning `cross-disease:gbm-vs-breast`
- no entity-specific GBM/CPTAC-GBM context

Expected classification after this slice:

- `context_fit`: `adjacent-fit`
- `context_fit_warnings`: still includes `cross-disease:gbm-vs-breast`
- `context_fit_reasons`: includes `context-warning:demoted-direct-fit`

This preserves the benchmark as potentially useful for cross-modal/proteomics
thinking, but prevents it from appearing as a direct benchmark for breast or
pan-cancer data-source questions.

### Legitimate Direct Rows

Rows should remain `direct-fit` when they are explicitly about the benchmark
context.

Examples:

- Entity text mentions GBM/glioblastoma and the benchmark is
  `cptac-gbm-2021-proteogenomics`.
- Entity text mentions CPTAC-GBM or the exact source study.
- Same-disease benchmark rows with strong context and task signal and no
  blocking warning.

### Existing Adjacent Rows

The existing cross-disease adjacent behavior should remain unchanged for rows
that already lack shared specific context. The current BRCA-vs-myeloma test is
still valid: it should stay `adjacent-fit` with its `cross-disease:*` warning.

## Implementation Shape

No public API shape changes are required.

Touch points:

- `science/src/science_tool/benchmark_opportunities.py`
  - add private helpers near `_context_fit_warning_cues(...)` /
    `_context_fit_for_row(...)`;
  - update the direct-fit branch only;
  - keep warning generation unchanged.
- `science/tests/test_benchmark_opportunities.py`
  - add a regression test for warned direct-fit demotion;
  - add a preservation test for explicit benchmark-context override;
  - keep existing context-fit regression tests running.

The implementation should not change CLI option handling or JSON schema. Any
row that changes label will naturally affect `context_fit_counts` and filtered
views.

## Testing

Add focused tests before implementation.

Required tests:

1. **Warned direct-fit demotes to adjacent-fit**
   - Project/entity carries breast or pan-cancer context.
   - Benchmark carries GBM/CPTAC-GBM context.
   - Task signal is present and would otherwise make the row direct.
   - Assert `context_fit == "adjacent-fit"`.
   - Assert `cross-disease:gbm-vs-breast` remains in warnings.
   - Assert `context-warning:demoted-direct-fit` appears in reasons.

2. **Explicit benchmark context preserves direct-fit**
   - Same fixture, but entity text explicitly contains `gbm` or `cptac-gbm`.
   - Assert `context_fit == "direct-fit"`.
   - Assert the warning is either absent if disease tokens now overlap, or still
     present only if the token sets genuinely still disagree.
   - Assert no demotion reason is present.

3. **Existing cross-disease adjacent behavior remains stable**
   - Keep or extend the current BRCA-vs-myeloma regression.

4. **Calibration smoke**
   - Run a targeted `science benchmark gaps --commons --context-fit direct-fit`
     for `~/d/cancer/data-sources/cbioportal`.
   - Confirm the count of warned direct-fit CPTAC-GBM rows decreases from the
     pass-1 baseline.

## Risks and Constraints

- The token-based override must not become a hand-coded list of active projects.
  It should derive from existing benchmark/project/entity tokens.
- `cbioportal` is both a data-source project and a broad cancer project. A
  shared `cbioportal` or `cancer` token alone should not override a GBM-vs-breast
  warning.
- If the implementation cannot distinguish benchmark-side warning tokens from
  project-side warning tokens cleanly, prefer a narrow parser for existing
  warning strings over a broad new inference path.
- Because this is classifier tuning, some aggregate counts will change. The
  implementation plan should include before/after smoke output rather than
  expecting exact global counts across all projects.

## Alternatives Considered

### Presentation-Only Suppression

Keep labels unchanged but sort or hide warned direct-fit rows. Rejected because
it leaves a misleading `direct-fit` label in JSON and filtered views.

### Metadata Enrichment First

Add richer disease/source metadata to benchmark records and rely on current
rules. Useful later, but it is slower and does not address the classifier rule
that currently ignores blocking warnings during direct-fit assignment.

### Demote All Cross-Disease Rows

Any `cross-disease:*` warning would prevent `direct-fit`. Rejected because a
data-source or pan-cancer project may have entities explicitly about the
benchmark disease/source; those should still be direct when the entity provides
the missing context.

## Success Criteria

- `cbioportal` no longer reports CPTAC-GBM as direct-fit for breast/pan-cancer
  entities that only have cross-disease warning evidence.
- Legitimate GBM/CPTAC-GBM entities can still produce direct-fit rows.
- Existing context-fit tests continue to pass.
- No CLI contract, JSON schema, scoring, or commons metadata changes are
  required.

## Ideal Architecture / Deferred Keystone

This slice is a scoped patch, not the terminus. It should ship as a **down
payment** on a typed context-fit refactor, recorded here so the *next* axis
request triggers the keystone rather than another override tangle.

### Root cause this patch does not remove

Context-fit flattens each side into **one undifferentiated token bag**, then
derives the label from bag intersection (`strong_context = project ∩ benchmark
≠ ∅`) while computing warnings **per-axis** (disease, sample, sim) separately.
The label decision and the warning decision read the data through two
incompatible lenses. The failure modes found while reviewing this design are all
symptoms of that single flattening:

- **Self-defusal.** Disease "match" and disease "absent" collapse into the same
  state — a bag either contains `gbm` or it does not, so there is no "the entity
  is silent on disease" state. The cross-disease warning (`_context_fit_warning_cues`,
  keyed on disjoint disease-token sets) therefore disappears the moment any
  entity/project token supplies the benchmark disease, which is why the
  disease-token override rules in this design are structurally unreachable.
- **`cptac-gbm` vs `gbm` brittleness.** Source-study identity and disease
  identity share one namespace. Because the tokenizer (`_TOKEN_RE =
  [A-Za-z0-9:_-]+`) keeps hyphens, a compound token is the *only* thing keeping
  the source study distinct from its disease.
- **`cbioportal` shared-token hazard.** Project *identity* tokens live in the
  same bag as *context* tokens, so a project name pollutes context matching and
  forces the "not merely a broad project token" carve-out.

Override rules cannot fix these, because they read the same flattened bag that
lost the distinctions.

### Target model

Represent each side as a structured `ContextProfile` — one axis at a time — the
same SSOT move already made for evidence types, kind descriptors, and belief
policy:

```text
ContextProfile:
  diseases:       frozenset[DiseaseTerm]     # gbm, breast, pan-cancer
  sample_types:   frozenset[SampleType]      # cell-line | primary | pdx | simulated
  modalities:     frozenset[Modality]
  source_studies: frozenset[SourceStudy]     # cptac-gbm-2021  (its OWN axis)
  domain:         frozenset[DomainLabel]
```

Each axis yields a **typed relation**, not disjoint-or-silence:

```text
AxisRelation = match | mismatch | subsumes | subsumed-by | unknown
```

The three states the current disjointness test cannot express are exactly the
ones that matter: `mismatch` (breast vs gbm), `unknown` (entity silent on
disease), and `subsumes` (pan-cancer ⊇ gbm). The label then becomes a **pure
function of the per-axis relation vector**, governed by a declared,
identity-stamped policy object (mirroring the `BeliefPolicy` keystone), e.g.:

> `direct-fit` requires `disease ∈ {match, subsumes}` **and** `sample ∈ {match,
> unknown}` **and** task-signal; a `disease:mismatch` demotes to `adjacent-fit`
> **unless** `source_study:match` overrides.

Per-axis relations are emitted as reasons (`disease:mismatch(gbm-vs-breast)`,
`source-study:match(cptac-gbm-2021)`, `sample:unknown`), so the label is
*derivable from the reasons* and tests assert on axis relations rather than
token strings.

### Why the typed model dissolves the failure modes

- The source-study override becomes a real relation vector (`disease:mismatch,
  source_study:match`), not a token-bag contradiction. Warning generation and
  label decision read the *same* typed axes, so they cannot disagree.
- Self-defusal disappears: a genuine GBM entity is `disease:match`, a silent
  entity is `disease:unknown`, and both are distinct from `mismatch`.
- The `cbioportal` hazard vanishes structurally — project identity is not a
  context axis, so it never enters axis comparison. A data-source / pan-cancer
  project declares `diseases: {pan-cancer}` → `disease:subsumes`, legitimately
  direct *without* a hand-coded stoplist.
- Test conflation cannot recur: each axis relation is asserted by its own test.

### Vocabulary sourcing

"Metadata Enrichment First" (see Alternatives Considered) is **not an
alternative** to this refactor — it is its prerequisite input. Axis extraction
should read *declared structured fields first* (commons benchmark records
already carry `domains` / `source_datasets`; entities carry structured
frontmatter) and fall back to lexical extraction only for free prose.

The offline / deterministic principle is preserved: comparing *typed* axis
values needs no embeddings or network. The one place an ontology helps is the
`subsumes` relation (GBM ⊂ glioma ⊂ CNS tumor; pan-cancer ⊇ any) — and that is a
**bundled static asset**, not a lookup service. So the ideal stays faithful to
"no network, deterministic"; it needs typed inputs plus one shipped ontology
file. (This is where the current `cross-disease` ontology non-goal is
deliberately relaxed.)

### Staging (keystone + slices)

- [ ] **Keystone** — typed `ContextProfile` + `AxisRelation`, extracted from
  existing tokens; behavior-neutral, label logic unchanged, relations emitted as
  reasons only.
- [ ] **Slice A** — move the disease axis onto relations; folds in the current
  cross-disease warning and this design's demotion as legible three-state logic.
- [ ] **Slice B** — source-study as its own axis; retires the compound-token
  brittleness.
- [ ] **Slice C** — declared combination policy object; sample / modality /
  domain axes migrate onto it one at a time.
- [ ] **Later** — structured-metadata-first extraction; bundled ontology asset
  for `subsumes`.

### Go / no-go

The scoped patch in this document is correct *if context-fit is done growing
axes*. It is not — it already carries disease, cell-line, simulated, and
domain-conflict, and this toolkit's trajectory is to keep hardening exactly these
classifiers. Every new warning axis under the current design is another override
tangle like the one this review surfaced. The keystone is the point where each
new axis becomes a **data addition, not a control-flow addition**.

Recommendation: **ship the scoped patch now** (source-study override + split
tests), and trigger this keystone when the *next* context axis is requested —
not speculatively on this one cluster of 23 rows.
