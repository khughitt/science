# Feedback Batch T — certification results

Measured against `docs/plans/2026-07-26-feedback-batch-t-design.md` and
`docs/plans/2026-07-27-feedback-batch-t-plan.md`. This document records the
Task 6 corpus certification, the Task 7 filing closures, and branch-wide
verification.

## `prereg.schedule-calibration-domain` corpus certification

### Measurement method

The validator ran against every project in the measured fleet that holds
pre-registrations. Each complete report was retained as JSON under `/tmp`, and
findings were selected by exact `rule` equality. No rendered-output substring
count was used:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science
for p in ~/d/natural-systems ~/d/3d-attention-bias ~/d/protein-landscape ~/d/seq-feats; do
  uv run --frozen science validate --project-root "$p" --format json \
    --output "/tmp/batch-t-$(basename $p).json"
done
uv run --frozen python - <<'PY'
import json, glob
for path in sorted(glob.glob("/tmp/batch-t-*.json")):
    payload = json.load(open(path))
    hits = [r for r in payload["results"]
            if r.get("rule") == "prereg.schedule-calibration-domain"]
    print(f"=== {path}: {len(hits)}")
    for r in hits:
        print(f"  {r.get('path')}\n    {r.get('message')}")
PY
```

The JSON artifacts were:

- `/tmp/batch-t-natural-systems.json`
- `/tmp/batch-t-3d-attention-bias.json`
- `/tmp/batch-t-protein-landscape.json`
- `/tmp/batch-t-seq-feats.json`

### Initial measurement

The design's survey predicted five findings in natural-systems and none in the
other three projects. Exact-rule selection reproduced that prediction:

| project | pre-registrations | expected | actual |
|---|---:|---:|---:|
| natural-systems | 34 | 5 | **5** |
| 3d-attention-bias | 4 | 0 | **0** |
| protein-landscape | 3 | 0 | **0** |
| seq-feats | 5 | 0 | **0** |

The five initial paths and messages were:

| path | message |
|---|---|
| `entities/pre-registrations/0007-pre-registration-t349-fiber-membership-covering-probe-q100.md` | `entities/pre-registrations/0007-pre-registration-t349-fiber-membership-covering-probe-q100.md declares a sampling schedule but carries no Cost Gate; the schedule's calibration domain is undeclared` |
| `entities/pre-registrations/0025-tractability-filter-confound.md` | `entities/pre-registrations/0025-tractability-filter-confound.md declares a sampling schedule but carries no Cost Gate; the schedule's calibration domain is undeclared` |
| `entities/pre-registrations/0026-fixed-margin-incidence-null-topology.md` | `entities/pre-registrations/0026-fixed-margin-incidence-null-topology.md declares a sampling schedule but carries no Cost Gate; the schedule's calibration domain is undeclared` |
| `entities/pre-registrations/0032-t878-subset-substructure-cycle-rank-frozen-axes.md` | `entities/pre-registrations/0032-t878-subset-substructure-cycle-rank-frozen-axes.md declares a sampling schedule but carries no Cost Gate; the schedule's calibration domain is undeclared` |
| `entities/pre-registrations/0034-arxiv-paper-skeleton-external-suppression.md` | `entities/pre-registrations/0034-arxiv-paper-skeleton-external-suppression.md declares a sampling schedule but carries no Cost Gate; the schedule's calibration domain is undeclared` |

All five source documents are under
`~/d/natural-systems/entities/pre-registrations/`.

### Finding adjudications

#### `0007` — substantively right

The document freezes burn-in at `100 * total_edges` and spacing at
`5 * total_edges`, while describing independence as “best-effort.” It promises
an achieved acceptance-rate diagnostic and post hoc degeneracy bounds, but
records no substrate measurement that calibrated those schedule constants.
The finding correctly identifies an undeclared calibration domain.

#### `0025` — substantively wrong in the initial instrument

This document reports the calibration evidence on its own permutation
substrate, not a schedule borrowed from another geometry. Its “MCMC
diagnostics” table gives four-chain acceptance rates and achieved ESS for every
power-curve value of theta: **1607–3392 effective draws out of 10,000**. That is
the evidence the rule asks for, expressed in a pre-Cost-Gate table.

Certification stopped at this ruling. The instrument was not accepted with a
known false positive. Later review established that prose alone cannot prove
that those diagnostics completed successfully on the same substrate and
authorize the particular schedule the rule found. The owning project therefore
migrated `0025` to an explicit canonical Cost Gate rather than teaching the
validator to infer those relations from prose.

#### `0026` — substantively right

