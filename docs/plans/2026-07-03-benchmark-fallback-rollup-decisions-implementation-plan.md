# Benchmark Fallback Rollup Decisions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Calibrate the recurring benchmark fallback rollups across active projects, record explicit decisions, and make only high-confidence commons metadata changes.

**Architecture:** This is a calibration and metadata-cleanup slice, not a `science` feature slice. The science worktree stores the design/plan/report artifacts; `~/d/science-commons` remains the source of benchmark dataset metadata. The `science benchmark test-triage` JSON payload, especially `fallback_diagnostics.rollups` and `suppressed_blocked_support`, is the single source of truth for report measurements.

**Tech Stack:** Python 3.13 via `rtk uv run --project science --frozen`, `science benchmark test-triage`, `science commons validate`, YAML frontmatter in `~/d/science-commons/datasets/*/entity.md`, git worktrees.

---

## File Structure

- Create: `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md`
  - Durable decision note in the science repo worktree. This is the primary deliverable even if no commons metadata changes are made.
- Create: `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/`
  - Calibration JSON snapshots used by the decision note:
    - `before.multiple-myeloma.json`
    - `before.post-acute-infection.json`
    - `before.natural-systems.json`
    - `before.cbioportal.json`
    - optional `after.<project>.json` files if commons metadata changes are made.
- Modify only if calibration proves a concrete metadata gap:
  - `~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/entity.md`
  - `~/d/science-commons/datasets/cptac-proteogenomics/entity.md`
  - `~/d/science-commons/datasets/dream4-in-silico-network/entity.md`
  - `~/d/science-commons/datasets/mmrf-commpass/entity.md`

Do not edit benchmark matching/scoring code in this slice.

---

### Task 0: Confirm Worktree, Dependency, and Baseline

**Files:**
- Read: `docs/plans/2026-07-03-benchmark-fallback-rollup-decisions-design.md`
- Read: `science/src/science_tool/benchmark_opportunities.py`
- Read: `science/src/science_tool/cli.py`

- [ ] **Step 1: Confirm the science worktree is isolated and clean**

Run:

```bash
rtk git status --short --branch
rtk git rev-parse --git-dir
rtk git rev-parse --git-common-dir
```

Expected:

- Branch is `benchmark-rollup-calibration`.
- Status is clean.
- `git-dir` and `git-common-dir` differ because this is a linked worktree.

- [ ] **Step 2: Confirm source resolution uses the worktree**

Run:

```bash
rtk env PYTHONPATH=science/src:science/model/src uv run --project science --frozen python -c "import science_tool; print(science_tool.__file__)"
```

Expected: path starts with the current worktree path and ends with:

```text
science/src/science_tool/__init__.py
```

- [ ] **Step 3: Confirm `fallback_diagnostics.rollups` exists**

Run:

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback --format json > /tmp/mm-fallback-rollups-check.json
rtk python -c "import json,sys; payload=json.load(open('/tmp/mm-fallback-rollups-check.json')); sys.exit(0 if 'rollups' in payload['fallback_diagnostics'] else 1)"
```

Expected: both commands exit 0. If this fails, stop: the fallback-rollups implementation is not active in this environment.

- [ ] **Step 4: Run focused benchmark tests**

Run:

```bash
rtk env PYTEST_DEBUG_TEMPROOT=/tmp PYTHONPATH=science/src:science/model/src uv run --project science --frozen pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Check commons repo status before any edits**

Run:

```bash
rtk git -C ~/d/science-commons status --short --branch
```

Expected: clean or only changes that the user has explicitly told you to include. If dirty with unrelated changes, stop and ask before editing commons metadata.

- [ ] **Step 6: Commit nothing in this task**

Expected: no changes were made.

---

### Task 1: Capture Calibration Snapshots

**Files:**
- Create directory: `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/`
- Create:
  - `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.multiple-myeloma.json`
  - `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.post-acute-infection.json`
  - `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.natural-systems.json`
  - `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.cbioportal.json`

- [ ] **Step 1: Create the report artifact directory**

Run:

```bash
rtk mkdir -p docs/reports/benchmark-fallback-rollup-decisions-2026-07-03
```

Expected: directory exists.

