# C4c rsID Variant Label Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add rsID input support for variant identity by resolving pinned dbSNP labels to exact small alleles, then minting the existing assembly-anchored VRS identity.

**Implementation status:** Implemented locally in `~/d/science` and `~/d/science-commons` for C4c-1. The rsID resolver, VRS minting boundary, variant-row validation, dbSNP recipe, and Snakemake workflow entrypoint are in place; the recipe fixture build passes. Full dbSNP archive fetch/build through Snakemake, full-source lockfile pinning, datapackage hash refresh, and resolver smoke against the real commons artifact remain operator-pending because the generated SQLite was not built in this session. Transcript/protein HGVS projection remains out of scope.

**Architecture:** C4c-1 is an input translation layer over C4a, not a new variant identity namespace. A pinned dbSNP reference dataset provides an indexed rsID-to-allele artifact; `science_tool.commons.rsid` resolves one rsID within a declared seqcol assembly; `variant.vrs_id_from_rsid(...)` converts the resolved allele to SPDI and delegates to `variant.vrs_id(...)`. The variant validator accepts `locator.format: rsid` while keeping `identity_context.molecular_ids.variant.namespace: vrs`.

**Tech Stack:** Python stdlib (`csv`, `gzip`, `hashlib`, `sqlite3`, `urllib.request`), existing commons resolver/datapackage helpers, existing C4a `variant.vrs_id`, pytest, ruff, pyright, `science validate`.

---

## Performance and Feasibility Guardrails

dbSNP human VCFs are large: the pinned b157 VCFs are 26 GB for GRCh37 and 28 GB for GRCh38 before
filtering/build products. Validation must therefore resolve and hash `rsid_mappings.sqlite` **once per
dataset validation pass**, not once per row. The commons resolver intentionally sha256-verifies resolved
resources on every `resolve(...)` call, so row code must pass a pre-resolved `sqlite_path` to
`vrs_id_from_rsid(...)` and then to `resolve_rsid(...)`.

Before committing a full generated SQLite/datapackage hash, the builder must report retained row count,
SQLite byte size, wall-clock build time, and skipped bucket counts. If the SQLite exceeds local storage
budget or lookup latency is unacceptable, stop and reassess partitioning before treating the artifact as
production-ready.

## Scope

This plan implements **C4c-1: rsID input** only.

In scope:

- Pinned human dbSNP VCF sources from the NCBI archive, not `latest_release`.
- GRCh38 and GRCh37 mappings because C4a supports both source assemblies.
- Precise small allele rows only: SNV, MNV, and small indel with literal `ACGTN` REF/ALT.
- Multi-allelic rsIDs are resolved only when row-level allele columns disambiguate them; otherwise they produce an explicit `ambiguous-rsid` defect.
- Row-level validation for datasets that declare `locator.format: rsid`.

Out of scope:

- Transcript HGVS projection.
- Protein HGVS projection.
- Structural variants, symbolic alleles, breakends, imprecise alleles.
- Live dbSNP/Variation Services calls.
- Treating an rsID as canonical identity. The canonical output remains `ga4gh:VA...`.

## Source Pinning Decision

Use NCBI dbSNP archive build 157 VCF files:

- `https://ftp.ncbi.nih.gov/snp/archive/b157/VCF/GCF_000001405.40.gz` for GRCh38.p14.
- `https://ftp.ncbi.nih.gov/snp/archive/b157/VCF/GCF_000001405.25.gz` for GRCh37.p13.

The recipe must reject `snp/latest_release/` URLs. The lockfile records URL, sha256, md5 when available,
and byte count. The NCBI directory provides `.md5` sidecars, but the commons lockfile still pins sha256
as the reproducibility handle.

## Data Contract

Create a commons dataset named `dataset:variant-labels-dbsnp-human` in `~/d/science-commons`.

Resources:

- `rsid_mappings.sqlite`
- `build-summary.yaml`

SQLite schema:

```sql
CREATE TABLE metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE rsid_alleles (
  rsid TEXT NOT NULL,
  seqcol_digest TEXT NOT NULL,
  contig TEXT NOT NULL,
  pos0 INTEGER NOT NULL,
  ref TEXT NOT NULL,
  alt TEXT NOT NULL,
  source_vcf TEXT NOT NULL,
  allele_index INTEGER NOT NULL,
  PRIMARY KEY (rsid, seqcol_digest, contig, pos0, ref, alt, source_vcf, allele_index)
);

CREATE INDEX rsid_alleles_lookup
ON rsid_alleles (rsid, seqcol_digest);
```

Rules:

- `rsid` is normalized to lowercase `rs` plus digits, for example `rs699`.
- `pos0` is 0-based.
- `contig` is the source VCF `CHROM` value. It must be a contig alias accepted by C4a for the matching `seqcol_digest`.
- Each ALT allele from a VCF row is emitted as a separate `rsid_alleles` row with a 1-based `allele_index`.
- Rows with multiple IDs emit one row per `rs...` ID.
- Rows with symbolic ALT, breakends, non-literal REF/ALT, empty ID, or missing POS are counted and skipped.
- `build-summary.yaml` records input rows, retained alleles, skipped buckets, distinct rsIDs, per-assembly retained counts, source URLs, source sha256 values, and build timestamp.

The `seqcol_digest` values stamped into `rsid_alleles` must come from `dataset:assembly-registry` at build
time. Do not hardcode these digests in the recipe: resolve the registry rows for GRCh38 and GRCh37, assert
that the expected assembly labels/accessions are present, and fail if either digest cannot be found. This
keeps the dbSNP artifact coupled to the same assembly identities that dataset frontmatter declares in
`identity_context.assembly.seqcol_digest`.

