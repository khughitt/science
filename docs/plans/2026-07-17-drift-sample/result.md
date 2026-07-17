# Plan correspondence-drift sample — result

**Gate outcome: DEMONSTRATE (material drift at θ = 0.10).**

Run 2026-07-17 against the frozen pre-registration
(`prereg.json`, sha256 `6d270db8…`, rubric commit `2c84ec27`). This record and
the artifacts beside it (`adjudications.json`, `verdicts.json`) make the result
reproducible: `score_run.py` re-probes the drawn plans at their pinned commits and
recomputes everything below.

## Headline

| Quantity | Value |
|---|---|
| n (first look) | 40 |
| mismatches, Manski bounds | k_lo = 22, k_hi = 24 |
| observed mismatch rate | ~55–60% |
| θ (materiality) | 0.10 |
| demonstrate threshold at n=40 | k ≥ 9 |
| gate (both bounds) | **demonstrate** |
| indeterminate | 2 / 40 (5%; ceiling 20%) |
| inter-rater | 92% agreement, Cohen's κ = 0.81 |

Both Manski bounds land on the same side of θ, so the two indeterminates do not
change the outcome (§6.3). The result clears the demonstrate threshold by more
than a factor of two.

## Confusion matrix (normalized claim → adjudicated)

| claim → adjudicated | count | |
|---|---|---|
| active → active | 15 | match |
| draft → active | 15 | **mismatch** (stale under-claim) |
| draft → complete | 4 | **mismatch** (stale under-claim) |
| complete → active | 2 | **mismatch** (over-claim) |
| active → complete | 1 | **mismatch** (over-claim) |
| superseded → superseded | 1 | match |
| active → indeterminate | 1 | indeterminate |
| draft → indeterminate | 1 | indeterminate |

The mass is **stale under-claim**: 19 plans assert `draft` while their promised
deliverables already exist. This is precisely the S1 §2.2 hypothesis — the one the
retracted "2 of 126 complete" count could not see — now measured directly under
blinding.

## Robustness

- **Not a normalization artifact.** 18 of the 22 mismatches claim *literal*
  `draft`; only two rest on the contested `proposed`/`design` → `draft` mappings
  (`0054-task7`, `0077`). Dropping both still leaves k = 20 — demonstrate.
- **Not concentrated in one project.** multiple-myeloma 13/24 (54%),
  natural-systems 8/12 (67%), protein-landscape 1/4. The equal-probability draw
  and predeclared normalization (§5, §6.2a) did their job: the signal is not
  natural-systems' illegal-vocabulary problem leaking in.
- **Not an over-counting artifact.** The adjudicators distinguished *created*
  deliverables from *modified/referenced* files — the reviewer notes in
  `adjudications.json` repeatedly drop pre-existing inputs and modify-targets. A
  minority kept modify-targets (flagged), so the built-deliverable signal is
  genuine.
- **Instrument reliability.** κ = 0.81 across 40 double-adjudications; three
  splits went to a third reviewer (`0017`, `0045`, `0096`).

## Ruling

Per the pre-registered three-way gate (§2, §7): **material drift is demonstrated,
so §5 of the curation-scope certification is RETAINED.** `plan` is admitted as a
correspondence-scoped kind, and the `curation_scope` axis is justified by measured
evidence rather than the retracted usage/status argument. Other correspondence
kinds are ratified individually from here — the sequence the certification's §7
lays out.
