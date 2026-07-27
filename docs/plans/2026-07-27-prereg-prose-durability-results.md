# `prereg.prose-path-nondurable` — certification results

Measured against `docs/plans/2026-07-27-prereg-prose-durability-design.md` at
commit `7cbc7e6b`.

## Measurement method

The validator ran against every project in the measured fleet. Each complete
report was retained as JSON and findings were selected by exact `rule`
equality; no rendered-output substring count was used. Pre-registration totals
were counted from each project's `entities/pre-registrations/` directory.

All commands below were run from `science/` inside the
`prereg-prose-durability` worktree, so `uv run --frozen science validate`
executed the branch's code, including the new rule. The validation loop in
Step 2 (the `while ... science validate ...` block) was executed as a
background run split across two shell invocations purely for wall-clock
reasons — 11 projects at roughly a minute each exceeds a single foreground
tool call in the harness that ran this certification. The cohort-derivation
half (`find -H` discovery, the `cohort.tsv` build, and the `-ne 11` guard) ran
to completion unmodified in the first invocation; the validation loop was
re-run alone, unmodified in its guard logic (the `if`-wrapped `science
validate` call and the `[ ! -s "$out" ]` fatal check), in the second.
`CERT_DIR` was re-declared to the same fixed literal
(`/tmp/prose-path-nondurable-cert`) at the top of the second invocation, so
the loop read back the same `cohort.tsv` and wrote into the same report
directory the first invocation had produced — no scope was lost across the
split. Every
guard described in the plan — the `find -H` (not `-L`) discovery, the
"no `2>/dev/null`" rule on the inner `find`, the explicit `if` around the
per-project count test, the cohort-size `-ne 11` FATAL, the `if`-wrapped
`science validate` invocation, the missing/empty-report FATAL, and the
final `-ne 11` reports-written FATAL — ran exactly as written in the plan.
No project was skipped, retried, or silently treated as zero.

Step 2 (verbatim, as it appears in the task brief):

```bash
set -euo pipefail
CERT_DIR=/tmp/prose-path-nondurable-cert
rm -rf "$CERT_DIR"
mkdir -p "$CERT_DIR"

# `-H` follows ONLY the command-line `~/d` symlink, not nested ones. `-L` also
# descends alias trees and double-counts the same project: `~/d/r/cbioportal` ->
# `cancer/data-sources/cbioportal` and `~/d/r/mm30` ->
# `cancer/cancer-types/multiple-myeloma`. With `-L` this yields 25 projects and a
# 13-row cohort for the same 11 real ones, inflating every total.
find -H ~/d -maxdepth 5 -name science.yaml \
     -not -path "*/.worktrees/*" -not -path "*/templates/*" -not -path "*/tests/*" \
     -printf '%h\n' | sort > "$CERT_DIR/all-projects.txt"

# No `2>/dev/null` on the inner find: a real failure must surface, not be
# mistaken for "this project has no pre-registrations". The directory test is
# what handles the ordinary absent case.
: > "$CERT_DIR/cohort.tsv"
while IFS= read -r root; do
  [ -d "$root/entities/pre-registrations" ] || continue
  count=$(find "$root/entities/pre-registrations" -maxdepth 1 -name '*.md' | wc -l)
  # An explicit `if`, not `[ ... ] && printf`: under `set -e` a false test as the
  # last statement in the loop body would abort the whole discovery pass.
  if [ "$count" -gt 0 ]; then
    printf '%s\t%s\n' "$count" "$root" >> "$CERT_DIR/cohort.tsv"
  fi
done < "$CERT_DIR/all-projects.txt"

echo "projects discovered: $(wc -l < "$CERT_DIR/all-projects.txt")"
echo "cohort:"; cat "$CERT_DIR/cohort.tsv"

cohort_rows=$(wc -l < "$CERT_DIR/cohort.tsv")
if [ "$cohort_rows" -ne 11 ]; then
  echo "FATAL: cohort has $cohort_rows rows, expected 11. The project layout has" >&2
  echo "changed since this plan was written; the design's table needs remeasuring," >&2
  echo "not reinterpreting. Do not proceed." >&2
  exit 1
fi

# `science validate` exits 1 when a report CONTAINS error findings, having
# written the JSON successfully -- a normal outcome for several projects. Run it
# as an `if` condition so `set -e` does not abort on that expected non-zero, and
# treat only a missing or empty report as fatal.
while IFS=$'\t' read -r count root; do
  slug=$(printf '%s' "$root" | sed "s|^$HOME/d/||; s|/|__|g")
  out="$CERT_DIR/$slug.json"
  if uv run --frozen science validate --project-root "$root" --format json --output "$out"; then
    rc=0
  else
    rc=$?
  fi
  if [ ! -s "$out" ]; then
    echo "FATAL: $root exited $rc and wrote no usable report at $out" >&2
    exit 1
  fi
  printf 'ok  rc=%-3s %5s pre-regs  %s\n' "$rc" "$count" "$slug"
done < "$CERT_DIR/cohort.tsv"

reports=$(find "$CERT_DIR" -maxdepth 1 -name '*.json' | wc -l)
if [ "$reports" -ne 11 ]; then
  echo "FATAL: $reports reports written, expected 11" >&2
  exit 1
fi
echo "reports written: $reports"
```