## Locator Contract

Existing C4a datasets keep:

```yaml
identity_context:
  molecular_ids:
    variant:
      namespace: vrs
      canonical: true
      resolution_status: resolved
      locator:
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
        allele_columns:
          ref: REF
          alt: ALT
  assembly:
    seqcol_digest: g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp
    registry: dataset:assembly-registry
    resolution_status: resolved
```

`allele_columns` is optional. If present, both `ref` and `alt` are required and filter candidate dbSNP
alleles after assembly filtering. If absent, exactly one dbSNP allele may remain for the declared assembly.

---

## File Map

Science repo (`~/d/science`):

- Create: `science/src/science_tool/commons/rsid.py`
  - Normalize rsID labels, query the pinned SQLite artifact, and return explicit defects.
- Create: `science/tests/test_commons_rsid.py`
  - Hermetic SQLite fixture tests for unknown, ambiguous, allele-filtered, and malformed rsIDs.
- Modify: `science/src/science_tool/commons/variant.py`
  - Add `vrs_id_from_rsid(...)` that resolves rsID labels and delegates to `vrs_id(...)`.
- Modify: `science/tests/test_commons_variant.py`
  - Add tests for rsID-to-VRS delegation and rsID defects.
- Modify: `science/src/science_tool/validate/checks/variant_identity.py`
  - Add `format: rsid` locator validation and row minting.
- Modify: `science/tests/validate/test_checks_variant_identity.py`
  - Add rsID locator and row-layer tests.
- Modify: `docs/plans/historical/2026-05-28-c4-variant-identity-design.md`
  - Mark C4c-1 planned/implemented after landing.
- Modify: `docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md`
  - Update C4 status after landing.
- Modify: `docs/plans/historical/2026-05-26-bio-data-architecture-umbrella-design.md`
  - Update umbrella status after landing.

Commons repo (`~/d/science-commons`):

- Create: `datasets/variant-labels-dbsnp-human/entity.md`
- Create: `datasets/variant-labels-dbsnp-human/datapackage.yaml`
- Create: `datasets/variant-labels-dbsnp-human/recipe/fetch.py`
- Create: `datasets/variant-labels-dbsnp-human/recipe/build.py`
- Create: `datasets/variant-labels-dbsnp-human/recipe/Snakefile`
- Create: `datasets/variant-labels-dbsnp-human/recipe/README.md`
- Create after fetch: `datasets/variant-labels-dbsnp-human/recipe/lockfile.yaml`
- Create after build under `$SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/`:
  - `rsid_mappings.sqlite`
  - `build-summary.yaml`

---

### Task 1: rsID Resolver

**Files:**
- Create: `science/src/science_tool/commons/rsid.py`
- Test: `science/tests/test_commons_rsid.py`

- [x] **Step 1: Write the failing resolver tests**

Add `science/tests/test_commons_rsid.py`:

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from science_tool.commons.rsid import RsidDefect, RsidMatch, resolve_rsid