- [ ] **Step 2: Capture multiple-myeloma fallback rollups**

Run:

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback --format json > docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.multiple-myeloma.json
```

Expected: command exits 0.

- [ ] **Step 3: Capture post-acute-infection fallback rollups**

Run:

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/health/processes/post-acute-infection --commons --source gap-fallback --format json > docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.post-acute-infection.json
```

Expected: command exits 0.

- [ ] **Step 4: Capture natural-systems fallback rollups**

Run:

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback --format json > docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.natural-systems.json
```

Expected: command exits 0.

- [ ] **Step 5: Capture cbioportal fallback rollups**

Run:

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/cancer/data-sources/cbioportal --commons --source gap-fallback --format json > docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.cbioportal.json
```

Expected: command exits 0.

- [ ] **Step 6: Verify every snapshot has visible rollups and MMRF suppression**

Run:

```bash
rtk python - <<'PY'
import json
from pathlib import Path

DOMINANT = [
    "dataset:ccle-proteomics-nusinow-2020",
    "dataset:cptac-proteogenomics",
    "dataset:dream4-in-silico-network",
]

root = Path("docs/reports/benchmark-fallback-rollup-decisions-2026-07-03")
benchmark_projects = {bid: [] for bid in DOMINANT}
mmrf_suppressed_projects = []
any_rollups = False

for path in sorted(root.glob("before.*.json")):
    project = path.stem.removeprefix("before.")
    payload = json.loads(path.read_text())
    diagnostics = payload["fallback_diagnostics"]
    rollups = diagnostics["rollups"]
    suppressed = diagnostics.get("suppressed_blocked_support", {})
    any_rollups = any_rollups or bool(rollups)
    present = {row["benchmark_id"] for row in rollups}
    for bid in DOMINANT:
        if bid in present:
            benchmark_projects[bid].append(project)
    mmrf_suppressed = any(
        row.get("benchmark_id") == "dataset:mmrf-commpass"
        for row in suppressed.get("top_benchmarks", [])
    )
    if mmrf_suppressed:
        mmrf_suppressed_projects.append(project)
    print(
        f"{path.name} rollups={len(rollups)} "
        f"suppressed_rows={suppressed.get('rows', 0)} "
        f"dominant_present={sorted(present & set(DOMINANT))} "
        f"mmrf_suppressed={mmrf_suppressed}"
    )

# Informational: cross-project distribution. Variation here is calibration
# SIGNAL to record in the decision note, not a failure.
for bid in DOMINANT:
    print(f"  {bid}: {benchmark_projects[bid] or 'NONE'}")
print(f"  mmrf-suppressed in: {mmrf_suppressed_projects or 'NONE'}")

# Hard invariants only: a broken rollups feature must fail loudly, but
# legitimate per-project variation must NOT halt calibration.
assert any_rollups, "no sampled project produced any visible fallback rollups"
for bid in DOMINANT:
    assert benchmark_projects[bid], f"{bid} did not appear as a rollup in ANY sampled project"
PY
```

Expected: prints one line per snapshot plus a per-benchmark presence summary, and
exits 0. The hard gate is only that rollups exist somewhere and each dominant
benchmark appears in at least one project (so a broken rollups feature still
fails loudly). Per-project variation — a project missing a dominant benchmark, or
MMRF not surfaced/suppressed there — is expected calibration signal: record it in
the decision note's `Context` rather than treating it as a failure.

- [ ] **Step 7: Commit the raw calibration snapshots**

Run:

```bash
rtk git add docs/reports/benchmark-fallback-rollup-decisions-2026-07-03
rtk git commit -m "docs: capture benchmark fallback rollup calibration"
```

Expected: commit succeeds.

---

### Task 2: Write the Decision Note

**Files:**
- Create: `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md`
- Read: `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.*.json`
- Read:
  - `~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/entity.md`
  - `~/d/science-commons/datasets/cptac-proteogenomics/entity.md`
  - `~/d/science-commons/datasets/dream4-in-silico-network/entity.md`
  - `~/d/science-commons/datasets/mmrf-commpass/entity.md`

- [ ] **Step 1: Extract rollup summary from JSON snapshots**

Run:

