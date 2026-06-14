# Schema Adoption Campaign — Manifest

Audited 2026-06-14. Statuses: `pending` | `done` | `no-op` | `blocked-data`.
Paths are package directories relative to each project root. No pushes — all commits stay local.

## mm30  [~/d/cancer/cancer-types/multiple-myeloma]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/external/ccle_proteomics/2020-01 | json | 2 | done | done | P1 5a32847d; P2 9e5002c8 — composite PK [Protein_Id,ccle_code] + FK ccle_code→cell-lines; assay-cohort enums |
| data/external/ctrp_v2/2015 | json | 3 | done | done | P1 5e368dd2; P2 194a92b8 — integer PKs on both lookups + 2 FKs from sensitivity-long; CCLE site/histology enums |
| data/external/gdsc_v2/2022-07-24 | json | 3 | done | done | P1 65edc4d3; P2 cc7e77ed — curve/cell-line PKs + cosmic_id FK; single-value enums on dataset/webrelease trimmed b876a573 (required kept) |
| data/external/oetjen_2018/2018-10 | json | 1 | done | done | P2 56fb7984 — **first git-tracking of descriptor** (removed oetjen descriptor-ignore .gitignore line; data file stays ignored); donor_id PK |
| data/external/opentargets/25.03 | json | 3 | done | done | P1 a082d175; P2 6d46a12a — assoc/tractability PKs + FK; EFO/MONDO disease + drug-type enums |
| data/external/walker_2024/2024-05 | json | 6 | done | done | P1 d66028e6; P2 8b737283 — 4 present resources (cell_barcode/symbol PKs, 2 FKs, 28/166 required); **4 absent resources** (2 parquet + 14GB h5ad + qc-report json) stay blocked-data |

## cancer-therapeutics  [~/d/cancer/therapeutics]  — all YAML

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/chembl-activities | yaml | 1 | done | done | P1 3879ab4 (git-tracked via .gitignore exception); P2 42e50281 — composite PK [chembl_id,gene_symbol] |
| data/raw/chembl | yaml | 1 | done | done | P1 7084e12; P2 8bcc356 — 5 required; no PK (drug×target non-unique) |
| data/raw/dgidb | yaml | 2 | done | done | P1 13f52fc; P2 ce4f9fd — raw-table required+enums, no PK; 1 resource blocked-data (../../processed parquet absent) |
| data/raw/drugcomb | yaml | 1 | done | done | P1 118c233; P2 313a7bd — composite PK [block_id,conc_r,conc_c]; 23-value study_name enum |
| data/raw/nci-almanac | yaml | 0 | no-op | no-op | no tabular resources |
| data/raw/nsc-crosswalk | yaml | 1 | done | done | P1 5fb915b; re-inferred 0e83835 (fetch-script regen stripped schema); P2 a2e1921 — PK [nsc]; map_status enum [ambiguous,mapped,unmapped] |
| data/raw/opentargets | yaml | 1 | done | done | P1 de6b855 (git-tracked via .gitignore exception); P2 39bc5ef — composite PK [drug_chembl_id,target_gene_symbol]; 29-value action_type enum |
| data/raw/string | yaml | 0 | no-op | no-op | no tabular resources |

## cancer-evolution  [~/d/cancer/mechanisms/evolution]

| Package | Fmt | Tabular | Phase 1 (shape) | Phase 2 (meaning) | Notes |
|---|---|---|---|---|---|
| data/raw/ampliconrepository-kim2024-pcawg | json | 9 | done | done | P1 061b1d0; P2 9ce468c — 9-table grains, single+composite PKs, subset-verified FKs; rejected 3 false FKs; headerless ecDNA_context_calls flagged |
| data/raw/ampliconrepository-kim2024-tcga | json | 9 | done | done | P1 141174c; P2 6e99379 — mirror of pcawg; PKs + 9 subset-verified FKs; rejected NA-placeholder FKs |
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

**Organizational decision — RESOLVED.** The cancer-therapeutics `datapackage.yaml` descriptors live
under gitignored `data/raw/`. Per "organization over workarounds", added a `.gitignore` exception
(ignore `data/raw/**` but descend and re-include `**/datapackage.yaml`; commit 5e397f9) so all
descriptors (incl. the newly-tracked chembl-activities + opentargets) track by rule, not force-add.
Verified: descriptors un-ignored, data payloads still ignored.

**Dropbox-sync caveat (for Phase 2).** These repos are Dropbox-synced; during this session nsc-crosswalk's
working-tree descriptor AND its data payload were transiently removed by a sync event. The committed
descriptor was restored from HEAD (schema intact — it was validly inferred from real data at commit
time); its data file (`../../processed/a2/nsc_crosswalk.tsv`) remains transiently absent and should
re-sync. Before Phase 2 runs, confirm each package's data files are present (the meaning-authoring
needs to read them); re-verify repo branch before any commit (mm30 especially).

## Phase 2 status — COMPLETE (2026-06-14)

All 14 effective-working-set packages have authored structural meaning (one subagent per package,
two-tier evidence rule, over-authoring review). Each authored invariant was verified against the
FULL data, not a sample — the discipline caught real traps: a 138-column required set rejected in
walker (sample said non-null, full data had 35k nulls); Description/drug_name-as-PK rejected
repeatedly; three false FKs in amplicon-pcawg and the NA-placeholder FKs in amplicon-tcga rejected
on exact subset miss. Relational invariants (PKs + subset-verified FKs) authored where the data
proved them; per-resource invariants only where the report surfaced AND data confirmed.

Per-package done-gate met: `validate --path` exit 0 for fully-present packages; for the partially-
blocked ones (walker_2024, dgidb) the ONLY gate failures are the manifest-recorded absent data files
(S3 json check), with zero failures on any present resource.

**Two judgment calls (spot-checked by user 2026-06-14):**
- **gdsc_v2** single-value enums on `dataset={GDSC2}` / `webrelease={Y}` — **RESOLVED: trimmed**
  (b876a573); `required` kept. User chose the conservative standard.
- **oetjen_2018**: its descriptor was previously gitignored (an oetjen-specific descriptor-ignore
  line peers lacked), so Phase 1's no-op never tracked it. P2 commit removed that one .gitignore line
  (data file still ignored) → first git-tracking. Consistent with the cancer-therapeutics descriptor
  exception chosen earlier.

**Volatility note:** nsc-crosswalk's descriptor is regenerated by `fetch_nsc_crosswalk.py`, which
strips the `schema` block on each run (it stripped P1's; re-inferred at 0e83835 before P2). Authored
schema there is durable only until the next fetch re-run — making the generator preserve/emit schema
is future work, out of this campaign's scope.
