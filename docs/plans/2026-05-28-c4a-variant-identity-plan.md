# C4a — Variant Identity (VRS 2.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mint reproducible, offline, assembly-anchored GA4GH VRS 2.0 variant identifiers (`ga4gh:VA…`) for variants declared on GRCh38 or GRCh37, from SPDI / genomic-HGVS / VCF inputs, plus the declaration + validate check that exercises them.

**Architecture:** A pinned, content-addressed per-contig reference-sequence store (bytes built locally, digests committed) is read by a pure, offline `ga4gh.vrs` `DataProxy` whose contig identity comes from the C1 assembly registry (extended here with per-contig refget digests + an alias table). A thin `vrs_id()` resolver wraps `ga4gh.vrs` normalization + identifier computation behind our own stable signature. A two-layer validate check verifies the variant-tier declaration (shape + locator) and then mints the actual dataset rows.

**Tech Stack:** Python 3.13, `ga4gh.vrs` (VRS 2.x; pinned in Task 2), the existing commons reference-collection substrate (`resolve()`, `dataset_frontmatters`, `@Check`), CSV/TSV data resources, pytest.

---

## Pre-flight (read once before Task 1)

- **Branch.** Create `feat/c4a-variant-identity` off `main`. Do all work there. (Subagent executors: `cd` to the repo root `~/d/science` and verify the branch before each task — commits must not land on `main`.)
- **Two repos.** Code + tests + fixtures live in `~/d/science` (the `science_tool` package under `science/src/science_tool/`, tests under `science/tests/`). The *commons data artifacts* (the sequence-store dataset and the assembly-registry resource additions) live in the separate `~/d/science-commons` repo and ship **built-unbuilt** (placeholder hash, count 0), exactly like the C2/C3 crosswalks. Tasks 1–11 are entirely in `~/d/science`; Task 12 touches `~/d/science-commons`.
- **Design source of truth.** `docs/plans/2026-05-28-c4-variant-identity-design.md` (C4a = §1–§9). Parent: `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` (C-D1…C-D6).
- **Test command.** From `~/d/science`: `uv run pytest science/tests/<file>::<test> -v`. The full validate suite is `uv run pytest science/tests/validate/ -q`.
- **House conventions.** Composition > inheritance; explicit > defensive; fail early (no silent fallbacks); no "legacy"/"compatibility" layers; no "Unified" prefix; no `Co-Authored-By` trailers; use `~/d/` in any doc/code paths.
- **Pattern templates to mirror (read these):** `science/src/science_tool/commons/assembly.py` (registry resolver), `commons/gene_crosswalk.py` + `gene_crosswalk_build.py` (resolver + build-helper split), `commons/resolver.py` (`resolve()` — note it re-hashes the whole file per call, so it is used **only** for the small CSVs, never the multi-GB sequence bytes), `validate/checks/identity_context.py` (`_tier_defect`, `_TierSpec`, two-stage check wiring), `science/tests/test_commons_gene_crosswalk.py` + `science/tests/validate/test_checks_identity_context.py` (test style).

---

## File Structure

**New in `science/src/science_tool/commons/`:**
- `assembly_report_build.py` — pure parser: NCBI assembly report text → contig rows + alias rows (build-time; `fetch_text` is the only network call).
- `contigs.py` — resolver over the registry's `contigs.csv` + `contig_aliases.csv`: `resolve_contig(alias, *, seqcol_digest) → ContigMatch`. Exactly-one-match; ambiguous/unknown/accession-mismatch are explicit errors.
- `sequence_store.py` — content-addressed per-contig sequence reader: `open_store(root).sequence(refget_digest, start, end)`; verify-once-per-contig against the refget digest; fail loud on missing.
- `refget_proxy.py` — the `ga4gh.vrs` `DataProxy` subclass over `contigs` + `sequence_store` (offline; fail-loud).
- `vrs.py` — the ga4gh.vrs boundary: `compute_vrs_id(proxy, *, fmt, expr) → str` (wraps whatever 2.x surface the spike pins; the *only* module that imports `ga4gh.vrs`).
- `variant.py` — public resolver: `vrs_id(expr, *, fmt, assembly_seqcol, …) → VariantMatch` (parses, resolves contig, flags, calls `vrs.compute_vrs_id`).
- `sequence_store_build.py` — build helper: slice FASTA into per-contig files named by refget digest, verify, write manifest (network build-time only).

**Modified in `science/src/science_tool/`:**
- `commons/assembly_registry_build.py` — add `build_contig_rows(level2, seqcol_digest)`.
- `validate/checks/identity_context.py` — rename private `_tier_defect` → public `tier_declaration_defect` (the shared, registry-agnostic shape validator); update internal callers.
- `validate/checks/variant_identity.py` *(new)* — `@Check(section="variant identity", order=33)`; declaration layer (reuses `tier_declaration_defect` + locator check) + row layer (mint located rows).

**New tests in `science/tests/`:** `test_commons_assembly_report_build.py`, `test_commons_contigs.py`, `test_commons_sequence_store.py`, `test_commons_refget_proxy.py`, `test_commons_vrs_spike.py`, `test_commons_variant.py`, `validate/test_checks_variant_identity.py`.

**New fixtures under `science/tests/fixtures/commons/`:** `assembly-registry/` + `assembly-registry-data/` (entity + `assemblies.csv`/`contigs.csv`/`contig_aliases.csv`), `seqstore/` (a tiny synthetic contig file), and a `variant-dataset/` for the check.

**New in `~/d/science-commons/` (Task 12):** `datasets/sequence-store-grch38-grch37/` (datapackage + recipe + entity), and additions to `datasets/assembly-registry/`.

---

## Task 1: Dependency spike — VRS identify through an injected proxy, offline

**Purpose:** De-risk the entire approach before building anything. Prove the pinned `ga4gh.vrs` can normalize + compute an identifier through a *custom* `DataProxy` with **no SeqRepo and no network**. The spike's confirmed API surface is recorded and consumed by Task 5 (`vrs.py`). If it fails, switch Task 5 to the fallback (local parsers + core models) — see Step 6.

**Files:**
- Create: `science/tests/test_commons_vrs_spike.py`

- [ ] **Step 1: Add `ga4gh.vrs` to the environment for the spike only**

Run (from `~/d/science`): `uv add --dev 'ga4gh.vrs>=2.3,<3'`
Expected: resolves a non-yanked 2.x release (2.1.x are yanked). Record the exact resolved version from `uv.lock` (e.g. `2.3.0`) in the commit message — Task 2 promotes it to a real dependency.

- [ ] **Step 2: Write the spike test (an in-memory proxy + a known identity property)**

```python
# science/tests/test_commons_vrs_spike.py
"""Spike (C4a Task 1): prove ga4gh.vrs normalizes + identifies through a custom,
offline DataProxy. This is a PERMANENT test — it is the contract Task 5 wraps.
If the public translator surface differs from what is asserted here, FIX THIS
TEST to match the installed version and record the working surface, then mirror
it in commons/vrs.py."""
from __future__ import annotations

import pytest

ga4gh_vrs = pytest.importorskip("ga4gh.vrs")

# A 40bp synthetic contig and its refget digest, computed below.
_SEQ = "CGTACGTACGTACGTACGTACGTACGTACGTACGTACGTA"


def _refget_digest(seq: str) -> str:
    from ga4gh.core import sha512t24u  # confirm import path in the installed pkg
    return "SQ." + sha512t24u(seq.encode("ascii"))


class _MemoryProxy:
    """Minimal offline DataProxy: serves one synthetic contig, no network."""

    def __init__(self, seq: str) -> None:
        self._seq = seq
        self._sq = _refget_digest(seq)

    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        if identifier not in (self._sq, f"ga4gh:{self._sq}"):
            raise KeyError(identifier)
        return self._seq[start:end]

    def get_metadata(self, identifier: str) -> dict:
        if identifier not in (self._sq, f"ga4gh:{self._sq}"):
            raise KeyError(identifier)
        return {"length": len(self._seq), "aliases": [f"ga4gh:{self._sq}"], "alphabet": "ACGT"}


def test_vrs_identifies_an_snv_through_custom_proxy_offline() -> None:
    from ga4gh.core import ga4gh_identify
    from ga4gh.vrs.extras.translator import AlleleTranslator

    proxy = _MemoryProxy(_SEQ)
    sq = _refget_digest(_SEQ)
    tlr = AlleleTranslator(data_proxy=proxy)
    # SPDI: <seq>:<pos0>:<del>:<ins> — substitute base at 0-based position 5.
    allele = tlr.translate_from(f"ga4gh:{sq}:5:G:T", fmt="spdi")
    vid = ga4gh_identify(allele)
    assert vid.startswith("ga4gh:VA.")
    # Determinism: the same input yields the same id (the core guarantee).
    allele2 = tlr.translate_from(f"ga4gh:{sq}:5:G:T", fmt="spdi")
    assert ga4gh_identify(allele2) == vid
```

- [ ] **Step 3: Run the spike**

