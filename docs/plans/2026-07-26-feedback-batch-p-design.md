# Feedback Batch P — the correspondence-drift cluster, lifted markers, and the kind vocabulary

**Status:** design, 2026-07-26. Successor to
[`2026-07-26-feedback-batch-o-design.md`](2026-07-26-feedback-batch-o-design.md).

Six downstream filings. Four of them (`fb-2026-07-26-013/014/015/016`) are one
cluster against `check:plan.correspondence-drift`, filed together by
natural-systems from a single 55-warning sweep; the other two are independent.

## Owner decisions

- **D1 — `resolve_task` reads the shipped archive format.** The glob is replaced
  by a status-aware reader that lives beside `known_task_ids` in `tasks.py`, so
  the context-budget slice-3 centralization has one place to re-point.
- **D2 — an unresolvable or off-axis task ref is a fact about the instrument.**
  `probe.py`'s module docstring already rules that `unknown is not absent`;
  Batch P applies the same rule to task refs instead of letting them masquerade
  as evidence of unstartedness.
- **D3 — deliverables are read, not guessed.** Extraction is scoped to a
  declared deliverables region. A plan with no such region declares nothing
  probeable and the screen stays silent (§6.3). This trades recall for
  precision, deliberately — see "What D3 costs" below.
- **D4 — polarity comes from the same declaration.** A removal-shaped section
  inverts its probes, so a retirement plan is scored in the direction it is
  actually measured in.
- **D5 — `fb-2026-07-26-013` lands in `probe.py` now**, not folded into the
  slice-3 plan. Slice 3 has zero implementation commits, and it keeps closed
  tasks in `tasks/done/YYYY-MM.md`, so a correct reader stays correct across the
  split.

## Baseline (measured before any change)

`check:plan.correspondence-drift` run over every project on disk that has
plans, using this branch's code at `e4fbc201`:

| project | plans probed | warnings | adjudications | task states |
|---|---|---|---|---|
| natural-systems | 103 | 2 | active 89, complete 7, draft 6, indeterminate 1 | active 98, **missing 81** |
| protein-landscape | 12 | 6 | active 8, complete 4 | active 1 |
| health/meta | 5 | 1 | active 2, draft 3 | missing 3 |
| 3d-attention-bias, cats, seq-feats, science/meta | 0 | 0 | — | — |

**Zero tasks resolve `done` anywhere in the fleet**, which is `-013` confirmed
by measurement rather than by reading: `TaskState.DONE` is unreachable, so
`Adjudicated.COMPLETE` is unreachable for any plan that cites a task.

Note the fleet total is 9 warnings, not the 55 the report describes — the
reporting project adjudicated and corrected its statuses after filing. The two
that remain in natural-systems are precisely the two verified false positives
`-015` names.

## Per-filing verdicts

### fb-2026-07-26-013 — `resolve_task` cannot see the shipped archive format

**Confirmed.** `correspondence/probe.py:50` is
`done_dir.glob(f"{task_id}*.md")`; `tasks_archive.py` routes terminal entries to
`tasks/done/YYYY-MM.md` month rollups. natural-systems' `tasks/done/` holds
exactly `2026-03.md` … `2026-07.md`, and 81 of its 179 task refs resolve
`missing` as a result.

The report's pointer to `refs.py::_load_task_ids` is right about the parser and
slightly wrong about the target: `_load_task_ids` is header-only and returns
bare ids without status, which cannot distinguish `DONE` from `ACTIVE`. The
right reuse is `tasks.py`'s own search-path helper plus a status-bearing scan.

