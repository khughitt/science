# Bio Identity P4.3 Liftover Consumption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish P4.3 by proving `transform: liftover` consumes the pinned `dataset:assembly-liftover-grch37-grch38` artifact offline through compatibility rows, gzipped chain bytes, validation, and register-run provenance.

**Architecture:** `~/d/science` owns the runtime readers, validation behavior, reduced commons-style fixture, and register-run provenance emission. `~/d/science-commons` owns the real operator-run liftover dataset and chain lockfile; this plan verifies that dataset shape but does not redesign it. Exact `from_seqcol_digest` / `to_seqcol_digest` remain explicit run provenance in `derivation.transformations[]`.

**Tech Stack:** Python 3.12, pytest, Ruff, Frictionless-style datapackage YAML, gzipped UCSC chain files, Science commons resolver.

---

## Preconditions

- Work in `~/d/science/.worktrees/bio-identity-p4-liftover` on branch `bio-identity-p4-liftover`.
- Keep unrelated worktrees and branches untouched, including `~/d/science/.worktrees/bio-identity-p4-gene-crosswalk-design`.
- Runtime tests must not fetch the network.
- Use `~/d/` paths in docs/comments, not absolute Dropbox paths.
- If this plan updates `~/d/science-commons`, create a matching isolated worktree under `~/d/science-commons/.worktrees/bio-identity-p4-liftover` and keep commits split by repo.

Useful constants from P4.1:

```text
GRCh37 seqcol digest: XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA
GRCh38 seqcol digest: XemD97fxYMS4q-FBm_n5CHQgmzh1_67a
Liftover dataset id: dataset:assembly-liftover-grch37-grch38
Compatibility resource: compatibility_relations
Chain resource path: chains/hg19ToHg38.over.chain.gz
```

## File Structure

`~/d/science`:

- `science/src/science_tool/commons/liftover.py` - add `load_chain(...)`, a small runtime loader that resolves a datapackage resource, gunzips it, parses chain text, and returns `list[Chain]`.
- `science/src/science_tool/datasets_register.py` - add exact liftover digest emission into `derivation.transformations[]` when source and target assembly identities are resolved.
- `science/tests/test_commons_liftover.py` - test chain loading from a commons-style fixture and one offline interval lift through the loaded chain.
- `science/tests/test_commons_assembly_compatibility.py` - test compatibility relation loading from a commons-style fixture and relation lookup using the real P4.1 digests.
- `science/tests/validate/test_checks_identity_context.py` - test validation using fixture-loaded compatibility relations and preserve warning/error truth table for wrong/missing relation shapes.
- `science/tests/test_dataset_register_run.py` - test `register-run` emits `from_seqcol_digest` / `to_seqcol_digest` for liftover when both source and output assemblies are resolved, and does not fabricate digests when unresolved.
- `science/tests/fixtures/commons/liftover/` - new reduced commons metadata fixture for `dataset:assembly-liftover-grch37-grch38`.
- `science/tests/fixtures/commons/liftover-data/` - new reduced data-root fixture containing `compatibility_relations.csv` and a tiny gzipped chain.
- `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md` - update after implementation lands to record P4.3 completion and move `Next:` to P4.4.

`~/d/science-commons`:

- `datasets/assembly-liftover-grch37-grch38/recipe/build.py` - verify only unless the recipe fails the plan's deterministic checks.
- `datasets/assembly-liftover-grch37-grch38/datapackage.yaml` - update only if the recipe deterministically regenerates different metadata.
- `datasets/assembly-liftover-grch37-grch38/entity.md` - update only if commons metadata changes.

## Task 1: Add Reduced Liftover Commons Fixture

**Files:**
- Create: `science/tests/fixtures/commons/liftover/datasets/assembly-liftover-grch37-grch38/entity.md`
- Create: `science/tests/fixtures/commons/liftover/datasets/assembly-liftover-grch37-grch38/datapackage.yaml`
- Create: `science/tests/fixtures/commons/liftover-data/assembly-liftover-grch37-grch38/compatibility_relations.csv`
- Create: `science/tests/fixtures/commons/liftover-data/assembly-liftover-grch37-grch38/chains/hg19ToHg38.over.chain.gz`

- [ ] **Step 1: Generate deterministic fixture bytes**

Run this from `~/d/science/.worktrees/bio-identity-p4-liftover`. The gzip file is binary, so generate this fixture with Python rather than `apply_patch`.