The null remains active and undrawn. The document fixes burn-in/thinning at
`5x / 1x` incidence ones and explicitly says those constants are heuristics
with no theoretical warrant on its non-half-regular margins. `R_hat < 1.01`
and ESS at least 400 are future execution gates, not achieved calibration
evidence. The finding is right.

#### `0032` — substantively right

The feasibility harness is genuine evidence, but it is not achieved target-run
certification. `pipeline/t878/feasibility-report.md` measures three chains and
`B=800` on the 163-node/96-edge typed graph, obtaining worst-cell
`tau=119.9` and proposing thinning 6000 attempts and burn-in 60000. The frozen
confirmatory plan instead uses adaptive `B>=2000` and does not declare the
confirmatory chain/concurrency geometry or the transfer boundary from the
feasibility geometry. The document therefore has useful pilot evidence but
does not fill the Cost Gate's target-geometry and calibration-domain
obligation. The finding is right.

#### `0034` — substantively right

This is the reported incident. The document imports `0026`'s `5x / 1x`
schedule onto an 8,010-row, 368,836-one arXiv incidence. Its own runs then
demonstrate the mismatch rather than certify it: first `R_hat=1.159`,
`ESS=8.6`, then `R_hat=1.0162`, `ESS=88`. Amendment 3 proposes a further
thinning increase with target ESS about 800, but records no accepted run at
that schedule. The failed achieved diagnostics must not become an escape hatch.
The finding is right.

### Rejected heuristics and structural resolution

Two attempted prose exemptions were rejected.

The first, in `4c9511ea`, treated a numeric markdown `ESS (of N)` row as
sufficient evidence. The same row can state a prospective target, report a
failed run, or belong to an unrelated analysis.

The second, in `d32adf98`, required an executed Outcome heading, a Power
section, MCMC-diagnostics prose, numeric power/CI/acceptance/ESS rows, an
achieved-power conclusion, and the absence of several failure phrases. That
conjunction was still unsound. It could not distinguish:

1. a prospective Power target after an unrelated executed outcome;
2. completed pilot diagnostics from a different substrate;
3. a failed calibration described with a failure phrase outside the blacklist;
4. completed Power calibration plus a separate future schedule elsewhere in
   the same document.

No document-level prose pattern can mechanically bind calibration completion,
diagnostic success, substrate/geometry identity, and authorization of the
specific schedule the rule detected. The final validator therefore recognizes
no prose exemption: only a present canonical
`## Cost Gate (execution geometry)` with filled `Target geometry` and
`Calibration domain` rows discharges the obligation. A present malformed gate
continues to warn.

#### Owning-project migration

The human authorized a transparent owning-project amendment. In the isolated
natural-systems worktree on branch `fix/prereg-0025-cost-gate`, commit
`d4112f545` (`pre-registration: backfill 0025 cost gate`) changes only
`entities/pre-registrations/0025-tractability-filter-confound.md`.
It is rebased onto owning-project commit `f733755b`, which added the
content-addressed vehicle as post-execution Amendment 3; the Cost Gate backfill
is the distinct post-execution Amendment 4.

The amendment:

- is marked POST-EXECUTION in frontmatter, the document header, the Cost Gate,
  and the Amendment Record;
- says it records already-achieved evidence for validator readability, changes
  no registered quantity, schedule, or verdict, and does not retroactively
  create precommitment;
- records the executed seven-target, four-chain geometry, 20,000 valid-move
  burn-in, 2,500 retained draws per chain spaced every 40 valid moves, and the
  actual 246-node/20-stratum/152-cross-edge/385-within-edge calibration domain;
- records the achieved acceptance/ESS/MCSE evidence and explicitly limits
  transfer and invalidation claims where hardware, library, concurrency, and
  wall-time evidence were not recorded.

The source facts come from the already-committed
`pipeline/t823/calibrate_null.py`, `null-calibration.json`, and
`exact-bounds.json`; no analysis was rerun and no unrecorded execution detail
was invented.

The isolated worktree was initialized against natural-systems' pinned Science
0.5.2 before the amendment. Its clean-base `bash validate.sh --verbose`
produced **574 errors and 102 warnings** (985 findings, first 40 displayed).
Those findings pre-dated this amendment, and the human explicitly authorized
them as out of scope. They were neither repaired nor absorbed into Batch T.

#### Final toolkit RED/GREEN

The `0025`-shaped test was changed first to require a warning when achieved
diagnostics prose has no Cost Gate:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science
uv run --frozen pytest \
  tests/validate/test_checks_prereg_schedule.py::test_achieved_diagnostics_without_cost_gate_warns \
  -q