```bash
rtk python - <<'PY'
import json
from collections import defaultdict
from pathlib import Path

root = Path("docs/reports/benchmark-fallback-rollup-decisions-2026-07-03")
totals = defaultdict(lambda: {"count": 0, "projects": [], "support": set(), "readiness": set(), "classes": set(), "facets": defaultdict(int), "examples": []})
for path in sorted(root.glob("before.*.json")):
    project = path.stem.removeprefix("before.")
    payload = json.loads(path.read_text())
    for rollup in payload["fallback_diagnostics"]["rollups"]:
        task = rollup["task_id"]
        row = totals[task]
        row["count"] += rollup["count"]
        row["projects"].append(f"{project}:{rollup['count']}")
        row["support"].add(str(rollup.get("task_support_state") or "none"))
        reason = rollup.get("task_support_reason")
        if reason:
            row["support"].add(f"reason={reason}")
        row["readiness"].add(rollup["readiness_label"])
        row["classes"].add(rollup["dataset_class"])
        for facet in rollup["top_facets"]:
            row["facets"][facet["facet"]] += facet["count"]
        for entity in rollup["example_entities"]:
            if entity not in row["examples"] and len(row["examples"]) < 5:
                row["examples"].append(entity)

for task, row in sorted(totals.items(), key=lambda item: (-item[1]["count"], item[0])):
    facets = ", ".join(f"{facet}:{count}" for facet, count in sorted(row["facets"].items(), key=lambda item: (-item[1], item[0]))[:6])
    print(f"- {task}")
    print(f"  total_count: {row['count']}")
    print(f"  projects: {', '.join(row['projects'])}")
    print(f"  support: {', '.join(sorted(row['support']))}")
    print(f"  readiness: {', '.join(sorted(row['readiness']))}")
    print(f"  dataset_class: {', '.join(sorted(row['classes']))}")
    print(f"  top_facets: {facets}")
    print(f"  examples: {', '.join(row['examples'])}")
PY
```

Expected: prints one block each for CCLE, CPTAC, and DREAM4.

- [ ] **Step 2: Create the decision note**

Create `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md` with this structure. The counts below match the observed calibration output used to draft this plan; if Step 1 prints different counts, use the freshly printed counts and note the difference in the `Context` section.

```markdown
# Benchmark Fallback Rollup Decisions - 2026-07-03

## Context

This calibration uses `science benchmark test-triage --commons --source gap-fallback`
after fallback rollups were added to `fallback_diagnostics.rollups`.

Active projects sampled:

- `~/d/cancer/cancer-types/multiple-myeloma`
- `~/d/health/processes/post-acute-infection`
- `~/d/natural-systems`
- `~/d/cancer/data-sources/cbioportal`

Raw JSON snapshots are stored in:

- `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.multiple-myeloma.json`
- `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.post-acute-infection.json`
- `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.natural-systems.json`
- `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/before.cbioportal.json`

## Decision Summary

| Benchmark task | Observed projects | Current state | Decision | Metadata change |
| --- | --- | --- | --- | --- |
| `dataset:ccle-proteomics-nusinow-2020#protein-lineage-association` | `multiple-myeloma:307`, `post-acute-infection:47`, `natural-systems:104`, `cbioportal:36` | `supported` / `runnable` / `deposit` | `keep-supported-fallback` | none |
| `dataset:cptac-proteogenomics#protein-rna-cross-modal` | `multiple-myeloma:297`, `post-acute-infection:47`, `natural-systems:113`, `cbioportal:34` | `candidate:requires-study-specific-staging` / `metadata-only` / `reference` | `needs-staging-recipe` | none, unless Task 3 finds a more precise durable reason |
| `dataset:dream4-in-silico-network#network-reconstruction` | `multiple-myeloma:294`, `post-acute-infection:46`, `natural-systems:101`, `cbioportal:42` | `candidate:requires-challenge-package-staging` / `metadata-only` / `pointer` | `valid-reference-only` | none, unless Task 3 confirms a concrete stageable package |
| `dataset:mmrf-commpass#progression-risk` | Suppressed in all sampled projects | `blocked:open-metadata-missing-progression-endpoint` | `keep-blocked-support` | none |

## Per-Benchmark Notes