```bash
uv run --frozen python - <<'PY'
from __future__ import annotations

import csv
import gzip
import hashlib
import io
from pathlib import Path

import yaml

root = Path("science/tests/fixtures/commons")
commons_dir = root / "liftover" / "datasets" / "assembly-liftover-grch37-grch38"
data_dir = root / "liftover-data" / "assembly-liftover-grch37-grch38"
chain_rel = Path("chains/hg19ToHg38.over.chain.gz")
chain_path = data_dir / chain_rel
commons_dir.mkdir(parents=True, exist_ok=True)
chain_path.parent.mkdir(parents=True, exist_ok=True)

chain_text = """\
chain 1000 chr1 1000 + 500 630 chr1 2000 + 1000 1140 7
50 10 20
70
"""

buffer = io.BytesIO()
with gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as gz:
    gz.write(chain_text.encode("utf-8"))
chain_bytes = buffer.getvalue()
chain_path.write_bytes(chain_bytes)
chain_hash = "sha256:" + hashlib.sha256(chain_bytes).hexdigest()

compat_path = data_dir / "compatibility_relations.csv"
with compat_path.open("w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(
        fh,
        fieldnames=[
            "source_seqcol_digest",
            "target_seqcol_digest",
            "relation",
            "method",
            "chain_resource",
            "direction",
            "source_label",
            "target_label",
            "source_url",
            "chain_sha256",
        ],
    )
    writer.writeheader()
    writer.writerow(
        {
            "source_seqcol_digest": "XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA",
            "target_seqcol_digest": "XemD97fxYMS4q-FBm_n5CHQgmzh1_67a",
            "relation": "liftover_possible",
            "method": "ucsc_chain",
            "chain_resource": chain_rel.as_posix(),
            "direction": "forward",
            "source_label": "GRCh37",
            "target_label": "GRCh38",
            "source_url": "https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz",
            "chain_sha256": chain_hash,
        }
    )
compat_bytes = compat_path.read_bytes()
compat_hash = "sha256:" + hashlib.sha256(compat_bytes).hexdigest()

(commons_dir / "entity.md").write_text(
    """\
---
schema_profile: science-entity-base/1.0+dataset/1.0
id: dataset:assembly-liftover-grch37-grch38
type: dataset
title: GRCh37 to GRCh38 assembly liftover chains
version: "1.0.0"
created: "2026-05-31"
updated: "2026-05-31"
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
---
""",
    encoding="utf-8",
)
(commons_dir / "datapackage.yaml").write_text(
    yaml.safe_dump(
        {
            "name": "assembly-liftover-grch37-grch38",
            "profile": "data-package",
            "resources": [
                {
                    "name": "compatibility_relations",
                    "path": "compatibility_relations.csv",
                    "format": "csv",
                    "mediatype": "text/csv",
                    "hash": compat_hash,
                    "bytes": len(compat_bytes),
                },
                {
                    "name": "hg19ToHg38_chain",
                    "path": chain_rel.as_posix(),
                    "format": "chain.gz",
                    "mediatype": "application/gzip",
                    "hash": chain_hash,
                    "bytes": len(chain_bytes),
                },
            ],
        },
        sort_keys=False,
    ),
    encoding="utf-8",
)

print(f"compatibility_relations {compat_hash} {len(compat_bytes)} bytes")
print(f"{chain_rel} {chain_hash} {len(chain_bytes)} bytes")
PY
```

Expected: the command prints two `sha256:<64 hex>` hashes and creates the four fixture files.

- [ ] **Step 2: Inspect generated fixture**

Run:

```bash
find science/tests/fixtures/commons/liftover science/tests/fixtures/commons/liftover-data -type f | sort
sed -n '1,120p' science/tests/fixtures/commons/liftover/datasets/assembly-liftover-grch37-grch38/datapackage.yaml
sed -n '1,5p' science/tests/fixtures/commons/liftover-data/assembly-liftover-grch37-grch38/compatibility_relations.csv
```

Expected: exactly these files exist:

```text
science/tests/fixtures/commons/liftover/datasets/assembly-liftover-grch37-grch38/datapackage.yaml
science/tests/fixtures/commons/liftover/datasets/assembly-liftover-grch37-grch38/entity.md
science/tests/fixtures/commons/liftover-data/assembly-liftover-grch37-grch38/chains/hg19ToHg38.over.chain.gz
science/tests/fixtures/commons/liftover-data/assembly-liftover-grch37-grch38/compatibility_relations.csv
```

The datapackage should contain resources named `compatibility_relations` and `hg19ToHg38_chain`.

- [ ] **Step 3: Commit fixture**

Run:

```bash
git add science/tests/fixtures/commons/liftover science/tests/fixtures/commons/liftover-data
git commit -m "Add liftover commons fixture"
```

## Task 2: Integration-Test Compatibility Relation Loading

**Files:**
- Modify: `science/tests/test_commons_assembly_compatibility.py`

- [ ] **Step 1: Add fixture loader test**

Update the top of `science/tests/test_commons_assembly_compatibility.py` so imports include `Path`, and add `load_compatibility_relations` to the existing import from `science_tool.commons.assembly_compatibility`:

```python
from pathlib import Path

from science_tool.commons.assembly_compatibility import (
    AssemblyCompatibilityError,
    CompatibilityRelation,
    load_compatibility_relations,
    parse_compatibility_rows,
    relation_for,
)
```

Then append these constants and the test below the existing helper/test definitions:

```python

_FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_LIFTOVER_COMMONS_ROOT = _FIXTURES / "liftover"
_LIFTOVER_DATA_ROOT = _FIXTURES / "liftover-data"
_GRCH37_DIGEST = "XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA"
_GRCH38_DIGEST = "XemD97fxYMS4q-FBm_n5CHQgmzh1_67a"
_LIFTOVER_DATASET = "dataset:assembly-liftover-grch37-grch38"


def test_load_compatibility_relations_from_commons_fixture() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )

    assert relations == [
        CompatibilityRelation(
            source_seqcol_digest=_GRCH37_DIGEST,
            target_seqcol_digest=_GRCH38_DIGEST,
            relation="liftover_possible",
            method="ucsc_chain",
            chain_resource="chains/hg19ToHg38.over.chain.gz",
            direction="forward",
            source_label="GRCh37",
            target_label="GRCh38",
            source_url="https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz",
            chain_sha256=relations[0].chain_sha256,
        )
    ]
    assert relation_for(relations, source_seqcol_digest=_GRCH37_DIGEST, target_seqcol_digest=_GRCH38_DIGEST) is not None
    assert relation_for(relations, source_seqcol_digest=_GRCH38_DIGEST, target_seqcol_digest=_GRCH37_DIGEST) is None
```

If the file already imports `Path` or `load_compatibility_relations` after a worker starts, merge the imports at the top rather than duplicating them.

- [ ] **Step 2: Run focused test**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_assembly_compatibility.py::test_load_compatibility_relations_from_commons_fixture -q
```

Expected: PASS. If it fails, fix only the fixture metadata/hash mismatch or import placement; do not change parser behavior for this task.

- [ ] **Step 3: Run compatibility suite**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_assembly_compatibility.py -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit compatibility fixture coverage**

Run:

```bash
git add science/tests/test_commons_assembly_compatibility.py
git commit -m "Test liftover compatibility fixture loading"
```

## Task 3: Add Runtime Gzipped Chain Loader

**Files:**
- Modify: `science/src/science_tool/commons/liftover.py`
- Modify: `science/tests/test_commons_liftover.py`

- [ ] **Step 1: Add failing tests for datapackage-resolved chain loading**

Update imports at the top of `science/tests/test_commons_liftover.py`:

```python
from pathlib import Path

from science_tool.commons.assembly_compatibility import load_compatibility_relations, relation_for
```

Add `load_chain` to the existing import from `science_tool.commons.liftover`.

Append these constants and tests:

```python
_FIXTURES = Path(__file__).parent / "fixtures" / "commons"
_LIFTOVER_COMMONS_ROOT = _FIXTURES / "liftover"
_LIFTOVER_DATA_ROOT = _FIXTURES / "liftover-data"
_GRCH37_DIGEST = "XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA"
_GRCH38_DIGEST = "XemD97fxYMS4q-FBm_n5CHQgmzh1_67a"
_LIFTOVER_DATASET = "dataset:assembly-liftover-grch37-grch38"


def test_load_chain_reads_gzipped_commons_resource() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )
    relation = relation_for(relations, source_seqcol_digest=_GRCH37_DIGEST, target_seqcol_digest=_GRCH38_DIGEST)
    assert relation is not None

    chains = load_chain(
        dataset_id=_LIFTOVER_DATASET,
        chain_resource=relation.chain_resource,
        expected_sha256=relation.chain_sha256,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )

    assert len(chains) == 1
    assert chains[0].source_name == "chr1"
    assert chains[0].target_name == "chr1"
    assert chains[0].chain_id == 7


def test_loaded_chain_lifts_interval_offline() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )
    relation = relation_for(relations, source_seqcol_digest=_GRCH37_DIGEST, target_seqcol_digest=_GRCH38_DIGEST)
    assert relation is not None
    chains = load_chain(
        dataset_id=_LIFTOVER_DATASET,
        chain_resource=relation.chain_resource,
        expected_sha256=relation.chain_sha256,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )

    result = lift_interval(
        chains,
        source_seqcol_digest=relation.source_seqcol_digest,
        target_seqcol_digest=relation.target_seqcol_digest,
        source_contig="chr1",
        start=510,
        end=511,
    )

    assert result == LiftedInterval(
        source_seqcol_digest=_GRCH37_DIGEST,
        target_seqcol_digest=_GRCH38_DIGEST,
        source_contig="chr1",
        target_contig="chr1",
        source_start=510,
        source_end=511,
        target_start=1010,
        target_end=1011,
        target_strand="+",
        chain_id=7,
    )


