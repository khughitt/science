# Benchmark Fallback Support Annotation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add task-local support metadata to the top three visible fallback benchmark records so `science benchmark test-triage` explains broad fallback rows without changing matching, scoring, or suppression behavior.

**Architecture:** This is a metadata-only change in `~/d/science-commons`. The `science` repo already parses and reports `benchmark.tasks[].support`, so the implementation updates three commons dataset entity frontmatter blocks, validates the commons metadata, and compares before/after `test-triage` output. The science worktree only holds this plan and the design spec; command code should remain untouched.

**Tech Stack:** YAML frontmatter in commons dataset entities, `science benchmark test-triage`, `science validate`, git commits in two repos (`science` and `science-commons`).

---

## File Structure

- Modify `~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/entity.md`
  - Add `support.state: supported` under `benchmark.tasks[].id == protein-lineage-association`.
- Modify `~/d/science-commons/datasets/cptac-proteogenomics/entity.md`
  - Add `support.state: candidate` under `benchmark.tasks[].id == protein-rna-cross-modal`.
  - Add `support.reason: requires-study-specific-staging`.
- Modify `~/d/science-commons/datasets/dream4-in-silico-network/entity.md`
  - Add `support.state: candidate` under `benchmark.tasks[].id == network-reconstruction`.
  - Add `support.reason: requires-challenge-package-staging`.
- Do not modify `science/src/` or `science/tests/`.

---

### Task 0: Preflight And Repository Boundaries

**Files:**
- No files changed.

- [ ] **Step 1: Verify the science worktree is clean except planned docs**

Run from `~/d/science/.worktrees/benchmark-fallback-support-annotation`:

```bash
git status --short
```

Expected before committing this plan: only the design/plan docs may be dirty or untracked. After this plan is committed, the worktree should be clean.

- [ ] **Step 2: Verify science-commons is clean**

Run:

```bash
git -C ~/d/science-commons status --short
```

Expected: no output. If there is output, stop and inspect before editing commons metadata.

- [ ] **Step 3: Confirm the three target tasks currently have no support blocks**

Run:

```bash
rg -n "support:|state: supported|state: candidate|state: blocked" ~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/entity.md ~/d/science-commons/datasets/cptac-proteogenomics/entity.md ~/d/science-commons/datasets/dream4-in-silico-network/entity.md
```

Expected before implementation: no `support:` block in these three files. Other lines such as prose containing the word "support" in the Markdown body are not relevant; inspect any match before proceeding.

- [ ] **Step 4: Confirm the science command code is already capable of reading task support**

Run:

```bash
rg -n "task_support_state|_task_support_from_mapping|BenchmarkTaskSupport" science/src/science_tool/benchmark_opportunities.py science/model/src/science_model/packages/schema.py
```

Expected: matches in existing code. Do not edit these files.

---

### Task 1: Capture Before-State Calibration

**Files:**
- No files changed.

- [ ] **Step 1: Capture unfiltered before-state reports**

Run from `~/d/science/.worktrees/benchmark-fallback-support-annotation`:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --format json > /tmp/mm-triage-before.json
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark test-triage --project-root ~/d/natural-systems --commons --format json > /tmp/ns-triage-before.json
```

Expected: both commands exit 0. Stale commons registry warnings on stderr are acceptable.

- [ ] **Step 2: Capture fallback-scoped before-state reports**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback --format json > /tmp/mm-triage-fallback-before.json
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback --format json > /tmp/ns-triage-fallback-before.json
```

Expected: both commands exit 0.

- [ ] **Step 3: Verify the three target benchmarks are visible fallback rows before annotation**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path

