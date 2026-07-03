# Bio Identity P4.4 Cytoband Proxy Reference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish P4.4 by promoting UCSC hg19 cytoBand as `dataset:cytoband-hg19`, adding a hash-verified offline Science cytoband reader, and proving `dataset:cytoband-hg19` works as a real `proxy.via` reference artifact.

**Architecture:** `~/d/science-commons` owns the pinned UCSC source, deterministic `cytobands.csv`, datapackage metadata, and dataset entity. `~/d/science` owns the runtime reader, reduced commons-style fixture, proxy provenance tests, and umbrella status update. Runtime code reads only through the commons resolver; network use is limited to the operator-run fetch recipe.

**Tech Stack:** Python 3.12, pytest, Ruff, Frictionless-style datapackage YAML, UCSC `cytoBand.txt.gz`, Science commons resolver.

---

## Preconditions

- Work in `~/d/science/.worktrees/bio-identity-p4-cytoband` on branch `bio-identity-p4-cytoband`.
- Create a matching `~/d/science-commons/.worktrees/bio-identity-p4-cytoband` worktree on branch `bio-identity-p4-cytoband` before editing commons bytes.
- Keep commits split by repo: commons artifact commits in `~/d/science-commons`, Science reader/tests/docs commits in `~/d/science`.
- Runtime tests must not fetch the network.
- Use `~/d/` paths in docs/comments, not absolute Dropbox paths.
- Source pin for P4.4:

```text
URL: https://hgdownload.cse.ucsc.edu/goldenPath/hg19/database/cytoBand.txt.gz
Compressed bytes: 6609
Compressed SHA-256: f9b82309b2bca1eb9d91a5cb2c6aa0528351158e6e20b51d82cca36d01735cba
Decompressed source rows: 862
```

## File Structure

`~/d/science-commons`:

- `datasets/cytoband-hg19/entity.md` - dataset entity for the public reference artifact.
- `datasets/cytoband-hg19/datapackage.yaml` - datapackage with one `cytobands` CSV resource and hash/bytes.
- `datasets/cytoband-hg19/cytobands.csv` - deterministic normalized UCSC hg19 cytoband table.
- `datasets/cytoband-hg19/.gitignore` - ignore local fetched source bytes under `sources/`.
- `datasets/cytoband-hg19/recipe/lockfile.yaml` - pinned UCSC URL, compressed source hash, compressed byte count, and source row count.
- `datasets/cytoband-hg19/recipe/fetch.py` - operator-run network fetch/verify helper.
- `datasets/cytoband-hg19/recipe/build.py` - lockfile-verified builder for `cytobands.csv` and `datapackage.yaml`.
- `datasets/cytoband-hg19/recipe/README.md` - recipe usage and source notes.

`~/d/science`:

- `science/src/science_tool/commons/cytoband.py` - runtime row reader and interval-overlap helper.
- `science/tests/test_commons_cytoband.py` - parser, resolver fixture, and overlap tests.
- `science/tests/fixtures/commons/cytoband/datasets/cytoband-hg19/entity.md` - reduced metadata fixture.
- `science/tests/fixtures/commons/cytoband/datasets/cytoband-hg19/datapackage.yaml` - reduced datapackage fixture.
- `science/tests/fixtures/commons/cytoband-data/cytoband-hg19/cytobands.csv` - reduced hash-verified data fixture.
- `science/tests/test_dataset_register_run.py` - real-slug `proxy.via` register-run routing assertion.
- `science/tests/validate/test_checks_identity_context.py` - real-slug proxy provenance assertion.
- `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md` - mark P4.4 landed and move to P5 re-planning.

## Task 1: Create Commons Cytoband Artifact Skeleton

**Files:**
- Create: `~/d/science-commons/datasets/cytoband-hg19/.gitignore`
- Create: `~/d/science-commons/datasets/cytoband-hg19/entity.md`
- Create: `~/d/science-commons/datasets/cytoband-hg19/recipe/lockfile.yaml`
- Create: `~/d/science-commons/datasets/cytoband-hg19/recipe/README.md`

- [ ] **Step 1: Create commons worktree**

Run from `~/d/science-commons`:

```bash
mkdir -p .worktrees
git worktree add .worktrees/bio-identity-p4-cytoband -b bio-identity-p4-cytoband
```

Expected: worktree is created at `~/d/science-commons/.worktrees/bio-identity-p4-cytoband`.

- [ ] **Step 2: Add skeleton metadata**

Use `apply_patch` from `~/d/science-commons/.worktrees/bio-identity-p4-cytoband`:

```markdown
*** Begin Patch
*** Add File: datasets/cytoband-hg19/.gitignore
+/sources/
*** Add File: datasets/cytoband-hg19/entity.md
+---
+schema_profile: science-entity-base/1.0+dataset/1.0
+id: dataset:cytoband-hg19
+type: dataset
+title: UCSC hg19 cytobands
+version: "1.0.0"
+created: "2026-07-03"
+updated: "2026-07-03"
+status: active
+origin: external
+source_class: reference
+tier: use-now
+access:
+  level: public
+  availability: available
+  verified: true
+  verification_method: retrieved
+datapackage: datapackage.yaml
+row_count: 862
+---
*** Add File: datasets/cytoband-hg19/recipe/lockfile.yaml
+resources:
+  cytoBand:
+    url: https://hgdownload.cse.ucsc.edu/goldenPath/hg19/database/cytoBand.txt.gz
+    path: sources/cytoBand.txt.gz
+    sha256: f9b82309b2bca1eb9d91a5cb2c6aa0528351158e6e20b51d82cca36d01735cba
+    bytes: 6609
+    decompressed_rows: 862
*** Add File: datasets/cytoband-hg19/recipe/README.md
+# cytoband-hg19 recipe
+
+This recipe pins UCSC hg19 `cytoBand.txt.gz` and builds a deterministic
+`cytobands.csv` reference artifact for `dataset:cytoband-hg19`.
+
+Source:
+
+```text
+https://hgdownload.cse.ucsc.edu/goldenPath/hg19/database/cytoBand.txt.gz
+```
+
+Use `cytoBand.txt.gz`, not `cytoBandIdeo.txt.gz`; the latter is modified for
+ideogram display. Runtime Science readers consume only the built CSV through
+the datapackage hash and never fetch UCSC.
+
+```bash
+python datasets/cytoband-hg19/recipe/fetch.py
+python datasets/cytoband-hg19/recipe/build.py
+```
*** End Patch
```

`datapackage.yaml` is not created in this skeleton task. Task 3 creates it only after real `cytobands.csv` bytes exist, so the committed metadata never carries fake hash or byte values.

- [ ] **Step 3: Verify skeleton has the expected files**

Run:

```bash
find datasets/cytoband-hg19 -maxdepth 3 -type f | sort
```

Expected output:

```text
datasets/cytoband-hg19/.gitignore
datasets/cytoband-hg19/entity.md
datasets/cytoband-hg19/recipe/README.md
datasets/cytoband-hg19/recipe/lockfile.yaml
```

Do not commit this task until Task 3 creates the real datapackage from built bytes.

## Task 2: Add Commons Fetch And Build Recipes

**Files:**
- Create: `~/d/science-commons/datasets/cytoband-hg19/recipe/fetch.py`
- Create: `~/d/science-commons/datasets/cytoband-hg19/recipe/build.py`

- [ ] **Step 1: Add failing recipe smoke checks**

Run before adding the scripts:

```bash
python datasets/cytoband-hg19/recipe/fetch.py --help
python datasets/cytoband-hg19/recipe/build.py --help
```

Expected: both fail with "No such file or directory".

- [ ] **Step 2: Implement `fetch.py`**

Create `datasets/cytoband-hg19/recipe/fetch.py` with the same operator-run shape as the liftover recipe:

```python
from __future__ import annotations

import argparse
import hashlib
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml

DATASET_NAME = "cytoband-hg19"
RESOURCE_NAME = "cytoBand"
DEFAULT_URL = "https://hgdownload.cse.ucsc.edu/goldenPath/hg19/database/cytoBand.txt.gz"
SOURCE_RESOURCE_PATH = Path("sources/cytoBand.txt.gz")
LOCKFILE_PATH = Path(__file__).with_name("lockfile.yaml")
REJECTED_URL_PARTS = ("latest", "current", "download/test")


def validate_explicit_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        raise ValueError("URL must be non-empty")
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"URL must be an absolute http(s) URL, got {url!r}")
    lowered = normalized.lower()
    for rejected in REJECTED_URL_PARTS:
        if rejected in lowered:
            raise ValueError(f"URL contains mutable or disallowed segment {rejected!r}: {url}")
    return normalized


def load_lockfile(path: Path) -> dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("resources"), dict):
        raise ValueError(f"{path}: expected lockfile with resources mapping")
    entry = raw["resources"].get(RESOURCE_NAME)
    if not isinstance(entry, dict):
        raise ValueError(f"{path}: missing {RESOURCE_NAME} resource")
    for key in ("url", "sha256", "bytes", "path"):
        if key not in entry:
            raise ValueError(f"{path}: {RESOURCE_NAME} missing {key}")
    validate_explicit_url(str(entry["url"]))
    return raw


def fetch_source(
    *,
    url: str,
    output_dir: Path,
    lockfile_path: Path = LOCKFILE_PATH,
    refresh_lockfile: bool = False,
) -> dict[str, Any]:
    normalized_url = validate_explicit_url(url)
    existing_lock = load_lockfile(lockfile_path) if lockfile_path.exists() else None
    if existing_lock is None and not refresh_lockfile:
        raise FileNotFoundError(f"missing lockfile: {lockfile_path}; pass --refresh-lockfile to create the pin")

    output_path = output_dir / SOURCE_RESOURCE_PATH
    candidate_path = output_path.with_name(output_path.name + ".candidate")
    sha256, byte_count = _download(normalized_url, candidate_path)
    observed_lock = {
        "resources": {
            RESOURCE_NAME: {
                "url": normalized_url,
                "path": SOURCE_RESOURCE_PATH.as_posix(),
                "sha256": sha256,
                "bytes": byte_count,
            }
        }
    }

    try:
        if existing_lock is not None and not refresh_lockfile:
            validate_lock_matches_observed(existing_lock, observed_lock, lockfile_path)
            candidate_path.replace(output_path)
            return existing_lock
        lockfile_path.parent.mkdir(parents=True, exist_ok=True)
        lockfile_path.write_text(yaml.safe_dump(observed_lock, sort_keys=False), encoding="utf-8")
        candidate_path.replace(output_path)
        return observed_lock
    except Exception:
        candidate_path.unlink(missing_ok=True)
        raise


def validate_lock_matches_observed(existing_lock: dict[str, Any], observed_lock: dict[str, Any], lockfile_path: Path) -> None:
    existing = existing_lock["resources"][RESOURCE_NAME]
    observed = observed_lock["resources"][RESOURCE_NAME]
    mismatches = [key for key in ("url", "sha256", "bytes") if str(existing[key]) != str(observed[key])]
    if mismatches:
        mismatch_text = ", ".join(mismatches)
        raise ValueError(
            f"{lockfile_path}: observed download does not match existing pin "
            f"({mismatch_text}); pass --refresh-lockfile to intentionally repin"
        )


def resolve_commons_data_root() -> Path:
    if env := os.environ.get("SCIENCE_COMMONS_DATA_ROOT"):
        return Path(env)
    return Path("/data/science-commons")


def _download(url: str, output_path: Path) -> tuple[str, int]:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    digest = hashlib.sha256()
    byte_count = 0
    with urllib.request.urlopen(url) as response, tmp_path.open("wb") as fh:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            digest.update(chunk)
            byte_count += len(chunk)
            fh.write(chunk)
    tmp_path.replace(output_path)
    return digest.hexdigest(), byte_count


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch pinned UCSC hg19 cytoBand source.")
    parser.add_argument("--url", default=DEFAULT_URL, help="Explicit cytoBand URL to download.")
    parser.add_argument("--output-dir", type=Path, help="Dataset data directory. Defaults under SCIENCE_COMMONS_DATA_ROOT.")
    parser.add_argument("--lockfile", type=Path, default=LOCKFILE_PATH, help="Path to recipe lockfile.")
    parser.add_argument("--refresh-lockfile", action="store_true", help="Rewrite the lockfile with observed URL/hash/bytes.")
    args = parser.parse_args()

    output_dir = args.output_dir or resolve_commons_data_root() / DATASET_NAME
    lock = fetch_source(
        url=args.url,
        output_dir=output_dir,
        lockfile_path=args.lockfile,
        refresh_lockfile=args.refresh_lockfile,
    )
    entry = lock["resources"][RESOURCE_NAME]
    print(f"wrote {entry['path']} ({entry['bytes']} bytes) to {output_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Implement `build.py`**

Create `datasets/cytoband-hg19/recipe/build.py`:

```python
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import os
import urllib.parse
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