```

RED was observed under the conjunction heuristic:

```text
FAILED ...test_achieved_diagnostics_without_cost_gate_warns
E assert 0 == 1
E  + where 0 = len([])
```

The implementation then removed both rejected exemptions and all
power-result/failure-phrase machinery. The same command passed GREEN. The
focused module passed 14 tests, including the achieved-prose warning, the
filled canonical gate, and malformed required-row boundaries. The final
toolkit code commit is `06e3b4bc`:
`fix(validate): require explicit schedule cost gates`.

The same implementation produced this exact-rule before/after audit:

```text
unamended 5 [0007, 0025, 0026, 0032, 0034]
amended   4 [0007,       0026, 0032, 0034]
```

The unamended source was a temporary clean detached worktree at committed
owning-project base `f733755b`; the amended source was the persistent isolated
worktree at commit `d4112f545`. The retained JSON reports were
`/tmp/batch-t-control-natural-systems.json` and
`/tmp/batch-t-final-natural-systems.json`. Their path-set difference is exactly
`0025`: no finding was added, and `0034` remains present. The temporary control
worktree was removed after measurement.

### Re-verification and final measured findings

Commands:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science
uv run --frozen pytest \
  tests/validate/test_checks_prereg_schedule.py \
  tests/validate/test_checks_prereg_vehicles.py -q
uv run --frozen pytest tests/validate -q
uv run --frozen ruff check
uv run --frozen pyright
```

Results: **35 focused tests passed**, the **948-test validator suite exited
zero**, full Ruff was clean, and Pyright reported **0 errors, 0 warnings**. The
validator suite emitted only the existing rdflib deprecation warnings.

Final JSON certification used the isolated amended natural-systems worktree:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science
uv run --frozen science validate \
  --project-root ~/d/natural-systems/.worktrees/feedback-batch-t-0025 \
  --format json --output /tmp/batch-t-final-natural-systems.json
uv run --frozen science validate \
  --project-root ~/d/3d-attention-bias \
  --format json --output /tmp/batch-t-final-3d-attention-bias.json
uv run --frozen science validate \
  --project-root ~/d/protein-landscape \
  --format json --output /tmp/batch-t-final-protein-landscape.json
uv run --frozen science validate \
  --project-root ~/d/seq-feats \
  --format json --output /tmp/batch-t-final-seq-feats.json