def _sqlite(path: Path) -> Path:
    with sqlite3.connect(path) as conn:
        conn.executescript(
            """
            CREATE TABLE metadata (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL
            );
            CREATE TABLE rsid_alleles (
              rsid TEXT NOT NULL,
              seqcol_digest TEXT NOT NULL,
              contig TEXT NOT NULL,
              pos0 INTEGER NOT NULL,
              ref TEXT NOT NULL,
              alt TEXT NOT NULL,
              source_vcf TEXT NOT NULL,
              allele_index INTEGER NOT NULL,
              PRIMARY KEY (rsid, seqcol_digest, contig, pos0, ref, alt, source_vcf, allele_index)
            );
            CREATE INDEX rsid_alleles_lookup
            ON rsid_alleles (rsid, seqcol_digest);
            """
        )
        conn.executemany(
            """
            INSERT INTO rsid_alleles
            (rsid, seqcol_digest, contig, pos0, ref, alt, source_vcf, allele_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("rs1", "GRCH38", "NC_000001.11", 10, "A", "G", "GCF_000001405.40.gz", 1),
                ("rs2", "GRCH38", "NC_000001.11", 20, "C", "T", "GCF_000001405.40.gz", 1),
                ("rs2", "GRCH38", "NC_000001.11", 20, "C", "A", "GCF_000001405.40.gz", 2),
                ("rs2", "GRCH37", "NC_000001.10", 19, "C", "T", "GCF_000001405.25.gz", 1),
            ],
        )
    return path


def test_resolve_rsid_returns_unique_match(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("RS1", assembly_seqcol="GRCH38", sqlite_path=path)

    assert result == RsidMatch(
        rsid="rs1",
        seqcol_digest="GRCH38",
        contig="NC_000001.11",
        pos0=10,
        ref="A",
        alt="G",
        source_vcf="GCF_000001405.40.gz",
        allele_index=1,
    )


def test_resolve_rsid_filters_by_ref_alt(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("rs2", assembly_seqcol="GRCH38", sqlite_path=path, ref="C", alt="A")

    assert isinstance(result, RsidMatch)
    assert result.alt == "A"


def test_resolve_rsid_reports_ambiguity_without_allele_filter(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("rs2", assembly_seqcol="GRCH38", sqlite_path=path)

    assert result == RsidDefect("rs2", "ambiguous-rsid", "2 candidate alleles for GRCH38")


def test_resolve_rsid_reports_unknown_after_assembly_filter(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("rs1", assembly_seqcol="GRCH37", sqlite_path=path)

    assert result == RsidDefect("rs1", "rsid-assembly-mismatch", "no allele for declared assembly GRCH37")


def test_resolve_rsid_rejects_malformed_label(tmp_path: Path) -> None:
    path = _sqlite(tmp_path / "rsid_mappings.sqlite")

    result = resolve_rsid("1", assembly_seqcol="GRCH38", sqlite_path=path)

    assert result == RsidDefect("1", "malformed-rsid", "expected rs followed by digits")
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_rsid.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.rsid'`.

- [x] **Step 3: Implement the resolver**

Create `science/src/science_tool/commons/rsid.py`:

```python
"""Pinned dbSNP rsID resolver for C4c variant-label inputs."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from science_tool.commons.resolver import resolve

_DEFAULT_DATASET = "dataset:variant-labels-dbsnp-human"
SQLITE_RESOURCE = "rsid_mappings.sqlite"
_RSID = re.compile(r"^rs[1-9][0-9]*$")


@dataclass(frozen=True, slots=True)
class RsidMatch:
    rsid: str
    seqcol_digest: str
    contig: str
    pos0: int
    ref: str
    alt: str
    source_vcf: str
    allele_index: int


@dataclass(frozen=True, slots=True)
class RsidDefect:
    query: str
    reason: str
    detail: str


def normalize_rsid(query: str) -> str | RsidDefect:
    value = query.strip().lower()
    if _RSID.fullmatch(value) is None:
        return RsidDefect(query, "malformed-rsid", "expected rs followed by digits")
    return value


def _sqlite_for_registry(
    registry: str,
    *,
    commons_root: Path | str | None,
    data_root: Path | str | None,
) -> Path:
    resolved = resolve(
        registry,
        SQLITE_RESOURCE,
        commons_root=None if commons_root is None else Path(commons_root),
        data_root=None if data_root is None else Path(data_root),
    )
    return resolved.path


def resolve_rsid(
    query: str,
    *,
    assembly_seqcol: str,
    registry: str = _DEFAULT_DATASET,
    sqlite_path: Path | str | None = None,
    ref: str | None = None,
    alt: str | None = None,
    commons_root: Path | str | None = None,
    data_root: Path | str | None = None,
) -> RsidMatch | RsidDefect:
    rsid = normalize_rsid(query)
    if isinstance(rsid, RsidDefect):
        return rsid

    db_path = Path(sqlite_path) if sqlite_path is not None else _sqlite_for_registry(
        registry,
        commons_root=commons_root,
        data_root=data_root,
    )
    uri = f"{db_path.resolve().as_uri()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        conn.row_factory = sqlite3.Row
        rows = list(
            conn.execute(
                """
                SELECT rsid, seqcol_digest, contig, pos0, ref, alt, source_vcf, allele_index
                FROM rsid_alleles
                WHERE rsid = ? AND seqcol_digest = ?
                ORDER BY contig, pos0, ref, alt, source_vcf, allele_index
                """,
                (rsid, assembly_seqcol),
            )
        )

    if not rows:
        return RsidDefect(rsid, "rsid-assembly-mismatch", f"no allele for declared assembly {assembly_seqcol}")

    if ref is not None or alt is not None:
        ref_filter = "" if ref is None else ref.upper()
        alt_filter = "" if alt is None else alt.upper()
        rows = [row for row in rows if row["ref"] == ref_filter and row["alt"] == alt_filter]
        if not rows:
            return RsidDefect(rsid, "rsid-allele-mismatch", "no candidate matches supplied REF/ALT")

    if len(rows) > 1:
        return RsidDefect(rsid, "ambiguous-rsid", f"{len(rows)} candidate alleles for {assembly_seqcol}")

    row = rows[0]
    return RsidMatch(
        rsid=row["rsid"],
        seqcol_digest=row["seqcol_digest"],
        contig=row["contig"],
        pos0=int(row["pos0"]),
        ref=row["ref"],
        alt=row["alt"],
        source_vcf=row["source_vcf"],
        allele_index=int(row["allele_index"]),
    )
```

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_rsid.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/commons/rsid.py science/tests/test_commons_rsid.py
rtk git commit -m "feat: add pinned rsid resolver"
```

### Task 2: Variant rsID Minting Boundary

**Files:**
- Modify: `science/src/science_tool/commons/variant.py`
- Test: `science/tests/test_commons_variant.py`

- [x] **Step 1: Write failing variant tests**

Append to `science/tests/test_commons_variant.py`:

```python
def test_vrs_id_from_rsid_delegates_to_spdi(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons.rsid import RsidMatch

    calls: list[tuple[str, str, str]] = []
    rsid_calls: list[object] = []

    def fake_resolve_rsid(*args: object, **kwargs: object) -> RsidMatch:
        rsid_calls.append(kwargs.get("sqlite_path"))
        return RsidMatch(
            rsid="rs1",
            seqcol_digest="GRCH38",
            contig="NC_000001.11",
            pos0=10,
            ref="A",
            alt="G",
            source_vcf="GCF_000001405.40.gz",
            allele_index=1,
        )

    monkeypatch.setattr(V, "resolve_rsid", fake_resolve_rsid)

    def fake_vrs_id(expr: str, *, fmt: str, assembly_seqcol: str, **kwargs: object) -> V.VariantMatch:
        calls.append((expr, fmt, assembly_seqcol))
        return V.VariantMatch(vrs_id="ga4gh:VA.rsid", refget_digest="SQ.ref")

    monkeypatch.setattr(V, "vrs_id", fake_vrs_id)

    result = V.vrs_id_from_rsid("rs1", assembly_seqcol="GRCH38", sqlite_path="/tmp/rsid.sqlite")

    assert result == V.VariantMatch(vrs_id="ga4gh:VA.rsid", refget_digest="SQ.ref")
    assert calls == [("NC_000001.11:10:A:G", "spdi", "GRCH38")]
    assert rsid_calls == ["/tmp/rsid.sqlite"]


def test_vrs_id_from_rsid_returns_variant_defect(monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.commons.rsid import RsidDefect

    monkeypatch.setattr(
        V,
        "resolve_rsid",
        lambda *args, **kwargs: RsidDefect("rs2", "ambiguous-rsid", "2 candidate alleles for GRCH38"),
    )

    result = V.vrs_id_from_rsid("rs2", assembly_seqcol="GRCH38")

    assert result == V.VariantDefect("rs2", "ambiguous-rsid", "2 candidate alleles for GRCH38")
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_variant.py::test_vrs_id_from_rsid_delegates_to_spdi science/tests/test_commons_variant.py::test_vrs_id_from_rsid_returns_variant_defect -q
```

Expected: FAIL with `AttributeError: module 'science_tool.commons.variant' has no attribute 'vrs_id_from_rsid'`.

- [x] **Step 3: Add `vrs_id_from_rsid`**

Modify `science/src/science_tool/commons/variant.py`:

```python
from science_tool.commons.rsid import RsidDefect, RsidMatch, resolve_rsid
```

Add after `vrs_id(...)`:

```python
def vrs_id_from_rsid(
    rsid: str,
    *,
    assembly_seqcol: str,
    registry: str = "dataset:variant-labels-dbsnp-human",
    sqlite_path: Path | str | None = None,
    ref: str | None = None,
    alt: str | None = None,
    commons_root: Path | str | None = None,
    data_root: Path | str | None = None,
    store_root: Path | str | None = None,
) -> VariantMatch | VariantDefect:
    resolved = resolve_rsid(
        rsid,
        assembly_seqcol=assembly_seqcol,
        registry=registry,
        sqlite_path=sqlite_path,
        ref=ref,
        alt=alt,
        commons_root=commons_root,
        data_root=data_root,
    )
    if isinstance(resolved, RsidDefect):
        return VariantDefect(resolved.query, resolved.reason, resolved.detail)
    assert isinstance(resolved, RsidMatch)
    expr = f"{resolved.contig}:{resolved.pos0}:{resolved.ref}:{resolved.alt}"
    return vrs_id(
        expr,
        fmt="spdi",
        assembly_seqcol=assembly_seqcol,
        commons_root=commons_root,
        data_root=data_root,
        store_root=store_root,
    )
```

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_commons_variant.py::test_vrs_id_from_rsid_delegates_to_spdi science/tests/test_commons_variant.py::test_vrs_id_from_rsid_returns_variant_defect -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/commons/variant.py science/tests/test_commons_variant.py
rtk git commit -m "feat: mint vrs ids from rsid labels"
```

### Task 3: rsID Locator Validation

**Files:**
- Modify: `science/src/science_tool/validate/checks/variant_identity.py`
- Test: `science/tests/validate/test_checks_variant_identity.py`

- [x] **Step 1: Write failing locator tests**

Append to `science/tests/validate/test_checks_variant_identity.py`:

```python
def test_rsid_locator_requires_registry() -> None:
    ds = _ds({"namespace": "vrs", "locator": {"resource": "variants.csv", "format": "rsid", "column": "rsid"}})

    errors = [r for r in evaluate_variant_declaration([ds]) if r.severity is Severity.ERROR]

    assert errors[0].rule == "identity.variant-locator-malformed"
    assert "rsid locator requires registry" in errors[0].message


def test_rsid_locator_accepts_optional_allele_columns() -> None:
    locator = {
        "resource": "variants.csv",
        "format": "rsid",
        "column": "rsid",
        "registry": "dataset:variant-labels-dbsnp-human",
        "allele_columns": {"ref": "REF", "alt": "ALT"},
    }
    ds = _ds({"namespace": "vrs", "locator": locator})

    assert list(evaluate_variant_declaration([ds])) == []
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/validate/test_checks_variant_identity.py::test_rsid_locator_requires_registry science/tests/validate/test_checks_variant_identity.py::test_rsid_locator_accepts_optional_allele_columns -q
```

Expected: FAIL because `rsid` is not an accepted locator format.

- [x] **Step 3: Extend locator validation**

In `science/src/science_tool/validate/checks/variant_identity.py`, change:

```python
_FORMATS = frozenset({"spdi", "hgvs", "vcf", "rsid"})
```

Then add this branch inside `_locator_defect(...)` after the `vcf` branch:

```python
    if fmt.lower() == "rsid":
        registry = locator.get("registry")
        if not isinstance(registry, str) or not registry.startswith("dataset:"):
            return "rsid locator requires registry dataset:<slug>"
        column = locator.get("column")
        if not isinstance(column, str) or not column.strip():
            return "rsid locator requires a nonblank column"
        allele_columns = locator.get("allele_columns")
        if allele_columns is not None:
            if not isinstance(allele_columns, dict):
                return "rsid locator allele_columns must be an object"
            for key in ("ref", "alt"):
                value = allele_columns.get(key)
                if not isinstance(value, str) or not value.strip():
                    return f"rsid locator allele_columns.{key} must be a nonblank string"
        return None
```

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/validate/test_checks_variant_identity.py::test_rsid_locator_requires_registry science/tests/validate/test_checks_variant_identity.py::test_rsid_locator_accepts_optional_allele_columns -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/validate/checks/variant_identity.py science/tests/validate/test_checks_variant_identity.py
rtk git commit -m "feat: accept rsid variant locators"
```

### Task 4: Variant Row Minting for rsID Locators

**Files:**
- Modify: `science/src/science_tool/validate/checks/variant_identity.py`
- Test: `science/tests/validate/test_checks_variant_identity.py`

- [x] **Step 1: Write failing row-layer tests**

Append to `science/tests/validate/test_checks_variant_identity.py`:

```python
def test_row_layer_mints_rsid_locator(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "rsid_mappings.sqlite"
    sqlite_path.write_bytes(b"fixture")
    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
        allele_columns:
          ref: REF
          alt: ALT
"""
    project = _variant_project(
        tmp_path,
        "rsid,REF,ALT\nrs1,A,G\n",
        locator=rsid_locator,
    )

    calls: list[tuple[str, str | None, str | None]] = []
    resolve_calls: list[tuple[str, str]] = []

    def fake_resolve(dataset_id: str, logical_path: str):
        resolve_calls.append((dataset_id, logical_path))
        return type("Resolved", (), {"path": sqlite_path})()

    def fake_vrs_id_from_rsid(
        rsid: str,
        *,
        assembly_seqcol: str,
        sqlite_path: Path,
        ref: str | None = None,
        alt: str | None = None,
    ) -> VariantMatch:
        calls.append((rsid, ref, alt))
        assert sqlite_path.name == "rsid_mappings.sqlite"
        return VariantMatch(vrs_id="ga4gh:VA.good", refget_digest="SQ.ref")

    monkeypatch.setattr("science_tool.commons.resolver.resolve", fake_resolve)
    monkeypatch.setattr("science_tool.commons.variant.vrs_id_from_rsid", fake_vrs_id_from_rsid)

    results = list(check_variant_identity(_ctx(project)))

    assert [r.rule for r in results if r.rule == "identity.variant-rows-minted"] == ["identity.variant-rows-minted"]
    assert resolve_calls == [("dataset:variant-labels-dbsnp-human", "rsid_mappings.sqlite")]
    assert calls == [("rs1", "A", "G")]


def test_row_layer_reports_ambiguous_rsid(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "rsid_mappings.sqlite"
    sqlite_path.write_bytes(b"fixture")
    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
"""
    project = _variant_project(
        tmp_path,
        "rsid\nrs2\n",
        locator=rsid_locator,
    )

    monkeypatch.setattr(
        "science_tool.commons.variant.vrs_id_from_rsid",
        lambda *args, **kwargs: VariantDefect("rs2", "ambiguous-rsid", "2 candidate alleles for GRCH38"),
    )
    monkeypatch.setattr(
        "science_tool.commons.resolver.resolve",
        lambda dataset_id, logical_path: type("Resolved", (), {"path": sqlite_path})(),
    )

    results = list(check_variant_identity(_ctx(project)))

    errors = [r for r in results if r.rule == "identity.variant-rows-unresolved"]
    assert len(errors) == 1
    assert "ambiguous-rsid=1" in errors[0].message


def test_row_layer_reports_short_rsid_allele_row_as_resource_invalid(tmp_path: Path, monkeypatch) -> None:
    sqlite_path = tmp_path / "rsid_mappings.sqlite"
    sqlite_path.write_bytes(b"fixture")
    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
        allele_columns:
          ref: REF
          alt: ALT
"""
    project = _variant_project(tmp_path, "rsid,REF,ALT\nrs1,A\n", locator=rsid_locator)
    monkeypatch.setattr(
        "science_tool.commons.resolver.resolve",
        lambda dataset_id, logical_path: type("Resolved", (), {"path": sqlite_path})(),
    )

    results = list(check_variant_identity(_ctx(project)))

    errors = [r for r in results if r.rule == "identity.variant-resource-invalid"]
    assert len(errors) == 1
    assert "missing value for column 'ALT'" in errors[0].message


def test_row_layer_reports_registry_unavailable_as_info(tmp_path: Path, monkeypatch) -> None:
    from science_tool.commons.errors import DataResourceNotFoundError

    rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
"""
    project = _variant_project(tmp_path, "rsid\nrs1\n", locator=rsid_locator)

    def fake_resolve(dataset_id: str, logical_path: str):
        raise DataResourceNotFoundError(dataset_id, logical_path, tried=[])

    monkeypatch.setattr("science_tool.commons.resolver.resolve", fake_resolve)

    results = list(check_variant_identity(_ctx(project)))

    infos = [r for r in results if r.rule == "identity.variant-registry-unavailable"]
    assert len(infos) == 1
    assert infos[0].severity is Severity.INFO
    assert not [r for r in results if r.severity is Severity.ERROR]
```

Extend `_variant_project(...)` and `_variant_project_bytes(...)` in the same file with `locator: str | None = None`.
Keep the existing default when `locator is None`, and pass this exact YAML string in the new rsID tests:

```python
rsid_locator = """\
        resource: variants.csv
        format: rsid
        column: rsid
        registry: dataset:variant-labels-dbsnp-human
        allele_columns:
          ref: REF
          alt: ALT
"""
```

In `_variant_project_bytes(...)`, render:

```python
    locator_yaml = locator if locator is not None else f"""\
        resource: {locator_resource}
        format: spdi
        column: variant
"""
```

and replace the hard-coded locator block with:

```python
      locator:
{locator_yaml}\
```

Thread the new argument through the delegating helper:

```python
def _variant_project(
    tmp_path: Path,
    variants_csv: str,
    *,
    datapackage_field: str | None = None,
    locator_resource: str = "variants.csv",
    resource_name: str = "variants",
    resource_path: str = "variants.csv",
    locator: str | None = None,
) -> Path:
    return _variant_project_bytes(
        tmp_path,
        variants_csv.encode("utf-8"),
        datapackage_field=datapackage_field,
        locator_resource=locator_resource,
        resource_name=resource_name,
        resource_path=resource_path,
        locator=locator,
    )
```

- [x] **Step 2: Run tests to verify they fail**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/validate/test_checks_variant_identity.py::test_row_layer_mints_rsid_locator science/tests/validate/test_checks_variant_identity.py::test_row_layer_reports_ambiguous_rsid science/tests/validate/test_checks_variant_identity.py::test_row_layer_reports_short_rsid_allele_row_as_resource_invalid science/tests/validate/test_checks_variant_identity.py::test_row_layer_reports_registry_unavailable_as_info -q
```

Expected: FAIL because the row layer still dispatches all formats through `vrs_id(...)`.

- [x] **Step 3: Add rsID dispatch helpers**

In `science/src/science_tool/validate/checks/variant_identity.py`, change the row-layer imports to include
`vrs_id_from_rsid` and the commons resolver:

```python
from science_tool.commons.resolver import resolve
from science_tool.commons.rsid import SQLITE_RESOURCE
from science_tool.commons.variant import (
    VariantDefect,
    VariantMatch,
    VariantStoreUnavailable,
    vrs_id,
    vrs_id_from_rsid,
)
```

Add helpers near `_row_expr(...)`:

```python
def _rsid_allele_filter(
    row: dict[str | None, str | list[str] | None],
    locator: dict[str, Any],
) -> tuple[str | None, str | None]:
    allele_columns = locator.get("allele_columns")
    if not isinstance(allele_columns, dict):
        return None, None
    return (
        _required_value(row, str(allele_columns["ref"])),
        _required_value(row, str(allele_columns["alt"])),
    )
```

After `fmt = str(locator["format"]).lower()` and before opening the located variant resource, resolve the
rsID registry once per dataset:

```python
        rsid_sqlite_path: Path | None = None
        if fmt == "rsid":
            try:
                rsid_sqlite_path = resolve(str(locator["registry"]), SQLITE_RESOURCE).path
            except CommonsError as error:
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: variant rsID registry unavailable; row VRS IDs cannot be minted: {error}",
                    "identity.variant-registry-unavailable",
                )
                continue