targets = {
    "dataset:ccle-proteomics-nusinow-2020",
    "dataset:cptac-proteogenomics",
    "dataset:dream4-in-silico-network",
}
for label, path in {
    "multiple-myeloma": Path("/tmp/mm-triage-fallback-before.json"),
    "natural-systems": Path("/tmp/ns-triage-fallback-before.json"),
}.items():
    payload = json.loads(path.read_text())
    rows = payload["buckets"]["fallback-diagnostic"]
    present = {row["benchmark_id"] for row in rows if row["benchmark_id"] in targets}
    diagnostics = payload["fallback_diagnostics"]
    print(label, "fallback_rows", len(rows))
    print(label, "task_support_counts", diagnostics["task_support_counts"])
    print(label, "present_targets", sorted(present))
    missing = sorted(targets - present)
    if missing:
        raise SystemExit(f"{label} missing expected fallback targets: {missing}")
    if diagnostics["task_support_counts"]["none"] == 0:
        raise SystemExit(f"{label} has no none support rows to reduce")
PY
```

Expected: prints each project's fallback row count, support counts, and all three target benchmark ids. If a target is missing, stop and reassess the design before editing metadata.

- [ ] **Step 4: Save the before-state summary for after-state comparison**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path

summary = {}
for label, path in {
    "multiple-myeloma": Path("/tmp/mm-triage-before.json"),
    "natural-systems": Path("/tmp/ns-triage-before.json"),
}.items():
    payload = json.loads(path.read_text())
    summary[label] = {
        "bucket_counts": payload["summary"]["bucket_counts"],
        "fallback_task_support_counts": payload["fallback_diagnostics"]["task_support_counts"],
        "suppressed_blocked_support_fallback_rows": payload["summary"]["suppressed_blocked_support_fallback_rows"],
    }
Path("/tmp/benchmark-fallback-support-before-summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
print(json.dumps(summary, indent=2, sort_keys=True))
PY
```

Expected: writes `/tmp/benchmark-fallback-support-before-summary.json` and prints the same JSON.

---

### Task 2: Annotate CCLE Proteomics As Supported

**Files:**
- Modify: `~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/entity.md`

- [ ] **Step 1: Add support metadata to the CCLE task**

In `~/d/science-commons/datasets/ccle-proteomics-nusinow-2020/entity.md`, find:

```yaml
      interpretation_limits:
        - "Positive performance supports protein-level transfer checks, not primary-tumor causal claims."
      contexts: ["cell line", "lineage", "TMT batch"]
```

Replace it with:

```yaml
      interpretation_limits:
        - "Positive performance supports protein-level transfer checks, not primary-tumor causal claims."
      contexts: ["cell line", "lineage", "TMT batch"]
      support:
        state: supported
        checked_at: "2026-07-03"
        evidence:
          - datapackage.yaml
          - datapackage.yaml#resources
        notes:
          - Runnable deposit benchmark for protein-level association checks across CCLE cancer cell lines.
          - Use as broad cell-line proteomics validation, not as a primary-tumor or causal benchmark.
```

- [ ] **Step 2: Validate the edited YAML parses through science**

Run from the science worktree:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark tests --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --benchmark ccle-proteomics-nusinow-2020 --format json > /tmp/ccle-support-check.json
```

Expected: exit 0.

- [ ] **Step 3: Assert CCLE rows expose supported task support**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path

payload = json.loads(Path("/tmp/ccle-support-check.json").read_text())
rows = [row for row in payload["benchmark_tests"] if row["benchmark_id"] == "dataset:ccle-proteomics-nusinow-2020"]
if not rows:
    raise SystemExit("no CCLE benchmark test rows found")
states = {row["task_support_state"] for row in rows}
print("ccle task_support_states", sorted(states))
if states != {"supported"}:
    raise SystemExit(f"expected only supported rows, got {states}")
PY
```

Expected: prints `ccle task_support_states ['supported']`.

---

### Task 3: Annotate CPTAC And DREAM4 As Candidates

**Files:**
- Modify: `~/d/science-commons/datasets/cptac-proteogenomics/entity.md`
- Modify: `~/d/science-commons/datasets/dream4-in-silico-network/entity.md`

