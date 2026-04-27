---
name: statistics-prereg-defensive-instrumentation
description: Use when pre-registering a test that selects a winner among multiple candidates, depends on frozen inputs, or could produce a result that "looks too good" — covers universe-locking, candidate-snapshot freezing, familywise nulls, leakage hedges, suspicious-result tripwires, and locked decision tables.
---

# Pre-Registration Defensive Instrumentation

Use when a pre-registered analysis (a) compares multiple candidate
operationalisations and selects a winner, (b) depends on input data that
could drift between pre-reg and run, or (c) could produce a "too good
to be true" headline that needs catching at runtime rather than after
publication.

A normal pre-registration says *what will be computed and how it will be
interpreted*. Defensive instrumentation adds the scaffolding that lets a
follow-up reader trust the run was honest: the universe didn't shift,
candidates weren't tweaked after results, multiple comparisons weren't
exploited, leakage didn't generate the win, suspicious outputs were
caught before being interpreted, and the decision was locked before
the data was seen.

Each technique below is independent — adopt the ones whose failure
mode applies. The full set is appropriate for confirmatory tests where
the result will be used to update a hypothesis verdict.

## The Six Instrumentation Techniques

### 1. Universe lock

The set of records the analysis runs on is computed at pre-registration
time, frozen to a file, and hashed. The runner re-derives the universe
at runtime and aborts on mismatch.

- **Locked file:** `<run-dir>/eligible-<unit>.json`, sorted IDs.
- **Recorded:** SHA256 of the sorted ID list, expected count, source
  filters used to derive it.
- **Runner check:** re-derives the universe from current inputs and
  asserts hash + count match. Aborts on drift.

Catches: silently expanded cohorts, source-data revisions between
pre-reg commit and run, off-by-one filter edits.

### 2. Candidate-snapshot freeze

If the test compares N candidate operationalisations (partitions,
feature sets, model variants, threshold settings), each candidate is
serialised to its own file and committed at a specific SHA *before any
criterion value is computed for any candidate*.

- **Locked files:** `<run-dir>/candidates/<name>.json`, one per
  candidate, with SHA256 recorded in a manifest.
- **Pre-reg lists:** the manifest hash, the per-candidate hashes, and
  the freeze commit SHA.
- **Runner check:** loads candidates only from the manifest; rejects
  unlisted files in the directory.

Catches: candidates being tweaked after the criterion was peeked at,
late-added candidates that escape the multiplicity correction, copy-
paste edits that don't survive code review.

### 3. Familywise null over candidates

If N candidates are compared and the test selects the winner, the null
distribution must be computed over the **best-of-N** statistic, not
per-candidate. Otherwise the headline p-value is uncorrected.

- **Per-iteration:** draw N matched-shape random candidates from the
  locked universe, compute the criterion for each, take the
  `min` (or `max`) z-score across the N.
- **Reference distribution:** the K-vector of best-of-N values.
- **P-value:** rank of the observed best against the K-vector.

Catches: the "best partition wins p < 0.01 per-candidate but the
familywise distribution shows the best random partition does too"
failure mode.

### 4. Leakage hedge

If any candidate's input features overlap with the criterion's input
features (e.g. a primitive-cooccurrence partition compared on
primitive-derived lenses), the test is run a second time on a
feature-set that excludes the overlap. The candidate is required to
win **both** the primary and the hedge to count as a confirmatory win.

- **Primary feature set $F_{\text{primary}}$:** locked at pre-reg.
- **Hedge feature set $F_{\text{hedge}}$:** $F_{\text{primary}}$ minus
  every feature derivable from any candidate's inputs.
- **Decision criteria:** `confirmatory_win` requires passing both;
  primary-only passes are labeled `leakage_suspect`.

Catches: trivially-true wins where the candidate predicts the criterion
because they share inputs.

### 5. Suspicious-result tripwires

The pre-reg names the failure modes that look like a victory but
indicate a bug, and the runner aborts (or flags) when any fires. At
minimum:

| Tripwire | Threshold | Action |
|---|---|---|
| Variance collapse in null | per-candidate $\sigma <$ named floor | abort, halt verdict |
| Implausible separation | $|z| >$ named ceiling (often 10) | abort, audit code path |
| Input-hash drift | any input file's hash changed | abort, require re-pre-reg |
| Library substitution | imported version differs from pre-reg | abort, lock and rerun |
| Metric explosion | criterion outside its theoretical range | abort, audit metric impl |