```

Inside the row loop, replace the single `vrs_id(...)` call with this block. The allele filter extraction
must stay inside the same `try` that catches `_row_expr(...)` `ValueError`, so short CSV rows become
`identity.variant-resource-invalid` instead of aborting the whole check:

```python
                    try:
                        expr = _row_expr(row, locator, fmt)
                        if fmt == "rsid":
                            if rsid_sqlite_path is None:
                                raise TypeError("rsID SQLite path was not resolved")
                            ref_filter, alt_filter = _rsid_allele_filter(row, locator)
                            # sqlite_path is pre-resolved once per dataset, so registry is
                            # intentionally omitted here: resolve_rsid only consults registry
                            # as a fallback when sqlite_path is None.
                            result = vrs_id_from_rsid(
                                expr,
                                assembly_seqcol=seqcol,
                                sqlite_path=rsid_sqlite_path,
                                ref=ref_filter,
                                alt=alt_filter,
                            )
                        else:
                            result = vrs_id(expr, fmt=fmt, assembly_seqcol=seqcol)
                    except ValueError as error:
                        invalid_resource = f"row {row_number}: {error}"
                        break
```

Update `_required_columns(...)` so rsID locators require the rsID column plus optional allele columns:

```python
    if fmt == "rsid":
        required = [str(locator["column"])]
        allele_columns = locator.get("allele_columns")
        if isinstance(allele_columns, dict):
            required.extend([str(allele_columns["ref"]), str(allele_columns["alt"])])
        return required