- [ ] **Step 1: Add candidate support to CPTAC**

In `~/d/science-commons/datasets/cptac-proteogenomics/entity.md`, find:

```yaml
      interpretation_limits:
        - "Protein prediction should exceed the RNA-only baseline."
      contexts: ["tumor type", "assay batch"]
```

Replace it with:

```yaml
      interpretation_limits:
        - "Protein prediction should exceed the RNA-only baseline."
      contexts: ["tumor type", "assay batch"]
      support:
        state: candidate
        reason: requires-study-specific-staging
        checked_at: "2026-07-03"
        evidence:
          - entity.md#benchmark.limitations
          - https://proteomic.datacommons.cancer.gov/pdc/
        notes:
          - Benchmark-relevant portal record; a concrete study/package must be selected and staged before use.
          - Keep visible as a candidate for proteogenomic cross-modal validation, not as a runnable fallback.
```

- [ ] **Step 2: Add candidate support to DREAM4**

In `~/d/science-commons/datasets/dream4-in-silico-network/entity.md`, find:

```yaml
      timepoints: ["challenge-provided simulated time-series measurements"]
      intervention: "simulated perturbation experiments"
      contexts: ["synthetic network", "time series", "perturbation"]
```

Replace it with:

```yaml
      timepoints: ["challenge-provided simulated time-series measurements"]
      intervention: "simulated perturbation experiments"
      contexts: ["synthetic network", "time series", "perturbation"]
      support:
        state: candidate
        reason: requires-challenge-package-staging
        checked_at: "2026-07-03"
        evidence:
          - entity.md#benchmark.limitations
          - https://www.synapse.org/Synapse:syn3049712
        notes:
          - Relevant synthetic benchmark for network reconstruction behavior checks.
          - Stage and document the exact DREAM4 challenge package before treating this task as runnable.
```

- [ ] **Step 3: Validate both candidate support states parse through science**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark tests --project-root ~/d/natural-systems --commons --benchmark cptac-proteogenomics --format json > /tmp/cptac-support-check.json
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark tests --project-root ~/d/natural-systems --commons --benchmark dream4-in-silico-network --format json > /tmp/dream4-support-check.json
```

Expected: both commands exit 0.

- [ ] **Step 4: Assert CPTAC and DREAM4 rows expose candidate task support**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path

checks = {
    "dataset:cptac-proteogenomics": Path("/tmp/cptac-support-check.json"),
    "dataset:dream4-in-silico-network": Path("/tmp/dream4-support-check.json"),
}
for benchmark_id, path in checks.items():
    payload = json.loads(path.read_text())
    rows = [row for row in payload["benchmark_tests"] if row["benchmark_id"] == benchmark_id]
    if not rows:
        raise SystemExit(f"no rows found for {benchmark_id}")
    states = {row["task_support_state"] for row in rows}
    reasons = {row["task_support_reason"] for row in rows}
    print(benchmark_id, "states", sorted(states), "reasons", sorted(reasons))
    if states != {"candidate"}:
        raise SystemExit(f"{benchmark_id}: expected candidate, got {states}")
    if not all(reasons):
        raise SystemExit(f"{benchmark_id}: missing candidate support reason")
PY
```

Expected: each benchmark prints `states ['candidate']` and a non-empty reason.

---

### Task 4: Validate Commons And Compare After-State Reports

**Files:**
- No additional files changed unless validation finds a metadata typo.

- [ ] **Step 1: Run commons validation**

Run from the science worktree:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science validate --project-root ~/d/science-commons
```

Expected: exit 0. If existing unrelated validation warnings/errors appear, inspect them. Do not ignore new `benchmark.task-support-*` failures from this change.

- [ ] **Step 2: Capture after-state reports**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --format json > /tmp/mm-triage-after.json
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark test-triage --project-root ~/d/natural-systems --commons --format json > /tmp/ns-triage-after.json
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --source gap-fallback --format json > /tmp/mm-triage-fallback-after.json
PYTHONPATH=science/src:science/model/src uv run --frozen --project science science benchmark test-triage --project-root ~/d/natural-systems --commons --source gap-fallback --format json > /tmp/ns-triage-fallback-after.json
```

