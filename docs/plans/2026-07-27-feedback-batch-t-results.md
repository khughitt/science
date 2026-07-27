# Feedback Batch T — certification results

Measured against `docs/plans/2026-07-26-feedback-batch-t-design.md` and
`docs/plans/2026-07-27-feedback-batch-t-plan.md`. This section records the
Task 6 corpus certification. Task 7 adds the filing closures and branch-wide
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
known false positive.

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

### Corpus-derived RED/GREEN refinement

The root cause was that the antecedent treated every schedule token as
prospective and could not recognize completed same-document calibration.
Across all 46 measured pre-registrations, only `0025` has the narrow mechanical
shape of a numeric markdown `ESS (of N)` row. Bare prospective thresholds such
as `ESS >= 400` and failed prose reports such as `ESS = 8.6` do not have that
shape.

A fixture reproducing `0025`'s four-chain schedule plus acceptance/ESS table
was added first. It asserted no finding without adding a Cost Gate. RED:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science
uv run --frozen pytest \
  tests/validate/test_checks_prereg_schedule.py::test_schedule_with_achieved_ess_table_passes_without_cost_gate \
  -q
```

The test failed with one
`prereg.schedule-calibration-domain` warning, for the expected reason. The
minimal implementation then exempted only a numeric table row matching
`ESS (of N)` with an achieved value. The new test and the existing prospective
schedule test both passed:

```bash
uv run --frozen pytest \
  tests/validate/test_checks_prereg_schedule.py::test_schedule_with_achieved_ess_table_passes_without_cost_gate \
  tests/validate/test_checks_prereg_schedule.py::test_schedule_without_cost_gate_warns \
  -q
```

The refinement is commit `4c9511ea`:
`fix(validate): narrow schedule-calibration-domain to undeclared calibration`.

### Re-verification and final measured findings

The required code and validator suites passed after the refinement:

```bash
cd ~/d/science/.worktrees/feedback-batch-t/science
uv run --frozen pytest \
  tests/validate/test_checks_prereg_schedule.py \
  tests/validate/test_checks_prereg_vehicles.py -q
uv run --frozen pytest tests/validate -q
uv run --frozen ruff check \
  src/science_tool/validate/checks/prereg_schedule.py \
  tests/validate/test_checks_prereg_schedule.py
```

Results: **34 focused tests passed**, **947 validator tests passed**, and focused
ruff was clean. The validator suite emitted only the existing rdflib
deprecation warnings.

The exact four-project JSON command above was then rerun. Final counts:

| project | expected after adjudication | actual |
|---|---:|---:|
| natural-systems | 4 | **4** |
| 3d-attention-bias | 0 | **0** |
| protein-landscape | 0 | **0** |
| seq-feats | 0 | **0** |

The surviving paths are `0007`, `0026`, `0032`, and `0034`, each with the same
path-specific message recorded above. `0025` is absent. In particular, the
refinement did **not** silence `0034`.

### Certification domain

This certification measures **one project and one method family**:
natural-systems contributes all five initial cases, all in the MCMC/sampling
schedule family. The other three projects contribute 12 pre-registrations but
declare no such schedules and produce zero findings. The result certifies the
instrument only over that measured domain; it does not claim coverage of other
schedule families or project conventions.