```

- [x] **Step 4: Run tests to verify they pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/validate/test_checks_variant_identity.py::test_row_layer_mints_rsid_locator science/tests/validate/test_checks_variant_identity.py::test_row_layer_reports_ambiguous_rsid science/tests/validate/test_checks_variant_identity.py::test_row_layer_reports_short_rsid_allele_row_as_resource_invalid science/tests/validate/test_checks_variant_identity.py::test_row_layer_reports_registry_unavailable_as_info -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/validate/checks/variant_identity.py science/tests/validate/test_checks_variant_identity.py
rtk git commit -m "feat: validate rsid variant rows"
```

### Task 5: dbSNP Commons Dataset Recipe

**Files:**
- Create: `~/d/science-commons/datasets/variant-labels-dbsnp-human/entity.md`
- Create: `~/d/science-commons/datasets/variant-labels-dbsnp-human/datapackage.yaml`
- Create: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/fetch.py`
- Create: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/build.py`
- Create: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/Snakefile`
- Create: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/README.md`
- Create after fetch: `~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/lockfile.yaml`

- [x] **Step 1: Create the dataset entity**

Create `entity.md`:

```markdown
---
schema_profile: science-entity-base/1.0+dataset/1.0
id: dataset:variant-labels-dbsnp-human
type: dataset
title: Human dbSNP rsID to small-allele variant-label map
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

Pinned dbSNP build 157 human rsID label map for C4c variant input translation.

This dataset is not a canonical variant identity system. It resolves external rsID labels to exact
assembly-anchored alleles so the Science C4a resolver can mint canonical GA4GH VRS identifiers from the
pinned local sequence store.

Only precise literal small alleles are retained. Symbolic alleles, breakends, imprecise structural
variants, and rows that cannot be represented as `contig:pos0:ref:alt` SPDI inputs are skipped and counted
in `build-summary.yaml`.
```