Expected: all commands exit 0.

- [ ] **Step 3: Verify fallback support counts improved and suppression did not change**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path

before = json.loads(Path("/tmp/benchmark-fallback-support-before-summary.json").read_text())
for label, after_path in {
    "multiple-myeloma": Path("/tmp/mm-triage-after.json"),
    "natural-systems": Path("/tmp/ns-triage-after.json"),
}.items():
    after = json.loads(after_path.read_text())
    after_counts = after["fallback_diagnostics"]["task_support_counts"]
    before_counts = before[label]["fallback_task_support_counts"]
    print(label, "before", before_counts)
    print(label, "after", after_counts)
    if after_counts["none"] >= before_counts["none"]:
        raise SystemExit(f"{label}: expected fewer none fallback rows")
    if after_counts["supported"] <= before_counts["supported"]:
        raise SystemExit(f"{label}: expected more supported fallback rows")
    if after_counts["candidate"] <= before_counts["candidate"]:
        raise SystemExit(f"{label}: expected more candidate fallback rows")
    after_suppressed = after["summary"]["suppressed_blocked_support_fallback_rows"]
    before_suppressed = before[label]["suppressed_blocked_support_fallback_rows"]
    if after_suppressed != before_suppressed:
        raise SystemExit(
            f"{label}: suppressed blocked fallback changed {before_suppressed} -> {after_suppressed}"
        )
PY
```

Expected: prints before/after counts and exits 0.

- [ ] **Step 4: Verify fallback target rows carry the intended support states**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path

expected = {
    "dataset:ccle-proteomics-nusinow-2020": "supported",
    "dataset:cptac-proteogenomics": "candidate",
    "dataset:dream4-in-silico-network": "candidate",
}
for label, path in {
    "multiple-myeloma": Path("/tmp/mm-triage-fallback-after.json"),
    "natural-systems": Path("/tmp/ns-triage-fallback-after.json"),
}.items():
    payload = json.loads(path.read_text())
    rows = payload["buckets"]["fallback-diagnostic"]
    by_benchmark = {}
    for row in rows:
        if row["benchmark_id"] in expected:
            by_benchmark.setdefault(row["benchmark_id"], set()).add(row["task_support_state"])
    print(label, {key: sorted(value) for key, value in by_benchmark.items()})
    missing = sorted(set(expected) - set(by_benchmark))
    if missing:
        raise SystemExit(f"{label}: missing expected fallback benchmarks after annotation: {missing}")
    for benchmark_id, state in expected.items():
        if by_benchmark[benchmark_id] != {state}:
            raise SystemExit(f"{label}: {benchmark_id} expected {state}, got {by_benchmark[benchmark_id]}")
PY
```

Expected: both projects show CCLE as `supported`, CPTAC as `candidate`, and DREAM4 as `candidate`.

- [ ] **Step 5: Verify unfiltered bucket-count guardrail**

Run:

```bash
PYTHONPATH=science/src:science/model/src uv run --frozen --project science python - <<'PY'
import json
from pathlib import Path

before = json.loads(Path("/tmp/benchmark-fallback-support-before-summary.json").read_text())
for label, after_path in {
    "multiple-myeloma": Path("/tmp/mm-triage-after.json"),
    "natural-systems": Path("/tmp/ns-triage-after.json"),
}.items():
    after = json.loads(after_path.read_text())
    before_buckets = before[label]["bucket_counts"]
    after_buckets = after["summary"]["bucket_counts"]
    print(label, "before buckets", before_buckets)
    print(label, "after buckets", after_buckets)
    if after_buckets != before_buckets:
        raise SystemExit(
            f"{label}: unfiltered bucket counts changed; inspect non-fallback candidate movement before commit"
        )
PY
```