Measured output: `projects discovered: 22`, 11 cohort rows totalling 144
pre-registrations, 11 reports written, no `FATAL`. Several projects exited
`rc=1` (error-severity findings from other rules) — expected, not a
certification failure.

Step 3 (verbatim):

```bash
uv run --frozen python - <<'PY'
import collections
import json
import pathlib

CERT_DIR = pathlib.Path("/tmp/prose-path-nondurable-cert")
RULE = "prereg.prose-path-nondurable"
HOME_D = str(pathlib.Path.home() / "d") + "/"

rows = []
for line in (CERT_DIR / "cohort.tsv").read_text().splitlines():
    count, root = line.split("\t")
    slug = root.replace(HOME_D, "").replace("/", "__")
    report = CERT_DIR / f"{slug}.json"
    if not report.is_file():
        raise SystemExit(
            f"MISSING REPORT: {report}. Certification is invalid -- a project that was "
            f"never validated must not be recorded as zero findings. Re-run Step 2."
        )
    hits = [r for r in json.loads(report.read_text())["results"] if r.get("rule") == RULE]
    docs = collections.Counter(r.get("path") for r in hits)
    rows.append((root.replace(HOME_D, ""), int(count), len(docs), hits))

rows.sort(key=lambda r: (-len(r[3]), r[0]))
print(f"{'project':46} {'pre-regs':>9} {'docs':>5} {'findings':>9}")
for name, npre, ndocs, hits in rows:
    print(f"{name:46} {npre:9} {ndocs:5} {len(hits):9}")
print(
    f"{'TOTAL (' + str(len(rows)) + ' projects)':46} "
    f"{sum(r[1] for r in rows):9} {sum(r[2] for r in rows):5} {sum(len(r[3]) for r in rows):9}"
)
print("\n=== design predicted: 11 projects, 144 pre-registrations, 10 documents, 16 findings\n")
for name, _, _, hits in rows:
    for hit in hits:
        print(f"  {name:40} {hit.get('path')}\n      {hit.get('message')}")
PY
```

## Result

One row per cohort member, in the order Step 3 printed them (most findings
first, then alphabetical).

| project | pre-registrations | documents | findings |
|---|---:|---:|---:|
| natural-systems | 34 | 4 | 6 |
| cancer/data-sources/cbioportal | 4 | 2 | 4 |
| cancer/mechanisms/evolution | 4 | 1 | 2 |
| protein-landscape | 3 | 1 | 2 |
| cancer/cancer-types/multiple-myeloma | 61 | 1 | 1 |
| cancer/therapeutics | 4 | 1 | 1 |
| 3d-attention-bias | 4 | 0 | 0 |
| health/comparisons/pan-disease | 14 | 0 | 0 |
| health/processes/cycles | 5 | 0 | 0 |
| health/processes/post-acute-infection | 6 | 0 | 0 |
| seq-feats | 5 | 0 | 0 |
| **total (11 projects)** | **144** | **10** | **16** |

Design predicted 11 projects, 144 pre-registrations, 10 documents, 16 findings.
Measured: 11/144/10/16 — matches exactly, on every one of the four numbers.

## Findings

All 16 findings report the `gitignored` durability state; none report
`not tracked by git`. `document` is the frozen pre-registration containing the
prose reference; `path` is the repo-relative path named in that prose.