DATASET_NAME = "cytoband-hg19"
OUTPUT_ROOT_TOKEN = "${OUTPUT_ROOT}"
RESOURCE_NAME = "cytoBand"
SOURCE_RESOURCE_PATH = Path("sources/cytoBand.txt.gz")
CYTOBANDS_RESOURCE_PATH = Path("cytobands.csv")
LOCKFILE_PATH = Path(__file__).with_name("lockfile.yaml")
DATAPACKAGE_PATH = Path(__file__).parents[1] / "datapackage.yaml"
ENTITY_PATH = Path(__file__).parents[1] / "entity.md"
REJECTED_URL_PARTS = ("latest", "current", "download/test")
FIELDNAMES = ["chrom", "start", "end", "name", "gie_stain"]
ALLOWED_STAINS = frozenset({"gneg", "gpos25", "gpos50", "gpos75", "gpos100", "acen", "gvar", "stalk"})
CHROM_ORDER = {f"chr{i}": i for i in range(1, 23)} | {"chrX": 23, "chrY": 24, "chrM": 25}


def build_dataset(
    *,
    data_dir: Path,
    lockfile_path: Path = LOCKFILE_PATH,
    datapackage_path: Path = DATAPACKAGE_PATH,
    entity_path: Path = ENTITY_PATH,
) -> None:
    lock = load_lockfile(lockfile_path)
    entry = lock["resources"][RESOURCE_NAME]
    source_path = data_dir / SOURCE_RESOURCE_PATH
    if not source_path.is_file():
        raise FileNotFoundError(f"required source file is absent: {source_path}")
    source_sha256, source_bytes = stream_sha256_and_bytes(source_path)
    if source_sha256.removeprefix("sha256:") != str(entry["sha256"]):
        raise ValueError(f"{source_path}: sha256 mismatch against lockfile")
    if source_bytes != int(entry["bytes"]):
        raise ValueError(f"{source_path}: byte count mismatch against lockfile")

    rows = parse_source_rows(source_path)
    expected_rows = entry.get("decompressed_rows")
    if expected_rows is not None and len(rows) != int(expected_rows):
        raise ValueError(f"{source_path}: expected {expected_rows} rows, observed {len(rows)}")

    cytobands_path = data_dir / CYTOBANDS_RESOURCE_PATH
    write_cytobands(cytobands_path, rows)
    cytobands_hash, cytobands_bytes = stream_sha256_and_bytes(cytobands_path)
    write_datapackage(datapackage_path, cytobands_hash=cytobands_hash, cytobands_bytes=cytobands_bytes)
    update_entity(entity_path, row_count=len(rows))