**Fix.** `tasks.py` gains `task_status_index(tasks_dir) -> dict[str, str]`,
built from `_task_search_paths` (active.md + done/*.md) with the same
header-only-plus-one-field discipline `known_task_ids` documents: a field-level
problem in one block must not crash a caller that only needs the index.
`resolve_task` consumes it.

### fb-2026-07-26-014 — deliverable probes have no polarity

**Confirmed.** `probe_path` (`probe.py:36-43`) maps exists→PRESENT and
missing→ABSENT unconditionally, and `adjudicate` reads PRESENT as progress. A
retirement plan is therefore scored backwards, and the remediation it prints
would move a complete plan backwards.

**Fix.** Polarity is carried on the probe request, sourced from D4's
removal-shaped section. An inverted probe reports PRESENT when its target is
*gone*. The `Probe.detail` string names the polarity so the evidence line stays
auditable.

### fb-2026-07-26-015 — every backticked path becomes a deliverable

**Confirmed, and the two named cases were re-verified against the tree.**

`entities/plans/0037-provenance-schema-integration-plan.md` is the sharper of
the two than the report suggests: the plan **has** a `## Suggested deliverables`
section, and that section contains **no** backticked paths at all. Every path
the extractor found (lines 40–50) sits under `## Recommended reading order`.
The instrument ignored the plan's own declaration and harvested its reading
list.

`entities/plans/0097-meta-model-v0-3-consolidation.md` has no
deliverables-shaped section at all; its extracted paths sit in the preamble and
under `### Task N` headings.

**Fix.** D3. Measured consequence: `0037` extracts nothing and goes
indeterminate; `0097` declares nothing and goes indeterminate. Both false
positives disappear for the right reason rather than by suppression.

#### What D3 costs

Deliverables-shaped headings, measured across the fleet:

| project | plans with a declared region | total plans |
|---|---|---|
| natural-systems | 34 | 109 |
| protein-landscape | ~2 (noisy matches) | 19 |
| health/meta | 0 | 7 |

So the screen goes quiet on roughly 70% of plans until they declare. That is the
intended trade: an advisory screen whose only remedy for a false positive is a
permanent per-file suppression must be high-precision, and silence on an
undeclared plan is an honest statement that the plan declared nothing probeable.
Recall becomes opt-in — a project that wants the screen adds a `## Deliverables`
section, which is a convention 31% of natural-systems plans already follow.

### fb-2026-07-26-016 — the remediation line reads as an estimate

**Confirmed verbatim** at `validate/checks/correspondence_drift.py:48`.
`adjudicate` is a three-branch classifier whose else-branch is ACTIVE, so
`active` is a lower bound, not a measurement.

**Sequencing matters here.** Rewording to "the true status is at least X" while
`-013` leaves COMPLETE structurally unreachable would advertise a bound the
instrument cannot compute — tuning the report instead of the instrument. `-013`
lands first.

### fb-2026-07-26-012 — `refs check` ignores lifted markers

**Confirmed.** `validate/checks/unresolved_markers.py:43,60` imports
`markers_cli._filter_lifted` and applies it to `scan_markers()`; `refs.py` has
no lifted filter anywhere. The `.anno.trig` sidecar is the record of a
deliberate adjudication, so honouring it is the correct direction.

This is the downstream half of Batch O's `fb-2026-07-26-001`: `MarkerHit` now
carries the exact matched `literal`, which is what makes filtering payload-form
`[TOKEN: reason]` markers correct rather than silently lossy.

### fb-2026-07-26-017 — no way to enumerate the canonical kinds

**Confirmed.** `science entity` exposes fourteen subcommands and none of them
prints the kind vocabulary; nothing else in the CLI does either. The report is
right that `fb-2026-07-11-007` fixed the instance (one command's prescribed
prefix) and not the class, and that the class has now recurred with `dataset:`.

**Fix.** Option 1 from the report: `science entity kinds`, reading
`CORE_PROFILE.entity_kinds` plus the project's local profile, with `--format
json` so a downstream `commitlint.config.mjs` becomes generated rather than
transcribed.

## Not in this batch, and why

- **`fb-2026-07-26-010` (kind:paper pre-read status) and `-011` (kind:plan
  readiness axis)** collide with the reverse-lineage-gate S2 plan, which
  re-rules status vocabularies and re-freezes `FROZEN_STATUS_VALUES` /
  `FROZEN_DEFAULT_STATUS`. `-011` additionally runs into a standing ruling
  (`core.py:459-462`: kind:plan carries no semantic axis, and `proposed` was
  deliberately refused as synonym drift), so the readiness verdict belongs on a
  separate declared field. Both sequence after S2.
- **`fb-2026-07-26-005`'s remainder** (`hint_for` returning a bare relative
  filename) is unclaimed by all three in-flight designs and needs the unbuilt
  state tier.
- **`fb-2026-07-22-001/002` and `fb-2026-06-28-004`** sequence after the
  vcs-boundary design, which supplies the declared-roots classification they
  each need.

## Certification

Every fix is certified against the fleet baseline above, not against assertion:

1. RED-first tests for each behavioural change.
2. Re-run the fleet probe and record the delta per project.
3. For `-013`, the falsifiable prediction is that natural-systems' 81 `missing`
   task states become mostly `done` and that `COMPLETE` becomes reachable.
   **A prediction in a design doc is a claim; it is recorded here so it can be
   contradicted by measurement** — see Batch O, where exactly that happened.

### Measured result

**The `-013` prediction held.** After the task-resolution fix alone,
natural-systems' task states moved from `81 missing / 98 active` to
`150 done / 28 active / 1 unknown` — **zero missing** — and `COMPLETE`
adjudications rose 7 → 23. The 70 states that moved `active` → `done` are the
second half of the same defect: any mention of an id anywhere in `active.md`,
including inside another task's `related:` list, used to read as ACTIVE.

Fleet warnings across the two changes, which push in opposite directions:

| stage | natural-systems | protein-landscape | health/meta | total |
|---|---|---|---|---|
| baseline | 2 | 6 | 1 | **9** |
| after `-013` (task resolution) | 11 | 6 | 1 | **18** |
| after `-015`/`-014` (declared regions) | 2 | 1 | 0 | **3** |

The count returning to roughly where it started conceals a full substitution of
content. Plans probed at all fell 103 → 20 in natural-systems (only those that
declare deliverables), and:

- Both verified false positives are gone. `0037` and `0097` no longer appear.
- Both surviving natural-systems warnings are **new, and true**.
  `0068-t251-hh-fit-workflow-plan.md` claims `active`; all seven paths under its
  `## Workflow Outputs` heading exist on disk and both cited tasks resolve
  `done`. That finding was unreachable before, because `COMPLETE` was.

So the screen speaks about a fifth as many plans and is right when it does — the
trade D3 was chosen for, confirmed by measurement rather than asserted.

### Two things the fixes exposed

- **The acceptance guard held a second copy of the signature version.**
  `validate/acceptance.py` hardcoded `v1:` in its matcher, so bumping the
  signature would have left a guard that kept honouring stale entries — the
  version would have been decorative. It now derives the pattern from
  `SIGNATURE_VERSION`, and a test asserts a v1 token is rejected.
- **`-014` has no consumer in the fleet.** The verified retirement plan
  (`0018-a5-guide-unification.md`) has no deliverables-shaped heading at all, so
  D3 already silences it. Polarity is shipped because silence is not a fix for
  "scored exactly backwards" — it only stops the wrong answer. A retirement plan
  can now declare `## Retirement targets` and be screened correctly, which is
  the difference between unscoreable and scoreable.

### Pre-existing failures, not absorbed

`tests/validate/` followed by `tests/test_correspondence_drift_health_integration.py`
fails two tests through an ordering interaction that empties the validation
findings list. **Verified identical on `main`** at `e4fbc201`; both modules pass
in isolation. Not this branch's regression and not fixed here.