def test_load_chain_rejects_relation_hash_mismatch() -> None:
    with pytest.raises(ChainFormatError, match="does not match compatibility chain_sha256"):
        load_chain(
            dataset_id=_LIFTOVER_DATASET,
            chain_resource="chains/hg19ToHg38.over.chain.gz",
            expected_sha256="sha256:" + "a" * 64,
            commons_root=_LIFTOVER_COMMONS_ROOT,
            data_root=_LIFTOVER_DATA_ROOT,
        )
```

- [ ] **Step 2: Run tests and verify intended failure**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_liftover.py::test_load_chain_reads_gzipped_commons_resource science/tests/test_commons_liftover.py::test_loaded_chain_lifts_interval_offline science/tests/test_commons_liftover.py::test_load_chain_rejects_relation_hash_mismatch -q
```

Expected: FAIL with `ImportError` or `NameError` for `load_chain`.

- [ ] **Step 3: Implement `load_chain`**

In `science/src/science_tool/commons/liftover.py`, add imports:

```python
import gzip
from pathlib import Path
```

Also import the commons resolver:

```python
from science_tool.commons.resolver import resolve
```

Add this function after `parse_chain_text`:

```python
def load_chain(
    *,
    dataset_id: str,
    chain_resource: str,
    expected_sha256: str | None = None,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> list[Chain]:
    """Resolve, gunzip, and parse a pinned UCSC chain resource offline."""
    resolved = resolve(dataset_id, chain_resource, commons_root=commons_root, data_root=data_root)
    if expected_sha256 is not None and resolved.hash != expected_sha256:
        raise ChainFormatError(
            f"{chain_resource}: datapackage hash {resolved.hash!r} does not match "
            f"compatibility chain_sha256 {expected_sha256!r}"
        )
    try:
        with gzip.open(resolved.path, "rt", encoding="utf-8", newline="") as handle:
            text = handle.read()
    except OSError as exc:
        raise ChainFormatError(f"{chain_resource}: cannot read gzipped chain resource: {exc}") from exc
    return parse_chain_text(text)
```

Do not add network fetching. `resolve(...)` must be the only path to chain bytes.

- [ ] **Step 4: Run focused liftover tests**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_liftover.py::test_load_chain_reads_gzipped_commons_resource science/tests/test_commons_liftover.py::test_loaded_chain_lifts_interval_offline science/tests/test_commons_liftover.py::test_load_chain_rejects_relation_hash_mismatch -q
```

Expected: PASS.

- [ ] **Step 5: Run liftover suite**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_liftover.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit runtime chain loader**

Run:

```bash
git add science/src/science_tool/commons/liftover.py science/tests/test_commons_liftover.py
git commit -m "Load pinned liftover chains offline"
```

## Task 4: Validate Cross-Dataset Remedy Against Fixture Relations

**Files:**
- Modify: `science/tests/validate/test_checks_identity_context.py`

- [ ] **Step 1: Add fixture-backed validation test**

Update imports at the top of `science/tests/validate/test_checks_identity_context.py`:

```python
from pathlib import Path
```

Add `load_compatibility_relations` to the existing imports from `science_tool.commons.assembly_compatibility`.

Append these constants near the existing `_LIFTOVER_DATASET` constant:

```python