Tripwires are the most consequential of the six: they convert "the
result is suspect" from a narrative judgement made after the fact into
a hard halt at runtime. Pick thresholds at pre-reg time; adjusting them
after seeing data invalidates the test.

### 6. Locked decision criteria

Every plausible outcome maps to a verdict label, written before any
criterion is computed. The table is exhaustive: every combination of
which candidate wins, whether the hedge passes, whether tripwires
fired, and what the familywise p-value range is, has a row.

```text
| outcome | verdict | hypothesis update |
|---|---|---|
| confirmatory_win, candidate=facet, hedge passes      | facet privileged | keep framing; name axis |
| confirmatory_win, candidate=relational, hedge passes | relational privileged | re-anchor on relational |
| confirmatory_win, candidate=overlapping, hedge fails | leakage_suspect | treat as null |
| tie_at_top                                           | no unique winner | flag tension |
| null (best p_fw > α)                                 | null | weaken the strong reading |
| tripwire fired                                       | halted | re-pre-reg after fix |
```

Locking the table forces the implications-of-each-outcome conversation
to happen before the data is seen — preventing post-hoc verdict
selection.

## Anti-Patterns

- **Per-candidate p-values reported as the headline** when N candidates
  were searched. Use the familywise null instead.
- **Late-added candidates** that "felt obvious" after seeing partial
  results. Either rerun the entire familywise null with the new N, or
  file a fresh pre-reg.
- **Tripwire thresholds picked after the run** ("we set the variance
  floor to ε that lets our run through"). Threshold is part of the
  pre-reg; adjusting it is an amendment, not a sensitivity.
- **Universe re-derived silently** because a source file changed
  between pre-reg and run. Either lock the source or hash-pin.
- **Decision-criteria table missing rows** ("we'll figure out what to
  do if the hedge fails when we get there"). Every row must exist
  before the run.
- **Leakage hedge added retroactively** when the primary result looks
  too clean. Hedge is locked at pre-reg.

## When To Skip Some Techniques

| Situation | Can skip |
|---|---|
| Single candidate, no selection | (3) familywise null, (4) leakage hedge |
| No feature overlap between candidate and criterion | (4) leakage hedge |
| Inputs immutable / single-source / version-pinned | weaker form of (1), (5)'s drift row |
| Exploratory analysis (no verdict update) | most of the above; document as exploratory |

The skip rule is structural — *can the failure mode arise here?* — not
convenience.

## Worked Example

A reference implementation of the full set is the natural-systems-guide
project's `t342` partition test:

- Universe lock: `pipeline/t342/eligible-models.json` + SHA256, runner
  asserts on hash and count (n=172).
- Candidate freeze: 6 partitions in
  `pipeline/t342/partition-snapshots/`, manifest committed at a
  pre-reg SHA, each snapshot SHA-recorded in the pre-reg.
- Familywise null: K=1000 iterations, best-of-6 min-z, per-iteration
  matched fiber-size distribution.
- Leakage hedge: primary lens-set $L_{\text{nb}}$ (6 lenses); hedge
  $L_{\text{hedge}}$ (4 lenses) excludes the two primitive-derived
  lenses, since one candidate is primitive-cooccurrence.
- Suspicious-result tripwires: variance floor $\sigma > 10^{-3}$,
  $|z|$ ceiling 10, hash drift abort, library substitution check.
  *Caught a real lens-deduplication bug mid-run* via cross-comparison
  with the sensitivity output, before the bug-suspect result was
  interpreted.
- Decision-criteria table: 7 rows covering confirmatory wins for each
  candidate type, leakage-suspect, tie, null, and halted.

The test produced a `null` verdict (best $p_{fw} = 0.46$) — and the
discipline of writing the verdict-mapping table before seeing the
data made the null a defensible, hypothesis-updating outcome rather
than a disappointing one.

## Companion Leaves

- [`prereg-amendment-vs-fresh`](./prereg-amendment-vs-fresh.md) — when
  a tripwire fires or universe drift is discovered, this decides
  whether to amend or write a fresh pre-reg.
- [`sensitivity-arbitration`](./sensitivity-arbitration.md) — for the
  *non-verdict-bearing* sensitivity layer that complements a
  defensively-instrumented confirmatory test.
- [`replicate-count-justification`](./replicate-count-justification.md)
  — for choosing K in the familywise null and locking it as a
  pre-registered parameter.
- [`power-floor-acknowledgement`](./power-floor-acknowledgement.md) —
  for interpreting a null verdict from a defensively-instrumented
  test.