def parse_source_rows(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    with gzip.open(path, "rt", encoding="utf-8", newline="") as fh:
        for row_index, line in enumerate(fh, start=1):
            stripped = line.rstrip("\n")
            if not stripped:
                continue
            cells = stripped.split("\t")
            if len(cells) != 5:
                raise ValueError(f"{path}: row {row_index}: expected 5 tab-separated fields, got {len(cells)}")
            chrom, start, end, name, gie_stain = cells
            for column, value in (("chrom", chrom), ("name", name), ("gie_stain", gie_stain)):
                if not value or value != value.strip():
                    raise ValueError(f"{path}: row {row_index}: invalid {column} {value!r}")
            if not start.isdecimal() or not end.isdecimal():
                raise ValueError(f"{path}: row {row_index}: invalid interval {start!r}-{end!r}")
            start_i = int(start)
            end_i = int(end)
            if start_i < 0 or end_i <= start_i:
                raise ValueError(f"{path}: row {row_index}: invalid interval {start!r}-{end!r}")
            if gie_stain not in ALLOWED_STAINS:
                raise ValueError(f"{path}: row {row_index}: invalid gie_stain {gie_stain!r}")
            key = (chrom, str(start_i), str(end_i), name, gie_stain)
            if key in seen:
                raise ValueError(f"{path}: row {row_index}: duplicate cytoband row {key!r}")
            seen.add(key)
            rows.append({"chrom": chrom, "start": str(start_i), "end": str(end_i), "name": name, "gie_stain": gie_stain})
    return sorted(rows, key=cytoband_sort_key)


def cytoband_sort_key(row: dict[str, str]) -> tuple[int, str, int, int, str, str]:
    chrom = row["chrom"]
    return (CHROM_ORDER.get(chrom, 10_000), chrom, int(row["start"]), int(row["end"]), row["name"], row["gie_stain"])


def write_cytobands(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDNAMES, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def load_lockfile(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing lockfile: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("resources"), dict):
        raise ValueError(f"{path}: expected lockfile with resources mapping")
    entry = raw["resources"].get(RESOURCE_NAME)
    if not isinstance(entry, dict):
        raise ValueError(f"{path}: missing {RESOURCE_NAME} resource")
    for key in ("url", "sha256", "bytes", "path"):
        if key not in entry:
            raise ValueError(f"{path}: {RESOURCE_NAME} missing {key}")
    validate_explicit_url(str(entry["url"]))
    return raw


def validate_explicit_url(url: str) -> str:
    normalized = url.strip()
    if not normalized:
        raise ValueError("URL must be non-empty")
    parsed = urllib.parse.urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"URL must be an absolute http(s) URL, got {url!r}")
    lowered = normalized.lower()
    for rejected in REJECTED_URL_PARTS:
        if rejected in lowered:
            raise ValueError(f"URL contains mutable or disallowed segment {rejected!r}: {url}")
    return normalized


def write_datapackage(path: Path, *, cytobands_hash: str, cytobands_bytes: int) -> None:
    doc = {
        "name": DATASET_NAME,
        "profile": "data-package",
        "resources": [
            {
                "name": "cytobands",
                "path": CYTOBANDS_RESOURCE_PATH.as_posix(),
                "format": "csv",
                "mediatype": "text/csv",
                "source": {"type": "local", "ref": f"{OUTPUT_ROOT_TOKEN}/{DATASET_NAME}/{CYTOBANDS_RESOURCE_PATH.as_posix()}"},
                "hash": cytobands_hash,
                "bytes": cytobands_bytes,
            }
        ],
    }
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def update_entity(path: Path, *, row_count: int) -> None:
    text = path.read_text(encoding="utf-8")
    today = datetime.now(UTC).date().isoformat()
    replacements = {
        "updated:": f'updated: "{today}"',
        "row_count:": f"row_count: {row_count}",
    }
    lines: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        replaced = False
        for prefix, new_line in replacements.items():
            if line.startswith(prefix):
                lines.append(new_line)
                seen.add(prefix)
                replaced = True
                break
        if not replaced:
            lines.append(line)
    if "row_count:" not in seen:
        insert_at = lines.index("---", 1)
        lines.insert(insert_at, f"row_count: {row_count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def stream_sha256_and_bytes(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
            byte_count += len(chunk)
    return f"sha256:{digest.hexdigest()}", byte_count


def resolve_commons_data_root() -> Path:
    if env := os.environ.get("SCIENCE_COMMONS_DATA_ROOT"):
        return Path(env)
    return Path("/data/science-commons")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build UCSC hg19 cytoband resources.")
    parser.add_argument("--data-dir", type=Path, help="Dataset data directory. Defaults under SCIENCE_COMMONS_DATA_ROOT.")
    parser.add_argument("--lockfile", type=Path, default=LOCKFILE_PATH, help="Path to recipe lockfile.")
    parser.add_argument("--datapackage", type=Path, default=DATAPACKAGE_PATH, help="Path to rewrite datapackage.yaml.")
    parser.add_argument("--entity", type=Path, default=ENTITY_PATH, help="Path to rewrite entity.md.")
    args = parser.parse_args()

    data_dir = args.data_dir or resolve_commons_data_root() / DATASET_NAME
    build_dataset(data_dir=data_dir, lockfile_path=args.lockfile, datapackage_path=args.datapackage, entity_path=args.entity)
    print(f"wrote cytoband resources to {data_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify CLI help works**

Run:

```bash
python datasets/cytoband-hg19/recipe/fetch.py --help
python datasets/cytoband-hg19/recipe/build.py --help
```

Expected: both commands exit 0 and print usage text.

## Task 3: Build And Commit The Real Commons Artifact

**Files:**
- Create: `~/d/science-commons/datasets/cytoband-hg19/cytobands.csv`
- Modify: `~/d/science-commons/datasets/cytoband-hg19/datapackage.yaml`
- Modify: `~/d/science-commons/datasets/cytoband-hg19/entity.md`

- [ ] **Step 1: Fetch pinned source into the dataset directory**

Run from `~/d/science-commons/.worktrees/bio-identity-p4-cytoband`:

```bash
python datasets/cytoband-hg19/recipe/fetch.py --output-dir datasets/cytoband-hg19
```

Expected:

```text
wrote sources/cytoBand.txt.gz (6609 bytes) to datasets/cytoband-hg19
```

- [ ] **Step 2: Build normalized CSV and datapackage**

Run:

```bash
python datasets/cytoband-hg19/recipe/build.py --data-dir datasets/cytoband-hg19
```

Expected: command exits 0 and prints `wrote cytoband resources to datasets/cytoband-hg19`.

- [ ] **Step 3: Verify row count, ordering, source pin, and datapackage hash**

Run:

```bash
python - <<'PY'
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import yaml

dataset = Path("datasets/cytoband-hg19")
rows = list(csv.DictReader((dataset / "cytobands.csv").open(newline="")))
assert len(rows) == 862, len(rows)
assert rows[0] == {"chrom": "chr1", "start": "0", "end": "2300000", "name": "p36.33", "gie_stain": "gneg"}
assert rows[-1] == {"chrom": "chrY", "start": "28800000", "end": "59373566", "name": "q12", "gie_stain": "gvar"}
assert len({tuple(row.items()) for row in rows}) == len(rows)
data = (dataset / "cytobands.csv").read_bytes()
digest = "sha256:" + hashlib.sha256(data).hexdigest()
dp = yaml.safe_load((dataset / "datapackage.yaml").read_text())
resource = dp["resources"][0]
assert resource["name"] == "cytobands"
assert resource["path"] == "cytobands.csv"
assert resource["hash"] == digest
assert resource["bytes"] == len(data)
lock = yaml.safe_load((dataset / "recipe" / "lockfile.yaml").read_text())
source = lock["resources"]["cytoBand"]
assert source["sha256"] == "f9b82309b2bca1eb9d91a5cb2c6aa0528351158e6e20b51d82cca36d01735cba"
assert source["bytes"] == 6609
print(digest, len(data), len(rows))
PY
```

Expected: command prints the generated `cytobands.csv` hash, byte count, and `862`.

- [ ] **Step 4: Ensure only real generated metadata exists**

Run:

```bash
test -s datasets/cytoband-hg19/datapackage.yaml
grep -R "sha256:000000" -n datasets/cytoband-hg19
```

Expected: `test -s` exits 0. `grep` has no output and exits 1.

- [ ] **Step 5: Commit commons artifact**

Run:

```bash
git status --short
git add datasets/cytoband-hg19
git commit -m "Add hg19 cytoband reference dataset"
```

Expected: commit succeeds in `~/d/science-commons/.worktrees/bio-identity-p4-cytoband`.

The local fetched source remains ignored under `datasets/cytoband-hg19/sources/`; do not force-add it.

## Task 4: Add Reduced Science Cytoband Fixture

**Files:**
- Create: `science/tests/fixtures/commons/cytoband/datasets/cytoband-hg19/entity.md`
- Create: `science/tests/fixtures/commons/cytoband/datasets/cytoband-hg19/datapackage.yaml`
- Create: `science/tests/fixtures/commons/cytoband-data/cytoband-hg19/cytobands.csv`

- [ ] **Step 1: Generate reduced fixture**

Run from `~/d/science/.worktrees/bio-identity-p4-cytoband`:

```bash
uv run --frozen python - <<'PY'
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import yaml

root = Path("science/tests/fixtures/commons")
commons_dir = root / "cytoband" / "datasets" / "cytoband-hg19"
data_dir = root / "cytoband-data" / "cytoband-hg19"
commons_dir.mkdir(parents=True, exist_ok=True)
data_dir.mkdir(parents=True, exist_ok=True)

rows = [
    {"chrom": "chr1", "start": "0", "end": "2300000", "name": "p36.33", "gie_stain": "gneg"},
    {"chrom": "chr1", "start": "2300000", "end": "5300000", "name": "p36.32", "gie_stain": "gpos25"},
    {"chrom": "chr1", "start": "5300000", "end": "7100000", "name": "p36.31", "gie_stain": "gneg"},
    {"chrom": "chr2", "start": "0", "end": "4400000", "name": "p25.3", "gie_stain": "gneg"},
]

csv_path = data_dir / "cytobands.csv"
with csv_path.open("w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=["chrom", "start", "end", "name", "gie_stain"])
    writer.writeheader()
    writer.writerows(rows)

data = csv_path.read_bytes()
resource_hash = "sha256:" + hashlib.sha256(data).hexdigest()

(commons_dir / "entity.md").write_text(
    """\
---
schema_profile: science-entity-base/1.0+dataset/1.0
id: dataset:cytoband-hg19
type: dataset
title: UCSC hg19 cytobands
version: "1.0.0"
created: "2026-07-03"
updated: "2026-07-03"
status: active
origin: external
source_class: reference
tier: use-now
access:
  level: public
  availability: available
  verified: true
  verification_method: retrieved
datapackage: datapackage.yaml
row_count: 4
---
""",
    encoding="utf-8",
)
(commons_dir / "datapackage.yaml").write_text(
    yaml.safe_dump(
        {
            "name": "cytoband-hg19",
            "profile": "data-package",
            "resources": [
                {
                    "name": "cytobands",
                    "path": "cytobands.csv",
                    "format": "csv",
                    "mediatype": "text/csv",
                    "hash": resource_hash,
                    "bytes": len(data),
                }
            ],
        },
        sort_keys=False,
    ),
    encoding="utf-8",
)

print(resource_hash, len(data), len(rows))
PY
```

Expected: command prints a `sha256:<64 hex>` hash, byte count, and `4`.

- [ ] **Step 2: Inspect fixture**

Run:

```bash
find science/tests/fixtures/commons/cytoband science/tests/fixtures/commons/cytoband-data -type f | sort
sed -n '1,20p' science/tests/fixtures/commons/cytoband-data/cytoband-hg19/cytobands.csv
```

Expected: three fixture files exist and `cytobands.csv` has four data rows.

- [ ] **Step 3: Commit fixture**

Run:

```bash
git add science/tests/fixtures/commons/cytoband science/tests/fixtures/commons/cytoband-data
git commit -m "Add cytoband commons fixture"
```

## Task 5: Implement Science Cytoband Reader With TDD

**Files:**
- Create: `science/src/science_tool/commons/cytoband.py`
- Create: `science/tests/test_commons_cytoband.py`

- [ ] **Step 1: Write failing reader tests**

Create `science/tests/test_commons_cytoband.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.cytoband import CytobandError, CytobandRow, bands_for_interval, load_cytobands

_FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_COMMONS_ROOT = _FIXTURES / "cytoband"
_DATA_ROOT = _FIXTURES / "cytoband-data"


def test_load_cytobands_reads_hash_verified_commons_fixture() -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    assert rows[:2] == [
        CytobandRow(chrom="chr1", start=0, end=2300000, name="p36.33", gie_stain="gneg"),
        CytobandRow(chrom="chr1", start=2300000, end=5300000, name="p36.32", gie_stain="gpos25"),
    ]


def test_bands_for_interval_returns_all_overlaps_in_artifact_order() -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    assert bands_for_interval(rows, chrom="chr1", start=2200000, end=5400000) == [
        CytobandRow(chrom="chr1", start=0, end=2300000, name="p36.33", gie_stain="gneg"),
        CytobandRow(chrom="chr1", start=2300000, end=5300000, name="p36.32", gie_stain="gpos25"),
        CytobandRow(chrom="chr1", start=5300000, end=7100000, name="p36.31", gie_stain="gneg"),
    ]


def test_bands_for_interval_allows_known_chromosome_no_overlap() -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    assert bands_for_interval(rows, chrom="chr1", start=7100000, end=7200000) == []


def test_bands_for_interval_rejects_unknown_chromosome() -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    with pytest.raises(CytobandError, match="unknown chromosome"):
        bands_for_interval(rows, chrom="1", start=0, end=1)


@pytest.mark.parametrize(("start", "end"), [(-1, 1), (1, 1), (2, 1)])
def test_bands_for_interval_rejects_invalid_interval(start: int, end: int) -> None:
    rows = load_cytobands(commons_root=_COMMONS_ROOT, data_root=_DATA_ROOT)

    with pytest.raises(CytobandError, match="invalid interval"):
        bands_for_interval(rows, chrom="chr1", start=start, end=end)


def test_parse_rejects_duplicate_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons import cytoband

    duplicate = [
        {"chrom": "chr1", "start": "0", "end": "1", "name": "p", "gie_stain": "new_stain"},
        {"chrom": "chr1", "start": "0", "end": "1", "name": "p", "gie_stain": "new_stain"},
    ]

    monkeypatch.setattr(cytoband, "_load_csv_rows", lambda *args, **kwargs: duplicate)

    with pytest.raises(CytobandError, match="duplicate cytoband row"):
        load_cytobands()


def test_runtime_accepts_new_non_empty_stain_value(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons import cytoband

    monkeypatch.setattr(
        cytoband,
        "_load_csv_rows",
        lambda *args, **kwargs: [{"chrom": "chr1", "start": "0", "end": "1", "name": "p", "gie_stain": "future"}],
    )

    assert load_cytobands() == [CytobandRow(chrom="chr1", start=0, end=1, name="p", gie_stain="future")]
```

- [ ] **Step 2: Run tests and verify they fail for the missing module**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_cytoband.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.cytoband'`.

- [ ] **Step 3: Implement the reader**

Create `science/src/science_tool/commons/cytoband.py`:

```python
"""Runtime reader for pinned cytoband reference rows."""

from __future__ import annotations

import csv
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.resolver import resolve

CYTOBAND_HG19_ID = "dataset:cytoband-hg19"
CYTOBANDS_RESOURCE = "cytobands.csv"
_COLUMNS = frozenset({"chrom", "start", "end", "name", "gie_stain"})


class CytobandError(ValueError):
    """The cytoband artifact cannot answer the requested lookup."""


@dataclass(frozen=True, slots=True)
class CytobandRow:
    chrom: str
    start: int
    end: int
    name: str
    gie_stain: str


def load_cytobands(
    dataset_id: str = CYTOBAND_HG19_ID,
    *,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[CytobandRow]:
    rows = _load_csv_rows(dataset_id=dataset_id, commons_root=commons_root, data_root=data_root)
    return _parse_rows(rows)


def bands_for_interval(rows: Sequence[CytobandRow], *, chrom: str, start: int, end: int) -> list[CytobandRow]:
    if start < 0 or end <= start:
        raise CytobandError(f"invalid interval {chrom}:{start}-{end}")
    known_chroms = {row.chrom for row in rows}
    if chrom not in known_chroms:
        raise CytobandError(f"unknown chromosome {chrom!r}")
    return [row for row in rows if row.chrom == chrom and row.start < end and start < row.end]


def _load_csv_rows(
    *,
    dataset_id: str,
    commons_root: Path | None,
    data_root: Path | None,
) -> list[dict[str, Any]]:
    resolved = resolve(dataset_id, CYTOBANDS_RESOURCE, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_header(CYTOBANDS_RESOURCE, reader.fieldnames)
        return list(reader)


def _parse_rows(rows: Iterable[dict[str, Any]]) -> list[CytobandRow]:
    parsed: list[CytobandRow] = []
    seen: set[tuple[str, int, int, str, str]] = set()
    for row_index, row in enumerate(rows):
        _validate_columns(row, row_index)
        chrom = _required_text(row, row_index, "chrom")
        start = _required_nonnegative_int(row, row_index, "start")
        end = _required_nonnegative_int(row, row_index, "end")
        name = _required_text(row, row_index, "name")
        gie_stain = _required_text(row, row_index, "gie_stain")
        if end <= start:
            raise CytobandError(f"row {row_index}: invalid interval {chrom}:{start}-{end}")
        key = (chrom, start, end, name, gie_stain)
        if key in seen:
            raise CytobandError(f"row {row_index}: duplicate cytoband row {key!r}")
        seen.add(key)
        parsed.append(CytobandRow(chrom=chrom, start=start, end=end, name=name, gie_stain=gie_stain))
    return parsed


def _validate_header(resource: str, fieldnames: Sequence[str] | None) -> None:
    if fieldnames is None:
        raise CytobandError(f"{resource}: missing CSV header")
    seen: set[str] = set()
    duplicate_columns: list[str] = []
    for fieldname in fieldnames:
        if fieldname in seen and fieldname not in duplicate_columns:
            duplicate_columns.append(fieldname)
        seen.add(fieldname)
    if duplicate_columns:
        raise CytobandError(f"{resource}: duplicate columns {sorted(duplicate_columns)!r}")
    actual = set(fieldnames)
    if actual != _COLUMNS:
        unexpected = sorted(actual - _COLUMNS)
        missing = sorted(_COLUMNS - actual)
        details: list[str] = []
        if unexpected:
            details.append(f"unexpected columns {unexpected!r}")
        if missing:
            details.append(f"missing columns {missing!r}")
        raise CytobandError(f"{resource}: malformed CSV header with {', '.join(details)}")


def _validate_columns(row: dict[str, Any], row_index: int) -> None:
    if None in row:
        raise CytobandError(f"row {row_index}: malformed CSV row with surplus columns")
    actual = set(row)
    if actual != _COLUMNS:
        unexpected = sorted(actual - _COLUMNS)
        missing = sorted(_COLUMNS - actual)
        details: list[str] = []
        if unexpected:
            details.append(f"unexpected columns {unexpected!r}")
        if missing:
            details.append(f"missing columns {missing!r}")
        raise CytobandError(f"row {row_index}: malformed CSV row with {', '.join(details)}")


def _required_text(row: dict[str, Any], row_index: int, column: str) -> str:
    value = row[column]
    if not isinstance(value, str):
        raise CytobandError(f"row {row_index}: column {column!r} must be a string")
    if not value:
        raise CytobandError(f"row {row_index}: blank {column}")
    if value != value.strip():
        raise CytobandError(f"row {row_index}: invalid whitespace in {column}={value!r}")
    return value


def _required_nonnegative_int(row: dict[str, Any], row_index: int, column: str) -> int:
    value = _required_text(row, row_index, column)
    if not value.isdecimal():
        raise CytobandError(f"row {row_index}: invalid {column} {value!r}")
    return int(value)
```

- [ ] **Step 4: Run reader tests**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_cytoband.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit reader and tests**

Run:

```bash
git add science/src/science_tool/commons/cytoband.py science/tests/test_commons_cytoband.py
git commit -m "Add cytoband commons reader"
```

## Task 6: Use Real Cytoband Slug In Proxy Provenance Tests

**Files:**
- Modify: `science/tests/test_dataset_register_run.py`
- Modify: `science/tests/validate/test_checks_identity_context.py`

- [ ] **Step 1: Update register-run proxy test to use `dataset:cytoband-hg19`**

In `science/tests/test_dataset_register_run.py::test_register_run_proxy_output_preserves_unresolved_proxy_and_routes_sources`, replace the synthetic slug with the real one:

```python
_seed_dataset(tmp_path, "cytoband-hg19")
```

and make the proxy block use:

```python
"via": "dataset:cytoband-hg19",
```

Update the final assertions to expect:

```python
assert derived["derivation"]["transformations"] == [
    {"kind": "proxy_via", "dataset": "dataset:cytoband-hg19", "type": "cytoband_proxy"}
]
assert "workflow-run:wf-r1" not in _frontmatter(tmp_path / "entities" / "datasets" / "cytoband-hg19.md")["consumed_by"]
```

- [ ] **Step 2: Add or update validation happy-path test for the real slug**

In `science/tests/validate/test_checks_identity_context.py`, update the proxy happy-path test so the reference dataset is:

```python
via = _ds("science-pkg-entity-1.0", id="dataset:cytoband-hg19")
```

and the derived identity/provenance use:

```python
"via": "dataset:cytoband-hg19"
```

```python
"transformations": [{"kind": "proxy_via", "dataset": "dataset:cytoband-hg19", "type": "cytoband_proxy"}]
```

Keep negative tests with synthetic/missing slugs if they are specifically testing missing-reference behavior.

- [ ] **Step 3: Run proxy provenance tests**

Run:

```bash
uv run --frozen pytest \
  science/tests/test_dataset_register_run.py::test_register_run_proxy_output_preserves_unresolved_proxy_and_routes_sources \
  science/tests/validate/test_checks_identity_context.py -q
```

Expected: selected tests pass.

- [ ] **Step 4: Commit proxy test updates**

Run:

```bash
git add science/tests/test_dataset_register_run.py science/tests/validate/test_checks_identity_context.py
git commit -m "Use real cytoband proxy reference in tests"
```

## Task 7: Update Umbrella Progress

**Files:**
- Modify: `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`

- [ ] **Step 1: Close the cytoband home fork**

In the `cytoband-hg19 home` section, replace the open fork text with:

```markdown
### `cytoband-hg19` home

Closed in P4.4: UCSC hg19 cytoBand is promoted as `dataset:cytoband-hg19` in `science-commons`. MM30/t665 should use this shared reference artifact as `identity_context.assembly.proxy.via` rather than creating an MM30-local cytoband reference.
```

- [ ] **Step 2: Add P4.4 progress ledger entry**

Append this entry before `Next:`:

```markdown
- 2026-07-03: P4.4 cytoband proxy reference landed. `science-commons` now has pinned `dataset:cytoband-hg19` bytes from UCSC hg19 `cytoBand.txt.gz`; Science has an offline hash-verified `science_tool.commons.cytoband` reader with parse + interval-overlap lookup, and proxy provenance tests use the real `dataset:cytoband-hg19` reference slug.
- Next: P5 MM30/t665 re-planning.
```

Remove the old `- Next: P4.4 cytoband-hg19 proxy reference.` line.

- [ ] **Step 3: Commit umbrella update**

Run:

```bash
git add docs/plans/2026-07-03-bio-identity-adoption-umbrella.md
git commit -m "Mark cytoband proxy reference landed"
```

## Task 8: Final Verification And Branch Review

**Files:**
- Verify only.

- [ ] **Step 1: Verify commons artifact**

Run from `~/d/science-commons/.worktrees/bio-identity-p4-cytoband`:

```bash
python datasets/cytoband-hg19/recipe/build.py --data-dir datasets/cytoband-hg19
git diff --exit-code -- datasets/cytoband-hg19
```

Expected: build exits 0 and `git diff --exit-code` exits 0, proving the recipe is deterministic over committed bytes.

- [ ] **Step 2: Run Science focused tests**

Run from `~/d/science/.worktrees/bio-identity-p4-cytoband`:

```bash
uv run --frozen pytest \
  science/tests/test_commons_cytoband.py \
  science/tests/test_dataset_register_run.py::test_register_run_proxy_output_preserves_unresolved_proxy_and_routes_sources \
  science/tests/validate/test_checks_identity_context.py -q
```

Expected: all selected tests pass.

- [ ] **Step 3: Run Ruff on changed Python files**

Run:

```bash
uv run --frozen ruff check \
  science/src/science_tool/commons/cytoband.py \
  science/tests/test_commons_cytoband.py \
  science/tests/test_dataset_register_run.py \
  science/tests/validate/test_checks_identity_context.py
```

Expected: Ruff exits 0.

- [ ] **Step 4: Check docs and worktree state**

Run:

```bash
git diff --check HEAD
git status --short
```

Expected: no whitespace errors. `git status --short` is clean in `~/d/science`; run the same status check in `~/d/science-commons/.worktrees/bio-identity-p4-cytoband` and confirm it is also clean.

## Self-Review Checklist

- Spec coverage:
  - Commons dataset exists with pinned UCSC URL, source hash/bytes, deterministic CSV, datapackage hash/bytes, entity row count.
  - Runtime reader loads through commons resolver and never fetches network.
  - Unknown chromosomes fail loudly; no-overlap on a known chromosome returns `[]`.
  - Duplicate rows fail; future non-empty stain values are accepted at runtime.
  - Proxy provenance tests use `dataset:cytoband-hg19` as the reference artifact.
  - Umbrella closes the cytoband home fork and moves to P5 re-planning.
- Placeholder scan:
  - Run:

```bash
python - <<'PY'
from pathlib import Path

text = Path("docs/plans/2026-07-03-bio-identity-p4-cytoband-implementation-plan.md").read_text(encoding="utf-8")
tokens = ["TO" + "DO", "T" + "BD", "fill" + " in", "later" + " step"]
matches = [token for token in tokens if token in text]
if matches:
    raise SystemExit(f"placeholder-like tokens remain: {matches}")
PY
```

  - Expected: command exits 0.
- Type consistency:
  - Public reader names are exactly `CytobandRow`, `CytobandError`, `load_cytobands`, and `bands_for_interval`.
  - Commons resource name is exactly `cytobands`; resource path is exactly `cytobands.csv`.
  - Dataset id is exactly `dataset:cytoband-hg19`.