Expected: before/after bucket counts are identical for both projects. If this fails, stop and inspect whether CPTAC or DREAM4 non-fallback rows moved from `metadata-needed` to `blocked-or-reference`; do not commit until that movement is accepted or the annotation strategy is revised.

---

### Task 5: Inspect Diff And Commit Commons Metadata

**Files:**
- Commit in `~/d/science-commons`:
  - `datasets/ccle-proteomics-nusinow-2020/entity.md`
  - `datasets/cptac-proteogenomics/entity.md`
  - `datasets/dream4-in-silico-network/entity.md`

- [ ] **Step 1: Inspect science-commons diff**

Run:

```bash
git -C ~/d/science-commons status --short
git -C ~/d/science-commons diff -- datasets/ccle-proteomics-nusinow-2020/entity.md datasets/cptac-proteogenomics/entity.md datasets/dream4-in-silico-network/entity.md
```

Expected: only the three target entity files are modified, and each diff adds exactly one `support:` block under the intended task.

- [ ] **Step 2: Commit commons metadata**

Run:

```bash
git -C ~/d/science-commons add datasets/ccle-proteomics-nusinow-2020/entity.md datasets/cptac-proteogenomics/entity.md datasets/dream4-in-silico-network/entity.md
git -C ~/d/science-commons commit -m "Annotate fallback benchmark task support"
```

Expected: one commons commit containing only the three metadata files.

- [ ] **Step 3: Confirm science-commons is clean**

Run:

```bash
git -C ~/d/science-commons status --short
```

Expected: no output.

---

### Task 6: Commit Science Planning Artifacts

**Files:**
- Modify: `docs/plans/2026-07-03-benchmark-fallback-support-annotation-design.md`
- Create: `docs/plans/2026-07-03-benchmark-fallback-support-annotation-implementation-plan.md`

- [ ] **Step 1: Inspect science worktree diff**

Run from `~/d/science/.worktrees/benchmark-fallback-support-annotation`:

```bash
git status --short
git diff --stat
git diff -- docs/plans/2026-07-03-benchmark-fallback-support-annotation-design.md docs/plans/2026-07-03-benchmark-fallback-support-annotation-implementation-plan.md
```

Expected: only the design and implementation plan docs are dirty/untracked.

- [ ] **Step 2: Commit science planning docs**

Run:

```bash
git add docs/plans/2026-07-03-benchmark-fallback-support-annotation-design.md docs/plans/2026-07-03-benchmark-fallback-support-annotation-implementation-plan.md
git commit -m "docs: plan benchmark fallback support annotation"
```

Expected: one science commit containing only the planning docs.

- [ ] **Step 3: Confirm final repo states**

Run:

```bash
git status --short
git -C ~/d/science-commons status --short
```

Expected: no output from either repo.

---

## Self-Review Checklist

- Spec coverage:
  - CCLE `supported` support metadata is covered in Task 2.
  - CPTAC and DREAM4 `candidate` support metadata is covered in Task 3.
  - Commons validation is covered in Task 4.
  - Fallback count improvement is covered in Task 4.
  - Suppressed blocked-support guardrail is covered in Task 4.
  - Unfiltered non-fallback bucket movement guardrail is covered in Task 4.
  - Separate `science` and `science-commons` commits are covered in Tasks 5 and 6.
- Placeholder scan:
  - No placeholder steps, no open-ended "add tests" instructions, and no unspecified files.
- Type/schema consistency:
  - Support states use `supported` and `candidate`.
  - Candidate reasons are lowercase kebab-case.
  - `checked_at` values use `YYYY-MM-DD`.
  - Support fields are limited to `state`, `reason`, `checked_at`, `evidence`, and `notes`.
