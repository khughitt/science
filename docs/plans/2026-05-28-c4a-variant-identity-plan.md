# C4a — Variant Identity (VRS 2.0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mint reproducible, offline, assembly-anchored GA4GH VRS 2.0 variant identifiers (`ga4gh:VA…`) for variants declared on GRCh38 or GRCh37, from SPDI / genomic-HGVS / VCF inputs, plus the declaration + validate check that exercises them.

**Architecture:** A pinned, content-addressed per-contig reference-sequence store (bytes built locally, digests committed) is read by a pure, offline `ga4gh.vrs` `DataProxy` whose contig identity comes from the C1 assembly registry (extended here with per-contig refget digests + an alias table). A thin `vrs_id()` resolver wraps `ga4gh.vrs` normalization + identifier computation behind our own stable signature. A two-layer validate check verifies the variant-tier declaration (shape + locator) and then mints the actual dataset rows.

**Tech Stack:** Python 3.13, `ga4gh.vrs` (VRS 2.x; pinned in Task 2), the existing commons reference-collection substrate (`resolve()`, `dataset_frontmatters`, `@Check`), CSV/TSV data resources, pytest.

---

## Pre-flight (read once before Task 1)

- **Branch.** Create `feat/c4a-variant-identity` off `main`. Do all work there. (Subagent executors: `cd` to the repo root `~/d/science` and verify the branch before each task — commits must not land on `main`.)
- **Two working directories.** Git operations run from the repo root `~/d/science`. Python package operations run from the nested package root `~/d/science/science` (this is where `pyproject.toml` and `uv.lock` live). Code + tests + fixtures live under `~/d/science/science/` (`src/science_tool/`, `tests/`). The *commons data artifacts* (the sequence-store dataset and the assembly-registry resource additions) live in the separate `~/d/science-commons` repo and ship **built-unbuilt** (placeholder hash, count 0), exactly like the C2/C3 crosswalks. Tasks 1–11 are entirely in `~/d/science`; Task 12 touches `~/d/science-commons`.
- **Design source of truth.** `docs/plans/2026-05-28-c4-variant-identity-design.md` (C4a = §1–§9). Parent: `docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md` (C-D1…C-D6).
- **Test command.** From `~/d/science/science`: `uv run pytest tests/<file>::<test> -v`. The full validate suite is `uv run pytest tests/validate/ -q`. When a command needs both git-root paths and the package environment, use `git -C ~/d/science ...` for git and `cd ~/d/science/science && uv run ...` for Python.
- **House conventions.** Composition > inheritance; explicit > defensive; fail early (no silent fallbacks); no "legacy"/"compatibility" layers; no "Unified" prefix; no `Co-Authored-By` trailers; use `~/d/` in any doc/code paths.
- **Pattern templates to mirror (read these):** `science/src/science_tool/commons/assembly.py` (registry resolver), `commons/gene_crosswalk.py` + `gene_crosswalk_build.py` (resolver + build-helper split), `commons/resolver.py` (`resolve()` — note it re-hashes the whole file per call, so it is used **only** for the small CSVs, never the multi-GB sequence bytes), `validate/checks/identity_context.py` (`_tier_defect`, `_TierSpec`, two-stage check wiring), `science/tests/test_commons_gene_crosswalk.py` + `science/tests/validate/test_checks_identity_context.py` (test style).

---

## File Structure

**New in `~/d/science/science/src/science_tool/commons/`:**
- `assembly_report_build.py` — pure parser + fail-loud join: NCBI assembly report text → contig alias rows joined to seqcol contigs (build-time; `fetch_text` is the only network call).
- `contigs.py` — resolver over the registry's `contigs.csv` + `contig_aliases.csv`: `resolve_contig(alias, *, seqcol_digest) → ContigMatch`. Exactly-one-match; ambiguous/unknown/accession-mismatch are explicit errors.
- `sequence_store.py` — content-addressed per-contig sequence reader: `open_store(root).sequence(refget_digest, start, end)`; verify-once-per-contig against the refget digest; fail loud on missing.
- `refget_proxy.py` — the `ga4gh.vrs` `DataProxy` subclass over `contigs` + `sequence_store` (offline; fail-loud).
- `vrs.py` — the ga4gh.vrs boundary: `compute_vrs_id(proxy, *, fmt, expr) → str` (wraps whatever 2.x surface the spike pins; the *only* module that imports `ga4gh.vrs`).
- `variant.py` — public resolver: `vrs_id(expr, *, fmt, assembly_seqcol, …) → VariantMatch` (parses, resolves contig, flags, calls `vrs.compute_vrs_id`).
- `sequence_store_build.py` — build helper: slice FASTA into per-contig files named by refget digest, verify, write manifest (network build-time only).

**Modified in `~/d/science/science/src/science_tool/`:**
- `commons/assembly_registry_build.py` — add `build_contig_rows(level2, seqcol_digest)`.
- `validate/checks/identity_context.py` — rename private `_tier_defect` → public `tier_declaration_defect` (the shared, registry-agnostic shape validator); update internal callers.
- `validate/checks/variant_identity.py` *(new)* — `@Check(section="variant identity", order=33)`; declaration layer (reuses `tier_declaration_defect` + locator check) + row layer (mint located rows).
- `validate/checks/__init__.py` — register `variant_identity` in `_load_canonical_checks()` so normal `science validate` runs the new check.

**New tests in `~/d/science/science/tests/`:** `test_commons_assembly_report_build.py`, `test_commons_contigs.py`, `test_commons_sequence_store.py`, `test_commons_refget_proxy.py`, `test_commons_vrs_spike.py`, `test_commons_variant.py`, `validate/test_checks_variant_identity.py`.

**New fixtures under `~/d/science/science/tests/fixtures/commons/`:** `assembly-c4a/datasets/assembly-registry/` + `assembly-c4a-data/assembly-registry/` (entity + `assemblies.csv`/`contigs.csv`/`contig_aliases.csv`), `seqstore/` (a tiny synthetic contig file), and a `variant-dataset/` for the check.