Run: `uv run pytest science/tests/test_commons_vrs_spike.py -v`
Expected: PASS. If `AlleleTranslator`/`translate_from`/`ga4gh_identify`/`sha512t24u` import paths differ in the installed version, adjust the test to the real surface (that *is* the spike's job) until it passes, then keep it.

- [ ] **Step 4: Add a normalization-property assertion**

Append a test proving fully-justified normalization is active (a left-shiftable indel normalizes to a canonical position, so two equivalent representations get the **same** id):

```python
def test_equivalent_indel_representations_share_one_id() -> None:
    from ga4gh.core import ga4gh_identify
    from ga4gh.vrs.extras.translator import AlleleTranslator

    # _SEQ has a CGTA tandem repeat region; deleting one 'A' is representable at
    # multiple positions but normalizes to one allele -> one id.
    proxy = _MemoryProxy(_SEQ)
    sq = _refget_digest(_SEQ)
    tlr = AlleleTranslator(data_proxy=proxy, normalize=True)
    a = ga4gh_identify(tlr.translate_from(f"ga4gh:{sq}:7:A:", fmt="spdi"))
    b = ga4gh_identify(tlr.translate_from(f"ga4gh:{sq}:11:A:", fmt="spdi"))
    assert a == b
```

Run: `uv run pytest science/tests/test_commons_vrs_spike.py -v`
Expected: PASS (if positions need adjusting for the synthetic sequence, adjust until the equivalence holds — the property, not the exact positions, is the point).

- [ ] **Step 5: Record the confirmed surface**

In the commit body, record the working import paths + class/method names (`AlleleTranslator(data_proxy=..., normalize=...)`, `translate_from(expr, fmt=...)`, `ga4gh_identify`, `sha512t24u`) and the exact pinned version. Task 5 mirrors exactly this.

- [ ] **Step 6: Commit (and record the decision branch)**

If the spike passed: proceed. If it could **not** be made to pass offline through a custom proxy, STOP and escalate — Task 5 then implements the fallback (local SPDI/HGVS_g/VCF parsers building VRS core `models.Allele` objects + `normalize()` + `ga4gh_identify`, bypassing the translator), and Tasks 8–9 call that instead. Record which path is taken.

```bash
git add science/tests/test_commons_vrs_spike.py uv.lock pyproject.toml
git commit -m "spike(c4a): VRS identify through custom offline DataProxy"
```

---

## Task 2: Promote `ga4gh.vrs` to a real dependency, pinned

**Files:**
- Modify: `science/pyproject.toml` (dependencies)
- Modify: `pyproject.toml` / `uv.lock` (workspace lock)

- [ ] **Step 1: Write a guard test that the dependency + version are present**

```python
# add to science/tests/test_commons_vrs_spike.py
def test_ga4gh_vrs_is_a_pinned_runtime_dependency() -> None:
    from importlib.metadata import version
    v = version("ga4gh.vrs")
    major, minor = (int(x) for x in v.split(".")[:2])
    assert (major, minor) >= (2, 3) and major < 3, f"unexpected ga4gh.vrs {v}"
```

- [ ] **Step 2: Run it to confirm it passes with the dev-added dep**

Run: `uv run pytest science/tests/test_commons_vrs_spike.py::test_ga4gh_vrs_is_a_pinned_runtime_dependency -v`
Expected: PASS (dep present from Task 1's `uv add --dev`).

- [ ] **Step 3: Move it from dev to a real runtime dependency**

Edit `science/src/science_tool`'s package config (`science/pyproject.toml`), adding to `[project].dependencies` the line `"ga4gh.vrs>=2.3,<3",` (exact resolved version stays pinned in `uv.lock`). Remove the dev-only entry added in Task 1.

Run: `uv sync && uv run python -c "import ga4gh.vrs; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Re-run the guard test**

Run: `uv run pytest science/tests/test_commons_vrs_spike.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/pyproject.toml pyproject.toml uv.lock
git commit -m "build(c4a): pin ga4gh.vrs (VRS 2.x) as a runtime dependency"
```

---

## Task 3: NCBI assembly-report parser → contig + alias rows (pure)

The alias columns (RefSeq/GenBank accession, UCSC name) are **not** in the seqcol level-2 record; they come from a pinned NCBI assembly report. This task is the pure parser only (no network except `fetch_text`).

**Files:**
- Create: `science/src/science_tool/commons/assembly_report_build.py`
- Test: `science/tests/test_commons_assembly_report_build.py`

- [ ] **Step 1: Write the failing test (with a 2-line assembly-report fixture)**

```python
# science/tests/test_commons_assembly_report_build.py
from __future__ import annotations

from science_tool.commons.assembly_report_build import parse_assembly_report

# Real NCBI assembly_report.txt format: '#'-comment header then tab-separated rows.
# Columns: Sequence-Name, Sequence-Role, Assigned-Molecule, ..., GenBank-Accn,
# Relationship, RefSeq-Accn, Assembly-Unit, Sequence-Length, UCSC-style-name
_REPORT = (
    "# Assembly name:  GRCh38\n"
    "# Sequence-Name\tSequence-Role\tAssigned-Molecule\tAssigned-Molecule-Location/Type\t"
    "GenBank-Accn\tRelationship\tRefSeq-Accn\tAssembly-Unit\tSequence-Length\tUCSC-style-name\n"
    "1\tassembled-molecule\t1\tChromosome\tCM000663.2\t=\tNC_000001.11\tPrimary Assembly\t248956422\tchr1\n"
    "MT\tassembled-molecule\tMT\tMitochondrion\tJ01415.2\t=\tNC_012920.1\tnon-nuclear\t16569\tchrM\n"
)


def test_parse_assembly_report_emits_alias_rows_per_kind() -> None:
    aliases = parse_assembly_report(_REPORT)
    chr1 = {(a["alias"], a["alias_kind"]) for a in aliases if a["sequence_name"] == "1"}
    assert chr1 == {
        ("1", "seqcol_name"),
        ("CM000663.2", "genbank_accession"),
        ("NC_000001.11", "refseq_accession"),
        ("chr1", "ucsc"),
    }
    nc = next(a for a in aliases if a["alias"] == "NC_000001.11")
    assert nc["sequence_accession"] == "NC_000001.11"
    assert nc["alias_kind"] == "refseq_accession"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/test_commons_assembly_report_build.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.assembly_report_build`.

- [ ] **Step 3: Implement the parser**

```python
# science/src/science_tool/commons/assembly_report_build.py
"""Pure parser for NCBI assembly_report.txt -> contig alias rows (Pillar C, C4a).

The seqcol level-2 record gives names/digests/lengths; the *aliases* (RefSeq /
GenBank accession, UCSC name) needed to resolve genomic-HGVS sequence accessions
and VCF CHROM labels come from the NCBI assembly report, joined on sequence name.
`fetch_text` is the only network call (build-time only). See
docs/plans/2026-05-28-c4-variant-identity-design.md (C4a-D1)."""
from __future__ import annotations

import csv
import io
from typing import Any

# Emit one alias row per (kind) so a single input string resolves to one contig.
_KINDS = (
    ("Sequence-Name", "seqcol_name"),
    ("GenBank-Accn", "genbank_accession"),
    ("RefSeq-Accn", "refseq_accession"),
    ("UCSC-style-name", "ucsc"),
)
_ACCESSION_KINDS = {"genbank_accession", "refseq_accession"}


def _header_index(report_text: str) -> tuple[list[str], list[str]]:
    """Return (column names, data lines). The column header is the LAST '#' line."""
    header: list[str] = []
    data: list[str] = []
    for line in report_text.splitlines():
        if line.startswith("#"):
            header = line.lstrip("#").strip().split("\t")
        elif line.strip():
            data.append(line)
    if not header:
        raise ValueError("assembly report has no '#'-prefixed column header line")
    return header, data


def parse_assembly_report(report_text: str) -> list[dict[str, Any]]:
    """Parse an NCBI assembly report into alias rows.

    Each row: {sequence_name, alias, alias_kind, sequence_accession}. A blank /
    'na' cell yields no row for that kind (no silent empty alias)."""
    header, data = _header_index(report_text)
    reader = csv.DictReader(io.StringIO("\n".join(data)), fieldnames=header, delimiter="\t")
    out: list[dict[str, Any]] = []
    for rec in reader:
        name = (rec.get("Sequence-Name") or "").strip()
        if not name:
            continue
        for column, kind in _KINDS:
            value = (rec.get(column) or "").strip()
            if not value or value.lower() == "na":
                continue
            out.append(
                {
                    "sequence_name": name,
                    "alias": value,
                    "alias_kind": kind,
                    "sequence_accession": value if kind in _ACCESSION_KINDS else "",
                }
            )
    return out


def fetch_text(url: str) -> str:
    """Fetch a text release file (build-time only; never called at resolve time)."""
    import httpx

    resp = httpx.get(url, timeout=60.0, follow_redirects=True)
    resp.raise_for_status()
    return resp.text
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest science/tests/test_commons_assembly_report_build.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/assembly_report_build.py science/tests/test_commons_assembly_report_build.py
git commit -m "feat(c4a): pure NCBI assembly-report parser for contig aliases"
```

---

## Task 4: Persist per-contig level-2 rows in the assembly-registry build

**Files:**
- Modify: `science/src/science_tool/commons/assembly_registry_build.py`
- Test: `science/tests/test_assembly_registry_build.py` (existing — add to it)

- [ ] **Step 1: Write the failing test**

```python
# add to science/tests/test_assembly_registry_build.py
def test_build_contig_rows_materializes_level2_with_ordinal() -> None:
    from science_tool.commons.assembly_registry_build import build_contig_rows

    level2 = {
        "names": ["1", "MT"],
        "lengths": [248956422, 16569],
        "sequences": ["SQ.aaa", "SQ.bbb"],
    }
    rows = build_contig_rows(level2=level2, seqcol_digest="DIGEST38")
    assert rows == [
        {"seqcol_digest": "DIGEST38", "sequence_index": 0, "name": "1", "refget_digest": "SQ.aaa", "length": 248956422},
        {"seqcol_digest": "DIGEST38", "sequence_index": 1, "name": "MT", "refget_digest": "SQ.bbb", "length": 16569},
    ]


def test_build_contig_rows_rejects_ragged_level2() -> None:
    import pytest
    from science_tool.commons.assembly_registry_build import build_contig_rows

    with pytest.raises(ValueError, match="ragged level-2"):
        build_contig_rows(level2={"names": ["1"], "lengths": [1, 2], "sequences": ["SQ.a", "SQ.b"]}, seqcol_digest="D")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/test_assembly_registry_build.py -k build_contig_rows -v`
Expected: FAIL — `ImportError: cannot import name 'build_contig_rows'`.

- [ ] **Step 3: Implement `build_contig_rows`**

Add to `science/src/science_tool/commons/assembly_registry_build.py`:

```python
def build_contig_rows(*, level2: dict[str, Any], seqcol_digest: str) -> list[dict[str, Any]]:
    """Materialize the seqcol level-2 record (names + per-contig SQ digests +
    lengths) into per-contig rows the refget proxy resolves through (C4a-D1).

    The seqcol digest already rolls up over exactly these attributes (C1); this
    persists what C1 fetches then discards. `sequence_index` makes names/lengths/
    sequences alignment auditable. A ragged level-2 record is a hard error."""
    names, lengths, sequences = level2["names"], level2["lengths"], level2["sequences"]
    if not (len(names) == len(lengths) == len(sequences)):
        raise ValueError(
            f"ragged level-2 record for {seqcol_digest!r}: "
            f"{len(names)} names / {len(lengths)} lengths / {len(sequences)} sequences"
        )
    return [
        {
            "seqcol_digest": seqcol_digest,
            "sequence_index": i,
            "name": names[i],
            "refget_digest": sequences[i],
            "length": lengths[i],
        }
        for i in range(len(names))
    ]
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest science/tests/test_assembly_registry_build.py -k build_contig_rows -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/assembly_registry_build.py science/tests/test_assembly_registry_build.py
git commit -m "feat(c4a): materialize seqcol level-2 contig rows in the registry build"
```

---

## Task 5: Contig + alias resolver (`contigs.py`)

Resolves an accepted input contig string (accession or label) to exactly one refget digest **within a declared assembly**, with explicit errors for ambiguity, unknown, and accession/assembly mismatch.

**Files:**
- Create: `science/src/science_tool/commons/contigs.py`
- Test: `science/tests/test_commons_contigs.py`
- Fixtures: `science/tests/fixtures/commons/assembly-registry/` (entity + datapackage) and `…/assembly-registry-data/` (`contigs.csv`, `contig_aliases.csv`)

- [ ] **Step 1: Create the fixtures**

Create `science/tests/fixtures/commons/assembly-registry-data/contigs.csv`:

```csv
seqcol_digest,sequence_index,name,refget_digest,length
DIGEST38,0,1,SQ.chr1_38,248956422
DIGEST37,0,1,SQ.chr1_37,249250621
```

Create `science/tests/fixtures/commons/assembly-registry-data/contig_aliases.csv`:

```csv
seqcol_digest,refget_digest,alias,alias_kind,sequence_accession
DIGEST38,SQ.chr1_38,1,seqcol_name,
DIGEST38,SQ.chr1_38,chr1,ucsc,
DIGEST38,SQ.chr1_38,NC_000001.11,refseq_accession,NC_000001.11
DIGEST37,SQ.chr1_37,1,seqcol_name,
DIGEST37,SQ.chr1_37,chr1,ucsc,
DIGEST37,SQ.chr1_37,NC_000001.10,refseq_accession,NC_000001.10
```

Create the commons entity + datapackage so `resolve()` finds these resources. `science/tests/fixtures/commons/assembly-registry/entity.md`:

```markdown
---
id: dataset:assembly-registry
type: dataset
schema_profile: science-entity-base/1.0+dataset/1.0
---
Assembly registry fixture (C4a contig/alias resources).
```

`science/tests/fixtures/commons/assembly-registry/datapackage.yaml` — compute the two hashes/bytes with `sha256sum` on the CSVs you just wrote and paste them (the resolver verifies them):

```yaml
name: assembly-registry
profile: data-package
title: "Assembly registry (C4a contig + alias fixture)"
version: "1.0.0"
resources:
  - name: contigs
    path: contigs.csv
    format: csv
    hash: "sha256:<sha256 of contigs.csv>"
    bytes: <byte length of contigs.csv>
  - name: contig_aliases
    path: contig_aliases.csv
    format: csv
    hash: "sha256:<sha256 of contig_aliases.csv>"
    bytes: <byte length of contig_aliases.csv>
```

Run to get the values: `sha256sum science/tests/fixtures/commons/assembly-registry-data/*.csv && wc -c science/tests/fixtures/commons/assembly-registry-data/*.csv`

- [ ] **Step 2: Write the failing test**

```python
# science/tests/test_commons_contigs.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.contigs import (
    AccessionAssemblyMismatch,
    AmbiguousContig,
    ContigError,
    ContigMatch,
    resolve_contig,
)

_FIX = Path(__file__).parent / "fixtures" / "commons" / "assembly-registry"
_DATA = Path(__file__).parent / "fixtures" / "commons" / "assembly-registry-data"


def _kw() -> dict:
    return {"commons_root": _FIX, "data_root": _DATA}


def test_resolve_by_refseq_accession() -> None:
    m = resolve_contig("NC_000001.11", seqcol_digest="DIGEST38", **_kw())
    assert isinstance(m, ContigMatch) and m.refget_digest == "SQ.chr1_38" and m.length == 248956422


def test_resolve_by_ucsc_and_bare_label() -> None:
    assert resolve_contig("chr1", seqcol_digest="DIGEST38", **_kw()).refget_digest == "SQ.chr1_38"
    assert resolve_contig("1", seqcol_digest="DIGEST38", **_kw()).refget_digest == "SQ.chr1_38"


def test_unknown_alias_is_error() -> None:
    with pytest.raises(ContigError, match="unknown contig"):
        resolve_contig("chrZ", seqcol_digest="DIGEST38", **_kw())


def test_accession_from_wrong_assembly_is_mismatch() -> None:
    # NC_000001.10 is the GRCh37 contig; declaring DIGEST38 must be caught here.
    m = resolve_contig("NC_000001.10", seqcol_digest="DIGEST38", **_kw())
    assert isinstance(m, AccessionAssemblyMismatch)
    assert m.found_seqcol_digest == "DIGEST37"


def test_alias_ambiguous_within_assembly_is_ambiguous(tmp_path: Path) -> None:
    # Build a data dir with a duplicate alias mapping to two contigs in one assembly.
    (tmp_path / "contigs.csv").write_text(
        "seqcol_digest,sequence_index,name,refget_digest,length\n"
        "D,0,1,SQ.a,10\nD,1,1_alt,SQ.b,10\n",
        encoding="utf-8",
    )
    (tmp_path / "contig_aliases.csv").write_text(
        "seqcol_digest,refget_digest,alias,alias_kind,sequence_accession\n"
        "D,SQ.a,dup,ucsc,\nD,SQ.b,dup,ucsc,\n",
        encoding="utf-8",
    )
    # Point resolve at a throwaway commons whose datapackage hashes match tmp files.
    # (Use the same fixture entity but override data_root; recompute hashes inline.)
    # Simpler: assert the pure parser raises on the duplicate (see Step 4 parser test).
    pytest.skip("ambiguity is covered by the pure-parser duplicate test in Step 4")
```

- [ ] **Step 3: Run it to verify it fails**

Run: `uv run pytest science/tests/test_commons_contigs.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.contigs`.

- [ ] **Step 4: Implement `contigs.py`**

```python
# science/src/science_tool/commons/contigs.py
"""Resolver over the registry's per-contig + alias resources (Pillar C, C4a-D1).

Resolves an accepted input contig string (RefSeq/GenBank accession, UCSC name, or
seqcol name) to exactly ONE refget digest WITHIN a declared assembly. Ambiguous,
unknown, and accession/assembly-mismatch inputs are explicit results — never a
silent pick (RCM-D6: never collapse distinct identities). Pure over pinned,
sha256-verified CSVs (no network)."""
from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_tool.commons.assembly import ASSEMBLY_REGISTRY_ID
from science_tool.commons.resolver import resolve

CONTIGS_RESOURCE = "contigs.csv"
ALIASES_RESOURCE = "contig_aliases.csv"
_ALIAS_KINDS = frozenset({"seqcol_name", "genbank_accession", "refseq_accession", "ucsc", "ensembl"})


class ContigError(ValueError):
    """A contig/alias row violates the collection contract, or an input cannot be
    resolved to exactly one contig (fail early; RCM-D1/D6)."""


@dataclass(frozen=True, slots=True)
class ContigMatch:
    """An input resolved to exactly one contig in the declared assembly."""

    refget_digest: str
    name: str
    length: int
    alias_kind: str


@dataclass(frozen=True, slots=True)
class AmbiguousContig:
    """An input matching >1 contig within the declared assembly. No refget_digest:
    the caller must not pick one."""

    query: str
    candidates: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AccessionAssemblyMismatch:
    """An accession that resolves to a contig in a DIFFERENT assembly than the one
    declared. Caught here, not downstream."""

    query: str
    found_seqcol_digest: str


ContigResolution = ContigMatch | AmbiguousContig | AccessionAssemblyMismatch


@dataclass(frozen=True, slots=True)
class _ContigRow:
    seqcol_digest: str
    name: str
    refget_digest: str
    length: int


@dataclass(frozen=True, slots=True)
class _AliasRow:
    seqcol_digest: str
    refget_digest: str
    alias: str
    alias_kind: str


def _parse_contig_rows(rows: Iterable[dict[str, Any]]) -> list[_ContigRow]:
    out: list[_ContigRow] = []
    seen_name: set[tuple[str, str]] = set()
    for i, row in enumerate(rows):
        digest = (row.get("seqcol_digest") or "").strip()
        rdigest = (row.get("refget_digest") or "").strip()
        name = (row.get("name") or "").strip()
        if not digest or not rdigest or not name:
            raise ContigError(f"contig row {i}: blank seqcol_digest/refget_digest/name")
        if (digest, name) in seen_name:
            raise ContigError(f"duplicate contig name {name!r} in assembly {digest!r}")
        seen_name.add((digest, name))
        out.append(_ContigRow(digest, name, rdigest, int(row["length"])))
    return out


def _parse_alias_rows(rows: Iterable[dict[str, Any]]) -> list[_AliasRow]:
    out: list[_AliasRow] = []
    seen: set[tuple[str, str]] = set()
    for i, row in enumerate(rows):
        digest = (row.get("seqcol_digest") or "").strip()
        rdigest = (row.get("refget_digest") or "").strip()
        alias = (row.get("alias") or "").strip()
        kind = (row.get("alias_kind") or "").strip()
        if not digest or not rdigest or not alias:
            raise ContigError(f"alias row {i}: blank seqcol_digest/refget_digest/alias")
        if kind not in _ALIAS_KINDS:
            raise ContigError(f"alias row {i}: invalid alias_kind {kind!r} (expected one of {sorted(_ALIAS_KINDS)})")
        if (digest, alias) in seen:
            raise ContigError(f"duplicate alias {alias!r} in assembly {digest!r}")
        seen.add((digest, alias))
        out.append(_AliasRow(digest, rdigest, alias, kind))
    return out


def _load(resource: str, parser, *, registry_id, commons_root, data_root):
    resolved = resolve(registry_id, resource, commons_root=commons_root, data_root=data_root)
    with resolved.path.open(encoding="utf-8", newline="") as fh:
        return parser(csv.DictReader(fh))


def resolve_contig(
    query: str,
    *,
    seqcol_digest: str,
    registry_id: str = ASSEMBLY_REGISTRY_ID,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> ContigResolution:
    """Resolve `query` to exactly one contig in assembly `seqcol_digest`.

    Returns ContigMatch (unique hit), AmbiguousContig (>1 in this assembly),
    AccessionAssemblyMismatch (resolves only in a DIFFERENT assembly), or raises
    ContigError for an entirely unknown alias."""
    aliases = _load(ALIASES_RESOURCE, _parse_alias_rows, registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    contigs = _load(CONTIGS_RESOURCE, _parse_contig_rows, registry_id=registry_id, commons_root=commons_root, data_root=data_root)
    by_key = {(c.seqcol_digest, c.refget_digest): c for c in contigs}

    in_assembly = [a for a in aliases if a.seqcol_digest == seqcol_digest and a.alias == query]
    if len(in_assembly) > 1:
        return AmbiguousContig(query, tuple(sorted(a.refget_digest for a in in_assembly)))
    if len(in_assembly) == 1:
        a = in_assembly[0]
        c = by_key[(a.seqcol_digest, a.refget_digest)]
        return ContigMatch(c.refget_digest, c.name, c.length, a.alias_kind)

    elsewhere = [a for a in aliases if a.alias == query]
    if elsewhere:
        return AccessionAssemblyMismatch(query, elsewhere[0].seqcol_digest)
    raise ContigError(f"unknown contig {query!r} in assembly {seqcol_digest!r}")
```

- [ ] **Step 5: Add the pure-parser duplicate tests**

```python
# add to science/tests/test_commons_contigs.py
def test_parser_rejects_duplicate_alias() -> None:
    from science_tool.commons.contigs import _parse_alias_rows

    with pytest.raises(ContigError, match="duplicate alias"):
        _parse_alias_rows([
            {"seqcol_digest": "D", "refget_digest": "SQ.a", "alias": "dup", "alias_kind": "ucsc", "sequence_accession": ""},
            {"seqcol_digest": "D", "refget_digest": "SQ.b", "alias": "dup", "alias_kind": "ucsc", "sequence_accession": ""},
        ])


def test_parser_rejects_duplicate_contig_name() -> None:
    from science_tool.commons.contigs import _parse_contig_rows

    with pytest.raises(ContigError, match="duplicate contig name"):
        _parse_contig_rows([
            {"seqcol_digest": "D", "sequence_index": 0, "name": "1", "refget_digest": "SQ.a", "length": 10},
            {"seqcol_digest": "D", "sequence_index": 1, "name": "1", "refget_digest": "SQ.b", "length": 10},
        ])
```

- [ ] **Step 6: Run all contig tests**

Run: `uv run pytest science/tests/test_commons_contigs.py -v`
Expected: PASS (the `test_alias_ambiguous…` test skips; duplicates covered by the parser tests).

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/commons/contigs.py science/tests/test_commons_contigs.py science/tests/fixtures/commons/assembly-registry science/tests/fixtures/commons/assembly-registry-data
git commit -m "feat(c4a): contig + alias resolver with mismatch/ambiguity errors"
```

---

## Task 6: Content-addressed sequence store reader (`sequence_store.py`)

Per-contig files named by refget digest, verified once on open (never re-hashed per substring; never routed through `resolve()`'s whole-file sha256). Fails loud on a missing contig.

**Files:**
- Create: `science/src/science_tool/commons/sequence_store.py`
- Test: `science/tests/test_commons_sequence_store.py`
- Fixture: `science/tests/fixtures/commons/seqstore/` (one synthetic contig file)

- [ ] **Step 1: Write the failing test (it builds its own tiny store)**

```python
# science/tests/test_commons_sequence_store.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.sequence_store import SequenceStoreError, refget_digest, open_store

_SEQ = "ACGTACGTACGTACGTTTTTGGGGCCCC"


def _make_store(tmp_path: Path, seq: str) -> tuple[Path, str]:
    digest = refget_digest(seq)
    (tmp_path / digest).write_text(seq, encoding="ascii")
    return tmp_path, digest


def test_full_and_sliced_reads(tmp_path: Path) -> None:
    root, digest = _make_store(tmp_path, _SEQ)
    store = open_store(root)
    assert store.sequence(digest) == _SEQ
    assert store.sequence(digest, 0, 4) == "ACGT"
    assert store.sequence(digest, 16, 20) == "TTTT"


def test_missing_contig_fails_loud(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    with pytest.raises(SequenceStoreError, match="not in sequence store"):
        store.sequence("SQ.does_not_exist", 0, 4)


def test_corrupt_contig_fails_verification(tmp_path: Path) -> None:
    root, digest = _make_store(tmp_path, _SEQ)
    (root / digest).write_text("CORRUPTEDSEQUENCE", encoding="ascii")  # bytes != digest
    store = open_store(root)
    with pytest.raises(SequenceStoreError, match="refget digest mismatch"):
        store.sequence(digest, 0, 4)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/test_commons_sequence_store.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.sequence_store`.

- [ ] **Step 3: Implement `sequence_store.py`**

```python
# science/src/science_tool/commons/sequence_store.py
"""Content-addressed per-contig reference-sequence reader (Pillar C, C4a-D3).

A flat store: one file per contig, named by its refget digest (SQ.<sha512t24u>).
A contig is verified ONCE on first read (its bytes must reproduce its digest),
then cached — it is never routed through the commons `resolve()` whole-file
sha256 (that would re-hash gigabytes per substring). The bytes are materialized
locally (digests are the committed authority); a missing contig fails loud and
NEVER triggers a fetch."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class SequenceStoreError(LookupError):
    """A requested contig is absent, or its bytes do not match its refget digest."""


def refget_digest(seq: str) -> str:
    """The GA4GH refget digest 'SQ.<sha512t24u>' of an (upper-case) sequence."""
    from ga4gh.core import sha512t24u  # import path confirmed by the Task 1 spike

    return "SQ." + sha512t24u(seq.upper().encode("ascii"))


@dataclass
class SequenceStore:
    root: Path
    _verified: set[str] = field(default_factory=set)

    def _path(self, digest: str) -> Path:
        return self.root / digest

    def sequence(self, digest: str, start: int | None = None, end: int | None = None) -> str:
        path = self._path(digest)
        if not path.is_file():
            raise SequenceStoreError(f"contig {digest!r} not in sequence store at {self.root}")
        seq = path.read_text(encoding="ascii")
        if digest not in self._verified:
            actual = refget_digest(seq)
            if actual != digest:
                raise SequenceStoreError(f"refget digest mismatch for {digest!r}: bytes hash to {actual!r}")
            self._verified.add(digest)
        return seq[start:end]


def open_store(root: Path) -> SequenceStore:
    """Open the flat refget store rooted at `root`. No I/O until a contig is read."""
    return SequenceStore(root=Path(root))
```

> Note: this reads whole-contig text for simplicity and correctness; a later optimization may `mmap`/offset-slice without changing this interface. The verify-once contract and fail-loud behavior are the invariants under test.

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest science/tests/test_commons_sequence_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/sequence_store.py science/tests/test_commons_sequence_store.py
git commit -m "feat(c4a): content-addressed sequence store, verify-once + fail-loud"
```

---

## Task 7: Offline refget `DataProxy` (`refget_proxy.py`)

**Files:**
- Create: `science/src/science_tool/commons/refget_proxy.py`
- Test: `science/tests/test_commons_refget_proxy.py`

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_commons_refget_proxy.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.refget_proxy import RefgetProxy
from science_tool.commons.sequence_store import open_store, refget_digest

_SEQ = "ACGTACGTACGTACGTTTTTGGGGCCCC"


def _proxy(tmp_path: Path) -> tuple[RefgetProxy, str]:
    digest = refget_digest(_SEQ)
    (tmp_path / digest).write_text(_SEQ, encoding="ascii")
    return RefgetProxy(store=open_store(tmp_path)), digest


def test_get_sequence_by_ga4gh_and_bare_digest(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    assert proxy.get_sequence(f"ga4gh:{digest}", 0, 4) == "ACGT"
    assert proxy.get_sequence(digest, 0, 4) == "ACGT"


def test_get_metadata_exposes_ga4gh_alias_and_length(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    meta = proxy.get_metadata(f"ga4gh:{digest}")
    assert meta["length"] == len(_SEQ)
    assert f"ga4gh:{digest}" in meta["aliases"]


def test_missing_identifier_fails_loud_no_network(tmp_path: Path) -> None:
    proxy = RefgetProxy(store=open_store(tmp_path))
    with pytest.raises(LookupError):
        proxy.get_sequence("ga4gh:SQ.absent", 0, 1)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/test_commons_refget_proxy.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.refget_proxy`.

- [ ] **Step 3: Implement `refget_proxy.py`**

```python
# science/src/science_tool/commons/refget_proxy.py
"""An offline ga4gh.vrs DataProxy over the local sequence store (Pillar C, C4a-D4).

Implements the two-method DataProxy contract (get_sequence + get_metadata) the
VRS translator/normalizer needs, serving bytes from the content-addressed store.
Identifiers are refget digests ('SQ.<...>' or 'ga4gh:SQ.<...>'). Pure + offline:
a missing contig raises (never fetches). The metadata `aliases` advertise the
ga4gh sequence id so the translator can anchor a VRS Location to it."""
from __future__ import annotations

from dataclasses import dataclass

from science_tool.commons.sequence_store import SequenceStore


def _bare(identifier: str) -> str:
    return identifier[len("ga4gh:") :] if identifier.startswith("ga4gh:") else identifier


@dataclass
class RefgetProxy:
    store: SequenceStore

    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str:
        return self.store.sequence(_bare(identifier), start, end)

    def get_metadata(self, identifier: str) -> dict:
        digest = _bare(identifier)
        seq = self.store.sequence(digest)  # raises if absent (fail loud, no network)
        return {"length": len(seq), "aliases": [f"ga4gh:{digest}"], "alphabet": "ACGT", "added": None}
```

> If the Task 1 spike showed the translator needs an additional DataProxy method or a richer `aliases` list (e.g. `translate_sequence_identifier`), add the minimal method here to match the spike's confirmed surface — the spike test is the contract.

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest science/tests/test_commons_refget_proxy.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/refget_proxy.py science/tests/test_commons_refget_proxy.py
git commit -m "feat(c4a): offline ga4gh.vrs DataProxy over the sequence store"
```

---

## Task 8: VRS boundary (`vrs.py`) + SPDI minting

Isolate every `ga4gh.vrs` call behind one stable function, then mint from SPDI (the simplest input — it carries the sequence id directly).

**Files:**
- Create: `science/src/science_tool/commons/vrs.py`
- Test: `science/tests/test_commons_variant.py`

- [ ] **Step 1: Write the failing test (property + captured golden)**

```python
# science/tests/test_commons_variant.py
from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("ga4gh.vrs")

from science_tool.commons.refget_proxy import RefgetProxy
from science_tool.commons.sequence_store import open_store, refget_digest
from science_tool.commons.vrs import compute_vrs_id

_SEQ = "CGTACGTACGTACGTACGTACGTACGTACGTACGTACGTA"


def _proxy(tmp_path: Path) -> tuple[RefgetProxy, str]:
    digest = refget_digest(_SEQ)
    (tmp_path / digest).write_text(_SEQ, encoding="ascii")
    return RefgetProxy(store=open_store(tmp_path)), digest


def test_compute_vrs_id_from_spdi_is_deterministic(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    expr = f"ga4gh:{digest}:5:G:T"
    vid = compute_vrs_id(proxy, fmt="spdi", expr=expr)
    assert vid.startswith("ga4gh:VA.")
    assert compute_vrs_id(proxy, fmt="spdi", expr=expr) == vid  # reproducible
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/test_commons_variant.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.vrs`.

- [ ] **Step 3: Implement `vrs.py` (mirror the Task 1 spike's confirmed surface)**

```python
# science/src/science_tool/commons/vrs.py
"""The single ga4gh.vrs boundary (Pillar C, C4a-D5).

Every ga4gh.vrs import lives here so the rest of the codebase depends only on our
stable signature. `compute_vrs_id` normalizes (fully-justified) and returns the
computed VRS identifier. The exact ga4gh.vrs surface (AlleleTranslator.translate_from
+ ga4gh_identify) is the one the Task 1 spike confirmed against the pinned version."""
from __future__ import annotations

from typing import Any, Protocol

_ACCEPTED_FMTS = frozenset({"spdi", "hgvs", "gnomad"})


class _Proxy(Protocol):
    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str: ...
    def get_metadata(self, identifier: str) -> dict: ...


def _translator(proxy: _Proxy) -> Any:
    from ga4gh.vrs.extras.translator import AlleleTranslator

    return AlleleTranslator(data_proxy=proxy, normalize=True)


def compute_vrs_id(proxy: _Proxy, *, fmt: str, expr: str) -> str:
    """Return 'ga4gh:VA.<digest>' for `expr` in `fmt` (spdi | hgvs | gnomad).

    `hgvs` is genomic HGVS only (transcript/protein HGVS is C4c). `gnomad` is the
    VCF 'chrom-pos-ref-alt' string form. Raises ValueError on an unaccepted fmt."""
    from ga4gh.core import ga4gh_identify

    if fmt not in _ACCEPTED_FMTS:
        raise ValueError(f"unsupported variant fmt {fmt!r}; expected one of {sorted(_ACCEPTED_FMTS)}")
    allele = _translator(proxy).translate_from(expr, fmt=fmt)
    return ga4gh_identify(allele)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest science/tests/test_commons_variant.py -v`
Expected: PASS. (If the spike recorded a different surface, mirror that surface here.)

- [ ] **Step 5: Add the captured-golden + assembly-anchoring tests**

Run a throwaway to capture the id, then pin it:

```python
# add to science/tests/test_commons_variant.py
# GOLDEN: captured once from compute_vrs_id(... ) against the pinned ga4gh.vrs;
# regenerate + re-review only on a deliberate version bump (Task 2 pin).
_GOLDEN_SNV = "<paste the printed ga4gh:VA... here>"


def test_spdi_snv_matches_pinned_golden(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    assert compute_vrs_id(proxy, fmt="spdi", expr=f"ga4gh:{digest}:5:G:T") == _GOLDEN_SNV


def test_same_change_on_a_different_sequence_is_a_different_id(tmp_path: Path) -> None:
    # Assembly-anchoring: a different reference sequence -> a different VRS id.
    other = "TTTTCGTACGTACGTACGTACGTACGTACGTACGTACGTA"
    od = refget_digest(other)
    (tmp_path / od).write_text(other, encoding="ascii")
    proxy = RefgetProxy(store=open_store(tmp_path))
    base, _ = _proxy(tmp_path)
    a = compute_vrs_id(base, fmt="spdi", expr=f"ga4gh:{refget_digest(_SEQ)}:5:G:T")
    b = compute_vrs_id(proxy, fmt="spdi", expr=f"ga4gh:{od}:5:G:T")
    assert a != b
```

Capture command: `uv run python -c "from pathlib import Path; import tempfile; from science_tool.commons.sequence_store import open_store, refget_digest; from science_tool.commons.refget_proxy import RefgetProxy; from science_tool.commons.vrs import compute_vrs_id; d=Path(tempfile.mkdtemp()); s='CGTACGTACGTACGTACGTACGTACGTACGTACGTACGTA'; g=refget_digest(s); (d/g).write_text(s); print(compute_vrs_id(RefgetProxy(store=open_store(d)), fmt='spdi', expr=f'ga4gh:{g}:5:G:T'))"`
Paste the printed value into `_GOLDEN_SNV`.

Run: `uv run pytest science/tests/test_commons_variant.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/vrs.py science/tests/test_commons_variant.py
git commit -m "feat(c4a): VRS boundary + SPDI minting (deterministic, assembly-anchored)"
```

---

## Task 9: Public variant resolver (`variant.py`) — HGVS_g, VCF, and flags

`vrs_id()` resolves the contig via Task 5, validates the input is an accepted small allele, mints via Task 8, and returns a typed result that flags (never silently drops) every rejection path.

**Files:**
- Create: `science/src/science_tool/commons/variant.py`
- Test: extend `science/tests/test_commons_variant.py`

- [ ] **Step 1: Write the failing tests (success + each flag)**

```python
# add to science/tests/test_commons_variant.py
from science_tool.commons.contigs import resolve_contig  # noqa: E402  (used via monkeypatch helper)


def test_vrs_id_from_vcf_against_declared_assembly(monkeypatch, tmp_path: Path) -> None:
    from science_tool.commons import variant as V

    proxy, digest = _proxy(tmp_path)
    # Stub contig resolution: VCF CHROM '1' -> our synthetic contig.
    from science_tool.commons.contigs import ContigMatch
    monkeypatch.setattr(V, "_resolve_contig", lambda q, **k: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))
    monkeypatch.setattr(V, "_open_proxy", lambda **k: proxy)
    m = V.vrs_id("1-6-G-T", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)
    assert isinstance(m, V.VariantMatch) and m.vrs_id.startswith("ga4gh:VA.")


def test_ref_mismatch_is_flagged(monkeypatch, tmp_path: Path) -> None:
    from science_tool.commons import variant as V
    from science_tool.commons.contigs import ContigMatch

    proxy, digest = _proxy(tmp_path)
    monkeypatch.setattr(V, "_resolve_contig", lambda q, **k: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))
    monkeypatch.setattr(V, "_open_proxy", lambda **k: proxy)
    # position 6 (1-based) is 'G' in _SEQ; claim REF 'A' -> mismatch.
    m = V.vrs_id("1-6-A-T", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)
    assert isinstance(m, V.VariantDefect) and m.reason == "ref-mismatch"


def test_symbolic_allele_rejected(tmp_path: Path) -> None:
    from science_tool.commons import variant as V

    m = V.vrs_id("1-6-G-<DEL>", fmt="vcf", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)
    assert isinstance(m, V.VariantDefect) and m.reason == "unsupported-allele"


def test_accession_assembly_mismatch_flagged(monkeypatch, tmp_path: Path) -> None:
    from science_tool.commons import variant as V
    from science_tool.commons.contigs import AccessionAssemblyMismatch

    monkeypatch.setattr(V, "_resolve_contig", lambda q, **k: AccessionAssemblyMismatch(q, "DIGEST37"))
    m = V.vrs_id("NC_000001.10:5:G:T", fmt="spdi", assembly_seqcol="DIGEST38", commons_root=tmp_path, data_root=tmp_path)
    assert isinstance(m, V.VariantDefect) and m.reason == "accession-assembly-mismatch"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/test_commons_variant.py -k "vcf or mismatch or symbolic" -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.variant`.

- [ ] **Step 3: Implement `variant.py`**

```python
# science/src/science_tool/commons/variant.py
"""Public variant-identity resolver (Pillar C, C4a-D5/D6).

vrs_id(expr, fmt, assembly_seqcol) parses an accepted small-allele expression
(SPDI / genomic-HGVS / VCF chrom-pos-ref-alt), resolves its contig within the
declared assembly (Task 5), validates the reference base, and mints the VRS id
(Task 8). Every rejection is a typed VariantDefect (flagged, never dropped):
unsupported-allele, accession-assembly-mismatch, ambiguous-contig, unknown-contig,
ref-mismatch, out-of-bounds."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.commons.contigs import (
    AccessionAssemblyMismatch,
    AmbiguousContig,
    ContigError,
    ContigMatch,
    resolve_contig as _resolve_contig,
)
from science_tool.commons.refget_proxy import RefgetProxy
from science_tool.commons.sequence_store import open_store
from science_tool.commons.vrs import compute_vrs_id

_SYMBOLIC = ("<", "[", "]", ".")  # symbolic alleles / breakends / missing


@dataclass(frozen=True, slots=True)
class VariantMatch:
    vrs_id: str
    refget_digest: str


@dataclass(frozen=True, slots=True)
class VariantDefect:
    query: str
    reason: str  # unsupported-allele | accession-assembly-mismatch | ambiguous-contig
    #              | unknown-contig | ref-mismatch | out-of-bounds
    detail: str


def _open_proxy(*, commons_root: Path | None, data_root: Path | None) -> RefgetProxy:
    from science_tool.commons.config import resolve_commons_data_root

    root = data_root if data_root is not None else resolve_commons_data_root()
    # The sequence store is a sibling dataset slug under the data root.
    return RefgetProxy(store=open_store(Path(root) / "sequence-store-grch38-grch37"))


def _parse(expr: str, fmt: str) -> tuple[str, int, str, str] | None:
    """Return (contig_query, pos0, ref, alt) for an accepted small allele, else None.

    pos0 is 0-based. SPDI is already 0-based; VCF is 1-based -> pos0 = pos-1.
    HGVS_g (g.<pos><ref>><alt>) is normalized by the translator, so we only pre-
    validate it is not symbolic and pass it through with pos/ref unknown (-1, '')."""
    if any(tok in expr for tok in _SYMBOLIC):
        return None
    if fmt == "spdi":
        seq, pos, ref, alt = expr.split(":")
        return seq, int(pos), ref, alt
    if fmt == "vcf":
        chrom, pos, ref, alt = expr.split("-")
        if "," in alt:  # multiallelic must be pre-split (one ALT per row)
            return None
        return chrom, int(pos) - 1, ref, alt
    if fmt == "hgvs":
        contig = expr.split(":", 1)[0]
        return contig, -1, "", ""  # ref validated by the proxy during translation
    return None


def vrs_id(
    expr: str,
    *,
    fmt: str,
    assembly_seqcol: str,
    commons_root: Path | None = None,
    data_root: Path | None = None,
) -> VariantMatch | VariantDefect:
    parsed = _parse(expr, fmt)
    if parsed is None:
        return VariantDefect(expr, "unsupported-allele", f"{fmt} expr is symbolic/imprecise/multiallelic or malformed")
    contig_query, pos0, ref, _alt = parsed

    try:
        resolution = _resolve_contig(contig_query, seqcol_digest=assembly_seqcol, commons_root=commons_root, data_root=data_root)
    except ContigError as exc:
        return VariantDefect(expr, "unknown-contig", str(exc))
    if isinstance(resolution, AmbiguousContig):
        return VariantDefect(expr, "ambiguous-contig", f"{contig_query} -> {resolution.candidates}")
    if isinstance(resolution, AccessionAssemblyMismatch):
        return VariantDefect(expr, "accession-assembly-mismatch", f"resolves only in {resolution.found_seqcol_digest}")
    assert isinstance(resolution, ContigMatch)

    proxy = _open_proxy(commons_root=commons_root, data_root=data_root)

    # For SPDI/VCF we know the asserted REF; validate it against the pinned bytes
    # and bounds BEFORE minting (HGVS_g defers to the translator's own check).
    if fmt in ("spdi", "vcf") and ref:
        if pos0 < 0 or pos0 + len(ref) > resolution.length:
            return VariantDefect(expr, "out-of-bounds", f"pos {pos0}+{len(ref)} exceeds contig length {resolution.length}")
        actual = proxy.get_sequence(resolution.refget_digest, pos0, pos0 + len(ref))
        if actual.upper() != ref.upper():
            return VariantDefect(expr, "ref-mismatch", f"declared REF {ref!r} != reference {actual!r}")

    # Re-express against the contig's ga4gh sequence id so the VRS id is anchored
    # to the pinned assembly sequence regardless of the input's contig label.
    sq = f"ga4gh:{resolution.refget_digest}"
    if fmt == "spdi":
        mint_expr, mint_fmt = f"{sq}:{pos0}:{ref}:{_alt}", "spdi"
    elif fmt == "vcf":
        mint_expr, mint_fmt = f"{sq}:{pos0}:{ref}:{_alt}", "spdi"  # normalize VCF via SPDI form
    else:  # hgvs_g — swap the input accession for the ga4gh sequence id
        mint_expr, mint_fmt = expr.replace(contig_query, sq, 1), "hgvs"

    minted = compute_vrs_id(proxy, fmt=mint_fmt, expr=mint_expr)
    return VariantMatch(vrs_id=minted, refget_digest=resolution.refget_digest)
```

> If the Task 1 spike showed `translate_from` cannot take a `ga4gh:SQ.*` sequence id in an HGVS string, keep VCF/SPDI (which can) and mark HGVS_g rows as `unsupported-allele` with reason `hgvs-needs-accession`, deferring HGVS_g anchoring refinement — record this in the commit. SPDI + VCF are the required C4a coverage; HGVS_g is best-effort.

- [ ] **Step 4: Run the variant tests**

Run: `uv run pytest science/tests/test_commons_variant.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/variant.py science/tests/test_commons_variant.py
git commit -m "feat(c4a): vrs_id resolver — VCF/SPDI/HGVS_g inputs, typed defect flags"
```

---

## Task 10: Factor the shared declaration-shape validator

The variant declaration layer must reuse the small, registry-agnostic shape check — not the crosswalk-shaped `evaluate_tier_identity`. Make the shape validator public.

**Files:**
- Modify: `science/src/science_tool/validate/checks/identity_context.py`
- Test: `science/tests/validate/test_checks_identity_context.py` (add)

- [ ] **Step 1: Write the failing test**

```python
# add to science/tests/validate/test_checks_identity_context.py
def test_tier_declaration_defect_is_public_and_registry_agnostic() -> None:
    from science_tool.validate.checks.identity_context import tier_declaration_defect

    assert tier_declaration_defect({"namespace": "vrs"}) is None
    assert tier_declaration_defect({"namespace": ""}) == "missing or blank namespace"
    assert tier_declaration_defect({"namespace": "vrs", "registry": "x"}) == "registry must be a 'dataset:' reference"
    assert tier_declaration_defect({"namespace": "vrs", "resolution_status": "maybe"}) == (
        "resolution_status must be 'resolved' or 'declared_unresolved'"
    )
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/validate/test_checks_identity_context.py -k tier_declaration_defect -v`
Expected: FAIL — `ImportError: cannot import name 'tier_declaration_defect'`.

- [ ] **Step 3: Rename `_tier_defect` → `tier_declaration_defect`**

In `science/src/science_tool/validate/checks/identity_context.py`, rename the function `_tier_defect` to `tier_declaration_defect` (public) and update its two internal call sites (`evaluate_tier_identity` body and `_run_tier_check`). Keep the docstring; it is now the shared, registry-agnostic shape validator both the crosswalk tiers and the variant tier call.

- [ ] **Step 4: Run the full identity-context test file (no regressions)**

Run: `uv run pytest science/tests/validate/test_checks_identity_context.py -v`
Expected: PASS (all existing tests + the new one).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/identity_context.py science/tests/validate/test_checks_identity_context.py
git commit -m "refactor(c4a): make tier_declaration_defect a public shared shape validator"
```

---

## Task 11: Variant-identity check (two layers, order 33)

**Files:**
- Create: `science/src/science_tool/validate/checks/variant_identity.py`
- Test: `science/tests/validate/test_checks_variant_identity.py`

- [ ] **Step 1: Write the failing test (pure evaluators, synthetic frontmatter)**

```python
# science/tests/validate/test_checks_variant_identity.py
from __future__ import annotations

from science_tool.validate.checks.variant_identity import evaluate_variant_declaration
from science_tool.validate.result import Severity

_PROFILE = "science-entity-base/1.0+dataset/1.0+bio.table/1.0+bio.identity_context/1.0"


def _ds(variant: dict | None, **fm) -> dict:
    idc = {"taxon": 9606}
    if variant is not None:
        idc["molecular_ids"] = {"variant": variant}
    return {"type": "dataset", "id": "dataset:v", "schema_profile": _PROFILE, "_path": "data/v/entity.md", "identity_context": idc, **fm}


def _locator() -> dict:
    return {"resource": "variants.csv", "format": "spdi", "column": "variant"}


def test_wellformed_vrs_declaration_passes_silently() -> None:
    ds = _ds({"namespace": "vrs", "canonical": True, "resolution_status": "resolved", "locator": _locator()})
    assert list(evaluate_variant_declaration([ds])) == []


def test_wrong_namespace_errors() -> None:
    ds = _ds({"namespace": "spdi", "locator": _locator()})
    rules = [r.rule for r in evaluate_variant_declaration([ds]) if r.severity is Severity.ERROR]
    assert "identity.variant-namespace-unsupported" in rules


def test_missing_locator_errors() -> None:
    ds = _ds({"namespace": "vrs"})
    rules = [r.rule for r in evaluate_variant_declaration([ds]) if r.severity is Severity.ERROR]
    assert "identity.variant-locator-malformed" in rules


def test_vcf_locator_requires_columns_map() -> None:
    ds = _ds({"namespace": "vrs", "locator": {"resource": "v.csv", "format": "vcf", "column": "x"}})
    rules = [r.rule for r in evaluate_variant_declaration([ds]) if r.severity is Severity.ERROR]
    assert "identity.variant-locator-malformed" in rules


def test_declared_unresolved_is_info_not_error() -> None:
    ds = _ds({"namespace": "vrs", "resolution_status": "declared_unresolved"})
    results = list(evaluate_variant_declaration([ds]))
    assert not [r for r in results if r.severity is Severity.ERROR]
    assert [r for r in results if r.rule == "identity.variant-declared-unresolved"]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/validate/test_checks_variant_identity.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.validate.checks.variant_identity`.

- [ ] **Step 3: Implement the declaration layer + check wrapper**

```python
# science/src/science_tool/validate/checks/variant_identity.py
"""Variant-tier identity check (Pillar C, C4a-D6; section 'variant identity', order 33).

Two layers. Layer 1 (here-implemented declaration check): the variant tier names
namespace 'vrs', a valid resolution_status, and a well-formed `locator` (the
convention that says WHERE the variant expressions live, since the bare tier flag
cannot drive row minting). Reuses the shared `tier_declaration_defect`; it does
NOT use the crosswalk-shaped `evaluate_tier_identity` (the variant tier has no
registry in C4a). Layer 2 (row minting) opens the located CSV/TSV resource via the
dataset datapackage and mints each row through `commons.variant.vrs_id`, reporting
outcome counts. Raw frontmatter is read via `dataset_frontmatters` (mirrors the
assembly/gene/protein checks)."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.checks.identity_context import tier_declaration_defect
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_SUPPORTED = frozenset({"vrs"})
_FORMATS = frozenset({"spdi", "hgvs", "vcf"})


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _variant_decl(fm: dict[str, Any]) -> Any:
    idc = fm.get("identity_context")
    mids = idc.get("molecular_ids") if isinstance(idc, dict) else None
    return mids.get("variant") if isinstance(mids, dict) else None


def _locator_defect(locator: Any) -> str | None:
    if not isinstance(locator, dict):
        return "missing or non-object locator"
    if not isinstance(locator.get("resource"), str) or not locator["resource"].strip():
        return "locator.resource (a datapackage resource name) is required"
    fmt = locator.get("format")
    if fmt not in _FORMATS:
        return f"locator.format must be one of {sorted(_FORMATS)}"
    if fmt == "vcf":
        cols = locator.get("columns")
        if not isinstance(cols, dict) or not {"chrom", "pos", "ref", "alt"} <= set(cols):
            return "vcf locator requires columns: {chrom, pos, ref, alt}"
    else:
        if not isinstance(locator.get("column"), str) or not locator["column"].strip():
            return f"{fmt} locator requires a single 'column'"
    return None


def evaluate_variant_declaration(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Layer 1: validate the variant-tier declaration shape + namespace + locator."""
    for fm in datasets:
        if fm.get("type") != "dataset":
            continue
        decl = _variant_decl(fm)
        if decl is None:
            continue
        path, ident, loc = fm.get("_path"), fm.get("id", "?"), "identity_context.molecular_ids.variant"
        if not isinstance(decl, dict):
            yield _result(Severity.ERROR, path, f"{ident}: {loc} must be an object", "identity.variant-malformed")
            continue
        defect = tier_declaration_defect(decl)
        if defect is not None:
            yield _result(Severity.ERROR, path, f"{ident}: malformed {loc} -- {defect}", "identity.variant-malformed")
            continue
        if str(decl["namespace"]) not in _SUPPORTED:
            yield _result(
                Severity.ERROR, path,
                f"{ident}: variant namespace {decl['namespace']!r} is not supported (expected 'vrs')",
                "identity.variant-namespace-unsupported",
            )
            continue
        if decl.get("resolution_status") == "declared_unresolved":
            yield _result(
                Severity.INFO, path,
                f"{ident}: variant identity declared_unresolved (honored; rows not minted)",
                "identity.variant-declared-unresolved",
            )
            continue
        locator_defect = _locator_defect(decl.get("locator"))
        if locator_defect is not None:
            yield _result(
                Severity.ERROR, path, f"{ident}: {loc}.locator -- {locator_defect}",
                "identity.variant-locator-malformed",
            )


@Check(section="variant identity", order=33)
def check_variant_identity(ctx: ValidateContext) -> Iterator[Result]:
    datasets = dataset_frontmatters(ctx)
    yield from evaluate_variant_declaration(datasets)
    yield from _evaluate_variant_rows(ctx, datasets)
```

- [ ] **Step 4: Run the declaration-layer tests**

Run: `uv run pytest science/tests/validate/test_checks_variant_identity.py -v`
Expected: PASS.

- [ ] **Step 5: Add the row layer + its test**

Add the row-minting fixture dataset under `science/tests/fixtures/` and a test that a 2-row `variants.csv` (one good SPDI, one ref-mismatch) yields a minted count of 1 and a defect count of 1. Implement `_evaluate_variant_rows` in `variant_identity.py`:

```python
def _evaluate_variant_rows(ctx: ValidateContext, datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Layer 2: for each well-declared, resolved variant tier, open the located
    CSV/TSV resource (relative to the dataset directory / its datapackage) and mint
    each row, reporting outcome counts. CSV/TSV only (no parquet dependency)."""
    import csv

    from science_tool.commons.variant import VariantDefect, VariantMatch, vrs_id

    for fm in datasets:
        decl = _variant_decl(fm)
        if not isinstance(decl, dict) or str(decl.get("namespace")) not in _SUPPORTED:
            continue
        if decl.get("resolution_status") == "declared_unresolved":
            continue
        locator = decl.get("locator")
        if _locator_defect(locator) is not None:
            continue  # already errored in layer 1
        assembly = (fm.get("identity_context") or {}).get("assembly") or {}
        seqcol = assembly.get("seqcol_digest")
        path, ident = fm.get("_path"), fm.get("id", "?")
        if not isinstance(seqcol, str) or not seqcol:
            yield _result(Severity.ERROR, path, f"{ident}: variant rows need identity_context.assembly.seqcol_digest", "identity.variant-no-assembly")
            continue
        resource = Path(str(path)).parent / locator["resource"] if path else None
        if resource is None or not resource.is_file():
            yield _result(Severity.INFO, path, f"{ident}: variant resource {locator['resource']!r} not found locally; rows not minted", "identity.variant-resource-unavailable")
            continue
        fmt = locator["format"]
        minted = 0
        defects: dict[str, int] = {}
        delimiter = "\t" if resource.suffix == ".tsv" else ","
        with resource.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter=delimiter):
                expr = _row_expr(row, locator, fmt)
                result = vrs_id(expr, fmt=fmt, assembly_seqcol=seqcol)
                if isinstance(result, VariantMatch):
                    minted += 1
                else:
                    defects[result.reason] = defects.get(result.reason, 0) + 1
        if defects:
            summary = ", ".join(f"{k}={v}" for k, v in sorted(defects.items()))
            yield _result(Severity.ERROR, path, f"{ident}: minted {minted}, unresolved variant rows: {summary}", "identity.variant-rows-unresolved")
        else:
            yield _result(Severity.INFO, path, f"{ident}: minted {minted} variant rows", "identity.variant-rows-minted")


def _row_expr(row: dict[str, Any], locator: dict[str, Any], fmt: str) -> str:
    if fmt == "vcf":
        c = locator["columns"]
        return f"{row[c['chrom']]}-{row[c['pos']]}-{row[c['ref']]}-{row[c['alt']]}"
    return row[locator["column"]]
```

Write `_row_expr`-driven fixture + test, run:

Run: `uv run pytest science/tests/validate/test_checks_variant_identity.py -v`
Expected: PASS (minted=1, one `ref-mismatch` defect → `identity.variant-rows-unresolved`).

- [ ] **Step 6: Verify the check registers at the right order with no collision**

Run: `uv run python -c "from science_tool.validate.checks import variant_identity; print('ok')" && uv run pytest science/tests/validate/ -q`
Expected: `ok`, then the whole validate suite passes (the new check at order 33 collides with nothing).

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/validate/checks/variant_identity.py science/tests/validate/test_checks_variant_identity.py science/tests/fixtures
git commit -m "feat(c4a): variant-identity check (declaration + row minting, order 33)"
```

---

## Task 12: Commons artifacts — sequence store + registry resources (built-unbuilt)

Scaffold the `~/d/science-commons` data artifacts so operators can build them; they ship unbuilt (placeholder hash, count 0), exactly like the C2/C3 crosswalks. No unit TDD (these are data recipes); a structure check guards the layout.

**Files (in `~/d/science-commons`):**
- Create: `datasets/sequence-store-grch38-grch37/{datapackage.yaml,entity.md,recipe/{build.py,sources.yaml,README.md}}`
- Modify: `datasets/assembly-registry/{datapackage.yaml,recipe/build.py,recipe/sources.yaml}`

**Files (in `~/d/science`):**
- Create: `science/src/science_tool/commons/sequence_store_build.py` (the build helper the recipe calls)
- Test: `science/tests/test_commons_sequence_store_build.py`

- [ ] **Step 1: Write the failing test for the build helper (pure slicing + verify)**

```python
# science/tests/test_commons_sequence_store_build.py
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.commons.sequence_store import refget_digest
from science_tool.commons.sequence_store_build import slice_fasta_to_store


def test_slice_fasta_writes_verified_contigs(tmp_path: Path) -> None:
    fasta = ">1 chromosome 1\nACGTACGT\nACGTACGT\n>MT\nTTTTGGGG\n"
    fasta_path = tmp_path / "genome.fa"
    fasta_path.write_text(fasta, encoding="ascii")
    out = tmp_path / "store"
    manifest = slice_fasta_to_store(fasta_path, out)
    chr1_digest = refget_digest("ACGTACGTACGTACGT")
    assert (out / chr1_digest).read_text() == "ACGTACGTACGTACGT"
    assert {m["name"] for m in manifest} == {"1", "MT"}
    assert next(m for m in manifest if m["name"] == "1")["refget_digest"] == chr1_digest


def test_slice_fasta_rejects_empty_contig(tmp_path: Path) -> None:
    (tmp_path / "g.fa").write_text(">1\n\n>2\nACGT\n", encoding="ascii")
    with pytest.raises(ValueError, match="empty contig"):
        slice_fasta_to_store(tmp_path / "g.fa", tmp_path / "out")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest science/tests/test_commons_sequence_store_build.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.sequence_store_build`.

- [ ] **Step 3: Implement `sequence_store_build.py`**

```python
# science/src/science_tool/commons/sequence_store_build.py
"""Build helper: slice a genome FASTA into a content-addressed sequence store
(Pillar C, C4a-D3). Each contig is written to a file named by its refget digest
and the digest is recomputed-and-asserted (the integrity gate). Operator-run;
the bytes are materialized locally and NOT committed (digests are the committed
authority). `fetch_fasta` is the only network call."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from science_tool.commons.sequence_store import refget_digest


def _iter_fasta(text: str):
    name: str | None = None
    chunks: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            if name is not None:
                yield name, "".join(chunks)
            name = line[1:].split()[0]  # id up to first whitespace
            chunks = []
        else:
            chunks.append(line.strip())
    if name is not None:
        yield name, "".join(chunks)


def slice_fasta_to_store(fasta_path: Path, out_dir: Path) -> list[dict[str, Any]]:
    """Write each contig to out_dir/<refget_digest>; return the manifest rows."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []
    for name, seq in _iter_fasta(Path(fasta_path).read_text(encoding="ascii")):
        if not seq:
            raise ValueError(f"empty contig {name!r} in {fasta_path}")
        seq = seq.upper()
        digest = refget_digest(seq)
        (out_dir / digest).write_text(seq, encoding="ascii")
        manifest.append({"name": name, "refget_digest": digest, "length": len(seq)})
    return manifest


def fetch_fasta(url: str, dest: Path) -> Path:
    """Stream a (optionally gzipped) FASTA to dest (build-time only)."""
    import gzip
    import httpx

    dest = Path(dest)
    with httpx.stream("GET", url, timeout=300.0, follow_redirects=True) as resp:
        resp.raise_for_status()
        raw = b"".join(resp.iter_bytes())
    data = gzip.decompress(raw) if url.endswith(".gz") else raw
    dest.write_bytes(data)
    return dest
```

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest science/tests/test_commons_sequence_store_build.py -v`
Expected: PASS.

- [ ] **Step 5: Scaffold the commons dataset (built-unbuilt) in `~/d/science-commons`**

Create `datasets/sequence-store-grch38-grch37/datapackage.yaml`:

```yaml
name: sequence-store-grch38-grch37
profile: data-package
title: "Reference sequence store (GRCh38 + GRCh37) — per-contig refget bytes"
version: "1.0.0"
licenses:
  - name: NCBI-PD
    path: https://www.ncbi.nlm.nih.gov/home/about/policies/
    title: NCBI Public Domain
provenance:
  - action: build
    tool: recipe/build.py
resources:
  - name: manifest
    path: manifest.csv
    format: csv
    description: "One row per contig: name, refget_digest, length, assembly seqcol_digest, sha256. The bytes (one file per refget_digest) are materialized locally, NOT committed (pinned + verifiable, not archival)."
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 0
```

Create `datasets/sequence-store-grch38-grch37/entity.md`:

```markdown
---
id: dataset:sequence-store-grch38-grch37
type: dataset
schema_profile: science-entity-base/1.0+dataset/1.0
source_class: reference
---
Per-contig reference sequence bytes for GRCh38 + GRCh37, content-addressed by
refget digest. Built locally via recipe/build.py; only the manifest of digests is
committed. See ~/d/science/docs/plans/2026-05-28-c4-variant-identity-design.md (C4a-D3).
```

Create `datasets/sequence-store-grch38-grch37/recipe/sources.yaml`:

```yaml
# Pinned, dated genome FASTA releases (immutable handles; latest/ is discovery-only).
assemblies:
  - label: GRCh38
    seqcol_digest: "REPLACE_WITH_GRCh38_SEQCOL_DIGEST"
    fasta_url: "REPLACE_WITH_PINNED_GRCh38_FASTA_URL"
  - label: GRCh37
    seqcol_digest: "REPLACE_WITH_GRCh37_SEQCOL_DIGEST"
    fasta_url: "REPLACE_WITH_PINNED_GRCh37_FASTA_URL"
```

Create `datasets/sequence-store-grch38-grch37/recipe/build.py`:

```python
"""Operator-run build of the GRCh38+GRCh37 sequence store.

Run from the dataset directory:
  uv run --with httpx python recipe/build.py
Network fetches the pinned FASTAs; output is ~6 GB of per-contig files + manifest.csv.
The bytes are NOT committed; commit only manifest.csv (digests) after building.
"""
from __future__ import annotations

import csv
from pathlib import Path

import yaml

from science_tool.commons.sequence_store_build import fetch_fasta, slice_fasta_to_store

_HERE = Path(__file__).resolve().parent
_OUT = _HERE.parent
_FIELDS = ["assembly_seqcol_digest", "name", "refget_digest", "length"]


def main() -> None:
    src = yaml.safe_load((_HERE / "sources.yaml").read_text(encoding="utf-8"))
    rows: list[dict] = []
    for asm in src["assemblies"]:
        fasta = fetch_fasta(asm["fasta_url"], _HERE / f"{asm['label']}.fa")
        for m in slice_fasta_to_store(fasta, _OUT):
            rows.append({"assembly_seqcol_digest": asm["seqcol_digest"], **m})
        fasta.unlink()
    with (_OUT / "manifest.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} contigs + manifest.csv (commit ONLY manifest.csv)")


if __name__ == "__main__":
    main()
```

Create `datasets/sequence-store-grch38-grch37/recipe/README.md` documenting: pinned/verifiable-not-archival caveat; bytes are local-only; commit only `manifest.csv`; rebuild may fail if upstream disappears but a produced store is digest-verified.

- [ ] **Step 6: Extend the assembly-registry recipe + datapackage**

In `~/d/science-commons/datasets/assembly-registry/`: add `contigs` and `contig_aliases` resources to `datapackage.yaml` (placeholder hashes/bytes), add the NCBI assembly-report URLs to `recipe/sources.yaml`, and update `recipe/build.py` to also write `contigs.csv` (via `assembly_registry_build.build_contig_rows` over each fetched level-2 record) and `contig_aliases.csv` (via `assembly_report_build.parse_assembly_report` over each fetched assembly report, joined to contigs on sequence name).

- [ ] **Step 7: Commit (two repos)**

```bash
git -C ~/d/science add science/src/science_tool/commons/sequence_store_build.py science/tests/test_commons_sequence_store_build.py
git -C ~/d/science commit -m "feat(c4a): sequence-store build helper (slice FASTA -> refget store)"
git -C ~/d/science-commons add datasets/sequence-store-grch38-grch37 datasets/assembly-registry
git -C ~/d/science-commons commit -m "feat(c4a): sequence-store dataset + registry contig/alias resources (unbuilt)"
```

---

## Task 13: Wire-up verification + docs

**Files:**
- Modify: `docs/plans/2026-05-28-c4-variant-identity-design.md` (status), `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` (§8 C4 row → C4a merged), `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md` (§8 remaining).

- [ ] **Step 1: Full suite green**

Run: `uv run pytest science/tests/ -q`
Expected: PASS (no regressions; new commons + validate tests included).

- [ ] **Step 2: Lint clean**

Run: `uv run ruff check science/src/science_tool/commons/ science/src/science_tool/validate/checks/variant_identity.py`
Expected: no errors. (Do NOT reformat unrelated modules.)

- [ ] **Step 3: Update the docs to mark C4a landed**

In the C4 design doc, set §12 status to "C4a implemented". In the Pillar-C design §8 and the umbrella §8, note C4a (variant identity) merged, C4b (liftover + compatibility relations) and C4c (rsID/transcript) remaining. Use `~/d/` paths.

- [ ] **Step 4: Commit**

```bash
git add docs/plans
git commit -m "docs(c4a): mark variant-identity sub-phase implemented; C4b/C4c remaining"
```

---

## Self-Review (run by the plan author)

**Spec coverage (design §1–§9):**
- §1 scope / accepted inputs → Tasks 8 (SPDI), 9 (HGVS_g, VCF), `_SYMBOLIC`/multiallelic rejection (Task 9 `_parse`). ✓
- §2 contig + alias tables (incl. `sequence_index`, hard duplicate errors) → Tasks 3, 4, 5. ✓
- §3 per-contig refget digests materialized → Task 4; alias source = pinned assembly report → Task 3 + Task 12 Step 6. ✓
- §4 assemblies by seqcol digest; b37/hs37d5 not aliased → enforced by `resolve_contig`'s assembly-scoped lookup + the registry only pinning exact digests (Task 5, Task 12). ✓
- §5 sequence store, digests-committed/bytes-local, flat refget store, pinned-not-archival → Tasks 6, 12. ✓
- §6 offline DataProxy, no-network tested invariant, fail-loud → Task 7. ✓
- §7 dependency spike first; pin pkg + spec version; fallback documented → Tasks 1, 2. ✓
- §8 variant tier convention (no schema change), locator contract, two-layer check (`tier_declaration_defect` not `evaluate_tier_identity`); CSV/TSV only; datapackage-resolved resource → Tasks 10, 11. ✓
- §9 fixtures + negatives (ref-mismatch, out-of-bounds, ambiguous alias, symbolic, multiallelic, missing store, accession mismatch) + version-tied golden → Tasks 5, 6, 8, 9, 11. ✓

**Placeholder scan:** The only intentional `REPLACE_WITH_*` tokens are in `~/d/science-commons` recipe `sources.yaml` (pinned digests/URLs an operator fills at build time — the same built-unbuilt pattern as C2/C3) and the captured `_GOLDEN_SNV` (empirically pinned in Task 8 Step 5, not invented). No code step is left as prose.

**Type consistency:** `refget_digest`, `open_store`/`SequenceStore.sequence`, `RefgetProxy.get_sequence/get_metadata`, `compute_vrs_id(proxy, *, fmt, expr)`, `resolve_contig(...) → ContigMatch|AmbiguousContig|AccessionAssemblyMismatch`, `vrs_id(...) → VariantMatch|VariantDefect`, and `tier_declaration_defect` are used consistently across Tasks 5–11.

**Known external-API risk:** the exact `ga4gh.vrs` translator/identify symbols are pinned by the Task 1 spike and isolated in `vrs.py`; every downstream task depends only on our signatures, so a surface difference is absorbed in one module.