- [x] **Step 2: Create the datapackage skeleton**

Create `datapackage.yaml` with zero placeholders that `recipe/build.py --update-datapackage` replaces:

```yaml
name: variant-labels-dbsnp-human
profile: data-package
resources:
- name: rsid_mappings
  path: rsid_mappings.sqlite
  format: sqlite
  mediatype: application/vnd.sqlite3
  source:
    type: local
    ref: ${OUTPUT_ROOT}/variant-labels-dbsnp-human/rsid_mappings.sqlite
  hash: sha256:0000000000000000000000000000000000000000000000000000000000000000
  bytes: 0
- name: build_summary
  path: build-summary.yaml
  format: yaml
  mediatype: application/x-yaml
  source:
    type: local
    ref: ${OUTPUT_ROOT}/variant-labels-dbsnp-human/build-summary.yaml
  hash: sha256:0000000000000000000000000000000000000000000000000000000000000000
  bytes: 0
```

- [x] **Step 3: Implement `recipe/fetch.py`**

The fetcher must:

- Reject any URL containing `/latest_release/`.
- Accept explicit archive URLs for both VCFs.
- Download `.gz` and `.gz.md5` sidecars.
- Compute sha256 and bytes.
- Write `lockfile.yaml`.
- Verify existing downloads against `lockfile.yaml` by default.