```

Findings were selected from those four artifacts by exact
`rule == "prereg.schedule-calibration-domain"` equality. Final counts:

| project | expected after adjudication | actual |
|---|---:|---:|
| natural-systems | 4 | **4** |
| 3d-attention-bias | 0 | **0** |
| protein-landscape | 0 | **0** |
| seq-feats | 0 | **0** |

The surviving paths are `0007`, `0026`, `0032`, and `0034`, each with the same
path-specific message recorded above. `0025` is absent. In particular, the
migration did **not** silence `0034`, and no prose inference is capable of
silencing any document.

### Certification domain

This certification measures **one project and one method family**:
natural-systems contributes all five initial cases, all in the MCMC/sampling
schedule family. The other three projects contribute 12 pre-registrations but
declare no such schedules and produce zero findings. The result certifies the
instrument only over that measured domain; it does not claim coverage of other
schedule families or project conventions.

## Design corrections and deferred rule

The design correctly identified `0025` as the honest risk but its proposed
response was incomplete. It said that, if the warning was substantively wrong,
the check should learn a narrow mechanical exemption from the corpus. Two such
exemptions were implemented and rejected during certification. Neither could
bind achieved diagnostics to the schedule, substrate, geometry, and
authorization relation that the rule needs. The corrected ruling is
structural: a frozen pre-registration that declares a schedule must carry the
canonical Cost Gate with filled `Target geometry` and `Calibration domain`
rows. Completed-diagnostics prose is not an exemption.

That correction did not convert a false positive into accepted validator
noise. The owning project made the already-achieved calibration evidence
explicit in post-execution Amendment 4 (`d4112f545`), and the deterministic
committed-base control proves that this structural change removes only `0025`.
The surviving `0034` incident remains visible.

The design's other correction remains load-bearing: execution-geometry mismatch
has **no fixed direction**. Compile-dominated pilots can overstate per-unit
cost, while batched measurements can understate sequential cost. Favourable
probe selection creates the reliably optimistic bias in the reported
incidents; mismatch alone only invalidates authorization.

`prereg.cost-geometry-undeclared` is deliberately **deferred**, not silently
dropped. Only **1 of 46** surveyed pre-registrations carried the Estimator
Certification Gate and only one mentioned a compute budget. A rule over that
surface would certify only the fixtures that teach it its own convention.
Batch T instead ships the schedule-calibration rule, for which the corpus
contained five real candidate findings. Reconsider the broader rule only after
the corpus has materially adopted Cost Gates and can falsify it.

## Downstream behavior changes

Downstream toolkit consumers will see these changes:

- `study-design-cost-gate-certification` is a registered canonical skill,
  discoverable through `skills/INDEX.md` and routed to agents. It teaches
  frozen geometry, the monotonicity tell, p90 over at least five repeats at one
  geometry, steady-state/target-concurrency measurement, schedule calibration
  domains, bottleneck-first remedy ladders, and the positive verdict-blind-gate
  pattern.
- `skills/study-design/estimator-certification.md` now routes its “price the
  design” step to the cost doctrine, and `skills/pipelines/SKILL.md` routes
  compile/contention work there without duplicating the doctrine.
- Both pre-registration template copies expose the optional
  `cost-gate` section, headed `Cost Gate (execution geometry)`. It is
  `required: false`: analyses with no cost or schedule decision may delete it.
  Users who keep it get explicit rows for target geometry, calibration domain,
  statistic (including repeat guidance), steady state, monotonicity, bottleneck
  profile, transfer, and invalidation.
- `science validate` now loads `prereg.schedule-calibration-domain`. For a
  frozen pre-registration whose content declares burn-in, thinning, R-hat, or
  ESS, it emits an ungated **WARN** when the canonical Cost Gate is absent or
  either load-bearing row is absent, empty, or still a placeholder. Filled
  canonical rows discharge the warning. Unfrozen pre-registrations and
  documents without schedule tokens are unchanged.
- The validator accepts no document-level prose shortcut. Achieved ESS,
  acceptance-rate, power, or Outcome prose does not silence the warning,
  because it cannot prove the required authorization relation. A malformed
  present gate still warns rather than becoming cheaper than a filled gate.
- The frozen-pre-registration predicate moved into
  `science_tool.validate.prereg_frozen` and is shared by the vehicle and
  schedule checks; the vehicle-check verdicts did not change.

The renderer-unblocking fix described as D0 was shipped separately as
`a3611ed2` and merged to main as `c6a57e70`; Batch T does not claim it again as
a branch-local behavior change.

## Filing closures

All six records were closed through `science feedback update` in the canonical
feedback store at `~/.config/science/feedback/`. Each was then read back through
`science feedback show` with `status: addressed` and a non-empty detailed
resolution.

| filing | terminal resolution |
|---|---|
| `fb-2026-07-13-001` | Exact execution geometry and the monotonicity tell are now doctrine; the template freezes target geometry and calibration domain. |
| `fb-2026-07-13-002` | The doctrine requires p90 wall time over `R >= 5` repeats at one executing geometry and forbids a best-across-sweep cost. |
| `fb-2026-07-12-014` | The doctrine and pipelines route name compile amortisation, require steady-state target-concurrency measurement, and record thread pinning. |
| `fb-2026-07-25-009` | Doctrine, template, and the certified WARN rule now require a schedule calibration domain; final corpus result is 4/0/0/0 and `0034` remains visible. |
| `fb-2026-07-25-010` | The doctrine requires profiling first, ordering remedies by the measured bottleneck, and presenting the cost split with options. |
| `fb-2026-07-25-011` | The positive verdict-blind pre-exposure gate pattern is recorded under “What Works,” preserving it as reusable doctrine. |

The canonical filing paths are:

```text
~/.config/science/feedback/fb-2026-07-13-001.yaml
~/.config/science/feedback/fb-2026-07-13-002.yaml
~/.config/science/feedback/fb-2026-07-12-014.yaml
~/.config/science/feedback/fb-2026-07-25-009.yaml
~/.config/science/feedback/fb-2026-07-25-010.yaml
~/.config/science/feedback/fb-2026-07-25-011.yaml
```

## Final verification

Task 7 ran the required commands sequentially from the package directories:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science
uv run --frozen pytest

cd ~/d/science/.worktrees/feedback-batch-t/science/model
uv run --frozen pytest

cd ~/d/science/.worktrees/feedback-batch-t/science
uv run --frozen ruff check
uv run --frozen pyright
```

| check | result |
|---|---|
| Science pytest | **11,603 passed, 7 skipped, 8 deselected**, exit 0 |
| science-model pytest | **1,468 passed**, exit 0 |
| Ruff | **All checks passed**, exit 0 |
| Pyright | **0 errors, 0 warnings, 0 informations**, exit 0 |

The Science suite reported only warnings and completed in 529.34 seconds.
No snapshot was updated and no failure was dismissed. The external
natural-systems amendment remains isolated on
`fix/prereg-0025-cost-gate` at `d4112f545`, based on `f733755b3`; neither that
branch nor `feedback-batch-t` was merged.