_FIXTURES = Path(__file__).parents[1] / "fixtures" / "commons"
_LIFTOVER_COMMONS_ROOT = _FIXTURES / "liftover"
_LIFTOVER_DATA_ROOT = _FIXTURES / "liftover-data"
_GRCH37_DIGEST = "XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA"
_GRCH38_DIGEST = "XemD97fxYMS4q-FBm_n5CHQgmzh1_67a"
```

If `Path` is already imported after a worker starts, merge imports at the top.

Append this test after `test_cross_dataset_mismatch_with_declared_liftover_passes`:

```python
def test_cross_dataset_mismatch_with_fixture_loaded_liftover_passes() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )
    source = _with_assembly("dataset:source", _GRCH37_DIGEST)
    derived = _with_assembly(
        "dataset:derived",
        _GRCH38_DIGEST,
        derivation={
            "inputs": ["dataset:source"],
            "transformations": [
                {
                    "kind": "identity_transform",
                    "target": "assembly",
                    "type": "liftover",
                    "from": "dataset:source",
                    "from_seqcol_digest": _GRCH37_DIGEST,
                    "to_seqcol_digest": _GRCH38_DIGEST,
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )

    assert (
        list(
            evaluate_cross_dataset_assembly(
                [source, derived],
                compatibility_relations_by_dataset_id={_LIFTOVER_DATASET: relations},
            )
        )
        == []
    )
```

- [ ] **Step 2: Add explicit warning test for missing exact digest fields**

Append this test near the cross-dataset liftover tests:

```python
def test_cross_dataset_mismatch_with_liftover_transform_but_no_exact_digests_warns() -> None:
    relations = load_compatibility_relations(
        dataset_id=_LIFTOVER_DATASET,
        commons_root=_LIFTOVER_COMMONS_ROOT,
        data_root=_LIFTOVER_DATA_ROOT,
    )
    source = _with_assembly("dataset:source", _GRCH37_DIGEST)
    derived = _with_assembly(
        "dataset:derived",
        _GRCH38_DIGEST,
        derivation={
            "inputs": ["dataset:source"],
            "transformations": [
                {
                    "kind": "identity_transform",
                    "target": "assembly",
                    "type": "liftover",
                    "from": "dataset:source",
                    "method": "ucsc_chain",
                    "dataset": _LIFTOVER_DATASET,
                }
            ],
        },
    )

    warns = [
        result
        for result in evaluate_cross_dataset_assembly(
            [source, derived],
            compatibility_relations_by_dataset_id={_LIFTOVER_DATASET: relations},
        )
        if result.rule == "identity.cross-dataset-assembly-mismatch"
    ]

    assert len(warns) == 1
```

- [ ] **Step 3: Run focused validation tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_identity_context.py::test_cross_dataset_mismatch_with_fixture_loaded_liftover_passes science/tests/validate/test_checks_identity_context.py::test_cross_dataset_mismatch_with_liftover_transform_but_no_exact_digests_warns -q
```

Expected: PASS. These tests should pass against current validator behavior once imports/constants are correct.

- [ ] **Step 4: Run identity-context validation suite**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_identity_context.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit fixture-backed validation coverage**

Run:

```bash
git add science/tests/validate/test_checks_identity_context.py
git commit -m "Test liftover remedy with fixture relations"
```

## Task 5: Emit Exact Liftover Digests From Register-Run

**Files:**
- Modify: `science/src/science_tool/datasets_register.py`
- Modify: `science/tests/test_dataset_register_run.py`

- [ ] **Step 1: Add failing register-run test for resolved liftover digest emission**

Append this test to `science/tests/test_dataset_register_run.py` near `test_register_run_transform_dataset_routes_to_transformations_not_data_inputs`:

```python
def test_register_run_liftover_transform_emits_exact_seqcol_digests(tmp_path: Path) -> None:
    _seed_dataset(
        tmp_path,
        "source",
        {
            "taxon": 9606,
            "assembly": {
                "seqcol_digest": "SQ.GRCh37",
                "registry": "dataset:assembly-registry",
                "resolution_status": "resolved",
            },
        },
    )
    _seed_dataset(tmp_path, "liftover-chain")
    transform = {
        "type": "liftover",
        "from": "dataset:source",
        "method": "ucsc_chain",
        "dataset": "dataset:liftover-chain",
    }
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "lifted", "path": "lifted.csv", "format": "csv"}],
        run_inputs=["dataset:source"],
        workflow_outputs=[
            {
                "slug": "lifted",
                "title": "Lifted",
                "resource_names": ["lifted"],
                "ontology_terms": [],
                "identity": {
                    "taxon": "inherit",
                    "assembly": {
                        "label": "GRCh38",
                        "seqcol_digest": "SQ.GRCh38",
                        "registry": "dataset:assembly-registry",
                        "resolution_status": "resolved",
                        "transform": transform,
                    },
                },
            }
        ],
    )
    _seed_resource_files(tmp_path, ["lifted"])

    res = _run_register(tmp_path)

    assert res.exit_code == 0, res.output
    entity = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-lifted.md")
    assert entity["derivation"]["inputs"] == ["dataset:source"]
    assert entity["derivation"]["transformations"] == [
        {
            "kind": "identity_transform",
            "target": "assembly",
            "dataset": "dataset:liftover-chain",
            "type": "liftover",
            "from": "dataset:source",
            "method": "ucsc_chain",
            "from_seqcol_digest": "SQ.GRCh37",
            "to_seqcol_digest": "SQ.GRCh38",
        }
    ]
```

- [ ] **Step 2: Add non-fabrication test for unresolved target assembly**

Append this test next:

```python
def test_register_run_liftover_transform_does_not_fabricate_unresolved_digests(tmp_path: Path) -> None:
    _seed_dataset(
        tmp_path,
        "source",
        {
            "taxon": 9606,
            "assembly": {
                "seqcol_digest": "SQ.GRCh37",
                "registry": "dataset:assembly-registry",
                "resolution_status": "resolved",
            },
        },
    )
    _seed_dataset(tmp_path, "liftover-chain")
    transform = {
        "type": "liftover",
        "from": "dataset:source",
        "method": "ucsc_chain",
        "dataset": "dataset:liftover-chain",
    }
    _seed_workflow_and_run(
        tmp_path,
        run_resources=[{"name": "lifted", "path": "lifted.csv", "format": "csv"}],
        run_inputs=["dataset:source"],
        workflow_outputs=[
            {
                "slug": "lifted",
                "title": "Lifted",
                "resource_names": ["lifted"],
                "ontology_terms": [],
                "identity": {
                    "taxon": "inherit",
                    "assembly": {
                        "label": "GRCh38",
                        "registry": "dataset:assembly-registry",
                        "resolution_status": "declared_unresolved",
                        "transform": transform,
                    },
                },
            }
        ],
    )
    _seed_resource_files(tmp_path, ["lifted"])

    res = _run_register(tmp_path)

    assert res.exit_code == 0, res.output
    entity = _frontmatter(tmp_path / "entities" / "datasets" / "wf-r1-lifted.md")
    transformation = entity["derivation"]["transformations"][0]
    assert transformation["from"] == "dataset:source"
    assert "from_seqcol_digest" not in transformation
    assert "to_seqcol_digest" not in transformation
```

- [ ] **Step 3: Run tests and verify intended failure**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_register_run.py::test_register_run_liftover_transform_emits_exact_seqcol_digests science/tests/test_dataset_register_run.py::test_register_run_liftover_transform_does_not_fabricate_unresolved_digests -q
```

Expected: first test FAILS because `from_seqcol_digest` / `to_seqcol_digest` are absent. The second may pass or fail depending on implementation state; after this task both must pass.

- [ ] **Step 4: Implement digest helpers**

In `science/src/science_tool/datasets_register.py`, add these helpers immediately before `_transform_entry`:

```python
def _assembly_seqcol_digest(identity_context: dict[str, Any] | None) -> str | None:
    assembly = identity_context.get("assembly") if isinstance(identity_context, dict) else None
    digest = assembly.get("seqcol_digest") if isinstance(assembly, dict) else None
    return digest if isinstance(digest, str) and digest and digest != "UNKNOWN" else None


def _liftover_transform_source_dataset(transform: dict[str, Any], selected_inputs: list[str]) -> str | None:
    from_value = transform.get("from")
    if from_value == "input" and len(selected_inputs) == 1:
        return selected_inputs[0]
    if isinstance(from_value, str) and from_value.startswith("dataset:"):
        return from_value
    return None
```

- [ ] **Step 5: Update `_transform_entry` to optionally add liftover digests**

Replace `_transform_entry` with:

```python
def _transform_entry(
    transform: dict[str, Any],
    target: str,
    *,
    identity_context: dict[str, Any] | None = None,
    selected_inputs: list[str] | None = None,
    identities: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": "identity_transform",
        "target": target,
        "dataset": transform["dataset"],
        "type": transform["type"],
    }
    for key in ("from", "to", "method"):
        if key in transform:
            entry[key] = transform[key]

    if target == "assembly" and transform.get("type") == "liftover":
        source_id = _liftover_transform_source_dataset(transform, selected_inputs or [])
        source_digest = _assembly_seqcol_digest((identities or {}).get(source_id or ""))
        target_digest = _assembly_seqcol_digest(identity_context)
        if source_digest is not None and target_digest is not None:
            entry["from_seqcol_digest"] = source_digest
            entry["to_seqcol_digest"] = target_digest
    return entry
```

This preserves `from` as the dataset id and adds separate digest fields only when both sides are resolved.

- [ ] **Step 6: Thread identity context through `_identity_transformations`**

Replace `_identity_transformations` with:

```python
def _identity_transformations(
    identity_context: dict[str, Any],
    *,
    selected_inputs: list[str] | None = None,
    identities: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    transformations: list[dict[str, Any]] = []
    assembly = identity_context.get("assembly")
    if isinstance(assembly, dict):
        transform = assembly.get("transform")
        if isinstance(transform, dict) and isinstance(transform.get("dataset"), str):
            transformations.append(
                _transform_entry(
                    transform,
                    "assembly",
                    identity_context=identity_context,
                    selected_inputs=selected_inputs,
                    identities=identities,
                )
            )
        proxy = assembly.get("proxy")
        if isinstance(proxy, dict) and isinstance(proxy.get("via"), str):
            transformations.append({"kind": "proxy_via", "dataset": proxy["via"], "type": proxy.get("type", "proxy")})
    molecular_ids = identity_context.get("molecular_ids")
    if isinstance(molecular_ids, dict):
        for tier, tier_identity in molecular_ids.items():
            if not isinstance(tier_identity, dict):
                continue
            transform = tier_identity.get("transform")
            if isinstance(transform, dict) and isinstance(transform.get("dataset"), str):
                transformations.append(_transform_entry(transform, f"molecular_ids.{tier}"))
    return transformations
```

- [ ] **Step 7: Pass selected inputs and identities from `_resolve_output_identity`**

In `_resolve_output_identity`, replace:

```python
        transformations=_identity_transformations(identity_context),
```

with:

```python
        transformations=_identity_transformations(
            identity_context,
            selected_inputs=selected_inputs,
            identities=identities,
        ),
```

- [ ] **Step 8: Run focused register-run tests**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_register_run.py::test_register_run_transform_dataset_routes_to_transformations_not_data_inputs science/tests/test_dataset_register_run.py::test_register_run_liftover_transform_emits_exact_seqcol_digests science/tests/test_dataset_register_run.py::test_register_run_liftover_transform_does_not_fabricate_unresolved_digests -q
```

Expected: PASS. Existing `transform.dataset` routing behavior must stay unchanged: liftover chain remains in `derivation.transformations[]`, not `derivation.inputs`.

- [ ] **Step 9: Run full register-run test file**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_register_run.py -q
```

Expected: all tests pass.

- [ ] **Step 10: Commit register-run provenance emission**

Run:

```bash
git add science/src/science_tool/datasets_register.py science/tests/test_dataset_register_run.py
git commit -m "Emit liftover seqcol provenance"
```

## Task 6: Verify Science Liftover Slice

**Files:**
- No file edits expected.

- [ ] **Step 1: Run focused P4.3 tests**

Run:

```bash
uv run --frozen pytest \
  science/tests/test_commons_assembly_compatibility.py \
  science/tests/test_commons_liftover.py \
  science/tests/validate/test_checks_identity_context.py \
  science/tests/test_dataset_register_run.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 2: Run adjacent identity/assembly tests**

Run:

```bash
uv run --frozen pytest \
  science/tests/test_commons_assembly.py \
  science/tests/test_identity_resolve.py \
  science/tests/test_identity_authoring.py \
  science/tests/test_identity_stamp.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 3: Run Ruff on changed files**

Run:

```bash
uv run --frozen ruff check \
  science/src/science_tool/commons/liftover.py \
  science/src/science_tool/datasets_register.py \
  science/tests/test_commons_assembly_compatibility.py \
  science/tests/test_commons_liftover.py \
  science/tests/validate/test_checks_identity_context.py \
  science/tests/test_dataset_register_run.py
```

Expected: `All checks passed!`.

- [ ] **Step 4: Commit any verification-only fixups**

If steps 1-3 required small fixes, commit them:

```bash
git add science/src/science_tool/commons/liftover.py science/src/science_tool/datasets_register.py science/tests/test_commons_assembly_compatibility.py science/tests/test_commons_liftover.py science/tests/validate/test_checks_identity_context.py science/tests/test_dataset_register_run.py science/tests/fixtures/commons/liftover science/tests/fixtures/commons/liftover-data
git commit -m "Stabilize liftover consumption tests"
```

If no files changed, skip this commit.

## Task 7: Verify Commons Liftover Artifact Shape

**Files:**
- Modify only if necessary: `~/d/science-commons/datasets/assembly-liftover-grch37-grch38/datapackage.yaml`
- Modify only if necessary: `~/d/science-commons/datasets/assembly-liftover-grch37-grch38/entity.md`

- [ ] **Step 1: Create science-commons worktree if needed**

If not already in an isolated science-commons workspace, run:

```bash
cd ~/d/science-commons
git worktree add .worktrees/bio-identity-p4-liftover -b bio-identity-p4-liftover
```

Then use:

```bash
COMMONS=~/d/science-commons/.worktrees/bio-identity-p4-liftover
```

- [ ] **Step 2: Inspect existing liftover dataset metadata**

Run:

```bash
cd "$COMMONS"
sed -n '1,160p' datasets/assembly-liftover-grch37-grch38/datapackage.yaml
sed -n '1,120p' datasets/assembly-liftover-grch37-grch38/recipe/lockfile.yaml
```

Expected:

- `datapackage.yaml` has resources named `compatibility_relations` and `hg19ToHg38_chain`;
- `recipe/lockfile.yaml` pins `https://hgdownload.soe.ucsc.edu/goldenPath/hg19/liftOver/hg19ToHg38.over.chain.gz`;
- lockfile SHA is `5c0598e500ceb5a78c73086929e8ef993aec309bcafb595139b53d440b125a1d`;
- lockfile byte count is `227698`.

- [ ] **Step 3: Fetch pinned chain if local data bytes are absent**

Run:

```bash
cd "$COMMONS"
uv run --with httpx python datasets/assembly-liftover-grch37-grch38/recipe/fetch.py
```

Expected: the command either reports the pinned file is already installed or writes it under `$SCIENCE_COMMONS_DATA_ROOT/assembly-liftover-grch37-grch38/chains/` after verifying the lockfile hash.

- [ ] **Step 4: Rebuild compatibility metadata with P4.1 digests**

Run:

```bash
cd "$COMMONS"
uv run --with pyyaml python datasets/assembly-liftover-grch37-grch38/recipe/build.py \
  --source-seqcol XJWKh8nsSqBFfcU0DIHMZohYyCWF-vcA \
  --target-seqcol XemD97fxYMS4q-FBm_n5CHQgmzh1_67a
```

Expected: writes liftover compatibility resources to the configured data root and updates `datasets/assembly-liftover-grch37-grch38/datapackage.yaml` only if metadata was stale.

- [ ] **Step 5: Inspect science-commons diff**

Run:

```bash
cd "$COMMONS"
git status --short
git diff -- datasets/assembly-liftover-grch37-grch38
```

Expected: either no diff, or a narrow datapackage metadata diff caused by deterministic rebuild. If there is a diff, confirm the resource hashes match the files in the data root before committing.

- [ ] **Step 6: Commit commons changes only if files changed**

If Step 5 shows changes:

```bash
cd "$COMMONS"
git add datasets/assembly-liftover-grch37-grch38/datapackage.yaml datasets/assembly-liftover-grch37-grch38/entity.md
git commit -m "Verify pinned GRCh37 GRCh38 liftover artifact"
```

If Step 5 is clean, do not create a commons commit.

## Task 8: Update Umbrella And Final Verification

**Files:**
- Modify: `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`

- [ ] **Step 1: Update P4 status text**

In `docs/plans/2026-07-03-bio-identity-adoption-umbrella.md`, change:

```markdown
**Status:** P4.1-P4.2 landed; P4.3 next.
```

to:

```markdown
**Status:** P4.1-P4.3 landed; P4.4 next.
```

Replace the P4.3 work-package bullet with:

```markdown
- **P4.3 liftover-chain consumption.** Landed. Science now fixture-tests `dataset:assembly-liftover-grch37-grch38` through commons-style compatibility rows and gzipped chain bytes, validates cross-dataset liftover remedies against exact `from_seqcol_digest -> to_seqcol_digest` relations, and emits exact liftover seqcol provenance from `register-run` when source and target assemblies are resolved.
```

Change the final ledger line:

```markdown
- Next: P4.3 liftover-chain consumption.
```

to:

```markdown
- 2026-07-03: P4.3 liftover-chain consumption landed. The explicit `from_seqcol_digest` / `to_seqcol_digest` provenance decision is closed for v1; the transform block records intent, while `derivation.transformations[]` records the exact lifted source-target pair. Science proves offline compatibility loading and a tiny gzipped-chain interval lift through a reduced built-artifact fixture.
- Next: P4.4 cytoband-hg19 proxy reference.
```

- [ ] **Step 2: Run full focused verification**

Run:

```bash
uv run --frozen pytest \
  science/tests/test_commons_assembly_compatibility.py \
  science/tests/test_commons_liftover.py \
  science/tests/validate/test_checks_identity_context.py \
  science/tests/test_dataset_register_run.py \
  science/tests/test_commons_assembly.py \
  science/tests/test_identity_resolve.py \
  science/tests/test_identity_authoring.py \
  science/tests/test_identity_stamp.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 3: Run Ruff**

Run:

```bash
uv run --frozen ruff check \
  science/src/science_tool/commons/liftover.py \
  science/src/science_tool/datasets_register.py \
  science/tests/test_commons_assembly_compatibility.py \
  science/tests/test_commons_liftover.py \
  science/tests/validate/test_checks_identity_context.py \
  science/tests/test_dataset_register_run.py
```

Expected: `All checks passed!`.

- [ ] **Step 4: Check whitespace and status**

Run:

```bash
git diff --check HEAD
git status --short
```

Expected: no whitespace errors. Status should show only intentional umbrella/doc changes before the final commit.

- [ ] **Step 5: Commit umbrella update**

Run:

```bash
git add docs/plans/2026-07-03-bio-identity-adoption-umbrella.md
git commit -m "Record liftover P4 progress"
```

## Self-Review Checklist

- [ ] The fixture is commons-style: entity + datapackage under `liftover/`, bytes under `liftover-data/`.
- [ ] The chain loader uses `commons.resolver.resolve` and never reads a chain path directly from the compatibility CSV without datapackage hash verification.
- [ ] Runtime chain loading uses gzip only for local bytes; no network path exists.
- [ ] `transform.from` remains a dataset reference or `input`; it is not renamed into `from_seqcol_digest`.
- [ ] `from_seqcol_digest` / `to_seqcol_digest` are emitted only when both source and target assembly identities have concrete non-`UNKNOWN` seqcol digests.
- [ ] Cross-dataset assembly mismatch remains a `WARN` unless remedied; provenance misrouting remains an `ERROR`.
- [ ] Reference liftover dataset stays in `derivation.transformations[]` and never enters `derivation.inputs`.
- [ ] The umbrella records P4.3 completion and moves the next phase to P4.4.

## Execution Handoff

Plan complete and saved to `docs/plans/2026-07-03-bio-identity-p4-liftover-implementation-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - execute tasks in this session using `superpowers:executing-plans`, with checkpoints.