Use the C4b liftover fetcher as the local pattern and adapt the dataset name, URL list, and lockfile keys.

- [x] **Step 4: Implement `recipe/build.py`**

The builder must:

- Read `lockfile.yaml`.
- Stream each pinned `.gz` VCF with `gzip.open(..., "rt")`.
- Map `GCF_000001405.40.gz` to the GRCh38 seqcol digest from `dataset:assembly-registry`.
- Map `GCF_000001405.25.gz` to the GRCh37 seqcol digest from `dataset:assembly-registry`.
- Assert those digests were read from the registry rows for GRCh38 and GRCh37 during this build; do not duplicate digest constants in the recipe.
- Create `rsid_mappings.sqlite` using the schema in this plan.
- Split comma-separated ALT alleles.
- Split semicolon-separated ID values and retain only IDs matching `^rs[1-9][0-9]*$`.
- Skip rows whose REF or ALT is non-literal, symbolic, breakend-like, or empty.
- Insert with `INSERT OR IGNORE` so duplicate dbSNP representations do not fail the build.
- Write `build-summary.yaml`.
- With `--update-datapackage`, compute sha256/bytes for both resources and rewrite `datapackage.yaml`.

- [x] **Step 5: Create `recipe/README.md`**

The README must state:

```markdown
# Human dbSNP rsID Variant Labels

This recipe builds `dataset:variant-labels-dbsnp-human`, the C4c rsID input resolver artifact.

Use archived NCBI dbSNP URLs only:

- `https://ftp.ncbi.nih.gov/snp/archive/b157/VCF/GCF_000001405.40.gz`
- `https://ftp.ncbi.nih.gov/snp/archive/b157/VCF/GCF_000001405.25.gz`

Do not use `https://ftp.ncbi.nih.gov/snp/latest_release/VCF/`; that path is mutable.

The built SQLite file is large and belongs under `$SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/`.
The commons repository stores the recipe, lockfile, entity, and datapackage hashes, not the bulk SQLite
or VCF bytes.
```

- [x] **Step 6: Add a Snakemake workflow entrypoint**

Create `recipe/Snakefile` so operators regenerate the artifact through the workflow rather than one-off
script invocations. The default target must:

- fetch the pinned dbSNP archive sources and `.md5` sidecars;
- write `recipe/lockfile.yaml`;
- require `assembly-registry/assemblies.csv` as an explicit input;
- build `$SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/rsid_mappings.sqlite`;
- write `$SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/build-summary.yaml`;
- refresh `datapackage.yaml`.

Run the workflow from the Science environment:

```bash
rtk uv run --frozen --project ~/d/science/meta snakemake \
  -s ~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/Snakefile \
  --cores 1
```

The workflow defaults to `$SCIENCE_COMMONS_DATA_ROOT` or `/data/science-commons`. Override
`assembly_registry` only for an equivalent pinned registry CSV; do not hardcode GRCh37/GRCh38 seqcol
digests into the dbSNP recipe.

- [x] **Step 7: Run a tiny fixture build before the full source build**

Add fixture mode or a small test VCF under a temporary directory and verify:

```bash
rtk uv run --frozen --project science python ~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/build.py --input-root /tmp/dbsnp-fixture --output-root /tmp/dbsnp-output
```

Expected: `rsid_mappings.sqlite` exists and contains at least one row for the fixture rsID.

- [ ] **Step 8: Run full-build feasibility check through Snakemake**

Start the full build only through the workflow:

```bash
rtk uv run --frozen --project ~/d/science/meta snakemake \
  -s ~/d/science-commons/datasets/variant-labels-dbsnp-human/recipe/Snakefile \
  --cores 1