| project | document | path | state |
|---|---|---|---|
| natural-systems | entities/pre-registrations/0001-pre-registration-limit-chain-transitivity-h01-and-triangle-inequality.md | pipeline/graph-analysis/data/graph-export.json | ignored |
| natural-systems | entities/pre-registrations/0014-pre-registration-amendment-h07-beta-selection-and-robustness-arbitration.md | data/processed/arxiv/datapackage.json | ignored |
| natural-systems | entities/pre-registrations/0026-fixed-margin-incidence-null-topology.md | pipeline/graph-analysis/data | ignored |
| natural-systems | entities/pre-registrations/0026-fixed-margin-incidence-null-topology.md | pipeline/h03/results/betti.json | ignored |
| natural-systems | entities/pre-registrations/0026-fixed-margin-incidence-null-topology.md | pipeline/graph-analysis/data/graph-export.json | ignored |
| natural-systems | entities/pre-registrations/0028-q0180-topic-blocking-incremental-recall-protocol.md | data/processed/formulation-breadth/source-ids.txt | ignored |
| cancer/data-sources/cbioportal | entities/pre-registrations/0002-pre-registration-t126-per-study-aggregate-sbs1-lrr-bias-test.md | results/signature-brca-2026-04-22 | ignored |
| cancer/data-sources/cbioportal | entities/pre-registrations/0002-pre-registration-t126-per-study-aggregate-sbs1-lrr-bias-test.md | data/gene_replication_timing.feather | ignored |
| cancer/data-sources/cbioportal | entities/pre-registrations/0003-h08-positive-control-agnostic-association-must-recover-known-signature.md | results/poc-2026-04-17/metadata/samples_annotated.feather | ignored |
| cancer/data-sources/cbioportal | entities/pre-registrations/0003-h08-positive-control-agnostic-association-must-recover-known-signature.md | data/mc3.v0.2.8.PUBLIC.maf.gz | ignored |
| cancer/mechanisms/evolution | entities/pre-registrations/0003-pre-registration-t064-q095-tcga-driver-mp-coupling.md | data/raw/t063-q095-tcga-public-payload/pancan_rnaseq_freeze.tsv.gz | ignored |
| cancer/mechanisms/evolution | entities/pre-registrations/0003-pre-registration-t064-q095-tcga-driver-mp-coupling.md | data/raw/t063-q095-tcga-public-payload/pancan_mutation_freeze.tsv.gz | ignored |
| protein-landscape | entities/pre-registrations/0003-pre-registration-q81-curator-derived-non-structural-benchmark-follow-up.md | results/heldout-taxa-benchmark | ignored |
| protein-landscape | entities/pre-registrations/0003-pre-registration-q81-curator-derived-non-structural-benchmark-follow-up.md | results/heldout-taxa-benchmark/q81-evaluation | ignored |
| cancer/cancer-types/multiple-myeloma | entities/pre-registrations/0058-t868-bcl2-dependency-venetoclax-p3-beyond-t1114.md | data/external/ctrp_v2/2015/ctrpv2-sensitivity-long.parquet | ignored |
| cancer/therapeutics | entities/pre-registrations/0001-a1-independent-action-calibration-of-nci-almanac.md | data/raw/nci-almanac/ComboDrugGrowth_Nov2017.zip | ignored |

## Gate status

`prereg.prose-path-nondurable` appears in no tier of `gates.py`; pinned by
`test_durability_failures_gate_the_build_but_undeclared_does_not`. Confirmed
directly against the shipped source: `gates.py` documents the rule's
deliberate absence from every tier, and the test asserts
`"prereg.prose-path-nondurable" not in gated` alongside the five durability
rules that *are* gated (`prereg.vehicle-gitignored`, `prereg.vehicle-untracked`,
`prereg.vehicle-hash-drift`, `prereg.vehicle-missing`,
`prereg.vehicle-uncontent-addressed`).

## Snapshots

**The real certification result: on the `_combined` fixture, the new rule
produces zero findings, exactly as the plan predicted.** `_combined` has no
`entities/pre-registrations/` directory, so `prereg.prose-path-nondurable`
correctly contributes no findings against it, and `json_default.json` —
which renders that finding list — matched the stored snapshot exactly.

Separately, `uv run --frozen pytest tests/validate -q -m snapshot` reported 1
failed, 1 passed: `text_default.txt` diverged on exactly one line —

```
-Checks: 68 included, 0 skipped (profile: full)
+Checks: 69 included, 0 skipped (profile: full)
```

— with every other line, including the full findings list, byte-identical.
This is **pre-existing on the branch base and independent of the shipped
rule**: reverting only `src/science_tool/validate/checks/prereg_vehicles.py`
to the branch base commit `f2f5c5e3` and re-running
`NO_COLOR=1 uv run --frozen pytest tests/validate -q -m snapshot` reproduces
the identical `68 → 69` diff. `included_count` at
`src/science_tool/validate/cli.py:260-261` is `len(result.sections)` — the
count of registered `@Check` functions, not of rules within a check. This
branch's two commits (`80d378e8`, `7cbc7e6b`) add a rule inside the existing
`check_prereg_vehicles` check function and add no new `@Check`, confirmed by
inspecting their diffs directly: neither adds a `@Check`-decorated function,
only private helpers (`_prose_message`, `_check_prose_paths`) called from the
existing check. The mechanism that would explain a `68 → 69` count shift by
this branch's own code therefore does not exist, and the isolation test rules
it out directly. `git log --oneline -- tests/validate/snapshots/text_default.txt`
additionally shows the snapshot file's own last edit was an unrelated commit
(`b59a38d0`) predating both shipping commits — consistent with, but not by
itself sufficient to establish, staleness that predates this branch.

The actual origin of the `68 → 69` staleness is unidentified and out of scope
for this task. It is a pre-existing upstream defect that this certification
surfaced, not a regression introduced by the rule under certification.

(A first run under this session's ambient shell showed additional ANSI color
codes in the diff; that was a `FORCE_COLOR=3` environment artifact unrelated
to the branch, confirmed by re-running with `FORCE_COLOR` unset and `NO_COLOR=1`,
which isolated the diff to the single line above.)

Per the task brief, this is reported rather than fixed: `scripts/update-
validate-snapshots.py` was not run, and the rule/test/fixture were not
touched.

## Filing

`fb-2026-07-27-009` against `check:prereg.vehicle-undeclared`, filed before
implementation. **Status: open — closed in Task 8, which rewrites this section.**