### CCLE Proteomics

Decision: `keep-supported-fallback`.

Evidence:

- Current commons metadata is a runnable deposit with `datapackage: datapackage.yaml`.
- Task support is already `supported`.
- Rollup facets are protein/multimodal/cross-sectional and match the benchmark's intended broad fallback role.

Interpretation:

This remains a broad cell-line protein-abundance fallback, not a primary-tumor or causal benchmark.

### CPTAC Proteogenomics

Decision: `needs-staging-recipe`.

Evidence:

- Current commons metadata is `dataset_class: reference`.
- Task support is `candidate` with reason `requires-study-specific-staging`.
- Rollup facets are proteomics/multimodal/bulk-RNA/genomics and repeatedly match project needs.

Interpretation:

Keep it visible as a candidate. Do not mark it runnable until a concrete CPTAC study/package is selected, access terms are checked, and a datapackage or recipe exists.

### DREAM4 In Silico Network

Decision: `valid-reference-only`.

Evidence:

- Current commons metadata is `dataset_class: pointer`.
- Task support is `candidate` with reason `requires-challenge-package-staging`.
- Rollup facets are perturbation/time-series/simulated gene expression.

Interpretation:

This is useful as a benchmark direction for mechanism/time-series validation, but it should remain metadata-only until the exact challenge package and access path are staged.

### MMRF CoMMpass

Decision: `keep-blocked-support`.

Evidence:

- Blocked fallback rows are suppressed from default fallback diagnostics.
- The blocked support reason reflects the current open-metadata progression endpoint limitation.

Interpretation:

No change in this slice.

## Follow-Up

Recommended next slice:

1. Audit CPTAC proteogenomics for a concrete study/package that can support `protein-rna-cross-modal`.
2. Audit DREAM4 access/package layout only if synthetic network reconstruction is a near-term priority.
3. Do not build extra review tooling until more than these recurring rollups require manual decisions.
```

- [ ] **Step 3: Verify the note has no replacement markers**

Run:

```bash
rtk rg -n "Replace wit[h]|TB[D]|TO[D]O|docs/superpower[s]" docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md
```

Expected: exit 1 with no matches.

- [ ] **Step 4: Commit the decision note**

Run:

```bash
rtk git add docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md
rtk git commit -m "docs: record benchmark fallback rollup decisions"
```

Expected: commit succeeds.

---

### Task 3: Audit Whether Commons Metadata Needs Edits

**Files:**
- Read:
  - `~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/entity.md`
  - `~/d/science-commons/datasets/cptac-proteogenomics/entity.md`
  - `~/d/science-commons/datasets/dream4-in-silico-network/entity.md`
  - `~/d/science-commons/datasets/mmrf-commpass/entity.md`
- Modify only if needed:
  - same commons files above.

- [ ] **Step 1: Inspect current support metadata**

Run:

```bash
rtk rg -n "id: |dataset_class:|datapackage:|support:|state:|reason:|checked_at:|evidence:|notes:|limitations:" ~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/entity.md
rtk rg -n "id: |dataset_class:|datapackage:|support:|state:|reason:|checked_at:|evidence:|notes:|limitations:" ~/d/science-commons/datasets/cptac-proteogenomics/entity.md
rtk rg -n "id: |dataset_class:|datapackage:|support:|state:|reason:|checked_at:|evidence:|notes:|limitations:" ~/d/science-commons/datasets/dream4-in-silico-network/entity.md
rtk rg -n "id: |dataset_class:|datapackage:|support:|state:|reason:|checked_at:|evidence:|notes:|limitations:" ~/d/science-commons/datasets/mmrf-commpass/entity.md
```

Expected:

- CCLE task support is `supported`.
- CPTAC task support is `candidate` with `requires-study-specific-staging`.
- DREAM4 task support is `candidate` with `requires-challenge-package-staging`.
- MMRF progression task support is `blocked` with `open-metadata-missing-progression-endpoint`.

- [ ] **Step 2: Decide whether an edit is needed**

Use these exact rules:

- If all four expected states/reasons are present and the decision note says `metadata_change: none`, make no commons edit.
- If CPTAC has a better durable reason than `requires-study-specific-staging`, edit only `support.reason`, `support.notes`, or `benchmark.limitations`.
- If DREAM4 has a confirmed concrete challenge package layout and access path, edit only `support.notes` or create a follow-up staging plan; do not change `dataset_class` in this task.
- If CCLE support notes fail to mention that it is broad cell-line proteomics rather than project-specific validation, tighten only `support.notes`.
- If MMRF blocked support is missing or changed, restore the blocked support metadata rather than changing report logic.

- [ ] **Step 3: If no commons edit is needed, record that explicitly**

Append this paragraph to `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md` under `## Follow-Up`:

```markdown

## Commons Metadata Audit

No commons metadata edits were made in this slice. The sampled dominant rollups
already carry explicit task-support metadata, and the remaining actionability
work is staging/audit work rather than report metadata cleanup.
```

Then run:

```bash
rtk git add docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md
rtk git commit -m "docs: note fallback rollup metadata audit"
```

Expected: commit succeeds. Skip Task 3 Steps 4-8.

- [ ] **Step 4: If a commons edit is needed, edit only the scoped commons file**

Use `apply_patch` from the science session to edit exactly one scoped commons
metadata file under `~/d/science-commons`. Example patch content for tightening
CPTAC notes only:

```diff
*** Begin Patch
*** Update File: ~/d/science-commons/datasets/cptac-proteogenomics/entity.md
@@
         notes:
           - Benchmark-relevant portal record; a concrete study/package must be selected and staged before use.
-          - Keep visible as a candidate for proteogenomic cross-modal validation, not as a runnable fallback.
+          - Keep visible as a candidate for proteogenomic cross-modal validation, not as a runnable fallback.
+          - Next action is selecting a specific CPTAC study/package and checking its access terms before writing a datapackage.
*** End Patch
```

Expected: only the scoped commons file changes.

- [ ] **Step 5: Validate commons metadata after any edit**

Run:

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science commons validate
```

Expected: PASS.

- [ ] **Step 6: Rebuild the commons index after any edit**

Run:

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science commons index rebuild
```

Expected: exits 0 and no longer leaves a stale registry warning for subsequent triage runs.

- [ ] **Step 7: Commit commons metadata edits in the commons repo**

Run:

```bash
rtk git -C ~/d/science-commons status --short
rtk git -C ~/d/science-commons add datasets/ccle-proteomics-nusinow-2020/entity.md datasets/cptac-proteogenomics/entity.md datasets/dream4-in-silico-network/entity.md datasets/mmrf-commpass/entity.md
rtk git -C ~/d/science-commons commit -m "docs: calibrate fallback benchmark support metadata"
```

Expected:

- `status --short` shows only intended commons metadata/index changes.
- Commit succeeds.

- [ ] **Step 8: Record commons commit in the decision note**

Run:

```bash
rtk git -C ~/d/science-commons log --oneline -1
```

Append this paragraph under `## Commons Metadata Audit`, using the exact commit hash printed by the command:

```markdown

Commons metadata changes were committed in `~/d/science-commons` as the latest
commons commit printed by `rtk git -C ~/d/science-commons log --oneline -1`.
The changes are limited to task-support notes/reasons for the dominant fallback
rollup records.
```

Run:

```bash
rtk git add docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md
rtk git commit -m "docs: reference fallback rollup commons audit"
```

Expected: commit succeeds.

---

### Task 4: Capture After Snapshots and Compare Behavior

**Files:**
- Create if commons metadata changed:
  - `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.multiple-myeloma.json`
  - `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.post-acute-infection.json`
  - `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.natural-systems.json`
  - `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.cbioportal.json`
- Modify: `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md`

- [ ] **Step 1: Capture after snapshots**

Run these commands if Task 3 made any commons edit. If Task 3 made no commons edit, skip to Step 4.

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback --format json > docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.multiple-myeloma.json
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/health/processes/post-acute-infection --commons --source gap-fallback --format json > docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.post-acute-infection.json
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback --format json > docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.natural-systems.json
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/cancer/data-sources/cbioportal --commons --source gap-fallback --format json > docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.cbioportal.json
```

Expected: all commands exit 0.

- [ ] **Step 2: Compare before/after rollup identities**

Run:

```bash
rtk python - <<'PY'
import json
from pathlib import Path