```

After the full archive build finishes, inspect `build-summary.yaml` before updating the datapackage:

```bash
rtk sed -n '1,120p' $SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/build-summary.yaml
rtk ls -lh $SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/rsid_mappings.sqlite
```

Expected: the summary reports input rows, retained alleles, skipped buckets, distinct rsIDs,
per-assembly counts, SQLite bytes, and build seconds. If the SQLite size or build time is outside local
operational limits, stop before committing datapackage hashes and revisit partitioning/indexing.

- [x] **Step 9: Commit commons recipe**

In `~/d/science-commons`:

```bash
rtk git add datasets/variant-labels-dbsnp-human
rtk git commit -m "data: add dbsnp variant label recipe"
```

### Task 6: Resolver Smoke Against Commons Data

**Files:**
- No new files unless the smoke reveals defects.

**Status:** Deferred until an operator fetches/builds the full dbSNP SQLite artifact through
`recipe/Snakefile` under `$SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/`. The recipe, workflow
entrypoint, and fixture path are implemented, but this session intentionally did not complete the 26 GB /
28 GB source archive workflow or build the full SQLite.

- [ ] **Step 1: Build the SQLite artifact through Snakemake**

Run the workflow against the pinned archive sources and verify the outputs under:

```text
$SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/rsid_mappings.sqlite
$SCIENCE_COMMONS_DATA_ROOT/variant-labels-dbsnp-human/build-summary.yaml
```

- [ ] **Step 2: Verify resolver lookup through the commons resolver**

Run:

```bash
rtk uv run --frozen --project science python -c "from science_tool.commons.rsid import resolve_rsid; print(resolve_rsid('rs699', assembly_seqcol='g04lKdxiYtG3dOGeUC5AdKEifw65G0Wp'))"
```

Expected: either an `RsidMatch(...)` for GRCh38 or a specific `RsidDefect(...)`. A `DataResourceNotFoundError`, hash mismatch, or SQLite open error is a failure.

- [ ] **Step 3: Commit datapackage hash updates**

If the full build updated `datapackage.yaml`, commit the final hashes in `~/d/science-commons`:

```bash
rtk git add datasets/variant-labels-dbsnp-human/datapackage.yaml datasets/variant-labels-dbsnp-human/recipe/lockfile.yaml
rtk git commit -m "fix: pin dbsnp variant label hashes"
```

### Task 7: Docs and Status Updates

**Files:**
- Modify: `docs/plans/historical/2026-05-28-c4-variant-identity-design.md`
- Modify: `docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md`
- Modify: `docs/plans/historical/2026-05-26-bio-data-architecture-umbrella-design.md`
- Modify: `docs/plans/2026-05-31-c4c-rsid-variant-label-plan.md`

- [x] **Step 1: Update C4 design status**

In `docs/plans/historical/2026-05-28-c4-variant-identity-design.md`, change C4c from wholly remaining to:

```markdown
C4c-1 rsID input is implemented through `dataset:variant-labels-dbsnp-human`; transcript/protein HGVS
projection remains deferred. Full dbSNP artifact build/operator smoke remains pending.
```

- [x] **Step 2: Update Pillar C status**

In `docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md`, update the C4 row to say:

```markdown
C4a variant identity, C4b liftover/compatibility, and C4c-1 rsID input implemented locally; full dbSNP artifact build/operator smoke and transcript/protein projection remain.
```

- [x] **Step 3: Update umbrella status**

In `docs/plans/historical/2026-05-26-bio-data-architecture-umbrella-design.md`, update the status line and §8 so C4c no longer appears fully open once C4c-1 lands.

- [x] **Step 4: Mark this plan implemented**

Change this plan's task checkboxes as tasks land and add an implementation status paragraph near the top:

```markdown
**Implementation status:** Implemented locally in `~/d/science` and `~/d/science-commons`; C4c-1 supports pinned dbSNP rsID input. Transcript/protein HGVS projection remains out of scope.
```

- [x] **Step 5: Commit docs**

```bash
rtk git add docs/plans/historical/2026-05-28-c4-variant-identity-design.md docs/plans/historical/2026-05-26-bio-identity-and-reference-genome-design.md docs/plans/historical/2026-05-26-bio-data-architecture-umbrella-design.md docs/plans/2026-05-31-c4c-rsid-variant-label-plan.md
rtk git commit -m "docs: update c4c rsid status"
```

### Task 8: Final Verification

**Files:**
- No new files.

- [x] **Step 1: Run targeted tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_commons_rsid.py \
  science/tests/test_commons_variant.py \
  science/tests/validate/test_checks_variant_identity.py \
  -q
```

Expected: PASS.

- [x] **Step 2: Run lint**

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/commons/rsid.py \
  science/src/science_tool/commons/variant.py \
  science/src/science_tool/validate/checks/variant_identity.py \
  science/tests/test_commons_rsid.py \
  science/tests/test_commons_variant.py \
  science/tests/validate/test_checks_variant_identity.py
```

Expected: `All checks passed!`

- [x] **Step 3: Run type check**

```bash
rtk uv run --frozen --project science pyright \
  science/src/science_tool/commons/rsid.py \
  science/src/science_tool/commons/variant.py \
  science/src/science_tool/validate/checks/variant_identity.py \
  science/tests/test_commons_rsid.py \
  science/tests/test_commons_variant.py \
  science/tests/validate/test_checks_variant_identity.py
```

Expected: `0 errors, 0 warnings, 0 informations`.

- [x] **Step 4: Run whitespace check**

```bash
rtk git diff --check
```

Expected: no output.

---

## Self-Review Checklist

- [x] **No new canonical identity:** rsID remains an input label; VRS remains canonical.
- [x] **No live service:** implementation uses only pinned local dbSNP artifacts.
- [x] **No silent ambiguity:** multi-allelic rsIDs require allele disambiguation or produce `ambiguous-rsid`.
- [x] **No giant CSV scan:** resolver uses indexed SQLite lookup.
- [x] **No per-row file hashing:** validation resolves/hash-verifies `rsid_mappings.sqlite` once per dataset and passes `sqlite_path` through row calls.
- [x] **Assembly anchored:** every lookup filters by declared `identity_context.assembly.seqcol_digest`.
- [x] **Registry-coupled digests:** the dbSNP build reads GRCh37/GRCh38 seqcol digests from `dataset:assembly-registry`, not hardcoded constants.
- [ ] **Feasibility checked:** full-build SQLite size, build time, and retained/skipped row counts are recorded before datapackage hashes are committed.
- [x] **Hermetic tests:** unit and validation tests use temporary SQLite fixtures and monkeypatches, not full dbSNP data.
- [x] **Transcript/protein projection remains out of scope:** no partial projection implementation is added.
