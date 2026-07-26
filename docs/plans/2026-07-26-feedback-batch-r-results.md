# Feedback Batch R — certification results

Measured against `docs/plans/2026-07-26-feedback-batch-r-design.md`. A
prediction in that document is a claim; each is certified or corrected here.

## Suite

Branch `feedback-batch-r`, based on `474bd68f`.

| check | result |
|---|---|
| `science` pytest | **10808 passed**, 7 skipped, 8 deselected |
| `science` ruff | clean |
| pyright (all three trees) | **0 errors, 0 warnings** |
| `science/model` pytest | 1374 passed, **1 failed — pre-existing, see below** |

## D2 certified: the scope boundary was present and unreachable

The design doc claimed `natural-systems` holds its boundary under the canonical
layout while the command read a path that no longer exists. Measured with the
shipped diagnostic:

| project | `scope_source` | resolved path |
|---|---|---|
| natural-systems | `declared` | `entities/specs/0037-scope-boundaries.md` |
| meta | `absent` | — |
| post-acute-infection | `absent` | — |
| evolution | `absent` | — |

Certified. Before this batch every one of these read as "skipped, absent",
including the one where the document exists and is reachable. No project in the
fleet still uses the legacy `specs/` path, so all five commands named in
`fb-2026-07-26-020` currently resolve nothing.

`natural-systems` has no `research-question` spec under either layout — the
2026-04 conventions audit lists `specs/research-question.md`, but it was not
carried through migration. Reported `absent`, which is correct.

## D4 certified, and the filing's magnitude corrected

`fb-2026-07-25-006` reported "2 of 49 anchors". Measured across every
exploration report in the fleet:

| report | identity verified | anchors | unverified |
|---|---|---|---|
| `meta/explore-2026-07-25` (the reported run) | 2 | **54** | 96% |
| `natural-systems/explore-2026-07-11` | 9 | 47 | 81% |

The direction is certified and the magnitude is slightly larger than filed: 54
identifier-bearing anchors, not 49. More useful than either number: **it is not
a one-off.** The second report, from a different project three months earlier,
sits at 81% unverified. Every one of those identifiers previously rendered in
the block exactly like the handful that resolved.

Note what `verified` counts. All 11 fleet-wide verifications are
`already-resolved` — anchors a human had already routed by hand. Zero resolved
freshly by DOI or title against the project corpus. The resolver's automatic
matching contributed nothing on real data; what it did was *report* that fact,
which is the whole point of the verdict.

## Corrections to the design doc

**D4 said unresolved anchors "were checked against the project corpus".** True
but incomplete as written: `mismatch` and `ambiguous` are also `unverified`, and
a mismatch is a *resolved identifier pointing at a different work*. Counting it
as verified would certify the exact misattribution the mismatch check exists to
catch. The shipped `verification` property and its tests state this; the design
doc's phrasing did not.

**D1 needed no fix but did need a second look.** `-002` was already fixed by
`7e2e317b`, but the fix is only load-bearing because `plan_report` accumulates
errors across all blocks before raising. Had it raised on the first bad block,
the "whole report rejected before the first write" guarantee would hold while
the human still fixed long titles one run at a time. Verified by reading, not
assumed from the commit message.

## Not absorbed: `main` is red at `474bd68f`

`science/model` `test_root_and_packaged_migrated_templates_match[pre-registration]`
fails **on `main`**, not on this branch. Batch Q's `94682ae5` added three comment
lines to `templates/pre-registration.md` and did not sync
`science/model/src/science_model/templates/pre-registration.md`.

This is more than a red test. The packaged template is the one that renders when
a pre-registration is scaffolded, so the guidance Batch Q added — telling authors
that `vehicles:` anchors the document's numeric claims and must not be duplicated
into `source_refs:` — does not reach the authors it was written for. The guard
caught a real gap, not a bookkeeping one.

Left for its owner, per the standing rule against absorbing another session's
drift into an unrelated branch.

## Scope note

`fb-2026-07-25-002` was closed without code: already shipped. The fleet-wide
spec-path repair was filed as `fb-2026-07-26-020` rather than folded in — five
commands and the project scaffolder, none of them covered by this batch's tests.