root = Path("docs/reports/benchmark-fallback-rollup-decisions-2026-07-03")
for before_path in sorted(root.glob("before.*.json")):
    project = before_path.name.removeprefix("before.").removesuffix(".json")
    after_path = root / f"after.{project}.json"
    if not after_path.exists():
        continue
    before = json.loads(before_path.read_text())
    after = json.loads(after_path.read_text())
    before_ids = [(r["benchmark_id"], r["task_id"], r["task_support_state"], r["task_support_reason"]) for r in before["fallback_diagnostics"]["rollups"]]
    after_ids = [(r["benchmark_id"], r["task_id"], r["task_support_state"], r["task_support_reason"]) for r in after["fallback_diagnostics"]["rollups"]]
    print(project, "before", before_ids)
    print(project, "after ", after_ids)
    assert len(after["fallback_diagnostics"]["rollups"]) == len(before["fallback_diagnostics"]["rollups"])
PY
```

Expected:

- Prints before/after identities for each project with after snapshots.
- Rollup count remains 3 unless the intentional metadata edit changed task support state/reason.

- [ ] **Step 3: Commit after snapshots**

Run:

```bash
rtk git add docs/reports/benchmark-fallback-rollup-decisions-2026-07-03/after.*.json
rtk git commit -m "docs: capture benchmark fallback rollup post-audit output"
```

Expected: commit succeeds if after snapshots exist. If there were no commons edits, skip this step.

- [ ] **Step 4: Run final visible table smoke checks**

Run:

```bash
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/health/processes/post-acute-infection --commons --source gap-fallback
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback
rtk env SCIENCE_COMMONS_ROOT=~/d/science-commons PYTHONPATH=science/src:science/model/src uv run --project science --frozen science benchmark test-triage --project-root ~/d/cancer/data-sources/cbioportal --commons --source gap-fallback
```

Expected:

- Commands exit 0.
- Visible fallback table still groups to the dominant rollups.
- MMRF remains in suppressed blocked fallback.
- No stale commons registry warning appears if Task 3 rebuilt the commons index.

- [ ] **Step 5: Update final verification note**

Append a `## Verification` section to `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md`:

```markdown

## Verification

Final checks run:

- `science commons validate`
- `science commons index rebuild` when commons metadata changed
- `science benchmark test-triage --commons --source gap-fallback` for all four active projects

Outcome:

- Visible fallback diagnostics remain grouped into the dominant benchmark/task rollups.
- MMRF blocked fallback rows remain suppressed by default.
- No benchmark matching, scoring, sorting, or fallback-selection code changed.
```

Run:

```bash
rtk git add docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md
rtk git commit -m "docs: verify benchmark fallback rollup decisions"
```

Expected: commit succeeds.

---

### Task 5: Final Review and Handoff

**Files:**
- Read: all files committed by this plan.

- [ ] **Step 1: Verify science worktree is clean**

Run:

```bash
rtk git status --short --branch
```

Expected: clean on `benchmark-rollup-calibration`.

- [ ] **Step 2: Verify commons repo is clean**

Run:

```bash
rtk git -C ~/d/science-commons status --short --branch
```

Expected: clean. If commons has intended uncommitted artifacts, commit them before finishing or explicitly report them.

- [ ] **Step 3: Show science commits for this branch**

Run:

```bash
rtk git log --oneline main..HEAD
```

Expected: shows the design commit, this plan commit, and report commits from Tasks 1-4.

- [ ] **Step 4: Summarize final decisions**

Final response should include:

- Path to `docs/reports/benchmark-fallback-rollup-decisions-2026-07-03.md`.
- Whether commons metadata changed.
- Any commons commit hash.
- The recommended next slice:
  - CPTAC staging recipe audit if `needs-staging-recipe` remains the top actionable item.
  - DREAM4 package audit if synthetic time-series/mechanism validation is prioritized.
  - Review tooling only if future calibration shows more than a small recurring set of manual decisions.

- [ ] **Step 5: Do not merge automatically**

Use `superpowers:finishing-a-development-branch` after execution and offer merge/cleanup options.
