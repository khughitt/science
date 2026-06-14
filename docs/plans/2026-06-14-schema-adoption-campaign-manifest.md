# Schema Adoption Campaign — Manifest

Audited 2026-06-14. Statuses: `pending` | `done` | `no-op` | `blocked-data`.
Paths are package directories relative to each project root. No pushes — all commits stay local.

## mm30  [~/d/cancer/cancer-types/multiple-myeloma]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/external/ccle_proteomics/2020-01 | json | 2 | done | pending | commit 5a32847d |
| data/external/ctrp_v2/2015 | json | 3 | done | pending | commit 5e368dd2 |
| data/external/gdsc_v2/2022-07-24 | json | 3 | done | pending | commit 65edc4d3 |
| data/external/oetjen_2018/2018-10 | json | 1 | done | pending | schema pre-existed (write a no-op); 2 non-tabular files absent |
| data/external/opentargets/25.03 | json | 3 | done | pending | commit a082d175 |
| data/external/walker_2024/2024-05 | json | 6 | done | pending | commit d66028e6 — 4 present tabular schema'd; 4 files absent locally stay blocked-data |

## cancer-therapeutics  [~/d/cancer/therapeutics]  — all YAML

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/chembl-activities | yaml | 1 | done | pending | commit 3879ab4 — **newly git-tracked** (force-add past data/raw/ ignore) |
| data/raw/chembl | yaml | 1 | done | pending | commit 7084e12 |
| data/raw/dgidb | yaml | 2 | done | pending | commit 13f52fc — 1 resource blocked-data (../../processed absent) |
| data/raw/drugcomb | yaml | 1 | done | pending | commit 118c233 |
| data/raw/nci-almanac | yaml | 0 | no-op | no-op | no tabular resources |
| data/raw/nsc-crosswalk | yaml | 1 | done | pending | commit 5fb915b |
| data/raw/opentargets | yaml | 1 | done | pending | commit de6b855 — **newly git-tracked** (force-add past data/raw/ ignore) |
| data/raw/string | yaml | 0 | no-op | no-op | no tabular resources |

## cancer-evolution  [~/d/cancer/mechanisms/evolution]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/ampliconrepository-kim2024-pcawg | json | 9 | done | pending | commit 061b1d0 |
| data/raw/ampliconrepository-kim2024-tcga | json | 9 | done | pending | commit 141174c |
| data/raw/kim2024-supplement | json | 0 | no-op | no-op | no tabular resources |
| data/raw/nct02415621-trial-patient-data | json | 0 | no-op | no-op | no tabular resources |

## health-meta  [~/d/health/meta]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| code/scripts/external/reactome | yaml | 6 | blocked-data | blocked-data | all 6 CSVs absent locally — needs hydration |

## Phase 1 status — COMPLETE (2026-06-14)

All 14 effective-working-set packages are shape-done (names+types written, gated, committed
local, NOT pushed; every change verified value-safe — only `schema` added, all other descriptor
content preserved; YAML ISO timestamps preserved as strings, re-quoted only). 8 JSON +
6 cancer-therapeutics YAML. no-op (0 tabular): nci-almanac, string, kim2024-supplement,
nct02415621. blocked-data: reactome (whole package); plus absent resources within walker_2024,
dgidb, oetjen_2018.

**Scaffold defect — FIXED.** The YAML timestamp coercion in `infer_schema.load_descriptor`
(`yaml.safe_load` parsed ISO timestamps to `datetime`, dropping the `T`) was fixed by a custom
`_RoundTripSafeLoader` that strips only the implicit timestamp resolver (+ round-trip regression
tests). Merged to local `main` (a93757b8). This unblocked the 6 YAML packages.

**OPEN organizational decision (needs user).** The cancer-therapeutics `datapackage.yaml`
descriptors live under `data/raw/`, which `.gitignore` excludes (data bytes). 4 descriptors were
already force-added/tracked historically; the campaign newly force-added **chembl-activities** and
**opentargets** (commits 3879ab4, de6b855) to match. Cleaner per "organization over workarounds":
add a `.gitignore` exception (`!data/raw/**/datapackage.yaml`) so all descriptors track by rule
instead of scattered force-adds. Pending user choice: (a) keep force-adds; (b) add gitignore
exception; (c) un-track the 2 new ones.

## Next: Phase 2 (paused before)

Structural-meaning authoring (required/enum/primaryKey + relational foreignKeys/composite keys,
two-tier evidence rule), subagent per package + over-authoring review + user spot-check, across
all `done` packages. Per-package done-gate = validate exit 0 (partial walker/dgidb/oetjen = fails
only name manifest-recorded absent resources, S3 json check).