**New in `~/d/science-commons/` (Task 12):** `datasets/sequence-store-grch38-grch37/` (datapackage + recipe + entity), and additions to `datasets/assembly-registry/`.

---

## Task 1: Dependency spike — VRS identify through an injected proxy, offline

**Purpose:** De-risk the entire approach before building anything. Prove the pinned `ga4gh.vrs` can normalize + compute an identifier through a *custom* `DataProxy` with **no SeqRepo and no network**. The spike's confirmed API surface is recorded and consumed by Task 5 (`vrs.py`). If it fails, switch Task 5 to the fallback (local parsers + core models) — see Step 6.

**Files:**
- Create: `science/tests/test_commons_vrs_spike.py`

- [ ] **Step 1: Add `ga4gh.vrs` to the environment for the spike only**

Run (from `~/d/science/science`): `uv add --dev 'ga4gh.vrs>=2.3,<3'`
Expected: resolves a non-yanked 2.x release (2.1.x are yanked). Record the exact resolved version from `science/uv.lock` (e.g. `2.3.0`) in the commit message — Task 2 promotes it to a real dependency.

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
_REPEAT_SEQ = "CCCCAAAAAGGGGTTTTCCCC"


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

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_vrs_spike.py -v`
Expected: PASS. If `AlleleTranslator`/`translate_from`/`ga4gh_identify`/`sha512t24u` import paths differ in the installed version, adjust the test to the real surface (that *is* the spike's job) until it passes, then keep it.

- [ ] **Step 4: Add a normalization-property assertion**

Append a test proving fully-justified normalization is active (a left-shiftable indel normalizes to a canonical position, so two equivalent representations get the **same** id):

```python
def test_equivalent_indel_representations_share_one_id() -> None:
    from ga4gh.core import ga4gh_identify
    from ga4gh.vrs.extras.translator import AlleleTranslator

    # _REPEAT_SEQ has an A homopolymer; deleting one A is representable at
    # multiple offsets but normalizes to one allele -> one id.
    proxy = _MemoryProxy(_REPEAT_SEQ)
    sq = _refget_digest(_REPEAT_SEQ)
    tlr = AlleleTranslator(data_proxy=proxy, normalize=True)
    a = ga4gh_identify(tlr.translate_from(f"ga4gh:{sq}:4:A:", fmt="spdi"))
    b = ga4gh_identify(tlr.translate_from(f"ga4gh:{sq}:5:A:", fmt="spdi"))
    assert a == b
```

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_vrs_spike.py -v`
Expected: PASS. If the exact offsets need adjustment for the installed VRS normalizer, keep the homopolymer fixture and adjust only within that repeated base run; do not switch back to a non-repeated sequence.

- [ ] **Step 5: Record the confirmed surface**

In the commit body, record the working import paths + class/method names (`AlleleTranslator(data_proxy=..., normalize=...)`, `translate_from(expr, fmt=...)`, `ga4gh_identify`, `sha512t24u`) and the exact pinned version. Task 5 mirrors exactly this.

- [ ] **Step 6: Commit (and record the decision branch)**

If the spike passed: proceed. If it could **not** be made to pass offline through a custom proxy, STOP and escalate — Task 5 then implements the fallback (local SPDI/HGVS_g/VCF parsers building VRS core `models.Allele` objects + `normalize()` + `ga4gh_identify`, bypassing the translator), and Tasks 8–9 call that instead. Record which path is taken.

```bash
git add science/tests/test_commons_vrs_spike.py science/uv.lock science/pyproject.toml
git commit -m "spike(c4a): VRS identify through custom offline DataProxy"
```

---

## Task 2: Promote `ga4gh.vrs` to a real dependency, pinned

**Files:**
- Modify: `science/pyproject.toml` (dependencies)
- Modify: `science/uv.lock` (package lock)

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

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_vrs_spike.py::test_ga4gh_vrs_is_a_pinned_runtime_dependency -v`
Expected: PASS (dep present from Task 1's `uv add --dev`).

- [ ] **Step 3: Move it from dev to a real runtime dependency**

Edit the package config (`science/pyproject.toml`), adding to `[project].dependencies` the line `"ga4gh.vrs>=2.3,<3",` (exact resolved version stays pinned in `science/uv.lock`). Remove the dev-only entry added in Task 1.

Run: `cd ~/d/science/science && uv sync && uv run python -c "import ga4gh.vrs; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Re-run the guard test**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_vrs_spike.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/pyproject.toml science/uv.lock
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

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_assembly_report_build.py -v`
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

- [ ] **Step 4: Add the fail-loud contig/alias join helper**

Append a test that the build-time alias join is explicit and cannot silently miss contigs. The assembly report's `Sequence-Name` is expected to match the seqcol level-2 `name`; if a future seqcol source uses accessions as names, this must fail during the commons build, not produce a partial alias table.

```python
def test_build_contig_alias_rows_joins_by_sequence_name_and_rejects_unmatched() -> None:
    import pytest
    from science_tool.commons.assembly_report_build import build_contig_alias_rows, parse_assembly_report

    contigs = [
        {"seqcol_digest": "DIGEST38", "sequence_index": 0, "name": "1", "refget_digest": "SQ.chr1", "length": 248956422},
        {"seqcol_digest": "DIGEST38", "sequence_index": 1, "name": "MT", "refget_digest": "SQ.mt", "length": 16569},
    ]
    aliases = build_contig_alias_rows(contig_rows=contigs, report_rows=parse_assembly_report(_REPORT))
    assert {
        "seqcol_digest": "DIGEST38",
        "refget_digest": "SQ.chr1",
        "alias": "NC_000001.11",
        "alias_kind": "refseq_accession",
        "sequence_accession": "NC_000001.11",
    } in aliases

    with pytest.raises(ValueError, match="assembly-report sequence name"):
        build_contig_alias_rows(contig_rows=contigs[:1], report_rows=parse_assembly_report(_REPORT))
