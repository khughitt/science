"""UniProt parsing for the protein crosswalk (Pillar C, C3).

Parses the UniProt idmapping long-format file (one ``accession <TAB> id_type
<TAB> value`` per line) into approved crosswalk rows, and the secondary-accession
file into ``merged`` rows with a forward pointer. Each approved row carries the C2
``gene_key`` built from UniProt's HGNC cross-reference. ``fetch_text`` is the only
network call (build-time only); all parsing is pure. The v1 scope (reviewed
Swiss-Prot, human) is a source-file choice — the parser is source-agnostic (it
emits one row per accession it sees). See
docs/plans/2026-05-26-bio-identity-and-reference-genome-design.md (C-D1/C-D3).
"""

from __future__ import annotations

import csv
import io
from collections import OrderedDict
from typing import Any

from science_tool.commons.gene_crosswalk import make_gene_key
from science_tool.commons.protein_crosswalk import make_protein_key

_HUMAN_TAXON = 9606
_OUT_SEP = ";"  # within-cell multi-value separator; NOT '|' (protein_key uses '|')

# UniProt idmapping id_types this build consumes.
_ID_ENTRY_NAME = "UniProtKB-ID"
_ID_ENSEMBL_PRO = "Ensembl_PRO"
_ID_REFSEQ = "RefSeq"
_ID_HGNC = "HGNC"


def parse_idmapping(dat_text: str) -> list[dict[str, Any]]:
    """Parse the UniProt idmapping long format (tab-separated) into approved rows.

    Groups lines by accession (column 0), collecting the entry name, Ensembl
    protein ids, RefSeq protein ids, and HGNC ids. The HGNC ids become the C2
    ``gene_key`` join via ``make_gene_key``. Multi-valued fields are ';'-joined.
    """
    by_ac: OrderedDict[str, dict[str, Any]] = OrderedDict()
    reader = csv.reader(io.StringIO(dat_text), delimiter="\t")
    for rec in reader:
        if len(rec) != 3:
            continue
        ac, id_type, value = rec[0].strip(), rec[1].strip(), rec[2].strip()
        if not ac or not value:
            continue
        bucket = by_ac.setdefault(ac, {"entry_name": "", "ensembl": [], "refseq": [], "hgnc": []})
        if id_type == _ID_ENTRY_NAME:
            bucket["entry_name"] = value
        elif id_type == _ID_ENSEMBL_PRO:
            bucket["ensembl"].append(value)
        elif id_type == _ID_REFSEQ:
            bucket["refseq"].append(value)
        elif id_type == _ID_HGNC and value.startswith("HGNC:"):
            bucket["hgnc"].append(value)
    rows: list[dict[str, Any]] = []
    for ac, b in by_ac.items():
        gene_keys = [make_gene_key(_HUMAN_TAXON, h) for h in b["hgnc"]]
        rows.append(
            {
                "protein_key": make_protein_key(_HUMAN_TAXON, ac),
                "entry_name": b["entry_name"],
                "ensembl_protein": _OUT_SEP.join(b["ensembl"]),
                "refseq_protein": _OUT_SEP.join(b["refseq"]),
                "gene_key": _OUT_SEP.join(gene_keys),
                "status": "approved",
                "replacement_protein_keys": "",
            }
        )
    return rows


def parse_secondary(sec_text: str, *, primary_keys: set[str]) -> list[dict[str, Any]]:
    """Parse the UniProt secondary-accession file into ``merged`` rows.

    Each data line is two whitespace-separated tokens ``secondary primary``;
    header/preamble lines (other token counts) are skipped. Only secondaries whose
    primary resolves to a known reviewed member (`primary_keys`) become rows — a
    merged secondary is a one-to-one redirect to its primary protein_key.
    """
    rows: list[dict[str, Any]] = []
    for line in sec_text.splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        secondary, primary = parts[0].strip(), parts[1].strip()
        if not secondary or not primary or "|" in secondary or "|" in primary:
            continue
        primary_key = make_protein_key(_HUMAN_TAXON, primary)
        if primary_key not in primary_keys:
            continue
        rows.append(
            {
                "protein_key": make_protein_key(_HUMAN_TAXON, secondary),
                "entry_name": "",
                "ensembl_protein": "",
                "refseq_protein": "",
                "gene_key": "",
                "status": "merged",
                "replacement_protein_keys": primary_key,
            }
        )
    return rows


def build_rows(*, idmapping_text: str, secondary_text: str) -> list[dict[str, Any]]:
    """Merge approved (idmapping) + merged (secondary-accession) rows.

    Secondary rows are restricted to those whose primary is a known approved
    member, so the crosswalk never points a merged row at a missing primary.
    """
    primary = parse_idmapping(idmapping_text)
    primary_keys = {r["protein_key"] for r in primary}
    merged = parse_secondary(secondary_text, primary_keys=primary_keys)
    return primary + merged


def fetch_text(url: str) -> str:
    """Fetch a text release file, transparently gunzipping a gzip body (UniProt
    handles are ``.gz``). Build-time only; never called at resolve time."""
    import gzip

    import httpx

    resp = httpx.get(url, timeout=120.0, follow_redirects=True)
    resp.raise_for_status()
    data = resp.content
    if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
        data = gzip.decompress(data)
    return data.decode("utf-8")
