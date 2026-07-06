# dbSNP Variant Labels Modular Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the completed dbSNP source downloads and refactor `dataset:variant-labels-dbsnp-human` so expensive work is split into durable shard outputs instead of one multi-day SQLite build.

**Architecture:** Keep the recipe local to `~/d/science-commons/datasets/variant-labels-dbsnp-human`. The workflow first verifies/fetches pinned archives, then splits each VCF once into deterministic rsID shards, builds one SQLite per archive/shard, and merges those shard databases into the final `rsid_mappings.sqlite`. Snakemake owns markers and shard files, while `datapackage.yaml` remains a tracked descriptor updated only after the final SQLite and summary exist.

**Tech Stack:** Python 3.13, Snakemake, SQLite, gzip VCF parsing, pytest, YAML datapackage metadata.

---

### Task 1: Preserve Existing State

**Files:**
- Modify: `~/d/science-commons/datasets/variant-labels-dbsnp-human/datapackage.yaml`
- Add: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/lockfile.yaml`
- Inspect only: `/data/science-commons/variant-labels-dbsnp-human/_src/*`

- [ ] **Step 1: Restore the tracked datapackage descriptor**

Run:

```bash
git -C ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle restore datasets/variant-labels-dbsnp-human/datapackage.yaml
```

Expected: `git status --short` no longer shows `D datasets/variant-labels-dbsnp-human/datapackage.yaml`.

- [ ] **Step 2: Keep the generated lockfile**

Run:

```bash
git -C ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle add datasets/variant-labels-dbsnp-human/recipe/lockfile.yaml
git -C ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle diff --cached -- datasets/variant-labels-dbsnp-human/recipe/lockfile.yaml
```

Expected: the staged lockfile pins exactly `GCF_000001405.40.gz` and `GCF_000001405.25.gz` with URL, `.md5`, SHA256, MD5, and byte counts.

### Task 2: Tests for Durable Sharding

**Files:**
- Create: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/test_build.py`
- Modify: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/build.py`

- [ ] **Step 1: Add failing tests for split, shard build, merge, and complete split reuse**

Add tests that create tiny gzipped VCF fixtures with two rsIDs, split them into four shards, build shard SQLite files, merge them, and assert:

```python
assert (split_dir / "shard-01.tsv.gz").is_file()
assert merged_summary["retained_alleles"] == 2
assert merged_summary["distinct_rsids"] == 2
assert reused_summary == first_summary
```

Run:

```bash
uv run --frozen --project ~/d/science/meta pytest ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle/datasets/variant-labels-dbsnp-human/recipe/test_build.py -q
```

Expected: fail because the shard APIs do not exist yet.

- [ ] **Step 2: Implement split/build/merge APIs**

In `build.py`, add:

```python
SHARD_COUNT = 64
SHARD_IDS = tuple(f"{index:02x}" for index in range(SHARD_COUNT))
ROW_FIELDS = ("rsid", "contig", "pos0", "ref", "alt", "source_vcf", "allele_index")
```

Add functions:

```python
def shard_id_for_rsid(rsid: str, *, shard_count: int = SHARD_COUNT) -> str: ...
def split_archive_to_shards(*, archive_path: Path, source_vcf: str, output_dir: Path, shard_count: int = SHARD_COUNT) -> dict[str, Any]: ...
def build_shard_sqlite(*, rows_path: Path, sqlite_path: Path, seqcol_digest: str, shard_id: str, source_vcf: str) -> dict[str, Any]: ...
def merge_shard_sqlites(*, shard_paths: list[Path], split_summary_paths: list[Path], shard_summary_paths: list[Path], output_dir: Path, lockfile_path: Path, datapackage_path: Path | None = None) -> dict[str, Any]: ...
```

Expected behavior:
- `split_archive_to_shards` writes `shard-<id>.tsv.gz` files and `split-summary.yaml` under an atomic temporary directory, then renames the directory into place.
- If the split output directory already has all shard files and a summary, it returns the existing summary without deleting or rewriting it.
- If the split output directory exists but is incomplete, it fails early with `FileExistsError`.
- `build_shard_sqlite` writes one shard SQLite atomically and writes no final output on failure.
- `merge_shard_sqlites` consumes existing shard SQLite files, writes the final SQLite and summary atomically, then refreshes `datapackage.yaml` only after both final outputs exist.

- [ ] **Step 3: Verify tests pass**

Run:

```bash
uv run --frozen --project ~/d/science/meta pytest ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle/datasets/variant-labels-dbsnp-human/recipe/test_build.py -q
```

Expected: all tests pass.

### Task 3: Refactor Snakemake Workflow

**Files:**
- Modify: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/Snakefile`
- Modify: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/README.md`

- [ ] **Step 1: Update the workflow rules**

Change `Snakefile` so:
- `rule all` requires the final SQLite, final summary, existing datapackage descriptor, and all split markers/shard SQLite summaries.
- `datapackage.yaml` is never listed in any rule `output:`.
- `rule split_archive` writes only a marker as Snakemake output and writes durable rows under `_work/splits/<archive-stem>/`.
- `rule build_shard` builds one SQLite per archive/shard under `_work/shards/<archive-stem>/shard-<id>.sqlite`.
- `rule merge_dataset` merges all shard SQLite files into `rsid_mappings.sqlite` and `build-summary.yaml`, with `datapackage.yaml` passed as a param, not an output.

- [ ] **Step 2: Update operator docs**

Document:
- existing source archives are reused through `recipe/lockfile.yaml`;
- split rows and shard SQLite files are durable under `$SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/_work/`;
- rerunning Snakemake must not delete `datapackage.yaml`;
- a failed final merge can be rerun without repeating source downloads or completed shard builds.

- [ ] **Step 3: Run a dry DAG check only**

Run:

```bash
uv run --frozen --project ~/d/science/meta snakemake \
  -s ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle/datasets/variant-labels-dbsnp-human/recipe/Snakefile \
  --config dataset_output_dir=/tmp/dbsnp-dag-check commons_data_root=/tmp output_root=/tmp \
  --cores 1 \
  -n
```

Expected: Snakemake builds the DAG without running jobs. Do not run the full workflow in this task.

### Task 4: Final Verification and Commit

**Files:**
- All changed files in `~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle`
- This implementation plan in `~/d/science/docs/plans/`

- [ ] **Step 1: Run focused tests**

Run:

```bash
uv run --frozen --project ~/d/science/meta pytest \
  ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle/datasets/variant-labels-dbsnp-human/recipe/test_fetch.py \
  ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle/datasets/variant-labels-dbsnp-human/recipe/test_build.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Check diffs for path and whitespace issues**

Run:

```bash
git -C ~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle diff --check
git -C ~/d/science diff --check
```

Expected: no output.

- [ ] **Step 3: Commit independently**

In `~/d/science`, commit this plan:

```bash
git add docs/plans/2026-07-06-dbsnp-variant-labels-modular-workflow-plan.md
git commit -m "docs: plan dbsnp modular workflow"
```

In `~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle`, commit the recipe refactor:

```bash
git add datasets/variant-labels-dbsnp-human
git commit -m "fix: shard dbsnp variant label workflow"
```

### Task 5: Deferred Operator Full Build

**Files:**
- No code changes.

- [ ] **Step 1: Run only after the refactor commit**

Run the actual full build separately:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons/.worktrees/dbsnp-variant-labels-lifecycle \
science commons dataset build variant-labels-dbsnp-human --cores 8
```

Expected: source downloads are reused, split/shard work is resumable, and failed final merge does not remove completed shard databases or the tracked datapackage descriptor.