```

Add to `assembly_report_build.py`:

```python
def build_contig_alias_rows(*, contig_rows: list[dict[str, Any]], report_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Join parsed assembly-report aliases to seqcol contig rows by Sequence-Name.

    The join is intentionally hard-fail. Alias correctness is the resolver contract;
    an unmatched report row means the seqcol level-2 names and assembly report do
    not describe the same naming surface."""
    by_name: dict[str, dict[str, Any]] = {}
    for row in contig_rows:
        name = str(row.get("name", "")).strip()
        if not name:
            raise ValueError("contig row has blank name")
        if name in by_name:
            raise ValueError(f"duplicate contig name {name!r}")
        by_name[name] = row

    out: list[dict[str, Any]] = []
    for alias in report_rows:
        name = str(alias.get("sequence_name", "")).strip()
        contig = by_name.get(name)
        if contig is None:
            raise ValueError(f"assembly-report sequence name {name!r} has no seqcol contig row")
        out.append(
            {
                "seqcol_digest": contig["seqcol_digest"],
                "refget_digest": contig["refget_digest"],
                "alias": alias["alias"],
                "alias_kind": alias["alias_kind"],
                "sequence_accession": alias["sequence_accession"],
            }
        )
    return out
```

- [ ] **Step 5: Run it to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_assembly_report_build.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

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


def test_build_contig_rows_rejects_duplicate_names_and_blank_fields() -> None:
    import pytest
    from science_tool.commons.assembly_registry_build import build_contig_rows

    with pytest.raises(ValueError, match="duplicate contig name"):
        build_contig_rows(level2={"names": ["1", "1"], "lengths": [1, 1], "sequences": ["SQ.a", "SQ.b"]}, seqcol_digest="D")
    with pytest.raises(ValueError, match="blank contig name"):
        build_contig_rows(level2={"names": [" "], "lengths": [1], "sequences": ["SQ.a"]}, seqcol_digest="D")
    with pytest.raises(ValueError, match="blank refget digest"):
        build_contig_rows(level2={"names": ["1"], "lengths": [1], "sequences": [" "]}, seqcol_digest="D")
    with pytest.raises(ValueError, match="invalid length"):
        build_contig_rows(level2={"names": ["1"], "lengths": [0], "sequences": ["SQ.a"]}, seqcol_digest="D")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_assembly_registry_build.py -k build_contig_rows -v`
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
    out: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    for i, (name, length, refget_digest) in enumerate(zip(names, lengths, sequences, strict=True)):
        name_s = str(name).strip()
        digest_s = str(refget_digest).strip()
        if not name_s:
            raise ValueError(f"blank contig name at index {i} for {seqcol_digest!r}")
        if not digest_s:
            raise ValueError(f"blank refget digest at index {i} for {seqcol_digest!r}")
        if name_s in seen_names:
            raise ValueError(f"duplicate contig name {name_s!r} in {seqcol_digest!r}")
        seen_names.add(name_s)
        length_i = int(length)
        if length_i <= 0:
            raise ValueError(f"invalid length {length!r} for contig {name_s!r}")
        out.append(
            {
                "seqcol_digest": seqcol_digest,
                "sequence_index": i,
                "name": name_s,
                "refget_digest": digest_s,
                "length": length_i,
            }
        )
    return out
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_assembly_registry_build.py -k build_contig_rows -v`
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
- Fixtures: `science/tests/fixtures/commons/assembly-c4a/datasets/assembly-registry/` (entity + datapackage) and `science/tests/fixtures/commons/assembly-c4a-data/assembly-registry/` (`contigs.csv`, `contig_aliases.csv`)

- [ ] **Step 1: Create the fixtures**

Create `science/tests/fixtures/commons/assembly-c4a-data/assembly-registry/contigs.csv`:

```csv
seqcol_digest,sequence_index,name,refget_digest,length
DIGEST38,0,1,SQ.chr1_38,248956422
DIGEST37,0,1,SQ.chr1_37,249250621
```

Create `science/tests/fixtures/commons/assembly-c4a-data/assembly-registry/contig_aliases.csv`:

```csv
seqcol_digest,refget_digest,alias,alias_kind,sequence_accession
DIGEST38,SQ.chr1_38,1,seqcol_name,
DIGEST38,SQ.chr1_38,chr1,ucsc,
DIGEST38,SQ.chr1_38,NC_000001.11,refseq_accession,NC_000001.11
DIGEST37,SQ.chr1_37,1,seqcol_name,
DIGEST37,SQ.chr1_37,chr1,ucsc,
DIGEST37,SQ.chr1_37,NC_000001.10,refseq_accession,NC_000001.10
```

Create the commons entity + datapackage so `resolve()` finds these resources. `CommonsEntityAdapter.load()` requires the canonical commons layout `datasets/<slug>/entity.md`; `resolve()` then reads resource bytes from `data_root/<slug>/<logical_path>`.

`science/tests/fixtures/commons/assembly-c4a/datasets/assembly-registry/entity.md`:

```markdown
---
id: dataset:assembly-registry
type: dataset
schema_profile: science-entity-base/1.0+dataset/1.0+bio.assembly_registry/1.0
title: "Assembly registry (C4a contig + alias fixture)"
version: "1.0.0"
created: "2026-05-28"
updated: "2026-05-28"
datapackage: datapackage.yaml
origin: external
status: active
tier: use-now
access:
  level: public
  verified: true
source_class: reference
member_key_column: seqcol_digest
assembly_count: 2
---
Assembly registry fixture (C4a contig/alias resources).
```

`science/tests/fixtures/commons/assembly-c4a/datasets/assembly-registry/datapackage.yaml` — compute the two hashes/bytes with `sha256sum` on the CSVs you just wrote and paste them (the resolver verifies them):

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

Run to get the values: `sha256sum science/tests/fixtures/commons/assembly-c4a-data/assembly-registry/*.csv && wc -c science/tests/fixtures/commons/assembly-c4a-data/assembly-registry/*.csv`

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

_FIX = Path(__file__).parent / "fixtures" / "commons" / "assembly-c4a"
_DATA = Path(__file__).parent / "fixtures" / "commons" / "assembly-c4a-data"


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

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_contigs.py -v`
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

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_contigs.py -v`
Expected: PASS (the `test_alias_ambiguous…` test skips; duplicates covered by the parser tests).

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/commons/contigs.py science/tests/test_commons_contigs.py science/tests/fixtures/commons/assembly-c4a science/tests/fixtures/commons/assembly-c4a-data
git commit -m "feat(c4a): contig + alias resolver with mismatch/ambiguity errors"
```

---

## Task 6: Content-addressed sequence store reader (`sequence_store.py`)

Per-contig files named by refget digest, stream-verified once on first use, then sliced by byte offset (never re-read whole contigs per substring; never routed through `resolve()`'s whole-file sha256). Refget hashing is over the exact sequence bytes (no implicit uppercasing), matching `ga4gh.core.sha512t24u`; build-time registry checks catch any FASTA/seqcol case mismatch. Fails loud on a missing contig.

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
    assert store.length(digest) == len(_SEQ)


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


def test_refget_digest_matches_ga4gh_core_without_case_normalization() -> None:
    from ga4gh.core import sha512t24u

    seq = "ACgt"
    assert refget_digest(seq) == "SQ." + sha512t24u(seq.encode("ascii"))
    assert refget_digest(seq) != refget_digest(seq.upper())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_sequence_store.py -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.sequence_store`.

- [ ] **Step 3: Implement `sequence_store.py`**

```python
# science/src/science_tool/commons/sequence_store.py
"""Content-addressed per-contig reference-sequence reader (Pillar C, C4a-D3).

A flat store: one file per contig, named by its refget digest (SQ.<sha512t24u>).
A contig is stream-verified ONCE on first use (its bytes must reproduce its
digest), then subsequent substring reads seek by byte offset. It is never routed
through the commons `resolve()` whole-file sha256 (that would re-hash gigabytes
per substring). The bytes are materialized locally (digests are the committed
authority); a missing contig fails loud and NEVER triggers a fetch."""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass, field
from pathlib import Path


class SequenceStoreError(LookupError):
    """A requested contig is absent, or its bytes do not match its refget digest."""


def _sha512t24u(data: bytes) -> str:
    return base64.urlsafe_b64encode(hashlib.sha512(data).digest()[:24]).decode("ascii").rstrip("=")


def refget_digest(seq: str) -> str:
    """The GA4GH refget digest 'SQ.<sha512t24u>' of the exact sequence bytes."""
    return "SQ." + _sha512t24u(seq.encode("ascii"))


@dataclass
class SequenceStore:
    root: Path
    _lengths: dict[str, int] = field(default_factory=dict)

    def _path(self, digest: str) -> Path:
        return self.root / digest

    def _verify(self, digest: str) -> int:
        path = self._path(digest)
        if not path.is_file():
            raise SequenceStoreError(f"contig {digest!r} not in sequence store at {self.root}")
        h = hashlib.sha512()
        n = 0
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                n += len(chunk)
                h.update(chunk)
        actual = "SQ." + base64.urlsafe_b64encode(h.digest()[:24]).decode("ascii").rstrip("=")
        if actual != digest:
            raise SequenceStoreError(f"refget digest mismatch for {digest!r}: bytes hash to {actual!r}")
        self._lengths[digest] = n
        return n

    def length(self, digest: str) -> int:
        return self._lengths.get(digest) or self._verify(digest)

    def sequence(self, digest: str, start: int | None = None, end: int | None = None) -> str:
        length = self.length(digest)
        start_i = 0 if start is None else start
        end_i = length if end is None else end
        if start_i < 0 or end_i < start_i or end_i > length:
            raise SequenceStoreError(f"slice {start_i}:{end_i} outside contig {digest!r} length {length}")
        path = self._path(digest)
        with path.open("rb") as fh:
            fh.seek(start_i)
            return fh.read(end_i - start_i).decode("ascii")


def open_store(root: Path) -> SequenceStore:
    """Open the flat refget store rooted at `root`. No I/O until a contig is read."""
    return SequenceStore(root=Path(root))
```

> Note: one-time digest verification streams the full contig, but row-level base lookups after that use byte offsets and never re-read the whole contig.

- [ ] **Step 4: Run it to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_sequence_store.py -v`
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

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_refget_proxy.py -v`
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
        length = self.store.length(digest)  # raises if absent/corrupt (fail loud, no network)
        return {"length": length, "aliases": [f"ga4gh:{digest}"], "alphabet": "ACGT", "added": None}
```

> If the Task 1 spike showed the translator needs an additional DataProxy method or a richer `aliases` list (e.g. `translate_sequence_identifier`), add the minimal method here to match the spike's confirmed surface — the spike test is the contract.

- [ ] **Step 4: Run it to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_refget_proxy.py -v`
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

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_variant.py -v`
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

_ACCEPTED_FMTS = frozenset({"spdi", "hgvs"})


class _Proxy(Protocol):
    def get_sequence(self, identifier: str, start: int | None = None, end: int | None = None) -> str: ...
    def get_metadata(self, identifier: str) -> dict: ...


def _translator(proxy: _Proxy) -> Any:
    from ga4gh.vrs.extras.translator import AlleleTranslator

    return AlleleTranslator(data_proxy=proxy, normalize=True)


def compute_vrs_id(proxy: _Proxy, *, fmt: str, expr: str) -> str:
    """Return 'ga4gh:VA.<digest>' for `expr` in `fmt` (spdi | hgvs).

    `hgvs` is genomic HGVS only (transcript/protein HGVS is C4c). VCF is parsed
    in `variant.py` and re-expressed as SPDI before crossing this boundary.
    Raises ValueError on an unaccepted fmt."""
    from ga4gh.core import ga4gh_identify

    if fmt not in _ACCEPTED_FMTS:
        raise ValueError(f"unsupported variant fmt {fmt!r}; expected one of {sorted(_ACCEPTED_FMTS)}")
    allele = _translator(proxy).translate_from(expr, fmt=fmt)
    return ga4gh_identify(allele)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_variant.py -v`
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


def test_compute_vrs_id_rejects_uncovered_formats(tmp_path: Path) -> None:
    proxy, digest = _proxy(tmp_path)
    with pytest.raises(ValueError, match="unsupported variant fmt 'gnomad'"):
        compute_vrs_id(proxy, fmt="gnomad", expr=f"ga4gh:{digest}:5:G:T")
```

Capture command: `cd ~/d/science/science && uv run python -c "from pathlib import Path; import tempfile; from science_tool.commons.sequence_store import open_store, refget_digest; from science_tool.commons.refget_proxy import RefgetProxy; from science_tool.commons.vrs import compute_vrs_id; d=Path(tempfile.mkdtemp()); s='CGTACGTACGTACGTACGTACGTACGTACGTACGTACGTA'; g=refget_digest(s); (d/g).write_text(s); print(compute_vrs_id(RefgetProxy(store=open_store(d)), fmt='spdi', expr=f'ga4gh:{g}:5:G:T'))"`
Paste the printed value into `_GOLDEN_SNV`.

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_variant.py -v`
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


def test_vrs_id_can_use_explicit_store_root_for_fixtures(monkeypatch, tmp_path: Path) -> None:
    from science_tool.commons import variant as V
    from science_tool.commons.contigs import ContigMatch
    from science_tool.commons.sequence_store import refget_digest

    digest = refget_digest(_SEQ)
    (tmp_path / digest).write_text(_SEQ, encoding="ascii")
    monkeypatch.setattr(V, "_resolve_contig", lambda q, **k: ContigMatch(digest, "1", len(_SEQ), "seqcol_name"))
    m = V.vrs_id("1-6-G-T", fmt="vcf", assembly_seqcol="DIGEST38", store_root=tmp_path)
    assert isinstance(m, V.VariantMatch)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_variant.py -k "vcf or mismatch or symbolic" -v`
Expected: FAIL — `ModuleNotFoundError: science_tool.commons.variant`.

- [ ] **Step 3: Implement `variant.py`**

```python
# science/src/science_tool/commons/variant.py
"""Public variant-identity resolver (Pillar C, C4a-D5/D6).

vrs_id(expr, fmt, assembly_seqcol) parses an accepted small-allele expression
(SPDI / genomic-HGVS / VCF chrom-pos-ref-alt), resolves its contig within the
declared assembly (Task 5), validates the reference base, and mints the VRS id
(Task 8). Every data rejection is a typed VariantDefect (flagged, never dropped):
unsupported-allele, accession-assembly-mismatch, ambiguous-contig, unknown-contig,
ref-mismatch, out-of-bounds. Local-store absence is infrastructure and raises
VariantStoreUnavailable/SequenceStoreError so validate can downgrade it to INFO."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_tool.commons.errors import CommonsError
from science_tool.commons.contigs import (
    AccessionAssemblyMismatch,
    AmbiguousContig,
    ContigError,
    ContigMatch,
    resolve_contig as _resolve_contig,
)
from science_tool.commons.refget_proxy import RefgetProxy
from science_tool.commons.resolver import resolve
from science_tool.commons.sequence_store import open_store
from science_tool.commons.vrs import compute_vrs_id

_BREAKEND_TOKENS = ("[", "]")
_SEQUENCE_STORE_ID = "dataset:sequence-store-grch38-grch37"
_SEQUENCE_STORE_MANIFEST = "manifest.csv"


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


class VariantStoreUnavailable(RuntimeError):
    """The local sequence store dataset is absent or its manifest cannot verify."""


def _open_proxy(
    *,
    commons_root: Path | None,
    data_root: Path | None,
    store_root: Path | None = None,
) -> RefgetProxy:
    if store_root is not None:
        return RefgetProxy(store=open_store(Path(store_root)))
    try:
        manifest = resolve(
            _SEQUENCE_STORE_ID,
            _SEQUENCE_STORE_MANIFEST,
            commons_root=commons_root,
            data_root=data_root,
        )
    except CommonsError as exc:
        raise VariantStoreUnavailable(str(exc)) from exc
    return RefgetProxy(store=open_store(manifest.path.parent))


def _parse(expr: str, fmt: str) -> tuple[str, int, str, str] | None:
    """Return (contig_query, pos0, ref, alt) for an accepted small allele, else None.

    pos0 is 0-based. SPDI is already 0-based; VCF is 1-based -> pos0 = pos-1.
    HGVS_g (g.<pos><ref>><alt>) is normalized by the translator, so we only pre-
    validate it is not symbolic and pass it through with pos/ref unknown (-1, '')."""
    def unsupported_allele(ref: str, alt: str) -> bool:
        # "." is unsupported only as a REF/ALT field, not inside accessions
        # (`NC_000001.11`) or refget ids (`SQ.<digest>`). Empty REF/ALT is valid
        # SPDI indel syntax; VCF symbolic alleles/breakends are rejected.
        return (
            (ref == "." or alt == ".")
            or alt.startswith("<")
            or any(tok in ref or tok in alt for tok in _BREAKEND_TOKENS)
            or (ref == "" and alt == "")
        )

    if fmt == "spdi":
        try:
            seq, pos, ref, alt = expr.rsplit(":", 3)
        except ValueError:
            return None
        if unsupported_allele(ref, alt):
            return None
        try:
            pos0 = int(pos)
        except ValueError:
            return None
        return seq, pos0, ref, alt
    if fmt == "vcf":
        try:
            chrom, pos, ref, alt = expr.split("-")
        except ValueError:
            return None
        if unsupported_allele(ref, alt):
            return None
        if "," in alt:  # multiallelic must be pre-split (one ALT per row)
            return None
        try:
            pos0 = int(pos) - 1
        except ValueError:
            return None
        return chrom, pos0, ref, alt
    if fmt == "hgvs":
        if any(tok in expr for tok in ("[", "]", "<", ">?")):
            return None
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
    store_root: Path | None = None,
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

    proxy = _open_proxy(commons_root=commons_root, data_root=data_root, store_root=store_root)

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

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_variant.py -v`
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

Run: `cd ~/d/science/science && uv run pytest tests/validate/test_checks_identity_context.py -k tier_declaration_defect -v`
Expected: FAIL — `ImportError: cannot import name 'tier_declaration_defect'`.

- [ ] **Step 3: Rename `_tier_defect` → `tier_declaration_defect`**

In `science/src/science_tool/validate/checks/identity_context.py`, rename the function `_tier_defect` to `tier_declaration_defect` (public) and update its two internal call sites (`evaluate_tier_identity` body and `_run_tier_check`). Keep the docstring; it is now the shared, registry-agnostic shape validator both the crosswalk tiers and the variant tier call.

- [ ] **Step 4: Run the full identity-context test file (no regressions)**

Run: `cd ~/d/science/science && uv run pytest tests/validate/test_checks_identity_context.py -v`
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
- Modify: `science/src/science_tool/validate/checks/__init__.py`
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

Run: `cd ~/d/science/science && uv run pytest tests/validate/test_checks_variant_identity.py -v`
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
        return "locator.resource (a datapackage resource path) is required"
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

Run: `cd ~/d/science/science && uv run pytest tests/validate/test_checks_variant_identity.py -v`
Expected: PASS.

- [ ] **Step 5: Add the row layer + its test**

Add the row-minting fixture dataset under `science/tests/fixtures/` and a test that a 2-row `variants.csv` (one good SPDI, one ref-mismatch) yields a minted count of 1 and a defect count of 1. Implement `_evaluate_variant_rows` in `variant_identity.py`:

```python
def _evaluate_variant_rows(ctx: ValidateContext, datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Layer 2: for each well-declared, resolved variant tier, open the located
    CSV/TSV resource through the dataset datapackage and mint each row, reporting
    outcome counts. CSV/TSV only (no parquet dependency)."""
    import csv

    from science_tool.commons.datapackage import read_datapackage, stream_sha256_and_bytes
    from science_tool.commons.sequence_store import SequenceStoreError
    from science_tool.commons.variant import VariantDefect, VariantMatch, VariantStoreUnavailable, vrs_id

    def datapackage_path(fm: dict[str, Any]) -> Path | None:
        raw_path = fm.get("_path")
        if not isinstance(raw_path, str) or not raw_path:
            return None
        entity_or_dp = ctx.project_root / raw_path
        if entity_or_dp.suffix in (".yaml", ".yml"):
            return entity_or_dp
        dp_value = fm.get("datapackage")
        if not isinstance(dp_value, str) or not dp_value.strip():
            return None
        project_relative = ctx.project_root / dp_value
        if project_relative.is_file():
            return project_relative
        return entity_or_dp.parent / dp_value

    def locate_resource(fm: dict[str, Any], logical_path: str) -> Path:
        dp = datapackage_path(fm)
        if dp is None:
            raise FileNotFoundError("dataset has no datapackage path")
        descriptor = read_datapackage(dp)
        resource = descriptor.resource(logical_path)
        abs_path = dp.parent / resource.path
        if not abs_path.is_file():
            raise FileNotFoundError(str(abs_path))
        actual_hash, actual_bytes = stream_sha256_and_bytes(abs_path)
        if actual_hash != resource.hash:
            raise ValueError(f"{resource.path}: expected {resource.hash}, got {actual_hash}")
        if resource.bytes is not None and actual_bytes != resource.bytes:
            raise ValueError(f"{resource.path}: expected {resource.bytes} bytes, got {actual_bytes}")
        return abs_path

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
        try:
            resource = locate_resource(fm, locator["resource"])
        except FileNotFoundError as exc:
            yield _result(Severity.INFO, path, f"{ident}: variant resource {locator['resource']!r} not found locally ({exc}); rows not minted", "identity.variant-resource-unavailable")
            continue
        except Exception as exc:
            yield _result(Severity.ERROR, path, f"{ident}: variant resource {locator['resource']!r} failed datapackage verification ({exc})", "identity.variant-resource-invalid")
            continue
        fmt = locator["format"]
        minted = 0
        defects: dict[str, int] = {}
        store_unavailable: str | None = None
        delimiter = "\t" if resource.suffix == ".tsv" else ","
        with resource.open(encoding="utf-8", newline="") as fh:
            for row in csv.DictReader(fh, delimiter=delimiter):
                expr = _row_expr(row, locator, fmt)
                try:
                    result = vrs_id(expr, fmt=fmt, assembly_seqcol=seqcol)
                except (SequenceStoreError, VariantStoreUnavailable) as exc:
                    store_unavailable = str(exc)
                    break
                if isinstance(result, VariantMatch):
                    minted += 1
                else:
                    defects[result.reason] = defects.get(result.reason, 0) + 1
        if store_unavailable is not None:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: variant sequence store unavailable ({store_unavailable}); rows not minted",
                "identity.variant-store-unavailable",
            )
            continue
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

Write `_row_expr`-driven fixture + test, including both cases: (1) a mocked `vrs_id`/tiny store path that yields `minted=1` plus one `ref-mismatch`, and (2) `vrs_id` raising `SequenceStoreError` to prove a fresh checkout with an unbuilt `sequence-store-grch38-grch37` reports `identity.variant-store-unavailable` at INFO instead of crashing. Because `_evaluate_variant_rows` imports `vrs_id` inside the function from `science_tool.commons.variant`, patch `science_tool.commons.variant.vrs_id` in the test; do not patch a name on `validate.checks.variant_identity`. Keep row defects as `Severity.ERROR`: a dataset declaring resolved variant identity is promising row resolvability; only local infrastructure absence (`variant-resource-unavailable`, `variant-store-unavailable`) degrades to INFO.

Run: `cd ~/d/science/science && uv run pytest tests/validate/test_checks_variant_identity.py -v`
Expected: PASS (minted=1, one `ref-mismatch` defect → `identity.variant-rows-unresolved`).

- [ ] **Step 6: Register the check in the canonical loader**

In `science/src/science_tool/validate/checks/__init__.py`, add `"variant_identity"` to `_load_canonical_checks()` after `"dataset_taxonomy"` and before `"prose_lints"`:

```python
        "identity_context",
        "dataset_taxonomy",
        "variant_identity",
        "prose_lints",
```

Update every literal canonical-check mirror in the same commit so bash-vs-Python parity stays current. At the time this plan was written, the known mirrors are:

- `science/tests/validate/test_parity_canonical_body.py::CHECK_MODULES`
- `science/tests/validate/test_parity_corpus.py::CHECK_MODULES`
- `science/tests/validate/test_formatter_snapshots.py::CHECK_MODULES`
- the explicit module tuple in `science/tests/validate/test_runner.py`

Use `rg -n "CHECK_MODULES|for module_name in \\(" science/tests/validate` before committing; any tuple that mirrors canonical modules must include `"variant_identity"` in the same relative position.

- [ ] **Step 7: Verify the check registers at the right order with no collision**

Run: `cd ~/d/science/science && uv run python -c "from science_tool.validate.checks import variant_identity; print('ok')" && uv run pytest tests/validate/ -q`
Expected: `ok`, then the whole validate suite passes (the new check at order 33 collides with nothing and is imported by the canonical loader).

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/validate/checks/variant_identity.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_variant_identity.py science/tests/fixtures
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
    assert next(m for m in manifest if m["name"] == "1")["sha256"].startswith("sha256:")


def test_slice_fasta_preserves_case_for_refget_digest(tmp_path: Path) -> None:
    fasta_path = tmp_path / "softmask.fa"
    fasta_path.write_text(">soft\nACgt\n", encoding="ascii")
    out = tmp_path / "store"
    manifest = slice_fasta_to_store(fasta_path, out)
    digest = refget_digest("ACgt")
    assert len(manifest) == 1
    row = manifest[0]
    assert row["name"] == "soft"
    assert row["refget_digest"] == digest
    assert row["length"] == 4
    assert row["sha256"].startswith("sha256:")
    assert (out / digest).read_text(encoding="ascii") == "ACgt"


def test_slice_fasta_rejects_empty_contig(tmp_path: Path) -> None:
    (tmp_path / "g.fa").write_text(">1\n\n>2\nACGT\n", encoding="ascii")
    with pytest.raises(ValueError, match="empty contig"):
        slice_fasta_to_store(tmp_path / "g.fa", tmp_path / "out")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_sequence_store_build.py -v`
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

import base64
import hashlib
import re
import shutil
from pathlib import Path
from typing import Any

_SAFE = re.compile(r"[^A-Za-z0-9_.-]+")


def _digest_from_hash(h: Any) -> str:
    return "SQ." + base64.urlsafe_b64encode(h.digest()[:24]).decode("ascii").rstrip("=")


def slice_fasta_to_store(fasta_path: Path, out_dir: Path) -> list[dict[str, Any]]:
    """Stream a FASTA into out_dir/<refget_digest>; return the manifest rows."""
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest: list[dict[str, Any]] = []

    name: str | None = None
    tmp: Path | None = None
    handle = None
    h: Any | None = None
    sha256: Any | None = None
    n = 0

    def finish() -> None:
        nonlocal name, tmp, handle, h, sha256, n
        if name is None:
            return
        assert tmp is not None and handle is not None and h is not None and sha256 is not None
        handle.close()
        if n == 0:
            tmp.unlink(missing_ok=True)
            raise ValueError(f"empty contig {name!r} in {fasta_path}")
        digest = _digest_from_hash(h)
        target = out_dir / digest
        tmp.replace(target)
        manifest.append({"name": name, "refget_digest": digest, "length": n, "sha256": f"sha256:{sha256.hexdigest()}"})
        name, tmp, handle, h, sha256, n = None, None, None, None, None, 0

    with Path(fasta_path).open(encoding="ascii") as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                finish()
                name = line[1:].split()[0]
                tmp = out_dir / f".{_SAFE.sub('_', name)}.tmp"
                handle = tmp.open("wb")
                h = hashlib.sha512()
                sha256 = hashlib.sha256()
                n = 0
                continue
            if name is None or handle is None or h is None or sha256 is None:
                raise ValueError(f"FASTA sequence before first header in {fasta_path}")
            chunk = line.encode("ascii")
            handle.write(chunk)
            h.update(chunk)
            sha256.update(chunk)
            n += len(chunk)
    finish()
    return manifest


def fetch_fasta(url: str, dest: Path) -> Path:
    """Stream a (optionally gzipped) FASTA to dest (build-time only)."""
    import gzip
    import httpx

    dest = Path(dest)
    tmp = dest.with_suffix(dest.suffix + ".download")
    with httpx.stream("GET", url, timeout=300.0, follow_redirects=True) as resp:
        resp.raise_for_status()
        with tmp.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)
    if url.endswith(".gz"):
        with gzip.open(tmp, "rb") as src, dest.open("wb") as out:
            shutil.copyfileobj(src, out, length=1024 * 1024)
        tmp.unlink()
    else:
        tmp.replace(dest)
    return dest
```

- [ ] **Step 4: Run it to verify it passes**

Run: `cd ~/d/science/science && uv run pytest tests/test_commons_sequence_store_build.py -v`
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
title: "Reference sequence store (GRCh38 + GRCh37)"
version: "1.0.0"
created: "2026-05-28"
updated: "2026-05-28"
datapackage: datapackage.yaml
origin: external
status: active
tier: use-now
access:
  level: public
  verified: true
source_class: reference
---
Per-contig reference sequence bytes for GRCh38 + GRCh37, content-addressed by
refget digest. Built locally via recipe/build.py; only the manifest of digests is
committed. See ~/d/science/docs/plans/2026-05-28-c4-variant-identity-design.md (C4a-D3).
```

Create `datasets/sequence-store-grch38-grch37/recipe/sources.yaml`:

```yaml
# Pinned, dated genome FASTA releases (immutable handles; latest/ is discovery-only).
# Before running this recipe, build datasets/assembly-registry/contigs.csv.
# Each FASTA must match that assembly's seqcol exactly:
# - no analysis-set extras (alts/decoys/HLA) unless those contigs are in the seqcol;
# - the FASTA header first token must equal contigs.csv "name" for that seqcol.
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
_FIELDS = ["assembly_seqcol_digest", "name", "refget_digest", "length", "sha256"]


def _expected_by_assembly() -> dict[tuple[str, str], str]:
    """Read the assembly-registry contigs.csv produced by the C1/C4a registry build."""
    path = _OUT.parent / "assembly-registry" / "contigs.csv"
    if not path.is_file():
        raise RuntimeError(f"{path}: build assembly-registry/contigs.csv before the sequence store")
    with path.open(encoding="utf-8", newline="") as fh:
        return {
            (row["seqcol_digest"], row["name"]): row["refget_digest"]
            for row in csv.DictReader(fh)
        }


def main() -> None:
    src = yaml.safe_load((_HERE / "sources.yaml").read_text(encoding="utf-8"))
    expected = _expected_by_assembly()
    rows: list[dict] = []
    for asm in src["assemblies"]:
        fasta = fetch_fasta(asm["fasta_url"], _HERE / f"{asm['label']}.fa")
        seen: set[tuple[str, str]] = set()
        for m in slice_fasta_to_store(fasta, _OUT):
            key = (asm["seqcol_digest"], m["name"])
            wanted = expected.get(key)
            if wanted is None:
                raise RuntimeError(
                    f"{key}: no matching assembly-registry contig row; FASTA must use the seqcol naming surface "
                    "and must not include contigs outside that seqcol"
                )
            if wanted != m["refget_digest"]:
                raise RuntimeError(f"{key}: FASTA digest {m['refget_digest']} != registry digest {wanted}")
            seen.add(key)
            rows.append({"assembly_seqcol_digest": asm["seqcol_digest"], **m})
        required = {key for key in expected if key[0] == asm["seqcol_digest"]}
        missing = required - seen
        if missing:
            sample = ", ".join(f"{name}" for _, name in sorted(missing)[:5])
            raise RuntimeError(f"{asm['label']}: FASTA missing {len(missing)} seqcol contigs (examples: {sample})")
        fasta.unlink()
    with (_OUT / "manifest.csv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} contigs + manifest.csv (commit ONLY manifest.csv)")


if __name__ == "__main__":
    main()
```

Create `datasets/sequence-store-grch38-grch37/recipe/README.md` documenting: pinned/verifiable-not-archival caveat; bytes are local-only; commit only `manifest.csv`; rebuild may fail if upstream disappears but a produced store is digest-verified; build `datasets/assembly-registry/contigs.csv` first; the pinned FASTA must match the seqcol contig set and naming exactly (no analysis-set extras unless they are in the seqcol, and header first token equals `contigs.csv` `name`); after building, update `datapackage.yaml`'s `manifest` resource `hash` and `bytes` to match the committed `manifest.csv`. The runtime resolver verifies `manifest.csv` through the normal commons datapackage path before opening the sibling byte files.

- [ ] **Step 6: Extend the assembly-registry recipe + datapackage**

In `~/d/science-commons/datasets/assembly-registry/`: add `contigs` and `contig_aliases` resources to `datapackage.yaml` (placeholder hashes/bytes), add the NCBI assembly-report URLs to `recipe/sources.yaml`, and update `recipe/build.py` to also write `contigs.csv` (via `assembly_registry_build.build_contig_rows` over each fetched level-2 record) and `contig_aliases.csv` (via `assembly_report_build.parse_assembly_report` plus `build_contig_alias_rows`). Do not hand-roll the join in the recipe; the pure helper's unmatched-name failure is the regression guard for alias correctness.

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

Run: `cd ~/d/science/science && uv run pytest tests/ -q`
Expected: PASS (no regressions; new commons + validate tests included).

- [ ] **Step 2: Lint clean**

Run: `cd ~/d/science/science && uv run ruff check src/science_tool/commons/ src/science_tool/validate/checks/variant_identity.py`
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
- §1 scope / accepted inputs → Tasks 8 (SPDI), 9 (HGVS_g, VCF), allele-field symbolic/multiallelic rejection (Task 9 `_parse`). ✓
- §2 contig + alias tables (incl. `sequence_index`, hard duplicate errors) → Tasks 3, 4, 5. ✓
- §3 per-contig refget digests materialized → Task 4; alias source = pinned assembly report with fail-loud seqcol-name join → Task 3 + Task 12 Step 6. ✓
- §4 assemblies by seqcol digest; b37/hs37d5 not aliased → enforced by `resolve_contig`'s assembly-scoped lookup + the registry only pinning exact digests (Task 5, Task 12). ✓
- §5 sequence store, digests-committed/bytes-local, flat refget store, pinned-not-archival, exact-byte refget digest consistency, manifest datapackage verification → Tasks 6, 9, 12. ✓
- §6 offline DataProxy, no-network tested invariant, fail-loud → Task 7. ✓
- §7 dependency spike first; pin pkg + spec version; fallback documented → Tasks 1, 2. ✓
- §8 variant tier convention (no schema change), locator contract, two-layer check (`tier_declaration_defect` not `evaluate_tier_identity`); CSV/TSV only; datapackage-resolved resource; unbuilt sequence store degrades to INFO not crash → Tasks 10, 11. ✓
- §9 fixtures + negatives (ref-mismatch, out-of-bounds, ambiguous alias, symbolic, multiallelic, missing store, accession mismatch) + version-tied golden → Tasks 5, 6, 8, 9, 11. ✓

**Placeholder scan:** The only intentional `REPLACE_WITH_*` tokens are in `~/d/science-commons` recipe `sources.yaml` (pinned digests/URLs an operator fills at build time — the same built-unbuilt pattern as C2/C3) and the captured `_GOLDEN_SNV` (empirically pinned in Task 8 Step 5, not invented). No code step is left as prose.

**Type consistency:** `refget_digest`, `open_store`/`SequenceStore.sequence`, `RefgetProxy.get_sequence/get_metadata`, `compute_vrs_id(proxy, *, fmt, expr)`, `resolve_contig(...) → ContigMatch|AmbiguousContig|AccessionAssemblyMismatch`, `vrs_id(...) → VariantMatch|VariantDefect` (with `VariantStoreUnavailable` reserved for absent local infrastructure), and `tier_declaration_defect` are used consistently across Tasks 5–11.

**Known external-API risk:** the exact `ga4gh.vrs` translator/identify symbols are pinned by the Task 1 spike and isolated in `vrs.py`; every downstream task depends only on our signatures, so a surface difference is absorbed in one module.
